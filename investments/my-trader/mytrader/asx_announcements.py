"""ASX Market Announcements fetch + extraction + summarization for principles_fit's
thesis (see .agent/plans/asx-announcements-principles-fit.md), the ASX-listed
sibling of sec_filings.py. Modeled on that module's style: direct-fetch via
requests, no third-party ASX wrapper library, graceful None/skip on any failure --
never raises. Two real structural differences from sec_filings.py, both
deliberate, not oversights:

- **No CIK-equivalent resolution step.** SEC needs a bulk ticker->CIK lookup;
  ASX's own announcement-list endpoint takes the bare ticker code directly
  (`.AX` suffix stripped), so there's no bulk map/cache table needed here.
- **ASX reports are PDFs, not HTML** (confirmed live 2026-08-03, see
  .agent/plans/completed/asx-market-announcements-handoff.md) -- extraction reuses
  briefs-finance's own scripts.extract.extract_text (pdfplumber, falling back to
  PyMuPDF+pytesseract OCR for scanned/image-based PDFs) rather than BeautifulSoup
  tag-stripping.

One cache, same invalidation philosophy as sec_filings.py's sec_filing_cache
(deliberately different from principles_fit.py's own "never cache the thesis"
policy): asx_announcement_cache, invalidated only when a new ASX `idsId` appears
for that (ticker, announcement_type) -- report text is static between lodgements,
unlike the live-stats thesis this feeds into, which shifts run to run.

Non-ASX tickers degrade gracefully via a plain `.AX`-suffix check --
get_announcement_summaries_for_ticker returns None with zero network calls, same
pattern sec_filings.py's CIK-lookup-miss degradation and
concentration.py/etf_mechanics.py's other missing-data cases already use.
"""

from __future__ import annotations

import asyncio
import re
import sqlite3
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

from . import config, db

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent.parent / ".claude" / "scripts"
sys.path.insert(0, str(_SCRIPTS_DIR))
from sdk_compat import ClaudeAgentOptions, run_text  # noqa: E402

# Bare `scripts.*` import, not `briefs_finance.scripts.*` -- briefs-finance's own
# pyproject.toml ([tool.hatch.build.targets.wheel] packages = ["scripts"]) exposes
# `scripts` as a top-level importable package via the shared uv workspace, same as
# principles_fit.py's existing `from scripts.config import PRINCIPLES_DIR`.
from scripts.extract import extract_text  # noqa: E402

_HEADERS = {"User-Agent": config.ASX_USER_AGENT}
_IDS_ID_RE = re.compile(r"idsId=(\d+)")
_PDF_URL_RE = re.compile(r'name="pdfURL"\s+value="([^"]+)"')
_APOSTROPHE_RE = re.compile(r"[’'�`]")
_TOC_SKIP_GAP_CHARS = 5000  # see _find_heading_index's docstring for why.

# --- Ticker helpers ------------------------------------------------------------


def _is_asx_ticker(ticker: str) -> bool:
    return ticker.strip().upper().endswith(".AX")


def _bare_asx_code(ticker: str) -> str:
    return ticker.strip().upper().removesuffix(".AX")

# --- List fetch + type filtering ------------------------------------------------


def _fetch_announcements_list(code: str, year: int) -> list[dict[str, str]] | None:
    url = config.ASX_ANNOUNCEMENTS_LIST_URL_TEMPLATE.format(code=code, year=year)
    try:
        r = requests.get(url, headers=_HEADERS, timeout=30)
        if r.status_code != 200:
            return None
        return _parse_announcements_html(r.text)
    except Exception:
        return None


def _parse_announcements_html(html: str) -> list[dict[str, str]]:
    """Real markup confirmed live 2026-08-03: each announcement is an <a
    href=".../displayAnnouncement.do?display=pdf&idsId=NNNNNNNN"> whose first
    direct text child is the real title, followed by <br/> and nested <span>s for
    page-count/filesize -- get_text(strip=True) on the whole <a> concatenates all
    of that together (title+pages+filesize with no separator), so pull only the
    first direct NavigableString child instead. Rows are already newest-first per
    ASX's own listing order (confirmed against real BXB/WES data), so no separate
    date-sort is needed for "most recent matching row" selection."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    for a in soup.find_all("a", href=True):
        m = _IDS_ID_RE.search(str(a["href"]))
        if m is None:
            continue
        title = next((c for c in a.contents if isinstance(c, str) and c.strip()), "").strip()
        if not title:
            continue
        rows.append({"title": title, "ids_id": m.group(1)})
    return rows


def _select_target_announcements(
    rows: list[dict[str, str]], types: dict[str, tuple[str, ...]]
) -> dict[str, dict[str, str]]:
    selected: dict[str, dict[str, str]] = {}
    for label, patterns in types.items():
        for row in rows:
            low = row["title"].lower()
            if any(p in low for p in patterns):
                selected[label] = row
                break
    return selected

# --- Interstitial + PDF fetch ---------------------------------------------------


def _resolve_pdf_url(ids_id: str) -> str | None:
    url = config.ASX_ANNOUNCEMENT_INTERSTITIAL_URL_TEMPLATE.format(ids_id=ids_id)
    try:
        r = requests.get(url, headers=_HEADERS, timeout=30)
        if r.status_code != 200:
            return None
        m = _PDF_URL_RE.search(r.text)
        return m.group(1) if m else None
    except Exception:
        return None


def _fetch_pdf_bytes(url: str) -> bytes | None:
    try:
        r = requests.get(url, headers=_HEADERS, timeout=60)
        if r.status_code != 200 or len(r.content) > config.ASX_MAX_RAW_PDF_BYTES:
            return None
        return r.content
    except Exception:
        return None


def _extract_pdf_text(pdf_bytes: bytes) -> str:
    """extract_text takes a Path, not bytes -- no in-memory variant exists in
    briefs-finance's extract.py to reuse, so write to a temp file first."""
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(pdf_bytes)
        tmp_path = Path(tmp.name)
    try:
        return extract_text(tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)

# --- Section extraction ----------------------------------------------------------


def _normalize_for_heading_search(s: str) -> str:
    """Same-length substitution (matched char -> single space), not deletion, so
    indices computed against the normalized copy still line up with the original
    text. Real ASX filers render the possessive apostrophe inconsistently after PDF
    extraction -- confirmed live 2026-08-03: pdfplumber renders BXB's real
    "Directors' Report" running header with a mangled replacement character where
    the apostrophe should be, which breaks a literal substring match unless both
    the heading candidate and the extracted text are normalized the same way."""
    return _APOSTROPHE_RE.sub(" ", s)


def _find_heading_index(haystack_lower: str, needle_lower: str) -> int | None:
    """Confirmed live 2026-08-03 against real BXB/WES PDFs: ASX report headings
    are used as repeating per-page running headers spanning many pages of one
    section, NOT sec_filings.py's DEF14A-style single-body-occurrence pattern --
    e.g. WES's real 2025 Annual Report repeats "operating and financial review"
    29 times across a ~40-page chapter. Taking the LAST occurrence (mirroring
    _find_def14a_heading_index) lands deep in an unrelated subsection near the
    chapter's end (e.g. its Sustainability Report sub-chapter), not the chapter's
    actual overview. But the very FIRST occurrence is often an isolated TOC line
    far ahead of the real running-header cluster (confirmed: WES's TOC mention sits
    ~40,000 chars before the real section start). Heuristic: if the first two
    occurrences are far apart (> _TOC_SKIP_GAP_CHARS), treat the first as a lone TOC
    line and use the second; otherwise the first occurrence already is real body
    text (confirmed for BXB's single-occurrence "review of operations" case)."""
    idxs = []
    start = 0
    while True:
        idx = haystack_lower.find(needle_lower, start)
        if idx == -1:
            break
        idxs.append(idx)
        start = idx + 1
    if not idxs:
        return None
    if len(idxs) >= 2 and (idxs[1] - idxs[0]) > _TOC_SKIP_GAP_CHARS:
        return idxs[1]
    return idxs[0]


def _extract_sections(text: str) -> dict[str, str]:
    normalized_lower = _normalize_for_heading_search(text).lower()
    sections: dict[str, str] = {}
    for heading in config.ASX_HEADING_CANDIDATES:
        needle = _normalize_for_heading_search(heading).lower()
        idx = _find_heading_index(normalized_lower, needle)
        if idx is None:
            continue
        sections[heading.replace(" ", "_")] = text[idx: idx + config.ASX_MAX_SECTION_CHARS]
    return sections

# --- Summarization ----------------------------------------------------------------

_SUMMARY_PROMPT = """\
You are summarizing part of {ticker}'s ASX {announcement_type} for an investment \
analyst. Condense the following into a focused, investment-relevant summary \
(200-400 words) -- keep material risks, competitive position, and financial \
trajectory; drop boilerplate legal/administrative text.

{sections_text}

Return plain text only, no markdown headers.
"""


def _summarize_sections(ticker: str, announcement_type: str, sections: dict[str, str]) -> str | None:
    sections_text = "\n\n".join(
        f"[{name.upper()}]\n{text[:config.ASX_MAX_SECTION_CHARS]}"
        for name, text in sections.items() if text.strip()
    )
    if not sections_text.strip():
        return None
    prompt = _SUMMARY_PROMPT.format(
        ticker=ticker, announcement_type=announcement_type, sections_text=sections_text,
    )
    try:
        raw = asyncio.run(run_text(
            prompt=prompt,
            options=ClaudeAgentOptions(allowed_tools=[], model=config.ASX_ANNOUNCEMENT_SUMMARY_MODEL),
        ))
        return raw.strip() or None
    except Exception:
        return None

# --- Orchestrator -------------------------------------------------------------


def get_announcement_summaries_for_ticker(ticker: str, conn: sqlite3.Connection) -> dict[str, str] | None:
    if not _is_asx_ticker(ticker):
        return None
    code = _bare_asx_code(ticker)

    current_year = datetime.now(timezone.utc).year
    rows = _fetch_announcements_list(code, current_year)
    selected: dict[str, dict[str, str]] = (
        _select_target_announcements(rows, config.ASX_ANNOUNCEMENT_TYPES) if rows else {}
    )

    missing = [label for label in config.ASX_ANNOUNCEMENT_TYPES if label not in selected]
    if missing:
        # Confirmed live 2026-08-03: as of this build, neither BXB's nor WES's
        # FY2026 Annual Report had been lodged yet (fiscal year end 30 June,
        # annual report typically lodges Aug-Oct) -- the current calendar year's
        # list can legitimately lack a type for months at a time, so fall back to
        # the previous year's list for whatever's still missing.
        prev_rows = _fetch_announcements_list(code, current_year - 1)
        if prev_rows:
            prev_selected = _select_target_announcements(prev_rows, config.ASX_ANNOUNCEMENT_TYPES)
            for label in missing:
                if label in prev_selected:
                    selected[label] = prev_selected[label]

    summaries: dict[str, str] = {}
    for label, row in selected.items():
        announcement_id = row["ids_id"]
        cached = db.get_cached_asx_summary(conn, ticker, label)
        if cached is not None and cached["announcement_id"] == announcement_id:
            summaries[label] = cached["summary"]
            continue

        summary = None
        pdf_url = _resolve_pdf_url(announcement_id)
        if pdf_url is not None:
            pdf_bytes = _fetch_pdf_bytes(pdf_url)
            if pdf_bytes is not None:
                text = _extract_pdf_text(pdf_bytes)
                sections = _extract_sections(text) if text else {}
                if sections:
                    summary = _summarize_sections(ticker, label, sections)

        if summary is not None:
            db.upsert_asx_summary_cache(
                conn, ticker=ticker, announcement_type=label,
                announcement_id=announcement_id, summary=summary,
            )
            summaries[label] = summary
        elif cached is not None:
            summaries[label] = cached["summary"]  # stale-but-usable fallback

        time.sleep(config.ASX_REQUEST_DELAY_SECONDS)

    return summaries or None
