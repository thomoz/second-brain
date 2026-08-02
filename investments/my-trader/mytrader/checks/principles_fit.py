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
"""

from __future__ import annotations

from typing import Any

from .. import config
from . import CheckResult


def _build_thesis(
    ticker: str,
    other_checks: list[CheckResult],
    briefs_score: dict[str, Any] | None,
    recent_return_1mo: float | None,
    recent_return_3mo: float | None,
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

    return " ".join(parts)


def check(
    ticker: str,
    data,
    other_checks: list[CheckResult],
    briefs_score: dict[str, Any] | None,
    recent_return_1mo: float | None,
    recent_return_3mo: float | None,
) -> CheckResult:
    if data is None:
        return CheckResult(name="principles_fit", verdict="unknown", detail="No market data available")

    from scripts.config import PRINCIPLES_DIR
    from scripts.score import score_thesis_against_principle

    if not PRINCIPLES_DIR.exists():
        return CheckResult(name="principles_fit", verdict="unknown", detail="Principle files not found")

    thesis = _build_thesis(ticker, other_checks, briefs_score, recent_return_1mo, recent_return_3mo)

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
        data={"thesis": thesis, "average": round(average, 1), "results": results},
    )
