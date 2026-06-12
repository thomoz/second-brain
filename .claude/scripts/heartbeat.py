"""
Heartbeat Script for Second Brain

Scheduled script that gathers Gmail/Calendar/Outlook data (no LLM),
diffs against previous run state, then calls the LLM once to reason
over what's changed. The LLM can write drafts, update HABITS.md,
expire old drafts, and send a WhatsApp summary notification.

Usage:
    uv run python heartbeat.py              # Normal run (active-hours gated)
    uv run python heartbeat.py --dry-run    # Print snapshot + diff, no LLM
    uv run python heartbeat.py --force      # Bypass active-hours + interval gate
"""

from __future__ import annotations

# AGENT_INVOKED_BY must be set before any imports so the soul-protect hook fires correctly
import os

os.environ["AGENT_INVOKED_BY"] = "heartbeat"

import argparse
import io
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

# Force UTF-8 stdout/stderr on Windows
if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if sys.stderr.encoding != "utf-8":
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent))

# State file for heartbeat is imported directly from config
from config import (
    DRAFT_EXPIRY_HOURS,
    DRAFTS_ACTIVE_DIR,
    DRAFTS_EXPIRED_DIR,
    EXPIRED_DRAFT_RETENTION_DAYS,
    HABITS_FILE,
    HEARTBEAT_FILE,
    HEARTBEAT_INTERVAL_MINUTES,
    HEARTBEAT_STATE_FILE,
    HEARTBEAT_TIMEZONE,
    LOCAL_TZ,
    OWNER_NAME,
    USER_FILE,
    ensure_directories,
    is_within_active_hours,
    now_local,
)
from notifications import send_toast_notification, send_whatsapp_notification
from sanitize import TRUST_BOUNDARY_INSTRUCTION, wrap_external_data
from sdk_compat import (
    AssistantMessage,
    ClaudeAgentOptions,
    HookMatcher,
    ResultMessage,
    TextBlock,
    query,
)
from shared import (
    append_to_daily_log,
    file_lock,
    load_state,
    log_hook_execution,
    save_state,
)

# =============================================================================
# DATA GATHERING (no LLM)
# =============================================================================


def _gather_emails() -> dict[str, Any]:
    """Gather email data from Gmail (all accounts) and Outlook."""
    result: dict[str, Any] = {"gmail": [], "outlook": [], "error": None}
    try:
        from integrations.gmail import list_all_accounts

        result["gmail"] = list_all_accounts(max_per_account=5, hours_ago=4)
        print(f"[{now_local()}] Gmail: {len(result['gmail'])} emails")
    except Exception as e:
        result["error"] = f"gmail: {e}"
        print(f"[{now_local()}] Gmail error (non-fatal): {e}")
    try:
        from integrations.outlook import list_messages

        result["outlook"] = list_messages(max_results=5, hours_ago=4)
        print(f"[{now_local()}] Outlook: {len(result['outlook'])} messages")
    except Exception as e:
        prev = result["error"] or ""
        result["error"] = (prev + f" | outlook: {e}").lstrip(" | ")
        print(f"[{now_local()}] Outlook error (non-fatal): {e}")
    return result


def _gather_calendar() -> dict[str, Any]:
    """Gather calendar events for next 24 hours across all calendars."""
    result: dict[str, Any] = {"events": [], "has_show_today": False, "error": None}
    try:
        from integrations.calendar_api import get_all_calendars_events

        cal_data = get_all_calendars_events(hours_ahead=24)
        events = []
        for cal_events in cal_data.values():
            events.extend(cal_events)
        result["events"] = events

        show_keywords = {"karaoke", "bingo", "trivia", "show"}
        for ev in events:
            summary = getattr(ev, "summary", "") or ""
            if any(kw in summary.lower() for kw in show_keywords):
                result["has_show_today"] = True
                break

        n_events = len(events)
        has_show = result["has_show_today"]
        print(f"[{now_local()}] Calendar: {n_events} events, has_show_today={has_show}")
    except Exception as e:
        result["error"] = str(e)
        print(f"[{now_local()}] Calendar error (non-fatal): {e}")
    return result


def _parse_draft_frontmatter(filepath: Path) -> dict[str, str]:
    """Parse YAML frontmatter from a draft markdown file."""
    content = filepath.read_text(encoding="utf-8")
    meta: dict[str, str] = {}
    if content.startswith("---"):
        end = content.find("---", 3)
        if end != -1:
            for line in content[3:end].strip().split("\n"):
                if ":" in line:
                    key, val = line.split(":", 1)
                    meta[key.strip()] = val.strip()
    return meta


def _gather_drafts() -> list[dict[str, str]]:
    """Scan drafts/active/ and return list of draft summary dicts."""
    if not DRAFTS_ACTIVE_DIR.exists():
        return []
    drafts = []
    for f in sorted(DRAFTS_ACTIVE_DIR.glob("*.md")):
        meta = _parse_draft_frontmatter(f)
        drafts.append(
            {
                "filename": f.name,
                "type": meta.get("type", "?"),
                "subject": meta.get("subject", ""),
                "recipient": meta.get("recipient", ""),
                "status": meta.get("status", ""),
                "created": meta.get("created", ""),
            }
        )
    return drafts


def build_snapshot() -> dict[str, Any]:
    """Gather all current data and return a snapshot dict for diffing."""
    email_data = _gather_emails()
    cal_data = _gather_calendar()
    active_drafts = _gather_drafts()
    # TODO Phase 7: WhatsApp inbound polling goes here.
    # Guard required: check BOT_LOCK_FILE exists before calling get_unread_messages()
    # from config import BOT_LOCK_FILE
    # if not BOT_LOCK_FILE.exists(): whatsapp_data = get_unread_messages()
    habits_text = HABITS_FILE.read_text(encoding="utf-8") if HABITS_FILE.exists() else ""
    return {
        "timestamp": now_local().isoformat(),
        "emails": email_data,
        "calendar": cal_data,
        "active_drafts": active_drafts,
        "habits": habits_text,
    }


# =============================================================================
# STATE DIFF
# =============================================================================


def _email_ids(email_list: list) -> set[str]:
    ids: set[str] = set()
    for e in email_list:
        eid = getattr(e, "id", None) or (e if isinstance(e, str) else "")
        if eid:
            ids.add(str(eid))
    return ids


def _event_ids(event_list: list) -> set[str]:
    ids: set[str] = set()
    for ev in event_list:
        eid = getattr(ev, "id", None) or getattr(ev, "uid", None) or ""
        if eid:
            ids.add(str(eid))
    return ids


def diff_snapshot(prev: dict[str, Any], curr: dict[str, Any]) -> dict[str, Any]:
    """Compare two snapshots. Returns dict with change counts and flags."""
    prev_gmail_ids = _email_ids(prev.get("emails", {}).get("gmail", []))
    curr_gmail_ids = _email_ids(curr["emails"]["gmail"])
    prev_outlook_ids = _email_ids(prev.get("emails", {}).get("outlook", []))
    curr_outlook_ids = _email_ids(curr["emails"]["outlook"])
    prev_event_ids = _event_ids(prev.get("calendar", {}).get("events", []))
    curr_event_ids = _event_ids(curr["calendar"]["events"])

    new_emails = (curr_gmail_ids - prev_gmail_ids) | (curr_outlook_ids - prev_outlook_ids)
    new_events = curr_event_ids - prev_event_ids

    prev_draft_files = {d["filename"] for d in prev.get("active_drafts", [])}
    curr_draft_files = {d["filename"] for d in curr["active_drafts"]}
    draft_changes = prev_draft_files != curr_draft_files

    habits_delta = prev.get("habits", "") != curr["habits"]

    is_first_run = not bool(prev)

    return {
        "new_emails": new_emails,
        "new_events": new_events,
        "draft_changes": draft_changes,
        "habits_delta": habits_delta,
        "is_first_run": is_first_run,
        "has_changes": bool(
            new_emails or new_events or draft_changes or habits_delta or is_first_run
        ),
    }


# =============================================================================
# DRAFT LIFECYCLE
# =============================================================================


def expire_old_drafts() -> int:
    """Move drafts older than DRAFT_EXPIRY_HOURS from active/ to expired/. Returns count moved."""
    if not DRAFTS_ACTIVE_DIR.exists():
        return 0
    DRAFTS_EXPIRED_DIR.mkdir(parents=True, exist_ok=True)
    now = now_local()
    expired_count = 0
    for f in sorted(DRAFTS_ACTIVE_DIR.glob("*.md")):
        meta = _parse_draft_frontmatter(f)
        created = meta.get("created", "")
        if not created:
            continue
        try:
            created_dt = datetime.fromisoformat(created)
            if created_dt.tzinfo is None:
                created_dt = created_dt.replace(tzinfo=LOCAL_TZ)
            age_hours = (now - created_dt).total_seconds() / 3600
            if age_hours > DRAFT_EXPIRY_HOURS:
                shutil.move(str(f), str(DRAFTS_EXPIRED_DIR / f.name))
                expired_count += 1
                print(f"[{now_local()}] Expired draft: {f.name} ({age_hours:.0f}h old)")
        except (ValueError, TypeError):
            pass
    return expired_count


def cleanup_expired_drafts() -> int:
    """Delete expired drafts older than EXPIRED_DRAFT_RETENTION_DAYS. Returns count deleted."""
    if not DRAFTS_EXPIRED_DIR.exists():
        return 0
    now = now_local()
    deleted_count = 0
    for f in sorted(DRAFTS_EXPIRED_DIR.glob("*.md")):
        meta = _parse_draft_frontmatter(f)
        created = meta.get("created", "")
        if not created:
            continue
        try:
            created_dt = datetime.fromisoformat(created)
            if created_dt.tzinfo is None:
                created_dt = created_dt.replace(tzinfo=LOCAL_TZ)
            age_days = (now - created_dt).total_seconds() / 86400
            if age_days > EXPIRED_DRAFT_RETENTION_DAYS:
                f.unlink()
                deleted_count += 1
                print(f"[{now_local()}] Deleted expired draft: {f.name} ({age_days:.0f}d old)")
        except (ValueError, TypeError):
            pass
    return deleted_count


def auto_check_habits_show(has_show_today: bool) -> bool:
    """Auto-check Shows pillar in HABITS.md if a show is on today's calendar."""
    if not has_show_today or not HABITS_FILE.exists():
        return False
    content = HABITS_FILE.read_text(encoding="utf-8")
    if "- [ ] **Shows**" in content:
        new_content = content.replace("- [ ] **Shows**", "- [x] **Shows**", 1)
        with file_lock(HABITS_FILE):
            HABITS_FILE.write_text(new_content, encoding="utf-8")
        print(f"[{now_local()}] Auto-checked Shows pillar in HABITS.md")
        return True
    return False


def reset_habits_if_new_day(state: dict) -> bool:
    """Archive and reset HABITS.md if it's a new day. Returns True if reset performed."""
    if not HABITS_FILE.exists():
        return False
    today_str = now_local().strftime("%Y-%m-%d")
    last_reset = state.get("last_habits_reset_date", "")
    if last_reset == today_str:
        return False

    content = HABITS_FILE.read_text(encoding="utf-8")
    # Archive yesterday's checked state and reset all checkboxes
    archived = content.replace("- [x]", "- [ ]")
    history_entry = f"\n\n## History — {last_reset or 'previous'}\n" + content if last_reset else ""
    new_content = archived + history_entry
    with file_lock(HABITS_FILE):
        HABITS_FILE.write_text(new_content, encoding="utf-8")
    state["last_habits_reset_date"] = today_str
    print(f"[{now_local()}] Reset HABITS.md for new day ({today_str})")
    return True


# =============================================================================
# LLM HEARTBEAT CALL
# =============================================================================


def run_heartbeat(dry_run: bool = False, force: bool = False) -> None:
    """Run a single heartbeat cycle."""
    import asyncio

    _start = time.time()

    # Active-hours gate
    if not force and not is_within_active_hours():
        print(f"[{now_local()}] Outside active hours, skipping heartbeat")
        return

    # Load state
    state = load_state(HEARTBEAT_STATE_FILE)

    # Interval gate
    if not force and state.get("last_run"):
        try:
            last_dt = datetime.fromisoformat(state["last_run"])
            elapsed_min = (now_local() - last_dt).total_seconds() / 60
            if elapsed_min < HEARTBEAT_INTERVAL_MINUTES:
                remaining = HEARTBEAT_INTERVAL_MINUTES - elapsed_min
                print(f"[{now_local()}] Last run {elapsed_min:.0f}m ago, next in {remaining:.0f}m")
                return
        except (ValueError, TypeError):
            pass

    print(f"[{now_local()}] Running heartbeat...")

    # Gather data
    snapshot = build_snapshot()

    # Diff against previous
    prev_snapshot = state.get("snapshot", {})
    diff = diff_snapshot(prev_snapshot, snapshot)

    print(
        f"[{now_local()}] Diff: new_emails={len(diff['new_emails'])}, "
        f"new_events={len(diff['new_events'])}, draft_changes={diff['draft_changes']}, "
        f"habits_delta={diff['habits_delta']}, is_first_run={diff['is_first_run']}"
    )

    # Draft lifecycle (Python-side, deterministic)
    expired = expire_old_drafts()
    cleaned = cleanup_expired_drafts()
    if expired:
        print(f"[{now_local()}] Expired {expired} drafts")
    if cleaned:
        print(f"[{now_local()}] Cleaned {cleaned} old expired drafts")

    # Auto-check Shows pillar if show on calendar
    auto_check_habits_show(snapshot["calendar"]["has_show_today"])

    # Reset habits if new day
    reset_habits_if_new_day(state)

    if dry_run:
        print("\n--- DRY RUN SNAPSHOT ---")
        print(f"Timestamp: {snapshot['timestamp']}")
        print(f"Gmail emails: {len(snapshot['emails']['gmail'])}")
        print(f"Outlook messages: {len(snapshot['emails']['outlook'])}")
        print(f"Calendar events: {len(snapshot['calendar']['events'])}")
        print(f"Has show today: {snapshot['calendar']['has_show_today']}")
        print(f"Active drafts: {len(snapshot['active_drafts'])}")
        print("\n--- DIFF SUMMARY ---")
        print(f"New emails: {len(diff['new_emails'])}")
        print(f"New events: {len(diff['new_events'])}")
        print(f"Draft changes: {diff['draft_changes']}")
        print(f"Habits delta: {diff['habits_delta']}")
        print(f"First run: {diff['is_first_run']}")
        return

    # Build system context for LLM
    heartbeat_checklist = ""
    if HEARTBEAT_FILE.exists():
        heartbeat_checklist = HEARTBEAT_FILE.read_text(encoding="utf-8")
    user_ctx = USER_FILE.read_text(encoding="utf-8") if USER_FILE.exists() else ""
    habits_ctx = HABITS_FILE.read_text(encoding="utf-8") if HABITS_FILE.exists() else ""

    # Format email context
    email_lines: list[str] = []
    try:
        from integrations.gmail import format_emails_for_context

        if snapshot["emails"]["gmail"]:
            email_lines.append(
                "### Gmail (all accounts)\n"
                + format_emails_for_context(snapshot["emails"]["gmail"])
            )
    except Exception:
        pass
    try:
        from integrations.outlook import format_messages_for_context as fmt_outlook

        if snapshot["emails"]["outlook"]:
            email_lines.append("### Outlook\n" + fmt_outlook(snapshot["emails"]["outlook"]))
    except Exception:
        pass

    if snapshot["emails"]["error"]:
        email_lines.append(f"**Email error:** {snapshot['emails']['error']}")

    email_ctx = "\n\n".join(email_lines) or "No emails retrieved."

    # Format calendar context
    cal_ctx = ""
    try:
        from integrations.calendar_api import (
            format_all_calendars_for_context,
            get_all_calendars_events,
        )

        cal_data = get_all_calendars_events(hours_ahead=24)
        cal_ctx = format_all_calendars_for_context(cal_data)
    except Exception as e:
        cal_ctx = f"Calendar error: {e}"

    # Format active drafts
    if snapshot["active_drafts"]:
        draft_lines = []
        for d in snapshot["active_drafts"]:
            line = (
                f"- **{d['filename']}** — type: {d['type']}, "
                f"recipient: {d['recipient']}, subject: {d['subject']}"
            )
            draft_lines.append(line)
        drafts_ctx = "\n".join(draft_lines)
    else:
        drafts_ctx = "No active drafts."

    diff_summary = ""
    if not diff["has_changes"] and not diff["is_first_run"]:
        diff_summary = (
            "\n**No changes detected** since last heartbeat. "
            "Focus on draft management and habits only.\n"
        )
    else:
        parts = []
        if diff["new_emails"]:
            parts.append(f"{len(diff['new_emails'])} new emails")
        if diff["new_events"]:
            parts.append(f"{len(diff['new_events'])} new calendar events")
        if diff["draft_changes"]:
            parts.append("draft list changed")
        if diff["habits_delta"]:
            parts.append("habits updated")
        if diff["is_first_run"]:
            parts.append("first run")
        diff_summary = f"\n**Changes since last heartbeat:** {', '.join(parts)}.\n"

    owner = OWNER_NAME or "Shaun"

    heartbeat_prompt = f"""This is a HEARTBEAT check. You are {owner}'s Second Brain.
Proactive check.

## Response Format

Your FINAL text response is sent to {owner} as a WhatsApp + Toast notification.
Keep it to bullet points only — every word costs attention on a phone:
- Bullet points for items needing attention
- A "Priority: NORMAL/HIGH/URGENT" line
- Or exactly "HEARTBEAT_OK" if nothing needs attention

Current time: {now_local().strftime("%Y-%m-%d %H:%M:%S %Z")}
Timezone: {HEARTBEAT_TIMEZONE}
Last heartbeat: {state.get("last_run", "Never")}
{diff_summary}
## Email
{wrap_external_data(email_ctx, "email")}

## Calendar
{wrap_external_data(cal_ctx, "calendar")}

## Active Drafts
{drafts_ctx}

## Habits Tracker
{habits_ctx}

{TRUST_BOUNDARY_INSTRUCTION}

## Instructions

### Priority 1: Alerts
Review the data above. Surface anything NEW needing {owner}'s attention:
- Urgent emails (SongbookDB support, venue bookings, important business)
- Shows starting soon (check calendar carefully)
- Anything time-sensitive

Skip items already known (not new since last heartbeat).

### Priority 2: Draft Management
For unreplied important emails (per USER.md criteria):
- Check if a draft already exists in drafts/active/ or drafts/sent/
- If no draft: create one in Memory/drafts/active/ with YAML frontmatter
  (type, source_id, recipient, subject, created, status)
- Filename: YYYY-MM-DD_email_<slugified-name>.md

### Priority 3: Habits
- Read habits state above
- If evening (after 19:00) and pillars unchecked, nudge {owner}
- Shows pillar is already auto-checked by Python if a show is on the calendar

## Heartbeat Checklist
{heartbeat_checklist}

## USER Context
{user_ctx}
"""

    # Inline soul-protect hook — belt-and-suspenders on top of soul-protect.py
    async def protect_soul(event: Any) -> Any:
        tool_input = getattr(event, "tool_input", None) or {}
        if isinstance(tool_input, dict) and "SOUL.md" in tool_input.get("file_path", ""):
            return HookMatcher(
                decision="deny",
                reason="SOUL.md is write-protected from automated processes.",
            )
        return HookMatcher(decision="allow")

    response_text = ""

    async def _run() -> None:
        nonlocal response_text
        async for message in query(
            prompt=heartbeat_prompt,
            options=ClaudeAgentOptions(
                allowed_tools=["Read", "Write", "Edit", "Glob", "Grep"],
                hooks={
                    "PreToolUse": [
                        HookMatcher(matcher="Write", hooks=[protect_soul]),
                        HookMatcher(matcher="Edit", hooks=[protect_soul]),
                    ]
                },
                max_turns=10,
            ),
        ):
            if isinstance(message, AssistantMessage):
                response_text = ""
                for block in message.content:
                    if isinstance(block, TextBlock):
                        response_text += block.text
            elif isinstance(message, ResultMessage):
                print(f"[{now_local()}] Heartbeat LLM completed: {message.subtype}")

    try:
        asyncio.run(_run())
    except Exception as e:
        print(f"[{now_local()}] Heartbeat LLM error: {e}")
        append_to_daily_log(f"**ERROR**: Heartbeat LLM failed — {e}")
        return

    # Save state
    state["last_run"] = now_local().isoformat()
    state["snapshot"] = {
        "timestamp": snapshot["timestamp"],
        "email_count": len(snapshot["emails"]["gmail"]) + len(snapshot["emails"]["outlook"]),
        "event_count": len(snapshot["calendar"]["events"]),
        "draft_count": len(snapshot["active_drafts"]),
    }
    save_state(HEARTBEAT_STATE_FILE, state)

    response_text = response_text.strip() or "HEARTBEAT_OK"

    if "HEARTBEAT_OK" in response_text:
        append_to_daily_log("HEARTBEAT_OK — nothing needs attention")
        print(f"[{now_local()}] Heartbeat OK — nothing to report")
    else:
        append_to_daily_log(f"**[Heartbeat]**\n{response_text}")
        send_toast_notification("Second Brain Alert", response_text)
        send_whatsapp_notification(response_text)
        print(f"[{now_local()}] Heartbeat alert sent: {response_text[:100]}...")

    elapsed = time.time() - _start
    log_hook_execution("heartbeat", f"completed in {elapsed:.1f}s")


# =============================================================================
# ENTRY POINT
# =============================================================================


def main() -> None:
    ensure_directories()

    parser = argparse.ArgumentParser(description="Second Brain heartbeat check")
    parser.add_argument("--dry-run", action="store_true", help="Print snapshot + diff, no LLM call")
    parser.add_argument("--force", action="store_true", help="Bypass active-hours + interval gate")
    args = parser.parse_args()

    if args.dry_run:
        print("Running in DRY RUN mode (no LLM call)")
    elif args.force:
        print("Running with --force (bypassing active-hours + interval gate)")

    run_heartbeat(dry_run=args.dry_run, force=args.force)


if __name__ == "__main__":
    main()
