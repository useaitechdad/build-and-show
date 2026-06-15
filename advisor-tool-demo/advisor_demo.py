"""Advisor-tool build-and-show: does a cheap executor + a smart advisor reach
expensive-model quality on a plan-sensitive coding task, at a fraction of the cost?

Runs N attempts of one task (a bounded worker pool with graceful shutdown) across
three configs -- Sonnet solo, Sonnet + Opus advisor, Opus solo -- verifying each
candidate in a timeout'd subprocess (a hang = DEADLOCK) and pricing each run from
the REAL usage.iterations the API returns.

    python3 advisor_demo.py --n 5
    python3 advisor_demo.py --dry          # 1 run, sonnet_solo only (pipeline check)

Captures, per advisor run, the verbatim advisor plan and the executor's text
before/after it fired -- the "show the concept" material for the video.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time

from _lib import load_key, call_messages, summarize_usage
from pool_task import TASK, CONFIGS

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(HERE, "results")
RUNS_DIR = os.path.join(RESULTS, "runs")
VERIFY_TIMEOUT = 30  # seconds; a graceful-shutdown that hangs past this = deadlock

# --- Pricing (USD per 1M tokens). PUBLIC LIST RATES -- VERIFY before publishing. ---
# Surfaced on screen, so these must be confirmed against anthropic.com/pricing.
PRICES = {
    "claude-sonnet-4-6": {"input": 3.00, "output": 15.00},
    "claude-opus-4-8":   {"input": 5.00, "output": 25.00},
}
PRICES_SOURCE = "list rates per 1M tok, verified platform.claude.com/docs pricing 2026-06-15"


def extract_code(text):
    blocks = re.findall(r"```(?:python)?\s*\n(.*?)```", text, re.DOTALL)
    if not blocks:
        return None
    return max(blocks, key=len).strip()


def split_content(content):
    """Return (pre_text, advisor_plans, post_text, advisor_fired)."""
    pre, post, plans = [], [], []
    seen_advisor = False
    for b in content:
        t = b.get("type")
        if t == "advisor_tool_result":
            seen_advisor = True
            c = b.get("content", {})
            if c.get("type") == "advisor_result":
                plans.append(c.get("text", ""))
            else:
                plans.append(f"[{c.get('type')}]")
        elif t == "text":
            (post if seen_advisor else pre).append(b.get("text", ""))
    return "\n".join(pre).strip(), plans, "\n".join(post).strip(), seen_advisor


def price_run(usage):
    """Cost in USD from real usage.iterations, split executor vs advisor."""
    execu = adv = 0.0
    for it in usage.get("iterations", []):
        if it.get("type") == "advisor_message":
            p = PRICES[it.get("model", "claude-opus-4-8")]
            adv += it.get("input_tokens", 0) / 1e6 * p["input"]
            adv += it.get("output_tokens", 0) / 1e6 * p["output"]
        elif it.get("type") == "message":
            # executor model priced from the top-level config (set by caller)
            it["_is_executor"] = True
    return execu, adv  # executor filled in by caller (needs the model id)


def cost_usd(usage, executor_model):
    execu = adv = 0.0
    for it in usage.get("iterations", []):
        if it.get("type") == "advisor_message":
            p = PRICES[it.get("model", "claude-opus-4-8")]
            adv += it.get("input_tokens", 0) / 1e6 * p["input"] + it.get("output_tokens", 0) / 1e6 * p["output"]
        elif it.get("type") == "message":
            p = PRICES[executor_model]
            execu += it.get("input_tokens", 0) / 1e6 * p["input"] + it.get("output_tokens", 0) / 1e6 * p["output"]
    return round(execu, 6), round(adv, 6)


def verify(candidate_path, trace_path):
    try:
        out = subprocess.run(
            [sys.executable, os.path.join(HERE, "verify_pool.py"),
             candidate_path, trace_path],
            capture_output=True, text=True, timeout=VERIFY_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        return {"passed": False, "reason": "DEADLOCK", "detail": f"shutdown did not return within {VERIFY_TIMEOUT}s"}
    try:
        return json.loads(out.stdout.strip().splitlines()[-1])
    except Exception:
        return {"passed": False, "reason": "verifier_crash",
                "stdout": out.stdout[-500:], "stderr": out.stderr[-500:]}


def run_one(key, config_key, idx):
    cfg = CONFIGS[config_key]
    body = {
        "model": cfg["model"],
        "max_tokens": 8192,
        "system": cfg["system"],
        "tools": cfg["tools"],
        "messages": [{"role": "user", "content": TASK + cfg["user_suffix"]}],
    }
    print(f"\n  [{cfg['label']}] run {idx+1}  ({cfg['model']})")
    t0 = time.time()
    status, resp = call_messages(key, body)
    elapsed = round(time.time() - t0, 1)
    if status != 200:
        print(f"    ✗ HTTP {status}: {json.dumps(resp)[:300]}")
        return {"config": config_key, "run": idx, "error": f"http_{status}", "resp": resp}

    content = resp.get("content", [])
    pre, plans, post, fired = split_content(content)
    code = extract_code(post or pre or "")
    usage = resp.get("usage", {})
    split = summarize_usage(usage)
    execu_cost, adv_cost = cost_usd(usage, cfg["model"])

    if fired:
        plan_preview = (plans[0][:220] + "…") if plans and len(plans[0]) > 220 else (plans[0] if plans else "")
        print(f"    ⏸  executor paused — phoned the advisor (Opus 4.8)")
        print(f"    💡 advisor: {plan_preview.strip()}")
        print(f"    ▶  executor resumed with the plan")

    # write candidate + verify
    os.makedirs(os.path.join(RUNS_DIR, config_key), exist_ok=True)
    cand_path = os.path.join(RUNS_DIR, config_key, f"run{idx+1}_candidate.py")
    trace_path = os.path.join(RUNS_DIR, config_key, f"run{idx+1}_trace.jsonl")
    if code:
        open(cand_path, "w").write(code)
        verdict = verify(cand_path, trace_path)
    else:
        verdict = {"passed": False, "reason": "no_code_block",
                   "stop_reason": resp.get("stop_reason")}

    mark = "✓ PASS" if verdict.get("passed") else f"✗ FAIL ({verdict.get('reason')})"
    print(f"    {mark}   advisor_calls={split['advisor_calls']}  "
          f"exec_out={split['executor_output_tokens']}  adv_out={split['advisor_output_tokens']}  "
          f"cost=${execu_cost+adv_cost:.4f}  {elapsed}s")

    # save transcript for the deck (only worth keeping when advisor fired or it's a clean example)
    transcript = {
        "config": config_key, "run": idx, "model": cfg["model"],
        "advisor_fired": fired, "advisor_plans": plans,
        "executor_pre_text": pre, "executor_post_text": post,
    }
    open(os.path.join(RUNS_DIR, config_key, f"run{idx+1}_transcript.json"), "w").write(
        json.dumps(transcript, indent=2))

    return {
        "config": config_key, "label": cfg["label"], "model": cfg["model"], "run": idx,
        "advisor_fired": fired, "passed": verdict.get("passed"), "reason": verdict.get("reason"),
        "verdict": verdict, "tokens": split, "stop_reason": resp.get("stop_reason"),
        "executor_cost_usd": execu_cost, "advisor_cost_usd": adv_cost,
        "total_cost_usd": round(execu_cost + adv_cost, 6),
        "elapsed_secs": elapsed,
        "candidate_path": cand_path if code else None,
        "trace_path": trace_path if code else None,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=5)
    ap.add_argument("--configs", default="sonnet_solo,advisor,opus_solo")
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()

    configs = ["sonnet_solo"] if args.dry else args.configs.split(",")
    n = 1 if args.dry else args.n
    key = load_key()
    os.makedirs(RUNS_DIR, exist_ok=True)
    print(f"key {len(key)} chars | configs={configs} | n={n} | pricing={PRICES_SOURCE}")

    all_runs = []
    for ck in configs:
        for i in range(n):
            all_runs.append(run_one(key, ck, i))

    # --- aggregate ---
    summary = {}
    for ck in configs:
        rs = [r for r in all_runs if r.get("config") == ck and "passed" in r]
        if not rs:
            continue
        passes = sum(1 for r in rs if r["passed"])
        costs = [r["total_cost_usd"] for r in rs]
        summary[ck] = {
            "label": CONFIGS[ck]["label"], "model": CONFIGS[ck]["model"],
            "runs": len(rs), "passed": passes, "pass_rate": round(passes / len(rs), 3),
            "mean_cost_usd": round(sum(costs) / len(costs), 6),
            "mean_total_tokens": round(sum(r["tokens"]["executor_output_tokens"] +
                                           r["tokens"]["advisor_output_tokens"] for r in rs) / len(rs)),
            "fail_reasons": sorted({r["reason"] for r in rs if not r["passed"]}),
        }

    out = {"pricing": PRICES, "pricing_source": PRICES_SOURCE,
           "verify_params": {"num_workers": 4, "max_queue": 8, "total_jobs": 60,
                             "timeout_secs": VERIFY_TIMEOUT},
           "summary": summary, "runs": all_runs}
    open(os.path.join(RESULTS, "demo_run.json"), "w").write(json.dumps(out, indent=2))

    print("\n" + "=" * 64)
    for ck, s in summary.items():
        print(f"{s['label']:24s} pass {s['passed']}/{s['runs']}  "
              f"mean ${s['mean_cost_usd']:.4f}/run  fails={s['fail_reasons']}")
    print("=" * 64)
    print(f"saved → {os.path.join(RESULTS, 'demo_run.json')}")


if __name__ == "__main__":
    main()
