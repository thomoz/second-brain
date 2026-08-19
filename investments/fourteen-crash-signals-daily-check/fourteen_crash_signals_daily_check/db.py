"""signals_hot_watchlist + signals_alert_state schema and CRUD -- this
package's own tables, built on the shared investments.db connection (same
pattern as goat.db's goat_* tables)."""

from __future__ import annotations

import sqlite3
from datetime import date, datetime, timezone


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _today() -> str:
    """Local calendar date (YYYY-MM-DD), NOT _now()[:10] (UTC) -- every caller of this
    package's one-row-per-day date keys compares against date.today() (local), e.g.
    credit_spread_issuer.py's `today = date.today()` and get_issuer_spread_near's
    target_date. Using a UTC-derived date here silently mismatched the local date for
    part of the day in Sydney (UTC+10/+11), e.g. record_issuer_spread's row was keyed
    to "yesterday" (UTC) while get_issuer_spread_near queried with today's local date
    and 0-day tolerance -- confirmed live 2026-08-19, fixed by keying every daily row to
    the same local calendar date every other date.today()-based comparison in this
    package already uses."""
    return date.today().isoformat()


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
            CREATE TABLE IF NOT EXISTS signals_lease_commitment_history (
                ticker              TEXT PRIMARY KEY,
                accession_number    TEXT NOT NULL,
                figure              REAL NOT NULL,
                filing_date         TEXT NOT NULL,
                checked_at          TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS signals_bond_cusip_cache (
                ticker              TEXT PRIMARY KEY,
                cusip               TEXT NOT NULL,
                accession_number    TEXT NOT NULL,
                resolved_at         TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS signals_issuer_spread_history (
                ticker              TEXT NOT NULL,
                spread_value        REAL NOT NULL,
                observed_at         TEXT NOT NULL,
                PRIMARY KEY (ticker, observed_at)
            );
            CREATE TABLE IF NOT EXISTS signals_manual_bond_yield (
                ticker              TEXT PRIMARY KEY,
                cusip               TEXT,
                yield_pct           REAL NOT NULL,
                entered_at          TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS signals_putcall_history (
                observed_at   TEXT PRIMARY KEY,
                ratio         REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS signals_regulator_alert_seen (
                guid          TEXT PRIMARY KEY,
                source        TEXT NOT NULL,
                title         TEXT NOT NULL,
                seen_at       TEXT NOT NULL
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


def get_lease_commitment_history(conn: sqlite3.Connection, ticker: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM signals_lease_commitment_history WHERE ticker = ?", (ticker,)
    ).fetchone()


def upsert_lease_commitment_history(
    conn: sqlite3.Connection, *, ticker: str, accession_number: str, figure: float, filing_date: str
) -> None:
    with conn:
        conn.execute(
            """INSERT INTO signals_lease_commitment_history
               (ticker, accession_number, figure, filing_date, checked_at)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(ticker) DO UPDATE SET accession_number=excluded.accession_number,
               figure=excluded.figure, filing_date=excluded.filing_date, checked_at=excluded.checked_at""",
            (ticker, accession_number, figure, filing_date, _now()),
        )


def get_bond_cusip(conn: sqlite3.Connection, ticker: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM signals_bond_cusip_cache WHERE ticker = ?", (ticker,)).fetchone()


def upsert_bond_cusip(conn: sqlite3.Connection, *, ticker: str, cusip: str, accession_number: str) -> None:
    with conn:
        conn.execute(
            """INSERT INTO signals_bond_cusip_cache (ticker, cusip, accession_number, resolved_at)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(ticker) DO UPDATE SET cusip=excluded.cusip,
               accession_number=excluded.accession_number, resolved_at=excluded.resolved_at""",
            (ticker, cusip, accession_number, _now()),
        )


def record_issuer_spread(conn: sqlite3.Connection, *, ticker: str, spread_value: float) -> None:
    today = _today()  # one row per ticker per day, local calendar date -- see _today()'s docstring
    with conn:
        conn.execute(
            """INSERT INTO signals_issuer_spread_history (ticker, spread_value, observed_at)
               VALUES (?, ?, ?)
               ON CONFLICT(ticker, observed_at) DO UPDATE SET spread_value=excluded.spread_value""",
            (ticker, spread_value, today),
        )


def get_issuer_spread_near(
    conn: sqlite3.Connection, ticker: str, target_date, tolerance_days: int
) -> sqlite3.Row | None:
    """Closest row to target_date within tolerance_days -- same nearest-match-with-
    tolerance philosophy as mytrader margin_debt.py's _find_prior_year_row, adapted to
    query the DB directly instead of an in-memory series."""
    from datetime import date as _date

    rows = conn.execute(
        "SELECT * FROM signals_issuer_spread_history WHERE ticker = ? ORDER BY observed_at", (ticker,)
    ).fetchall()
    best, best_diff = None, None
    for row in rows:
        row_date = _date.fromisoformat(row["observed_at"])
        diff = abs((row_date - target_date).days)
        if best_diff is None or diff < best_diff:
            best, best_diff = row, diff
    if best is None or best_diff > tolerance_days:
        return None
    return best


def record_putcall_ratio(conn: sqlite3.Connection, *, ratio: float) -> None:
    today = _today()  # one row per day, local calendar date -- see _today()'s docstring
    with conn:
        conn.execute(
            """INSERT INTO signals_putcall_history (observed_at, ratio) VALUES (?, ?)
               ON CONFLICT(observed_at) DO UPDATE SET ratio=excluded.ratio""",
            (today, ratio),
        )


def get_putcall_history(conn: sqlite3.Connection, since_days: int) -> list[sqlite3.Row]:
    from datetime import date, timedelta

    cutoff = (date.today() - timedelta(days=since_days)).isoformat()
    return conn.execute(
        "SELECT * FROM signals_putcall_history WHERE observed_at >= ? ORDER BY observed_at",
        (cutoff,),
    ).fetchall()


def has_seen_regulator_alert(conn: sqlite3.Connection, guid: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM signals_regulator_alert_seen WHERE guid = ?", (guid,)
    ).fetchone()
    return row is not None


def mark_regulator_alert_seen(conn: sqlite3.Connection, *, guid: str, source: str, title: str) -> None:
    with conn:
        conn.execute(
            """INSERT INTO signals_regulator_alert_seen (guid, source, title, seen_at)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(guid) DO NOTHING""",
            (guid, source, title, _now()),
        )


def get_manual_bond_yield(conn: sqlite3.Connection, ticker: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM signals_manual_bond_yield WHERE ticker = ?", (ticker,)).fetchone()


def set_manual_bond_yield(conn: sqlite3.Connection, *, ticker: str, cusip: str | None, yield_pct: float) -> None:
    with conn:
        conn.execute(
            """INSERT INTO signals_manual_bond_yield (ticker, cusip, yield_pct, entered_at)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(ticker) DO UPDATE SET cusip=excluded.cusip,
               yield_pct=excluded.yield_pct, entered_at=excluded.entered_at""",
            (ticker, cusip, yield_pct, _now()),
        )
