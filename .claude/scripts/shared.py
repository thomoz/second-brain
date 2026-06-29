"""Shared utilities: file locking, atomic writes, retry, daily log, bash patterns."""

from __future__ import annotations

import contextlib
import json
import os
import time
from pathlib import Path


@contextlib.contextmanager
def file_lock(path: Path, timeout: float = 30.0):
    """Cross-platform exclusive file lock (Windows: msvcrt; POSIX: fcntl)."""
    lock_path = str(path) + ".lock"
    if os.name == "nt":
        import msvcrt

        deadline = time.monotonic() + timeout
        with open(lock_path, "w") as f:
            while True:
                try:
                    msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except OSError:
                    if time.monotonic() > deadline:
                        raise TimeoutError(f"Could not acquire lock on {path} within {timeout}s")
                    time.sleep(0.05)
            try:
                yield
            finally:
                try:
                    msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
                except OSError:
                    pass
        try:
            Path(lock_path).unlink(missing_ok=True)
        except OSError:
            pass
    else:
        import fcntl

        with open(lock_path, "w") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)
        try:
            Path(lock_path).unlink(missing_ok=True)
        except OSError:
            pass


def with_retry(fn, max_retries: int = 3, base_delay: float = 1.0):
    """Retry with exponential backoff. Wrap external API calls with this."""
    for attempt in range(max_retries):
        try:
            return fn()
        except Exception:
            if attempt == max_retries - 1:
                raise
            time.sleep(base_delay * (2**attempt))


def atomic_write(path: Path, content: str) -> None:
    """Write to .tmp then os.replace -- prevents partial writes on crash."""
    tmp = str(path) + ".tmp"
    Path(tmp).write_text(content, encoding="utf-8")
    os.replace(tmp, str(path))


def append_audit_log(hook_name: str, tool_name: str, reason: str, payload: str = "", _path: Path | None = None) -> None:
    """Append a security block event to the persistent audit log.

    Path is derived from __file__ so it works regardless of hook invocation CWD.
    _path is for testing only — pass a tmp_path to redirect writes.
    Uses plain open() (no lock) — append is atomic enough for a log file.
    """
    from datetime import datetime

    if _path is None:
        project_root = Path(__file__).resolve().parent.parent.parent
        _path = project_root / ".claude" / "data" / "security_audit.log"
    _path.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    snippet = payload[:120].replace("\n", " ") if payload else ""
    line = f"{ts} | hook={hook_name} | tool={tool_name} | {reason} | {snippet}\n"
    try:
        with open(_path, "a", encoding="utf-8") as f:
            f.write(line)
    except OSError:
        pass  # Never let audit log failure block a hook


def append_to_daily_log(text: str) -> None:
    """Append timestamped entry to today's daily log with file locking."""
    from config import get_today_log_path, now_local

    log_path = get_today_log_path()  # creates year/month dirs
    timestamp = now_local().strftime("%H:%M")
    # Escape trust-boundary tags so injected </external_data> can't break reflection's wrapper
    safe_text = text.strip().replace("<external_data", "&lt;external_data").replace("</external_data>", "&lt;/external_data&gt;")
    entry = f"\n## {timestamp}\n{safe_text}\n"
    with file_lock(log_path):
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(entry)


def load_state(path: Path) -> dict:
    """Load JSON state from path, returning {} if missing or invalid."""
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except (json.JSONDecodeError, OSError):
        return {}


def save_state(path: Path, state: dict) -> None:
    """Atomically write JSON state to path, creating parent dirs as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(path, json.dumps(state, indent=2, default=str))


def log_hook_execution(hook_name: str, result: str) -> None:
    """Append a hook execution summary to today's daily log."""
    append_to_daily_log(f"**[Hook: {hook_name}]** {result}")


# Dangerous bash patterns used by command-guard.py (Phase 8) and pi_safety.ts.
# Keep this list in sync with the TypeScript version in pi_ext/pi_safety.ts.
DANGEROUS_BASH_PATTERNS: list[str] = [
    r"rm\s+(-[a-z]*f[a-z]*\s+|--force\s+)",
    r"\bdd\b.*of=",
    r"\bmkfs\b",
    r">\s*/dev/(sd|hd|nvme)",
    r"truncate.*--size\s+0",
    r"\bshred\b",
    r"Remove-Item.*-Recurse.*-Force",
    r"Format-Volume",
    r"(cat|type|Get-Content)\s+.*\.env",
    r"\bprintenv\b",
    r"\$env:[A-Z_]*(TOKEN|KEY|SECRET|PASSWORD|APIKEY)",
    r"echo\s+\$[A-Z_]*(TOKEN|KEY|SECRET)",
    r"python.*os\.environ",
    r"import\s+os.*\bgetenv\b",
    r"curl\s+.*\$\w*(TOKEN|KEY|SECRET)",
    r"wget\s+.*\|\s*(ba)?sh",
    r"pip\s+install\b",
    r"pip3\s+install\b",
    r"npm\s+install\b",
    r"brew\s+install\b",
    r"apt(-get)?\s+install\b",
    r"choco\s+install\b",
    r"winget\s+install\b",
    r"\bsudo\b",
    r"chmod\s+[0-7]*7[0-7][0-7]",
    r"icacls.*grant.*Everyone",
    r"Set-ExecutionPolicy\s+Unrestricted",
    r"\beval\b",
    r"\bexec\b\s+[^(]",
    r"os\.system\s*\(",
    r"subprocess.*shell\s*=\s*True",
    r"\b(stripe|paypal|square)\b.*\b(charge|payment|transfer)\b",
    r"del\s+/[sqa]",
    r"Remove-Item.*\*",
    # Social media / outbound POST guard (never auto-post)
    r"curl\s+.*-X\s+POST.*(?:twitter|instagram|linkedin|facebook|tiktok|reddit|api\.openai)",
    r"curl\s+.*(?:twitter|instagram|linkedin|facebook|tiktok).*-X\s+POST",
    r"wget\s+.*--post-data.*(?:twitter|instagram|linkedin|facebook)",
    # Git push guard (never push without explicit approval)
    r"git\s+push\s+.*--force",
    r"git\s+push\s+.*-f\b",
    # Writes outside Memory/ vault (catches absolute path writes to system dirs)
    r">\s*/(?!tmp|var/tmp)[a-z]",
]
