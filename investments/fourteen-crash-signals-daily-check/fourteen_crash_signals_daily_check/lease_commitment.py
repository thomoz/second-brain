"""Marker 2 -- off-balance-sheet lease commitments ("leases that have not yet
commenced"), disclosed as narrative footnote text in the Leases note of the Financial
Statements section of a 10-K/10-Q -- not a clean XBRL field (see the Phase 2 handoff's
Marker #2 section for the full fact-check). Reuses sec_filings.py's CIK/filing-index/
document-fetch plumbing directly (now public, see Task 1) plus a new heading-search + a
new strictly-parseable LLM prompt, distinct from sec_filings._summarize_sections's
free-prose one."""

from __future__ import annotations

import re
import sqlite3
from typing import Any

from mytrader import sec_filings
from mytrader.checks import CheckResult

from . import config, db

_LEASE_HEADING_CANDIDATES = (
    "leases that have not yet commenced",
    "leases not yet commenced",
    "leases signed but not yet commenced",
)

_LEASE_FIGURE_PROMPT = """\
You are extracting a single financial figure from a SEC filing's Leases note for {ticker}.

Return ONLY a single number in USD (no symbols, no commas, no words) for the total \
dollar amount of leases that have not yet commenced (i.e. signed but not yet begun). \
If this filing does not disclose such a figure, return exactly: NONE

Text:
---
{text}
---
"""


def _find_lease_note_window(text: str) -> str | None:
    """Mirrors sec_filings._find_def14a_heading_index's heuristic: footnotes have no
    Item-style header, so search for the heading phrase itself, preferring the last
    ALL-CAPS occurrence (the real note header) over a prose cross-reference, falling back
    to plain last-occurrence if no ALL-CAPS hit exists."""
    lower = text.lower()
    idxs: list[int] = []
    for heading in _LEASE_HEADING_CANDIDATES:
        start = 0
        while True:
            idx = lower.find(heading, start)
            if idx == -1:
                break
            idxs.append(idx)
            start = idx + 1
    if not idxs:
        return None
    caps_idxs = [i for i in idxs if text[i:i + 40].isupper()]
    idx = caps_idxs[-1] if caps_idxs else idxs[-1]
    return text[idx: idx + config.SIGNALS_LEASE_NOTE_WINDOW_CHARS]


def _summarize_lease_figure(ticker: str, text: str) -> float | None:
    import asyncio
    import sys
    from pathlib import Path

    _scripts_dir = Path(__file__).resolve().parent.parent.parent.parent / ".claude" / "scripts"
    sys.path.insert(0, str(_scripts_dir))
    from sdk_compat import ClaudeAgentOptions, run_text

    prompt = _LEASE_FIGURE_PROMPT.format(ticker=ticker, text=text[:config.SIGNALS_LEASE_NOTE_WINDOW_CHARS])
    try:
        raw = asyncio.run(run_text(
            prompt=prompt,
            options=ClaudeAgentOptions(allowed_tools=[], model="sonnet"),
        )).strip()
    except Exception:
        return None
    if raw.upper() == "NONE":
        return None
    cleaned = re.sub(r"[^\d.]", "", raw)
    try:
        return float(cleaned) if cleaned else None
    except ValueError:
        return None


def _latest_10k_or_10q(index: dict[str, Any]) -> tuple[str, dict[str, str]] | None:
    """Whichever of 10-K/10-Q was filed most recently -- an annual 10-K can update this
    figure too, not just quarterlies (Phase 2 handoff, Marker #2 resolution)."""
    candidates = []
    for filing_type in ("10-K", "10-Q"):
        entry = sec_filings.latest_filing_entry(index, filing_type)
        if entry is not None:
            candidates.append((filing_type, entry))
    if not candidates:
        return None
    candidates.sort(key=lambda c: c[1]["filing_date"], reverse=True)
    return candidates[0]


def _check_one_ticker(conn: sqlite3.Connection, ticker: str) -> CheckResult | None:
    cik = sec_filings.get_cik(conn, ticker)
    if cik is None:
        return None
    index = sec_filings.fetch_filing_index(cik)
    if index is None:
        return None
    latest = _latest_10k_or_10q(index)
    if latest is None:
        return None
    filing_type, entry = latest

    prior = db.get_lease_commitment_history(conn, ticker)
    if prior is not None and prior["accession_number"] == entry["accession_number"]:
        figure = prior["figure"]  # unchanged since last check -- skip re-fetch/re-summarize
    else:
        html = sec_filings.fetch_filing_document(cik, entry["accession_number"], entry["primary_document"])
        if html is None:
            return None
        text = sec_filings.strip_html(html)
        window = _find_lease_note_window(text)
        if window is None:
            return None  # not disclosed this filing -- an honest gap, not a fetch failure
        figure = _summarize_lease_figure(ticker, window)
        if figure is None:
            return None
        db.upsert_lease_commitment_history(
            conn, ticker=ticker, accession_number=entry["accession_number"],
            figure=figure, filing_date=entry["filing_date"],
        )

    if prior is None:
        return CheckResult(
            name="lease_commitments", verdict="ok",
            detail=f"{ticker}: ${figure / 1e9:.1f}B uncommenced lease commitments "
                   f"(baseline, {filing_type} filed {entry['filing_date']}) -- no prior "
                   f"reading to compare growth against yet",
            data={"ticker": ticker, "figure": figure, "filing_date": entry["filing_date"]},
        )

    growth_pct = (figure - prior["figure"]) / prior["figure"] * 100 if prior["figure"] else 0.0
    detail = (
        f"{ticker}: ${figure / 1e9:.1f}B uncommenced lease commitments "
        f"({growth_pct:+.1f}% since last filing, {filing_type} filed {entry['filing_date']})"
    )
    verdict = "flag" if growth_pct >= config.SIGNALS_LEASE_COMMITMENT_GROWTH_FLAG_PCT else "ok"
    return CheckResult(
        name="lease_commitments", verdict=verdict, detail=detail,
        data={"ticker": ticker, "figure": figure, "growth_pct": growth_pct, "filing_date": entry["filing_date"]},
    )


def check_lease_commitments(conn: sqlite3.Connection, hot_watchlist: list[Any]) -> list[CheckResult]:
    results = []
    for row in hot_watchlist:
        result = _check_one_ticker(conn, row["ticker"])
        if result is not None:
            results.append(result)
    return results
