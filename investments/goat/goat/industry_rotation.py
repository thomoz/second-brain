"""Industry rotation ranking for Finviz's finer-grained industry groups -- see
.agent/plans/goat-industry-rotation-ranking.md. Direct sibling of
sector_rotation.py's fetch/rank pair, at industry rather than sector granularity.
No breakout signal here -- see that plan's "Explicitly Deferred" section."""

from __future__ import annotations

from typing import Any

import pandas as pd
from mytrader.checks import CheckResult

from . import config, price_history


def fetch_all_industry_closes() -> dict[str, pd.Series | None]:
    closes: dict[str, pd.Series | None] = {}
    for ticker in config.GOAT_INDUSTRY_ETFS:
        try:
            closes[ticker] = price_history.fetch_close_history(
                ticker, config.GOAT_INDUSTRY_HISTORY_LOOKBACK_DAYS
            )
        except Exception as e:
            print(f"[goat-industry-scan] error fetching {ticker}: {e}")
            closes[ticker] = None
    return closes


def rank_industries(closes: dict[str, pd.Series | None]) -> list[dict[str, Any]]:
    window = config.GOAT_INDUSTRY_RANK_WINDOW_TRADING_DAYS
    short_window = config.GOAT_ROTATION_SHORT_WINDOW_TRADING_DAYS
    rows: list[dict[str, Any]] = []
    for ticker, industry_label in config.GOAT_INDUSTRY_ETFS.items():
        close = closes.get(ticker)
        if close is None or len(close) < window + 1:
            rows.append({
                "ticker": ticker, "industry_label": industry_label,
                "return_pct": None, "rising": None,
                "return_pct_1w": None, "rising_1w": None,
            })
            continue
        pct = float((close.iloc[-1] / close.iloc[-(window + 1)] - 1) * 100)
        # Short-window ("this week") read -- same idiom as sector_rotation.rank_sectors.
        if len(close) < short_window + 1:
            pct_1w, rising_1w = None, None
        else:
            pct_1w = float((close.iloc[-1] / close.iloc[-(short_window + 1)] - 1) * 100)
            rising_1w = pct_1w > 0
        rows.append({
            "ticker": ticker, "industry_label": industry_label,
            "return_pct": pct, "rising": pct > 0,
            "return_pct_1w": pct_1w, "rising_1w": rising_1w,
        })
    # Rows with no data sort last, not first/interspersed.
    rows.sort(key=lambda r: (r["return_pct"] is None, -(r["return_pct"] or 0)))
    for i, row in enumerate(rows, start=1):
        row["rank"] = i
    return rows


def check_industry_breakout(ticker: str, industry_label: str, close: pd.Series) -> CheckResult:
    """Exact structural copy of sector_rotation.check_sector_breakout -- the
    signal definition isn't granularity-specific, only the universe it's
    applied to changes, so this reuses the same GOAT_SECTOR_MA_SHORT_DAYS/
    _SLOPE_LOOKBACK_DAYS/_CROSS_RECENCY_DAYS constants rather than cloning new
    GOAT_INDUSTRY_* duplicates. Per heartbeat.py's module docstring convention
    (deliberate duplication over a shared helper), this stays its own copy, not
    a refactor of check_sector_breakout."""
    min_len = config.GOAT_SECTOR_MA_SHORT_DAYS + config.GOAT_SECTOR_SLOPE_LOOKBACK_DAYS
    if len(close) < min_len:
        return CheckResult(
            name="industry_breakout", verdict="unknown",
            detail=f"{ticker} ({industry_label}): insufficient price history for a "
                   f"{config.GOAT_SECTOR_MA_SHORT_DAYS}-day MA",
        )

    ma50 = close.rolling(config.GOAT_SECTOR_MA_SHORT_DAYS).mean()
    diff = (close - ma50).dropna()
    sign = diff.gt(0).astype(int) - diff.lt(0).astype(int)
    sign_changed = sign.diff().fillna(0) != 0
    sign_changes = sign[sign_changed]

    slope_up = bool(
        ma50.iloc[-1] > ma50.iloc[-1 - config.GOAT_SECTOR_SLOPE_LOOKBACK_DAYS]
    )

    if sign_changes.empty:
        return CheckResult(
            name="industry_breakout", verdict="ok",
            detail=f"{ticker} ({industry_label}): no 50DMA cross in available history; "
                   f"MA currently {'rising' if slope_up else 'falling'}",
        )

    cross_date = sign_changes.index[-1]
    crossed_above = bool(sign_changes.iloc[-1] > 0)
    cross_pos = close.index.get_loc(cross_date)
    trading_days_since_cross = (len(close) - 1) - cross_pos
    fresh = trading_days_since_cross <= config.GOAT_SECTOR_CROSS_RECENCY_DAYS

    data = {
        "cross_date": cross_date.date().isoformat(), "crossed_above": crossed_above,
        "trading_days_since_cross": trading_days_since_cross, "slope_up": slope_up,
    }

    if crossed_above and slope_up and fresh:
        detail = (
            f"{ticker} ({industry_label}): crossed above its "
            f"{config.GOAT_SECTOR_MA_SHORT_DAYS}-day MA {trading_days_since_cross} "
            f"trading day(s) ago, MA now sloping up -- breakout entry signal "
            f"(webinar Step 1)"
        )
        return CheckResult(name="industry_breakout", verdict="interesting", detail=detail, data=data)

    direction = "crossed above" if crossed_above else "crossed below"
    return CheckResult(
        name="industry_breakout", verdict="ok",
        detail=f"{ticker} ({industry_label}): {direction} its "
               f"{config.GOAT_SECTOR_MA_SHORT_DAYS}-day MA {trading_days_since_cross} "
               f"trading day(s) ago (MA {'rising' if slope_up else 'falling'}) -- "
               f"not (yet) a fresh rising breakout",
        data=data,
    )
