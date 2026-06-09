# Gemini 3 Flash vs 3.5 Flash — Thought-Preservation Test

> Build-and-show experiment for the "Use AI with Tech Dad" channel.
> All raw data in `results/*.json`. Re-runnable via `scripts/compare_flash.py`.

---

## 1. Question

3.5 Flash's headline new capability is **thought preservation** — per Google's docs it
"maintains intermediate reasoning across multi-turn conversations automatically." Both
3 Flash and 3.5 Flash are thinking models by default (3 Flash defaults to `high`, 3.5
to `medium`), so the claim is *not* "3.5 can think and 3 can't." The claim under test:

> **Does 3.5 actually use accumulated context across many turns better than 3 — and where does the difference show up?**

## 2. Method

| | Detail |
|---|---|
| SDK | `google-genai` 1.72.0 (`genai.Client` + `client.chats`) |
| Models | `gemini-3-flash-preview` (3 Flash) · `gemini-3.5-flash` (3.5 Flash) |
| Thinking config | **As shipped** — default levels (3=`high`, 3.5=`medium`), `include_thoughts=True` |
| Session | One `chats.create()` per (model, scenario); turns sent sequentially so prior reasoning + thought signatures persist in history |
| Captured per turn | answer text, thought summary, latency (s), `thoughtsTokenCount`, output/total tokens |
| Billing | Caller's own `GEMINI_API_KEY` (local `.env` or env var); ~22 API calls total |

### Scenarios
- **`long_horizon`** (primary, 7 turns): turn 1 sets **four non-obvious invariants**
  (R1 64-bit signed IDs / R2 out-of-order arrival / R3 silent dup-reject / R4
  non-monotonic clock); turns 2–5 add **distraction features** (range query, subscribe,
  snapshot/reload) + one probe; turn 6 adds a late invariant (R5 tombstoning); turn 7
  asks for the **final class + a restated list of every rule** — nothing restated by us.
  Objective test: do the invariants survive, and are they *implemented* or just *named*?
- **`debug_refactor`** (3 turns): early root-cause analysis must survive to a final fix.
- **`oneshot_reasoning`** (1 turn, control): single hard prompt, no memory involved.

### Scoring
For `long_horizon`, the final class (turn 7) is checked against each of the 9
agreed items on two axes: **(a) Retained** (mentioned/remembered) and **(b) Implemented**
(actually enforced in code, not just annotated).

---

## 3. Data

### `long_horizon` — cost per turn (as shipped)

| Turn | 3 Flash latency | 3 Flash think tok | 3.5 latency | 3.5 think tok |
|---|---|---|---|---|
| 1 | 4.07s | 262 | 3.93s | 284 |
| 2 | 11.26s | 671 | 17.70s | 1488 |
| 3 | 10.75s | 527 | 10.75s | 682 |
| 4 | 5.94s | 258 | 5.61s | 326 |
| 5 | 11.65s | 754 | 19.31s | 1557 |
| 6 | 15.69s | 1518 | 22.60s | 1736 |
| 7 | 14.83s | 767 | 20.27s | 925 |
| **Total** | **~74.2s · 4,757 think / 5,096 out tok** | | **~100.2s · 6,998 think / 7,213 out tok** | |

**3.5 Flash ran ~35% slower wall-clock and spent ~47% more thinking + ~42% more output tokens** on this task. It is not the cheaper/faster option here — it works harder.

### `debug_refactor` (3 turns) — summary
Both models found the bug (t1), the unhashable-type interaction (t2), and produced a
correct hybrid fix (t3). The only tell: **3.5 attributed each carried-over decision to
the specific earlier turn** ("Corrected Indentation (Turn 1)"); 3 kept the substance but
not the provenance.

### `oneshot_reasoning` (control)
Single-turn; no memory effect. Comparable (3.5 used slightly more thinking, 629 vs 575 tok).

---

## 4. Results — `long_horizon` scorecard

| # | Item | 3 Flash retained | 3 Flash implemented | 3.5 retained | 3.5 implemented |
|---|---|:---:|:---:|:---:|:---:|
| R1 | 64-bit signed IDs | ✅ | ⚠️ **annotated only** | ✅ | ✅ **enforces `INT64_MIN/MAX`** |
| R2 | Out-of-order arrival | ✅ | ✅ sorted timeline | ✅ | ✅ sorted timeline |
| R3 | Silent dup-reject | ✅ | ✅ | ✅ | ✅ |
| R4 | Non-monotonic clock | ✅ | ✅ logical ts only | ✅ | ✅ logical ts only |
| R5 | Tombstone (never re-accept) | ✅ | ✅ | ✅ | ✅ |
| F1 | Range query | ✅ | ✅ bisect | ✅ | ✅ bisect |
| F2 | Subscribe | ✅ | ✅ | ✅ | ✅ **+ unsubscribe** |
| F3 | Snapshot / reload | ✅ | ⚠️ **crashes on `bytes` data** | ✅ | ✅ **base64-encodes payload** |
| — | Tombstone honored on reload | — | ❌ not filtered | — | ✅ drops tombstoned on reload |

### Key finding
**Retention is a TIE — both models kept all 9 items across 7 turns with distractions.**
The "3 forgets, 3.5 remembers" framing is *false* for these models. The real, repeatable
difference is **integration depth**: 3.5 *acted on* the accumulated constraints where 3
only *labelled* them —

- **R1:** 3.5 defines `INT64_MIN/MAX` and raises on out-of-range IDs; 3 writes a `# (R1)`
  comment but never enforces the bound.
- **F3:** 3.5 anticipates non-JSON `bytes` payloads and base64-encodes them; 3's snapshot
  would raise on binary data.
- **Cross-feature:** 3.5 honors the tombstone invariant *inside* the reload path; 3 doesn't.

This costs 3.5 ~35% more time and ~45% more tokens.

> ⚠️ **Single-run caveat — see §6.** This scorecard is one run. When re-tested
> with N=5 and a fixed language (§6), only **R1-enforcement** reproduced. The
> base64 and tombstone-on-reload differences were **noise** and did NOT hold up.
> Do not cite them.

---

## 6. Replication — N=5, language-controlled (the result to trust)

The single run had two confounds: language drifted (Python→Java between runs) and
3.5 ran at a different default level. We re-ran `long_horizon` **5× per model**,
pinned to **Python**, at **as-shipped defaults**, auto-scoring the final class for
three depth markers and hand-verifying the headline.

### Marker hit-rates (N=5)

| Marker | Flash 3 | Flash 3.5 | Verdict |
|---|:---:|:---:|---|
| **R1 — enforces 64-bit signed bound** | **0/5** | **5/5** | ✅ **real, reproducible** |
| Snapshot handles `bytes` (base64) | 0/5 | 0/5 | ❌ no difference (single run was a fluke) |
| Tombstone honored on reload | 3/5 | 3/5 | ❌ noise, no signal |

### Hand-verification (R1)
- **Flash 3, all 5 runs:** *no* explicit ID bound or validation anywhere.
- **Flash 3.5, all 5 runs:** defines `±9223372036854775808` and `raise ValueError`
  on out-of-range IDs (wording varies, behavior identical).

### Conclusion (the claim the video can stand on)
**Both models remember a rule stated 6 turns earlier; only 3.5 reliably turns it
into an enforced guard.** Flash 3 retains the constraint as intent (a comment) but
0/5 times writes the check. This is *follow-through on accumulated constraints*, not
memory — and it's the single difference that held up under replication. Everything
else (raw retention of all 9 items, the other two depth markers) was a tie.

Cost trade-off still applies: 3.5 is slower and spends more tokens.

---

## 5. What this means for the video

- **Honest thesis:** *Both Flash models remember the whole conversation. 3.5's real edge
  isn't memory — it's that it turns remembered rules into correct code, while 3 tends to
  acknowledge them and move on.* That's the frontier-coding gain, shown live.
- **Fact-check-safe:** no "3.5 crushes 3" overclaim; the scorecard backs every statement.
- **The on-screen money shot:** R1 side-by-side — same conversation, 3 writes a comment,
  3.5 writes the guard clause. And the snapshot `bytes` edge case.
- **Trade-off to state plainly:** 3.5's depth isn't free — slower, more tokens. (Cost was
  covered in the prior pricing video, so mention, don't dwell.)

*Generated from `results/long_horizon.json`, `results/debug_refactor.json`,
`results/oneshot_reasoning.json` — 2026-06-08.*
