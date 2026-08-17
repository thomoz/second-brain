"""S&P 500 constituent universe for the heartbeat scanner -- Goat Phase 3. Scrapes
Wikipedia's constituent table (no official free API exists), weekly-cached in the
goat_sp500_constituents table so the scan itself doesn't re-scrape every run. Mirrors
mytrader/asx_announcements.py's direct-fetch style (requests + BeautifulSoup, headers
dict, timeout, try/except-returns-None-on-any-failure) -- no third-party HTML-table
wrapper library (neither lxml nor html5lib is a declared dependency anywhere in the
workspace, so pandas.read_html is not used here)."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

from mytrader import tickers

from . import config, db

_HEADERS = {"User-Agent": config.GOAT_SP500_USER_AGENT}


def fetch_sp500_constituents() -> list[dict[str, str]] | None:
    """Scrapes the current S&P 500 constituent list from Wikipedia. Returns None
    on any fetch/parse failure (network error, missing table, wrong column
    count) -- same graceful-degradation contract as price_history.fetch_close_history."""
    import requests
    from bs4 import BeautifulSoup

    try:
        r = requests.get(config.GOAT_SP500_WIKI_URL, headers=_HEADERS, timeout=30)
        if r.status_code != 200:
            return None
        soup = BeautifulSoup(r.text, "html.parser")
        table = soup.find("table", {"id": "constituents"})
        if table is None:
            table = soup.find("table", {"class": "wikitable"})
        if table is None:
            return None

        rows: list[dict[str, str]] = []
        trs = table.find_all("tr")
        for tr in trs[1:]:  # skip header row
            cells = tr.find_all("td")
            if len(cells) < 3:
                continue
            symbol = cells[0].get_text(strip=True)
            security = cells[1].get_text(strip=True)
            gics_sector = cells[2].get_text(strip=True)
            if not symbol or not security or not gics_sector:
                continue
            rows.append({
                "ticker": tickers.normalize(symbol),
                "security": security,
                "gics_sector": gics_sector,
            })
        return rows or None
    except Exception:
        return None


def get_or_refresh_sp500_constituents(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Returns the cached constituent list, refreshing from Wikipedia first if the
    cache is missing or older than GOAT_SP500_CACHE_TTL_DAYS. On scrape failure,
    falls back to whatever's already cached (even if stale) rather than returning
    nothing -- a scrape failure must never leave the heartbeat scan with zero
    candidates to check when a perfectly good week-old cache exists."""
    fetched_at = db.get_sp500_constituents_fetched_at(conn)
    stale = fetched_at is None or (
        datetime.now(timezone.utc) - datetime.fromisoformat(fetched_at)
        > timedelta(days=config.GOAT_SP500_CACHE_TTL_DAYS)
    )

    if stale:
        rows = fetch_sp500_constituents()
        if rows is not None:
            db.replace_sp500_constituents(conn, rows)
        elif fetched_at is None:
            print("[goat-sp500-universe] Wikipedia scrape failed and no cache exists yet")

    return db.get_sp500_constituents(conn)
