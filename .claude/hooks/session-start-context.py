#!/usr/bin/env python3
"""SessionStart hook: inject memory context into every conversation."""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Add scripts dir to path for session_context and config imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

data = json.load(sys.stdin)

# First-run: inject BOOTSTRAP.md if it still exists
bootstrap = Path("Memory/BOOTSTRAP.md")
if bootstrap.exists():
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": (
                "[FIRST-RUN ONBOARDING IN PROGRESS]\n\n"
                + bootstrap.read_text(encoding="utf-8")
            ),
        }
    }))
    sys.exit(0)

# Normal session: inject SOUL + USER + MEMORY + HEARTBEAT + recent daily logs
from session_context import build_context

context = build_context("startup")
print(json.dumps({
    "hookSpecificOutput": {
        "hookEventName": "SessionStart",
        "additionalContext": context,
    }
}))
sys.exit(0)
