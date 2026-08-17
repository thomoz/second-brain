"""Fundamentals survival context for heartbeat candidates -- Goat Phase 3, per
HANDOFF.md's debt -> cash runway -> margins -> revenue growth -> cash generation
priority order. Informational on every candidate, NOT a pass/fail gate --
confirmed with Shaun 2026-08-17 (gating on all 5 independently would disqualify
almost the entire S&P 500, since almost no company is debt-free). The only thing
that actually suppresses staging is a genuine near-term-insolvency combination:
high debt/equity AND cash-burning with under a year of runway -- see
insolvency_risk below."""

from __future__ import annotations

from mytrader import config as mytrader_config
from mytrader import market_data

from . import config


def compute_survival_context(ticker: str, data) -> dict:
    """`data` is a mytrader.market_data.TickerData or None. Every field is
    None-safe -- a ticker with a totally empty .info still returns a dict with
    insolvency_risk=False (unknown fields do not, by themselves, indicate
    insolvency risk -- that would be a false-positive-suppression bug, not a
    safe default) and a summary noting what's unavailable."""
    if data is None:
        return {
            "debt_to_equity": None, "cash_runway_years": None,
            "gross_margin": None, "operating_margin": None,
            "revenue_growth": None, "cash_generating": None,
            "insolvency_risk": False,
            "summary": "no fundamentals data available",
        }

    info = data.info

    debt_to_equity = info.get("debtToEquity")
    if debt_to_equity is None:
        computed = market_data.fetch_balance_sheet_financials(data.ticker)
        if computed is not None:
            debt_to_equity = computed.get("debtToEquity")

    total_cash = info.get("totalCash")
    free_cashflow = info.get("freeCashflow")
    cash_burning = free_cashflow is not None and free_cashflow < 0
    cash_runway_years = (
        round(total_cash / abs(free_cashflow), 1)
        if cash_burning and total_cash is not None
        else None
    )

    gross_margin = info.get("grossMargins")
    operating_margin = info.get("operatingMargins")
    revenue_growth = info.get("revenueGrowth")
    cash_generating = (info.get("operatingCashflow") or 0) > 0

    insolvency_risk = bool(
        debt_to_equity is not None
        and debt_to_equity >= mytrader_config.DEBT_TO_EQUITY_FLAG
        and cash_runway_years is not None
        and cash_runway_years < config.GOAT_CASH_RUNWAY_FLAG_YEARS
    )

    parts = []
    if debt_to_equity is not None:
        below = "below" if debt_to_equity < mytrader_config.DEBT_TO_EQUITY_FLAG else "at/above"
        parts.append(f"debt/equity {debt_to_equity:.1f} ({below} flag threshold)")
    else:
        parts.append("debt/equity unavailable")

    if cash_burning:
        if cash_runway_years is not None:
            parts.append(f"cash runway {cash_runway_years:.1f} years (cash-burning)")
        else:
            parts.append("cash-burning, runway unknown (cash balance unavailable)")
    else:
        parts.append("N/A — cash generative" if total_cash is not None or free_cashflow is not None
                      else "cash flow unavailable")

    if gross_margin is not None:
        parts.append(f"gross margin {gross_margin * 100:.1f}%")
    if operating_margin is not None:
        parts.append(f"operating margin {operating_margin * 100:.1f}%")
    if revenue_growth is not None:
        sign = "+" if revenue_growth >= 0 else ""
        parts.append(f"revenue growth {sign}{revenue_growth * 100:.1f}% YoY")
    parts.append("cash-generating" if cash_generating else "not currently cash-generating")

    summary = ", ".join(parts)
    if insolvency_risk:
        summary += " -- near-term insolvency risk (high debt/equity + short cash runway)"

    return {
        "debt_to_equity": debt_to_equity,
        "cash_runway_years": cash_runway_years,
        "gross_margin": gross_margin,
        "operating_margin": operating_margin,
        "revenue_growth": revenue_growth,
        "cash_generating": cash_generating,
        "insolvency_risk": insolvency_risk,
        "summary": summary,
    }
