"""Price history fetch for Goat's technical checks."""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
from mytrader import tickers


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
            hist = yf.Ticker(candidate).history(start=start, auto_adjust=True)
        except Exception:
            continue
        if hist.empty:
            continue
        close = hist["Close"]
        if getattr(close.index, "tz", None) is not None:
            close.index = close.index.tz_localize(None)
        return close
    return None
