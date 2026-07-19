from __future__ import annotations

from mytrader import db


def test_upsert_holding_inserts_new_row(db_conn):
    db.upsert_holding(
        db_conn, ticker="V", name="Visa Inc", asset_type="stock", bucket="1",
        qty=0.1001, avg_price=318.41, currency="USD",
    )
    row = db.get_holding_row(db_conn, "V", "1")
    assert row is not None
    assert row["qty"] == 0.1001
    assert row["avg_price"] == 318.41


def test_upsert_holding_updates_existing_row(db_conn):
    db.upsert_holding(
        db_conn, ticker="V", name="Visa Inc", asset_type="stock", bucket="1",
        qty=0.1, avg_price=300.0,
    )
    db.upsert_holding(
        db_conn, ticker="V", name="Visa Inc", asset_type="stock", bucket="1",
        qty=0.2, avg_price=320.0,
    )
    rows = db.get_all_holdings(db_conn)
    assert len(rows) == 1
    assert rows[0]["qty"] == 0.2
    assert rows[0]["avg_price"] == 320.0


def test_same_ticker_different_bucket_allowed(db_conn):
    db.upsert_holding(
        db_conn, ticker="PMGOLD", name="Perth Mint Gold", asset_type="etf", bucket="3a",
        qty=10.0, avg_price=57.56,
    )
    db.upsert_holding(
        db_conn, ticker="PMGOLD", name="Perth Mint Gold", asset_type="etf", bucket="3b",
        qty=5.0, avg_price=57.56,
    )
    rows = db.get_all_holdings(db_conn)
    assert len(rows) == 2
    buckets = {row["bucket"] for row in rows}
    assert buckets == {"3a", "3b"}


def test_delete_holding_if_zero_removes_row(db_conn):
    db.upsert_holding(
        db_conn, ticker="V", name="Visa Inc", asset_type="stock", bucket="1",
        qty=0.0000001, avg_price=320.0,
    )
    db.delete_holding_if_zero(db_conn, "V", "1")
    assert db.get_holding_row(db_conn, "V", "1") is None


def test_delete_holding_if_zero_keeps_nonzero_row(db_conn):
    db.upsert_holding(
        db_conn, ticker="V", name="Visa Inc", asset_type="stock", bucket="1",
        qty=0.5, avg_price=320.0,
    )
    db.delete_holding_if_zero(db_conn, "V", "1")
    assert db.get_holding_row(db_conn, "V", "1") is not None


def test_upsert_watchlist_row_defaults_to_raw_status(db_conn):
    db.upsert_watchlist_row(
        db_conn, ticker="VRTX", name="Vertex Pharmaceuticals", asset_type="stock", bucket="1",
    )
    row = db.get_watchlist_row(db_conn, "VRTX", "1")
    assert row["status"] == "raw"
    assert row["source"] == "manual"


def test_upsert_watchlist_row_upserts_by_natural_key(db_conn):
    db.upsert_watchlist_row(
        db_conn, ticker="VRTX", name="Vertex Pharmaceuticals", asset_type="stock", bucket="1",
        status="discussed",
    )
    db.upsert_watchlist_row(
        db_conn, ticker="VRTX", name="Vertex Pharmaceuticals", asset_type="stock", bucket="1",
        status="discussed", notes="updated notes",
    )
    rows = db.get_all_watchlist(db_conn)
    assert len(rows) == 1
    assert rows[0]["notes"] == "updated notes"


def test_get_open_alert_returns_none_when_no_alert(db_conn):
    assert db.get_open_alert(db_conn, "VRTX", "holdings", "dividend") is None


def test_insert_alert_then_get_open_alert_finds_it(db_conn):
    db.insert_alert(
        db_conn, ticker="VRTX", source_table="holdings", check_name="dividend",
        severity="flag", message="Dividend cut detected",
    )
    row = db.get_open_alert(db_conn, "VRTX", "holdings", "dividend")
    assert row is not None
    assert row["message"] == "Dividend cut detected"
    assert row["acknowledged"] == 0


def test_acknowledge_alert_removes_it_from_open_query(db_conn):
    db.insert_alert(
        db_conn, ticker="VRTX", source_table="holdings", check_name="dividend",
        severity="flag", message="Dividend cut detected",
    )
    alert = db.get_open_alert(db_conn, "VRTX", "holdings", "dividend")
    db.acknowledge_alert(db_conn, alert["id"])
    assert db.get_open_alert(db_conn, "VRTX", "holdings", "dividend") is None
    assert db.get_open_alerts(db_conn) == []


def test_touch_checked_updates_holdings_row(db_conn):
    db.upsert_holding(
        db_conn, ticker="V", name="Visa Inc", asset_type="stock", bucket="1",
        qty=0.1, avg_price=318.41,
    )
    db.touch_checked(db_conn, "holdings", "V", "1", 0.05)
    row = db.get_holding_row(db_conn, "V", "1")
    assert row["last_checked_at"] is not None
    assert row["last_expense_ratio"] == 0.05


def test_touch_checked_updates_watchlist_row(db_conn):
    db.upsert_watchlist_row(
        db_conn, ticker="VRTX", name="Vertex Pharmaceuticals", asset_type="stock", bucket="1",
        status="discussed",
    )
    db.touch_checked(db_conn, "watchlist", "VRTX", "1", 0.03)
    row = db.get_watchlist_row(db_conn, "VRTX", "1")
    assert row["last_checked_at"] is not None
    assert row["last_expense_ratio"] == 0.03


def test_touch_checked_preserves_expense_ratio_when_none_passed(db_conn):
    db.upsert_holding(
        db_conn, ticker="V", name="Visa Inc", asset_type="stock", bucket="1",
        qty=0.1, avg_price=318.41, last_expense_ratio=0.09,
    )
    db.touch_checked(db_conn, "holdings", "V", "1", None)
    row = db.get_holding_row(db_conn, "V", "1")
    assert row["last_checked_at"] is not None
    assert row["last_expense_ratio"] == 0.09
