from __future__ import annotations

from volume_earnings_scanner import db


def test_insert_pending_candidate_new_vs_duplicate(db_conn):
    inserted = db.insert_ve_pending_candidate(
        db_conn, ticker="ABCD", signal_type="volume", signal_detail="spike", company_name="ABCD Inc",
    )
    assert inserted is True

    duplicate = db.insert_ve_pending_candidate(
        db_conn, ticker="ABCD", signal_type="earnings", signal_detail="different detail",
    )
    assert duplicate is False  # append-only -- never upgrades an existing row

    row = db.get_ve_pending_candidate(db_conn, "ABCD")
    assert row["signal_type"] == "volume"  # original value preserved


def test_get_all_and_delete_pending_candidate(db_conn):
    db.insert_ve_pending_candidate(db_conn, ticker="AAA", signal_type="volume", signal_detail="d1")
    db.insert_ve_pending_candidate(db_conn, ticker="BBB", signal_type="both", signal_detail="d2")

    all_rows = db.get_all_ve_pending_candidates(db_conn)
    assert {r["ticker"] for r in all_rows} == {"AAA", "BBB"}

    deleted = db.delete_ve_pending_candidate(db_conn, "AAA")
    assert deleted == 1
    assert db.get_ve_pending_candidate(db_conn, "AAA") is None


def test_universe_cache_roundtrip(db_conn):
    assert db.get_universe_cache_fetched_at(db_conn) is None

    db.replace_universe_cache(db_conn, [
        {"ticker": "XYZ", "company": "XYZ Corp", "market_cap_text": "100.00M"},
    ])
    rows = db.get_universe_cache(db_conn)
    assert len(rows) == 1
    assert rows[0]["ticker"] == "XYZ"
    assert db.get_universe_cache_fetched_at(db_conn) is not None


def test_replace_universe_cache_drops_stale_rows(db_conn):
    db.replace_universe_cache(db_conn, [{"ticker": "OLD", "company": "", "market_cap_text": ""}])
    db.replace_universe_cache(db_conn, [{"ticker": "NEW", "company": "", "market_cap_text": ""}])
    rows = db.get_universe_cache(db_conn)
    assert {r["ticker"] for r in rows} == {"NEW"}
