"""Sector rotation ranking + breakout signal for the 11 SPDR Select Sector ETFs --
Goat Phase 2. See goat/config.py for GOAT_SECTOR_* threshold sourcing. Scope is
deliberately limited to 50DMA cross-detection + slope-turn only -- the "heartbeat"
consolidation pattern stays deferred to Phase 3 (see this feature's plan doc,
"THREE DECISIONS RESOLVED" section)."""

from __future__ import annotations

from typing import Any

import pandas as pd
from mytrader.checks import CheckResult

from . import config, price_history


def fetch_all_sector_closes() -> dict[str, pd.Series | None]:
    closes: dict[str, pd.Series | None] = {}
    for ticker in config.GOAT_SECTOR_ETFS:
        try:
            closes[ticker] = price_history.fetch_close_history(
                ticker, config.GOAT_SECTOR_HISTORY_LOOKBACK_DAYS
            )
        except Exception as e:
            print(f"[goat-sector-scan] error fetching {ticker}: {e}")
            closes[ticker] = None
    return closes


def rank_sectors(closes: dict[str, pd.Series | None]) -> list[dict[str, Any]]:
    window = config.GOAT_SECTOR_RANK_WINDOW_TRADING_DAYS
    rows: list[dict[str, Any]] = []
    for ticker, sector_label in config.GOAT_SECTOR_ETFS.items():
        close = closes.get(ticker)
        if close is None or len(close) < window + 1:
            rows.append({
                "ticker": ticker, "sector_label": sector_label,
                "return_pct": None, "rising": None,
            })
            continue
        pct = float((close.iloc[-1] / close.iloc[-(window + 1)] - 1) * 100)
        rows.append({
            "ticker": ticker, "sector_label": sector_label,
            "return_pct": pct, "rising": pct > 0,
        })
    # Rows with no data sort last, not first/interspersed.
    rows.sort(key=lambda r: (r["return_pct"] is None, -(r["return_pct"] or 0)))
    for i, row in enumerate(rows, start=1):
        row["rank"] = i
    return rows


def check_sector_breakout(ticker: str, sector_label: str, close: pd.Series) -> CheckResult:
    """Flags 'interesting' (never 'flag' -- this is an opportunity signal, not a
    risk warning, matching mytrader/checks/opportunity.py's verdict convention)
    when `ticker` crossed above its 50-day MA within the last
    GOAT_SECTOR_CROSS_RECENCY_DAYS trading days AND the 50DMA itself is currently
    sloping up -- the webinar's literal Step 1 entry rule."""
    min_len = config.GOAT_SECTOR_MA_SHORT_DAYS + config.GOAT_SECTOR_SLOPE_LOOKBACK_DAYS
    if len(close) < min_len:
        return CheckResult(
            name="sector_breakout", verdict="unknown",
            detail=f"{ticker} ({sector_label}): insufficient price history for a "
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
            name="sector_breakout", verdict="ok",
            detail=f"{ticker} ({sector_label}): no 50DMA cross in available history; "
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
            f"{ticker} ({sector_label}): crossed above its "
            f"{config.GOAT_SECTOR_MA_SHORT_DAYS}-day MA {trading_days_since_cross} "
            f"trading day(s) ago, MA now sloping up -- breakout entry signal "
            f"(webinar Step 1)"
        )
        return CheckResult(name="sector_breakout", verdict="interesting", detail=detail, data=data)

    direction = "crossed above" if crossed_above else "crossed below"
    return CheckResult(
        name="sector_breakout", verdict="ok",
        detail=f"{ticker} ({sector_label}): {direction} its "
               f"{config.GOAT_SECTOR_MA_SHORT_DAYS}-day MA {trading_days_since_cross} "
               f"trading day(s) ago (MA {'rising' if slope_up else 'falling'}) -- "
               f"not (yet) a fresh rising breakout",
        data=data,
    )
