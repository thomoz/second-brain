"""Balance sheet / leverage health check.

debtToEquity/currentRatio are frequently absent from yfinance for financial-sector
tickers (banks, etc.) — verified 2026-07-19 against NU (Nu Holdings): both fields are
simply missing from the info dict, not a data-fetch failure. Banks don't have a
conventional current-assets/current-liabilities split, so Yahoo doesn't populate
these the way it does for industrials/consumer companies. Falls back to
returnOnEquity as a rough health proxy in that case rather than reporting "unknown"
for an entire sector when a genuinely relevant number is sitting right there.
"""

from __future__ import annotations

from .. import config
from . import CheckResult


def check(data) -> CheckResult:
    if data is None:
        return CheckResult(name="balance_sheet", verdict="unknown", detail="No market data available")

    debt_to_equity = data.info.get("debtToEquity")
    current_ratio = data.info.get("currentRatio")

    if debt_to_equity is None and current_ratio is None:
        roe = data.info.get("returnOnEquity")
        if roe is None:
            return CheckResult(name="balance_sheet", verdict="unknown", detail="No balance sheet data available")
        roe_pct = roe * 100
        if roe_pct <= config.ROE_FLAG_THRESHOLD_PCT:
            return CheckResult(
                name="balance_sheet", verdict="flag",
                detail=f"debt/equity and current ratio unavailable (common for financials); "
                       f"return on equity {roe_pct:.1f}% <= {config.ROE_FLAG_THRESHOLD_PCT}% fallback threshold",
                data={"return_on_equity_pct": round(roe_pct, 2)},
            )
        return CheckResult(
            name="balance_sheet", verdict="ok",
            detail=f"debt/equity and current ratio unavailable (common for financials); "
                   f"return on equity {roe_pct:.1f}% used as fallback health proxy",
            data={"return_on_equity_pct": round(roe_pct, 2)},
        )

    flags = []
    if debt_to_equity is not None and debt_to_equity >= config.DEBT_TO_EQUITY_FLAG:
        flags.append(f"debt/equity {debt_to_equity:.1f} >= {config.DEBT_TO_EQUITY_FLAG}")
    if current_ratio is not None and current_ratio <= config.CURRENT_RATIO_FLAG:
        flags.append(f"current ratio {current_ratio:.2f} <= {config.CURRENT_RATIO_FLAG}")

    data_out = {"debt_to_equity": debt_to_equity, "current_ratio": current_ratio}
    if flags:
        return CheckResult(name="balance_sheet", verdict="flag", detail="; ".join(flags), data=data_out)

    return CheckResult(
        name="balance_sheet", verdict="ok",
        detail="Debt/equity and current ratio within thresholds", data=data_out,
    )
