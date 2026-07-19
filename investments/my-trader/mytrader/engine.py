"""Assessment engine — aggregates all 7 checks + ethical filter + briefs-finance score lookup."""

from __future__ import annotations

import sqlite3
from typing import Any

from scripts.ethical_filter import check_ticker as ethical_check

from . import db, market_data, tickers
from .checks import balance_sheet, concentration, dividend, etf_mechanics, fx, sector_risk, valuation


def _read_briefs_finance_score(ticker: str, conn: sqlite3.Connection) -> dict[str, Any] | None:
    """Read-only lookup of briefs-finance's existing likelihood score for a ticker."""
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


def _lookup_or_compute_briefs_finance_score(ticker: str, conn: sqlite3.Connection) -> dict[str, Any] | None:
    """Read briefs-finance's existing likelihood score, computing one on the spot if
    the ticker has a non-excluded Briefs Finance recommendation but no score yet
    (confirmed 2026-07-19 — Shaun: "throw everything you have at assessing it").

    Costs ~9 haiku LLM calls (one per investor-principle file, via
    scripts.score.compute_score) the *first* time only — the result is persisted to
    likelihood_scores, so every subsequent call for this ticker (from Find or
    Monitor — both go through this same function) just reads the cached row. Returns
    None only when the ticker was never a Briefs Finance recommendation at all —
    there's no buy_thesis to score against the 9 principles in that case, nothing to
    compute regardless of budget.
    """
    existing = _read_briefs_finance_score(ticker, conn)
    if existing is not None:
        return existing

    rec = conn.execute(
        "SELECT id FROM recommendations WHERE ticker = ? AND excluded = 0 ORDER BY id DESC LIMIT 1",
        (ticker,),
    ).fetchone()
    if rec is None:
        return None

    from scripts.score import compute_score

    compute_score(rec["id"], conn)
    return _read_briefs_finance_score(ticker, conn)


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

    briefs_score = _lookup_or_compute_briefs_finance_score(normalized, conn)

    return {
        "ticker": normalized,
        "excluded": excluded,
        "exclusion_reason": exclusion_reason,
        "checks": results,
        "briefs_finance_score": briefs_score,
        "data_available": data is not None,
    }
