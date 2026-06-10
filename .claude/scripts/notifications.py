"""
Notification utilities for Second Brain heartbeat.

Channels: Windows Toast (local), WhatsApp (GREEN-API), console (fallback).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


def send_console_notification(title: str, message: str) -> bool:
    """Print notification to console. Always safe to call."""
    print(f"\n{'=' * 60}")
    print(f"[NOTIFY] {title}")
    print(f"{'=' * 60}")
    print(message)
    print(f"{'=' * 60}\n")
    return True


def send_toast_notification(title: str, message: str, duration: int = 5) -> bool:
    """Send Windows Toast notification, falling back to console."""
    if sys.platform != "win32":
        return send_console_notification(title, message)
    try:
        from win10toast_click import ToastNotifier

        ToastNotifier().show_toast(title, message[:200], duration=duration, threaded=True)
        return True
    except Exception:
        return send_console_notification(title, message)


def send_whatsapp_notification(message: str, chat_id: str = "") -> bool:
    """Send WhatsApp notification to Shaun's personal number via GREEN-API."""
    from config import WHATSAPP_MY_NUMBER
    from integrations.whatsapp import send_message

    if not WHATSAPP_MY_NUMBER and not chat_id:
        return False
    return send_message(chat_id or f"{WHATSAPP_MY_NUMBER}@c.us", message)
