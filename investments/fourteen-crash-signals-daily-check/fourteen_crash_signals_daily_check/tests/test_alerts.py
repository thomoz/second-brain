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


def _fake_result(verdict: str, streak_days: int = 5, detail: str = "spread wide"):
    from mytrader.checks import CheckResult

    return CheckResult(name="credit_spread_streak", verdict=verdict, detail=detail, data={"streak_days": streak_days})


def test_notify_credit_spread_streak_daily_sends_on_every_flag_call(monkeypatch):
    whatsapp_calls = []
    monkeypatch.setitem(sys.modules, "notifications", _fake_notifications_module([], whatsapp_calls))

    alerts.notify_credit_spread_streak_daily(_fake_result("flag", streak_days=3))
    alerts.notify_credit_spread_streak_daily(_fake_result("flag", streak_days=4))
    assert len(whatsapp_calls) == 2  # unlike maybe_notify, this fires every call while flagging


def test_notify_credit_spread_streak_daily_does_not_send_when_ok(monkeypatch):
    whatsapp_calls = []
    monkeypatch.setitem(sys.modules, "notifications", _fake_notifications_module([], whatsapp_calls))

    alerts.notify_credit_spread_streak_daily(_fake_result("ok"))
    assert whatsapp_calls == []


def test_notify_credit_spread_streak_daily_message_contains_streak_days(monkeypatch):
    whatsapp_calls = []
    monkeypatch.setitem(sys.modules, "notifications", _fake_notifications_module([], whatsapp_calls))

    alerts.notify_credit_spread_streak_daily(_fake_result("flag", streak_days=7))
    assert "day 7" in whatsapp_calls[0][0][0]
