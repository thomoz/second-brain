"""FTSE 100 constituent universe for the heartbeat scanner -- LSE Heartbeat
Universe, per .agent/plans/lse-heartbeat-universe.md. Scrapes Wikipedia's
constituent table (no official free API exists), cached for
GOAT_FTSE100_CACHE_TTL_DAYS in the goat_ftse100_constituents table so the daily
scan doesn't re-scrape every run. Mirrors sp500_universe.py's two-function
shape exactly (closest precedent: also DB-cached, also goat-only)."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

from mytrader import tickers

from . import config, db

_HEADERS = {"User-Agent": config.GOAT_FTSE100_USER_AGENT}


def fetch_ftse100_constituents() -> list[dict[str, str]] | None:
    """Scrapes the current FTSE 100 constituent list from Wikipedia. Returns None
    on any fetch/parse failure (network error, missing table, wrong column
    count) -- same graceful-degradation contract as fetch_sp500_constituents."""
    import requests
    from bs4 import BeautifulSoup

    try:
        r = requests.get(config.GOAT_FTSE100_WIKI_URL, headers=_HEADERS, timeout=30)
        if r.status_code != 200:
            return None
        soup = BeautifulSoup(r.text, "html.parser")
        table = soup.find("table", {"class": "wikitable"})
        if table is None:
            return None

        rows: list[dict[str, str]] = []
        trs = table.find_all("tr")
        for tr in trs[1:]:  # skip header row
            cells = tr.find_all("td")
            if len(cells) < 3:
                continue
            company = cells[0].get_text(strip=True)
            ticker = cells[1].get_text(strip=True)
            icb_sector = cells[2].get_text(strip=True)
            if not company or not ticker or not icb_sector:
                continue
            rows.append({
                "ticker": tickers.normalize(ticker),  # bare code; tickers.lse_variant adds .L later
                "company": company,
                "icb_sector": icb_sector,
            })
        return rows or None
    except Exception:
        return None


def get_or_refresh_ftse100_constituents(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Returns the cached constituent list, refreshing from Wikipedia first if the
    cache is missing or older than GOAT_FTSE100_CACHE_TTL_DAYS. On scrape failure,
    falls back to whatever's already cached (even if stale) rather than returning
    nothing -- mirrors get_or_refresh_sp500_constituents exactly."""
    fetched_at = db.get_ftse100_constituents_fetched_at(conn)
    stale = fetched_at is None or (
        datetime.now(timezone.utc) - datetime.fromisoformat(fetched_at)
        > timedelta(days=config.GOAT_FTSE100_CACHE_TTL_DAYS)
    )

    if stale:
        rows = fetch_ftse100_constituents()
        if rows is not None:
            db.replace_ftse100_constituents(conn, rows)
        elif fetched_at is None:
            print("[goat-ftse100-universe] Wikipedia scrape failed and no cache exists yet")

    return db.get_ftse100_constituents(conn)
