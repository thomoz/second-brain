"""Orchestrator for the OpenInsider Form 4 scan -- Goat insider trading scanner.
Two halves: holdings-watch (P/S filings on tickers Shaun currently holds) and
discovery (market-wide $25k+ open-market purchases, staged into the existing
goat_pending_candidates table like every other Goat candidate source). Dedup is
by filing identity (goat_insider_filings_seen), not goat_alert_history -- see
NOTES in .agent/plans/insider-trading-scanner.md for why a discrete one-time
event doesn't fit that table's open/acknowledge semantics."""

from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta
from typing import Any

from mytrader import db as mt_db

from . import config, db, openinsider


def _within_lookback(trade_date_str: str, lookback_days: int) -> bool:
    try:
        trade_date = datetime.strptime(trade_date_str, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return True
    return (date.today() - trade_date).days <= lookback_days


def _pct_owned_change_clause(row: dict) -> str:
    """Informational context, not a filter (same precedent as heartbeat_scan's
    fundamentals survival context) -- a $2M sale reads very differently against
    a $2.5M stake than against a $100M one. Omitted entirely when OpenInsider's
    ΔOwn is unparsable/"New" (no prior reported stake, per
    openinsider._parse_pct_owned_change) rather than guessing."""
    pct = row.get("pct_owned_change")
    if pct is None:
        return ""
    return f" ({abs(pct):.0f}% of position)"


def _prior_sale_count(conn: sqlite3.Connection, ticker: str, insider_name: str, trade_date_str: str) -> int:
    """Prior 'S' filings by this insider/ticker in the trailing
    GOAT_INSIDER_SALE_LOOKBACK_DAYS before trade_date_str -- drives which
    threshold applies (see run_holdings_watch)."""
    try:
        trade_date_obj = datetime.strptime(trade_date_str, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return 0  # can't establish a window -- treat as a first sale (stricter threshold)
    start_date = (trade_date_obj - timedelta(days=config.GOAT_INSIDER_SALE_LOOKBACK_DAYS)).isoformat()
    return db.count_insider_sales_since(
        conn, ticker=ticker, insider_name=insider_name,
        start_date=start_date, before_date=trade_date_str,
    )


def run_holdings_watch(conn: sqlite3.Connection) -> dict[str, Any]:
    held_tickers = sorted({row["ticker"] for row in mt_db.get_all_holdings(conn)})
    if not held_tickers:
        return {"checked_holdings": 0, "new_alerts": [], "recent_filings": []}

    purchases = openinsider.fetch_screener_filings(
        held_tickers, "P", config.GOAT_INSIDER_PURCHASE_MIN_VALUE
    )
    sales = openinsider.fetch_screener_filings(
        held_tickers, "S", config.GOAT_INSIDER_SALE_MIN_VALUE
    )
    if purchases is None and sales is None:
        print("[goat-insider-scan] OpenInsider screener fetch failed for both purchases and sales")
        return {"checked_holdings": len(held_tickers), "new_alerts": [], "recent_filings": []}

    new_alerts: list[dict[str, Any]] = []
    for row in (purchases or []) + (sales or []):
        if not _within_lookback(row.get("trade_date", ""), config.GOAT_INSIDER_HOLDINGS_WATCH_LOOKBACK_DAYS):
            continue
        dedup_key = openinsider.build_dedup_key(row)
        newly_seen = db.insert_goat_insider_filing_seen(
            conn, dedup_key=dedup_key, ticker=row["ticker"],
            filing_date=row.get("filing_date", ""), trade_date=row.get("trade_date", ""),
            insider_name=row.get("insider_name", ""), trade_type=row["trade_type_code"],
            value=row["value"], kind="holdings_watch", pct_owned_change=row.get("pct_owned_change"),
        )
        if not newly_seen:
            continue

        # Sales are gated on % of the insider's own position, not dollar value
        # (Shaun 2026-08-17 -- $25k/$100k floors are meaningless against a
        # large-cap exec's stake). Every sale is still recorded above
        # regardless of this gate, so count_insider_sales_since sees the full
        # history even for sales that never alerted -- that's what makes the
        # "repeated small sales" pattern detectable at all.
        prior_sales = 0
        if row["trade_type_code"] == "S":
            prior_sales = _prior_sale_count(
                conn, row["ticker"], row.get("insider_name", ""), row.get("trade_date", "")
            )
            threshold = (
                config.GOAT_INSIDER_SALE_PCT_THRESHOLD_REPEAT if prior_sales > 0
                else config.GOAT_INSIDER_SALE_PCT_THRESHOLD_FIRST
            )
            pct = row.get("pct_owned_change")
            # Fail open on an unparsable %, same philosophy as _within_lookback
            # -- never silently drop a real sale filing over a parsing gap.
            if pct is not None and abs(pct) < threshold:
                continue

        action = "bought" if row["trade_type_code"] == "P" else "sold"
        reason_clause = (
            f" -- {prior_sales + 1}th sale by this insider on this ticker in "
            f"{config.GOAT_INSIDER_SALE_LOOKBACK_DAYS} days, cumulative exit risk"
            if prior_sales > 0 else ""
        )
        detail = (
            f"{row.get('insider_name', 'Unknown insider')} ({row.get('title', '')}) "
            f"{action} ${row['value']:,.0f} of {row['ticker']}{_pct_owned_change_clause(row)} "
            f"on {row.get('trade_date', 'unknown date')}{reason_clause}"
        )
        new_alerts.append({"ticker": row["ticker"], "message": detail})

    return {
        "checked_holdings": len(held_tickers),
        "new_alerts": new_alerts,
        "recent_filings": [dict(r) for r in db.get_recent_insider_filings_seen(conn, kind="holdings_watch")],
    }


def run_discovery_scan(conn: sqlite3.Connection) -> dict[str, Any]:
    rows = openinsider.fetch_discovery_purchases()
    if rows is None:
        print("[goat-insider-scan] OpenInsider discovery fetch failed")
        rows = []

    new_candidates: list[dict[str, Any]] = []
    for row in rows:
        if not _within_lookback(row.get("trade_date", ""), config.GOAT_INSIDER_DISCOVERY_LOOKBACK_DAYS):
            continue
        ticker = row["ticker"]
        if ticker in config.GOAT_BANNED_TICKERS:
            continue
        if mt_db.get_holding_row(conn, ticker) is not None:
            continue
        if mt_db.get_watchlist_row(conn, ticker) is not None:
            continue
        if db.get_goat_pending_candidate(conn, ticker) is not None:
            continue

        dedup_key = openinsider.build_dedup_key(row)
        newly_seen = db.insert_goat_insider_filing_seen(
            conn, dedup_key=dedup_key, ticker=ticker,
            filing_date=row.get("filing_date", ""), trade_date=row.get("trade_date", ""),
            insider_name=row.get("insider_name", ""), trade_type=row["trade_type_code"],
            value=row["value"], kind="discovery",
        )
        if not newly_seen:
            continue

        signal_detail = (
            f"{row.get('insider_name', 'Unknown insider')} ({row.get('title', '')}) "
            f"bought ${row['value']:,.0f} of {ticker}{_pct_owned_change_clause(row)} "
            f"on {row.get('trade_date', 'unknown date')}"
        )
        db.insert_goat_pending_candidate(
            conn, ticker=ticker, sector_label="Insider Buy",
            signal_detail=signal_detail, source="goat_insider_discovery",
        )
        new_candidates.append({"ticker": ticker, "sector_label": "Insider Buy", "detail": signal_detail})

    return {
        "new_candidates": new_candidates,
        "pending_candidates": [
            dict(r) for r in db.get_all_goat_pending_candidates(conn) if r["source"] == "goat_insider_discovery"
        ],
    }


def render_insider_scan_report(watch_result: dict[str, Any], discovery_result: dict[str, Any]) -> str:
    lines = [
        "# Insider Trading Scan — OpenInsider",
        "",
        "Auto-generated by Goat's daily insider scan -- overwritten every run. "
        "Advisor notes only; no trade action is ever suggested here (see SOUL.md).",
        "",
        "## Holdings Watch",
        f"Checked {watch_result['checked_holdings']} held ticker(s) for open-market "
        "P/S insider filings.",
        "",
    ]
    if watch_result["new_alerts"]:
        for a in watch_result["new_alerts"]:
            lines.append(f"- **{a['ticker']}** -- {a['message']}")
    else:
        lines.append("No new insider activity on current holdings.")

    lines += [
        "",
        "## Discovery Candidates — Pending Review",
        "Market-wide $25k+ open-market insider purchases, staged for explicit review. "
        "Review each one and either `promote-candidate` (writes it into my-trader's "
        "real watchlist, labeled Goat-approved) or `dismiss-candidate` (discards it). "
        "Edits here are overwritten on the next `scan-insiders` run.",
        "",
        "| Ticker | Sector | Signal | Flagged |",
        "|--------|--------|--------|---------|",
    ]
    for row in discovery_result["pending_candidates"]:
        lines.append(
            f"| {row['ticker']} | {row['sector_label']} | {row['signal_detail']} "
            f"| {row['flagged_at'][:10]} |"
        )
    lines += ["", f"Last auto-generated: {date.today().isoformat()}."]
    return "\n".join(lines) + "\n"


def write_insider_scan_report(watch_result: dict[str, Any], discovery_result: dict[str, Any]) -> None:
    config.GOAT_INSIDER_SCAN_REPORT_PATH.write_text(
        render_insider_scan_report(watch_result, discovery_result), encoding="utf-8"
    )
