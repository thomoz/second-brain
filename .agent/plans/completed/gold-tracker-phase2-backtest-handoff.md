# Handoff: Gold Signal Backtest Module (Phase 2)

## Status: Not started — design agreed 2026-08-07 (same day Phase 1 shipped), ready for /plan-feature

## Context

Phase 1 (`.agent/plans/completed/gold-tracker-phase1-indicators.md`, shipped 2026-08-07)
added 5 daily macro-indicator checks to Monitor: `real_yields`, `dollar_index`,
`gold_trend`, `gold_silver_ratio`, `vix`. `check_gold_trend()` in particular reports a
200DMA cross as neutral `"info"` specifically because whether it's actually predictive
for gold is unvalidated — a 200DMA cross is a contested signal (standard
trend-following treats a break below as bearish, but gold has a documented
small-sample history of behaving as a contrarian buy signal instead). This module is
that validation.

**Not waiting for Phase 1's live daily runs to accumulate data first.** The original
Phase 1 handoff's sequencing note ("build backtest second, after Phase 1 indicators
exist") implied a data dependency that turned out not to be real: the backtest
methodology tests against decades of pre-existing historical price/FRED data
(confirmed live 2026-08-07, see table below), independent of Monitor's forward-looking
daily cadence. Shaun asked for this directly — "I want to test on historical data,
that was the whole idea" — once that was clarified.

## Decisions resolved 2026-08-07

1. **Signal scope: all 5 Phase 1 signals** — `real_yields` (negative/elevated),
   `dollar_index` (>3%/30-day move), `gold_trend` (200DMA cross), `gold_silver_ratio`
   (>=80 / <=50), `vix` (>=30) — not just the contested gold-trend cross.
2. **Train/validation split: 2018-01-01, a fixed calendar date, applied uniformly**
   across all 5 signals. Any threshold or episode-definition tuning happens only on
   data before this date; every reported "does this signal work" conclusion comes only
   from occurrences on or after it — never from the tuning window. Confirmed live
   2026-08-07 that every signal has a healthy sample of historical occurrences on both
   sides of this date (raw counts checked in conversation, not reproduced here — the
   point is the split isn't starving either window, not the exact numbers, which will
   shift slightly once the plan's real episode-deduplication logic is applied).
3. **Forward-return horizons: 3m / 6m / 12m / 24m.** Matches briefs-finance's existing
   stock backtest's 3/6/12m, plus a 24m horizon per gold's longer documented cycles
   (not applicable to the stock backtest, which is why it stops at 12m).
4. **Benchmark: compare against an unconditional baseline** — gold's own
   average/median forward return over random windows of the same length, not
   conditioned on any signal. Without this, "gold rose after the signal fired" doesn't
   show the signal added anything over just holding gold generally.
5. **Output: a distribution, not a single score** — N, mean, median, win-rate (%
   positive), best/worst case, per signal per horizon, with N always visible. These are
   rare events (a handful to a few dozen occurrences), so sample size must never be
   buried behind a headline percentage.
6. **Framing: advisor-note historical context only** — never a predictive guarantee,
   never a buy/sell recommendation, never wired into any "opportunity" gating logic.
   Same philosophy as every other advisor-mode surface in this tool.
7. **Cadence: on-demand CLI only, not part of Monitor's daily run.** Backtesting
   decades of history is a "run when curious / after tuning something" action, not a
   daily recheck — Monitor's existing 14 checks stay exactly as they are; this is a
   new, separate CLI entry point (see "How Shaun will use it" below).
8. **Occurrence-finding must evaluate every trading day, not a coarser sample.**
   Confirmed live 2026-08-07 via FRED series metadata: `DFII10` and `DTWEXBGS` are
   both published at **Daily** frequency (not weekly/monthly as might be assumed from
   how Monitor's own `dollar_index` check reads them — that check only compares two
   points, today vs. `DXY_LOOKBACK_DAYS` prior, once per Monitor run — see Task 2.3 of
   `gold-tracker-phase1-indicators.md`). Combined with GC=F/SI=F/VIX (also daily via
   yfinance), all 5 signals have genuinely daily source data. The backtest's
   occurrence-finding logic must recompute each signal's trigger condition for
   **every single day** in its history (e.g. `dollar_index`'s "30-day change >= 3%"
   check re-evaluated as a rolling window on every trading day, not sampled monthly),
   not just at fixed/wider intervals — otherwise a short-lived spike that reverts
   within a window can be missed entirely, and occurrence dates used to anchor
   forward-return calculations would be wrong or absent. This is a stricter
   requirement than Monitor's own live checks need (Monitor only ever needs "is this
   true right now"; the backtest needs "every day this became true historically").

## Data availability confirmed live 2026-08-07

| Series | Earliest data | Frequency | Source |
|---|---|---|---|
| GC=F / SI=F (gold/silver futures) | 2000-08-30 | Daily (trading days) | yfinance |
| ^VIX | 1990-01-02 | Daily (trading days) | yfinance |
| DFII10 (10Y real yield) | 2003-01-02 | Daily (confirmed via FRED series metadata) | FRED |
| DTWEXBGS (broad USD index) | 2006-01-02 | Daily (confirmed via FRED series metadata) — shortest series; each signal is backtested against its own full available history, this just sets the floor for dollar_index specifically | FRED |

## What "backtest" means here

1. For each of the 5 signals, find every historical occurrence — a clean,
   de-duplicated **episode**, not a raw day-count of a threshold being met (e.g. the
   gold/silver ratio wobbling back and forth across 80 for a week should count as one
   episode, not five) — by evaluating the signal's trigger condition on **every
   trading day** across its full available history (see Decision 8 — no monthly/
   coarser sampling).
2. Split occurrences at 2018-01-01 into tuning vs. validation.
3. For each validation-window occurrence, compute gold's forward return at
   3m/6m/12m/24m from the occurrence date (reuse GC=F, the same instrument
   `check_gold_trend()` already tracks).
4. Compute the unconditional baseline: gold's average/median return over random
   windows of the same length, over the same overall history.
5. Report both side by side, per signal per horizon: N, mean, median, win-rate,
   best/worst — so "signal fired" performance is directly comparable to "no signal"
   performance.

Exact episode-deduplication logic (e.g. a minimum-gap-days rule between two
occurrences of the same signal so threshold-hugging noise doesn't inflate N) is left
to the plan to design and justify — not pre-decided here.

## How Shaun will use it — MUST be documented in the plan's own output, not left implicit

Shaun explicitly asked that this handoff instruct the plan to spell out how to use the
finished tool, not just implement it silently. The plan (and its STEP-BY-STEP TASKS)
must include a documentation task covering:

- The exact CLI command(s) to run it — e.g. a new `gold-backtest` subcommand on
  mytrader's existing argparse-based `main.py` CLI, mirroring how `monitor`/
  `snapshot`/`seed` are already wired (see `main.py`'s subparsers, ~lines 241–300),
  and/or a standalone module entry point mirroring
  `investments/briefs-finance/scripts/backtest.py`'s own `--ticker`/`--stats` flag
  pattern (lines 241–245).
- What the output looks like and how to read it — a worked example against real data
  for at least one signal, in the same console-table style as
  `briefs-finance/scripts/backtest.py`'s `print_stats()` (lines 185–238).
- Where results are saved, if anywhere (console-only, or also a persisted `.md` file
  / DB table so results don't need re-running every time to reference).
- A new "Gold Signal Backtest" section in `.claude/skills/my-trader/SKILL.md`
  documenting the command, what it measures, and how to interpret a result (e.g. "N=8
  is not a lot — read directionally, not as proof").
- The plan's own final report to Shaun (its completion summary) must end with a short
  "what to run and what you'll see" recap, not just "tests pass" — this is the part
  Shaun explicitly asked for.

## Explicit non-goals

- Not a buy/sell signal, not gated into `opportunity.py`'s opportunity framing — this
  backtest **informs** whether that gating would ever be justified, it doesn't
  implement the gating itself.
- Not wired into Monitor's daily cadence (see Decision 7).
- Not a general backtesting framework for arbitrary future signals — scoped to these 5
  Phase 1 checks specifically; a 6th signal backtested later is a follow-up, not scope
  creep to pull in now.

## Reference code

- `investments/briefs-finance/scripts/backtest.py` — `backtest_recommendation()` /
  `run_backtest()` (lines 38–182) for the outcome-window forward-return methodology to
  generalize from recommendation dates to signal-occurrence dates; `print_stats()`
  (lines 185–238) for the distribution-reporting console pattern to mirror.
- `investments/my-trader/mytrader/macro_indicators.py` — the 5 signal check functions
  (`check_real_yields`, `check_dollar_index`, `check_gold_trend`,
  `check_gold_silver_ratio`, `check_vix`) define exactly what each signal's trigger
  condition is; the backtest's occurrence-finding logic must match each check's live
  threshold/condition exactly — reuse `config.py`'s existing constants
  (`REAL_YIELD_FLAG_NEGATIVE_PCT` etc.), don't reintroduce separate copies.
- `investments/my-trader/mytrader/crash_windows.py` — `_fetch_close_series()` /
  `_drawdown()` for the existing long-range-history-fetch and window-slicing patterns
  already used elsewhere in this codebase.
- `investments/my-trader/mytrader/main.py` — argparse subparser pattern (lines
  241–300) for wiring in a new CLI command.

## Validation (once built)

```powershell
uv run --directory investments/my-trader python -m pytest mytrader/tests/ -q
# Manual: run the new backtest command against real data, confirm the output matches
# the "worked example" the plan's own documentation task produced.
```
