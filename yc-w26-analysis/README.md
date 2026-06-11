# YC Winter 2026 — The Solo-Founder Spike

**TL;DR:** I pulled all **198** companies in Y Combinator's Winter 2026 batch
straight from YC's public directory. **13 of them are a single person** — no
cofounder, no employees. That's **7% of the batch** — the highest share in the
six-batch window, after 2–4% held for the previous two years. For 20 years YC's
#1 piece of advice was "don't be a single founder." The data just moved.

Every number in the companion video comes from the one script in this folder.
Run it yourself.

## Run it

```bash
python3 pull_yc_batch.py --batch winter-2026
```

No API key, no credentials. The script reads the public
[yc-oss API](https://github.com/yc-oss/api), which mirrors YC's own Algolia
directory index — the same data that powers
[ycombinator.com/companies](https://www.ycombinator.com/companies). It writes
`results/winter-2026_analysis.json` and prints the breakdown.

Add `--demo` for paced, screen-capture-friendly output.

## What it measures

- **AI share** — companies whose own one-liner / description mentions AI, agents,
  ML, etc. (whole-word match). W26: **158/198 (80%)**.
- **Team size** — the directory's `team_size` field (total headcount). We count
  `team_size == 1` as a single-person company. W26: **13**.
- **Trend** — the same count across the last six batches, to show whether
  solo-building is actually rising.

## The honest caveats

- The public directory exposes **headcount, not founder count**. "13" is
  companies that are *one person total*. Analysts who enrich with founder data
  (e.g. Rebel Fund) report **~22 solo founders (~11%)** — a related but different
  metric. Both point the same way.
- `team_size` is self-reported and current; a company that has since hired moves
  out of the bucket. Re-running later may shift the count by one or two.

## Results

See [`METHODOLOGY_AND_RESULTS.md`](./METHODOLOGY_AND_RESULTS.md) for the full
breakdown, the list of all 13 companies, and the batch-over-batch trend table.
