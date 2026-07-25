"""Historical broad-market crash-window drawdown lookup.

Fixed, well-documented market-wide drawdowns (not company-specific dips) so the same
windows apply to every ticker consistently. Peak/trough values for a fixed historical
window never change once computed, so results are deterministic. A ticker that didn't
exist yet for a given window (e.g. FIVE, IPO'd 2012, has no 2008 data) is simply
skipped for that window rather than erroring.

Built 2026-07-25 after manually running this exact peak-to-trough calculation ad hoc
for a dollar-store comparison (DG/DLTR/FIVE/OLLI) earlier the same week — generalizing
it into a reusable check rather than a one-off script.
"""

from __future__ import annotations

from . import tickers

CRASH_WINDOWS: list[tuple[str, str, str]] = [
    ("2008 financial crisis", "2007-10-01", "2009-03-09"),
    ("Dec 2018 correction", "2018-08-01", "2018-12-31"),
    ("COVID crash (2020)", "2020-01-01", "2020-04-15"),
    ("2022 bear market", "2021-10-01", "2022-12-31"),
]


def _drawdown(close, start: str, end: str) -> float | None:
    window = close[start:end]
    if window.empty:
        return None
    peak = float(window.max())
    if peak == 0:
        return None
    peak_date = window.idxmax()
    trough_window = close.loc[peak_date:end]
    if trough_window.empty:
        return None
    trough = float(trough_window.min())
    return round((trough / peak - 1) * 100, 1)


def _fetch_close_series(ticker: str):
    """Long-range adjusted-close history for `ticker`, or None if unavailable. Split
    out from fetch_crash_drawdowns (see test_crash_windows.py) so it can be unit
    tested directly — conftest.py's global _no_real_crash_drawdown_fetch fixture
    stubs fetch_crash_drawdowns itself for every other test in the suite, the same
    pattern return_data.py's _fetch_cumulative_return_pct/fetch_recent_return_pct
    split already uses."""
    import yfinance as yf

    for candidate in (tickers.normalize(ticker), tickers.asx_variant(ticker)):
        try:
            hist = yf.Ticker(candidate).history(start="2007-01-01", auto_adjust=True)
        except Exception:
            continue
        if hist.empty:
            continue
        close = hist["Close"]
        if getattr(close.index, "tz", None) is not None:
            close.index = close.index.tz_localize(None)
        return close
    return None


def fetch_crash_drawdowns(ticker: str) -> list[dict[str, object]] | None:
    """Peak-to-trough drawdown for `ticker` over each window in CRASH_WINDOWS.
    Returns None if no price history is available at all; otherwise a list with one
    entry per window the ticker has data for (windows before IPO are omitted)."""
    close = _fetch_close_series(ticker)
    if close is None:
        return None

    results = []
    for label, start, end in CRASH_WINDOWS:
        pct = _drawdown(close, start, end)
        if pct is not None:
            results.append({"label": label, "drawdown_pct": pct})
    return results if results else None
