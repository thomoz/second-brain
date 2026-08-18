"""Transition-only WhatsApp/toast alert -- fires only for markers that newly
flip into a firing state this run (per db.upsert_signal_state), never a daily
dump of all 14 rows regardless of change. Writes its own small maybe_notify
rather than importing goat.monitor.maybe_notify: that function's alert_label/
candidate_label shape is specific to Goat's own exit-alert/staged-candidate
framing, which doesn't fit this tool's "named marker transitioned to firing"
shape."""

from __future__ import annotations

import sqlite3
from typing import Any

from . import db


def maybe_notify(conn: sqlite3.Connection, results: list[dict[str, Any]]) -> None:
    """results: list of {'marker_key': str, 'is_firing': bool, 'detail': str}."""
    newly_firing = [
        r for r in results
        if db.upsert_signal_state(conn, marker_key=r["marker_key"], is_firing=r["is_firing"], detail=r["detail"])
    ]
    if not newly_firing:
        return

    import sys
    from pathlib import Path

    _scripts_dir = Path(__file__).resolve().parent.parent.parent.parent / ".claude" / "scripts"
    sys.path.insert(0, str(_scripts_dir))
    from notifications import send_toast_notification, send_whatsapp_notification

    summary = f"{len(newly_firing)} crash-warning signal(s) newly firing"
    send_toast_notification("14 Crash Signals", summary + " -- check investments/fourteen-crash-signals-daily-check/")

    lines = [f"14 Crash Signals: {summary}."]
    lines += [f"- {r['detail']}" for r in newly_firing]
    send_whatsapp_notification("\n".join(lines))


def notify_credit_spread_streak_daily(result) -> None:
    """Deliberate exception to this module's transition-only alert rule above -- Shaun
    explicitly asked for a daily 'day N and counting' WhatsApp ping while Marker 14's
    streak continues, not just once on first firing (2026-08-18, Phase 2 handoff). Does
    not touch db.upsert_signal_state -- main.py still calls that separately for
    credit_spread_streak, for state-tracking/report consistency; this function's firing
    decision is independent of that transition gate."""
    if result.verdict != "flag":
        return
    streak_days = result.data.get("streak_days", "?")

    import sys
    from pathlib import Path

    _scripts_dir = Path(__file__).resolve().parent.parent.parent.parent / ".claude" / "scripts"
    sys.path.insert(0, str(_scripts_dir))
    from notifications import send_whatsapp_notification

    send_whatsapp_notification(
        f"14 Crash Signals: credit spread streak, day {streak_days} and counting -- {result.detail}"
    )
