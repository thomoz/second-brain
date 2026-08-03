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
from .scale import format_scale


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
        # Scale anchored between the two ROE thresholds already used across the tool:
        # the fallback flag floor (below) and Buffett/Smith's own stated 15%+ "good"
        # bar (opportunity.py) -- 15%+ clamps to 10/10, not a new number.
        roe_scale = format_scale(roe_pct, config.OPPORTUNITY_ROE_MIN_PCT, config.ROE_FLAG_THRESHOLD_PCT)
        if roe_pct <= config.ROE_FLAG_THRESHOLD_PCT:
            return CheckResult(
                name="balance_sheet", verdict="flag",
                detail=f"debt/equity and current ratio unavailable (common for financials); "
                       f"return on equity {roe_pct:.1f}% <= {config.ROE_FLAG_THRESHOLD_PCT}% fallback threshold "
                       f"({roe_scale})",
                data={"return_on_equity_pct": round(roe_pct, 2)},
            )
        return CheckResult(
            name="balance_sheet", verdict="ok",
            detail=f"debt/equity and current ratio unavailable (common for financials); "
                   f"return on equity {roe_pct:.1f}% used as fallback health proxy ({roe_scale})",
            data={"return_on_equity_pct": round(roe_pct, 2)},
        )

    de_scale = (
        format_scale(debt_to_equity, config.DEBT_TO_EQUITY_IDEAL, config.DEBT_TO_EQUITY_FLAG)
        if debt_to_equity is not None else None
    )
    cr_scale = (
        format_scale(current_ratio, config.CURRENT_RATIO_HEALTHY, config.CURRENT_RATIO_FLAG)
        if current_ratio is not None else None
    )

    flags = []
    if debt_to_equity is not None and debt_to_equity >= config.DEBT_TO_EQUITY_FLAG:
        flags.append(f"debt/equity {debt_to_equity:.1f} >= {config.DEBT_TO_EQUITY_FLAG} ({de_scale})")
    if current_ratio is not None and current_ratio <= config.CURRENT_RATIO_FLAG:
        flags.append(f"current ratio {current_ratio:.2f} <= {config.CURRENT_RATIO_FLAG} ({cr_scale})")

    data_out = {"debt_to_equity": debt_to_equity, "current_ratio": current_ratio}
    if flags:
        return CheckResult(name="balance_sheet", verdict="flag", detail="; ".join(flags), data=data_out)

    parts = []
    if debt_to_equity is not None:
        parts.append(f"debt/equity {debt_to_equity:.1f} ({de_scale})")
    if current_ratio is not None:
        parts.append(f"current ratio {current_ratio:.2f} ({cr_scale})")
    detail = f"{', '.join(parts)} — within thresholds" if parts else "Debt/equity and current ratio within thresholds"

    return CheckResult(name="balance_sheet", verdict="ok", detail=detail, data=data_out)
