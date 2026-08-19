"""Marker 8 -- insider selling, aggregate 365-day trend against the dynamic hot
watchlist. Reuses mytrader.openinsider's screener scraper directly (a pure
data-fetch function, not coupled to Goat's own per-filing holdings-watch
orchestration) with the new filing_date_days param this package added. This is
an aggregate sum over a year, not a per-filing alert -- do not confuse with
goat.insider_scan.run_holdings_watch, which is a different check shape.

NOTE: the scraper moved from goat/goat/openinsider.py to mytrader/openinsider.py
2026-08-19 -- this import updated accordingly, no behavior change."""

from __future__ import annotations

import sqlite3

from mytrader import openinsider
from mytrader.checks import CheckResult

from . import config, db


def check_insider_trend(conn: sqlite3.Connection) -> list[CheckResult]:
    watchlist = db.get_hot_watchlist(conn)
    if not watchlist:
        return []
    tickers = [row["ticker"] for row in watchlist]

    purchases = openinsider.fetch_screener_filings(
        tickers, "P", config.SIGNALS_INSIDER_TREND_MIN_VALUE,
        filing_date_days=config.SIGNALS_INSIDER_TREND_LOOKBACK_DAYS,
    )
    sales = openinsider.fetch_screener_filings(
        tickers, "S", config.SIGNALS_INSIDER_TREND_MIN_VALUE,
        filing_date_days=config.SIGNALS_INSIDER_TREND_LOOKBACK_DAYS,
    )
    if purchases is None and sales is None:
        return [CheckResult(name="insider_trend", verdict="unknown", detail="OpenInsider fetch failed for both purchases and sales")]

    totals: dict[str, dict[str, float]] = {t: {"bought": 0.0, "sold": 0.0} for t in tickers}
    for row in purchases or []:
        totals[row["ticker"]]["bought"] += row["value"]
    for row in sales or []:
        totals[row["ticker"]]["sold"] += row["value"]

    results: list[CheckResult] = []
    for ticker, amounts in totals.items():
        bought, sold = amounts["bought"], amounts["sold"]
        if bought == 0 and sold == 0:
            continue
        ratio = sold / bought if bought > 0 else (float("inf") if sold > 0 else 0.0)
        detail = (
            f"{ticker}: ${sold:,.0f} sold vs ${bought:,.0f} bought, trailing "
            f"{config.SIGNALS_INSIDER_TREND_LOOKBACK_DAYS} days"
        )
        verdict = "flag" if ratio >= config.SIGNALS_INSIDER_TREND_NET_SELL_FLAG_RATIO else "ok"
        results.append(CheckResult(
            name="insider_trend", verdict=verdict, detail=detail,
            data={"ticker": ticker, "bought": bought, "sold": sold, "ratio": ratio},
        ))
    return results
