"""Balance sheet / leverage health check."""

from __future__ import annotations

from .. import config
from . import CheckResult


def check(data) -> CheckResult:
    if data is None:
        return CheckResult(name="balance_sheet", verdict="unknown", detail="No market data available")

    debt_to_equity = data.info.get("debtToEquity")
    current_ratio = data.info.get("currentRatio")

    if debt_to_equity is None and current_ratio is None:
        return CheckResult(name="balance_sheet", verdict="unknown", detail="No balance sheet data available")

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
