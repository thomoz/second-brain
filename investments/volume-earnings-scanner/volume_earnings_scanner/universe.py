"""Universe construction for the Volume-Spike + Record-Earnings Scanner. Two Finviz
cap-bucket screens (VE_FINVIZ_SCREENS), unioned and deduped by ticker -- mirrors
ai_resistant_moat_scanner/universe.py's own multi-screen-then-merge pattern exactly
(that file merges per-sector screens; this merges per-cap-bucket screens instead).
Screened rows are cached in volume_earnings_universe_cache for
VE_UNIVERSE_CACHE_TTL_DAYS with a stale-fallback (a scrape failure must never leave
the scan with zero names when a good week-old cache exists).

Each daily run scores 1/N of the screened universe (rotating by calendar date).
"""

from __future__ import annotations

import sqlite3
import time
from datetime import date, datetime, timedelta, timezone
from typing import Any

from mytrader import finviz_screener

from . import config, db


def fetch_screened_universe() -> list[dict[str, Any]] | None:
    """Run every screen in config.VE_FINVIZ_SCREENS, concat, dedup by ticker.
    Returns None only if EVERY screen returned None (total Finviz failure); a
    partial result is fine -- the precise re-test happens per-ticker in scan.py."""
    merged: dict[str, dict[str, Any]] = {}
    all_failed = True
    for i, screen in enumerate(config.VE_FINVIZ_SCREENS):
        rows = finviz_screener.fetch_screener_universe(filters=screen, sort="marketcap")
        if rows is None:
            print(f"[volume-earnings-scan] Finviz screen failed: {screen}")
        else:
            all_failed = False
            for r in rows:
                merged.setdefault(r["ticker"], r)
        if i < len(config.VE_FINVIZ_SCREENS) - 1:
            time.sleep(config.VE_FINVIZ_REQUEST_DELAY_SECONDS)

    if all_failed:
        return None

    return [
        {
            "ticker": r["ticker"],
            "company": r.get("company") or "",
            "market_cap_text": r.get("market_cap_text") or "",
        }
        for r in merged.values()
    ]


def get_or_refresh_screened_universe(conn: sqlite3.Connection) -> tuple[list[sqlite3.Row], bool]:
    """Returns (cached screened rows, finviz_failed). Refreshes from Finviz first if
    the cache is missing or older than VE_UNIVERSE_CACHE_TTL_DAYS. On total scrape
    failure, falls back to whatever's already cached (even if stale). `finviz_failed`
    is True only when a refresh was attempted, it failed, and there is no cache."""
    fetched_at = db.get_universe_cache_fetched_at(conn)
    stale = fetched_at is None or (
        datetime.now(timezone.utc) - datetime.fromisoformat(fetched_at)
        > timedelta(days=config.VE_UNIVERSE_CACHE_TTL_DAYS)
    )

    finviz_failed = False
    if stale:
        rows = fetch_screened_universe()
        if rows is not None:
            db.replace_universe_cache(conn, rows)
        elif fetched_at is None:
            finviz_failed = True
            print("[volume-earnings-scan] Finviz screen failed and no universe cache exists yet")

    return db.get_universe_cache(conn), finviz_failed


def get_scan_universe(conn: sqlite3.Connection) -> dict[str, Any]:
    """{"screened": [rows], "slice_today": [tickers], "slice_index": int,
    "finviz_failed": bool}. slice_today is the slice_index-th partition of the
    deterministically-sorted screened tickers -- over VE_UNIVERSE_SLICES
    consecutive calendar days every screened name is covered exactly once."""
    screened, finviz_failed = get_or_refresh_screened_universe(conn)
    screened_rows = [dict(r) for r in screened]

    n_slices = config.VE_UNIVERSE_SLICES
    slice_index = date.today().toordinal() % n_slices
    screened_tickers = sorted({r["ticker"] for r in screened_rows})
    slice_today = screened_tickers[slice_index::n_slices]

    return {
        "screened": screened_rows,
        "slice_today": slice_today,
        "slice_index": slice_index,
        "finviz_failed": finviz_failed,
    }
