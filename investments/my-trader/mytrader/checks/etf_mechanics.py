"""ETF mechanics drift check — expense ratio baseline capture / drift detection.

Phase A can only capture a baseline on first sight; true drift detection activates
once Monitor (Phase B) runs repeatedly and this is called again with a populated
existing_row.
"""

from __future__ import annotations

from . import CheckResult


def check(data, existing_row) -> CheckResult:
    if data is None:
        return CheckResult(name="etf_mechanics", verdict="unknown", detail="No market data available")

    if data.info.get("quoteType") != "ETF":
        return CheckResult(name="etf_mechanics", verdict="unknown", detail="Not an ETF")

    expense_ratio = data.info.get("netExpenseRatio")
    category = data.info.get("category")
    prior_ratio = existing_row["last_expense_ratio"] if existing_row is not None else None

    if prior_ratio is not None and expense_ratio is not None and prior_ratio != expense_ratio:
        return CheckResult(
            name="etf_mechanics", verdict="flag",
            detail=f"Expense ratio changed from {prior_ratio:.4f} to {expense_ratio:.4f}",
            data={"expense_ratio": expense_ratio, "prior_expense_ratio": prior_ratio, "category": category},
        )

    return CheckResult(
        name="etf_mechanics", verdict="info",
        detail=f"Baseline captured: expense ratio {expense_ratio}",
        data={"expense_ratio": expense_ratio, "category": category},
    )
