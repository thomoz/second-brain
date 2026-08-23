"""Industry rotation ranking for Finviz's finer-grained industry groups -- see
.agent/plans/goat-industry-rotation-ranking.md. Direct sibling of
sector_rotation.py's fetch/rank pair, at industry rather than sector granularity.
No breakout signal here -- see that plan's "Explicitly Deferred" section."""

from __future__ import annotations

from typing import Any

import pandas as pd

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
    rows: list[dict[str, Any]] = []
    for ticker, industry_label in config.GOAT_INDUSTRY_ETFS.items():
        close = closes.get(ticker)
        if close is None or len(close) < window + 1:
            rows.append({
                "ticker": ticker, "industry_label": industry_label,
                "return_pct": None, "rising": None,
            })
            continue
        pct = float((close.iloc[-1] / close.iloc[-(window + 1)] - 1) * 100)
        rows.append({
            "ticker": ticker, "industry_label": industry_label,
            "return_pct": pct, "rising": pct > 0,
        })
    # Rows with no data sort last, not first/interspersed.
    rows.sort(key=lambda r: (r["return_pct"] is None, -(r["return_pct"] or 0)))
    for i, row in enumerate(rows, start=1):
        row["rank"] = i
    return rows
