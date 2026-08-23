"""Local-side counterpart to ibkr_remote_apply.py. IBKR positions can only be fetched
locally (IB Gateway only runs on Shaun's machine, see ibkr_sync.py's module
docstring), but the diff against tracked holdings -- and any resulting write -- must
happen against the VPS's investments.db, the single source of truth since
.agent/plans/investments-db-ssh-single-source.md. This module sends the already-
fetched positions (plain JSON-safe dicts) to the VPS over SSH and streams back its
diff report / write summary exactly as if it had run locally.
"""

from __future__ import annotations

import json
import subprocess
import sys
from typing import Any

VPS = "secondbrain@137.184.102.104"
REMOTE_DIR = "/home/secondbrain/second-brain"


def push_positions_remote(
    positions: list[dict[str, Any]], summary: dict[str, Any] | None, apply: bool
) -> None:
    payload = json.dumps({"positions": positions, "summary": summary, "apply": apply}).encode("utf-8")
    remote_command = (
        f"cd {REMOTE_DIR}/investments/my-trader && "
        f"{REMOTE_DIR}/investments/.venv/bin/python -m mytrader.ibkr_remote_apply"
    )

    result = subprocess.run(
        ["ssh", "-o", "ConnectTimeout=10", VPS, remote_command],
        input=payload,
        capture_output=True,
    )

    if result.stdout:
        sys.stdout.write(result.stdout.decode("utf-8", errors="replace"))
    if result.returncode != 0:
        if result.stderr:
            sys.stderr.write(result.stderr.decode("utf-8", errors="replace"))
        print(f"ERROR: remote IBKR apply failed (exit {result.returncode})", file=sys.stderr)
        sys.exit(result.returncode)
