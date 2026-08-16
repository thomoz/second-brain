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
        # persistence check). Shaun flagged the ambiguity 2026-08-16. No longer
        # cites the Weinstein 6% envelope by name since that value is no longer
        # the live default (see config.py's 2026-08-16 override note).
        return CheckResult(
            name="below_150dma", verdict="flag",
            detail=f"{ticker}: now {latest_pct_below:.1f}% below its "
                   f"{config.GOAT_MA_LONG_DAYS}-day MA as of today's close; has stayed "
                   f">={config.GOAT_150DMA_FLAG_PCT:.0f}% below for "
                   f"{config.GOAT_150DMA_MIN_CONSECUTIVE_DAYS}+ consecutive trading day(s) -- "
                   f"150DMA exit-rule threshold triggered",
            data=data,
        )
    return CheckResult(
        name="below_150dma", verdict="ok",
        detail=f"{ticker}: {abs(latest_pct_below):.1f}% "
               f"{'below' if latest_pct_below > 0 else 'above'} its "
               f"{config.GOAT_MA_LONG_DAYS}-day MA",
        data=data,
    )


def check_150dma_exit_live(ticker: str, close: pd.Series, live_price: float) -> CheckResult:
    """Live/intraday sibling of check_150dma_exit. `close` must be historical
    daily closes for COMPLETED trading days only -- callers must strip any
    trailing same-day partial bar before calling this (see live_monitor.py's
    _completed_closes_only). `live_price` stands in for "today's close" as it
    would look at end of day, but the 150-day MA itself is computed only from
    `close` (completed days) -- it is never live-updating, matching HANDOFF's
    explicit design decision that the MA is not recomputed from partial-day
    data. Persistence (GOAT_150DMA_MIN_CONSECUTIVE_DAYS) is checked across the
    most recent (N-1) COMPLETED days plus today's live day, so this stays
    correct even if that config value is ever raised above 1."""
    n_prior_needed = config.GOAT_150DMA_MIN_CONSECUTIVE_DAYS - 1
    min_len = config.GOAT_MA_LONG_DAYS + n_prior_needed
    if len(close) < min_len:
        return CheckResult(
            name="below_150dma", verdict="unknown",
            detail=f"{ticker}: insufficient price history for a "
                   f"{config.GOAT_MA_LONG_DAYS}-day MA",
        )

    ma_today = float(close.tail(config.GOAT_MA_LONG_DAYS).mean())
    pct_below_today = (ma_today - live_price) / ma_today * 100
    today_qualifies = pct_below_today >= config.GOAT_150DMA_FLAG_PCT

    prior_qualifies = True
    if n_prior_needed > 0:
        ma = close.rolling(config.GOAT_MA_LONG_DAYS).mean()
        pct_below_hist = ((ma - close) / ma * 100).dropna()
        prior_qualifies = bool(
            (pct_below_hist.tail(n_prior_needed) >= config.GOAT_150DMA_FLAG_PCT).all()
        )

    flagged = bool(today_qualifies and prior_qualifies)
    data = {"pct_below": float(pct_below_today), "ma": ma_today, "price": float(live_price)}

    if flagged:
        return CheckResult(
            name="below_150dma", verdict="flag",
            detail=f"{ticker}: LIVE price now {pct_below_today:.1f}% below its "
                   f"{config.GOAT_MA_LONG_DAYS}-day MA (intraday -- not yet a "
                   f"confirmed close); has stayed >={config.GOAT_150DMA_FLAG_PCT:.0f}% "
                   f"below for {config.GOAT_150DMA_MIN_CONSECUTIVE_DAYS}+ trading "
                   f"day(s) including today -- 150DMA exit-rule threshold triggered",
            data=data,
        )
    return CheckResult(
        name="below_150dma", verdict="ok",
        detail=f"{ticker}: LIVE price {abs(pct_below_today):.1f}% "
               f"{'below' if pct_below_today > 0 else 'above'} its "
               f"{config.GOAT_MA_LONG_DAYS}-day MA (intraday)",
        data=data,
    )
