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

# Added 2026-10-20 for the DMA-breakout industry filter -- mirrors the exact
# slug rule documented above GOAT_FINVIZ_INDUSTRY_SLUGS in config.py (lowercase,
# strip spaces/ampersands/hyphens/commas/periods, prefix "ind_"). Used as the
# fallback for any Finviz industry label not already in that override dict.
_FINVIZ_SLUG_STRIP_CHARS = " &-,."


def _derive_finviz_slug(industry_label: str) -> str:
    """Mechanically derives a Finviz industry screener slug from a label, per
    the rule verified in config.py's GOAT_FINVIZ_INDUSTRY_SLUGS comment. A
    wrong/stale derived slug just yields an empty Finviz screen for that
    industry (fail-safe-empty, via fetch_screener_universe), never a crash."""
    return f"ind_{''.join(ch for ch in industry_label if ch not in _FINVIZ_SLUG_STRIP_CHARS).lower()}"


def fetch_industry_constituents_us(industry_label: str) -> list[dict] | None:
    """Looks up an explicit Finviz slug override in GOAT_FINVIZ_INDUSTRY_SLUGS
    first; falls back to the rule-derived slug (_derive_finviz_slug) for any
    of the other Finviz industries that dict doesn't cover. A wrong/stale slug
    (explicit or derived) just yields an empty Finviz screen for that industry
    -- fetch_screener_universe's own fail-safe-empty behavior, not a crash."""
    slug = config.GOAT_FINVIZ_INDUSTRY_SLUGS.get(industry_label)
    if slug is None:
        slug = _derive_finviz_slug(industry_label)
        print(
            f"[goat-industry-constituents] no explicit slug override for {industry_label!r} "
            f"-- using derived slug {slug!r}"
        )
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
