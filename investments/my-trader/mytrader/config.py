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

# Phase C — macro monitoring indicators (tool-preplan.md "Monitoring Indicators",
# confirmed 2026-07-19). Thresholds below are best-guess defaults set during planning
# without live data access — sanity-check against real fetched values at Task 5.4's
# manual validation step and tune if obviously wrong, same as PE_RICH_THRESHOLD etc.
# above were always understood to be starting points, not final.
MOVE_INDEX_TICKER = "^MOVE"  # ICE BofA MOVE Index — confirm this resolves via
                              # yfinance at Task 2.1's validation step; if it doesn't,
                              # check_move_index() must still degrade to "unknown"
                              # gracefully rather than blocking the rest of Phase C.
MOVE_INDEX_FLAG_LEVEL = 140.0  # tool-preplan.md notes MOVE was "confirmed low as of
                                 # early 2026 (lowest since 2021)" — no crisis-level
                                 # reading to calibrate against during planning.

FRED_MEDIAN_HOME_PRICE_SERIES = "MSPUS"
FRED_MEDIAN_HOUSEHOLD_INCOME_SERIES = "MEHOINUSA672N"
HOUSING_P2I_FLAG_RATIO = 5.0  # tool-preplan.md: ratio "~5x" currently vs "~2.5-3x
                                # considered affordable by convention" (fact-checked
                                # 2026-07-18) — flag at the current stretched level.

FRED_CONSUMER_SENTIMENT_SERIES = "UMCSENT"
CONSUMER_SENTIMENT_FLAG_LEVEL = 50.0  # tool-preplan.md: record low 44.8 (May 2026),
                                        # recovered to 49.5 (Jun 2026) — set just above
                                        # the recovered reading so a re-decline back
                                        # toward the record low would flag.

FRED_YIELD_CURVE_SERIES = "T10Y2Y"       # matches briefs-finance's own
FRED_RECESSION_PROB_SERIES = "RECPROUSM156N"  # FRED_SERIES values — see module
                                                # docstring in macro_indicators.py for
                                                # why these are duplicated, not imported.
FRED_2Y_TREASURY_SERIES = "DGS2"
FRED_10Y_TREASURY_SERIES = "DGS10"
RECESSION_PROB_FLAG_PCT = 20.0  # tool-preplan.md: NY Fed model "~25-30% 12-month
                                  # recession probability as of mid-2026" — flag below
                                  # that observed level so Monitor already flags today.
STEEPENER_LOOKBACK_DAYS = 90  # window for comparing short/long-end direction to
                                # classify bull vs. bear steepening.
