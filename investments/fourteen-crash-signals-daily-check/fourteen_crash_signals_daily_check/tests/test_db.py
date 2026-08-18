from __future__ import annotations

from fourteen_crash_signals_daily_check import db


def test_replace_and_get_hot_watchlist(db_conn):
    db.replace_hot_watchlist(db_conn, [
        {"ticker": "NVDA", "sector_label": "Technology", "market_cap": 5e12, "rank": 1},
        {"ticker": "MSFT", "sector_label": "Technology", "market_cap": 3e12, "rank": 2},
    ])
    rows = db.get_hot_watchlist(db_conn)
    assert [r["ticker"] for r in rows] == ["NVDA", "MSFT"]


def test_replace_hot_watchlist_clears_prior_rows(db_conn):
    db.replace_hot_watchlist(db_conn, [{"ticker": "NVDA", "sector_label": "Technology", "market_cap": 5e12, "rank": 1}])
    db.replace_hot_watchlist(db_conn, [{"ticker": "ORCL", "sector_label": "Technology", "market_cap": 1e12, "rank": 1}])
    rows = db.get_hot_watchlist(db_conn)
    assert [r["ticker"] for r in rows] == ["ORCL"]


def test_upsert_signal_state_true_only_on_absent_to_firing_transition(db_conn):
    assert db.upsert_signal_state(db_conn, marker_key="m1", is_firing=True, detail="first fire") is True


def test_upsert_signal_state_false_on_repeat_firing(db_conn):
    db.upsert_signal_state(db_conn, marker_key="m1", is_firing=True, detail="first fire")
    assert db.upsert_signal_state(db_conn, marker_key="m1", is_firing=True, detail="still firing") is False


def test_upsert_signal_state_false_when_staying_not_firing(db_conn):
    assert db.upsert_signal_state(db_conn, marker_key="m1", is_firing=False, detail="ok") is False
    assert db.upsert_signal_state(db_conn, marker_key="m1", is_firing=False, detail="still ok") is False


def test_upsert_signal_state_refires_after_returning_to_not_firing(db_conn):
    db.upsert_signal_state(db_conn, marker_key="m1", is_firing=True, detail="fire")
    db.upsert_signal_state(db_conn, marker_key="m1", is_firing=False, detail="resolved")
    assert db.upsert_signal_state(db_conn, marker_key="m1", is_firing=True, detail="fire again") is True


def test_get_all_signal_states_orders_by_marker_key(db_conn):
    db.upsert_signal_state(db_conn, marker_key="zzz", is_firing=True, detail="z")
    db.upsert_signal_state(db_conn, marker_key="aaa", is_firing=True, detail="a")
    rows = db.get_all_signal_states(db_conn)
    assert [r["marker_key"] for r in rows] == ["aaa", "zzz"]
