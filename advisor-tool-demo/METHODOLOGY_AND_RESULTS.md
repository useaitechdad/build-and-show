# Methodology & results

Everything here is self-measured against the live Claude API using the advisor tool beta
(`advisor-tool-2026-03-01`). Quality is graded by code, cost is computed from the real
`usage.iterations` the API returns, and the grand total reconciles to the Anthropic Console bill.

## How the advisor tool works (and how we price it)
Inside one `/v1/messages` request, the executor can call an `advisor` tool. The server runs a
separate inference pass on the advisor model (Opus) over the full transcript and returns a short
plan; the executor continues. Billing is reported per sub-inference in `usage.iterations[]`:
- `type: "message"` → executor tokens, billed at the executor model's rate.
- `type: "advisor_message"` → advisor tokens, billed at the **advisor (Opus) rate**, *separately*.

`_lib.py: accumulate_cost()` sums each across all turns. Rates (per 1M tokens, list, verified
2026-06-15): Haiku 4.5 `$1/$5`, Sonnet 4.6 `$3/$15`, **Opus 4.8 `$5/$25`**. (Using the older
`$15/$75` Opus rate over-estimates ~3× — a real trap; the published numbers here use the verified rate.)

## Test 1 — simple task: thread-safe bounded worker pool with graceful shutdown
- 3 configs × 5 runs: Sonnet solo · Sonnet+Opus advisor · Opus solo.
- Each model writes one module; a deterministic verifier (`verify_pool.py`) stress-tests it in a
  timeout'd subprocess (a hang = deadlock) — submit 60 tasks, trigger shutdown mid-flight, assert no
  task lost, concurrency cap respected, clean join.
- **Result:** all three pass 5/5. Cost: Sonnet $0.025 · Opus $0.043 · **advisor $0.105 (4.3×)**.
  The advisor adds Opus tokens on top of a task the executor already solves → pure overhead.

## Test 2 — agentic task: build a mini-SQL query engine
- A real multi-turn agent loop (`ag_agent.py`) with `read_file` / `write_file` / `run_tests` tools.
  The executor builds `solution.py` over up to 16 turns, iterating against **visible** tests.
- Graded on **16 hidden** SQL queries it never sees, by comparing its output to a correct reference
  **oracle** (`sql_ref.py`, never shown to the model) — so a model that overfits the visible set is
  caught on precedence, multi-key `ORDER BY`, `GROUP BY` aggregates, short-circuit booleans, etc.
- Executor = **Haiku** on purpose (so the advisor has room to help); advisor capped at `max_uses: 2`.
- **Result (N=5):** Haiku solo **98.8%** @ $0.22 · Haiku+advisor **90.0%** @ $0.65 · Opus solo 100% @ $0.36.
  The advisor *lowered* Haiku's quality (its mid-task reviews triggered rewrites that broke working
  code) and cost **more than just using Opus**.

### Why it backfired
- Each advisor call re-ships the whole growing transcript at Opus rates.
- In beta it over-consults (1–3 calls/task even with `max_uses: 2`).
- Its second-guessing pushed a capable-enough executor into churn.

### A note on the difficulty probe (a variance lesson)
A single Haiku run scored 12/16 on the SQL task, which looked like "outmatched." At N=5 Haiku
actually averaged 98.8% — the probe was a noisy low draw. Single runs mislead; the headline numbers
are N=5.

## Fairness — where the advisor *does* win (not reproduced here)
Anthropic's published gains are on tasks where the cheap model is near-helpless solo: SWE-bench
Multilingual (Sonnet+advisor 72.1%→74.8%, −11.9% cost) and **BrowseComp (Haiku 19.7%→41.2%)**. Those
are real — and the common thread is an executor genuinely over its head. Our tasks weren't that
extreme. The honest takeaway isn't "the advisor is bad," it's: **it only pays when your model is
truly outmatched — and most everyday work isn't.**

## What this does NOT prove
- Not a verdict on Anthropic's benchmark regime (we didn't run SWE-bench/BrowseComp).
- Beta behavior; will change. Re-run on your workload.
- List-rate pricing, no caching/batch; single-machine; N=5.
