"""Tight-base ("heartbeat") entry signal -- Goat Phase 3's stock-level entry
check, with its consolidation leg redesigned 2026-08-26 (see
.agent/plans/goat-heartbeat-quiet-redesign.md and
investments/goat/heartbeat-quiet-redesign-handoff.md), redesigned again
2026-09-20 to drop every moving-average-relative gate, and redesigned a third
time the same day to drop the breakout requirement entirely per Shaun: he does
not require the stock to have already broken out of its base -- in fact he'd
rather see it before it has, since that is the earlier, quieter entry. The
instruction was explicitly to drop the requirement, not to flip it into a
"must not have broken out yet" gate -- so a ticker mid-breakout still qualifies
too, this check simply no longer looks at or cares about breakout status at
all.

What remains is purely the base itself -- the most recent
GOAT_HEARTBEAT_MIN_DURATION_DAYS closes:

  1. Base range -- the high-low close range over that window is a small percent
     of the window's own mean.
  2. Base smoothness -- most of the window's closes sit inside a tighter inner
     band around its own mean (the webinar's "smooth up-down-up-down" shape).

No moving average and no breakout/cross event is consulted anywhere in this
check. The price series (price_history.fetch_close_history) is close-only --
there is no intraday high/low -- so every "range" here is a close-to-close
range."""

from __future__ import annotations

import pandas as pd
from mytrader.checks import CheckResult

from . import config


def check_heartbeat_breakout(ticker: str, sector_label: str, close: pd.Series) -> CheckResult:
    """Flags 'interesting' (never 'flag' -- an opportunity signal, matching
    mytrader/checks/opportunity.py's verdict convention) only when the most
    recent GOAT_HEARTBEAT_MIN_DURATION_DAYS closes form a tight, smooth sideways
    base -- narrow high-low range AND most days sitting inside a tighter inner
    band around the base's own mean. Whether the stock has since broken out of
    that base is neither required nor excluded -- not evaluated at all."""
    base_window = config.GOAT_HEARTBEAT_MIN_DURATION_DAYS
    if len(close) < base_window:
        return CheckResult(
            name="heartbeat_breakout", verdict="unknown",
            detail=f"{ticker} ({sector_label}): insufficient price history for a "
                   f"heartbeat check (needs {base_window} trading days, has {len(close)})",
        )

    base_close = close.tail(base_window)
    base_mean = float(base_close.mean())
    if base_mean <= 0:
        return CheckResult(
            name="heartbeat_breakout", verdict="unknown",
            detail=f"{ticker} ({sector_label}): base window has a non-positive mean close "
                   f"-- cannot assess the heartbeat base",
        )

    base_range_pct = float(base_close.max() - base_close.min()) / base_mean * 100
    inner = config.GOAT_HEARTBEAT_BASE_INNER_BAND_PCT / 100
    within_inner = ((base_close - base_mean).abs() / base_mean) <= inner
    smoothness_fraction = float(within_inner.mean())

    base_high = float(base_close.max())
    pct_below_base_high = (base_high - float(close.iloc[-1])) / base_high * 100

    base_is_narrow = base_range_pct <= config.GOAT_HEARTBEAT_BASE_RANGE_MAX_PCT
    base_is_smooth = smoothness_fraction >= config.GOAT_HEARTBEAT_BASE_SMOOTHNESS_MIN_FRACTION

    data = {
        "base_range_pct": round(base_range_pct, 2),
        "base_smoothness_fraction": round(smoothness_fraction, 2),
        "pct_below_base_high": round(pct_below_base_high, 2),  # 0 or negative == already at/above it
    }

    if base_is_narrow and base_is_smooth:
        position = (
            "already at/above the top of its own range -- may already be breaking out"
            if pct_below_base_high <= 0
            else f"currently {pct_below_base_high:.1f}% below the top of its own range -- no breakout yet"
        )
        detail = (
            f"{ticker} ({sector_label}): {base_window} trading days of tight sideways "
            f"consolidation -- {base_range_pct:.1f}% high-low close range vs. the "
            f"{config.GOAT_HEARTBEAT_BASE_RANGE_MAX_PCT:.0f}% ceiling (tighter is better), "
            f"{smoothness_fraction * 100:.0f}% of days inside the smooth inner band -- {position} "
            f"-- heartbeat entry signal"
        )
        return CheckResult(name="heartbeat_breakout", verdict="interesting", detail=detail, data=data)

    reasons = []
    if not base_is_narrow:
        reasons.append(
            f"base high-low close range {base_range_pct:.1f}% exceeds the "
            f"{config.GOAT_HEARTBEAT_BASE_RANGE_MAX_PCT:.0f}% tightness ceiling"
        )
    if not base_is_smooth:
        reasons.append(
            f"only {smoothness_fraction * 100:.0f}% of base days sit inside the smooth inner "
            f"band (need {config.GOAT_HEARTBEAT_BASE_SMOOTHNESS_MIN_FRACTION * 100:.0f}%)"
        )

    return CheckResult(
        name="heartbeat_breakout", verdict="ok",
        detail=f"{ticker} ({sector_label}): not (yet) a heartbeat base -- " + "; ".join(reasons),
        data=data,
    )
