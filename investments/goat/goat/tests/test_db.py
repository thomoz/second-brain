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


def test_get_goat_pending_candidate_returns_none_when_absent(db_conn):
    assert db.get_goat_pending_candidate(db_conn, "XLK") is None


def test_insert_goat_pending_candidate_then_get_finds_it(db_conn):
    db.insert_goat_pending_candidate(
        db_conn, ticker="XLK", sector_label="Technology",
        signal_detail="XLK crossed above its 50-day MA 3 trading day(s) ago",
    )
    row = db.get_goat_pending_candidate(db_conn, "XLK")
    assert row is not None
    assert row["sector_label"] == "Technology"
    assert row["source"] == "goat_sector_rotation"


def test_insert_goat_pending_candidate_twice_is_a_no_op(db_conn):
    db.insert_goat_pending_candidate(
        db_conn, ticker="XLK", sector_label="Technology", signal_detail="first detail",
    )
    db.insert_goat_pending_candidate(
        db_conn, ticker="XLK", sector_label="Technology", signal_detail="second detail",
    )
    rows = db.get_all_goat_pending_candidates(db_conn)
    assert len(rows) == 1
    assert rows[0]["signal_detail"] == "first detail"


def test_delete_goat_pending_candidate_removes_it(db_conn):
    db.insert_goat_pending_candidate(
        db_conn, ticker="XLK", sector_label="Technology", signal_detail="detail",
    )
    count = db.delete_goat_pending_candidate(db_conn, "XLK")
    assert count == 1
    assert db.get_goat_pending_candidate(db_conn, "XLK") is None


def test_get_all_goat_pending_candidates_lists_ticker_sorted(db_conn):
    db.insert_goat_pending_candidate(db_conn, ticker="XLV", sector_label="Health Care", signal_detail="d")
    db.insert_goat_pending_candidate(db_conn, ticker="XLK", sector_label="Technology", signal_detail="d")
    rows = db.get_all_goat_pending_candidates(db_conn)
    assert [r["ticker"] for r in rows] == ["XLK", "XLV"]


def test_insert_goat_insider_filing_seen_returns_true_on_first_insert(db_conn):
    result = db.insert_goat_insider_filing_seen(
        db_conn, dedup_key="AAPL|2026-08-15|2026-08-14|Jane Doe|P|150000.00",
        ticker="AAPL", filing_date="2026-08-15", trade_date="2026-08-14",
        insider_name="Jane Doe", trade_type="P", value=150000.0, kind="holdings_watch",
    )
    assert result is True


def test_insert_goat_insider_filing_seen_returns_false_on_duplicate_dedup_key(db_conn):
    kwargs = dict(
        dedup_key="AAPL|2026-08-15|2026-08-14|Jane Doe|P|150000.00",
        ticker="AAPL", filing_date="2026-08-15", trade_date="2026-08-14",
        insider_name="Jane Doe", trade_type="P", value=150000.0, kind="holdings_watch",
    )
    db.insert_goat_insider_filing_seen(db_conn, **kwargs)
    result = db.insert_goat_insider_filing_seen(db_conn, **kwargs)
    assert result is False


def test_get_recent_insider_filings_seen_filters_by_kind(db_conn):
    db.insert_goat_insider_filing_seen(
        db_conn, dedup_key="k1", ticker="AAPL", filing_date="2026-08-15", trade_date="2026-08-14",
        insider_name="Jane Doe", trade_type="P", value=150000.0, kind="holdings_watch",
    )
    db.insert_goat_insider_filing_seen(
        db_conn, dedup_key="k2", ticker="MSFT", filing_date="2026-08-15", trade_date="2026-08-14",
        insider_name="John Smith", trade_type="P", value=30000.0, kind="discovery",
    )
    rows = db.get_recent_insider_filings_seen(db_conn, kind="discovery")
    assert len(rows) == 1
    assert rows[0]["ticker"] == "MSFT"


def test_get_recent_insider_filings_seen_orders_newest_first(db_conn):
    db.insert_goat_insider_filing_seen(
        db_conn, dedup_key="k1", ticker="AAPL", filing_date="2026-08-15", trade_date="2026-08-14",
        insider_name="Jane Doe", trade_type="P", value=150000.0, kind="holdings_watch",
    )
    db.insert_goat_insider_filing_seen(
        db_conn, dedup_key="k2", ticker="MSFT", filing_date="2026-08-15", trade_date="2026-08-14",
        insider_name="John Smith", trade_type="P", value=30000.0, kind="holdings_watch",
    )
    rows = db.get_recent_insider_filings_seen(db_conn)
    assert rows[0]["ticker"] == "MSFT"
    assert rows[1]["ticker"] == "AAPL"


def test_insert_goat_insider_filing_seen_stores_pct_owned_change(db_conn):
    db.insert_goat_insider_filing_seen(
        db_conn, dedup_key="k1", ticker="AAPL", filing_date="2026-08-15", trade_date="2026-08-14",
        insider_name="Jane Doe", trade_type="S", value=150000.0, kind="holdings_watch",
        pct_owned_change=-12.5,
    )
    rows = db.get_recent_insider_filings_seen(db_conn)
    assert rows[0]["pct_owned_change"] == -12.5


def test_insert_goat_insider_filing_seen_defaults_pct_owned_change_to_none(db_conn):
    db.insert_goat_insider_filing_seen(
        db_conn, dedup_key="k1", ticker="AAPL", filing_date="2026-08-15", trade_date="2026-08-14",
        insider_name="Jane Doe", trade_type="P", value=150000.0, kind="holdings_watch",
    )
    rows = db.get_recent_insider_filings_seen(db_conn)
    assert rows[0]["pct_owned_change"] is None


def test_count_insider_sales_since_counts_only_matching_ticker_and_insider(db_conn):
    db.insert_goat_insider_filing_seen(
        db_conn, dedup_key="k1", ticker="AAPL", filing_date="2026-08-01", trade_date="2026-08-01",
        insider_name="Jane Doe", trade_type="S", value=50000.0, kind="holdings_watch",
    )
    db.insert_goat_insider_filing_seen(
        db_conn, dedup_key="k2", ticker="AAPL", filing_date="2026-08-01", trade_date="2026-08-01",
        insider_name="John Smith", trade_type="S", value=50000.0, kind="holdings_watch",
    )
    db.insert_goat_insider_filing_seen(
        db_conn, dedup_key="k3", ticker="MSFT", filing_date="2026-08-01", trade_date="2026-08-01",
        insider_name="Jane Doe", trade_type="S", value=50000.0, kind="holdings_watch",
    )
    count = db.count_insider_sales_since(
        db_conn, ticker="AAPL", insider_name="Jane Doe", start_date="2026-05-01", before_date="2026-08-17",
    )
    assert count == 1


def test_count_insider_sales_since_excludes_filings_outside_window(db_conn):
    db.insert_goat_insider_filing_seen(
        db_conn, dedup_key="k1", ticker="AAPL", filing_date="2026-01-01", trade_date="2026-01-01",
        insider_name="Jane Doe", trade_type="S", value=50000.0, kind="holdings_watch",
    )
    count = db.count_insider_sales_since(
        db_conn, ticker="AAPL", insider_name="Jane Doe", start_date="2026-05-01", before_date="2026-08-17",
    )
    assert count == 0


def test_count_insider_sales_since_excludes_purchases(db_conn):
    db.insert_goat_insider_filing_seen(
        db_conn, dedup_key="k1", ticker="AAPL", filing_date="2026-08-01", trade_date="2026-08-01",
        insider_name="Jane Doe", trade_type="P", value=50000.0, kind="holdings_watch",
    )
    count = db.count_insider_sales_since(
        db_conn, ticker="AAPL", insider_name="Jane Doe", start_date="2026-05-01", before_date="2026-08-17",
    )
    assert count == 0


def test_init_goat_tables_migration_is_idempotent(db_conn):
    from goat.db import init_goat_tables

    init_goat_tables(db_conn)  # second call must not raise (column already exists)
    init_goat_tables(db_conn)
