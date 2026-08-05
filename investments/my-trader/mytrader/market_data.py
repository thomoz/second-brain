"""yfinance data fetch wrapper for the my-trader assessment engine."""

from __future__ import annotations

from contextlib import contextmanager
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


_cache: dict[str, TickerData | None] | None = None


@contextmanager
def cached_session():
    """Enable an in-memory per-run cache for fetch_ticker_data. Off by default (module
    global stays None) — Find and the existing test suite are unaffected unless this
    context is explicitly entered. Monitor uses this to avoid an O(n^2) yfinance call
    blowup: concentration.check() re-fetches every existing holding for every ticker
    it assesses, and Monitor calls run_assessment() once per holding+watchlist row."""
    global _cache
    _cache = {}
    try:
        yield
    finally:
        _cache = None


def _looks_valid(info: dict[str, Any]) -> bool:
    # yfinance's failure-mode info dict for a symbol that doesn't exist on the primary
    # lookup (e.g. an ASX-only ticker tried bare, without .AX) still comes back with
    # quoteType set to the literal string "NONE" -- truthy, so `bool(...)` alone was
    # fooled into treating it as valid data and never triggering the .AX fallback
    # below. Found live 2026-08-04: XMET (Betashares Energy Transition Metals ETF,
    # ASX-only) silently assessed against a garbage info dict -- no PE, no balance
    # sheet, no sector, "Not an ETF" despite genuinely being one -- while
    # crash_windows.py/return_data.py (which each retry both variants independently
    # for price history) got real ASX data, making the bug easy to miss.
    return info.get("regularMarketPrice") is not None or info.get("quoteType") not in (None, "NONE")


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
    primary lookup returns no info. Returns None if both fail. Cached for the
    duration of a cached_session() context, if one is active."""
    normalized = tickers.normalize(ticker)
    if _cache is not None and normalized in _cache:
        return _cache[normalized]
    data = _fetch_one(normalized)
    if data is None:
        data = _fetch_one(tickers.asx_variant(ticker))
    if _cache is not None:
        _cache[normalized] = data
    return data


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
