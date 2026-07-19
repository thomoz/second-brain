"""Path constants and thresholds for the my-trader assessment engine."""

from __future__ import annotations

from pathlib import Path

from scripts.config import DB_PATH  # noqa: F401  (re-exported for mytrader callers)

MY_TRADER_DIR = Path(__file__).resolve().parent.parent  # mytrader -> my-trader
HOLDINGS_MD_PATH = MY_TRADER_DIR / "holdings.md"
WATCHLIST_MD_PATH = MY_TRADER_DIR / "potential-holdings.md"
MONITOR_REPORT_PATH = MY_TRADER_DIR / "monitor-report.md"

BERKSHIRE_HOLDINGS: frozenset[str] = frozenset({
    # Manually maintained — update periodically from Berkshire's 13F filings
    # (quiverquant.com/insiders/berkshire-hathaway or cnbc.com/berkshire-hathaway-portfolio).
    # Last updated: 2026-07-19 (empty — populate before first real Find run).
})

SECTOR_FLASHPOINTS: dict[str, str] = {
    "Energy": "Strait of Hormuz / Middle East conflict — ~20M bbl/day transit risk",
    "Semiconductors": "Taiwan/China export-control risk (TSMC, ASML supply chain)",
}

DIVIDEND_CUT_THRESHOLD_PCT = -5.0  # TTM vs prior-12mo decline beyond this = "cut"
PE_RICH_THRESHOLD = 35.0
PE_CHEAP_THRESHOLD = 12.0
DEBT_TO_EQUITY_FLAG = 150.0
CURRENT_RATIO_FLAG = 1.0
SECTOR_CONCENTRATION_FLAG_PCT = 25.0  # candidate's sector as % of holdings mkt value
