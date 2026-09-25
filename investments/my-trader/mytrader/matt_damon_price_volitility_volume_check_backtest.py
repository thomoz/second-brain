"""One-off backtest: does the Matt Damon Price/Volatility/Volume Check alignment
reading (see checks/matt_damon_price_volitility_volume_check.py) correlate with
subsequent price direction any better than price ROC alone, or than an
unconditioned baseline? Confirmed scope with Shaun 2026-09-25: holdings +
"discussed" watchlist tickers, ~2yr history each, 10-trading-day forward return,
state-conditioned methodology reusing gold_backtest.py's generic forward-return/
baseline/state-conditioning functions (NOT investments/backtest/'s unrelated
Streamlit walk-forward trading-strategy backtester -- that tool optimizes RSI
entry/exit parameters per-fold, a different question from "does this state
predict this return").

Run manually, read the printed comparison, then hand-write the conclusion into
investments/roc-triple-signal-handoff.md's Validation section -- this script does
not persist or auto-decide anything.
"""

from __future__ import annotations

import pandas as pd

from . import config, db, tickers
from .checks.matt_damon_price_volitility_volume_check import (
    _alignment_label, _roc, _smoothed_volume_series, _volatility_series,
)
from .gold_backtest import compute_forward_return_trading_days


def _fetch_backtest_history(ticker: str) -> pd.DataFrame | None:
    import yfinance as yf

    for candidate in (tickers.normalize(ticker), tickers.asx_variant(ticker)):
        try:
            hist = yf.Ticker(candidate).history(
                period=config.MATT_DAMON_BACKTEST_HISTORY_PERIOD, auto_adjust=True
            )
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
    """Day-by-day alignment label, short-window only (the window the backtest's
    forward horizon of 10 trading days is scoped against) -- loop-based since
    _roc needs a fixed lookback per row; acceptable cost at ~2yr/ticker, not a hot
    path. Do NOT copy this O(n^2) pattern into the live check() function (which
    correctly only computes the *last* value) or into anything scheduled."""
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
    """Comparison classifier: price ROC direction alone, same window -- the thing
    Shaun's confluence idea needs to beat."""
    labels = []
    for i in range(len(close)):
        r = _roc(close.iloc[: i + 1], window)
        labels.append("unknown" if r is None else ("up" if r > 0 else "down" if r < 0 else "flat"))
    return pd.Series(labels, index=close.index)


def _state_conditioned_raw_returns(
    state: pd.Series, close: pd.Series, n_days: int,
) -> dict[str, list[float]]:
    """Raw per-occurrence forward returns per state value, over the WHOLE series
    (no window_start/window_end slicing -- unlike gold_backtest.compute_state_
    conditioned_stats, this backtest wants every occurrence in the ~2yr pull, not
    a validation-split subset). Mirrors that function's body up to but not
    including its final _distribution_stats dict-comprehension, so raw returns
    can be pooled ACROSS tickers before computing one final stats dict per state
    -- avoids a weighted-mean-of-means bug from averaging per-ticker summaries."""
    by_state: dict[str, list[float]] = {}
    for pos, (_, value) in enumerate(state.items()):
        if pd.isna(value):
            continue
        r = compute_forward_return_trading_days(close, pos, n_days)
        if r is not None:
            by_state.setdefault(str(value), []).append(r)
    return by_state


def _baseline_raw_returns(close: pd.Series, n_days: int) -> list[float]:
    """Unconditioned forward-return distribution over the whole series -- mirrors
    gold_backtest.compute_baseline_trading_days minus the final _distribution_
    stats call, so it can be pooled across tickers the same way the state-
    conditioned returns are."""
    returns = []
    for pos in range(len(close)):
        r = compute_forward_return_trading_days(close, pos, n_days)
        if r is not None:
            returns.append(r)
    return returns


def _pool_stats(returns: list[float]) -> dict:
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


def run_backtest(conn) -> dict:
    tickers_to_check = sorted(
        {r["ticker"] for r in db.get_all_holdings(conn)}
        | {r["ticker"] for r in db.get_all_watchlist(conn) if r["status"] == "discussed"}
    )
    n_days = config.MATT_DAMON_BACKTEST_FORWARD_HORIZON_TRADING_DAYS
    window = config.MATT_DAMON_SHORT_WINDOW_DAYS

    confluence_by_state: dict[str, list[float]] = {}
    price_only_by_state: dict[str, list[float]] = {}
    baseline_returns: list[float] = []

    for ticker in tickers_to_check:
        frame = _fetch_backtest_history(ticker)
        if frame is None:
            print(f"[matt_damon_price_volitility_volume_check_backtest] skipping {ticker} -- insufficient history")
            continue
        close = frame["Close"]

        confluence_state = _confluence_state_series(frame, window)
        for label, returns in _state_conditioned_raw_returns(confluence_state, close, n_days).items():
            if label in ("unknown", "no_read"):
                continue
            confluence_by_state.setdefault(label, []).extend(returns)

        price_only_state = _price_roc_only_state_series(close, window)
        for label, returns in _state_conditioned_raw_returns(price_only_state, close, n_days).items():
            if label in ("unknown", "flat"):
                continue
            price_only_by_state.setdefault(label, []).extend(returns)

        baseline_returns.extend(_baseline_raw_returns(close, n_days))

    return {
        "confluence": {k: _pool_stats(v) for k, v in confluence_by_state.items()},
        "price_only": {k: _pool_stats(v) for k, v in price_only_by_state.items()},
        "baseline": _pool_stats(baseline_returns),
        "tickers_checked": len(tickers_to_check),
    }


def print_comparison(results: dict) -> None:
    n_days = config.MATT_DAMON_BACKTEST_FORWARD_HORIZON_TRADING_DAYS
    print(
        f"\n=== Matt Damon Price/Volatility/Volume Check Backtest "
        f"({results['tickers_checked']} ticker(s), {n_days}-trading-day forward return) ==="
    )
    print("\nConfluence-aligned states:")
    for label, stats in sorted(results["confluence"].items()):
        print(f"  {label:<16} N={stats['n']:<5} mean={stats['mean']} median={stats['median']} "
              f"win-rate={stats['win_rate']}% best={stats['best']} worst={stats['worst']}")
    print("\nPrice-ROC-only states:")
    for label, stats in sorted(results["price_only"].items()):
        print(f"  {label:<16} N={stats['n']:<5} mean={stats['mean']} median={stats['median']} "
              f"win-rate={stats['win_rate']}% best={stats['best']} worst={stats['worst']}")
    b = results["baseline"]
    print(f"\nUnconditioned baseline: N={b['n']:<5} mean={b['mean']} median={b['median']} "
          f"win-rate={b['win_rate']}% best={b['best']} worst={b['worst']}")


def main() -> None:
    from scripts.db import get_connection, init_db

    from .config import DB_PATH
    from .db import init_mytrader_tables

    init_db(DB_PATH)
    conn = get_connection(DB_PATH)
    init_mytrader_tables(conn)
    results = run_backtest(conn)
    conn.close()
    print_comparison(results)


if __name__ == "__main__":
    main()
