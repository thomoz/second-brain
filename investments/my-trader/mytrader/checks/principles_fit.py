"""Principles-fit check — grades Find's own read of a ticker against the 9 named-
investor frameworks already used by briefs-finance's own LLM scoring
(investments/briefs-finance/principles/*.md).

Pulled over 2026-08-02 at Shaun's request. Briefs Finance's own principles score
(scripts.score.compute_score) only ever grades a Briefs-Finance-report's PDF-derived
buy_thesis — for a ticker Briefs Finance never covered, or where the thesis was thin
(see UBER's 22/100 Dalio score: the source thesis was a retrospective "SWF made money
on an early stake" narrative with no macro/valuation argument at all, not a fair test
of the company itself), there's no way to get a Buffett/Graham/Munger/etc read.

Reuses scripts.score.score_thesis_against_principle() directly (same uv workspace)
rather than duplicating it, but grades a thesis this check builds itself from Find's
own live check results instead of a PDF-derived buy_thesis.

Deliberately NOT cached and NOT run by Monitor (see engine.run_assessment's
include_principles_fit param, defaulted False so Monitor's daily re-check of 50+
holdings/watchlist rows is unaffected) — confirmed 2026-08-02: unlike Briefs
Finance's thesis text, which never changes once ingested, the summary here is built
from live fundamentals that shift run to run, so caching it would just go stale.
Recomputed fresh on every explicit Find call instead — Find is a deliberate,
on-demand action, not a high-frequency loop, so the repeat cost is low.

Macro-regime context (added 2026-08-02, same day) — a real gap found comparing
UBER's before/after principles_fit scores: every framework improved once graded
against Find's own thesis instead of Briefs Finance's weak PDF thesis, EXCEPT Dalio
(+2 vs +11 to +34 for the others) — Dalio's framework is fundamentally about
debt-cycle/regime fit, which neither thesis provided any material on. Folds in
Monitor's own macro-indicator snapshot (MOVE, credit spreads, recession signal,
CPI x3, etc.) via db.get_macro_snapshot(), read from cache rather than fetched live
— those signals are inherently slow-moving (CPI is monthly/quarterly, credit
spreads/yield curve are daily), so Monitor's once-a-day refresh is fresh enough, and
re-fetching MOVE/FRED/ABS/ONS live on every Find call would add real latency for no
real freshness gain. Cache can go stale if Monitor's timer misses a day — the "as of"
date is surfaced in the thesis text itself so that's visible, not hidden, matching
macro_indicators.py's own existing practice of surfacing FRED observation dates.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from .. import config, db
from . import CheckResult


def _build_thesis(
    ticker: str,
    other_checks: list[CheckResult],
    briefs_score: dict[str, Any] | None,
    recent_return_1mo: float | None,
    recent_return_3mo: float | None,
    macro_rows: list[sqlite3.Row] | None = None,
) -> str:
    """Construct a short thesis-style summary from Find's own live check results, in
    place of a PDF-derived buy_thesis, so the principle files have something concrete
    to grade."""
    by_name = {c.name: c for c in other_checks}
    parts = [f"{ticker}."]

    val = by_name.get("valuation")
    if val is not None and val.data.get("pe") is not None:
        parts.append(f"PE {val.data['pe']:.1f}.")

    bs = by_name.get("balance_sheet")
    if bs is not None:
        if bs.data.get("debt_to_equity") is not None:
            parts.append(f"Debt/equity {bs.data['debt_to_equity']:.1f}.")
        if bs.data.get("current_ratio") is not None:
            parts.append(f"Current ratio {bs.data['current_ratio']:.2f}.")
        if bs.data.get("return_on_equity_pct") is not None:
            parts.append(f"ROE {bs.data['return_on_equity_pct']:.1f}%.")

    div = by_name.get("dividend")
    if div is not None:
        parts.append(f"Dividend: {div.detail}.")

    if recent_return_1mo is not None and recent_return_3mo is not None:
        parts.append(
            f"Price action: {recent_return_1mo:+.1f}% over 1 month, "
            f"{recent_return_3mo:+.1f}% over 3 months."
        )

    if briefs_score is not None:
        parts.append(f"Briefs Finance likelihood score: {briefs_score['score']}/100.")

    flagged = [c.name for c in other_checks if c.verdict == "flag"]
    if flagged:
        parts.append(f"Active risk flags this run: {', '.join(flagged)}.")
    else:
        parts.append("No active risk flags this run.")

    if macro_rows:
        as_of = macro_rows[0]["computed_at"][:10]
        macro_parts = "; ".join(f"{r['name']} [{r['verdict']}] {r['detail']}" for r in macro_rows)
        parts.append(f"Macro regime as of {as_of}: {macro_parts}.")

    return " ".join(parts)


def check(
    ticker: str,
    data,
    other_checks: list[CheckResult],
    briefs_score: dict[str, Any] | None,
    recent_return_1mo: float | None,
    recent_return_3mo: float | None,
    conn: sqlite3.Connection | None = None,
) -> CheckResult:
    if data is None:
        return CheckResult(name="principles_fit", verdict="unknown", detail="No market data available")

    from scripts.config import PRINCIPLES_DIR
    from scripts.score import score_thesis_against_principle

    if not PRINCIPLES_DIR.exists():
        return CheckResult(name="principles_fit", verdict="unknown", detail="Principle files not found")

    macro_rows = db.get_macro_snapshot(conn) if conn is not None else []
    thesis = _build_thesis(
        ticker, other_checks, briefs_score, recent_return_1mo, recent_return_3mo, macro_rows
    )

    results = []
    for md_file in sorted(PRINCIPLES_DIR.glob("*.md")):
        principle_name = md_file.stem
        file_content = md_file.read_text(encoding="utf-8")
        score, reasoning = score_thesis_against_principle(thesis, principle_name, file_content)
        results.append({"principle": principle_name, "score": score, "reasoning": reasoning})

    if not results:
        return CheckResult(name="principles_fit", verdict="unknown", detail="No principle files scored")

    average = sum(r["score"] for r in results) / len(results)
    top3 = sorted(results, key=lambda r: r["score"], reverse=True)[:3]
    top_summary = ", ".join(f"{r['principle']} {r['score']}" for r in top3)

    # Same 0-100 scale and "high conviction" semantics as the Briefs Finance score,
    # so reuse its threshold rather than inventing a second number for the same idea.
    verdict = "interesting" if average >= config.OPPORTUNITY_SCORE_FLAG else "info"
    detail = f"avg {average:.0f}/100 across 9 investor frameworks (top: {top_summary})"

    return CheckResult(
        name="principles_fit", verdict=verdict, detail=detail,
        data={
            "thesis": thesis, "average": round(average, 1), "results": results,
            "macro_snapshot_as_of": macro_rows[0]["computed_at"][:10] if macro_rows else None,
        },
    )
