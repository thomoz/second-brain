"""Path constants + universe / scoring config for the Volume-Spike + Record-Earnings
Scanner. Screens US small/micro-cap stocks for two independent "Wall St is about to
notice this" signals -- unusual trading volume, or a record/accelerating earnings
quarter -- per .agent/plans/volume-spike-earnings-scanner.md.

Data-only config: adding/tuning a threshold here is a config edit, never a code
change. Mirrors ai_resistant_moat_scanner/config.py's and mytrader/cash_value_scan's
path-constant + tunable-threshold style.

Every threshold below is v1/tunable, following this codebase's established
precedent (Cash-Value Scan's 0.80->0.50, AI-Moat Scan's anti-signal penalty halving)
of shipping a conservative first guess and tuning against the first few days of
real output.
"""

from __future__ import annotations

from pathlib import Path

from scripts.config import DB_PATH  # noqa: F401  (re-exported for callers)

PKG_DIR = Path(__file__).resolve().parent.parent  # -> investments/volume-earnings-scanner
# Single-report shape (mirrors goat.dma_breakout_scan, the closest precedent for a
# binary signal-trip scan with no per-row score to show) -- no separate full
# scan-report.md the way ai_resistant_moat_scanner has one for its ranked scores.
VE_CANDIDATES_MD_PATH = PKG_DIR / "volume-earnings-candidates-pending-review.md"

# --- Universe --------------------------------------------------------------------
# Two Finviz cap-bucket screens, unioned and deduped (universe.py), approximating
# $0-$2B market cap -- small/micro-caps only, the range Goat's own index-membership
# scanners (S&P 500 / FTSE 100 / ASX 200) structurally exclude.
#
# LIVE-VERIFIED 2026-10-14 against finviz.com/screener.ashx (via
# mytrader.finviz_screener.fetch_screener_universe, sort="marketcap" ascending):
#   - cap_microunder,geo_usa -> 800 results (page cap), starting ~$0.17M mcap. This
#     is Finviz's "nano and micro" combined bucket (<~$300M).
#   - cap_small,geo_usa       -> 800 results (page cap), starting ~$300.25M mcap.
#     Confirms the nano/micro -> small boundary sits right at $300M as the
#     filter-naming convention implied; no surprises, no token correction needed.
# Both screens hit the 800-row pagination cap (FINVIZ_MAX_PAGES x
# FINVIZ_SCREENER_ROWS_PER_PAGE) -- the real universe below $2B is larger than what
# gets screened in full; VE_UNIVERSE_SLICES below covers it in rotating daily slices.
VE_FINVIZ_SCREENS: tuple[str, ...] = (
    "cap_microunder,geo_usa,sh_avgvol_o100,sh_price_o1",
    "cap_small,geo_usa,sh_avgvol_o100,sh_price_o1",
)

VE_UNIVERSE_CACHE_TTL_DAYS = 7  # Finviz screen re-run cadence.
VE_UNIVERSE_SLICES = 5  # 1/5 of the screened universe scored per calendar day --
    # start at the same value as MOAT_UNIVERSE_SLICES; a small/micro-cap universe
    # capped at ~1600 names (2 screens x 800) is in the same ballpark, tune after
    # the first few live runs confirm actual per-slice counts and run time.

# --- Precise per-ticker floor (re-checked via yfinance .info, never trusted from
# the coarse Finviz screen -- same two-pass idiom as cash_value_scan) ------------
VE_MIN_MARKET_CAP_USD = 50_000_000.0
VE_MAX_MARKET_CAP_USD = 2_000_000_000.0
VE_MIN_PRICE_USD = 1.0
VE_MIN_AVG_VOLUME = 100_000  # matches GOAT_DMA_BREAKOUT_MIN_AVG_VOLUME / FINVIZ_SCREENER_FILTERS.

# --- Signal 1: volume spike ------------------------------------------------------
VE_VOLUME_SPIKE_RATIO_THRESHOLD = 3.0  # today's volume >= 3x (300%) its trailing
    # average -- the figure from the TradingView-style alert that inspired this
    # tool. Start conservative, tune after the first live run (cash-value's
    # 0.80->0.50 precedent).
VE_VOLUME_AVG_WINDOW_DAYS = 20  # trailing window the spike is measured against --
    # deliberately SHORT and DIFFERENT from yfinance's own ~3-month `averageVolume`
    # liquidity-floor figure (see volume_signal.py module docstring GOTCHA).
VE_PRICE_HISTORY_LOOKBACK_DAYS = 60  # comfortably covers the 20-day trailing window
    # plus weekends/holidays/thin-trading gaps.

# --- Signal 2: record earnings ---------------------------------------------------
VE_EARNINGS_MIN_QUARTERS_FOR_RECORD = 4
VE_EARNINGS_MIN_QUARTERS_FOR_YOY_ACCEL = 5  # needs quarter[0] AND quarter[4] (a
    # year-ago same quarter) both present -- see earnings_signal.py LIVE-VERIFIED
    # note on realistic free-data depth (~5-6 quarters even for a mega-cap).

# --- Pacing --------------------------------------------------------------------
VE_FETCH_DELAY_SECONDS = 0.2  # matches CASH_VALUE_FETCH_DELAY_SECONDS.
VE_FINVIZ_REQUEST_DELAY_SECONDS = 0.5  # matches MOAT_FINVIZ_REQUEST_DELAY_SECONDS.

VE_REPORT_MAX_ROWS = 120
