from __future__ import annotations

from scripts.db import upsert_recommendation, upsert_report

from mytrader import candidate_sync, db


def _seed_report(conn, content_hash="hash1") -> int:
    return upsert_report(
        conn, file_path="report.pdf", content_hash=content_hash, report_date="2026-07-19",
    )


def _seed_recommendation(
    conn, report_id, ticker="NVDA", company_name="NVIDIA Corp",
    buy_thesis="AI chip demand", excluded=False,
) -> int:
    return upsert_recommendation(
        conn, report_id=report_id, ticker=ticker, company_name=company_name,
        buy_thesis=buy_thesis, excluded=excluded,
    )


def test_sync_new_candidates_inserts_new_watchlist_row(db_conn):
    report_id = _seed_report(db_conn)
    _seed_recommendation(db_conn, report_id)

    added = candidate_sync.sync_new_candidates(db_conn)

    assert len(added) == 1
    assert added[0]["ticker"] == "NVDA"
    row = db.get_watchlist_row(db_conn, "NVDA")
    assert row is not None
    assert row["status"] == "raw"
    assert row["source"] == "briefs_finance_ingest"
    assert row["bucket"] == "unassigned"


def test_sync_new_candidates_skips_excluded_recommendations(db_conn):
    report_id = _seed_report(db_conn)
    _seed_recommendation(db_conn, report_id, ticker="LMT", excluded=True)

    added = candidate_sync.sync_new_candidates(db_conn)

    assert added == []
    assert db.get_watchlist_row(db_conn, "LMT") is None


def test_sync_new_candidates_skips_ticker_already_in_holdings(db_conn):
    db.upsert_holding(
        db_conn, ticker="NVDA", name="NVIDIA Corp", asset_type="stock", bucket="1",
        qty=1.0, avg_price=100.0,
    )
    report_id = _seed_report(db_conn)
    _seed_recommendation(db_conn, report_id)

    added = candidate_sync.sync_new_candidates(db_conn)

    assert added == []
    assert db.get_watchlist_row(db_conn, "NVDA") is None


def test_sync_new_candidates_skips_ticker_already_in_watchlist(db_conn):
    db.upsert_watchlist_row(
        db_conn, ticker="NVDA", name="NVIDIA Corp", asset_type="stock", bucket="2",
        status="discussed",
    )
    report_id = _seed_report(db_conn)
    _seed_recommendation(db_conn, report_id)

    added = candidate_sync.sync_new_candidates(db_conn)

    assert added == []


def test_sync_new_candidates_advances_watermark_and_does_not_reprocess(db_conn):
    report_id = _seed_report(db_conn)
    _seed_recommendation(db_conn, report_id)

    candidate_sync.sync_new_candidates(db_conn)
    second = candidate_sync.sync_new_candidates(db_conn)

    assert second == []


def test_sync_new_candidates_only_processes_rows_after_watermark(db_conn):
    report_id = _seed_report(db_conn)
    _seed_recommendation(db_conn, report_id, ticker="NVDA", company_name="NVIDIA Corp")
    _seed_recommendation(db_conn, report_id, ticker="AAPL", company_name="Apple Inc")

    candidate_sync.sync_new_candidates(db_conn)

    _seed_recommendation(db_conn, report_id, ticker="MSFT", company_name="Microsoft Corp")
    second = candidate_sync.sync_new_candidates(db_conn)

    assert len(second) == 1
    assert second[0]["ticker"] == "MSFT"


def test_sync_new_candidates_uses_empty_notes_when_buy_thesis_is_none(db_conn):
    report_id = _seed_report(db_conn)
    _seed_recommendation(db_conn, report_id, buy_thesis=None)

    candidate_sync.sync_new_candidates(db_conn)

    row = db.get_watchlist_row(db_conn, "NVDA")
    assert row["notes"] == ""
