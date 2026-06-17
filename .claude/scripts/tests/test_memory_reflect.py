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
