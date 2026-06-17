"""Unit tests for memory_reflect.py helpers -- no live API calls."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from memory_reflect import (
    apply_memory_additions,
    apply_user_updates,
    parse_reflection_response,
    trim_memory_if_needed,
)


# --- parse_reflection_response ---

def test_parse_nothing_to_update():
    text = '{"memory_additions": [], "user_updates": [], "nothing_to_update": true}'
    result = parse_reflection_response(text)
    assert result["nothing_to_update"] is True
    assert result["memory_additions"] == []


def test_parse_with_additions():
    payload = {
        "memory_additions": ["- item one", "- item two"],
        "user_updates": ["- prefers short answers"],
        "nothing_to_update": False,
    }
    result = parse_reflection_response(json.dumps(payload))
    assert result["nothing_to_update"] is False
    assert len(result["memory_additions"]) == 2
    assert len(result["user_updates"]) == 1


def test_parse_fenced_json():
    text = "```json\n{\"memory_additions\": [\"- bullet\"], \"user_updates\": [], \"nothing_to_update\": false}\n```"
    result = parse_reflection_response(text)
    assert result["memory_additions"] == ["- bullet"]


def test_parse_malformed_returns_parse_error():
    result = parse_reflection_response("not json at all")
    assert result.get("_parse_error") is True
    assert result["nothing_to_update"] is True


def test_parse_missing_keys_defaults_to_empty():
    result = parse_reflection_response('{"nothing_to_update": false}')
    assert result["memory_additions"] == []
    assert result["user_updates"] == []


# --- apply_memory_additions ---

def test_apply_memory_additions_writes_section(tmp_path, monkeypatch):
    import memory_reflect
    mem_file = tmp_path / "MEMORY.md"
    mem_file.write_text("# Memory\n\n## Key Facts\n- existing\n", encoding="utf-8")
    monkeypatch.setattr(memory_reflect, "MEMORY_FILE", mem_file)

    result = apply_memory_additions(["- new item"], "2026-06-17")
    assert result is True
    content = mem_file.read_text(encoding="utf-8")
    assert "## 2026-06-17 Reflection" in content
    assert "- new item" in content
    assert "- existing" in content


def test_apply_memory_additions_empty_list_noop(tmp_path, monkeypatch):
    import memory_reflect
    mem_file = tmp_path / "MEMORY.md"
    mem_file.write_text("# Memory\n", encoding="utf-8")
    monkeypatch.setattr(memory_reflect, "MEMORY_FILE", mem_file)

    result = apply_memory_additions([], "2026-06-17")
    assert result is False
    assert mem_file.read_text(encoding="utf-8") == "# Memory\n"


def test_apply_memory_additions_creates_file_if_missing(tmp_path, monkeypatch):
    import memory_reflect
    mem_file = tmp_path / "MEMORY.md"
    monkeypatch.setattr(memory_reflect, "MEMORY_FILE", mem_file)

    result = apply_memory_additions(["- new item"], "2026-06-17")
    assert result is True
    assert mem_file.exists()
    assert "- new item" in mem_file.read_text(encoding="utf-8")


# --- apply_user_updates ---

def test_apply_user_updates_writes_section(tmp_path, monkeypatch):
    import memory_reflect
    user_file = tmp_path / "USER.md"
    user_file.write_text("# User\n", encoding="utf-8")
    monkeypatch.setattr(memory_reflect, "USER_FILE", user_file)

    result = apply_user_updates(["- prefers bullets"], "2026-06-17")
    assert result is True
    content = user_file.read_text(encoding="utf-8")
    assert "## 2026-06-17 Reflection" in content
    assert "- prefers bullets" in content


def test_apply_user_updates_empty_list_noop(tmp_path, monkeypatch):
    import memory_reflect
    user_file = tmp_path / "USER.md"
    user_file.write_text("# User\n", encoding="utf-8")
    monkeypatch.setattr(memory_reflect, "USER_FILE", user_file)

    result = apply_user_updates([], "2026-06-17")
    assert result is False


# --- trim_memory_if_needed ---

def test_trim_skips_when_small(tmp_path, monkeypatch):
    import memory_reflect
    mem_file = tmp_path / "MEMORY.md"
    mem_file.write_text("# Memory\n- line\n", encoding="utf-8")
    monkeypatch.setattr(memory_reflect, "MEMORY_FILE", mem_file)

    result = trim_memory_if_needed(max_lines=200)
    assert result is False


def test_trim_archives_overflow(tmp_path, monkeypatch):
    import memory_reflect
    mem_file = tmp_path / "MEMORY.md"
    mem_file.write_text("\n".join(f"- line {i}" for i in range(10)) + "\n", encoding="utf-8")
    monkeypatch.setattr(memory_reflect, "MEMORY_FILE", mem_file)
    monkeypatch.setattr(memory_reflect, "VAULT_DIR", tmp_path)

    result = trim_memory_if_needed(max_lines=5)
    assert result is True
    remaining = mem_file.read_text(encoding="utf-8").splitlines()
    assert len(remaining) <= 5


# =============================================================================
# New routing function tests (Task 13)
# =============================================================================

from memory_reflect import (
    append_to_entity_page,
    append_to_profile_file,
    append_to_topic_page,
    archive_decision,
    count_file_mentions,
    update_memory_active_items,
    update_memory_preferences,
)


# --- parse_reflection_response: full new schema ---

def test_parse_full_new_schema():
    payload = {
        "active_items": ["- (Jun 17) active thing"],
        "entity_updates": [{"page": "songbookdb", "content": "- note"}],
        "topic_updates": [{"page": "investment-strategy", "content": "- note"}],
        "new_entity_pages": [],
        "new_topic_pages": [],
        "profile_updates": [{"file": "goals", "content": "- goal note"}],
        "decision_archive": ["- completed decision"],
        "memory_preferences": ["- brief bullets"],
        "memory_additions": ["- fallback item"],
        "user_updates": ["- config change"],
        "nothing_to_update": False,
    }
    result = parse_reflection_response(json.dumps(payload))
    assert result["active_items"] == ["- (Jun 17) active thing"]
    assert result["entity_updates"] == [{"page": "songbookdb", "content": "- note"}]
    assert result["topic_updates"] == [{"page": "investment-strategy", "content": "- note"}]
    assert result["profile_updates"] == [{"file": "goals", "content": "- goal note"}]
    assert result["decision_archive"] == ["- completed decision"]
    assert result["memory_preferences"] == ["- brief bullets"]
    assert result["memory_additions"] == ["- fallback item"]
    assert result["user_updates"] == ["- config change"]
    assert result["nothing_to_update"] is False


# --- append_to_entity_page ---

def test_append_to_entity_page(tmp_path, monkeypatch):
    import memory_reflect
    monkeypatch.setattr(memory_reflect, "ENTITIES_DIR", tmp_path / "entities")
    (tmp_path / "entities").mkdir()
    page = tmp_path / "entities" / "songbookdb.md"
    page.write_text("# SongbookDB\n", encoding="utf-8")
    result = memory_reflect.append_to_entity_page("songbookdb", "- (Jun 17) test item")
    assert result is True
    assert "test item" in page.read_text(encoding="utf-8")


def test_append_to_entity_page_missing_returns_false(tmp_path, monkeypatch):
    import memory_reflect
    monkeypatch.setattr(memory_reflect, "ENTITIES_DIR", tmp_path / "entities")
    (tmp_path / "entities").mkdir()
    result = memory_reflect.append_to_entity_page("nonexistent", "- item")
    assert result is False


# --- append_to_topic_page ---

def test_append_to_topic_page(tmp_path, monkeypatch):
    import memory_reflect
    monkeypatch.setattr(memory_reflect, "TOPICS_DIR", tmp_path / "topics")
    (tmp_path / "topics").mkdir()
    page = tmp_path / "topics" / "investment-strategy.md"
    page.write_text("# Investment\n", encoding="utf-8")
    result = memory_reflect.append_to_topic_page("investment-strategy", "- (Jun 17) market note")
    assert result is True
    assert "market note" in page.read_text(encoding="utf-8")


def test_append_to_topic_page_missing_returns_false(tmp_path, monkeypatch):
    import memory_reflect
    monkeypatch.setattr(memory_reflect, "TOPICS_DIR", tmp_path / "topics")
    (tmp_path / "topics").mkdir()
    result = memory_reflect.append_to_topic_page("nonexistent", "- item")
    assert result is False


# --- append_to_profile_file ---

def test_append_to_profile_file(tmp_path, monkeypatch):
    import memory_reflect
    monkeypatch.setattr(memory_reflect, "PROFILE_DIR", tmp_path / "Profile")
    (tmp_path / "Profile").mkdir()
    profile = tmp_path / "Profile" / "goals.md"
    profile.write_text("# Goals\n_(not yet populated)_\n", encoding="utf-8")
    result = memory_reflect.append_to_profile_file("goals", "- want to grow hosting revenue", "2026-06-17")
    assert result is True
    content = profile.read_text(encoding="utf-8")
    assert "2026-06-17 Update" in content
    assert "grow hosting revenue" in content


def test_append_to_profile_file_missing_returns_false(tmp_path, monkeypatch):
    import memory_reflect
    monkeypatch.setattr(memory_reflect, "PROFILE_DIR", tmp_path / "Profile")
    (tmp_path / "Profile").mkdir()
    result = memory_reflect.append_to_profile_file("values", "- content", "2026-06-17")
    assert result is False


# --- archive_decision ---

def test_archive_decision_creates_quarter_file(tmp_path, monkeypatch):
    import memory_reflect
    monkeypatch.setattr(memory_reflect, "DECISIONS_DIR", tmp_path / "decisions")
    result = memory_reflect.archive_decision("- chose Codex backend", "2026-06-17")
    assert result is True
    archive = tmp_path / "decisions" / "2026-Q2.md"
    assert archive.exists()
    assert "chose Codex backend" in archive.read_text(encoding="utf-8")


def test_archive_decision_appends_to_existing(tmp_path, monkeypatch):
    import memory_reflect
    monkeypatch.setattr(memory_reflect, "DECISIONS_DIR", tmp_path / "decisions")
    (tmp_path / "decisions").mkdir()
    archive = tmp_path / "decisions" / "2026-Q2.md"
    archive.write_text("# Q2\n- first decision\n", encoding="utf-8")
    memory_reflect.archive_decision("- second decision", "2026-06-17")
    content = archive.read_text(encoding="utf-8")
    assert "first decision" in content
    assert "second decision" in content


# --- update_memory_active_items ---

def test_update_memory_active_items_finds_section(tmp_path, monkeypatch):
    import memory_reflect
    mem_file = tmp_path / "MEMORY.md"
    mem_file.write_text("# Memory\n\n## Active Items\n\n- existing\n\n## Preferences\n- pref\n", encoding="utf-8")
    monkeypatch.setattr(memory_reflect, "MEMORY_FILE", mem_file)
    result = memory_reflect.update_memory_active_items(["- new active item"])
    assert result is True
    content = mem_file.read_text(encoding="utf-8")
    assert "new active item" in content
    assert "existing" in content
    assert "pref" in content


def test_update_memory_active_items_creates_section(tmp_path, monkeypatch):
    import memory_reflect
    mem_file = tmp_path / "MEMORY.md"
    mem_file.write_text("# Memory\n\n## Preferences\n- pref\n", encoding="utf-8")
    monkeypatch.setattr(memory_reflect, "MEMORY_FILE", mem_file)
    result = memory_reflect.update_memory_active_items(["- new item"])
    assert result is True
    assert "## Active Items" in mem_file.read_text(encoding="utf-8")


def test_update_memory_active_items_empty_noop(tmp_path, monkeypatch):
    import memory_reflect
    mem_file = tmp_path / "MEMORY.md"
    mem_file.write_text("# Memory\n", encoding="utf-8")
    monkeypatch.setattr(memory_reflect, "MEMORY_FILE", mem_file)
    result = memory_reflect.update_memory_active_items([])
    assert result is False


# --- update_memory_preferences ---

def test_update_memory_preferences_finds_section(tmp_path, monkeypatch):
    import memory_reflect
    mem_file = tmp_path / "MEMORY.md"
    mem_file.write_text("# Memory\n\n## Preferences\n- existing pref\n\n---\n", encoding="utf-8")
    monkeypatch.setattr(memory_reflect, "MEMORY_FILE", mem_file)
    result = memory_reflect.update_memory_preferences(["- new pref"])
    assert result is True
    content = mem_file.read_text(encoding="utf-8")
    assert "new pref" in content
    assert "existing pref" in content


def test_update_memory_preferences_creates_section(tmp_path, monkeypatch):
    import memory_reflect
    mem_file = tmp_path / "MEMORY.md"
    mem_file.write_text("# Memory\n\n## Active Items\n- item\n", encoding="utf-8")
    monkeypatch.setattr(memory_reflect, "MEMORY_FILE", mem_file)
    result = memory_reflect.update_memory_preferences(["- new pref"])
    assert result is True
    assert "## Preferences" in mem_file.read_text(encoding="utf-8")


# --- count_file_mentions ---

def test_count_file_mentions(tmp_path, monkeypatch):
    import memory_reflect
    monkeypatch.setattr(memory_reflect, "VAULT_DIR", tmp_path)
    (tmp_path / "a.md").write_text("SongbookDB is great", encoding="utf-8")
    (tmp_path / "b.md").write_text("songbookdb rocks", encoding="utf-8")
    (tmp_path / "c.md").write_text("nothing here", encoding="utf-8")
    count = memory_reflect.count_file_mentions("SongbookDB")
    assert count == 2


def test_count_file_mentions_zero(tmp_path, monkeypatch):
    import memory_reflect
    monkeypatch.setattr(memory_reflect, "VAULT_DIR", tmp_path)
    (tmp_path / "a.md").write_text("something else", encoding="utf-8")
    count = memory_reflect.count_file_mentions("UnknownEntity")
    assert count == 0
