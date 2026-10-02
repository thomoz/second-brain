"""Price history fetch for Goat's technical checks."""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
from mytrader import tickers, yf_retry


def fetch_close_history(ticker: str, lookback_days: int) -> pd.Series | None:
    """Long-range daily close history for a single ticker. Mirrors
    mytrader.crash_windows._fetch_close_series -- tries the ticker as-is first,
    then the ASX `.AX` variant, since Goat's holdings include real ASX-listed
    stocks/ETFs (unlike gold's futures-only ticker, which never needs this
    fallback). Ported rather than imported since that function is module-private
    to crash_windows.py."""
    import yfinance as yf

    start = (date.today() - timedelta(days=lookback_days)).isoformat()
    for candidate in (tickers.normalize(ticker), tickers.asx_variant(ticker)):
        try:
            hist = yf_retry.call(lambda c=candidate: yf.Ticker(c).history(start=start, auto_adjust=True))
        except Exception:
            continue
        if hist.empty:
            continue
        close = hist["Close"].dropna()
        if close.empty:
            continue
        if getattr(close.index, "tz", None) is not None:
            close.index = close.index.tz_localize(None)
        return close
    return None


def fetch_close_volume_history(ticker: str, lookback_days: int) -> pd.DataFrame | None:
    """Sibling of fetch_close_history that also keeps Volume -- added for the
    heartbeat pattern-quality handoff's volume-declining report-only signal
    (see .agent/plans/goat-heartbeat-pattern-quality.md). fetch_close_history
    itself is shared by six other Goat modules with no need for Volume
    (dma_breakout_scan, hated_industries_scan, industry_rotation,
    insider_scan, live_monitor, monitor, sector_rotation) -- a new sibling
    avoids touching any of their call sites, matching the precedent set by
    mytrader/checks/matt_damon_price_volitility_volume_check.py's own
    _fetch_price_volume_history (a sibling of mytrader's close-only
    fetchers, not a modification of them -- see
    .agent/plans/completed/matt-damon-price-volitility-volume-check.md
    Task 2)."""
    import yfinance as yf

    start = (date.today() - timedelta(days=lookback_days)).isoformat()
    for candidate in (tickers.normalize(ticker), tickers.asx_variant(ticker)):
        try:
            hist = yf_retry.call(lambda c=candidate: yf.Ticker(c).history(start=start, auto_adjust=True))
        except Exception:
            continue
        if hist.empty:
            continue
        frame = hist[["Close", "Volume"]].dropna(subset=["Close"])
        if frame.empty:
            continue
        if getattr(frame.index, "tz", None) is not None:
            frame.index = frame.index.tz_localize(None)
        return frame
    return None
