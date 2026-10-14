"""Grouped WhatsApp + toast alert for the Volume-Spike + Record-Earnings Scan -- one
message per run listing every genuinely-new staged candidate. No-op on an empty
list; silent on zero-candidate days. Reaches .claude/scripts/notifications.py via a
sys.path insert, mirroring ai_resistant_moat_scanner.notify exactly.

Both channels are titled "Volume/Earnings Scanner Alert" so Shaun knows which
module sent it.
"""

from __future__ import annotations

from typing import Any

_TITLE = "Volume/Earnings Scanner Alert"


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
        f"{n} new volume/earnings candidate(s) -- see "
        "investments/volume-earnings-scanner/volume-earnings-candidates-pending-review.md",
    )

    lines = [f"{_TITLE}: {n} new candidate(s).", ""]
    for c in new_candidates:
        company = c.get("company") or ""
        name_str = f"{c['ticker']} — {company}" if company else c["ticker"]
        lines.append(f"- {name_str} ({c.get('signal_type', '')}): {c.get('detail', '')}")
    send_whatsapp_notification("\n".join(lines))
