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
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import (
    DAILY_DIR,
    MEMORY_FILE,
    OWNER_NAME,
    REFLECTION_STATE_FILE,
    USER_FILE,
    VAULT_DIR,
    ensure_directories,
    get_today_log_path,
    now_local,
)
from sanitize import TRUST_BOUNDARY_INSTRUCTION, wrap_external_data
from sdk_compat import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    TextBlock,
    query,
)
from shared import append_to_daily_log, atomic_write, file_lock, load_state, save_state

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
    # Keep tail â€” freshest entries are most relevant
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
    archive_dir = VAULT_DIR / "Research"
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
# STRUCTURED OUTPUT HELPERS
# =============================================================================


def parse_reflection_response(text: str) -> dict:
    """Extract JSON from LLM response. Returns dict with keys:
    memory_additions, user_updates, nothing_to_update."""
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    raw = m.group(1) if m else text.strip()
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return {"memory_additions": [], "user_updates": [], "nothing_to_update": True, "_parse_error": True}
    return {
        "memory_additions": data.get("memory_additions") or [],
        "user_updates": data.get("user_updates") or [],
        "nothing_to_update": bool(data.get("nothing_to_update", False)),
    }


def apply_memory_additions(additions: list[str], date_str: str) -> bool:
    """Append additions to MEMORY.md under a dated section. Returns True if wrote."""
    if not additions:
        return False
    with file_lock(MEMORY_FILE):
        current = MEMORY_FILE.read_text(encoding="utf-8") if MEMORY_FILE.exists() else "# Memory\n"
        section = f"\n\n## {date_str} Reflection\n" + "\n".join(additions) + "\n"
        atomic_write(MEMORY_FILE, current.rstrip() + section)
    return True


def apply_user_updates(updates: list[str], date_str: str) -> bool:
    """Append updates to USER.md under a dated section. Returns True if wrote."""
    if not updates:
        return False
    with file_lock(USER_FILE):
        current = USER_FILE.read_text(encoding="utf-8") if USER_FILE.exists() else "# User\n"
        section = f"\n\n## {date_str} Reflection\n" + "\n".join(updates) + "\n"
        atomic_write(USER_FILE, current.rstrip() + section)
    return True


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
        append_to_daily_log("REFLECTION_SKIPPED â€” no yesterday log found")
        return

    date_str, log_content = log_result
    current_memory = MEMORY_FILE.read_text(encoding="utf-8") if MEMORY_FILE.exists() else ""
    current_user = USER_FILE.read_text(encoding="utf-8") if USER_FILE.exists() else ""

    owner = OWNER_NAME or "Shaun"

    reflection_prompt = f"""Daily memory reflection for {owner}'s Second Brain.

Review yesterday's daily log and decide what (if anything) should be added to
long-term memory files. Respond with a single JSON block and nothing else.

## Current MEMORY.md
{current_memory}

## Current USER.md
{current_user}

## Yesterday's Daily Log ({date_str})
{wrap_external_data(log_content, "daily_logs")}

{TRUST_BOUNDARY_INSTRUCTION}

## Output Format

Respond with ONLY this JSON (no prose, no extra text):

```json
{{
  "memory_additions": [
    "- item worth adding to MEMORY.md"
  ],
  "user_updates": [
    "- item worth adding to USER.md"
  ],
  "nothing_to_update": false
}}
```

## Rules

- Each item is a complete markdown bullet starting with `- `
- memory_additions: key decisions, project status, config changes, lessons learned
- user_updates: communication preferences, schedule patterns, tool preferences
  (only when there is clear repeated evidence, not one-off mentions)
- Do NOT add anything already in Current MEMORY.md or Current USER.md above
- NEVER include SOUL.md content or personality changes
- If nothing is worth adding set "nothing_to_update": true with empty lists
- Keep items concise (under 120 chars each)
"""

    response_text = ""

    async def _run() -> None:
        nonlocal response_text
        async for message in query(
            prompt=reflection_prompt,
            options=ClaudeAgentOptions(
                allowed_tools=[],   # lean -- Python writes files, not the LLM
                max_turns=1,
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
        append_to_daily_log(f"**ERROR**: Reflection failed â€” {e}")
        return

    # Parse structured output and apply changes
    parsed = parse_reflection_response(response_text)

    if parsed.get("_parse_error"):
        print(f"[{now_local()}] Reflection: could not parse LLM response â€” skipping")
        append_to_daily_log(f"**[Reflection]** Parse error â€” raw: {response_text[:200]}")
        return

    wrote_memory = apply_memory_additions(parsed["memory_additions"], date_str)
    wrote_user = apply_user_updates(parsed["user_updates"], date_str)

    # Trim MEMORY.md if it grew too large
    trim_memory_if_needed()

    # Save state
    state["last_run_date"] = today_str
    state["log_processed"] = date_str
    state["result"] = "REFLECTION_OK" if parsed["nothing_to_update"] else "promoted"
    save_state(REFLECTION_STATE_FILE, state)

    if parsed["nothing_to_update"] and not (wrote_memory or wrote_user):
        append_to_daily_log("REFLECTION_OK â€” nothing to promote from yesterday's log")
        print(f"[{now_local()}] Reflection OK â€” nothing to promote")
    else:
        append_to_daily_log(f"**[Reflection]** Promoted items from {date_str} to MEMORY.md/USER.md")
        print(f"[{now_local()}] Reflection complete â€” items promoted")


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
