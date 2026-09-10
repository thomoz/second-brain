from __future__ import annotations

import sys
import types

import pytest

from ai_resistant_moat_scanner import notify


@pytest.fixture
def _fake_notifications(monkeypatch):
    calls: dict[str, list] = {"toast": [], "whatsapp": []}
    mod = types.ModuleType("notifications")
    mod.send_toast_notification = lambda title, message: calls["toast"].append((title, message))
    mod.send_whatsapp_notification = lambda message, chat_id="": calls["whatsapp"].append(message)
    monkeypatch.setitem(sys.modules, "notifications", mod)
    return calls


def test_maybe_notify_noop_on_empty(_fake_notifications):
    notify.maybe_notify([])
    assert _fake_notifications["toast"] == []
    assert _fake_notifications["whatsapp"] == []


def test_maybe_notify_sends_titled_alert(_fake_notifications):
    notify.maybe_notify([
        {"ticker": "NOW", "industry": "Software - Application", "moat_score": 88.4,
         "thesis": "Workflow system of record."},
    ])
    assert _fake_notifications["toast"][0][0] == "AI-Resistant Moat Alert"
    body = _fake_notifications["whatsapp"][0]
    assert body.startswith("AI-Resistant Moat Alert:")
    assert "NOW" in body and "88.4" in body
