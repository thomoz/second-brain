"""Unit tests for integrations/whatsapp.py — no live API calls."""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from integrations.whatsapp import (
    WhatsAppMessage,
    format_messages_for_context,
    get_greenapi_base,
    send_message,
)


def test_get_greenapi_base():
    assert get_greenapi_base("12345") == "https://api.green-api.com/waInstance12345"
    assert get_greenapi_base("99999") == "https://api.green-api.com/waInstance99999"


def test_format_messages_empty():
    result = format_messages_for_context([])
    assert result == "No WhatsApp messages."


def test_format_messages_single():
    ts = datetime(2026, 6, 10, 9, 30)
    msg = WhatsAppMessage(id="1", sender="61412345678@c.us", text="Hello!", timestamp=ts, is_from_me=False)
    result = format_messages_for_context([msg])
    assert "09:30" in result
    assert "61412345678@c.us" in result
    assert "Hello!" in result


def test_format_messages_multiple():
    ts1 = datetime(2026, 6, 10, 9, 0)
    ts2 = datetime(2026, 6, 10, 10, 0)
    msgs = [
        WhatsAppMessage(id="1", sender="Alice", text="Hi", timestamp=ts1, is_from_me=False),
        WhatsAppMessage(id="2", sender="Bob", text="Hey", timestamp=ts2, is_from_me=False),
    ]
    result = format_messages_for_context(msgs)
    lines = result.strip().splitlines()
    assert len(lines) == 2
    assert "Alice" in lines[0]
    assert "Bob" in lines[1]


def test_send_message_returns_false_without_credentials(monkeypatch):
    """send_message returns False if WHATSAPP_INSTANCE_ID or WHATSAPP_API_TOKEN not set."""
    import config
    monkeypatch.setattr(config, "WHATSAPP_INSTANCE_ID", "")
    monkeypatch.setattr(config, "WHATSAPP_API_TOKEN", "")
    result = send_message("61412345678@c.us", "test")
    assert result is False
