"""Going-concern / bankruptcy-risk check -- added 2026-10-20, Shaun: "I predominantly
want to know if a company has a high likelihood of going under soon eg coreweave has
about 3 months worth of cashflow - not great. So i want a clear statement after each
deep dive about this."

Cash runway = Total Cash / monthly cash burn, where monthly burn is derived from
Free Cash Flow (negative FCF = burn). The 12-month flag threshold is not invented --
it mirrors the standard auditor "going concern" look-forward horizon (ASC 205-40 /
ISA 570: management and auditors must assess whether substantial doubt exists about
a company's ability to continue operating over the next twelve months). A company
burning cash with less than a year of runway at the current rate is exactly inside
the window those standards are built around.

Prefers yfinance's own TTM freeCashflow .info field (more current than the annual
statement) and falls back to market_data.fetch_cash_flow_statement's latest ANNUAL
figure -- same fallback shape as cash_value_scan.py's compute_cash_value_metrics.
Positive FCF always verdicts "ok" regardless of cash balance -- a cash-generative
company isn't burning toward insolvency, runway doesn't apply.

Deliberately scoped to cash runway only, not a debt-maturity-wall risk -- yfinance
doesn't expose a debt maturity schedule, and modeling that would need data this tool
doesn't have access to. Positioned last in engine.run_assessment's results list (see
engine.py) so it reads as the closing statement of the deep dive, not buried among
the other checks.
"""

from __future__ import annotations

from .. import config, market_data
from . import CheckResult
from .scale import format_scale


def check(data) -> CheckResult:
    if data is None:
        return CheckResult(name="going_concern", verdict="unknown", detail="No market data available")

    info = data.info
    total_cash = info.get("totalCash")
    fcf = info.get("freeCashflow")
    source = "info"
    if fcf is None:
        annual = market_data.fetch_cash_flow_statement(data.ticker)
        if annual is not None and annual.get("free_cash_flow") is not None:
            fcf = annual["free_cash_flow"]
            source = "annual"

    if total_cash is None or fcf is None:
        return CheckResult(
            name="going_concern", verdict="unknown",
            detail="Total Cash and/or Free Cash Flow unavailable -- cannot assess bankruptcy/cash-runway risk",
        )

    annual_note = " (annual FCF)" if source == "annual" else ""

    if fcf >= 0:
        return CheckResult(
            name="going_concern", verdict="ok",
            detail=f"Free Cash Flow positive (${fcf / 1e6:,.0f}M{annual_note}) "
                   f"-- cash-generative, no bankruptcy/cash-runway risk from this signal",
            data={"free_cash_flow": fcf, "total_cash": total_cash, "runway_months": None},
        )

    monthly_burn = -fcf / 12
    runway_months = total_cash / monthly_burn if monthly_burn > 0 else None
    if runway_months is None:
        return CheckResult(
            name="going_concern", verdict="unknown",
            detail="Free Cash Flow negative but monthly burn rate could not be computed",
        )

    # Higher runway is safer -- COMFORTABLE_MONTHS is the scale's "good" end,
    # FLAG_MONTHS the "bad" end, same reversed-order usage as balance_sheet.py's
    # Debt/Equity scale.
    runway_scale = format_scale(
        runway_months, config.GOING_CONCERN_RUNWAY_COMFORTABLE_MONTHS, config.GOING_CONCERN_RUNWAY_FLAG_MONTHS
    )
    base = (
        f"Cash ${total_cash / 1e6:,.0f}M / burn ~${monthly_burn / 1e6:,.0f}M per month{annual_note} "
        f"= ~{runway_months:.1f} months of runway at the current rate -- more runway is safer ({runway_scale})"
    )
    data_out = {"free_cash_flow": fcf, "total_cash": total_cash, "runway_months": round(runway_months, 1)}

    if runway_months <= config.GOING_CONCERN_RUNWAY_FLAG_MONTHS:
        return CheckResult(
            name="going_concern", verdict="flag",
            detail=f"BANKRUPTCY RISK: {base}, inside the standard one-year going-concern horizon "
                   f"-- will likely need to raise capital, cut spending, or sell assets soon",
            data=data_out,
        )

    return CheckResult(name="going_concern", verdict="ok", detail=f"No near-term bankruptcy risk: {base}", data=data_out)
