"""moat_pending_candidates + moat_qualitative_cache + moat_universe_cache schema
and CRUD. Built on the shared VPS-only investments.db connection, kept deliberately
separate from goat's own pending-candidates table (different filer scope + purpose).

Mirrors goat/db.py's INSERT-OR-IGNORE + `cur.rowcount == 1` dedup idiom and its
idempotent ALTER-TABLE migration hook (empty for now, pattern kept ready)."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_moat_tables(conn: sqlite3.Connection) -> None:
    with conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS moat_pending_candidates (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker            TEXT NOT NULL UNIQUE,
                industry          TEXT NOT NULL,
                moat_score        REAL NOT NULL,
                quant_score       REAL NOT NULL,
                qualitative_score REAL NOT NULL,
                thesis            TEXT NOT NULL,
                sub_scores_json   TEXT NOT NULL,
                source            TEXT NOT NULL DEFAULT 'ai_resistant_moat_scan',
                flagged_at        TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS moat_qualitative_cache (
                ticker           TEXT NOT NULL,
                accession_number TEXT NOT NULL,
                rubric_version   TEXT NOT NULL,
                extraction_json  TEXT NOT NULL,
                rubric_json      TEXT NOT NULL,
                thesis           TEXT NOT NULL,
                computed_at      TEXT NOT NULL,
                PRIMARY KEY (ticker, accession_number, rubric_version)
            );
            CREATE TABLE IF NOT EXISTS moat_universe_cache (
                ticker      TEXT PRIMARY KEY,
                company     TEXT NOT NULL,
                industry    TEXT NOT NULL,
                sector      TEXT NOT NULL,
                fetched_at  TEXT NOT NULL
            );
        """)
    # Idempotent column-migration hook -- SQLite has no "ADD COLUMN IF NOT EXISTS",
    # so a duplicate-column error is caught and ignored (mirrors goat/db.py). No
    # columns to migrate yet; keep the pattern ready.
    _MIGRATIONS: tuple[str, ...] = ()
    with conn:
        for stmt in _MIGRATIONS:
            try:
                conn.execute(stmt)
            except sqlite3.OperationalError:
                pass


# --- moat_pending_candidates ---------------------------------------------------

def insert_moat_pending_candidate(
    conn: sqlite3.Connection,
    *,
    ticker: str,
    industry: str,
    moat_score: float,
    quant_score: float,
    qualitative_score: float,
    thesis: str,
    sub_scores_json: str,
    source: str = "ai_resistant_moat_scan",
) -> bool:
    """Returns True if this candidate was newly staged (inserted), False if a pending
    row for the ticker already exists. Append-only; a same-day re-run is a safe no-op."""
    with conn:
        cur = conn.execute(
            """INSERT OR IGNORE INTO moat_pending_candidates
               (ticker, industry, moat_score, quant_score, qualitative_score, thesis,
                sub_scores_json, source, flagged_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (ticker, industry, moat_score, quant_score, qualitative_score, thesis,
             sub_scores_json, source, _now()),
        )
        return cur.rowcount == 1


def get_moat_pending_candidate(conn: sqlite3.Connection, ticker: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM moat_pending_candidates WHERE ticker = ?", (ticker,)
    ).fetchone()


def get_all_moat_pending_candidates(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM moat_pending_candidates ORDER BY moat_score DESC"
    ).fetchall()


def delete_moat_pending_candidate(conn: sqlite3.Connection, ticker: str) -> int:
    with conn:
        cur = conn.execute(
            "DELETE FROM moat_pending_candidates WHERE ticker = ?", (ticker,)
        )
        return cur.rowcount


# --- moat_qualitative_cache ---------------------------------------------------

def get_cached_qualitative(
    conn: sqlite3.Connection, ticker: str, accession_number: str, rubric_version: str
) -> sqlite3.Row | None:
    return conn.execute(
        """SELECT * FROM moat_qualitative_cache
           WHERE ticker = ? AND accession_number = ? AND rubric_version = ?""",
        (ticker, accession_number, rubric_version),
    ).fetchone()


def upsert_qualitative_cache(
    conn: sqlite3.Connection,
    *,
    ticker: str,
    accession_number: str,
    rubric_version: str,
    extraction_json: str,
    rubric_json: str,
    thesis: str,
) -> None:
    with conn:
        conn.execute(
            """INSERT OR REPLACE INTO moat_qualitative_cache
               (ticker, accession_number, rubric_version, extraction_json, rubric_json,
                thesis, computed_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (ticker, accession_number, rubric_version, extraction_json, rubric_json,
             thesis, _now()),
        )


# --- moat_universe_cache ----------------------------------------------------

def get_universe_cache_fetched_at(conn: sqlite3.Connection) -> str | None:
    """The whole table is refreshed atomically (replace_universe_cache), so every row
    shares the same fetched_at -- MAX is just "the" value."""
    row = conn.execute("SELECT MAX(fetched_at) AS fetched_at FROM moat_universe_cache").fetchone()
    return row["fetched_at"] if row is not None else None


def replace_universe_cache(conn: sqlite3.Connection, rows: list[dict]) -> None:
    """Delete-all-then-insert-all -- the screened membership changes between refreshes
    and a stale row for a name that's dropped out must not linger (mirrors
    goat.db.replace_sp500_constituents)."""
    now = _now()
    with conn:
        conn.execute("DELETE FROM moat_universe_cache")
        conn.executemany(
            """INSERT INTO moat_universe_cache (ticker, company, industry, sector, fetched_at)
               VALUES (?, ?, ?, ?, ?)""",
            [(r["ticker"], r.get("company") or "", r.get("industry") or "",
              r.get("sector") or "", now) for r in rows],
        )


def get_universe_cache(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM moat_universe_cache ORDER BY ticker").fetchall()
