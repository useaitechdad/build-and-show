# Methodology & Results — YC W26 Solo Founders

## Source

[yc-oss API](https://github.com/yc-oss/api) batch endpoint
`https://yc-oss.github.io/api/batches/winter-2026.json`, a daily mirror of YC's
public Algolia directory index (`YCCompany_production`) — the same index that
powers ycombinator.com/companies. No authentication. Pulled 2026-06-11.

## Method

1. Fetch the full batch JSON (198 records).
2. **AI share:** whole-word regex match for `ai`, `artificial intelligence`,
   `machine learning`, `llm(s)`, `agent(s)`, `agentic`, `neural`, `deep learning`
   across each company's one-liner, long description, tags, and industries. Word
   boundaries prevent false hits inside words like "maintain" or "chair."
3. **Single-person companies:** `team_size == 1`.
4. **Trend:** repeat the `team_size == 1` count across the last six batches.

## Results (Winter 2026)

| Metric | Value |
|---|---|
| Total companies | 198 |
| Mention AI in their own pitch | 158 (80%) |
| **Single-person companies (team_size == 1)** | **13 (7%)** |
| Two-person companies | 95 |

### The 13 single-person companies

| Company | One-liner | Category |
|---|---|---|
| Aurorin CAD | Claude code for Mechanical Engineers | Hardware / CAD |
| Hlabs | US-Made Parts for Robots | Robotics |
| GRU Space | Moon hotel → space construction | Space |
| Button Computer | The tiny computer built for voice AI | Hardware |
| DAIVIN! | Tankless dive gear | Hardware |
| Envariant | Interpretability & reasoning infra for foundation models | AI infra |
| Rhizome AI | Agent platform for life sciences | AI / bio |
| Overdrive Health | AI-native medical billing services | Healthcare |
| ClaimGlide | AI automated prior-auths for private medical practices | Healthcare |
| Reframe | AI-native hardware procurement marketplace | Marketplace |
| InventoryQuant | Automating the inventory process in insurance | Fintech / insurance |
| Sparkles | Make everyone on your team an engineer | Dev tools |
| Traverse | Research lab solving non-verifiable work | AI research |

Five of the thirteen build hardware, robotics, or space — categories that
historically demanded a team and capital, now attempted by one person plus AI.

### Batch-over-batch trend: single-person companies

| Batch | Single-person | Total | Share |
|---|---|---|---|
| Winter 2024 | 9 | 249 | 4% |
| Summer 2024 | 5 | 248 | 2% |
| Winter 2025 | 7 | 168 | 4% |
| Summer 2025 | 5 | 166 | 3% |
| Fall 2025 | 3 | 148 | 2% |
| **Winter 2026** | **13** | **198** | **7%** |

The share held in a 2–4% band for two years, then jumped to 7% in W26 — the
highest in the six-batch window (more than 3× the immediately preceding batch).

## Caveats

- **Headcount, not founder count.** The public directory exposes `team_size`
  (total people), not number of founders. "13" = companies that are one person
  total. Founder-enriched datasets (e.g. Rebel Fund's batch analysis) report
  ~22 solo founders (~11%) — a different, larger metric.
- **Self-reported and current.** `team_size` reflects today; a company that has
  hired since launch leaves the bucket. Counts can drift ±1–2 on re-runs.
- **Correlation, not proof.** The timing aligns with capable coding agents, but
  this data shows the *what*, not a causal *why*.

Raw analysis output: [`results/winter-2026_analysis.json`](./results/winter-2026_analysis.json).
Captured run: [`results/demo_output.txt`](./results/demo_output.txt).
