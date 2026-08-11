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


def test_move_bucket_preserves_return_data(db_conn):
    """Regression: cmd_watchlist_move_bucket (main.py) deletes the old (ticker, bucket)
    row and inserts a fresh one for the new bucket via upsert_watchlist_row, which
    never touches dividend_yield_pct/ten_year_return_pct. Found 2026-07-19 when moving
    TSLA and UBER to the ai_postcrash bucket silently wiped their 10Y Return figures —
    upsert_watchlist_row's INSERT branch leaves those columns NULL on a brand-new
    (ticker, bucket) key. The real fix carries the values through via a follow-up
    update_watchlist_return_data call; this locks in that the round trip preserves them."""
    db.upsert_watchlist_row(
        db_conn, ticker="TSLA", name="Tesla Inc", asset_type="stock", bucket="1",
    )
    db.update_watchlist_return_data(db_conn, "TSLA", "1", None, 2425.0)

    row = db.get_watchlist_row(db_conn, "TSLA", "1")
    db.delete_watchlist_row(db_conn, "TSLA", "1")
    db.upsert_watchlist_row(
        db_conn, ticker="TSLA", name=row["name"], asset_type=row["asset_type"],
        bucket="ai_postcrash", status=row["status"], notes=row["notes"],
        source=row["source"], last_expense_ratio=row["last_expense_ratio"],
    )
    db.update_watchlist_return_data(
        db_conn, "TSLA", "ai_postcrash", row["dividend_yield_pct"], row["ten_year_return_pct"],
    )

    moved = db.get_watchlist_row(db_conn, "TSLA", "ai_postcrash")
    assert moved["ten_year_return_pct"] == 2425.0


def test_insert_pending_candidate_then_get_finds_it(db_conn):
    db.insert_pending_candidate(
        db_conn, ticker="NVDA", company_name="Nvidia", buy_thesis="AI chip demand",
    )
    row = db.get_pending_candidate(db_conn, "NVDA")
    assert row is not None
    assert row["company_name"] == "Nvidia"
    assert row["source"] == "briefs_finance_ingest"


def test_insert_pending_candidate_ignores_duplicate_ticker(db_conn):
    db.insert_pending_candidate(db_conn, ticker="NVDA", company_name="Nvidia", buy_thesis="first")
    db.insert_pending_candidate(db_conn, ticker="NVDA", company_name="Nvidia", buy_thesis="second")
    assert len(db.get_all_pending_candidates(db_conn)) == 1
    row = db.get_pending_candidate(db_conn, "NVDA")
    assert row["buy_thesis"] == "first"


def test_delete_pending_candidate_removes_it(db_conn):
    db.insert_pending_candidate(db_conn, ticker="NVDA", company_name="Nvidia", buy_thesis=None)
    count = db.delete_pending_candidate(db_conn, "NVDA")
    assert count == 1
    assert db.get_pending_candidate(db_conn, "NVDA") is None


def test_delete_pending_candidate_returns_zero_when_not_found(db_conn):
    assert db.delete_pending_candidate(db_conn, "NOPE") == 0


def test_delete_watchlist_row_removes_specific_bucket(db_conn):
    db.upsert_watchlist_row(
        db_conn, ticker="PMGOLD", name="Perth Mint Gold", asset_type="etf", bucket="3a",
    )
    db.upsert_watchlist_row(
        db_conn, ticker="PMGOLD", name="Perth Mint Gold", asset_type="etf", bucket="3b",
    )
    count = db.delete_watchlist_row(db_conn, "PMGOLD", "3a")
    assert count == 1
    assert db.get_watchlist_row(db_conn, "PMGOLD", "3a") is None
    assert db.get_watchlist_row(db_conn, "PMGOLD", "3b") is not None


def test_delete_watchlist_row_removes_all_buckets_when_bucket_omitted(db_conn):
    db.upsert_watchlist_row(
        db_conn, ticker="PMGOLD", name="Perth Mint Gold", asset_type="etf", bucket="3a",
    )
    db.upsert_watchlist_row(
        db_conn, ticker="PMGOLD", name="Perth Mint Gold", asset_type="etf", bucket="3b",
    )
    count = db.delete_watchlist_row(db_conn, "PMGOLD")
    assert count == 2
    assert db.get_watchlist_row(db_conn, "PMGOLD") is None


def test_delete_watchlist_row_returns_zero_when_not_found(db_conn):
    assert db.delete_watchlist_row(db_conn, "NOPE") == 0


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


def test_get_sync_watermark_returns_none_when_unset(db_conn):
    assert db.get_sync_watermark(db_conn, "some_key") is None


def test_set_sync_watermark_then_get_returns_value(db_conn):
    db.set_sync_watermark(db_conn, "some_key", "42")
    assert db.get_sync_watermark(db_conn, "some_key") == "42"


def test_set_sync_watermark_overwrites_existing_value(db_conn):
    db.set_sync_watermark(db_conn, "some_key", "42")
    db.set_sync_watermark(db_conn, "some_key", "99")
    assert db.get_sync_watermark(db_conn, "some_key") == "99"


def test_get_macro_snapshot_empty_when_unset(db_conn):
    assert db.get_macro_snapshot(db_conn) == []


def test_upsert_macro_snapshot_inserts_all_checks(db_conn):
    from mytrader.checks import CheckResult

    checks = [
        CheckResult(name="move_index", verdict="ok", detail="MOVE at 90.0"),
        CheckResult(name="credit_spreads", verdict="flag", detail="HY OAS widening"),
    ]
    db.upsert_macro_snapshot(db_conn, checks)
    rows = db.get_macro_snapshot(db_conn)
    assert len(rows) == 2
    by_name = {r["name"]: r for r in rows}
    assert by_name["move_index"]["verdict"] == "ok"
    assert by_name["credit_spreads"]["detail"] == "HY OAS widening"
    assert by_name["move_index"]["computed_at"] is not None


def test_upsert_macro_snapshot_overwrites_not_duplicates(db_conn):
    from mytrader.checks import CheckResult

    db.upsert_macro_snapshot(db_conn, [CheckResult(name="move_index", verdict="ok", detail="v1")])
    db.upsert_macro_snapshot(db_conn, [CheckResult(name="move_index", verdict="flag", detail="v2")])
    rows = db.get_macro_snapshot(db_conn)
    assert len(rows) == 1
    assert rows[0]["verdict"] == "flag"
    assert rows[0]["detail"] == "v2"


def test_get_cik_for_ticker_returns_none_when_unmapped(db_conn):
    assert db.get_cik_for_ticker(db_conn, "KO") is None


def test_upsert_cik_map_bulk_then_get_finds_it(db_conn):
    db.upsert_cik_map_bulk(db_conn, {"KO": "21344", "AAPL": "320193"})
    assert db.get_cik_for_ticker(db_conn, "KO") == "21344"
    assert db.get_cik_for_ticker(db_conn, "AAPL") == "320193"


def test_upsert_cik_map_bulk_is_full_resync_not_incremental(db_conn):
    """A delisted/renamed ticker must disappear on refresh, not accumulate forever."""
    db.upsert_cik_map_bulk(db_conn, {"KO": "21344"})
    db.upsert_cik_map_bulk(db_conn, {"AAPL": "320193"})
    assert db.get_cik_for_ticker(db_conn, "KO") is None
    assert db.get_cik_for_ticker(db_conn, "AAPL") == "320193"


def test_get_cached_filing_summary_returns_none_when_unset(db_conn):
    assert db.get_cached_filing_summary(db_conn, "KO", "10-K") is None


def test_upsert_filing_summary_cache_then_get_finds_it(db_conn):
    db.upsert_filing_summary_cache(
        db_conn, ticker="KO", filing_type="10-K",
        accession_number="0000021344-26-000010", summary="Strong moat, rising margins.",
    )
    row = db.get_cached_filing_summary(db_conn, "KO", "10-K")
    assert row is not None
    assert row["accession_number"] == "0000021344-26-000010"
    assert row["summary"] == "Strong moat, rising margins."


def test_upsert_filing_summary_cache_replaces_on_same_key(db_conn):
    db.upsert_filing_summary_cache(
        db_conn, ticker="KO", filing_type="10-K",
        accession_number="0000021344-25-000001", summary="Old summary.",
    )
    db.upsert_filing_summary_cache(
        db_conn, ticker="KO", filing_type="10-K",
        accession_number="0000021344-26-000010", summary="New summary.",
    )
    row = db.get_cached_filing_summary(db_conn, "KO", "10-K")
    assert row["accession_number"] == "0000021344-26-000010"
    assert row["summary"] == "New summary."


def test_record_price_snapshot_then_get_price_history(db_conn):
    db.record_price_snapshot(
        db_conn, ticker="V", bucket="1", date="2026-08-01", price=340.0, qty=0.1, mkt_value=34.0,
    )
    db.record_price_snapshot(
        db_conn, ticker="V", bucket="1", date="2026-08-02", price=345.0, qty=0.1, mkt_value=34.5,
    )
    rows = db.get_price_history(db_conn, "V", "1")
    assert [r["date"] for r in rows] == ["2026-08-01", "2026-08-02"]
    assert rows[1]["price"] == 345.0


def test_record_price_snapshot_same_day_replaces_not_duplicates(db_conn):
    db.record_price_snapshot(
        db_conn, ticker="V", bucket="1", date="2026-08-01", price=340.0, qty=0.1, mkt_value=34.0,
    )
    db.record_price_snapshot(
        db_conn, ticker="V", bucket="1", date="2026-08-01", price=342.0, qty=0.1, mkt_value=34.2,
    )
    rows = db.get_price_history(db_conn, "V", "1")
    assert len(rows) == 1
    assert rows[0]["price"] == 342.0


def test_get_price_history_filters_by_ticker_across_buckets(db_conn):
    db.record_price_snapshot(
        db_conn, ticker="PMGOLD", bucket="3a", date="2026-08-01", price=57.0, qty=10.0, mkt_value=570.0,
    )
    db.record_price_snapshot(
        db_conn, ticker="PMGOLD", bucket="3b", date="2026-08-01", price=57.0, qty=5.0, mkt_value=285.0,
    )
    rows = db.get_price_history(db_conn, "PMGOLD")
    assert len(rows) == 2
    assert {r["bucket"] for r in rows} == {"3a", "3b"}


def test_get_portfolio_value_history_sums_across_tickers_per_day(db_conn):
    db.record_price_snapshot(
        db_conn, ticker="V", bucket="1", date="2026-08-01", price=340.0, qty=0.1, mkt_value=34.0,
    )
    db.record_price_snapshot(
        db_conn, ticker="PMGOLD", bucket="3a", date="2026-08-01", price=57.0, qty=10.0, mkt_value=570.0,
    )
    db.record_price_snapshot(
        db_conn, ticker="V", bucket="1", date="2026-08-02", price=345.0, qty=0.1, mkt_value=34.5,
    )
    rows = db.get_portfolio_value_history(db_conn)
    assert [dict(r) for r in rows] == [
        {"date": "2026-08-01", "total_mkt_value": 604.0},
        {"date": "2026-08-02", "total_mkt_value": 34.5},
    ]
