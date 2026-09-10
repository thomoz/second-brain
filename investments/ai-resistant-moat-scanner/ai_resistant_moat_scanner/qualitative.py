"""Qualitative half of the moat score -- an LLM grading a fixed 6-part
AI-resistance rubric against the latest 10-K's Business + Risk Factors sections.

Caching: the rubric sub-scores + the extraction JSON are cached per
(ticker, accession_number, rubric_version). Filing text is static between filings, so
a cache hit on an unchanged accession costs zero LLM calls (same distinction
mytrader.checks.principles_fit documents -- never cache a live-stats thesis, DO cache
filing-derived sub-scores per accession). Bumping config.RUBRIC_VERSION cleanly
re-scores everything.

A failed rubric call returns None -- a quant-only row that is never stageable. Unlike
briefs-finance score.py (which defaults to 50 on a parse failure because it is grading
an already-surfaced pick), staging a name into Shaun's review queue on a broken rubric
call would just be noise.
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

from . import config, db, filings_extract

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


_RUBRIC_KEYS = (
    "system_of_record",
    "switching_costs",
    "ecosystem_lockin",
    "regulatory_entrenchment",
    "workflow_breadth",
    "mission_criticality",
)

_RUBRIC_PROMPT = """\
You are grading how AI-durable {ticker}'s embedded-software moat is, for a \
concentrated-value investor. The target pattern is the Salesforce property: software \
so engrained in the customer's operations that the ROI of building an AI replacement \
does not make sense. This rubric encodes a 2026 view of what AI can and cannot \
cheaply rebuild.

Score each of the six dimensions 0-10 (0 = absent, 10 = textbook-strong), grounding \
each score in specific language from the filing. Quote or closely paraphrase the \
filing text that justifies each score in `citations`.

1. system_of_record: is the product the authoritative store of data the customer's \
   business runs on (vs a point tool sitting beside the real system)?
2. switching_costs: migration cost, retraining, data lock-in, contractual friction, \
   integration depth.
3. ecosystem_lockin: third-party app marketplace, partner/developer network, \
   certifications, an economy built on the platform.
4. regulatory_entrenchment: the product is how the customer meets a compliance / \
   audit / reporting obligation; replacing it re-opens regulatory risk.
5. workflow_breadth: how many distinct workflows / departments / roles depend on it \
   day to day (broad footprint is harder to dislodge).
6. mission_criticality: what breaks, and how badly, if the product goes away.

Also return:
- anti_signals: a list of short strings for MATERIAL weaknesses in AI-durability \
  only. Include an item only if it genuinely lowers the odds this software survives \
  the AI wave: a true point-solution, core value an LLM could cheaply reproduce, \
  genuinely low switching cost, real commoditization, management explicitly \
  conceding moat erosion or pricing pressure it cannot resist, or serious \
  customer-concentration risk. Do NOT list routine competitive boilerplate, \
  generic "technology changes rapidly" risk-factor language, standard SaaS churn \
  disclosure, or a vendor describing its own product as easy to use / configurable. \
  A textbook-strong moat usually has 0-2 items here; an empty list is the right \
  answer for the strongest names.
- thesis: <= 25 words, one line, what makes this AI-durable or not.

Return ONLY valid JSON (no markdown, no commentary):
{{"system_of_record": 0, "switching_costs": 0, "ecosystem_lockin": 0, \
"regulatory_entrenchment": 0, "workflow_breadth": 0, "mission_criticality": 0, \
"citations": {{"system_of_record": "...", "switching_costs": "...", \
"ecosystem_lockin": "...", "regulatory_entrenchment": "...", \
"workflow_breadth": "...", "mission_criticality": "..."}}, \
"anti_signals": ["..."], "thesis": "..."}}

Disclosed metrics (may be empty): {extraction_notes}

Filing sections:
{sections_text}
"""


def _clamp_int_0_10(value: Any) -> int:
    try:
        return max(0, min(10, int(round(float(value)))))
    except (TypeError, ValueError):
        return 0


def score_rubric(
    ticker: str, sections: dict[str, str], extraction: dict[str, Any]
) -> dict[str, Any] | None:
    """One LLM rubric call. Returns {"sub_scores": {6 keys}, "citations": {...},
    "anti_signals": [...], "thesis": "..."} or None (a failed rubric call must not
    stage a name)."""
    sections_text = "\n\n".join(
        f"[{name.upper()}]\n{text[:config.MOAT_MAX_SECTION_CHARS]}"
        for name in ("business", "risk_factors")
        if (text := sections.get(name, "")).strip()
    )
    if not sections_text.strip():
        return None

    prompt = _RUBRIC_PROMPT.format(
        ticker=ticker,
        extraction_notes=(extraction.get("notes") or "none"),
        sections_text=sections_text,
    )
    try:
        raw = asyncio.run(run_text(
            prompt=prompt,
            options=ClaudeAgentOptions(allowed_tools=[], model=config.MOAT_RUBRIC_MODEL),
        ))
        data = _parse_json(raw)
    except Exception as e:
        print(f"[ai-moat-scan] rubric scoring failed for {ticker}: {e}")
        return None

    sub_scores = {k: _clamp_int_0_10(data.get(k)) for k in _RUBRIC_KEYS}
    citations = data.get("citations") or {}
    anti_signals = [str(s) for s in (data.get("anti_signals") or []) if str(s).strip()]
    thesis = str(data.get("thesis") or "").strip() or "No thesis returned."
    return {
        "sub_scores": sub_scores,
        "citations": {k: str(v) for k, v in citations.items()} if isinstance(citations, dict) else {},
        "anti_signals": anti_signals,
        "thesis": thesis,
    }


def compute_qualitative_score(rubric: dict[str, Any]) -> float:
    """raw = sum of the 6 sub-scores / 60 * 100; each anti-signal costs
    MOAT_ANTI_SIGNAL_PENALTY_EACH points, capped at MOAT_ANTI_SIGNAL_PENALTY_CAP."""
    raw = sum(rubric["sub_scores"].values()) / 60.0 * 100.0
    penalty = min(
        len(rubric["anti_signals"]) * config.MOAT_ANTI_SIGNAL_PENALTY_EACH,
        config.MOAT_ANTI_SIGNAL_PENALTY_CAP,
    )
    return max(0.0, round(raw - penalty, 1))


def _result_from_rubric(
    rubric: dict[str, Any], extraction: dict[str, Any], entry: dict[str, str]
) -> dict[str, Any]:
    return {
        "qualitative_score": compute_qualitative_score(rubric),
        "sub_scores": rubric["sub_scores"],
        "citations": rubric.get("citations", {}),
        "anti_signals": rubric["anti_signals"],
        "thesis": rubric["thesis"],
        "extraction": extraction,
        "accession_number": entry["accession_number"],
        "filing_date": entry["filing_date"],
    }


def get_qualitative(conn: sqlite3.Connection, ticker: str) -> dict[str, Any] | None:
    """Cache-aware orchestrator. None when there is no readable 10-K, or the rubric
    call fails. A cache hit on an unchanged accession makes zero LLM / fetch calls."""
    entry = filings_extract.latest_10k(conn, ticker)
    if entry is None:
        return None

    cached = db.get_cached_qualitative(
        conn, ticker, entry["accession_number"], config.RUBRIC_VERSION
    )
    if cached is not None:
        rubric = json.loads(cached["rubric_json"])
        extraction = json.loads(cached["extraction_json"])
        return _result_from_rubric(rubric, extraction, entry)

    sections = filings_extract.fetch_10k_sections(entry)
    if sections is None:
        return None

    extraction = filings_extract.extract_disclosures(ticker, sections)
    rubric = score_rubric(ticker, sections, extraction)
    if rubric is None:
        return None

    db.upsert_qualitative_cache(
        conn,
        ticker=ticker,
        accession_number=entry["accession_number"],
        rubric_version=config.RUBRIC_VERSION,
        extraction_json=json.dumps(extraction),
        rubric_json=json.dumps(rubric),
        thesis=rubric["thesis"],
    )
    return _result_from_rubric(rubric, extraction, entry)
