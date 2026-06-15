#!/usr/bin/env python3
"""
Sub-agents vs. one big context — a measurable demo.

The same task ("read 6 noisy incident reports and find the single most common
root cause") is answered two ways:

  1. INLINE  — one agent stuffs all 6 full reports into its own context window.
  2. SUB-AGENTS — a lead agent delegates each report to a sub-agent with its OWN
     clean window; each sub-agent returns a 1-2 sentence summary. The lead only
     ever sees the short summaries.

We measure the ROOT (orchestrator) context — the tokens the lead agent has to
hold — in each approach. That root window is the thing that rots as an agent
runs for many turns, so keeping it small is the whole point of sub-agents.

Total tokens are roughly similar either way (the reports still get read, just in
isolated windows). The win is a lean, clean root context — not fewer tokens.

Runs on a real model (Gemini 3 Flash). Reads GEMINI_API_KEY from the environment.
"""
import os
import sys
import json
import time

from google import genai

MODEL = "gemini-3-flash-preview"
TASK = (
    "You are triaging production incidents. Across the incident report(s) provided, "
    "identify the SINGLE most common underlying root cause and name the service involved "
    "most often. Answer in 2-3 sentences."
)
SUBAGENT_INSTR = (
    "Read this ONE incident report and extract only what matters for finding the most "
    "common root cause across many incidents: the root cause and the service involved. "
    "Reply in at most 2 short sentences. Be terse."
)

# --- 6 noisy incident reports (synthetic; bundled so the demo is self-contained) ---
# Real sub-agent workloads read large, noisy artifacts (logs, traces, code). To stay
# faithful to that, each report carries a realistic volume of routine log lines around
# the few that actually matter — exactly the noise a sub-agent reads so the lead doesn't.
_NOISE = [
    "{ts} {svc} INFO  healthcheck ok rps={rps} p99={p}ms inflight={inf}",
    "{ts} {svc} INFO  GET /v1/health 200 1ms",
    "{ts} {svc} DEBUG cache hit key=sess:{rps} ttl=300",
    "{ts} {svc} INFO  span trace_id=8f2a{inf} dur={p}ms ok",
    "{ts} {svc} DEBUG pool stats active={inf} idle={rps} waiters=0",
    "{ts} {svc} INFO  POST /v1/event 202 {p}ms",
    "{ts} {svc} DEBUG metrics flushed n={rps} sink=otlp ok",
    "{ts} {svc} INFO  config reload no-op generation={inf}",
]
def _log(service, lines):
    noise = []
    for i in range(90):
        t = _NOISE[i % len(_NOISE)]
        noise.append(t.format(
            ts=f"2026-06-1{2 + i % 6} {(i % 24):02d}:{(i * 7 % 60):02d}:{(i * 13 % 60):02d}",
            svc=service, rps=40 + i % 60, p=30 + i % 90, inf=i % 50))
    return "\n".join(noise[:45] + lines + noise[45:])

REPORTS = [
    ("INC-4471", "checkout-api", _log("checkout-api", [
        "2026-06-13 02:11:42 checkout-api WARN  db pool exhausted (50/50) waiters=37",
        "2026-06-13 02:11:43 checkout-api ERROR connection acquire timeout after 5000ms",
        "2026-06-13 02:11:43 checkout-api ERROR upstream payments-svc 503",
        "Postmortem: A traffic spike during a flash sale exhausted the checkout-api database "
        "connection pool (max 50). Requests queued waiting for a connection and timed out. "
        "Root cause: connection pool exhaustion under load; the pool size was never tuned for "
        "peak traffic. Remediation: raised pool to 200, added a queue-depth alert.",
    ])),
    ("INC-4488", "search-svc", _log("search-svc", [
        "2026-06-14 09:02:10 search-svc WARN  GC pause 1.8s heap=7.9G/8G",
        "2026-06-14 09:02:12 search-svc ERROR OOMKilled container restarted",
        "Postmortem: search-svc ran out of memory after a deploy doubled the in-memory cache "
        "without raising the container limit. Root cause: memory limit too low for the new "
        "cache size; effectively a resource-limit misconfiguration. Remediation: raised limit, "
        "added heap headroom alerting.",
    ])),
    ("INC-4502", "payments-svc", _log("payments-svc", [
        "2026-06-15 14:20:01 payments-svc WARN  db pool 48/50",
        "2026-06-15 14:20:03 payments-svc ERROR acquire timeout; retrying",
        "2026-06-15 14:20:04 payments-svc ERROR settlement batch stalled",
        "Postmortem: A nightly settlement batch opened long-lived transactions that held database "
        "connections, starving live traffic. Root cause: connection pool exhaustion caused by the "
        "batch holding connections; pool contention between batch and online paths. Remediation: "
        "separate pool for batch, shorter transactions.",
    ])),
    ("INC-4519", "notif-svc", _log("notif-svc", [
        "2026-06-16 03:30:00 notif-svc WARN  retry storm to email provider",
        "2026-06-16 03:30:05 notif-svc ERROR provider 429 rate limited",
        "Postmortem: A misconfigured retry policy (no backoff) turned a brief email-provider blip "
        "into a self-inflicted retry storm. Root cause: missing exponential backoff. Remediation: "
        "added jittered backoff and a circuit breaker.",
    ])),
    ("INC-4530", "checkout-api", _log("checkout-api", [
        "2026-06-17 11:05:21 checkout-api WARN  db pool 50/50 waiters=22",
        "2026-06-17 11:05:23 checkout-api ERROR connection acquire timeout",
        "Postmortem: A slow query (missing index) held connections far longer than normal, and "
        "the checkout-api connection pool filled up and timed out. Root cause: connection pool "
        "exhaustion, triggered this time by a slow unindexed query. Remediation: added the index, "
        "raised pool, added slow-query alerting.",
    ])),
    ("INC-4544", "inventory-svc", _log("inventory-svc", [
        "2026-06-18 19:44:02 inventory-svc WARN  db pool 49/50",
        "2026-06-18 19:44:04 inventory-svc ERROR acquire timeout waiters=15",
        "Postmortem: A deploy cut the inventory-svc connection pool size by half via a bad config "
        "default, and normal traffic exhausted it. Root cause: connection pool exhaustion from a "
        "config regression that shrank the pool. Remediation: restored pool size, added a config "
        "guardrail test.",
    ])),
]


def count_tokens(client, text):
    return client.models.count_tokens(model=MODEL, contents=text).total_tokens


def generate(client, text):
    r = client.models.generate_content(model=MODEL, contents=text)
    return r.text.strip()


def run_inline(client):
    """One agent, all six full reports in a single context window."""
    blob = "\n\n".join(f"=== {iid} ({svc}) ===\n{body}" for iid, svc, body in REPORTS)
    prompt = f"{TASK}\n\nINCIDENT REPORTS:\n\n{blob}"
    root_tokens = count_tokens(client, prompt)
    answer = generate(client, prompt)
    return {"root_context_tokens": root_tokens, "total_tokens": root_tokens, "answer": answer}


def run_subagents(client):
    """Lead delegates each report to a sub-agent with its own clean window."""
    total = 0
    summaries = []
    for iid, svc, body in REPORTS:
        sub_prompt = f"{SUBAGENT_INSTR}\n\nINCIDENT REPORT {iid}:\n\n{body}"
        total += count_tokens(client, sub_prompt)          # spent inside the sub-agent's window
        summary = generate(client, sub_prompt)
        summaries.append(f"{iid} ({svc}): {summary}")
    # The lead only ever sees the short summaries — this is its root context.
    lead_prompt = f"{TASK}\n\nSUB-AGENT SUMMARIES:\n\n" + "\n".join(summaries)
    root_tokens = count_tokens(client, lead_prompt)
    total += root_tokens
    answer = generate(client, lead_prompt)
    return {"root_context_tokens": root_tokens, "total_tokens": total,
            "answer": answer, "summaries": summaries}


def main():
    key = os.getenv("GEMINI_API_KEY", "")
    if not key:
        sys.exit("GEMINI_API_KEY not set in the environment.")
    client = genai.Client(api_key=key)

    print("\n  SUB-AGENTS vs ONE BIG CONTEXT  ·  6 noisy incident reports\n")
    print("  [1/2] INLINE — one agent reads all 6 full reports ...")
    inline = run_inline(client)
    print(f"        root context: {inline['root_context_tokens']:,} tokens")

    print("  [2/2] SUB-AGENTS — 6 clean windows, lead sees only summaries ...")
    sub = run_subagents(client)
    print(f"        root context: {sub['root_context_tokens']:,} tokens\n")

    ratio = inline["root_context_tokens"] / max(1, sub["root_context_tokens"])
    same = inline["answer"].split(".")[0].lower(), sub["answer"].split(".")[0].lower()

    print("  " + "-" * 54)
    print(f"  ROOT CONTEXT   inline {inline['root_context_tokens']:>7,}   "
          f"sub-agents {sub['root_context_tokens']:>6,}   -> {ratio:.1f}x leaner")
    print(f"  TOTAL TOKENS   inline {inline['total_tokens']:>7,}   "
          f"sub-agents {sub['total_tokens']:>6,}   (similar work)")
    print("  " + "-" * 54)
    print("\n  INLINE answer:\n   " + inline["answer"].replace("\n", " "))
    print("\n  SUB-AGENTS answer:\n   " + sub["answer"].replace("\n", " "))
    print("\n  Same conclusion:", "YES" if "pool" in sub["answer"].lower()
          and "pool" in inline["answer"].lower() else "compare above")
    print()

    out = {
        "model": MODEL,
        "task": TASK,
        "n_reports": len(REPORTS),
        "inline": inline,
        "subagents": sub,
        "root_context_ratio": round(ratio, 2),
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results", "demo_run.json")
    with open(path, "w") as f:
        json.dump(out, f, indent=2)
    print(f"  saved -> {path}\n")


if __name__ == "__main__":
    main()
