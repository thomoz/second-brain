"""Marker 4 -- capex outruns cash flow, via a negative free-cash-flow check (design (b)
from the Phase 2 handoff, not a two-period capex/revenue growth-gap -- simpler,
single-period, and doesn't need a second income-statement fetch). Confirmed live
2026-08-18 against real ORCL data: FCF = Operating Cash Flow + Capital Expenditure
(capex already negative)."""

from __future__ import annotations

from typing import Any

from mytrader import market_data
from mytrader.checks import CheckResult

from . import config


def _check_one_ticker(ticker: str) -> CheckResult | None:
    cf = market_data.fetch_cash_flow_statement(ticker)
    if cf is None:
        return None
    fcf = cf["free_cash_flow"]
    capex = abs(cf.get("capital_expenditure", 0.0))
    detail = (
        f"{ticker}: Free Cash Flow ${fcf / 1e9:+.1f}B, Capital Expenditure ${capex / 1e9:.1f}B "
        f"(period ending {cf.get('period_end', '?')})"
    )
    verdict = "flag" if fcf < 0 and capex >= config.SIGNALS_CAPEX_MIN_FLAG_ABS else "ok"
    return CheckResult(
        name="capex_cashflow", verdict=verdict, detail=detail,
        data={"ticker": ticker, "free_cash_flow": fcf, "capital_expenditure": capex, "period_end": cf.get("period_end")},
    )


def check_capex_cashflow(hot_watchlist: list[Any]) -> list[CheckResult]:
    results = []
    for row in hot_watchlist:
        result = _check_one_ticker(row["ticker"])
        if result is not None:
            results.append(result)
    return results
