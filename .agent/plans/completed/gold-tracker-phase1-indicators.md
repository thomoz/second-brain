# Feature: Gold Tracker — Phase 1 Macro Indicators

The following plan should be complete, but validate documentation and codebase
patterns and task sanity before implementing. Pay special attention to naming of
existing config constants, check functions, and imports — mirror the existing
macro-indicator pattern exactly, don't invent a new shape for it.

Source handoff: `.agent/plans/gold-tracker-handoff.md` (design + all 5 open questions
resolved 2026-08-07 — read its "Decisions" section before starting, it supersedes the
original "Open Questions" list below it in that file).

## Feature Description

Add 5 new portfolio-wide macro indicators to my-trader's existing Monitor macro-check
system, giving Shaun daily visibility into the macro drivers that actually move gold
(real yields, USD strength) plus the gold price itself (trend vs its 200-day moving
average, gold/silver ratio) and a general risk-sentiment gauge (VIX) — extending the
same `macro_indicators.py` pattern already used for MOVE index, housing
affordability, consumer sentiment, recession signal, inflation expectations, credit
spreads, and AU/US/UK CPI (9 existing checks → 14 after this feature).

Context: Shaun holds gold via PMGOLD (Perth Mint Gold Structured Product, ASX-listed,
bucket 3a, ~69 units — `investments/my-trader/holdings.md`) and recently added to the
position. This is Phase 1 only — indicator plumbing. The backtest/signal-validation
module referenced in the handoff is explicitly **out of scope** for this plan (see
NOTES).

## User Story

As Shaun (a multi-business founder holding physical/structured gold exposure via
PMGOLD)
I want Monitor's daily macro-indicator report to include the specific drivers that
move gold — real yields, USD strength, the gold price itself vs its long-run trend,
the gold/silver ratio, and general market stress (VIX)
So that I get an early, unopinionated read on my gold position's macro backdrop
alongside the portfolio-wide checks I already see every day, without having to
piece it together manually.

## Problem Statement

Monitor's existing macro indicators (recession risk, inflation, credit spreads, CPI)
say nothing about gold specifically. Shaun has no daily visibility into the factors
that most directly move his PMGOLD position's macro backdrop.

## Solution Statement

Add 5 new check functions to the existing `mytrader/macro_indicators.py` module,
following its established pattern exactly (FRED-backed checks via
`scripts.macro.fred_observation_on`/`fred_value_on`, yfinance-backed checks via a
private latest-close/history helper, `config.py`-sourced thresholds with cited
rationale, graceful `"unknown"` degradation, wired into `run_all()`). No new module,
no changes to `monitor.py`, `db.py`, or `main.py` — the existing
`_reconcile_alerts`/`upsert_macro_snapshot`/`render_report` machinery in `monitor.py`
already iterates whatever `macro_indicators.run_all()` returns generically, so these
5 new checks plug in with zero changes outside `macro_indicators.py` and `config.py`.

## Feature Metadata

**Feature Type**: Enhancement (extends an existing, well-established check pattern)
**Estimated Complexity**: Medium — no new architecture, but one check (`gold_trend`)
needs a genuinely new technique (rolling moving averages + cross detection) not yet
used anywhere in `macro_indicators.py`.
**Primary Systems Affected**: `investments/my-trader/mytrader/macro_indicators.py`,
`investments/my-trader/mytrader/config.py`
**Dependencies**: None new — reuses `yfinance` (already a dependency) and the
existing FRED helper (`briefs-finance`'s `scripts/macro.py`, already imported by
`macro_indicators.py`). `FRED_API_KEY` must be set in the environment for the two
FRED-backed checks to return real data (same as every existing FRED check — degrades
to `"unknown"` gracefully if unset, per the module's established pattern).

---

## CONTEXT REFERENCES

### Relevant Codebase Files — READ THESE BEFORE IMPLEMENTING

- `investments/my-trader/mytrader/macro_indicators.py` (whole file, 374 lines) — the
  module you're extending. Read the module docstring (lines 1–36) for why
  `FRED_YIELD_CURVE_SERIES`/`FRED_RECESSION_PROB_SERIES` intentionally duplicate
  strings from briefs-finance's own config rather than importing them — the same
  duplication-over-cross-project-coupling reasoning applies to any new FRED series
  constants you add.
  - `check_move_index()` (lines 60–78) — the exact pattern to mirror for
    `check_vix()`: single yfinance latest-close via a private helper, one threshold,
    `"unknown"` on fetch failure.
  - `check_housing_affordability()` (lines 81–114) — two-FRED-series pattern with a
    computed ratio and an `as_of` string built from each series' own observation
    date; also shows the `data={...}` dict convention for machine-readable fields.
  - `check_recession_signal()` (lines 141–203), specifically the `today`/`prior =
    today - timedelta(days=config.STEEPENER_LOOKBACK_DAYS)` lookback-comparison
    pattern (lines 142–143, 156–159) — this is the exact shape `check_dollar_index()`
    needs (today's DXY value vs. a value ~30 days prior, not an absolute level).
  - `run_all()` (lines 362–373) — append the 5 new check calls here.
- `investments/my-trader/mytrader/config.py` — read the Phase C macro block (lines
  88–186) for the citation-comment convention (every threshold's comment states
  where the number came from and, ideally, a live confirmed reading). Also read the
  ETF block (lines 278–310, especially 283–286's "these are NOT sourced from
  principle files... best-guess default... confirmed with Shaun" framing) — this is
  the exact rhetorical pattern to use for the 2026-08-07 decision that these new
  thresholds ship as best-guess defaults, not final numbers (see NOTES).
- `investments/my-trader/mytrader/crash_windows.py`, specifically
  `_fetch_close_series()` (lines 41–61) — the long-range yfinance `.history(start=...,
  auto_adjust=True)` fetch pattern, including the tz-naive index normalization
  (`if getattr(close.index, "tz", None) is not None: close.index =
  close.index.tz_localize(None)`) needed before any string-date slicing/rolling-window
  math on the returned Series. `check_gold_trend()`'s new history-fetch helper should
  mirror this exactly (same tz-strip step is required or rolling-window date slicing
  will silently misbehave).
- `investments/my-trader/mytrader/market_data.py`,
  `fetch_fx_change_pct(base, quote="AUD", period="3mo")` (lines 86–99) — reuse this
  as-is for the PMGOLD AUD context in `check_gold_trend()`. Call as
  `market_data.fetch_fx_change_pct("USD")` to get AUD/USD 3-month % change (matches
  the exact call convention in `checks/fx.py` line 17 — see below).
- `investments/my-trader/mytrader/checks/fx.py` (whole file, 30 lines) — shows the
  exact calling convention and detail-string phrasing (`f"AUD/{currency} 3mo move:
  {change_pct:+.1f}%"`) for `fetch_fx_change_pct`. Mirror this phrasing in
  `check_gold_trend()`'s PMGOLD/AUD context.
- `investments/my-trader/mytrader/checks/price_action.py` (whole file, 30 lines) —
  the "always `verdict='info'`, never a judgment call" pattern. `check_gold_trend()`
  must follow this exactly for the golden/death-cross event specifically (see
  "Critical design constraint" in the handoff — do NOT make the cross event a
  `"flag"` or an opportunity signal).
- `investments/my-trader/mytrader/checks/opportunity.py`, docstring lines 23–37 and
  the gating logic at lines 84–90 — read this to understand the gating pattern the
  handoff references, but **do not implement it in this plan** (see NOTES — the
  "gate opportunity framing on other Phase 1 checks" idea is explicitly deferred
  until the backtest module exists to back it with real base rates).
- `investments/my-trader/mytrader/monitor.py`:
  - `_reconcile_alerts()` (lines 47–65) — **critical GOTCHA**: this only calls
    `db.insert_alert` when `check.verdict == "flag"`. Since `check_gold_trend()`
    must always return `verdict="info"` (never `"flag"`), the golden/death-cross
    event will **never** create a discrete `alert_history` row through this
    mechanism — it will only ever appear as an updating line in
    `monitor-report.md`'s "Macro Indicators" section (via `render_report`, which
    shows every macro check every run regardless of verdict — lines 178–183). This
    is intentional per the handoff's design constraint, not a bug to work around.
    `check_real_yields`, `check_dollar_index`, `check_gold_silver_ratio`, and
    `check_vix` all use normal `"flag"`/`"ok"` verdicts and go through the standard
    dedup mechanism exactly like the 9 existing checks.
  - `run_monitor()` lines 119–126 — confirms `macro_indicators.run_all()` and
    `db.upsert_macro_snapshot()` are called generically; **no changes needed here**.
  - `render_report()` lines 178–183 — confirms the "Macro Indicators" section
    renders whatever `result["macro_checks"]` contains generically; **no changes
    needed here**.
- `investments/my-trader/mytrader/db.py`, `upsert_macro_snapshot()` (lines 328–343)
  — persists all checks by `name` regardless of verdict, keyed for
  `checks/principles_fit.py`'s cached macro-regime read; **no changes needed here**,
  the 5 new checks are picked up automatically once `run_all()` returns them.
- `investments/my-trader/mytrader/tests/test_macro_indicators.py` (whole file) — the
  test pattern to mirror: `monkeypatch.setattr("mytrader.macro_indicators.<fn>",
  ...)` per fetch function, one test for `"unknown"`, one for `"flag"`, one for
  `"ok"` per check. `test_run_all_returns_nine_check_results` (lines 357–369) must be
  updated (rename + extend to 14) as part of this plan.
- `investments/my-trader/mytrader/tests/conftest.py` — confirms no new global
  `autouse` fixture is needed: `macro_indicators.run_all()` is already globally
  stubbed to `[]` for every `test_monitor.py` test via `_no_macro_or_sync_by_default`
  (that file's own fixture, not `conftest.py`), and `test_macro_indicators.py`
  exercises the real functions with per-test monkeypatching, matching the existing 9
  checks' own test style.
- `.claude/skills/my-trader/SKILL.md`, "Macro Monitoring Indicators" section (lines
  219–249) — narrative documentation of the 9 existing checks that needs a matching
  addition for the 5 new ones, same prose style (what it measures, why, source,
  threshold rationale in one flowing paragraph, not a bullet list).

### New Files to Create

None — every change lives inside the two files above (`macro_indicators.py`,
`config.py`) plus test/doc updates. Per the handoff's resolved decision #3, this is
deliberately Phase 1 only; the backtest module (a genuinely new file/module) is a
separate follow-up plan.

### Relevant Documentation

- [FRED DFII10 — 10-Year Treasury Inflation-Indexed Security, Constant Maturity](https://fred.stlouisfed.org/series/DFII10)
  - The real-yield series for `check_real_yields()`. Same access pattern as every
    existing FRED series in this module (`fred_observation_on`), no new auth/setup.
- [FRED DTWEXBGS — Nominal Broad U.S. Dollar Index](https://fred.stlouisfed.org/series/DTWEXBGS)
  - The USD-strength series for `check_dollar_index()`, resolved 2026-08-07 in favor
    of FRED over yfinance's `DX-Y.NYB` (see Decisions #5 in the handoff) — keeps this
    module's existing FRED-first pattern rather than introducing a second data
    source for one check.
- [yfinance — Ticker.history()](https://github.com/ranaroussi/yfinance) — no
  official hosted docs; behavior is exactly what `crash_windows._fetch_close_series`
  and `macro_indicators._yfinance_latest_close` already demonstrate in this
  codebase — prefer those as the reference over external yfinance docs.

### Patterns to Follow

**Config threshold citation convention** (config.py, e.g. lines 147–151, 283–310):
every new `*_FLAG_*` constant gets a comment stating (a) where the number came from
(a cited convention, a live reading, or an explicit "best-guess default") and (b) if
a live value was confirmed during planning, what it was and when. Per the handoff's
resolved decision #4, all 5 new checks' thresholds should be commented as
"best-guess default, ship and revisit after first live report" — do not present them
as more authoritative than that.

**Check function shape** (every function in `macro_indicators.py`): fetch → if
data unavailable, return `CheckResult(verdict="unknown", detail="<source> data
unavailable (...)")` → else compute → build a human-readable `detail` string
embedding the actual numbers and threshold → return `CheckResult(verdict="flag"|"ok"|
"info", detail=..., data={...machine-readable fields...})`.

**Graceful degradation, not exceptions**: every fetch helper (`_yfinance_latest_close`,
`fred_observation_on`, the new history-fetch helper) already swallows exceptions and
returns `None` on failure — check functions branch on `None`, they never need their
own try/except.

**Always-`"info"` checks never gate on other checks in this module** — `price_action.py`
and `crash_resilience.py` (per-ticker checks) establish this, and `check_gold_trend()`
must follow it: report the cross event and current state as neutral fact, no framing
about whether it's a good or bad time to buy.

---

## IMPLEMENTATION PLAN

### Phase 1: Config

Add the new tickers/series IDs and threshold constants to `config.py`, in a new
dated block after the existing "Added 2026-08-04 — ETF-specific criteria" section
(or wherever the file's chronological tail currently ends — check before inserting).

### Phase 2: Core Implementation

Add one new private fetch helper (long-range history close, for the rolling-average
computation) and 5 new check functions to `macro_indicators.py`, each following the
existing per-function pattern exactly.

### Phase 3: Integration

Append the 5 new check calls to `run_all()`. No other integration work — `monitor.py`,
`db.py`, and `main.py` already handle whatever `run_all()` returns generically (see
CONTEXT REFERENCES above — this was independently confirmed by reading each of the
three files, not assumed).

### Phase 4: Testing & Documentation

Add per-check tests to `test_macro_indicators.py` mirroring the existing style, update
the `run_all()` count test, and extend `.claude/skills/my-trader/SKILL.md`'s macro
indicators narrative.

---

## STEP-BY-STEP TASKS

### Task 1.1 — UPDATE `investments/my-trader/mytrader/config.py`

- **IMPLEMENT**: Add a new block (after the existing tail of the file) with:
  ```python
  # Added <today's date> -- Phase 1 gold-tracking macro indicators (see
  # .agent/plans/gold-tracker-handoff.md). Thresholds below are best-guess defaults,
  # not sourced from a specific stated criterion the way OPPORTUNITY_* thresholds
  # are -- ship, then tune against real monitor-report.md readings (resolved
  # 2026-08-07, same discipline as ETF_AUM_FLAG_USD above).
  FRED_REAL_YIELD_10Y_SERIES = "DFII10"  # 10Y TIPS yield -- opportunity cost of
                                            # holding non-yielding gold; single most
                                            # important gold driver per handoff research.
  REAL_YIELD_FLAG_NEGATIVE_PCT = 0.0  # flag when real yields go negative (bullish
                                         # catalyst for gold).
  REAL_YIELD_FLAG_HIGH_PCT = 2.0  # flag when real yields climb above this (historically
                                     # pressures gold hard) -- two-sided band.

  FRED_USD_INDEX_SERIES = "DTWEXBGS"  # Nominal Broad U.S. Dollar Index -- FRED over
                                         # yfinance DX-Y.NYB, resolved 2026-08-07 (keeps
                                         # this module's FRED-first pattern).
  DXY_LOOKBACK_DAYS = 30  # compare today's DXY to ~30 days prior -- same
                            # today/prior lookback shape as STEEPENER_LOOKBACK_DAYS.
  DXY_FLAG_MOVE_PCT = 3.0  # flag on a >3% move over the lookback window, not an
                             # absolute level (DXY doesn't have a natural "high/low"
                             # the way a bounded ratio does).

  GOLD_FUTURES_TICKER = "GC=F"  # confirmed live 2026-08-07 via yfinance.
  GOLD_MA_SHORT_DAYS = 50
  GOLD_MA_LONG_DAYS = 200
  GOLD_MA_HISTORY_LOOKBACK_DAYS = 500  # calendar days of history to fetch -- must
                                          # comfortably exceed GOLD_MA_LONG_DAYS
                                          # trading days plus enough trailing window
                                          # to find the most recent price/200DMA cross
                                          # (confirmed live 2026-08-07: last cross was
                                          # ~2 months before that date).
  PMGOLD_YFINANCE_TICKER = "PMGOLD.AX"  # Shaun's actual holding (bucket 3a,
                                           # holdings.md) -- AUD-denominated, shown
                                           # alongside the USD futures series per the
                                           # 2026-08-07 "track both" decision.

  SILVER_FUTURES_TICKER = "SI=F"
  GOLD_SILVER_RATIO_FLAG_HIGH = 80.0  # commonly-cited historical-extreme high.
  GOLD_SILVER_RATIO_FLAG_LOW = 50.0  # commonly-cited historical-extreme low.

  VIX_TICKER = "^VIX"
  VIX_FLAG_LEVEL = 30.0  # widely-cited crisis-adjacent level.
  ```
  Adjust the `<today's date>` placeholder to the real date of implementation, and
  double-check `GOLD_MA_HISTORY_LOOKBACK_DAYS` is generous enough in practice during
  Task 5's manual validation (widen if the cross-detection window in Task 2.4 needs
  more history to reliably find the confirmed 2026-06-05 cross).
- **PATTERN**: `config.py` lines 88–186 (Phase C macro block) for constant naming
  (`<DOMAIN>_<QUALIFIER>_SERIES`/`_FLAG_<UNIT>`) and comment density.
- **GOTCHA**: Do not reuse `MOVE_INDEX_TICKER`'s bare-caret convention (`"^MOVE"`) for
  `GOLD_FUTURES_TICKER`/`SILVER_FUTURES_TICKER` — futures use the `=F` suffix, not a
  caret; only indices (`^VIX`, `^MOVE`) use the caret.
- **VALIDATE**: `uv run --directory investments/my-trader python -c "from mytrader import config; print(config.GOLD_FUTURES_TICKER, config.FRED_REAL_YIELD_10Y_SERIES)"`

### Task 2.1 — ADD `_yfinance_history_close()` helper to `macro_indicators.py`

- **IMPLEMENT**: A private helper mirroring `crash_windows._fetch_close_series`,
  simplified for a single non-ASX ticker (futures/index tickers never need the
  `.AX` fallback `crash_windows.py` uses for equities):
  ```python
  def _yfinance_history_close(ticker: str, lookback_days: int):
      import yfinance as yf
      from datetime import date, timedelta

      try:
          start = (date.today() - timedelta(days=lookback_days)).isoformat()
          hist = yf.Ticker(ticker).history(start=start, auto_adjust=True)
          if hist.empty:
              return None
          close = hist["Close"]
          if getattr(close.index, "tz", None) is not None:
              close.index = close.index.tz_localize(None)
          return close
      except Exception:
          return None
  ```
- **PATTERN**: `crash_windows.py` lines 41–61 — same tz-naive normalization is
  required, don't skip it (rolling-window/date-comparison logic downstream will
  silently misbehave on a tz-aware index).
- **VALIDATE**: `uv run --directory investments/my-trader python -c "from mytrader.macro_indicators import _yfinance_history_close; s = _yfinance_history_close('GC=F', 500); print(s.tail())"`
  — confirm it returns a real, tz-naive pandas Series with recent gold closes.

### Task 2.2 — ADD `check_real_yields()` to `macro_indicators.py`

- **IMPLEMENT**: Fetch `fred_observation_on(config.FRED_REAL_YIELD_10Y_SERIES,
  date.today())`. If `None`, return `"unknown"`. Else flag if value `<
  REAL_YIELD_FLAG_NEGATIVE_PCT` (detail notes "negative real yields — bullish
  catalyst for gold") or value `> REAL_YIELD_FLAG_HIGH_PCT` (detail notes "elevated
  real yields — historically pressures gold"); otherwise `"ok"`.
- **PATTERN**: `check_consumer_sentiment()` (lines 117–138) — single-series FRED
  check with an `as_of` string and a single threshold, closest existing shape. Adapt
  to a two-sided band like `check_inflation_expectations` isn't quite right either —
  this needs its own two-branch flag logic (negative OR above-high), most similar in
  structure to `check_recession_signal`'s multi-condition `verdict = "flag" if (...)
  else "ok"` (line 190).
- **GOTCHA**: Report which side triggered the flag in the detail text — "negative"
  and "elevated" are opposite-direction signals with different implications, don't
  collapse them into one generic "outside band" message the way `us_cpi`/`uk_cpi` do
  (those don't need to distinguish direction the way this does, since the handoff is
  explicit that negative real yields are a *bullish* catalyst, not just "abnormal").
- **VALIDATE**: `uv run --directory investments/my-trader python -m pytest mytrader/tests/test_macro_indicators.py -k real_yields -v`
  (after Task 4.1 adds the tests)

### Task 2.3 — ADD `check_dollar_index()` to `macro_indicators.py`

- **IMPLEMENT**: `today = date.today()`, `prior = today -
  timedelta(days=config.DXY_LOOKBACK_DAYS)`. Fetch `fred_value_on(config.
  FRED_USD_INDEX_SERIES, today)` and `fred_value_on(config.FRED_USD_INDEX_SERIES,
  prior)`. If either is `None`, return `"unknown"`. Compute `pct_change = (now -
  prior_value) / prior_value * 100`. Flag if `abs(pct_change) >=
  config.DXY_FLAG_MOVE_PCT`.
- **PATTERN**: `check_recession_signal()` lines 142–143 and 156–159 — the exact
  `today`/`prior` two-point lookback pattern via `fred_value_on` (not
  `fred_observation_on`, since only the value is needed here, not the observation
  date for each point — matches how `short_now`/`short_prior`/`long_now`/`long_prior`
  are fetched there).
- **VALIDATE**: `uv run --directory investments/my-trader python -m pytest mytrader/tests/test_macro_indicators.py -k dollar_index -v`

### Task 2.4 — ADD `check_gold_trend()` to `macro_indicators.py`

- **IMPLEMENT**: The most involved check in this plan.
  1. `close = _yfinance_history_close(config.GOLD_FUTURES_TICKER,
     config.GOLD_MA_HISTORY_LOOKBACK_DAYS)`. If `None` or too short to compute a
     200-day rolling average, return `"unknown"`.
  2. Compute `ma_short = close.rolling(config.GOLD_MA_SHORT_DAYS).mean()` and
     `ma_long = close.rolling(config.GOLD_MA_LONG_DAYS).mean()`.
  3. Current price = `close.iloc[-1]`, current 50DMA/200DMA = `ma_short.iloc[-1]`/
     `ma_long.iloc[-1]`.
  4. Cross detection: build `diff = (close - ma_long).dropna()`, take the sign of
     each value, find the most recent index where the sign differs from the
     previous day's sign (a sign flip = a cross event). If found, note the cross
     date, the direction ("crossed above" / "crossed below"), and the price at that
     date. If no sign flip exists anywhere in the fetched window, say so explicitly
     ("no cross in the past N days of history") rather than silently omitting it.
  5. PMGOLD/AUD context: `pmgold_price = _yfinance_latest_close(config.
     PMGOLD_YFINANCE_TICKER)`, `fx_change = market_data.fetch_fx_change_pct("USD")`.
     Both are allowed to independently be `None` — degrade that part of the detail
     string gracefully without failing the whole check (the GC=F side is the
     required data; PMGOLD/AUD is enrichment).
  6. **verdict is always `"info"`** (or `"unknown"` only if the GC=F fetch itself
     fails) — never `"flag"`, never an opportunity signal, per the handoff's
     explicit design constraint. Do not add any "this looks like a buying
     opportunity" framing gated on other checks — that's explicitly deferred (see
     NOTES).
  7. `detail` should read naturally, e.g.: `"GC=F $4,412 (50DMA $4,380, 200DMA
     $4,479, -1.5% below); crossed below 200DMA on 2026-06-05 at $4,337, no cross
     back since; PMGOLD $61.20 AUD; AUD/USD 3mo move -0.8%"` — adapt exact wording,
     but include all of: current futures price, both MAs, % distance from 200DMA,
     most recent cross event (direction + date + price, or "no cross" statement),
     PMGOLD price, AUD/USD context.
- **IMPORTS**: add `from . import market_data` to the top of `macro_indicators.py`
  (not currently imported there — verify before assuming).
- **PATTERN**: `checks/price_action.py` (whole file) for the "always info, state
  facts, no judgment" tone. `checks/fx.py` line 17 + `market_data.py` lines 86–99 for
  the `fetch_fx_change_pct` call/phrasing convention.
- **GOTCHA**: `close.rolling(...).mean()` produces `NaN` for the first
  `GOLD_MA_LONG_DAYS - 1` rows — `.dropna()` before sign-flip detection or the
  leading NaN block will corrupt the comparison. Also: pandas Series `.iloc[-1]`
  after a `.dropna()` may not correspond to "today" if the most recent fetch had a
  gap — use `.index[-1]` alongside the value when reporting the cross date, don't
  assume index alignment across the three derived series (`close`, `ma_short`,
  `ma_long`) without checking.
- **GOTCHA**: Do not build the "gate opportunity framing on real_yields/dollar_index
  not flagging" logic described in the handoff — see NOTES, this needs the (out of
  scope) backtest module's base-rate context to be responsible, not a bare
  if-statement.
- **VALIDATE**: `uv run --directory investments/my-trader python -c "from mytrader.macro_indicators import check_gold_trend; r = check_gold_trend(); print(r.verdict); print(r.detail)"`
  — confirm against the handoff's confirmed 2026-08-07 numbers (crossed below
  200DMA 2026-06-05 at $4,337; as of that date $4,323 vs 200DMA $4,479) as a sanity
  check that the cross-detection logic finds the same event a human found manually
  in conversation. Numbers will have moved on by implementation time — check the
  *shape* of the output (a real cross date within the fetched window, plausible
  price/MA values), not exact figures.

### Task 2.5 — ADD `check_gold_silver_ratio()` to `macro_indicators.py`

- **IMPLEMENT**: `gold = _yfinance_latest_close(config.GOLD_FUTURES_TICKER)`,
  `silver = _yfinance_latest_close(config.SILVER_FUTURES_TICKER)`. If either is
  `None` or `silver == 0`, return `"unknown"`. `ratio = round(gold / silver, 1)`.
  Flag if `ratio >= config.GOLD_SILVER_RATIO_FLAG_HIGH` or `ratio <=
  config.GOLD_SILVER_RATIO_FLAG_LOW`.
- **PATTERN**: `check_move_index()` (lines 60–78) for the single-yfinance-value
  fetch-and-threshold shape; extend to two fetches + a ratio the way
  `check_housing_affordability` extends to two FRED fetches + a ratio (lines 81–114).
- **VALIDATE**: `uv run --directory investments/my-trader python -m pytest mytrader/tests/test_macro_indicators.py -k gold_silver -v`

### Task 2.6 — ADD `check_vix()` to `macro_indicators.py`

- **IMPLEMENT**: Direct copy of `check_move_index()`'s shape with
  `config.VIX_TICKER`/`config.VIX_FLAG_LEVEL` substituted, `name="vix"`.
- **PATTERN**: `check_move_index()` lines 60–78, verbatim structure.
- **VALIDATE**: `uv run --directory investments/my-trader python -m pytest mytrader/tests/test_macro_indicators.py -k vix -v`

### Task 3.1 — UPDATE `run_all()` in `macro_indicators.py`

- **IMPLEMENT**: Append the 5 new check calls after `check_uk_cpi()`:
  ```python
  def run_all() -> list[CheckResult]:
      return [
          check_move_index(),
          check_housing_affordability(),
          check_consumer_sentiment(),
          check_recession_signal(),
          check_inflation_expectations(),
          check_credit_spreads(),
          check_australia_cpi(),
          check_us_cpi(),
          check_uk_cpi(),
          check_real_yields(),
          check_dollar_index(),
          check_gold_trend(),
          check_gold_silver_ratio(),
          check_vix(),
      ]
  ```
- **PATTERN**: `run_all()` lines 362–373 (existing, being extended).
- **VALIDATE**: `uv run --directory investments/my-trader python -c "from mytrader.macro_indicators import run_all; print(len(run_all()))"` → expect `14`
  (requires `FRED_API_KEY` set and network access for a fully-populated real run;
  otherwise some will legitimately return `"unknown"`, which is fine — the count
  should still be 14).

### Task 4.1 — UPDATE `investments/my-trader/mytrader/tests/test_macro_indicators.py`

- **IMPLEMENT**: Add tests for each of the 5 new checks, mirroring the existing
  per-check test triplet style (unknown / flag / ok, or unknown / flag-high /
  flag-low / ok where a two-sided band applies):
  - `check_real_yields`: unknown-when-fred-unavailable; flags-when-negative;
    flags-when-above-high-threshold; ok-in-between.
  - `check_dollar_index`: unknown-when-either-fred-value-missing (mock
    `fred_value_on`); flags-on-large-move (both directions); ok-on-small-move.
  - `check_gold_trend`: mock `_yfinance_history_close` (and
    `market_data.fetch_fx_change_pct`, and `_yfinance_latest_close` for the PMGOLD
    leg) — construct a small synthetic `pandas.Series` with a known, deliberately
    engineered cross partway through so the test can assert the detected cross
    date/direction matches exactly; also test the "no cross in window" case and the
    "history fetch fails → unknown" case.
  - `check_gold_silver_ratio`: unknown-when-either-price-missing;
    flags-above-high; flags-below-low; ok-in-between.
  - `check_vix`: unknown/flag/ok, identical shape to
    `test_check_move_index_*` (lines 10–31), values substituted.
- **UPDATE**: `test_run_all_returns_nine_check_results` (lines 357–369) → rename to
  `test_run_all_returns_fourteen_check_results`, add
  `monkeypatch.setattr("mytrader.macro_indicators._yfinance_history_close", lambda
  ticker, lookback_days: None)` and
  `monkeypatch.setattr("mytrader.macro_indicators.market_data.fetch_fx_change_pct",
  lambda base: None)` alongside the existing stubs (the existing
  `_yfinance_latest_close` stub already covers `check_vix`/
  `check_gold_silver_ratio`'s calls; `fred_observation_on`'s existing stub does NOT
  cover `check_dollar_index`, which calls `fred_value_on` — stub that too), update
  the expected count to `14` and the expected name set to include `"real_yields"`,
  `"dollar_index"`, `"gold_trend"`, `"gold_silver_ratio"`, `"vix"`.
- **PATTERN**: Every existing test in this file — `monkeypatch.setattr` on the exact
  dotted path (`"mytrader.macro_indicators.<fn>"`), never patch the underlying
  library call directly.
- **VALIDATE**: `uv run --directory investments/my-trader python -m pytest mytrader/tests/test_macro_indicators.py -v`

### Task 4.2 — UPDATE `.claude/skills/my-trader/SKILL.md`

- **IMPLEMENT**: Extend the "Macro Monitoring Indicators" section (currently lines
  219–249) to mention the 5 new checks in the same flowing-prose style as the
  existing paragraph — what each measures, its data source, and the threshold
  rationale (best-guess default, ship-and-revisit, per the 2026-08-07 decision).
  Update "9 portfolio-wide checks" (line 221) to "14 portfolio-wide checks".
- **PATTERN**: Lines 219–249 (existing prose for the 9 checks) — match the density
  and tone exactly, don't switch to a bullet list.
- **VALIDATE**: Manual read-through — confirm the paragraph accurately describes
  what Tasks 2.2–2.6 actually built (write this task last, after implementation, not
  from this plan's description alone, in case anything shifted during
  implementation).

### Task 5 — Manual validation against the real environment

- **IMPLEMENT**: Nothing to write — this is a live-data confirmation pass.
  1. Run the full test suite (Level 2 below) — must pass with zero regressions.
  2. Run a real `monitor` invocation against the actual shared DB and confirm the 5
     new rows appear in `investments/my-trader/monitor-report.md`'s "Macro
     Indicators" section with real (or gracefully-`"unknown"`) values.
  3. Specifically eyeball `check_gold_trend()`'s output against the handoff's
     confirmed 2026-08-07 numbers (crossed below 200DMA 2026-06-05 at $4,337) —
     the cross date should either match that or reflect a newer cross if one has
     happened since. If the detected cross date looks wrong, the sign-flip
     detection logic (Task 2.4) needs debugging before this ships, not a threshold
     tweak.
  4. Confirm `GOLD_MA_HISTORY_LOOKBACK_DAYS = 500` was actually enough history —
     if the real fetch returns fewer trading days than needed to cover both the
     200-day rolling window AND the known 2026-06-05 cross, widen it.
- **VALIDATE**: `uv run --directory investments/my-trader python -m mytrader.main monitor`
  then inspect `investments/my-trader/monitor-report.md` directly.

---

## TESTING STRATEGY

### Unit Tests

Every new check function gets full branch coverage (unknown / flag / ok, or the
two-sided-band equivalent) via `monkeypatch`-stubbed fetch functions — no real
network calls in the unit test suite, matching every existing test in
`test_macro_indicators.py`. `check_gold_trend()` additionally needs a synthetic
`pandas.Series` fixture with a hand-constructed, known cross point so the
sign-flip-detection algorithm itself is verified deterministically, not just its
error-handling branches.

### Integration Tests

`run_all()`'s count/name-set test (Task 4.1) is the integration check for this
feature — confirms all 14 checks wire together without exceptions when every
external fetch is stubbed to fail gracefully. `test_monitor.py` needs no changes
(it already stubs `macro_indicators.run_all` entirely at the monitor level), but
re-run its suite anyway to confirm nothing broke.

### Edge Cases

- FRED API key unset → `check_real_yields`/`check_dollar_index` both degrade to
  `"unknown"`, same as every existing FRED check.
- `GC=F` yfinance history fetch fails or returns fewer than
  `GOLD_MA_LONG_DAYS` rows → `check_gold_trend` returns `"unknown"`, not a crash.
- PMGOLD or AUD/USD fetch fails independently of the GC=F fetch succeeding →
  `check_gold_trend` still returns real GC=F-based `"info"`, with the PMGOLD/AUD
  portion of the detail string gracefully noting unavailability (mirrors
  `checks/fx.py`'s own "change_pct is None" branch).
- No cross event anywhere within `GOLD_MA_HISTORY_LOOKBACK_DAYS` — detail states
  this explicitly rather than omitting the cross-status sentence.
- Gold/silver ratio at a fetch failure for exactly one leg (gold fetches, silver
  doesn't, or vice versa) → `"unknown"`, not a `ZeroDivisionError` or a ratio
  computed against stale/missing data.

---

## VALIDATION COMMANDS

### Level 1: Syntax & Style

```powershell
cd investments/my-trader
uv run ruff check .
uv run mypy mytrader
```

### Level 2: Unit Tests

```powershell
cd investments/my-trader
uv run pytest mytrader/tests -v
```

### Level 3: Integration Tests

```powershell
cd investments/my-trader
uv run pytest mytrader/tests/test_macro_indicators.py mytrader/tests/test_monitor.py -v
```

### Level 4: Manual Validation

See Task 5 above — a real `python -m mytrader.main monitor` run, inspecting
`investments/my-trader/monitor-report.md`'s "Macro Indicators" section for all 14
rows (9 existing + 5 new), and specifically sanity-checking `gold_trend`'s detected
cross event against the handoff's confirmed 2026-08-07 numbers.

### Level 5: Additional Validation

N/A — no MCP servers or additional CLI tools involved beyond `uv`/`pytest`/`ruff`/
`mypy`, all covered above.

---

## ACCEPTANCE CRITERIA

- [ ] `check_real_yields`, `check_dollar_index`, `check_gold_trend`,
      `check_gold_silver_ratio`, `check_vix` all exist in `macro_indicators.py` and
      are included in `run_all()`
- [ ] `run_all()` returns exactly 14 `CheckResult`s
- [ ] `check_gold_trend` always returns `verdict="info"` (or `"unknown"` on total
      fetch failure) — never `"flag"`, never an opportunity-style signal
- [ ] `check_gold_trend`'s detail includes GC=F price, 50DMA, 200DMA, most recent
      price/200DMA cross (direction + date + price, or explicit "no cross" note),
      PMGOLD AUD price, and AUD/USD 3mo context
- [ ] All new `config.py` thresholds carry a "best-guess default, ship and revisit"
      style comment, consistent with the 2026-08-07 decision
- [ ] All validation commands pass with zero errors, zero regressions in the
      existing 155+ test suite
- [ ] `monitor-report.md`'s "Macro Indicators" section shows all 14 checks after a
      real `monitor` run
- [ ] `.claude/skills/my-trader/SKILL.md` updated to describe the 5 new checks
- [ ] No changes made to `monitor.py`, `db.py`, or `main.py` (confirms the "extend
      the existing generic wiring, don't special-case" design held up in practice)
- [ ] No backtest module, no gated "opportunity" framing on the gold cross event,
      and no train/validation split logic built as part of this pass (explicitly
      out of scope — see NOTES)

---

## COMPLETION CHECKLIST

- [ ] All tasks completed in order (1.1 → 2.1–2.6 → 3.1 → 4.1–4.2 → 5)
- [ ] Each task's own validation command passed immediately after that task
- [ ] Full test suite passes (`uv run pytest mytrader/tests -v`)
- [ ] `ruff`/`mypy` clean
- [ ] Real `monitor` run confirms all 14 macro rows, including a sane
      `gold_trend` reading
- [ ] `SKILL.md` documentation updated
- [ ] Acceptance criteria all met

---

## NOTES

**Scope boundary (2026-08-07 decision, from the handoff)**: this plan is Phase 1
indicators only. Do NOT build in this pass:
- The backtest/signal-validation module (`gold_backtest`-style CLI, train/validation
  split, forward-return distributions) — a separate follow-up plan once this
  indicator data has actually been flowing for a while.
- Any "this cross looks like a buying opportunity" framing gated on
  `real_yields`/`dollar_index` not showing deterioration. The handoff raises this
  idea, but doing it responsibly needs the backtest module's historical base-rate
  context (sample size, win rate, distribution) to avoid presenting an untested
  heuristic as if it were validated — building the gate now without that context
  would be worse than not building it, not just premature.

**Threshold discipline**: every new `config.py` constant in this plan is an
explicitly-flagged best guess (2026-08-07 decision #4) — do not spend implementation
time trying to research "the correct" real-yield band or DXY move threshold beyond
what's already stated in the handoff. Ship the defaults, let Shaun tune them against
real `monitor-report.md` output.

**`check_gold_trend` is the one genuinely new technique in this module** — every
other check (including the 4 other new ones in this plan) is a straightforward
extension of an existing single-value or two-value fetch-and-threshold shape.
Budget the most implementation and testing time here; the sign-flip cross-detection
logic in particular deserves a deliberately-constructed synthetic test case, not
just mocked-to-None error-path tests.
