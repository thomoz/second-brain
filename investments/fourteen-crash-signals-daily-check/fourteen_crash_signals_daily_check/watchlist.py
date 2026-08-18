"""Hot-company watchlist -- the shared "which mega-caps are driving the
current cycle" input every per-issuer marker in this package reads from.
Composes goat.sector_rotation's rising-sector ranking with goat.sp500_universe's
cached S&P 500 constituent list (mirroring goat.heartbeat_scan's own filter
exactly), then narrows to mega-cap names by market cap. Never hardcodes a
ticker -- see the Phase 1 plan's Design Decision #1 for the full rationale."""

from __future__ import annotations

import sqlite3
from typing import Any

from goat import config as goat_config
from goat import sector_rotation, sp500_universe
from mytrader import market_data

from . import config, db


def compute_hot_watchlist(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    closes = sector_rotation.fetch_all_sector_closes()
    ranking = sector_rotation.rank_sectors(closes)
    rising_etf_labels = {row["sector_label"] for row in ranking if row["rising"]}

    constituents = sp500_universe.get_or_refresh_sp500_constituents(conn)

    candidates: list[dict[str, Any]] = []
    for c in constituents:
        etf_label = goat_config.GOAT_GICS_TO_ETF_SECTOR_LABEL.get(c["gics_sector"])
        if etf_label is None or etf_label not in rising_etf_labels:
            continue
        try:
            data = market_data.fetch_ticker_data(c["ticker"])
        except Exception as e:
            print(f"[fourteen-signals-watchlist] error fetching {c['ticker']}: {e}")
            continue
        if data is None:
            continue
        market_cap = data.info.get("marketCap")
        if market_cap is None or market_cap < config.SIGNALS_HOT_WATCHLIST_MIN_MARKET_CAP:
            continue
        candidates.append({"ticker": c["ticker"], "sector_label": etf_label, "market_cap": market_cap})

    candidates.sort(key=lambda r: -r["market_cap"])
    top = candidates[: config.SIGNALS_HOT_WATCHLIST_TOP_N]
    for i, row in enumerate(top, start=1):
        row["rank"] = i
    return top


def get_or_refresh_hot_watchlist(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Recomputed every call -- unlike Goat's S&P 500 cache, this has no TTL: the
    handoff's own decision is 'refreshed on an ongoing basis', and the only real
    cost here (beyond Goat's already-cached constituent list) is one yfinance
    .info fetch per rising-sector constituent, which for a handful of rising
    sectors out of 11 is cheap enough to do daily. If Shaun later finds the
    daily fetch cost too high (a rising sector could have 50+ constituents), a
    TTL cache is a reasonable follow-up -- not added speculatively now.

    Confirmed real, not just hypothetical (2026-08-18): two live end-to-end
    daily-check runs took ~16min and ~38min respectively (the second may also
    reflect yfinance rate-limiting from two heavy runs in one hour, not purely
    this function's own cost). market_cap_milestone.py no longer independently
    scans the full S&P 500, so this function is now the sole remaining
    per-run yfinance bottleneck. Shaun's call (2026-08-18): leave as a known
    follow-up rather than add a TTL cache speculatively -- revisit if the real
    scheduled VPS run is consistently slow."""
    rows = compute_hot_watchlist(conn)
    db.replace_hot_watchlist(conn, rows)
    return db.get_hot_watchlist(conn)
