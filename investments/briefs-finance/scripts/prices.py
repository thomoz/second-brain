"""yfinance OHLCV wrapper for stock and S&P 500 price lookups."""

from __future__ import annotations

from datetime import date, timedelta

from .config import PRICE_WINDOW_DAYS, SP500_TICKER


def _is_near_future(target: date, buffer_days: int = 2) -> bool:
    from datetime import date as _date
    delta = (target - _date.today()).days
    return delta >= -buffer_days


def get_close_on_or_after(ticker: str, target: date, window: int = PRICE_WINDOW_DAYS) -> float | None:
    """Return closing price on or after target date (finds next trading day within window)."""
    if _is_near_future(target):
        return None
    import yfinance as yf
    end = target + timedelta(days=window)
    try:
        hist = yf.Ticker(ticker).history(
            start=target.isoformat(), end=end.isoformat(), auto_adjust=True
        )
        if hist.empty:
            return None
        return float(hist["Close"].iloc[0])
    except Exception:
        return None


def get_close_on_or_before(ticker: str, target: date, window: int = PRICE_WINDOW_DAYS, auto_adjust: bool = True) -> float | None:
    """Return closing price on or before target date (looks back within window)."""
    import yfinance as yf
    start = target - timedelta(days=window)
    try:
        hist = yf.Ticker(ticker).history(
            start=start.isoformat(),
            end=(target + timedelta(days=1)).isoformat(),
            auto_adjust=auto_adjust,
        )
        if hist.empty:
            return None
        return float(hist["Close"].iloc[-1])
    except Exception:
        return None


def get_sp500_on_or_after(target: date) -> float | None:
    return get_close_on_or_after(SP500_TICKER, target)


def compute_return_pct(start_price: float | None, end_price: float | None) -> float | None:
    """Return percentage return, or None if either price is missing."""
    if start_price is None or end_price is None or start_price == 0:
        return None
    return round((end_price - start_price) / start_price * 100, 4)


def get_asx_fallback(ticker: str, target: date) -> float | None:
    """Try appending .AX suffix if primary ticker returned None."""
    asx_ticker = ticker.upper() + ".AX"
    return get_close_on_or_after(asx_ticker, target)
