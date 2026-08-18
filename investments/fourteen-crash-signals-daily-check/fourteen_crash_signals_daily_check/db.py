"""signals_hot_watchlist + signals_alert_state schema and CRUD -- this
package's own tables, built on the shared investments.db connection (same
pattern as goat.db's goat_* tables)."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_signals_tables(conn: sqlite3.Connection) -> None:
    with conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS signals_hot_watchlist (
                ticker        TEXT PRIMARY KEY,
                sector_label  TEXT NOT NULL,
                market_cap    REAL NOT NULL,
                rank          INTEGER NOT NULL,
                computed_at   TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS signals_alert_state (
                marker_key    TEXT PRIMARY KEY,
                is_firing     INTEGER NOT NULL,
                detail        TEXT NOT NULL,
                updated_at    TEXT NOT NULL
            );
        """)


def replace_hot_watchlist(conn: sqlite3.Connection, rows: list[dict]) -> None:
    """Delete-all-then-insert-all, not a per-row upsert -- mirrors
    goat.db.replace_sp500_constituents: this is recomputed fresh every run
    (see watchlist.get_or_refresh_hot_watchlist), so a stale row for a ticker
    that's dropped off the hot list must not linger."""
    now = _now()
    with conn:
        conn.execute("DELETE FROM signals_hot_watchlist")
        conn.executemany(
            """INSERT INTO signals_hot_watchlist (ticker, sector_label, market_cap, rank, computed_at)
               VALUES (?, ?, ?, ?, ?)""",
            [(r["ticker"], r["sector_label"], r["market_cap"], r["rank"], now) for r in rows],
        )


def get_hot_watchlist(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM signals_hot_watchlist ORDER BY rank").fetchall()


def upsert_signal_state(conn: sqlite3.Connection, *, marker_key: str, is_firing: bool, detail: str) -> bool:
    """Returns True only on a False/absent -> True transition (a genuine
    new-firing event worth alerting on) -- see alerts.maybe_notify."""
    prior = conn.execute(
        "SELECT is_firing FROM signals_alert_state WHERE marker_key = ?", (marker_key,)
    ).fetchone()
    was_firing = bool(prior["is_firing"]) if prior else False
    with conn:
        conn.execute(
            """INSERT INTO signals_alert_state (marker_key, is_firing, detail, updated_at)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(marker_key) DO UPDATE SET is_firing=excluded.is_firing,
               detail=excluded.detail, updated_at=excluded.updated_at""",
            (marker_key, int(is_firing), detail, _now()),
        )
    return is_firing and not was_firing


def get_all_signal_states(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM signals_alert_state ORDER BY marker_key").fetchall()
