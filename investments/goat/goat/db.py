"""goat_alert_history schema + CRUD -- Goat's own alert table, kept separate from
my-trader's alert_history (see the Phase 1 plan's Notes for why) but built on the
same shared investments.db connection."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_goat_tables(conn: sqlite3.Connection) -> None:
    with conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS goat_alert_history (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker          TEXT NOT NULL,
                source_table    TEXT NOT NULL,
                check_name      TEXT NOT NULL,
                severity        TEXT NOT NULL,
                message         TEXT NOT NULL,
                created_at      TEXT NOT NULL,
                acknowledged    INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS goat_pending_candidates (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker          TEXT NOT NULL UNIQUE,
                sector_label    TEXT NOT NULL,
                signal_detail   TEXT NOT NULL,
                source          TEXT NOT NULL DEFAULT 'goat_sector_rotation',
                flagged_at      TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS goat_sp500_constituents (
                ticker      TEXT PRIMARY KEY,
                security    TEXT NOT NULL,
                gics_sector TEXT NOT NULL,
                fetched_at  TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS goat_insider_filings_seen (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                dedup_key       TEXT NOT NULL UNIQUE,
                ticker          TEXT NOT NULL,
                filing_date     TEXT NOT NULL,
                trade_date      TEXT NOT NULL,
                insider_name    TEXT NOT NULL,
                trade_type      TEXT NOT NULL,
                value           REAL NOT NULL,
                kind            TEXT NOT NULL,
                seen_at         TEXT NOT NULL
            );
        """)
    # Migration for DBs created before pct_owned_change existed (added
    # 2026-08-17 for the repeated-small-sales pattern -- see
    # count_insider_sales_since) -- SQLite has no "ADD COLUMN IF NOT EXISTS",
    # so this is guarded by catching the duplicate-column error instead.
    # Safe to call every init_goat_tables run (idempotent).
    with conn:
        try:
            conn.execute("ALTER TABLE goat_insider_filings_seen ADD COLUMN pct_owned_change REAL")
        except sqlite3.OperationalError:
            pass
    # Migration for DBs created before trade_date existed on pending_candidates
    # (added 2026-08-18 for price-since-trade tracking -- see
    # insider_scan.compute_discovery_price_performance). NULL for non-insider
    # candidate sources (e.g. sector rotation), which have no single trade date.
    with conn:
        try:
            conn.execute("ALTER TABLE goat_pending_candidates ADD COLUMN trade_date TEXT")
        except sqlite3.OperationalError:
            pass


def get_open_goat_alert(
    conn: sqlite3.Connection, ticker: str, source_table: str, check_name: str
) -> sqlite3.Row | None:
    """Mirrors mytrader.db.get_open_alert's dedup shape exactly -- message
    deliberately excluded from the dedup key for the same reason (see that
    function's docstring)."""
    return conn.execute(
        """SELECT * FROM goat_alert_history
           WHERE ticker = ? AND source_table = ? AND check_name = ? AND acknowledged = 0
           ORDER BY created_at DESC LIMIT 1""",
        (ticker, source_table, check_name),
    ).fetchone()


def insert_goat_alert(
    conn: sqlite3.Connection, *, ticker: str, source_table: str,
    check_name: str, severity: str, message: str,
) -> None:
    now = _now()
    with conn:
        conn.execute(
            """INSERT INTO goat_alert_history
               (ticker, source_table, check_name, severity, message, created_at, acknowledged)
               VALUES (?, ?, ?, ?, ?, ?, 0)""",
            (ticker, source_table, check_name, severity, message, now),
        )


def acknowledge_goat_alert(conn: sqlite3.Connection, alert_id: int) -> None:
    with conn:
        conn.execute("UPDATE goat_alert_history SET acknowledged = 1 WHERE id = ?", (alert_id,))


def get_open_goat_alerts(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM goat_alert_history WHERE acknowledged = 0 ORDER BY created_at DESC"
    ).fetchall()


def get_goat_pending_candidate(conn: sqlite3.Connection, ticker: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM goat_pending_candidates WHERE ticker = ?", (ticker,)
    ).fetchone()


def get_all_goat_pending_candidates(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM goat_pending_candidates ORDER BY ticker"
    ).fetchall()


def insert_goat_pending_candidate(
    conn: sqlite3.Connection, *, ticker: str, sector_label: str,
    signal_detail: str, source: str = "goat_sector_rotation",
    trade_date: str | None = None,
) -> None:
    with conn:
        conn.execute(
            """INSERT OR IGNORE INTO goat_pending_candidates
               (ticker, sector_label, signal_detail, source, flagged_at, trade_date)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (ticker, sector_label, signal_detail, source, _now(), trade_date),
        )


def delete_goat_pending_candidate(conn: sqlite3.Connection, ticker: str) -> int:
    with conn:
        cur = conn.execute(
            "DELETE FROM goat_pending_candidates WHERE ticker = ?", (ticker,)
        )
        return cur.rowcount


def get_sp500_constituents_fetched_at(conn: sqlite3.Connection) -> str | None:
    """The whole table is refreshed atomically (replace_sp500_constituents), so
    every row shares the same fetched_at -- MAX is just "the" value, not really
    an aggregation."""
    row = conn.execute("SELECT MAX(fetched_at) AS fetched_at FROM goat_sp500_constituents").fetchone()
    return row["fetched_at"] if row is not None else None


def replace_sp500_constituents(conn: sqlite3.Connection, rows: list[dict]) -> None:
    """Delete-all-then-insert-all, not a per-row upsert -- the constituent list
    changes membership (additions/removals) between refreshes, and a stale row
    for a ticker that's dropped out of the index must not linger."""
    now = _now()
    with conn:
        conn.execute("DELETE FROM goat_sp500_constituents")
        conn.executemany(
            """INSERT INTO goat_sp500_constituents (ticker, security, gics_sector, fetched_at)
               VALUES (?, ?, ?, ?)""",
            [(r["ticker"], r["security"], r["gics_sector"], now) for r in rows],
        )


def get_sp500_constituents(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM goat_sp500_constituents ORDER BY ticker").fetchall()


def insert_goat_insider_filing_seen(
    conn: sqlite3.Connection, *, dedup_key: str, ticker: str, filing_date: str,
    trade_date: str, insider_name: str, trade_type: str, value: float, kind: str,
    pct_owned_change: float | None = None,
) -> bool:
    """Returns True if this filing was newly seen (inserted), False if it's a
    duplicate of a filing already alerted/staged in a prior run. Every sale
    filing gets recorded here regardless of whether it was alert-worthy --
    count_insider_sales_since relies on the full history, not just alerted
    filings, to catch a run of individually-small sales."""
    with conn:
        cur = conn.execute(
            """INSERT OR IGNORE INTO goat_insider_filings_seen
               (dedup_key, ticker, filing_date, trade_date, insider_name, trade_type, value, kind, seen_at, pct_owned_change)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (dedup_key, ticker, filing_date, trade_date, insider_name, trade_type, value, kind, _now(), pct_owned_change),
        )
        return cur.rowcount == 1


def get_recent_insider_filings_seen(
    conn: sqlite3.Connection, kind: str | None = None, limit: int = 50
) -> list[sqlite3.Row]:
    if kind is not None:
        return conn.execute(
            "SELECT * FROM goat_insider_filings_seen WHERE kind = ? ORDER BY seen_at DESC LIMIT ?",
            (kind, limit),
        ).fetchall()
    return conn.execute(
        "SELECT * FROM goat_insider_filings_seen ORDER BY seen_at DESC LIMIT ?", (limit,)
    ).fetchall()


def count_insider_sales_since(
    conn: sqlite3.Connection, *, ticker: str, insider_name: str, start_date: str, before_date: str,
) -> int:
    """Counts this insider's prior 'S' filings on this ticker with
    start_date <= trade_date < before_date -- strictly before, so a filing
    can never count itself regardless of insert order. Used to detect a
    pattern of repeated smaller sales (each individually under the
    single-sale threshold) that only look alarming in aggregate -- see
    insider_scan.run_holdings_watch."""
    row = conn.execute(
        """SELECT COUNT(*) AS n FROM goat_insider_filings_seen
           WHERE ticker = ? AND insider_name = ? AND trade_type = 'S'
             AND trade_date >= ? AND trade_date < ?""",
        (ticker, insider_name, start_date, before_date),
    ).fetchone()
    return row["n"]
