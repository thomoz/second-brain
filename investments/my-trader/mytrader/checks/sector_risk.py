"""Sector/geopolitical flashpoint check — informational, per-holding sector exposure."""

from __future__ import annotations

from .. import config
from . import CheckResult


def check(data) -> CheckResult:
    if data is None:
        return CheckResult(name="sector_risk", verdict="unknown", detail="No market data available")

    sector = data.info.get("sector")
    industry = data.info.get("industry")

    flashpoint = config.SECTOR_FLASHPOINTS.get(sector) or config.SECTOR_FLASHPOINTS.get(industry)
    matched_on = sector if sector in config.SECTOR_FLASHPOINTS else industry

    if flashpoint:
        return CheckResult(
            name="sector_risk", verdict="info",
            detail=f"{matched_on} flashpoint: {flashpoint}",
            data={"sector": sector, "industry": industry, "matched_on": matched_on},
        )

    return CheckResult(
        name="sector_risk", verdict="ok",
        detail="No known active geopolitical flashpoint for this sector/industry",
        data={"sector": sector, "industry": industry},
    )
