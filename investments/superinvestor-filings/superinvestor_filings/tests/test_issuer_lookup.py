from __future__ import annotations

from mytrader.db import upsert_cik_map_bulk

from superinvestor_filings import issuer_lookup


def test_hint_wins_over_lookup(db_conn):
    upsert_cik_map_bulk(db_conn, {"WRONG": "12345"})
    assert issuer_lookup.resolve_ticker(db_conn, "12345", "amr") == "AMR"


def test_falls_back_to_cik_map(db_conn):
    upsert_cik_map_bulk(db_conn, {"AMR": "1301063"})
    assert issuer_lookup.resolve_ticker(db_conn, "0001301063", None) == "AMR"


def test_none_when_absent(db_conn):
    assert issuer_lookup.resolve_ticker(db_conn, "9999999", None) is None
    assert issuer_lookup.resolve_ticker(db_conn, None, None) is None
