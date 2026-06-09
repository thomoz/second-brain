# Feature: Phase 4 — Integrations (Gmail Multi-Account + Google Calendar + Outlook)

The following plan should be complete, but validate codebase patterns and task sanity before
implementing. Pay special attention to import paths — integration files use `sys.path.insert`
to reach config.py from the parent scripts/ directory.

## Feature Description

Wire up three live data sources — 8 Gmail accounts, 6 Google Calendars, and 1 Outlook
account — so the heartbeat (Phase 6) has real data to work with. All integrations are
read-only at this phase. Each returns structured Python dataclasses; the LLM never sees
raw credentials.

## User Story

As Shaun's Second Brain,
I want to read email from 8 Gmail accounts, 6 Google Calendars, and 1 Outlook inbox,
So that the heartbeat can draft replies and surface insights across all of Shaun's businesses.

## Problem Statement

Cole's reference implementation has a single-account Gmail + single-calendar model.
Shaun has 8 Gmail accounts (separate Google identities, each needs its own OAuth token)
and 6 calendars. The current auth.py/gmail.py/calendar_api.py must be refactored for
multi-account, and Outlook/query.py/setup_auth.py must be created from scratch.

## Solution Statement

- `config.py`: add all missing constants (LOCAL_TZ alias, Google paths/scopes, multi-account
  Gmail dict, multi-calendar dict, Outlook constants).
- `auth.py`: parameterise by `account_name` to load per-account token files.
- `gmail.py`: accept `account_name` parameter; add `list_all_accounts()` helper.
- `calendar_api.py`: replace singular `GOOGLE_CALENDAR_ID` with `GOOGLE_CALENDAR_IDS` dict;
  add `get_all_calendars_events()`.
- `outlook.py`: new file — MSAL device code flow, Graph API mail read.
- `registry.py`: update to reflect multi-account Gmail and multi-calendar.
- `setup_auth.py`: new file — loops 8 Gmail accounts + Outlook device code flow.
- `query.py`: new unified CLI — gmail / calendar / outlook subcommands.
- `pyproject.toml`: new file — declares Phase 4 deps so `uv sync` works.

## Feature Metadata

**Feature Type**: New Capability  
**Estimated Complexity**: Medium-High  
**Primary Systems Affected**: config.py, auth.py, gmail.py, calendar_api.py, registry.py  
**Dependencies**: google-api-python-client, google-auth-oauthlib, msal, requests, python-dotenv

---

## CONTEXT REFERENCES

### Relevant Codebase Files — READ BEFORE IMPLEMENTING

- `.claude/scripts/config.py` (entire file) — current constants; needs LOCAL_TZ alias +
  all Google/Outlook/multi-account additions
- `.claude/scripts/integrations/auth.py` (entire file) — single-token Google OAuth; must be
  refactored to accept `account_name` parameter
- `.claude/scripts/integrations/gmail.py` (lines 1–60, 800–900) — service builder and CLI;
  `get_gmail_service()` must accept `account_name`
- `.claude/scripts/integrations/calendar_api.py` (entire file) — imports singular
  `GOOGLE_CALENDAR_ID`; must switch to `GOOGLE_CALENDAR_IDS` dict
- `.claude/scripts/integrations/registry.py` (entire file) — needs multi-account Gmail entries
  and Outlook entry added
- `.claude/scripts/sanitize.py` (entire file) — `sanitize_external_text()` used in all
  integrations; understand interface before touching integration files
- `.claude/scripts/shared.py` — `with_retry()` used in all API calls
- `.claude/scripts/tests/conftest.py` — test fixture patterns to follow
- `.claude/scripts/tests/test_sanitize.py` — test class/method naming pattern to mirror

### Reference Files (Cole's implementation — READ for patterns)

- `O:\AI\Dynamous\Courses\workshops\claude-code-second-brain\.claude\scripts\config.py`
  — lines 54–95: complete Google + Calendar constant pattern to adapt
- `O:\AI\Dynamous\Courses\workshops\claude-code-second-brain\.claude\scripts\setup_auth.py`
  — full file: structure to adapt (remove Asana/Slack; add Outlook; add multi-account Gmail)
- `O:\AI\Dynamous\Courses\workshops\claude-code-second-brain\.claude\skills\direct-integrations\scripts\query.py`
  — full file: CLI structure to adapt (keep gmail + calendar; add outlook; remove asana/slack/sheets/docs/circle/drive)
- `O:\AI\Dynamous\Courses\workshops\claude-code-second-brain\.claude\scripts\pyproject.toml`
  — dependency list for Phase 4 (google-api-python-client, google-auth-oauthlib, msal)

### New Files to Create

- `.claude/scripts/pyproject.toml` — project manifest for uv
- `.claude/scripts/integrations/outlook.py` — MSAL device code + Graph API mail reader
- `.claude/scripts/integrations/setup_auth.py` — one-time auth runner (Google × 8 + Outlook)
- `.claude/scripts/integrations/query.py` — unified CLI (gmail / calendar / outlook)
- `.claude/scripts/tests/test_integrations.py` — smoke tests for multi-account helpers

### Relevant Documentation

- Google Gmail API Python quickstart: https://developers.google.com/gmail/api/quickstart/python
  — shows `InstalledAppFlow` pattern (already implemented in auth.py — reference only)
- Google Calendar API: https://developers.google.com/calendar/api/v3/reference/events/list
  — `calendarId` parameter accepts any calendar ID string
- MSAL Python device code flow: https://msal-python.readthedocs.io/en/latest/#msal.PublicClientApplication.initiate_device_flow
  — `initiate_device_flow` + `acquire_token_by_device_flow`; token cached via `SerializableTokenCache`
- Microsoft Graph Mail API: https://learn.microsoft.com/en-us/graph/api/user-list-messages
  — `GET /me/messages` with `$filter=isRead eq false`

### Patterns to Follow

**Import pattern** (all integration files):
```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import LOCAL_TZ, now_local          # noqa: E402
from sanitize import sanitize_external_text     # noqa: E402
from shared import with_retry                   # noqa: E402
```

**Dataclass pattern** (all integration files):
```python
@dataclass
class OutlookMessage:
    id: str
    subject: str
    sender: str
    sender_email: str
    date: datetime
    snippet: str
    is_unread: bool
    thread_id: str
```

**with_retry pattern**:
```python
result = with_retry(
    lambda: service.users().messages().list(userId="me", ...).execute()
)
```

**format_for_context pattern** — always sanitize, always respect max_chars budget:
```python
def format_X_for_context(items: list[X], max_chars: int = 2000) -> str:
    if not items:
        return "No items found."
    output: list[str] = []
    chars = 0
    for item in items:
        entry = f"- **{sanitize_external_text(item.subject, 'source')}** ..."
        if chars + len(entry) > max_chars:
            output.append(f"\n... and {len(items) - len(output)} more")
            break
        output.append(entry)
        chars += len(entry)
    return "\n\n".join(output)
```

**Test pattern** (mirror test_sanitize.py):
```python
class TestGmailMultiAccount:
    def test_something(self) -> None:
        assert ...
```

---

## KEY DESIGN DECISIONS

### Multi-Account Gmail
Each of 8 Gmail accounts is a separate Google identity — each needs its own OAuth token
file. One shared `google_credentials.json` (the app's client ID) is fine for all accounts.

Token file naming convention: `token_gmail_{account_name}.json`
e.g. `token_gmail_personal.json`, `token_gmail_sbdb.json`

`auth.py` gains `account_name: str` parameter throughout. Default remains `"personal"`.

### Multi-Calendar
All 6 calendars are accessed via a single Google OAuth token (the personal account token).
The non-personal calendars (BGK, bingo, trivia, dogdaycare, HME) must be shared with
`shaunthommo10@gmail.com` in Google Calendar settings for single-token access to work.

**IMPORTANT**: Document this sharing requirement in setup_auth.py output — it's a
manual step the user must complete before calendar queries will work for non-personal
calendars.

`GOOGLE_CALENDAR_IDS` is a dict: `{"personal": "...", "bgk": "...", ...}` from env vars.
`calendar_api.py` gains `get_all_calendars_events()` that loops all IDs.

### Outlook Token Storage
Token stored at `.claude/scripts/integrations/outlook_token.json`.
MSAL `SerializableTokenCache` persists across runs automatically.
`OUTLOOK_TENANT_ID=consumers` — correct for personal Microsoft accounts.

### No WhatsApp
Skipped entirely per user decision. Do not add `whatsapp.py` or registry entry.

### No Show-Day Reminders
`calendar_api.py` does NOT add `is_show_day` detection — calendar is context-only.
Remove `SHOW_KEYWORDS` and `is_show_event()` if they exist.

### query.py Location
Lives at `.claude/scripts/integrations/query.py` (not in skills/).
CLAUDE.md build commands reference this path.

---

## IMPLEMENTATION PLAN

### Phase 1: Foundation — config.py + deps

Update `config.py` with all missing constants and create `pyproject.toml`.
Nothing else can be imported or tested until config.py is correct.

### Phase 2: Auth Layer — auth.py multi-account

Refactor `auth.py` to be account-name-aware. All downstream files depend on this.

### Phase 3: Core Integrations — gmail.py, calendar_api.py, outlook.py

Update Gmail and Calendar for multi-account/multi-calendar. Create Outlook.

### Phase 4: Supporting Files — registry.py, setup_auth.py, query.py

Update registry; create the auth setup runner and the unified CLI.

### Phase 5: Tests + Validation

Add smoke tests; run setup_auth.py to authenticate all accounts; validate CLI.

---

## STEP-BY-STEP TASKS

### Task 0: INSTALL missing dependencies (run BEFORE any code changes)

Pre-execution environment check revealed:
- `google-api-python-client` — NOT installed (breaks all Gmail/Calendar imports)
- `msal` — NOT installed (breaks Outlook)
- `pytest` — NOT installed (breaks test validation)
- `google-auth`, `google-auth-oauthlib`, `requests` — already installed ✓
- `auth.py` already has a hard ImportError (missing config constants) — confirmed by import test

**ALSO**: `auth.py` currently has `ImportError: cannot import name 'GOOGLE_CREDENTIALS_FILE'
from 'config'` — this means Tasks 3+ validations will fail until Task 2 (config.py) is done.
Task ordering in this plan already accounts for this — do NOT skip ahead.

**ALSO**: Hook CWD bug — if Bash `cd` commands change the working directory to `.claude/scripts`,
the soul-protect PreToolUse hook will crash with a path error. Always `cd` back to the project
root before running Edit/Write tools. Fix settings.json hook paths to absolute to prevent recurrence.

Install missing packages first so each Task's VALIDATE command can run immediately after:

```powershell
cd O:\AI\Dynamous\Courses\second-brain-workshop
pip install google-api-python-client msal pytest
```

- **VALIDATE**:
  ```powershell
  python -c "import googleapiclient; import msal; import pytest; print('All Phase 4 deps OK')"
  ```
  Expected: `All Phase 4 deps OK`

---

### Task 1: CREATE `.claude/scripts/pyproject.toml`

- **IMPLEMENT**: Project manifest declaring all Phase 1–4 deps so `uv sync` installs them
- **MIRROR**: `O:\AI\Dynamous\Courses\workshops\claude-code-second-brain\.claude\scripts\pyproject.toml`
- **CONTENT**: Adapt Cole's pyproject.toml — keep all Phase 1–3 deps; replace `claude-agent-sdk`
  with `pi-sdk-compat` shim reference; add `msal>=1.28.0` and `requests>=2.31.0` for Outlook;
  remove `asana`, `slack-sdk`, `slack-bolt` (not used); keep `win10toast-click` for Phase 6
- **GOTCHA**: The project already has a `uv.lock` but no `pyproject.toml` — uv needs the
  manifest to resolve and sync. Do not delete uv.lock.
- **VALIDATE**: `cd .claude\scripts && uv sync --no-dev`
  Expected: packages resolve without errors

```toml
[project]
name = "second-brain"
version = "0.1.0"
description = "Shaun Thomson's Second Brain"
requires-python = ">=3.12"
dependencies = [
    "python-dotenv>=1.0.0",
    "tzdata>=2024.1",
    # Phase 3: Memory Search
    "fastembed>=0.4.0",
    "sqlite-vec>=0.1.6",
    "numpy>=1.26.0",
    "psycopg[binary]>=3.1.0",
    "pgvector>=0.3.0",
    # Phase 4: Integrations
    "google-api-python-client>=2.100.0",
    "google-auth-oauthlib>=1.2.0",
    "google-auth-httplib2>=0.2.0",
    "msal>=1.28.0",
    "requests>=2.31.0",
    # Phase 6: Notifications (Windows)
    "win10toast-click>=0.1.2; sys_platform == 'win32'",
]

[project.optional-dependencies]
dev = [
    "mypy>=1.8.0",
    "ruff>=0.2.0",
    "pytest>=8.0.0",
]

[tool.ruff]
target-version = "py312"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP"]

[tool.mypy]
python_version = "3.12"
strict = true
```

---

### Task 2: UPDATE `.claude/scripts/config.py`

- **IMPLEMENT**: Add all missing Phase 4 constants to the existing file
- **PATTERN**: Cole's config.py lines 52–95, 141 for constant names and structure
- **GOTCHA**: The existing config.py has `TZ = zoneinfo.ZoneInfo("Australia/Sydney")` but
  integration files import `LOCAL_TZ`. Add `LOCAL_TZ = TZ` alias — do NOT remove `TZ`.
- **GOTCHA**: The existing `load_dotenv()` call has no path argument — it finds `.env` via
  default search (CWD). Cole's version uses explicit path. Change to explicit:
  `load_dotenv(Path(__file__).parent / ".env")` to match expected `.claude/scripts/.env` location.
- **ADD** these constants after the existing Phase 3 section:

```python
# ---------------------------------------------------------------------------
# Phase 4: Integrations
# ---------------------------------------------------------------------------

# LOCAL_TZ alias — integration files import LOCAL_TZ; TZ is the canonical name
LOCAL_TZ = TZ

# Integration directory — absolute path derived from __file__ so CWD doesn't matter
INTEGRATIONS_DIR = Path(__file__).resolve().parent / "integrations"

# Google OAuth — shared credentials file, per-account token files
GOOGLE_CREDENTIALS_FILE = INTEGRATIONS_DIR / "google_credentials.json"
GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/calendar.readonly",
]

def google_token_file(account_name: str) -> Path:
    """Return path to per-account Gmail token file."""
    return INTEGRATIONS_DIR / f"token_gmail_{account_name}.json"

# Gmail accounts — populated from GMAIL_ACCOUNT_* env vars
# Maps account_name → email address (for display/logging only; auth uses token file)
GMAIL_ACCOUNTS: dict[str, str] = {}
for _key, _val in _os.environ.items():
    if _key.startswith("GMAIL_ACCOUNT_") and _val:
        _acct = _key[len("GMAIL_ACCOUNT_"):].lower()
        GMAIL_ACCOUNTS[_acct] = _val

# Google Calendar IDs — populated from GOOGLE_CALENDAR_ID_* env vars
# Maps calendar_name → calendar_id
GOOGLE_CALENDAR_IDS: dict[str, str] = {}
for _key, _val in _os.environ.items():
    if _key.startswith("GOOGLE_CALENDAR_ID_") and _val:
        _cal = _key[len("GOOGLE_CALENDAR_ID_"):].lower()
        GOOGLE_CALENDAR_IDS[_cal] = _val

# Outlook (Microsoft Graph)
OUTLOOK_CLIENT_ID = _os.getenv("OUTLOOK_CLIENT_ID", "")
OUTLOOK_TENANT_ID = _os.getenv("OUTLOOK_TENANT_ID", "consumers")
OUTLOOK_TOKEN_FILE = INTEGRATIONS_DIR / "outlook_token.json"
OUTLOOK_SCOPES = ["Mail.Read"]
```

- **VALIDATE**: 
  ```
  cd .claude\scripts && python -c "from config import LOCAL_TZ, GOOGLE_CREDENTIALS_FILE, GOOGLE_CALENDAR_IDS, GMAIL_ACCOUNTS, OUTLOOK_CLIENT_ID; print('Gmail accounts:', list(GMAIL_ACCOUNTS.keys())); print('Calendars:', list(GOOGLE_CALENDAR_IDS.keys()))"
  ```
  Expected: 8 Gmail account names, 6 calendar names

---

### Task 3: UPDATE `.claude/scripts/integrations/auth.py`

- **IMPLEMENT**: Add `account_name: str` param to all three functions; derive token file
  path from `google_token_file(account_name)` in config
- **PATTERN**: Existing auth.py structure — keep all logic, only change token file resolution
- **IMPORTS**: Add `from config import ..., google_token_file` to imports
- **CHANGE** `get_google_credentials()` → `get_google_credentials(account_name: str = "personal")`
  - Replace `GOOGLE_TOKEN_FILE` reference with `google_token_file(account_name)`
- **CHANGE** `run_initial_auth()` → `run_initial_auth(account_name: str = "personal", headless: bool = False)`
  - Replace `GOOGLE_TOKEN_FILE` reference with `google_token_file(account_name)`
  - Print which account is being authenticated: `f"Authenticating account: {account_name}"`
- **CHANGE** `is_google_authenticated()` → `is_google_authenticated(account_name: str = "personal")`
  - Replace `GOOGLE_TOKEN_FILE` reference with `google_token_file(account_name)`
- **GOTCHA**: The `GOOGLE_TOKEN_FILE` constant no longer exists in config — remove its import
- **VALIDATE**:
  ```
  cd .claude\scripts && python -c "from integrations.auth import is_google_authenticated; print(is_google_authenticated('personal'))"
  ```
  Expected: `False` (no token yet — that's correct before setup_auth runs)

---

### Task 4: UPDATE `.claude/scripts/integrations/gmail.py`

- **IMPLEMENT**: Add `account_name: str = "personal"` to `get_gmail_service()` and all
  functions that call it; add `list_all_accounts()` top-level function
- **CHANGE** `get_gmail_service()` → `get_gmail_service(account_name: str = "personal")`
  - Pass `account_name` to `get_google_credentials(account_name)`
- **CHANGE** `list_emails()`, `get_unread_count()`, `check_for_urgent_emails()`,
  `get_important_unreplied_emails()` — each gains `account_name: str = "personal"` param
  and passes it to `get_gmail_service(account_name)`
- **ADD** after existing functions:

```python
def list_all_accounts(
    account_names: list[str] | None = None,
    max_per_account: int = 10,
    unread_only: bool = True,
    hours_ago: int | None = 4,
) -> list[Email]:
    """Query all configured Gmail accounts and return merged, sorted results."""
    from config import GMAIL_ACCOUNTS
    accounts = account_names or list(GMAIL_ACCOUNTS.keys())
    all_emails: list[Email] = []
    for acct in accounts:
        if not is_google_authenticated(acct):
            continue
        try:
            emails = list_emails(
                max_results=max_per_account,
                unread_only=unread_only,
                hours_ago=hours_ago,
                account_name=acct,
            )
            # Tag each email with which account it came from
            for e in emails:
                e.snippet = f"[{acct}] {e.snippet}"
            all_emails.extend(emails)
        except Exception as ex:
            print(f"Warning: failed to query account {acct}: {ex}")
    return sorted(all_emails, key=lambda e: e.date, reverse=True)
```

- **GOTCHA**: The existing `LOCAL_TZ` import from config will work once Task 2 is done.
  No change needed to that import line.
- **VALIDATE**:
  ```
  cd .claude\scripts && python -c "from integrations.gmail import list_all_accounts; print('list_all_accounts import OK')"
  ```

---

### Task 5: UPDATE `.claude/scripts/integrations/calendar_api.py`

- **IMPLEMENT**: Replace `GOOGLE_CALENDAR_ID` (singular) import with `GOOGLE_CALENDAR_IDS`
  (dict); add `get_all_calendars_events()` function; remove show-day detection
- **CHANGE** import line:
  ```python
  # BEFORE:
  from config import LOCAL_TZ, GOOGLE_CALENDAR_ID
  # AFTER:
  from config import LOCAL_TZ, GOOGLE_CALENDAR_IDS
  ```
- **CHANGE** `get_upcoming_events()` default calendar:
  ```python
  # BEFORE: cal_id = calendar_id or GOOGLE_CALENDAR_ID
  # AFTER:
  cal_id = calendar_id or next(iter(GOOGLE_CALENDAR_IDS.values()), "primary")
  ```
- **ADD** new function after `check_for_upcoming_meetings()`:

```python
def get_all_calendars_events(
    hours_ahead: int = 24,
    max_per_calendar: int = 10,
) -> dict[str, list[CalendarEvent]]:
    """Query all configured calendars. Returns dict of cal_name → events.
    
    NOTE: Non-personal calendars must be shared with the authenticated Google
    account (shaunthommo10@gmail.com) in Google Calendar settings for access to work.
    Calendars that return an error are silently skipped with a warning.
    """
    results: dict[str, list[CalendarEvent]] = {}
    for cal_name, cal_id in GOOGLE_CALENDAR_IDS.items():
        try:
            events = get_upcoming_events(
                hours_ahead=hours_ahead,
                calendar_id=cal_id,
                max_results=max_per_calendar,
            )
            results[cal_name] = events
        except Exception as ex:
            print(f"Warning: calendar '{cal_name}' ({cal_id}) inaccessible: {ex}")
            results[cal_name] = []
    return results


def format_all_calendars_for_context(
    calendar_events: dict[str, list[CalendarEvent]]
) -> str:
    """Format multi-calendar results for context injection."""
    if not calendar_events:
        return "No calendar data."
    sections: list[str] = []
    for cal_name, events in calendar_events.items():
        header = f"### Calendar: {cal_name}"
        body = format_events_for_context(events) if events else "No upcoming events."
        sections.append(f"{header}\n{body}")
    return "\n\n".join(sections)
```

- **VALIDATE**:
  ```
  cd .claude\scripts && python -c "from integrations.calendar_api import get_all_calendars_events; print('calendar multi-account import OK')"
  ```

---

### Task 6: CREATE `.claude/scripts/integrations/outlook.py`

- **IMPLEMENT**: MSAL device code flow + Microsoft Graph mail reader
- **PATTERN**: PRD Phase 4 Outlook section; integration_template.py for dataclass/format pattern
- **IMPORTS**: `msal`, `requests`, `json`, `os`, `Path`; config: `OUTLOOK_CLIENT_ID`, `OUTLOOK_TENANT_ID`, `OUTLOOK_TOKEN_FILE`, `OUTLOOK_SCOPES`, `LOCAL_TZ`, `now_local`

```python
"""
Outlook/Microsoft 365 integration for Second Brain.

Read-only access to Outlook inbox via Microsoft Graph API.
Uses MSAL device code flow (no browser required on first run).

Usage:
    uv run python -m integrations.outlook list --max 5
    uv run python -m integrations.outlook unread
    uv run python -m integrations.outlook auth
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import (          # noqa: E402
    LOCAL_TZ, now_local,
    OUTLOOK_CLIENT_ID, OUTLOOK_TENANT_ID,
    OUTLOOK_TOKEN_FILE, OUTLOOK_SCOPES,
)
from sanitize import sanitize_external_text  # noqa: E402
from shared import with_retry                # noqa: E402

GRAPH_BASE = "https://graph.microsoft.com/v1.0"


@dataclass
class OutlookMessage:
    id: str
    subject: str
    sender: str
    sender_email: str
    date: datetime
    snippet: str
    is_unread: bool
    thread_id: str
    labels: list[str] = field(default_factory=list)


def _get_token_cache() -> msal.SerializableTokenCache:
    import msal
    cache = msal.SerializableTokenCache()
    if OUTLOOK_TOKEN_FILE.exists():
        cache.deserialize(OUTLOOK_TOKEN_FILE.read_text(encoding="utf-8"))
    return cache


def _save_token_cache(cache: Any) -> None:
    if cache.has_state_changed:
        OUTLOOK_TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
        OUTLOOK_TOKEN_FILE.write_text(cache.serialize(), encoding="utf-8")


def get_access_token() -> str:
    """Acquire Outlook access token. Uses cached token if valid; device code flow otherwise."""
    import msal

    if not OUTLOOK_CLIENT_ID:
        raise RuntimeError(
            "OUTLOOK_CLIENT_ID not set in .env\n"
            "Add: OUTLOOK_CLIENT_ID=<your-azure-app-client-id>"
        )

    cache = _get_token_cache()
    app = msal.PublicClientApplication(
        OUTLOOK_CLIENT_ID,
        authority=f"https://login.microsoftonline.com/{OUTLOOK_TENANT_ID}",
        token_cache=cache,
    )

    # Try silent token refresh first
    accounts = app.get_accounts()
    if accounts:
        result = app.acquire_token_silent(OUTLOOK_SCOPES, account=accounts[0])
        if result and "access_token" in result:
            _save_token_cache(cache)
            return result["access_token"]

    # Device code flow (interactive — only runs when no cached token)
    flow = app.initiate_device_flow(scopes=OUTLOOK_SCOPES)
    if "user_code" not in flow:
        raise RuntimeError(f"Device flow failed: {flow.get('error_description', 'unknown')}")

    print("\n" + "=" * 60)
    print("  OUTLOOK AUTHENTICATION")
    print("=" * 60)
    print(f"\n{flow['message']}\n")

    result = app.acquire_token_by_device_flow(flow)
    if "access_token" not in result:
        raise RuntimeError(f"Outlook auth failed: {result.get('error_description', result)}")

    _save_token_cache(cache)
    return result["access_token"]


def is_outlook_authenticated() -> bool:
    """Check if a valid Outlook token exists without triggering auth flow."""
    if not OUTLOOK_TOKEN_FILE.exists():
        return False
    try:
        import msal
        cache = _get_token_cache()
        app = msal.PublicClientApplication(
            OUTLOOK_CLIENT_ID,
            authority=f"https://login.microsoftonline.com/{OUTLOOK_TENANT_ID}",
            token_cache=cache,
        )
        accounts = app.get_accounts()
        return bool(accounts)
    except Exception:
        return False


def _parse_outlook_message(msg: dict[str, Any]) -> OutlookMessage:
    """Parse a Graph API message dict into OutlookMessage."""
    sender_info = msg.get("from", {}).get("emailAddress", {})
    received = msg.get("receivedDateTime", "")
    try:
        date = datetime.fromisoformat(received.replace("Z", "+00:00"))
    except Exception:
        date = now_local()

    return OutlookMessage(
        id=msg.get("id", ""),
        subject=msg.get("subject", "(no subject)"),
        sender=sender_info.get("name", ""),
        sender_email=sender_info.get("address", ""),
        date=date,
        snippet=msg.get("bodyPreview", "")[:200],
        is_unread=not msg.get("isRead", True),
        thread_id=msg.get("conversationId", ""),
    )


def list_messages(
    max_results: int = 15,
    unread_only: bool = False,
    hours_ago: int | None = None,
) -> list[OutlookMessage]:
    """List Outlook messages, optionally filtered."""
    token = get_access_token()
    headers = {"Authorization": f"Bearer {token}"}

    filters: list[str] = []
    if unread_only:
        filters.append("isRead eq false")
    if hours_ago:
        from datetime import timedelta, timezone
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours_ago)
        filters.append(f"receivedDateTime ge {cutoff.strftime('%Y-%m-%dT%H:%M:%SZ')}")

    params: dict[str, Any] = {
        "$top": max_results,
        "$select": "id,subject,from,receivedDateTime,bodyPreview,isRead,conversationId",
        "$orderby": "receivedDateTime desc",
    }
    if filters:
        params["$filter"] = " and ".join(filters)

    result: dict[str, Any] = with_retry(
        lambda: __import__("requests").get(
            f"{GRAPH_BASE}/me/messages",
            headers=headers,
            params=params,
        ).json()
    )

    return [_parse_outlook_message(m) for m in result.get("value", [])]


def get_unread_count() -> int:
    """Get count of unread messages in Outlook inbox."""
    token = get_access_token()
    headers = {"Authorization": f"Bearer {token}"}
    result: dict[str, Any] = with_retry(
        lambda: __import__("requests").get(
            f"{GRAPH_BASE}/me/mailFolders/inbox",
            headers=headers,
            params={"$select": "unreadItemCount"},
        ).json()
    )
    return int(result.get("unreadItemCount", 0))


def format_messages_for_context(messages: list[OutlookMessage], max_chars: int = 2000) -> str:
    """Format Outlook messages for context injection."""
    if not messages:
        return "No Outlook messages found."
    output: list[str] = []
    chars = 0
    for msg in messages:
        date_local = msg.date.astimezone(LOCAL_TZ) if msg.date.tzinfo else msg.date
        subject = sanitize_external_text(msg.subject, "outlook")
        sender = sanitize_external_text(msg.sender, "outlook")
        snippet = sanitize_external_text(msg.snippet[:100], "outlook")
        entry = (
            f"- **{subject}** [thread_id: {msg.thread_id}]\n"
            f"  From: {sender} <{msg.sender_email}>\n"
            f"  Date: {date_local.strftime('%Y-%m-%d %H:%M')}\n"
            f"  {'[UNREAD] ' if msg.is_unread else ''}{snippet}"
        )
        if chars + len(entry) > max_chars:
            output.append(f"\n... and {len(messages) - len(output)} more")
            break
        output.append(entry)
        chars += len(entry)
    return "\n\n".join(output)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Outlook integration")
    parser.add_argument("command", choices=["auth", "list", "unread"])
    parser.add_argument("--max", type=int, default=10)
    parser.add_argument("--hours", type=int, default=None)
    args = parser.parse_args()

    if args.command == "auth":
        get_access_token()
        print("Outlook authentication successful!")
    elif args.command == "list":
        msgs = list_messages(max_results=args.max, hours_ago=args.hours)
        print(format_messages_for_context(msgs))
    elif args.command == "unread":
        print(f"Unread Outlook messages: {get_unread_count()}")
```

- **GOTCHA**: `_get_token_cache()` uses `msal` inside the function body — import it locally
  to avoid top-level import failure when msal is not yet installed
- **GOTCHA**: `with_retry` wraps a `requests.get()` — use `__import__("requests")` inside
  the lambda, or import requests at the top of the module (preferred — add to imports)
- **VALIDATE**:
  ```
  cd .claude\scripts && python -c "from integrations.outlook import is_outlook_authenticated; print('Outlook import OK:', is_outlook_authenticated())"
  ```

---

### Task 7: UPDATE `.claude/scripts/integrations/registry.py`

- **IMPLEMENT**: Replace single "gmail" entry with multi-account awareness; add "outlook" entry;
  update "calendar" to reflect multi-calendar config
- **CHANGE** `_has_google_token()`:

```python
def _has_google_token(account_name: str = "personal") -> bool:
    """Check if Google OAuth token file exists for the given account."""
    from config import google_token_file
    return google_token_file(account_name).exists()
```

- **CHANGE** `get_enabled()` Gmail check:
  Uses `_has_google_token("personal")` as the primary gate (if personal account is authed,
  Gmail integration is considered enabled; individual account availability checked at runtime)

- **ADD** "outlook" to `_REGISTRY`:
```python
"outlook": IntegrationInfo(
    name="outlook",
    display_name="Outlook",
    auth_type="token",
    required_config=["OUTLOOK_CLIENT_ID"],
    module_path="integrations.outlook",
),
```

- **VALIDATE**:
  ```
  cd .claude\scripts && python -c "from integrations.registry import get_all; print(list(get_all().keys()))"
  ```
  Expected: includes "gmail", "calendar", "outlook"

---

### Task 8: CREATE `.claude/scripts/integrations/setup_auth.py`

- **IMPLEMENT**: One-time interactive auth runner adapted from Cole's setup_auth.py
- **PATTERN**: `O:\AI\Dynamous\Courses\workshops\claude-code-second-brain\.claude\scripts\setup_auth.py`
  — keep `print_header()`, `print_status()`, `main()` structure exactly
- **REMOVE**: Asana, Slack, Circle sections from Cole's version
- **ADAPT** Google section to loop all 8 Gmail accounts:

```python
def check_google(check_only: bool = False, headless: bool = False) -> bool:
    """Authenticate all 8 Gmail accounts + validate Calendar access."""
    from config import GMAIL_ACCOUNTS, GOOGLE_CALENDAR_IDS, GOOGLE_CREDENTIALS_FILE
    from integrations.auth import is_google_authenticated, run_initial_auth

    print_header("Google OAuth — Gmail (8 accounts) + Calendar (6 calendars)")

    if not GOOGLE_CREDENTIALS_FILE.exists():
        print(f"  Missing: {GOOGLE_CREDENTIALS_FILE}")
        print("  Download from Google Cloud Console → Credentials → OAuth client ID → Desktop app")
        return False

    # Print calendar sharing notice
    print("  NOTE: Non-personal calendars must be shared with shaunthommo10@gmail.com")
    print("  in Google Calendar settings for multi-calendar access to work.")
    print(f"  Calendars to configure: {', '.join(GOOGLE_CALENDAR_IDS.keys())}\n")

    all_ok = True
    for account_name, email in GMAIL_ACCOUNTS.items():
        if is_google_authenticated(account_name):
            print_status(f"Gmail [{account_name}]", True, email)
            continue
        if check_only:
            print_status(f"Gmail [{account_name}]", False, f"{email} — not authenticated")
            all_ok = False
            continue
        print(f"\n  Authenticating {account_name} ({email})...")
        try:
            run_initial_auth(account_name=account_name, headless=headless)
            print_status(f"Gmail [{account_name}]", True, email)
        except Exception as e:
            print_status(f"Gmail [{account_name}]", False, str(e))
            all_ok = False

    return all_ok
```

- **ADD** Outlook section:

```python
def check_outlook(check_only: bool = False) -> bool:
    """Authenticate Outlook via MSAL device code flow."""
    from config import OUTLOOK_CLIENT_ID
    from integrations.outlook import get_access_token, is_outlook_authenticated

    print_header("Outlook (Microsoft Graph — Device Code Flow)")

    if not OUTLOOK_CLIENT_ID:
        print_status("Outlook", False, "OUTLOOK_CLIENT_ID not set in .env")
        return False

    if is_outlook_authenticated():
        print_status("Outlook", True, "Token exists and is valid/refreshable")
        return True

    if check_only:
        print_status("Outlook", False, "Not authenticated — run without --check")
        return False

    try:
        get_access_token()  # Triggers device code flow
        print_status("Outlook", True, "Authenticated successfully")
        return True
    except Exception as e:
        print_status("Outlook", False, str(e))
        return False
```

- **VALIDATE**:
  ```
  cd .claude\scripts && python integrations\setup_auth.py --check
  ```
  Expected: shows status for all 8 Gmail accounts + Outlook (all unauthenticated at this point)

---

### Task 9: CREATE `.claude/scripts/integrations/query.py`

- **IMPLEMENT**: Unified CLI for gmail / calendar / outlook — adapted from Cole's query.py
- **PATTERN**: Cole's `query.py` main structure (subparsers, cmd_* functions, try/except in main)
- **REMOVE**: asana, slack, sheets, docs, circle, drive subcommands entirely
- **ADAPT** `cmd_gmail()`:
  - Add `--account` flag: `gmail_parser.add_argument("--account", default=None)`
  - When `--account` is provided, query that account only
  - When not provided (default), call `list_all_accounts()` for list/urgent actions
  - Import `list_all_accounts` alongside existing imports
- **ADAPT** `cmd_calendar()`:
  - Add `--calendar` flag: `cal_parser.add_argument("--calendar", default=None)`
  - "all" action: calls `get_all_calendars_events()` and `format_all_calendars_for_context()`
  - Single calendar: passes `calendar_id=GOOGLE_CALENDAR_IDS[args.calendar]`
- **ADD** `cmd_outlook()`:

```python
def cmd_outlook(args: argparse.Namespace) -> None:
    from integrations.outlook import (
        format_messages_for_context, get_unread_count, list_messages,
    )
    if args.action == "list":
        msgs = list_messages(max_results=args.max, hours_ago=args.hours)
        print(format_messages_for_context(msgs))
    elif args.action == "unread":
        print(f"Unread Outlook messages: {get_unread_count()}")
    elif args.action == "urgent":
        msgs = list_messages(max_results=20, unread_only=True, hours_ago=args.hours or 2)
        print(format_messages_for_context(msgs))
```

- **VALIDATE**:
  ```
  cd .claude\scripts && python integrations\query.py --help
  ```
  Expected: shows gmail, calendar, outlook subcommands

---

### Task 10: AUTHENTICATE — Run setup_auth.py for all accounts

This is an interactive human step, not automated. Document the commands.

```powershell
cd O:\AI\Dynamous\Courses\second-brain-workshop\.claude\scripts

# Authenticate all 8 Gmail accounts (opens browser 8 times)
uv run python integrations\setup_auth.py

# Or authenticate one account at a time:
uv run python -c "
import sys; sys.path.insert(0,'.')
from integrations.auth import run_initial_auth
run_initial_auth('personal')    # shaunthommo10@gmail.com
"
```

Repeat `run_initial_auth('<account_name>')` for each of:
`personal`, `sbdb`, `karaoke`, `hosting`, `bingo`, `trivia`, `finntwist`, `hooklust`

Then run Outlook auth:
```powershell
uv run python integrations\setup_auth.py  # triggers device code flow for Outlook
```

**GOTCHA**: Each Gmail auth opens a browser window. Sign in as the correct Google account
for each flow (the browser may auto-fill the wrong account — check before authorizing).

**CALENDAR SHARING STEP** (manual — cannot be automated):
For each non-personal calendar, share it with `shaunthommo10@gmail.com`:
- BGK: Sign into `info@billygoatkaraoke.com.au` → Google Calendar → Settings → 
  Share with specific people → add `shaunthommo10@gmail.com` → "See all event details"
- Repeat for bingo, trivia, dogdaycare, HME calendars

---

### Task 11: ADD `.claude/scripts/tests/test_integrations.py`

- **IMPLEMENT**: Smoke tests for multi-account config loading and format functions
- **PATTERN**: `test_sanitize.py` — class-per-feature, one assert per test method
- **SCOPE**: Unit tests only — no live API calls; mock the service layer

```python
"""Smoke tests for Phase 4 integration helpers."""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class TestConfigMultiAccount:
    def test_gmail_accounts_loaded(self) -> None:
        from config import GMAIL_ACCOUNTS
        assert len(GMAIL_ACCOUNTS) == 8

    def test_calendar_ids_loaded(self) -> None:
        from config import GOOGLE_CALENDAR_IDS
        assert len(GOOGLE_CALENDAR_IDS) == 6

    def test_local_tz_alias(self) -> None:
        from config import LOCAL_TZ, TZ
        assert LOCAL_TZ is TZ

    def test_google_token_file_per_account(self) -> None:
        from config import google_token_file
        path = google_token_file("personal")
        assert "token_gmail_personal.json" in str(path)

    def test_outlook_constants_present(self) -> None:
        from config import OUTLOOK_CLIENT_ID, OUTLOOK_TENANT_ID
        assert OUTLOOK_CLIENT_ID  # non-empty
        assert OUTLOOK_TENANT_ID == "consumers"


class TestGmailFormatting:
    def test_format_empty(self) -> None:
        from integrations.gmail import format_emails_for_context
        assert format_emails_for_context([]) == "No emails found."


class TestCalendarFormatting:
    def test_format_empty_dict(self) -> None:
        from integrations.calendar_api import format_all_calendars_for_context
        result = format_all_calendars_for_context({})
        assert "No calendar data" in result

    def test_format_empty_calendar(self) -> None:
        from integrations.calendar_api import format_all_calendars_for_context
        result = format_all_calendars_for_context({"personal": []})
        assert "personal" in result
        assert "No upcoming events" in result


class TestOutlookFormatting:
    def test_format_empty(self) -> None:
        from integrations.outlook import format_messages_for_context
        assert format_messages_for_context([]) == "No Outlook messages found."
```

- **VALIDATE**: `cd .claude\scripts && uv run pytest tests\test_integrations.py -v`

---

## VALIDATION COMMANDS

### Level 1: Config correctness
```powershell
cd O:\AI\Dynamous\Courses\second-brain-workshop\.claude\scripts
python -c "from config import LOCAL_TZ, GMAIL_ACCOUNTS, GOOGLE_CALENDAR_IDS, GOOGLE_CREDENTIALS_FILE, GOOGLE_SCOPES, OUTLOOK_CLIENT_ID, OUTLOOK_TENANT_ID; print('Gmail:', list(GMAIL_ACCOUNTS.keys())); print('Calendars:', list(GOOGLE_CALENDAR_IDS.keys())); print('Creds file exists:', GOOGLE_CREDENTIALS_FILE.exists())"
```
Expected: 8 Gmail account names, 6 calendar names, creds file: True

### Level 2: Import validation (all integrations)
```powershell
python -c "from integrations.gmail import list_all_accounts; from integrations.calendar_api import get_all_calendars_events; from integrations.outlook import is_outlook_authenticated; from integrations.registry import get_all; print('All imports OK'); print('Registry:', list(get_all().keys()))"
```

### Level 3: Unit tests
```powershell
uv run pytest tests\test_integrations.py tests\test_sanitize.py -v
```

### Level 4: Auth status check
```powershell
python integrations\setup_auth.py --check
```
Expected: lists all 8 Gmail accounts + Outlook with auth status

### Level 5: Live integration test (after auth)
```powershell
# Gmail — single account
python integrations\query.py gmail list --account personal --max 3

# Gmail — all accounts  
python integrations\query.py gmail list --max 3

# Calendar — all calendars
python integrations\query.py calendar all

# Calendar — single
python integrations\query.py calendar today --calendar personal

# Outlook
python integrations\query.py outlook list --max 3
```

### Level 6: Update CLAUDE.md build commands
After all validation passes, update the `## Build Commands` section in `CLAUDE.md` to add:
```markdown
# Integrations (Phase 4)
python .claude/scripts/integrations/setup_auth.py --check         # Check auth status
python .claude/scripts/integrations/setup_auth.py                 # Run auth flows
python .claude/scripts/integrations/query.py gmail list           # All accounts unread
python .claude/scripts/integrations/query.py gmail list --account sbdb  # Single account
python .claude/scripts/integrations/query.py calendar all         # All 6 calendars
python .claude/scripts/integrations/query.py calendar today       # Personal calendar today
python .claude/scripts/integrations/query.py outlook list         # Outlook inbox
python .claude/scripts/integrations/query.py outlook unread       # Unread count
```

---

## TESTING STRATEGY

### Unit Tests
- `test_integrations.py`: Config loading (8 accounts, 6 calendars), format functions (empty input),
  token file path generation
- No live API calls in unit tests — all format functions can be tested with empty/mock data

### Integration Tests (manual, after auth)
- Run `query.py` against each live service after setup_auth.py completes
- Confirm each Gmail account returns its own emails (not cross-contaminated)
- Confirm calendar queries don't throw errors for shared calendars

### Edge Cases
- Account with expired/missing token: `list_all_accounts()` must skip it with warning, not raise
- Calendar not shared with primary account: `get_all_calendars_events()` must skip with warning
- Empty Outlook inbox: `format_messages_for_context([])` must return graceful message
- `GMAIL_ACCOUNT_*` env vars missing: `GMAIL_ACCOUNTS` dict will be empty — setup_auth.py must
  warn clearly

---

## ACCEPTANCE CRITERIA

- [ ] `config.py` exports `LOCAL_TZ`, `GMAIL_ACCOUNTS` (8 entries), `GOOGLE_CALENDAR_IDS` (6 entries), 
  `GOOGLE_CREDENTIALS_FILE`, `GOOGLE_SCOPES`, `google_token_file()`, `OUTLOOK_CLIENT_ID`,
  `OUTLOOK_TENANT_ID`, `OUTLOOK_TOKEN_FILE`
- [ ] `auth.py` `get_google_credentials(account_name)` loads per-account token file
- [ ] `gmail.py` `list_all_accounts()` queries all 8 accounts, merges results, skips unauthenticated
- [ ] `calendar_api.py` `get_all_calendars_events()` queries all 6 calendar IDs
- [ ] `outlook.py` imports cleanly; `is_outlook_authenticated()` returns bool without raising
- [ ] `setup_auth.py --check` runs without error and shows status for all integrations
- [ ] `query.py` accepts `gmail`, `calendar`, `outlook` subcommands
- [ ] Unit tests pass: `pytest tests/test_integrations.py -v`
- [ ] After manual auth: at least 3 Gmail accounts and 1 calendar return live data via query.py
- [ ] After manual Outlook auth: `query.py outlook list` returns messages
- [ ] No import errors when running any integration file directly

---

## COMPLETION CHECKLIST

- [ ] Task 1: pyproject.toml created, `uv sync` passes
- [ ] Task 2: config.py updated, 8 Gmail + 6 calendar constants verified
- [ ] Task 3: auth.py account_name param working
- [ ] Task 4: gmail.py list_all_accounts() added
- [ ] Task 5: calendar_api.py get_all_calendars_events() added
- [ ] Task 6: outlook.py created, imports cleanly
- [ ] Task 7: registry.py updated with outlook entry
- [ ] Task 8: setup_auth.py created, --check works
- [ ] Task 9: query.py created, --help shows subcommands
- [ ] Task 10: All 8 Gmail accounts authenticated (human step)
- [ ] Task 11: test_integrations.py unit tests pass
- [ ] CLAUDE.md build commands updated

---

## NOTES

**Calendar sharing is a blocking manual step**: Before `get_all_calendars_events()` returns
real data for non-personal calendars, Shaun must share each calendar with
`shaunthommo10@gmail.com`. Without this, those calendars will silently return empty
(the function catches the 403 and logs a warning). This is documented in setup_auth.py output.

**Token expiry with Testing mode**: Since the OAuth app stays in Testing mode (7-day token
expiry), `setup_auth.py` will need to be re-run weekly. This is an acceptable tradeoff vs.
Publishing the app (which would expose the OAuth client to the public).
Consider adding a `--reauth` flag to setup_auth.py that forces re-authentication for all
accounts even if tokens exist.

**Outlook TENANT_ID=consumers**: This is the correct value for personal Microsoft accounts
(outlook.com, hotmail.com). Do not change to a GUID unless using an organizational account.

**No `query.py` in skills/**: Cole's version lives in `.claude/skills/direct-integrations/scripts/`.
Ours lives in `.claude/scripts/integrations/query.py` — referenced from CLAUDE.md build commands
and heartbeat.py (Phase 6).

**Confidence Score: 8/10** — High confidence for Tasks 1–9 (pure code). Task 10 (auth flows)
depends on Shaun completing 8 browser OAuth flows + calendar sharing manually; that's the
primary risk to one-pass success.
