#!/usr/bin/env python3
"""PreCompact hook: flush conversation to daily log before auto-compaction."""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

data = json.load(sys.stdin)

# Recursion guard
if os.environ.get("AGENT_INVOKED_BY"):
    sys.exit(0)

transcript_path = data.get("transcript_path", "")
session_id = data.get("session_id", "unknown")

# Fallback: if Claude Code didn't provide transcript_path, construct it from session_id.
if (not transcript_path or not Path(transcript_path).exists()) and session_id != "unknown":
    project_root = Path(__file__).resolve().parent.parent.parent
    encoded = re.sub(r"[:\\/\s]", "-", str(project_root)).strip("-")
    candidate = Path.home() / ".claude" / "projects" / encoded / f"{session_id}.jsonl"
    if candidate.exists():
        transcript_path = str(candidate)

if not transcript_path or not Path(transcript_path).exists():
    sys.exit(0)

scripts_dir = Path(__file__).resolve().parent.parent / "scripts"
venv_python = scripts_dir / ".venv" / "Scripts" / "python.exe"
python_exe = str(venv_python) if venv_python.exists() else sys.executable

subprocess.Popen(
    [python_exe, str(scripts_dir / "memory_flush.py"), transcript_path, session_id],
    start_new_session=True,
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
)
sys.exit(0)
