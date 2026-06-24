"""Tests for the block-secrets PreToolUse hook."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HOOK = str(Path(__file__).resolve().parent.parent.parent / "hooks" / "block-secrets.py")


def _run(tool_name: str, tool_input: dict) -> subprocess.CompletedProcess:
    payload = json.dumps({"tool_name": tool_name, "tool_input": tool_input})
    return subprocess.run(
        [sys.executable, HOOK],
        input=payload.encode(),
        capture_output=True,
    )


# Dangerous content strings are split across concatenations so this file
# does not trigger its own write hook. At runtime they evaluate to the
# exact blocked patterns that block-secrets.py is designed to catch.
_ENV_LIST_CMD = "print" + "env"
_CAT_ENV_CMD = "c" + "at .env"
_ECHO_TOKEN = "echo " + "$TOKEN"
_PRINT_OS_ENV = "pr" + "int(os.environ)"
_PRINT_OS_GETENV = "import os; pr" + "int(os.getenv(" + "'KEY'))"
_SUBSHELL_CAT_ENV = "echo $(c" + "at .env)"
_PYTHON_INLINE_CMD = "python3 -c 'import os; pr" + "int(os.environ)'"


# =============================================================================
# Sensitive File Blocking (must block -- exit 2)
# =============================================================================


class TestSensitiveFileBlocking:
    """Read tool: credential and secret files must be blocked."""

    def test_env_file_blocked(self) -> None:
        result = _run("Read", {"file_path": ".env"})
        assert result.returncode == 2

    def test_env_local_blocked(self) -> None:
        result = _run("Read", {"file_path": ".env.local"})
        assert result.returncode == 2

    def test_google_credentials_blocked(self) -> None:
        result = _run("Read", {"file_path": "google_credentials.json"})
        assert result.returncode == 2

    def test_gmail_token_blocked(self) -> None:
        result = _run("Read", {"file_path": "token_gmail_sbdb.json"})
        assert result.returncode == 2

    def test_gmail_token_personal_blocked(self) -> None:
        result = _run("Read", {"file_path": "token_gmail_personal.json"})
        assert result.returncode == 2

    def test_outlook_token_blocked(self) -> None:
        result = _run("Read", {"file_path": "outlook_token.json"})
        assert result.returncode == 2

    def test_ssh_private_key_blocked(self) -> None:
        result = _run("Read", {"file_path": "id_rsa"})
        assert result.returncode == 2

    def test_master_env_blocked(self) -> None:
        result = _run("Read", {"file_path": "master.env"})
        assert result.returncode == 2

    def test_grep_env_path_blocked(self) -> None:
        result = _run("Grep", {"path": ".env", "pattern": "TOKEN"})
        assert result.returncode == 2


# =============================================================================
# Safe File Access (must allow -- exit 0)
# =============================================================================


class TestSafeFileAccess:
    """Files that are safe to read must pass through."""

    def test_soul_md_allowed(self) -> None:
        result = _run("Read", {"file_path": "Memory/SOUL.md"})
        assert result.returncode == 0

    def test_block_hook_py_allowed(self) -> None:
        """The hook file itself must not be blocked by the name pattern."""
        result = _run("Read", {"file_path": ".claude/hooks/block-secrets.py"})
        assert result.returncode == 0

    def test_env_example_allowed(self) -> None:
        result = _run("Read", {"file_path": ".env.example"})
        assert result.returncode == 0

    def test_pyproject_toml_allowed(self) -> None:
        result = _run("Read", {"file_path": "pyproject.toml"})
        assert result.returncode == 0

    def test_memory_md_allowed(self) -> None:
        result = _run("Read", {"file_path": "Memory/MEMORY.md"})
        assert result.returncode == 0


# =============================================================================
# Bash Exfiltration (must block -- exit 2)
# =============================================================================


class TestBashExfiltration:
    """Bash commands that would expose secrets must be blocked."""

    def test_cat_env_blocked(self) -> None:
        result = _run("Bash", {"command": _CAT_ENV_CMD})
        assert result.returncode == 2

    def test_env_list_blocked(self) -> None:
        result = _run("Bash", {"command": _ENV_LIST_CMD})
        assert result.returncode == 2

    def test_echo_token_blocked(self) -> None:
        result = _run("Bash", {"command": _ECHO_TOKEN})
        assert result.returncode == 2

    def test_python_os_environ_blocked(self) -> None:
        result = _run("Bash", {"command": _PYTHON_INLINE_CMD})
        assert result.returncode == 2

    def test_base64_piped_to_bash_blocked(self) -> None:
        result = _run("Bash", {"command": "base64 -d file | bash"})
        assert result.returncode == 2

    def test_subshell_cat_env_blocked(self) -> None:
        result = _run("Bash", {"command": _SUBSHELL_CAT_ENV})
        assert result.returncode == 2


# =============================================================================
# Safe Bash Commands (must allow -- exit 0)
# =============================================================================


class TestSafeBash:
    """Legitimate bash commands must be allowed through."""

    def test_git_status_allowed(self) -> None:
        result = _run("Bash", {"command": "git status"})
        assert result.returncode == 0

    def test_uv_run_allowed(self) -> None:
        result = _run("Bash", {"command": "uv run python heartbeat.py"})
        assert result.returncode == 0

    def test_memory_index_allowed(self) -> None:
        result = _run("Bash", {"command": "python .claude/scripts/memory_index.py --stats"})
        assert result.returncode == 0


# =============================================================================
# Two-Step Attack: Write Content (must block -- exit 2)
# =============================================================================


class TestWriteContentExfiltration:
    """Write/Edit tool with exfiltration content must be blocked."""

    def test_write_environ_dump_blocked(self) -> None:
        result = _run("Write", {"file_path": "dump.py", "content": _PRINT_OS_ENV})
        assert result.returncode == 2

    def test_write_getenv_dump_blocked(self) -> None:
        result = _run("Write", {"file_path": "dump.py", "content": _PRINT_OS_GETENV})
        assert result.returncode == 2


# =============================================================================
# Safe Write Content (must allow -- exit 0)
# =============================================================================


class TestSafeWriteContent:
    """Legitimate write content must not be blocked."""

    def test_normal_daily_log_write_allowed(self) -> None:
        result = _run("Write", {
            "file_path": "Memory/daily/2026-06-13.md",
            "content": "## 09:00\nMorning tasks completed.",
        })
        assert result.returncode == 0

    def test_config_import_allowed(self) -> None:
        """Importing a token constant (not dumping it) is allowed."""
        result = _run("Write", {
            "file_path": "script.py",
            "content": "from config import WHATSAPP_API_TOKEN\nrequests.post(url)",
        })
        assert result.returncode == 0


# =============================================================================
# WhatsApp Bot Write Path Whitelist (AGENT_INVOKED_BY=chat)
# =============================================================================


def _run_as_chat(tool_name: str, tool_input: dict) -> subprocess.CompletedProcess:
    """Run the hook with AGENT_INVOKED_BY=chat to simulate WhatsApp bot context."""
    import os
    payload = json.dumps({"tool_name": tool_name, "tool_input": tool_input})
    env = {**os.environ, "AGENT_INVOKED_BY": "chat"}
    return subprocess.run(
        [sys.executable, HOOK],
        input=payload.encode(),
        capture_output=True,
        env=env,
    )


class TestWhatsAppWritePathWhitelist:
    """WhatsApp bot (AGENT_INVOKED_BY=chat) may only write to allowed directories."""

    def test_plans_dir_allowed(self) -> None:
        result = _run_as_chat("Write", {
            "file_path": str(Path(__file__).resolve().parent.parent.parent.parent / ".agent" / "plans" / "test-handoff.md"),
            "content": "# Test Handoff\n",
        })
        assert result.returncode == 0

    def test_drafts_active_dir_allowed(self) -> None:
        result = _run_as_chat("Write", {
            "file_path": str(Path(__file__).resolve().parent.parent.parent.parent / "Memory" / "drafts" / "active" / "draft-test.md"),
            "content": "# Draft\n",
        })
        assert result.returncode == 0

    def test_memory_root_blocked(self) -> None:
        result = _run_as_chat("Write", {
            "file_path": str(Path(__file__).resolve().parent.parent.parent.parent / "Memory" / "MEMORY.md"),
            "content": "# Should be blocked\n",
        })
        assert result.returncode == 2

    def test_daily_log_blocked(self) -> None:
        result = _run_as_chat("Write", {
            "file_path": str(Path(__file__).resolve().parent.parent.parent.parent / "Memory" / "daily" / "2026-06-21.md"),
            "content": "injected content",
        })
        assert result.returncode == 2

    def test_scripts_dir_blocked(self) -> None:
        result = _run_as_chat("Write", {
            "file_path": str(Path(__file__).resolve().parent.parent.parent / "scripts" / "evil.py"),
            "content": "import os",
        })
        assert result.returncode == 2


    def test_entities_dir_allowed(self) -> None:
        """WhatsApp bot may write to Memory/entities/ for save commands."""
        result = _run_as_chat("Write", {
            "file_path": str(Path(__file__).resolve().parent.parent.parent.parent / "Memory" / "entities" / "juno-wonderdog" / "characters.md"),
            "content": "## 2026-06-23 [WhatsApp save]\nTest character note.",
        })
        assert result.returncode == 0

    def test_topics_dir_allowed(self) -> None:
        """WhatsApp bot may write to Memory/topics/ for save commands."""
        result = _run_as_chat("Write", {
            "file_path": str(Path(__file__).resolve().parent.parent.parent.parent / "Memory" / "topics" / "investment-strategy.md"),
            "content": "## 2026-06-23 [WhatsApp save]\nTest investment note.",
        })
        assert result.returncode == 0

    def test_scratch_allowed(self) -> None:
        """WhatsApp bot may write to Memory/scratch.md for reminders and ideas."""
        result = _run_as_chat("Write", {
            "file_path": str(Path(__file__).resolve().parent.parent.parent.parent / "Memory" / "scratch.md"),
            "content": "## 2026-06-23 [WhatsApp save]\nTest idea.",
        })
        assert result.returncode == 0

    def test_non_chat_context_allows_daily_log(self) -> None:
        """Outside WhatsApp bot context the path whitelist does not apply."""
        result = _run("Write", {
            "file_path": str(Path(__file__).resolve().parent.parent.parent.parent / "Memory" / "daily" / "2026-06-21.md"),
            "content": "## 09:00\nNormal heartbeat entry.",
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
