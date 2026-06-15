# Sub-agents vs. one big context

**Finding:** on the same task — read six noisy incident logs and find the single most
common root cause — sub-agents kept the **lead agent's context 83× leaner** (262 vs
21,781 tokens) and reached the **identical** conclusion. The catch: they used slightly
**more** total tokens (22,230 vs 21,781). The win isn't fewer tokens — it's a clean root
context that doesn't rot.

This is the demo behind the *Use AI with Tech Dad* video on sub-agents.

## What it measures

The same task is answered two ways, and we count the **root (orchestrator) context** —
the tokens the lead agent has to hold — in each:

1. **Inline** — one agent stuffs all six full logs into its own context window.
2. **Sub-agents** — a lead agent hands each log to a sub-agent with its **own clean
   window**; each sub-agent reads one log and returns a 1–2 sentence summary. The lead
   only ever sees the summaries.

The root window is the thing that fills up and degrades ("context rot") as an agent runs
for many turns — so keeping it small is the whole point of sub-agents.

## The result (real run, Gemini 3 Flash)

```
ROOT CONTEXT   inline 21,781   sub-agents    262   -> 83x leaner
TOTAL TOKENS   inline 21,781   sub-agents 22,230   (about the same)
```

Both approaches concluded: **database connection-pool exhaustion** (4 of 6 incidents),
service **checkout-api**. Raw numbers in [`results/demo_run.json`](./results/demo_run.json).

## Run it yourself

The six incident reports are synthetic and bundled in the script, so it's fully
self-contained. It calls a real model, so you need a Gemini API key (the calls bill to
**your** key, never a shared one):

```bash
pip install -r requirements.txt
export GEMINI_API_KEY=your_key_here
python3 subagent_demo.py
```

Swap in any other provider's SDK and the pattern is identical — this isn't specific to
one model.

## The honest caveat

Sub-agents do **not** reduce total token usage — here they cost a little more, because the
logs still get read, just inside separate windows. What you buy is a lean, clean lead
context: the expensive reading is isolated, so the orchestrator can keep working across
many turns without drowning in its own history. Use sub-agents when a subtask is **big,
noisy, or parallel** (searching a codebase, reading logs, scraping pages) — not to save
tokens.

See [`METHODOLOGY_AND_RESULTS.md`](./METHODOLOGY_AND_RESULTS.md) for the full method and
limits.
