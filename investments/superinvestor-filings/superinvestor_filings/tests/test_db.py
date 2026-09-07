from __future__ import annotations

from superinvestor_filings import db


def _insert(conn, **overrides):
    kwargs = dict(
        dedup_key="edgar|pabrai|SC 13G|RAIN|acc-1", source="edgar", filer_key="pabrai",
        filer_display="Mohnish Pabrai / Dalal Street", form_type="SC 13G", issuer="RAIN",
    )
    kwargs.update(overrides)
    return db.insert_superinvestor_filing_seen(conn, **kwargs)


def test_init_tables_is_idempotent(db_conn):
    db.init_superinvestor_tables(db_conn)
    db.init_superinvestor_tables(db_conn)  # must not raise
    assert db.count_seen(db_conn) == 0


def test_insert_returns_true_first_time_false_on_duplicate(db_conn):
    assert _insert(db_conn) is True
    assert _insert(db_conn) is False
    assert db.count_seen(db_conn) == 1


def test_get_last_pct_owned_returns_most_recent(db_conn):
    _insert(db_conn, dedup_key="k1", pct_owned=5.2)
    _insert(db_conn, dedup_key="k2", pct_owned=6.4)
    assert db.get_last_pct_owned(db_conn, "pabrai", "RAIN") == 6.4


def test_get_last_pct_owned_none_when_no_prior_or_no_pct(db_conn):
    assert db.get_last_pct_owned(db_conn, "pabrai", "RAIN") is None
    _insert(db_conn, dedup_key="k3", pct_owned=None)
    assert db.get_last_pct_owned(db_conn, "pabrai", "RAIN") is None


def test_get_recent_filters_by_source(db_conn):
    _insert(db_conn, dedup_key="e1", source="edgar")
    _insert(db_conn, dedup_key="s1", source="sast")
    assert len(db.get_recent_superinvestor_filings_seen(db_conn, source="edgar")) == 1
    assert len(db.get_recent_superinvestor_filings_seen(db_conn)) == 2
