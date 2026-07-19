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
