"""Valuation check — trailing/forward PE vs configured bands."""

from __future__ import annotations

from .. import config
from . import CheckResult
from .scale import format_scale


def check(data) -> CheckResult:
    if data is None:
        return CheckResult(name="valuation", verdict="unknown", detail="No market data available")

    pe = data.info.get("trailingPE") or data.info.get("forwardPE")
    if pe is None:
        return CheckResult(
            name="valuation", verdict="unknown",
            detail="No PE data available (loss-making or data-sparse)",
        )

    # Scale hint anchored between the two thresholds this check already uses --
    # cheap threshold = 10/10, rich threshold = 0/10 -- not shown for negative PE,
    # which isn't a valid cheapness signal at all (loss-making).
    pe_scale = format_scale(pe, config.PE_CHEAP_THRESHOLD, config.PE_RICH_THRESHOLD)

    if pe >= config.PE_RICH_THRESHOLD:
        verdict, detail = "flag", f"PE {pe:.1f} above rich threshold ({config.PE_RICH_THRESHOLD}) ({pe_scale})"
    elif pe < 0:
        verdict, detail = "unknown", f"PE {pe:.1f} is negative (loss-making) — not a valid cheapness signal"
    elif pe <= config.PE_CHEAP_THRESHOLD:
        verdict, detail = "ok", f"PE {pe:.1f} at/below cheap threshold ({config.PE_CHEAP_THRESHOLD}) ({pe_scale})"
    else:
        verdict, detail = "ok", f"PE {pe:.1f} within normal range ({pe_scale})"

    return CheckResult(name="valuation", verdict=verdict, detail=detail, data={"pe": pe})
