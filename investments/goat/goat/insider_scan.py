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

import pandas as pd
from mytrader import db as mt_db

from . import config, db, openinsider, price_history


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
            trade_date=row.get("trade_date"),
        )
        new_candidates.append({"ticker": ticker, "sector_label": "Insider Buy", "detail": signal_detail})

    return {
        "new_candidates": new_candidates,
        "pending_candidates": [
            dict(r) for r in db.get_all_goat_pending_candidates(conn) if r["source"] == "goat_insider_discovery"
        ],
    }


def _price_move_since(ticker: str, trade_date_str: str) -> dict[str, Any] | None:
    """% price move from the close on/after trade_date_str to the latest close,
    plus days elapsed. Returns None on unparsable date, a future date, or a
    price-fetch miss (delisted/no data) -- callers must treat that as "unknown",
    not zero."""
    try:
        trade_date_obj = datetime.strptime(trade_date_str, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None
    days_since = (date.today() - trade_date_obj).days
    if days_since < 0:
        return None

    # +10 days of slack so the fetch window still includes the trade date itself
    # even if it landed right at the start of a weekend/holiday run.
    close = price_history.fetch_close_history(ticker, days_since + 10)
    if close is None or close.empty:
        return None
    on_or_after = close[close.index >= pd.Timestamp(trade_date_obj)]
    if on_or_after.empty:
        return None
    start_price = float(on_or_after.iloc[0])
    latest_price = float(close.iloc[-1])
    if start_price == 0:
        return None
    return {
        "pct_change": (latest_price - start_price) / start_price * 100,
        "days_since": days_since,
    }


def _confirms_signal(trade_type_code: str, pct_change: float, threshold: float) -> bool:
    """Direction-aware only -- a buy is flagged on a rise, a sale on a fall.
    The contrarian direction is deliberately never flagged here (Shaun
    2026-08-18): that's a distinct read ("insider was early/wrong") he wants
    to judge himself, not have the tool call out as noteworthy."""
    if trade_type_code == "P":
        return pct_change >= threshold
    if trade_type_code == "S":
        return pct_change <= -threshold
    return False


def _price_note(pct_change: float, days_since: int, trade_type_code: str) -> str:
    flag = " \U0001F6A9 confirms signal" if _confirms_signal(
        trade_type_code, pct_change, config.GOAT_INSIDER_PRICE_FLAG_PCT
    ) else ""
    stale = (
        f"; {days_since}d -- may not reflect the insider signal anymore"
        if days_since > config.GOAT_INSIDER_PRICE_STALE_DAYS else ""
    )
    return f"{pct_change:+.1f}% since trade{flag}{stale}"


def compute_discovery_price_performance(
    conn: sqlite3.Connection, pending_candidates: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Annotates each discovery candidate with a 'price_note' field (network
    call per row, via yfinance) -- kept separate from run_discovery_scan so
    that function stays DB-only and cheap to test/call on every dedup check.

    Also sets 'newly_flagged' and persists price_flag_notified the first time
    a ticker's move crosses the confirms-signal threshold (Shaun 2026-08-18:
    a report-only flag was easy to miss for days) -- guarded by the DB column
    so the WhatsApp ping fires once per ticker, not every run it stays up."""
    for row in pending_candidates:
        trade_date = row.get("trade_date")
        move = _price_move_since(row["ticker"], trade_date) if trade_date else None
        if move is None:
            row["price_note"] = "price unavailable"
            row["newly_flagged"] = False
            continue
        row["price_note"] = _price_note(move["pct_change"], move["days_since"], "P")
        flagged = _confirms_signal("P", move["pct_change"], config.GOAT_INSIDER_PRICE_FLAG_PCT)
        row["newly_flagged"] = flagged and not row.get("price_flag_notified")
        if row["newly_flagged"]:
            db.mark_pending_candidate_price_flag_notified(conn, row["ticker"])
    return pending_candidates


def compute_holdings_watch_price_performance(
    conn: sqlite3.Connection, recent_filings: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Same as compute_discovery_price_performance but direction-aware per
    row's own trade_type (P or S), since Holdings Watch filings mix buys and
    sells, and guarded per-filing (dedup_key) rather than per-ticker, since a
    ticker can have multiple tracked filings."""
    for row in recent_filings:
        trade_date = row.get("trade_date")
        trade_type = row.get("trade_type", "")
        move = _price_move_since(row["ticker"], trade_date) if trade_date else None
        if move is None:
            row["price_note"] = "price unavailable"
            row["newly_flagged"] = False
            continue
        row["price_note"] = _price_note(move["pct_change"], move["days_since"], trade_type)
        flagged = _confirms_signal(trade_type, move["pct_change"], config.GOAT_INSIDER_PRICE_FLAG_PCT)
        row["newly_flagged"] = flagged and not row.get("price_flag_notified")
        if row["newly_flagged"]:
            db.mark_insider_filing_price_flag_notified(conn, row["dedup_key"])
    return recent_filings


def maybe_notify_price_flags(newly_flagged: list[dict[str, Any]]) -> None:
    """Fires once per ticker/filing the run its price move first crosses the
    confirms-signal threshold -- see compute_discovery_price_performance's
    docstring for why this is separate from monitor.maybe_notify (that one
    fires on new alerts/candidates being staged, not on a price move against
    an already-staged one)."""
    if not newly_flagged:
        return
    import sys
    from pathlib import Path

    _scripts_dir = Path(__file__).resolve().parent.parent.parent.parent / ".claude" / "scripts"
    sys.path.insert(0, str(_scripts_dir))
    from notifications import send_toast_notification, send_whatsapp_notification

    summary = f"{len(newly_flagged)} insider price move(s) just confirmed the signal"
    send_toast_notification("Goat Insider Scan", summary + " -- check investments/goat/insider-scan-report.md")

    lines = [f"Goat Insider Scan: {summary}."] + [
        f"- {row['ticker']}: {row['price_note']}" for row in newly_flagged
    ]
    send_whatsapp_notification("\n".join(lines))


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
        "| Ticker | Sector | Signal | Price Since Trade | Flagged |",
        "|--------|--------|--------|--------------------|---------|",
    ]
    for row in discovery_result["pending_candidates"]:
        lines.append(
            f"| {row['ticker']} | {row['sector_label']} | {row['signal_detail']} "
            f"| {row.get('price_note', 'n/a')} | {row['flagged_at'][:10]} |"
        )

    recent_filings = watch_result.get("recent_filings") or []
    lines += [
        "",
        "## Price Performance — Recent Holdings Filings",
        "Price move since trade date for P/S filings seen on your holdings "
        "(most recent 20, including ones below the alert threshold). "
        "\U0001F6A9 marks a move that confirms the insider's signal direction "
        "(buy -> price rose, sale -> price fell) by "
        f"{config.GOAT_INSIDER_PRICE_FLAG_PCT:.0f}%+.",
        "",
    ]
    if recent_filings:
        lines += ["| Ticker | Action | Value | Trade Date | Price Since Trade |",
                   "|--------|--------|-------|------------|--------------------|"]
        for row in recent_filings[:20]:
            action = "Bought" if row.get("trade_type") == "P" else "Sold"
            lines.append(
                f"| {row['ticker']} | {action} | ${row['value']:,.0f} | {row['trade_date']} "
                f"| {row.get('price_note', 'n/a')} |"
            )
    else:
        lines.append("No insider filings recorded yet for current holdings.")

    lines += ["", f"Last auto-generated: {date.today().isoformat()}."]
    return "\n".join(lines) + "\n"


def write_insider_scan_report(watch_result: dict[str, Any], discovery_result: dict[str, Any]) -> None:
    config.GOAT_INSIDER_SCAN_REPORT_PATH.write_text(
        render_insider_scan_report(watch_result, discovery_result), encoding="utf-8"
    )
