"""Dividend yield + 10-year cumulative return enrichment for watchlist rows.

Display-only data for watchlist.md's Dividend/10Y Return columns — not used
by any assessment check. Cached on the watchlist row and refreshed on demand via the
`refresh-watchlist-data` CLI command, not recomputed on every snapshot regen: these
numbers don't meaningfully change day to day, and a 10-year price-history fetch per
ticker is comparatively expensive to run on every Monitor/add/remove.

10Y Return is a total-return *approximation* — yfinance's auto_adjust=True history
folds dividends and splits into the adjusted close, which isn't the same as a precise
dividend-reinvestment calculation, but is close enough for a glanceable snapshot.
"""

from __future__ import annotations

from . import db, market_data, tickers

# No real sustainable equity/ETF dividend yield gets anywhere near this — observed in
# practice that yfinance's info['dividendYield'] occasionally returns garbage for a
# subset of tickers (e.g. 84%, 92%, 95% for GDX/MSFT/TSM in one real run) rather than
# a fraction/percent parsing ambiguity. Treat anything above this as bad data, not a
# real yield, and fall back to "—" rather than display a misleading number.
MAX_PLAUSIBLE_DIVIDEND_YIELD_PCT = 15.0


def fetch_dividend_yield_pct(ticker: str) -> float | None:
    data = market_data.fetch_ticker_data(ticker)
    if data is None:
        return None
    # Two Yahoo fields, two different scales, verified 2026-07-19 by reading
    # yfinance's own source (scrapers/quote.py's _fetch_info just passes through
    # Yahoo's raw value with zero scaling of its own — the inconsistency below is
    # Yahoo's, not yfinance's) and cross-checking against real dividendRate/price:
    #
    # - trailingAnnualDividendYield is a genuine fraction (needs *100) and is the more
    #   precise figure for individual stocks, but comes back 0.0/missing for most
    #   ETFs (HDV showed 0.0 despite a real ~2.9% yield).
    # - dividendYield is *already* a direct percent number (0.92 means 0.92%, not a
    #   fraction — confirmed against MSFT: dividendRate 3.64 / price 393.82 = 0.92%).
    #   Populated for both stocks and ETFs, but can be stale for recently-adjusted
    #   tickers (NVDA showed dividendYield=0.49, i.e. "0.49%", vs
    #   trailingAnnualDividendYield's far more accurate 0.0193% — NVDA's real yield is
    #   near-zero; 0.49% likely reflects data from before its 2024 stock split).
    #
    # Prefer the more precise trailing figure when Yahoo actually populated it;
    # fall back to the forward figure (which covers ETFs) otherwise.
    trailing = data.info.get("trailingAnnualDividendYield")
    if trailing:
        pct = round(float(trailing) * 100, 2)
    else:
        yld = data.info.get("dividendYield")
        if yld is None:
            return None
        pct = round(float(yld), 2)
    if pct > MAX_PLAUSIBLE_DIVIDEND_YIELD_PCT:
        return None
    return pct


def fetch_ten_year_return_pct(ticker: str) -> float | None:
    import yfinance as yf

    for candidate in (tickers.normalize(ticker), tickers.asx_variant(ticker)):
        try:
            hist = yf.Ticker(candidate).history(period="10y", auto_adjust=True)
        except Exception:
            continue
        if hist.empty or len(hist) < 2:
            continue
        start = float(hist["Close"].iloc[0])
        end = float(hist["Close"].iloc[-1])
        if start == 0:
            continue
        return round((end / start - 1) * 100, 1)
    return None


def refresh_watchlist_return_data(conn) -> int:
    """Fetch and store dividend yield + 10Y return for every watchlist row (both the
    main watchlist and Post-Crash AI Watch — bucket doesn't matter here). Returns the
    number of rows where at least one value was found."""
    updated = 0
    for row in db.get_all_watchlist(conn):
        dividend = fetch_dividend_yield_pct(row["ticker"])
        ten_year = fetch_ten_year_return_pct(row["ticker"])
        db.update_watchlist_return_data(conn, row["ticker"], row["bucket"], dividend, ten_year)
        if dividend is not None or ten_year is not None:
            updated += 1
    return updated
