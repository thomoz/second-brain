"""
Integration registry for the Second Brain.

Lightweight registry that tracks which integrations are available and which
are enabled based on environment configuration. No plugin system — just a
dict of metadata with lazy module loading.

Usage:
    from integrations.registry import get_all, get_enabled, is_enabled

    all_integrations = get_all()       # All registered integrations
    enabled = get_enabled()            # Only integrations with required config set
    if is_enabled("gmail"):            # Check a specific integration
        ...
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass
class IntegrationInfo:
    """Metadata for a registered integration."""

    name: str  # e.g. "gmail"
    display_name: str  # e.g. "Gmail"
    auth_type: str  # "google_oauth" | "token"
    required_config: list[str] = field(default_factory=list)  # Env vars needed
    module_path: str = ""  # e.g. "integrations.gmail"


# ---------------------------------------------------------------------------
# Registry — populated at import time with metadata only.
# Actual integration modules are NOT imported until needed (lazy).
# ---------------------------------------------------------------------------
_REGISTRY: dict[str, IntegrationInfo] = {
    "gmail": IntegrationInfo(
        name="gmail",
        display_name="Gmail (8 accounts)",
        auth_type="google_oauth",
        required_config=[],  # File-based (token_gmail_personal.json)
        module_path="integrations.gmail",
    ),
    "calendar": IntegrationInfo(
        name="calendar",
        display_name="Google Calendar (6 calendars)",
        auth_type="google_oauth",
        required_config=[],  # IDs loaded from GOOGLE_CALENDAR_ID_* env vars
        module_path="integrations.calendar_api",
    ),
    "outlook": IntegrationInfo(
        name="outlook",
        display_name="Outlook",
        auth_type="token",
        required_config=["OUTLOOK_CLIENT_ID"],
        module_path="integrations.outlook",
    ),
}


def _has_google_token(account_name: str = "personal") -> bool:
    """Check if Google OAuth token file exists for the given account."""
    from config import google_token_file
    return google_token_file(account_name).exists()


def get_all() -> dict[str, IntegrationInfo]:
    """Return all registered integrations."""
    return dict(_REGISTRY)


def get_enabled() -> dict[str, IntegrationInfo]:
    """Return only integrations whose required config is set."""
    enabled: dict[str, IntegrationInfo] = {}

    for name, info in _REGISTRY.items():
        if info.auth_type == "google_oauth":
            # Google integrations need the personal account token file to exist
            if not _has_google_token("personal"):
                continue
        elif info.required_config:
            # Token-based integrations need their env vars set
            if not all(os.getenv(var, "") for var in info.required_config):
                continue

        enabled[name] = info

    return enabled


def is_enabled(name: str) -> bool:
    """Check if a specific integration is enabled."""
    return name in get_enabled()
