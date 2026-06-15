# Does Claude's Advisor Tool actually save money? I tested it.

Anthropic's **[advisor tool](https://docs.claude.com)** (beta, `advisor-tool-2026-03-01`) lets a
cheap, fast **executor** model (Sonnet or Haiku) consult a high-intelligence **advisor** model
(Opus) *mid-task*, inside a single API call. The pitch: near-Opus quality at lower cost, because
the advisor only writes a short plan while the cheap model does the bulk of the work.

Lots of write-ups quote Anthropic's benchmark slide. I couldn't find one that actually *ran* it on
everyday work — so this repo does, end to end, with the exact numbers reconciled to a real bill.

**TL;DR — across three tasks and three model tiers, on realistic work, the advisor never improved
quality and always cost more (sometimes it made things worse).** The idea is sound and it's still
beta; the win-cases in the docs are tasks where the cheap model is near-helpless on its own — which
most everyday work isn't.

> ⚠️ The advisor tool is in **beta** and (at time of writing) **API-only**. Numbers will drift as the
> models and the feature change. Re-run it on *your* workload before trusting any of this.

## The results (self-measured)

### Test 1 — a simple coding task (thread-safe worker pool), N=5 each
| Config | Pass rate | Mean cost/run |
|---|---|---|
| Sonnet solo | 5/5 | **$0.025** |
| Opus solo | 5/5 | $0.043 |
| Sonnet + Opus advisor | 5/5 | **$0.105** |

Same perfect result every way → the advisor was a **4.3× tax** for zero gain. On a task the model
already handles, there's nothing for the advisor to fix.

### Test 2 — a real agentic task (build a mini-SQL engine over many turns), N=5 each
Graded on **hidden** edge cases the agent never saw (operator precedence, multi-key sort, aggregates):

| Config | Hidden-test quality | Mean cost/run |
|---|---|---|
| Haiku solo | **98.8%** | $0.22 |
| Haiku + Opus advisor | **90.0%** | $0.65 |
| Opus solo | 100% | $0.36 |

Adding the advisor made Haiku **worse** *and* cost **more than just using Opus directly** — which
scored a clean 100%. If you'll pay advisor money, buy the better model.

**Total real spend for the whole investigation: $9.29**, reconciled to the Anthropic Console to the
cent. Opus 4.8 is priced at $5/$25 per MTok (input/output) — using the old $15/$75 rates inflates the
estimate ~3×; this repo uses the verified rates in [`_lib.py`](./_lib.py).

## Run it yourself

Pure Python standard library — **no `pip install`**. You need an API key with advisor-tool beta access
(calls bill to **your** key).

```bash
export ANTHROPIC_API_KEY=sk-ant-...        # a key with advisor-tool-2026-03-01 beta access

python3 smoke_test.py                      # confirm beta access + see the advisor fire (1 cheap call)
python3 advisor_demo.py --n 5              # Test 1: simple task, 3 configs
python3 run_sql.py --n 5 \
  --configs haiku_solo,haiku_advisor,opus_solo   # Test 2: agentic SQL engine
```

Results land in `results/`. `--n 5` for Test 2 makes ~real API spend (~$5–10 at list rates); start
with `--pilot` (1 run per config) to calibrate.

## What's here
| File | Role |
|---|---|
| `_lib.py` | Key loading, the single `/v1/messages` call (stdlib urllib), cost accounting |
| `smoke_test.py` | One call that proves the advisor fires and prints the token split |
| `advisor_demo.py`, `pool_task.py`, `verify_pool.py` | Test 1: simple worker-pool task |
| `run_sql.py`, `ag_agent.py`, `sql_spec.py`, `sql_ref.py`, `sql_grader.py` | Test 2: agentic SQL engine (graded vs a hidden reference oracle) |
| `ag_spec.py`, `ag_grader.py`, `run_agentic.py` | A second agentic task (expression evaluator) used along the way |
| `results/act1_simple_task.json`, `results/act2_sql_engine.json` | The real runs behind the tables above |

See [`METHODOLOGY_AND_RESULTS.md`](./METHODOLOGY_AND_RESULTS.md) for the full method, fairness notes,
and what this does **not** prove.

## Honest limits
- **Beta + a moving target.** Re-run on your own workload; don't treat these as universal.
- **Not Anthropic's benchmark regime.** Anthropic's wins (SWE-bench; Haiku BrowseComp 19.7%→41.2%) are
  tasks where the cheap model is near-helpless solo. My tasks weren't that extreme — and that's the
  point: most everyday work isn't either.
- **LLM non-determinism.** N=5 smooths it but won't reproduce to the cent.
- **List-rate pricing**, no prompt caching, no batch discount.
