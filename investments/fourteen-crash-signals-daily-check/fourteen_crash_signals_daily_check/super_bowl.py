"""Marker 9 -- the Super Bowl signal. No structured free data source exists for "% of
Super Bowl ads that were AI-related" (see the Phase 2 handoff) -- a scheduled daily job
can't do the web-research pass a human/agent can. v1 scope, confirmed with Shaun
2026-08-18: a date-proximity reminder, not content automation.

Manual reset flow: once SIGNALS_NEXT_SUPER_BOWL_DATE passes, this check flags every day
until Shaun manually checks that year's post-game trade coverage (Adweek etc.) and bumps
SIGNALS_NEXT_SUPER_BOWL_DATE forward to next year's game in config.py -- the flag clears
itself the moment the constant is bumped, no separate acknowledgment table needed."""

from __future__ import annotations

from datetime import date

from mytrader.checks import CheckResult

from . import config


def check_super_bowl_signal() -> CheckResult:
    today = date.today()
    target = config.SIGNALS_NEXT_SUPER_BOWL_DATE
    if today < target:
        days_left = (target - today).days
        return CheckResult(
            name="super_bowl_signal", verdict="unknown",
            detail=f"Next Super Bowl is {target.isoformat()} ({days_left} day(s) away) -- "
                   f"ad-share content is not automatable, nothing to check yet",
            data={"next_date": target.isoformat(), "days_left": days_left},
        )
    return CheckResult(
        name="super_bowl_signal", verdict="flag",
        detail=f"Super Bowl ({target.isoformat()}) has passed -- manually check that year's "
               f"post-game trade coverage (Adweek etc.) for AI-related ad share, then bump "
               f"SIGNALS_NEXT_SUPER_BOWL_DATE forward in config.py to clear this flag",
        data={"next_date": target.isoformat()},
    )
