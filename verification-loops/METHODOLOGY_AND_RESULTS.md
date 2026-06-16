# Methodology & results

Everything here is self-measured against the live Claude API. Quality is graded by code (differential
comparison against a reference oracle), and the grand total reconciles to the run in `results/verify_run.json`.

## The question
Does making an AI agent *check its own work* make it reliable — and does a fancier check beat a simpler one?

## The setup
- **Task:** implement a mini-SQL query engine from scratch (`SELECT / WHERE / GROUP BY / ORDER BY / LIMIT`,
  operator precedence, multi-key sort, aggregates). A real parser; no `eval`, no `sqlite3`.
- **Model:** `claude-haiku-4-5-20251001`, held constant across every run.
- **Loop:** a real multi-turn agent with `read_file` / `write_file` tools, plus a per-mode feedback tool.
- **The only manipulated variable:** *how* the agent can check its work (same model, task, and 16-turn budget).

### Three modes
| Mode | Feedback tool | System prompt gist |
|---|---|---|
| `trust` | none | write it; stop when confident (cannot run anything) |
| `test` | `run_tests` → 10 visible examples | run the examples, fix failures, repeat until they pass |
| `verify` | `verify` → 24-case differential vs oracle | check broadly, fix the root cause, repeat until zero failures |

### Grading
Every candidate is graded on **16 HIDDEN queries** it never saw, by comparing its output to a correct
**oracle** (`oracle.py`, never shown to the model). The verifier's 24-case `PROBE` set is **disjoint** from
the hidden set — so acing the hidden set means correct code, not a fit to the grader.

## Results (N=5 per mode)

| Mode | Hidden scores (/16) | Mean | Perfect | Mean turns | Mean cost |
|---|---|---|---|---|---|
| Trust it | 16, 14, 13, 15, 16 | **92.5%** | 2/5 | 3.2 | $0.045 |
| Test it | 16, 16, 16, 16, 16 | **100%** | 5/5 | 9.8 | $0.163 |
| Verify it | 16, 16, 16, **0**, 16 | **80.0%** | 4/5 | 8.2 | $0.155 |

(List rates per 1M tokens, verified 2026-06-15: Haiku 4.5 $1 in / $5 out. No caching.)

### Reading the numbers
1. **Trusting the unchecked answer is a coin flip.** 92.5% mean, but perfect only **2 of 5** — and one run
   scored 13/16: code that looks finished and quietly fails the tricky cases (parenthesized conditions,
   multi-key ordering). Confidence told you nothing.
2. **Running the example tests in a loop fixed it.** `test` hit **16/16 on all 5 runs.** The model didn't
   get smarter — it got to *see its failures and try again.*
3. **The fancier verifier did NOT do better — it did worse, and once catastrophically.** `verify` was 80%
   with one **0/16** run. In that run the model wrote a broken parser, the verifier *correctly* reported it
   (1/24 passing, 6 failing cases shown), the model rewrote three times, never recovered, and **stopped —
   shipping broken code.** A verification loop is only as good as the model's ability to act on it.

## The honest takeaway
The reliability lever isn't a smarter model — it's a check the model **can act on**, in a loop. And here the
*simplest* check (run the examples) beat both blind trust and the elaborate differential verifier. More
checking is not automatically better; over-checking gave a weak model more rope to spiral.

## What this does NOT prove
- One model, one task, N=5 — directional, not a benchmark.
- "Trust it" scoring 92.5% is task-dependent (small task); blind trust degrades faster on harder work.
- The verify `0/16` is one event at N=5 — it shows the failure mode exists, not its exact frequency.
- List-rate pricing, single machine, LLM non-determinism — re-run and expect variation.
