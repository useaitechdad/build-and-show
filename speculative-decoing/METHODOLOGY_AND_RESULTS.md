# Speculative Decoding — Methodology & Results

> Build-and-show experiment for the "Use AI with Tech Dad" channel.
> All raw data in `results/*.json`. Re-runnable via `speculative_sim.py` (stdlib only).

---

## 1. Question

Speculative decoding is advertised as a "free lunch": a large language model that runs
several times faster **with no change to its output**. Two claims are worth proving,
not just repeating:

1. **Lossless** — the speculative output is *identical* to what the target model would
   have produced on its own.
2. **Faster** — it does meaningfully fewer *expensive* (target) forward passes.

## 2. Method

| | Detail |
|---|---|
| Language | Python 3, standard library only (no GPU, weights, or network) |
| Target model | char-level n-gram, context = last **6** chars (slow, accurate) |
| Draft model  | char-level n-gram, context = last **3** chars (cheap, weaker) |
| Decoding | **greedy** (argmax) — makes "identical" a one-line equality check |
| Corpus | ~3 KB of original prose embedded in the script (no third-party text) |
| Default run | 600 tokens, block size K=4, draft cost = 0.1× a target pass |

### The algorithm (greedy speculative decoding)
1. The **draft** proposes `K` tokens autoregressively (K cheap passes).
2. The **target** verifies all `K` positions — plus one bonus position — in **one** pass.
3. Accept the matching prefix; at the first mismatch, take the target's token and discard
   the rest of the draft. Commit `(accepted + 1)` tokens. Repeat.

Because step 3 always commits at least one *target* token and never commits a token the
target disagrees with, the final sequence equals plain target-only greedy decoding —
which the script verifies with `baseline == speculative`.

### Cost model (stated, not hidden)
One target pass costs `1.0`; one draft pass costs `--draft-cost` (default `0.1`).
`speedup = baseline_cost / speculative_cost`. The two headline facts that *don't* depend
on this assumption are reported separately: identical output, and the raw target-pass count.

---

## 3. Results — default config (target=6, draft=3, K=4, 600 tokens)

| Metric | Baseline (target alone) | Speculative |
|---|---|---|
| Output | — | **identical, byte-for-byte** |
| Target forward passes | 600 | **168** |
| Draft forward passes | 0 | 669 |
| Accept rate | — | **64.7%** (433 / 669) |
| Tokens per target pass | 1.00 | **3.57** |
| Cost (draft = 0.1×) | 600.0 | 234.9 → **2.55×** |

Raw: `results/headline.json`.

## 4. The block-size sweet spot (`--sweep`)

Larger blocks mean fewer target passes — but as the block grows, the draft's later
guesses get rejected, so the extra draft work is wasted. Speedup therefore **peaks and
then declines**.

| K | accept % | target passes | tokens/pass | speedup | identical |
|---:|---:|---:|---:|---:|:--:|
| 1 | 78.6 | 336 | 1.79 | 1.62× | ✅ |
| 2 | 75.0 | 240 | 2.50 | 2.08× | ✅ |
| 3 | 71.1 | 192 | 3.13 | 2.40× | ✅ |
| 4 | 64.7 | 168 | 3.57 | 2.55× | ✅ |
| 5 | 63.3 | 144 | 4.17 | 2.78× | ✅ |
| **6** | **66.8** | **120** | **5.00** | **3.12×** | ✅ |
| 8 | 50.2 | 120 | 5.00 | 2.78× | ✅ |
| 12 | 33.6 | 120 | 5.00 | 2.28× | ✅ |
| 16 | 25.3 | 120 | 5.00 | 1.93× | ✅ |

Raw: `results/sweep.json`. **Output is identical at every block size** — K only trades
speed for wasted draft work, never correctness.

---

## 5. Conclusion

**Both claims hold.** The speculative output is byte-for-byte identical to the target
model's own output, and it gets there in far fewer expensive passes — ~3.6× fewer tokens
per slow pass at the sweet spot. The only knob that matters is block size, and the only
way speculative decoding "loses" is by wasting draft work when the draft and target
disagree — it never degrades the answer.

This is a teaching simulation; the *mechanism* is exactly what production systems use
(vLLM, TensorRT-LLM, Hugging Face assisted generation), where real-world speedups are
typically 2–3× depending on draft/target alignment.

*Generated from `results/headline.json` and `results/sweep.json`.*
