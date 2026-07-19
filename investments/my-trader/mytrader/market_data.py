"""yfinance data fetch wrapper for the my-trader assessment engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from . import tickers


@dataclass
class TickerData:
    ticker: str
    info: dict[str, Any]
    dividends: Any  # pandas.Series
    news: list[dict[str, Any]] = field(default_factory=list)
    calendar: dict[str, Any] = field(default_factory=dict)


def _looks_valid(info: dict[str, Any]) -> bool:
    return info.get("regularMarketPrice") is not None or bool(info.get("quoteType"))


def _fetch_one(ticker: str) -> TickerData | None:
    import yfinance as yf

    try:
        t = yf.Ticker(ticker)
        info = t.info or {}
        if not _looks_valid(info):
            return None
        return TickerData(
            ticker=ticker,
            info=info,
            dividends=t.dividends,
            news=t.news or [],
            calendar=t.calendar or {},
        )
    except Exception:
        return None


def fetch_ticker_data(ticker: str) -> TickerData | None:
    """Fetch yfinance data for a normalized ticker. Tries .AX fallback if the
    primary lookup returns no info. Returns None if both fail."""
    normalized = tickers.normalize(ticker)
    data = _fetch_one(normalized)
    if data is not None:
        return data
    return _fetch_one(tickers.asx_variant(ticker))


def fetch_fx_change_pct(base: str, quote: str = "AUD", period: str = "3mo") -> float | None:
    import yfinance as yf

    try:
        hist = yf.Ticker(f"{quote}{base}=X").history(period=period)
        if hist.empty:
            return None
        start = float(hist["Close"].iloc[0])
        end = float(hist["Close"].iloc[-1])
        if start == 0:
            return None
        return round((end - start) / start * 100, 2)
    except Exception:
        return None
