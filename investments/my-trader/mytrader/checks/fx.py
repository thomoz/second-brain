"""FX exposure check — informational context, not pass/fail (AUD investor)."""

from __future__ import annotations

from .. import market_data
from . import CheckResult


def check(data) -> CheckResult:
    if data is None:
        return CheckResult(name="fx", verdict="unknown", detail="No market data available")

    currency = data.info.get("currency")
    if not currency or currency == "AUD":
        return CheckResult(name="fx", verdict="info", detail="AUD-denominated, no FX exposure", data={"currency": currency})

    change_pct = market_data.fetch_fx_change_pct(currency)
    if change_pct is None:
        return CheckResult(
            name="fx", verdict="info",
            detail=f"{currency}-denominated; AUD/{currency} 3mo change unavailable",
            data={"currency": currency},
        )

    return CheckResult(
        name="fx", verdict="info",
        detail=f"{currency}-denominated; AUD/{currency} 3mo move: {change_pct:+.1f}%",
        data={"currency": currency, "fx_change_pct_3mo": change_pct},
    )
