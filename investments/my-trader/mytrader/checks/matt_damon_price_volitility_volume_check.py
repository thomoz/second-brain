"""Matt Damon Price/Volatility/Volume Check -- rate-of-change (ROC) of price,
volatility, and volume read together, over a short (10-trading-day) and long
(25-trading-day) window, to see whether the three are moving in an aligned
direction ("confluence") or not.

Deliberately always verdict="info", never "flag"/"interesting" -- same "report
the fact, don't judge it" philosophy as price_action.py/technical_levels.py. The
alignment label below is a descriptive convenience, not a validated predictive
claim: whether this three-signal combination actually predicts direction any
better than price ROC alone is an open empirical question, answered (positively
or negatively) by matt_damon_price_volitility_volume_check_backtest.py -- see
that module and .agent/plans/matt-damon-price-volitility-volume-check.md for the
result. Until/unless that backtest shows a real edge, this stays a reporting
check, not a live gate -- the exact discipline the Goat heartbeat "quiet base"
BBW-percentile leg skipped, which shipped an unvalidated lookback-window
assumption as a live gate and produced zero candidates for 10 days before needing
a full diagnose-and-rebuild (see .agent/plans/completed/goat-heartbeat-quiet-redesign.md).
"""

from __future__ import annotations

import pandas as pd

from .. import config, tickers
from . import CheckResult


def _fetch_price_volume_history(
    ticker: str, period: str = config.MATT_DAMON_HISTORY_PERIOD
) -> pd.DataFrame | None:
    """Close+Volume history -- unlike goat/price_history.py and
    technical_levels._fetch_close_series, keeps the Volume column (both those
    functions fetch the full yfinance frame and discard everything but Close;
    Volume was never a new API surface, just thrown away)."""
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
    """Standard ROC: (value_today - value_N_ago) / value_N_ago * 100. None if not
    enough history or the N-ago value is zero/NaN. Assumes series is already
    dropna()'d and index-ordered oldest-to-newest."""
    if len(series) <= window:
        return None
    then = series.iloc[-window - 1]
    now = series.iloc[-1]
    if then in (0, None) or pd.isna(then) or pd.isna(now):
        return None
    return float((now - then) / then * 100)


def _volatility_series(
    close: pd.Series, window: int = config.MATT_DAMON_VOLATILITY_WINDOW_DAYS
) -> pd.Series:
    """Rolling std-dev of daily pct returns -- the ROC of THIS series is the
    volatility-expansion/contraction read. Close-only (no OHLC frame needed), and
    doesn't need a percentile-vs-own-history normalization (the BBW-percentile
    shape that already failed once in goat-heartbeat-quiet-redesign)."""
    return close.pct_change().rolling(window).std() * 100


def _smoothed_volume_series(
    volume: pd.Series, window: int = config.MATT_DAMON_VOLUME_SMOOTHING_DAYS
) -> pd.Series:
    return volume.rolling(window).mean()


def _alignment_label(
    price_roc: float | None, vol_roc: float | None, volume_roc: float | None
) -> str:
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
        return CheckResult(
            name="matt_damon_price_volitility_volume_check", verdict="unknown",
            detail="No market data available",
        )
    frame = _fetch_price_volume_history(data.ticker)
    min_needed = (
        max(
            config.MATT_DAMON_LONG_WINDOW_DAYS,
            config.MATT_DAMON_VOLATILITY_WINDOW_DAYS,
            config.MATT_DAMON_VOLUME_SMOOTHING_DAYS,
        )
        + 1
    )
    if frame is None or len(frame) < min_needed:
        return CheckResult(
            name="matt_damon_price_volitility_volume_check", verdict="unknown",
            detail="Not enough price/volume history for ROC confluence",
        )

    close = frame["Close"]
    vol_series = _volatility_series(close)
    volume_smoothed = _smoothed_volume_series(frame["Volume"])

    data_out: dict = {}
    parts = []
    for label, window in (
        ("short", config.MATT_DAMON_SHORT_WINDOW_DAYS),
        ("long", config.MATT_DAMON_LONG_WINDOW_DAYS),
    ):
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

    return CheckResult(
        name="matt_damon_price_volitility_volume_check", verdict="info",
        detail="; ".join(parts), data=data_out,
    )
