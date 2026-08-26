"""Tight-base ("heartbeat") + 50DMA-cross-and-slope combined entry signal --
Goat Phase 3's stock-level entry check, with its consolidation leg redesigned
2026-08-26 (see .agent/plans/goat-heartbeat-quiet-redesign.md and
investments/goat/heartbeat-quiet-redesign-handoff.md).

The old BBW-percentile squeeze measured "quiet" against each ticker's own
trailing 252-trading-day Bollinger BandWidth percentile -- structurally unable
to pass on the ~343 trading days the scanner fetches (it flagged zero candidates
on every run 2026-08-17 -> 2026-08-26, quiet score pinned near 0.00 for 42 of 42
hand-checked large caps). It is replaced here by three direct, recent-window,
close-only tests:

  1. Base range -- the high-low close range over the GOAT_HEARTBEAT_MIN_DURATION_DAYS
     base window is a small percent of the base's own mean.
  2. Base smoothness -- most of the base-window closes sit inside a tighter inner
     band around the base mean (the webinar's "smooth up-down-up-down" shape).
  3. Position of strength -- during the base, price held at/above its 150-day MA
     (small dip tolerance) with that 150-day MA flat-to-rising, and price spent
     most of the base at/below its 50-day MA so the breakout is a genuine reclaim.

No trailing-year self-percentile anchor anywhere -- every measure reads off the
recent past the way the pattern reads off a chart.

The breakout leg (a fresh cross up through the 50-day MA with that MA sloping up)
is unchanged. It is a deliberate second, independent copy of
sector_rotation.check_sector_breakout's sign-flip cross-detection idiom, not an
import of its internals -- matches this codebase's own already-accepted
duplication precedent between macro_indicators.check_gold_trend() and
sector_rotation.check_sector_breakout() (see macro_indicators.py's docstring).
Do not refactor either into a shared helper as a side effect of this module.

The price series (price_history.fetch_close_history) is close-only -- there is
no intraday high/low -- so every "range" here is a close-to-close range."""

from __future__ import annotations

import pandas as pd
from mytrader.checks import CheckResult

from . import config


def check_heartbeat_breakout(ticker: str, sector_label: str, close: pd.Series) -> CheckResult:
    """Flags 'interesting' (never 'flag' -- an opportunity signal, matching
    mytrader/checks/opportunity.py's verdict convention) only when ALL of:
    (a) a tight sideways base over the GOAT_HEARTBEAT_MIN_DURATION_DAYS window of
    closes ending the day before the most recent 50DMA cross -- narrow high-low
    range AND smooth (most days inside a tighter inner band); (b) that base sat in
    a position of strength -- price held at/above its 150-day MA (small dip
    tolerance) with the 150-day MA flat-to-rising, and price spent most of the base
    at/below its 50-day MA; (c) a fresh cross up through the 50-day MA within the
    last GOAT_SECTOR_CROSS_RECENCY_DAYS trading days with the 50-day MA sloping up
    (the same webinar Step 1 idiom sector_rotation.check_sector_breakout implements
    for sector ETFs), and price at/above its 150-day MA on that breakout bar."""
    base_window = config.GOAT_HEARTBEAT_MIN_DURATION_DAYS
    min_len = (
        config.GOAT_MA_LONG_DAYS
        + base_window
        + config.GOAT_HEARTBEAT_MA_LONG_SLOPE_LOOKBACK_DAYS
        + config.GOAT_SECTOR_CROSS_RECENCY_DAYS
    )
    if len(close) < min_len:
        return CheckResult(
            name="heartbeat_breakout", verdict="unknown",
            detail=f"{ticker} ({sector_label}): insufficient price history for a "
                   f"heartbeat check (needs {min_len} trading days, has {len(close)})",
        )

    ma50 = close.rolling(config.GOAT_SECTOR_MA_SHORT_DAYS).mean()
    ma150 = close.rolling(config.GOAT_MA_LONG_DAYS).mean()

    # --- 50DMA cross detection: ported verbatim from sector_rotation.check_sector_breakout ---
    diff = (close - ma50).dropna()
    sign = diff.gt(0).astype(int) - diff.lt(0).astype(int)
    sign_changed = sign.diff().fillna(0) != 0
    sign_changes = sign[sign_changed]

    slope_up_50 = bool(
        ma50.iloc[-1] > ma50.iloc[-1 - config.GOAT_SECTOR_SLOPE_LOOKBACK_DAYS]
    )

    if sign_changes.empty:
        return CheckResult(
            name="heartbeat_breakout", verdict="ok",
            detail=f"{ticker} ({sector_label}): no 50-day MA cross in available history; "
                   f"50-day MA currently {'rising' if slope_up_50 else 'falling'}",
        )

    cross_date = sign_changes.index[-1]
    crossed_above = bool(sign_changes.iloc[-1] > 0)
    cross_pos = close.index.get_loc(cross_date)
    trading_days_since_cross = (len(close) - 1) - cross_pos
    fresh = trading_days_since_cross <= config.GOAT_SECTOR_CROSS_RECENCY_DAYS

    # Bail before computing base metrics if the breakout leg can't pass -- avoids
    # NaN-slice edge cases when an old downside cross would put the base window
    # before the 150DMA warm-up.
    if not crossed_above or not fresh:
        direction = "crossed above" if crossed_above else "crossed below"
        return CheckResult(
            name="heartbeat_breakout", verdict="ok",
            detail=f"{ticker} ({sector_label}): last 50-day MA event was a {direction} "
                   f"{trading_days_since_cross} trading day(s) ago "
                   f"(fresh window is {config.GOAT_SECTOR_CROSS_RECENCY_DAYS} days) -- "
                   f"not a fresh breakout, not a heartbeat entry",
            data={"crossed_above": crossed_above,
                  "trading_days_since_cross": trading_days_since_cross,
                  "slope_up": slope_up_50},
        )

    # --- base window: the `base_window` closes ending the day BEFORE the cross ---
    base_close = close.iloc[:cross_pos].tail(base_window)
    base_ma50 = ma50.iloc[:cross_pos].tail(base_window)
    base_ma150 = ma150.iloc[:cross_pos].tail(base_window)
    # min_len guarantees these are full-length and NaN-free, but guard anyway:
    if len(base_close) < base_window or base_ma150.isna().any() or float(base_close.mean()) <= 0:
        return CheckResult(
            name="heartbeat_breakout", verdict="unknown",
            detail=f"{ticker} ({sector_label}): base window not fully covered by price "
                   f"history / 150-day MA -- cannot assess the heartbeat base",
        )

    base_mean = float(base_close.mean())
    base_range_pct = float(base_close.max() - base_close.min()) / base_mean * 100
    inner = config.GOAT_HEARTBEAT_BASE_INNER_BAND_PCT / 100
    within_inner = ((base_close - base_mean).abs() / base_mean) <= inner
    smoothness_fraction = float(within_inner.mean())
    below_ma50_fraction = float((base_close <= base_ma50).mean())

    # positive pct_below == price is BELOW the MA (exit_check.py sign convention)
    base_pct_below_ma150 = (base_ma150 - base_close) / base_ma150 * 100
    max_dip_below_ma150_pct = float(base_pct_below_ma150.max())
    price_pct_below_ma150_now = float((ma150.iloc[-1] - close.iloc[-1]) / ma150.iloc[-1] * 100)
    ma150_slope_up = bool(
        ma150.iloc[-1] >= ma150.iloc[-1 - config.GOAT_HEARTBEAT_MA_LONG_SLOPE_LOOKBACK_DAYS]
    )

    base_is_narrow = base_range_pct <= config.GOAT_HEARTBEAT_BASE_RANGE_MAX_PCT
    base_is_smooth = smoothness_fraction >= config.GOAT_HEARTBEAT_BASE_SMOOTHNESS_MIN_FRACTION
    base_reclaims_ma50 = below_ma50_fraction >= config.GOAT_HEARTBEAT_BASE_BELOW_MA50_MIN_FRACTION
    held_above_ma150 = max_dip_below_ma150_pct <= config.GOAT_HEARTBEAT_MA_LONG_TOLERANCE_PCT
    above_ma150_now = price_pct_below_ma150_now <= 0

    data = {
        "base_range_pct": round(base_range_pct, 2),
        "base_smoothness_fraction": round(smoothness_fraction, 2),
        "base_below_ma50_fraction": round(below_ma50_fraction, 2),
        "max_dip_below_ma150_pct": round(max_dip_below_ma150_pct, 2),
        "price_vs_ma150_now_pct": round(-price_pct_below_ma150_now, 2),  # +ve == above
        "ma150_slope_up": ma150_slope_up,
        "cross_date": cross_date.date().isoformat(),
        "crossed_above": crossed_above,
        "trading_days_since_cross": trading_days_since_cross,
        "slope_up": slope_up_50,  # key name kept -- existing tests / data convention
    }

    base_ok = (
        base_is_narrow and base_is_smooth and base_reclaims_ma50
        and held_above_ma150 and above_ma150_now and ma150_slope_up
    )
    if base_ok and slope_up_50:
        detail = (
            f"{ticker} ({sector_label}): {base_window} trading days of tight sideways "
            f"consolidation before the breakout -- {base_range_pct:.1f}% high-low close range "
            f"vs. the {config.GOAT_HEARTBEAT_BASE_RANGE_MAX_PCT:.0f}% ceiling (tighter is "
            f"better), {smoothness_fraction * 100:.0f}% of days inside the smooth inner band, "
            f"price at/below its 50-day MA on {below_ma50_fraction * 100:.0f}% of base days -- "
            f"held at/above its 150-day MA throughout (worst dip {max_dip_below_ma150_pct:.1f}% "
            f"below, within the {config.GOAT_HEARTBEAT_MA_LONG_TOLERANCE_PCT:.0f}% tolerance) "
            f"with that 150-day MA flat-to-rising. Then a fresh cross above the 50-day MA "
            f"{trading_days_since_cross} trading day(s) ago, 50-day MA now sloping up -- "
            f"heartbeat entry signal (webinar Step 1)"
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
    if not base_reclaims_ma50:
        reasons.append(
            f"price was at/below its 50-day MA on only {below_ma50_fraction * 100:.0f}% of base "
            f"days, so the cross-up is not a clear reclaim"
        )
    if not held_above_ma150:
        reasons.append(
            f"price dipped {max_dip_below_ma150_pct:.1f}% below its 150-day MA during the base, "
            f"past the {config.GOAT_HEARTBEAT_MA_LONG_TOLERANCE_PCT:.0f}% tolerance"
        )
    if not above_ma150_now:
        reasons.append("price is below its 150-day MA on the breakout bar")
    if not ma150_slope_up:
        reasons.append("the 150-day MA is still sloping down")
    if not slope_up_50:
        reasons.append("the 50-day MA is not yet sloping up")

    return CheckResult(
        name="heartbeat_breakout", verdict="ok",
        detail=f"{ticker} ({sector_label}): fresh cross above the 50-day MA "
               f"{trading_days_since_cross} trading day(s) ago, but not (yet) a heartbeat entry -- "
               + "; ".join(reasons),
        data=data,
    )
