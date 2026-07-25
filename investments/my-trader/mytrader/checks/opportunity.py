"""Opportunity signal — surfaces watchlist candidates worth a second look, not just
risk warnings.

Confirmed 2026-07-19: Shaun pointed out Monitor's report only ever told him what to
avoid or watch out for, never what to be interested in. First version of this check
used arbitrary thresholds (raw PE cutoff, "price went up 10%") invented without
research — Shaun called this out directly: "You need to research a bunch of tests and
mental models that expert and successful traders use... otherwise this whole tool is
a waste of time." Rebuilt from `investments/briefs-finance/principles/*.md` — the 9
investor-principle files already in this codebase (used by briefs-finance's own LLM
scoring) — pulling out their concrete, *quantitative* stated criteria rather than
inventing new ones:

- Graham (graham.md): "Price not more than 1.5x book value, or combined P/E x P/B <
  22.5" — the actual Graham Number formula, not an arbitrary PE cutoff. Also
  explicitly: "Earnings power and assets matter; price momentum does not" — direct
  confirmation that raw rising-price momentum is NOT a value signal.
- Lynch (lynch.md): "PEG ratio: P/E divided by growth rate — PEG < 1 is attractive."
- Buffett (buffett.md) / Smith (smith.md): "High return on equity (15%+
  consistently)" / "ROCE consistently above 15%" — both independently state the same
  15% threshold. Paired with "pay a fair price" (Buffett) — quality at a fair price,
  not quality at any price.
- Marks (marks.md) / Neilson (neilson.md): "asset is unloved, under-owned, or out of
  favour" / "trades at a significant discount... for non-structural reasons" — a
  price decline is only a signal when the business itself isn't the problem, which is
  exactly what the "no active flags elsewhere" gate below enforces.
- Munger (munger.md): "thesis provides multiple independent reasons to buy
  (confluence)" — reflected below by noting when 2+ signals align.

All signals below are gated on the ticker having NO active "flag" verdict among the
other 7 checks in the same assessment (dividend cut, balance sheet stress, rich
valuation, etc.) — Marks' risk-first framing and Munger's inversion ("what could go
wrong before what could go right") both argue you shouldn't call something an
opportunity while it has a live, unresolved problem. concentration is explicitly
excluded from this gate — Shaun already ruled sector overlap out of scope here
("it doesn't matter if I have another holding in the same sector... I can make the
choice myself by asking you to deeply compare them").

Fix history:
- 2026-07-19: BRK-B's yfinance priceToBook (0.00097, a dual-share-class data mismatch)
  made the Graham Number leg fire on garbage data — added OPPORTUNITY_MIN_PLAUSIBLE_PB
  floor.
- 2026-07-19: a full-watchlist sweep found TLT (PE -4226.0), LAND, and JOBY all firing
  the Graham PE-fallback leg on deeply negative PE — negative PE means negative
  earnings, not "cheap". The primary Graham-Number leg already required pe > 0; the
  fallback leg didn't. Both valuation.py and this file's fallback now require pe > 0.
"""

from __future__ import annotations

from typing import Any

from .. import config
from . import CheckResult


def check(
    data,
    other_checks: list[CheckResult],
    briefs_score: dict[str, Any] | None,
    recent_return_pct: float | None,
) -> CheckResult:
    if data is None:
        return CheckResult(name="opportunity", verdict="unknown", detail="No market data available")

    has_active_flag = any(c.verdict == "flag" for c in other_checks if c.name != "concentration")
    if has_active_flag:
        return CheckResult(
            name="opportunity", verdict="ok",
            detail="Active risk flag(s) present elsewhere this run — not calling this "
                   "an opportunity regardless of price or valuation",
        )

    reasons = []

    pe = data.info.get("trailingPE") or data.info.get("forwardPE")
    pb = data.info.get("priceToBook")
    # Yahoo's priceToBook is unreliable for dual-share-class companies -- verified
    # 2026-07-19 against BRK-B: bookValue returned was BRK-A's per-share book value
    # ($505,559) divided against BRK-B's price ($490.91), producing a nonsense
    # near-zero P/B (0.00097) that made the Graham Number leg fire on garbage data.
    # Real P/B for a legitimate company is essentially never below this floor.
    pb_plausible = pb is not None and pb >= config.OPPORTUNITY_MIN_PLAUSIBLE_PB
    if pe is not None and pb_plausible and pe > 0 and pe * pb < config.OPPORTUNITY_GRAHAM_NUMBER_MAX:
        reasons.append(f"Graham [PE {pe:.1f} x P/B {pb:.2f} = {pe * pb:.1f}, below {config.OPPORTUNITY_GRAHAM_NUMBER_MAX}]")
    elif pe is not None and 0 < pe <= config.PE_CHEAP_THRESHOLD:
        reasons.append(f"Graham [PE {pe:.1f} at/below cheap threshold ({config.PE_CHEAP_THRESHOLD}), P/B unavailable/implausible]")

    peg = data.info.get("pegRatio") or data.info.get("trailingPegRatio")
    if peg is not None and 0 < peg <= config.OPPORTUNITY_PEG_MAX:
        reasons.append(f"Lynch [PEG {peg:.2f} at/below {config.OPPORTUNITY_PEG_MAX} — growth at a reasonable price]")

    roe = data.info.get("returnOnEquity")
    already_rich = pe is not None and pe >= config.PE_RICH_THRESHOLD
    if roe is not None and roe * 100 >= config.OPPORTUNITY_ROE_MIN_PCT and not already_rich:
        reasons.append(f"Buffett/Smith [ROE {roe * 100:.1f}% at/above {config.OPPORTUNITY_ROE_MIN_PCT}%, not richly valued]")

    if recent_return_pct is not None and recent_return_pct <= -config.OPPORTUNITY_DIP_FLAG_PCT:
        reasons.append(
            f"Marks/Neilson [down {recent_return_pct:.1f}% over 3 months with no other "
            f"flags — possible overreaction, not a fundamental problem]"
        )

    if briefs_score is not None and briefs_score["score"] >= config.OPPORTUNITY_SCORE_FLAG:
        provisional = " (provisional)" if briefs_score["provisional"] else ""
        reasons.append(f"Briefs Finance [score {briefs_score['score']}/100{provisional}]")

    if reasons:
        confluence = f" ({len(reasons)} independent signals)" if len(reasons) > 1 else ""
        return CheckResult(
            name="opportunity", verdict="interesting",
            detail="; ".join(reasons) + confluence, data={"reasons": reasons},
        )
    return CheckResult(name="opportunity", verdict="ok", detail="No standout positive signal this run")
