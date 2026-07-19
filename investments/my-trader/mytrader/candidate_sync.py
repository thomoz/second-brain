"""Briefs Finance ingest -> my-trader candidate sync (tool-preplan.md "Briefs Finance
report integration", confirmed 2026-07-19).

Reads briefs-finance's recommendations table for rows newer than a stored watermark
(sync_state key "briefs_finance_last_recommendation_id") and inserts each into
my-trader's watchlist as status="raw" (never "discussed" -- see find.py's own
"reserved for a future Phase C auto-ingest flow" comment; a human still has to
actually discuss a candidate before Monitor's assessment loop picks it up, since that
loop filters to status="discussed" only). Bucket defaults to "unassigned" (matches
seed.py's existing convention -- briefs-finance's recommendations table has no bucket
concept, that's a my-trader-only classification a human assigns).

Ethical filtering is inherited, not re-applied: recommendations.excluded is already
computed by briefs-finance's own ingest_pdf() via check_ticker() at ingest time
(scripts/ingest.py:86), so filtering WHERE excluded = 0 here satisfies
tool-preplan.md's "ethical filter inherited" decision without a second ethical-filter
call.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from . import db, tickers

_WATERMARK_KEY = "briefs_finance_last_recommendation_id"


def sync_new_candidates(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    last_id = int(db.get_sync_watermark(conn, _WATERMARK_KEY) or 0)
    rows = conn.execute(
        """SELECT id, ticker, company_name, buy_thesis FROM recommendations
           WHERE id > ? AND excluded = 0 ORDER BY id""",
        (last_id,),
    ).fetchall()

    added: list[dict[str, Any]] = []
    max_id = last_id
    for row in rows:
        max_id = max(max_id, row["id"])
        normalized = tickers.normalize(row["ticker"])
        if db.get_holding_row(conn, normalized) is not None:
            continue
        if db.get_watchlist_row(conn, normalized) is not None:
            continue
        db.upsert_watchlist_row(
            conn, ticker=normalized, name=row["company_name"], asset_type="stock",
            bucket="unassigned", status="raw", notes=row["buy_thesis"] or "",
            source="briefs_finance_ingest",
        )
        added.append({"ticker": normalized, "company_name": row["company_name"]})

    if max_id > last_id:
        db.set_sync_watermark(conn, _WATERMARK_KEY, str(max_id))
    return added
