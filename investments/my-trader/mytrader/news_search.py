"""Live news/event search for checks/news_events.py -- covers material catalysts
(M&A offers, litigation, credit-rating actions, leadership turnover, short-seller
reports) that fundamentals-only checks structurally cannot see. See
checks/news_events.py's module docstring for the ZIM case that motivated this and
its known limits.

Runs via sdk_compat with allowed_tools=["WebSearch"] -- under the active Codex
backend (confirmed live 2026-08-05: sdk_compat.BACKEND == "codex") this turns on
Codex CLI's own tools.web_search flag (see codex_sdk_compat.py's _wants_web), which
is flat-rate on the ChatGPT subscription, not a separate paid search API.

Cached per ticker for NEWS_EVENTS_CACHE_HOURS -- unlike sec_filing_cache/
asx_announcement_cache (invalidated on a new accession/announcement id), news has no
version identifier to key off, so this is a plain time-based TTL, not "until
something changes".
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import config, db

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent.parent / ".claude" / "scripts"
sys.path.insert(0, str(_SCRIPTS_DIR))
from sdk_compat import ClaudeAgentOptions, run_text  # noqa: E402

_SEARCH_PROMPT = """\
You are researching live news and events for {ticker} on behalf of an investment \
analyst doing a deep-dive review. Use web search to check each of the following, \
and report only what you find real, current evidence for -- do not speculate:

1. "{ticker} takeover offer" -- any live M&A activity: buyout offers, mergers, or a \
rival/counter-bid on top of an existing deal. Also specifically search \
"{ticker} counter-bid" or "{ticker} rival bid" -- a signed deal can attract a \
higher competing offer later, which a single generic search for the original deal \
can miss once it has already found that first announcement.
2. "{ticker} lawsuit OR investigation" -- litigation, SEC/DOJ investigations, or \
regulatory action
3. "{ticker} credit rating downgrade" -- recent Moody's/S&P/Fitch rating actions
4. "{ticker} CEO resigns" -- CEO/executive leadership changes
5. "{ticker} short seller report" -- fraud or accounting-quality allegations from a \
short seller

Ignore routine background noise (e.g. every large company has some pending \
litigation -- only report something specific and material, not a generic mention). \
Ignore anything not from the last ~6 months unless it is still actively unresolved \
(e.g. a signed-but-not-yet-closed merger).

Respond with ONLY a JSON object, no markdown fences, no other text:
{{"material": true or false, "detail": "one or two sentence summary of what you \
found, or empty string if nothing material", "findings": ["short finding 1", ...]}}

Set "material" to true only if something you found would meaningfully change how an \
investor should read this ticker's other fundamentals this run (a live deal, a \
credit downgrade, a fraud allegation, a leadership shakeup) -- not for routine, \
long-resolved, or immaterial items.
"""


def _parse_json(raw: str) -> dict:
    cleaned = raw.strip()
    for fence in ("```json", "```"):
        if cleaned.startswith(fence):
            cleaned = cleaned[len(fence):]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    return json.loads(cleaned.strip())


def _search_news_events(ticker: str) -> dict | None:
    prompt = _SEARCH_PROMPT.format(ticker=ticker)
    try:
        raw = asyncio.run(run_text(
            prompt=prompt,
            options=ClaudeAgentOptions(allowed_tools=["WebSearch"], model=config.NEWS_EVENTS_SUMMARY_MODEL),
        ))
        return _parse_json(raw)
    except Exception:
        return None


def _format_detail(result: dict) -> str:
    summary = (result.get("detail") or "").strip()
    findings = [str(f).strip() for f in (result.get("findings") or []) if str(f).strip()]
    if summary and findings:
        return f"{summary} ({'; '.join(findings)})"
    if findings:
        return "; ".join(findings)
    if summary:
        return summary
    return "No material news/event findings this run."


def get_news_events_for_ticker(ticker: str, conn: sqlite3.Connection) -> dict | None:
    """Returns {"verdict": "flag"|"info", "detail": str}. Returns None only when the
    search itself failed (network/LLM error) and no cached row exists to fall back
    on -- "nothing material found" is a normal successful result (verdict="info"),
    not a None."""
    cached = db.get_cached_news_events(conn, ticker)
    if cached is not None:
        fetched_at = datetime.fromisoformat(cached["fetched_at"])
        age_hours = (datetime.now(timezone.utc) - fetched_at).total_seconds() / 3600
        if age_hours < config.NEWS_EVENTS_CACHE_HOURS:
            return {"verdict": cached["verdict"], "detail": cached["detail"]}

    result = _search_news_events(ticker)
    if result is None:
        if cached is not None:
            return {"verdict": cached["verdict"], "detail": cached["detail"]}  # stale-but-usable fallback
        return None

    verdict = "flag" if result.get("material") else "info"
    detail = _format_detail(result)

    db.upsert_news_events_cache(conn, ticker=ticker, verdict=verdict, detail=detail)
    return {"verdict": verdict, "detail": detail}
