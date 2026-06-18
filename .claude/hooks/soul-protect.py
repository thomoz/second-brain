#!/usr/bin/env python3
"""PreToolUse hook: block all automated agents from editing SOUL.md."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from shared import append_audit_log

data = json.load(sys.stdin)

if os.environ.get("AGENT_INVOKED_BY"):
    tool_input = data.get("tool_input") or {}
    file_path = tool_input.get("file_path", "")
    if "SOUL.md" in file_path:
        tool_name = data.get("tool_name", "Write")
        append_audit_log("soul-protect", tool_name, "Blocked: automated agent attempted to edit SOUL.md", file_path)
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": (
                    "SOUL.md is write-protected from all automated processes. "
                    "Log personality change suggestions to the daily log instead."
                ),
            }
        }))
        sys.exit(0)

sys.exit(0)
