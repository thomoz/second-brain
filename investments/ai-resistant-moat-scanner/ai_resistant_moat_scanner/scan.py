"""Orchestrator for the AI-Resistant Moat Scan.

Each run scores 1/N of the screened universe (rotating by calendar date) + every seed
name + every currently-staged name. Held / watchlisted tickers are scored and shown
(tagged) but never staged -- the report is meant to show your own holdings' moat
scores too, unlike goat-heartbeat which skips them entirely. Ethical-filter drops
(DEFENSE_TICKERS) are removed entirely and never shown.

Mirrors goat.heartbeat_scan.run_heartbeat_scan + cash_value_scan.run_scan /
_enrich_universe: a per-ticker try/except so one bad ticker can't sink the run, and a
market_data.cached_session() to prevent an O(n) yfinance re-fetch storm.
"""

from __future__ import annotations

import sqlite3
import time
from typing import Any

from mytrader import db as mt_db
from mytrader import market_data, sec_filings
from scripts.ethical_filter import check_ticker as ethical_check

from . import config, db, qualitative, quant, scoring, universe


def run_scan(conn: sqlite3.Connection) -> dict[str, Any]:
    # Warm the sec_cik_map on a fresh DB (superinvestor scan_edgar:227-230 pattern).
    try:
        sec_filings.get_cik(conn, "AAPL")
    except Exception:
        pass

    universe_data = universe.get_scan_universe(conn)
    finviz_failed = bool(universe_data.get("finviz_failed")) and not universe_data["screened"]

    staged = {r["ticker"] for r in db.get_all_moat_pending_candidates(conn)}
    held = {r["ticker"] for r in mt_db.get_all_holdings(conn)}
    watched = {r["ticker"] for r in mt_db.get_all_watchlist(conn)}

    to_score = sorted(
        set(universe_data["slice_today"]) | set(config.MOAT_SEED_TICKERS) | staged
    )
    industry_by_ticker = {
        r["ticker"]: (r.get("industry") or "seed / not screened")
        for r in universe_data["screened"]
    }
    company_by_ticker = {
        r["ticker"]: (r.get("company") or "") for r in universe_data["screened"]
    }

    rows: list[dict[str, Any]] = []
    new_candidates: list[dict[str, Any]] = []

    with market_data.cached_session():
        for ticker in to_score:
            try:
                excluded, review_reason = ethical_check(ticker)
                if excluded:
                    continue  # defense contractor -- dropped, never shown

                data = market_data.fetch_ticker_data(ticker)
                if data is None:
                    print(f"[ai-moat-scan] no market data for {ticker}, skipping")
                    continue

                revenue_history = market_data.fetch_income_statement_history(data.ticker)
                qualitative_result = qualitative.get_qualitative(conn, ticker)
                extraction = qualitative_result["extraction"] if qualitative_result else {}

                quant_metrics = quant.compute_quant_metrics(data, extraction, revenue_history)
                if quant_metrics is None:
                    print(f"[ai-moat-scan] {ticker} below market-cap floor or no margin data, skipping")
                    continue

                tags: list[str] = []
                if ticker in held:
                    tags.append("held")
                elif ticker in watched:
                    tags.append("watchlist")
                if ticker in staged:
                    tags.append("staged")
                if review_reason:
                    tags.append(review_reason)

                row = scoring.assemble_row(
                    ticker,
                    industry_by_ticker.get(ticker, "seed / not screened"),
                    company_by_ticker.get(ticker) or (data.info.get("shortName") or ""),
                    quant_metrics,
                    qualitative_result,
                    tags,
                )

                if (
                    row["moat_score"] is not None
                    and row["moat_score"] >= config.MOAT_STAGE_THRESHOLD
                    and ticker not in held
                    and ticker not in watched
                    and ticker not in staged
                ):
                    db.insert_moat_pending_candidate(
                        conn,
                        ticker=ticker,
                        industry=row["industry"],
                        moat_score=row["moat_score"],
                        quant_score=row["quant_score"],
                        qualitative_score=row["qualitative_score"],
                        thesis=row["thesis"],
                        sub_scores_json=row["sub_scores_json"],
                    )
                    new_candidates.append({
                        "ticker": ticker,
                        "industry": row["industry"],
                        "moat_score": row["moat_score"],
                        "thesis": row["thesis"],
                    })
                    staged.add(ticker)

                rows.append(row)
                time.sleep(config.MOAT_FETCH_DELAY_SECONDS)
            except Exception as e:
                print(f"[ai-moat-scan] error on {ticker}: {e}")

    scored = sorted(
        [r for r in rows if r["moat_score"] is not None],
        key=lambda r: r["moat_score"],
        reverse=True,
    )
    unscored = [r for r in rows if r["moat_score"] is None]

    return {
        "scanned": len(rows),
        "slice_index": universe_data["slice_index"],
        "slices": config.MOAT_UNIVERSE_SLICES,
        "screened_total": len(universe_data["screened"]),
        "finviz_failed": finviz_failed,
        "rows": scored + unscored,
        "new_candidates": new_candidates,
        "pending_candidates": [dict(r) for r in db.get_all_moat_pending_candidates(conn)],
    }
