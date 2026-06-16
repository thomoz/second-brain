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

flush_log = scripts_dir.parent / "data" / "flush_errors.log"
try:
    flush_log.parent.mkdir(parents=True, exist_ok=True)
    stderr_target = open(flush_log, "a")
except OSError:
    stderr_target = subprocess.DEVNULL

popen_kwargs: dict = {
    "stdout": subprocess.DEVNULL,
    "stderr": stderr_target,
}
if os.name == "nt":
    popen_kwargs["creationflags"] = 0x00000008 | 0x08000000
else:
    popen_kwargs["start_new_session"] = True

subprocess.Popen(
    [python_exe, str(scripts_dir / "memory_flush.py"), transcript_path, session_id],
    **popen_kwargs,
)
sys.exit(0)
