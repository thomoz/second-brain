"""Unit tests for whatsapp_health.py."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import whatsapp_health as wh


def _write_log(tmp_path: Path, lines: list[str]) -> Path:
    log_path = tmp_path / "whatsapp_runs.log"
    log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return log_path


def test_check_health_missing_log_is_healthy(tmp_path):
    result = wh.check_health(tmp_path / "nope.log")
    assert result == {"healthy": True, "consecutive_errors": 0}


def test_check_health_no_errors_is_healthy(tmp_path):
    log_path = _write_log(tmp_path, [
        "All adapters connected",
        "Message from 61410868612@c.us: hi",
    ])
    result = wh.check_health(log_path)
    assert result["healthy"] is True
    assert result["consecutive_errors"] == 0


def test_check_health_below_threshold_is_healthy(tmp_path):
    log_path = _write_log(tmp_path, [
        "All adapters connected",
        "WhatsApp poll error: timeout",
        "WhatsApp poll error: timeout",
    ])
    result = wh.check_health(log_path)
    assert result["healthy"] is True
    assert result["consecutive_errors"] == 2


def test_check_health_at_threshold_is_unhealthy(tmp_path):
    log_path = _write_log(tmp_path, [
        "All adapters connected",
        "WhatsApp poll error: timeout",
        "WhatsApp poll error: timeout",
        "WhatsApp poll error: timeout",
    ])
    result = wh.check_health(log_path)
    assert result["healthy"] is False
    assert result["consecutive_errors"] == 3


def test_check_health_stops_counting_at_last_success(tmp_path):
    # 3 errors happened long ago, but a real message was processed since --
    # only the 1 error after that message should count.
    log_path = _write_log(tmp_path, [
        "WhatsApp poll error: timeout",
        "WhatsApp poll error: timeout",
        "WhatsApp poll error: timeout",
        "Message from 61410868612@c.us: hi",
        "WhatsApp poll error: timeout",
    ])
    result = wh.check_health(log_path)
    assert result["healthy"] is True
    assert result["consecutive_errors"] == 1


def test_run_health_check_alerts_once_then_dedupes(tmp_path, monkeypatch):
    log_path = _write_log(tmp_path, [
        "WhatsApp poll error: timeout",
        "WhatsApp poll error: timeout",
        "WhatsApp poll error: timeout",
    ])
    monkeypatch.setattr(wh, "WHATSAPP_LOG_PATH", log_path)
    monkeypatch.setattr(wh, "WHATSAPP_HEALTH_STATE_FILE", tmp_path / "state.json")
    monkeypatch.setattr(wh, "check_health", lambda: {"healthy": False, "consecutive_errors": 3})

    sent = []
    monkeypatch.setattr(
        "notifications.send_whatsapp_notification", lambda msg, **kw: sent.append(msg)
    )
    monkeypatch.setattr("notifications.send_toast_notification", lambda *a, **kw: None)

    first = wh.run_health_check()
    assert first is not None
    assert len(sent) == 1

    second = wh.run_health_check()
    assert second is None
    assert len(sent) == 1  # not re-sent while still unhealthy


def test_run_health_check_clears_alert_on_recovery(tmp_path, monkeypatch):
    monkeypatch.setattr(wh, "WHATSAPP_HEALTH_STATE_FILE", tmp_path / "state.json")
    from shared import save_state

    save_state(tmp_path / "state.json", {"alerted": True})
    monkeypatch.setattr(wh, "check_health", lambda: {"healthy": True, "consecutive_errors": 0})
    monkeypatch.setattr("notifications.send_whatsapp_notification", lambda msg, **kw: None)
    monkeypatch.setattr("notifications.send_toast_notification", lambda *a, **kw: None)

    result = wh.run_health_check()

    assert result is None
    from shared import load_state

    state = load_state(tmp_path / "state.json")
    assert state["alerted"] is False
