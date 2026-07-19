"""Opportunity signal — surfaces watchlist candidates worth a second look, not just
risk warnings.

Confirmed 2026-07-19: Shaun pointed out Monitor's report only ever told him what to
avoid or watch out for, never what to be interested in. Distinct from the other 7
checks (neutral-to-cautionary by design): this one actively looks for reasons to be
interested — cheap valuation, strong recent price momentum, a high Briefs Finance
likelihood score — and returns verdict="interesting" (not "flag") when any fire.
"interesting" is a deliberately distinct verdict from "flag": it's positive, not a
risk, and (per monitor.py) is rendered as a live snapshot every run rather than
going through the alert_history dedup machinery — Shaun wants to see it every run
while it's true, not just once when first detected.

Explicitly does NOT compare against existing holdings in the same sector (considered
and rejected 2026-07-19 — Shaun: "it doesn't matter if I have another holding in the
same sector... I can make the choice myself by asking you to deeply compare them").
This looks at the candidate alone.
"""

from __future__ import annotations

from typing import Any

from .. import config
from . import CheckResult


def check(
    data, briefs_score: dict[str, Any] | None, recent_return_pct: float | None,
) -> CheckResult:
    if data is None:
        return CheckResult(name="opportunity", verdict="unknown", detail="No market data available")

    reasons = []

    pe = data.info.get("trailingPE") or data.info.get("forwardPE")
    if pe is not None and pe <= config.PE_CHEAP_THRESHOLD:
        reasons.append(f"PE {pe:.1f} at/below cheap threshold ({config.PE_CHEAP_THRESHOLD})")

    if recent_return_pct is not None and recent_return_pct >= config.OPPORTUNITY_MOMENTUM_FLAG_PCT:
        reasons.append(f"up {recent_return_pct:+.1f}% over the last 3 months")

    if briefs_score is not None and briefs_score["score"] >= config.OPPORTUNITY_SCORE_FLAG:
        provisional = " (provisional)" if briefs_score["provisional"] else ""
        reasons.append(f"Briefs Finance score {briefs_score['score']}/100{provisional}")

    if reasons:
        return CheckResult(
            name="opportunity", verdict="interesting",
            detail="; ".join(reasons), data={"reasons": reasons},
        )
    return CheckResult(name="opportunity", verdict="ok", detail="No standout positive signal this run")
