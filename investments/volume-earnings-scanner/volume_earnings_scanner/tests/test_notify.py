from __future__ import annotations

from volume_earnings_scanner import notify


def test_maybe_notify_noop_on_empty_list():
    # Empty list returns before the notifications module is ever imported -- no
    # mocking needed, and importing it for real here would be a real side effect.
    notify.maybe_notify([])


def test_maybe_notify_sends_both_channels_on_new_candidates(monkeypatch):
    sent = {}

    import sys
    import types

    fake_module = types.ModuleType("notifications")
    fake_module.send_toast_notification = lambda title, body: sent.setdefault("toast", (title, body))
    fake_module.send_whatsapp_notification = lambda body: sent.setdefault("whatsapp", body)
    monkeypatch.setitem(sys.modules, "notifications", fake_module)

    notify.maybe_notify([
        {"ticker": "ABCD", "company": "ABCD Inc", "signal_type": "both", "detail": "BOTH SIGNALS -- test"},
    ])

    assert "toast" in sent
    assert "whatsapp" in sent
    assert "ABCD" in sent["whatsapp"]
