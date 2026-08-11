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
