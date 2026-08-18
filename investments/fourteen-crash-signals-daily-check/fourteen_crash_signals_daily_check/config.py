"""Path constants and thresholds for the Fourteen Crash Signals daily check --
Phase 1 (4 of 14 markers + the shared hot-company watchlist layer). See the
source handoff (investments/my-trader/14-signals-crash-warning-handoff.md) for
the full 14-marker fact-check and both rounds of resolved decisions."""

from __future__ import annotations

from pathlib import Path

from scripts.config import DB_PATH  # noqa: F401  (re-exported for this package's callers)

SIGNALS_DIR = Path(__file__).resolve().parent.parent  # package -> investments/fourteen-crash-signals-daily-check
SIGNALS_REPORT_PATH = SIGNALS_DIR / "signals-report.md"

# Hot-company watchlist -- see the Phase 1 plan's Design Decision #1 for full
# rationale. v1/tunable, same status as GOAT_SECTOR_RANK_WINDOW_TRADING_DAYS.
# Shared by every per-issuer marker in this package, including market_cap_milestone
# (Shaun 2026-08-18: scanning the full ~500-name S&P 500 for marker 10 took ~16
# minutes in practice -- narrowing to "the top N most active players in whichever
# sector is currently hot" is both faster and thematically consistent with the
# marker's own historical grounding, e.g. Cisco overtaking Microsoft was itself a
# hot-sector story, not a broad-market scan).
SIGNALS_HOT_WATCHLIST_MIN_MARKET_CAP = 100_000_000_000  # $100B mega-cap floor
SIGNALS_HOT_WATCHLIST_TOP_N = 10  # Shaun's own number, 2026-08-18 ("top 10 most
                                     # active players in the industry") -- was 8
                                     # (the count of names the video/fact-check
                                     # named) until this correction.

# Marker 14 -- high-yield credit spread streak ("the master signal").
# Deliberately separate from mytrader.config.CREDIT_SPREAD_FLAG_PCT/FRED_HY_OAS_SERIES's
# existing single-day check -- see the Phase 1 plan's Design Decision #2.
SIGNALS_CREDIT_SPREAD_SERIES = "BAMLH0A0HYM2"  # same FRED series, different threshold/shape
SIGNALS_CREDIT_SPREAD_STREAK_FLAG_PCT = 3.5  # the video's own historical trigger level
SIGNALS_CREDIT_SPREAD_STREAK_TRADING_DAYS = 21  # ~1 trading month
SIGNALS_CREDIT_SPREAD_LOOKBACK_DAYS = 45  # calendar days fetched -- comfortably covers
                                             # 21 trading days + weekends, same margin
                                             # philosophy as GOAT_MA_HISTORY_LOOKBACK_DAYS

# Marker 5 -- margin debt YoY growth, from FINRA's own published spreadsheet.
SIGNALS_MARGIN_DEBT_URL = "https://www.finra.org/sites/default/files/2021-03/margin-statistics.xlsx"
SIGNALS_MARGIN_DEBT_YOY_FLAG_PCT = 40.0  # v1/tunable -- video's own framing: extreme
    # YoY growth "last seen at the peaks of 2000, 2007, and 2021"; not a literature-final number.

# Marker 8 -- insider selling, aggregate 365-day trend against the hot watchlist.
SIGNALS_INSIDER_TREND_LOOKBACK_DAYS = 365
SIGNALS_INSIDER_TREND_MIN_VALUE = 1_000  # near-zero floor, same philosophy as
                                             # GOAT_INSIDER_SALE_MIN_VALUE
SIGNALS_INSIDER_TREND_NET_SELL_FLAG_RATIO = 3.0  # v1/tunable -- see the plan's Design Decision #3

# Marker 10 -- most-valuable-company milestone.
SIGNALS_MARKET_CAP_MILESTONE_STEP = 500_000_000_000  # $500B round-number rungs
