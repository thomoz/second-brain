"""India / SEBI SAST Regulation 29 leg -- BSE "Insider Trading / SAST" feed.

Feed (confirmed live 2026-09-08, see INDIA-LEG-FINDINGS.md):
  GET https://api.bseindia.com/BseIndiaAPI/api/AnnSubCategoryGetData/w
      ?pageno=N&strCat=Insider Trading / SAST&strPrevDate=YYYYMMDD
      &strToDate=YYYYMMDD&strScrip=&strSearch=P&strType=C&subcategory=-1
Needs a browser UA + Referer/Origin + Sec-Fetch-* headers and a session primed with
GET https://www.bseindia.com/. Date range must be <= 1 month; 50 rows/page.

Each row:
  SUBCATNAME -- "Disclosures under Reg. 29(1)/(2) of SEBI (SAST) Regulations, 2011"
                (the two we want; the category also carries Reg 31, Reg 10, trading-
                window closures -- filtered out here)
  SLONGNAME / SCRIP_CD -- the issuer
  HEADLINE   -- "...Regulations, 2011 for <ACQUIRER NAME>"  <- the name we match
  NEWS_DT    -- disclosure timestamp
  NEWSID     -- stable GUID, used as the dedup ref
  ATTACHMENTNAME -- the disclosure PDF (holds the exact % -- usually a scanned image,
                    so v1 links to it rather than parsing it)

NSE is a dead end from this VPS (403 at the Akamai edge). BSE-only is the v1;
SAST disclosures are filed with both exchanges so BSE still catches them.

Structurally parallel to edgar_monitor: fetch -> filter to Reg 29 -> name-match the
acquirer against each tracked investor's india_aliases -> dedup -> insert into
superinvestor_filings_seen (source='sast') -> build an alert dict. Never raises.
"""

from __future__ import annotations

import re
import sqlite3
import time
from datetime import date, datetime, timedelta, timezone
from typing import Any

import requests

from mytrader.db import get_sync_watermark, set_sync_watermark

from . import config, db

SAST_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
_BSE_HOME = "https://www.bseindia.com/"
_BSE_ANN_API = "https://api.bseindia.com/BseIndiaAPI/api/AnnSubCategoryGetData/w"
_BSE_ATTACH_URL = "https://www.bseindia.com/xml-data/corpfiling/AttachLive/{name}"
_SAST_CATEGORY = "Insider Trading / SAST"

_HEADERS = {
    "User-Agent": SAST_USER_AGENT,
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.bseindia.com/corporates/ann.html",
    "Origin": "https://www.bseindia.com",
    "Sec-Fetch-Site": "same-site",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Dest": "empty",
}

_ACQUIRER_RE = re.compile(r"\bfor\s+(.{2,120}?)\s*$", re.IGNORECASE)


def _session() -> requests.Session:
    s = requests.Session()
    try:
        s.get(_BSE_HOME, headers={"User-Agent": SAST_USER_AGENT}, timeout=20)
    except Exception:
        pass
    return s


def fetch_sast_disclosures(prev_date: str, to_date: str) -> list[dict[str, Any]] | None:
    """Paginate the BSE SAST-category feed for the date window (YYYYMMDD, <= 1 month).
    Returns the raw row list, or None if the very first page fails (partial results
    on a later-page failure are returned as-is -- better than nothing for a daily
    seed)."""
    s = _session()
    rows: list[dict[str, Any]] = []
    for page in range(1, config.SUPERINVESTOR_SAST_MAX_PAGES + 1):
        try:
            r = s.get(_BSE_ANN_API, headers=_HEADERS, timeout=30, params={
                "pageno": str(page),
                "strCat": _SAST_CATEGORY,
                "strPrevDate": prev_date,
                "strToDate": to_date,
                "strScrip": "",
                "strSearch": "P",
                "strType": "C",
                "subcategory": "-1",
            })
            if r.status_code != 200:
                return rows or None
            payload = r.json()
        except Exception:
            return rows or None
        table = payload.get("Table", []) if isinstance(payload, dict) else []
        if not table:
            break
        rows.extend(table)
        time.sleep(config.SUPERINVESTOR_SAST_REQUEST_DELAY_SECONDS)
    return rows


def _reg_label(subcat: str) -> str | None:
    s = (subcat or "").strip()
    if s.startswith("Disclosures under Reg. 29(1)"):
        return "SAST Reg 29(1)"
    if s.startswith("Disclosures under Reg. 29(2)"):
        return "SAST Reg 29(2)"
    return None


def _acquirer_name(headline: str, newssub: str) -> str:
    m = _ACQUIRER_RE.search((headline or "").strip())
    if m:
        return m.group(1).strip().rstrip(".")
    # Fallback: the trailing segment of NEWSSUB after the last " - " (some rows
    # carry the acquirer there instead).
    parts = re.split(r"\s-\s", newssub or "")
    tail = parts[-1].strip() if parts else ""
    return "" if tail.lower().startswith("disclosures under reg") else tail


def _match_tracked_filer(acquirer: str) -> tuple[str, str] | None:
    a = acquirer.lower()
    if not a:
        return None
    for filer_key, cfg in config.SUPERINVESTOR_TRACKED.items():
        for alias in cfg.get("india_aliases", []):
            if alias.lower() in a:
                return filer_key, cfg["display"]
    return None


def scan_india(conn: sqlite3.Connection) -> dict[str, Any]:
    first_seed = get_sync_watermark(conn, config.SUPERINVESTOR_SAST_FIRST_SEED_WATERMARK) is None
    today = date.today()
    prev = (today - timedelta(days=config.SUPERINVESTOR_SAST_LOOKBACK_DAYS)).strftime("%Y%m%d")
    rows = fetch_sast_disclosures(prev, today.strftime("%Y%m%d"))

    if rows is None:
        print("[superinvestor-scan] BSE SAST feed fetch failed -- skipped this run")
        recent = [dict(r) for r in db.get_recent_superinvestor_filings_seen(conn, source="sast", limit=100)]
        return {"new_filings": [], "recent_filings": recent, "first_seed": False}

    new_filings: list[dict[str, Any]] = []
    for row in rows:
        reg = _reg_label(row.get("SUBCATNAME", ""))
        if reg is None:
            continue
        acquirer = _acquirer_name(row.get("HEADLINE", ""), row.get("NEWSSUB", ""))
        match = _match_tracked_filer(acquirer)
        if match is None:
            continue
        filer_key, filer_display = match

        scrip = row.get("SCRIP_CD")
        issuer = (row.get("SLONGNAME") or "").strip() or f"BSE {scrip}"
        newsid = row.get("NEWSID") or ""
        disclosed = (row.get("NEWS_DT") or "")[:10]
        attach = row.get("ATTACHMENTNAME") or ""
        raw_url = _BSE_ATTACH_URL.format(name=attach) if attach else (row.get("NSURL") or "")
        # Reg 29(1) is by definition a 5% crossing; Reg 29(2) is a >= 2% move whose
        # direction is not in the JSON, so it stays untagged.
        crossing = "5% cross" if reg == "SAST Reg 29(1)" else None

        dedup_key = "|".join(["sast", filer_key, reg, issuer, newsid])
        newly_seen = db.insert_superinvestor_filing_seen(
            conn, dedup_key=dedup_key, source="sast", filer_key=filer_key,
            filer_display=filer_display, form_type=reg, issuer=issuer,
            issuer_ticker=None, accession=newsid, event_date=None, filed_date=disclosed,
            shares=None, pct_owned=None, pct_owned_change=None, material_crossing=crossing,
            transaction_code=None, raw_url=raw_url,
        )
        if not newly_seen or first_seed:
            continue

        line = (
            f"{reg} -- {acquirer} on {issuer} (BSE {scrip}), disclosed {disclosed}"
        )
        if crossing:
            line += f" [{crossing}]"
        new_filings.append({
            "filer_key": filer_key, "filer_display": filer_display, "form_type": reg,
            "issuer": issuer, "issuer_ticker": None, "filed_date": disclosed,
            "event_date": None, "material_crossing": crossing, "summary": line,
            "raw_url": raw_url,
        })

    if first_seed:
        set_sync_watermark(
            conn, config.SUPERINVESTOR_SAST_FIRST_SEED_WATERMARK,
            datetime.now(timezone.utc).isoformat(),
        )

    recent = [dict(r) for r in db.get_recent_superinvestor_filings_seen(conn, source="sast", limit=100)]
    return {"new_filings": new_filings, "recent_filings": recent, "first_seed": first_seed}
