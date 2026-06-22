"""SQLite schema + CRUD for Briefs Finance investment database."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import DATA_DIR, DB_PATH


def get_connection(db_path: Path = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(db_path: Path = DB_PATH) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = get_connection(db_path)
    with conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS reports (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path       TEXT NOT NULL,
                content_hash    TEXT NOT NULL UNIQUE,
                report_date     TEXT,
                report_type     TEXT,
                series          TEXT,
                title           TEXT,
                inferred_sector TEXT,
                raw_text        TEXT,
                ingested_at     TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS recommendations (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                report_id         INTEGER NOT NULL REFERENCES reports(id),
                ticker            TEXT NOT NULL,
                company_name      TEXT,
                buy_thesis        TEXT,
                exit_trigger      TEXT,
                excluded          INTEGER NOT NULL DEFAULT 0,
                exclusion_reason  TEXT,
                extracted_at      TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS outcomes (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                recommendation_id   INTEGER NOT NULL UNIQUE REFERENCES recommendations(id),
                price_at_rec        REAL,
                price_3m            REAL,
                price_6m            REAL,
                price_12m           REAL,
                sp500_at_rec        REAL,
                sp500_3m            REAL,
                sp500_6m            REAL,
                sp500_12m           REAL,
                return_3m           REAL,
                return_6m           REAL,
                return_12m          REAL,
                vs_sp500_3m         REAL,
                vs_sp500_6m         REAL,
                vs_sp500_12m        REAL,
                fetched_at          TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS sector_context (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                recommendation_id   INTEGER NOT NULL UNIQUE REFERENCES recommendations(id),
                sector_etf          TEXT,
                etf_price_at_rec    REAL,
                etf_price_3m        REAL,
                etf_price_6m        REAL,
                etf_price_12m       REAL,
                etf_return_3m       REAL,
                etf_return_6m       REAL,
                etf_return_12m      REAL,
                stock_vs_sector_3m  REAL,
                stock_vs_sector_6m  REAL,
                stock_vs_sector_12m REAL,
                fetched_at          TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS macro_snapshot (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                report_id       INTEGER NOT NULL UNIQUE REFERENCES reports(id),
                snapshot_date   TEXT,
                treasury_10y    REAL,
                tbill_3m        REAL,
                vix             REAL,
                gold_price      REAL,
                usd_strength    REAL,
                bonds_20y       REAL,
                yield_curve     REAL,
                recession_prob  REAL,
                cpi_yoy         REAL,
                fed_funds       REAL,
                fetched_at      TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS principles_evaluations (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                recommendation_id INTEGER NOT NULL REFERENCES recommendations(id),
                principle         TEXT NOT NULL,
                score             INTEGER NOT NULL,
                reasoning         TEXT,
                scored_at         TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS likelihood_scores (
                id                      INTEGER PRIMARY KEY AUTOINCREMENT,
                recommendation_id       INTEGER NOT NULL UNIQUE REFERENCES recommendations(id),
                score                   INTEGER NOT NULL,
                base_rate               REAL,
                sector_rate             REAL,
                ticker_history          REAL,
                principles              REAL,
                macro                   REAL,
                sector_context          REAL,
                breakdown_json          TEXT,
                provisional             INTEGER NOT NULL DEFAULT 0,
                computed_at             TEXT NOT NULL
            );
        """)
    conn.close()


def _now() -> str:
    return datetime.utcnow().isoformat()


def upsert_report(
    conn: sqlite3.Connection,
    *,
    file_path: str,
    content_hash: str,
    report_date: str | None = None,
    report_type: str | None = None,
    series: str | None = None,
    title: str | None = None,
    inferred_sector: str | None = None,
    raw_text: str | None = None,
) -> int:
    """Insert or update a report by content_hash. Returns report id."""
    existing = conn.execute(
        "SELECT id FROM reports WHERE content_hash = ?", (content_hash,)
    ).fetchone()
    if existing:
        return existing["id"]
    cur = conn.execute(
        """INSERT INTO reports
           (file_path, content_hash, report_date, report_type, series, title,
            inferred_sector, raw_text, ingested_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (file_path, content_hash, report_date, report_type, series, title,
         inferred_sector, raw_text, _now()),
    )
    return cur.lastrowid  # type: ignore[return-value]


def upsert_recommendation(
    conn: sqlite3.Connection,
    *,
    report_id: int,
    ticker: str,
    company_name: str | None = None,
    buy_thesis: str | None = None,
    exit_trigger: str | None = None,
    excluded: bool = False,
    exclusion_reason: str | None = None,
) -> int:
    """Insert recommendation. Returns new id (no update — recommendations are immutable)."""
    existing = conn.execute(
        "SELECT id FROM recommendations WHERE report_id = ? AND ticker = ?",
        (report_id, ticker),
    ).fetchone()
    if existing:
        return existing["id"]
    cur = conn.execute(
        """INSERT INTO recommendations
           (report_id, ticker, company_name, buy_thesis, exit_trigger,
            excluded, exclusion_reason, extracted_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (report_id, ticker, company_name, buy_thesis, exit_trigger,
         int(excluded), exclusion_reason, _now()),
    )
    return cur.lastrowid  # type: ignore[return-value]


def upsert_outcome(conn: sqlite3.Connection, *, recommendation_id: int, **kwargs: Any) -> None:
    fields = [
        "price_at_rec", "price_3m", "price_6m", "price_12m",
        "sp500_at_rec", "sp500_3m", "sp500_6m", "sp500_12m",
        "return_3m", "return_6m", "return_12m",
        "vs_sp500_3m", "vs_sp500_6m", "vs_sp500_12m",
    ]
    values = {f: kwargs.get(f) for f in fields}
    conn.execute(
        f"""INSERT OR REPLACE INTO outcomes
            (recommendation_id, {', '.join(fields)}, fetched_at)
            VALUES (?, {', '.join('?' for _ in fields)}, ?)""",
        [recommendation_id, *[values[f] for f in fields], _now()],
    )


def upsert_sector_context(conn: sqlite3.Connection, *, recommendation_id: int, **kwargs: Any) -> None:
    fields = [
        "sector_etf",
        "etf_price_at_rec", "etf_price_3m", "etf_price_6m", "etf_price_12m",
        "etf_return_3m", "etf_return_6m", "etf_return_12m",
        "stock_vs_sector_3m", "stock_vs_sector_6m", "stock_vs_sector_12m",
    ]
    values = {f: kwargs.get(f) for f in fields}
    conn.execute(
        f"""INSERT OR REPLACE INTO sector_context
            (recommendation_id, {', '.join(fields)}, fetched_at)
            VALUES (?, {', '.join('?' for _ in fields)}, ?)""",
        [recommendation_id, *[values[f] for f in fields], _now()],
    )


def upsert_macro_snapshot(conn: sqlite3.Connection, *, report_id: int, **kwargs: Any) -> None:
    fields = [
        "snapshot_date",
        "treasury_10y", "tbill_3m", "vix", "gold_price", "usd_strength", "bonds_20y",
        "yield_curve", "recession_prob", "cpi_yoy", "fed_funds",
    ]
    values = {f: kwargs.get(f) for f in fields}
    conn.execute(
        f"""INSERT OR REPLACE INTO macro_snapshot
            (report_id, {', '.join(fields)}, fetched_at)
            VALUES (?, {', '.join('?' for _ in fields)}, ?)""",
        [report_id, *[values[f] for f in fields], _now()],
    )


def get_all_outcomes(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("""
        SELECT o.*, r.ticker, r.report_id, rep.inferred_sector, rep.report_date
        FROM outcomes o
        JOIN recommendations r ON r.id = o.recommendation_id
        JOIN reports rep ON rep.id = r.report_id
        WHERE r.excluded = 0
    """).fetchall()


def get_ticker_outcomes(conn: sqlite3.Connection, ticker: str) -> list[sqlite3.Row]:
    return conn.execute("""
        SELECT o.*, r.ticker, r.report_id, rep.inferred_sector, rep.report_date
        FROM outcomes o
        JOIN recommendations r ON r.id = o.recommendation_id
        JOIN reports rep ON rep.id = r.report_id
        WHERE r.ticker = ? AND r.excluded = 0
    """, (ticker.upper(),)).fetchall()


def get_sector_outcomes(conn: sqlite3.Connection, etf: str) -> list[sqlite3.Row]:
    return conn.execute("""
        SELECT o.*, sc.sector_etf, r.ticker
        FROM outcomes o
        JOIN recommendations r ON r.id = o.recommendation_id
        JOIN sector_context sc ON sc.recommendation_id = r.id
        WHERE sc.sector_etf = ? AND r.excluded = 0
    """, (etf.upper(),)).fetchall()
