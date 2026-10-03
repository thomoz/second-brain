"""Industry constituent universe -- Part B-2 of
.agent/plans/goat-industry-pipeline.md. US leg is Finviz-screener-backed and
DB-cached per industry_label (TTL, mirrors sp500_universe.py's shape); ASX leg
is a pure dict lookup over the hand-curated GOAT_ASX_INDUSTRY_CONSTITUENTS
(static config value -- no network, no TTL applies)."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

from mytrader import finviz_screener, tickers

from . import config, db


def fetch_industry_constituents_us(industry_label: str) -> list[dict] | None:
    """Returns None (logged, not a crash) when no Finviz slug is mapped for
    this industry_label -- a gated industry that happens to be one of the 39
    with an ETF but somehow missing a slug entry still degrades safely rather
    than raising."""
    slug = config.GOAT_FINVIZ_INDUSTRY_SLUGS.get(industry_label)
    if slug is None:
        print(f"[goat-industry-constituents] no Finviz slug mapped for {industry_label!r}")
        return None
    rows = finviz_screener.fetch_screener_universe(filters=f"{slug},sh_avgvol_o100,sh_price_o1")
    if rows is None:
        return None
    return [
        {"ticker": tickers.normalize(r["ticker"]), "company": r.get("company", ""), "market": "US"}
        for r in rows
    ]


def get_asx_industry_constituents(industry_label: str) -> list[dict]:
    """Pure dict lookup, no network, no caching -- GOAT_ASX_INDUSTRY_CONSTITUENTS
    is already a static config value. Returns [] for an industry with no
    curated ASX coverage (never a crash)."""
    return [
        {
            "ticker": tickers.asx_variant(ticker), "company": "", "market": "ASX",
            "industry_label": industry_label,
        }
        for ticker, label in config.GOAT_ASX_INDUSTRY_CONSTITUENTS.items()
        if label == industry_label
    ]


def get_or_refresh_industry_constituents(conn: sqlite3.Connection, industry_label: str) -> list[dict]:
    """TTL-checks and refreshes the US (Finviz) leg only -- the ASX leg is
    static and combined in fresh every call. On a Finviz scrape/slug failure,
    falls back to whatever's already cached for this industry_label (even if
    stale) rather than returning zero US constituents -- mirrors
    sp500_universe.get_or_refresh_sp500_constituents's stale-fallback shape,
    applied per-industry_label instead of globally."""
    fetched_at = db.get_industry_constituents_fetched_at(conn, industry_label)
    stale = fetched_at is None or (
        datetime.now(timezone.utc) - datetime.fromisoformat(fetched_at)
        > timedelta(days=config.GOAT_INDUSTRY_CONSTITUENTS_CACHE_TTL_DAYS)
    )

    if stale:
        rows = fetch_industry_constituents_us(industry_label)
        if rows is not None:
            db.replace_industry_constituents(conn, industry_label, rows)
        elif fetched_at is None:
            print(
                f"[goat-industry-constituents] US fetch failed and no cache exists yet for {industry_label!r}"
            )

    us_rows = [dict(r) for r in db.get_industry_constituents(conn, industry_label)]
    asx_rows = get_asx_industry_constituents(industry_label)
    return us_rows + asx_rows
