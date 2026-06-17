# Feature: Phase 6 — Proactive Systems (Heartbeat + Reflection)

The following plan should be complete, but validate documentation and codebase patterns
before implementing. Pay special attention to sdk_compat imports — NEVER import from
claude_agent_sdk directly. All LLM calls go through `.claude/scripts/sdk_compat.py`.

NOTE: The WhatsApp chat bot (interactive CarPlay bot) is Phase 7. This plan covers only
the scheduled proactive systems. Phase 6 adds WhatsApp as an OUTBOUND notification channel
for the heartbeat. The full interactive bot moves to Phase 7.

## Feature Description

Adds two proactive subsystems:

1. **Heartbeat** — Scheduled script that gathers Gmail/Calendar/Outlook data (no LLM),
   diffs against the previous run's state, then calls the LLM once to reason over what's
   changed. The LLM can write drafts, update HABITS.md, expire old drafts, and send a
   WhatsApp summary notification to Shaun. Runs every HEARTBEAT_INTERVAL_MINUTES (currently
   30 in .env, should be 240+ for production). Active-hours gated.

2. **Daily Reflection** — Separate script that reads the last N days of daily logs and
   calls the LLM once to update MEMORY.md and USER.md with learned patterns. Runs once
   per day. SOUL.md is write-protected from all automated processes.

## User Story

As Shaun (multi-business founder)
I want automated monitoring of my inbox/calendar with WhatsApp summary notifications
So that I stay on top of urgent matters without manually checking every system

## Problem Statement

Phases 1–5 built memory, hooks, search, integrations, and skills — but everything is
reactive (requires manual invocation). Phase 6 adds scheduled proactive monitoring.

## Solution Statement

- Heartbeat: Python-only data gather → state diff → single LLM call (3-stage, no guardrail)
- Reflection: Daily LLM call over recent logs → update MEMORY.md + USER.md
- Notifications: Windows Toast + outbound WhatsApp via GREEN-API REST API
- All LLM calls use sdk_compat; AGENT_INVOKED_BY env var set by all automated scripts

## Feature Metadata

**Feature Type**: New Capability
**Estimated Complexity**: Medium
**Primary Systems Affected**: .claude/scripts/, .claude/hooks/
**Dependencies**: requests (existing), win10toast-click (existing), GREEN-API REST API

---

## CONTEXT REFERENCES

### Relevant Codebase Files — READ THESE BEFORE IMPLEMENTING

- `.claude/scripts/sdk_compat.py` — ALL LLM calls import from here. Never import from
  `claude_agent_sdk` directly. Exports: `query`, `ClaudeAgentOptions`, `AssistantMessage`,
  `TextBlock`, `ResultMessage`, `HookMatcher`, `run_text`.

- `.claude/scripts/config.py` (full file) — Current constants. Add Phase 6 constants
  (HEARTBEAT_STATE_FILE, WHATSAPP_* send constants, etc.). NOTE: `ACTIVE_DRAFTS_DIR`
  already exists; `DRAFTS_DIR / "sent"` and `DRAFTS_DIR / "expired"` already created
  in `ensure_directories()` but not named as constants.

- `.claude/scripts/shared.py` (full file) — Current utilities. Missing: `load_state()`,
  `save_state()`, `log_hook_execution()`, `file_lock` timeout param.

- `.claude/hooks/soul-protect.py` (full file) — Currently only blocks
  `AGENT_INVOKED_BY == "reflection"`. Must block ANY truthy `AGENT_INVOKED_BY` value.

- `.claude/scripts/integrations/query.py` (full file) — Unified CLI. Pattern to follow
  when adding `whatsapp` subcommand (`cmd_whatsapp()` function + subparser).

- `.claude/scripts/sanitize.py` — Use `sanitize_external_text()` and
  `TRUST_BOUNDARY_INSTRUCTION` in heartbeat for external data from emails/calendar.

- `.claude/scripts/pyproject.toml` — Already has `win10toast-click`. No new deps needed
  for Phase 6 (requests is already in Phase 4 deps; GREEN-API called directly via REST).

### Cole's Reference Files — READ THESE BEFORE IMPLEMENTING

All at `O:\AI\Dynamous\Courses\workshops\claude-code-second-brain\`:

- `.claude/scripts/heartbeat.py` — Full reference. Adapt: remove Asana/Slack/Circle,
  replace `from claude_agent_sdk import ...` with `from sdk_compat import ...`, add
  soul-protect inline hook, no guardrail LLM call.

- `.claude/scripts/memory_reflect.py` — Full reference. Adapt: same sdk_compat swap,
  inline `protect_soul_file` hook pattern to copy.

- `.claude/scripts/notifications.py` — Reference for `send_toast_notification()` and
  `_notify_windows()`. Replace Slack notification with WhatsApp send.

### New Files to Create

```
.claude/scripts/heartbeat.py               # 3-stage heartbeat pipeline
.claude/scripts/notifications.py           # Windows Toast + WhatsApp outbound send
.claude/scripts/memory_reflect.py          # Daily reflection (MEMORY.md + USER.md)
.claude/scripts/integrations/whatsapp.py   # GREEN-API REST client (send + query)
```

### Files to Update

```
.claude/scripts/config.py                  # Add Phase 6 constants + helpers
.claude/scripts/shared.py                  # Add load_state, save_state, etc.
.claude/scripts/integrations/query.py      # Add whatsapp subcommand
.claude/hooks/soul-protect.py              # Block ANY AGENT_INVOKED_BY value
```

### Patterns to Follow

**sdk_compat import pattern** (MANDATORY — never import claude_agent_sdk directly):
```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))  # adjust depth as needed
from sdk_compat import query, ClaudeAgentOptions, AssistantMessage, TextBlock
```

**Automated script env var** (set before any LLM call):
```python
import os
os.environ["AGENT_INVOKED_BY"] = "heartbeat"  # or "reflection"
```

**Inline soul-protect hook** (for heartbeat + reflection LLM calls):
```python
async def protect_soul(event):
    tool_input = event.tool_input or {}
    if "SOUL.md" in tool_input.get("file_path", ""):
        return HookMatcher(decision="deny", reason="SOUL.md is write-protected from automated processes.")
    return HookMatcher(decision="allow")
```

**State load/save** (after shared.py update):
```python
from shared import load_state, save_state
state = load_state(HEARTBEAT_STATE_FILE)   # returns {} if file missing
save_state(HEARTBEAT_STATE_FILE, new_state)
```

**GREEN-API REST send pattern** (no SDK, use requests):
```python
BASE = f"https://api.green-api.com/waInstance{instance_id}"
resp = requests.post(
    f"{BASE}/sendMessage/{api_token}",
    json={"chatId": f"{phone}@c.us", "message": text},
    timeout=10,
)
```

---

## IMPLEMENTATION PLAN

### Phase A: Foundation (config + shared)

Extend config.py and shared.py with constants and utilities all Phase 6 scripts need.
Do this first — every subsequent task depends on these.

### Phase B: Integrations (WhatsApp module + query.py update)

Add the GREEN-API WhatsApp REST client used by notifications.py and the query.py CLI.
Phase 6 only needs outbound send. Inbound polling is Phase 7.

### Phase C: Proactive Scripts (notifications + heartbeat + reflection)

Build the scheduled scripts. Order: notifications.py → heartbeat.py → memory_reflect.py.

### Phase D: Hook Update (soul-protect.py)

One-line change. Expand protection from "reflection only" to "any automated process."

### Phase E: Dependencies + Scheduler Setup

No new pyproject.toml deps needed. Configure Windows Task Scheduler for both scripts.

---

## STEP-BY-STEP TASKS

IMPORTANT: Execute in order. Each task is independently testable.

---

### Task 1: UPDATE `.claude/scripts/config.py`

- **ADD** constants block `# Phase 6: Proactive Systems` after Phase 4 block
- **ADD** `PROJECT_ROOT` derived from `__file__`:
  ```python
  PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
  ```
- **ADD** owner/heartbeat constants (read from env with defaults):
  ```python
  OWNER_NAME = _os.getenv("OWNER_NAME", "Shaun")
  ACTIVE_HOURS_START = int(_os.getenv("ACTIVE_HOURS_START", "7"))
  ACTIVE_HOURS_END = int(_os.getenv("ACTIVE_HOURS_END", "22"))
  ```
  NOTE: `.env` has `HEARTBEART_INTERVAL_MINUTES` (typo: extra A). Read BOTH spellings,
  prefer correct spelling, fall back to typo variant:
  ```python
  _hb_env = _os.getenv("HEARTBEAT_INTERVAL_MINUTES") or _os.getenv("HEARTBEART_INTERVAL_MINUTES", "240")
  HEARTBEAT_INTERVAL_MINUTES = int(_hb_env)
  ```
- **ADD** Memory file path constants:
  ```python
  SOUL_FILE = VAULT_DIR / "SOUL.md"
  USER_FILE = VAULT_DIR / "USER.md"
  MEMORY_FILE = VAULT_DIR / "MEMORY.md"
  HABITS_FILE = VAULT_DIR / "HABITS.md"
  HEARTBEAT_FILE = VAULT_DIR / "HEARTBEAT.md"
  ```
- **ADD** State file constants:
  ```python
  HEARTBEAT_STATE_FILE = STATE_DIR / "heartbeat-state.json"
  REFLECTION_STATE_FILE = STATE_DIR / "reflection-state.json"
  ```
- **ADD** Draft lifecycle constants (dirs already created in ensure_directories):
  ```python
  DRAFTS_ACTIVE_DIR = ACTIVE_DRAFTS_DIR  # alias for clarity
  DRAFTS_EXPIRED_DIR = DRAFTS_DIR / "expired"
  DRAFTS_SENT_DIR = DRAFTS_DIR / "sent"
  DRAFT_EXPIRY_HOURS = int(_os.getenv("DRAFT_EXPIRY_HOURS", "24"))
  EXPIRED_DRAFT_RETENTION_DAYS = int(_os.getenv("EXPIRED_DRAFT_RETENTION_DAYS", "30"))
  ```
- **ADD** WhatsApp send constants (outbound only — inbound/chat constants are Phase 7):
  ```python
  WHATSAPP_INSTANCE_ID = _os.getenv("WHATSAPP_INSTANCE_ID", "")
  WHATSAPP_API_TOKEN = _os.getenv("WHATSAPP_API_TOKEN", "")
  WHATSAPP_MY_NUMBER = _os.getenv("WHATSAPP_MY_NUMBER", "")  # format: 61412345678
  ```
- **ADD** helper functions:
  ```python
  def is_within_active_hours() -> bool:
      hour = now_local().hour
      return ACTIVE_HOURS_START <= hour < ACTIVE_HOURS_END

  def get_today_log_path() -> Path:
      return DAILY_DIR / f"{now_local().strftime('%Y-%m-%d')}.md"
  ```
- **GOTCHA**: `HEARTBEAT_STATE_FILE = STATE_DIR / "heartbeat-state.json"` matches the
  existing filename at `.claude/data/state/heartbeat-state.json` (per CLAUDE.md).
- **GOTCHA**: `DRAFTS_DIR / "sent"` and `DRAFTS_DIR / "expired"` are already created in
  `ensure_directories()` — add named constants only, no duplicate `mkdir` calls.
- **VALIDATE**:
  ```powershell
  cd .claude/scripts
  uv run python -c "from config import HEARTBEAT_STATE_FILE, WHATSAPP_MY_NUMBER, is_within_active_hours; print(HEARTBEAT_STATE_FILE, is_within_active_hours())"
  ```

---

### Task 2: UPDATE `.claude/scripts/shared.py`

- **ADD** `import json` at top of file
- **ADD** `load_state(path: Path) -> dict`:
  ```python
  def load_state(path: Path) -> dict:
      try:
          return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
      except (json.JSONDecodeError, OSError):
          return {}
  ```
- **ADD** `save_state(path: Path, state: dict) -> None`:
  ```python
  def save_state(path: Path, state: dict) -> None:
      path.parent.mkdir(parents=True, exist_ok=True)
      atomic_write(path, json.dumps(state, indent=2, default=str))
  ```
- **ADD** `log_hook_execution(hook_name: str, result: str) -> None`:
  ```python
  def log_hook_execution(hook_name: str, result: str) -> None:
      append_to_daily_log(f"**[Hook: {hook_name}]** {result}")
  ```
- **UPDATE** `file_lock()` to accept `timeout: float = 30.0`. On Windows, raise
  `TimeoutError` if lock not acquired within timeout:
  ```python
  @contextlib.contextmanager
  def file_lock(path: Path, timeout: float = 30.0):
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
      else:
          # fcntl branch: unchanged
  ```
- **GOTCHA**: Do NOT add an async `validate_bash_command` hook to shared.py — that hook
  lives as an inline closure inside heartbeat.py and memory_reflect.py, not in shared.py.
- **VALIDATE**:
  ```powershell
  cd .claude/scripts
  uv run python -c "from shared import load_state, save_state; import tempfile, pathlib; p = pathlib.Path(tempfile.mktemp(suffix='.json')); save_state(p, {'x': 1}); print(load_state(p))"
  ```

---

### Task 3: CREATE `.claude/scripts/integrations/whatsapp.py`

Phase 6 needs outbound send. `get_unread_messages()` is included for the CLI but the
heartbeat does NOT call it (Phase 7 bot handles inbound).

- **IMPLEMENT** `@dataclass WhatsAppMessage`:
  Fields: `id: str`, `sender: str`, `text: str`, `timestamp: datetime`, `is_from_me: bool`

- **IMPLEMENT** `get_greenapi_base(instance_id: str) -> str`:
  ```python
  def get_greenapi_base(instance_id: str) -> str:
      return f"https://api.green-api.com/waInstance{instance_id}"
  ```

- **IMPLEMENT** `send_message(chat_id: str, text: str, instance_id: str = "", api_token: str = "") -> bool`:
  ```python
  def send_message(chat_id: str, text: str, instance_id: str = "", api_token: str = "") -> bool:
      from config import WHATSAPP_INSTANCE_ID, WHATSAPP_API_TOKEN
      iid = instance_id or WHATSAPP_INSTANCE_ID
      tok = api_token or WHATSAPP_API_TOKEN
      if not iid or not tok:
          return False
      resp = requests.post(
          f"{get_greenapi_base(iid)}/sendMessage/{tok}",
          json={"chatId": chat_id, "message": text},
          timeout=10,
      )
      return resp.status_code == 200
  ```

- **IMPLEMENT** `get_unread_messages(limit: int = 10) -> list[WhatsAppMessage]`:
  Polls GREEN-API notification queue via `receiveNotification` + `deleteNotification`.
  Returns incoming text messages only. Stops after `limit` messages or empty queue.
  NOTE: Destructive (dequeues messages). Do not call if Phase 7 bot is running.

- **IMPLEMENT** `format_messages_for_context(messages: list[WhatsAppMessage]) -> str`:
  Returns multi-line string: `[HH:MM] {sender}: {text}` per message.

- **IMPORTS**: `requests`, `dataclasses`, `datetime`, `sys`, `Path`
- **VALIDATE**:
  ```powershell
  cd .claude/scripts
  uv run python -c "from integrations.whatsapp import WhatsAppMessage, get_greenapi_base; print(get_greenapi_base('12345'))"
  ```

---

### Task 4: UPDATE `.claude/scripts/integrations/query.py`

- **ADD** `cmd_whatsapp(args: argparse.Namespace) -> None` after `cmd_outlook`:
  ```python
  def cmd_whatsapp(args: argparse.Namespace) -> None:
      from integrations.whatsapp import format_messages_for_context, get_unread_messages, send_message
      from config import WHATSAPP_MY_NUMBER

      if args.action == "list":
          msgs = get_unread_messages(limit=args.max)
          print(format_messages_for_context(msgs))
      elif args.action == "unread":
          msgs = get_unread_messages(limit=50)
          print(f"Unread WhatsApp messages: {len(msgs)}")
      elif args.action == "send":
          if not args.text:
              print("Error: --text required for send command")
              sys.exit(1)
          chat_id = args.chat_id or f"{WHATSAPP_MY_NUMBER}@c.us"
          ok = send_message(chat_id, args.text)
          print("Sent" if ok else "Failed to send")
  ```
- **ADD** whatsapp subparser in `main()`:
  ```python
  wa_parser = subparsers.add_parser("whatsapp", help="WhatsApp operations via GREEN-API")
  wa_parser.add_argument("action", choices=["list", "unread", "send"])
  wa_parser.add_argument("--max", type=int, default=10)
  wa_parser.add_argument("--text", default=None)
  wa_parser.add_argument("--chat-id", default=None, dest="chat_id")
  ```
- **ADD** dispatch: `elif args.service == "whatsapp": cmd_whatsapp(args)`
- **VALIDATE**:
  ```powershell
  cd .claude/scripts
  uv run python integrations/query.py whatsapp --help
  ```

---

### Task 5: CREATE `.claude/scripts/notifications.py`

- **IMPLEMENT** `send_console_notification(title: str, message: str) -> bool`:
  Prints `[NOTIFY] {title}: {message}` to stdout. Returns True. Always safe to call.

- **IMPLEMENT** `send_toast_notification(title: str, message: str, duration: int = 5) -> bool`:
  Uses `win10toast_click.ToastNotifier` on Windows. Falls back to console on non-Windows
  or ImportError. Reference: Cole's `_notify_windows()`.
  ```python
  def send_toast_notification(title: str, message: str, duration: int = 5) -> bool:
      if sys.platform != "win32":
          return send_console_notification(title, message)
      try:
          from win10toast_click import ToastNotifier
          ToastNotifier().show_toast(title, message, duration=duration, threaded=True)
          return True
      except Exception:
          return send_console_notification(title, message)
  ```

- **IMPLEMENT** `send_whatsapp_notification(message: str, chat_id: str = "") -> bool`:
  ```python
  def send_whatsapp_notification(message: str, chat_id: str = "") -> bool:
      from config import WHATSAPP_MY_NUMBER
      from integrations.whatsapp import send_message
      if not WHATSAPP_MY_NUMBER and not chat_id:
          return False
      return send_message(chat_id or f"{WHATSAPP_MY_NUMBER}@c.us", message)
  ```

- **VALIDATE**:
  ```powershell
  cd .claude/scripts
  uv run python -c "from notifications import send_console_notification; send_console_notification('Test', 'Phase 6 notifications OK')"
  ```

---

### Task 6: CREATE `.claude/scripts/heartbeat.py`

**Section A: Imports + setup**
```python
import os
os.environ["AGENT_INVOKED_BY"] = "heartbeat"  # Must be first — before any imports
import sys, json, argparse
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from sdk_compat import query, ClaudeAgentOptions, HookMatcher
from config import (
    VAULT_DIR, DAILY_DIR, DRAFTS_ACTIVE_DIR, DRAFTS_EXPIRED_DIR, DRAFTS_SENT_DIR,
    HEARTBEAT_STATE_FILE, HEARTBEAT_FILE, HABITS_FILE, SOUL_FILE, USER_FILE, MEMORY_FILE,
    HEARTBEAT_INTERVAL_MINUTES, DRAFT_EXPIRY_HOURS, now_local,
    is_within_active_hours, get_today_log_path, GOOGLE_CALENDAR_IDS,
)
from shared import load_state, save_state, append_to_daily_log, file_lock
from sanitize import sanitize_external_text, TRUST_BOUNDARY_INSTRUCTION
```

**Section B: Data gathering (no LLM)**

- **IMPLEMENT** `_gather_emails() -> dict`:
  Calls `list_all_accounts()` from `integrations.gmail` + `list_messages()` from
  `integrations.outlook`. Wraps each in try/except — auth failure returns empty, not crash.
  Returns: `{"gmail": [...], "outlook": [...], "error": None|str}`

- **IMPLEMENT** `_gather_calendar() -> dict`:
  Calls `get_all_calendars_events()` from `integrations.calendar_api`.
  Returns: `{"events": [...], "has_show_today": bool, "error": None|str}`
  For `has_show_today`: check if any event title contains "karaoke", "bingo", "trivia",
  or "show" (case-insensitive).

- **IMPLEMENT** `_gather_drafts() -> list[dict]`:
  Scan `DRAFTS_ACTIVE_DIR` for `.md` files. Parse YAML frontmatter for type, created,
  subject, recipient, status. Return list of summary dicts.

- **IMPLEMENT** `build_snapshot() -> dict`:
  ```python
  {
      "timestamp": now_local().isoformat(),
      "emails": _gather_emails(),
      "calendar": _gather_calendar(),
      "active_drafts": _gather_drafts(),
      "habits": HABITS_FILE.read_text() if HABITS_FILE.exists() else "",
  }
  ```

**Section C: State diff**

- **IMPLEMENT** `diff_snapshot(prev: dict, curr: dict) -> dict`:
  Compare email counts, new events, draft changes, habits delta.
  Returns dict with: `new_emails`, `new_events`, `draft_changes`, `habits_delta`,
  `is_first_run`.

**Section D: Draft lifecycle**

- **IMPLEMENT** `expire_old_drafts() -> int`:
  Move drafts in `DRAFTS_ACTIVE_DIR` older than `DRAFT_EXPIRY_HOURS` to `DRAFTS_EXPIRED_DIR`.
  Parse `created` from YAML frontmatter. Return count expired.

- **IMPLEMENT** `auto_check_habits_show(has_show_today: bool) -> bool`:
  If `has_show_today` and HABITS.md Shows pillar unchecked (`- [ ] **Shows**`),
  replace with `- [x] **Shows**`. Returns True if changed.

**Section E: Morning HABITS.md reset**

- **IMPLEMENT** `reset_habits_if_new_day(state: dict) -> bool`:
  Check `state.get("last_habits_reset_date")` vs today. If new day: archive yesterday's
  checkboxes to `## History`, reset all `- [x]` → `- [ ]`, save today's date in state.
  Returns True if reset performed.

**Section F: LLM reasoning call**

- **IMPLEMENT** inline `protect_soul` hook (copy from patterns section)
- **IMPLEMENT** `run_heartbeat(dry_run: bool = False, force: bool = False) -> None`:
  1. `is_within_active_hours()` — skip + log if outside window
  2. Load state via `load_state(HEARTBEAT_STATE_FILE)`
  3. Unless `force`: skip if last run < `HEARTBEAT_INTERVAL_MINUTES` ago
  4. Build snapshot, diff, expire drafts, auto-check show pillar, reset HABITS if new day
  5. If `dry_run`: print snapshot + diff summary, return
  6. Build system prompt: `HEARTBEAT_FILE` + `USER_FILE` + snapshot + diff + `TRUST_BOUNDARY_INSTRUCTION`
  7. Include current local time in prompt so LLM can decide on late-day nudge timing
  8. `query(prompt, options=ClaudeAgentOptions(allowed_tools=["Read","Write","Edit","Glob","Grep"], hooks=[protect_soul], max_turns=10))`
  9. Save state (update `last_run` timestamp)
  10. `send_toast_notification()` + `send_whatsapp_notification()` with result summary
  11. `append_to_daily_log()` with run summary

- **ADD** `main()` with argparse: `--dry-run`, `--force`
- **GOTCHA**: `os.environ["AGENT_INVOKED_BY"] = "heartbeat"` MUST be set before any import
  so the soul-protect.py PreToolUse hook fires correctly during the LLM call.
- **GOTCHA**: Wrap ALL integration calls in try/except. Auth failures must not abort heartbeat.
- **GOTCHA**: Late-day nudge is the LLM's decision based on the time in the prompt. Do not
  hardcode any time-of-day logic in Python for this.
- **VALIDATE**:
  ```powershell
  cd .claude/scripts
  uv run python heartbeat.py --dry-run
  ```

---

### Task 7: CREATE `.claude/scripts/memory_reflect.py`

- **SET** `os.environ["AGENT_INVOKED_BY"] = "reflection"` at top before imports
- **IMPLEMENT** `get_yesterday_log() -> tuple[str, str] | None`:
  Returns `(date_str, content)` for yesterday's log file, or None if it doesn't exist.
  Cole's reference reads yesterday only (not a rolling N-day window) — each daily run
  processes the previous day. If a day is missed, it's missed; logs aren't re-processed.
- **IMPLEMENT** inline `protect_soul` hook — copy from patterns section (don't import
  from heartbeat.py; each file has its own inline copy).
- **IMPLEMENT** `trim_memory_if_needed(max_lines: int = 200) -> bool`:
  If MEMORY.md exceeds `max_lines`, archive the oldest entries to a dated file in
  `Memory/Research/` and trim MEMORY.md back to `max_lines`. Returns True if trimmed.
  Reference: Cole's memory_reflect trims MEMORY.md at ~200 lines.
- **IMPLEMENT** `run_reflection(dry_run: bool = False, force: bool = False) -> None`:
  1. Load state via `load_state(REFLECTION_STATE_FILE)`
  2. Unless `force`: skip if `state.get("last_run_date") == today`
  3. Get yesterday's log via `get_yesterday_log()`
  4. If `dry_run`: print yesterday's log path (or "no log found"), return
  5. Build prompt: yesterday's log + current MEMORY.md + USER.md
  6. System instruction: promote key items to MEMORY.md and update USER.md;
     do NOT edit SOUL.md
  7. Use `file_lock(MEMORY_FILE)` to guard against concurrent heartbeat writes
  8. `query(prompt, options=ClaudeAgentOptions(allowed_tools=["Read","Write","Edit","Glob","Grep"], hooks=[protect_soul], max_turns=5))`
  9. `trim_memory_if_needed()` after LLM write
  10. Save state with `last_run_date = today`
  11. `append_to_daily_log()` with summary
- **ADD** `main()` with argparse: `--dry-run`, `--force`
- **GOTCHA**: SOUL.md has belt-and-suspenders protection: inline `protect_soul` hook AND
  the `soul-protect.py` PreToolUse hook (updated in Task 8).
- **VALIDATE**:
  ```powershell
  cd .claude/scripts
  uv run python memory_reflect.py --dry-run
  ```

---

### Task 8: UPDATE `.claude/hooks/soul-protect.py`

- **UPDATE** docstring to: `"""PreToolUse hook: block all automated agents from editing SOUL.md."""`
- **UPDATE** condition — one character change:
  ```python
  # BEFORE:
  if os.environ.get("AGENT_INVOKED_BY") == "reflection":

  # AFTER:
  if os.environ.get("AGENT_INVOKED_BY"):
  ```
- **UPDATE** deny reason:
  ```python
  "SOUL.md is write-protected from all automated processes. "
  "Log personality change suggestions to the daily log instead."
  ```
- **VALIDATE**:
  ```powershell
  $env:AGENT_INVOKED_BY = "heartbeat"
  echo '{"tool_input": {"file_path": "Memory/SOUL.md"}}' | uv run python .claude/hooks/soul-protect.py
  # Expect: JSON with permissionDecision: deny
  Remove-Item Env:\AGENT_INVOKED_BY

  $env:AGENT_INVOKED_BY = "heartbeat"
  echo '{"tool_input": {"file_path": "Memory/MEMORY.md"}}' | uv run python .claude/hooks/soul-protect.py
  # Expect: exit 0, no deny
  Remove-Item Env:\AGENT_INVOKED_BY
  ```

---

### Task 9: SETUP — Add .env variables

Add to `.claude/scripts/.env` (do not commit):
```
# Phase 6: WhatsApp outbound (GREEN-API)
WHATSAPP_INSTANCE_ID=
WHATSAPP_API_TOKEN=
WHATSAPP_MY_NUMBER=61XXXXXXXXX

# Phase 6: Owner / Heartbeat
OWNER_NAME=Shaun
ACTIVE_HOURS_START=7
ACTIVE_HOURS_END=22
DRAFT_EXPIRY_HOURS=24
```

WHATSAPP_MY_NUMBER format: country code + number, no `+`.
Australian mobile +61 412 345 678 → `61412345678`
GREEN-API chat_id format: `61412345678@c.us`

GREEN-API account setup (one-time manual step):
1. Sign up at https://green-api.com
2. Create an instance, scan QR code with your WhatsApp
3. Copy Instance ID and API Token to .env

---

### Task 10: SETUP — Windows Task Scheduler

```powershell
# Heartbeat — every 4 hours, starting 7 AM:
$trigger = New-ScheduledTaskTrigger -RepetitionInterval (New-TimeSpan -Hours 4) -Once -At "07:00"
$action = New-ScheduledTaskAction `
    -Execute "uv" `
    -Argument "run python heartbeat.py" `
    -WorkingDirectory "O:\AI\Dynamous\Courses\second-brain-workshop\.claude\scripts"
Register-ScheduledTask -TaskName "SecondBrain-Heartbeat" -Trigger $trigger -Action $action -RunLevel Highest

# Reflection — once daily at 3 AM:
$trigger2 = New-ScheduledTaskTrigger -Daily -At "03:00"
$action2 = New-ScheduledTaskAction `
    -Execute "uv" `
    -Argument "run python memory_reflect.py" `
    -WorkingDirectory "O:\AI\Dynamous\Courses\second-brain-workshop\.claude\scripts"
Register-ScheduledTask -TaskName "SecondBrain-Reflection" -Trigger $trigger2 -Action $action2 -RunLevel Highest
```

---

## TESTING STRATEGY

### Unit Tests

Add to `.claude/scripts/tests/`:

- `test_heartbeat.py` — Test `diff_snapshot()` with mock prev/curr dicts. Test
  `expire_old_drafts()` with temp directory. Test `reset_habits_if_new_day()`.
  No live API calls, no LLM calls.

- `test_notifications.py` — Test `send_console_notification()`. Mock Windows toast import.

- `test_whatsapp.py` — Test `format_messages_for_context()` with mock data.
  Test GREEN-API payload parsing helper with sample JSON.

### Edge Cases

- Heartbeat skips gracefully when all integrations fail auth (empty data, no crash)
- Reflection skips if already ran today (unless `--force`)
- soul-protect.py blocks SOUL.md for any truthy `AGENT_INVOKED_BY` value
- `send_whatsapp_notification()` returns False gracefully if WHATSAPP_MY_NUMBER not set

---

## VALIDATION COMMANDS

### Level 1: Syntax (ast.parse — quick, no deps)

```powershell
uv run python -c "import ast; ast.parse(open('.claude/scripts/heartbeat.py').read())"
uv run python -c "import ast; ast.parse(open('.claude/scripts/memory_reflect.py').read())"
uv run python -c "import ast; ast.parse(open('.claude/scripts/notifications.py').read())"
uv run python -c "import ast; ast.parse(open('.claude/scripts/integrations/whatsapp.py').read())"
uv run python -c "import ast; ast.parse(open('.claude/hooks/soul-protect.py').read())"
```

### Level 1b: Style

```powershell
cd .claude/scripts
uv run ruff check . --fix
uv run ruff format .
```

### Level 2: Unit Tests

```powershell
cd .claude/scripts
uv run pytest tests/ -v
```

### Level 3: Integration Smoke Tests

```powershell
cd .claude/scripts

# Config
uv run python -c "from config import HEARTBEAT_STATE_FILE, WHATSAPP_MY_NUMBER, is_within_active_hours; print('config OK', is_within_active_hours())"

# shared.py
uv run python -c "from shared import load_state, save_state; print('shared OK')"

# WhatsApp integration module
uv run python -c "from integrations.whatsapp import send_message, get_greenapi_base; print('whatsapp OK')"

# WhatsApp CLI
uv run python integrations/query.py whatsapp --help

# Notifications
uv run python -c "from notifications import send_console_notification; send_console_notification('Test', 'OK')"

# Heartbeat dry run
uv run python heartbeat.py --dry-run

# Reflection dry run
uv run python memory_reflect.py --dry-run
```

### Level 4: soul-protect validation

```powershell
# Should BLOCK — automated process editing SOUL.md:
$env:AGENT_INVOKED_BY = "heartbeat"
echo '{"tool_input": {"file_path": "Memory/SOUL.md"}}' | uv run python .claude/hooks/soul-protect.py
# Expect: JSON with permissionDecision: deny
Remove-Item Env:\AGENT_INVOKED_BY

# Should ALLOW — automated process editing a non-SOUL file:
$env:AGENT_INVOKED_BY = "heartbeat"
echo '{"tool_input": {"file_path": "Memory/MEMORY.md"}}' | uv run python .claude/hooks/soul-protect.py
# Expect: exit 0, no deny output
Remove-Item Env:\AGENT_INVOKED_BY

# Should ALLOW — Shaun directly (no AGENT_INVOKED_BY set):
echo '{"tool_input": {"file_path": "Memory/SOUL.md"}}' | uv run python .claude/hooks/soul-protect.py
# Expect: exit 0, no deny output (Shaun can always edit SOUL.md manually)
```

### Level 5: Full Run (requires integrations + LLM credentials)

```powershell
uv run python .claude/scripts/heartbeat.py --force
uv run python .claude/scripts/memory_reflect.py --force
```

---

## ACCEPTANCE CRITERIA

- [ ] `heartbeat.py --dry-run` runs without errors, prints snapshot + diff
- [ ] `heartbeat.py --force` calls sdk_compat LLM and exits without error
- [ ] `memory_reflect.py --dry-run` lists log files that would be included
- [ ] `memory_reflect.py --force` calls LLM and updates MEMORY.md/USER.md
- [ ] `soul-protect.py` denies SOUL.md writes for ANY truthy `AGENT_INVOKED_BY` value
- [ ] `query.py whatsapp send --text "test"` sends successfully (if GREEN-API creds set)
- [ ] Windows Task Scheduler tasks created for heartbeat + reflection
- [ ] `uv run ruff check .` returns 0 errors
- [ ] All unit tests pass

---

## COMPLETION CHECKLIST

- [ ] All tasks completed in order (1 → 10)
- [ ] Each task validated immediately after implementation
- [ ] `uv run pytest tests/ -v` passes
- [ ] `uv run ruff check .` passes
- [ ] `heartbeat.py --dry-run` succeeds
- [ ] `memory_reflect.py --dry-run` succeeds
- [ ] soul-protect updated and validated
- [ ] .env updated with Phase 6 keys (not committed)
- [ ] GREEN-API account created, QR scanned (manual step)
- [ ] Windows Task Scheduler configured

---

## NOTES

**No guardrail LLM call**: Cole's PRD has a 5-stage pipeline with a separate guardrail LLM
call. We skip it. `sanitize.py` + `TRUST_BOUNDARY_INSTRUCTION` + heartbeat system prompt
constraints are sufficient for a single-owner setup. Halves token cost per run.

**Heartbeat outbound-only for WhatsApp**: The heartbeat SENDS WhatsApp notifications but
does NOT poll inbound messages. The Phase 7 bot owns inbound. GREEN-API's notification
queue is destructive (polling dequeues messages) — mixing heartbeat polling with the Phase 7
bot's listener would cause missed messages.

**HEARTBEAT_INTERVAL_MINUTES typo tolerance**: `.env` has `HEARTBEART_INTERVAL_MINUTES=30`
(extra A). Config reads both spellings; prefer correct, fall back to typo variant.

**Late-day nudge**: Pass current local time in the heartbeat LLM prompt. The LLM decides
whether to include a habits check-in nudge in the WhatsApp notification. No hardcoded
time logic in Python.

**HABITS.md auto-detection scope**: Python only auto-checks the Shows pillar (calendar
event keyword match). All other pillars are self-report only. The LLM can suggest them
in its narrative output.

### Confidence Score: 9/10

Risks:
1. GREEN-API account needs manual setup (scan QR) before outbound send can be tested.
   All other tasks are pure Python with no external dependencies beyond existing Phase 4 auth.
2. sdk_compat LLM call in heartbeat/reflection needs real backend credentials to test
   `--force` mode. `--dry-run` can be validated without them.
