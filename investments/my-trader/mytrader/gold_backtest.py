"""Historical backtest for gold's macro signals and technical indicators.

Two methodologies, unified under one results shape:

- Episode-based (the 5 macro signals from macro_indicators.py): rare,
  discrete regime-shift events. Find every historical occurrence, compute
  forward return from each occurrence date.
- State-conditioned (the 6 technical indicators from gold_technicals.py):
  common, persistent daily readings. Classify every trading day's state,
  compute forward return conditioned on every day that state held (not just
  the day it started).

Both feed the exact same downstream shape -- {n, mean, median, win_rate, best,
worst, baseline} keyed by (name, value, horizon_unit, horizon_value) -- so
gold_outlook.py never needs to know which methodology produced a given row.
See .agent/plans/gold-tracker-phase2-outlook.md for the full design rationale.
"""

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
    _fetch_ohlcv, macd_series, moving_average_series, rsi_series, stochastic_series,
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
    boundary doesn't matter. Distinct from compute_forward_return_trading_days,
    which is positional/trading-day based -- required at day/week resolution,
    where calendar-day arithmetic would land on non-trading days."""
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
# derivation must also produce for the join to find a match.

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
