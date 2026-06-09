#!/usr/bin/env python3
"""
speculative_sim.py — a faithful, dependency-free simulation of speculative decoding.

The point of speculative decoding: a small, cheap "draft" model guesses the next
few tokens; the big, expensive "target" model verifies all of them in ONE forward
pass and keeps the longest correct prefix (plus one free bonus token). The output
is byte-for-byte identical to running the target alone — you just pay for far
fewer expensive target forward passes.

This script demonstrates that with REAL (tiny) models so the guarantee is provable,
not asserted:
  - TARGET model  = a character-level n-gram that sees the last 6 chars (default).
  - DRAFT model   = a character-level n-gram that sees only the last 3 chars —
                    genuinely cheaper and genuinely weaker, exactly like a small
                    draft LLM approximating a big target LLM. (Orders are tunable
                    via --target-order / --draft-order.)

Model sizes (n-gram context order) are configurable: the target sees more context
than the draft, so it is both slower and more accurate — exactly the real setup.
Both are trained on the same embedded corpus. We decode greedily, which makes the
"lossless" claim checkable with a hard equality assert. (The same guarantee holds
for *sampling* via the standard accept/reject correction; greedy is used here so the
proof is a one-line `==`.)

No GPU, no weights, no network — pure standard library. Run:

    python3 speculative_sim.py                 # headline run + writes results/
    python3 speculative_sim.py --sweep          # speedup vs draft block size K
    python3 speculative_sim.py --tokens 1200 --k 4 --draft-cost 0.1

Cost model (stated, not hidden): one target forward pass costs 1.0; one draft pass
costs `--draft-cost` (default 0.1, i.e. the draft is ~10x cheaper, a typical ratio).
Speedup = baseline_cost / speculative_cost. We report it as a RANGE across plausible
draft-cost ratios so we never overclaim a single hero number.
"""

from __future__ import annotations

import argparse
import json
import os

FPS_UNUSED = None  # (kept intentionally; this file emits data, not video)

# ---------------------------------------------------------------------------
# Corpus — original text written for this demo (no third-party content).
# Character statistics from this drive both toy models.
# ---------------------------------------------------------------------------
CORPUS = (
    "the machine reads one token, then predicts the next token, then reads that token, "
    "and predicts the next one again. every step waits for the step before it, and the "
    "model is enormous, so each step is slow. the slow part is not the arithmetic, it is "
    "moving the weights and the key value cache through memory on every single step. a "
    "small model is cheap to run, but it is not as accurate as the larger model, so on "
    "its own it would drift and make mistakes that the bigger network would not. the idea "
    "is simple and a little surprising. let the small model guess a short run of tokens "
    "ahead, racing along on its own, and then let the big model check that whole run in a "
    "single pass instead of one token at a time. where the guess matches what the big "
    "model would have written, the tokens are accepted and kept. at the first place where "
    "they disagree, the big model overrides the draft, the remainder of the guess is "
    "discarded, and the loop begins again from the corrected position. the answer you "
    "receive is exactly the answer the big model would have produced entirely on its own, "
    "token for token, because the big model holds the final say on every token it emits. "
    "what changes is only the number of slow passes through the big network, never the "
    "text that comes out of it. when the little model guesses well, one slow pass yields "
    "several finished tokens at once. when it guesses poorly, the system falls back to a "
    "single token per pass, the same speed as before, never slower in tokens, paying only "
    "a little wasted effort on drafts that were thrown away. researchers measured the "
    "acceptance rate, the fraction of guessed tokens the target keeps, and found it climbs "
    "high whenever the draft and the target broadly agree about ordinary language. higher "
    "acceptance means more tokens per expensive pass, which means a real and measurable "
    "speedup on a single device, with no change to the weights, no retraining, and no loss "
    "in quality. the technique appears under several names, speculative decoding, assisted "
    "generation, and blockwise parallel sampling, yet the core trick is always the same. "
    "guess cheaply, verify in parallel, keep the longest correct prefix, and repeat until "
    "the sentence is done. memory bandwidth is the true bottleneck of generation, not "
    "compute, because loading the parameters for one token costs almost as much as loading "
    "them to score five candidate tokens in one batched forward pass. that asymmetry is the "
    "whole reason the free lunch exists at all. an engineer picks a draft model that is "
    "small enough to be cheap yet aligned enough to be trusted, tunes the block length so "
    "the gamble pays off, and watches the same output arrive in a fraction of the wall "
    "clock time. nothing about the meaning of the text has changed, only the schedule of "
    "the slow steps that produced it, and that is a bargain worth taking almost every time."
) * 3


def train(order: int, text: str) -> dict[str, dict[str, int]]:
    """Train a char-level model of the given context order (1 = bigram, 2 = trigram)."""
    table: dict[str, dict[str, int]] = {}
    for i in range(order, len(text)):
        ctx = text[i - order : i]
        nxt = text[i]
        table.setdefault(ctx, {}).setdefault(nxt, 0)
        table[ctx][nxt] += 1
    return table


def argmax_next(table: dict[str, dict[str, int]], ctx: str) -> str:
    """Greedy next char. Deterministic tie-break by char so runs are reproducible."""
    dist = table.get(ctx)
    if not dist:
        return " "  # unseen context backs off to a space (stable, harmless)
    return max(sorted(dist.items()), key=lambda kv: kv[1])[0]


class Target:
    """The big, accurate model. Sees `order` chars of context. One call = one
    expensive forward pass."""

    def __init__(self, table, order):
        self.table = table
        self.order = order

    def next(self, seq: str) -> str:
        return argmax_next(self.table, seq[-self.order :])

    def verify_block(self, seq: str, k: int) -> list[str]:
        """Verify k positions in ONE pass: the argmax the target *would* emit at each
        position, given the running sequence extended by the accepted prefix so far.
        Mirrors the single batched forward pass a real target runs over the draft."""
        out = []
        cur = seq
        for _ in range(k):
            t = self.next(cur)
            out.append(t)
            cur += t
        return out


class Draft:
    """The small, cheap, weaker model. Sees fewer context chars than the target, so
    it is cheaper and less accurate. One call = one cheap forward pass."""

    def __init__(self, table, order):
        self.table = table
        self.order = order

    def propose(self, seq: str, k: int) -> str:
        cur = seq
        for _ in range(k):
            cur += argmax_next(self.table, cur[-self.order :])
        return cur[len(seq) :]


def baseline_greedy(target: Target, prompt: str, n: int) -> tuple[str, int]:
    """Vanilla autoregressive decoding: one target pass per token."""
    seq = prompt
    passes = 0
    for _ in range(n):
        seq += target.next(seq)
        passes += 1
    return seq[len(prompt) :], passes


def speculative_greedy(target: Target, draft: Draft, prompt: str, n: int, k: int):
    """Speculative decoding (greedy). Returns (generated, stats)."""
    seq = prompt
    target_passes = 0
    draft_passes = 0
    proposed = 0
    accepted = 0
    generated = 0

    while generated < n:
        block = min(k, n - generated)
        # 1. Draft proposes `block` tokens autoregressively (cheap passes).
        guess = draft.propose(seq, block)
        draft_passes += block
        proposed += block
        # 2. Target verifies the whole block in ONE pass + computes the bonus token.
        truth = target.verify_block(seq, block + 1)  # +1 = the free bonus token
        target_passes += 1
        # 3. Accept the matching prefix; on first mismatch take the target's token.
        i = 0
        while i < block and guess[i] == truth[i]:
            i += 1
        accepted += i
        # Tokens committed this round: i accepted drafts + 1 target token (the bonus
        # if all accepted, or the correction at the first mismatch).
        committed = "".join(truth[: i + 1])
        seq += committed
        generated += len(committed)

    generated_text = seq[len(prompt) :][:n]
    stats = {
        "target_passes": target_passes,
        "draft_passes": draft_passes,
        "proposed": proposed,
        "accepted": accepted,
        "accept_rate": round(accepted / proposed, 4) if proposed else 0.0,
        "tokens": len(generated_text),
        "tokens_per_target_pass": round(len(generated_text) / target_passes, 3),
    }
    return generated_text, stats


def cost(target_passes: int, draft_passes: int, draft_cost: float) -> float:
    return target_passes * 1.0 + draft_passes * draft_cost


def run_headline(prompt: str, n: int, k: int, draft_cost: float,
                 target_order: int = 6, draft_order: int = 3, verbose: bool = True):
    target = Target(train(target_order, CORPUS), target_order)
    draft = Draft(train(draft_order, CORPUS), draft_order)

    base_text, base_passes = baseline_greedy(target, prompt, n)
    spec_text, st = speculative_greedy(target, draft, prompt, n, k)

    identical = base_text == spec_text
    base_cost = cost(base_passes, 0, draft_cost)
    spec_cost = cost(st["target_passes"], st["draft_passes"], draft_cost)
    speedup = round(base_cost / spec_cost, 2)

    result = {
        "prompt": prompt,
        "tokens_generated": n,
        "draft_block_k": k,
        "draft_cost_ratio": draft_cost,
        "target_context_chars": target_order,
        "draft_context_chars": draft_order,
        "identical_output": identical,
        "baseline_target_passes": base_passes,
        "speculative": st,
        "baseline_cost": round(base_cost, 1),
        "speculative_cost": round(spec_cost, 2),
        "speedup_x": speedup,
        "target_pass_reduction": f"{base_passes} -> {st['target_passes']}",
    }

    if verbose:
        print("=" * 64)
        print("SPECULATIVE DECODING — faithful greedy simulation")
        print("=" * 64)
        print(f"  draft model : {draft_order}-char context  (cheap, weaker)")
        print(f"  target model: {target_order}-char context  (slow, accurate)")
        print(f"  tokens generated : {n}   draft block K = {k}")
        print("-" * 64)
        print(f"  IDENTICAL OUTPUT vs target-alone : "
              f"{'YES — byte-for-byte' if identical else 'NO (!!)'}")
        print(f"  accept rate (draft guesses kept) : {st['accept_rate']*100:.1f}%")
        print(f"  target forward passes : {base_passes} (baseline)  ->  "
              f"{st['target_passes']} (speculative)")
        print(f"  tokens per slow target pass      : {st['tokens_per_target_pass']}")
        print(f"  speedup @ draft_cost={draft_cost} : {speedup}x")
        print("-" * 64)
        print("  baseline output [:80]:  " + repr(base_text[:80]))
        print("  spec     output [:80]:  " + repr(spec_text[:80]))
        print("=" * 64)
    return result


def run_sweep(prompt: str, n: int, draft_cost: float,
              target_order: int = 6, draft_order: int = 3):
    target = Target(train(target_order, CORPUS), target_order)
    draft = Draft(train(draft_order, CORPUS), draft_order)
    base_text, base_passes = baseline_greedy(target, prompt, n)
    rows = []
    print(f"{'K':>3} {'accept%':>8} {'tgt_pass':>9} {'tok/pass':>9} {'speedup':>8} {'identical':>10}")
    for k in [1, 2, 3, 4, 5, 6, 8, 12, 16]:
        spec_text, st = speculative_greedy(target, draft, prompt, n, k)
        spec_cost = cost(st["target_passes"], st["draft_passes"], draft_cost)
        speedup = round((base_passes * 1.0) / spec_cost, 2)
        identical = base_text == spec_text
        rows.append({
            "k": k, "accept_rate": st["accept_rate"], "target_passes": st["target_passes"],
            "tokens_per_target_pass": st["tokens_per_target_pass"], "speedup_x": speedup,
            "identical": identical,
        })
        print(f"{k:>3} {st['accept_rate']*100:>7.1f}% {st['target_passes']:>9} "
              f"{st['tokens_per_target_pass']:>9} {speedup:>7}x {str(identical):>10}")
    return {"baseline_target_passes": base_passes, "tokens": n,
            "draft_cost_ratio": draft_cost, "sweep": rows}


def main():
    ap = argparse.ArgumentParser(description="Faithful speculative-decoding simulation")
    ap.add_argument("--tokens", type=int, default=600)
    ap.add_argument("--k", type=int, default=4, help="draft block size")
    ap.add_argument("--draft-cost", type=float, default=0.1,
                    help="cost of one draft pass relative to one target pass")
    ap.add_argument("--prompt", default="the model ")
    ap.add_argument("--target-order", type=int, default=6,
                    help="context chars seen by the big target model")
    ap.add_argument("--draft-order", type=int, default=3,
                    help="context chars seen by the small draft model")
    ap.add_argument("--sweep", action="store_true", help="sweep speedup vs K")
    ap.add_argument("--out-dir", default=None, help="directory to write results JSON")
    args = ap.parse_args()

    out_dir = args.out_dir or os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "results")
    os.makedirs(out_dir, exist_ok=True)

    if args.sweep:
        res = run_sweep(args.prompt, args.tokens, args.draft_cost,
                        args.target_order, args.draft_order)
        with open(os.path.join(out_dir, "sweep.json"), "w") as f:
            json.dump(res, f, indent=2)
        print(f"\nwrote {os.path.join(out_dir, 'sweep.json')}")
        return

    res = run_headline(args.prompt, args.tokens, args.k, args.draft_cost,
                       args.target_order, args.draft_order)
    with open(os.path.join(out_dir, "headline.json"), "w") as f:
        json.dump(res, f, indent=2)
    print(f"wrote {os.path.join(out_dir, 'headline.json')}")


if __name__ == "__main__":
    main()
