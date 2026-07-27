"""WhatsApp bot health check — surfaces a degraded poll loop within minutes
instead of days.

Built 2026-07-27 after the bot went silent (repeated `receiveNotification`
timeouts) for ~6 days with nothing telling Shaun — he only found out by chance
when a reply never came, and WhatsApp's own delivery tick marks are NOT proof
the bot's poll loop actually captured the message (see
GREEN-API-troubleshooting.md — this exact confusion cost debugging time in the
2026-07-19 outage too).

Deliberately alerts via the existing `send_whatsapp_notification` /
`send_toast_notification` channels rather than adding a new send-capable
integration (e.g. auto-sending email would cross the project's advisor-mode
"never act/send autonomously" line for a brand-new channel; these two are
already an established exception, used for self-directed system notifications
to Shaun, not correspondence with third parties). Outbound `sendMessage` and
the inbound long-poll `receiveNotification` are different GREEN-API endpoints
— diagnosed 2026-07-25/26: quick one-shot calls (getStateInstance,
getWaSettings, lastIncomingMessages) kept succeeding fine while only the
long-poll degraded, so a WhatsApp-sent alert is a reasonable bet for THIS
failure class specifically. Known gap: a total account/session outage (wrong
account linked, logged out) would silence the outbound path too — this
doesn't solve that case, only the "poll loop quietly degrades" case.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from config import WHATSAPP_HEALTH_STATE_FILE, WHATSAPP_LOG_PATH, now_local
from shared import load_state, save_state

# A run of this many consecutive "poll error" log lines with no successfully
# processed message in between is treated as a real degradation, not a single
# transient network blip (the bot itself doesn't error on every single poll
# tick normally — see whatsapp_runs.log history from the 2026-07-19 outage).
CONSECUTIVE_ERROR_THRESHOLD = 3

_ERROR_RE = re.compile(r"WhatsApp poll error:")
_MESSAGE_RE = re.compile(r"Message from ")
_STARTUP_RE = re.compile(r"All adapters connected")


def _tail_lines(path: Path, max_lines: int = 500) -> list[str]:
    if not path.exists():
        return []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    return text.splitlines()[-max_lines:]


def check_health(log_path: Path | None = None) -> dict[str, Any]:
    """Inspect the bot's own log for a run of consecutive poll errors since the
    last successfully processed message (or since bot start, if none yet)."""
    lines = _tail_lines(log_path or WHATSAPP_LOG_PATH)
    consecutive_errors = 0
    for line in reversed(lines):
        if _MESSAGE_RE.search(line) or _STARTUP_RE.search(line):
            break
        if _ERROR_RE.search(line):
            consecutive_errors += 1
    return {
        "healthy": consecutive_errors < CONSECUTIVE_ERROR_THRESHOLD,
        "consecutive_errors": consecutive_errors,
    }


def run_health_check() -> str | None:
    """Check health and alert on a NEW degradation only (deduped via
    WHATSAPP_HEALTH_STATE_FILE so an ongoing outage alerts once, not every
    30-minute heartbeat cycle) — clears the alerted flag on recovery so a
    future degradation alerts fresh. Returns the alert message if one was sent
    this call, else None."""
    from notifications import send_toast_notification, send_whatsapp_notification

    result = check_health()
    state = load_state(WHATSAPP_HEALTH_STATE_FILE)
    was_alerted = state.get("alerted", False)

    if not result["healthy"] and not was_alerted:
        message = (
            f"⚠️ WhatsApp bot: {result['consecutive_errors']} consecutive poll "
            f"errors logged, nothing processed successfully since. Inbound "
            f"messages may not be arriving — check whatsapp_runs.log and the "
            f"GREEN-API instance state (see GREEN-API-troubleshooting.md)."
        )
        send_toast_notification("Second Brain: WhatsApp bot degraded", message)
        send_whatsapp_notification(message)
        state["alerted"] = True
        state["alerted_at"] = now_local().isoformat()
        save_state(WHATSAPP_HEALTH_STATE_FILE, state)
        return message

    if result["healthy"] and was_alerted:
        state["alerted"] = False
        state["recovered_at"] = now_local().isoformat()
        save_state(WHATSAPP_HEALTH_STATE_FILE, state)

    return None
