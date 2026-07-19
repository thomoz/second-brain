"""Dividend trend check — trailing 365-day sum vs prior 365-day window."""

from __future__ import annotations

from datetime import datetime, timedelta

from .. import config
from . import CheckResult


def check(data) -> CheckResult:
    if data is None:
        return CheckResult(name="dividend", verdict="unknown", detail="No market data available")

    dividends = data.dividends
    if dividends is None or dividends.empty:
        return CheckResult(name="dividend", verdict="info", detail="No dividend history")

    index = dividends.index
    if getattr(index, "tz", None) is not None:
        index = index.tz_localize(None)
    dividends = dividends.copy()
    dividends.index = index

    now = datetime.now()
    trailing_start = now - timedelta(days=365)
    prior_start = now - timedelta(days=730)

    trailing = float(dividends[(dividends.index > trailing_start) & (dividends.index <= now)].sum())
    prior = float(dividends[(dividends.index > prior_start) & (dividends.index <= trailing_start)].sum())

    if prior == 0:
        if trailing == 0:
            return CheckResult(
                name="dividend", verdict="info", detail="No recent dividend activity",
                data={"trailing": trailing, "prior": prior},
            )
        return CheckResult(
            name="dividend", verdict="ok", detail="New/resumed dividend, no prior-year baseline",
            data={"trailing": trailing, "prior": prior},
        )

    change_pct = (trailing - prior) / prior * 100
    if change_pct <= config.DIVIDEND_CUT_THRESHOLD_PCT:
        verdict = "flag"
        detail = f"Dividend declined {change_pct:.1f}% vs prior 12 months"
    elif change_pct > 0:
        verdict = "ok"
        detail = f"Dividend grew {change_pct:.1f}% vs prior 12 months"
    else:
        verdict = "info"
        detail = f"Dividend roughly flat ({change_pct:.1f}% vs prior 12 months)"

    return CheckResult(
        name="dividend", verdict=verdict, detail=detail,
        data={"trailing": round(trailing, 4), "prior": round(prior, 4), "change_pct": round(change_pct, 2)},
    )
