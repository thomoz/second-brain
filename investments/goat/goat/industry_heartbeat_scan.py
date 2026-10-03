"""Industry-level stock heartbeat scan -- Part B-3 of
.agent/plans/goat-industry-pipeline.md. Gated on industries whose ETF is
CURRENTLY IN A FRESH BREAKOUT (not just rising) -- a tighter gate than the
sector-level heartbeat scan's "any rising sector" filter, since the industry
universe is much larger (143 vs. 11) and an ungated scan here would mean far
more yfinance calls per run. Per the orchestrator-independence pattern (see
heartbeat_scan.py's own module docstring precedent), this recomputes its own
gate rather than depending on monitor.run_industry_scan's prior output -- the
`industries` override lets a caller (the --industries CLI flag) bypass gate
computation entirely."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from mytrader import db as mt_db
from mytrader import market_data

from . import config, db, fundamentals_context, heartbeat, industry_constituents, industry_rotation, price_history

_SYDNEY_TZ = ZoneInfo("Australia/Sydney")


def _today_sydney() -> str:
    """Module-private copy, not cross-imported -- per this codebase's convention
    (see monitor.py/heartbeat_scan.py's own identical docstrings)."""
    return datetime.now(_SYDNEY_TZ).date().isoformat()


def _compute_gated_industries() -> list[str]:
    closes = industry_rotation.fetch_all_industry_closes()
    gated = []
    for ticker, industry_label in config.GOAT_INDUSTRY_ETFS.items():
        close = closes.get(ticker)
        if close is None:
            continue
        check = industry_rotation.check_industry_breakout(ticker, industry_label, close)
        if check.verdict == "interesting":
            gated.append(industry_label)
    return gated


def run_industry_heartbeat_scan(conn: sqlite3.Connection, industries: list[str] | None = None) -> dict[str, Any]:
    gated_industries = industries if industries is not None else _compute_gated_industries()

    scanned = 0
    new_candidates: list[dict[str, Any]] = []
    for industry_label in gated_industries:
        constituents = industry_constituents.get_or_refresh_industry_constituents(conn, industry_label)
        for c in constituents:
            ticker = c["ticker"]
            company_name = c["company"]
            try:
                frame = price_history.fetch_close_volume_history(
                    ticker, config.GOAT_HEARTBEAT_HISTORY_LOOKBACK_DAYS
                )
                if frame is None:
                    print(f"[goat-industry-heartbeat-scan] no price history for {ticker}, skipping")
                    continue
                scanned += 1
                close = frame["Close"]
                volume = frame["Volume"]

                check = heartbeat.check_heartbeat_breakout(ticker, industry_label, close, volume)
                if check.verdict != "interesting":
                    continue

                data = market_data.fetch_ticker_data(ticker)
                context = fundamentals_context.compute_survival_context(ticker, data)
                if context["insolvency_risk"]:
                    print(f"[goat-industry-heartbeat-scan] {ticker} suppressed -- near-term insolvency risk")
                    continue

                if mt_db.get_holding_row(conn, ticker) is not None:
                    continue
                if mt_db.get_watchlist_row(conn, ticker) is not None:
                    continue
                if db.get_goat_pending_candidate(conn, ticker) is not None:
                    continue

                exchange_name = data.info.get("fullExchangeName") or data.info.get("exchange")
                signal_detail = f"{check.detail}; survival context: {context['summary']}"
                db.insert_goat_pending_candidate(
                    conn, ticker=ticker, sector_label=industry_label,
                    signal_detail=signal_detail, source="goat_industry_heartbeat_scan",
                    company_name=company_name, exchange=exchange_name,
                )
                breakout_status = (
                    "no breakout yet" if check.data.get("pct_below_base_high", 0) > 0
                    else "may be breaking out now"
                )
                notify_detail = (
                    f"{config.GOAT_HEARTBEAT_MIN_DURATION_DAYS} days of consolidation, {breakout_status}"
                )
                new_candidates.append({
                    "ticker": ticker, "sector_label": industry_label,
                    "detail": signal_detail, "notify_detail": notify_detail, "company": company_name,
                })
            except Exception as e:
                print(f"[goat-industry-heartbeat-scan] error checking {ticker}: {e}")

    return {
        "scanned": scanned,
        "gated_industries": sorted(gated_industries),
        "new_candidates": new_candidates,
        "pending_candidates": [
            dict(r) for r in db.get_all_goat_pending_candidates(conn)
            if r["source"] == "goat_industry_heartbeat_scan"
        ],
    }


def render_industry_heartbeat_candidates_report(result: dict[str, Any]) -> str:
    lines = [
        "# Industry Heartbeat Candidates — Pending Review",
        "",
        "Auto-generated by Goat's industry heartbeat scan -- a stock inside an "
        "industry currently in a fresh 50DMA breakout (per industry-ranking.md / "
        "industry-candidates-pending-review.md) sitting in a tight, smooth "
        "sideways base, with fundamentals survival context attached for you to "
        "judge yourself. Scans each gated industry's cached US (Finviz) + ASX "
        "(curated) constituent list. Review each one and either "
        "`promote-candidate` (writes it into my-trader's real watchlist, labeled "
        "Goat-approved) or `dismiss-candidate` (discards it). Edits here are "
        "overwritten on the next `scan-industry-heartbeat` run.",
        "",
        f"Scanned {result['scanned']} ticker(s) across "
        f"{len(result['gated_industries'])} gated industry(ies): "
        f"{', '.join(result['gated_industries']) if result['gated_industries'] else 'none'}.",
        "",
        "| Ticker | Company | Exchange | Industry | Signal | Flagged |",
        "|--------|---------|----------|----------|--------|---------|",
    ]
    for row in result["pending_candidates"]:
        company = (row.get("company_name") or "n/a").replace("|", "/")
        exchange = (row.get("exchange") or "n/a").replace("|", "/")
        lines.append(
            f"| {row['ticker']} | {company} | {exchange} | {row['sector_label']} "
            f"| {row['signal_detail']} | {row['flagged_at'][:10]} |"
        )
    lines += ["", f"Last auto-generated: {_today_sydney()}."]
    return "\n".join(lines) + "\n"


def write_industry_heartbeat_candidates_report(result: dict[str, Any]) -> None:
    config.GOAT_INDUSTRY_HEARTBEAT_CANDIDATES_MD_PATH.write_text(
        render_industry_heartbeat_candidates_report(result), encoding="utf-8"
    )
