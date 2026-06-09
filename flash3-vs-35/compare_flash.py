#!/usr/bin/env python3
"""
compare_flash.py — side-by-side Gemini 3 Flash vs 3.5 Flash on multi-turn tasks.

Spine: THOUGHT PRESERVATION. 3.5 Flash automatically carries its intermediate
reasoning across turns; 3 Flash re-derives each turn. We run the SAME chat
conversation through both models and capture, per turn:
  - the answer text
  - thinking-token count (thoughtsTokenCount) + total tokens
  - latency
  - any thought summary the API returns (include_thoughts=True)

Models are run AS SHIPPED (default thinking levels: 3 Flash = high, 3.5 = medium)
so the comparison reflects what a developer actually gets out of the box.

Usage:
  python3 compare_flash.py                 # run all scenarios, both models
  python3 compare_flash.py --scenario debug_refactor
  python3 compare_flash.py --env /path/to/.env
  python3 compare_flash.py --scenario long_horizon --runs 5 --language Python

Requires: pip install google-genai ; and a GEMINI_API_KEY (env var or a local .env).
"""

import argparse
import json
import os
import re
import time
from pathlib import Path

from google import genai
from google.genai import types

ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = ROOT / "results"

MODELS = [
    ("flash3", "gemini-3-flash-preview"),
    ("flash35", "gemini-3.5-flash"),
]

# Each scenario is a list of sequential USER turns. The payoff turns deliberately
# depend on reasoning the model produced in EARLIER turns without restating it —
# that is where thought preservation should separate 3.5 from 3.
SCENARIOS = {
    # The spine demo: an early root-cause analysis must survive to the final turn.
    "debug_refactor": [
        # Turn 1 — force an intermediate decision, but forbid the fix.
        "Here is a Python function:\n\n"
        "```python\n"
        "def dedupe_keep_order(items):\n"
        "    seen = {}\n"
        "    out = []\n"
        "    for i in items:\n"
        "        if i not in seen:\n"
        "            seen[i] = True\n"
        "        out.append(i)\n"
        "    return out\n"
        "```\n\n"
        "Find the single root-cause bug and explain WHY it happens. "
        "Do NOT rewrite the code yet — just the root cause, in 2-3 sentences.",
        # Turn 2 — add a constraint that interacts with the (unrestated) root cause.
        "Good. New constraint: items can now include unhashable values like lists. "
        "Without writing code yet, explain how that constraint interacts with the "
        "specific bug you identified a moment ago.",
        # Turn 3 — the payoff: requires BOTH earlier reasoning threads, none restated.
        "Now write the final corrected function that satisfies everything we've "
        "discussed. Then list, as bullet points, each decision you carried over "
        "from our earlier turns.",
    ],
    # The HARD long-horizon test. Turn 1 sets four non-obvious invariants; turns
    # 2-6 pile on features + distractions without restating them; turn 7 (payoff)
    # requires ALL of them to survive with nothing restated. Objectively scorable:
    # check the final class for each invariant.
    "long_horizon": [
        # Turn 1 — establish 4 quirky, easy-to-forget invariants.
        "We're building an in-memory EventStore, incrementally, over several "
        "messages. Lock in these NON-NEGOTIABLE rules for the whole session, then "
        "just acknowledge them in one line:\n"
        "  (R1) event IDs are 64-bit SIGNED integers (negatives are legal),\n"
        "  (R2) events can arrive OUT OF ORDER,\n"
        "  (R3) duplicate IDs must be silently rejected,\n"
        "  (R4) the system clock may jump BACKWARDS, so never assume time is monotonic.",
        # Turn 2 — distraction feature.
        "Add a feature: query all events whose timestamp falls in a [start, end] range.",
        # Turn 3 — distraction feature.
        "Add a feature: let callers subscribe to be notified of newly accepted events.",
        # Turn 4 — probe (no new rule, just keeps the model busy).
        "What's the time complexity of your duplicate-rejection check as currently designed?",
        # Turn 5 — distraction feature.
        "Add a feature: snapshot the entire store to a JSON-serializable dict and reload from it.",
        # Turn 6 — extend one invariant late.
        "Curveball: introduce 'tombstoning' — an event ID can be deleted, and once "
        "tombstoned it must NEVER be accepted again, even if it reappears.",
        # Turn 7 — payoff: everything must survive, nothing restated.
        "Now write the FINAL EventStore class implementing everything we've discussed. "
        "Then, as a numbered list, restate every invariant and every feature we agreed "
        "on across this whole conversation, in the order they came up.",
    ],
    # A control: single hard one-shot (no multi-turn memory involved).
    "oneshot_reasoning": [
        "A bat and a ball cost $1.10 in total. The bat costs $1.00 more than the "
        "ball. A pencil costs half what the ball costs. How much do TWO balls and "
        "THREE pencils cost together? Show the key step, then give the final number.",
    ],
}


def run_scenario(client, model_id, turns, thinking_level=None):
    """Run one scenario through one model as a single chat; capture per-turn data.

    thinking_level=None  -> as shipped (model default).
    thinking_level="high"/"medium"/... -> pin both models to the same effort
    (control run that isolates capability from how-much-it-was-allowed-to-think).
    """
    tcfg = types.ThinkingConfig(include_thoughts=True)
    if thinking_level:
        tcfg.thinking_level = thinking_level
    chat = client.chats.create(
        model=model_id,
        config=types.GenerateContentConfig(thinking_config=tcfg),
    )
    turn_records = []
    for idx, user_msg in enumerate(turns, start=1):
        t0 = time.time()
        resp = chat.send_message(user_msg)
        latency = round(time.time() - t0, 2)

        answer, thoughts = [], []
        cand = resp.candidates[0] if resp.candidates else None
        if cand and cand.content and cand.content.parts:
            for p in cand.content.parts:
                if getattr(p, "text", None):
                    (thoughts if getattr(p, "thought", False) else answer).append(p.text)

        um = resp.usage_metadata
        turn_records.append({
            "turn": idx,
            "user": user_msg,
            "answer": "".join(answer).strip(),
            "thought_summary": "".join(thoughts).strip(),
            "latency_s": latency,
            "thinking_tokens": getattr(um, "thoughts_token_count", None) if um else None,
            "output_tokens": getattr(um, "candidates_token_count", None) if um else None,
            "total_tokens": getattr(um, "total_token_count", None) if um else None,
        })
        print(f"    turn {idx}: {latency}s, "
              f"think={turn_records[-1]['thinking_tokens']} tok, "
              f"out={turn_records[-1]['output_tokens']} tok")
    return turn_records


# Python-specific depth markers for the long_horizon final class. Python has no
# native int64, so enforcing R1 REQUIRES an explicit bound — a clean discriminator.
def score_turn7(answer: str) -> dict:
    a = answer
    low = a.lower()
    r1 = bool(re.search(r"2\s*\*\*\s*63|9223372036854775|1\s*<<\s*63", a)) and \
        any(k in low for k in ["raise", "valueerror", "overflow"])
    f3 = "base64" in low
    idx = low.find("from_snapshot")
    region = low[idx: idx + 1500] if idx >= 0 else ""
    tomb = ("tombston" in region) and any(k in region for k in ["continue", "skip", "not in", "drop", "if "])
    return {"r1_enforced": r1, "snapshot_base64": f3, "tombstone_on_reload": tomb}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", help="run only this scenario key")
    ap.add_argument("--thinking_level", help="pin BOTH models to this level (e.g. high) — control run")
    ap.add_argument("--runs", type=int, default=1, help="repeat each (model,scenario) N times for stats")
    ap.add_argument("--language", help="pin the implementation language (kills the language confound)")
    ap.add_argument("--env", default=".env",
                    help="path to a .env with GEMINI_API_KEY (or just set it in your environment)")
    args = ap.parse_args()

    # Load GEMINI_API_KEY from a local .env if present; otherwise use the environment.
    if os.path.exists(args.env):
        for line in Path(args.env).read_text().splitlines():
            if line.startswith("GEMINI_API_KEY="):
                os.environ["GEMINI_API_KEY"] = line.split("=", 1)[1].strip()
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise SystemExit("GEMINI_API_KEY not found (set it or pass --env).")

    client = genai.Client(api_key=api_key)
    scenarios = {args.scenario: SCENARIOS[args.scenario]} if args.scenario else SCENARIOS
    RESULTS_DIR.mkdir(exist_ok=True)

    lvl = args.thinking_level
    suffix = f"_think-{lvl}" if lvl else ""
    if args.runs > 1:
        suffix += f"_x{args.runs}"
    for sname, turns in scenarios.items():
        # Pin language to remove the language-choice confound.
        if args.language:
            turns = list(turns)
            turns[0] += f"\n\n(All code in this session must be written in {args.language}.)"
        print(f"\n=== scenario: {sname} ({len(turns)} turn(s)) x{args.runs}"
              f"{f' @ thinking_level={lvl}' if lvl else ' @ as-shipped defaults'}"
              f"{f' [{args.language}]' if args.language else ''} ===")
        out = {"scenario": sname, "turns": len(turns), "thinking_level": lvl or "default",
               "language": args.language, "runs": args.runs, "models": {}}
        for label, model_id in MODELS:
            print(f"  model: {model_id}")
            runs_data, scores = [], []
            for r in range(1, args.runs + 1):
                print(f"   run {r}/{args.runs}")
                tr = run_scenario(client, model_id, turns, thinking_level=lvl)
                runs_data.append(tr)
                if sname == "long_horizon":
                    sc = score_turn7(tr[-1]["answer"])
                    scores.append(sc)
                    print(f"     markers: {sc}")
            entry = {"model_id": model_id, "runs_data": runs_data}
            if scores:
                n = len(scores)
                entry["marker_rates"] = {
                    k: f"{sum(1 for s in scores if s[k])}/{n}" for k in scores[0]
                }
            out["models"][label] = entry
        dest = RESULTS_DIR / f"{sname}{suffix}.json"
        dest.write_text(json.dumps(out, indent=2))
        print(f"  → saved {dest}")
        # Print the headline comparison.
        if out["models"].get("flash3", {}).get("marker_rates"):
            print("\n  MARKER HIT-RATES (Python, as-shipped):")
            for k in out["models"]["flash3"]["marker_rates"]:
                print(f"    {k:24s}  3 Flash {out['models']['flash3']['marker_rates'][k]}"
                      f"   |   3.5 Flash {out['models']['flash35']['marker_rates'][k]}")


if __name__ == "__main__":
    main()
