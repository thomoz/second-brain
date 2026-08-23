"""Path constants and thresholds for Goat Phase 1 -- the 150-day-MA holdings exit check."""

from __future__ import annotations

from pathlib import Path

from scripts.config import DB_PATH  # noqa: F401  (re-exported for goat callers)

GOAT_DIR = Path(__file__).resolve().parent.parent  # goat -> investments/goat
GOAT_MONITOR_REPORT_PATH = GOAT_DIR / "goat-report.md"

# 150-day-MA exit check, per investments/goat/HANDOFF.md Phase 1 -- the source
# webinar notes only say "reasonably below" with no number. The original v1
# (2026-08-11) synthesized two sourced technical-analysis conventions: Stan
# Weinstein's Stage Analysis 6% lower-envelope, plus a standard 2+ consecutive-day
# whipsaw filter. Shaun explicitly overrode both 2026-08-16 ("I need to be alerted
# via whatsapp AS SOON AS IT DROPS BELOW THE 150DMA... as soon as it crosses, not
# 6% after") -- he wants the earliest possible signal and is knowingly accepting
# more false positives (a dip that bounces back the next day still alerts) in
# exchange for speed. Flag on ANY close below the MA, on day one:
GOAT_MA_LONG_DAYS = 150
GOAT_MA_HISTORY_LOOKBACK_DAYS = 400  # calendar days fetched -- comfortably exceeds
                                        # 150 trading days (~7 months) plus margin
                                        # for weekends/holidays, same margin
                                        # philosophy as GOLD_MA_HISTORY_LOOKBACK_DAYS
                                        # (500 for a 200-day MA).
GOAT_150DMA_FLAG_PCT = 0.0  # any close at/below the 150DMA counts as a qualifying
                              # day -- was 6.0 (Weinstein's lower-envelope
                              # convention) until Shaun's 2026-08-16 override, see
                              # comment above.
GOAT_150DMA_MIN_CONSECUTIVE_DAYS = 1  # flags on the first qualifying day, no
                                         # whipsaw-confirmation wait -- was 2 until
                                         # Shaun's 2026-08-16 override, see comment
                                         # above. NOTE: this only removes the
                                         # *confirmation delay* within a given
                                         # day's batch check -- the monitor itself
                                         # still runs once daily (EOD), so this
                                         # alone does not give same-day/intraday
                                         # alerting. True "as it happens" alerting
                                         # needs a separate intraday-polling build
                                         # (see HANDOFF.md).

# Sector rotation ranking + breakout signal, per investments/goat/HANDOFF.md Phase 2.
# Scope resolved with Shaun 2026-08-11: this signal is 50DMA cross-detection +
# 50DMA slope-turn ONLY -- the "heartbeat" consolidation pattern stays deferred to
# Phase 3 (unresearched, acknowledged hardest part of the project). Do not add a
# heartbeat/consolidation threshold here.
GOAT_SECTOR_ETFS: dict[str, str] = {
    "XLK": "Technology", "XLF": "Financials", "XLE": "Energy",
    "XLV": "Health Care", "XLY": "Consumer Discretionary", "XLP": "Consumer Staples",
    "XLI": "Industrials", "XLB": "Materials", "XLU": "Utilities",
    "XLRE": "Real Estate", "XLC": "Communication Services",
}  # The 11 SPDR Select Sector ETFs -- State Street's own standard, free,
   # GICS-aligned sector-rotation universe. Per HANDOFF.md's answer to Shaun's Q1
   # ("is there a free way to see which sectors are rising/falling?").

GOAT_BANNED_TICKERS: set[str] = {"XLI"}  # Banned per Shaun 2026-08-17 -- RTX Corp
    # (defense contractor) is a top-5 holding (~5.2%). Stays in GOAT_SECTOR_ETFS
    # above (still shown in sector-ranking.md for rotation-comparison context) but
    # is never staged as a breakout candidate and can never be promoted, even
    # manually -- see monitor._stage_new_sector_candidates and
    # main.cmd_promote_candidate.

GOAT_SECTOR_HISTORY_LOOKBACK_DAYS = 400  # calendar days -- same margin philosophy
                                            # as GOAT_MA_HISTORY_LOOKBACK_DAYS,
                                            # comfortably exceeds the rank window +
                                            # 50-day MA + slope lookback below.
GOAT_SECTOR_RANK_WINDOW_TRADING_DAYS = 63  # ~3 calendar months of trading days --
                                              # v1 starting guess per HANDOFF.md
                                              # (Shaun's own webinar notes cite
                                              # multi-month-to-multi-year heartbeat
                                              # timeframes but state no exact
                                              # rank-window number) -- flagged
                                              # tunable, not literature-final.
GOAT_SECTOR_MA_SHORT_DAYS = 50  # the moving average whose cross/slope IS the entry
                                   # signal per the webinar notes (Step 1) --
                                   # distinct from exit_check's 150-day exit MA.
GOAT_SECTOR_SLOPE_LOOKBACK_DAYS = 5  # today vs. N trading days ago -- same idiom
                                        # as gold_technicals.compute_trend's
                                        # ma50_rising check (ma.iloc[-1] >
                                        # ma.iloc[-6]).
GOAT_SECTOR_CROSS_RECENCY_DAYS = 10  # a cross older than this no longer counts as
                                        # "just crossed" (Shaun's own words
                                        # describing the LULU chart that prompted
                                        # this feature) -- keeps the breakout signal
                                        # a fresh event rather than a standing
                                        # condition that would re-fire indefinitely.
                                        # v1/tunable, not literature-sourced.

GOAT_SECTOR_RANKING_MD_PATH = GOAT_DIR / "sector-ranking.md"
GOAT_SECTOR_CANDIDATES_MD_PATH = GOAT_DIR / "sector-candidates-pending-review.md"

# Industry rotation ranking, per .agent/plans/goat-industry-rotation-ranking.md --
# extends sector rotation (above) down to Finviz's ~143 finer-grained industry
# groups, prompted by Shaun sharing Finviz "Money Flowing IN/OUT" screenshots
# 2026-08-23. Full taxonomy sourced from finviz.com/groups?g=industry, fetched
# 2026-08-23 -- embedded verbatim as the canonical reference list.
GOAT_FINVIZ_INDUSTRIES: list[str] = [
    "Advertising Agencies", "Aerospace & Defense", "Agricultural Inputs", "Airlines",
    "Airports & Air Services", "Aluminum", "Apparel Manufacturing", "Apparel Retail",
    "Asset Management", "Auto & Truck Dealerships", "Auto Manufacturers", "Auto Parts",
    "Banks - Diversified", "Banks - Regional", "Beverages - Brewers",
    "Beverages - Non-Alcoholic", "Beverages - Wineries & Distilleries", "Biotechnology",
    "Broadcasting", "Building Materials", "Building Products & Equipment",
    "Business Equipment & Supplies", "Capital Markets", "Chemicals", "Coking Coal",
    "Communication Equipment", "Computer Hardware", "Confectioners", "Conglomerates",
    "Consulting Services", "Consumer Electronics", "Copper", "Credit Services",
    "Department Stores", "Diagnostics & Research", "Discount Stores",
    "Drug Manufacturers - General", "Drug Manufacturers - Specialty & Generic",
    "Education & Training Services", "Electrical Equipment & Parts",
    "Electronic Components", "Electronic Gaming & Multimedia",
    "Electronics & Computer Distribution", "Engineering & Construction",
    "Entertainment", "Farm & Heavy Construction Machinery", "Farm Products",
    "Financial Conglomerates", "Financial Data & Stock Exchanges", "Food Distribution",
    "Footwear & Accessories", "Furnishings, Fixtures & Appliances", "Gambling", "Gold",
    "Grocery Stores", "Health Information Services", "Healthcare Plans",
    "Home Improvement Retail", "Household & Personal Products",
    "Industrial Distribution", "Information Technology Services",
    "Insurance - Diversified", "Insurance - Life", "Insurance - Property & Casualty",
    "Insurance - Reinsurance", "Insurance - Specialty", "Insurance Brokers",
    "Integrated Freight & Logistics", "Internet Content & Information",
    "Internet Retail", "Leisure", "Lodging", "Lumber & Wood Production",
    "Luxury Goods", "Marine Shipping", "Medical Care Facilities", "Medical Devices",
    "Medical Distribution", "Medical Instruments & Supplies", "Metal Fabrication",
    "Mortgage Finance", "Oil & Gas Drilling", "Oil & Gas E&P",
    "Oil & Gas Equipment & Services", "Oil & Gas Integrated", "Oil & Gas Midstream",
    "Oil & Gas Refining & Marketing", "Other Industrial Metals & Mining",
    "Other Precious Metals & Mining", "Packaged Foods", "Packaging & Containers",
    "Paper & Paper Products", "Personal Services", "Pharmaceutical Retailers",
    "Pollution & Treatment Controls", "Publishing", "Railroads",
    "Real Estate - Development", "Real Estate Services", "Recreational Vehicles",
    "REIT - Diversified", "REIT - Healthcare Facilities", "REIT - Hotel & Motel",
    "REIT - Industrial", "REIT - Mortgage", "REIT - Office", "REIT - Residential",
    "REIT - Retail", "REIT - Specialty", "Rental & Leasing Services",
    "Residential Construction", "Resorts & Casinos", "Restaurants",
    "Scientific & Technical Instruments", "Security & Protection Services",
    "Semiconductor Equipment & Materials", "Semiconductors", "Shell Companies",
    "Silver", "Software - Application", "Software - Infrastructure", "Solar",
    "Specialty Business Services", "Specialty Chemicals",
    "Specialty Industrial Machinery", "Specialty Retail",
    "Staffing & Employment Services", "Steel", "Telecom Services",
    "Textile Manufacturing", "Thermal Coal", "Tobacco", "Tools & Accessories",
    "Travel Services", "Trucking", "Uranium", "Utilities - Diversified",
    "Utilities - Independent Power Producers", "Utilities - Regulated Electric",
    "Utilities - Regulated Gas", "Utilities - Regulated Water",
    "Utilities - Renewable", "Waste Management",
]  # 143 industries -- must match Finviz's own count exactly; a mismatch here would
   # silently skew the "Not Covered" gap list in industry-ranking.md.

GOAT_INDUSTRY_ETFS: dict[str, str] = {
    "ITA": "Aerospace & Defense", "JETS": "Airlines", "CARZ": "Auto Manufacturers",
    "KBWB": "Banks - Diversified", "KRE": "Banks - Regional", "XBI": "Biotechnology",
    "XHB": "Building Products & Equipment", "IAI": "Capital Markets",
    "COPX": "Copper", "ESPO": "Electronic Gaming & Multimedia",
    "PAVE": "Engineering & Construction", "BJK": "Gambling", "GDX": "Gold",
    "IHF": "Healthcare Plans", "KIE": "Insurance - Diversified",
    "FDN": "Internet Content & Information", "IBUY": "Internet Retail",
    "WOOD": "Lumber & Wood Production", "BOAT": "Marine Shipping",
    "IHI": "Medical Devices", "XOP": "Oil & Gas E&P",
    "XES": "Oil & Gas Equipment & Services", "CRAK": "Oil & Gas Refining & Marketing",
    "PICK": "Other Industrial Metals & Mining", "INDS": "REIT - Industrial",
    "REM": "REIT - Mortgage", "ITB": "Residential Construction",
    "EATZ": "Restaurants", "SMH": "Semiconductors", "SIL": "Silver",
    "IGV": "Software - Application", "TAN": "Solar", "SLX": "Steel",
    "IYZ": "Telecom Services", "URA": "Uranium",
    "PHO": "Utilities - Regulated Water", "ICLN": "Utilities - Renewable",
    "MOO": "Agricultural Inputs", "EVX": "Waste Management",
}  # 39 of 143 Finviz industries with a real, dedicated, currently-trading ETF --
   # researched 2026-08-23 (Finviz taxonomy cross-referenced against SPDR/iShares/
   # VanEck/Invesco/Global X/First Trust/Pacer/AdvisorShares). dict[ticker, label]
   # shape mirrors GOAT_SECTOR_ETFS -- one ticker per industry only; where an ETF
   # plausibly fits two industries (e.g. IGV, BJK, IHI) only one label is kept here,
   # the other stays a gap -- see the plan's "Gotcha" note before adding a ticker
   # under two entries (silent overwrite, no error). The remaining 104 industries
   # have no dedicated ETF and are surfaced as a "Not Covered" list in
   # industry-ranking.md, never silently proxied -- Shaun's confirmed decision,
   # 2026-08-23. INDS and EVX are lower-liquidity, medium-confidence picks (not
   # individually web-verified this session) -- if either fails to resolve against
   # real yfinance data, drop that one row to the gap list rather than guessing a
   # replacement.

GOAT_INDUSTRY_HISTORY_LOOKBACK_DAYS = 400  # calendar days -- same margin philosophy
                                              # as GOAT_SECTOR_HISTORY_LOOKBACK_DAYS,
                                              # comfortably exceeds the 126-trading-
                                              # day rank window below.
GOAT_INDUSTRY_RANK_WINDOW_TRADING_DAYS = 126  # ~6 calendar months of trading days --
                                                 # matches the Finviz screenshots that
                                                 # prompted this feature. Deliberately
                                                 # a SEPARATE constant from
                                                 # GOAT_SECTOR_RANK_WINDOW_TRADING_DAYS
                                                 # (63/3-month) -- Shaun confirmed
                                                 # 2026-08-23 these do not need to
                                                 # match.
GOAT_INDUSTRY_RANKING_MD_PATH = GOAT_DIR / "industry-ranking.md"

# Intraday 150DMA live-check polling, per investments/goat/HANDOFF.md's
# "Intraday 150DMA Alerting" section (raised 2026-08-16) -- Shaun wants a
# WhatsApp alert as soon as a holding's LIVE price crosses below its 150DMA
# while the relevant market is still open, not at next morning's daily batch.
# This is genuinely a new, unresearched cadence choice -- v1/tunable, not
# literature-final, same as GOAT_SECTOR_RANK_WINDOW_TRADING_DAYS.
GOAT_LIVE_POLL_INTERVAL_MINUTES = 10  # tighter than the only existing
                                         # recurring-timer precedent in this repo
                                         # (second-brain-heartbeat.timer, every 30
                                         # min) to honor "as soon as it drops" --
                                         # each run is cheap because only
                                         # currently-open-market holdings get
                                         # fetched, not the whole holdings table.
                                         # NOTE: not programmatically linked to
                                         # second-brain-goat-live-check.timer's
                                         # OnCalendar=*:0/10 step -- if this is
                                         # ever tuned, update that file too.

# ASX/US regular-session local hours -- deliberately regular-session only, no
# pre/post-market, and deliberately no market-holiday calendar (a holiday just
# means fetch_current_price/fetch_close_history return stale/None data, which
# the existing per-ticker try/except already handles gracefully -- see
# HANDOFF.md's explicitly-deferred scope; a real holiday calendar is a separate
# follow-up, not built speculatively here).
GOAT_ASX_TZ = "Australia/Sydney"
GOAT_ASX_MARKET_OPEN = (10, 0)   # 10:00am Sydney local
GOAT_ASX_MARKET_CLOSE = (16, 0)  # 4:00pm Sydney local
GOAT_US_TZ = "America/New_York"
GOAT_US_MARKET_OPEN = (9, 30)    # 9:30am US Eastern
GOAT_US_MARKET_CLOSE = (16, 0)   # 4:00pm US Eastern

# S&P 500 heartbeat scanner, per investments/goat/HANDOFF.md Phase 3. See
# .agent/plans/goat-phase3-heartbeat-scanner.md's "RESEARCH RESOLVED" section
# for why BBW-percentile-squeeze was chosen over Minervini's VCP.
GOAT_HEARTBEAT_HISTORY_LOOKBACK_DAYS = 500  # calendar days -- same margin
                                               # philosophy as GOLD_MA_HISTORY_LOOKBACK_DAYS
                                               # (500 calendar days for a 200-day MA in
                                               # mytrader/config.py); here it must
                                               # comfortably cover the 252-trading-day BBW
                                               # percentile lookback below plus the 20-day
                                               # Bollinger period plus weekday/holiday margin.
GOAT_HEARTBEAT_BBW_PERIOD_DAYS = 20  # textbook Bollinger default -- same value as
                                        # mytrader.config.GOLD_TA_BOLLINGER_PERIOD_DAYS,
                                        # reused for consistency, not re-derived.
GOAT_HEARTBEAT_BBW_STD_MULTIPLIER = 2.0  # textbook default -- same value as
                                            # mytrader.config.GOLD_TA_BOLLINGER_STD_MULTIPLIER.
GOAT_HEARTBEAT_BBW_PERCENTILE_LOOKBACK_DAYS = 252  # ~1 trading year -- the window BBW's
                                                       # own rolling percentile is measured
                                                       # against (self-relative to each
                                                       # ticker's own volatility regime, not
                                                       # a universal fixed %). v1/tunable.
GOAT_HEARTBEAT_BBW_PERCENTILE = 10  # flag when BBW sits at/below its own trailing
                                       # GOAT_HEARTBEAT_BBW_PERCENTILE_LOOKBACK_DAYS-day
                                       # 10th percentile -- "near a 1-year volatility low".
                                       # v1/tunable, not literature-final, same status as
                                       # GOAT_SECTOR_CROSS_RECENCY_DAYS.
GOAT_HEARTBEAT_MIN_DURATION_DAYS = 63  # ~3 calendar months of trading days -- matches the
                                          # webinar's own "3 months minimum" and this
                                          # codebase's existing GOAT_SECTOR_RANK_WINDOW_TRADING_DAYS
                                          # precedent for that exact figure.
GOAT_HEARTBEAT_SQUEEZE_MIN_FRACTION = 0.8  # at least 80% of the trailing
                                              # GOAT_HEARTBEAT_MIN_DURATION_DAYS days must be
                                              # in-squeeze -- the webinar describes "smooth
                                              # up-down-up-down", not a perfectly unbroken
                                              # flat line, so a strict 100%-of-days
                                              # requirement would misfire on ordinary
                                              # single-day noise. v1/tunable.

# Fundamentals survival context, per HANDOFF.md's debt -> cash runway -> margins ->
# revenue growth -> cash generation priority order. Informational on every candidate,
# NOT a pass/fail gate -- confirmed with Shaun 2026-08-17 (gating on all 5 would
# disqualify almost the entire S&P 500). debt/equity reuses mytrader.config's existing
# DEBT_TO_EQUITY_FLAG threshold directly, not a new number.
GOAT_CASH_RUNWAY_FLAG_YEARS = 1.0  # cash-burning companies with less than this many
                                      # years of runway (totalCash / abs(freeCashflow))
                                      # combined with high debt/equity trip the
                                      # insolvency-risk suppression check below --
                                      # 1 year is a conservative, common
                                      # cash-runway-concern floor. v1/tunable.

GOAT_SP500_WIKI_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
GOAT_SP500_CACHE_TTL_DAYS = 7  # matches the weekly scan cadence -- no point
                                  # re-scraping Wikipedia more often than the scan itself
                                  # runs.
GOAT_SP500_USER_AGENT = "Mozilla/5.0 (compatible; SecondBrainGoat/1.0)"

# GICS Sector (Wikipedia's own column values) -> GOAT_SECTOR_ETFS label mapping.
# Only "Information Technology" actually differs from GOAT_SECTOR_ETFS's "Technology"
# -- the rest are written out explicitly anyway so a future Wikipedia label change
# fails loudly (KeyError on an unmapped sector) rather than silently dropping tickers.
GOAT_GICS_TO_ETF_SECTOR_LABEL: dict[str, str] = {
    "Information Technology": "Technology",
    "Financials": "Financials",
    "Energy": "Energy",
    "Health Care": "Health Care",
    "Consumer Discretionary": "Consumer Discretionary",
    "Consumer Staples": "Consumer Staples",
    "Industrials": "Industrials",
    "Materials": "Materials",
    "Utilities": "Utilities",
    "Real Estate": "Real Estate",
    "Communication Services": "Communication Services",
}

GOAT_HEARTBEAT_CANDIDATES_MD_PATH = GOAT_DIR / "heartbeat-candidates-pending-review.md"

# Insider trading scanner (OpenInsider), per investments/insider-trading-scanner-handoff.md
# and Shaun's 2026-08-17 clarification: he's after large open-market sells (potential
# "board member expects bad news" signal, plausibly $1M+) and $25k+ open-market buys.
# P/S trade-type codes only -- excludes grants (A), option exercises (M), gifts (G),
# tax-withholding sales (F), none of which reflect the same conviction signal.
# NOTE: the scraper itself (openinsider.py, incl. OPENINSIDER_BASE_URL/USER_AGENT)
# moved to mytrader/openinsider.py + mytrader/config.py 2026-08-19 -- goat depends on
# my-trader, not the reverse, so that's the only workspace-safe place for a module
# both this package and fourteen_crash_signals_daily_check's insider_trend.py share.
GOAT_INSIDER_PURCHASE_MIN_VALUE = 25_000  # matches OpenInsider's own
                                              # /latest-insider-purchases-25k floor.
                                              # Purchases stay dollar-gated -- Shaun's
                                              # 2026-08-17 "thresholds aren't helpful"
                                              # feedback was specifically about sells
                                              # (a CEO "bailing out"), not buys.
GOAT_INSIDER_SALE_MIN_VALUE = 1_000  # Shaun 2026-08-17: $25k/$100k dollar floors are
    # meaningless for a large-cap exec trying to exit quietly -- a $5M sale is trivial
    # against a $500M stake but alarming against a $5.5M one. Dropped to a near-zero
    # noise floor (filters literal fractional-share administrative trades only); the
    # real gate for sales is now GOAT_INSIDER_SALE_PCT_THRESHOLD_FIRST/_REPEAT below.
GOAT_INSIDER_SALE_LOOKBACK_DAYS = 90  # rolling window for detecting repeated smaller
    # sales by the same insider on the same ticker. Shaun 2026-08-17: "they could easily
    # sell most of their stock at 1% per day over three months" while staying under any
    # single-sale threshold every time. v1/tunable -- Shaun flagged this window itself
    # as something to revisit.
GOAT_INSIDER_SALE_PCT_THRESHOLD_FIRST = 10.0  # % of the insider's own position --
    # gates a sale when this insider has had no OTHER sale on this ticker within
    # GOAT_INSIDER_SALE_LOOKBACK_DAYS. Shaun's number, 2026-08-17.
GOAT_INSIDER_SALE_PCT_THRESHOLD_REPEAT = 1.0  # % of position -- much lower bar once
    # ANY prior sale by this same insider/ticker exists in the lookback window, to
    # catch the "salami slicing" pattern described above. Shaun's number, 2026-08-17.
GOAT_INSIDER_HOLDINGS_WATCH_LOOKBACK_DAYS = 5  # Form 4 must be filed within 2 US
    # business days of the trade -- 5 calendar days of slack covers weekends/holidays
    # on top of this scan's own daily cadence, without re-surfacing anything genuinely
    # stale. v1/tunable. NOTE: this gates which filings this RUN considers "fresh
    # enough to process" -- distinct from GOAT_INSIDER_SALE_LOOKBACK_DAYS's 90-day
    # pattern-detection window, which looks back across many runs' worth of history.
GOAT_INSIDER_DISCOVERY_LOOKBACK_DAYS = 5  # same reasoning as above -- a safety net on
    # top of OpenInsider's own latest-first page ordering.
GOAT_INSIDER_SCAN_REPORT_PATH = GOAT_DIR / "insider-scan-report.md"

GOAT_INSIDER_PRICE_FLAG_TIERS: list[tuple[int, float]] = [
    (7, 2.5), (14, 5.0), (21, 7.5), (28, 10.0),
]  # (max_days_since_trade, threshold_pct), ascending. Shaun's own numbers,
    # 2026-08-20 -- supersedes the old flat GOAT_INSIDER_PRICE_FLAG_PCT (15.0)
    # immediately, applied to BOTH the live insider-scan report's confirms-signal
    # flag AND the price-outcomes dataset's "confirmed" labeling, so the two never
    # drift apart. A fast, small move is treated as more meaningful than a slow,
    # large one (price moves grow with elapsed time under normal random-walk
    # drift, so a flat threshold was implicitly biased the wrong way).
GOAT_INSIDER_PRICE_FLAG_PCT_TAIL = 12.5  # threshold once days_since_trade exceeds
    # the last tier's max_days (28) -- Shaun's number, 2026-08-20.

GOAT_INSIDER_OUTCOME_HORIZONS_DAYS: list[int] = [1, 3, 7, 14, 30, 90, 180]  # snapshot
    # schedule for goat_insider_price_outcomes. Includes 180 to match the max
    # tracking window below (Shaun 2026-08-20: raised from 90 -> 180 days) --
    # without a matching 180d horizon the extended window would collect no new
    # snapshot past day 90, defeating the point of the extension.
GOAT_INSIDER_OUTCOME_MAX_TRACKING_DAYS = 180  # Shaun 2026-08-20: raised from the
    # handoff doc's original 90-day proposal to better match how insider-trading
    # literature typically studies outcomes (6-12 months) -- filings older than
    # this stop maturing new snapshot horizons. Distinct from
    # GOAT_INSIDER_PRICE_STALE_DAYS (90, unchanged) -- that constant is about the
    # existing report's "may be stale" annotation for repeated-sale-pattern
    # detection, a different concern.
GOAT_INSIDER_OUTCOME_BENCHMARK_TICKER = "SPY"  # excess-return benchmark for every
    # slice -- SPY-only, not per-sector (most discovery candidates are smaller-cap
    # names outside goat_sp500_constituents coverage anyway). "Buys rose 60% of
    # the time" during a market rally isn't an insider-specific signal without
    # this -- excess return isolates the trade-attributable part.
GOAT_INSIDER_PATTERN_MIN_SAMPLE = 20  # minimum filings in a slice before the
    # pattern report states a conclusion instead of "not enough data yet". Trade
    # dates only go back to 2026-08-12 as of this build -- most slices are
    # expected to say "not enough data yet" for the first several weeks, that's
    # expected, not a bug.
GOAT_INSIDER_CLUSTER_WINDOW_DAYS = 7  # multiple distinct insiders on the same
    # ticker/trade_type within this many days counts as cluster buying/selling --
    # v1/tunable, rounded up slightly from the GOAT_INSIDER_HOLDINGS_WATCH_
    # LOOKBACK_DAYS/GOAT_INSIDER_DISCOVERY_LOOKBACK_DAYS precedent (5 days).

GOAT_INSIDER_PATTERN_ANALYSIS_PATH = GOAT_DIR / "insider-pattern-analysis.md"

GOAT_INSIDER_PRICE_STALE_DAYS = 90  # matches GOAT_INSIDER_SALE_LOOKBACK_DAYS's window --
    # past this many days since the trade, a price move is more likely broad market
    # drift than a reaction to the insider signal, so it's annotated, not hidden

# Strait of Hormuz war-risk tracking, per Shaun's 2026-08-18 request -- two free/
# scrapeable proxies since neither the Baltic Exchange's TD3C index nor JWC's
# lloydswordings.com circular archive offer a free API (confirmed via research
# before building this). Deliberately reports "info"/"changed since last check"
# rather than an auto-classified escalation/de-escalation verdict -- reading
# whether a move or a new circular means de-escalating or escalating requires
# judgment this tool can't make reliably, same philosophy as check_gold_trend's
# "info, not flag" treatment in mytrader/macro_indicators.py.
GOAT_BWET_TICKER = "BWET"  # Breakwave Tanker Shipping ETF -- 90% TD3C VLCC / 10%
    # TD20 Suezmax freight futures, the closest free (yfinance) proxy for
    # Gulf/Hormuz tanker war-risk cost; also reflects broader tanker-cycle noise
    # unrelated to Hormuz specifically, so the report says this explicitly rather
    # than presenting it as a clean signal.
GOAT_BWET_LOOKBACK_DAYS = 14  # shorter than DXY_LOOKBACK_DAYS's 90 -- tanker rates
    # can move sharply within days around a Hormuz escalation/de-escalation event,
    # a multi-month window would smear that out.
GOAT_BWET_FLAG_MOVE_PCT = 15.0  # both directions meaningful: a spike often reflects
    # rising war-risk premiums/reduced ship availability, a sharp drop often
    # reflects risk easing -- so this flags on abs(move), not a one-sided threshold.
GOAT_LMA_JWC_URL = "https://lmalloyds.com/committee/joint-war-committee/"
GOAT_LMA_JWC_USER_AGENT = "Mozilla/5.0 (compatible; SecondBrainGoat/1.0)"
GOAT_HORMUZ_REPORT_PATH = GOAT_DIR / "hormuz-risk-report.md"
    # (candidates are never auto-removed, per my-trader's no-auto-delete convention).
