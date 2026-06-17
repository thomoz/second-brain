"""
Shared SessionStart context builder.

Reads the key memory files (SOUL.md, USER.md, MEMORY.md, HEARTBEAT.md,
recent daily logs) and returns them as one context string.

This is the SINGLE source of truth used by:
  * .claude/hooks/session-start-context.py  (Claude Code SessionStart hook)
  * .claude/chat/engine.py                  (Pi/Codex chat - the hook does not
                                             fire on non-Claude backends, so the
                                             engine injects this directly)

Pure local file reads, no API calls.
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from config import DAILY_DIR, MEMORY_DIR, now_local

MAX_DAILY_LOG_LINES = 30
# ~15,000 tokens. SOUL.md + USER.md + MEMORY.md + HEARTBEAT.md + recent logs
# ~= 55K; 60K cap leaves headroom.
MAX_CONTEXT_CHARS = 60_000
RESUME_MAX_CHARS = 60_000


def read_file_safe(path: Path) -> str:
    """Read a file, returning empty string if it doesn't exist."""
    try:
        if path.exists():
            return path.read_text(encoding="utf-8")
    except OSError:
        pass
    return ""


def get_recent_daily_log(max_lines: int = MAX_DAILY_LOG_LINES) -> list[tuple[str, str]]:
    """Read the last 3 days of daily logs. Returns list of (date, content) pairs."""
    results = []
    for i in range(3):
        d = (now_local() - timedelta(days=i)).strftime("%Y-%m-%d")
        content = read_file_safe(DAILY_DIR / f"{d}.md")
        if content:
            lines = content.strip().splitlines()
            if len(lines) > max_lines:
                lines = lines[-max_lines:]
            results.append((d, "\n".join(lines)))
    return results


def build_context(source: str = "startup") -> str:
    """Build the SessionStart context string from the memory files.

    Args:
        source: session start source (startup, resume, clear, compact).
    """
    parts: list[str] = []

    today = now_local()
    parts.append(f"## Today\n{today.strftime('%A, %B')} {today.day}, {today.strftime('%Y')}")

    bootstrap = read_file_safe(MEMORY_DIR / "BOOTSTRAP.md")
    if bootstrap:
        parts.append("## BOOTSTRAP (First-Run Onboarding)\n" + bootstrap.strip())

    soul = read_file_safe(MEMORY_DIR / "SOUL.md")
    if soul:
        parts.append("## Soul\n" + soul.strip())

    user = read_file_safe(MEMORY_DIR / "USER.md")
    if user:
        parts.append("## User\n" + user.strip())

    memory = read_file_safe(MEMORY_DIR / "MEMORY.md")
    if memory:
        parts.append("## Long-Term Memory\n" + memory.strip())

    heartbeat = read_file_safe(MEMORY_DIR / "HEARTBEAT.md")
    if heartbeat:
        parts.append("## Heartbeat Monitoring\n" + heartbeat.strip())

    # Core memories — permanent file, always inject if non-empty
    core_mem_path = MEMORY_DIR / "core-memories.md"
    if core_mem_path.exists():
        core_mem = read_file_safe(core_mem_path)
        if core_mem and "_(Empty" not in core_mem:
            parts.append("## Core Memories\n" + core_mem.strip())

    # Profile — inject non-placeholder files for key categories
    profile_dir = MEMORY_DIR / "Profile"
    if profile_dir.exists():
        profile_parts = []
        for fname in ["values.md", "goals.md", "personality.md", "health.md"]:
            fpath = profile_dir / fname
            if fpath.exists():
                content = read_file_safe(fpath)
                if content and "_(not yet" not in content:
                    profile_parts.append(f"### {fname.replace('.md','').title()}\n{content.strip()}")
        if profile_parts:
            parts.append("## Profile\n" + "\n\n".join(profile_parts))

    daily_logs = get_recent_daily_log()
    for date, content in daily_logs:
        parts.append(f"## Daily log {date}\n" + content.strip())

    context = "\n\n---\n\n".join(parts)

    max_chars = RESUME_MAX_CHARS if source in ("resume", "compact") else MAX_CONTEXT_CHARS
    if len(context) > max_chars:
        context = context[:max_chars]
        last_newline = context.rfind("\n")
        if last_newline > 0:
            context = context[:last_newline]

    return context
