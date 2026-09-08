"""superinvestor_filings_seen -- permanent, append-only, deduped-by-key log of every
fast-disclosure filing this scanner has ever surfaced for a tracked investor. A filing
alerts only on its first insert. Kept deliberately separate from
goat_insider_filings_seen (different filer scope, different purpose -- see
.agent/plans/completed/superinvestor-filings-scanner.md NOTES #12). Mirrors goat/db.py's
INSERT-OR-IGNORE + rowcount dedup idiom and its idempotent ALTER-TABLE migration
pattern."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_superinvestor_tables(conn: sqlite3.Connection) -> None:
    with conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS superinvestor_filings_seen (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                dedup_key         TEXT NOT NULL UNIQUE,
                source            TEXT NOT NULL,          -- 'edgar' | 'sast'
                filer_key         TEXT NOT NULL,          -- e.g. 'pabrai'
                filer_display     TEXT NOT NULL,
                form_type         TEXT NOT NULL,          -- 'SC 13G', '4', 'SAST Reg 29(2)', ...
                issuer            TEXT NOT NULL,
                issuer_ticker     TEXT,
                accession         TEXT,                   -- EDGAR accession / exchange ref
                event_date        TEXT,                   -- transaction / acquisition date
                filed_date        TEXT,
                shares            REAL,
                pct_owned         REAL,
                pct_owned_change  REAL,
                material_crossing TEXT,                   -- '5% cross' | '10% cross' | 'below 5%' | NULL
                transaction_code  TEXT,                   -- P/S/A/M/G/F for Form 4; NULL otherwise
                raw_url           TEXT,
                first_seen_at     TEXT NOT NULL
            );
        """)
    # Idempotent column-migration hook for any future column -- SQLite has no
    # "ADD COLUMN IF NOT EXISTS" so a duplicate-column error is caught and ignored
    # (mirrors goat/db.py:71-115). No columns to migrate yet; keep the pattern ready.
    _MIGRATIONS: tuple[str, ...] = ()
    with conn:
        for stmt in _MIGRATIONS:
            try:
                conn.execute(stmt)
            except sqlite3.OperationalError:
                pass


def insert_superinvestor_filing_seen(
    conn: sqlite3.Connection,
    *,
    dedup_key: str,
    source: str,
    filer_key: str,
    filer_display: str,
    form_type: str,
    issuer: str,
    issuer_ticker: str | None = None,
    accession: str | None = None,
    event_date: str | None = None,
    filed_date: str | None = None,
    shares: float | None = None,
    pct_owned: float | None = None,
    pct_owned_change: float | None = None,
    material_crossing: str | None = None,
    transaction_code: str | None = None,
    raw_url: str | None = None,
) -> bool:
    """Returns True if this filing was newly seen (inserted), False if it duplicates a
    filing already recorded in a prior run. Append-only; a same-day re-run is a safe
    no-op (mirrors goat.db.insert_goat_insider_filing_seen)."""
    with conn:
        cur = conn.execute(
            """INSERT OR IGNORE INTO superinvestor_filings_seen
               (dedup_key, source, filer_key, filer_display, form_type, issuer,
                issuer_ticker, accession, event_date, filed_date, shares, pct_owned,
                pct_owned_change, material_crossing, transaction_code, raw_url, first_seen_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (dedup_key, source, filer_key, filer_display, form_type, issuer,
             issuer_ticker, accession, event_date, filed_date, shares, pct_owned,
             pct_owned_change, material_crossing, transaction_code, raw_url, _now()),
        )
        return cur.rowcount == 1


def get_recent_superinvestor_filings_seen(
    conn: sqlite3.Connection, source: str | None = None, limit: int = 100
) -> list[sqlite3.Row]:
    if source is not None:
        return conn.execute(
            """SELECT * FROM superinvestor_filings_seen WHERE source = ?
               ORDER BY first_seen_at DESC LIMIT ?""",
            (source, limit),
        ).fetchall()
    return conn.execute(
        "SELECT * FROM superinvestor_filings_seen ORDER BY first_seen_at DESC LIMIT ?",
        (limit,),
    ).fetchall()


def get_last_pct_owned(
    conn: sqlite3.Connection, filer_key: str, issuer: str
) -> float | None:
    """Most recent prior `pct_owned` this scanner recorded for the same
    filer_key + issuer pair -- the prior-percent baseline
    edgar_parse.classify_material_crossing compares against. None when there is no
    prior row or the prior row never carried a parsed percent."""
    row = conn.execute(
        """SELECT pct_owned FROM superinvestor_filings_seen
           WHERE filer_key = ? AND issuer = ? AND pct_owned IS NOT NULL
           ORDER BY first_seen_at DESC LIMIT 1""",
        (filer_key, issuer),
    ).fetchone()
    return row["pct_owned"] if row is not None else None


def count_seen(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT COUNT(*) AS n FROM superinvestor_filings_seen").fetchone()
    return row["n"]
