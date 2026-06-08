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
_load_dotenv()

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


def ensure_directories() -> None:
    """Ensure all Phase 1-3 runtime directories exist."""
    for d in [DAILY_DIR, STATE_DIR, DATA_DIR, EMBEDDING_CACHE_DIR,
              ACTIVE_DRAFTS_DIR, DRAFTS_DIR / "sent", DRAFTS_DIR / "expired"]:
        d.mkdir(parents=True, exist_ok=True)
