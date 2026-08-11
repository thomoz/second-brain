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
        return CheckResult(
            name="below_150dma", verdict="flag",
            detail=f"{ticker}: closed {latest_pct_below:.1f}% below its "
                   f"{config.GOAT_MA_LONG_DAYS}-day MA for "
                   f"{config.GOAT_150DMA_MIN_CONSECUTIVE_DAYS}+ consecutive days -- "
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
