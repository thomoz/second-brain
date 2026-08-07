# Feature: Gold Signal & Technical Outlook

The following plan should be complete, but validate documentation and codebase
patterns and task sanity before implementing. Pay special attention to naming of
existing config constants, check functions, and imports — mirror existing patterns
exactly, don't invent a new shape where one already fits.

Source: `.agent/plans/gold-tracker-phase2-backtest-handoff.md` (original backtest-only
design, Decisions 1–8, still valid and incorporated below), extended through a live
2026-08-07 conversation with Shaun in four corrections, in order:

1. Not a standalone historical-validation report — a daily read, using whatever
   technical metrics an expert trader would use (not just the 200DMA), of what gold's
   price is likely to do today, tomorrow, this week, and this month.
2. A real directional guess at every horizon, including today/tomorrow — withholding
   one was overcautious. Advisor-mode means never *acting* autonomously; it does not
   mean withholding an interpreted opinion Shaun reviews and decides on himself:
   "This isn't you deciding what I should do. This is you giving a guided guess."
3. **Every horizon's guess must actually be grounded in backtested historical data —
   today/tomorrow and this week included, not just this month.** The first version of
   this plan only built historical validation for the 5 slow-moving macro signals at
   month-scale, leaving Today/Tomorrow and This Week's directional guess resting on
   live technical-indicator readings plus documented rationale, but no real backtest
   behind them. Shaun: "I need it to be for this week, and today/tomorrow too... as
   well as this month." This revision fixes that gap by giving the technical
   indicators (moving averages, MACD, RSI, Stochastic) their own historical backtest,
   validated at the day/week timescale they actually operate at, using the same
   rigor already applied to the macro signals.
4. **Each day's new data must be folded into the historical dataset daily, not left
   stale for up to a week.** The backtest's cached-refresh wrapper originally allowed
   up to 7 days between full recomputes. Shaun: "each day's new data needs to be
   added to the historical data." Since the full-history fetch is already cheap (a
   handful of bulk API calls, not per-day loops — confirmed low single-digit seconds
   in practice), there was no real reason for a week-long cache; the refresh window
   is now capped at roughly a day (Task 1.2), so the historical dataset — and every
   state-conditioned/episode backtest built from it — is never more than about a day
   behind live data.

That conversation is the authority on scope for this plan.

## Feature Description

A daily "Gold Outlook" — folded into Monitor's existing scheduled run, written to a
new `investments/my-trader/gold-outlook.md` file — that combines:

1. **Live technical indicators** (new: trend, momentum, volatility, key levels,
   volume, seasonality) computed from GC=F's real OHLCV data.
2. **Live macro signals** — Phase 1's existing 5 gold-relevant checks (`real_yields`,
   `dollar_index`, `gold_trend`, `gold_silver_ratio`, `vix`), reused with one
   additive change (a `direction` field, Task 1.3).
3. **Two historical backtests, both feeding all three horizon sections, both
   refreshed daily so each new trading day's data is incorporated**:
   - **Episode-based** (the 5 macro signals): rare regime-shift events — every
     historical occurrence of each signal, gold's forward return from each, at
     1-day, 5-day, and 1/3/6/12/24-month horizons.
   - **State-conditioned** (new — the technical indicators): common daily
     readings — for every trading day in history, which "state" each indicator was
     in (e.g. price above/below its 20-day average), and gold's forward return
     conditioned on that state, at 1-day, 5-day, and 1-month horizons (technical
     indicators don't get the longer 3/6/12/24-month legs — see NOTES for why).

Every currently-active signal or indicator state, at every horizon, gets looked up
against its own real historical track record — never a fixed "documented rationale"
substitute. Today/Tomorrow, This Week, and This Month all use the **same** lookup
method (`gold_outlook._horizon_read()`), just pointed at a different horizon — the
only thing that changes between sections is which horizon's numbers come back, not
the underlying honesty of the read.

## User Story

As Shaun (holding PMGOLD, not trained to read trading signals himself)
I want a daily outlook that combines live technical indicators, live macro signals,
and their actual historical track record — at every horizon, refreshed with each
day's new data — into a plain-language, horizon-appropriate directional guess
So that I get the best available, honestly-caveated sense of what gold's price action
might do today, this week, and this month, grounded in real, current data rather than
a mix of validated numbers and inserted rationale, without the tool ever issuing a
specific trade directive.

## Problem Statement

Phase 1 gives 5 raw macro facts and one always-neutral 200DMA-cross fact, with no
interpretation and no historical validation at all. Technical indicators (moving
averages, RSI, MACD, Stochastic) have never been computed in this codebase, let alone
validated. Shaun wants an actual interpreted, historically-grounded, up-to-date read
at every horizon he cares about — today, tomorrow, this week, and this month — not a
partial answer where only the slowest-moving signals get real evidence behind them,
and not a read that's quietly a week stale.

## Solution Statement

Three new/extended modules working together, wired into Monitor's existing daily run:

- `mytrader/gold_technicals.py` (new) — fetches GC=F's full OHLCV history once,
  exposes both **today's snapshot** (used for the live outlook) and **full historical
  series** (used by `gold_backtest.py`'s state-conditioned backtest) for every
  indicator, from the same underlying formula — no duplicated math between "today's
  value" and "the historical series," a single source of truth per indicator.
- `mytrader/gold_backtest.py` (new) — two backtest methodologies sharing one set of
  fetch/stats helpers: **episode-based** for the 5 macro signals (rare events,
  forward return from each occurrence, day/week/month horizons) and
  **state-conditioned** for the 6 technical-indicator readings (common daily states,
  forward return conditioned on every day that state held, day/week/month-1
  horizons). A cached-with-refresh wrapper means Monitor refreshes both backtests
  roughly once per day — enough to fold each day's new price/FRED data into the
  historical dataset — without redundantly recomputing more than once if Monitor or
  another command happens to run again the same day.
- `mytrader/gold_outlook.py` (new) — one unified lookup (`_horizon_read()`) used by
  all three horizon builders: for every currently-active signal/state, look up its
  real backtest stats at that horizon, score it only if real historical data exists,
  and show N alongside every number. Writes `gold-outlook.md`.
- `monitor.py` — one new integration point; `monitor-report.md` gets a one-line
  pointer to the new file.

## Feature Metadata

**Feature Type**: New Capability (three new modules, one new integration point, one
new DB table, two backtest methodologies)
**Estimated Complexity**: Very High — a from-scratch technical-indicator suite shared
between a live snapshot and a full-history backtest, two distinct backtest
methodologies (episode-based and state-conditioned) unified under one DB schema and
one outlook-lookup function, refreshed daily, all wired into the daily-run path.
**Primary Systems Affected**: `investments/my-trader/mytrader/gold_technicals.py`
(new), `investments/my-trader/mytrader/gold_backtest.py` (new),
`investments/my-trader/mytrader/gold_outlook.py` (new),
`investments/my-trader/mytrader/monitor.py`, `investments/my-trader/mytrader/config.py`,
`investments/my-trader/mytrader/db.py`, `investments/my-trader/mytrader/main.py`,
`investments/my-trader/mytrader/macro_indicators.py` (one additive field),
`investments/briefs-finance/scripts/macro.py`, `.claude/skills/my-trader/SKILL.md`
**Dependencies**: None new — `pandas`/`yfinance`/`numpy` (already transitively
available via `pandas`), `requests` (already `briefs-finance`). No technical-analysis
library — every indicator is hand-computed in plain pandas.

**Non-goals**: no autonomous trading, no specific buy/sell directive anywhere in this
feature (a directional *guess*, backed by real historical stats, is in scope — a
trade instruction is not); no changes to Phase 1's live check thresholds/verdict
logic (the one authorized change, Task 1.3, is additive only).

---

## CONTEXT REFERENCES

### Relevant Codebase Files — READ THESE BEFORE IMPLEMENTING

- `investments/my-trader/mytrader/macro_indicators.py` — the 5 signals reused for the
  macro layer, and `check_gold_trend()` (lines 464–527) as the precedent for
  hand-rolling moving-average/cross-detection math in plain pandas. **One authorized
  additive change** (Task 1.3): `check_real_yields()` (393–430), `check_dollar_index()`
  (433–461), `check_gold_trend()` (464–527), `check_gold_silver_ratio()` (530–562),
  `check_vix()` (565–583) each get a `"direction"` key added to `data` — no
  threshold/verdict/detail changes.
- `investments/my-trader/mytrader/config.py` — citation-comment convention; the
  existing Phase 1 gold block (lines 350–393) is reused directly, not redefined.
- `investments/my-trader/mytrader/monitor.py` (219 lines) — integration point:
  `run_monitor()` (91–140, macro-checks block 119–127 — new outlook call goes
  immediately after), `render_report()` (143–197, "New Candidates Synced" section
  185–194 is the exact precedent for a one-line pointer to a separately-regenerated
  file), `maybe_notify()` (204–219, **do not** wire the outlook into this — no toast).
- `investments/briefs-finance/scripts/prices.py` — `compute_return_pct()` (54–58),
  reused, not reimplemented.
- `investments/briefs-finance/scripts/macro.py` — `fred_observation_on()` (23–65) is
  the pattern `fred_series_range()` (Task 1.1) extends.
- `investments/my-trader/mytrader/crash_windows.py` — `_fetch_close_series()` (41–61)
  for the long-range fetch + tz-naive normalization pattern every fetch helper here
  must follow.
- `investments/my-trader/mytrader/db.py` — `init_mytrader_tables()` (27–115) and
  `upsert_macro_snapshot()`/`get_macro_snapshot()` (328–347) as the closest existing
  precedent for the new `gold_backtest_results` table.
- `investments/my-trader/mytrader/main.py` — argparse pattern (241–330);
  `cmd_sync_candidates()`/`"sync-candidates"` (174–186, 287–290) is the closest
  precedent for the new `gold-backtest` on-demand subcommand.
- `investments/my-trader/mytrader/tests/test_crash_windows.py` — the
  `_install_fake_yfinance()` pattern and synthetic-Series-with-known-answer test
  style every new test here should follow.
- `investments/my-trader/mytrader/tests/test_macro_indicators.py` —
  `monkeypatch.setattr("mytrader.<module>.<fn>", ...)` convention.
- `investments/briefs-finance/scripts/tests/test_macro.py` —
  `unittest.mock.patch("scripts.macro.requests.get", ...)` convention (distinct from
  `mytrader`'s `monkeypatch` convention).
- `.claude/skills/my-trader/SKILL.md` — "Macro Monitoring Indicators" section's
  closing sentence is stale, corrected in Task 6.1.

### New Files to Create

- `investments/my-trader/mytrader/gold_technicals.py`
- `investments/my-trader/mytrader/gold_backtest.py`
- `investments/my-trader/mytrader/gold_outlook.py`
- `investments/my-trader/mytrader/tests/test_gold_technicals.py`
- `investments/my-trader/mytrader/tests/test_gold_backtest.py`
- `investments/my-trader/mytrader/tests/test_gold_outlook.py`

### Files to Update

- `investments/briefs-finance/scripts/macro.py` — add `fred_series_range()`.
- `investments/briefs-finance/scripts/tests/test_macro.py` — tests for it.
- `investments/my-trader/mytrader/macro_indicators.py` — additive `direction` field.
- `investments/my-trader/mytrader/tests/test_macro_indicators.py` — tests for it.
- `investments/my-trader/mytrader/config.py` — new `GOLD_TA_*`/`GOLD_BACKTEST_*`
  constants (needs `from datetime import date` added — the file currently has no
  `datetime` import at all).
- `investments/my-trader/mytrader/db.py` — new `gold_backtest_results` table + CRUD.
- `investments/my-trader/mytrader/tests/test_db.py` — tests for it.
- `investments/my-trader/mytrader/main.py` — new `gold-backtest` on-demand subcommand.
- `investments/my-trader/mytrader/monitor.py` — one new call, one new pointer line.
- `investments/my-trader/mytrader/tests/test_monitor.py` — stub the new call.
- `.claude/skills/my-trader/SKILL.md` — new "Gold Outlook" section.

### Relevant Documentation

- [FRED — fred/series/observations endpoint](https://fred.stlouisfed.org/docs/api/fred/series_observations.html)
  — same endpoint `fred_observation_on()` calls; `fred_series_range()` uses a date
  range instead of a single-point lookback.
- No external technical-analysis documentation — RSI/MACD/Stochastic/ATR/Bollinger
  formulas are specified exactly in Task 2.2, so implementation is unambiguous.

### Patterns to Follow

**One formula, two consumers**: every indicator in `gold_technicals.py` is built as
a `*_series()` function returning the full historical `pandas.Series` (or dict of
Series), with a thin `compute_*()` wrapper extracting just the latest value for the
live snapshot. `gold_backtest.py` imports the same `*_series()` functions directly —
there is exactly one RSI formula, one MACD formula, etc. in this codebase, never two
independently-maintained copies that could silently drift.

**Two backtest methodologies, each fitted to its signal type**:
- **Episode-based** (macro signals): rare, discrete regime-shift events. Find every
  historical occurrence, compute forward return from each occurrence date.
- **State-conditioned** (technical indicators): common, persistent daily readings.
  Classify every trading day's state, compute forward return conditioned on every
  day that state held (not just the day it started) — a much larger, statistically
  richer sample for something that isn't a rare event.

Both feed the exact same downstream shape — `{n, mean, median, win_rate, best, worst,
baseline}` keyed by `(name, value, horizon_unit, horizon_value)` — so
`gold_outlook.py` never needs to know which methodology produced a given row.

**Refresh daily, not weekly**: `gold_backtest.get_cached_or_refresh()` recomputes
roughly once every 24 hours (Task 1.2's `GOLD_BACKTEST_REFRESH_MAX_AGE_DAYS = 1`), so
each new trading day's price/FRED data is folded into both backtests before the next
Monitor run needs them — never left stale for up to a week.

**Transparent synthesis, never a bare invented percentage**: every horizon's "lean"
shows its component signals/indicators, each with its own historical N and mean vs
baseline, never collapsed into an unexplained single number.

**Graceful degradation over exceptions**: every fetch/compute helper returns `None`
on missing data; orchestration functions wrap sub-steps so one failing signal doesn't
take down the whole report.

**Reuse Phase 1's exact live thresholds — never duplicate them**: the macro-signal
episode finders compare against the same `config.py` constants `macro_indicators.py`
already uses.

---

## IMPLEMENTATION PLAN

### Phase 1: Foundation
Bulk FRED fetch function, all new config constants, the one authorized additive
change to Phase 1 (`direction` field).

### Phase 2: Technical Indicators (`gold_technicals.py`)
Shared series/snapshot functions for trend, momentum, volatility, levels, volume,
seasonality — used both for today's live read and for the historical backtest.

### Phase 3: Historical Backtest (`gold_backtest.py`)
Episode-based backtest for the 5 macro signals (day/week/month horizons) +
state-conditioned backtest for the 6 technical indicators (day/week/month-1
horizons), unified under one results shape and one DB table, refreshed daily.

### Phase 4: Synthesis (`gold_outlook.py`) + Monitor Integration
One shared horizon-lookup function powering all three sections; wire into
`monitor.py`; `gold-outlook.md` output.

### Phase 5: Testing
Deterministic synthetic-data tests for every indicator/episode-finder/state-finder/
synthesis component.

### Phase 6: Documentation + Manual Validation
`SKILL.md` section with a real worked example; live run against real data.

---

## STEP-BY-STEP TASKS

### Task 1.1 — UPDATE `investments/briefs-finance/scripts/macro.py`

- **IMPLEMENT**: Add `fred_series_range()`:
  ```python
  def fred_series_range(
      series_id: str, start: date, end: date
  ) -> list[tuple[date, float]] | None:
      """Full published-observation history for series_id between start/end
      (inclusive), ascending by date. Distinct from fred_observation_on's
      single-latest-point-on-or-before lookup -- gold_backtest.py needs the whole
      daily history, not just the most recent value. Returns plain (date, value)
      tuples, not a pandas Series -- briefs-finance declares no pandas dependency;
      the caller (mytrader, which does) converts.
      """
      if not FRED_API_KEY:
          return None
      try:
          params = {
              "series_id": series_id,
              "observation_start": start.isoformat(),
              "observation_end": end.isoformat(),
              "sort_order": "asc",
              "limit": 100000,
              "api_key": FRED_API_KEY,
              "file_type": "json",
          }
          r = requests.get(
              "https://api.stlouisfed.org/fred/series/observations",
              params=params, timeout=30,
          )
          obs = r.json().get("observations", [])
          result = [(date.fromisoformat(o["date"]), float(o["value"]))
                    for o in obs if o["value"] != "."]
          return result if result else None
      except Exception:
          return None
  ```
- **PATTERN**: `fred_observation_on()` (23–65).
- **GOTCHA**: `timeout=30`, not `fred_observation_on`'s `timeout=10`.
- **VALIDATE**: `uv run --directory investments/briefs-finance python -c "from scripts.macro import fred_series_range; from datetime import date; r = fred_series_range('DGS10', date(2024,1,1), date(2024,1,31)); print(len(r) if r else r)"`

### Task 1.2 — UPDATE `investments/my-trader/mytrader/config.py`

- **IMPLEMENT**: Add `from datetime import date` to the imports (currently absent).
  Then add a new dated block after the existing Phase 1 gold block:
  ```python
  # Added 2026-08-07 -- Gold Outlook (technicals + historical backtest), see
  # .agent/plans/gold-tracker-phase2-outlook.md. GOLD_TA_* are standard,
  # widely-cited technical-analysis conventions (RSI 14/70/30, MACD 12/26/9, etc.
  # -- textbook defaults). GOLD_BACKTEST_* are this plan's own methodology
  # choices -- best-guess defaults, ship and revisit.

  GOLD_TA_MA_FAST_DAYS = 20  # short-term trend leg; GOLD_MA_SHORT_DAYS (50) /
                               # GOLD_MA_LONG_DAYS (200) above are reused as-is.
  GOLD_TA_RSI_PERIOD_DAYS = 14  # textbook default (Wilder's original).
  GOLD_TA_RSI_OVERBOUGHT = 70.0
  GOLD_TA_RSI_OVERSOLD = 30.0
  GOLD_TA_RSI_BULLISH_ABOVE = 55.0  # "elevated" state boundary for the
                                       # state-conditioned backtest -- a healthy-
                                       # momentum zone short of overbought, not the
                                       # same threshold as GOLD_TA_RSI_OVERBOUGHT
                                       # (70), which flags exhaustion instead.
  GOLD_TA_RSI_BEARISH_BELOW = 45.0  # "depressed" state boundary, same idea
                                       # mirrored below the midline. The 45-55 band
                                       # itself is the excluded "neutral" state --
                                       # not backtested, same treatment as
                                       # gold_silver_ratio's un-flagged middle range.
  GOLD_TA_MACD_FAST_DAYS = 12  # textbook default.
  GOLD_TA_MACD_SLOW_DAYS = 26
  GOLD_TA_MACD_SIGNAL_DAYS = 9
  GOLD_TA_STOCH_PERIOD_DAYS = 14  # textbook default.
  GOLD_TA_STOCH_SMOOTHING_DAYS = 3
  GOLD_TA_STOCH_OVERBOUGHT = 80.0
  GOLD_TA_STOCH_OVERSOLD = 20.0
  GOLD_TA_ATR_PERIOD_DAYS = 14  # textbook default (Wilder's original).
  GOLD_TA_BOLLINGER_PERIOD_DAYS = 20  # textbook default.
  GOLD_TA_BOLLINGER_STD_MULTIPLIER = 2.0
  GOLD_TA_LEVEL_LOOKBACK_DAYS = 20  # trading days (~1 month) for the recent
                                       # swing high/low support/resistance proxy.
  GOLD_TA_VOLUME_AVG_DAYS = 20

  GOLD_BACKTEST_HISTORY_START = date(2000, 1, 1)  # comfortably before every
                                       # signal's earliest data (GC=F/SI=F
                                       # 2000-08-30, VIX 1990-01-02, DFII10
                                       # 2003-01-02, DTWEXBGS 2006-01-02).
  GOLD_BACKTEST_TRAIN_VALIDATION_SPLIT_DATE = date(2018, 1, 1)  # fixed calendar
                                       # date -- only occurrences/states on/after
                                       # this date are ever reported.
  GOLD_BACKTEST_FORWARD_HORIZONS_TRADING_DAYS = (1, 5)  # 1 trading day ~=
                                       # today/tomorrow, 5 trading days ~= this
                                       # week. Used by BOTH backtest methodologies
                                       # -- the 5 macro-signal episodes are cheap
                                       # to re-check at these short horizons too
                                       # (N is bounded by episode count either way,
                                       # not by horizon), and the 6 technical
                                       # indicator states are the whole reason
                                       # these horizons exist.
  GOLD_BACKTEST_FORWARD_HORIZONS_MONTHS = (1, 3, 6, 12, 24)  # macro-signal
                                       # episodes only (see NOTES for why
                                       # technical-indicator states stop at 1
                                       # month) -- 3/6/12/24 matches briefs-
                                       # finance's own stock backtest + a 24m leg
                                       # for gold's longer cycles; 1m is this
                                       # plan's own addition for "this month".
  GOLD_BACKTEST_MIN_EPISODE_GAP_DAYS = 60  # calendar days -- collapses
                                       # threshold-hugging noise into one episode
                                       # per genuine event for the 4 magnitude-
                                       # threshold macro signals. Does NOT apply
                                       # to gold_trend's cross episodes (already
                                       # discrete) or to any state-conditioned
                                       # technical indicator (state-conditioning
                                       # uses every day a state holds, not
                                       # discrete episodes -- there's nothing to
                                       # de-duplicate).
  GOLD_BACKTEST_REFRESH_MAX_AGE_DAYS = 1  # Monitor calls
                                       # gold_backtest.get_cached_or_refresh() on
                                       # every run -- capped at ~1 day (not the
                                       # originally-planned week) so each day's
                                       # new price/FRED data is actually folded
                                       # into the historical dataset daily, per
                                       # Shaun's explicit correction 2026-08-07
                                       # ("each day's new data needs to be added
                                       # to the historical data") -- confirmed
                                       # cheap enough to run daily (a handful of
                                       # bulk fetches, not per-day loops), so
                                       # there's no real cost to refreshing this
                                       # often. The on-demand `gold-backtest` CLI
                                       # subcommand always force-refreshes
                                       # regardless of this cache.
  ```
- **PATTERN**: The Phase 1 gold block immediately above.
- **VALIDATE**: `uv run --directory investments/my-trader python -c "from mytrader import config; print(config.GOLD_TA_RSI_BULLISH_ABOVE, config.GOLD_BACKTEST_FORWARD_HORIZONS_TRADING_DAYS)"`

### Task 1.3 — UPDATE `investments/my-trader/mytrader/macro_indicators.py`

- **IMPLEMENT**: Add a `"direction"` key to each of the 5 gold checks' `data` dict —
  purely additive, computed from the exact condition each function already branches
  on:
  ```python
  # check_real_yields():
  data = {"value": value, "as_of": obs_date.isoformat(), "direction": None}
  if value < config.REAL_YIELD_FLAG_NEGATIVE_PCT:
      data["direction"] = "negative"
      return CheckResult(name="real_yields", verdict="flag", detail=..., data=data)
  if value > config.REAL_YIELD_FLAG_HIGH_PCT:
      data["direction"] = "elevated"
      return CheckResult(name="real_yields", verdict="flag", detail=..., data=data)
  return CheckResult(name="real_yields", verdict="ok", detail=..., data=data)

  # check_dollar_index():
  data = {"value": now_value, "pct_change": pct_change,
          "lookback_days": config.DXY_LOOKBACK_DAYS, "direction": None}
  if pct_change >= config.DXY_FLAG_MOVE_PCT:
      data["direction"] = "rising"
  elif pct_change <= -config.DXY_FLAG_MOVE_PCT:
      data["direction"] = "falling"

  # check_gold_trend() -- normalize the existing cross_direction local to
  # gold_backtest.py's underscore convention:
  direction = None
  if cross_direction == "crossed above":
      direction = "crossed_above"
  elif cross_direction == "crossed below":
      direction = "crossed_below"
  # add "direction": direction to the returned data={...} dict, alongside the
  # existing "cross_direction" key (kept as-is for the detail text).

  # check_gold_silver_ratio():
  data = {"gold": gold, "silver": silver, "ratio": ratio, "direction": None}
  if ratio >= config.GOLD_SILVER_RATIO_FLAG_HIGH:
      data["direction"] = "high"
  elif ratio <= config.GOLD_SILVER_RATIO_FLAG_LOW:
      data["direction"] = "low"

  # check_vix():
  data = {"value": value, "direction": "elevated" if value >= config.VIX_FLAG_LEVEL else None}
  ```
- **PATTERN**: Match each function's existing branch structure — one field per
  return path, nothing else. Cross-check final `direction` values against
  `gold_backtest.py`'s `Episode.direction` labels (Task 3.1) — must match
  character-for-character (`"negative"`, `"elevated"`, `"rising"`, `"falling"`,
  `"crossed_above"`, `"crossed_below"`, `"high"`, `"low"`).
- **GOTCHA**: `check_gold_trend()`'s existing `cross_direction` local uses spaced
  words — normalize to the underscored form, or the join in `gold_outlook.py` will
  silently find no match and that signal will just quietly vanish from every
  section rather than erroring.
- **VALIDATE**: `uv run --directory investments/my-trader python -m pytest mytrader/tests/test_macro_indicators.py -v`
  (after adding a `data["direction"]` assertion to each existing flag/ok test for
  these 5 checks)

### Task 2.1 — CREATE `gold_technicals.py`: OHLCV fetch + series/snapshot indicators

- **IMPLEMENT**:
  ```python
  """Technical-analysis indicators for GC=F -- trend, momentum, volatility, key
  levels, volume, and seasonality, computed from real OHLCV data. Every indicator
  is built as a *_series() function (the full historical Series, consumed by
  gold_backtest.py's state-conditioned backtest) with a thin compute_*() wrapper
  around it (today's value only, consumed by the live outlook) -- one formula, two
  consumers, so there is never a second, independently-drifting implementation of
  the same indicator. Does NOT modify macro_indicators.check_gold_trend(), which
  stays exactly as Phase 1 shipped it -- some overlap (both independently touch
  50/200DMA) is accepted, same cross-module-coupling tradeoff macro_indicators.py's
  own docstring already makes for its duplicated FRED series-ID strings.
  """
  from __future__ import annotations

  from datetime import date

  import pandas as pd

  from . import config


  def _fetch_ohlcv(ticker: str, start: date) -> pd.DataFrame | None:
      import yfinance as yf
      try:
          hist = yf.Ticker(ticker).history(start=start.isoformat(), auto_adjust=True)
          if hist.empty:
              return None
          if getattr(hist.index, "tz", None) is not None:
              hist.index = hist.index.tz_localize(None)
          return hist[["Open", "High", "Low", "Close", "Volume"]]
      except Exception:
          return None


  def moving_average_series(close: pd.Series, days: int) -> pd.Series:
      return close.rolling(days).mean()


  def rsi_series(close: pd.Series, period: int = config.GOLD_TA_RSI_PERIOD_DAYS) -> pd.Series:
      delta = close.diff()
      gain = delta.clip(lower=0)
      loss = -delta.clip(upper=0)
      # Wilder's smoothing (textbook RSI), not a plain SMA.
      avg_gain = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
      avg_loss = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
      rs = avg_gain / avg_loss
      return 100 - (100 / (1 + rs))


  def macd_series(close: pd.Series) -> dict[str, pd.Series]:
      ema_fast = close.ewm(span=config.GOLD_TA_MACD_FAST_DAYS, adjust=False).mean()
      ema_slow = close.ewm(span=config.GOLD_TA_MACD_SLOW_DAYS, adjust=False).mean()
      macd_line = ema_fast - ema_slow
      signal_line = macd_line.ewm(span=config.GOLD_TA_MACD_SIGNAL_DAYS, adjust=False).mean()
      return {"macd": macd_line, "signal": signal_line, "histogram": macd_line - signal_line}


  def stochastic_series(df: pd.DataFrame) -> dict[str, pd.Series]:
      period = config.GOLD_TA_STOCH_PERIOD_DAYS
      low_min = df["Low"].rolling(period).min()
      high_max = df["High"].rolling(period).max()
      k = (df["Close"] - low_min) / (high_max - low_min) * 100
      d = k.rolling(config.GOLD_TA_STOCH_SMOOTHING_DAYS).mean()
      return {"k": k, "d": d}


  def atr_series(df: pd.DataFrame, period: int = config.GOLD_TA_ATR_PERIOD_DAYS) -> pd.Series:
      prev_close = df["Close"].shift(1)
      tr = pd.concat([
          df["High"] - df["Low"],
          (df["High"] - prev_close).abs(),
          (df["Low"] - prev_close).abs(),
      ], axis=1).max(axis=1)
      return tr.ewm(alpha=1 / period, adjust=False).mean()
  ```
- **PATTERN**: `crash_windows._fetch_close_series()` (41–61) for the tz-naive
  fetch pattern, extended to keep the full OHLCV frame.
- **GOTCHA**: `rsi_series`'s `min_periods=period` on the `.ewm()` calls prevents a
  spuriously-computed RSI before enough history exists.
- **VALIDATE**: `uv run --directory investments/my-trader python -c "from mytrader.gold_technicals import _fetch_ohlcv, rsi_series; from mytrader.config import GOLD_BACKTEST_HISTORY_START; df = _fetch_ohlcv('GC=F', GOLD_BACKTEST_HISTORY_START); print(rsi_series(df['Close']).tail())"`

### Task 2.2 — ADD snapshot wrappers + remaining indicators to `gold_technicals.py`

- **IMPLEMENT**:
  ```python
  def compute_trend(df: pd.DataFrame) -> dict:
      close = df["Close"]
      ma20 = moving_average_series(close, config.GOLD_TA_MA_FAST_DAYS)
      ma50 = moving_average_series(close, config.GOLD_MA_SHORT_DAYS)
      ma200 = moving_average_series(close, config.GOLD_MA_LONG_DAYS)
      price = float(close.iloc[-1])
      return {
          "price": price,
          "prev_close": float(close.iloc[-2]),
          "ma20": float(ma20.iloc[-1]), "ma50": float(ma50.iloc[-1]), "ma200": float(ma200.iloc[-1]),
          "price_above_ma20": price > ma20.iloc[-1],
          "price_above_ma50": price > ma50.iloc[-1],
          "price_above_ma200": price > ma200.iloc[-1],
          "ma20_rising": ma20.iloc[-1] > ma20.iloc[-6],
          "ma50_rising": ma50.iloc[-1] > ma50.iloc[-6],
      }


  def compute_macd(close: pd.Series) -> dict:
      s = macd_series(close)
      return {
          "macd": float(s["macd"].iloc[-1]), "signal": float(s["signal"].iloc[-1]),
          "histogram": float(s["histogram"].iloc[-1]),
          "histogram_rising": s["histogram"].iloc[-1] > s["histogram"].iloc[-2],
      }


  def compute_rsi(close: pd.Series) -> float:
      return float(rsi_series(close).iloc[-1])


  def compute_stochastic(df: pd.DataFrame) -> dict:
      s = stochastic_series(df)
      return {"k": float(s["k"].iloc[-1]), "d": float(s["d"].iloc[-1])}


  def compute_atr(df: pd.DataFrame) -> float:
      return float(atr_series(df).iloc[-1])


  def compute_bollinger(close: pd.Series) -> dict:
      period = config.GOLD_TA_BOLLINGER_PERIOD_DAYS
      mid = close.rolling(period).mean()
      std = close.rolling(period).std()
      upper = mid + config.GOLD_TA_BOLLINGER_STD_MULTIPLIER * std
      lower = mid - config.GOLD_TA_BOLLINGER_STD_MULTIPLIER * std
      width_pct = (upper.iloc[-1] - lower.iloc[-1]) / mid.iloc[-1] * 100
      return {"mid": float(mid.iloc[-1]), "upper": float(upper.iloc[-1]),
              "lower": float(lower.iloc[-1]), "width_pct": round(float(width_pct), 2)}


  def compute_levels(df: pd.DataFrame) -> dict:
      window = df.tail(config.GOLD_TA_LEVEL_LOOKBACK_DAYS)
      return {"resistance": float(window["High"].max()), "support": float(window["Low"].min())}


  def compute_volume_context(df: pd.DataFrame) -> dict:
      avg = df["Volume"].rolling(config.GOLD_TA_VOLUME_AVG_DAYS).mean()
      today = float(df["Volume"].iloc[-1])
      avg_today = float(avg.iloc[-1])
      return {"volume": today, "avg_volume": avg_today,
              "above_average": today > avg_today if avg_today else None}


  def compute_seasonality(close: pd.Series, as_of: date) -> dict:
      """This calendar month's historical average/median return across every year
      of available history -- month-of-year only (week-of-year would have far
      fewer samples per bucket given ~25 years of data)."""
      monthly = close.resample("ME").last()
      monthly_returns = monthly.pct_change().dropna() * 100
      same_month = monthly_returns[monthly_returns.index.month == as_of.month]
      if same_month.empty:
          return {"n": 0, "mean": None, "median": None}
      return {
          "n": len(same_month),
          "mean": round(float(same_month.mean()), 2),
          "median": round(float(same_month.median()), 2),
      }


  def compute_today_technicals() -> dict | None:
      df = _fetch_ohlcv(config.GOLD_FUTURES_TICKER, config.GOLD_BACKTEST_HISTORY_START)
      if df is None or len(df) < config.GOLD_MA_LONG_DAYS:
          return None
      close = df["Close"]
      return {
          "trend": compute_trend(df), "macd": compute_macd(close), "rsi": compute_rsi(close),
          "stochastic": compute_stochastic(df), "atr": compute_atr(df),
          "bollinger": compute_bollinger(close), "levels": compute_levels(df),
          "volume": compute_volume_context(df), "seasonality": compute_seasonality(close, date.today()),
      }
  ```
- **PATTERN**: `macro_indicators.run_all()` (586–602) for the single orchestration
  shape.
- **GOTCHA**: `compute_seasonality`'s `close.resample("ME")` requires a
  `DatetimeIndex` — confirmed present per `_fetch_ohlcv`'s tz-naive normalization.
- **VALIDATE**: `uv run --directory investments/my-trader python -m pytest mytrader/tests/test_gold_technicals.py -v`
  (after Task 5.1)

### Task 3.1 — CREATE `gold_backtest.py`: shared helpers, episode-based macro backtest

- **IMPLEMENT**:
  ```python
  from __future__ import annotations

  from datetime import date, timedelta
  from typing import NamedTuple

  import numpy as np
  import pandas as pd
  from dateutil.relativedelta import relativedelta
  from scripts.macro import fred_series_range
  from scripts.prices import compute_return_pct

  from . import config
  from .gold_technicals import (
      _fetch_ohlcv, atr_series, macd_series, moving_average_series, rsi_series, stochastic_series,
  )


  class Episode(NamedTuple):
      occurred_on: date
      signal: str
      direction: str


  def _yfinance_full_history_close(ticker: str) -> pd.Series | None:
      import yfinance as yf
      try:
          hist = yf.Ticker(ticker).history(
              start=config.GOLD_BACKTEST_HISTORY_START.isoformat(), auto_adjust=True
          )
          if hist.empty:
              return None
          close = hist["Close"]
          if getattr(close.index, "tz", None) is not None:
              close.index = close.index.tz_localize(None)
          return close
      except Exception:
          return None


  def _fred_full_history_series(series_id: str) -> pd.Series | None:
      pairs = fred_series_range(series_id, config.GOLD_BACKTEST_HISTORY_START, date.today())
      if not pairs:
          return None
      dates, values = zip(*pairs)
      return pd.Series(list(values), index=pd.to_datetime(list(dates)))


  def _merge_close_occurrences(dates: list[date], min_gap_days: int) -> list[date]:
      if not dates:
          return []
      ordered = sorted(dates)
      kept = [ordered[0]]
      for d in ordered[1:]:
          if (d - kept[-1]).days > min_gap_days:
              kept.append(d)
      return kept


  def find_real_yield_episodes(series: pd.Series) -> list[Episode]:
      negative = series[series < config.REAL_YIELD_FLAG_NEGATIVE_PCT].index
      elevated = series[series > config.REAL_YIELD_FLAG_HIGH_PCT].index
      out = []
      for d in _merge_close_occurrences([i.date() for i in negative], config.GOLD_BACKTEST_MIN_EPISODE_GAP_DAYS):
          out.append(Episode(d, "real_yields", "negative"))
      for d in _merge_close_occurrences([i.date() for i in elevated], config.GOLD_BACKTEST_MIN_EPISODE_GAP_DAYS):
          out.append(Episode(d, "real_yields", "elevated"))
      return out


  def find_dollar_index_episodes(series: pd.Series) -> list[Episode]:
      rising, falling = [], []
      lookback = timedelta(days=config.DXY_LOOKBACK_DAYS)
      for d, v in series.items():
          prior = series.asof(d - lookback)
          if pd.isna(prior) or prior == 0:
              continue
          pct_change = (v - prior) / prior * 100
          if pct_change >= config.DXY_FLAG_MOVE_PCT:
              rising.append(d.date())
          elif pct_change <= -config.DXY_FLAG_MOVE_PCT:
              falling.append(d.date())
      out = []
      for d in _merge_close_occurrences(rising, config.GOLD_BACKTEST_MIN_EPISODE_GAP_DAYS):
          out.append(Episode(d, "dollar_index", "rising"))
      for d in _merge_close_occurrences(falling, config.GOLD_BACKTEST_MIN_EPISODE_GAP_DAYS):
          out.append(Episode(d, "dollar_index", "falling"))
      return out


  def find_gold_trend_episodes(close: pd.Series) -> list[Episode]:
      ma_long = moving_average_series(close, config.GOLD_MA_LONG_DAYS)
      diff = (close - ma_long).dropna()
      sign = diff.gt(0).astype(int) - diff.lt(0).astype(int)
      sign_changed = sign.diff().fillna(0) != 0
      out = []
      for idx in sign[sign_changed].index:
          direction = "crossed_above" if sign.loc[idx] > 0 else "crossed_below"
          out.append(Episode(idx.date(), "gold_trend", direction))
      return out  # no gap-merge -- a sign-flip is already discrete/non-repeating.


  def find_gold_silver_ratio_episodes(gold: pd.Series, silver: pd.Series) -> list[Episode]:
      ratio = (gold / silver).dropna()
      high = ratio[ratio >= config.GOLD_SILVER_RATIO_FLAG_HIGH].index
      low = ratio[ratio <= config.GOLD_SILVER_RATIO_FLAG_LOW].index
      out = []
      for d in _merge_close_occurrences([i.date() for i in high], config.GOLD_BACKTEST_MIN_EPISODE_GAP_DAYS):
          out.append(Episode(d, "gold_silver_ratio", "high"))
      for d in _merge_close_occurrences([i.date() for i in low], config.GOLD_BACKTEST_MIN_EPISODE_GAP_DAYS):
          out.append(Episode(d, "gold_silver_ratio", "low"))
      return out


  def find_vix_episodes(vix: pd.Series) -> list[Episode]:
      elevated = vix[vix >= config.VIX_FLAG_LEVEL].index
      return [
          Episode(d, "vix", "elevated")
          for d in _merge_close_occurrences([i.date() for i in elevated], config.GOLD_BACKTEST_MIN_EPISODE_GAP_DAYS)
      ]


  def _position_on_or_after(gold_close: pd.Series, target: date) -> int | None:
      """Positional (iloc) index of the first row on or after target date, or
      None if target is beyond the fetched series -- used to anchor an episode's
      occurrence date into gold_close's row-position space for the trading-day
      (not calendar-day) forward-return math below."""
      idx = gold_close.index.searchsorted(pd.Timestamp(target))
      return int(idx) if idx < len(gold_close) else None


  def compute_forward_return_calendar(gold_close: pd.Series, occurred_on: date, months: int) -> float | None:
      """Month-scale forward return, calendar-date based (relativedelta + asof) --
      appropriate at this resolution since a few days' slop around a month
      boundary doesn't matter. Distinct from compute_forward_return_trading_days
      (Task 3.2), which is positional/trading-day based -- required at day/week
      resolution, where calendar-day arithmetic would land on non-trading days."""
      target = occurred_on + relativedelta(months=months)
      last_available = gold_close.index[-1].date()
      if target > last_available:
          return None
      start_price = gold_close.asof(pd.Timestamp(occurred_on))
      end_price = gold_close.asof(pd.Timestamp(target))
      if pd.isna(start_price) or pd.isna(end_price):
          return None
      return compute_return_pct(float(start_price), float(end_price))


  def _distribution_stats(returns: list[float]) -> dict:
      n = len(returns)
      if n == 0:
          return {"n": 0, "mean": None, "median": None, "win_rate": None, "best": None, "worst": None}
      wins = sum(1 for r in returns if r > 0)
      sorted_r = sorted(returns)
      median = sorted_r[n // 2] if n % 2 else (sorted_r[n // 2 - 1] + sorted_r[n // 2]) / 2
      return {
          "n": n, "mean": round(sum(returns) / n, 2), "median": round(median, 2),
          "win_rate": round(wins / n * 100, 1), "best": round(max(returns), 2), "worst": round(min(returns), 2),
      }
  ```
- **PATTERN/GOTCHA**: as originally scoped in the handoff — reuse exact live
  thresholds; in-memory series, never per-day network calls; the future-date guard
  in `compute_forward_return_calendar` is correctness-critical (`asof()` silently
  returns the last available value beyond range, which would fabricate a "forward
  return" from today's price).
- **VALIDATE**: `uv run --directory investments/my-trader python -m pytest mytrader/tests/test_gold_backtest.py -k episodes -v`

### Task 3.2 — ADD trading-day forward returns + state-conditioned backtest to `gold_backtest.py`

- **IMPLEMENT**: The new piece this revision adds — validates the 6 technical
  indicators the same way the macro signals are validated, at the day/week/month-1
  timescale they actually operate at:
  ```python
  def compute_forward_return_trading_days(gold_close: pd.Series, position: int, n_days: int) -> float | None:
      """Forward return n_days *trading days* ahead of row `position` in
      gold_close -- positional (iloc), not calendar-date based, since day/week
      horizons are too short for calendar arithmetic to be meaningful (Friday + 1
      calendar day lands on Saturday, no price)."""
      target_pos = position + n_days
      if target_pos >= len(gold_close):
          return None
      start_price = float(gold_close.iloc[position])
      end_price = float(gold_close.iloc[target_pos])
      return compute_return_pct(start_price, end_price)


  def compute_baseline_trading_days(gold_close: pd.Series, n_days: int, window_start: date, window_end: date) -> dict:
      window = gold_close[window_start.isoformat():window_end.isoformat()]
      returns = []
      for ts in window.index:
          pos = gold_close.index.get_loc(ts)
          r = compute_forward_return_trading_days(gold_close, pos, n_days)
          if r is not None:
              returns.append(r)
      return _distribution_stats(returns)


  def compute_baseline_calendar(gold_close: pd.Series, months: int, window_start: date, window_end: date) -> dict:
      window = gold_close[window_start.isoformat():window_end.isoformat()]
      returns = [
          r for d in window.index
          if (r := compute_forward_return_calendar(gold_close, d.date(), months)) is not None
      ]
      return _distribution_stats(returns)


  # -- Technical-indicator state classifiers: each returns a Series aligned to
  # close's index, values are the exact strings gold_outlook.py's live-state
  # derivation (Task 4.1) must also produce for the join to find a match.

  def state_ma_trend(close: pd.Series, ma_days: int) -> pd.Series:
      ma = moving_average_series(close, ma_days)
      return pd.Series(
          np.where(close > ma, "above", np.where(close < ma, "below", "equal")), index=close.index
      )


  def state_macd_histogram(close: pd.Series) -> pd.Series:
      hist = macd_series(close)["histogram"]
      return pd.Series(
          np.where(hist > 0, "positive", np.where(hist < 0, "negative", "flat")), index=close.index
      )


  def state_macd_crossover(close: pd.Series) -> pd.Series:
      s = macd_series(close)
      return pd.Series(np.where(s["macd"] > s["signal"], "above", "below"), index=close.index)


  def state_rsi_zone(close: pd.Series) -> pd.Series:
      rsi = rsi_series(close)
      return pd.Series(
          np.where(rsi > config.GOLD_TA_RSI_BULLISH_ABOVE, "elevated",
                   np.where(rsi < config.GOLD_TA_RSI_BEARISH_BELOW, "depressed", "neutral")),
          index=close.index,
      )


  def state_stochastic_crossover(df: pd.DataFrame) -> pd.Series:
      s = stochastic_series(df)
      return pd.Series(np.where(s["k"] > s["d"], "above", "below"), index=df.index)


  TECHNICAL_STATE_EXCLUDED_VALUES = ("equal", "flat", "neutral")  # not scored --
                                       # no bullish/bearish implication, same
                                       # treatment as a macro signal sitting
                                       # inside its un-flagged neutral range.


  def compute_state_conditioned_stats(
      state: pd.Series, gold_close: pd.Series, n_days: int, window_start: date, window_end: date
  ) -> dict[str, dict]:
      """For each distinct state value, the forward-return distribution n_days
      trading days ahead, computed on EVERY day that state held true within the
      window -- not just the day the state started (unlike episode-based
      backtesting for the macro signals, a technical indicator's state
      typically persists for many consecutive days, so this gives a real, much
      larger sample and directly answers 'given today's reading, what's tended
      to happen next'). Single O(rows) pass, not a per-state-value re-scan."""
      aligned = state.reindex(gold_close.index)
      window_start_ts, window_end_ts = pd.Timestamp(window_start), pd.Timestamp(window_end)
      by_state: dict[str, list[float]] = {}
      for pos, (ts, value) in enumerate(aligned.items()):
          if pd.isna(value) or ts < window_start_ts or ts > window_end_ts:
              continue
          r = compute_forward_return_trading_days(gold_close, pos, n_days)
          if r is not None:
              by_state.setdefault(str(value), []).append(r)
      return {k: _distribution_stats(v) for k, v in by_state.items()}
  ```
- **PATTERN**: `compute_baseline_calendar` mirrors the original handoff's
  `compute_baseline`, renamed for symmetry with the new `compute_baseline_trading_days`.
  Both state classifiers and the macro-signal episode finders share the same
  `config.py`-threshold-reuse discipline.
- **GOTCHA**: `state_rsi_zone`'s three-way classification (`"elevated"`/
  `"depressed"`/`"neutral"`) means only 2 of the 3 values are ever scored — the
  45–55 neutral band is intentionally excluded via
  `TECHNICAL_STATE_EXCLUDED_VALUES`, same treatment as a macro signal that isn't
  currently triggered.
- **GOTCHA**: All 6 state classifiers must produce value strings that exactly match
  what `gold_outlook.py`'s live-state derivation (Task 4.1) produces for the same
  live reading — this is the load-bearing join key for every lookup in this
  feature. Write the cross-consistency test (Task 5.3) before considering this
  task done, not after.
- **VALIDATE**: `uv run --directory investments/my-trader python -m pytest mytrader/tests/test_gold_backtest.py -k "state or trading_days" -v`

### Task 3.3 — ADD unified orchestration + daily-refresh wrapper to `gold_backtest.py`

- **IMPLEMENT**: Results keyed uniformly `(name, value, horizon_unit, horizon_value)`
  regardless of which methodology produced them:
  ```python
  TECHNICAL_INDICATORS = (
      "ma20_trend", "ma50_trend", "macd_histogram", "macd_crossover", "rsi_zone", "stochastic_crossover",
  )


  def run_backtest() -> dict[tuple[str, str, str, int], dict]:
      gold_close = _yfinance_full_history_close(config.GOLD_FUTURES_TICKER)
      silver_close = _yfinance_full_history_close(config.SILVER_FUTURES_TICKER)
      vix_close = _yfinance_full_history_close(config.VIX_TICKER)
      real_yield_series = _fred_full_history_series(config.FRED_REAL_YIELD_10Y_SERIES)
      dxy_series = _fred_full_history_series(config.FRED_USD_INDEX_SERIES)
      ohlcv = _fetch_ohlcv(config.GOLD_FUTURES_TICKER, config.GOLD_BACKTEST_HISTORY_START)

      if gold_close is None:
          raise RuntimeError("GC=F price history unavailable -- cannot backtest without gold's own price series")

      split = config.GOLD_BACKTEST_TRAIN_VALIDATION_SPLIT_DATE
      last_available = gold_close.index[-1].date()
      results: dict[tuple[str, str, str, int], dict] = {}

      # -- episode-based: 5 macro signals, day(1,5) + month(1,3,6,12,24) --
      episodes: list[Episode] = []
      if real_yield_series is not None:
          episodes += find_real_yield_episodes(real_yield_series)
      if dxy_series is not None:
          episodes += find_dollar_index_episodes(dxy_series)
      episodes += find_gold_trend_episodes(gold_close)
      if silver_close is not None:
          episodes += find_gold_silver_ratio_episodes(gold_close, silver_close)
      if vix_close is not None:
          episodes += find_vix_episodes(vix_close)
      validation_episodes = [e for e in episodes if e.occurred_on >= split]

      for n_days in config.GOLD_BACKTEST_FORWARD_HORIZONS_TRADING_DAYS:
          baseline = compute_baseline_trading_days(gold_close, n_days, split, last_available)
          by_group: dict[tuple[str, str], list[float]] = {}
          for ep in validation_episodes:
              pos = _position_on_or_after(gold_close, ep.occurred_on)
              if pos is None:
                  continue
              r = compute_forward_return_trading_days(gold_close, pos, n_days)
              if r is not None:
                  by_group.setdefault((ep.signal, ep.direction), []).append(r)
          for (signal, direction), returns in by_group.items():
              stats = _distribution_stats(returns)
              stats["baseline"] = baseline
              results[(signal, direction, "day", n_days)] = stats

      for months in config.GOLD_BACKTEST_FORWARD_HORIZONS_MONTHS:
          baseline = compute_baseline_calendar(gold_close, months, split, last_available)
          by_group = {}
          for ep in validation_episodes:
              r = compute_forward_return_calendar(gold_close, ep.occurred_on, months)
              if r is not None:
                  by_group.setdefault((ep.signal, ep.direction), []).append(r)
          for (signal, direction), returns in by_group.items():
              stats = _distribution_stats(returns)
              stats["baseline"] = baseline
              results[(signal, direction, "month", months)] = stats

      # -- state-conditioned: 6 technical indicators, day(1,5) + month(1) only --
      if ohlcv is not None:
          close = ohlcv["Close"]
          states = {
              "ma20_trend": state_ma_trend(close, config.GOLD_TA_MA_FAST_DAYS),
              "ma50_trend": state_ma_trend(close, config.GOLD_MA_SHORT_DAYS),
              "macd_histogram": state_macd_histogram(close),
              "macd_crossover": state_macd_crossover(close),
              "rsi_zone": state_rsi_zone(close),
              "stochastic_crossover": state_stochastic_crossover(ohlcv),
          }
          for n_days in config.GOLD_BACKTEST_FORWARD_HORIZONS_TRADING_DAYS:
              baseline = compute_baseline_trading_days(close, n_days, split, last_available)
              for name, state in states.items():
                  per_state = compute_state_conditioned_stats(state, close, n_days, split, last_available)
                  for value, stats in per_state.items():
                      if value in TECHNICAL_STATE_EXCLUDED_VALUES:
                          continue
                      stats["baseline"] = baseline
                      results[(name, value, "day", n_days)] = stats
          month_baseline = compute_baseline_calendar(close, 1, split, last_available)
          for name, state in states.items():
              # month-1 state-conditioning still needs trading-day-anchored
              # forward returns internally (state changes daily) but reported
              # against the SAME 1-month baseline the macro signals use, so
              # "this month" reads are apples-to-apples across both signal types.
              per_state = compute_state_conditioned_stats(
                  state, close, config.GOLD_TA_MA_FAST_DAYS, split, last_available
              )  # ~20 trading days approximates 1 calendar month; see NOTES.
              for value, stats in per_state.items():
                  if value in TECHNICAL_STATE_EXCLUDED_VALUES:
                      continue
                  stats["baseline"] = month_baseline
                  results[(name, value, "month", 1)] = stats

      return results


  def get_cached_or_refresh(conn, max_age_days: int = config.GOLD_BACKTEST_REFRESH_MAX_AGE_DAYS) -> dict:
      """Read the last persisted backtest if computed within max_age_days (~1 day
      by default), else recompute and persist. Monitor calls this every run --
      capping the cache at roughly a day (not the originally-planned week) means
      each new trading day's price/FRED data is folded into both backtests before
      the next day's outlook needs it, per Shaun's explicit correction: 'each
      day's new data needs to be added to the historical data.' Cheap enough to
      run daily -- a handful of bulk fetches, not per-day loops."""
      from datetime import datetime, timezone
      from . import db

      rows = db.get_gold_backtest_results(conn)
      if rows:
          last_computed = max(datetime.fromisoformat(r["computed_at"]) for r in rows)
          if (datetime.now(timezone.utc) - last_computed).days < max_age_days:
              return _rows_to_results(rows)
      results = run_backtest()
      db.upsert_gold_backtest_results(conn, results)
      return results


  def _rows_to_results(rows) -> dict[tuple[str, str, str, int], dict]:
      out = {}
      for r in rows:
          out[(r["signal"], r["direction"], r["horizon_unit"], r["horizon_value"])] = {
              "n": r["n"], "mean": r["mean_return_pct"], "median": r["median_return_pct"],
              "win_rate": r["win_rate_pct"], "best": r["best_return_pct"], "worst": r["worst_return_pct"],
              "baseline": {
                  "n": r["baseline_n"], "mean": r["baseline_mean_pct"],
                  "median": r["baseline_median_pct"], "win_rate": r["baseline_win_rate_pct"],
              },
          }
      return out


  def print_stats(results: dict) -> None:
      print(f"\n=== Gold Signal & Technical Backtest (validation window: on/after "
            f"{config.GOLD_BACKTEST_TRAIN_VALIDATION_SPLIT_DATE.isoformat()}) ===")
      for (name, value, unit, hval), stats in sorted(results.items()):
          b = stats["baseline"]
          label = f"{hval}{'d' if unit == 'day' else 'm'}"
          print(f"\n{name} ({value}), {label} forward:")
          print(f"  Signal:   N={stats['n']:<3} mean={stats['mean']} median={stats['median']} "
                f"win-rate={stats['win_rate']}% best={stats['best']} worst={stats['worst']}")
          print(f"  Baseline: N={b['n']:<3} mean={b['mean']} median={b['median']} win-rate={b['win_rate']}%")


  def main() -> None:
      import argparse
      from scripts.db import get_connection, init_db
      from .config import DB_PATH
      from .db import init_mytrader_tables, upsert_gold_backtest_results

      argparse.ArgumentParser(description="Backtest gold's macro signals and technical indicators").parse_args()
      results = run_backtest()
      init_db(DB_PATH)
      conn = get_connection(DB_PATH)
      init_mytrader_tables(conn)
      upsert_gold_backtest_results(conn, results)
      conn.close()
      print_stats(results)


  if __name__ == "__main__":
      main()
  ```
- **GOTCHA**: The month-1 state-conditioning block approximates "1 calendar
  month" as `GOLD_TA_MA_FAST_DAYS` (20) trading days for the forward-return
  offset, while its *baseline* is computed via the calendar-based
  `compute_baseline_calendar` for direct comparability with the macro signals'
  own month-1 baseline. Deliberate approximation, not a precision bug — see NOTES.
- **GOTCHA**: `run_backtest()` raises only if `gold_close is None`; every other
  series (including `ohlcv`) degrades to "skip that portion of the backtest."
- **VALIDATE**: `uv run --directory investments/my-trader python -m pytest mytrader/tests/test_gold_backtest.py -k "run_backtest or cached" -v`

### Task 3.4 — UPDATE `investments/my-trader/mytrader/db.py`

- **IMPLEMENT**: Schema uses `horizon_unit`/`horizon_value` instead of a
  months-only column, so one table serves both backtest methodologies:
  ```sql
  CREATE TABLE IF NOT EXISTS gold_backtest_results (
      id                      INTEGER PRIMARY KEY AUTOINCREMENT,
      signal                  TEXT NOT NULL,
      direction               TEXT NOT NULL,
      horizon_unit            TEXT NOT NULL,  -- 'day' or 'month'
      horizon_value           INTEGER NOT NULL,
      n                       INTEGER NOT NULL,
      mean_return_pct         REAL,
      median_return_pct       REAL,
      win_rate_pct            REAL,
      best_return_pct         REAL,
      worst_return_pct        REAL,
      baseline_n              INTEGER NOT NULL,
      baseline_mean_pct       REAL,
      baseline_median_pct     REAL,
      baseline_win_rate_pct   REAL,
      computed_at             TEXT NOT NULL,
      UNIQUE(signal, direction, horizon_unit, horizon_value)
  );
  ```
  ```python
  def upsert_gold_backtest_results(conn: sqlite3.Connection, results: dict) -> None:
      now = _now()
      with conn:
          for (signal, direction, horizon_unit, horizon_value), stats in results.items():
              b = stats["baseline"]
              conn.execute(
                  """INSERT OR REPLACE INTO gold_backtest_results
                     (signal, direction, horizon_unit, horizon_value, n, mean_return_pct,
                      median_return_pct, win_rate_pct, best_return_pct, worst_return_pct,
                      baseline_n, baseline_mean_pct, baseline_median_pct,
                      baseline_win_rate_pct, computed_at)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                  (signal, direction, horizon_unit, horizon_value, stats["n"], stats["mean"],
                   stats["median"], stats["win_rate"], stats["best"], stats["worst"],
                   b["n"], b["mean"], b["median"], b["win_rate"], now),
              )


  def get_gold_backtest_results(conn: sqlite3.Connection) -> list[sqlite3.Row]:
      return conn.execute(
          "SELECT * FROM gold_backtest_results ORDER BY signal, direction, horizon_unit, horizon_value"
      ).fetchall()
  ```
- **PATTERN**: `upsert_macro_snapshot()`/`get_macro_snapshot()` (328–347).
- **VALIDATE**: `uv run --directory investments/my-trader python -m pytest mytrader/tests/test_db.py -k gold_backtest -v`

### Task 4.1 — CREATE `gold_outlook.py`: unified live-state derivation + horizon lookup

- **IMPLEMENT**: One state-derivation function and one lookup function, shared by
  all three horizon builders — this is what actually closes the gap Shaun flagged:
  every horizon uses the identical, real-backtest-grounded method.
  ```python
  """Daily Gold Outlook -- synthesizes gold_technicals.py (live indicators),
  macro_indicators.py's 5 gold-relevant checks (live, unmodified except for the
  additive `direction` field), and gold_backtest.py (both backtest methodologies,
  refreshed roughly daily) into 3 horizon sections. Every section uses the SAME
  lookup method (_horizon_read) against real historical data -- today/tomorrow and
  this week are not a documented-rationale substitute, they use the same
  backtest-grounded approach as this month, just at shorter horizons. Advisor-note
  only: no buy/sell directive anywhere here (SOUL.md).
  """
  from __future__ import annotations

  from datetime import date

  from . import config, gold_backtest, gold_technicals

  GOLD_SIGNALS = ("real_yields", "dollar_index", "gold_trend", "gold_silver_ratio", "vix")


  def _label(beat_baseline: bool) -> str:
      return "bullish" if beat_baseline else "bearish"


  def _live_signal_states(technicals: dict, macro_checks: list) -> dict[str, str]:
      """Every currently-active signal/indicator this plan has a backtest for,
      by name -> today's state-value string. Values MUST match gold_backtest.py's
      state classifiers / episode directions character-for-character (Task 3.2's
      GOTCHA) -- this dict is the live half of the join."""
      trend = technicals["trend"]; macd = technicals["macd"]
      rsi = technicals["rsi"]; stoch = technicals["stochastic"]
      states = {
          "ma20_trend": "above" if trend["price_above_ma20"] else "below",
          "ma50_trend": "above" if trend["price_above_ma50"] else "below",
          "macd_histogram": "positive" if macd["histogram"] > 0 else "negative",
          "macd_crossover": "above" if macd["macd"] > macd["signal"] else "below",
          "rsi_zone": ("elevated" if rsi > config.GOLD_TA_RSI_BULLISH_ABOVE
                       else "depressed" if rsi < config.GOLD_TA_RSI_BEARISH_BELOW else "neutral"),
          "stochastic_crossover": "above" if stoch["k"] > stoch["d"] else "below",
      }
      for check in macro_checks:
          if check.name in GOLD_SIGNALS and check.data and check.data.get("direction"):
              states[check.name] = check.data["direction"]
      return states


  def _synthesize_label(components: dict[str, str]) -> str:
      bullish = sum(1 for v in components.values() if v == "bullish")
      bearish = sum(1 for v in components.values() if v == "bearish")
      total = len(components)
      if total == 0:
          return "insufficient historical data for today's active signals"
      if bullish > bearish and bullish >= total / 2:
          return f"bullish lean ({bullish}/{total})"
      if bearish > bullish and bearish >= total / 2:
          return f"bearish lean ({bearish}/{total})"
      return f"mixed ({bullish} bullish / {bearish} bearish / {total - bullish - bearish} neutral)"


  def _horizon_read(states: dict[str, str], backtest_results: dict, horizon_unit: str, horizon_value: int) -> dict:
      """Shared by all three horizons. Looks up EVERY currently-active
      signal/state's real backtest stats at (horizon_unit, horizon_value), scores
      only entries with actual historical data (n > 0), and always carries N so a
      thin sample never masquerades as a strong one."""
      components: dict[str, str] = {}
      notes: list[str] = []
      for name, state_value in states.items():
          if state_value in (None, "neutral", "equal", "flat"):
              continue
          stats = backtest_results.get((name, state_value, horizon_unit, horizon_value))
          if not stats or stats["n"] == 0:
              continue
          beat_baseline = (stats["mean"] or 0) > (stats["baseline"]["mean"] or 0)
          components[name] = _label(beat_baseline)
          notes.append(
              f"{name} ({state_value}): N={stats['n']}, mean {stats['mean']}% vs "
              f"baseline {stats['baseline']['mean']}%, win-rate {stats['win_rate']}%"
          )
      return {"label": _synthesize_label(components), "components": components, "notes": notes}
  ```
- **PATTERN**: `macro_indicators.run_all()` for orchestration shape; the
  transparent-component-count synthesis carried over unchanged from the earlier
  version of this plan.
- **GOTCHA**: `_live_signal_states`'s value strings and `gold_backtest.py`'s
  `state_*`/`find_*_episodes` direction strings are two independently-written
  pieces of code that must agree exactly — this is the single most important
  cross-module consistency requirement in this whole feature (Task 5.3 tests it
  directly; do not skip that test).
- **VALIDATE**: `uv run --directory investments/my-trader python -m pytest mytrader/tests/test_gold_outlook.py -k "horizon_read or synthesize or live_states" -v`

### Task 4.2 — ADD the 3 horizon builders + orchestration to `gold_outlook.py`

- **IMPLEMENT**: All three now genuinely differ only in which `(horizon_unit,
  horizon_value)` they query — this is the direct fix for Shaun's "I need it to be
  for this week, and today/tomorrow too... as well as this month":
  ```python
  def build_today_read(technicals: dict, macro_checks: list, backtest_results: dict) -> dict:
      states = _live_signal_states(technicals, macro_checks)
      read = _horizon_read(states, backtest_results, "day", 1)
      atr = technicals["atr"]; price = technicals["trend"]["price"]
      return {
          "direction_guess": read["label"],
          "confidence": "low -- shortest horizon, smallest per-signal samples" if read["components"] else "unavailable",
          "components": read["components"], "notes": read["notes"],
          "expected_move_dollars": round(atr, 2),
          "expected_move_pct": round(atr / price * 100, 2),
          "resistance": technicals["levels"]["resistance"], "support": technicals["levels"]["support"],
          "volume_note": "above-average volume" if technicals["volume"]["above_average"] else "below-average volume",
      }


  def build_week_read(technicals: dict, macro_checks: list, backtest_results: dict) -> dict:
      states = _live_signal_states(technicals, macro_checks)
      read = _horizon_read(states, backtest_results, "day", 5)
      return {
          "direction_guess": read["label"],
          "confidence": "medium -- more historical data than today/tomorrow, less than this month" if read["components"] else "unavailable",
          "components": read["components"], "notes": read["notes"],
      }


  def build_month_read(technicals: dict, macro_checks: list, backtest_results: dict) -> dict:
      states = _live_signal_states(technicals, macro_checks)
      read = _horizon_read(states, backtest_results, "month", 1)
      seasonality = technicals["seasonality"]
      components = dict(read["components"])
      notes = list(read["notes"])
      if seasonality["n"] > 0 and seasonality["median"] is not None:
          components["seasonality"] = _label(seasonality["median"] > 0)
          notes.append(f"seasonality: this calendar month has historically averaged "
                       f"{seasonality['mean']}% (median {seasonality['median']}%, N={seasonality['n']} years)")
      return {
          "direction_guess": _synthesize_label(components),
          "confidence": "highest -- most historical data, longest-validated horizon" if components else "unavailable",
          "components": components, "notes": notes, "seasonality": seasonality,
      }


  def build_outlook(conn, macro_checks: list) -> dict | None:
      technicals = gold_technicals.compute_today_technicals()
      if technicals is None:
          return None
      try:
          backtest_results = gold_backtest.get_cached_or_refresh(conn)
      except Exception as e:
          print(f"[gold_outlook] backtest unavailable: {e}")
          backtest_results = {}
      return {
          "as_of": date.today().isoformat(),
          "today": build_today_read(technicals, macro_checks, backtest_results),
          "week": build_week_read(technicals, macro_checks, backtest_results),
          "month": build_month_read(technicals, macro_checks, backtest_results),
      }


  def render_outlook_markdown(outlook: dict) -> str:
      t, w, m = outlook["today"], outlook["week"], outlook["month"]
      lines = [
          "# Gold Outlook", "",
          "Auto-generated by Monitor -- overwritten every run. Advisor notes only -- "
          "guesses for your own review, never a trade directive (see SOUL.md). Every "
          "horizon's guess is grounded in real historical backtest data (N always "
          "shown), refreshed roughly daily so each new trading day's data is folded "
          "in; confidence is labeled per horizon and scales with how much history "
          "backs it -- lowest for Today/Tomorrow, highest for This Month.",
          "", f"## As of {outlook['as_of']}", "",
          f"### Today / Tomorrow -- {t['direction_guess']} (confidence: {t['confidence']})",
      ]
      for note in t["notes"]:
          lines.append(f"- {note}")
      lines += [
          f"- Expected daily move (ATR-based): ~${t['expected_move_dollars']} ({t['expected_move_pct']}%)",
          f"- Nearest resistance: ${t['resistance']}, nearest support: ${t['support']}",
          f"- Volume: {t['volume_note']}", "",
          f"### This Week -- {w['direction_guess']} (confidence: {w['confidence']})",
      ]
      for note in w["notes"]:
          lines.append(f"- {note}")
      lines += ["", f"### This Month -- {m['direction_guess']} (confidence: {m['confidence']})"]
      for note in m["notes"]:
          lines.append(f"- {note}")
      lines += ["", "Small sample sizes throughout -- read directionally, not as proof. "
                     "Never a buy/sell recommendation."]
      return "\n".join(lines) + "\n"


  def write_outlook(outlook: dict) -> None:
      config.MY_TRADER_DIR.joinpath("gold-outlook.md").write_text(
          render_outlook_markdown(outlook), encoding="utf-8"
      )
  ```
- **PATTERN**: `monitor.render_report()` (143–197) for markdown-building style.
- **VALIDATE**: `uv run --directory investments/my-trader python -c "from mytrader.gold_outlook import build_outlook, write_outlook; from mytrader.macro_indicators import run_all; from scripts.db import get_connection, init_db; from mytrader.config import DB_PATH; from mytrader.db import init_mytrader_tables; init_db(DB_PATH); conn = get_connection(DB_PATH); init_mytrader_tables(conn); o = build_outlook(conn, run_all()); write_outlook(o); print('wrote gold-outlook.md')"`

### Task 4.3 — UPDATE `investments/my-trader/mytrader/monitor.py`

- **IMPLEMENT**: In `run_monitor()`, immediately after the macro-checks block
  (after line 126, before `snapshot.regenerate_all(conn)`):
  ```python
  try:
      outlook = gold_outlook.build_outlook(conn, macro_checks)
      if outlook is not None:
          gold_outlook.write_outlook(outlook)
  except Exception as e:
      print(f"[monitor] error building gold outlook: {e}")
      outlook = None
  ```
  Add `"gold_outlook_available": outlook is not None` to the returned dict. Add
  `gold_outlook` to the existing top-of-file import line (`from . import
  candidate_sync, config, db, engine, gold_outlook, macro_indicators, market_data,
  snapshot`, alphabetical, matching every other same-package import already there —
  no circular-import risk since `gold_outlook.py` never imports `monitor.py`). In
  `render_report()`, add a pointer section after "Macro Indicators":
  ```python
  lines += ["", "### Gold Outlook"]
  if result.get("gold_outlook_available"):
      lines.append("See investments/my-trader/gold-outlook.md — today/tomorrow, "
                    "this week, and this month reads, refreshed this run.")
  else:
      lines.append("Unavailable this run.")
  ```
- **PATTERN**: The "New Candidates Synced" pointer shape (185–194).
- **VALIDATE**: `uv run --directory investments/my-trader python -m pytest mytrader/tests/test_monitor.py -v`
  (after Task 5.4 stubs the new call)

### Task 4.4 — UPDATE `investments/my-trader/mytrader/main.py`

- **IMPLEMENT**:
  ```python
  def cmd_gold_backtest(args) -> None:
      from .db import upsert_gold_backtest_results
      from .gold_backtest import print_stats, run_backtest

      conn = _open_conn()
      results = run_backtest()
      upsert_gold_backtest_results(conn, results)
      conn.close()
      print_stats(results)
  ```
  ```python
  subparsers.add_parser(
      "gold-backtest",
      help="Force a fresh backtest of gold's macro signals + technical indicators (slow, on-demand)",
  )
  ```
  Add `"gold-backtest": cmd_gold_backtest,` to `dispatch`.
- **PATTERN**: `cmd_sync_candidates()`/`"sync-candidates"` (174–186, 287–290).
- **VALIDATE**: `uv run --directory investments/my-trader python -m mytrader.main gold-backtest --help`

### Task 5.1 — CREATE `investments/my-trader/mytrader/tests/test_gold_technicals.py`

- **IMPLEMENT**: Deterministic synthetic-`DataFrame` tests, mirroring
  `test_crash_windows.py`'s pattern — one hand-computed-expected-value test per
  `*_series`/`compute_*` function (trend, MACD, RSI at both extremes, Stochastic at
  its period high, ATR on a known true range, Bollinger width widening with
  variance, levels within a window, volume above/below average, seasonality
  filtering to the matching month across years), plus
  `test_compute_today_technicals_returns_none_when_history_too_short`.
- **VALIDATE**: `uv run --directory investments/my-trader python -m pytest mytrader/tests/test_gold_technicals.py -v`

### Task 5.2 — CREATE `investments/my-trader/mytrader/tests/test_gold_backtest.py`

- **IMPLEMENT**:
  - Episode finders: same deterministic-known-answer tests as originally scoped,
    including `test_find_gold_trend_episodes_detects_every_sign_flip_no_merge`.
  - `test_compute_forward_return_calendar_returns_none_for_future_target` and
    `test_compute_forward_return_trading_days_returns_none_past_series_end` — both
    correctness-critical future-date guards, tested independently since they use
    different mechanisms (asof vs positional).
  - State classifiers: `test_state_ma_trend_labels_above_below_equal`,
    `test_state_macd_histogram_sign`, `test_state_macd_crossover`,
    `test_state_rsi_zone_three_way_split`, `test_state_stochastic_crossover` — each
    against a hand-built series with a known expected state sequence.
  - `test_compute_state_conditioned_stats_uses_every_day_state_holds` — a
    synthetic series where a state persists for N consecutive days, assert the
    resulting sample size reflects all N days (not just the first), proving this
    is genuinely different from episode-based counting.
  - `test_get_cached_or_refresh_uses_fresh_cache_without_refetching` and
    `test_get_cached_or_refresh_refetches_when_stale` (seed a `computed_at` more
    than `GOLD_BACKTEST_REFRESH_MAX_AGE_DAYS` (~1 day) old — not a week old —
    reflecting the daily-refresh correction).
- **VALIDATE**: `uv run --directory investments/my-trader python -m pytest mytrader/tests/test_gold_backtest.py -v`

### Task 5.3 — CREATE `investments/my-trader/mytrader/tests/test_gold_outlook.py`

- **IMPLEMENT**:
  - `test_horizon_read_scores_only_entries_with_historical_data` — a state present
    in `states` but absent from `backtest_results` is silently omitted, not scored
    as neutral/zero.
  - `test_synthesize_label_counts_and_labels_correctly`.
  - **`test_live_state_values_match_gold_backtest_state_and_episode_labels`** — for
    every one of the 11 signals/indicators (5 macro + 6 technical), construct a
    live reading known to produce each possible state, and independently construct
    the equivalent historical input to `gold_backtest.py`'s matching `state_*`/
    `find_*_episodes` function; assert the two produce identical value strings.
    This is the cross-module consistency test Task 4.1's GOTCHA requires — it is
    the single most important test in this feature, since a silent string mismatch
    here means a signal just vanishes from the outlook with no error anywhere.
  - `test_build_today_week_month_reads_query_different_horizons` — same
    `backtest_results` fixture with distinct stats seeded at `("day",1)`, `("day",5)`,
    `("month",1)` for the same signal; assert each horizon builder surfaces its own
    horizon's numbers, not another horizon's by accident.
  - `test_render_outlook_markdown_includes_all_three_horizon_sections`.
- **VALIDATE**: `uv run --directory investments/my-trader python -m pytest mytrader/tests/test_gold_outlook.py -v`

### Task 5.4 — UPDATE `test_monitor.py` + `briefs-finance` tests

- **IMPLEMENT**: In `test_monitor.py`, stub `gold_outlook.build_outlook` (check
  whether an existing fixture already globally stubs `macro_indicators.run_all` and
  mirror that same treatment) and add a test asserting `render_report()`'s new
  "Gold Outlook" section renders correctly in both the available/unavailable case.
  In `investments/briefs-finance/scripts/tests/test_macro.py`, add
  `test_fred_series_range_returns_ascending_pairs_within_window` and
  `test_fred_series_range_returns_none_without_key`, following that file's
  `unittest.mock.patch` convention.
- **VALIDATE**: `uv run --directory investments/my-trader python -m pytest mytrader/tests/test_monitor.py -v` /
  `uv run --directory investments/briefs-finance python -m pytest scripts/tests/test_macro.py -v`

### Task 6.1 — UPDATE `.claude/skills/my-trader/SKILL.md`

- **IMPLEMENT**:
  1. Fix the stale "out of scope for this pass" sentence at the end of "Macro
     Monitoring Indicators" — point to the new "Gold Outlook" section.
  2. Add `uv run --directory investments/my-trader python -m mytrader.main
     gold-backtest` to the Quick Reference block.
  3. New `## Gold Outlook` section: what it is (`gold-outlook.md`, regenerated
     every `monitor` run, three horizons — Today/Tomorrow, This Week, This Month —
     each a real directional guess grounded in real historical backtest data, not
     just live readings); the two backtest methodologies in one sentence each
     (episode-based for the 5 rare macro signals, state-conditioned for the 6
     common technical indicators); the daily-refresh cadence
     (`GOLD_BACKTEST_REFRESH_MAX_AGE_DAYS`, ~1 day — each new trading day's data is
     folded in automatically, not left stale for a week); confidence scales per
     horizon; a real worked example (**write after Task 7**); explicit non-goals
     (no buy/sell directive, no autonomous action, small samples — read
     directionally).
- **VALIDATE**: Manual read-through, written last.

### Task 7 — Manual validation against the real environment

- **IMPLEMENT**:
  1. Full test suite, both workspace members — zero regressions.
  2. `uv run --directory investments/my-trader python -m mytrader.main monitor` —
     confirm `gold-outlook.md` is created, `monitor-report.md` shows the pointer,
     and the run completes in reasonable time (first run of the day does the full
     backtest; a same-day re-run hits the cache).
  3. Read `gold-outlook.md` end to end — confirm all three horizons show a real
     direction guess with N-backed notes and an appropriately scaled confidence
     label (Today/Tomorrow visibly more hedged than This Month).
  4. Cross-check `gold_technicals`' trend section against
     `macro_indicators.check_gold_trend()`'s live output for basic sanity.
  5. Force a fresh backtest via `mytrader.main gold-backtest`, confirm it completes
     in a reasonable time (low tens of seconds at most — this now does
     meaningfully more computation than the original macro-only design, but still
     zero per-day network calls, so a slowdown here means a loop is doing
     something it shouldn't).
  6. Confirm the daily-refresh behavior directly: run `monitor` on two different
     days (or manually backdate a `computed_at` row in `gold_backtest_results` by
     more than a day), confirm the second run triggers a real recompute rather
     than serving a stale cache — this is the concrete check for "each day's new
     data needs to be added to the historical data."
  7. Spot-check one state-conditioned result by hand (e.g. count how many trading
     days `rsi_zone` was `"elevated"` in a small date range and manually verify
     against `compute_state_conditioned_stats`'s reported N for that range).
  8. Write Task 6.1's worked-example section using this run's real numbers.
- **VALIDATE**:
  ```powershell
  uv run --directory investments/my-trader python -m pytest mytrader/tests -v
  uv run --directory investments/briefs-finance python -m pytest scripts/tests -v
  uv run --directory investments/my-trader python -m mytrader.main monitor
  uv run --directory investments/my-trader python -m mytrader.main gold-backtest
  ```

---

## TESTING STRATEGY

### Unit Tests
Every indicator/state-classifier/episode-finder function gets a deterministic,
hand-computed-expected-value test. The cross-module state-string consistency test
(Task 5.3) is the single highest-priority test in this feature — a mismatch there
is a silent, hard-to-notice bug (a signal just disappears from the outlook).

### Integration Tests
`run_backtest()`/`get_cached_or_refresh()`/`build_outlook()` each get an end-to-end
test with every sub-fetch mocked. `test_monitor.py`'s updated suite is the
integration check for the Monitor wiring.

### Edge Cases
- Insufficient price history → `compute_today_technicals()`/`build_outlook()`
  return `None`, Monitor renders "Unavailable this run."
- `FRED_API_KEY` unset → `real_yields`/`dollar_index` absent from both the episode
  backtest and the live outlook's macro-signal components; technical-indicator
  components are unaffected (no FRED dependency).
- A live state with no matching historical row (`backtest_results.get(...)` is
  `None`) → silently omitted from that horizon's components, never scored as 0/
  neutral.
- Forward-return targets beyond either fetched series' range → excluded from
  stats, never fabricated (both the calendar-based `asof` guard and the
  positional trading-day guard).
- A technical indicator's neutral state (`"equal"`/`"flat"`/`"neutral"`) → never
  scored, at any horizon.
- Backtest cache exactly at the ~1-day freshness boundary → tested both sides.
- Monitor runs more than once on the same calendar day → the second run reuses the
  cache rather than redundantly re-fetching/recomputing.

---

## VALIDATION COMMANDS

### Level 1: Syntax & Style
```powershell
uv run --directory investments/my-trader ruff check mytrader
uv run --directory investments/my-trader mypy mytrader
uv run --directory investments/briefs-finance ruff check scripts
uv run --directory investments/briefs-finance mypy scripts
```

### Level 2: Unit Tests
```powershell
uv run --directory investments/my-trader python -m pytest mytrader/tests -v
uv run --directory investments/briefs-finance python -m pytest scripts/tests -v
```

### Level 3: Integration Tests
```powershell
uv run --directory investments/my-trader python -m pytest mytrader/tests/test_gold_technicals.py mytrader/tests/test_gold_backtest.py mytrader/tests/test_gold_outlook.py mytrader/tests/test_monitor.py mytrader/tests/test_db.py -v
uv run --directory investments/briefs-finance python -m pytest scripts/tests/test_macro.py -v
```

### Level 4: Manual Validation
See Task 7.

### Level 5: Additional Validation
N/A.

---

## ACCEPTANCE CRITERIA

- [ ] `gold_technicals.py` exposes both full-history `*_series()` functions and
      today-only `compute_*()` wrappers for trend, MACD, RSI, Stochastic, ATR,
      Bollinger, levels, volume, seasonality — one formula per indicator, reused
      by both the live snapshot and the historical backtest
- [ ] `gold_backtest.py` runs BOTH an episode-based backtest (5 macro signals, at
      day-1/day-5/month-1/3/6/12/24 horizons) AND a state-conditioned backtest (6
      technical indicators, at day-1/day-5/month-1 horizons), unified under one
      `(name, value, horizon_unit, horizon_value)` results shape and one DB table
- [ ] The backtest cache refreshes roughly once per day
      (`GOLD_BACKTEST_REFRESH_MAX_AGE_DAYS = 1`), not once per week, so each new
      trading day's price/FRED data is folded into the historical dataset before
      the next outlook is built
- [ ] Every currently-active signal/indicator state is looked up against real
      historical data at all three outlook horizons — Today/Tomorrow and This Week
      are genuinely backtest-grounded, not a documented-rationale substitute
- [ ] `gold_outlook.py`'s three horizon builders all use the same `_horizon_read()`
      lookup, differing only in which `(horizon_unit, horizon_value)` they query
- [ ] The live-state derivation in `gold_outlook.py` and the state/episode
      classifiers in `gold_backtest.py` are verified identical via a dedicated
      cross-module consistency test (Task 5.3)
- [ ] `monitor.py` calls the outlook builder once per run, writes
      `gold-outlook.md`, `monitor-report.md` gets a one-line pointer
- [ ] `macro_indicators.py`'s live check thresholds/verdict logic are unmodified;
      the only change is the additive `direction` field
- [ ] No buy/sell directive, no autonomous trading action, anywhere in any new file
- [ ] All validation commands pass with zero errors, zero regressions

---

## COMPLETION CHECKLIST

- [ ] All tasks completed in order (1.1–1.3 → 2.1–2.2 → 3.1–3.4 → 4.1–4.4 →
      5.1–5.4 → 6.1 → 7)
- [ ] Each task's own validation command passed immediately after that task
- [ ] Full test suite passes for both `my-trader` and `briefs-finance`
- [ ] `ruff`/`mypy` clean for all changed/new files
- [ ] Real `monitor` run produces a real, honest, fully backtest-grounded
      `gold-outlook.md` at all three horizons, confirmed to refresh with new data
      daily (Task 7 step 6)
- [ ] `SKILL.md` documentation updated with real output, written last
- [ ] Acceptance criteria all met

---

## NOTES

**Why two backtest methodologies instead of one**: the 5 macro signals are rare,
discrete regime-shift events (a handful to a few dozen occurrences across decades) —
episode-based backtesting (forward return from each occurrence date) is the right
fit. The 6 technical indicators are common, persistent daily readings (price is
above or below its 20DMA on the large majority of trading days) — treating them as
discrete "episodes" would either drastically undercount the real sample (using only
the crossing moment) or require inventing an artificial de-duplication rule for
something that isn't actually a rare event. State-conditioned backtesting (forward
return computed on every day a state held, not just when it started) is the
statistically correct fit and is standard practice in real technical-indicator
validation studies ("what's the average N-day forward return when RSI > 70").

**Why technical indicators stop at a 1-month horizon (no 3/6/12/24-month legs)**: a
14-day RSI or a 20-day moving average has essentially nothing to say about gold 12
or 24 months out — extending their backtest to those horizons would produce numbers
that look precise but aren't meaningfully connected to what the indicator measures.
The macro signals (yields, USD strength, VIX) are slower-moving and plausibly
relevant at those longer horizons, which is why only they get the full 1/3/6/12/24
set.

**Why the month-1 state-conditioning uses a trading-day approximation
(`GOLD_TA_MA_FAST_DAYS`, 20 trading days) rather than exact calendar-month
arithmetic**: its baseline is deliberately computed via the same calendar-based
`compute_baseline_calendar` the macro signals use at month-1, so This Month's
technical-indicator numbers and macro-signal numbers are directly comparable
side by side — matching horizons exactly (not off by a few days from calendar-month
imprecision) was judged more valuable than exact calendar precision at this
resolution, where a few days either way barely changes month-scale returns.

**Why every horizon gets a direction, but confidence is scaled per horizon**: an
earlier version of this plan withheld any directional call for Today/Tomorrow
entirely. Shaun corrected this: "This isn't you deciding what I should do. This is
you giving a guided guess." Confidence still honestly reflects how much history
backs each horizon's read (least at today/tomorrow, most at this month) — but every
horizon gets a real guess, not a refusal.

**Why This Week and Today/Tomorrow originally lacked real backtest grounding, and
why that was wrong**: the first version of this plan only historically validated
the 5 macro signals (month-scale), leaving the technical indicators — which drive
most of Today/Tomorrow's and all of This Week's read — resting on live values plus
documented rationale (e.g. "negative real yields = bullish, per config.py's own
comment") rather than an actual backtest. Shaun caught this directly: "This is
painful... I need it to be for this week, and today/tomorrow too... as well as this
month." This revision's state-conditioned backtest (Tasks 3.2–3.3) and the unified
`_horizon_read()` lookup (Task 4.1) are the fix — every section now works the same
way, just at a different horizon.

**Why the backtest refreshes roughly daily instead of weekly**: the original
`GOLD_BACKTEST_REFRESH_MAX_AGE_DAYS` was set to 7, reasoning that decades of history
only meaningfully change when a new rare macro episode occurs. Shaun corrected this
too: "each day's new data needs to be added to the historical data" — a fair point
independent of episode rarity, since the state-conditioned technical backtest (and
the live outlook's own freshness) benefits from every new trading day's candle being
folded in promptly, and the full-history refresh was already confirmed cheap (a
handful of bulk fetches, not per-day loops) — there was no real performance reason
for a week-long cache in the first place. `GOLD_BACKTEST_REFRESH_MAX_AGE_DAYS` is
now 1.

**Why the Phase 1 tweak (Task 1.3) is safe**: adding a `direction` field is purely
additive — every existing caller of these 5 checks reads `verdict`/`detail`/existing
`data` keys, none of which change. A new dict key an existing caller doesn't look
for is inert to it.

**Scope still not covered**: options-implied volatility/skew, CFTC Commitment-of-
Traders positioning, intraday/tick-level price action, and any machine-learning
forecast model — none available from this codebase's existing free data sources
without a new, separately-justified integration.
