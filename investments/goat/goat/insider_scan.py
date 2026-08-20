"""Orchestrator for the OpenInsider Form 4 scan -- Goat insider trading scanner.
Two halves: holdings-watch (P/S filings on tickers Shaun currently holds) and
discovery (market-wide $25k+ open-market purchases, staged into the existing
goat_pending_candidates table like every other Goat candidate source). Dedup is
by filing identity (goat_insider_filings_seen), not goat_alert_history -- see
NOTES in .agent/plans/insider-trading-scanner.md for why a discrete one-time
event doesn't fit that table's open/acknowledge semantics."""

from __future__ import annotations

import re
import sqlite3
from datetime import date, datetime, timedelta
from typing import Any

import pandas as pd
from mytrader import db as mt_db
from mytrader import openinsider

from . import config, db, price_history


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
            title=row.get("title", ""),
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
            value=row["value"], kind="discovery", title=row.get("title", ""),
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


def run_discovery_sell_tracking(conn: sqlite3.Connection) -> dict[str, Any]:
    """Market-wide sell tracking, data-only -- explicitly no
    goat_pending_candidates row and no WhatsApp notify (Shaun 2026-08-20: there's
    no 'should I act on this' question for a sell on a stock he doesn't hold,
    it's purely a data point for insider_pattern_analysis). Held tickers are
    skipped -- those sells are already covered by run_holdings_watch."""
    held_tickers = {row["ticker"] for row in mt_db.get_all_holdings(conn)}
    rows = openinsider.fetch_discovery_sales()
    if rows is None:
        print("[goat-insider-scan] OpenInsider sell-discovery fetch failed")
        return {"tracked": 0}

    tracked = 0
    for row in rows:
        if not _within_lookback(row.get("trade_date", ""), config.GOAT_INSIDER_DISCOVERY_LOOKBACK_DAYS):
            continue
        if row["ticker"] in held_tickers:
            continue
        dedup_key = openinsider.build_dedup_key(row)
        newly_seen = db.insert_goat_insider_filing_seen(
            conn, dedup_key=dedup_key, ticker=row["ticker"],
            filing_date=row.get("filing_date", ""), trade_date=row.get("trade_date", ""),
            insider_name=row.get("insider_name", ""), trade_type=row["trade_type_code"],
            value=row["value"], kind="discovery_sell",
            pct_owned_change=row.get("pct_owned_change"), title=row.get("title", ""),
        )
        if newly_seen:
            tracked += 1
    return {"tracked": tracked}


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


def _threshold_for_days(days_since: int) -> float:
    for max_days, pct in config.GOAT_INSIDER_PRICE_FLAG_TIERS:
        if days_since <= max_days:
            return pct
    return config.GOAT_INSIDER_PRICE_FLAG_PCT_TAIL


def _tiered_threshold_description() -> str:
    """English description of the tier table for the report footer, derived
    programmatically from config so it can never drift out of sync."""
    parts = [f"{pct:.1f}% within {max_days}d" for max_days, pct in config.GOAT_INSIDER_PRICE_FLAG_TIERS]
    parts.append(f"{config.GOAT_INSIDER_PRICE_FLAG_PCT_TAIL:.1f}% after that")
    return ", ".join(parts)


def _price_at_horizon(ticker: str, trade_date_str: str, horizon_days: int) -> dict[str, Any] | None:
    """pct_change from the close on/after trade_date_str to the close on/after
    trade_date_str + horizon_days -- distinct from _price_move_since, which
    measures to *today's* latest close. Returns None on unparsable date or a
    price-fetch/window miss; callers must treat that as 'not yet maturable',
    not zero."""
    try:
        trade_date_obj = datetime.strptime(trade_date_str, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None
    target_date = trade_date_obj + timedelta(days=horizon_days)
    days_since_trade = (date.today() - trade_date_obj).days
    if days_since_trade < horizon_days:
        return None  # horizon not reached yet

    close = price_history.fetch_close_history(ticker, days_since_trade + 10)
    if close is None or close.empty:
        return None
    start_slice = close[close.index >= pd.Timestamp(trade_date_obj)]
    end_slice = close[close.index >= pd.Timestamp(target_date)]
    if start_slice.empty or end_slice.empty:
        return None
    start_price = float(start_slice.iloc[0])
    end_price = float(end_slice.iloc[0])
    if start_price == 0:
        return None
    return {"pct_change": (end_price - start_price) / start_price * 100}


def mature_price_outcome_snapshots(conn: sqlite3.Connection) -> dict[str, Any]:
    """Nightly job: for every filing within GOAT_INSIDER_OUTCOME_MAX_TRACKING_DAYS
    of its trade date, insert any not-yet-captured horizon that's been reached.
    Independent of goat_pending_candidates' lifecycle -- dismissing/promoting a
    candidate no longer destroys its outcome history."""
    matured = 0
    benchmark_cache: dict[tuple[str, int], float | None] = {}
    filings = db.get_recent_insider_filings_seen(conn, limit=100000)
    for filing in filings:
        if not _within_lookback(filing["trade_date"], config.GOAT_INSIDER_OUTCOME_MAX_TRACKING_DAYS):
            continue
        captured = db.get_captured_horizons(conn, filing["dedup_key"])
        for horizon in config.GOAT_INSIDER_OUTCOME_HORIZONS_DAYS:
            if horizon in captured:
                continue
            outcome = _price_at_horizon(filing["ticker"], filing["trade_date"], horizon)
            if outcome is None:
                continue
            cache_key = (filing["trade_date"], horizon)
            if cache_key not in benchmark_cache:
                bm = _price_at_horizon(
                    config.GOAT_INSIDER_OUTCOME_BENCHMARK_TICKER, filing["trade_date"], horizon
                )
                benchmark_cache[cache_key] = bm["pct_change"] if bm else None
            benchmark_pct = benchmark_cache[cache_key]
            excess_pct = (
                outcome["pct_change"] - benchmark_pct if benchmark_pct is not None else None
            )
            db.insert_price_outcome(
                conn, dedup_key=filing["dedup_key"], ticker=filing["ticker"],
                trade_type=filing["trade_type"], horizon_days=horizon,
                pct_change=outcome["pct_change"], benchmark_pct_change=benchmark_pct,
                excess_pct_change=excess_pct, snapshot_date=date.today().isoformat(),
            )
            matured += 1
    return {"matured": matured}


def _confirms_signal(trade_type_code: str, pct_change: float, days_since: int) -> bool:
    """Direction-aware only -- a buy is flagged on a rise, a sale on a fall.
    The contrarian direction is deliberately never flagged here (Shaun
    2026-08-18): that's a distinct read ("insider was early/wrong") he wants
    to judge himself, not have the tool call out as noteworthy. Threshold is
    time-aware (Shaun 2026-08-20) -- see _threshold_for_days."""
    threshold = _threshold_for_days(days_since)
    if trade_type_code == "P":
        return pct_change >= threshold
    if trade_type_code == "S":
        return pct_change <= -threshold
    return False


def _price_note(pct_change: float, days_since: int, trade_type_code: str) -> str:
    flag = " \U0001F6A9 confirms signal" if _confirms_signal(
        trade_type_code, pct_change, days_since
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
            row["pct_change"] = None
            row["newly_flagged"] = False
            continue
        row["price_note"] = _price_note(move["pct_change"], move["days_since"], "P")
        row["pct_change"] = move["pct_change"]
        flagged = _confirms_signal("P", move["pct_change"], move["days_since"])
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
            row["pct_change"] = None
            row["newly_flagged"] = False
            continue
        row["price_note"] = _price_note(move["pct_change"], move["days_since"], trade_type)
        row["pct_change"] = move["pct_change"]
        flagged = _confirms_signal(trade_type, move["pct_change"], move["days_since"])
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


_TRADE_VALUE_RE = re.compile(r"\$([\d,]+)")


def _parse_trade_value(signal_detail: str) -> float | None:
    """Pulls the dollar value out of a discovery candidate's signal_detail text
    (e.g. '...bought $3,425,500 of AAT...') for size-sorting -- goat_pending_candidates
    doesn't store the raw value as its own column (see insert_goat_pending_candidate),
    and signal_detail's format is fully controlled by run_discovery_scan's f-string
    above, not freeform text, so this is safe to regex rather than needing a schema
    migration + backfill for candidates already staged before this existed."""
    m = _TRADE_VALUE_RE.search(signal_detail)
    return float(m.group(1).replace(",", "")) if m else None


def _render_discovery_rows(rows: list[dict[str, Any]]) -> list[str]:
    return [
        f"| {row['ticker']} | {row['sector_label']} | {row['signal_detail']} "
        f"| {row.get('price_note', 'n/a')} | {row['flagged_at'][:10]} |"
        for row in rows
    ]


def _render_holdings_rows(rows: list[dict[str, Any]]) -> list[str]:
    lines = []
    for row in rows:
        action = "Bought" if row.get("trade_type") == "P" else "Sold"
        lines.append(
            f"| {row['ticker']} | {action} | ${row['value']:,.0f} | {row['trade_date']} "
            f"| {row.get('price_note', 'n/a')} |"
        )
    return lines


_DISCOVERY_HEADER = ["| Ticker | Sector | Signal | Price Since Trade | Flagged |",
                      "|--------|--------|--------|--------------------|---------|"]
_HOLDINGS_HEADER = ["| Ticker | Action | Value | Trade Date | Price Since Trade |",
                     "|--------|--------|-------|------------|--------------------|"]


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
    ] + _DISCOVERY_HEADER
    candidates = discovery_result["pending_candidates"]
    lines += _render_discovery_rows(candidates)

    # Same rows as above, re-sorted three ways so Shaun can scan by what matters to
    # him in the moment instead of only ticker-alphabetical order (Shaun 2026-08-20).
    for row in candidates:
        row["trade_value"] = _parse_trade_value(row["signal_detail"])
    by_size = sorted(
        (r for r in candidates if r["trade_value"] is not None),
        key=lambda r: r["trade_value"], reverse=True,
    )
    price_up = sorted(
        (r for r in candidates if r.get("pct_change") is not None and r["pct_change"] > 0),
        key=lambda r: r["pct_change"], reverse=True,
    )
    price_down = sorted(
        (r for r in candidates if r.get("pct_change") is not None and r["pct_change"] < 0),
        key=lambda r: r["pct_change"],
    )
    by_date = sorted(
        (r for r in candidates if r.get("trade_date")),
        key=lambda r: r["trade_date"], reverse=True,
    )
    lines += [
        "",
        "### Discovery Candidates — By Trade Date",
        "Same candidates, re-sorted by the insider's trade date, most recent first.",
        "",
    ]
    lines += _DISCOVERY_HEADER + _render_discovery_rows(by_date) if by_date else [
        "No candidates with a recorded trade date."
    ]
    lines += [
        "",
        "### Discovery Candidates — By Trade Size",
        "Same candidates, re-sorted by the dollar value of the insider's buy (highest "
        "first) -- not percent of their own position, which stays visible per-row in "
        "the Signal column if you'd rather judge by conviction instead.",
        "",
    ]
    lines += _DISCOVERY_HEADER + _render_discovery_rows(by_size) if by_size else [
        "No candidates with a parseable trade value."
    ]
    lines += [
        "",
        "### Discovery Candidates — Price Up Since Trade",
        "Candidates whose price has risen since the insider's buy, biggest gain first.",
        "",
    ]
    lines += _DISCOVERY_HEADER + _render_discovery_rows(price_up) if price_up else [
        "No candidates have moved up since their trade yet."
    ]
    lines += [
        "",
        "### Discovery Candidates — Price Down Since Trade",
        "Candidates whose price has fallen since the insider's buy, biggest drop first.",
        "",
    ]
    lines += _DISCOVERY_HEADER + _render_discovery_rows(price_down) if price_down else [
        "No candidates have moved down since their trade yet."
    ]

    recent_filings = (watch_result.get("recent_filings") or [])[:20]
    lines += [
        "",
        "## Stocks You Own That Have Had Price Moves Since Insider Buy/Sell Activity",
        "Price move since trade date for P/S filings seen on your holdings "
        "(most recent 20, including ones below the alert threshold). "
        "\U0001F6A9 marks a move that confirms the insider's signal direction "
        "(buy -> price rose, sale -> price fell) past a time-aware threshold "
        f"({_tiered_threshold_description()}).",
        "",
    ]
    if recent_filings:
        lines += _HOLDINGS_HEADER + _render_holdings_rows(recent_filings)
    else:
        lines.append("No insider filings recorded yet for current holdings.")

    holdings_by_size = sorted(recent_filings, key=lambda r: r["value"], reverse=True)
    holdings_up = sorted(
        (r for r in recent_filings if r.get("pct_change") is not None and r["pct_change"] > 0),
        key=lambda r: r["pct_change"], reverse=True,
    )
    holdings_down = sorted(
        (r for r in recent_filings if r.get("pct_change") is not None and r["pct_change"] < 0),
        key=lambda r: r["pct_change"],
    )
    holdings_by_date = sorted(
        (r for r in recent_filings if r.get("trade_date")),
        key=lambda r: r["trade_date"], reverse=True,
    )
    lines += [
        "",
        "### Holdings Filings — By Trade Date",
        "Same filings, re-sorted by trade date, most recent first.",
        "",
    ]
    lines += _HOLDINGS_HEADER + _render_holdings_rows(holdings_by_date) if holdings_by_date else [
        "No insider filings recorded yet for current holdings."
    ]
    lines += [
        "",
        "### Holdings Filings — By Trade Size",
        "Same filings, re-sorted by dollar value (highest first).",
        "",
    ]
    lines += _HOLDINGS_HEADER + _render_holdings_rows(holdings_by_size) if holdings_by_size else [
        "No insider filings recorded yet for current holdings."
    ]
    lines += [
        "",
        "### Holdings Filings — Price Up Since Trade",
        "Filings where the price has risen since the trade, biggest gain first.",
        "",
    ]
    lines += _HOLDINGS_HEADER + _render_holdings_rows(holdings_up) if holdings_up else [
        "No holdings filings have moved up since their trade yet."
    ]
    lines += [
        "",
        "### Holdings Filings — Price Down Since Trade",
        "Filings where the price has fallen since the trade, biggest drop first.",
        "",
    ]
    lines += _HOLDINGS_HEADER + _render_holdings_rows(holdings_down) if holdings_down else [
        "No holdings filings have moved down since their trade yet."
    ]

    lines += ["", f"Last auto-generated: {date.today().isoformat()}."]
    return "\n".join(lines) + "\n"


def write_insider_scan_report(watch_result: dict[str, Any], discovery_result: dict[str, Any]) -> None:
    config.GOAT_INSIDER_SCAN_REPORT_PATH.write_text(
        render_insider_scan_report(watch_result, discovery_result), encoding="utf-8"
    )
