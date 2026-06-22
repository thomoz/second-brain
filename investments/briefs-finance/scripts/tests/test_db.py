"""Tests for db.py — schema, upserts, deduplication."""

from __future__ import annotations

from scripts.db import (
    get_connection,
    init_db,
    upsert_macro_snapshot,
    upsert_outcome,
    upsert_recommendation,
    upsert_report,
    upsert_sector_context,
)


def test_init_db_creates_tables(db_path):
    """init_db creates all required tables."""
    init_db(db_path)
    conn = get_connection(db_path)
    tables = {row[0] for row in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    conn.close()
    expected = {"reports", "recommendations", "outcomes", "sector_context",
                "macro_snapshot", "principles_evaluations", "likelihood_scores"}
    assert expected.issubset(tables)


def test_upsert_report_deduplicates_on_hash(db_conn):
    """Inserting the same content_hash twice returns the same id."""
    with db_conn:
        id1 = upsert_report(db_conn, file_path="a.pdf", content_hash="hash1",
                            report_date="2025-08-30", title="Test")
        id2 = upsert_report(db_conn, file_path="b.pdf", content_hash="hash1",
                            report_date="2025-09-01", title="Test Dup")
    assert id1 == id2


def test_upsert_report_different_hashes(db_conn):
    """Different content hashes get different ids."""
    with db_conn:
        id1 = upsert_report(db_conn, file_path="a.pdf", content_hash="hash_a", title="A")
        id2 = upsert_report(db_conn, file_path="b.pdf", content_hash="hash_b", title="B")
    assert id1 != id2


def test_upsert_recommendation_deduplicates(db_conn, sample_report_id):
    """Same report_id + ticker returns same id on second insert."""
    with db_conn:
        id1 = upsert_recommendation(db_conn, report_id=sample_report_id, ticker="KGC", buy_thesis="Buy gold")
        id2 = upsert_recommendation(db_conn, report_id=sample_report_id, ticker="KGC", buy_thesis="Buy more gold")
    assert id1 == id2


def test_upsert_outcome_stores_returns(db_conn, sample_rec_id):
    """Outcome upsert stores return values correctly."""
    with db_conn:
        upsert_outcome(
            db_conn,
            recommendation_id=sample_rec_id,
            price_at_rec=10.0,
            price_6m=12.0,
            return_6m=20.0,
            vs_sp500_6m=5.0,
        )
    row = db_conn.execute(
        "SELECT return_6m, vs_sp500_6m FROM outcomes WHERE recommendation_id = ?",
        (sample_rec_id,),
    ).fetchone()
    assert row["return_6m"] == 20.0
    assert row["vs_sp500_6m"] == 5.0


def test_upsert_sector_context_stores_etf(db_conn, sample_rec_id):
    """Sector context stores ETF ticker and returns."""
    with db_conn:
        upsert_sector_context(
            db_conn,
            recommendation_id=sample_rec_id,
            sector_etf="GDX",
            etf_price_at_rec=30.0,
            etf_price_6m=33.0,
            etf_return_6m=10.0,
            stock_vs_sector_6m=5.0,
        )
    row = db_conn.execute(
        "SELECT sector_etf, etf_return_6m FROM sector_context WHERE recommendation_id = ?",
        (sample_rec_id,),
    ).fetchone()
    assert row["sector_etf"] == "GDX"
    assert row["etf_return_6m"] == 10.0


def test_upsert_macro_snapshot_stores_rates(db_conn, sample_report_id):
    """Macro snapshot stores treasury yield and VIX."""
    with db_conn:
        upsert_macro_snapshot(
            db_conn,
            report_id=sample_report_id,
            snapshot_date="2025-08-30",
            treasury_10y=4.25,
            vix=18.5,
            gold_price=1920.0,
        )
    row = db_conn.execute(
        "SELECT treasury_10y, vix FROM macro_snapshot WHERE report_id = ?",
        (sample_report_id,),
    ).fetchone()
    assert row["treasury_10y"] == 4.25
    assert row["vix"] == 18.5
