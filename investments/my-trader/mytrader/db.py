"""holdings / watchlist / alert_history schema + CRUD, built on briefs-finance's shared DB connection."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_mytrader_tables(conn: sqlite3.Connection) -> None:
    with conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS holdings (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker              TEXT NOT NULL,
                name                TEXT,
                asset_type          TEXT NOT NULL,
                bucket              TEXT NOT NULL,
                qty                 REAL NOT NULL,
                avg_price           REAL NOT NULL,
                currency            TEXT,
                last_expense_ratio  REAL,
                last_checked_at     TEXT,
                added_at            TEXT NOT NULL,
                updated_at          TEXT NOT NULL,
                UNIQUE(ticker, bucket)
            );
            CREATE TABLE IF NOT EXISTS watchlist (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker              TEXT NOT NULL,
                name                TEXT,
                asset_type          TEXT NOT NULL,
                bucket              TEXT NOT NULL,
                status              TEXT NOT NULL DEFAULT 'raw',
                notes               TEXT,
                source              TEXT NOT NULL DEFAULT 'manual',
                last_expense_ratio  REAL,
                last_checked_at     TEXT,
                added_at            TEXT NOT NULL,
                updated_at          TEXT NOT NULL,
                UNIQUE(ticker, bucket)
            );
            CREATE TABLE IF NOT EXISTS alert_history (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker          TEXT NOT NULL,
                source_table    TEXT NOT NULL,
                check_name      TEXT NOT NULL,
                severity        TEXT NOT NULL,
                message         TEXT NOT NULL,
                created_at      TEXT NOT NULL,
                acknowledged    INTEGER NOT NULL DEFAULT 0
            );
        """)


def get_holding_row(conn: sqlite3.Connection, ticker: str, bucket: str | None = None) -> sqlite3.Row | None:
    if bucket is not None:
        return conn.execute(
            "SELECT * FROM holdings WHERE ticker = ? AND bucket = ?", (ticker, bucket)
        ).fetchone()
    return conn.execute(
        "SELECT * FROM holdings WHERE ticker = ? ORDER BY updated_at DESC LIMIT 1", (ticker,)
    ).fetchone()


def get_watchlist_row(conn: sqlite3.Connection, ticker: str, bucket: str | None = None) -> sqlite3.Row | None:
    if bucket is not None:
        return conn.execute(
            "SELECT * FROM watchlist WHERE ticker = ? AND bucket = ?", (ticker, bucket)
        ).fetchone()
    return conn.execute(
        "SELECT * FROM watchlist WHERE ticker = ? ORDER BY updated_at DESC LIMIT 1", (ticker,)
    ).fetchone()


def get_all_holdings(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM holdings ORDER BY ticker, bucket").fetchall()


def get_all_watchlist(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM watchlist ORDER BY ticker, bucket").fetchall()


def upsert_holding(
    conn: sqlite3.Connection,
    *,
    ticker: str,
    name: str | None,
    asset_type: str,
    bucket: str,
    qty: float,
    avg_price: float,
    currency: str | None = None,
    last_expense_ratio: float | None = None,
) -> None:
    """Insert or update a holding by (ticker, bucket) natural key."""
    existing = get_holding_row(conn, ticker, bucket)
    now = _now()
    with conn:
        if existing:
            conn.execute(
                """UPDATE holdings SET name = ?, asset_type = ?, qty = ?, avg_price = ?,
                   currency = ?, last_expense_ratio = ?, updated_at = ?
                   WHERE ticker = ? AND bucket = ?""",
                (name, asset_type, qty, avg_price, currency, last_expense_ratio, now, ticker, bucket),
            )
        else:
            conn.execute(
                """INSERT INTO holdings
                   (ticker, name, asset_type, bucket, qty, avg_price, currency,
                    last_expense_ratio, added_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (ticker, name, asset_type, bucket, qty, avg_price, currency,
                 last_expense_ratio, now, now),
            )


def delete_holding_if_zero(conn: sqlite3.Connection, ticker: str, bucket: str, epsilon: float = 1e-6) -> None:
    row = get_holding_row(conn, ticker, bucket)
    if row is not None and abs(row["qty"]) < epsilon:
        with conn:
            conn.execute("DELETE FROM holdings WHERE ticker = ? AND bucket = ?", (ticker, bucket))


def upsert_watchlist_row(
    conn: sqlite3.Connection,
    *,
    ticker: str,
    name: str | None,
    asset_type: str,
    bucket: str,
    status: str = "raw",
    notes: str | None = None,
    source: str = "manual",
    last_expense_ratio: float | None = None,
) -> None:
    """Insert or update a watchlist row by (ticker, bucket) natural key."""
    existing = get_watchlist_row(conn, ticker, bucket)
    now = _now()
    with conn:
        if existing:
            conn.execute(
                """UPDATE watchlist SET name = ?, asset_type = ?, status = ?, notes = ?,
                   source = ?, last_expense_ratio = ?, updated_at = ?
                   WHERE ticker = ? AND bucket = ?""",
                (name, asset_type, status, notes, source, last_expense_ratio, now, ticker, bucket),
            )
        else:
            conn.execute(
                """INSERT INTO watchlist
                   (ticker, name, asset_type, bucket, status, notes, source,
                    last_expense_ratio, added_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (ticker, name, asset_type, bucket, status, notes, source,
                 last_expense_ratio, now, now),
            )


def get_open_alert(
    conn: sqlite3.Connection, ticker: str, source_table: str, check_name: str
) -> sqlite3.Row | None:
    """Most recent unacknowledged alert for this (ticker, source_table, check_name),
    or None. Dedup key deliberately excludes `message` — a check's message text can
    drift run-to-run (e.g. a PE ratio nudging) without that being a new material
    event; only a flag->ok->flag transition should raise a fresh alert."""
    return conn.execute(
        """SELECT * FROM alert_history
           WHERE ticker = ? AND source_table = ? AND check_name = ? AND acknowledged = 0
           ORDER BY created_at DESC LIMIT 1""",
        (ticker, source_table, check_name),
    ).fetchone()


def insert_alert(
    conn: sqlite3.Connection, *, ticker: str, source_table: str,
    check_name: str, severity: str, message: str,
) -> None:
    now = _now()
    with conn:
        conn.execute(
            """INSERT INTO alert_history
               (ticker, source_table, check_name, severity, message, created_at, acknowledged)
               VALUES (?, ?, ?, ?, ?, ?, 0)""",
            (ticker, source_table, check_name, severity, message, now),
        )


def acknowledge_alert(conn: sqlite3.Connection, alert_id: int) -> None:
    with conn:
        conn.execute("UPDATE alert_history SET acknowledged = 1 WHERE id = ?", (alert_id,))


def get_open_alerts(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM alert_history WHERE acknowledged = 0 ORDER BY created_at DESC"
    ).fetchall()


def touch_checked(
    conn: sqlite3.Connection, table: str, ticker: str, bucket: str,
    last_expense_ratio: float | None,
) -> None:
    """Update last_checked_at (and last_expense_ratio if the check produced one) for
    a holdings/watchlist row. `table` must be "holdings" or "watchlist" — always a
    hardcoded literal from monitor.py's own call sites, never external input."""
    assert table in ("holdings", "watchlist"), f"invalid table: {table!r}"
    now = _now()
    with conn:
        if last_expense_ratio is not None:
            conn.execute(
                f"UPDATE {table} SET last_checked_at = ?, last_expense_ratio = ? "
                f"WHERE ticker = ? AND bucket = ?",
                (now, last_expense_ratio, ticker, bucket),
            )
        else:
            conn.execute(
                f"UPDATE {table} SET last_checked_at = ? WHERE ticker = ? AND bucket = ?",
                (now, ticker, bucket),
            )
