"""Monitor — scheduled re-check of all holdings + vetted watchlist candidates.

Runs Find's same assessment engine against every current holding and every watchlist
row marked status="discussed" (never "raw" — Monitor doesn't proactively discover new
candidates via the assessment engine, per tool-preplan.md's "Monitor's scope"
decision). High-bar alerting: a check flipping to verdict="flag" for the first time
(no existing open alert of that check_name for that ticker) creates a new alert and
is surfaced; repeat runs of an already-flagged condition stay quiet. When a
previously flagged check stops flagging, its open alert is auto-acknowledged so a
future re-flag raises a fresh one. Output is a standalone file only
(monitor-report.md) plus a bare toast notification when there's at least one new
alert — no Second Brain daily-log or WhatsApp push, per tool-preplan.md's "output
channel" decision.

Also surfaces "Watchlist Opportunities" every run (confirmed 2026-07-19, Shaun: "I
also want to know if I should be interested in a holding on the watchlist" — Monitor
was previously only ever a list of things to worry about) — checks/opportunity.py's
verdict="interesting" signal (cheap valuation, strong recent momentum, high Briefs
Finance score) for status="discussed" watchlist rows, rendered as a live snapshot
every run rather than deduped through alert_history like the risk checks.

Also runs candidate_sync.sync_new_candidates() once per run (re-added 2026-07-19,
same day it was first removed) -- this is safe to run unattended because it only
ever writes to the separate pending_candidates staging table/
synced-candidates-pending-review.md, never to watchlist.md
directly. The original "turn off automatic candidate_sync" complaint was about it
silently polluting Shaun's curated watchlist, not about automation itself -- once the
target became the pending-review staging area, running it unattended stopped being a
problem.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo

SYDNEY_TZ = ZoneInfo("Australia/Sydney")


def _today_sydney() -> str:
    """Report date label — always Sydney local, regardless of host clock/timezone."""
    return datetime.now(SYDNEY_TZ).date().isoformat()
from typing import Any

from . import candidate_sync, config, db, econ_calendar, engine, gold_outlook, macro_indicators, market_data, snapshot

SEVERITY = "flag"  # Phase B keeps severity simple: every alert comes from a
                    # "flag" verdict. Refining severity tiers is a later tuning task.

MACRO_TICKER = "MACRO"
MACRO_SOURCE_TABLE = "macro"


def _reconcile_alerts(
    ticker: str, source_table: str, checks: list, conn: sqlite3.Connection
) -> list[dict[str, Any]]:
    new_alerts: list[dict[str, Any]] = []
    for check in checks:
        existing = db.get_open_alert(conn, ticker, source_table, check.name)
        if check.verdict == "flag":
            if existing is None:
                db.insert_alert(
                    conn, ticker=ticker, source_table=source_table,
                    check_name=check.name, severity=SEVERITY, message=check.detail,
                )
                new_alerts.append({
                    "ticker": ticker, "source_table": source_table,
                    "check_name": check.name, "message": check.detail,
                })
        elif existing is not None:
            db.acknowledge_alert(conn, existing["id"])
    return new_alerts


def _process_row(
    row: sqlite3.Row, source_table: str, conn: sqlite3.Connection
) -> tuple[list[dict[str, Any]], Any, dict[str, Any]]:
    """Returns (new_alerts, opportunity_check, result). opportunity_check is the raw
    CheckResult (or None) — the "interesting" verdict deliberately does NOT go
    through _reconcile_alerts/alert_history (confirmed 2026-07-19, Shaun: "I also
    want to know if I should be interested in a holding on the watchlist"): unlike
    risk flags, which should go quiet after the first time so Shaun isn't renotified
    of an unchanged risk, an opportunity signal should keep showing up every run
    while it's still true — Shaun wants a live snapshot, not a one-time alert.
    result is the full engine.run_assessment() dict -- used to render a per-holding
    report section (added 2026-08-13, Shaun: "the monitor report doesn't list my
    Holdings, or give a report for each holding")."""
    ticker = row["ticker"]
    bucket = row["bucket"]
    result = engine.run_assessment(ticker, conn)
    new_alerts = _reconcile_alerts(ticker, source_table, result["checks"], conn)

    etf_check = next((c for c in result["checks"] if c.name == "etf_mechanics"), None)
    expense_ratio = etf_check.data.get("expense_ratio") if etf_check else None
    db.touch_checked(conn, source_table, ticker, bucket, expense_ratio)

    opportunity_check = next((c for c in result["checks"] if c.name == "opportunity"), None)
    return new_alerts, opportunity_check, result


def run_monitor(conn: sqlite3.Connection) -> dict[str, Any]:
    try:
        synced_candidates = candidate_sync.sync_new_candidates(conn)
    except Exception as e:
        print(f"[monitor] error syncing briefs-finance candidates: {e}")
        synced_candidates = []

    holdings = db.get_all_holdings(conn)
    watchlist = [w for w in db.get_all_watchlist(conn) if w["status"] == "discussed"]

    new_alerts: list[dict[str, Any]] = []
    opportunities: list[dict[str, Any]] = []
    holdings_report: list[dict[str, Any]] = []
    total_mkt_value = 0.0  # currency-naive sum, same known limitation as
                            # checks/concentration.py's own market-value aggregation
    with market_data.cached_session():
        for row in holdings:
            try:
                row_alerts, _, result = _process_row(row, "holdings", conn)
                new_alerts.extend(row_alerts)
                qty = row["qty"]
                avg_price = row["avg_price"]
                cost_basis = qty * avg_price
                current_price = market_data.fetch_current_price(row["ticker"])
                if current_price is not None:
                    mkt_value = qty * current_price
                    pnl = mkt_value - cost_basis
                    pnl_pct = (pnl / cost_basis * 100) if cost_basis else None
                    total_mkt_value += mkt_value
                else:
                    mkt_value = pnl = pnl_pct = None
                holdings_report.append({
                    "ticker": row["ticker"], "name": row["name"], "bucket": row["bucket"],
                    "qty": qty, "avg_price": avg_price,
                    "current_price": current_price, "mkt_value": mkt_value,
                    "pnl": pnl, "pnl_pct": pnl_pct,
                    "mlp": result.get("mlp", False), "mlp_name": result.get("mlp_name"),
                    "checks": [
                        {"name": c.name, "verdict": c.verdict, "detail": c.detail} for c in result["checks"]
                    ],
                })
            except Exception as e:
                print(f"[monitor] error checking holding {row['ticker']}: {e}")
        for row in watchlist:
            try:
                row_alerts, opp_check, _ = _process_row(row, "watchlist", conn)
                new_alerts.extend(row_alerts)
                if opp_check is not None and opp_check.verdict == "interesting":
                    opportunities.append({"ticker": row["ticker"], "detail": opp_check.detail})
            except Exception as e:
                print(f"[monitor] error checking watchlist {row['ticker']}: {e}")

    try:
        upcoming_releases = econ_calendar.fetch_upcoming_releases()
    except Exception as e:
        print(f"[monitor] error fetching upcoming economic releases: {e}")
        upcoming_releases = []

    try:
        macro_checks = macro_indicators.run_all()
    except Exception as e:
        print(f"[monitor] error running macro indicators: {e}")
        macro_checks = []
    new_alerts.extend(_reconcile_alerts(MACRO_TICKER, MACRO_SOURCE_TABLE, macro_checks, conn))
    if macro_checks:
        db.upsert_macro_snapshot(conn, macro_checks)

    try:
        outlook = gold_outlook.build_outlook(conn, macro_checks)
        if outlook is not None:
            gold_outlook.write_outlook(outlook)
    except Exception as e:
        print(f"[monitor] error building gold outlook: {e}")
        outlook = None

    snapshot.regenerate_all(conn)

    # Attach % of portfolio + this ticker's own open alerts to each holdings_report
    # entry now that the run is fully complete (total_mkt_value needs every holding
    # priced first; open alerts need macro reconciliation above to have already run,
    # so a fresh MACRO alert from this same run isn't missed) -- added 2026-08-13,
    # closing two of the gaps found rating Monitor's Holdings report against "would
    # this help a trader decide what action to take" (35/100): no P&L context, and
    # open alerts living in a disconnected section a trader had to cross-reference.
    open_alerts_all = [dict(a) for a in db.get_open_alerts(conn)]
    alerts_by_ticker: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for a in open_alerts_all:
        alerts_by_ticker.setdefault((a["ticker"], a["source_table"]), []).append(a)
    for h in holdings_report:
        h["pct_of_portfolio"] = (
            round(h["mkt_value"] / total_mkt_value * 100, 1)
            if h["mkt_value"] is not None and total_mkt_value > 0 else None
        )
        h["open_alerts"] = alerts_by_ticker.get((h["ticker"], "holdings"), [])

    return {
        "checked_holdings": len(holdings),
        "checked_watchlist": len(watchlist),
        "new_alerts": new_alerts,
        "open_alerts": open_alerts_all,
        "upcoming_releases": upcoming_releases,
        "holdings_report": holdings_report,
        "macro_checks": [
            {"name": c.name, "verdict": c.verdict, "detail": c.detail} for c in macro_checks
        ],
        "synced_candidates": synced_candidates,
        "opportunities": opportunities,
        "gold_outlook_available": outlook is not None,
    }


# Checks that render pure structural boilerplate for a given (name, detail) pair --
# never carries per-run information, so it's noise in the Holdings report. Kept as an
# exact-match set rather than a broader "hide unknown verdicts" rule: concentration's
# "unknown" verdict still carries a real per-ticker sector % even when the Berkshire
# portion is unpopulated, so that one stays visible.
_NOISE_CHECKS = {("etf_mechanics", "Not an ETF")}


def _is_noise_check(c: dict[str, Any]) -> bool:
    return (c["name"], c["detail"]) in _NOISE_CHECKS


def _bottom_line(checks: list[dict[str, Any]]) -> str:
    """One-sentence synthesis of a holding's checks this run -- added 2026-08-13 so a
    trader doesn't have to mentally scan every check line on every holding, every run,
    to tell whether anything actually needs attention."""
    flags = [c["name"] for c in checks if c["verdict"] == "flag"]
    interesting = [c["name"] for c in checks if c["verdict"] == "interesting"]
    if flags:
        return f"{len(flags)} flag(s) active ({', '.join(flags)}) — worth a look."
    if interesting:
        return f"{len(interesting)} opportunity signal(s) ({', '.join(interesting)}), no active flags."
    return "Nothing notable this run."


def render_report(result: dict[str, Any]) -> str:
    lines = [
        "# my-trader Monitor Report",
        "",
        "What this is: your daily check on holdings and watchlist tickers — new "
        "risk flags, opportunities, and current price action.",
        "",
        "Auto-generated by Monitor — overwritten every run. Advisor notes only; "
        "no trade action is ever suggested here (see SOUL.md).",
        "",
        f"## Run: {_today_sydney()}",
        f"Checked {result['checked_holdings']} holding(s), "
        f"{result['checked_watchlist']} watchlist candidate(s).",
        "",
        "### Upcoming Economic Releases (next 48h)",
    ]
    upcoming_releases = result.get("upcoming_releases", [])
    if upcoming_releases:
        for rel in upcoming_releases:
            when = "today" if rel["days_until"] == 0 else "tomorrow" if rel["days_until"] == 1 else f"in {rel['days_until']} days"
            lines.append(f"- **{rel['release_name']}** — {rel['date']} ({when})")
    else:
        lines.append("No CPI/PPI/jobs releases scheduled in the next 48 hours.")

    lines += ["", "### Holdings (this run)"]
    holdings_report = result.get("holdings_report", [])
    if holdings_report:
        for h in holdings_report:
            bucket_label = config.BUCKET_LABELS.get(h["bucket"], f"bucket {h['bucket']}")
            lines.append(f"\n**{h['ticker']}** ({h['name']}, {bucket_label})")

            if h.get("mlp"):
                lines.append(f"- MLP — skipped: {h['mlp_name']} is structured as a Master Limited Partnership.")
                continue

            if h.get("current_price") is not None:
                pnl_str = f"{'+' if h['pnl'] >= 0 else ''}${h['pnl']:,.2f}"
                pnl_pct_str = f" ({h['pnl_pct']:+.1f}%)" if h.get("pnl_pct") is not None else ""
                price_line = (
                    f"{h['qty']} @ avg ${h['avg_price']:,.2f} | now ${h['current_price']:,.2f} "
                    f"| P&L {pnl_str}{pnl_pct_str}"
                )
            else:
                price_line = f"{h['qty']} @ avg ${h['avg_price']:,.2f} | current price unavailable"
            if h.get("pct_of_portfolio") is not None:
                price_line += f" | {h['pct_of_portfolio']:.1f}% of tracked portfolio"
            lines.append(price_line)

            lines.append(f"Bottom line: {_bottom_line(h['checks'])}")

            open_alerts = h.get("open_alerts", [])
            if open_alerts:
                for a in open_alerts:
                    lines.append(f"- OPEN ALERT ({a['check_name']}, since {a['created_at'][:10]}): {a['message']}")
            else:
                lines.append("Open alerts: none")

            for c in h["checks"]:
                if _is_noise_check(c):
                    continue
                line = f"- [{c['verdict']}] {c['name']}: {c['detail']}"
                if c["name"] == "opportunity" and c["verdict"] == "interesting":
                    line += " (you already hold this — reads as an add-to-position signal, not a new-buy signal)"
                lines.append(line)
    else:
        lines.append("No holdings tracked.")

    lines += ["", "### New Alerts This Run"]
    if result["new_alerts"]:
        for a in result["new_alerts"]:
            lines.append(f"- **{a['ticker']}** ({a['source_table']}) — {a['check_name']}: {a['message']}")
    else:
        lines.append("No new material changes.")
    lines += ["", "### All Open Alerts"]
    if result["open_alerts"]:
        for a in result["open_alerts"]:
            lines.append(
                f"- **{a['ticker']}** ({a['source_table']}) — {a['check_name']}: "
                f"{a['message']} (first flagged {a['created_at'][:10]})"
            )
    else:
        lines.append("None.")

    lines += ["", "### Watchlist Opportunities (this run)"]
    if result["opportunities"]:
        for o in result["opportunities"]:
            lines.append(f"- **{o['ticker']}** — {o['detail']}")
    else:
        lines.append("Nothing standing out this run.")

    lines += ["", "### Macro Indicators (this run)"]
    if result["macro_checks"]:
        for c in result["macro_checks"]:
            lines.append(f"- **{c['name']}** [{c['verdict']}] — {c['detail']}")
    else:
        lines.append("Unavailable this run.")

    lines += ["", "### Gold Outlook"]
    if result.get("gold_outlook_available"):
        lines.append("See investments/my-trader/gold-outlook.md — today/tomorrow, "
                      "this week, and this month reads, refreshed this run.")
    else:
        lines.append("Unavailable this run.")

    lines += ["", "### New Candidates Synced (Pending Review)"]
    if result["synced_candidates"]:
        for cand in result["synced_candidates"]:
            lines.append(f"- **{cand['ticker']}** — {cand['company_name'] or '(no name)'}")
        lines.append(
            "See synced-candidates-pending-review.md — promote-candidate or "
            "dismiss-candidate each one. Not added to the watchlist automatically."
        )
    else:
        lines.append("None this run.")

    lines += ["", f"Last auto-generated: {_today_sydney()}."]
    return "\n".join(lines) + "\n"


def write_report(result: dict[str, Any]) -> None:
    config.MONITOR_REPORT_PATH.write_text(render_report(result), encoding="utf-8")


def maybe_notify(result: dict[str, Any]) -> None:
    if not result["new_alerts"]:
        return
    import sys
    from pathlib import Path

    _scripts_dir = Path(__file__).resolve().parent.parent.parent.parent / ".claude" / "scripts"
    sys.path.insert(0, str(_scripts_dir))
    from notifications import send_toast_notification

    n = len(result["new_alerts"])
    send_toast_notification(
        "my-trader Monitor",
        f"{n} item(s) flagged — check investments/my-trader/my-trader-report.md",
    )
