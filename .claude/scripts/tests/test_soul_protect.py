"""Tests for the soul-protect PreToolUse hook."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

HOOK = str(Path(__file__).resolve().parent.parent.parent / "hooks" / "soul-protect.py")

_AGENT_ENV = {**os.environ, "AGENT_INVOKED_BY": "heartbeat"}
_HUMAN_ENV = {k: v for k, v in os.environ.items() if k != "AGENT_INVOKED_BY"}


def _run(tool_name: str, file_path: str, env: dict | None = None) -> subprocess.CompletedProcess:
    payload = json.dumps({"tool_name": tool_name, "tool_input": {"file_path": file_path}})
    return subprocess.run(
        [sys.executable, HOOK],
        input=payload.encode(),
        capture_output=True,
        env=env or _AGENT_ENV,
    )


def _is_denied(result: subprocess.CompletedProcess) -> bool:
    """Return True if hook output contains a JSON deny decision."""
    try:
        out = json.loads(result.stdout.decode())
        decision = (
            out.get("hookSpecificOutput", {}).get("permissionDecision", "")
        )
        return decision == "deny"
    except (json.JSONDecodeError, AttributeError):
        return False


# =============================================================================
# SOUL.md protection
# =============================================================================


class TestSoulMdProtection:
    def test_soul_md_write_blocked_by_agent(self) -> None:
        result = _run("Write", "Memory/SOUL.md")
        assert _is_denied(result)

    def test_soul_md_edit_blocked_by_agent(self) -> None:
        result = _run("Edit", "Memory/SOUL.md")
        assert _is_denied(result)

    def test_soul_md_full_path_blocked(self) -> None:
        result = _run("Write", "/home/secondbrain/second-brain/Memory/SOUL.md")
        assert _is_denied(result)

    def test_soul_md_allowed_for_human(self) -> None:
        result = _run("Write", "Memory/SOUL.md", env=_HUMAN_ENV)
        assert not _is_denied(result)
        assert result.returncode == 0


# =============================================================================
# Hook script protection (.claude/hooks/)
# =============================================================================


class TestHookScriptProtection:
    def test_block_secrets_hook_blocked(self) -> None:
        result = _run("Write", ".claude/hooks/block-secrets.py")
        assert _is_denied(result)

    def test_command_guard_hook_blocked(self) -> None:
        result = _run("Edit", ".claude/hooks/command-guard.py")
        assert _is_denied(result)

    def test_soul_protect_hook_blocked(self) -> None:
        result = _run("Write", ".claude/hooks/soul-protect.py")
        assert _is_denied(result)

    def test_any_hook_blocked_with_full_path(self) -> None:
        result = _run("Write", "/home/secondbrain/second-brain/.claude/hooks/session-start-context.py")
        assert _is_denied(result)

    def test_windows_path_hook_blocked(self) -> None:
        result = _run("Write", r"O:\AI\Dynamous\Courses\second-brain-workshop\.claude\hooks\block-secrets.py")
        assert _is_denied(result)

    def test_hook_blocked_allowed_for_human(self) -> None:
        result = _run("Write", ".claude/hooks/block-secrets.py", env=_HUMAN_ENV)
        assert not _is_denied(result)
        assert result.returncode == 0


# =============================================================================
# Settings file protection (.claude/settings.json)
# =============================================================================


class TestSettingsProtection:
    def test_settings_json_blocked(self) -> None:
        result = _run("Write", ".claude/settings.json")
        assert _is_denied(result)

    def test_settings_local_json_blocked(self) -> None:
        result = _run("Edit", ".claude/settings.local.json")
        assert _is_denied(result)

    def test_settings_full_path_blocked(self) -> None:
        result = _run("Write", "/home/secondbrain/second-brain/.claude/settings.json")
        assert _is_denied(result)

    def test_settings_windows_path_blocked(self) -> None:
        result = _run("Write", r"O:\AI\Dynamous\Courses\second-brain-workshop\.claude\settings.json")
        assert _is_denied(result)

    def test_settings_allowed_for_human(self) -> None:
        result = _run("Write", ".claude/settings.json", env=_HUMAN_ENV)
        assert not _is_denied(result)
        assert result.returncode == 0


# =============================================================================
# Files that must NOT be blocked
# =============================================================================


class TestAllowedFiles:
    def test_daily_log_allowed(self) -> None:
        result = _run("Write", "Memory/daily/2026-06-18.md")
        assert not _is_denied(result)

    def test_draft_allowed(self) -> None:
        result = _run("Write", "Memory/drafts/active/2026-06-18_email_reply.md")
        assert not _is_denied(result)

    def test_habits_allowed(self) -> None:
        result = _run("Edit", "Memory/HABITS.md")
        assert not _is_denied(result)

    def test_memory_md_allowed(self) -> None:
        result = _run("Write", "Memory/MEMORY.md")
        assert not _is_denied(result)

    def test_entity_page_allowed(self) -> None:
        result = _run("Write", "Memory/entities/songbookdb.md")
        assert not _is_denied(result)

    def test_skill_file_allowed(self) -> None:
        result = _run("Write", ".claude/skills/ask-me-questions/SKILL.md")
        assert not _is_denied(result)

    def test_malformed_json_exits_zero(self) -> None:
        result = subprocess.run(
            [sys.executable, HOOK],
            input=b"not json",
            capture_output=True,
            env=_AGENT_ENV,
        )
        assert result.returncode == 0

    def test_empty_file_path_exits_zero(self) -> None:
        result = _run("Write", "")
        assert not _is_denied(result)
        assert result.returncode == 0
