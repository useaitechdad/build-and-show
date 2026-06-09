# Speculative Decoding — a faithful, dependency-free simulation

The runnable demo behind the video *"The Free Lunch That Makes AI 3× Faster."*

Speculative decoding lets a big language model produce text **far faster** while
returning **byte-for-byte the same output** it would have produced on its own. A
small, cheap *draft* model guesses several tokens ahead; the big *target* model
verifies the whole guess in **one** forward pass, keeps the longest correct prefix,
and overrules the rest. Because the target has the final say on every token it keeps,
quality is unchanged — you only pay for fewer slow passes.

This repo proves that with **real (tiny) models**, so the guarantee is demonstrated,
not asserted — and it needs **no GPU, no weights, no network** (pure Python stdlib).

## TL;DR result (default config)

| | value |
|---|---|
| Output vs target-alone | **identical — byte-for-byte** |
| Draft acceptance rate | **64.7%** |
| Slow target passes | **600 → 168** |
| Tokens per slow pass | **3.57** |
| Speedup (draft 10× cheaper) | **2.55×** |
| Best block size K (sweep) | **K≈6 → 3.1×** |

Full method + the block-size sweep in `METHODOLOGY_AND_RESULTS.md`.

## How the toy models map to the real thing
- **Target** = a character-level n-gram seeing the last **6** chars (slow, accurate).
- **Draft**  = a character-level n-gram seeing the last **3** chars (cheap, weaker).

The draft sees less context, so it is genuinely cheaper *and* genuinely less accurate
— exactly the relationship between a small draft LLM and a big target LLM. We decode
**greedily**, which makes "identical output" checkable with a one-line `==`. (The same
guarantee holds for *sampling* via the standard accept/reject correction; greedy is
used here purely so the proof is trivial to read.)

## Run it
```bash
python3 speculative_sim.py                 # headline run → results/headline.json
python3 speculative_sim.py --sweep         # speedup vs block size K → results/sweep.json
python3 speculative_sim.py --tokens 1200 --k 6 --draft-cost 0.1
python3 speculative_sim.py --target-order 8 --draft-order 4   # tune model sizes
```

## Honesty notes
- The **speedup** depends on the stated cost model (`--draft-cost`, default 0.1 = the
  draft is ~10× cheaper than the target). It's a *proxy* for the real memory-bound cost,
  not a benchmark of any specific GPU. The numbers we stand on are the two that don't
  depend on that assumption: **output is identical**, and **target passes drop ~3.6×**.
- This is a teaching simulation, not a kernel. Real speedups (vLLM, TensorRT-LLM,
  Hugging Face assisted generation) are typically **2–3×** and depend on how well the
  draft is aligned to the target. The mechanism shown here is the real one.
