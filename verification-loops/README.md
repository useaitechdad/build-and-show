# Verification loops: does making an AI agent check its work make it reliable?

Short answer from this repo: **trusting an agent's unchecked answer is a coin flip — and the fix
is a loop, not a smarter model. But a *simpler* check beat a fancier one.**

Same model (Claude Haiku 4.5), same task (build a mini-SQL query engine from scratch), 5 runs each
under three modes, all graded on **16 hidden tests the model never sees**:

| Mode | What the agent can do | Hidden score (mean) | Perfect runs | Notes |
|---|---|---|---|---|
| **Trust it** | write code, stop when confident — *never runs anything* | **92.5%** | **2 / 5** | worst run 13/16; confident but wrong |
| **Test it** | run the example tests, fix failures, repeat | **100%** | **5 / 5** | the boring check — flawless |
| **Verify it** | a differential verifier hammers it vs an oracle, fix, repeat | **80%** | **4 / 5** | one run shipped broken code (**0/16**) |

The takeaway isn't "add a fancy verifier." It's: **don't trust the model's word — give it a check it
can act on, in a loop.** More checking isn't automatically better (the differential verifier sent one
run into a rewrite spiral it never recovered from). *LLM proposes; deterministic code disposes.*

## Run it yourself

Pure Python standard library — no installs. You need an Anthropic API key:

```bash
export ANTHROPIC_API_KEY=sk-ant-...        # or put it in a local .env file
python3 run_demo.py --n 5                   # ~$2-3 of Haiku usage at list rates
```

Results (per-run + summary) land in `results/verify_run.json`. Useful flags:

```bash
python3 run_demo.py --n 5 --modes trust,test,verify
python3 run_demo.py --n 3 --model claude-haiku-4-5-20251001
```

No key needed to inspect what was measured — `results/verify_run.json` holds the exact run from the video.

## How it works

- **`task.py`** — the spec, plus three disjoint query sets: `VISIBLE` (10 examples the *test* agent runs),
  `PROBE` (24 cases the *verify* agent checks against), `HIDDEN` (16 held-out cases — the only scoreboard).
- **`oracle.py`** — a correct reference engine. Never shown to the model; every grade is the candidate
  compared against it.
- **`grader.py`** — differential comparison of a candidate vs the oracle over any named set.
- **`agent.py`** — a real multi-turn tool loop (`read_file` / `write_file` / `run_tests` / `verify`).
  The **mode** is the only thing that changes between conditions: same model, same task, same turn budget.
- **`run_demo.py`** — runs all three modes × N, grades each on the hidden set, writes the JSON.

`PROBE` and `HIDDEN` are **disjoint** query strings from the same feature space, so a *verify* agent that
aces the hidden set proves it produced genuinely-correct code — not a fit to the grader.

## What this does *not* prove

- One model (Haiku 4.5), one task, N=5 — directional, not a benchmark. Re-run on your own workload.
- "Trust it" looks decent here (92.5%) partly because the task is small; on harder tasks blind trust
  degrades faster. The robust finding is the *reliability* gap (2/5 vs 5/5 perfect), not the exact means.
- List-rate pricing, no caching/batch; LLM runs are non-deterministic, so your numbers will vary.

Part of the **[Use AI with Tech Dad](https://www.youtube.com/@UseAIwithTechDad)** *build-and-show* series —
tested, not hyped.
