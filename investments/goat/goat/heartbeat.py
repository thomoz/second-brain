"""Tight-base ("heartbeat") entry signal -- Goat Phase 3's stock-level entry
check, with its consolidation leg redesigned 2026-08-26 (see
.agent/plans/goat-heartbeat-quiet-redesign.md and
investments/goat/heartbeat-quiet-redesign-handoff.md), redesigned again
2026-09-20 (three more times, same day) to drop every moving-average-relative
gate, then to drop the breakout requirement entirely, then to extend the base
window and reject a broken-down base. Per Shaun: he does not require the stock
to have already broken out of its base -- in fact he'd rather see it before it
has, since that is the earlier, quieter entry. The instruction was explicitly
to drop the requirement, not to flip it into a "must not have broken out yet"
gate -- so a ticker mid-breakout still qualifies too, this check simply no
longer looks at or cares about breakout status at all.

The window extension (63 -> GOAT_HEARTBEAT_MIN_DURATION_DAYS trading days) and
the breakdown rejection below both came from one real bad result: BAC and CAH
both rallied hard over ~2 months then reversed sharply (BAC's RSI went from
~70 to ~29 in the same window) -- at the old 63-day window that whole
round-trip still measured as a 12-13% range with 100% "smoothness", because
both metrics are dispersion-from-the-window's-own-mean, blind to trend
direction or where in the window the move landed. Confirmed live 2026-09-20:
re-running the same two tickers with a 126-day window pushed both to a
30%+ range and well under 80% smoothness -- a clean, decisive fail instead of
a narrow accidental pass.

What remains is purely the base itself -- the most recent
GOAT_HEARTBEAT_MIN_DURATION_DAYS closes:

  1. Base range -- the high-low close range over that window is a small percent
     of the window's own mean.
  2. Base smoothness -- most of the window's closes sit inside a tighter inner
     band around its own mean (the webinar's "smooth up-down-up-down" shape).
  3. Not broken down -- the most recent GOAT_HEARTBEAT_BREAKDOWN_RECENT_DAYS
     closes have not fallen below the settled (older) part of the base's own
     low. A stock currently making a fresh low below where its base had been
     trading is a breakdown, not a quiet base worth watching, regardless of
     what the range/smoothness stats say -- asymmetric with the breakout side
     on purpose (a breakout is fine/expected per the redesign above; a
     breakdown isn't). Deliberately NOT "is today the single lowest close in
     the window" -- in a genuinely quiet, choppy base some day is always going
     to be the low by chance, and that alone shouldn't disqualify it; only a
     recent multi-day move below the settled range should.
  4. Real rhythm, not a single arc -- added 2026-09-20 after Shaun shared real
     "great heartbeat" examples (XLE, SMH, XBI): the common thread across all
     three wasn't just a narrow range, it was several distinct, repeated
     up-down swings within that range over many months -- an actual rhythm,
     like an EKG trace. Range and smoothness alone can't tell a genuine
     multi-swing rhythm apart from one smooth, single-direction drift that
     happens to stay within tolerance (which is exactly how BAC/CAH slipped
     through before the window-extension fix -- a real gap this closes
     directly instead of relying on window length as a proxy). Counted via a
     ZigZag-style filter (_count_swings): walk the closes, and confirm a new
     swing only once price reverses from its running extreme by at least
     GOAT_HEARTBEAT_SWING_MIN_REVERSAL_PCT. Deliberately NOT shape-matching --
     no grading on how round, even, evenly-spaced, or symmetric each swing
     looks, only a minimum-amplitude filter so ordinary day-to-day noise
     inside a swing never gets miscounted as its own swing. Requires at least
     GOAT_HEARTBEAT_MIN_SWINGS confirmed reversals.

No moving average and no breakout-above-the-range event is consulted anywhere
in this check. The price series (price_history.fetch_close_history) is
close-only -- there is no intraday high/low -- so every "range" here is a
close-to-close range."""

from __future__ import annotations

import pandas as pd
from mytrader.checks import CheckResult

from . import config


def _count_swings(base_close: pd.Series, min_reversal_pct: float) -> int:
    """ZigZag-style swing count. Walks the closes tracking a running extreme
    (the highest close since the last confirmed swing while trending up, or
    the lowest while trending down); confirms a new swing -- and flips
    direction -- only once price reverses from that extreme by at least
    min_reversal_pct. A move smaller than that is treated as noise and simply
    absorbed into the current extreme, never confirmed as its own swing.
    Deliberately not shape-matching: no requirement on a swing's duration,
    symmetry, or evenness relative to any other swing, only its amplitude."""
    prices = base_close.to_numpy()
    if len(prices) < 2:
        return 0

    threshold = min_reversal_pct / 100.0
    trend = 1 if prices[1] >= prices[0] else -1
    extreme = float(prices[0])
    swings = 0

    for p in prices[1:]:
        p = float(p)
        if trend == 1:
            if p > extreme:
                extreme = p
            elif (extreme - p) / extreme >= threshold:
                swings += 1
                trend = -1
                extreme = p
        else:
            if p < extreme:
                extreme = p
            elif (p - extreme) / extreme >= threshold:
                swings += 1
                trend = 1
                extreme = p

    return swings


def check_heartbeat_breakout(ticker: str, sector_label: str, close: pd.Series) -> CheckResult:
    """Flags 'interesting' (never 'flag' -- an opportunity signal, matching
    mytrader/checks/opportunity.py's verdict convention) only when the most
    recent GOAT_HEARTBEAT_MIN_DURATION_DAYS closes form a tight, smooth sideways
    base -- narrow high-low range AND most days sitting inside a tighter inner
    band around the base's own mean -- AND the recent stretch of it has not
    fallen below the settled (older) part of the base's own low -- AND the
    base shows a real repeated up-down rhythm (multiple confirmed swings), not
    a single directional move. Whether the stock has broken OUT (above) that
    base is neither required nor excluded -- not evaluated at all; breaking
    DOWN below it is excluded, on purpose -- see module docstring."""
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
    last_close = float(close.iloc[-1])
    pct_below_base_high = (base_high - last_close) / base_high * 100

    # Compares the recent stretch's low against the settled (older) part of the
    # base, not "is today the single lowest close" -- in a genuinely quiet,
    # choppy base some day is always going to be the low by chance, and that
    # alone shouldn't disqualify it. Only a sustained recent move below the
    # settled range counts as a breakdown.
    recent_days = config.GOAT_HEARTBEAT_BREAKDOWN_RECENT_DAYS
    settled = base_close.iloc[:-recent_days]
    recent = base_close.iloc[-recent_days:]
    base_low_settled = float(settled.min())
    broke_down = float(recent.min()) < base_low_settled

    base_is_narrow = base_range_pct <= config.GOAT_HEARTBEAT_BASE_RANGE_MAX_PCT
    base_is_smooth = smoothness_fraction >= config.GOAT_HEARTBEAT_BASE_SMOOTHNESS_MIN_FRACTION

    swing_count = _count_swings(base_close, config.GOAT_HEARTBEAT_SWING_MIN_REVERSAL_PCT)
    has_enough_swings = swing_count >= config.GOAT_HEARTBEAT_MIN_SWINGS

    data = {
        "base_range_pct": round(base_range_pct, 2),
        "base_smoothness_fraction": round(smoothness_fraction, 2),
        "pct_below_base_high": round(pct_below_base_high, 2),  # 0 or negative == already at/above it
        "broke_down": broke_down,
        "swing_count": swing_count,
    }

    if base_is_narrow and base_is_smooth and not broke_down and has_enough_swings:
        position = (
            "already at/above the top of its own range -- may already be breaking out"
            if pct_below_base_high <= 0
            else f"currently {pct_below_base_high:.1f}% below the top of its own range -- no breakout yet"
        )
        detail = (
            f"{ticker} ({sector_label}): {base_window} trading days of tight sideways "
            f"consolidation -- {base_range_pct:.1f}% high-low close range vs. the "
            f"{config.GOAT_HEARTBEAT_BASE_RANGE_MAX_PCT:.0f}% ceiling (tighter is better), "
            f"{smoothness_fraction * 100:.0f}% of days inside the smooth inner band, "
            f"{swing_count} confirmed up-down swings (a real rhythm, not a single move) -- {position} "
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
    if broke_down:
        reasons.append(
            f"the last {recent_days} days dipped to {float(recent.min()):.2f}, below the "
            f"settled base's low of {base_low_settled:.2f} -- a breakdown, not a heartbeat"
        )
    if not has_enough_swings:
        reasons.append(
            f"only {swing_count} confirmed up-down swing(s) of >= "
            f"{config.GOAT_HEARTBEAT_SWING_MIN_REVERSAL_PCT:.0f}% within the base (need "
            f"{config.GOAT_HEARTBEAT_MIN_SWINGS}) -- looks like a single directional move, "
            f"not a repeated heartbeat rhythm"
        )

    return CheckResult(
        name="heartbeat_breakout", verdict="ok",
        detail=f"{ticker} ({sector_label}): not (yet) a heartbeat base -- " + "; ".join(reasons),
        data=data,
    )
