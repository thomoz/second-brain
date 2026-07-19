"""Portfolio concentration check — Berkshire overlap + sector concentration vs existing holdings.

Market-value aggregation is currency-naive (sums qty * avg_price across USD/AUD holdings
without FX normalization) — matches the existing hand-maintained holdings.md's own
naivety, not a regression. A real gap worth fixing later (Phase C candidate).
"""

from __future__ import annotations

from .. import config, db, market_data
from . import CheckResult


def check(data, conn) -> CheckResult:
    if data is None:
        return CheckResult(name="concentration", verdict="unknown", detail="No market data available")

    ticker = data.ticker.split(".")[0]  # strip .AX fallback suffix before comparing

    if not config.BERKSHIRE_HOLDINGS:
        berkshire_verdict = "unknown"
        berkshire_detail = "Berkshire 13F holdings list not populated (manual data entry required)"
    elif ticker in config.BERKSHIRE_HOLDINGS:
        berkshire_verdict = "flag"
        berkshire_detail = f"{ticker} already held by Berkshire Hathaway"
    else:
        berkshire_verdict = "ok"
        berkshire_detail = f"{ticker} not in known Berkshire holdings"

    sector = data.info.get("sector")
    sector_pct = None
    if not sector:
        sector_verdict = "unknown"
        sector_detail = "No sector data for candidate"
    else:
        holdings = db.get_all_holdings(conn)
        total_value = 0.0
        sector_value = 0.0
        for row in holdings:
            value = row["qty"] * row["avg_price"]
            total_value += value
            row_data = market_data.fetch_ticker_data(row["ticker"])
            if row_data is not None and row_data.info.get("sector") == sector:
                sector_value += value
        if total_value > 0:
            sector_pct = round(sector_value / total_value * 100, 1)
            if sector_pct >= config.SECTOR_CONCENTRATION_FLAG_PCT:
                sector_verdict = "flag"
                sector_detail = f"{sector} already {sector_pct}% of holdings value"
            else:
                sector_verdict = "ok"
                sector_detail = f"{sector} is {sector_pct}% of holdings value"
        else:
            sector_verdict = "info"
            sector_detail = "No existing holdings to compare sector concentration against"

    overall_verdict = (
        "flag" if "flag" in (berkshire_verdict, sector_verdict)
        else "unknown" if "unknown" in (berkshire_verdict, sector_verdict)
        else "ok"
    )

    return CheckResult(
        name="concentration",
        verdict=overall_verdict,
        detail=f"Berkshire: {berkshire_detail}. Sector: {sector_detail}",
        data={
            "berkshire": {"verdict": berkshire_verdict, "detail": berkshire_detail},
            "sector": {"verdict": sector_verdict, "detail": sector_detail, "sector_pct": sector_pct},
        },
    )
