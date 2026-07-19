"""Briefs Finance ingest -> my-trader candidate sync (tool-preplan.md "Briefs Finance
report integration", confirmed 2026-07-19; revised 2026-07-19 same day per Shaun's
feedback after the first backlog sync flooded watchlist.md with stale/AI-hype
picks).

Reads briefs-finance's recommendations table for rows newer than a stored watermark
(sync_state key "briefs_finance_last_recommendation_id") and inserts each into the
pending_candidates table -- a separate staging area, never directly into watchlist.
Rendered as its own file (synced-candidates-pending-review.md by snapshot.py) so
watchlist.md stays exactly what Shaun has explicitly curated. Promoting a
pending candidate into the real watchlist (main.py's promote-candidate command) or
discarding it (dismiss-candidate) are separate, explicit actions.

This function is manual/on-demand only (main.py's sync-candidates command) -- it is
NOT called from monitor.run_monitor() (removed 2026-07-19 same day as this file was
first built, per Shaun's "turn off automatic candidate_sync" decision: only pull new
Briefs Finance picks in when explicitly asked).

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
        if db.get_pending_candidate(conn, normalized) is not None:
            continue
        db.insert_pending_candidate(
            conn, ticker=normalized, company_name=row["company_name"],
            buy_thesis=row["buy_thesis"], source="briefs_finance_ingest",
        )
        added.append({"ticker": normalized, "company_name": row["company_name"]})

    if max_id > last_id:
        db.set_sync_watermark(conn, _WATERMARK_KEY, str(max_id))
    return added
