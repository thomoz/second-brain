"""Central path constants and timezone utilities for Second Brain scripts."""

from __future__ import annotations

import zoneinfo
from datetime import date, datetime
from pathlib import Path

# Project root — absolute, CWD-independent (.claude/scripts → .claude → project root)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Vault root
VAULT_DIR = PROJECT_ROOT / "Memory"
MEMORY_DIR = VAULT_DIR
DAILY_DIR = VAULT_DIR / "daily"
DRAFTS_DIR = VAULT_DIR / "drafts"
ACTIVE_DRAFTS_DIR = DRAFTS_DIR / "active"

# Runtime dirs
SCRIPTS_DIR = PROJECT_ROOT / ".claude/scripts"
DATA_DIR = PROJECT_ROOT / ".claude/data"
STATE_DIR = DATA_DIR / "state"

# Timezone: all timestamps use Sydney local time
TZ = zoneinfo.ZoneInfo("Australia/Sydney")


def now_local() -> datetime:
    """Current datetime in Australia/Sydney timezone."""
    return datetime.now(tz=TZ)


# ---------------------------------------------------------------------------
# Phase 3: Memory Search
# ---------------------------------------------------------------------------
import os as _os

from dotenv import load_dotenv as _load_dotenv

_load_dotenv(Path(__file__).parent / ".env")

# Database
DATABASE_PATH = DATA_DIR / "memory.db"
DATABASE_URL = _os.getenv("DATABASE_URL", "")

# Embedding model
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_DIMENSIONS = 384
EMBEDDING_CACHE_DIR = DATA_DIR / "models"

# Search tuning (match Cole's reference exactly)
SEARCH_CHUNK_MAX_TOKENS = 400
SEARCH_CHUNK_OVERLAP_TOKENS = 80  # NOTE: PRD says 50 — actual code uses 80
SEARCH_VECTOR_WEIGHT = 0.7
SEARCH_KEYWORD_WEIGHT = 0.3
SEARCH_DEFAULT_LIMIT = 10
SEARCH_MIN_SCORE = 0.2


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
        _acct = _key[len("GMAIL_ACCOUNT_") :].lower()
        GMAIL_ACCOUNTS[_acct] = _val

# Google Calendar IDs — populated from GOOGLE_CALENDAR_ID_* env vars
# Maps calendar_name → calendar_id
GOOGLE_CALENDAR_IDS: dict[str, str] = {}
for _key, _val in _os.environ.items():
    if _key.startswith("GOOGLE_CALENDAR_ID_") and _val:
        _cal = _key[len("GOOGLE_CALENDAR_ID_") :].lower()
        GOOGLE_CALENDAR_IDS[_cal] = _val

# Outlook (Microsoft Graph)
OUTLOOK_CLIENT_ID = _os.getenv("OUTLOOK_CLIENT_ID", "")
OUTLOOK_TENANT_ID = _os.getenv("OUTLOOK_TENANT_ID", "consumers")
OUTLOOK_TOKEN_FILE = INTEGRATIONS_DIR / "outlook_token.json"
OUTLOOK_SCOPES = ["Mail.Read"]
OUTLOOK_JUNK_FOLDER = "junkemail"  # Graph API well-known folder id
OUTLOOK_JUNK_RULES_FILE = DATA_DIR / "outlook_junk_rules.json"


# ---------------------------------------------------------------------------
# Phase 6: Proactive Systems
# ---------------------------------------------------------------------------

# Owner / active hours
OWNER_NAME = _os.getenv("OWNER_NAME", "Shaun")
ACTIVE_HOURS_START = int(_os.getenv("ACTIVE_HOURS_START", "7"))
ACTIVE_HOURS_END = int(_os.getenv("ACTIVE_HOURS_END", "22"))

# Heartbeat interval — read both spellings (typo guard: HEARTBEART vs HEARTBEAT)
_hb_env = _os.getenv("HEARTBEAT_INTERVAL_MINUTES") or _os.getenv(
    "HEARTBEART_INTERVAL_MINUTES", "240"
)
HEARTBEAT_INTERVAL_MINUTES = int(_hb_env)

# Heartbeat timezone label (for display in prompts)
HEARTBEAT_TIMEZONE = _os.getenv("HEARTBEAT_TIMEZONE", "Australia/Sydney")

# Memory file path constants
SOUL_FILE = VAULT_DIR / "SOUL.md"
USER_FILE = VAULT_DIR / "USER.md"
MEMORY_FILE = VAULT_DIR / "MEMORY.md"
HABITS_FILE = VAULT_DIR / "HABITS.md"
HEARTBEAT_FILE = VAULT_DIR / "HEARTBEAT.md"
# Own file (not a HEARTBEAT.md section) since 2026-08-14 -- a section name inside a
# differently-named file was how real WhatsApp handoffs went unseen for days.
HANDOFF_FILE = VAULT_DIR / "whatsapp-handoff-messages-for-local-session.md"

# State file constants
HEARTBEAT_STATE_FILE = STATE_DIR / "heartbeat-state.json"
REFLECTION_STATE_FILE = STATE_DIR / "reflection-state.json"
WHATSAPP_HEALTH_STATE_FILE = STATE_DIR / "whatsapp-health-state.json"
# Tracks which handoff entries have already been surfaced in a session's context
# (separate from handoff_check.py's own seen_hashes, which gates the hourly toast).
HANDOFF_SURFACED_STATE_FILE = STATE_DIR / "handoff-surfaced-state.json"

# WhatsApp bot's own stdout/stderr log (path set via the systemd unit's
# StandardOutput/StandardError=append: directives, not written by Python directly —
# defined here so whatsapp_health.py doesn't hardcode a duplicate path).
WHATSAPP_LOG_PATH = SCRIPTS_DIR / "whatsapp_runs.log"

# Draft lifecycle constants (dirs already created in ensure_directories)
DRAFTS_ACTIVE_DIR = ACTIVE_DRAFTS_DIR  # alias for clarity
DRAFTS_EXPIRED_DIR = DRAFTS_DIR / "expired"
DRAFTS_SENT_DIR = DRAFTS_DIR / "sent"
DRAFT_EXPIRY_HOURS = int(_os.getenv("DRAFT_EXPIRY_HOURS", "24"))
EXPIRED_DRAFT_RETENTION_DAYS = int(_os.getenv("EXPIRED_DRAFT_RETENTION_DAYS", "30"))

# WhatsApp outbound (GREEN-API) — inbound polling is Phase 7
WHATSAPP_INSTANCE_ID = _os.getenv("WHATSAPP_INSTANCE_ID", "")
WHATSAPP_API_TOKEN = _os.getenv("WHATSAPP_API_TOKEN", "")
WHATSAPP_MY_NUMBER = _os.getenv("WHATSAPP_MY_NUMBER", "")  # format: 61412345678


def is_within_active_hours() -> bool:
    """Return True if current local hour is within active hours window."""
    hour = now_local().hour
    return ACTIVE_HOURS_START <= hour < ACTIVE_HOURS_END


def get_log_path_for_date(d: date) -> Path:
    """Return daily log path for a given date (Memory/daily/YYYY/MM/YYYY-MM-DD.md)."""
    return DAILY_DIR / d.strftime("%Y") / d.strftime("%m") / f"{d.strftime('%Y-%m-%d')}.md"


def get_today_log_path() -> Path:
    """Return path to today's daily log, creating the year/month directory if needed."""
    today = now_local().date()
    path = get_log_path_for_date(today)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


# ---------------------------------------------------------------------------
# Phase 7: WhatsApp Chat Bot
# ---------------------------------------------------------------------------

CHAT_DB_PATH = DATA_DIR / "chat.db"
CHAT_MAX_TURNS = int(_os.getenv("CHAT_MAX_TURNS", "20"))
CHAT_MAX_BUDGET_USD = float(_os.getenv("CHAT_MAX_BUDGET_USD", "0.50"))
WHATSAPP_POLL_INTERVAL = float(_os.getenv("WHATSAPP_POLL_INTERVAL", "1.0"))

# Lock file: bot writes this on start, heartbeat checks it before WA polling
BOT_LOCK_FILE = STATE_DIR / "whatsapp-bot.lock"


# Structured memory directories
ENTITIES_DIR = VAULT_DIR / "entities"
TOPICS_DIR = VAULT_DIR / "topics"
DECISIONS_DIR = VAULT_DIR / "decisions"
PROFILE_DIR = VAULT_DIR / "Profile"
CORE_MEMORIES_FILE = VAULT_DIR / "core-memories.md"
GUIDE_FILE = VAULT_DIR / "GUIDE.md"


def ensure_directories() -> None:
    """Ensure all Phase 1-3 runtime directories exist."""
    for d in [
        DAILY_DIR,
        STATE_DIR,
        DATA_DIR,
        EMBEDDING_CACHE_DIR,
        ACTIVE_DRAFTS_DIR,
        DRAFTS_DIR / "sent",
        DRAFTS_DIR / "expired",
        ENTITIES_DIR,
        TOPICS_DIR,
        DECISIONS_DIR,
        PROFILE_DIR,
    ]:
        d.mkdir(parents=True, exist_ok=True)
