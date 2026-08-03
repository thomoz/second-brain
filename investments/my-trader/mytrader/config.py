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

# checks/scale.py display anchors, added 2026-08-03 -- the "good" end of the 0-10
# scale hint shown next to debt/equity and current ratio. Not new signals/verdicts
# (DEBT_TO_EQUITY_FLAG/CURRENT_RATIO_FLAG above are unchanged and still the only
# flag-trigger logic) -- just the other end of the display range.
DEBT_TO_EQUITY_IDEAL = 0.0  # debt-free is the top of the scale
CURRENT_RATIO_HEALTHY = 2.0  # conventional "2:1 is healthy" liquidity rule of thumb
                               # (same class of citation as HOUSING_P2I_FLAG_RATIO's
                               # "~2.5-3x considered affordable by convention" below)
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

# Added 2026-07-30 -- investment-strategy.md's "credit stress" job (alongside
# valuation and recession-onset), previously flagged as a legitimate but
# unimplemented indicator ("High-yield credit spread (OAS)... a counter-check
# against the valuation metrics").
FRED_HY_OAS_SERIES = "BAMLH0A0HYM2"  # ICE BofA US High Yield Index OAS
CREDIT_SPREAD_FLAG_PCT = 5.0  # live 2026-07-28 reading: 2.84pp -- historically tight,
                                # no stress priced in. >=5pp is a widely-cited "credit
                                # markets pricing real stress" level (2008 peaked
                                # ~20pp, COVID ~11pp), so this flags well before
                                # crisis-level, not at it.

FRED_YIELD_CURVE_3M10Y_SERIES = "T10Y3M"  # the Fed's own preferred yield-curve
                                             # inversion metric (vs. the 2s10s already
                                             # tracked above) -- folded into
                                             # check_recession_signal() as an
                                             # additional data point/flag trigger
                                             # rather than a separate check, matching
                                             # how the bull/bear steepener refinement
                                             # was folded into that same check.

# Added 2026-07-30 -- FRED's own AU CPI series (AUSCPIALLQINMEI, via OECD relay) was
# found 18+ months stale, so this reads directly from the ABS's own published
# spreadsheet instead (see mytrader/abs_cpi.py). RBA_TARGET_BAND_* is the Reserve
# Bank of Australia's official inflation target -- live 2026-07-30 reading (June
# 2026 data): 3.8% YoY, already outside/above the band.
RBA_TARGET_BAND_LOW_PCT = 2.0
RBA_TARGET_BAND_HIGH_PCT = 3.0

# Added 2026-07-30 -- US CPI YoY via FRED's own units="pc1" (percent change from
# year ago) transform on the raw CPIAUCSL index, avoiding a second manual lookback
# query. The Fed's target is a single 2% point (not an official band like the RBA's),
# so this uses a commonly-cited +/-1pp tolerance range as a reasonable "comfortable"
# band -- live 2026-07-30 reading (June 2026 data): 3.46% YoY, already above it.
FRED_US_CPI_SERIES = "CPIAUCSL"
US_CPI_TARGET_BAND_LOW_PCT = 1.0
US_CPI_TARGET_BAND_HIGH_PCT = 3.0

# Added 2026-07-30 -- UK CPI YoY read directly from the ONS (mytrader/ons_cpi.py),
# same realized/backward-looking job as us_cpi/australia_cpi. BoE's target is a
# single 2% point (like the Fed's, not an official band like the RBA's) -- same
# +/-1pp tolerance approximation. Live 2026-07-30 reading (June 2026 data): 2.6%
# YoY, within this band (unlike AU/US currently).
UK_CPI_TARGET_BAND_LOW_PCT = 1.0
UK_CPI_TARGET_BAND_HIGH_PCT = 3.0

# Added 2026-08-03 -- SEC EDGAR filing reads for principles_fit's thesis (see
# .agent/plans/sec-filings-principles-fit.md). SEC_USER_AGENT is a legally-required
# descriptive header per SEC's fair-access policy -- confirmed with Shaun, do not
# change without asking (a generic/missing User-Agent can get the IP rate-limited).
SEC_USER_AGENT = "Shaun Thomson thomoz@outlook.com"
SEC_CIK_MAP_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_SUBMISSIONS_URL_TEMPLATE = "https://data.sec.gov/submissions/CIK{cik_padded}.json"
SEC_ARCHIVES_URL_TEMPLATE = (
    "https://www.sec.gov/Archives/edgar/data/{cik}/{accession_no_dashes}/{document}"
)
SEC_CIK_MAP_REFRESH_DAYS = 30  # bulk ticker->CIK file changes rarely; a brand-new
                                 # IPO not yet in a <30-day-old cache is a known,
                                 # accepted gap -- not solved in v1, see SKILL.md.
SEC_FILING_TYPES = ("10-K", "10-Q", "DEF 14A")
SEC_REQUEST_DELAY_SECONDS = 0.2  # small courtesy delay between the handful of
                                    # sequential SEC requests one Find call can make
                                    # (index + up to 3 documents) -- well under SEC's
                                    # stated ~10 req/sec limit, defensive only.
SEC_FILING_SUMMARY_MODEL = "sonnet"  # LOCKED IN 2026-08-03 after a real side-by-side
                                        # comparison against "haiku" on KO's real 10-K
                                        # (resolved at test time, via the active Codex
                                        # backend, to gpt-5.4 vs gpt-5.4-mini -- see
                                        # sdk_compat's model-agnostic architecture rule).
                                        # Both tiers produced accurate, well-organized
                                        # summaries; sonnet's additionally closed with an
                                        # explicit synthesized investment-thesis paragraph
                                        # haiku's did not, which matters since this
                                        # summary feeds 9 downstream principle-grading
                                        # calls -- kept as the default on that margin.
SEC_MAX_SECTION_CHARS = 6000  # per-section cap fed into the summarization prompt --
                                 # mirrors scripts/score.py's own
                                 # file_content[:3000] truncation pattern for the same
                                 # "don't blow the prompt budget" reason.
SEC_MAX_RAW_DOCUMENT_BYTES = 10_000_000  # guard against a mislinked huge document;
                                            # a 10-K/10-Q/DEF14A primary document is
                                            # never legitimately this large.

# Added 2026-08-03 -- ASX Market Announcements reads for principles_fit's thesis (see
# .agent/plans/asx-announcements-principles-fit.md), the ASX-listed sibling of the
# SEC_* block above. ASX_USER_AGENT deliberately differs in kind from SEC_USER_AGENT:
# SEC's is a descriptive contact-email UA required by SEC's fair-access policy; ASX's
# access path runs through an Incapsula/Imperva WAF on the interstitial page (see
# .agent/plans/completed/asx-market-announcements-handoff.md), so a real browser UA is
# used there instead to avoid tripping bot detection -- not a fair-access header, a
# WAF-compatibility one.
ASX_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
ASX_ANNOUNCEMENTS_LIST_URL_TEMPLATE = (
    "https://www.asx.com.au/asx/v2/statistics/announcements.do"
    "?by=asxCode&asxCode={code}&timeframe=Y&year={year}"
)  # confirmed live 2026-08-03 against real BXB/WES data, see the handoff above.
ASX_ANNOUNCEMENT_INTERSTITIAL_URL_TEMPLATE = (
    "https://www.asx.com.au/asx/v2/statistics/displayAnnouncement.do?display=pdf&idsId={ids_id}"
)  # confirmed live 2026-08-03 -- the click-through legal interstitial whose HTML
   # embeds the real PDF URL in a hidden `pdfURL` form field, see the handoff above.
ASX_ANNOUNCEMENT_TYPES: dict[str, tuple[str, ...]] = {
    "Annual Report": ("annual report", "full year statutory accounts", "full-year statutory accounts"),
    "Half-Year Report": (
        "half year accounts", "half-year accounts", "half yearly report",
        "half year report", "half-year report", "appendix 4d",
    ),
}  # VALIDATED live 2026-08-03 against real BXB/WES announcement titles (Task 4.3) --
   # the originally-guessed "annual report"/"half year report" substrings alone missed
   # real filer wording: BXB's half-year financial statements are titled literally
   # "Half Year Accounts" (no "report"/"half-year" wording at all), and BXB's annual
   # equivalent is titled "Full Year Statutory Accounts" (no literal "annual report"
   # anywhere). WES uses more SEC-DEF14A-like conventional wording ("2025 Annual
   # Report (including Appendix 4E)", "2026 Half-year Report incorporating Appendix
   # 4D") so its original guesses matched fine. Deliberately does NOT match "annual
   # general meeting" / "full-year result presentation" / "full-year media release"
   # titles (also real, confirmed present) -- those are meeting notices and investor
   # decks, not the primary disclosure document this feature wants.
ASX_REQUEST_DELAY_SECONDS = 0.2  # mirrors SEC_REQUEST_DELAY_SECONDS; the WAF caution
                                    # above makes this more important here, not less.
ASX_ANNOUNCEMENT_SUMMARY_MODEL = "sonnet"  # reuses SEC_FILING_SUMMARY_MODEL's
                                              # already-locked-in tier as a starting
                                              # default, not a fresh evaluation -- PDF
                                              # text is noisier than SEC's clean HTML,
                                              # revisit after seeing real ASX-PDF-
                                              # derived summary quality.
ASX_MAX_SECTION_CHARS = 6000  # mirrors SEC_MAX_SECTION_CHARS.
ASX_MAX_RAW_PDF_BYTES = 20_000_000  # NOTE: intentionally 2x SEC_MAX_RAW_DOCUMENT_BYTES
                                       # -- confirmed live 2026-08-03: WES's real 2025
                                       # Annual Report PDF is 13.9MB and BXB's real
                                       # Full Year Statutory Accounts PDF is 10.3MB,
                                       # both of which SEC's 10MB-equivalent guard
                                       # would have rejected as "mislinked huge
                                       # document" -- ASX annual reports routinely run
                                       # much larger than SEC's clean HTML filings.
ASX_HEADING_CANDIDATES = (
    "operating and financial review",
    "review of operations",
    "risk management",
    "directors report",  # apostrophe deliberately omitted -- see
                           # _normalize_for_heading_search in asx_announcements.py.
)  # VALIDATED live 2026-08-03 against real fetched BXB Half-Year Accounts and WES
   # Annual Report PDFs (Task 4.3), replacing the originally-guessed
   # "principal risks"/"directors' report" list, which had two real, confirmed
   # problems: (1) "principal risks"/"key risks" appear ZERO times in either real
   # document -- not a real ASX heading convention, at least not for these filers;
   # (2) "directors' report" with a literal straight/curly apostrophe fails to match
   # real extracted text because pdfplumber renders the filer's typographic
   # apostrophe as a mangled replacement character in practice (confirmed: BXB's
   # real "Directors' Report" running header extracts as "Directors� Report"-
   # shaped text) -- apostrophe-bearing candidates must have the apostrophe stripped
   # before matching, both from the candidate and the extracted text.
