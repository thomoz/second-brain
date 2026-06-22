"""LLM-powered structured extraction from Briefs Finance PDF text."""

from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

# sdk_compat lives in .claude/scripts, not in this package
_SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent.parent / ".claude" / "scripts"
sys.path.insert(0, str(_SCRIPTS_DIR))
from sdk_compat import ClaudeAgentOptions, run_text  # noqa: E402

EXTRACTION_PROMPT = """
Extract ALL stock recommendations from this Briefs Finance report.
Also identify the primary market sector/theme keyword.
Return ONLY valid JSON (no markdown, no explanation):
{{
  "report_date": "YYYY-MM-DD",
  "title": "exact report title",
  "report_type": "thematic|flagship|holdings|plus",
  "series": "growth|income|wealth_preservation|null",
  "inferred_sector": "one of: gold energy oil uranium rare_earth copper lithium water ai tech robotics cybersecurity space data_center china japan europe biotech healthcare income consumer gaming drone africa cannabis stablecoin quantum defence — or null",
  "recommendations": [
    {{"ticker":"SYMBOL","company_name":"Full Name","buy_thesis":"why buy","exit_trigger":"or null"}}
  ]
}}
For holdings reports: top/bottom performers (e.g. "USAR: +85.22%") are the extractable recommendations.
Use buy_thesis = "Briefs Fund top performer [month]" or "Briefs Fund bottom performer [month]".
Analyst notes that name specific buy/sell tickers should also be included.
Report text:
---
{text}
---
"""


def _parse_json(raw: str) -> dict:
    cleaned = raw.strip()
    for fence in ("```json", "```"):
        if cleaned.startswith(fence):
            cleaned = cleaned[len(fence):]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    return json.loads(cleaned.strip())


def extract_recommendations(text: str, max_retries: int = 3) -> dict:
    """Call LLM to extract structured data from PDF text. Retries on JSON parse failure."""
    truncated = text[:12000]  # cap tokens
    prompt = EXTRACTION_PROMPT.format(text=truncated)

    for attempt in range(max_retries):
        try:
            raw = asyncio.run(run_text(
                prompt=prompt,
                options=ClaudeAgentOptions(allowed_tools=[], model="sonnet"),
            ))
            return _parse_json(raw)
        except (json.JSONDecodeError, ValueError) as exc:
            if attempt == max_retries - 1:
                return {
                    "report_date": None,
                    "title": None,
                    "report_type": "thematic",
                    "series": None,
                    "inferred_sector": None,
                    "recommendations": [],
                    "_error": str(exc),
                }
            time.sleep(1.0)
    return {"recommendations": []}
