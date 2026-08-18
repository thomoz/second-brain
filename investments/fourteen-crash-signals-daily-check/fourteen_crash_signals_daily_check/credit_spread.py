"""Marker 14 -- high-yield credit spread streak, "the video's own single most
reliable historical marker". Deliberately separate from
mytrader.macro_indicators.check_credit_spreads (a different consumer's
single-day, 5.0pp check) -- this needs a duration condition (>=3.5% held for
~a month) that function doesn't compute. Both read the same FRED series via
scripts.macro's low-level helpers -- see the Phase 1 plan's Design Decision #2."""

from __future__ import annotations

from datetime import date, timedelta

from mytrader.checks import CheckResult
from scripts.macro import fred_series_range

from . import config


def check_credit_spread_streak() -> CheckResult:
    today = date.today()
    history = fred_series_range(
        config.SIGNALS_CREDIT_SPREAD_SERIES,
        today - timedelta(days=config.SIGNALS_CREDIT_SPREAD_LOOKBACK_DAYS),
        today,
    )
    if not history:
        return CheckResult(
            name="credit_spread_streak", verdict="unknown",
            detail="FRED high-yield credit spread data unavailable (FRED_API_KEY not set, or series unavailable)",
        )

    streak_days = 0
    for _, value in reversed(history):  # walk backward from most recent -- history is ascending
        if value >= config.SIGNALS_CREDIT_SPREAD_STREAK_FLAG_PCT:
            streak_days += 1
        else:
            break

    latest_date, latest_value = history[-1]
    if streak_days >= config.SIGNALS_CREDIT_SPREAD_STREAK_TRADING_DAYS:
        return CheckResult(
            name="credit_spread_streak", verdict="flag",
            detail=f"ICE BofA US HY OAS at {latest_value:.2f}pp (as of {latest_date.isoformat()}), "
                   f"at/above {config.SIGNALS_CREDIT_SPREAD_STREAK_FLAG_PCT:.1f}pp for {streak_days} "
                   f"trading day(s) -- the video's single most reliable historical marker",
            data={"value": latest_value, "streak_days": streak_days, "as_of": latest_date.isoformat()},
        )
    watch = latest_value >= config.SIGNALS_CREDIT_SPREAD_WATCH_PCT
    detail = (
        f"ICE BofA US HY OAS at {latest_value:.2f}pp (as of {latest_date.isoformat()}); "
        f"{streak_days} consecutive day(s) at/above {config.SIGNALS_CREDIT_SPREAD_STREAK_FLAG_PCT:.1f}pp "
        f"(needs {config.SIGNALS_CREDIT_SPREAD_STREAK_TRADING_DAYS} to flag)"
    )
    if watch:
        gap = config.SIGNALS_CREDIT_SPREAD_STREAK_FLAG_PCT - config.SIGNALS_CREDIT_SPREAD_WATCH_PCT
        detail += f" -- WATCH: within {gap:.1f}pp of the flag threshold"
    return CheckResult(
        name="credit_spread_streak", verdict="ok", detail=detail,
        data={"value": latest_value, "streak_days": streak_days, "as_of": latest_date.isoformat(), "watch": watch},
    )
