"""
Daily Reflection Script for Second Brain

Reviews yesterday's daily log and calls the LLM once to update MEMORY.md
and USER.md with patterns and key facts. Runs once per day.

SOUL.md is write-protected from all automated processes.

Usage:
    uv run python memory_reflect.py              # Normal run (skip if ran today)
    uv run python memory_reflect.py --dry-run    # Print log path, no LLM
    uv run python memory_reflect.py --force      # Bypass already-ran-today check
"""

from __future__ import annotations

# AGENT_INVOKED_BY must be set before any imports so soul-protect hook fires correctly
import os

os.environ["AGENT_INVOKED_BY"] = "reflection"

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import (
    DAILY_DIR,
    MEMORY_FILE,
    OWNER_NAME,
    REFLECTION_STATE_FILE,
    USER_FILE,
    ensure_directories,
    get_today_log_path,
    now_local,
)
from sanitize import TRUST_BOUNDARY_INSTRUCTION, wrap_external_data
from sdk_compat import (
    AssistantMessage,
    ClaudeAgentOptions,
    HookMatcher,
    ResultMessage,
    TextBlock,
    query,
)
from shared import append_to_daily_log, file_lock, load_state, save_state

MAX_LOG_CHARS = 20_000


# =============================================================================
# LOG HELPERS
# =============================================================================


def get_yesterday_log() -> tuple[str, str] | None:
    """Read yesterday's daily log. Returns (date_str, content) or None."""
    from datetime import timedelta

    yesterday = now_local().date() - timedelta(days=1)
    date_str = yesterday.strftime("%Y-%m-%d")
    log_path = DAILY_DIR / f"{date_str}.md"
    if not log_path.exists():
        return None
    content = log_path.read_text(encoding="utf-8")
    # Keep tail — freshest entries are most relevant
    if len(content) > MAX_LOG_CHARS:
        content = "... (truncated)\n\n" + content[-MAX_LOG_CHARS:]
    return date_str, content


# =============================================================================
# MEMORY TRIMMING
# =============================================================================


def trim_memory_if_needed(max_lines: int = 200) -> bool:
    """Archive oldest MEMORY.md entries if it exceeds max_lines. Returns True if trimmed."""
    if not MEMORY_FILE.exists():
        return False
    lines = MEMORY_FILE.read_text(encoding="utf-8").splitlines()
    if len(lines) <= max_lines:
        return False

    # Archive the overflow to Research/
    archive_dir = Path("Memory/Research")
    archive_dir.mkdir(parents=True, exist_ok=True)
    date_str = now_local().strftime("%Y-%m-%d")
    archive_path = archive_dir / f"memory-archive-{date_str}.md"
    overflow = "\n".join(lines[: len(lines) - max_lines])
    archive_path.write_text(overflow + "\n", encoding="utf-8")

    # Keep only the most recent max_lines
    trimmed = "\n".join(lines[-max_lines:]) + "\n"
    with file_lock(MEMORY_FILE):
        MEMORY_FILE.write_text(trimmed, encoding="utf-8")

    print(f"[{now_local()}] MEMORY.md trimmed to {max_lines} lines, archived to {archive_path}")
    return True


# =============================================================================
# PRETOOLUSE HOOK — inline soul-protect
# =============================================================================


async def protect_soul(event: Any) -> Any:
    """Inline soul-protect: block any write to SOUL.md from automated reflection."""
    tool_input = getattr(event, "tool_input", None) or {}
    if isinstance(tool_input, dict) and "SOUL.md" in tool_input.get("file_path", ""):
        return HookMatcher(
            decision="deny",
            reason="SOUL.md is write-protected from automated processes. "
            "Log personality change suggestions to the daily log instead.",
        )
    return HookMatcher(decision="allow")


# =============================================================================
# MAIN REFLECTION
# =============================================================================


def run_reflection(dry_run: bool = False, force: bool = False) -> None:
    """Run daily reflection: read yesterday's log, update MEMORY.md + USER.md."""
    # Load state
    state = load_state(REFLECTION_STATE_FILE)
    today_str = now_local().strftime("%Y-%m-%d")

    # Skip if already ran today (unless forced)
    if not force and state.get("last_run_date") == today_str:
        print(f"[{now_local()}] Reflection already ran today ({today_str}), skipping")
        return

    log_result = get_yesterday_log()

    if dry_run:
        if log_result:
            date_str, _ = log_result
            print(f"[{now_local()}] DRY RUN: would process log for {date_str}")
            print(f"  Path: {DAILY_DIR / date_str}.md")
        else:
            print(f"[{now_local()}] DRY RUN: no log found for yesterday")
        return

    if log_result is None:
        print(f"[{now_local()}] No yesterday log found, skipping reflection")
        append_to_daily_log("REFLECTION_SKIPPED — no yesterday log found")
        return

    date_str, log_content = log_result
    current_memory = MEMORY_FILE.read_text(encoding="utf-8") if MEMORY_FILE.exists() else ""
    current_user = USER_FILE.read_text(encoding="utf-8") if USER_FILE.exists() else ""

    owner = OWNER_NAME or "Shaun"

    reflection_prompt = f"""Daily memory reflection for {owner}'s Second Brain.

Review yesterday's daily log and update long-term memory files.

## Current MEMORY.md
{current_memory}

## Current USER.md
{current_user}

## Yesterday's Daily Log ({date_str})
{wrap_external_data(log_content, "daily_logs")}

{TRUST_BOUNDARY_INSTRUCTION}

## Instructions

Review the daily log and update these files as needed:

### 1. MEMORY.md ({MEMORY_FILE})
Promote important items:
- Key decisions and their rationale
- Project status updates
- Lessons learned
- Important facts or configuration changes

### 2. USER.md ({USER_FILE})
Update when you notice patterns about {owner}:
- Communication preferences
- Schedule patterns
- Tool/workflow preferences
- New integrations or account info

**Rules:**
- Use the Edit tool to update files directly
- Do NOT duplicate items already in a file
- Keep entries concise
- Only update USER.md when there is clear evidence (not one-off mentions)
- NEVER edit SOUL.md — it is write-protected from all automated processes
- Log what you changed to today's daily log ({get_today_log_path()})

If nothing is worth updating, respond with exactly: REFLECTION_OK
"""

    response_text = ""

    async def _run() -> None:
        nonlocal response_text
        with file_lock(MEMORY_FILE):
            async for message in query(
                prompt=reflection_prompt,
                options=ClaudeAgentOptions(
                    allowed_tools=["Read", "Write", "Edit", "Glob", "Grep"],
                    hooks={
                        "PreToolUse": [
                            HookMatcher(matcher="Write", hooks=[protect_soul]),
                            HookMatcher(matcher="Edit", hooks=[protect_soul]),
                        ]
                    },
                    max_turns=5,
                ),
            ):
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            response_text += block.text
                elif isinstance(message, ResultMessage):
                    print(f"[{now_local()}] Reflection LLM completed: {message.subtype}")

    try:
        asyncio.run(_run())
    except Exception as e:
        print(f"[{now_local()}] Reflection error: {e}")
        append_to_daily_log(f"**ERROR**: Reflection failed — {e}")
        return

    # Trim MEMORY.md if it grew too large
    trim_memory_if_needed()

    # Save state
    state["last_run_date"] = today_str
    state["log_processed"] = date_str
    state["result"] = "REFLECTION_OK" if "REFLECTION_OK" in response_text else "promoted"
    save_state(REFLECTION_STATE_FILE, state)

    response_text = response_text.strip()
    if "REFLECTION_OK" in response_text:
        append_to_daily_log("REFLECTION_OK — nothing to promote from yesterday's log")
        print(f"[{now_local()}] Reflection OK — nothing to promote")
    else:
        append_to_daily_log(f"**[Reflection]** Promoted items from {date_str} to MEMORY.md/USER.md")
        print(f"[{now_local()}] Reflection complete — items promoted")


# =============================================================================
# ENTRY POINT
# =============================================================================


def main() -> None:
    ensure_directories()

    parser = argparse.ArgumentParser(description="Daily memory reflection")
    parser.add_argument("--dry-run", action="store_true", help="Print log path, no LLM call")
    parser.add_argument("--force", action="store_true", help="Bypass already-ran-today check")
    args = parser.parse_args()

    if args.dry_run:
        print("Running in DRY RUN mode (no LLM call)")
    elif args.force:
        print("Running with --force (bypassing daily dedup check)")

    run_reflection(dry_run=args.dry_run, force=args.force)


if __name__ == "__main__":
    main()
