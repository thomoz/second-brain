"""Unit tests for memory_lint.py — no live file system access, uses tmp_path."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import memory_lint


# --- check_broken_links ---

def test_check_broken_links_detects_missing_page(tmp_path, monkeypatch):
    monkeypatch.setattr(memory_lint, "VAULT_DIR", tmp_path)
    monkeypatch.setattr(memory_lint, "ENTITIES_DIR", tmp_path / "entities")
    monkeypatch.setattr(memory_lint, "TOPICS_DIR", tmp_path / "topics")
    monkeypatch.setattr(memory_lint, "DECISIONS_DIR", tmp_path / "decisions")
    (tmp_path / "entities").mkdir()
    (tmp_path / "topics").mkdir()
    (tmp_path / "decisions").mkdir()
    # MEMORY.md links to a page that doesn't exist
    (tmp_path / "MEMORY.md").write_text("[[nonexistent-page]]", encoding="utf-8")
    issues = memory_lint.check_broken_links()
    assert any("nonexistent-page" in i for i in issues)


def test_check_broken_links_passes_for_existing_page(tmp_path, monkeypatch):
    monkeypatch.setattr(memory_lint, "VAULT_DIR", tmp_path)
    monkeypatch.setattr(memory_lint, "ENTITIES_DIR", tmp_path / "entities")
    monkeypatch.setattr(memory_lint, "TOPICS_DIR", tmp_path / "topics")
    monkeypatch.setattr(memory_lint, "DECISIONS_DIR", tmp_path / "decisions")
    (tmp_path / "entities").mkdir()
    (tmp_path / "topics").mkdir()
    (tmp_path / "decisions").mkdir()
    (tmp_path / "entities" / "songbookdb.md").write_text("# SongbookDB\n", encoding="utf-8")
    (tmp_path / "MEMORY.md").write_text("[[songbookdb]]", encoding="utf-8")
    issues = memory_lint.check_broken_links()
    assert not any("songbookdb" in i for i in issues)


# --- check_orphan_pages ---

def test_check_orphan_pages_detects_unlisted_page(tmp_path, monkeypatch):
    monkeypatch.setattr(memory_lint, "VAULT_DIR", tmp_path)
    monkeypatch.setattr(memory_lint, "ENTITIES_DIR", tmp_path / "entities")
    monkeypatch.setattr(memory_lint, "TOPICS_DIR", tmp_path / "topics")
    monkeypatch.setattr(memory_lint, "DECISIONS_DIR", tmp_path / "decisions")
    monkeypatch.setattr(memory_lint, "MEMORY_FILE", tmp_path / "MEMORY.md")
    monkeypatch.setattr(memory_lint, "PAGE_DIRS", {
        "entities": tmp_path / "entities",
        "topics": tmp_path / "topics",
        "decisions": tmp_path / "decisions",
    })
    (tmp_path / "entities").mkdir()
    (tmp_path / "topics").mkdir()
    (tmp_path / "decisions").mkdir()
    (tmp_path / "entities" / "orphan.md").write_text("# Orphan\n", encoding="utf-8")
    (tmp_path / "MEMORY.md").write_text("# Memory\n## Active Items\n- item\n", encoding="utf-8")
    issues = memory_lint.check_orphan_pages()
    assert any("orphan" in i for i in issues)


def test_check_orphan_pages_passes_for_indexed_page(tmp_path, monkeypatch):
    monkeypatch.setattr(memory_lint, "VAULT_DIR", tmp_path)
    monkeypatch.setattr(memory_lint, "ENTITIES_DIR", tmp_path / "entities")
    monkeypatch.setattr(memory_lint, "TOPICS_DIR", tmp_path / "topics")
    monkeypatch.setattr(memory_lint, "DECISIONS_DIR", tmp_path / "decisions")
    monkeypatch.setattr(memory_lint, "MEMORY_FILE", tmp_path / "MEMORY.md")
    monkeypatch.setattr(memory_lint, "PAGE_DIRS", {
        "entities": tmp_path / "entities",
        "topics": tmp_path / "topics",
        "decisions": tmp_path / "decisions",
    })
    (tmp_path / "entities").mkdir()
    (tmp_path / "topics").mkdir()
    (tmp_path / "decisions").mkdir()
    (tmp_path / "entities" / "songbookdb.md").write_text("# SongbookDB\n", encoding="utf-8")
    (tmp_path / "MEMORY.md").write_text("[[songbookdb]]", encoding="utf-8")
    issues = memory_lint.check_orphan_pages()
    assert not any("songbookdb" in i for i in issues)


# --- check_stale_active_items ---

def test_check_stale_active_items_detects_old_date(tmp_path, monkeypatch):
    monkeypatch.setattr(memory_lint, "MEMORY_FILE", tmp_path / "MEMORY.md")
    # Write an active item with a date 60 days ago
    from datetime import datetime, timedelta
    old_date = datetime.now() - timedelta(days=60)
    month_abbr = old_date.strftime("%b")
    day = old_date.day
    content = f"# Memory\n\n## Active Items\n\n- ({month_abbr} {day}) old unresolved item\n\n## Preferences\n"
    (tmp_path / "MEMORY.md").write_text(content, encoding="utf-8")
    issues = memory_lint.check_stale_active_items()
    assert any("old unresolved item" in i for i in issues)


def test_check_stale_active_items_passes_for_recent(tmp_path, monkeypatch):
    monkeypatch.setattr(memory_lint, "MEMORY_FILE", tmp_path / "MEMORY.md")
    from datetime import datetime
    today = datetime.now()
    month_abbr = today.strftime("%b")
    day = today.day
    content = f"# Memory\n\n## Active Items\n\n- ({month_abbr} {day}) recent item\n\n## Preferences\n"
    (tmp_path / "MEMORY.md").write_text(content, encoding="utf-8")
    issues = memory_lint.check_stale_active_items()
    assert not any("recent item" in i for i in issues)


# --- check_missing_frontmatter ---

def test_check_missing_frontmatter_detects_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(memory_lint, "VAULT_DIR", tmp_path)
    monkeypatch.setattr(memory_lint, "ENTITIES_DIR", tmp_path / "entities")
    monkeypatch.setattr(memory_lint, "TOPICS_DIR", tmp_path / "topics")
    monkeypatch.setattr(memory_lint, "DECISIONS_DIR", tmp_path / "decisions")
    monkeypatch.setattr(memory_lint, "PAGE_DIRS", {
        "entities": tmp_path / "entities",
        "topics": tmp_path / "topics",
        "decisions": tmp_path / "decisions",
    })
    (tmp_path / "entities").mkdir()
    (tmp_path / "topics").mkdir()
    (tmp_path / "decisions").mkdir()
    (tmp_path / "entities" / "nofm.md").write_text("# No frontmatter\n", encoding="utf-8")
    issues = memory_lint.check_missing_frontmatter()
    assert any("nofm" in i for i in issues)


def test_check_missing_frontmatter_passes_for_valid(tmp_path, monkeypatch):
    monkeypatch.setattr(memory_lint, "VAULT_DIR", tmp_path)
    monkeypatch.setattr(memory_lint, "ENTITIES_DIR", tmp_path / "entities")
    monkeypatch.setattr(memory_lint, "TOPICS_DIR", tmp_path / "topics")
    monkeypatch.setattr(memory_lint, "DECISIONS_DIR", tmp_path / "decisions")
    monkeypatch.setattr(memory_lint, "PAGE_DIRS", {
        "entities": tmp_path / "entities",
        "topics": tmp_path / "topics",
        "decisions": tmp_path / "decisions",
    })
    (tmp_path / "entities").mkdir()
    (tmp_path / "topics").mkdir()
    (tmp_path / "decisions").mkdir()
    content = "---\ntitle: Test\ntype: entity\ncreated: 2026-06-17\nupdated: 2026-06-17\n---\n# Test\n"
    (tmp_path / "entities" / "test.md").write_text(content, encoding="utf-8")
    issues = memory_lint.check_missing_frontmatter()
    assert not any("test" in i for i in issues)
