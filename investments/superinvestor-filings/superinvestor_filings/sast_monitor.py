"""India / SEBI SAST Regulation 29 leg -- Phase 5.

STATUS 2026-09-07: SPIKE NOT YET DONE. The NSE / BSE "System Driven Disclosures
(SAST)" feeds have not been verified as no-login, machine-readable endpoints from
this environment, and NSE is known to block non-browser clients (needs a cookie
primed from GET https://www.nseindia.com, reused via a requests.Session, plus a
browser-like User-Agent). Per the plan's STOP CONDITION, no scraper is built here
without Shaun's sign-off on a confirmed feed. See
investments/superinvestor-filings/INDIA-LEG-FINDINGS.md.

When the spike confirms a feed, this module becomes structurally parallel to
edgar_monitor: fetch_sast_disclosures(session_date) -> list[dict] | None, then
scan_india(conn) name-pattern-matches each acquirer against the tracked investor's
`india_aliases` (case-insensitive substring, any match), builds a dedup_key with
source='sast', inserts into superinvestor_filings_seen, and returns alert dicts.
Reg 29(2) rows carry a >= 2% change -- surface it (better granularity than US 13G).
"""

from __future__ import annotations

import sqlite3
from typing import Any

# Browser-like UA for NSE/BSE (config.SEC_USER_AGENT is a contact-email UA required
# only by SEC's fair-access policy and is NOT appropriate here) -- mirrors
# goat.config.GOAT_SP500_USER_AGENT's idiom.
SAST_USER_AGENT = "Mozilla/5.0 (compatible; SecondBrainSuperinvestor/1.0)"


def fetch_sast_disclosures(session_date: str) -> list[dict[str, Any]] | None:
    """Phase 5 spike deliverable. Returns None until a confirmed feed is wired."""
    return None


def scan_india(conn: sqlite3.Connection) -> dict[str, Any]:
    print(
        "[superinvestor-scan] India / SEBI SAST leg is not yet available -- Phase 5 "
        "spike pending (see investments/superinvestor-filings/INDIA-LEG-FINDINGS.md)"
    )
    return {"new_filings": [], "recent_filings": []}
