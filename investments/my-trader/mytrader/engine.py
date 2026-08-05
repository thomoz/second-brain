"""Assessment engine — aggregates all 10 checks + ethical filter + briefs-finance score lookup."""

from __future__ import annotations

import sqlite3
from typing import Any

from scripts.ethical_filter import check_ticker as ethical_check

from . import db, market_data, return_data, tickers
from .checks import (
    balance_sheet,
    concentration,
    crash_resilience,
    dividend,
    etf_mechanics,
    fx,
    news_events,
    opportunity,
    price_action,
    principles_fit,
    sector_risk,
    valuation,
)


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


def _refresh_backtest_for_ticker(ticker: str) -> None:
    """Ticker-scoped backtest refresh (confirmed 2026-07-19 — Shaun: "throw
    everything you have at it"). Cheap (yfinance price lookups only, no LLM calls)
    unlike score computation, so this runs on *every* assessment rather than being
    cached once — backtest outcomes genuinely change over time as 3m/6m/12m windows
    elapse, so there's real value in refreshing on every call. Uses its own DB
    connection (scripts.backtest.run_backtest's own lifecycle, WAL mode allows this
    concurrently with engine.run_assessment's connection). No-op if the ticker has no
    Briefs Finance recommendation at all (query just returns zero rows). Swallows
    exceptions — a backtest hiccup (network, etc.) shouldn't break the rest of the
    assessment.
    """
    try:
        from scripts.backtest import run_backtest

        run_backtest(ticker_filter=ticker)
    except Exception:
        pass


def run_assessment(
    ticker: str,
    conn: sqlite3.Connection,
    include_principles_fit: bool = False,
    include_news_events: bool = False,
) -> dict[str, Any]:
    """include_principles_fit: opt-in, Find-only (see checks/principles_fit.py) — 9
    extra LLM calls per assessment, so defaulted off. Monitor never passes True, so
    its daily re-check of every holding + discussed watchlist row is unaffected.

    include_news_events: opt-in, Find-only (see checks/news_events.py) — one
    LLM+web-search call per assessment, same reasoning as include_principles_fit.
    Added to other_checks (not appended after, like principles_fit) so a "flag"
    verdict here participates in opportunity.py's existing risk-flag gate."""
    normalized = tickers.normalize(ticker)
    data = market_data.fetch_ticker_data(normalized)
    excluded, exclusion_reason = ethical_check(normalized)
    existing_row = db.get_holding_row(conn, normalized) or db.get_watchlist_row(conn, normalized)

    _refresh_backtest_for_ticker(normalized)
    briefs_score = _lookup_or_compute_briefs_finance_score(normalized, conn)
    recent_return_1mo = return_data.fetch_recent_return_pct(normalized, period="1mo") if data is not None else None
    recent_return_3mo = return_data.fetch_recent_return_pct(normalized, period="3mo") if data is not None else None

    other_checks = [
        dividend.check(data),
        valuation.check(data),
        balance_sheet.check(data),
        fx.check(data),
        concentration.check(data, conn),
        sector_risk.check(data),
        etf_mechanics.check(data, existing_row),
    ]
    if include_news_events:
        other_checks.append(news_events.check(normalized, conn))
    results = [
        *other_checks,
        opportunity.check(data, other_checks, briefs_score, recent_return_3mo),
        price_action.check(recent_return_1mo, recent_return_3mo),
        crash_resilience.check(data),
    ]
    if include_principles_fit:
        results.append(
            principles_fit.check(
                normalized, data, other_checks, briefs_score, recent_return_1mo, recent_return_3mo, conn
            )
        )

    return {
        "ticker": normalized,
        "excluded": excluded,
        "exclusion_reason": exclusion_reason,
        "checks": results,
        "briefs_finance_score": briefs_score,
        "data_available": data is not None,
    }
