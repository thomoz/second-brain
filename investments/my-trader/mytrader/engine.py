"""Assessment engine — aggregates all 7 checks + ethical filter + briefs-finance score lookup."""

from __future__ import annotations

import sqlite3
from typing import Any

from scripts.ethical_filter import check_ticker as ethical_check

from . import db, market_data, tickers
from .checks import balance_sheet, concentration, dividend, etf_mechanics, fx, sector_risk, valuation


def _lookup_briefs_finance_score(ticker: str, conn: sqlite3.Connection) -> dict[str, Any] | None:
    """Read-only lookup of briefs-finance's existing likelihood score for a ticker.

    Never triggers a fresh scoring run (scripts.score.compute_score) — that's an
    expensive, network/LLM-calling side effect Find shouldn't cause implicitly.
    """
    row = conn.execute(
        """SELECT ls.score, ls.provisional, ls.computed_at
           FROM likelihood_scores ls
           JOIN recommendations r ON r.id = ls.recommendation_id
           WHERE r.ticker = ? AND r.excluded = 0
           ORDER BY ls.computed_at DESC LIMIT 1""",
        (ticker,),
    ).fetchone()
    if row is None:
        return None
    return {"score": row["score"], "provisional": bool(row["provisional"]), "computed_at": row["computed_at"]}


def run_assessment(ticker: str, conn: sqlite3.Connection) -> dict[str, Any]:
    normalized = tickers.normalize(ticker)
    data = market_data.fetch_ticker_data(normalized)
    excluded, exclusion_reason = ethical_check(normalized)
    existing_row = db.get_holding_row(conn, normalized) or db.get_watchlist_row(conn, normalized)

    results = [
        dividend.check(data),
        valuation.check(data),
        balance_sheet.check(data),
        fx.check(data),
        concentration.check(data, conn),
        sector_risk.check(data),
        etf_mechanics.check(data, existing_row),
    ]

    briefs_score = _lookup_briefs_finance_score(normalized, conn)

    return {
        "ticker": normalized,
        "excluded": excluded,
        "exclusion_reason": exclusion_reason,
        "checks": results,
        "briefs_finance_score": briefs_score,
        "data_available": data is not None,
    }
