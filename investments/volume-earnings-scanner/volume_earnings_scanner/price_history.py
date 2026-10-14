"""Close+volume price history fetch -- ported from goat/price_history.py's
fetch_close_volume_history, not imported. goat depends on my-trader, not the
reverse, and this package is a my-trader-dependent sibling of goat, not a goat
dependant (see goat/config.py's own GOAT_INDUSTRY_ETFS migration comment for why a
cross-package import in that direction would be circular/wrong-direction). The
.AX-fallback shape is harmless even though this scan is US-only -- kept to stay a
faithful copy rather than a divergent rewrite, same posture earnings_watch.py's own
_fetch_close_history takes for its "private copy, not a shared import" decision."""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
from mytrader import tickers, yf_retry


def fetch_close_volume_history(ticker: str, lookback_days: int) -> pd.DataFrame | None:
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
