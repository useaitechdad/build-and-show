# Build & Show

Reproducible code and raw data behind the **[Use AI with Tech Dad](https://www.youtube.com/@UseAIwithTechDad)** *build-and-show* videos.

Every video on the channel that makes a claim about how an AI system behaves ships its
proof here: a small, self-contained demo you can **run yourself** and check. The rule for
this repo is simple — *tested, not hyped*. If a video says "X is faster" or "Y remembers
but Z doesn't," the script that measured it lives in a folder below, along with the exact
numbers that ended up on screen.

## Demos

| Demo | What it shows | Verified finding | Video |
|---|---|---|---|
| [`speculative-decoding/`](./speculative-decoding) | How a big LLM can run ~3× faster while returning **byte-for-byte identical** output, via a small draft model + one-pass verification | Output is provably identical to the target model alone; ~3.6× fewer expensive forward passes at the sweet spot (K≈6 → 3.1×) | *(add link)* |
| [`flash3-vs-35/`](./flash3-vs-35) | Whether Gemini 3 Flash and 3.5 Flash *act on* a rule stated 6 turns earlier — not just recall it | Both **remember** the rule; only 3.5 **enforces** it in code (**5/5** runs vs **0/5** for Flash 3, which leaves it as a comment). Two other apparent gaps didn't survive N=5 replication | *(add link)* |
| [`yc-w26-analysis/`](./yc-w26-analysis) | Whether YC still backs its 20-year "get a cofounder" advice — by pulling all 198 companies in the Winter 2026 batch from YC's public directory and counting how many are one person | **13 of 198** W26 companies are a single person (`team_size = 1`) — **7%**, a multi-year high vs the **2–4%** that held across every batch from 2022 to 2025. (The widely-quoted "22 solo founders" is a third-party *founder*-count, cited separately, not produced by this script) | *(add link)* |

*More coming — each new build-and-show video adds a folder.*

## How to use this repo

Each demo is a **self-contained folder** with its own `README.md` (what it is + how to run),
a `METHODOLOGY_AND_RESULTS.md` (method, scorecard, honesty notes), and a `results/` directory
with the raw output. Most demos are **pure Python standard library** — no GPU, no API key, no
`pip install` — so you can clone and run in seconds:

```bash
git clone https://github.com/useaitechdad/build-and-show
cd build-and-show/speculative-decoding
python3 speculative_sim.py            # then read that folder's README for the flags
```

Where a demo needs a real API key or model download, its own README says so up front, and
any calls bill to **your** key, never a shared one.

## Principles

- **Reproducible.** The numbers in the video come from the script at its default config. Run it and you should get the same result (allowing for documented LLM non-determinism).
- **Honest about limits.** Each demo states what it *doesn't* prove — toy models, single runs, cost assumptions — so nothing reads as more than it is.
- **No secrets.** These folders are scanned before publishing: no keys, no paths, no personal data.

## Stay in the loop

🎥 **YouTube:** [@UseAIwithTechDad](https://www.youtube.com/@UseAIwithTechDad) — narrow-deep breakdowns of how AI dev tools *actually* behave, under the hood.

If a demo helped, a ⭐ on the repo and a sub on the channel are the two things that keep the series going.

## License

Released under the [MIT License](./LICENSE) — use the code freely; attribution appreciated.
