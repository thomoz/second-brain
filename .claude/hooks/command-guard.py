#!/usr/bin/env python3
"""PreToolUse hook: block dangerous bash commands (destructive ops, package installs)."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# __file__-relative path — robust regardless of hook invocation CWD
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from shared import DANGEROUS_BASH_PATTERNS

_COMPILED = [re.compile(p, re.IGNORECASE) for p in DANGEROUS_BASH_PATTERNS]

# Strip binary path prefixes that could bypass pattern matching
_PATH_PREFIXES = [
    "/usr/bin/", "/bin/", "/usr/local/bin/",
    "C:\\Windows\\System32\\", "C:\\Windows\\SysWOW64\\",
]


def _strip_prefixes(cmd: str) -> str:
    for prefix in _PATH_PREFIXES:
        cmd = cmd.replace(prefix, "")
    return cmd


def _all_segments(command: str):
    """Yield top-level command and any subshell contents."""
    yield command
    for sub in re.findall(r'\$\((.*?)\)', command, re.DOTALL):
        yield sub
    for sub in re.findall(r'`(.*?)`', command, re.DOTALL):
        yield sub


def check_command(command: str) -> str | None:
    normalized = _strip_prefixes(" ".join(command.split()))
    for segment in _all_segments(normalized):
        for pattern in _COMPILED:
            if pattern.search(segment):
                return f"Blocked: matches dangerous pattern '{pattern.pattern}'"
    return None


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)  # Malformed input — allow (fail open on parse errors)

    if data.get("tool_name") != "Bash":
        sys.exit(0)

    command = data.get("tool_input", {}).get("command", "")
    reason = check_command(command)

    if reason:
        print(
            f"SECURITY: {reason}. This command matches a dangerous pattern and cannot "
            "be executed autonomously. Ask Shaun to run it manually if needed.",
            file=sys.stderr,
        )
        sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()
