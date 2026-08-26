"""Path constants and thresholds for the my-trader assessment engine."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from scripts.config import DB_PATH  # noqa: F401  (re-exported for mytrader callers)

MY_TRADER_DIR = Path(__file__).resolve().parent.parent  # mytrader -> my-trader
HOLDINGS_MD_PATH = MY_TRADER_DIR / "holdings.md"
WATCHLIST_MD_PATH = MY_TRADER_DIR / "watchlist.md"
MONITOR_REPORT_PATH = MY_TRADER_DIR / "my-trader-report.md"
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

# Bucket code -> plain-English framing, added 2026-08-13 for monitor.py's Holdings
# report (Shaun rated the report 35/100 for trader decision-usefulness -- a raw
# bucket code like "1" doesn't tell you a -20% dip is expected/acceptable there,
# vs the same move on a Bucket 2 tactical position). Buckets 3a/3b are gold's own
# core/tactical split (tool-preplan.md's "Bucket 3" section); "unassigned" is a
# plain watchlist-style holding with no strategic category yet (see
# feedback_watchlist_bucket_terminology memory: say "on the Watchlist", not
# "bucket unassigned", when talking to Shaun -- this label is for report text,
# not conversational framing).
BUCKET_LABELS = {
    "1": "Long-term hold — never timed, dips are expected and not a reason to act alone",
    "2": "Crash-trade tactical — bought for a crash trade, sold after recovery",
    "3a": "Gold core — permanent ballast position, never timed",
    "3b": "Gold tactical — timed sleeve, evaluate against your entry thesis",
    CRASH_DISCOUNT_BUCKET: "Crash-discount buy — watching to add more at a crash-driven discount",
    AI_POSTCRASH_BUCKET: "Post-Crash AI Watch — deliberately not buying at today's valuation",
    "unassigned": "No strategic bucket assigned yet",
}

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
# Added 2026-08-04 -- ETF-specific criteria (checks/etf_mechanics.py), built after the
# XMET (Betashares Energy Transition Metals ETF) bug showed the tool was grading funds
# against principles_fit's 9 stock-picking frameworks (Buffett/Graham/etc.), which
# grade individual operating businesses and don't apply to a diversified fund -- IVV
# and SPY had already independently landed ~35/100 there despite being exactly what
# they're supposed to be. These two thresholds are NOT sourced from
# investments/briefs-finance's principle files (those don't cover funds at all) --
# they're industry rules-of-thumb, same class of best-guess default as
# OPPORTUNITY_DIP_FLAG_PCT, confirmed with Shaun 2026-08-04.
ETF_AUM_FLAG_USD = 50_000_000.0  # widely-cited rule of thumb (ETF.com/Morningstar-
                                    # style coverage): funds below this level are
                                    # economically marginal for the issuer to keep
                                    # running -- real closure/delisting risk. Verified
                                    # this field (yfinance's totalAssets) populates for
                                    # both US- and AU-domiciled ETFs (XMET $129M,
                                    # PMGOLD $2.4B, IVV $888B all read live 2026-08-04).
ETF_AUM_HEALTHY_USD = 500_000_000.0  # 0-10 scale's "excellent" anchor -- 10x the flag
                                        # threshold, comfortably inside established-
                                        # liquid-fund territory. An anchor point for
                                        # format_scale's display range, not itself a
                                        # flag trigger -- same class as
                                        # DEBT_TO_EQUITY_IDEAL/CURRENT_RATIO_HEALTHY.
ETF_EXPENSE_RATIO_FLAG_PCT = 1.0  # Core index funds (IVV/VOO/SPY) run 0.03-0.09%;
                                     # actively-managed/thematic ETFs routinely run
                                     # 0.5-1.5%+, so 1.00%+ is a widely-cited "getting
                                     # expensive" line for a fund. yfinance's
                                     # netExpenseRatio is consistently unpopulated for
                                     # AU-domiciled ETFs (confirmed live against XMET/
                                     # PMGOLD/IXI.AX, all None) -- degrades to unknown
                                     # for those, same graceful-degradation pattern as
                                     # the FRED-backed macro checks.
ETF_EXPENSE_RATIO_CHEAP_PCT = 0.20  # matches real core index-fund pricing (IVV 0.03%
                                       # confirmed live).

# Added 2026-08-05 -- news/event search (checks/news_events.py), covering live
# catalysts fundamentals-only checks structurally can't see (M&A offers, lawsuits,
# credit downgrades, leadership turnover, short-seller reports). Confirmed live
# against ZIM: yfinance's own news feed (already fetched into TickerData.news,
# previously unused by any check) carried none of ZIM's live Hapag-Lloyd takeover
# story -- its 10 most recent items were generic Zacks-style market recaps -- but a
# single web search surfaced it immediately, including a live rival counter-bid
# neither yfinance nor a stale third-party video had. Runs via sdk_compat with
# allowed_tools=["WebSearch"] -- under the active Codex backend (confirmed live:
# sdk_compat.BACKEND == "codex") this uses Codex CLI's own tools.web_search flag,
# flat-rate on the ChatGPT subscription, not a separate paid search API.
NEWS_EVENTS_SUMMARY_MODEL = "sonnet"  # same Claude-shaped tier alias as
                                          # SEC_FILING_SUMMARY_MODEL/
                                          # ASX_ANNOUNCEMENT_SUMMARY_MODEL.
NEWS_EVENTS_CACHE_HOURS = 20.0  # short, time-based TTL -- unlike sec_filing_cache/
                                   # asx_announcement_cache (invalidated on a new
                                   # accession/announcement id), news has no version
                                   # identifier to key off, so this is roughly "once
                                   # per day" rather than "until something changes".

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

# Added 2026-08-07 -- Phase 1 gold-tracking macro indicators (see
# .agent/plans/gold-tracker-handoff.md and gold-tracker-phase1-indicators.md). Shaun
# holds gold via PMGOLD (ASX, bucket 3a, holdings.md) and recently added to the
# position. Thresholds below are best-guess defaults, not sourced from a specific
# stated criterion the way OPPORTUNITY_* thresholds are -- ship, then tune against
# real monitor-report.md readings (resolved 2026-08-07, same discipline as
# ETF_AUM_FLAG_USD above).
FRED_REAL_YIELD_10Y_SERIES = "DFII10"  # 10Y TIPS yield -- opportunity cost of
                                          # holding non-yielding gold; single most
                                          # important gold driver per handoff research.
REAL_YIELD_FLAG_NEGATIVE_PCT = 0.0  # flag when real yields go negative (bullish
                                       # catalyst for gold).
REAL_YIELD_FLAG_HIGH_PCT = 2.0  # flag when real yields climb above this (historically
                                   # pressures gold hard) -- two-sided band.

FRED_USD_INDEX_SERIES = "DTWEXBGS"  # Nominal Broad U.S. Dollar Index -- FRED over
                                       # yfinance DX-Y.NYB, resolved 2026-08-07 (keeps
                                       # this module's FRED-first pattern).
DXY_LOOKBACK_DAYS = 30  # compare today's DXY to ~30 days prior -- same
                          # today/prior lookback shape as STEEPENER_LOOKBACK_DAYS.
DXY_FLAG_MOVE_PCT = 3.0  # flag on a >3% move over the lookback window, not an
                           # absolute level (DXY doesn't have a natural "high/low"
                           # the way a bounded ratio does).

GOLD_FUTURES_TICKER = "GC=F"  # confirmed live 2026-08-07 via yfinance.
GOLD_MA_SHORT_DAYS = 50
GOLD_MA_LONG_DAYS = 200
GOLD_MA_HISTORY_LOOKBACK_DAYS = 500  # calendar days of history to fetch -- must
                                        # comfortably exceed GOLD_MA_LONG_DAYS
                                        # trading days plus enough trailing window
                                        # to find the most recent price/200DMA cross
                                        # (confirmed live 2026-08-07: last cross was
                                        # ~2 months before that date).
PMGOLD_YFINANCE_TICKER = "PMGOLD.AX"  # Shaun's actual holding (bucket 3a,
                                         # holdings.md) -- AUD-denominated, shown
                                         # alongside the USD futures series per the
                                         # 2026-08-07 "track both" decision.

SILVER_FUTURES_TICKER = "SI=F"
GOLD_SILVER_RATIO_FLAG_HIGH = 80.0  # commonly-cited historical-extreme high.
GOLD_SILVER_RATIO_FLAG_LOW = 50.0  # commonly-cited historical-extreme low.

VIX_TICKER = "^VIX"
VIX_FLAG_LEVEL = 30.0  # widely-cited crisis-adjacent level.

# Added 2026-08-07 -- Gold Outlook (technicals + historical backtest), see
# .agent/plans/gold-tracker-phase2-outlook.md. GOLD_TA_* are standard,
# widely-cited technical-analysis conventions (RSI 14/70/30, MACD 12/26/9, etc.
# -- textbook defaults). GOLD_BACKTEST_* are this plan's own methodology
# choices -- best-guess defaults, ship and revisit.

GOLD_TA_MA_FAST_DAYS = 20  # short-term trend leg; GOLD_MA_SHORT_DAYS (50) /
                             # GOLD_MA_LONG_DAYS (200) above are reused as-is.
GOLD_TA_RSI_PERIOD_DAYS = 14  # textbook default (Wilder's original).
GOLD_TA_RSI_OVERBOUGHT = 70.0
GOLD_TA_RSI_OVERSOLD = 30.0
GOLD_TA_RSI_BULLISH_ABOVE = 55.0  # "elevated" state boundary for the
                                     # state-conditioned backtest -- a healthy-
                                     # momentum zone short of overbought, not the
                                     # same threshold as GOLD_TA_RSI_OVERBOUGHT
                                     # (70), which flags exhaustion instead.
GOLD_TA_RSI_BEARISH_BELOW = 45.0  # "depressed" state boundary, same idea
                                     # mirrored below the midline. The 45-55 band
                                     # itself is the excluded "neutral" state --
                                     # not backtested, same treatment as
                                     # gold_silver_ratio's un-flagged middle range.
GOLD_TA_MACD_FAST_DAYS = 12  # textbook default.
GOLD_TA_MACD_SLOW_DAYS = 26
GOLD_TA_MACD_SIGNAL_DAYS = 9
GOLD_TA_STOCH_PERIOD_DAYS = 14  # textbook default.
GOLD_TA_STOCH_SMOOTHING_DAYS = 3
GOLD_TA_STOCH_OVERBOUGHT = 80.0
GOLD_TA_STOCH_OVERSOLD = 20.0
GOLD_TA_ATR_PERIOD_DAYS = 14  # textbook default (Wilder's original).
GOLD_TA_BOLLINGER_PERIOD_DAYS = 20  # textbook default.
GOLD_TA_BOLLINGER_STD_MULTIPLIER = 2.0
GOLD_TA_LEVEL_LOOKBACK_DAYS = 20  # trading days (~1 month) for the recent
                                     # swing high/low support/resistance proxy.
GOLD_TA_VOLUME_AVG_DAYS = 20

GOLD_BACKTEST_HISTORY_START = date(2000, 1, 1)  # comfortably before every
                                     # signal's earliest data (GC=F/SI=F
                                     # 2000-08-30, VIX 1990-01-02, DFII10
                                     # 2003-01-02, DTWEXBGS 2006-01-02).
GOLD_BACKTEST_TRAIN_VALIDATION_SPLIT_DATE = date(2018, 1, 1)  # fixed calendar
                                     # date -- only occurrences/states on/after
                                     # this date are ever reported.
GOLD_BACKTEST_FORWARD_HORIZONS_TRADING_DAYS = (1, 5)  # 1 trading day ~=
                                     # today/tomorrow, 5 trading days ~= this
                                     # week. Used by BOTH backtest methodologies
                                     # -- the 5 macro-signal episodes are cheap
                                     # to re-check at these short horizons too
                                     # (N is bounded by episode count either way,
                                     # not by horizon), and the 6 technical
                                     # indicator states are the whole reason
                                     # these horizons exist.
GOLD_BACKTEST_FORWARD_HORIZONS_MONTHS = (1, 3, 6, 12, 24)  # macro-signal
                                     # episodes only (see NOTES for why
                                     # technical-indicator states stop at 1
                                     # month) -- 3/6/12/24 matches briefs-
                                     # finance's own stock backtest + a 24m leg
                                     # for gold's longer cycles; 1m is this
                                     # plan's own addition for "this month".
GOLD_BACKTEST_MIN_EPISODE_GAP_DAYS = 60  # calendar days -- collapses
                                     # threshold-hugging noise into one episode
                                     # per genuine event for the 4 magnitude-
                                     # threshold macro signals. Does NOT apply
                                     # to gold_trend's cross episodes (already
                                     # discrete) or to any state-conditioned
                                     # technical indicator (state-conditioning
                                     # uses every day a state holds, not
                                     # discrete episodes -- there's nothing to
                                     # de-duplicate).
GOLD_BACKTEST_REFRESH_MAX_AGE_DAYS = 1  # Monitor calls
                                     # gold_backtest.get_cached_or_refresh() on
                                     # every run -- capped at ~1 day (not the
                                     # originally-planned week) so each day's
                                     # new price/FRED data is actually folded
                                     # into the historical dataset daily, per
                                     # Shaun's explicit correction 2026-08-07
                                     # ("each day's new data needs to be added
                                     # to the historical data") -- confirmed
                                     # cheap enough to run daily (a handful of
                                     # bulk fetches, not per-day loops), so
                                     # there's no real cost to refreshing this
                                     # often. The on-demand `gold-backtest` CLI
                                     # subcommand always force-refreshes
                                     # regardless of this cache.

# Added 2026-08-08 -- COT (Commitments of Traders) large-speculator positioning,
# a real gap identified in conversation (positioning/sentiment data the Outlook had
# zero coverage of) -- see .agent/plans/gold-tracker-phase2-outlook.md conversation
# history. CFTC's public Socrata API, free, no login/key required, weekly cadence
# (published every Friday, data as-of the prior Tuesday), history back to 1986
# (confirmed live 2026-08-08: 1927 weekly reports for COMEX gold).
COT_API_URL = "https://publicreporting.cftc.gov/resource/6dca-aqww.json"
COT_MARKET_NAME = "GOLD - COMMODITY EXCHANGE INC."  # COMEX gold futures, Legacy
                                     # report -- confirmed live 2026-08-08 against
                                     # the real Socrata dataset (distinct from
                                     # "PAX GOLD PERP STYLE", a crypto-synthetic
                                     # contract that also matches a looser filter).
COT_LOOKBACK_WEEKS = 156  # 3 years of weekly reports -- Larry Williams' original
                             # COT Index formulation's standard lookback, a
                             # widely-cited methodology (not an invented
                             # threshold): (current net - rolling min) /
                             # (rolling max - rolling min) * 100 over this window.
COT_EXTREME_LONG_PCT = 90.0  # COT Index >= this -- large speculators near their
                                # most-long in 3 years, the classic "crowded long"
                                # contrarian-watch level (Williams' own convention).
COT_EXTREME_SHORT_PCT = 10.0  # symmetric "crowded short" level.

# Added 2026-08-11 -- IBKR Holdings Sync (see investments/my-trader/ibkr-sync-handoff.md
# and .agent/plans/ibkr-holdings-sync.md). Local-only, read-only, on-demand -- never
# wired into monitor.py or any systemd unit. Live account confirmed with Shaun
# 2026-08-11; IB Gateway (not TWS) is the app he's running.
IBKR_HOST = "127.0.0.1"
IBKR_PORT = 4001  # IB Gateway, live account. Paper would be 4002; TWS equivalents are
                   # 7496 (live) / 7497 (paper), not used here.
IBKR_CLIENT_ID = 27  # arbitrary, must be unique per simultaneous API client connected
                      # to the same Gateway instance -- change if this ever collides.

# OpenInsider.com scraper config (mytrader/openinsider.py), moved here from
# goat/goat/config.py 2026-08-19 -- goat's insider_scan.py and
# fourteen_crash_signals_daily_check's insider_trend.py both already depend on
# my-trader, not the reverse, and the scraper itself only ever depended on
# mytrader.tickers -- this was the correct import direction to let a new Find-only
# check (checks/insider_selling.py) reuse it without a circular workspace dependency.
OPENINSIDER_BASE_URL = "http://openinsider.com"
OPENINSIDER_USER_AGENT = "Mozilla/5.0 (compatible; SecondBrainGoat/1.0)"

# Insider selling check (Find-only deep-dive, checks/insider_selling.py). Added
# 2026-08-19 after Shaun asked whether Chevron's Michael Wirth selling 90%+ of his
# CVX position would have been caught -- it wasn't, since goat's Holdings Watch only
# tracks tickers Shaun already holds. This closes that gap at Find time instead.
INSIDER_SELLING_LOOKBACK_DAYS = 30  # deliberately wider than goat's
    # GOAT_INSIDER_HOLDINGS_WATCH_LOOKBACK_DAYS (5d, tuned for a daily incremental
    # poll) -- Find is a one-shot deep dive with no persisted state between runs to
    # catch a sale a narrow window would miss. Shaun's number, 2026-08-19.
INSIDER_SELLING_MIN_VALUE = 1_000  # same near-zero noise floor as
    # GOAT_INSIDER_SALE_MIN_VALUE -- filters fractional-share administrative trades
    # only; the real gate is the pct-of-position threshold below.
INSIDER_SELLING_FLAG_PCT_THRESHOLD = 10.0  # % of the insider's own position --
    # matches GOAT_INSIDER_SALE_PCT_THRESHOLD_FIRST. No repeat-sale state exists in a
    # one-shot Find check (unlike goat's Holdings Watch), so there's one threshold
    # here, not a first/repeat pair.

# ---------------------------------------------------------------------------
# Cash-Value Scanner -- mytrader/cash_value_scan.py, per
# .agent/plans/cash-value-scanner.md. Scheduled daily on the VPS. Screens for
# companies trading near cash value: net cash (cash + short-term investments minus
# total debt) >= CASH_VALUE_RATIO_THRESHOLD of market cap, AND positive operating
# cash flow (free cash flow is shown + tagged, not a hard gate).
# Advisor-notes report only; no staging, no alerts. Shaun's idea 2026-08-26.
# ---------------------------------------------------------------------------
CASH_VALUE_REPORT_PATH = MY_TRADER_DIR / "cash-value-report.md"

CASH_VALUE_RATIO_THRESHOLD = 0.50  # qualifies when net cash / market cap >= this.
    # Higher = more of the share price is just the bank balance. 0.50 = "the market
    # values the whole operating business at ~50c on the dollar and hands the other
    # ~50c back as balance-sheet cash." Still squarely deep-value (a normal healthy
    # company runs 5-15% net cash / mcap; 20%+ is already cash-rich). Loosened from
    # 0.80 by Shaun 2026-08-26 after the first live run returned zero names -- 0.80
    # is near-net-net territory, effectively non-existent in developed markets.
CASH_VALUE_MICRO_CAP_TAG_USD = 50_000_000.0  # tag (NOT drop) US rows below this
    # market cap with "micro" -- cash-value micro-caps are disproportionately
    # distressed / illiquid, but Finviz's coarse filter (avg vol > 100K, price > $1)
    # already removes the untradeable shells and Shaun wants to eyeball everything.
    # Smaller = less liquid / higher risk. Shaun's call, 2026-08-26.
CASH_VALUE_MICRO_CAP_TAG_AUD = 75_000_000.0  # ~same threshold for AUD-denominated
    # ASX rows (rough USD->AUD, not a live FX rate -- this is a display tag only).
CASH_VALUE_EXCLUDED_SECTORS = frozenset({
    "Financial",           # Finviz's sector string
    "Financials",          # GICS / Wikipedia S&P/ASX 200 sector string
    "Financial Services",  # yfinance's .info["sector"] string
    "Real Estate",         # all three vocabularies agree on this one
})  # net cash is not a meaningful concept for a bank / REIT -- Shaun's call,
    # 2026-08-26. Checked against BOTH the coarse universe sector (Finviz/Wikipedia)
    # and yfinance's .info sector, which use different wording -- verified live
    # 2026-08-26 that the ASX 200 Wikipedia table says "Financials".
CASH_VALUE_REPORT_MAX_ROWS = 60  # if more than this qualify, show the top N by cash
    # ratio and note the overflow count. Ratio sort + the OCF gate should keep it
    # well under this in practice. v1 best-guess cap.
CASH_VALUE_FETCH_DELAY_SECONDS = 0.2  # pause between per-ticker yfinance .info calls
    # in the enrichment loop -- ~700 back-to-back lookups reliably trips Yahoo's
    # rate limit, and a throttled lookup is indistinguishable from "no data" (the
    # ticker silently drops). ~700 * 0.2s = ~2.5min added to a nightly job -- fine.
CASH_VALUE_DEGRADED_ASX_MIN_FRACTION = 0.20  # the S&P/ASX 200 is large-caps with
    # near-complete yfinance coverage, so it's a controlled reference set: if fewer
    # than this fraction of ASX constituents return balance-sheet data in a run,
    # Yahoo is hard-rate-limiting and the whole run is treated as degraded -- keep
    # the previous report with a banner rather than overwrite it with a throttled-
    # empty one (same instinct as the stale-Finviz banner). Healthy runs clear ~0.7+
    # (200 minus ~35 financials/REITs minus a few genuine data gaps).

# Finviz screener scraper (mytrader/finviz_screener.py) -- the US universe source for
# the cash-value scan. Coarse Price/Cash prefilter only; the precise net-cash test
# runs in the yfinance enrichment pass. Live-verified 2026-08-26: 492 matches / 25
# pages, public, no login. robots.txt disallows /screener?* and /export + /api/*,
# but not the legacy /screener.ashx path used here, and the export endpoints are
# never touched -- same acceptable-scrape class as openinsider.com / en.wikipedia.org
# already scraped in this repo.
FINVIZ_SCREENER_URL = "https://finviz.com/screener.ashx"
FINVIZ_USER_AGENT = (  # a real browser UA -- Finviz blocks obviously-bot UAs on
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "  # some paths,
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"              # same reason
)                                                                     # as ASX_USER_AGENT.
FINVIZ_SCREENER_FILTERS = "fa_pc_u3,geo_usa,sh_avgvol_o100,sh_price_o1"  # Price/Cash
    # < 3 + US-listed + avg vol > 100K + price > $1. P/C uses GROSS cash and net cash
    # <= gross cash, so net cash >= 80% of mcap implies P/C <= 1.25 -- a P/C < 3 net
    # safely contains every true positive. Lower P/C = more cash-like.
FINVIZ_SCREENER_ROWS_PER_PAGE = 20  # free tier; pagination is &r=1,21,41,...
FINVIZ_MAX_PAGES = 40  # safety cap (~25 pages of real data today) -- stop paginating
    # past this even if the end-of-results signal is somehow missed.
FINVIZ_REQUEST_DELAY_SECONDS = 0.5  # courtesy delay between sequential page GETs --
    # same class as SEC_REQUEST_DELAY_SECONDS (0.2), a little wider for a third-party
    # site with bot detection.

# S&P/ASX 200 constituent scrape (mytrader/asx200_universe.py) -- the ASX universe
# source. Wikipedia is scrape-friendly; a descriptive UA is enough (same style as
# OPENINSIDER_USER_AGENT). Live-verified 2026-08-26: a "Constituent companies"
# wikitable, 200 rows, columns Code / Company / Sector / Market Capitalisation (A$) /
# Headquarters. yfinance ticker form is <CODE>.AX.
ASX200_WIKI_URL = "https://en.wikipedia.org/wiki/S%26P/ASX_200"
ASX200_USER_AGENT = "Mozilla/5.0 (compatible; SecondBrainMyTrader/1.0)"
