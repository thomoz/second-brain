"""India / SEBI SAST Regulation 29 leg -- Phase 5.

STATUS 2026-09-08: SPIKE DONE -- feed CONFIRMED on BSE, build pending Shaun's go.
Working endpoint (no login):
  GET https://api.bseindia.com/BseIndiaAPI/api/AnnSubCategoryGetData/w
      ?pageno=N&strCat=Insider Trading / SAST&strPrevDate=YYYYMMDD
      &strToDate=YYYYMMDD&strScrip=&strSearch=P&strType=C&subcategory=-1
Needs browser UA + Referer https://www.bseindia.com/corporates/ann.html + Origin
https://www.bseindia.com + Sec-Fetch-* headers, and a GET https://www.bseindia.com/
session prime. Range must be <= 1 month; 50 rows/page; ~30 SAST rows/day.
Row: NEWSSUB carries "Regulation 29(1)/(2)" + issuer + acquirer (trailing segment
after the last " - "); SLONGNAME/SCRIP_CD = issuer; NEWS_DT = date; NEWSID = dedup
ref; ATTACHMENTNAME = PDF (holds the exact % -- not in the JSON).
NSE is a dead end from this VPS (403 at the Akamai edge). Full write-up:
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
