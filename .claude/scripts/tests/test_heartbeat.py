"""Unit tests for heartbeat.py — no live API calls, no LLM calls."""

from __future__ import annotations

import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from heartbeat import (
    auto_check_habits_show,
    build_snapshot,
    diff_snapshot,
    expire_old_drafts,
    reset_habits_if_new_day,
)


# =============================================================================
# diff_snapshot tests
# =============================================================================


def test_diff_first_run_is_first_run():
    """diff_snapshot with empty prev returns is_first_run=True."""
    curr = {
        "emails": {"gmail": [], "outlook": [], "error": None},
        "calendar": {"events": [], "has_show_today": False, "error": None},
        "active_drafts": [],
        "habits": "",
    }
    diff = diff_snapshot({}, curr)
    assert diff["is_first_run"] is True
    assert diff["has_changes"] is True


def test_diff_no_changes():
    """diff_snapshot with identical prev/curr returns has_changes=False."""
    snapshot = {
        "emails": {"gmail": [], "outlook": [], "error": None},
        "calendar": {"events": [], "has_show_today": False, "error": None},
        "active_drafts": [],
        "habits": "same",
    }
    diff = diff_snapshot(snapshot, snapshot)
    assert diff["has_changes"] is False
    assert diff["is_first_run"] is False


def test_diff_detects_habits_change():
    prev = {
        "emails": {"gmail": [], "outlook": [], "error": None},
        "calendar": {"events": [], "has_show_today": False, "error": None},
        "active_drafts": [],
        "habits": "old habits text",
    }
    curr = {**prev, "habits": "new habits text"}
    diff = diff_snapshot(prev, curr)
    assert diff["habits_delta"] is True
    assert diff["has_changes"] is True


def test_diff_detects_draft_changes():
    prev = {
        "emails": {"gmail": [], "outlook": [], "error": None},
        "calendar": {"events": [], "has_show_today": False, "error": None},
        "active_drafts": [{"filename": "old.md", "type": "email", "subject": "", "recipient": "", "status": "", "created": ""}],
        "habits": "",
    }
    curr = {**prev, "active_drafts": []}
    diff = diff_snapshot(prev, curr)
    assert diff["draft_changes"] is True
    assert diff["has_changes"] is True


# =============================================================================
# expire_old_drafts tests
# =============================================================================


def test_expire_old_drafts_moves_old_files(tmp_path, monkeypatch):
    """expire_old_drafts moves files older than DRAFT_EXPIRY_HOURS to expired/."""
    import heartbeat

    active_dir = tmp_path / "active"
    expired_dir = tmp_path / "expired"
    active_dir.mkdir()

    # Create a draft file with a created timestamp 48h ago
    from config import now_local

    old_ts = now_local().replace(hour=0, minute=0) - __import__("datetime").timedelta(hours=48)
    draft = active_dir / "2024-01-01_email_test.md"
    draft.write_text(
        f"---\ntype: email\ncreated: {old_ts.isoformat()}\nstatus: active\n---\nBody\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(heartbeat, "DRAFTS_ACTIVE_DIR", active_dir)
    monkeypatch.setattr(heartbeat, "DRAFTS_EXPIRED_DIR", expired_dir)
    monkeypatch.setattr(heartbeat, "DRAFT_EXPIRY_HOURS", 24)

    count = expire_old_drafts()
    assert count == 1
    assert not draft.exists()
    assert (expired_dir / draft.name).exists()


def test_expire_old_drafts_keeps_recent_files(tmp_path, monkeypatch):
    """expire_old_drafts leaves recent drafts alone."""
    import heartbeat

    active_dir = tmp_path / "active"
    active_dir.mkdir()

    from config import now_local

    recent_ts = now_local()
    draft = active_dir / "2024-01-01_email_recent.md"
    draft.write_text(
        f"---\ntype: email\ncreated: {recent_ts.isoformat()}\nstatus: active\n---\nBody\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(heartbeat, "DRAFTS_ACTIVE_DIR", active_dir)
    monkeypatch.setattr(heartbeat, "DRAFT_EXPIRY_HOURS", 24)

    count = expire_old_drafts()
    assert count == 0
    assert draft.exists()


# =============================================================================
# reset_habits_if_new_day tests
# =============================================================================


def test_reset_habits_if_new_day_skips_same_day(tmp_path, monkeypatch):
    """reset_habits_if_new_day skips if last_habits_reset_date == today."""
    import heartbeat
    from config import now_local

    habits_file = tmp_path / "HABITS.md"
    habits_file.write_text("- [x] **Shows**\n- [ ] **Exercise**\n", encoding="utf-8")
    monkeypatch.setattr(heartbeat, "HABITS_FILE", habits_file)

    today = now_local().strftime("%Y-%m-%d")
    state = {"last_habits_reset_date": today}
    result = reset_habits_if_new_day(state)
    assert result is False


def test_reset_habits_if_new_day_resets_on_new_day(tmp_path, monkeypatch):
    """reset_habits_if_new_day resets checkboxes if last reset was yesterday."""
    import heartbeat

    habits_file = tmp_path / "HABITS.md"
    habits_file.write_text("- [x] **Shows**\n- [x] **Exercise**\n", encoding="utf-8")
    monkeypatch.setattr(heartbeat, "HABITS_FILE", habits_file)

    state = {"last_habits_reset_date": "2000-01-01"}
    result = reset_habits_if_new_day(state)
    assert result is True
    content = habits_file.read_text(encoding="utf-8")
    assert "- [ ]" in content


# =============================================================================
# auto_check_habits_show tests
# =============================================================================


def test_auto_check_habits_show_checks_when_show(tmp_path, monkeypatch):
    import heartbeat

    habits_file = tmp_path / "HABITS.md"
    habits_file.write_text("- [ ] **Shows**\n- [ ] **Exercise**\n", encoding="utf-8")
    monkeypatch.setattr(heartbeat, "HABITS_FILE", habits_file)

    result = auto_check_habits_show(has_show_today=True)
    assert result is True
    assert "- [x] **Shows**" in habits_file.read_text(encoding="utf-8")


def test_auto_check_habits_show_skips_when_no_show(tmp_path, monkeypatch):
    import heartbeat

    habits_file = tmp_path / "HABITS.md"
    habits_file.write_text("- [ ] **Shows**\n", encoding="utf-8")
    monkeypatch.setattr(heartbeat, "HABITS_FILE", habits_file)

    result = auto_check_habits_show(has_show_today=False)
    assert result is False
    assert "- [ ] **Shows**" in habits_file.read_text(encoding="utf-8")
