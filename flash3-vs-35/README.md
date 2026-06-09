# Gemini 3 Flash vs 3.5 Flash — Thought-Preservation Test

Reproducible harness + raw data behind the video *"Both remember. Only one builds
what it remembered."*

## TL;DR finding
Both Gemini 3 Flash and 3.5 Flash **remember** a rule stated 6 turns earlier. The
difference is **follow-through**: asked to implement it, 3.5 reliably writes the
guard clause (**5/5 runs**); Flash 3 keeps the rule as a comment and never enforces
it (**0/5**). Two other apparent differences did *not* survive replication. Full
method + scorecard in `METHODOLOGY_AND_RESULTS.md`.

## Files
- `compare_flash.py` — the comparison harness (multi-turn chat through both models,
  captures answers + thinking-tokens + latency; `score_turn7()` auto-scores depth markers)
- `METHODOLOGY_AND_RESULTS.md` — method, per-turn cost data, scorecard, replication
- `results/*.json` — raw outputs for every run (single, matched-`high` control, N=5,
  plus the debug/oneshot scenarios)

## Run it yourself
```bash
pip install google-genai
export GEMINI_API_KEY=your_key_here        # or put it in a local .env

# headline N=5 (language-controlled):
python3 compare_flash.py --scenario long_horizon --runs 5 --language Python

# matched-thinking control:
python3 compare_flash.py --scenario long_horizon --thinking_level high
```
Calls bill to your own `GEMINI_API_KEY`. Models: `gemini-3-flash-preview`,
`gemini-3.5-flash` (as of 2026-06).

> Results vary run-to-run (LLM non-determinism) — that's the whole reason the test
> uses N=5 rather than a single lucky run.
