"""Grouped WhatsApp + toast digest for the superinvestor fast-disclosure scanner --
one message per run listing every genuinely-new filing. No-op on an empty list.
Reaches .claude/scripts/notifications.py via a sys.path insert, mirroring
goat.insider_scan.maybe_notify_price_flags exactly."""

from __future__ import annotations

from typing import Any


def send_digest(new_filings: list[dict[str, Any]]) -> None:
    if not new_filings:
        return

    import sys
    from pathlib import Path

    _scripts_dir = Path(__file__).resolve().parent.parent.parent.parent / ".claude" / "scripts"
    sys.path.insert(0, str(_scripts_dir))
    from notifications import send_toast_notification, send_whatsapp_notification

    # Group the human summary lines by investor for the message body.
    by_investor: dict[str, list[str]] = {}
    for a in new_filings:
        by_investor.setdefault(a.get("filer_display", a.get("filer_key", "Tracked investor")), []).append(
            a["summary"]
        )

    total = len(new_filings)
    summary = f"{total} new fast disclosure(s) from tracked superinvestor(s)"
    send_toast_notification(
        "Superinvestor Filings",
        summary + " -- see investments/superinvestor-filings/superinvestor-filings-report.md",
    )

    lines: list[str] = []
    for investor, items in by_investor.items():
        lines.append(f"{investor} -- {len(items)} new fast disclosure(s):")
        lines.extend(f"- {s}" for s in items)
    send_whatsapp_notification("\n".join(lines))
