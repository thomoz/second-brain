from __future__ import annotations

from goat import db


def test_get_open_goat_alert_returns_none_when_no_alert(db_conn):
    assert db.get_open_goat_alert(db_conn, "AAPL", "holdings", "below_150dma") is None


def test_insert_goat_alert_then_get_open_goat_alert_finds_it(db_conn):
    db.insert_goat_alert(
        db_conn, ticker="AAPL", source_table="holdings",
        check_name="below_150dma", severity="flag", message="AAPL closed 8.0% below its 150-day MA",
    )
    row = db.get_open_goat_alert(db_conn, "AAPL", "holdings", "below_150dma")
    assert row is not None
    assert row["ticker"] == "AAPL"
    assert row["acknowledged"] == 0


def test_acknowledge_goat_alert_removes_it_from_open_query(db_conn):
    db.insert_goat_alert(
        db_conn, ticker="AAPL", source_table="holdings",
        check_name="below_150dma", severity="flag", message="AAPL closed 8.0% below its 150-day MA",
    )
    alert = db.get_open_goat_alert(db_conn, "AAPL", "holdings", "below_150dma")
    db.acknowledge_goat_alert(db_conn, alert["id"])
    assert db.get_open_goat_alert(db_conn, "AAPL", "holdings", "below_150dma") is None
    assert db.get_open_goat_alerts(db_conn) == []


def test_get_open_goat_alerts_lists_all_unacknowledged_across_tickers(db_conn):
    db.insert_goat_alert(
        db_conn, ticker="AAPL", source_table="holdings",
        check_name="below_150dma", severity="flag", message="AAPL flagged",
    )
    db.insert_goat_alert(
        db_conn, ticker="MSFT", source_table="holdings",
        check_name="below_150dma", severity="flag", message="MSFT flagged",
    )
    open_alerts = db.get_open_goat_alerts(db_conn)
    assert {a["ticker"] for a in open_alerts} == {"AAPL", "MSFT"}
