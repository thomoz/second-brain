"""Unit tests for handoff_check.py — no live toast calls, no network."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import handoff_check  # noqa: E402

SAMPLE_HANDOFF_FILE = """---
title: WhatsApp Handoff Messages For Local Session
type: system
---
# WhatsApp Handoff Messages — For Local Session

Notes left via WhatsApp that need to surface in the next local session.

## Active handoffs

## 2026-08-08 [WhatsApp save]
Add some sort of copper ETFs etc, two buckets for.
Also turn Siri back on phone.

## 2026-08-13 [WhatsApp save]
Deep dive Disney.
"""


def test_parse_handoff_entries_extracts_dated_entries():
    entries = handoff_check.parse_handoff_entries(SAMPLE_HANDOFF_FILE)
    assert len(entries) == 2
    assert entries[0]["date"] == "2026-08-08"
    assert "copper ETFs" in entries[0]["text"]
    assert entries[1]["date"] == "2026-08-13"
    assert entries[1]["text"] == "Deep dive Disney."


def test_parse_handoff_entries_stops_before_a_trailing_non_dated_section():
    # Defensive case: if a future section is ever added below the entries, parsing
    # must not swallow it as if it were a handoff.
    text = SAMPLE_HANDOFF_FILE + "\n## Archive\nOld handled items go here.\n"
    entries = handoff_check.parse_handoff_entries(text)
    assert len(entries) == 2
    assert not any("Archive" in e["text"] or "Old handled" in e["text"] for e in entries)


def test_parse_handoff_entries_empty_section():
    text = "# Handoffs\n\n## Active handoffs\n\n## Archive\n- stuff\n"
    assert handoff_check.parse_handoff_entries(text) == []


def test_parse_handoff_entries_missing_section_returns_empty():
    assert handoff_check.parse_handoff_entries("# Handoffs\n\nNo handoff section here.\n") == []


def test_first_run_seeds_baseline_without_alerting(tmp_path, monkeypatch):
    handoff_file = tmp_path / "whatsapp-handoff-messages-for-local-session.md"
    handoff_file.write_text(SAMPLE_HANDOFF_FILE, encoding="utf-8")
    state_file = tmp_path / "handoff-check-state.json"
    monkeypatch.setattr(handoff_check, "HANDOFF_FILE", handoff_file)
    monkeypatch.setattr(handoff_check, "HANDOFF_STATE_FILE", state_file)

    alerts = []
    monkeypatch.setattr(handoff_check, "send_toast_notification", lambda title, body: alerts.append((title, body)))

    new_entries = handoff_check.check_for_new_handoffs()

    assert new_entries == []
    assert alerts == []
    assert state_file.exists()


def test_second_run_with_no_changes_does_not_alert(tmp_path, monkeypatch):
    handoff_file = tmp_path / "whatsapp-handoff-messages-for-local-session.md"
    handoff_file.write_text(SAMPLE_HANDOFF_FILE, encoding="utf-8")
    state_file = tmp_path / "handoff-check-state.json"
    monkeypatch.setattr(handoff_check, "HANDOFF_FILE", handoff_file)
    monkeypatch.setattr(handoff_check, "HANDOFF_STATE_FILE", state_file)

    alerts = []
    monkeypatch.setattr(handoff_check, "send_toast_notification", lambda title, body: alerts.append((title, body)))

    handoff_check.check_for_new_handoffs()  # seeds baseline
    new_entries = handoff_check.check_for_new_handoffs()  # nothing changed

    assert new_entries == []
    assert alerts == []


def test_new_entry_added_after_baseline_triggers_alert(tmp_path, monkeypatch):
    handoff_file = tmp_path / "whatsapp-handoff-messages-for-local-session.md"
    handoff_file.write_text(SAMPLE_HANDOFF_FILE, encoding="utf-8")
    state_file = tmp_path / "handoff-check-state.json"
    monkeypatch.setattr(handoff_check, "HANDOFF_FILE", handoff_file)
    monkeypatch.setattr(handoff_check, "HANDOFF_STATE_FILE", state_file)

    alerts = []
    monkeypatch.setattr(handoff_check, "send_toast_notification", lambda title, body: alerts.append((title, body)))

    handoff_check.check_for_new_handoffs()  # seeds baseline (2 existing entries)

    handoff_file.write_text(
        SAMPLE_HANDOFF_FILE + "\n## 2026-08-14 [WhatsApp save]\nCheck the mail.\n",
        encoding="utf-8",
    )
    new_entries = handoff_check.check_for_new_handoffs()

    assert len(new_entries) == 1
    assert new_entries[0]["text"] == "Check the mail."
    assert len(alerts) == 1
    title, body = alerts[0]
    assert title == "New Handoff"
    assert "Check the mail." in body


def test_multiple_new_entries_alert_once_with_count_in_title(tmp_path, monkeypatch):
    handoff_file = tmp_path / "whatsapp-handoff-messages-for-local-session.md"
    handoff_file.write_text(SAMPLE_HANDOFF_FILE, encoding="utf-8")
    state_file = tmp_path / "handoff-check-state.json"
    monkeypatch.setattr(handoff_check, "HANDOFF_FILE", handoff_file)
    monkeypatch.setattr(handoff_check, "HANDOFF_STATE_FILE", state_file)
    monkeypatch.setattr(handoff_check, "send_toast_notification", lambda title, body: None)

    handoff_check.check_for_new_handoffs()  # seeds baseline

    handoff_file.write_text(
        SAMPLE_HANDOFF_FILE
        + "\n## 2026-08-14 [WhatsApp save]\nFirst new one.\n"
        + "\n## 2026-08-14 [WhatsApp save]\nSecond new one.\n",
        encoding="utf-8",
    )

    alerts = []
    monkeypatch.setattr(handoff_check, "send_toast_notification", lambda title, body: alerts.append((title, body)))
    new_entries = handoff_check.check_for_new_handoffs()

    assert len(new_entries) == 2
    assert len(alerts) == 1
    assert alerts[0][0] == "2 New Handoffs"


def test_removed_handoff_does_not_cause_a_false_new_alert(tmp_path, monkeypatch):
    """If a handoff is archived/removed (per the file's own instructions) and never
    comes back, it must not be treated as "new" again on some future run."""
    handoff_file = tmp_path / "whatsapp-handoff-messages-for-local-session.md"
    handoff_file.write_text(SAMPLE_HANDOFF_FILE, encoding="utf-8")
    state_file = tmp_path / "handoff-check-state.json"
    monkeypatch.setattr(handoff_check, "HANDOFF_FILE", handoff_file)
    monkeypatch.setattr(handoff_check, "HANDOFF_STATE_FILE", state_file)
    monkeypatch.setattr(handoff_check, "send_toast_notification", lambda title, body: None)

    handoff_check.check_for_new_handoffs()  # seeds baseline (2 entries)

    # Remove the Disney entry (simulating it being handled and archived)
    trimmed = SAMPLE_HANDOFF_FILE.replace(
        "## 2026-08-13 [WhatsApp save]\nDeep dive Disney.\n", ""
    )
    handoff_file.write_text(trimmed, encoding="utf-8")
    new_entries = handoff_check.check_for_new_handoffs()
    assert new_entries == []

    # Re-run with the trimmed file again -- still nothing new
    new_entries = handoff_check.check_for_new_handoffs()
    assert new_entries == []


def test_dry_run_does_not_write_state_or_alert(tmp_path, monkeypatch):
    handoff_file = tmp_path / "whatsapp-handoff-messages-for-local-session.md"
    handoff_file.write_text(SAMPLE_HANDOFF_FILE, encoding="utf-8")
    state_file = tmp_path / "handoff-check-state.json"
    monkeypatch.setattr(handoff_check, "HANDOFF_FILE", handoff_file)
    monkeypatch.setattr(handoff_check, "HANDOFF_STATE_FILE", state_file)

    alerts = []
    monkeypatch.setattr(handoff_check, "send_toast_notification", lambda title, body: alerts.append((title, body)))

    handoff_check.check_for_new_handoffs(dry_run=True)

    assert alerts == []
    assert not state_file.exists()


def test_missing_handoff_file_returns_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(handoff_check, "HANDOFF_FILE", tmp_path / "does-not-exist.md")
    assert handoff_check.check_for_new_handoffs() == []
