"""Path constants + tracked-investor config for the superinvestor fast-disclosure
filings scanner. Data-only: adding a second investor here is a config edit, never a
code change. Mirrors goat/config.py's path-constant style."""

from __future__ import annotations

from pathlib import Path

from scripts.config import DB_PATH  # noqa: F401  (re-exported for callers)

PKG_DIR = Path(__file__).resolve().parent.parent  # -> investments/superinvestor-filings
SUPERINVESTOR_REPORT_PATH = PKG_DIR / "superinvestor-filings-report.md"

# The fast-disclosure form set (see investments/superinvestor-filings-scanner-handoff.md
# for why each beats the ~135-day 13F lag). Values must match EDGAR's own `form`
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
# number. ~6 CIKs x N filings per run stays well under SEC's ~10 req/s limit.
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
    # Add more investors here (Li Lu / Himalaya, Guy Spier / Aquamarine, ...) -- data only.
}
