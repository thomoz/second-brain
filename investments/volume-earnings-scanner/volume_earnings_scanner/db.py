"""volume_earnings_pending_candidates + volume_earnings_universe_cache schema and
CRUD. Built on the shared VPS-only investments.db connection, kept deliberately
separate from goat's own pending-candidates table and from moat_pending_candidates
(different filer scope + its own signal_type/signal_detail columns).

Mirrors ai_resistant_moat_scanner/db.py's INSERT-OR-IGNORE + `cur.rowcount == 1`
dedup idiom and its idempotent ALTER-TABLE migration hook (empty for now, pattern
kept ready)."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_ve_tables(conn: sqlite3.Connection) -> None:
    with conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS volume_earnings_pending_candidates (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker         TEXT NOT NULL UNIQUE,
                signal_type    TEXT NOT NULL,
                signal_detail  TEXT NOT NULL,
                company_name   TEXT,
                source         TEXT NOT NULL DEFAULT 'volume_earnings_scan',
                flagged_at     TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS volume_earnings_universe_cache (
                ticker          TEXT PRIMARY KEY,
                company         TEXT NOT NULL,
                market_cap_text TEXT NOT NULL,
                fetched_at      TEXT NOT NULL
            );
        """)
    # Idempotent column-migration hook -- SQLite has no "ADD COLUMN IF NOT EXISTS",
    # so a duplicate-column error is caught and ignored (mirrors moat/goat db.py). No
    # columns to migrate yet; keep the pattern ready.
    _MIGRATIONS: tuple[str, ...] = ()
    with conn:
        for stmt in _MIGRATIONS:
            try:
                conn.execute(stmt)
            except sqlite3.OperationalError:
                pass


# --- volume_earnings_pending_candidates ----------------------------------------

def insert_ve_pending_candidate(
    conn: sqlite3.Connection,
    *,
    ticker: str,
    signal_type: str,
    signal_detail: str,
    company_name: str | None = None,
    source: str = "volume_earnings_scan",
) -> bool:
    """Returns True if this candidate was newly staged (inserted), False if a pending
    row for the ticker already exists. Append-only; a same-day re-run is a safe no-op
    -- a ticker that trips a NEW signal on a later run keeps its originally-staged
    signal_type/detail rather than upgrading (same INSERT-OR-IGNORE posture as
    moat_pending_candidates)."""
    with conn:
        cur = conn.execute(
            """INSERT OR IGNORE INTO volume_earnings_pending_candidates
               (ticker, signal_type, signal_detail, company_name, source, flagged_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (ticker, signal_type, signal_detail, company_name, source, _now()),
        )
        return cur.rowcount == 1


def get_ve_pending_candidate(conn: sqlite3.Connection, ticker: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM volume_earnings_pending_candidates WHERE ticker = ?", (ticker,)
    ).fetchone()


def get_all_ve_pending_candidates(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM volume_earnings_pending_candidates ORDER BY flagged_at DESC"
    ).fetchall()


def delete_ve_pending_candidate(conn: sqlite3.Connection, ticker: str) -> int:
    with conn:
        cur = conn.execute(
            "DELETE FROM volume_earnings_pending_candidates WHERE ticker = ?", (ticker,)
        )
        return cur.rowcount


# --- volume_earnings_universe_cache --------------------------------------------

def get_universe_cache_fetched_at(conn: sqlite3.Connection) -> str | None:
    """The whole table is refreshed atomically (replace_universe_cache), so every row
    shares the same fetched_at -- MAX is just "the" value."""
    row = conn.execute(
        "SELECT MAX(fetched_at) AS fetched_at FROM volume_earnings_universe_cache"
    ).fetchone()
    return row["fetched_at"] if row is not None else None


def replace_universe_cache(conn: sqlite3.Connection, rows: list[dict]) -> None:
    """Delete-all-then-insert-all -- the screened membership changes between refreshes
    and a stale row for a name that's dropped out must not linger (mirrors
    ai_resistant_moat_scanner.db.replace_universe_cache)."""
    now = _now()
    with conn:
        conn.execute("DELETE FROM volume_earnings_universe_cache")
        conn.executemany(
            """INSERT INTO volume_earnings_universe_cache
               (ticker, company, market_cap_text, fetched_at)
               VALUES (?, ?, ?, ?)""",
            [(r["ticker"], r.get("company") or "", r.get("market_cap_text") or "", now)
             for r in rows],
        )


def get_universe_cache(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM volume_earnings_universe_cache ORDER BY ticker"
    ).fetchall()
