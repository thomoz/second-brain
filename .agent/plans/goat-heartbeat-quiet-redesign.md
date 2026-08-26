# Feature: Goat Heartbeat Scanner — "Quiet" Leg Redesign

The following plan should be complete, but it's important that you validate documentation and
codebase patterns and task sanity before you start implementing. Pay special attention to naming
of existing utils, types, and constants — import from the right files, reuse the constants that
already exist (`GOAT_MA_LONG_DAYS`, `GOAT_SECTOR_MA_SHORT_DAYS`, `GOAT_SECTOR_SLOPE_LOOKBACK_DAYS`,
`GOAT_SECTOR_CROSS_RECENCY_DAYS`) rather than adding duplicates.

## Feature Description

The Goat weekly heartbeat scanner (`investments/goat/goat/heartbeat.py`, orchestrated by
`heartbeat_scan.py`) screens S&P 500 constituents inside currently-rising sectors for the webinar's
"heartbeat" entry pattern: a smooth, low-volatility sideways consolidation followed by a fresh
breakout above the 50-day moving average with that MA turning up.

It has flagged **zero candidates on every run since it shipped 2026-08-17**. Diagnosis
(`investments/goat/heartbeat-quiet-redesign-handoff.md`, diagnostic run 2026-08-26): the
consolidation ("quiet") leg is structurally unable to pass. It measures quietness as *"is today's
Bollinger Band Width in the calmest 10% of days versus this stock's own trailing 252 trading
days?"* — which needs ~345 trading days of history just to compute one usable reading, but the tool
only fetches ~343. Result: `squeeze_fraction` (needs ≥ 0.80) is pinned at 0.00 for 27 of 42
hand-checked large-cap names, sample max 0.25.

This feature **replaces the BBW-percentile squeeze leg** with a direct, recent-window definition of
the heartbeat base that behaves like reading the pattern off a chart:

1. **Tight sideways base** — the high-low range of closes over the ~3-month base window is a small
   % of the base's own average (a direct measure, no trailing-year anchor), and most days sit
   inside a tighter inner band (the "smooth up-down-up-down" shape test).
2. **Position of strength** — during the base, price held at/above its 150-day MA (small dip
   tolerance), that 150-day MA is flat-to-rising, and price spent most of the base at/below its
   50-day MA (so the breakout is a genuine reclaim).
3. **Breakout** — unchanged: a fresh cross up through the 50-day MA with the 50-day MA sloping up.

The `heartbeat_scan.py` orchestration, the S&P 500 universe scrape, the fundamentals survival
context, the `goat_pending_candidates` staging, the report renderer, the weekly Saturday timer, and
the CLI all stay exactly as they are. Only `heartbeat.py`, its config constants, and its tests
change.

## User Story

As Shaun, running Goat's weekly heartbeat scan to surface individual stocks worth a chart look
inside sectors that are already rising
I want the scan's "is this stock in a quiet consolidation" test to actually work on real market
history — measured directly against the recent past and anchored to the 50/150-day moving averages
the rest of Goat already uses
So that the scanner produces real candidates to review instead of an empty table every week, and
the ones it flags genuinely look like a heartbeat base against a plotted 50 + 150 MA.

## Problem Statement

`heartbeat.py::_is_in_squeeze` classifies a day as "quiet" only if its Bollinger Band Width sits
at/below its own trailing `GOAT_HEARTBEAT_BBW_PERCENTILE_LOOKBACK_DAYS` (252-trading-day)
`GOAT_HEARTBEAT_BBW_PERCENTILE` (10th) percentile. `.rolling(252).quantile(...)` returns `NaN` for
the first 251 rows, and `_is_in_squeeze`'s `.fillna(False)` force-stamps those rows "not quiet."
`check_heartbeat_breakout` then requires `GOAT_HEARTBEAT_SQUEEZE_MIN_FRACTION` (0.80) of the 63 days
immediately before the breakout cross to be "quiet."

The math (from the handoff):

- `GOAT_HEARTBEAT_HISTORY_LOOKBACK_DAYS = 500` calendar days ≈ 343 trading days from yfinance.
- 252 of those are burned building the percentile yardstick → only ~91 carry a real reading, and
  after the 20-day Bollinger warm-up, ~73.
- The 63-day pre-cross window needs 63 *consecutive valid* days, all landing in the ~2 weeks before
  a fresh cross. With ~73 valid days total it barely fits, and the force-stamped zone drags the
  fraction toward zero.

The Phase 3 plan (`.agent/plans/completed/goat-phase3-heartbeat-scanner.md`, "RESEARCH RESOLVED …
BINDING") said the BBW-percentile choice should not be revisited *"without equally real
justification (e.g. a manual validation run showing BBW-squeeze is producing obviously wrong
candidates against real charts)."* Zero candidates across the entire S&P 500 for 10 straight days,
with the quiet score pinned near 0.00 for 42 of 42 hand-picked names, is that justification —
confirmed by Shaun 2026-08-26.

## Solution Statement

Rewrite `check_heartbeat_breakout`'s consolidation leg as three direct, recent-window tests, all
close-only (the price series from `price_history.fetch_close_history` has **no intraday high/low** —
every measure must be built from closes):

1. **Base range** — over the `GOAT_HEARTBEAT_MIN_DURATION_DAYS` (63) window of closes ending the
   day before the most recent 50DMA cross: `(base.max() - base.min()) / base.mean() * 100` must be
   ≤ `GOAT_HEARTBEAT_BASE_RANGE_MAX_PCT` (new, 15.0 — see research note below).
2. **Base smoothness** — at least `GOAT_HEARTBEAT_BASE_SMOOTHNESS_MIN_FRACTION` (0.80, renamed from
   `GOAT_HEARTBEAT_SQUEEZE_MIN_FRACTION`) of the base-window closes sit within
   ± `GOAT_HEARTBEAT_BASE_INNER_BAND_PCT` (new, 8.0) of the base-window mean. Catches a base that
   is flat for weeks then takes one big step and back — that satisfies the outright range ceiling
   but is not a "smooth up-down-up-down" heartbeat.
3. **Position of strength**:
   - During the base window, price never closed more than `GOAT_HEARTBEAT_MA_LONG_TOLERANCE_PCT`
     (new, 3.0) below its 150-day MA, **and** price is at/above its 150-day MA on the breakout bar
     itself.
   - The 150-day MA is flat-to-rising: `ma150.iloc[-1] >= ma150.iloc[-1 -
     GOAT_HEARTBEAT_MA_LONG_SLOPE_LOOKBACK_DAYS]` (new lookback, 20 — the existing
     `GOAT_SECTOR_SLOPE_LOOKBACK_DAYS` of 5 is right for the fast 50DMA but far too short for a
     150-day line, which barely moves in a trading week).
   - During the base window, at least `GOAT_HEARTBEAT_BASE_BELOW_MA50_MIN_FRACTION` (new, 0.6) of
     closes were at/below the 50-day MA — so the breakout cross-up is a genuine reclaim of the 50,
     not noise chopping across a flat fast MA (Shaun confirmed this shape requirement 2026-08-26).

The **breakout leg is unchanged**: fresh cross up (`crossed_above`) within
`GOAT_SECTOR_CROSS_RECENCY_DAYS` (10) trading days, and the 50DMA sloping up over
`GOAT_SECTOR_SLOPE_LOOKBACK_DAYS` (5).

`bollinger_width_series` and `_is_in_squeeze` are **deleted** — nothing else in the codebase
imports them (`grep` confirms: only `heartbeat.py`, its tests, and the handoff's historical
diagnostic snippet). `GOAT_HEARTBEAT_BBW_PERCENTILE_LOOKBACK_DAYS`,
`GOAT_HEARTBEAT_BBW_PERCENTILE`, `GOAT_HEARTBEAT_BBW_PERIOD_DAYS`, and
`GOAT_HEARTBEAT_BBW_STD_MULTIPLIER` are removed from `config.py`.

**New minimum-history requirement**:
`GOAT_MA_LONG_DAYS` (150) + `GOAT_HEARTBEAT_MIN_DURATION_DAYS` (63) +
`GOAT_HEARTBEAT_MA_LONG_SLOPE_LOOKBACK_DAYS` (20) + `GOAT_SECTOR_CROSS_RECENCY_DAYS` (10) = **243
trading days**. This guarantees the 150-day MA is non-`NaN` across the entire base window even when
the most recent cross is at the far edge of the fresh window. Below this, return `verdict="unknown"`
honestly (the current guard rigs an `"ok"`/no-fire instead). `GOAT_HEARTBEAT_HISTORY_LOOKBACK_DAYS`
stays 500 calendar days (~343 trading days) — comfortably above 243 with ~100 days of slack for the
base window to sit earlier than the freshest possible cross; the handoff explicitly says not to
shrink it below ~1 year + base + slope + margin, and 500 already sits right at that floor.

### Research note — why direct range %, and why 15.0 (v1/tunable)

Light research pass 2026-08-26, same discipline as the original BBW-vs-VCP call:

- **A fixed BBW threshold was rejected.** StockCharts' Bollinger BandWidth ChartSchool page (Bollinger's
  own reference) states plainly that no universal BandWidth threshold exists — utilities average
  <5, tech >7 on the same setting — "traders must establish baseline ranges for each security
  independently." A fixed BBW cutoff across 500 tickers reproduces the exact
  generalisation failure this redesign exists to fix. The self-percentile approach *was* the
  per-security baseline — it just needs more history than the tool fetches, and a direct range %
  sidesteps the history problem entirely.
- **Direct high-low range % has sourced numbers behind it.** Minervini's VCP literature
  (finermarketpoints, deepvue, tradingmomentum): a whole consolidation base runs 10–35% deep; the
  *final* tight contraction is 3–8% over 1–3 weeks; a final contraction over ~10% is "wider /
  sloppier and fails more often." The Goat webinar's "smooth heartbeat, 3 months minimum" is a
  broader structure than Minervini's final 1–3-week contraction, so a threshold between his
  "final contraction ≤ ~8–10%" and his "whole base ≤ 35%" is defensible. **15.0%** is the v1
  number — mid-way, leaning tight. Document it as v1/tunable exactly like
  `GOAT_SECTOR_CROSS_RECENCY_DAYS`, not literature-final.
- `GOAT_HEARTBEAT_BASE_INNER_BAND_PCT = 8.0` (~half the range ceiling), `..._TOLERANCE_PCT = 3.0`,
  `..._SLOPE_LOOKBACK_DAYS = 20`, `..._BELOW_MA50_MIN_FRACTION = 0.6` are all v1/tunable design
  numbers, not sourced — flag each as such in its config comment.

## Feature Metadata

**Feature Type**: Bug Fix (a shipped feature that has never once produced its intended output) with
an Enhancement-shaped fix (the consolidation metric is redesigned, not merely retuned).
**Estimated Complexity**: Medium — one module's core function rewritten, six config constants
added / one renamed / four removed, and its test file substantially rewritten (the synthetic
price-series builders need rebuilding around the new gates). No new dependency, no DB change, no
orchestration change, no schema change, no new file.
**Primary Systems Affected**: `investments/goat/goat/heartbeat.py`, `investments/goat/goat/config.py`,
`investments/goat/goat/tests/test_heartbeat.py`. Doc touch-ups: `investments/goat/HANDOFF.md`,
`investments/goat/heartbeat-quiet-redesign-handoff.md`, `investments/TOOLS.md`.
**Dependencies**: None new. `pandas`, `mytrader.checks.CheckResult` (already imported).

---

## CONTEXT REFERENCES

### Relevant Codebase Files — YOU MUST READ THESE BEFORE IMPLEMENTING

- `investments/goat/heartbeat-quiet-redesign-handoff.md` (whole file) — the diagnosis, Shaun's
  direction, the seven open questions (all four that needed Shaun's input are resolved — see
  "Decisions confirmed" below), and the "Explicitly NOT in scope" list. Read first.
- `investments/goat/goat/heartbeat.py` (whole file, 131 lines) — the file being rewritten. Key
  spans: `min_len` history guard (lines 55–64); ported 50DMA cross+slope block (lines 66–74);
  `bbw`/`in_squeeze` (lines 76–77, being deleted); `sign_changes.empty` early `ok` (lines 79–84);
  `cross_date` / `crossed_above` / `trading_days_since_cross` / `fresh` (lines 86–90 — **keep this
  exactly**); `pre_cross_window` / `squeeze_fraction` / `sustained_squeeze` (lines 92–99 — being
  replaced); `data` dict (lines 101–108); `interesting` branch (lines 110–119); trailing `ok`
  branch (lines 121–130).
- `investments/goat/goat/config.py` — the `GOAT_HEARTBEAT_*` block is lines 227–262. Also read the
  comment style around `GOAT_SECTOR_CROSS_RECENCY_DAYS` (lines 82–88) and
  `GOAT_150DMA_FLAG_PCT` (lines 27–30) as the templates for v1/tunable and
  Shaun's-number documentation density. Constants reused unchanged: `GOAT_MA_LONG_DAYS` (line 21),
  `GOAT_SECTOR_MA_SHORT_DAYS` (line 75), `GOAT_SECTOR_SLOPE_LOOKBACK_DAYS` (line 78),
  `GOAT_SECTOR_CROSS_RECENCY_DAYS` (line 82).
- `investments/goat/goat/exit_check.py` (lines 26–30) — `ma = close.rolling(config.GOAT_MA_LONG_DAYS).mean()`
  is the exact 150-day MA idiom to reuse for the position-of-strength leg;
  `pct_below = ((ma - close) / ma * 100)` (line 27) is the "% below the 150DMA" sign convention
  already established in this package (positive = below the MA) — match it.
- `investments/goat/goat/sector_rotation.py` (lines 53–113, esp. 67–75) — `check_sector_breakout`'s
  sign-flip cross-detection block. `heartbeat.py` already holds a ported copy of this (lines
  66–74); the rewrite keeps that copy verbatim. Do **not** refactor either into a shared helper
  (see the module docstring's own note, `heartbeat.py` lines 11–16).
- `investments/goat/goat/heartbeat_scan.py` (whole file, esp. lines 42–71) — the per-ticker loop.
  It calls `heartbeat.check_heartbeat_breakout(ticker, sector_label, close)` and reads only
  `check.verdict` and `check.detail`. **Confirm during implementation that the signature and these
  two attributes are unchanged** — then this file needs no edit. It passes
  `config.GOAT_HEARTBEAT_HISTORY_LOOKBACK_DAYS` (unchanged) to `fetch_close_history`.
- `investments/goat/goat/tests/test_heartbeat.py` (whole file, 85 lines) — being rewritten. The
  synthetic-series helpers (`_noisy_prices`, `_tight_prices`, `_rising_tail`, `_heartbeat_series`,
  `_no_squeeze_series`, lines 10–47) are BBW-era and must be rebuilt. The
  `test_check_heartbeat_breakout_normal_volatility_does_not_fire` case (lines 58–66) is the
  gating-proof regression test — its intent (breakout leg alone passes, base leg does not, verdict
  stays `ok`) must be preserved with the new base leg (handoff Q7).
- `investments/goat/goat/tests/test_sector_rotation.py` (lines 8–48) — `_dates`, `_flat_then_move`,
  `_series_with_cross`, `_declining_then_spike_series` are the price-series test-builder idioms to
  mirror. `_series_with_cross`'s "lead-in of length `ma_days + slope_lookback + 20`, then a step"
  construction (lines 28–34) is the closest existing template for building a controlled 50DMA
  cross.
- `investments/goat/goat/tests/conftest.py` (whole file) — `_no_real_price_history_fetch` (autouse,
  lines 50–57) stubs `fetch_close_history` to `None` globally; `test_heartbeat.py` builds its own
  `pd.Series` and calls `check_heartbeat_breakout` directly, so it is unaffected.
  `_isolate_goat_report_path` (lines 29–47) already isolates `GOAT_HEARTBEAT_CANDIDATES_MD_PATH`;
  no new path, so no conftest change.
- `investments/goat/goat/tests/test_exit_check.py` (lines 12–19) — `_flat_then` (a
  `GOAT_MA_LONG_DAYS`-day flat lead-in so the 150-day MA is stable regardless of the tail) is a
  useful pattern for the 150DMA-position test cases.
- `investments/my-trader/mytrader/checks/__init__.py` (whole file, 15 lines) — `CheckResult` is
  `name` / `verdict` (`"ok"` | `"flag"` | `"info"` | `"unknown"`, and `"interesting"` by the
  convention below) / `detail` / `data: dict`.
- `.agent/plans/completed/goat-phase3-heartbeat-scanner.md` — the plan this supersedes for the
  heartbeat leg only. Its "RESEARCH RESOLVED … BINDING" section (lines 42–56) and its `GOTCHA`
  about 500 calendar days being "comfortable margin" (line 222) are the exact claims this plan
  overturns, with justification. Mirror its task structure and `GOTCHA`-callout style.
- `.agent/plans/goat-rotation-trend-tracking.md` — a same-package sibling plan drafted the same
  week; mirror its decision-documentation and "Patterns to Follow" style.

### New Files to Create

None. This is a rewrite of one existing module plus its test file.

### Relevant Documentation

None to fetch during implementation — the research is captured above and in the handoff. Pure
`pandas` + this codebase's own conventions.

### Patterns to Follow

**CheckResult verdict convention** (`.agent/plans/completed/goat-phase3-heartbeat-scanner.md`
line 101, `sector_rotation.py` lines 53–56): `"flag"` = a genuine risk / action-required signal
(Phase 1's exit check only); `"interesting"` = an opportunity signal — the heartbeat breakout uses
this, never `"flag"`; `"unknown"` = missing / insufficient data; `"ok"` = checked, pattern not
present.

**Check-interpretation convention** (project memory `feedback_check_interpretation_convention.md`):
every `detail` string spells out full metric names (not abbreviations) and says which direction is
good, not just a number vs a threshold. E.g. not "range 12% < 15%" but "the close stayed inside a
12% high-low band over the 63-day base (tighter is better; the ceiling is 15%)". `exit_check.py`'s
`detail` text (lines 50–62) and `fundamentals_context.py`'s `summary` builder (lines 62–89) are the
in-package models.

**Config constant documentation density** (`config.py` throughout): every threshold gets a trailing
`#` comment block — what it is, where it came from (sourced-with-citation vs "Shaun's number, date"
vs "v1/tunable, not literature-final"), and its relationship to neighbouring constants. New
constants that are design choices, not sourced numbers, must say so explicitly (see
`GOAT_SECTOR_CROSS_RECENCY_DAYS`'s comment).

**`*_series()` full-history vs `compute_*()` latest-value split** (`gold_technicals.py` docstring
lines 1–11): not directly relevant now that `bollinger_width_series` is being removed, but the
principle — one formula, no second drifting copy — is why the 50DMA cross block stays a single
ported copy and is not re-derived.

**Positive-`pct_below` sign convention for MA distance** (`exit_check.py` line 27):
`(ma - close) / ma * 100` → positive means price is *below* the MA. Reuse this sign so the new
`data` fields read consistently with the rest of the package.

**Graceful degradation** (every Goat fetch loop): `heartbeat_scan.py`'s per-ticker `try/except`
(lines 42–73) already isolates a bad ticker. `check_heartbeat_breakout` must never raise on a
short or degenerate series — return `"unknown"` for too-short, and guard against
`base.mean() == 0` / empty slices even though real price data never hits those.

---

## DECISIONS CONFIRMED WITH SHAUN (2026-08-26, this planning session)

The handoff's four open questions that needed Shaun's input — answered "y" to all recommendations:

1. **Base tightness measure** → direct high-low close range over the ~63-day base window as a % of
   the base mean, ≤ a fixed threshold (15.0, v1/tunable). **Not** a fixed BBW threshold (Bollinger's
   own guidance says a fixed BBW cutoff doesn't generalise across securities — the exact bug being
   fixed). Keep a separate ≥80%-of-days inner-band "smoothness" test alongside the outright range
   ceiling.
2. **50DMA during the base** → require price to have spent most of the base at/below the 50DMA
   (`GOAT_HEARTBEAT_BASE_BELOW_MA50_MIN_FRACTION = 0.6`), so the cross-up is a genuine reclaim.
3. **"Near or above" the 150DMA during the base** → allow price to dip up to 3% below the 150DMA
   during the base (`GOAT_HEARTBEAT_MA_LONG_TOLERANCE_PCT = 3.0`), but require price at/above the
   150DMA on the breakout bar itself.
4. **150DMA slope** → flat-to-rising (`ma150.iloc[-1] >= ma150.iloc[-1 - 20]`), not strictly
   rising.

Planner's own calls (documented, not requiring sign-off): history-fetch size stays 500;
`GOAT_HEARTBEAT_MA_LONG_SLOPE_LOOKBACK_DAYS = 20` (new); keep the 0.80-of-days framing for
smoothness (renamed constant); `bollinger_width_series` / `_is_in_squeeze` and the four BBW config
constants removed entirely rather than repurposed; regression coverage keeps the "breakout leg
alone passes, base does not → still `ok`" test (handoff Q7).

### Explicitly NOT in scope (from the handoff — do not build)

- No change to Phase 1 / Phase 2 cadence or thresholds.
- No VCP pivot/swing-detection (still deferred, same as Phase 3).
- No change to `fundamentals_context.py`, the insolvency suppression, `heartbeat_scan.py`'s
  orchestration, `sp500_universe.py`, the report renderer, the `goat_pending_candidates` staging,
  the CLI, the systemd units, or `deploy.ps1`.
- No batched / parallel yfinance fetching.
- No new alerting behaviour.

---

## IMPLEMENTATION PLAN

### Phase 1: Config

Add / rename / remove the `GOAT_HEARTBEAT_*` constants. Isolated change — nothing imports the
removed ones outside `heartbeat.py` and its tests.

### Phase 2: Core rewrite — `heartbeat.py`

Delete `bollinger_width_series` and `_is_in_squeeze`. Rewrite `check_heartbeat_breakout`:
new `min_len`; keep the ported 50DMA cross+slope block verbatim; add the 150DMA computation and
slope check; replace the squeeze block with the base-range + smoothness + position-of-strength
tests; rebuild the `data` dict and `detail` strings. Rewrite the module docstring.

### Phase 3: Tests — `test_heartbeat.py`

Rebuild the synthetic price-series helpers around the new gates. Cover: full valid pattern fires;
each individual gate failing keeps the verdict `ok` (with the breakout leg still passing, proving
the base leg gates); too-short history → `unknown`; stale cross → `ok`; no cross → `ok`.

### Phase 4: Docs + validation

Update `HANDOFF.md`, the handoff doc's `## Status` line, `investments/TOOLS.md`. Run the full goat
suite, ruff, mypy. Run the (DB-free, local-safe) diagnostic to confirm the base score is no longer
pinned near zero. The full `scan-heartbeat` run is VPS-only (Level 4).

---

## STEP-BY-STEP TASKS

Execute in order, top to bottom. Each task's `VALIDATE` command must pass before moving on.

### Task 1: UPDATE `investments/goat/goat/config.py` — heartbeat constants

- **REMOVE** these four constants (lines 242–262 area) and their comment blocks entirely:
  - `GOAT_HEARTBEAT_BBW_PERCENTILE_LOOKBACK_DAYS`
  - `GOAT_HEARTBEAT_BBW_PERCENTILE`
  - `GOAT_HEARTBEAT_BBW_PERIOD_DAYS`
  - `GOAT_HEARTBEAT_BBW_STD_MULTIPLIER`
- **RENAME** `GOAT_HEARTBEAT_SQUEEZE_MIN_FRACTION` → `GOAT_HEARTBEAT_BASE_SMOOTHNESS_MIN_FRACTION`
  (keep the value `0.8`; rewrite the comment for the new meaning — see below).
- **KEEP** `GOAT_HEARTBEAT_HISTORY_LOOKBACK_DAYS = 500` and `GOAT_HEARTBEAT_MIN_DURATION_DAYS = 63`.
  Rewrite `GOAT_HEARTBEAT_HISTORY_LOOKBACK_DAYS`'s comment: it no longer needs to cover a
  252-trading-day percentile window; it now must cover `GOAT_MA_LONG_DAYS` (150) +
  `GOAT_HEARTBEAT_MIN_DURATION_DAYS` (63) + `GOAT_HEARTBEAT_MA_LONG_SLOPE_LOOKBACK_DAYS` (20) +
  `GOAT_SECTOR_CROSS_RECENCY_DAYS` (10) ≈ 243 trading days, with weekend/holiday margin — 500
  calendar days ≈ 343 trading days clears that with ~100 days of slack. Rewrite
  `GOAT_HEARTBEAT_MIN_DURATION_DAYS`'s comment to say it is now the length of the tight-base
  measurement window (it was already 63 for the pre-cross squeeze window — same value, clearer
  meaning).
- **ADD**, in the `GOAT_HEARTBEAT_*` block, with full doc-comments matching the file's density:
  ```python
  # Tight-base ("heartbeat") consolidation leg -- redesigned 2026-08-26 per
  # .agent/plans/goat-heartbeat-quiet-redesign.md. Replaces the old BBW-percentile
  # squeeze, which was structurally unable to pass on real history (needed ~345
  # trading days to compute one usable reading; the tool fetches ~343). All measures
  # below are direct and recent-window -- no trailing-year self-percentile anchor.
  # Price series is close-only (no intraday high/low), so range is a close-range.
  GOAT_HEARTBEAT_BASE_RANGE_MAX_PCT = 15.0  # max (max_close - min_close) / mean_close
      # over the GOAT_HEARTBEAT_MIN_DURATION_DAYS base window, as a percent -- tighter
      # is better. Between Minervini's VCP "final contraction <= ~8-10%" and "whole
      # base <= 35%" (finermarketpoints / deepvue / tradingmomentum, 2026-08-26); the
      # Goat webinar's "smooth 3-month heartbeat" is broader than the final
      # contraction, so this leans toward the tight end of the base range. v1/tunable,
      # not literature-final -- same status as GOAT_SECTOR_CROSS_RECENCY_DAYS.
  GOAT_HEARTBEAT_BASE_INNER_BAND_PCT = 8.0  # at least
      # GOAT_HEARTBEAT_BASE_SMOOTHNESS_MIN_FRACTION of base-window closes must sit
      # within +/- this percent of the base-window mean -- the "smooth up-down-up-down"
      # shape test (webinar's own words), distinct from the outright
      # GOAT_HEARTBEAT_BASE_RANGE_MAX_PCT ceiling which one lone spike day could still
      # satisfy. ~half the range ceiling. v1/tunable design number, not sourced.
  GOAT_HEARTBEAT_BASE_SMOOTHNESS_MIN_FRACTION = 0.8  # >= this fraction of base-window
      # closes must be inside the GOAT_HEARTBEAT_BASE_INNER_BAND_PCT band. Renamed from
      # GOAT_HEARTBEAT_SQUEEZE_MIN_FRACTION (same 0.8 value) -- the webinar describes
      # "smooth up-down-up-down", not a dead-flat line, so a strict 100%-of-days test
      # would misfire on ordinary noise. v1/tunable.
  GOAT_HEARTBEAT_BASE_BELOW_MA50_MIN_FRACTION = 0.6  # >= this fraction of base-window
      # closes must be at/below the 50-day MA, so the breakout cross-up is a genuine
      # reclaim of the 50 rather than noise chopping across a flat fast MA. Shaun
      # confirmed this shape requirement 2026-08-26. v1/tunable design number.
  GOAT_HEARTBEAT_MA_LONG_TOLERANCE_PCT = 3.0  # during the base, price may close up to
      # this percent below its 150-day MA (the webinar's exit rule explicitly tolerates
      # brief dips through the 150) -- but price must be AT/ABOVE the 150-day MA on the
      # breakout bar itself. Distinct from GOAT_150DMA_FLAG_PCT (0.0): that is Shaun's
      # "alert the instant a HOLDING touches its 150DMA" exit number; this is an
      # entry-pattern shape tolerance, a different purpose. v1/tunable design number.
  GOAT_HEARTBEAT_MA_LONG_SLOPE_LOOKBACK_DAYS = 20  # 150-day MA today vs. N trading days
      # ago for the flat-to-rising check (ma150.iloc[-1] >= ma150.iloc[-1 - N]).
      # Deliberately longer than GOAT_SECTOR_SLOPE_LOOKBACK_DAYS (5, correct for the
      # fast 50DMA) -- a 150-day line barely moves in a trading week, so 5 days of it
      # is noise. ~1 trading month. v1/tunable design number.
  ```
- **GOTCHA**: put the removals and additions in the right block so the file still reads top-to-bottom
  by feature. The `GOAT_HEARTBEAT_CANDIDATES_MD_PATH` line (currently line 300) stays where it is.
- **GOTCHA**: `grep -rn "GOAT_HEARTBEAT_BBW\|GOAT_HEARTBEAT_SQUEEZE_MIN_FRACTION" investments/`
  before and after — the only hits outside this file must be `heartbeat.py`, `test_heartbeat.py`,
  and the handoff `.md` (docs, left alone). If `test_monitor.py` or `conftest.py` reference any of
  them, stop and reassess (they should only touch `GOAT_HEARTBEAT_CANDIDATES_MD_PATH`).
- **VALIDATE**:
  `uv run --directory investments/goat python -c "from goat import config; print(config.GOAT_HEARTBEAT_BASE_RANGE_MAX_PCT, config.GOAT_HEARTBEAT_BASE_SMOOTHNESS_MIN_FRACTION, config.GOAT_HEARTBEAT_MA_LONG_SLOPE_LOOKBACK_DAYS); assert not hasattr(config, 'GOAT_HEARTBEAT_BBW_PERCENTILE')"`

### Task 2: REWRITE `investments/goat/goat/heartbeat.py`

- **REMOVE**: `bollinger_width_series` (lines 26–32) and `_is_in_squeeze` (lines 35–45) entirely.
- **REWRITE the module docstring** (lines 1–16) to describe the new leg. Keep the paragraph that
  explains the 50DMA cross+slope block is a deliberate independent copy of
  `sector_rotation.check_sector_breakout`'s idiom and must not be refactored into a shared helper
  (that reasoning is unchanged). Drop all BBW / `gold_technicals` porting references. Point at
  `.agent/plans/goat-heartbeat-quiet-redesign.md` and
  `investments/goat/heartbeat-quiet-redesign-handoff.md`.
- **REWRITE `check_heartbeat_breakout`**. Structure:

  ```python
  def check_heartbeat_breakout(ticker: str, sector_label: str, close: pd.Series) -> CheckResult:
      base_window = config.GOAT_HEARTBEAT_MIN_DURATION_DAYS
      min_len = (
          config.GOAT_MA_LONG_DAYS
          + base_window
          + config.GOAT_HEARTBEAT_MA_LONG_SLOPE_LOOKBACK_DAYS
          + config.GOAT_SECTOR_CROSS_RECENCY_DAYS
      )
      if len(close) < min_len:
          return CheckResult(
              name="heartbeat_breakout", verdict="unknown",
              detail=f"{ticker} ({sector_label}): insufficient price history for a "
                     f"heartbeat check (needs {min_len} trading days, has {len(close)})",
          )

      ma50 = close.rolling(config.GOAT_SECTOR_MA_SHORT_DAYS).mean()
      ma150 = close.rolling(config.GOAT_MA_LONG_DAYS).mean()

      # --- 50DMA cross detection: ported verbatim from sector_rotation.check_sector_breakout ---
      diff = (close - ma50).dropna()
      sign = diff.gt(0).astype(int) - diff.lt(0).astype(int)
      sign_changed = sign.diff().fillna(0) != 0
      sign_changes = sign[sign_changed]

      slope_up_50 = bool(
          ma50.iloc[-1] > ma50.iloc[-1 - config.GOAT_SECTOR_SLOPE_LOOKBACK_DAYS]
      )

      if sign_changes.empty:
          return CheckResult(
              name="heartbeat_breakout", verdict="ok",
              detail=f"{ticker} ({sector_label}): no 50-day MA cross in available history; "
                     f"50-day MA currently {'rising' if slope_up_50 else 'falling'}",
          )

      cross_date = sign_changes.index[-1]
      crossed_above = bool(sign_changes.iloc[-1] > 0)
      cross_pos = close.index.get_loc(cross_date)
      trading_days_since_cross = (len(close) - 1) - cross_pos
      fresh = trading_days_since_cross <= config.GOAT_SECTOR_CROSS_RECENCY_DAYS

      # Bail before computing base metrics if the breakout leg can't pass -- avoids
      # NaN-slice edge cases when an old downside cross would put the base window
      # before the 150DMA warm-up.
      if not crossed_above or not fresh:
          direction = "crossed above" if crossed_above else "crossed below"
          return CheckResult(
              name="heartbeat_breakout", verdict="ok",
              detail=f"{ticker} ({sector_label}): last 50-day MA event was a {direction} "
                     f"{trading_days_since_cross} trading day(s) ago "
                     f"(fresh window is {config.GOAT_SECTOR_CROSS_RECENCY_DAYS} days) -- "
                     f"not a fresh breakout, not a heartbeat entry",
              data={"crossed_above": crossed_above,
                    "trading_days_since_cross": trading_days_since_cross,
                    "slope_up": slope_up_50},
          )

      # --- base window: the `base_window` closes ending the day BEFORE the cross ---
      base_close = close.iloc[:cross_pos].tail(base_window)
      base_ma50 = ma50.iloc[:cross_pos].tail(base_window)
      base_ma150 = ma150.iloc[:cross_pos].tail(base_window)
      # min_len guarantees these are full-length and NaN-free, but guard anyway:
      if len(base_close) < base_window or base_ma150.isna().any() or float(base_close.mean()) <= 0:
          return CheckResult(
              name="heartbeat_breakout", verdict="unknown",
              detail=f"{ticker} ({sector_label}): base window not fully covered by price "
                     f"history / 150-day MA -- cannot assess the heartbeat base",
          )

      base_mean = float(base_close.mean())
      base_range_pct = float(base_close.max() - base_close.min()) / base_mean * 100
      inner = config.GOAT_HEARTBEAT_BASE_INNER_BAND_PCT / 100
      within_inner = ((base_close - base_mean).abs() / base_mean) <= inner
      smoothness_fraction = float(within_inner.mean())
      below_ma50_fraction = float((base_close <= base_ma50).mean())

      # positive pct_below == price is BELOW the MA (exit_check.py sign convention)
      base_pct_below_ma150 = (base_ma150 - base_close) / base_ma150 * 100
      max_dip_below_ma150_pct = float(base_pct_below_ma150.max())
      price_pct_below_ma150_now = float((ma150.iloc[-1] - close.iloc[-1]) / ma150.iloc[-1] * 100)
      ma150_slope_up = bool(
          ma150.iloc[-1] >= ma150.iloc[-1 - config.GOAT_HEARTBEAT_MA_LONG_SLOPE_LOOKBACK_DAYS]
      )

      base_is_narrow = base_range_pct <= config.GOAT_HEARTBEAT_BASE_RANGE_MAX_PCT
      base_is_smooth = smoothness_fraction >= config.GOAT_HEARTBEAT_BASE_SMOOTHNESS_MIN_FRACTION
      base_reclaims_ma50 = below_ma50_fraction >= config.GOAT_HEARTBEAT_BASE_BELOW_MA50_MIN_FRACTION
      held_above_ma150 = max_dip_below_ma150_pct <= config.GOAT_HEARTBEAT_MA_LONG_TOLERANCE_PCT
      above_ma150_now = price_pct_below_ma150_now <= 0

      data = {
          "base_range_pct": round(base_range_pct, 2),
          "base_smoothness_fraction": round(smoothness_fraction, 2),
          "base_below_ma50_fraction": round(below_ma50_fraction, 2),
          "max_dip_below_ma150_pct": round(max_dip_below_ma150_pct, 2),
          "price_vs_ma150_now_pct": round(-price_pct_below_ma150_now, 2),  # +ve == above
          "ma150_slope_up": ma150_slope_up,
          "cross_date": cross_date.date().isoformat(),
          "crossed_above": crossed_above,
          "trading_days_since_cross": trading_days_since_cross,
          "slope_up": slope_up_50,  # key name kept -- existing tests / data convention
      }

      base_ok = (
          base_is_narrow and base_is_smooth and base_reclaims_ma50
          and held_above_ma150 and above_ma150_now and ma150_slope_up
      )
      if base_ok and slope_up_50:
          detail = (
              f"{ticker} ({sector_label}): {base_window} trading days of tight sideways "
              f"consolidation before the breakout -- {base_range_pct:.1f}% high-low close range "
              f"vs. the {config.GOAT_HEARTBEAT_BASE_RANGE_MAX_PCT:.0f}% ceiling (tighter is "
              f"better), {smoothness_fraction * 100:.0f}% of days inside the smooth inner band, "
              f"price at/below its 50-day MA on {below_ma50_fraction * 100:.0f}% of base days -- "
              f"held at/above its 150-day MA throughout (worst dip {max_dip_below_ma150_pct:.1f}% "
              f"below, within the {config.GOAT_HEARTBEAT_MA_LONG_TOLERANCE_PCT:.0f}% tolerance) "
              f"with that 150-day MA flat-to-rising. Then a fresh cross above the 50-day MA "
              f"{trading_days_since_cross} trading day(s) ago, 50-day MA now sloping up -- "
              f"heartbeat entry signal (webinar Step 1)"
          )
          return CheckResult(name="heartbeat_breakout", verdict="interesting", detail=detail, data=data)

      reasons = []
      if not base_is_narrow:
          reasons.append(
              f"base high-low close range {base_range_pct:.1f}% exceeds the "
              f"{config.GOAT_HEARTBEAT_BASE_RANGE_MAX_PCT:.0f}% tightness ceiling"
          )
      if not base_is_smooth:
          reasons.append(
              f"only {smoothness_fraction * 100:.0f}% of base days sit inside the smooth inner "
              f"band (need {config.GOAT_HEARTBEAT_BASE_SMOOTHNESS_MIN_FRACTION * 100:.0f}%)"
          )
      if not base_reclaims_ma50:
          reasons.append(
              f"price was at/below its 50-day MA on only {below_ma50_fraction * 100:.0f}% of base "
              f"days, so the cross-up is not a clear reclaim"
          )
      if not held_above_ma150:
          reasons.append(
              f"price dipped {max_dip_below_ma150_pct:.1f}% below its 150-day MA during the base, "
              f"past the {config.GOAT_HEARTBEAT_MA_LONG_TOLERANCE_PCT:.0f}% tolerance"
          )
      if not above_ma150_now:
          reasons.append("price is below its 150-day MA on the breakout bar")
      if not ma150_slope_up:
          reasons.append("the 150-day MA is still sloping down")
      if not slope_up_50:
          reasons.append("the 50-day MA is not yet sloping up")

      return CheckResult(
          name="heartbeat_breakout", verdict="ok",
          detail=f"{ticker} ({sector_label}): fresh cross above the 50-day MA "
                 f"{trading_days_since_cross} trading day(s) ago, but not (yet) a heartbeat entry -- "
                 + "; ".join(reasons),
          data=data,
      )
  ```

- **PATTERN**: the 50DMA cross block is `heartbeat.py` lines 66–90 kept verbatim (which itself
  mirrors `sector_rotation.py` lines 67–90). The 150DMA computation mirrors `exit_check.py` line 26.
  The `reasons`-list-then-`"; ".join()` detail construction mirrors
  `fundamentals_context.py`'s `parts` builder (lines 62–87).
- **IMPORTS**: unchanged — `import pandas as pd`, `from mytrader.checks import CheckResult`,
  `from . import config`. Remove nothing from imports (all still used).
- **GOTCHA**: `close.index.get_loc(cross_date)` returns an `int` for a unique `DatetimeIndex` — the
  existing code (line 88) already relies on this and passes mypy; keep the same call, don't add a
  cast.
- **GOTCHA**: take `base_ma50` / `base_ma150` with the **same positional slice** as `base_close`
  (`.iloc[:cross_pos].tail(base_window)`) so their indexes align for the elementwise
  `base_close <= base_ma50` / `base_ma150 - base_close` comparisons. Do not `.dropna()` these
  slices independently or the lengths/indexes can diverge.
- **GOTCHA**: `above_ma150_now` uses `price_pct_below_ma150_now <= 0` (price at or above the MA
  qualifies) — matches the "at/above" wording of Shaun's decision #3, and the `<= 0` boundary
  mirrors `exit_check.py`'s inclusive treatment.
- **GOTCHA**: `ma150_slope_up` uses `>=` (flat-to-rising, Shaun's decision #4), not `>`.
- **GOTCHA**: the early `not crossed_above or not fresh` return happens *before* the base slice, so
  a stale or downside cross can never index into the 150DMA warm-up region. Keep that ordering.
- **VALIDATE**:
  `uv run --directory investments/goat ruff check goat/heartbeat.py && uv run --directory investments/goat mypy goat/heartbeat.py`

### Task 3: REWRITE `investments/goat/goat/tests/test_heartbeat.py`

- **IMPLEMENT**: new synthetic-series builders and cases. The builders must produce a series long
  enough for the new `min_len` (≥ 243 trading days) with a controllable lead-in trend, a
  controllable base window, and a controllable breakout tail. Suggested shape (tune the numbers so
  every `data` metric of the valid case sits comfortably mid-gate, not on a boundary — then derive
  each negative case by perturbing exactly one parameter):

  ```python
  from __future__ import annotations
  import math
  import pandas as pd
  from goat import config, heartbeat

  def _dates(n: int, start: str = "2024-01-01") -> pd.DatetimeIndex:
      return pd.date_range(start, periods=n, freq="D")

  def _lead(n: int = 200, start: float = 88.0, end: float = 103.0) -> list[float]:
      """Gently rising lead-in so the 150-day MA slopes up and ends just below the
      base level. End slightly ABOVE the base center so the 50-day MA stays over
      price through the base (satisfies BASE_BELOW_MA50_MIN_FRACTION)."""
      return [start + (end - start) * i / (n - 1) for i in range(n)]

  def _base(n: int, center: float, amp: float) -> list[float]:
      """Smooth oscillation: peak-to-trough == 2*amp, range% ~= 2*amp/center*100."""
      return [center + amp * math.sin(i / 3.0) for i in range(n)]

  def _breakout_tail(n: int, start_level: float, jump: float = 5.0, step: float = 1.3) -> list[float]:
      return [start_level + jump + i * step for i in range(n)]

  def _series(prices: list[float]) -> pd.Series:
      return pd.Series(prices, index=_dates(len(prices)))

  def _valid_heartbeat(base_amp: float = 2.5, tail_len: int = 7, lead_end: float = 103.0) -> pd.Series:
      lead = _lead(end=lead_end)
      base = _base(config.GOAT_HEARTBEAT_MIN_DURATION_DAYS + 3, center=101.0, amp=base_amp)
      tail = _breakout_tail(tail_len, base[-1])
      return _series(lead + base + tail)
  ```

- **CASES** (names are suggestions; keep the intent):
  - `test_fires_on_tight_base_then_fresh_breakout` — `_valid_heartbeat()` → `verdict == "interesting"`;
    assert `data["crossed_above"] is True`, `data["slope_up"] is True`, `data["ma150_slope_up"] is True`,
    `data["base_range_pct"] <= config.GOAT_HEARTBEAT_BASE_RANGE_MAX_PCT`.
  - `test_wide_base_does_not_fire` — `_valid_heartbeat(base_amp=12.0)` (peak-to-trough ~24% of
    ~101 → well over the 15% ceiling) → `verdict == "ok"`; assert the breakout leg still passed
    (`data["crossed_above"] is True`, `data["slope_up"] is True`) and
    `data["base_range_pct"] > config.GOAT_HEARTBEAT_BASE_RANGE_MAX_PCT`. **This is the
    gating-proof regression test (handoff Q7) — it replaces
    `test_check_heartbeat_breakout_normal_volatility_does_not_fire`.**
  - `test_spiky_base_does_not_fire` — a base that is flat then takes one ~12% step and back
    (range under the ceiling, but < 80% of days inside the inner band) → `verdict == "ok"`,
    `data["base_smoothness_fraction"] < config.GOAT_HEARTBEAT_BASE_SMOOTHNESS_MIN_FRACTION`.
    Build by overwriting ~6 mid-base points with `center + 11`.
  - `test_price_below_150dma_during_base_does_not_fire` — tight base but positioned well below a
    flat/declining 150-day MA (make `_lead` descend, e.g. `_lead(start=130, end=101)` so the
    150-day MA sits above price through the base) → `verdict == "ok"`,
    `data["max_dip_below_ma150_pct"] > config.GOAT_HEARTBEAT_MA_LONG_TOLERANCE_PCT`.
  - `test_falling_150dma_does_not_fire` — tight base, price near the 150, but the 150-day MA still
    sloping down (steep descending lead that hasn't flattened by the cross) → `verdict == "ok"`,
    `data["ma150_slope_up"] is False`.
  - `test_base_spent_above_ma50_does_not_fire` — tight base, 150-day MA fine, but price sat mostly
    *above* the 50-day MA through the base (make `lead_end` well below the base center, e.g.
    `_lead(end=95)`, so the rising 50-day MA stays under price) → `verdict == "ok"`,
    `data["base_below_ma50_fraction"] < config.GOAT_HEARTBEAT_BASE_BELOW_MA50_MIN_FRACTION`.
  - `test_insufficient_history_is_unknown` — `_series([100.0] * 200)` (< `min_len`) →
    `verdict == "unknown"`.
  - `test_stale_cross_does_not_fire` — `_valid_heartbeat(tail_len=config.GOAT_SECTOR_CROSS_RECENCY_DAYS + 12)`
    → `verdict == "ok"` (cross is now older than the fresh window).
  - `test_no_cross_in_history_is_ok` — `_series([100.0] * (min_len + 20))` (flat forever, no cross)
    → `verdict == "ok"`.
  - `test_downside_cross_does_not_fire` — a tight base then a *drop* through the 50-day MA within
    the fresh window → `verdict == "ok"`, `data["crossed_above"] is False`.
- **PATTERN**: `test_sector_rotation.py` lines 8–48 for builder style; the existing
  `test_heartbeat.py` case names / assertions for the `verdict` + `data` assertion shape.
- **GOTCHA**: the current `_noisy_prices` amplitude (8) is close to the new 15% ceiling — do not
  just reuse it and hope. Pick each case's parameters so the metric under test is clearly on the
  intended side of its threshold (aim for ≥ 30% margin), then assert the specific `data` field, so
  a future threshold tweak breaks the test loudly instead of silently flipping a verdict.
- **GOTCHA**: `pd.date_range(..., freq="D")` gives calendar days (weekends included) — that's fine
  and matches the existing helpers; `check_heartbeat_breakout` counts *rows*, not business days.
- **VALIDATE**: `uv run --directory investments/goat python -m pytest -q goat/tests/test_heartbeat.py`

### Task 4: VERIFY `heartbeat_scan.py` needs no change

- **IMPLEMENT**: read `heartbeat_scan.py` lines 42–71 again against the final `heartbeat.py`.
  Confirm: (a) `check_heartbeat_breakout(ticker, sector_label, close)` signature unchanged;
  (b) only `check.verdict` and `check.detail` are read; (c) `config.GOAT_HEARTBEAT_HISTORY_LOOKBACK_DAYS`
  still exists and is still passed to `fetch_close_history`. If all three hold, make **no edit**.
- **GOTCHA**: do not "helpfully" wire any new `data` field into the report — the handoff's "Stays"
  list includes the report renderer unchanged, and `render_heartbeat_candidates_report` only ever
  used `signal_detail` (which is `check.detail`).
- **VALIDATE**: `uv run --directory investments/goat python -m pytest -q goat/tests/test_heartbeat_scan.py`

### Task 5: RUN the full goat suite + lint + types

- **VALIDATE**:
  ```
  uv run --directory investments/goat python -m pytest -q
  uv run --directory investments/goat ruff check goat
  uv run --directory investments/goat mypy goat
  ```
  Expect 203 collected minus the removed `test_heartbeat.py` cases plus the new ones, all passing;
  ruff + mypy clean. If any *other* test file fails, it referenced a removed constant — fix that
  reference (it should not happen; Task 1's grep guards against it).

### Task 6: RUN the redesign diagnostic (DB-free, local-safe)

- **IMPLEMENT**: save this to the scratchpad and run it. It makes real yfinance calls but **never
  opens the DB** (`goat.config` only reads a path constant), so it is safe to run locally — same
  as the original diagnostic in the handoff (run locally 2026-08-26). It replaces the handoff's
  BBW-era diagnostic, which imports now-deleted symbols.
  ```python
  from collections import Counter
  from goat import config
  from goat.heartbeat import check_heartbeat_breakout
  from goat.price_history import fetch_close_history

  SAMPLE = ["KO","PG","WMT","COST","MDLZ","CL","XOM","CVX","COP","EOG","WMB","KMI",
            "JPM","BAC","GS","BLK","SCHW","AXP","JNJ","UNH","LLY","ABBV","MRK","ABT",
            "CAT","DE","HON","UNP","RTX","EMR","LIN","SHW","APD","FCX","NEM","NUE",
            "PLD","AMT","EQIX","WELL","O","VICI"]

  verdicts = Counter()
  for t in SAMPLE:
      close = fetch_close_history(t, config.GOAT_HEARTBEAT_HISTORY_LOOKBACK_DAYS)
      if close is None:
          print(f"{t}: no history"); continue
      res = check_heartbeat_breakout(t, "sample", close)
      d = res.data or {}
      verdicts[res.verdict] += 1
      print(f"{t:<6} days={len(close):>4} verdict={res.verdict:<11} "
            f"range%={d.get('base_range_pct')} smooth={d.get('base_smoothness_fraction')} "
            f"below50={d.get('base_below_ma50_fraction')} dip150%={d.get('max_dip_below_ma150_pct')} "
            f"ma150up={d.get('ma150_slope_up')} crossUp={d.get('crossed_above')} "
            f"sinceCross={d.get('trading_days_since_cross')}")
  print(dict(verdicts))
  ```
  Run: `uv run --directory investments/goat python -c "import runpy; runpy.run_path(r'<scratchpad path>', run_name='__main__')"`
- **ACCEPTANCE**: `base_range_pct` is a real distribution (not `None`/pinned), and `"unknown"` is a
  small minority (most large caps have > 243 trading days). It is fine and expected for this
  large-cap staples/energy/financials sample to still produce **zero `"interesting"`** — those
  names are mostly not in a tight base right now — but the per-gate `data` fields must show the
  legs are being evaluated, not structurally dead. Contrast with the old diagnostic's
  `quietScore = 0.00` for 27/42.
- **VALIDATE**: manual read of the printed table.

### Task 7: UPDATE `investments/goat/HANDOFF.md`

- **IMPLEMENT**: in the `## Status:` header (line 3), after the "Phase 3 complete 2026-08-17"
  clause, add a sentence recording this redesign — matching the style of the existing phase notes
  (date, what changed, test count, what's still gated). Suggested:
  > Heartbeat "quiet" leg redesigned 2026-08-26 — see
  > `.agent/plans/goat-heartbeat-quiet-redesign.md`. The BBW-percentile squeeze (structurally
  > unable to pass on real history — flagged zero candidates every run 2026-08-17 → 08-26) is
  > replaced by a direct base-range % + smoothness test plus a 50/150-day-MA position filter in
  > `heartbeat.py` (`bollinger_width_series` / `_is_in_squeeze` and the four `GOAT_HEARTBEAT_BBW_*`
  > config constants removed). `heartbeat_scan.py` orchestration, staging, report, and the weekly
  > Saturday timer are unchanged. N/N tests passing, ruff + mypy clean. Still needs a real
  > `scan-heartbeat` run on the VPS (Level 4) before its output is trusted; the weekly timer state
  > is unchanged.
- **VALIDATE**: manual read-through.

### Task 8: UPDATE `investments/goat/heartbeat-quiet-redesign-handoff.md`

- **IMPLEMENT**: change the `## Status:` line (line 3) from
  `NOT STARTED — handoff drafted 2026-08-26. Awaiting /plan-feature ...` to
  `PLANNED — see .agent/plans/goat-heartbeat-quiet-redesign.md (created 2026-08-26). Four open
  questions for Shaun resolved there.` Leave the rest of the handoff as the historical record
  (same convention as `industry-rotation-handoff.md` after its plan was written).
- **VALIDATE**: manual read-through.

### Task 9: UPDATE `investments/TOOLS.md`

- **IMPLEMENT**: the "Goat Heartbeat Scan (S&P 500)" row (line 36) currently reads "…for the
  low-volatility-consolidation-then-breakout pattern, with fundamentals survival context…".
  Adjust to mention the 150-day-MA position filter, e.g. "…for a tight sideways base sitting on/above
  a flat-to-rising 150-day MA, then a fresh 50-day-MA breakout, with fundamentals survival
  context…". One-line tweak only; no schedule/command/output-path change (none of those move).
- **VALIDATE**: manual read-through.

---

## TESTING STRATEGY

### Unit Tests

`test_heartbeat.py` — deterministic `pd.Series` inputs, no network, no DB (the module function is
pure compute). Every gate gets a dedicated case where that gate is the *only* thing failing and the
breakout leg still passes, so a regression that weakens one gate fails exactly one test with a
clear name. The `test_wide_base_does_not_fire` case is the load-bearing one: it proves the
consolidation leg actually gates (the original bug was the opposite — the leg could never pass;
a subtler future bug is a leg that never *fails*).

### Integration Tests

`test_heartbeat_scan.py` (unchanged) is the integration layer — it monkeypatches
`check_heartbeat_breakout` wholesale, so it exercises the orchestration/staging/dedup path
independent of this change. Running it green (Task 4) confirms the signature/attribute contract
still holds.

### Edge Cases

- Series exactly `min_len` long — `ma150.iloc[-1 - 20]` must still be a real number (index
  `min_len - 21 = 222 > 149`); covered by making `test_insufficient_history_is_unknown` use
  `min_len - 1` and adding one valid case at a modest length.
- Newly-listed S&P 500 name with < 243 trading days → `"unknown"`, never a false `"interesting"`.
- Downside cross within the fresh window → early `"ok"` return, base window never sliced.
- Stale (old) cross → early `"ok"` return.
- Flat-forever series → `sign_changes.empty` → `"ok"`.
- `base_close.mean()` degenerate (≤ 0) — guarded to `"unknown"`; unreachable with real prices but
  keeps the function total.
- A base that satisfies the range ceiling via one big spike (fails smoothness) — dedicated case.

---

## VALIDATION COMMANDS

Execute every command; zero failures expected.

### Level 1: Syntax & Style

```
uv run --directory investments/goat ruff check goat
uv run --directory investments/goat mypy goat
```

### Level 2: Unit Tests

```
uv run --directory investments/goat python -m pytest -q
```

### Level 3: Integration Tests

Covered by Level 2 (`test_heartbeat_scan.py` runs in the same suite — no separate integration
directory in this workspace).

### Level 4: Manual Validation

**Never run `scan-heartbeat` locally** — it opens the shared `investments.db`, which is VPS-only
since 2026-08-23. Use the wrapper:

```powershell
.\scripts\invoke_investments.ps1 -Package goat -Command "scan-heartbeat"
```

Confirm the run completes, reports how many tickers it scanned across which rising sectors, and —
if it stages anything — that each candidate's `signal_detail` reads sensibly. Then plot 3–5 of any
flagged names with their 50 + 150-day MAs and eyeball whether the flagged base genuinely looks like
a smooth heartbeat sitting on the 150, not just a series that numerically satisfies the formula
(same spirit as the Phase 3 plan's Level 4 and HANDOFF's own reference-chart validation).

The DB-free diagnostic (Task 6) is the local-safe "did the score stop collapsing" check and can be
run any time.

### Level 5: Additional Validation

N/A.

---

## ACCEPTANCE CRITERIA

- [ ] `bollinger_width_series`, `_is_in_squeeze`, and the four `GOAT_HEARTBEAT_BBW_*` config
      constants are gone; `grep -rn "GOAT_HEARTBEAT_BBW\|_is_in_squeeze\|bollinger_width_series"
      investments/goat/goat` returns nothing.
- [ ] `check_heartbeat_breakout` signature is unchanged (`(ticker, sector_label, close) ->
      CheckResult`) and `heartbeat_scan.py` is not edited.
- [ ] The consolidation leg is a direct base-range % + inner-band smoothness test — no rolling
      self-percentile anywhere in `heartbeat.py`.
- [ ] The position-of-strength leg checks: price held ≤ `GOAT_HEARTBEAT_MA_LONG_TOLERANCE_PCT`
      below the 150-day MA during the base; price at/above the 150-day MA on the breakout bar;
      150-day MA flat-to-rising over `GOAT_HEARTBEAT_MA_LONG_SLOPE_LOOKBACK_DAYS`; price at/below
      the 50-day MA on ≥ `GOAT_HEARTBEAT_BASE_BELOW_MA50_MIN_FRACTION` of base days.
- [ ] The breakout leg (fresh cross-up + 50-day MA sloping up) is byte-identical to the ported
      block it replaces.
- [ ] `min_len` = 150 + 63 + 20 + 10 = 243; a shorter series returns `verdict="unknown"`.
- [ ] `test_heartbeat.py` has a case proving the base leg gates: breakout leg passes, wide base,
      verdict stays `"ok"` (handoff Q7).
- [ ] Full `uv run --directory investments/goat python -m pytest -q` passes; ruff + mypy clean.
- [ ] Task 6 diagnostic shows `base_range_pct` as a real distribution across the sample, not
      `None`/pinned; `"unknown"` is a small minority.
- [ ] `HANDOFF.md`, the redesign handoff `## Status` line, and `investments/TOOLS.md` updated.
- [ ] No change to `fundamentals_context.py`, `heartbeat_scan.py`, `sp500_universe.py`,
      `main.py`, `conftest.py`, the systemd units, or `deploy.ps1`.

---

## COMPLETION CHECKLIST

- [ ] Tasks 1–9 completed in order.
- [ ] Each task's `VALIDATE` command run and passed immediately after that task.
- [ ] Full `investments/goat` test suite green; ruff + mypy clean.
- [ ] Task 6 diagnostic run and its table eyeballed.
- [ ] Level 4 (`scan-heartbeat` via `invoke_investments.ps1` on the VPS) run and any flagged
      candidates chart-checked — OR explicitly handed to Shaun as the remaining step if the VPS
      run isn't done in this session.
- [ ] Docs updated (HANDOFF, redesign handoff status, TOOLS.md).
- [ ] `git grep` confirms no dangling references to removed symbols.

---

## NOTES

- **Why this overturns the Phase 3 "BINDING" decision**: the Phase 3 plan explicitly allowed
  revisiting the BBW-percentile metric given "a manual validation run showing BBW-squeeze is
  producing obviously wrong candidates against real charts." The 2026-08-26 diagnostic (zero
  candidates across the whole S&P 500 for 10 straight days, quiet score pinned near 0.00 for 42/42
  hand-picked names) is a stronger form of that — the metric isn't producing *wrong* candidates, it
  is producing *none*, ever, by construction. Shaun confirmed the redesign is in scope 2026-08-26.
- **Why remove BBW rather than repurpose it**: the handoff floated keeping
  `GOAT_HEARTBEAT_BBW_PERIOD_DAYS` / `_STD_MULTIPLIER` "if BBW stays as the range measure against a
  fixed cut." The research pass killed the fixed-cut option (Bollinger's own ChartSchool: no
  universal BandWidth threshold; utilities <5, tech >7). With no fixed-cut and no percentile, BBW
  has no role — and dead config is worse than lean config in a file this carefully annotated. The
  direct close-range % is a simpler, chart-truer measure with sourced numbers behind it.
- **The 0.6 "reclaim" fraction and the 3% / 20-day / 8% numbers are design choices, not sourced.**
  They are flagged v1/tunable in their config comments. If Level 4 shows the scan is too strict
  (still near-zero candidates) or too loose (obvious junk), these four plus
  `GOAT_HEARTBEAT_BASE_RANGE_MAX_PCT` are the tuning surface — change the constant, not the logic.
- **`slope_up` vs `slope_up_50` / `ma150_slope_up`**: the `data` dict keeps the key `"slope_up"`
  for the 50-day MA (existing tests and the package's `data` convention read it) and adds
  `"ma150_slope_up"` for the new 150-day check. Don't rename `"slope_up"`.
- **The base window is the 63 closes ending the day *before* the cross** — same as the old
  `pre_cross_window` (`in_squeeze.iloc[:cross_pos].tail(63)`). The cross bar itself and everything
  after it is the breakout, not the base.
- **Deferred, not built** (would each need their own handoff): a streak counter ("N weeks in the
  base"); volume confirmation on the breakout; an ATR-based flatness alternative to the close-range
  %; re-tuning any Phase 1/2 constant; a VCP-style multi-contraction structure test.

## Confidence

**7/10** for one-pass success. The core-function rewrite (Tasks 1, 2, 4) and the doc updates
(7–9) are low-risk and fully specified. The risk sits in Task 3: the synthetic price-series
builders have to satisfy six interacting gates simultaneously for the valid case, and the numeric
parameters (`_lead` start/end, `_base` amp, `tail_len`) will almost certainly need iteration to
land every `data` metric cleanly mid-gate. That is normal test-fixture tuning, not a design risk —
the plan gives a working starting shape and the rule "perturb one parameter per negative case" —
but budget for a few pytest cycles there. Everything else should go first-pass.
