from __future__ import annotations

import json

from ai_resistant_moat_scanner import db


def _stage(conn, ticker, moat):
    return db.insert_moat_pending_candidate(
        conn, ticker=ticker, industry="Software - Application", moat_score=moat,
        quant_score=moat - 5, qualitative_score=moat + 5, thesis="t", sub_scores_json="{}",
    )


def test_init_moat_tables_is_idempotent(db_conn):
    db.init_moat_tables(db_conn)
    db.init_moat_tables(db_conn)  # no error


def test_pending_candidate_insert_dedup(db_conn):
    assert _stage(db_conn, "CRM", 88.0) is True
    assert _stage(db_conn, "CRM", 90.0) is False  # already staged
    assert len(db.get_all_moat_pending_candidates(db_conn)) == 1


def test_get_all_pending_ordered_by_moat_score_desc(db_conn):
    _stage(db_conn, "AAA", 70.0)
    _stage(db_conn, "BBB", 95.0)
    _stage(db_conn, "CCC", 82.0)
    tickers = [r["ticker"] for r in db.get_all_moat_pending_candidates(db_conn)]
    assert tickers == ["BBB", "CCC", "AAA"]


def test_delete_pending_returns_count(db_conn):
    _stage(db_conn, "CRM", 88.0)
    assert db.delete_moat_pending_candidate(db_conn, "CRM") == 1
    assert db.delete_moat_pending_candidate(db_conn, "CRM") == 0


def test_qualitative_cache_roundtrip_keyed_by_rubric_version(db_conn):
    db.upsert_qualitative_cache(
        db_conn, ticker="CRM", accession_number="0001-25-000001", rubric_version="2026-09",
        extraction_json=json.dumps({"nrr_pct": 112}), rubric_json=json.dumps({"thesis": "x"}),
        thesis="x",
    )
    hit = db.get_cached_qualitative(db_conn, "CRM", "0001-25-000001", "2026-09")
    assert hit is not None
    assert json.loads(hit["extraction_json"])["nrr_pct"] == 112

    # Different rubric_version -> cache miss.
    assert db.get_cached_qualitative(db_conn, "CRM", "0001-25-000001", "2027-01") is None


def test_qualitative_cache_upsert_replaces(db_conn):
    for thesis in ("first", "second"):
        db.upsert_qualitative_cache(
            db_conn, ticker="CRM", accession_number="acc", rubric_version="2026-09",
            extraction_json="{}", rubric_json="{}", thesis=thesis,
        )
    assert db.get_cached_qualitative(db_conn, "CRM", "acc", "2026-09")["thesis"] == "second"


def test_universe_cache_replace_and_stale_fallback(db_conn):
    db.replace_universe_cache(db_conn, [
        {"ticker": "CRM", "company": "Salesforce", "industry": "Software - Application", "sector": "Technology"},
    ])
    assert db.get_universe_cache_fetched_at(db_conn) is not None
    rows = db.get_universe_cache(db_conn)
    assert [r["ticker"] for r in rows] == ["CRM"]

    db.replace_universe_cache(db_conn, [
        {"ticker": "NOW", "company": "ServiceNow", "industry": "Software - Application", "sector": "Technology"},
    ])
    assert [r["ticker"] for r in db.get_universe_cache(db_conn)] == ["NOW"]  # full replace
