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
        """)


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
) -> None:
    with conn:
        conn.execute(
            """INSERT OR IGNORE INTO goat_pending_candidates
               (ticker, sector_label, signal_detail, source, flagged_at)
               VALUES (?, ?, ?, ?, ?)""",
            (ticker, sector_label, signal_detail, source, _now()),
        )


def delete_goat_pending_candidate(conn: sqlite3.Connection, ticker: str) -> int:
    with conn:
        cur = conn.execute(
            "DELETE FROM goat_pending_candidates WHERE ticker = ?", (ticker,)
        )
        return cur.rowcount
