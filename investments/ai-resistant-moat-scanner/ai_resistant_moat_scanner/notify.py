"""Grouped WhatsApp + toast alert for the AI-Resistant Moat Scan -- one message per
run listing every genuinely-new staged candidate. No-op on an empty list; silent on
zero-candidate days. Reaches .claude/scripts/notifications.py via a sys.path insert,
mirroring superinvestor_filings.notify exactly.

Both channels are titled "AI-Resistant Moat Alert" so Shaun knows which module sent it.
"""

from __future__ import annotations

from typing import Any

_TITLE = "AI-Resistant Moat Alert"


def maybe_notify(new_candidates: list[dict[str, Any]]) -> None:
    if not new_candidates:
        return

    import sys
    from pathlib import Path

    _scripts_dir = Path(__file__).resolve().parent.parent.parent.parent / ".claude" / "scripts"
    sys.path.insert(0, str(_scripts_dir))
    from notifications import send_toast_notification, send_whatsapp_notification

    n = len(new_candidates)
    send_toast_notification(
        _TITLE,
        f"{n} new embedded-moat candidate(s) -- see "
        "investments/ai-resistant-moat-scanner/moat-candidates-pending-review.md",
    )

    lines = [f"{_TITLE}: {n} new embedded-moat candidate(s).", ""]
    for c in new_candidates:
        moat = c.get("moat_score")
        moat_str = f" moat {moat:.1f}" if isinstance(moat, (int, float)) else ""
        lines.append(f"- {c['ticker']} ({c.get('industry', '')}){moat_str}: {c.get('thesis', '')}")
    send_whatsapp_notification("\n".join(lines))
