"""Central path constants and timezone utilities for Second Brain scripts."""
from __future__ import annotations

import zoneinfo
from datetime import datetime
from pathlib import Path

# Vault root (all Memory/ paths are relative to repo root)
VAULT_DIR = Path("Memory")
MEMORY_DIR = VAULT_DIR
DAILY_DIR = VAULT_DIR / "daily"
DRAFTS_DIR = VAULT_DIR / "drafts"
ACTIVE_DRAFTS_DIR = DRAFTS_DIR / "active"

# Runtime dirs
SCRIPTS_DIR = Path(".claude/scripts")
DATA_DIR = Path(".claude/data")
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
SEARCH_CHUNK_OVERLAP_TOKENS = 80    # NOTE: PRD says 50 — actual code uses 80
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


def ensure_directories() -> None:
    """Ensure all Phase 1-3 runtime directories exist."""
    for d in [DAILY_DIR, STATE_DIR, DATA_DIR, EMBEDDING_CACHE_DIR,
              ACTIVE_DRAFTS_DIR, DRAFTS_DIR / "sent", DRAFTS_DIR / "expired"]:
        d.mkdir(parents=True, exist_ok=True)
