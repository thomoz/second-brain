#!/usr/bin/env python3
"""PreToolUse hook: block automated agents from editing SOUL.md and security config files."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from shared import append_audit_log

# Files that automated agents must never write. Patterns matched against the
# normalised (forward-slash) file path. Order matters: first match wins.
_PROTECTED: list[tuple[str, str]] = [
    (
        "SOUL.md",
        "SOUL.md is write-protected from all automated processes. "
        "Log personality change suggestions to the daily log instead.",
    ),
    (
        ".claude/hooks/",
        "Hook scripts in .claude/hooks/ are write-protected from automated processes. "
        "Modifying security hooks could undermine the entire defense chain.",
    ),
    (
        ".claude/settings",
        ".claude/settings.json is write-protected from automated processes. "
        "Modifying hook configuration could disable security protections.",
    ),
]


def check_protected_path(file_path: str) -> tuple[str, str] | None:
    """Return (audit_reason, deny_message) if path is write-protected, else None."""
    normalized = file_path.replace("\\", "/")
    for pattern, message in _PROTECTED:
        if pattern in normalized:
            return (
                f"Blocked: automated agent attempted to edit protected file: {file_path}",
                message,
            )
    return None


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    if not os.environ.get("AGENT_INVOKED_BY"):
        sys.exit(0)

    tool_input = data.get("tool_input") or {}
    file_path = tool_input.get("file_path", "")
    tool_name = data.get("tool_name", "Write")

    result = check_protected_path(file_path)
    if result:
        reason, message = result
        append_audit_log("soul-protect", tool_name, reason, file_path)
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": message,
            }
        }))


if __name__ == "__main__":
    main()
