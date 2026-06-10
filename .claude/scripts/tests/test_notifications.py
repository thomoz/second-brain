"""Unit tests for notifications.py."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from notifications import send_console_notification, send_toast_notification


def test_send_console_notification_returns_true(capsys):
    result = send_console_notification("Test Title", "Test message")
    assert result is True
    captured = capsys.readouterr()
    assert "Test Title" in captured.out
    assert "Test message" in captured.out


def test_send_console_notification_formats_output(capsys):
    send_console_notification("Alert", "Something happened")
    captured = capsys.readouterr()
    assert "[NOTIFY] Alert" in captured.out
    assert "Something happened" in captured.out


def test_send_toast_falls_back_to_console_on_non_windows(monkeypatch, capsys):
    monkeypatch.setattr("sys.platform", "linux")
    result = send_toast_notification("Test", "Message")
    assert result is True
    captured = capsys.readouterr()
    assert "Test" in captured.out


def test_send_toast_falls_back_on_import_error(monkeypatch, capsys):
    monkeypatch.setattr("sys.platform", "win32")
    with patch.dict("sys.modules", {"win10toast_click": None}):
        result = send_toast_notification("Test", "Message")
        # Should fall back to console
        assert result is True
