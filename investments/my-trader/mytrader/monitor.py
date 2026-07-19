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
from datetime import date
from typing import Any

from . import candidate_sync, config, db, engine, macro_indicators, market_data, snapshot

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
) -> tuple[list[dict[str, Any]], Any]:
    """Returns (new_alerts, opportunity_check). opportunity_check is the raw
    CheckResult (or None) — the "interesting" verdict deliberately does NOT go
    through _reconcile_alerts/alert_history (confirmed 2026-07-19, Shaun: "I also
    want to know if I should be interested in a holding on the watchlist"): unlike
    risk flags, which should go quiet after the first time so Shaun isn't renotified
    of an unchanged risk, an opportunity signal should keep showing up every run
    while it's still true — Shaun wants a live snapshot, not a one-time alert."""
    ticker = row["ticker"]
    bucket = row["bucket"]
    result = engine.run_assessment(ticker, conn)
    new_alerts = _reconcile_alerts(ticker, source_table, result["checks"], conn)

    etf_check = next((c for c in result["checks"] if c.name == "etf_mechanics"), None)
    expense_ratio = etf_check.data.get("expense_ratio") if etf_check else None
    db.touch_checked(conn, source_table, ticker, bucket, expense_ratio)

    opportunity_check = next((c for c in result["checks"] if c.name == "opportunity"), None)
    return new_alerts, opportunity_check


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
    with market_data.cached_session():
        for row in holdings:
            try:
                row_alerts, _ = _process_row(row, "holdings", conn)
                new_alerts.extend(row_alerts)
            except Exception as e:
                print(f"[monitor] error checking holding {row['ticker']}: {e}")
        for row in watchlist:
            try:
                row_alerts, opp_check = _process_row(row, "watchlist", conn)
                new_alerts.extend(row_alerts)
                if opp_check is not None and opp_check.verdict == "interesting":
                    opportunities.append({"ticker": row["ticker"], "detail": opp_check.detail})
            except Exception as e:
                print(f"[monitor] error checking watchlist {row['ticker']}: {e}")

    try:
        macro_checks = macro_indicators.run_all()
    except Exception as e:
        print(f"[monitor] error running macro indicators: {e}")
        macro_checks = []
    new_alerts.extend(_reconcile_alerts(MACRO_TICKER, MACRO_SOURCE_TABLE, macro_checks, conn))

    snapshot.regenerate_all(conn)

    return {
        "checked_holdings": len(holdings),
        "checked_watchlist": len(watchlist),
        "new_alerts": new_alerts,
        "open_alerts": [dict(a) for a in db.get_open_alerts(conn)],
        "macro_checks": [
            {"name": c.name, "verdict": c.verdict, "detail": c.detail} for c in macro_checks
        ],
        "synced_candidates": synced_candidates,
        "opportunities": opportunities,
    }


def render_report(result: dict[str, Any]) -> str:
    lines = [
        "# my-trader Monitor Report",
        "",
        "Auto-generated by Monitor — overwritten every run. Advisor notes only; "
        "no trade action is ever suggested here (see SOUL.md).",
        "",
        f"## Run: {date.today().isoformat()}",
        f"Checked {result['checked_holdings']} holding(s), "
        f"{result['checked_watchlist']} watchlist candidate(s).",
        "",
        "### New Alerts This Run",
    ]
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

    lines += ["", f"Last auto-generated: {date.today().isoformat()}."]
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
        f"{n} item(s) flagged — check investments/my-trader/monitor-report.md",
    )
