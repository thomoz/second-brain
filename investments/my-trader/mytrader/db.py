"""holdings / watchlist / alert_history schema + CRUD, built on briefs-finance's shared DB connection."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_watchlist_return_columns(conn: sqlite3.Connection) -> None:
    """Additive migration for the dividend-yield/10Y-return enrichment columns —
    ALTER TABLE ADD COLUMN rather than a CREATE TABLE change, so it's safe to run
    against a watchlist table that already has real rows."""
    cols = {row["name"] for row in conn.execute("PRAGMA table_info(watchlist)")}
    with conn:
        if "dividend_yield_pct" not in cols:
            conn.execute("ALTER TABLE watchlist ADD COLUMN dividend_yield_pct REAL")
        if "ten_year_return_pct" not in cols:
            conn.execute("ALTER TABLE watchlist ADD COLUMN ten_year_return_pct REAL")
        if "return_data_updated_at" not in cols:
            conn.execute("ALTER TABLE watchlist ADD COLUMN return_data_updated_at TEXT")


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
            CREATE TABLE IF NOT EXISTS sync_state (
                key             TEXT PRIMARY KEY,
                value           TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS pending_candidates (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker          TEXT NOT NULL UNIQUE,
                company_name    TEXT,
                buy_thesis      TEXT,
                source          TEXT NOT NULL DEFAULT 'briefs_finance_ingest',
                synced_at       TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS macro_snapshot_cache (
                name            TEXT PRIMARY KEY,
                verdict         TEXT NOT NULL,
                detail          TEXT NOT NULL,
                computed_at     TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sec_cik_map (
                ticker          TEXT PRIMARY KEY,
                cik             TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sec_filing_cache (
                ticker              TEXT NOT NULL,
                filing_type         TEXT NOT NULL,
                accession_number    TEXT NOT NULL,
                summary             TEXT NOT NULL,
                fetched_at          TEXT NOT NULL,
                PRIMARY KEY (ticker, filing_type)
            );
            CREATE TABLE IF NOT EXISTS asx_announcement_cache (
                ticker              TEXT NOT NULL,
                announcement_type   TEXT NOT NULL,
                announcement_id     TEXT NOT NULL,
                summary             TEXT NOT NULL,
                fetched_at          TEXT NOT NULL,
                PRIMARY KEY (ticker, announcement_type)
            );
        """)
    _ensure_watchlist_return_columns(conn)


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


def get_pending_candidate(conn: sqlite3.Connection, ticker: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM pending_candidates WHERE ticker = ?", (ticker,)
    ).fetchone()


def get_all_pending_candidates(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM pending_candidates ORDER BY ticker").fetchall()


def insert_pending_candidate(
    conn: sqlite3.Connection, *, ticker: str, company_name: str | None,
    buy_thesis: str | None, source: str = "briefs_finance_ingest",
) -> None:
    with conn:
        conn.execute(
            """INSERT OR IGNORE INTO pending_candidates
               (ticker, company_name, buy_thesis, source, synced_at)
               VALUES (?, ?, ?, ?, ?)""",
            (ticker, company_name, buy_thesis, source, _now()),
        )


def delete_pending_candidate(conn: sqlite3.Connection, ticker: str) -> int:
    with conn:
        cur = conn.execute("DELETE FROM pending_candidates WHERE ticker = ?", (ticker,))
        return cur.rowcount


def delete_watchlist_row(conn: sqlite3.Connection, ticker: str, bucket: str | None = None) -> int:
    """Delete a watchlist row by ticker (and bucket, if given). bucket=None deletes
    every row for that ticker across all buckets. Returns the number of rows deleted."""
    with conn:
        if bucket is not None:
            cur = conn.execute(
                "DELETE FROM watchlist WHERE ticker = ? AND bucket = ?", (ticker, bucket)
            )
        else:
            cur = conn.execute("DELETE FROM watchlist WHERE ticker = ?", (ticker,))
        return cur.rowcount


def update_watchlist_return_data(
    conn: sqlite3.Connection, ticker: str, bucket: str,
    dividend_yield_pct: float | None, ten_year_return_pct: float | None,
) -> None:
    with conn:
        conn.execute(
            """UPDATE watchlist SET dividend_yield_pct = ?, ten_year_return_pct = ?,
               return_data_updated_at = ? WHERE ticker = ? AND bucket = ?""",
            (dividend_yield_pct, ten_year_return_pct, _now(), ticker, bucket),
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


def get_sync_watermark(conn: sqlite3.Connection, key: str) -> str | None:
    row = conn.execute("SELECT value FROM sync_state WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else None


def set_sync_watermark(conn: sqlite3.Connection, key: str, value: str) -> None:
    with conn:
        conn.execute(
            "INSERT OR REPLACE INTO sync_state (key, value) VALUES (?, ?)",
            (key, value),
        )


def upsert_macro_snapshot(conn: sqlite3.Connection, checks: list) -> None:
    """Persist the latest macro-indicator snapshot (all 9, regardless of verdict) so
    checks/principles_fit.py can read a cheap, cached regime read on every Find call
    instead of re-fetching MOVE/FRED/ABS/ONS live each time — those signals are
    inherently slow-moving (CPI is monthly/quarterly, credit spreads/yield curve are
    daily), so Monitor's once-a-day refresh is fresh enough. Always overwrites — only
    the latest snapshot matters, no history needed here (Monitor's own alert_history
    already tracks flagged changes over time)."""
    now = _now()
    with conn:
        for c in checks:
            conn.execute(
                """INSERT OR REPLACE INTO macro_snapshot_cache (name, verdict, detail, computed_at)
                   VALUES (?, ?, ?, ?)""",
                (c.name, c.verdict, c.detail, now),
            )


def get_macro_snapshot(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM macro_snapshot_cache ORDER BY name").fetchall()


def upsert_cik_map_bulk(conn: sqlite3.Connection, ticker_to_cik: dict[str, str]) -> None:
    """Full resync, not incremental -- company tickers get delisted/renamed, so a
    stale row must be able to disappear on refresh, not just accumulate."""
    with conn:
        conn.execute("DELETE FROM sec_cik_map")
        conn.executemany(
            "INSERT INTO sec_cik_map (ticker, cik) VALUES (?, ?)",
            list(ticker_to_cik.items()),
        )


def get_cik_for_ticker(conn: sqlite3.Connection, ticker: str) -> str | None:
    row = conn.execute("SELECT cik FROM sec_cik_map WHERE ticker = ?", (ticker,)).fetchone()
    return row["cik"] if row else None


def get_cached_filing_summary(
    conn: sqlite3.Connection, ticker: str, filing_type: str
) -> sqlite3.Row | None:
    return conn.execute(
        """SELECT * FROM sec_filing_cache WHERE ticker = ? AND filing_type = ?""",
        (ticker, filing_type),
    ).fetchone()


def upsert_filing_summary_cache(
    conn: sqlite3.Connection, *, ticker: str, filing_type: str,
    accession_number: str, summary: str,
) -> None:
    with conn:
        conn.execute(
            """INSERT OR REPLACE INTO sec_filing_cache
               (ticker, filing_type, accession_number, summary, fetched_at)
               VALUES (?, ?, ?, ?, ?)""",
            (ticker, filing_type, accession_number, summary, _now()),
        )


def get_cached_asx_summary(
    conn: sqlite3.Connection, ticker: str, announcement_type: str
) -> sqlite3.Row | None:
    return conn.execute(
        """SELECT * FROM asx_announcement_cache WHERE ticker = ? AND announcement_type = ?""",
        (ticker, announcement_type),
    ).fetchone()


def upsert_asx_summary_cache(
    conn: sqlite3.Connection, *, ticker: str, announcement_type: str,
    announcement_id: str, summary: str,
) -> None:
    with conn:
        conn.execute(
            """INSERT OR REPLACE INTO asx_announcement_cache
               (ticker, announcement_type, announcement_id, summary, fetched_at)
               VALUES (?, ?, ?, ?, ?)""",
            (ticker, announcement_type, announcement_id, summary, _now()),
        )


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
