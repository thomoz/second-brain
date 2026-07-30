"""Path constants and thresholds for the my-trader assessment engine."""

from __future__ import annotations

from pathlib import Path

from scripts.config import DB_PATH  # noqa: F401  (re-exported for mytrader callers)

MY_TRADER_DIR = Path(__file__).resolve().parent.parent  # mytrader -> my-trader
HOLDINGS_MD_PATH = MY_TRADER_DIR / "holdings.md"
WATCHLIST_MD_PATH = MY_TRADER_DIR / "watchlist.md"
MONITOR_REPORT_PATH = MY_TRADER_DIR / "monitor-report.md"
PENDING_CANDIDATES_MD_PATH = MY_TRADER_DIR / "synced-candidates-pending-review.md"

AI_POSTCRASH_BUCKET = "ai_postcrash"  # watchlist bucket for major AI-boom names
                                       # (chip/foundry monopoly, hyperscaler platform
                                       # dominance) deliberately not bought at current
                                       # AI-bubble valuations — revisit if/when the
                                       # sector corrects. Rendered as its own section
                                       # in watchlist.md by snapshot.py.

CRASH_DISCOUNT_BUCKET = "4"  # Bucket 4, added 2026-07-25: great, durable companies
                              # (KO, BRK-B, TSLA, UBER) Shaun wants to buy at a
                              # crash-discount price rather than today's price — not
                              # timed around a specific bubble like ai_postcrash, and
                              # not a sell-after-recovery trade like Bucket 2. Once
                              # actually bought, migrates to Bucket 1. Rendered as its
                              # own section in watchlist.md by snapshot.py.

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
ROE_FLAG_THRESHOLD_PCT = 5.0  # balance_sheet.py's fallback proxy when debt/equity and
                                # current ratio are both unavailable (common for banks/
                                # financials) — flag if return on equity is weak.

# checks/opportunity.py — confirmed 2026-07-19: Monitor was only ever surfacing risk
# warnings, never "this looks worth a look" positive signals. Rebuilt 2026-07-19, same
# day, after Shaun called out the first version's arbitrary thresholds ("research a
# bunch of tests and mental models that expert and successful traders use") — every
# threshold below is the ACTUAL stated criterion from the matching
# investments/briefs-finance/principles/*.md file, not invented. PE_CHEAP_THRESHOLD
# (above) is reused as Graham's fallback leg when P/B is unavailable.
OPPORTUNITY_GRAHAM_NUMBER_MAX = 22.5  # graham.md: "combined P/E x P/B < 22.5" — the
                                        # actual Graham Number formula from The
                                        # Intelligent Investor, not an arbitrary cutoff.
OPPORTUNITY_MIN_PLAUSIBLE_PB = 0.1  # yfinance's priceToBook is unreliable for
                                      # dual-share-class companies (verified against
                                      # BRK-B: book value from the wrong share class
                                      # produced P/B=0.00097) — treat anything below
                                      # this floor as bad data, not a real signal.
OPPORTUNITY_PEG_MAX = 1.0  # lynch.md: "PEG ratio... PEG < 1 is attractive."
OPPORTUNITY_ROE_MIN_PCT = 15.0  # buffett.md: "High return on equity (15%+
                                  # consistently)"; smith.md: "ROCE consistently above
                                  # 15%" — same number, independently stated twice.
OPPORTUNITY_DIP_FLAG_PCT = 10.0  # marks.md/neilson.md: contrarian "unloved... out of
                                   # favour" / "discount... for non-structural
                                   # reasons" — magnitude is still a best-guess
                                   # starting point (the principle files don't state a
                                   # specific %), but the direction and "no other
                                   # active flags" gate are the sourced part.
OPPORTUNITY_SCORE_FLAG = 70  # Briefs Finance likelihood score at/above this = high
                               # conviction, best-guess starting point (0-100 scale).

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

# Added 2026-07-30 -- not part of tool-preplan.md's original 5-indicator Phase C list,
# added on request as a market-implied (forward-looking) complement to the
# already-tracked recession_prob/yield_curve signals, which are backward/coincident.
FRED_BREAKEVEN_10Y_SERIES = "T10YIE"
FRED_BREAKEVEN_5Y5Y_FORWARD_SERIES = "T5YIFR"  # Fed's own preferred longer-run
                                                 # inflation-expectations gauge --
                                                 # strips out near-term noise the 10Y
                                                 # breakeven still carries.
INFLATION_EXPECTATION_FLAG_PCT = 3.0  # live 2026-07-29 reading: 5Y5Y forward 2.28%,
                                        # 10Y breakeven 2.26% -- both still anchored
                                        # close to the Fed's 2% target despite CPI
                                        # running at 4.2% (investment-strategy.md),
                                        # meaning the bond market currently reads the
                                        # inflation shock as transitory, not structural.
                                        # Flag set with headroom above today's level so
                                        # a genuine de-anchoring move would trigger it.
