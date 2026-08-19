"""Marker 1 -- record debt issuance in the hot sector. Per-issuer, reads the hot
watchlist (like Markers #2/#4/#12). Uses the same three form types
(424B2/424B5/FWP) already declared as SIGNALS_BOND_PROSPECTUS_FORM_TYPES for
Marker #12's CUSIP discovery -- the same filing types that disclose a CUSIP also
*are* the debt-issuance events this marker wants to count, confirmed live 2026-08-18.

Zero new DB state (a deliberate simplification vs. the Phase 3 handoff's own suggestion
of a filing-count-history table): EDGAR's full-text search API accepts arbitrary
startdt/enddt ranges on every call, so both the trailing window and the historical
baseline are computed via two live queries per ticker per run, not accumulated locally.

Honest limitation (state this in the report, same standard as Marker #12's bond-yield
proxy): this counts filing EVENTS, not aggregate dollar principal -- it cannot reproduce
a literal "$570B global AI-debt issuance" figure. It answers "is this issuer suddenly
filing debt prospectuses faster than its own history," a real, directionally-correct
proxy for "record debt issuance," not an exact dollar match."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from mytrader import sec_filings
from mytrader.checks import CheckResult

from . import config


def _check_one_ticker(conn, ticker: str) -> CheckResult | None:
    cik = sec_filings.get_cik(conn, ticker)
    if cik is None:
        return None
    today = date.today()
    forms = ",".join(config.SIGNALS_BOND_PROSPECTUS_FORM_TYPES)

    trailing_count = sec_filings.edgar_fulltext_search_count(
        forms, cik=cik,
        startdt=today - timedelta(days=config.SIGNALS_DEBT_ISSUANCE_LOOKBACK_DAYS), enddt=today,
    )
    if trailing_count is None:
        return None
    baseline_count = sec_filings.edgar_fulltext_search_count(
        forms, cik=cik,
        startdt=today - timedelta(days=config.SIGNALS_DEBT_ISSUANCE_BASELINE_DAYS), enddt=today,
    )
    if baseline_count is None:
        return None

    periods = config.SIGNALS_DEBT_ISSUANCE_BASELINE_DAYS / config.SIGNALS_DEBT_ISSUANCE_LOOKBACK_DAYS
    baseline_rate = baseline_count / periods  # average filings per trailing-window-length period

    detail = (
        f"{ticker}: {trailing_count} debt-prospectus filing(s) in the trailing "
        f"{config.SIGNALS_DEBT_ISSUANCE_LOOKBACK_DAYS}d (own {config.SIGNALS_DEBT_ISSUANCE_BASELINE_DAYS}d "
        f"average: {baseline_rate:.1f}/period) -- counts filing events, not dollar principal"
    )
    verdict = "ok"
    if baseline_rate > 0 and trailing_count >= baseline_rate * config.SIGNALS_DEBT_ISSUANCE_FLAG_RATIO:
        verdict = "flag"
    return CheckResult(
        name="debt_issuance", verdict=verdict, detail=detail,
        data={"ticker": ticker, "trailing_count": trailing_count, "baseline_rate": baseline_rate},
    )


def check_debt_issuance(conn, hot_watchlist: list[Any]) -> list[CheckResult]:
    results = []
    for row in hot_watchlist:
        result = _check_one_ticker(conn, row["ticker"])
        if result is not None:
            results.append(result)
    return results
