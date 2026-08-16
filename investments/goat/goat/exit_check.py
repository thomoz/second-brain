"""The 150-day-MA holdings exit-rule detector -- Goat Phase 1's one genuinely new
check. See goat/config.py for the threshold sourcing rationale."""

from __future__ import annotations

import pandas as pd
from mytrader.checks import CheckResult

from . import config


def check_150dma_exit(ticker: str, close: pd.Series) -> CheckResult:
    """Flags when `ticker`'s daily close has stayed >= GOAT_150DMA_FLAG_PCT below
    its GOAT_MA_LONG_DAYS-day moving average for the most recent
    GOAT_150DMA_MIN_CONSECUTIVE_DAYS+ consecutive trading days -- looks only at the
    *current* tail state, not whether this has ever happened in the ticker's
    history."""
    min_len = config.GOAT_MA_LONG_DAYS + config.GOAT_150DMA_MIN_CONSECUTIVE_DAYS
    if len(close) < min_len:
        return CheckResult(
            name="below_150dma", verdict="unknown",
            detail=f"{ticker}: insufficient price history for a "
                   f"{config.GOAT_MA_LONG_DAYS}-day MA",
        )

    ma = close.rolling(config.GOAT_MA_LONG_DAYS).mean()
    pct_below = ((ma - close) / ma * 100).dropna()

    qualifies = pct_below >= config.GOAT_150DMA_FLAG_PCT
    flagged = bool(qualifies.tail(config.GOAT_150DMA_MIN_CONSECUTIVE_DAYS).all())

    latest_pct_below = float(pct_below.iloc[-1])
    data = {
        "pct_below": latest_pct_below,
        "ma": float(ma.iloc[-1]),
        "price": float(close.iloc[-1]),
    }

    if flagged:
        # Deliberately separates the magnitude (today's snapshot, latest_pct_below)
        # from the duration (how long the >= FLAG_PCT condition has held) -- an
        # earlier phrasing folded both into one "closed X% below ... for N+
        # consecutive days" sentence, which read as if X% applied on each of the N
        # days and accumulated (it doesn't; X% is today only, N is a separate
        # persistence check). Shaun flagged the ambiguity 2026-08-16.
        return CheckResult(
            name="below_150dma", verdict="flag",
            detail=f"{ticker}: now {latest_pct_below:.1f}% below its "
                   f"{config.GOAT_MA_LONG_DAYS}-day MA as of today's close; has stayed "
                   f">={config.GOAT_150DMA_FLAG_PCT:.0f}% below for "
                   f"{config.GOAT_150DMA_MIN_CONSECUTIVE_DAYS}+ consecutive trading days -- "
                   f"exit-rule threshold (Stage Analysis 6% envelope) triggered",
            data=data,
        )
    return CheckResult(
        name="below_150dma", verdict="ok",
        detail=f"{ticker}: {abs(latest_pct_below):.1f}% "
               f"{'below' if latest_pct_below > 0 else 'above'} its "
               f"{config.GOAT_MA_LONG_DAYS}-day MA",
        data=data,
    )
