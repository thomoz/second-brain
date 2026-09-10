"""Latest-10-K fetch + targeted LLM extraction of disclosed lock-in economics
(NRR / RPO / recurring-revenue % / customer count / logo churn) as nullable JSON.

"Not disclosed -> null, never guessed." Every network/LLM boundary returns None (or
an all-None dict) on any failure, never raises -- module policy, same as
mytrader.sec_filings.
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

from mytrader import sec_filings

from . import config

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent.parent / ".claude" / "scripts"
sys.path.insert(0, str(_SCRIPTS_DIR))
from sdk_compat import ClaudeAgentOptions, run_text  # noqa: E402


def _parse_json(raw: str) -> dict:
    """Strip ```json / ``` fences then json.loads. Copied verbatim from
    briefs-finance scripts/score.py:33-40."""
    cleaned = raw.strip()
    for fence in ("```json", "```"):
        if cleaned.startswith(fence):
            cleaned = cleaned[len(fence):]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    return json.loads(cleaned.strip())


_EXTRACTION_KEYS = (
    "recurring_revenue_pct",
    "nrr_pct",
    "rpo_usd",
    "rpo_yoy_pct",
    "customer_count",
    "logo_churn_pct",
    "notes",
)


def _all_none() -> dict[str, Any]:
    return {k: (None if k != "notes" else "") for k in _EXTRACTION_KEYS}


def latest_10k(conn: sqlite3.Connection, ticker: str) -> dict[str, str] | None:
    """The most recent 10-K filing entry for a ticker, or None (non-US / no CIK / no
    10-K / fetch failure). Keys: cik, accession_number, primary_document, filing_date."""
    cik = sec_filings.get_cik(conn, ticker.upper())
    if cik is None:
        return None
    index = sec_filings.fetch_filing_index(cik)
    if index is None:
        return None
    entry = sec_filings.latest_filing_entry(index, "10-K")
    if entry is None:
        return None
    return {
        "cik": cik,
        "accession_number": entry["accession_number"],
        "primary_document": entry["primary_document"],
        "filing_date": entry["filing_date"],
    }


def fetch_10k_sections(entry: dict[str, str]) -> dict[str, str] | None:
    """Item 1 / 1A / 7 text for a 10-K filing entry (keys business / risk_factors /
    mda). None on fetch failure or empty extraction."""
    html = sec_filings.fetch_filing_document(
        entry["cik"], entry["accession_number"], entry["primary_document"]
    )
    if html is None:
        return None
    sections = sec_filings.extract_sections(html, "10-K")
    return sections or None


_EXTRACTION_PROMPT = """\
You are extracting disclosed lock-in / recurring-revenue economics from {ticker}'s \
latest 10-K for an investment analyst. Use ONLY what the filing explicitly states. \
Do NOT estimate, infer, or calculate a number the filing does not give directly -- \
use null for anything not explicitly disclosed.

Return ONLY valid JSON (no markdown, no commentary):
{{"recurring_revenue_pct": <0-100 or null>, "nrr_pct": <number or null>, \
"rpo_usd": <number in USD or null>, "rpo_yoy_pct": <number or null>, \
"customer_count": <integer or null>, "logo_churn_pct": <number or null>, \
"notes": "<=40 words on what the filing does and does not disclose about lock-in economics"}}

Fields:
- recurring_revenue_pct: subscription / recurring revenue as a percent of total revenue
- nrr_pct: net revenue retention / net dollar retention rate (e.g. 112 for 112%)
- rpo_usd: remaining performance obligations / total contracted backlog, in USD
- rpo_yoy_pct: year-over-year change in RPO, as a percent
- customer_count: number of customers / accounts / logos
- logo_churn_pct: annual customer (logo) churn rate, as a percent

Filing sections:
{sections_text}
"""


def extract_disclosures(ticker: str, sections: dict[str, str]) -> dict[str, Any]:
    """One LLM extraction call -> the 7-key nullable dict. Any failure (LLM error,
    unparseable JSON) returns the all-None dict -- a failed extraction contributes
    nothing to the score, it never fabricates a number."""
    sections_text = "\n\n".join(
        f"[{name.upper()}]\n{text[:config.MOAT_MAX_SECTION_CHARS]}"
        for name in ("business", "mda")
        if (text := sections.get(name, "")).strip()
    )
    if not sections_text.strip():
        return _all_none()

    prompt = _EXTRACTION_PROMPT.format(ticker=ticker, sections_text=sections_text)
    try:
        raw = asyncio.run(run_text(
            prompt=prompt,
            options=ClaudeAgentOptions(allowed_tools=[], model=config.MOAT_EXTRACTION_MODEL),
        ))
        data = _parse_json(raw)
    except Exception as e:
        print(f"[ai-moat-scan] extraction failed for {ticker}: {e}")
        return _all_none()

    result = _all_none()
    for key in _EXTRACTION_KEYS:
        val = data.get(key)
        if key == "notes":
            result["notes"] = str(val)[:400] if val else ""
            continue
        if val is None:
            continue
        try:
            if key == "customer_count":
                result[key] = int(val)
            else:
                result[key] = float(val)
        except (TypeError, ValueError):
            continue
    return result
