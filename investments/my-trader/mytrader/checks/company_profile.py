"""Company/ETF profile — a brief plain-English description of what the ticker
represents, always shown first, always "info" (never a judgment). Added 2026-08-12
at Shaun's request, so deep dive output doesn't require already knowing what the
company does going in. Sourced from yfinance's own longBusinessSummary (present for
both individual equities and funds) -- trimmed to its first couple of sentences
rather than the full paragraph, since the ask was for a brief explanation."""

from __future__ import annotations

from . import CheckResult

_MAX_LEN = 400


def _brief(summary: str) -> str:
    # Naive split on ". " -- a name ending in an abbreviation like "L.P." consumes one
    # of the two sentence slots without adding content (known, accepted gap; same
    # blunt-heuristic tradeoff as the SEC/ASX filing-section heuristics elsewhere in
    # this codebase). Result is still a correct, just occasionally shorter, sentence.
    sentences = summary.strip().split(". ")
    brief = ". ".join(sentences[:2]).strip()
    if not brief.endswith("."):
        brief += "."
    if len(brief) > _MAX_LEN:
        brief = brief[: _MAX_LEN - 3].rstrip() + "..."
    return brief


def check(data) -> CheckResult:
    if data is None:
        return CheckResult(name="company_profile", verdict="unknown", detail="No market data available")

    summary = data.info.get("longBusinessSummary")
    if summary:
        return CheckResult(name="company_profile", verdict="info", detail=_brief(summary))

    name = data.info.get("longName") or data.ticker
    parts = [p for p in (data.info.get("sector"), data.info.get("industry"), data.info.get("category")) if p]
    if parts:
        return CheckResult(
            name="company_profile", verdict="info",
            detail=f"{name} — {' / '.join(parts)} (no business summary available)",
        )
    return CheckResult(name="company_profile", verdict="unknown", detail="No business summary available")
