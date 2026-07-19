"""Valuation check — trailing/forward PE vs configured bands."""

from __future__ import annotations

from .. import config
from . import CheckResult


def check(data) -> CheckResult:
    if data is None:
        return CheckResult(name="valuation", verdict="unknown", detail="No market data available")

    pe = data.info.get("trailingPE") or data.info.get("forwardPE")
    if pe is None:
        return CheckResult(
            name="valuation", verdict="unknown",
            detail="No PE data available (loss-making or data-sparse)",
        )

    if pe >= config.PE_RICH_THRESHOLD:
        verdict, detail = "flag", f"PE {pe:.1f} above rich threshold ({config.PE_RICH_THRESHOLD})"
    elif pe <= config.PE_CHEAP_THRESHOLD:
        verdict, detail = "ok", f"PE {pe:.1f} at/below cheap threshold ({config.PE_CHEAP_THRESHOLD})"
    else:
        verdict, detail = "ok", f"PE {pe:.1f} within normal range"

    return CheckResult(name="valuation", verdict=verdict, detail=detail, data={"pe": pe})
