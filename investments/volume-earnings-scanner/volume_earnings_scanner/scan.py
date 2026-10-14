"""Orchestrator for the Volume-Spike + Record-Earnings Scan.

Each run scores 1/N of the screened small/micro-cap universe (rotating by calendar
date). Volume spike and record earnings are independent (OR) triggers, not an AND
gate (Decision #2) -- either alone stages + alerts; a ticker that fires both in the
same run is staged with signal_type="both" and called out specially so Shaun can see
the strongest case at a glance.

Mirrors ai_resistant_moat_scanner/scan.py's run_scan shape: a per-ticker try/except
so one bad ticker can't sink the run, and a market_data.cached_session() to prevent
an O(n) yfinance re-fetch storm.
"""

from __future__ import annotations

import sqlite3
import time
from typing import Any

from mytrader import db as mt_db
from mytrader import market_data
from scripts.ethical_filter import check_ticker as ethical_check

from . import config, db, earnings_signal, price_history, universe, volume_signal


def passes_precise_floor(data: market_data.TickerData | None) -> bool:
    """Precise per-ticker liquidity/market-cap/price re-test against the real
    yfinance .info dict, never trusted from the coarse Finviz screen text columns
    -- same two-pass idiom as mytrader.cash_value_scan._enrich_universe."""
    if data is None:
        return False
    info = data.info
    avg_volume = info.get("averageVolume")
    if avg_volume is None or avg_volume < config.VE_MIN_AVG_VOLUME:
        return False
    market_cap = info.get("marketCap")
    if market_cap is None or not (config.VE_MIN_MARKET_CAP_USD <= market_cap <= config.VE_MAX_MARKET_CAP_USD):
        return False
    price = info.get("regularMarketPrice") or info.get("currentPrice")
    if price is None or price < config.VE_MIN_PRICE_USD:
        return False
    return True


def _signal_type(volume_interesting: bool, earnings_interesting: bool) -> str | None:
    if volume_interesting and earnings_interesting:
        return "both"
    if volume_interesting:
        return "volume"
    if earnings_interesting:
        return "earnings"
    return None


def run_scan(conn: sqlite3.Connection) -> dict[str, Any]:
    universe_data = universe.get_scan_universe(conn)
    finviz_failed = bool(universe_data.get("finviz_failed")) and not universe_data["screened"]

    staged = {r["ticker"] for r in db.get_all_ve_pending_candidates(conn)}
    held = {r["ticker"] for r in mt_db.get_all_holdings(conn)}
    watched = {r["ticker"] for r in mt_db.get_all_watchlist(conn)}

    company_by_ticker = {
        r["ticker"]: (r.get("company") or "") for r in universe_data["screened"]
    }

    scanned = 0
    rows: list[dict[str, Any]] = []
    new_candidates: list[dict[str, Any]] = []

    with market_data.cached_session():
        for ticker in universe_data["slice_today"]:
            try:
                excluded, review_reason = ethical_check(ticker)
                if excluded:
                    continue  # defense contractor -- dropped, never shown

                frame = price_history.fetch_close_volume_history(
                    ticker, config.VE_PRICE_HISTORY_LOOKBACK_DAYS
                )
                volume_result = (
                    volume_signal.check_volume_spike(ticker, frame["Close"], frame["Volume"])
                    if frame is not None
                    else None
                )

                eps_history = earnings_signal.fetch_quarterly_eps_history(ticker)
                earnings_result = earnings_signal.check_record_earnings(ticker, eps_history)

                scanned += 1
                volume_interesting = volume_result is not None and volume_result.verdict == "interesting"
                earnings_interesting = earnings_result.verdict == "interesting"

                tags: list[str] = []
                if ticker in held:
                    tags.append("held")
                elif ticker in watched:
                    tags.append("watchlist")
                if ticker in staged:
                    tags.append("staged")
                if review_reason:
                    tags.append(review_reason)

                row = {
                    "ticker": ticker,
                    "company": company_by_ticker.get(ticker, ""),
                    "volume_result": volume_result,
                    "earnings_result": earnings_result,
                    "tags": tags,
                }
                rows.append(row)

                signal_type = _signal_type(volume_interesting, earnings_interesting)
                if signal_type is None:
                    continue
                if ticker in held or ticker in watched or ticker in staged:
                    continue

                data = market_data.fetch_ticker_data(ticker)
                if not passes_precise_floor(data):
                    continue

                details = []
                if volume_interesting and volume_result is not None:
                    details.append(volume_result.detail)
                if earnings_interesting:
                    details.append(earnings_result.detail)
                signal_detail = "; ".join(details)
                if signal_type == "both":
                    signal_detail = "BOTH SIGNALS -- " + signal_detail

                company_name = row["company"] or data.info.get("longName") or ""
                db.insert_ve_pending_candidate(
                    conn, ticker=ticker, signal_type=signal_type,
                    signal_detail=signal_detail, company_name=company_name,
                )
                new_candidates.append({
                    "ticker": ticker, "company": company_name,
                    "signal_type": signal_type, "detail": signal_detail,
                })
                staged.add(ticker)
                time.sleep(config.VE_FETCH_DELAY_SECONDS)
            except Exception as e:
                print(f"[volume-earnings-scan] error on {ticker}: {e}")

    return {
        "scanned": scanned,
        "slice_index": universe_data["slice_index"],
        "slices": config.VE_UNIVERSE_SLICES,
        "screened_total": len(universe_data["screened"]),
        "finviz_failed": finviz_failed,
        "rows": rows,
        "new_candidates": new_candidates,
        "pending_candidates": [dict(r) for r in db.get_all_ve_pending_candidates(conn)],
    }
