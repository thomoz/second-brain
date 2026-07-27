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


def check_session() -> dict[str, Any]:
    """Query GREEN-API directly for the account link state via `getStateInstance`.

    Deliberately independent of the bot process and the notification queue —
    it still works even if the bot has crashed, or if the queue-based event
    pipeline itself is misconfigured (see the `incomingWebhook` lesson in
    GREEN-API-troubleshooting.md — that failure looked identical to this one
    from the outside, so this check needs a signal that doesn't depend on the
    same pipeline). `authorized: None` means the request itself failed
    (network blip on this check) — treated as inconclusive, not a disconnect.
    """
    import requests

    from config import WHATSAPP_API_TOKEN, WHATSAPP_INSTANCE_ID
    from integrations.whatsapp import get_greenapi_base

    if not WHATSAPP_INSTANCE_ID or not WHATSAPP_API_TOKEN:
        return {"authorized": None, "state": ""}
    try:
        base = get_greenapi_base(WHATSAPP_INSTANCE_ID)
        resp = requests.get(f"{base}/getStateInstance/{WHATSAPP_API_TOKEN}", timeout=15)
        if resp.status_code != 200:
            return {"authorized": None, "state": ""}
        state = resp.json().get("stateInstance", "")
        return {"authorized": state == "authorized", "state": state}
    except Exception:
        return {"authorized": None, "state": ""}


def run_session_check() -> str | None:
    """Alert on a NEW loss of GREEN-API session authorization (deduped in the
    same state file as run_health_check, separate key). This is the "total
    session outage" case that run_health_check's log-scanning explicitly
    doesn't catch (see its docstring). The WhatsApp alert here is best-effort
    only — if the session is genuinely down, sending over WhatsApp will also
    fail; the toast/console channel is the fallback that still gets through.
    """
    from notifications import send_toast_notification, send_whatsapp_notification

    result = check_session()
    state = load_state(WHATSAPP_HEALTH_STATE_FILE)
    was_alerted = state.get("session_alerted", False)

    if result["authorized"] is False and not was_alerted:
        message = (
            f"⚠️ WhatsApp bot: GREEN-API session state is '{result['state']}', "
            f"not authorized. The account is disconnected — see the relinking "
            f"steps in GREEN-API-troubleshooting.md."
        )
        send_toast_notification("Second Brain: WhatsApp session disconnected", message)
        send_whatsapp_notification(message)
        state["session_alerted"] = True
        state["session_alerted_at"] = now_local().isoformat()
        save_state(WHATSAPP_HEALTH_STATE_FILE, state)
        return message

    if result["authorized"] is True and was_alerted:
        state["session_alerted"] = False
        state["session_recovered_at"] = now_local().isoformat()
        save_state(WHATSAPP_HEALTH_STATE_FILE, state)

    return None
