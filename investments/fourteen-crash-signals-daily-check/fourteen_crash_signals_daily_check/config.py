"""Path constants and thresholds for the Fourteen Crash Signals daily check --
Phase 1 (4 of 14 markers + the shared hot-company watchlist layer). See the
source handoff (investments/my-trader/14-signals-crash-warning-handoff.md) for
the full 14-marker fact-check and both rounds of resolved decisions."""

from __future__ import annotations

from datetime import date
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

# Marker 2 -- off-balance-sheet lease commitments (SEC EDGAR 10-K/10-Q "Leases" note,
# LLM-extracted dollar figure). See the Phase 2 handoff, Marker #2 resolution.
SIGNALS_LEASE_COMMITMENT_GROWTH_FLAG_PCT = 50.0  # v1/tunable, unbacktestable -- no
    # historical time series for this disclosure exists; Shaun's own framing, 2026-08-18:
    # retune after a few quarters of real report output.
SIGNALS_LEASE_NOTE_WINDOW_CHARS = 8000  # trailing window after the heading match --
    # mirrors sec_filings._find_def14a_heading_index's own window size.

# Marker 4 -- capex outruns cash flow (negative free cash flow while capex is large).
SIGNALS_CAPEX_MIN_FLAG_ABS = 10_000_000_000  # $10B sanity floor -- should never bind in
    # practice since watchlist.py already mega-cap-filters at $100B; insurance against a
    # data glitch, not a real threshold.

# Marker 9 -- the Super Bowl signal (date-reminder + manual-check-flag; no structured
# free data source exists for "% of ads that were AI-related" -- see the handoff).
SIGNALS_NEXT_SUPER_BOWL_DATE = date(2027, 2, 14)  # Super Bowl LXI, SoFi Stadium --
    # human-maintained, bump forward by hand once Shaun records that year's ad-share
    # reading (see super_bowl.py's module docstring for the manual reset flow).

# Marker 12 -- credit turns in the hot sector (bond yield vs Treasury proxy, per-issuer).
SIGNALS_CREDIT_SPREAD_ISSUER_TREASURY_SERIES = "DGS10"  # v1 simplification: a fixed
    # 10Y Treasury comparator, not maturity-matched per-bond -- parsing each prospectus's
    # own maturity date was out of scope for this phase; a known follow-up, not a silent
    # shortcut (flagged explicitly in this plan's NOTES).
SIGNALS_CREDIT_SPREAD_ISSUER_DIVERGENCE_FLAG_RATIO = 1.3  # v1/tunable -- current spread
    # >=1.3x the reading from 90 days ago.
SIGNALS_ISSUER_SPREAD_LOOKBACK_DAYS = 90
SIGNALS_ISSUER_SPREAD_LOOKBACK_TOLERANCE_DAYS = 10  # daily-granularity data, much
    # tighter than margin_debt's 20-day monthly-bucket tolerance.
SIGNALS_BOND_CUSIP_REFRESH_DAYS = 30  # mirrors SEC_CIK_MAP_REFRESH_DAYS -- a company
    # could issue a new bond; don't cache a resolved CUSIP forever.
SIGNALS_BOND_PROSPECTUS_FORM_TYPES = ("424B2", "424B5", "FWP")

# Marker 14 enhancement -- "watch" tier below the flag threshold (added 2026-08-18;
# confirmed with Shaun: keep verdict="ok" + data={"watch": True} rather than a new verdict
# string, so nothing else that branches on verdict needs to change).
SIGNALS_CREDIT_SPREAD_WATCH_PCT = 3.2  # within 0.3pp of the 3.5pp flag threshold.
