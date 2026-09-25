# Feature: Matt Damon Price/Volatility/Volume Check

The following plan should be complete, but it's important that you validate
documentation and codebase patterns and task sanity before you start implementing.

Pay special attention to naming of existing utils/types/models. Import from the
right files.

## Feature Description

A new `my-trader` assessment check that reads the rate of change (ROC) of price,
volatility, and volume together for a ticker, over a short (10-trading-day) and a
long (25-trading-day) window, and reports whether the three are moving in an
aligned direction ("confluence") or not. It runs everywhere the existing
assessment engine already runs — Monitor's daily holdings+watchlist loop AND an
on-demand `find --ticker X` lookup — with zero new CLI wiring, by being added to
`engine.py`'s existing unconditional check list the same way `price_action` and
`technical_levels` already are.

Before this check's alignment reading is allowed to imply anything predictive, a
one-off backtest script answers the actual empirical question Shaun asked
("is this combination a better predictor than price alone") using real historical
data across his own holdings + watchlist. Until/unless that backtest shows a real
edge, the check stays `verdict="info"` — a reporting tool, not a signal — mirroring
`price_action.py` and `technical_levels.py`'s own explicit "report the fact, don't
judge it" precedent, and avoiding the exact mistake that shipped and failed in
Goat's original heartbeat "quiet base" BBW-percentile leg (an unvalidated
lookback-window assumption that produced zero candidates against the entire S&P
500 for 10 days before being diagnosed and rebuilt).

## User Story

As Shaun (my-trader's only user)
I want a daily (and on-demand, per-ticker) read of price/volatility/volume rate-of-
change together, not just each in isolation
So that I can see whether the three-signal combination is actually a more useful
read than any one alone — backed by a real historical check, not just an assumption

## Problem Statement

Every existing technical check in my-trader (`price_action.py`, `technical_levels.py`)
looks at one dimension at a time. Shaun's thesis is that price momentum,
volatility expansion/contraction, and volume confirmation carry different pieces
of the same story, and reading them together might predict direction better than
any one alone — but that is an empirical claim, not yet checked against real data.

## Solution Statement

1. Build a new check module that computes price ROC, volatility ROC (rolling
   std-dev of returns), and volume ROC (on smoothed volume) at two windows (10
   trading days, 25 trading days), and reports the six raw numbers plus a
   descriptive (not predictive) alignment label per window.
2. Wire it into `engine.py`'s existing unconditional results list so it appears
   automatically in both Monitor's daily report and `find --ticker X`.
3. Build a one-off backtest script, reusing `gold_backtest.py`'s existing generic
   state-conditioned forward-return machinery, that classifies every trading day
   of ~2 years of history for every current holding + "discussed" watchlist ticker
   into a confluence state, and compares the state-conditioned forward 10-trading-
   day return against (a) an unconditioned baseline and (b) a price-ROC-only
   classifier, using the same tickers/history.
4. Write the backtest's result (positive or negative) back into
   `investments/roc-triple-signal-handoff.md` so the finding isn't lost.

## Feature Metadata

**Feature Type**: New Capability (check module) + one-off research script
**Estimated Complexity**: Medium
**Primary Systems Affected**: `investments/my-trader/mytrader/checks/`,
`investments/my-trader/mytrader/engine.py`, `investments/my-trader/mytrader/config.py`
**Dependencies**: `yfinance`, `pandas`, `numpy` — all already used by this package.
No new external dependency.

---

## CONTEXT REFERENCES

### Relevant Codebase Files — READ THESE BEFORE IMPLEMENTING

- `investments/my-trader/mytrader/checks/technical_levels.py` (all 79 lines) —
  closest direct precedent for this new check's shape: private `_fetch_*_series`
  helper (lines 25-42) split out for monkeypatch-based unit testing, `check()`
  taking `data: TickerData` (lines 45-78), `verdict="info"`/`"unknown"` only,
  `data={...}` dict on `CheckResult` for raw numbers, two-candidate
  bare-then-`.AX` ticker lookup (lines 31-41).
- `investments/my-trader/mytrader/checks/price_action.py` (all 31 lines) — the
  "report the fact, don't judge it" philosophy this check must also follow;
  its docstring (lines 9-13) is the direct textual precedent to echo in the new
  module's own docstring.
- `investments/my-trader/mytrader/checks/__init__.py` (14 lines) — the
  `CheckResult` dataclass every check returns (`name`, `verdict`, `detail`, `data`).
- `investments/my-trader/mytrader/engine.py` lines 10-28 (import block) and
  169-175 (`results = [...]` list) — the wiring point. `price_action.check(...)`,
  `crash_resilience.check(data)`, and `technical_levels.check(data)` are all
  appended here unconditionally (not gated behind an `include_*` flag like
  `principles_fit`/`news_events`/`insider_selling`/`earnings_deterioration`,
  which are Find-only LLM-cost opt-ins). This new check is cheap pure-yfinance
  math, so it belongs in this same unconditional list — that single addition is
  what makes it appear in both Monitor and Find automatically, no other wiring
  needed.
- `investments/my-trader/mytrader/find.py` lines 10-20 (`lookup_ticker`) — confirms
  Find calls `engine.run_assessment(...)`, same function Monitor calls
  (`monitor.py` line 91: `engine.run_assessment(ticker, conn)`), which is *why*
  adding the check to `engine.py`'s unconditional list alone satisfies "should
  also assess a stock I manually give you" with no CLI change.
- `investments/my-trader/mytrader/main.py` lines 20-34 (`_print_assessment`) —
  loops over `result["checks"]` generically (`for check in result["checks"]:
  print(...)`), so a new check needs no special-case rendering here either.
- `investments/my-trader/mytrader/monitor.py` lines 138-142 (holdings_report
  `"checks"` list comprehension) — same generic rendering on the Monitor report
  side; confirms no `monitor.py` changes are needed beyond what `engine.py`
  already provides.
- `investments/my-trader/mytrader/market_data.py` lines 24-37 (`cached_session`)
  — Monitor wraps its whole run in this context to avoid refetching `.info` per
  ticker; the new history+volume fetch this check needs is a *different* yfinance
  call (`.history()`, not `.info`) so it is NOT covered by this existing cache —
  call it directly per-check the same way `technical_levels._fetch_close_series`
  already does (that fetch also isn't cached, and is accepted as-is).
- `investments/my-trader/mytrader/tickers.py` (15 lines) — `normalize()` and
  `asx_variant()`, reuse directly, don't reimplement.
- `investments/goat/goat/price_history.py` (all 35 lines) — the closest existing
  long-range fetch pattern, BUT it only keeps `hist["Close"]` (line 28) and
  discards `Volume`. Do not import/reuse this function as-is — write a sibling
  function in the new check module that keeps both columns (see Gotcha below).
- `investments/my-trader/mytrader/gold_backtest.py` (all 462 lines) — **the
  backtest script's direct methodology precedent**, not
  `investments/backtest/` (see Gotcha below). Specifically reuse (import, don't
  reimplement):
  - `compute_forward_return_trading_days(close, position, n_days)` (lines
    179-189) — positional forward-return math.
  - `compute_baseline_trading_days(close, n_days, window_start, window_end)`
    (lines 192-200) — unconditioned baseline distribution over a date window.
  - `compute_state_conditioned_stats(state, close, n_days, window_start,
    window_end)` (lines 271-290) — the exact "classify every day into a state,
    compute forward-return distribution per state" function this backtest needs;
    takes any `state: pd.Series` of string labels aligned to `close`'s index, so
    it works unmodified for a confluence-state series instead of a gold
    technical-indicator state series.
  - `_distribution_stats` (lines 166-176) is private (underscore) — don't import
    it directly; the three functions above already call it internally and return
    its `{n, mean, median, win_rate, best, worst}` shape.
  - `state_ma_trend` (lines 216-220) as the *pattern* (not the function itself)
    for writing a state-classifier: `pd.Series(np.where(cond, "label_a",
    np.where(cond2, "label_b", "label_c")), index=close.index)`.
- `investments/my-trader/mytrader/tests/test_gold_backtest.py` lines 1-50 — test
  pattern for state-classifier and episode-finder functions (monkeypatch config
  constants, build a small synthetic `pd.Series`/`pd.DataFrame`, assert on
  labels/positions).
- `investments/my-trader/mytrader/tests/test_checks_technical_levels.py` (all 60
  lines) — exact test pattern to mirror for the new check module: monkeypatch the
  private fetch helper to return a synthetic `pd.Series`/`pd.DataFrame`, assert on
  `verdict`/`detail`/`data` keys. Covers: no data → unknown, fetch failure →
  unknown, insufficient history → unknown, full-history happy path, partial-
  history partial-output.
- `investments/my-trader/mytrader/config.py` lines 429-462 (`GOLD_TA_*` section)
  and 464-499 (`GOLD_BACKTEST_*` section) — the constants-naming and inline-
  comment-rationale style to mirror for the new `MATT_DAMON_*` constants
  (see Task list below for exact names).
- `investments/my-trader/mytrader/db.py` — read `get_all_holdings(conn)` and
  `get_all_watchlist(conn)` signatures (used by `monitor.py` lines 109-110) —
  the backtest script needs the same holdings + `status="discussed"` watchlist
  rows Monitor already re-checks daily (confirms handoff's open question #6).
- `.agent/plans/completed/goat-heartbeat-quiet-redesign.md` — read in full. The
  direct cautionary precedent: a plausible technical pattern (BBW rolling
  percentile) shipped as a live gate with an unvalidated 252-trading-day
  lookback window the fetched history couldn't fill, ran for 10 days, produced
  zero candidates, then needed a full diagnose-and-rebuild. This plan's
  "verdict stays info until backtest earns it" structure exists specifically to
  not repeat this.
- `investments/roc-triple-signal-handoff.md` (the source handoff, already read in
  full this session) — every open question this plan resolves traces back to a
  numbered question in that file's "Open Questions" section; the resolutions are
  restated inline below so this plan is self-contained, but the handoff has the
  full reasoning if anything here seems under-justified.

### New Files to Create

- `investments/my-trader/mytrader/checks/matt_damon_price_volitility_volume_check.py` — the check module
  (fetch helper + ROC/state computation + `check()`).
- `investments/my-trader/mytrader/matt_damon_price_volitility_volume_check_backtest.py` — the one-off
  validation script (module-level, alongside `gold_backtest.py`, not inside
  `checks/` since it's not itself a `CheckResult`-returning check).
- `investments/my-trader/mytrader/tests/test_checks_matt_damon_price_volitility_volume_check.py` — unit
  tests for the check module.
- `investments/my-trader/mytrader/tests/test_matt_damon_price_volitility_volume_check_backtest.py` — unit
  tests for the state-classifier + aggregation logic in the backtest script
  (not for the live yfinance pull — mirrors `test_gold_backtest.py`'s approach
  of testing classifiers/math against synthetic series, not real network calls).

### Files to Update

- `investments/my-trader/mytrader/engine.py` — add the import and one line in
  the unconditional `results = [...]` list (lines 169-175).
- `investments/my-trader/mytrader/config.py` — add a new `MATT_DAMON_*`
  constants section, mirroring the `GOLD_TA_*`/`GOLD_BACKTEST_*` style at lines
  429-499.
- `investments/roc-triple-signal-handoff.md` — append the backtest's result
  (positive or negative) once run, per the handoff's own "Validation" section
  instruction. Do this as the last implementation task, not before.

### Patterns to Follow

**Naming Conventions:** snake_case module/function names, `_leading_underscore`
for module-private helpers meant to be monkeypatched in tests (see
`technical_levels._fetch_close_series`), `SCREAMING_SNAKE_CASE` for config
constants grouped under a dated comment banner (see `config.py` line 429-433).

**Check module shape** (from `technical_levels.py`):
```python
def _fetch_*_series(ticker: str):
    ...  # private, monkeypatched directly in tests

def check(data) -> CheckResult:
    if data is None:
        return CheckResult(name="...", verdict="unknown", detail="No market data available")
    series = _fetch_*_series(data.ticker)
    if series is None or <not enough history>:
        return CheckResult(name="...", verdict="unknown", detail="Not enough price history for ...")
    ...
    return CheckResult(name="...", verdict="info", detail="...", data={...})
```

**Error handling:** every yfinance call is wrapped in a bare
`try/except Exception: continue`/`return None` (see every fetcher in
`market_data.py`, `technical_levels.py`, `goat/price_history.py`) — never let a
single ticker's network hiccup break the whole Monitor run. Match this exactly.

**Docstring rationale style:** every non-obvious module in this codebase opens
with a docstring explaining *why*, often citing a specific date/quote/prior
incident (see `technical_levels.py` lines 1-14, `price_action.py` lines 1-13).
The new check's docstring must state plainly that the alignment label is
descriptive only, not a validated predictive claim, pointing at the backtest
script and this plan file.

---

## IMPLEMENTATION PLAN

### Phase 1: Config + Fetcher

Add the config constants and the Close+Volume history fetcher the check needs.

**Tasks:**
- Add `MATT_DAMON_*` constants to `config.py`.
- Write `_fetch_price_volume_history(ticker, period="1y")` in the new
  `matt_damon_price_volitility_volume_check.py` module.

### Phase 2: Core ROC + State Computation

**Tasks:**
- Implement price ROC, volatility-of-returns ROC, and smoothed-volume ROC as
  pure functions operating on a `pd.DataFrame`/`pd.Series`.
- Implement the descriptive alignment-label classifier (per-window).
- Implement `check(data) -> CheckResult`.

### Phase 3: Engine Wiring

**Tasks:**
- Add the check to `engine.py`'s unconditional results list.
- Manually verify it shows up via both `find --ticker X` and a Monitor dry run.

### Phase 4: Backtest Script

**Tasks:**
- Write the confluence-state classifier as a reusable series function shared
  between the live check and the backtest (single source of truth — see Gotcha
  below).
- Write `matt_damon_price_volitility_volume_check_backtest.py`, importing `gold_backtest.py`'s three
  generic functions.
- Run it against real data, interpret the result, append the finding to the
  handoff doc.

### Phase 5: Testing & Validation

**Tasks:**
- Unit tests for the check module (mirroring
  `test_checks_technical_levels.py`).
- Unit tests for the backtest's classifier/aggregation logic (mirroring
  `test_gold_backtest.py`).
- Full test suite run, zero regressions.

---

## STEP-BY-STEP TASKS

IMPORTANT: Execute every task in order, top to bottom. Each task is atomic and
independently testable.

### 1. UPDATE `investments/my-trader/mytrader/config.py`

- **IMPLEMENT**: Add a new constants section (append after the `GOLD_BACKTEST_*`
  block, e.g. after line 499) with a dated banner comment matching the existing
  style:
  ```python
  # Added 2026-09-25 -- Matt Damon Price/Volatility/Volume Check check, see
  # .agent/plans/roc-confluence-check.md and investments/roc-triple-signal-
  # handoff.md. Windows/lookbacks are this plan's own methodology choices --
  # confirmed with Shaun (10-day short / 25-day long), best-guess defaults on
  # the rest, ship and revisit per the backtest step.

  MATT_DAMON_SHORT_WINDOW_DAYS = 10   # trading days -- "is this
                                       # accelerating right now".
  MATT_DAMON_LONG_WINDOW_DAYS = 25    # trading days -- "is this an
                                       # established move".
  MATT_DAMON_VOLATILITY_WINDOW_DAYS = 20  # rolling std-dev-of-returns
                                       # window that itself gets ROC'd -- 20 is
                                       # a textbook default (same window
                                       # Bollinger Bands and GOLD_TA_BOLLINGER_
                                       # PERIOD_DAYS use), cheap warm-up (21
                                       # closes to first reading).
  MATT_DAMON_VOLUME_SMOOTHING_DAYS = 10  # rolling mean of daily volume
                                       # before computing its ROC -- avoids a
                                       # single outlier-volume day (news,
                                       # index rebalance, options expiry)
                                       # dominating the reading, matches the
                                       # long ROC window for consistency.
  MATT_DAMON_HISTORY_PERIOD = "1y"   # yfinance period string for the live
                                       # check -- comfortably covers the
                                       # longest warm-up need (long window 25 +
                                       # volatility window 20 + volume
                                       # smoothing 10 = 55 trading days, well
                                       # under a year's ~252).
  MATT_DAMON_BACKTEST_HISTORY_PERIOD = "2y"  # longer pull for the
                                       # one-off backtest script only -- more
                                       # sample per ticker, still cheap.
  MATT_DAMON_BACKTEST_FORWARD_HORIZON_TRADING_DAYS = 10  # confirmed with
                                       # Shaun -- compare mean 10-trading-day-
                                       # forward return following an "aligned"
                                       # reading vs. baseline vs. price-ROC-
                                       # alone, over the same tickers/history.
  ```
- **PATTERN**: `config.py` lines 429-499 (banner comment + constant + inline
  rationale comment style).
- **VALIDATE**:
  `uv run --directory investments/my-trader python -c "from mytrader import config; print(config.MATT_DAMON_SHORT_WINDOW_DAYS, config.MATT_DAMON_LONG_WINDOW_DAYS)"`

### 2. CREATE `investments/my-trader/mytrader/checks/matt_damon_price_volitility_volume_check.py`

- **IMPLEMENT**: Module docstring first, stating explicitly (mirroring
  `price_action.py` lines 9-13 / `technical_levels.py` lines 9-14): this check
  is deliberately `verdict="info"` only; the alignment label is a descriptive
  convenience, not a validated predictive claim; see
  `matt_damon_price_volitility_volume_check_backtest.py` and `.agent/plans/roc-confluence-check.md` for
  the empirical validation step and its result.

  Then:
  ```python
  def _fetch_price_volume_history(ticker: str, period: str = config.MATT_DAMON_HISTORY_PERIOD) -> pd.DataFrame | None:
      """Close+Volume history -- unlike goat/price_history.py and
      technical_levels._fetch_close_series, keeps the Volume column (both
      those functions fetch the full yfinance frame and discard everything but
      Close; Volume was never a new API surface, just thrown away)."""
      import yfinance as yf
      for candidate in (tickers.normalize(ticker), tickers.asx_variant(ticker)):
          try:
              hist = yf.Ticker(candidate).history(period=period, auto_adjust=True)
          except Exception:
              continue
          if hist.empty:
              continue
          frame = hist[["Close", "Volume"]].dropna(subset=["Close"])
          if len(frame) < 2:
              continue
          return frame
      return None


  def _roc(series: pd.Series, window: int) -> float | None:
      """Standard ROC: (value_today - value_N_ago) / value_N_ago * 100. None if
      not enough history or the N-ago value is zero/NaN."""
      if len(series) <= window:
          return None
      then = series.iloc[-window - 1]
      now = series.iloc[-1]
      if then in (0, None) or pd.isna(then) or pd.isna(now):
          return None
      return float((now - then) / then * 100)


  def _volatility_series(close: pd.Series, window: int = config.MATT_DAMON_VOLATILITY_WINDOW_DAYS) -> pd.Series:
      """Rolling std-dev of daily pct returns -- the ROC of THIS series is the
      volatility-expansion/contraction read. Recommended default over ATR/BBW
      per the handoff's lookback-window-trap discussion: close-only (no OHLC
      frame needed), and doesn't need a percentile-vs-own-history
      normalization (the BBW-percentile shape that already failed once in
      goat-heartbeat-quiet-redesign)."""
      return close.pct_change().rolling(window).std() * 100


  def _smoothed_volume_series(volume: pd.Series, window: int = config.MATT_DAMON_VOLUME_SMOOTHING_DAYS) -> pd.Series:
      return volume.rolling(window).mean()


  def _alignment_label(price_roc: float | None, vol_roc: float | None, volume_roc: float | None) -> str:
      """Descriptive-only label -- NOT a validated predictive claim (see module
      docstring). 'aligned_bullish': price+volume both accelerating up while
      volatility contracts. 'aligned_bearish': the mirror. Anything else:
      'no_read' -- three numbers agreeing on nothing in particular."""
      if price_roc is None or vol_roc is None or volume_roc is None:
          return "unknown"
      if price_roc > 0 and volume_roc > 0 and vol_roc < 0:
          return "aligned_bullish"
      if price_roc < 0 and volume_roc < 0 and vol_roc < 0:
          return "aligned_bearish"
      return "no_read"


  def check(data) -> CheckResult:
      if data is None:
          return CheckResult(name="matt_damon_price_volitility_volume_check", verdict="unknown", detail="No market data available")
      frame = _fetch_price_volume_history(data.ticker)
      min_needed = max(config.MATT_DAMON_LONG_WINDOW_DAYS, config.MATT_DAMON_VOLATILITY_WINDOW_DAYS, config.MATT_DAMON_VOLUME_SMOOTHING_DAYS) + 1
      if frame is None or len(frame) < min_needed:
          return CheckResult(name="matt_damon_price_volitility_volume_check", verdict="unknown", detail="Not enough price/volume history for ROC confluence")

      close = frame["Close"]
      vol_series = _volatility_series(close)
      volume_smoothed = _smoothed_volume_series(frame["Volume"])

      data_out: dict = {}
      parts = []
      for label, window in (("short", config.MATT_DAMON_SHORT_WINDOW_DAYS), ("long", config.MATT_DAMON_LONG_WINDOW_DAYS)):
          price_roc = _roc(close, window)
          vol_roc = _roc(vol_series.dropna(), window)
          volume_roc = _roc(volume_smoothed.dropna(), window)
          alignment = _alignment_label(price_roc, vol_roc, volume_roc)
          data_out[f"price_roc_{label}"] = price_roc
          data_out[f"volatility_roc_{label}"] = vol_roc
          data_out[f"volume_roc_{label}"] = volume_roc
          data_out[f"alignment_{label}"] = alignment
          def fmt(v):
              return f"{v:+.1f}%" if v is not None else "n/a"
          parts.append(
              f"{window}d: price {fmt(price_roc)} / volatility {fmt(vol_roc)} / "
              f"volume {fmt(volume_roc)} ({alignment})"
          )

      return CheckResult(name="matt_damon_price_volitility_volume_check", verdict="info", detail="; ".join(parts), data=data_out)
  ```
- **IMPORTS**: `from __future__ import annotations`, `pandas as pd` (lazy
  `yfinance` import inside the fetch function, matching every other fetcher),
  `from .. import tickers, config`, `from . import CheckResult`.
- **PATTERN**: `checks/technical_levels.py` end to end.
- **GOTCHA**: `_roc`'s `series.iloc[-window - 1]` indexing assumes `series` is
  already `.dropna()`'d and index-ordered oldest-to-newest (true of
  `close`/`vol_series.dropna()`/`volume_smoothed.dropna()` as constructed
  above) — don't call `_roc` on a raw un-dropna'd rolling series or the
  "N rows back" offset will be wrong.
- **GOTCHA**: `min_needed` must add `+1` because `_roc(series, window)` needs
  `window + 1` rows (today plus N days ago), not just `window` rows — the same
  off-by-one `technical_levels.py` avoids via its own `len(closes) < window`
  check happening to be for a *mean*, not a fixed-offset lookup; don't copy
  that exact comparison without the `+1` adjustment here.
- **VALIDATE**:
  `uv run --directory investments/my-trader python -c "from mytrader.find import lookup_ticker; from scripts.db import get_connection; from mytrader.config import DB_PATH; c = get_connection(DB_PATH); print(lookup_ticker('AAPL', c))"`
  — inspect that a `matt_damon_price_volitility_volume_check` entry appears in the printed checks list.
  (Confirm exact DB-connection helper name/import path in `find.py`/`main.py`
  before running — `main.py`'s `_open_conn()` is the one Find's own CLI path
  uses; reuse whatever it imports rather than assuming.)

### 3. UPDATE `investments/my-trader/mytrader/engine.py`

- **IMPLEMENT**: Add `matt_damon_price_volitility_volume_check` to the import block (alphabetical,
  matching the existing `from .checks import (...)` ordering at lines 11-28)
  and one line in the unconditional results list:
  ```python
  results = [
      *other_checks,
      opportunity.check(data, other_checks, briefs_score, recent_return_3mo),
      price_action.check(recent_return_1mo, recent_return_3mo),
      crash_resilience.check(data),
      technical_levels.check(data),
      matt_damon_price_volitility_volume_check.check(data),
  ]
  ```
- **PATTERN**: `engine.py` lines 169-175 — append alongside
  `technical_levels.check(data)`, same `data` argument (the `TickerData`
  object), same unconditional (non-`include_*`-gated) placement.
- **GOTCHA**: Do NOT add an `include_matt_damon_price_volitility_volume_check` opt-in flag — this check
  is cheap pure-math (no LLM/WebSearch call), same cost profile as
  `price_action`/`technical_levels`, which is exactly why it belongs
  unconditional. Adding a flag here would be over-engineering relative to the
  actual cost, and would also silently break "should also assess a stock I
  manually give you" if `find.py` isn't updated to pass it — the unconditional
  placement avoids that whole class of bug.
- **VALIDATE**: `uv run --directory investments/my-trader python -m pytest mytrader/tests/test_engine.py -q`

### 4. CREATE `investments/my-trader/mytrader/tests/test_checks_matt_damon_price_volitility_volume_check.py`

- **IMPLEMENT**: Mirror `test_checks_technical_levels.py`'s structure exactly:
  - `test_no_data_returns_unknown` — `check(None).verdict == "unknown"`.
  - `test_returns_unknown_when_fetch_fails` — monkeypatch
    `_fetch_price_volume_history` to return `None`.
  - `test_returns_unknown_when_too_little_history` — monkeypatch to return a
    short synthetic `pd.DataFrame({"Close": [...], "Volume": [...]})`.
  - `test_reports_aligned_bullish_when_price_and_volume_rise_and_volatility_falls`
    — construct a synthetic ~60-row `DataFrame` with a clean accelerating-price
    /accelerating-volume/flattening-volatility shape (e.g. price rising at an
    increasing rate, volume rising, then a low-noise tail so
    `_volatility_series` trends down); assert `verdict == "info"`,
    `data["alignment_short"] == "aligned_bullish"`, and both window labels
    appear in `detail`.
  - `test_reports_no_read_when_signals_disagree` — construct a `DataFrame`
    where price rises but volume falls; assert `alignment_short == "no_read"`.
  - `test_asx_fallback` — mirror whatever ASX-fallback test pattern
    `test_checks_technical_levels.py`'s peers use elsewhere in this test
    directory (check `test_crash_windows.py`/`test_return_data.py` for the
    exact monkeypatch-two-candidates pattern, since `technical_levels.py`'s own
    test file doesn't happen to test the `.AX` branch directly — confirm this
    during implementation rather than assuming).
- **PATTERN**: `mytrader/tests/test_checks_technical_levels.py` in full.
- **VALIDATE**: `uv run --directory investments/my-trader python -m pytest mytrader/tests/test_checks_matt_damon_price_volitility_volume_check.py -v`

### 5. CREATE `investments/my-trader/mytrader/matt_damon_price_volitility_volume_check_backtest.py`

- **IMPLEMENT**: A one-off validation script, not a scheduled/cached job (no DB
  persistence table — unlike `gold_backtest.py`'s `get_cached_or_refresh`, this
  doesn't need to be re-run automatically since the live check's verdict never
  depends on its outcome). Structure:
  ```python
  """One-off backtest: does the Matt Damon Price/Volatility/Volume Check alignment reading (see
  checks/matt_damon_price_volitility_volume_check.py) correlate with subsequent price direction any
  better than price ROC alone, or than an unconditioned baseline? Confirmed
  scope with Shaun 2026-09-25: holdings + "discussed" watchlist tickers, ~2yr
  history each, 10-trading-day forward return, state-conditioned methodology
  reusing gold_backtest.py's generic forward-return/baseline/state-conditioning
  functions (NOT investments/backtest/'s unrelated Streamlit walk-forward
  trading-strategy backtester -- that tool optimizes RSI entry/exit parameters
  per-fold, a different question from "does this state predict this return").

  Run manually, read the printed comparison, then hand-write the conclusion
  into investments/roc-triple-signal-handoff.md's Validation section -- this
  script does not persist or auto-decide anything.
  """
  from __future__ import annotations

  from datetime import date, timedelta

  import pandas as pd

  from . import config, db, tickers
  from .checks.matt_damon_price_volitility_volume_check import _alignment_label, _roc, _smoothed_volume_series, _volatility_series
  from .gold_backtest import compute_baseline_trading_days, compute_forward_return_trading_days, compute_state_conditioned_stats


  def _fetch_backtest_history(ticker: str) -> pd.DataFrame | None:
      import yfinance as yf
      for candidate in (tickers.normalize(ticker), tickers.asx_variant(ticker)):
          try:
              hist = yf.Ticker(candidate).history(period=config.MATT_DAMON_BACKTEST_HISTORY_PERIOD, auto_adjust=True)
          except Exception:
              continue
          if hist.empty:
              continue
          frame = hist[["Close", "Volume"]].dropna(subset=["Close"])
          if getattr(frame.index, "tz", None) is not None:
              frame.index = frame.index.tz_localize(None)
          if len(frame) < config.MATT_DAMON_LONG_WINDOW_DAYS * 3:
              continue
          return frame
      return None


  def _confluence_state_series(frame: pd.DataFrame, window: int) -> pd.Series:
      """Day-by-day alignment label, short-window only (the window the
      backtest's forward horizon of 10 trading days is scoped against) --
      vectorized-by-loop over positions since _roc needs a fixed lookback per
      row; acceptable cost at ~2yr/ticker, not a hot path."""
      close = frame["Close"]
      vol_series = _volatility_series(close).dropna()
      volume_smoothed = _smoothed_volume_series(frame["Volume"]).dropna()
      labels = []
      for i in range(len(close)):
          price_roc = _roc(close.iloc[: i + 1], window)
          vs = vol_series[vol_series.index <= close.index[i]]
          vol_roc = _roc(vs, window) if len(vs) else None
          vols = volume_smoothed[volume_smoothed.index <= close.index[i]]
          volume_roc = _roc(vols, window) if len(vols) else None
          labels.append(_alignment_label(price_roc, vol_roc, volume_roc))
      return pd.Series(labels, index=close.index)


  def _price_roc_only_state_series(close: pd.Series, window: int) -> pd.Series:
      """Comparison classifier: price ROC direction alone, same window --
      the thing Shaun's confluence idea needs to beat."""
      labels = []
      for i in range(len(close)):
          r = _roc(close.iloc[: i + 1], window)
          labels.append("unknown" if r is None else ("up" if r > 0 else "down" if r < 0 else "flat"))
      return pd.Series(labels, index=close.index)


  def run_backtest(conn) -> dict:
      tickers_to_check = sorted({r["ticker"] for r in db.get_all_holdings(conn)} | {
          r["ticker"] for r in db.get_all_watchlist(conn) if r["status"] == "discussed"
      })
      n_days = config.MATT_DAMON_BACKTEST_FORWARD_HORIZON_TRADING_DAYS
      window = config.MATT_DAMON_SHORT_WINDOW_DAYS

      confluence_by_state: dict[str, list[float]] = {}
      price_only_by_state: dict[str, list[float]] = {}
      baselines: list[dict] = []

      for ticker in tickers_to_check:
          frame = _fetch_backtest_history(ticker)
          if frame is None:
              print(f"[matt_damon_price_volitility_volume_check_backtest] skipping {ticker} -- insufficient history")
              continue
          close = frame["Close"]
          window_start = close.index[0].date()
          window_end = close.index[-1].date()

          confluence_state = _confluence_state_series(frame, window)
          for label, stats in compute_state_conditioned_stats(confluence_state, close, n_days, window_start, window_end).items():
              if label in ("unknown", "no_read"):
                  continue
              confluence_by_state.setdefault(label, []).extend(
                  [r for r in _extract_returns(confluence_state, close, n_days, window_start, window_end, label)]
              )

          price_only_state = _price_roc_only_state_series(close, window)
          for label, stats in compute_state_conditioned_stats(price_only_state, close, n_days, window_start, window_end).items():
              if label in ("unknown", "flat"):
                  continue
              price_only_by_state.setdefault(label, []).extend(
                  [r for r in _extract_returns(price_only_state, close, n_days, window_start, window_end, label)]
              )

          baselines.append(compute_baseline_trading_days(close, n_days, window_start, window_end))

      return {
          "confluence": {k: _pool_stats(v) for k, v in confluence_by_state.items()},
          "price_only": {k: _pool_stats(v) for k, v in price_only_by_state.items()},
          "baseline": _pool_stats([r for b in baselines for r in b.get("_raw", [])]) if baselines else None,
          "tickers_checked": len(tickers_to_check),
      }
  ```
  Notes on the sketch above (finalize exact helper shapes during
  implementation — this is deliberately left slightly open rather than
  pretending a false precision):
  - `compute_state_conditioned_stats` already returns `_distribution_stats`
    dicts (n/mean/median/win_rate/best/worst) per state — pooling raw returns
    *across tickers* before computing final stats (rather than averaging
    per-ticker stats dicts) needs either (a) a small local re-implementation of
    `_distribution_stats`-equivalent pooling, or (b) calling
    `compute_state_conditioned_stats` once per ticker and then combining
    the `n`/`mean` weighted by `n` per state across tickers. Prefer (a) — pool
    raw per-occurrence returns first, then compute stats once — cleaner and
    avoids weighted-mean-of-means bugs. This means writing a small
    `_extract_returns`-style helper that returns the raw list (not just the
    summary dict) per state; check whether `compute_state_conditioned_stats`
    can be trivially adapted/duplicated at the small scale needed here, or
    whether pulling the raw per-occurrence return list requires a thin local
    variant of that function returning `dict[str, list[float]]` instead of
    `dict[str, dict]`. Given `compute_state_conditioned_stats`'s body is only
    ~12 lines (`gold_backtest.py` lines 271-290), a local
    `_state_conditioned_raw_returns` variant returning the pre-`_distribution_
    stats` `by_state: dict[str, list[float]]` dict directly (i.e. everything
    up to but not including the final dict-comprehension line) is the
    cleanest fix — write it in `matt_damon_price_volitility_volume_check_backtest.py`, not
    `gold_backtest.py` (don't modify the gold module for this).
  - `compute_baseline_trading_days` similarly returns a summary dict, not raw
    returns — same treatment needed if baseline pooling across tickers is
    wanted; simplest fix is a small local
    `_baseline_raw_returns(close, n_days, window_start, window_end) ->
    list[float]` mirroring lines 192-200 minus the final `_distribution_stats`
    call.
  - This is exactly the kind of "confirm during build, don't guess" spot the
    source handoff repeatedly flags — resolve it by writing the smallest local
    helper that gets raw per-occurrence returns out, pool across all tickers,
    then compute one final stats dict per state/classifier. Do not silently
    approximate by averaging pre-computed per-ticker means.
  - Add a `main()` + `if __name__ == "__main__":` entry (argparse-free is fine,
    mirror `gold_backtest.py` lines 444-461's shape minus the DB-persistence
    call) that opens a connection via whatever `main.py`'s `_open_conn()`
    imports, calls `run_backtest(conn)`, and prints a comparison table:
    confluence-state stats vs. price-only-state stats vs. pooled baseline,
    for the confirmed 10-trading-day horizon.
- **IMPORTS**: `from . import config, db, tickers`, `from .checks.matt_damon_price_volitility_volume_check
  import _alignment_label, _roc, _smoothed_volume_series, _volatility_series`,
  `from .gold_backtest import compute_baseline_trading_days,
  compute_forward_return_trading_days, compute_state_conditioned_stats` (or the
  small local raw-returns variants described above).
- **GOTCHA**: `investments/backtest/` (the Streamlit walk-forward RSI
  backtester) is NOT the thing to reuse here — confirmed by reading
  `investments/backtest/backtester.py` and `app.py` in full: it optimizes
  entry/exit RSI thresholds per walk-forward fold for a trading *strategy*,
  a different question from "does today's state predict tomorrow's return."
  `gold_backtest.py`'s state-conditioned functions are the right reuse target.
- **GOTCHA**: the per-day loop in `_confluence_state_series`/
  `_price_roc_only_state_series` recomputes `_roc` on a growing slice
  (`close.iloc[:i+1]`) for every row — O(n) per row, O(n²) total. At ~2yr
  (~500 rows) per ticker × ~dozens of tickers this is still fast in wall-clock
  terms for a one-off manual script, but do not copy this pattern into the
  live `check()` function (which correctly only computes the *last* value, not
  a full historical series) or into anything that runs on a schedule.
- **VALIDATE**:
  `uv run --directory investments/my-trader python -m mytrader.matt_damon_price_volitility_volume_check_backtest`
  — should print a comparison table and not raise. Expect this to legitimately
  fail informatively (e.g. "no tickers with enough history") if run against an
  empty/test DB — that's fine, it's a manual research script, not something
  CI needs to pass against real market data.

### 6. CREATE `investments/my-trader/mytrader/tests/test_matt_damon_price_volitility_volume_check_backtest.py`

- **IMPLEMENT**: Test the pure classifier/pooling functions against small
  synthetic `pd.DataFrame`s (5-20 rows), NOT the yfinance fetch. Mirror
  `test_gold_backtest.py`'s synthetic-series approach:
  - `test_confluence_state_series_labels_clear_bullish_run` — construct a
    DataFrame with an obvious accelerating-price/rising-volume/falling-
    volatility shape over enough rows to clear the window + volatility +
    volume warm-up, assert the tail of the resulting state series is
    `"aligned_bullish"`.
  - `test_price_roc_only_state_series_labels_up_down` — simple monotonic
    rising/falling synthetic series, assert `"up"`/`"down"` labels.
  - `test_raw_returns_helper_pools_correctly` — whatever the chosen local
    raw-returns helper is named (task 5's open item), assert it returns a
    `dict[str, list[float]]` with the right per-occurrence values for a small
    hand-computed example.
- **PATTERN**: `mytrader/tests/test_gold_backtest.py` lines 1-50 (synthetic
  `pd.date_range`-indexed series, `monkeypatch` only where a config constant
  needs shrinking for a small fixture).
- **VALIDATE**: `uv run --directory investments/my-trader python -m pytest mytrader/tests/test_matt_damon_price_volitility_volume_check_backtest.py -v`

### 7. RUN the backtest against real data and interpret it

- **IMPLEMENT**: `uv run --directory investments/my-trader python -m
  mytrader.matt_damon_price_volitility_volume_check_backtest` against the real VPS-synced
  `investments.db` (see `CLAUDE.md`'s note that `investments.db` is VPS-only —
  run this via `scripts/invoke_investments.ps1 -Package my-trader -Command
  "python -m mytrader.matt_damon_price_volitility_volume_check_backtest"` if the package's other
  interactive commands are VPS-routed the same way `TOOLS.md`'s "Manual /
  on-demand only" section describes; confirm the exact invocation pattern
  against that section before running, since this plan was drafted from
  `investments/roc-triple-signal-handoff.md`'s codebase snapshot, not a live
  re-check of `TOOLS.md`'s full "Manual" table).
- **VALIDATE**: Read the printed comparison. Per Shaun's confirmed bar: does
  the confluence-aligned state's mean 10-day-forward return clearly beat both
  the price-ROC-only state and the pooled baseline, on a sample size large
  enough to mean something (report the `n` alongside any conclusion — a
  favorable mean off `n=4` occurrences is not a finding)? Write whichever
  outcome up.

### 8. UPDATE `investments/roc-triple-signal-handoff.md`

- **IMPLEMENT**: Append a new `## Backtest Result (YYYY-MM-DD)` section above
  the `## Sources consulted` section with: sample size (tickers checked,
  total occurrences per state), the three comparison numbers (confluence-
  aligned mean/win-rate, price-ROC-only mean/win-rate, baseline mean/win-rate),
  and a one-line verdict: either "no change — stays `verdict=\"info\"`,
  no live gate" (if inconclusive/negative, per the handoff's own explicit
  fallback) or a concrete next-step recommendation (if the backtest shows a
  real edge, e.g. "revisit thresholds for a `verdict=\"interesting\"` gate,
  new follow-up plan needed — do not add a gate in this same plan without a
  fresh `/plan-feature` pass," matching the handoff's own "only if the
  backtest shows a real edge" build-order discipline).
- **VALIDATE**: Read the file back; confirm the new section renders as valid
  Markdown and doesn't disturb the existing content above it.

---

## TESTING STRATEGY

### Unit Tests

- `checks/matt_damon_price_volitility_volume_check.py`: no-data/fetch-failure/insufficient-history →
  `unknown`; full-history happy path for both `aligned_bullish` and `no_read`;
  `data` dict has all 8 expected keys (`price_roc_short/long`,
  `volatility_roc_short/long`, `volume_roc_short/long`, `alignment_short/long`).
  All via `monkeypatch` on `_fetch_price_volume_history`, no real network calls
  — matches every other check's test file in this codebase.
- `matt_damon_price_volitility_volume_check_backtest.py`: state-classifier functions against small
  synthetic series; the raw-returns pooling helper against a hand-computed
  example. No real yfinance calls, no real DB — matches `test_gold_backtest.py`.

### Integration Tests

- `test_engine.py` (existing file — extend if it asserts on the full check-name
  list, otherwise no change needed beyond confirming the existing test suite
  still passes with the new check appended) confirms `matt_damon_price_volitility_volume_check` appears
  in `run_assessment(...)["checks"]`.

### Edge Cases

- Ticker with clearly accelerating price+volume+contracting volatility (both
  windows) — covered by the "aligned_bullish" unit test.
- Ticker with insufficient history for the long window/volatility
  window/volume smoothing warm-up — `verdict="unknown"`, no crash.
- Ticker where Volume is present but all zero/NaN for the whole window (some
  ETFs/OTC names can have gappy volume) — `_roc` on an all-zero/NaN
  `volume_smoothed` series must return `None`, not raise or divide by zero;
  add an explicit unit test for this.
- ASX ticker routing through the `.AX` fallback — confirm the exact test
  pattern used elsewhere in this test directory during implementation (see
  Task 4).
- Backtest script run against a ticker with real Volume=0 days scattered
  through history (illiquid ASX names) — `.dropna()` after
  `_smoothed_volume_series` should already exclude the resulting NaN rows from
  `_roc`'s lookback window; confirm this doesn't silently shift window
  alignment versus the price/volatility series (all three should be reindexed
  consistently — if this bites, align all three series to `close.index` at the
  top of `check()`/`_confluence_state_series` rather than letting each one
  independently drop rows).

---

## VALIDATION COMMANDS

### Level 1: Syntax & Style

No project-wide linter/formatter config found for `investments/my-trader` in
this pass — match the surrounding file's existing style (this codebase does
not appear to run `ruff`/`black` in CI for this package; confirm during
implementation by checking for a `[tool.ruff]`/`[tool.black]` section in
`investments/my-trader/pyproject.toml` before assuming none exists).

### Level 2: Unit Tests

```powershell
uv run --directory investments/my-trader python -m pytest mytrader/tests/test_checks_matt_damon_price_volitility_volume_check.py mytrader/tests/test_matt_damon_price_volitility_volume_check_backtest.py -v
```

### Level 3: Full Suite (zero regressions)

```powershell
uv run --directory investments/my-trader python -m pytest -q
```

### Level 4: Manual Validation

```powershell
scripts\invoke_investments.ps1 -Package my-trader -Command "find --ticker TICKER"
```
Expected: a new `matt_damon_price_volitility_volume_check` line in the output showing both windows'
price/volatility/volume ROC and alignment label, `verdict="info"`.

Then run a Monitor dry run (or wait for the next 7:30am Sydney scheduled run)
and confirm `investments/my-trader/my-trader-report.md` shows a `matt_damon_price_volitility_volume_check`
line per holding/watchlist row, same generic check-list rendering as
`technical_levels`.

### Level 5: Backtest (research validation, not CI)

```powershell
uv run --directory investments/my-trader python -m mytrader.matt_damon_price_volitility_volume_check_backtest
```
(Or via `scripts/invoke_investments.ps1` if that's the correct VPS-DB-connected
invocation — confirm per Task 7.) Read the output, write the conclusion into
`investments/roc-triple-signal-handoff.md` (Task 8).

---

## ACCEPTANCE CRITERIA

- [ ] `matt_damon_price_volitility_volume_check.check()` returns `verdict="unknown"` for no-data/
      insufficient-history, `verdict="info"` otherwise — never `"flag"`/
      `"interesting"`.
- [ ] `matt_damon_price_volitility_volume_check` appears automatically in both `find --ticker X` output
      and Monitor's daily report, with no changes needed to `find.py`,
      `main.py`, or `monitor.py`.
- [ ] The check reports both short (10d) and long (25d) window readings for
      all three ROC dimensions plus an alignment label per window.
- [ ] The backtest script runs against real holdings + discussed-watchlist
      tickers over ~2yr history, compares confluence-state vs. price-ROC-only
      vs. baseline forward 10-trading-day returns, and its result is written
      into `investments/roc-triple-signal-handoff.md`.
- [ ] No live gate/alert/watchlist-add is added regardless of backtest outcome
      — that is explicitly out of scope for this plan (handoff's "Explicitly
      deferred" section).
- [ ] All new/existing tests pass; full `investments/my-trader` suite has zero
      regressions.
- [ ] No new external dependency added.

---

## COMPLETION CHECKLIST

- [ ] All 8 tasks completed in order.
- [ ] Each task's validation command passed immediately after that task.
- [ ] Full test suite passes.
- [ ] Manual `find --ticker` check confirms the new check line renders
      correctly.
- [ ] Backtest run, result interpreted honestly (including "inconclusive" as a
      valid, expected outcome), and written into the handoff doc.
- [ ] Acceptance criteria all met.

---

## NOTES

- **Name**: confirmed "Matt Damon Price/Volatility/Volume Check" (module
  `matt_damon_price_volitility_volume_check.py`, check name
  `"matt_damon_price_volitility_volume_check"`). Note the spelling
  "volitility" (not "volatility") is intentional in the identifier/filename —
  matches exactly what Shaun asked for; don't "fix" it during implementation.
  If a different name is ever preferred later, it's a pure find-and-replace
  across this plan + code (module filename, `CheckResult.name`, config
  constant prefix, docstrings) —
  no logic depends on the name itself.
- **Why not gate on the backtest result within this same plan**: per the
  handoff's explicit build order and Shaun's confirmed backtest bar, the
  verdict logic is an *output* of the backtest, not a decision to pre-bake.
  If the backtest shows a real edge, the natural next step is a fresh, short
  follow-up plan (thresholds, `verdict="interesting"` gate design, whether it
  participates in `opportunity.py`'s risk-flag gate the way
  `news_events`/`insider_selling`/`earnings_deterioration` do) — deliberately
  not pre-designed here, matching the handoff's own "decide on thresholds from
  evidence, not from a plausible-sounding a-priori rule."
- **Why `investments/backtest/` is not reused**: confirmed by reading both its
  files in full — it's a generic Streamlit RSI walk-forward *trading-strategy*
  backtester (optimizes entry/exit thresholds per fold), a different
  methodology from the state-conditioned "does today's classification predict
  tomorrow's return" question this plan needs. `gold_backtest.py` already has
  exactly the right reusable generic functions for that.
- **Two open implementation details deliberately left for build-time, not
  guessed here** (flagged inline in Task 5 rather than pretending false
  precision): (1) the exact shape of the raw-per-occurrence-returns pooling
  helper (small local variant of `gold_backtest.py`'s private
  `_distribution_stats`-adjacent logic), and (2) the exact ASX-fallback test
  pattern to mirror in Task 4 (confirmed to exist somewhere in
  `test_crash_windows.py`/`test_return_data.py`, exact assertion shape not
  re-derived in this planning pass).

## Confidence Score

**7/10** for one-pass implementation success. The check module (Tasks 1-4) is
very low risk — it's a near-mechanical mirror of `technical_levels.py` with a
well-precedented test pattern. The backtest script (Tasks 5-6) is the riskier
half: the exact shape of pooling raw per-occurrence returns out of
`gold_backtest.py`'s summary-returning functions is deliberately left as a
build-time decision rather than fully specified pseudocode, since guessing
wrong there would be worse than flagging it honestly. An implementer should
budget real thinking time for Task 5, not treat it as copy-paste.
