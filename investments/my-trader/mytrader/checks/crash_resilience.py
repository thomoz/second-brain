"""Crash-resilience check — how has this ticker actually behaved in past broad-market
drawdowns. Retrospective context, not a live health/valuation signal: verdict is
always "info" (or "unknown" with no data), and this check is deliberately NOT included
in opportunity.py's other_checks gate list — a bad crash history isn't a "flag" the
same way a dividend cut or balance-sheet stress is, it's just useful context to weigh
alongside everything else.

Prompted 2026-07-19 by a real gap found comparing dollar-store tickers: FIVE and OLLI
both "look like" defensive dollar stores by name but historically amplified market
crashes ~2x (FIVE: -59.1% in COVID vs the S&P 500's -33.9%), while DG (genuine
consumables/staples business) barely dipped (-1.1%). That distinction — same category
label, very different crash behaviour — wasn't visible anywhere in the assessment
until now.
"""

from __future__ import annotations

from .. import crash_windows
from . import CheckResult


def check(data) -> CheckResult:
    if data is None:
        return CheckResult(name="crash_resilience", verdict="unknown", detail="No market data available")

    drawdowns = crash_windows.fetch_crash_drawdowns(data.ticker)
    if not drawdowns:
        return CheckResult(
            name="crash_resilience", verdict="info",
            detail="No historical crash-window data available (likely IPO'd after all tracked windows)",
        )

    parts = [f"{d['label']} {d['drawdown_pct']:+.1f}%" for d in drawdowns]
    return CheckResult(
        name="crash_resilience", verdict="info", detail="; ".join(parts),
        data={"drawdowns": drawdowns},
    )
