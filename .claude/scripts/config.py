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
