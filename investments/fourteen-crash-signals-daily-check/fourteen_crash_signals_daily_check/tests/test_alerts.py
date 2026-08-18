from __future__ import annotations

import sys
import types

from fourteen_crash_signals_daily_check import alerts


def _fake_notifications_module(toast_calls, whatsapp_calls):
    fake_module = types.ModuleType("notifications")
    fake_module.send_toast_notification = lambda *a, **k: toast_calls.append((a, k))
    fake_module.send_whatsapp_notification = lambda *a, **k: whatsapp_calls.append((a, k))
    return fake_module


def test_maybe_notify_skips_when_nothing_firing(db_conn, monkeypatch):
    toast_calls, whatsapp_calls = [], []
    monkeypatch.setitem(sys.modules, "notifications", _fake_notifications_module(toast_calls, whatsapp_calls))

    alerts.maybe_notify(db_conn, [{"marker_key": "m1", "is_firing": False, "detail": "ok"}])
    assert toast_calls == []
    assert whatsapp_calls == []


def test_maybe_notify_fires_on_first_time_firing(db_conn, monkeypatch):
    toast_calls, whatsapp_calls = [], []
    monkeypatch.setitem(sys.modules, "notifications", _fake_notifications_module(toast_calls, whatsapp_calls))

    alerts.maybe_notify(db_conn, [{"marker_key": "m1", "is_firing": True, "detail": "spread wide"}])
    assert len(toast_calls) == 1
    assert len(whatsapp_calls) == 1
    assert "spread wide" in whatsapp_calls[0][0][0]


def test_maybe_notify_does_not_refire_on_repeat_firing(db_conn, monkeypatch):
    toast_calls, whatsapp_calls = [], []
    monkeypatch.setitem(sys.modules, "notifications", _fake_notifications_module(toast_calls, whatsapp_calls))

    alerts.maybe_notify(db_conn, [{"marker_key": "m1", "is_firing": True, "detail": "spread wide"}])
    alerts.maybe_notify(db_conn, [{"marker_key": "m1", "is_firing": True, "detail": "still wide"}])
    assert len(whatsapp_calls) == 1  # only the first call alerted


def test_maybe_notify_refires_after_transition_back_to_firing(db_conn, monkeypatch):
    toast_calls, whatsapp_calls = [], []
    monkeypatch.setitem(sys.modules, "notifications", _fake_notifications_module(toast_calls, whatsapp_calls))

    alerts.maybe_notify(db_conn, [{"marker_key": "m1", "is_firing": True, "detail": "fire"}])
    alerts.maybe_notify(db_conn, [{"marker_key": "m1", "is_firing": False, "detail": "resolved"}])
    alerts.maybe_notify(db_conn, [{"marker_key": "m1", "is_firing": True, "detail": "fire again"}])
    assert len(whatsapp_calls) == 2
