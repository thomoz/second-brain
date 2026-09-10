"""Path constants + universe / scoring config for the AI-Resistant Moat Scanner.

Ranks US-listed public companies by how AI-durable their embedded-software moat is --
the Salesforce property: software so engrained in the customer's operations that the
ROI of building an AI replacement doesn't make sense. Daily VPS scan, advisor notes
only (see SOUL.md) -- no auto-buy, no auto-watchlist-add.

Data-only config: adding a seed ticker or a target industry here is a config edit,
never a code change. Mirrors goat/config.py's and cash_value_scan's path-constant +
tunable-threshold style.

DATED CAVEAT (2026-09): the AI-resistance rubric encodes a 2026 view of what AI can
and cannot cheaply rebuild -- revisit it, do not treat it as permanent (same spirit
as the check-interpretation convention). Bump RUBRIC_VERSION when the rubric text
changes; that cleanly invalidates every cached sub-score.
"""

from __future__ import annotations

from pathlib import Path

from scripts.config import DB_PATH  # noqa: F401  (re-exported for callers)

PKG_DIR = Path(__file__).resolve().parent.parent  # -> investments/ai-resistant-moat-scanner
MOAT_SCAN_REPORT_PATH = PKG_DIR / "moat-scan-report.md"
MOAT_CANDIDATES_MD_PATH = PKG_DIR / "moat-candidates-pending-review.md"

# Surfaced in the report header + stored on every moat_qualitative_cache row; a bump
# here makes every cached rubric sub-score miss on the next run (see db.py PK).
RUBRIC_VERSION = "2026-09"

# --- Universe --------------------------------------------------------------------
# One coarse Finviz screen string per target sector. Finviz's industry filter is
# single-select (you cannot OR industries in `f=`), so the scan screens by SECTOR
# and then filters to MOAT_TARGET_INDUSTRIES client-side using the parsed `industry`
# column. EVERY TOKEN HERE IS A BEST GUESS -- verified live during the build (Task 6);
# a wrong token just yields a smaller/empty screened universe and the seed list still
# carries the scan.
MOAT_FINVIZ_SECTOR_SCREENS: list[str] = [
    "cap_midover,fa_grossmargin_o60,geo_usa,sh_avgvol_o100,sec_technology",
    "cap_midover,fa_grossmargin_o60,geo_usa,sh_avgvol_o100,sec_healthcare",
    "cap_midover,fa_grossmargin_o60,geo_usa,sh_avgvol_o100,sec_financial",
    "cap_midover,fa_grossmargin_o60,geo_usa,sh_avgvol_o100,sec_communicationservices",
    "cap_midover,fa_grossmargin_o60,geo_usa,sh_avgvol_o100,sec_industrials",
]

# Exact Finviz industry labels (verbatim from goat/config.py:GOAT_FINVIZ_INDUSTRIES)
# -- the embedded-software / system-of-record / workflow-lock-in industries.
MOAT_TARGET_INDUSTRIES: frozenset[str] = frozenset({
    "Software - Application",
    "Software - Infrastructure",
    "Information Technology Services",
    "Health Information Services",
    "Healthcare Plans",
    "Insurance Brokers",
    "Financial Data & Stock Exchanges",
    "Specialty Business Services",
    "Consulting Services",
    "Financial Conglomerates",
    "Diagnostics & Research",
})

# Curated known-embedded-moat names so the scan is anchored even if the Finviz screen
# drifts. Re-scored every day (not rotated).
MOAT_SEED_TICKERS: tuple[str, ...] = (
    "CRM", "NOW", "INTU", "ADP", "PAYX", "VEEV", "TYL", "ADSK", "ANSS", "PTC",
    "ORCL", "WDAY", "SPGI", "FICO", "VRSK", "MSCI", "FDS", "SSNC", "MANH", "DSGX",
    "PCTY", "PEGA", "BSY", "GWRE", "CSGP", "IT", "BR", "JKHY", "FIS", "FI",
)

MOAT_UNIVERSE_CACHE_TTL_DAYS = 7  # Finviz screen re-run cadence; the seed list is code.
MOAT_UNIVERSE_SLICES = 5  # 1/5 of the screened universe scored per calendar day.

# --- Scoring --------------------------------------------------------------------
MOAT_STAGE_THRESHOLD = 80.0  # blended score at/above which a fresh name is staged.
    # Start conservative, tune down after the first live run (cash-value 0.80 -> 0.50
    # precedent).
MOAT_BLEND_QUANT_WEIGHT = 0.5  # qualitative weight = 1 - this.

MOAT_QUANT_WEIGHTS: dict[str, float] = {
    "gross_margin": 0.25,
    "fcf_margin": 0.20,
    "operating_margin": 0.15,
    "rule_of_40": 0.15,
    "revenue_durability": 0.15,
    "recurring_revenue": 0.10,
}  # sums to 1.0

# Each ramp is (zero_at, hundred_at); descending ramps (hundred_at < zero_at) allowed.
MOAT_GROSS_MARGIN_RAMP = (0.50, 0.75)
MOAT_FCF_MARGIN_RAMP = (0.0, 0.20)
MOAT_OPERATING_MARGIN_RAMP = (0.0, 0.25)
MOAT_RULE_OF_40_RAMP = (20.0, 40.0)
MOAT_REVENUE_DURABILITY_RAMP = (-10.0, 0.0)  # worst annual YoY %; see quant.py for the
    # special handling (>=0 -> 100 "never declined", <=-10 -> 0, in between scaled to ~70 at 0).
MOAT_RECURRING_REVENUE_RAMP = (0.50, 0.90)

MOAT_DISCLOSURE_BONUS_MAX = 5.0  # max points added to quant_score for strong disclosed
    # NRR (>=110%) + growing RPO + low logo churn (<10%); null fields contribute nothing.
MOAT_ANTI_SIGNAL_PENALTY_EACH = 8.0
MOAT_ANTI_SIGNAL_PENALTY_CAP = 30.0
MOAT_QUANT_NEUTRAL = 50.0  # score for an unavailable-but-not-negative sub-metric.

MOAT_MIN_MARKET_CAP_USD = 2_000_000_000.0  # re-checked precisely per ticker in quant.py,
    # not trusted from the coarse Finviz screen.

# --- Models --------------------------------------------------------------------
MOAT_RUBRIC_MODEL = "sonnet"  # 6-part rubric grading against filing text.
MOAT_EXTRACTION_MODEL = "haiku"  # nullable structured extraction (mirrors score.py's haiku).

# --- Pacing --------------------------------------------------------------------
MOAT_SEC_REQUEST_DELAY_SECONDS = 0.2
MOAT_FETCH_DELAY_SECONDS = 0.2
MOAT_FINVIZ_REQUEST_DELAY_SECONDS = 0.5

MOAT_MAX_SECTION_CHARS = 6000  # per-section cap into the LLM prompt (mirrors SEC_MAX_SECTION_CHARS).
MOAT_REPORT_MAX_ROWS = 120
