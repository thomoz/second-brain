"""Path constants + tracked-investor config for the superinvestor fast-disclosure
filings scanner. Data-only: adding a second investor here is a config edit, never a
code change. Mirrors goat/config.py's path-constant style."""

from __future__ import annotations

from pathlib import Path

from scripts.config import DB_PATH  # noqa: F401  (re-exported for callers)

PKG_DIR = Path(__file__).resolve().parent.parent  # -> investments/superinvestor-filings
SUPERINVESTOR_REPORT_PATH = PKG_DIR / "superinvestor-filings-report.md"

# The fast-disclosure form set (see
# .agent/plans/completed/superinvestor-filings-scanner.md for why each beats the
# ~135-day 13F lag). Values must match EDGAR's own `form`
# strings in data.sec.gov/submissions/CIK*.json exactly. EDGAR emits BOTH the legacy
# "SC 13x" and the post-2024 structured-submission "SCHEDULE 13x" label for the same
# form family -- confirmed live 2026-09-08: Pabrai Mohnish's two most recent 13G
# filings (2026-05-14, 2026-08-13) come through as "SCHEDULE 13G" / "SCHEDULE 13G/A".
# Both spellings must be here or the newest, highest-value filings are silently missed;
# edgar_monitor._canonical_form collapses them for dedup + display.
SUPERINVESTOR_EDGAR_FORMS: set[str] = {
    "SC 13D", "SC 13D/A", "SC 13G", "SC 13G/A",
    "SCHEDULE 13D", "SCHEDULE 13D/A", "SCHEDULE 13G", "SCHEDULE 13G/A",
    "3", "4", "4/A", "5",
}

# How far back a filing counts as "recent" -- also the window silent-seeded into the
# seen-log on the very first run (no alerts) so go-live doesn't fire N months of
# historical filings at once.
SUPERINVESTOR_LOOKBACK_DAYS = 30

# sync_state key marking that the first silent seed pass has completed.
SUPERINVESTOR_FIRST_SEED_WATERMARK = "superinvestor_first_seed_done"

# Courtesy delay between EDGAR document fetches -- reuses my-trader's SEC pacing
# number. ~12 CIKs x N filings per run stays well under SEC's ~10 req/s limit.
SUPERINVESTOR_SEC_REQUEST_DELAY_SECONDS = 0.2

# --- India / SEBI SAST leg (Phase 5) ----------------------------------------
# Feed: BSE AnnSubCategoryGetData, category "Insider Trading / SAST". Confirmed
# live 2026-09-08 (see INDIA-LEG-FINDINGS.md). NSE is blocked at the edge for the
# VPS IP, so BSE-only -- acceptable, SAST disclosures are dual-filed. The acquirer
# name comes from the row's HEADLINE ("...Regulations, 2011 for <acquirer>"); the
# exact % is only in a (usually scanned/image) PDF, so v1 alerts on the event,
# not the number.
SUPERINVESTOR_SAST_FIRST_SEED_WATERMARK = "superinvestor_sast_first_seed_done"
SUPERINVESTOR_SAST_LOOKBACK_DAYS = 28   # BSE requires the date range <= 1 month
SUPERINVESTOR_SAST_MAX_PAGES = 40      # 50 rows/page; the SAST category runs
                                        # ~1300 rows/month -> ~26 pages, cap generous
SUPERINVESTOR_SAST_REQUEST_DELAY_SECONDS = 0.4  # BSE is slower/flakier than EDGAR

SUPERINVESTOR_TRACKED: dict[str, dict] = {
    "pabrai": {
        "display": "Mohnish Pabrai / Dalal Street",
        # Plain unpadded digit strings -- mytrader.sec_filings zero-pads internally.
        # Resolved 2026-09-07 via EDGAR company search; a dead CIK just yields None
        # from fetch_filing_index and is skipped -- the `resolve-ciks` command
        # re-surfaces the live entity/CIK pairs by name for manual review.
        "edgar_ciks": [
            "1549575",   # Dalal Street, LLC (13F + SC 13G filer)
            "1173334",   # PABRAI MOHNISH (individual -- Section 16 / group filings)
            "1571785",   # Pabrai Investment Fund 2, L.P.
            "1571780",   # Pabrai Investment Fund 3, Ltd.
            "1415742",   # Pabrai Investment Fund IV LP
            "1571786",   # Pabrai Investment Fund IV, L.P.
        ],
        # India / SEBI SAST -- case-insensitive substring match against the acquirer
        # name in a BSE SAST row's HEADLINE. "pabrai" is a rare-enough token to use
        # bare (catches "Mohnish Pabrai", "Pabrai Investment Fund II LP", etc.).
        # VERIFY against real hits: run `scan --india-only` and eyeball the acquirer
        # names in the report -- Pabrai's fund entities have been renamed over the years.
        "india_aliases": [
            "pabrai", "dalal street", "dhandho",
        ],
    },

    # --- US / SEC EDGAR filers ---------------------------------------------------
    # CIKs resolved 2026-09-09 via EDGAR company search, then each one's
    # data.sec.gov/submissions feed was checked to confirm it actually carries
    # fast-disclosure forms (SC 13D/G or Form 3/4/5) and not just quarterly 13F.
    "abrams": {
        "display": "David Abrams / Abrams Capital",
        # Prolific fast-disclosure filer -- recent-submissions window held
        # 25 SC 13G, 72 SC 13G/A, 2 SC 13D, 10 SC 13D/A, 71 Form 4, 11 Form 3.
        "edgar_ciks": [
            "1358706",   # Abrams Capital Management, L.P. (manager -- primary filer)
            "1426355",   # Abrams Capital Management, LLC (general partner / co-filer)
        ],
        "india_aliases": [],
    },
    "southeastern": {
        "display": "Mason Hawkins / Southeastern Asset Management (Longleaf)",
        # Deep value, concentrated, takes board-level stakes -- one of the heaviest
        # Schedule 13D/G filers on EDGAR (85 SC 13G, 156 SC 13G/A, 15 SC 13D,
        # 36 SC 13D/A). DFAN14A proxy-fight filings fall outside the tracked form
        # set and are ignored.
        "edgar_ciks": ["807985"],   # SOUTHEASTERN ASSET MANAGEMENT INC/TN/
        "india_aliases": [],
    },
    "fairholme": {
        "display": "Bruce Berkowitz / Fairholme Capital Management",
        # Hyper-concentrated (St. Joe / JOE dominates the book). Active filer:
        # 13 SC 13G, 40 SC 13G/A, 5 SC 13D, 28 SC 13D/A, 67 Form 4, 4 Form 3.
        "edgar_ciks": ["1056831"],  # FAIRHOLME CAPITAL MANAGEMENT LLC
        "india_aliases": [],
    },
    "chou": {
        "display": "Francis Chou / Chou Associates",
        # Deep value in small-cap / distressed names -- crosses 5% often enough to
        # matter, though at lower volume (3 SC 13G, 8 SC 13G/A, 4 Form 4, 1 Form 3).
        "edgar_ciks": [
            "1389403",   # Chou Associates Management Inc. (manager)
            "1389402",   # Chou Associates Fund (co-filer on some schedules)
        ],
        "india_aliases": [],
    },

    # --- India / SEBI SAST only (no SEC EDGAR presence) ------------------------
    # These disclose SAST Reg 29 on BSE, not with the SEC, so edgar_ciks is empty.
    # The India leg matches india_aliases (case-insensitive substring) against the
    # acquirer name parsed from each BSE SAST row's HEADLINE. RUN
    # `scan --india-only` ONCE and eyeball the matched acquirer names before
    # trusting these -- several common Indian surnames collide.
    "jhunjhunwala": {
        "display": "Rekha Jhunjhunwala / RARE Enterprises (Rakesh Jhunjhunwala estate)",
        "edgar_ciks": [],
        # "jhunjhunwala" is a rare, safe token; "rare enterprises" is the family office.
        "india_aliases": ["jhunjhunwala", "rare enterprises"],
    },
    "kacholia": {
        "display": "Ashish Kacholia",
        "edgar_ciks": [],
        # "kacholia" is rare and safe on its own; "bengal finance" is his PMS vehicle.
        "india_aliases": ["kacholia", "bengal finance & investment"],
    },
    "abakkus": {
        "display": "Sunil Singhania / Abakkus Asset Manager",
        "edgar_ciks": [],
        "india_aliases": ["abakkus", "sunil singhania"],
    },
    "damani": {
        "display": "Radhakishan Damani / Bright Star Investments",
        "edgar_ciks": [],
        # Bare "damani" was left out on purpose -- it catches unrelated Damani-family
        # filers. Add it back only if these two strings miss real disclosures.
        "india_aliases": ["radhakishan damani", "bright star investments"],
    },
    "kedia": {
        "display": "Vijay Kedia / Kedia Securities",
        "edgar_ciks": [],
        # VERIFY: "kedia" alone collides with the Kedia commodities group -- keep tight.
        "india_aliases": ["vijay kedia", "kedia securities"],
    },

    # NOTE: Li Lu / Himalaya Capital (CIK 1709323) and Guy Spier / Aquamarine
    # (CIK 1404599) were evaluated 2026-09-09 and deliberately NOT added -- both
    # hold large-caps below the 5% line and file only quarterly 13F (nothing in the
    # fast-disclosure set), so the scanner would never see them. Same for Norbert
    # Lou / Punch Card Management (CIK 1631664). Only add a filer whose submissions
    # feed actually carries SC 13D/G or Form 3/4/5.
}
