"""Conversational Find — ephemeral ticker lookup and explicit watchlist-add."""

from __future__ import annotations

import sqlite3

from . import db, engine, snapshot, tickers


def lookup_ticker(ticker: str, conn: sqlite3.Connection) -> dict:
    """Ephemeral 'what do you think of TICKER' lookup. Persists nothing."""
    return engine.run_assessment(ticker, conn)


def add_to_watchlist(
    ticker: str,
    name: str,
    asset_type: str,
    bucket: str,
    notes: str,
    conn: sqlite3.Connection,
) -> None:
    """Explicit 'add TICKER to the watchlist' action — a human chose to track it, so
    status is always 'discussed' here ('raw' is reserved for a future Phase C
    auto-ingest flow). Persists a DB row and regenerates the markdown snapshots."""
    normalized = tickers.normalize(ticker)
    db.upsert_watchlist_row(
        conn,
        ticker=normalized,
        name=name,
        asset_type=asset_type,
        bucket=bucket,
        status="discussed",
        notes=notes,
        source="manual",
    )
    snapshot.regenerate_all(conn)
