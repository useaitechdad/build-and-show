# Methodology & Results

## The question

Do sub-agents actually keep an orchestrator's context small — or is that just folklore?
"Small context" matters because an agent's context window is finite, and as it fills, the
model's performance degrades (often called *context rot*). The claim under test: handing
heavy sub-tasks to sub-agents with their own windows keeps the **lead** agent's context
lean, letting it run longer without drifting.

## Setup

- **Task:** read six production incident reports and identify the single most common root
  cause + the most-involved service.
- **Inputs:** six synthetic incident reports, bundled in `subagent_demo.py`. Each is a
  realistic mix of routine log lines (noise) wrapped around a short postmortem (signal) —
  the kind of large, low-density artifact a sub-agent is meant to chew through.
- **Model:** `gemini-3-flash-preview`. The pattern is model-agnostic; any frontier model
  shows the same shape.

## The two approaches

| | Inline | Sub-agents |
|---|---|---|
| Who reads the logs | one agent, all six | one sub-agent per log, each in its own window |
| What the lead holds | all six full logs | six 1–2 sentence summaries |
| Root (lead) context | the entire blob | just the summaries |

We measure the **root context** with the model's own `count_tokens`, so the numbers are
exact, not estimated.

## Results (one real run)

| Metric | Inline | Sub-agents | |
|---|---:|---:|---|
| **Root (lead) context** | 21,781 | **262** | **83.1× leaner** |
| **Total tokens processed** | 21,781 | 22,230 | ~the same (slightly more) |
| Final conclusion | pool exhaustion · checkout-api | pool exhaustion · checkout-api | **identical** |

Raw object: [`results/demo_run.json`](./results/demo_run.json).

## What this proves — and what it doesn't

**Proves:** delegating to sub-agents keeps the orchestrator's context dramatically smaller
(here 83×) while preserving the answer. That smaller, cleaner root context is what resists
rot over long runs.

**Doesn't prove / honesty notes:**
- **Not a token-cost win.** Total usage was slightly *higher* with sub-agents — the logs
  still get read, plus summarization overhead. If your goal is fewer tokens, this isn't it.
- **Exact numbers vary run to run.** The summaries are model output, so the sub-agent root
  count (~260) wobbles a little; the inline count is deterministic. The *ratio* (tens of ×)
  is the robust result, not the exact figure.
- **Synthetic inputs.** The reports are fabricated to be representative; real logs differ.
- **Single task, single run.** This is an illustration of a mechanism, not a benchmark.

## Reproduce

```bash
pip install -r requirements.txt
export GEMINI_API_KEY=your_key_here
python3 subagent_demo.py
```
