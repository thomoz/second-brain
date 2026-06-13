"""Tests for the command-guard PreToolUse hook."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HOOK = str(Path(__file__).resolve().parent.parent.parent / "hooks" / "command-guard.py")


def _run(tool_name: str, tool_input: dict) -> subprocess.CompletedProcess:
    payload = json.dumps({"tool_name": tool_name, "tool_input": tool_input})
    return subprocess.run(
        [sys.executable, HOOK],
        input=payload.encode(),
        capture_output=True,
    )


# =============================================================================
# Dangerous Bash (must block -- exit 2)
# =============================================================================


class TestDangerousBash:
    """Destructive or dangerous bash commands must be blocked."""

    def test_rm_rf_blocked(self) -> None:
        result = _run("Bash", {"command": "rm -rf Memory/"})
        assert result.returncode == 2

    def test_remove_item_recurse_blocked(self) -> None:
        result = _run("Bash", {"command": "Remove-Item -Recurse -Force .claude/data"})
        assert result.returncode == 2

    def test_pip_install_blocked(self) -> None:
        result = _run("Bash", {"command": "pip install requests"})
        assert result.returncode == 2

    def test_sudo_apt_install_blocked(self) -> None:
        result = _run("Bash", {"command": "sudo apt install curl"})
        assert result.returncode == 2

    def test_set_execution_policy_blocked(self) -> None:
        result = _run("Bash", {"command": "Set-ExecutionPolicy Unrestricted"})
        assert result.returncode == 2

    def test_del_recursive_blocked(self) -> None:
        result = _run("Bash", {"command": "del /s /q Memory"})
        assert result.returncode == 2


# =============================================================================
# Safe Bash (must allow -- exit 0)
# =============================================================================


class TestSafeBash:
    """Legitimate bash commands must be allowed through."""

    def test_git_status_allowed(self) -> None:
        result = _run("Bash", {"command": "git status"})
        assert result.returncode == 0

    def test_git_log_allowed(self) -> None:
        result = _run("Bash", {"command": "git log --oneline -5"})
        assert result.returncode == 0

    def test_uv_run_allowed(self) -> None:
        result = _run("Bash", {"command": "uv run python heartbeat.py --dry-run"})
        assert result.returncode == 0

    def test_memory_search_allowed(self) -> None:
        result = _run("Bash", {"command": "python .claude/scripts/memory_search.py 'karaoke'"})
        assert result.returncode == 0


# =============================================================================
# Non-Bash Tools (must allow -- exit 0)
# =============================================================================


class TestNonBashTools:
    """command-guard only fires on Bash -- other tools must pass through."""

    def test_read_tool_allowed(self) -> None:
        result = _run("Read", {"file_path": "Memory/SOUL.md"})
        assert result.returncode == 0

    def test_write_tool_allowed(self) -> None:
        result = _run("Write", {
            "file_path": "Memory/daily/2026-06-13.md",
            "content": "## test entry",
        })
        assert result.returncode == 0


# =============================================================================
# Malformed Input (must allow -- fail open)
# =============================================================================


class TestMalformedInput:
    """Malformed hook input must not block legitimate tool calls (fail open)."""

    def test_malformed_json_exits_0(self) -> None:
        result = subprocess.run(
            [sys.executable, HOOK],
            input=b"not valid json",
            capture_output=True,
        )
        assert result.returncode == 0
