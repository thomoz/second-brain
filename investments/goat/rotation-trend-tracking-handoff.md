# Sector/Industry Rotation Trend Tracking — Session Handoff

## Status: SUPERSEDED 2026-09-02 — folded into
`investments/goat/industry-pipeline-handoff.md` (Part A) so it can be planned
alongside the industry-heartbeat pipeline, which touches the same files. This file
and `.agent/plans/goat-rotation-trend-tracking.md` stay as the detailed Part-A
reference. Original status: NOT STARTED — handoff drafted 2026-08-23.

## What This Is

Both `sector-ranking.md` (11 SPDR sector ETFs, 3-month window) and
`industry-ranking.md` (39 Finviz industry ETFs, 6-month window, shipped
2026-08-23 — see `.agent/plans/goat-industry-rotation-ranking.md`) are pure
live-re-fetch snapshots: every run recomputes each ticker's return over its
window and **overwrites** the file. Neither has any memory of what the number
was on a previous run.

Prompted directly by Shaun asking, after the industry ranking shipped: "if SMH
drifts down to just +30%, will that represent a trend and will we see it?" —
answer today is no. The stated goal of this whole rotation-ranking feature
line is "know which way the trends are heading," which the current
overwrite-only design does not actually serve. Confirmed with Shaun
(2026-08-23): scope covers **both** sector and industry rankings, not just
industry — they share the identical gap for the identical reason.

## Context

- **Not entirely invisible today** — both files are git-tracked and committed
  on every vault sync, so `git log -p` on either file lets you manually diff
  a past day's numbers against today's. That's an accidental side effect of
  vault sync, not a designed feature — no delta column, no direction
  indicator, no "N days rising/falling" streak, nothing surfaced in the
  report itself.
- **Deliberately deferred at ship time.** Both features' plans explicitly
  chose live re-fetch / no daily-snapshot DB table to keep initial scope
  small (see `goat-industry-rotation-ranking.md`'s Decision #2 and
  `sector_rotation.py`'s original Phase 2 plan). This handoff is the
  follow-up that revisits that call now that Shaun has said trend visibility
  is actually the point.

## Reference Design — Goat Academy's own tool (screenshot shared by Shaun, 2026-08-23)

Shaun shared a screenshot of a "Rotation Flow" report from Goat Academy's own
free resources tool (same source webinar this whole package is modeled on) —
strong signal for the target shape here, not just a nice-to-have inspiration:

- Every industry/sector is classified into one of **three discrete states**:
  **DOWNHILL**, **BASE**, **CLIMBING** — not a raw return number.
- The report shows **day-over-day transitions** (their example: `2026-08-20 →
  2026-08-21`), one row per industry: `Industry | FROM | TO` (e.g. "Engineering
  & Construction: DOWNHILL → BASE", "Other Metals and Minerals: BASE →
  CLIMBING").
- A **Summary line rolls up transition counts** across the whole universe,
  e.g. "10 DOWNHILL → BASE · 8 BASE → CLIMBING · 3 BASE → DOWNHILL · 2
  CLIMBING → BASE · 1 DOWNHILL → CLIMBING" — this is the actual "which way are
  trends heading" answer Shaun's after, at a glance, without reading every row.
- Filter chips at the top (e.g. "Industrials — Other", "Natural Gas
  Distribution", "Hotels/Resorts") suggest per-industry drill-down, likely out
  of scope for a markdown report but worth noting.

**This resolves several of the open questions below in favor of a specific
shape**: state-transition tracking (not a numeric delta), day-over-day
granularity (not an N-day lookback), and a rollup-summary-plus-detail-table
report layout. What it does **not** tell us: the actual criteria that decides
whether a given industry is DOWNHILL/BASE/CLIMBING on a given day — that
classification logic isn't visible in a screenshot and isn't documented in
`goat-academy-webinar-1.md` (checked — no match). This needs real research
before shipping a number, same discipline every other Goat threshold in this
repo has been held to (heartbeat squeeze %, 150DMA exit rule, etc.) — do not
guess three bucket boundaries and ship them.

**Starting hypothesis for planning to validate, not a decided answer**: Goat's
existing `check_sector_breakout()` already classifies price-vs-50DMA
position + MA slope into a binary signal (crossed above + MA rising = fresh
breakout). A 3-state version of the same mechanics is a plausible way to
derive DOWNHILL (below MA, MA falling) / BASE (near MA or MA flat) / CLIMBING
(above MA, MA rising) without inventing an unrelated new metric — but this is
a hypothesis to research/backtest during `/plan-feature`, not an assumption to
build from directly.

## Reference Design #2 — Winston App's "Winston's Watchlist" (screenshot shared by Shaun, 2026-08-23)

A second screenshot, from the paid Winston App (already referenced as context-only
in `goat/HANDOFF.md` — "$57/mo, finds index funds by sector," not being adopted).
Per-stock watchlist (SPOT, HCA, CLH, ECL, SAM, WM, TM, RSG, ...), each row tagged
with its Industry and a **binary** trend badge — a small sparkline plus a colored
"▲ Rising" / "▼ Falling" label, not a 3-state bucket. Two other per-row columns
worth noting but **not new asks**: "Pattern" (a mini breakout-price chart) and
"Your Exit Line" (150-day-average exit price, above/below indicator, % distance)
— both map directly onto Goat features that already ship (the heartbeat scanner's
consolidation/breakout pattern, and the Phase 1 150DMA exit check), just at
individual-stock granularity with a nicer visual. Good validation Goat's existing
design already covers that ground; nothing to add here.

**What's new/relevant to this handoff**: the simpler 2-state (Rising/Falling)
industry-trend model, as an alternative to Reference #1's 3-state DOWNHILL/BASE/
CLIMBING. Notably, **`rank_sectors()`/`rank_industries()` already compute a
`rising: bool` field** (`return_pct > 0`) on every run, for free — a day-over-day
Rising/Falling badge needs *zero new classification research*, only a snapshot
of yesterday's `rising` value to diff against today's. This is a materially
cheaper MVP than Reference #1's 3-state model, which needs a sourced
DOWNHILL/BASE/CLIMBING threshold before it can ship at all. See revised Open
Question #1 below — this is now a real fork in the road, not just an
implementation detail.

## Design direction (recommended, not yet built)

- **A new daily-snapshot table is the only way to do this properly.** Git-diffing
  the markdown file is not a substitute — it can't answer "how many days has
  this been falling" or render a transition table without manual archaeology.
- Store one row per ticker per run: date, ticker, label (sector or industry),
  return_pct, rank, and (once the classification logic is sourced) the
  DOWNHILL/BASE/CLIMBING state. Reuse across both rankings if the schema is
  generic enough (ticker/label/return_pct/rank/state/scope), or keep two
  tables mirroring the existing separate `GOAT_SECTOR_*`/`GOAT_INDUSTRY_*`
  config namespaces — scope this during planning, not here.
- Report changes: add a Rotation Flow section per the reference design above
  (FROM/TO table + summary rollup), likely alongside (not replacing) the
  existing level-based Top 5/Bottom 5 + Full Ranking tables already shipped —
  exact final layout is still an open question below.

## Explicitly NOT scoped here (do not build as part of this handoff)

- No change to the underlying ranking computation (`rank_sectors`/
  `rank_industries` stay as-is) — this is additive history + display only.
- No new alerting/notification on trend changes — that's a separate,
  bigger design question (what counts as alert-worthy drift?) not implied by
  Shaun's question, which was about visibility, not automation.

## Open Questions for Shaun (resolve during `/plan-feature`)

1. **State model — 2-state (Rising/Falling) vs. 3-state (DOWNHILL/BASE/
   CLIMBING) — the real fork, resolve first, everything else depends on it.**
   - **Cheap option**: reuse the `rising: bool` field `rank_sectors()`/
     `rank_industries()` already compute (`return_pct > 0`) — a Rising/Falling
     badge needs no new research, just a prior-day snapshot to diff against.
     Matches Reference #2 (Winston App) exactly.
   - **Richer option**: the 3-state DOWNHILL/BASE/CLIMBING model from
     Reference #1 (Goat Academy) — genuinely more informative (a "BASE"
     state distinguishes real consolidation from noise around zero, which a
     binary flag can't) but needs a sourced, defensible classification
     threshold before it can ship — not documented in `goat-academy-webinar-1.md`
     (checked, no match) or visible in a screenshot. The 50DMA-position-and-
     slope hypothesis above is a starting point for that research, not a
     decision.
   - Recommend surfacing both options to Shaun explicitly during
     `/plan-feature` rather than picking one here — this doc is scoping, not
     deciding.
2. **Comparison granularity** — the reference tool steps day-over-day; confirm
   that's right for Goat's cadence too (sector ranking runs daily already;
   industry ranking now does too), vs. a longer step (weekly) that might be
   less noisy for a 6-month-window metric like industry ranking.
3. **Schema** — one shared snapshot table for both rankings (ticker, label,
   return_pct, rank, state, scope, date), or two tables mirroring the existing
   `GOAT_SECTOR_*`/`GOAT_INDUSTRY_*` config split?
4. **Retention** — keep every snapshot indefinitely, or cap history (e.g.
   90 days) given this grows by ~50 rows/day (11 sectors + 39 industries)?
5. **Write cadence** — does every on-demand `scan-sectors`/`scan-industries`
   run also insert a snapshot row, or only the once-daily `monitor` cadence?
   (Matters for avoiding same-day double-counting if Shaun runs both in one
   day.)
6. **Report layout** — Rotation Flow (FROM/TO table + summary rollup) as a new
   section alongside the existing Top 5/Bottom 5/Full Ranking tables, or does
   it replace the level-based view? Reference tool shows only the flow view,
   no absolute-level ranking at all.
7. **Per-industry filter chips** (visible in the reference screenshot) — likely
   out of scope for a markdown report; confirm not wanted before dropping it
   silently.

## Validation (once built)

```powershell
uv run --directory investments/goat python -m pytest -q

# On the VPS via invoke_investments.ps1 — never run locally against the real DB:
.\scripts\invoke_investments.ps1 -Package goat -Command "scan-sectors"
.\scripts\invoke_investments.ps1 -Package goat -Command "scan-industries"
.\scripts\invoke_investments.ps1 -Package goat -Command "monitor"
```
