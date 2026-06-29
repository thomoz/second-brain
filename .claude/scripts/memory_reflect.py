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
    DECISIONS_DIR,
    ENTITIES_DIR,
    MEMORY_FILE,
    OWNER_NAME,
    PROFILE_DIR,
    REFLECTION_STATE_FILE,
    TOPICS_DIR,
    USER_FILE,
    VAULT_DIR,
    ensure_directories,
    get_log_path_for_date,
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
    log_path = get_log_path_for_date(yesterday)
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

    # Archive the overflow to decisions/ (avoids recreating retired Research/ folder)
    archive_dir = VAULT_DIR / "decisions"
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
    """Extract JSON from LLM response. Returns dict with all routing keys."""
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    raw = m.group(1) if m else text.strip()
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return {
            "active_items": [],
            "resolved_items": [],
            "daily_log_only": [],
            "entity_updates": [],
            "topic_updates": [],
            "new_entity_pages": [],
            "new_topic_pages": [],
            "profile_updates": [],
            "decision_archive": [],
            "memory_preferences": [],
            "memory_additions": [],
            "user_updates": [],
            "nothing_to_update": True,
            "_parse_error": True,
        }
    return {
        # New routing keys
        "active_items": data.get("active_items") or [],
        "resolved_items": data.get("resolved_items") or [],
        "daily_log_only": data.get("daily_log_only") or [],
        "entity_updates": data.get("entity_updates") or [],
        "topic_updates": data.get("topic_updates") or [],
        "new_entity_pages": data.get("new_entity_pages") or [],
        "new_topic_pages": data.get("new_topic_pages") or [],
        "profile_updates": data.get("profile_updates") or [],
        "decision_archive": data.get("decision_archive") or [],
        "memory_preferences": data.get("memory_preferences") or [],
        # Backward-compat keys (memory_additions redirected to daily log)
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
# ROUTING HELPERS
# =============================================================================


def get_existing_pages() -> dict[str, list[str]]:
    """Return stems of existing entity and topic pages for routing context."""
    entities = sorted(p.stem for p in ENTITIES_DIR.glob("*.md")) if ENTITIES_DIR.exists() else []
    topics = sorted(p.stem for p in TOPICS_DIR.glob("*.md")) if TOPICS_DIR.exists() else []
    return {"entities": entities, "topics": topics}


def count_file_mentions(name: str) -> int:
    """Count Memory/ files that mention this name (case-insensitive). Used for page creation threshold."""
    count = 0
    if not VAULT_DIR.exists():
        return 0
    for md_file in VAULT_DIR.rglob("*.md"):
        try:
            if name.lower() in md_file.read_text(encoding="utf-8").lower():
                count += 1
        except OSError:
            pass
    return count


def append_to_entity_page(page: str, content: str) -> bool:
    """Append dated bullet to existing entity page. Returns True if wrote."""
    page_path = ENTITIES_DIR / f"{page}.md"
    if not page_path.exists():
        return False
    with file_lock(page_path):
        current = page_path.read_text(encoding="utf-8")
        atomic_write(page_path, current.rstrip() + "\n" + content + "\n")
    return True


def append_to_topic_page(page: str, content: str) -> bool:
    """Append dated bullet to existing topic page. Returns True if wrote."""
    page_path = TOPICS_DIR / f"{page}.md"
    if not page_path.exists():
        return False
    with file_lock(page_path):
        current = page_path.read_text(encoding="utf-8")
        atomic_write(page_path, current.rstrip() + "\n" + content + "\n")
    return True


def append_to_profile_file(filename: str, content: str, date_str: str) -> bool:
    """Append dated section to Profile/ file. Returns True if wrote."""
    profile_path = PROFILE_DIR / f"{filename}.md"
    if not profile_path.exists():
        return False
    with file_lock(profile_path):
        current = profile_path.read_text(encoding="utf-8")
        section = f"\n\n## {date_str} Update\n{content}\n"
        atomic_write(profile_path, current.rstrip() + section)
    return True


def archive_decision(content: str, date_str: str) -> bool:
    """Append completed decision to current quarter archive."""
    month = int(date_str[5:7])
    quarter = f"{date_str[:4]}-Q{(month - 1) // 3 + 1}"
    archive_path = DECISIONS_DIR / f"{quarter}.md"
    DECISIONS_DIR.mkdir(parents=True, exist_ok=True)
    if not archive_path.exists():
        archive_path.write_text(
            f"---\ntitle: {quarter} Decisions\ntype: decisions\nquarter: {quarter}\ncreated: {date_str}\n---\n\n# {quarter} Decisions\n\n",
            encoding="utf-8",
        )
    with file_lock(archive_path):
        current = archive_path.read_text(encoding="utf-8")
        atomic_write(archive_path, current.rstrip() + "\n" + content + "\n")
    return True


def update_memory_active_items(items: list[str]) -> bool:
    """Append items to MEMORY.md ## Active Items section."""
    if not items:
        return False
    with file_lock(MEMORY_FILE):
        current = MEMORY_FILE.read_text(encoding="utf-8") if MEMORY_FILE.exists() else ""
        marker = "## Active Items"
        if marker in current:
            idx = current.index(marker)
            next_section = current.find("\n## ", idx + len(marker))
            footer_idx = current.rfind("\n---")
            if next_section != -1:
                insert_at = next_section
            elif footer_idx != -1:
                insert_at = footer_idx
            else:
                insert_at = len(current)
            new_items_str = "\n" + "\n".join(items)
            updated = current[:insert_at] + new_items_str + current[insert_at:]
        else:
            updated = current.rstrip() + "\n\n## Active Items\n\n" + "\n".join(items) + "\n"
        atomic_write(MEMORY_FILE, updated)
    return True


def update_memory_preferences(preferences: list[str]) -> bool:
    """Append items to MEMORY.md ## Preferences section."""
    if not preferences:
        return False
    with file_lock(MEMORY_FILE):
        current = MEMORY_FILE.read_text(encoding="utf-8") if MEMORY_FILE.exists() else ""
        marker = "## Preferences"
        if marker in current:
            idx = current.index(marker)
            next_section = current.find("\n## ", idx + len(marker))
            footer_idx = current.rfind("\n---")
            insert_at = next_section if next_section != -1 else (footer_idx if footer_idx != -1 else len(current))
            updated = current[:insert_at] + "\n" + "\n".join(preferences) + current[insert_at:]
        else:
            updated = current.rstrip() + "\n\n## Preferences\n\n" + "\n".join(preferences) + "\n"
        atomic_write(MEMORY_FILE, updated)
    return True


def remove_memory_active_items(items_to_remove: list[str]) -> bool:
    """Remove resolved active items from MEMORY.md Active Items section.
    Matches by substring — each entry in items_to_remove is a unique fragment of the line to remove.
    Returns True if any lines were removed."""
    if not items_to_remove or not MEMORY_FILE.exists():
        return False
    with file_lock(MEMORY_FILE):
        current = MEMORY_FILE.read_text(encoding="utf-8")
        lines = current.splitlines(keepends=True)
        new_lines = []
        removed = 0
        for line in lines:
            if any(fragment.lower() in line.lower() for fragment in items_to_remove):
                removed += 1
            else:
                new_lines.append(line)
        if removed == 0:
            return False
        atomic_write(MEMORY_FILE, "".join(new_lines))
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
        append_to_daily_log("REFLECTION_SKIPPED — no yesterday log found")
        return

    date_str, log_content = log_result
    current_memory = MEMORY_FILE.read_text(encoding="utf-8") if MEMORY_FILE.exists() else ""
    current_user = USER_FILE.read_text(encoding="utf-8") if USER_FILE.exists() else ""

    owner = OWNER_NAME or "Shaun"

    # Pre-compute existing pages for routing context
    pages = get_existing_pages()
    entity_list = ", ".join(pages["entities"]) or "none yet"
    topic_list = ", ".join(pages["topics"]) or "none yet"

    reflection_prompt = f"""Daily memory reflection for {owner}'s Second Brain.

Review yesterday's daily log and route items to the correct memory destination.
Respond with a single JSON block and nothing else.

## Existing Entity Pages
{entity_list}

## Existing Topic Pages
{topic_list}

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
  "active_items": ["- (Mon DD) time-sensitive or unresolved item"],
  "resolved_items": ["unique substring of existing active item that is now done"],
  "daily_log_only": ["- routine note worth logging but not tracking across sessions"],
  "entity_updates": [
    {{"page": "songbookdb", "content": "- (Mon DD) note about SongbookDB"}}
  ],
  "topic_updates": [
    {{"page": "investment-strategy", "content": "- (Mon DD) note about investments"}}
  ],
  "new_entity_pages": [],
  "new_topic_pages": [],
  "profile_updates": [
    {{"file": "goals", "content": "- (Mon DD) goal-related observation"}}
  ],
  "decision_archive": ["- (Mon DD) completed decision — chose X, done"],
  "memory_preferences": ["- preference or standing instruction"],
  "memory_additions": [],
  "user_updates": ["- operational config change"],
  "nothing_to_update": false
}}
```

## Routing Rules

### active_items -- STRICT BAR
Only add if ALL of the following are true:
  1. Requires action that cannot be completed in a single session
  2. Relates to a named business, project, or person already tracked in the vault
  3. Is NOT a routine notification, automated alert, or transactional email
Target: under 20 total active items. Quality over quantity.

### NEVER add to active_items:
  - DocuSign / e-signature notifications
  - PayPal / Stripe / bank transaction emails
  - Automated security alerts (password change, login notification) unless the account is actively compromised
  - Newsletters, subscription emails, marketing
  - Emails from senders not already tracked as a contact or entity
  - Items that can be handled in a single sitting
  - Items already present in Current MEMORY.md

### resolved_items
List substrings (unique fragments) of existing active items in Current MEMORY.md that are now
clearly resolved, stale (>14 days old with no follow-up), or irrelevant. Python will remove
lines containing these substrings. Be conservative -- only include items you are confident are done.

### daily_log_only
Items worth noting briefly but not worth tracking across sessions. These go to the daily log.
Use for: routine email follow-ups, one-off admin tasks, transactional notifications.

### entity_updates
"page" must be a stem from the Existing Entity Pages list. Facts about named businesses, people, venues.

### topic_updates
"page" must be a stem from the Existing Topic Pages list. Investment notes, growth strategy, etc.

### new_entity_pages / new_topic_pages
Only suggest if name appears in 3+ Memory/ files already.

### profile_updates
Personal statements about values, goals, health, relationships, finances.
"file" must be one of: values, goals, history, personality, health, relationships, finances.
Profile/ files are permanent -- never suggest archiving or summarising.

### decision_archive
Only for COMPLETED decisions -- no future action needed.

### memory_preferences
Standing communication or tool preferences only.

### memory_additions -- REDIRECT, DO NOT USE FOR MEMORY.md
This key is deprecated as a MEMORY.md destination. If you have items that don't fit the above
categories, put them in daily_log_only instead. memory_additions is ignored.

### nothing_to_update
Set true with all empty lists if the log contains nothing worth promoting.

### General
- Do NOT add anything already present in Current MEMORY.md or Current USER.md
- NEVER include SOUL.md content or personality edits
- Keep each item under 120 chars
- When yesterday's log contains any personal statements about values, goals, health,
  relationships, or finances -- route to profile_updates
- Treat Profile/ files as permanent. Never suggest archiving or summarising them.
- When in doubt, use daily_log_only or nothing_to_update -- prefer a lean MEMORY.md
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
        append_to_daily_log(f"**ERROR**: Reflection failed — {e}")
        return

    # Parse structured output and apply changes
    parsed = parse_reflection_response(response_text)

    if parsed.get("_parse_error"):
        print(f"[{now_local()}] Reflection: could not parse LLM response — skipping")
        append_to_daily_log(f"**[Reflection]** Parse error — raw: {response_text[:200]}")
        return

    # Route to structured pages
    wrote_entity = any(
        append_to_entity_page(u["page"], u["content"])
        for u in parsed["entity_updates"]
        if isinstance(u, dict) and "page" in u and "content" in u
    )
    wrote_topic = any(
        append_to_topic_page(u["page"], u["content"])
        for u in parsed["topic_updates"]
        if isinstance(u, dict) and "page" in u and "content" in u
    )
    wrote_profile = any(
        append_to_profile_file(u["file"], u["content"], date_str)
        for u in parsed["profile_updates"]
        if isinstance(u, dict) and "file" in u and "content" in u
    )
    wrote_decisions = any(archive_decision(d, date_str) for d in parsed["decision_archive"] if d)

    # Handle new page creation (verify 3-mention threshold first)
    for page_spec in parsed.get("new_entity_pages", []):
        if isinstance(page_spec, dict) and "name" in page_spec and "content" in page_spec:
            if count_file_mentions(page_spec["name"]) >= 3:
                page_path = ENTITIES_DIR / f"{page_spec['name']}.md"
                if not page_path.exists():
                    atomic_write(page_path, page_spec["content"])

    for page_spec in parsed.get("new_topic_pages", []):
        if isinstance(page_spec, dict) and "name" in page_spec and "content" in page_spec:
            if count_file_mentions(page_spec["name"]) >= 3:
                page_path = TOPICS_DIR / f"{page_spec['name']}.md"
                if not page_path.exists():
                    atomic_write(page_path, page_spec["content"])

    # MEMORY.md updates: prune resolved items first, then add new ones
    wrote_pruned = remove_memory_active_items(parsed.get("resolved_items", []))
    wrote_active = update_memory_active_items(parsed["active_items"])
    wrote_prefs = update_memory_preferences(parsed["memory_preferences"])

    # memory_additions deprecated as MEMORY.md destination -- redirect noise to daily log
    all_noise = parsed["memory_additions"] + parsed.get("daily_log_only", [])
    if all_noise:
        append_to_daily_log("[Reflection noise]\n" + "\n".join(all_noise))
    wrote_memory = False  # no longer writes to MEMORY.md

    wrote_user = apply_user_updates(parsed["user_updates"], date_str)

    trim_memory_if_needed()

    wrote_any = any([wrote_entity, wrote_topic, wrote_profile, wrote_decisions,
                     wrote_active, wrote_prefs, wrote_pruned, wrote_user])

    # Save state
    state["last_run_date"] = today_str
    state["log_processed"] = date_str
    state["result"] = "REFLECTION_OK" if parsed["nothing_to_update"] else "promoted"
    save_state(REFLECTION_STATE_FILE, state)

    if parsed["nothing_to_update"] and not wrote_any:
        append_to_daily_log("REFLECTION_OK — nothing to promote from yesterday's log")
        print(f"[{now_local()}] Reflection OK — nothing to promote")
    else:
        append_to_daily_log(f"**[Reflection]** Promoted items from {date_str} to structured memory pages")
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
