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


def fetch_current_price(ticker: str) -> float | None:
    """Current price for a holding, via the same fetch_ticker_data() path used
    everywhere else (cached within a cached_session() context). Moved here from
    snapshot.py's private _current_price() (2026-08-13) so monitor.py's Holdings
    report can show live price/P&L per holding without a second, independently
    -drifting implementation."""
    data = fetch_ticker_data(ticker)
    if data is None:
        return None
    return data.info.get("regularMarketPrice") or data.info.get("currentPrice")


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


def fetch_balance_sheet_financials(ticker: str) -> dict[str, float] | None:
    """Deeper fallback for entity types where yfinance's .info convenience ratios
    (debtToEquity/currentRatio/returnOnEquity) are empty but the underlying
    balance_sheet/financials statements have real numbers one level deeper --
    confirmed 2026-08-06 against GROW.L (Molten Ventures, a UK investment trust):
    .info's three ratio fields were all None, but Total Debt, Stockholders Equity,
    and Net Income were all present in the statements. checks/balance_sheet.py
    already has a documented ROE-only fallback for this class of gap (banks,
    verified 2026-07-19 against NU) -- this just extends where that ROE (and,
    when available, debt/equity) can come from, rather than giving up to
    "unknown" when real data exists.

    Returns a dict shaped like the fields it's standing in for -- "debtToEquity"
    in the same percent-of-equity units as yfinance's own .info field,
    "returnOnEquity" as a fraction (not *100) -- so callers can treat these
    exactly like .info.get(...) results. Returns None if the statements are
    empty or missing the needed rows (not every ticker has this data either --
    same graceful degradation as everywhere else in this module)."""
    import yfinance as yf

    try:
        t = yf.Ticker(ticker)
        bs = t.balance_sheet
        if bs is None or bs.empty:
            return None
        equity = bs.loc["Stockholders Equity"].iloc[0] if "Stockholders Equity" in bs.index else None
        if equity is None or float(equity) == 0:
            return None

        result: dict[str, float] = {}
        if "Total Debt" in bs.index:
            total_debt = bs.loc["Total Debt"].iloc[0]
            if total_debt is not None:
                result["debtToEquity"] = round(float(total_debt) / float(equity) * 100, 2)

        fin = t.financials
        if fin is not None and not fin.empty and "Net Income" in fin.index:
            net_income = fin.loc["Net Income"].iloc[0]
            if net_income is not None:
                result["returnOnEquity"] = float(net_income) / float(equity)

        return result or None
    except Exception:
        return None
