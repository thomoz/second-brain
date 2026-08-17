"""BBW-percentile-squeeze + 50DMA-cross-and-slope combined heartbeat signal --
Goat Phase 3's stock-level entry check. See goat/config.py for threshold sourcing
and .agent/plans/goat-phase3-heartbeat-scanner.md's "RESEARCH RESOLVED" section for
why BBW-percentile-squeeze was chosen over Minervini's VCP.

bollinger_width_series ports gold_technicals.compute_bollinger's width_pct formula
to a *_series() form (that module's own documented "*_series() full history +
compute_*() latest-value wrapper" convention) -- needed here because heartbeat
detection must look back over the whole trailing window, not just today's value.

The breakout leg (cross+slope) is a deliberate second, independent copy of
sector_rotation.check_sector_breakout's sign-flip cross-detection idiom, not an
import of its internals -- matches this codebase's own already-accepted
duplication precedent between macro_indicators.check_gold_trend() and
sector_rotation.check_sector_breakout() (see macro_indicators.py's docstring).
Do not refactor either into a shared helper as a side effect of this module."""

from __future__ import annotations

import pandas as pd
from mytrader.checks import CheckResult

from . import config


def bollinger_width_series(close: pd.Series) -> pd.Series:
    period = config.GOAT_HEARTBEAT_BBW_PERIOD_DAYS
    mid = close.rolling(period).mean()
    std = close.rolling(period).std()
    upper = mid + config.GOAT_HEARTBEAT_BBW_STD_MULTIPLIER * std
    lower = mid - config.GOAT_HEARTBEAT_BBW_STD_MULTIPLIER * std
    return (upper - lower) / mid * 100


def _is_in_squeeze(bbw: pd.Series) -> pd.Series:
    """True where BBW sits at/below its own trailing
    GOAT_HEARTBEAT_BBW_PERCENTILE_LOOKBACK_DAYS-day GOAT_HEARTBEAT_BBW_PERCENTILE
    percentile. .fillna(False) so early-history NaN rows (rolling window not yet
    full) never count as "in squeeze" by accident -- would otherwise silently
    inflate the squeeze fraction for tickers near the edge of their available
    history."""
    threshold = bbw.rolling(config.GOAT_HEARTBEAT_BBW_PERCENTILE_LOOKBACK_DAYS).quantile(
        config.GOAT_HEARTBEAT_BBW_PERCENTILE / 100
    )
    return (bbw <= threshold).fillna(False)


def check_heartbeat_breakout(ticker: str, sector_label: str, close: pd.Series) -> CheckResult:
    """Flags 'interesting' (never 'flag' -- an opportunity signal, matching
    mytrader/checks/opportunity.py's verdict convention) only when BOTH legs pass:
    (a) a sustained BBW-percentile squeeze over the GOAT_HEARTBEAT_MIN_DURATION_DAYS
    window immediately before the most recent 50DMA cross, and (b) that cross is a
    fresh cross-above with the 50DMA now sloping up (the same webinar Step 1 idiom
    sector_rotation.check_sector_breakout already implements for sector ETFs)."""
    min_len = (
        config.GOAT_HEARTBEAT_BBW_PERCENTILE_LOOKBACK_DAYS
        + config.GOAT_HEARTBEAT_MIN_DURATION_DAYS
    )
    if len(close) < min_len:
        return CheckResult(
            name="heartbeat_breakout", verdict="unknown",
            detail=f"{ticker} ({sector_label}): insufficient price history for a "
                   f"heartbeat check (needs {min_len} trading days)",
        )

    ma50 = close.rolling(config.GOAT_SECTOR_MA_SHORT_DAYS).mean()
    diff = (close - ma50).dropna()
    sign = diff.gt(0).astype(int) - diff.lt(0).astype(int)
    sign_changed = sign.diff().fillna(0) != 0
    sign_changes = sign[sign_changed]

    slope_up = bool(
        ma50.iloc[-1] > ma50.iloc[-1 - config.GOAT_SECTOR_SLOPE_LOOKBACK_DAYS]
    )

    bbw = bollinger_width_series(close)
    in_squeeze = _is_in_squeeze(bbw)

    if sign_changes.empty:
        return CheckResult(
            name="heartbeat_breakout", verdict="ok",
            detail=f"{ticker} ({sector_label}): no 50DMA cross in available history; "
                   f"MA currently {'rising' if slope_up else 'falling'}",
        )

    cross_date = sign_changes.index[-1]
    crossed_above = bool(sign_changes.iloc[-1] > 0)
    cross_pos = close.index.get_loc(cross_date)
    trading_days_since_cross = (len(close) - 1) - cross_pos
    fresh = trading_days_since_cross <= config.GOAT_SECTOR_CROSS_RECENCY_DAYS

    pre_cross_window = in_squeeze.iloc[:cross_pos].tail(config.GOAT_HEARTBEAT_MIN_DURATION_DAYS)
    squeeze_fraction = (
        float(pre_cross_window.mean()) if len(pre_cross_window) > 0 else 0.0
    )
    sustained_squeeze = (
        len(pre_cross_window) >= config.GOAT_HEARTBEAT_MIN_DURATION_DAYS
        and squeeze_fraction >= config.GOAT_HEARTBEAT_SQUEEZE_MIN_FRACTION
    )

    data = {
        "bbw_pct": round(float(bbw.iloc[-1]), 2) if pd.notna(bbw.iloc[-1]) else None,
        "squeeze_fraction": round(squeeze_fraction, 2),
        "cross_date": cross_date.date().isoformat(),
        "crossed_above": crossed_above,
        "trading_days_since_cross": trading_days_since_cross,
        "slope_up": slope_up,
    }

    if crossed_above and slope_up and fresh and sustained_squeeze:
        detail = (
            f"{ticker} ({sector_label}): sustained low-volatility consolidation "
            f"({squeeze_fraction * 100:.0f}% of the prior "
            f"{config.GOAT_HEARTBEAT_MIN_DURATION_DAYS} trading days in a BBW squeeze) "
            f"followed by a breakout above its {config.GOAT_SECTOR_MA_SHORT_DAYS}-day MA "
            f"{trading_days_since_cross} trading day(s) ago, MA now sloping up -- "
            f"heartbeat entry signal (webinar Step 1)"
        )
        return CheckResult(name="heartbeat_breakout", verdict="interesting", detail=detail, data=data)

    direction = "crossed above" if crossed_above else "crossed below"
    reason = "no sustained consolidation before the cross" if not sustained_squeeze else "not a fresh/rising cross"
    return CheckResult(
        name="heartbeat_breakout", verdict="ok",
        detail=f"{ticker} ({sector_label}): {direction} its "
               f"{config.GOAT_SECTOR_MA_SHORT_DAYS}-day MA {trading_days_since_cross} "
               f"trading day(s) ago (MA {'rising' if slope_up else 'falling'}) -- {reason}, "
               f"not (yet) a heartbeat entry",
        data=data,
    )
