"""Technical moving-average levels -- current price vs 50/150/200-day moving
averages. Added 2026-08-13 after rating Monitor's Holdings report against "would
this help a trader decide what action to take" (35/100) -- one of the biggest gaps
was no distance-from-key-levels read, despite this being exactly what Shaun already
tracks manually (e.g. plotting 50/150 SMA on real charts) and what the Goat tool
(investments/goat/) already computes for its own sector-ETF universe. This gives
every my-trader holding/watchlist ticker the same read, not just Goat's sectors.

Deliberately always verdict="info", never "flag"/"interesting" -- same philosophy as
price_action.py/crash_resilience.py/macro_indicators.py's gold_trend check: a moving
-average cross is a widely contested, context-dependent signal (bullish trend-
following vs. Goat's own "sell when reasonably below the 150DMA" exit rule vs a
stock-specific whipsaw), so this check reports the fact -- price vs each MA, not a
judgment on what it means.
"""

from __future__ import annotations

from .. import tickers
from . import CheckResult

_WINDOWS = (50, 150, 200)


def _fetch_close_series(ticker: str):
    """Long-range adjusted-close history -- same two-candidate (bare, then .AX)
    lookup pattern as crash_windows.py/return_data.py, split out for direct
    unit-testing the same way those modules are."""
    import yfinance as yf

    for candidate in (tickers.normalize(ticker), tickers.asx_variant(ticker)):
        try:
            hist = yf.Ticker(candidate).history(period="1y", auto_adjust=True)
        except Exception:
            continue
        if hist.empty:
            continue
        closes = hist["Close"].dropna()
        if len(closes) < 2:
            continue
        return closes
    return None


def check(data) -> CheckResult:
    if data is None:
        return CheckResult(name="technical_levels", verdict="unknown", detail="No market data available")

    closes = _fetch_close_series(data.ticker)
    if closes is None or len(closes) < min(_WINDOWS):
        return CheckResult(
            name="technical_levels", verdict="unknown",
            detail="Not enough price history for moving-average levels",
        )

    current = float(closes.iloc[-1])
    parts = []
    ma_data: dict[str, float] = {}
    for window in _WINDOWS:
        if len(closes) < window:
            continue
        ma = float(closes.tail(window).mean())
        pct_from_ma = (current / ma - 1) * 100
        position = "above" if current >= ma else "below"
        parts.append(f"{window}DMA ${ma:,.2f} ({position}, {pct_from_ma:+.1f}%)")
        ma_data[f"ma{window}"] = ma

    if not parts:
        return CheckResult(
            name="technical_levels", verdict="unknown",
            detail="Not enough price history for moving-average levels",
        )

    return CheckResult(
        name="technical_levels", verdict="info",
        detail=f"Price ${current:,.2f} vs " + "; ".join(parts),
        data={"current_price": current, **ma_data},
    )
