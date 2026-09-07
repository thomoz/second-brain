from __future__ import annotations

from superinvestor_filings import sast_monitor


def test_scan_india_is_a_safe_noop_until_phase5(db_conn):
    result = sast_monitor.scan_india(db_conn)
    assert result == {"new_filings": [], "recent_filings": []}


def test_fetch_sast_disclosures_returns_none_until_feed_confirmed():
    assert sast_monitor.fetch_sast_disclosures("2026-09-07") is None
