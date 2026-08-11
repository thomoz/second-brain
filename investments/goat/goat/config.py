"""Path constants and thresholds for Goat Phase 1 -- the 150-day-MA holdings exit check."""

from __future__ import annotations

from pathlib import Path

from scripts.config import DB_PATH  # noqa: F401  (re-exported for goat callers)

GOAT_DIR = Path(__file__).resolve().parent.parent  # goat -> investments/goat
GOAT_MONITOR_REPORT_PATH = GOAT_DIR / "monitor-report.md"

# 150-day-MA exit check, per investments/goat/HANDOFF.md Phase 1 -- the source
# webinar notes only say "reasonably below" with no number. Synthesized from two
# sourced technical-analysis conventions (researched 2026-08-11, no exact
# precedent exists for this specific rule -- flagged as v1/tunable, not literature-
# final):
#   - Stan Weinstein's Stage Analysis uses a 6% lower envelope below a security's
#     long moving average (his version: 30-week MA on broad market indices) as a
#     breakdown/health threshold -- the closest well-documented match to this
#     exact "MA-based exit" framework. Applied here to the 150-day MA on
#     individual holdings, not Weinstein's original 30-week/index context, so
#     treat the % as a reasonable starting point, not a proven-for-this-exact-use
#     constant.
#   - Standard whipsaw-avoidance practice across trend-following systems requires
#     2+ consecutive daily closes past a moving-average threshold before treating
#     it as a real signal (not a single noisy day) -- matches the source notes'
#     own warning: "sometimes prices break through it slightly but come back up
#     above."
GOAT_MA_LONG_DAYS = 150
GOAT_MA_HISTORY_LOOKBACK_DAYS = 400  # calendar days fetched -- comfortably exceeds
                                        # 150 trading days (~7 months) plus margin
                                        # for weekends/holidays and the lookback
                                        # needed to check "2+ consecutive days",
                                        # same margin philosophy as
                                        # GOLD_MA_HISTORY_LOOKBACK_DAYS (500 for a
                                        # 200-day MA).
GOAT_150DMA_FLAG_PCT = 6.0  # close must be this many % below the 150DMA to count
                              # as a qualifying day (Weinstein's 6% lower-envelope
                              # convention).
GOAT_150DMA_MIN_CONSECUTIVE_DAYS = 2  # must hold for this many consecutive
                                         # trading days before flagging (standard
                                         # whipsaw filter).

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
