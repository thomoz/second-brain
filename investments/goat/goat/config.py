"""Path constants and thresholds for Goat Phase 1 -- the 150-day-MA holdings exit check."""

from __future__ import annotations

from pathlib import Path

from scripts.config import DB_PATH  # noqa: F401  (re-exported for goat callers)

GOAT_DIR = Path(__file__).resolve().parent.parent  # goat -> investments/goat
GOAT_MONITOR_REPORT_PATH = GOAT_DIR / "monitor-report.md"

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
