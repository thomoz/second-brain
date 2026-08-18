"""SEC EDGAR filing fetch + extraction + summarization for principles_fit's thesis
(see .agent/plans/sec-filings-principles-fit.md). Modeled on abs_cpi.py's style:
direct government-source fetch via requests, no third-party SEC wrapper library,
explicit User-Agent, graceful None/skip on any failure -- never raises.

Two independent caches, deliberately different from principles_fit.py's own "never
cache the thesis" policy documented in that file's module docstring: sec_cik_map
(bulk ticker->CIK map, refreshed on a >SEC_CIK_MAP_REFRESH_DAYS-stale schedule via the
existing sync_state watermark table) and sec_filing_cache (per-ticker/filing_type
summary, invalidated only when a newer accession_number appears -- filing text is
static between filings, unlike the live stats principles_fit's own thesis is built
from, so this is a fundamentally different invalidation rule, not an inconsistency).

Non-US tickers (SEC EDGAR has no ASX/LSE/etc coverage) degrade gracefully via a plain
CIK-lookup miss -- get_filing_summaries_for_ticker returns None, exactly like
concentration.py/etf_mechanics.py already handle other missing-data cases.
"""

from __future__ import annotations

import asyncio
import re
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

from . import config, db

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent.parent / ".claude" / "scripts"
sys.path.insert(0, str(_SCRIPTS_DIR))
from sdk_compat import ClaudeAgentOptions, run_text  # noqa: E402

_HEADERS = {"User-Agent": config.SEC_USER_AGENT}
_ITEM_HEADER_RE = re.compile(r"(?:^|\n)\s*item\s+(\d+[a-z]?)\.?\s", re.IGNORECASE)
_PART_HEADER_RE = re.compile(r"(?:^|\n)\s*part\s+(i{1,3}|iv)\b", re.IGNORECASE)
_DEF14A_HEADINGS = (
    "compensation discussion and analysis",
    "executive compensation",
    "security ownership of certain beneficial owners",
)

# --- CIK resolution ----------------------------------------------------------


def _fetch_cik_map_bulk() -> dict[str, str] | None:
    """company_tickers.json shape: {"0": {"cik_str": <int>, "ticker": <str>,
    "title": <str>}, "1": {...}, ...}."""
    try:
        r = requests.get(config.SEC_CIK_MAP_URL, headers=_HEADERS, timeout=30)
        if r.status_code != 200:
            return None
        raw = r.json()
        return {row["ticker"].upper(): str(row["cik_str"]) for row in raw.values()}
    except Exception:
        return None


def _refresh_cik_map_if_stale(conn: sqlite3.Connection) -> None:
    last = db.get_sync_watermark(conn, "sec_cik_map_refreshed_at")
    if last is not None:
        age_days = (datetime.now(timezone.utc) - datetime.fromisoformat(last)).days
        if age_days < config.SEC_CIK_MAP_REFRESH_DAYS:
            return
    bulk = _fetch_cik_map_bulk()
    if bulk is None:
        return  # keep using whatever's cached (possibly nothing) rather than block
    db.upsert_cik_map_bulk(conn, bulk)
    db.set_sync_watermark(conn, "sec_cik_map_refreshed_at", datetime.now(timezone.utc).isoformat())


def get_cik(conn: sqlite3.Connection, ticker: str) -> str | None:
    _refresh_cik_map_if_stale(conn)
    return db.get_cik_for_ticker(conn, ticker)

# --- Filing index + document fetch ------------------------------------------


def fetch_filing_index(cik: str) -> dict[str, Any] | None:
    url = config.SEC_SUBMISSIONS_URL_TEMPLATE.format(cik_padded=f"{int(cik):010d}")
    try:
        r = requests.get(url, headers=_HEADERS, timeout=15)
        if r.status_code != 200:
            return None
        return r.json()
    except Exception:
        return None


def latest_filing_entry(index: dict[str, Any], form_type: str) -> dict[str, str] | None:
    recent = index.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    for i, form in enumerate(forms):
        if form == form_type:
            return {
                "accession_number": recent["accessionNumber"][i],
                "primary_document": recent["primaryDocument"][i],
                "filing_date": recent["filingDate"][i],
            }
    return None  # older filings paginated into index["filings"]["files"] aren't
                 # checked in v1 -- "most recent filing" should always land in the
                 # "recent" array per SEC's own docs (~last ~1000 filings).


def fetch_filing_document(cik: str, accession_number: str, document: str) -> str | None:
    url = config.SEC_ARCHIVES_URL_TEMPLATE.format(
        cik=str(int(cik)), accession_no_dashes=accession_number.replace("-", ""),
        document=document,
    )
    try:
        r = requests.get(url, headers=_HEADERS, timeout=30)
        if r.status_code != 200 or len(r.content) > config.SEC_MAX_RAW_DOCUMENT_BYTES:
            return None
        return r.text
    except Exception:
        return None

# --- Section extraction ------------------------------------------------------


def strip_html(html: str) -> str:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    return soup.get_text(separator="\n")


def _split_by_item(text: str) -> dict[str, str]:
    # GOTCHA (real, found against a live KO 10-K/10-Q at Task 3.1): every item label
    # appears exactly twice in practice -- once in the table of contents (a dense
    # cluster of "Item N. Title ... <page#>" lines packed within a few hundred chars
    # of each other) and once at the real section body, which can be tens of
    # thousands of characters later. "Keep first occurrence" (the original approach)
    # grabbed the TOC line, not the actual section text. "Keep LAST occurrence"
    # (overwrite on each match, not skip) reliably lands on the real body instead --
    # confirmed against real filings, not assumed.
    matches = list(_ITEM_HEADER_RE.finditer(text))
    items: dict[str, str] = {}
    for i, m in enumerate(matches):
        label = m.group(1).upper()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        items[label] = text[m.start():end]
    return items


def _split_by_part(text: str) -> dict[str, str]:
    # Same TOC-vs-body duplication as _split_by_item above -- "Part I"/"Part II" each
    # appear once in the TOC and once at the real section start; keep the LAST
    # occurrence, not the first.
    matches = list(_PART_HEADER_RE.finditer(text))
    if not matches:
        return {"": text}
    parts: dict[str, str] = {}
    for i, m in enumerate(matches):
        label = m.group(1).upper()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        parts[label] = text[m.start():end]
    return parts


def _extract_10k_sections(text: str) -> dict[str, str]:
    items = _split_by_item(text)
    sections = {}
    if "1" in items:
        sections["business"] = items["1"]
    if "1A" in items:
        sections["risk_factors"] = items["1A"]
    if "7" in items:
        sections["mda"] = items["7"]
    if "8" in items:
        sections["financial_statements"] = items["8"]
    return sections


def _extract_10q_sections(text: str) -> dict[str, str]:
    # 10-Q Item numbers repeat across Part I and Part II with DIFFERENT meanings
    # (Part I Item 2 = MD&A; Part II Item 1A = Risk Factors). Must split by Part
    # FIRST, then find Items within each Part's own substring -- splitting by Item
    # across the whole document conflates them.
    parts = _split_by_part(text)
    part1_items = _split_by_item(parts.get("I", ""))
    part2_items = _split_by_item(parts.get("II", ""))
    sections = {}
    if "2" in part1_items:
        sections["mda"] = part1_items["2"]
    if "1A" in part2_items:
        sections["risk_factors"] = part2_items["1A"]
    if "1" in part1_items:
        sections["financial_statements"] = part1_items["1"]
    return sections


def _find_def14a_heading_index(text: str, lower_text: str, heading: str) -> int | None:
    """A real proxy heading appears many times: once in the TOC, once (or more) as an
    inline prose cross-reference ("see 'Executive Compensation'..."), and once as the
    actual section header. Confirmed against a real KO DEF 14A (Task 3.1): the real
    header is reliably in ALL CAPS ("COMPENSATION DISCUSSION AND ANALYSIS"), while
    every prose cross-reference uses normal title case -- rfind alone (last
    occurrence) isn't reliable here since the last mention can just be another
    prose reference near the end of the document. Prefer the last ALL-CAPS
    occurrence; fall back to plain rfind if no ALL-CAPS occurrence exists (still
    better than nothing, and this filer-specific formatting variance is a known,
    documented limitation, not something this heuristic can fully solve)."""
    idxs = []
    start = 0
    while True:
        idx = lower_text.find(heading, start)
        if idx == -1:
            break
        idxs.append(idx)
        start = idx + 1
    if not idxs:
        return None
    caps_idxs = [i for i in idxs if text[i:i + len(heading)].isupper()]
    return caps_idxs[-1] if caps_idxs else idxs[-1]


def _extract_def14a_sections(text: str) -> dict[str, str]:
    # No reliable Item-header convention in practice (unlike 10-K/10-Q) -- real proxy
    # statements use free-form section titles, and individual filers don't always use
    # the exact SEC-caption wording (e.g. KO's 2026 proxy never uses the literal
    # phrase "security ownership of certain beneficial owners" -- confirmed against a
    # real filing at Task 3.1; that heading is a known, accepted gap, not a bug).
    # Heading-substring search + a fixed trailing window is a deliberately blunter
    # heuristic than the Item-splitting above; the LLM summarization step is expected
    # to filter noise within the window, not this extraction step. Biggest
    # technical-risk area in this module -- see SKILL.md's Known Limitations.
    lower = text.lower()
    sections = {}
    for heading in _DEF14A_HEADINGS:
        idx = _find_def14a_heading_index(text, lower, heading)
        if idx is None:
            continue
        sections[heading.replace(" ", "_")] = text[idx: idx + 8000]
    return sections


def _extract_sections(html: str, filing_type: str) -> dict[str, str]:
    text = strip_html(html)
    if filing_type == "10-K":
        return _extract_10k_sections(text)
    if filing_type == "10-Q":
        return _extract_10q_sections(text)
    if filing_type == "DEF 14A":
        return _extract_def14a_sections(text)
    return {}

# --- Summarization ------------------------------------------------------------

_SUMMARY_PROMPT = """\
You are summarizing part of {ticker}'s {filing_type} SEC filing for an investment \
analyst. Condense the following into a focused, investment-relevant summary \
(200-400 words) -- keep material risks, competitive position, and financial \
trajectory; drop boilerplate legal hedging and repetitive disclaimers.

{sections_text}

Return plain text only, no markdown headers.
"""


def _summarize_sections(ticker: str, filing_type: str, sections: dict[str, str]) -> str | None:
    sections_text = "\n\n".join(
        f"[{name.upper()}]\n{text[:config.SEC_MAX_SECTION_CHARS]}"
        for name, text in sections.items() if text.strip()
    )
    if not sections_text.strip():
        return None
    prompt = _SUMMARY_PROMPT.format(ticker=ticker, filing_type=filing_type, sections_text=sections_text)
    try:
        raw = asyncio.run(run_text(
            prompt=prompt,
            options=ClaudeAgentOptions(allowed_tools=[], model=config.SEC_FILING_SUMMARY_MODEL),
        ))
        return raw.strip() or None
    except Exception:
        return None

# --- Orchestrator --------------------------------------------------------------


def get_filing_summaries_for_ticker(ticker: str, conn: sqlite3.Connection) -> dict[str, str] | None:
    cik = get_cik(conn, ticker.upper())
    if cik is None:
        return None
    index = fetch_filing_index(cik)
    if index is None:
        return None

    summaries: dict[str, str] = {}
    for filing_type in config.SEC_FILING_TYPES:
        latest = latest_filing_entry(index, filing_type)
        if latest is None:
            continue
        cached = db.get_cached_filing_summary(conn, ticker, filing_type)
        if cached is not None and cached["accession_number"] == latest["accession_number"]:
            summaries[filing_type] = cached["summary"]
            continue

        html = fetch_filing_document(cik, latest["accession_number"], latest["primary_document"])
        summary = None
        if html is not None:
            sections = _extract_sections(html, filing_type)
            if sections:
                summary = _summarize_sections(ticker, filing_type, sections)

        if summary is not None:
            db.upsert_filing_summary_cache(
                conn, ticker=ticker, filing_type=filing_type,
                accession_number=latest["accession_number"], summary=summary,
            )
            summaries[filing_type] = summary
        elif cached is not None:
            summaries[filing_type] = cached["summary"]  # stale-but-usable fallback

        time.sleep(config.SEC_REQUEST_DELAY_SECONDS)

    return summaries or None
