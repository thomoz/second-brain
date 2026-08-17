from __future__ import annotations

from datetime import date, timedelta

from mytrader import db as mt_db

from goat import config as goat_config, db as goat_db, insider_scan


def _seed_holding(conn, ticker="VRTX", bucket="1"):
    mt_db.upsert_holding(
        conn, ticker=ticker, name="Vertex Pharmaceuticals", asset_type="stock",
        bucket=bucket, qty=1.0, avg_price=100.0,
    )


def _sale_row(ticker="VRTX", trade_date=None, value=2_000_000.0, pct_owned_change=None):
    return {
        "ticker": ticker,
        "filing_date": (trade_date or date.today()).isoformat(),
        "trade_date": (trade_date or date.today()).isoformat(),
        "insider_name": "Jane Doe",
        "title": "CFO",
        "trade_type_code": "S",
        "value": value,
        "pct_owned_change": pct_owned_change,
    }


def _purchase_row(ticker="ACME", trade_date=None, value=30_000.0, pct_owned_change=None):
    return {
        "ticker": ticker,
        "filing_date": (trade_date or date.today()).isoformat(),
        "trade_date": (trade_date or date.today()).isoformat(),
        "insider_name": "John Smith",
        "title": "Director",
        "trade_type_code": "P",
        "value": value,
        "pct_owned_change": pct_owned_change,
    }


def test_run_holdings_watch_alerts_on_new_sale_filing(db_conn, monkeypatch):
    _seed_holding(db_conn, ticker="VRTX")
    monkeypatch.setattr(
        "goat.insider_scan.openinsider.fetch_screener_filings",
        lambda tickers_list, trade_type, min_value: [_sale_row()] if trade_type == "S" else [],
    )
    result = insider_scan.run_holdings_watch(db_conn)
    assert len(result["new_alerts"]) == 1
    assert "VRTX" in result["new_alerts"][0]["message"]
    assert "2,000,000" in result["new_alerts"][0]["message"]


def test_run_holdings_watch_message_includes_pct_owned_change_when_present(db_conn, monkeypatch):
    _seed_holding(db_conn, ticker="VRTX")
    monkeypatch.setattr(
        "goat.insider_scan.openinsider.fetch_screener_filings",
        lambda tickers_list, trade_type, min_value: (
            [_sale_row(pct_owned_change=-91.0)] if trade_type == "S" else []
        ),
    )
    result = insider_scan.run_holdings_watch(db_conn)
    assert "(91% of position)" in result["new_alerts"][0]["message"]


def test_run_holdings_watch_message_omits_pct_clause_when_none(db_conn, monkeypatch):
    _seed_holding(db_conn, ticker="VRTX")
    monkeypatch.setattr(
        "goat.insider_scan.openinsider.fetch_screener_filings",
        lambda tickers_list, trade_type, min_value: (
            [_sale_row(pct_owned_change=None)] if trade_type == "S" else []
        ),
    )
    result = insider_scan.run_holdings_watch(db_conn)
    assert "of position" not in result["new_alerts"][0]["message"]


def test_run_holdings_watch_suppresses_first_sale_under_10pct_threshold(db_conn, monkeypatch):
    _seed_holding(db_conn, ticker="VRTX")
    monkeypatch.setattr(
        "goat.insider_scan.openinsider.fetch_screener_filings",
        lambda tickers_list, trade_type, min_value: (
            [_sale_row(pct_owned_change=-5.0)] if trade_type == "S" else []
        ),
    )
    result = insider_scan.run_holdings_watch(db_conn)
    assert result["new_alerts"] == []


def test_run_holdings_watch_alerts_first_sale_at_10pct_threshold(db_conn, monkeypatch):
    _seed_holding(db_conn, ticker="VRTX")
    monkeypatch.setattr(
        "goat.insider_scan.openinsider.fetch_screener_filings",
        lambda tickers_list, trade_type, min_value: (
            [_sale_row(pct_owned_change=-10.0)] if trade_type == "S" else []
        ),
    )
    result = insider_scan.run_holdings_watch(db_conn)
    assert len(result["new_alerts"]) == 1


def test_run_holdings_watch_alerts_repeat_sale_above_1pct_when_prior_sale_within_90_days(db_conn, monkeypatch):
    _seed_holding(db_conn, ticker="VRTX")
    prior_date = (date.today() - timedelta(days=30)).isoformat()
    goat_db.insert_goat_insider_filing_seen(
        db_conn, dedup_key="prior-sale-key", ticker="VRTX", filing_date=prior_date,
        trade_date=prior_date, insider_name="Jane Doe", trade_type="S", value=50_000.0,
        kind="holdings_watch", pct_owned_change=-3.0,
    )
    monkeypatch.setattr(
        "goat.insider_scan.openinsider.fetch_screener_filings",
        lambda tickers_list, trade_type, min_value: (
            [_sale_row(pct_owned_change=-2.0)] if trade_type == "S" else []
        ),
    )
    result = insider_scan.run_holdings_watch(db_conn)
    assert len(result["new_alerts"]) == 1
    assert "cumulative exit risk" in result["new_alerts"][0]["message"]


def test_run_holdings_watch_suppresses_repeat_sale_under_1pct_threshold(db_conn, monkeypatch):
    _seed_holding(db_conn, ticker="VRTX")
    prior_date = (date.today() - timedelta(days=30)).isoformat()
    goat_db.insert_goat_insider_filing_seen(
        db_conn, dedup_key="prior-sale-key-2", ticker="VRTX", filing_date=prior_date,
        trade_date=prior_date, insider_name="Jane Doe", trade_type="S", value=50_000.0,
        kind="holdings_watch", pct_owned_change=-3.0,
    )
    monkeypatch.setattr(
        "goat.insider_scan.openinsider.fetch_screener_filings",
        lambda tickers_list, trade_type, min_value: (
            [_sale_row(pct_owned_change=-0.5)] if trade_type == "S" else []
        ),
    )
    result = insider_scan.run_holdings_watch(db_conn)
    assert result["new_alerts"] == []


def test_run_holdings_watch_ignores_prior_sale_outside_90_day_window(db_conn, monkeypatch):
    _seed_holding(db_conn, ticker="VRTX")
    old_date = (date.today() - timedelta(days=120)).isoformat()
    goat_db.insert_goat_insider_filing_seen(
        db_conn, dedup_key="old-sale-key", ticker="VRTX", filing_date=old_date,
        trade_date=old_date, insider_name="Jane Doe", trade_type="S", value=50_000.0,
        kind="holdings_watch", pct_owned_change=-3.0,
    )
    monkeypatch.setattr(
        "goat.insider_scan.openinsider.fetch_screener_filings",
        lambda tickers_list, trade_type, min_value: (
            [_sale_row(pct_owned_change=-2.0)] if trade_type == "S" else []
        ),
    )
    result = insider_scan.run_holdings_watch(db_conn)
    assert result["new_alerts"] == []  # treated as a first sale (10% bar) -- the 120-day-old sale doesn't count


def test_run_holdings_watch_stays_quiet_on_repeat_run(db_conn, monkeypatch):
    _seed_holding(db_conn, ticker="VRTX")
    monkeypatch.setattr(
        "goat.insider_scan.openinsider.fetch_screener_filings",
        lambda tickers_list, trade_type, min_value: [_sale_row()] if trade_type == "S" else [],
    )
    insider_scan.run_holdings_watch(db_conn)
    result = insider_scan.run_holdings_watch(db_conn)
    assert result["new_alerts"] == []


def test_run_holdings_watch_skips_fetch_when_no_holdings(db_conn, monkeypatch):
    calls = []
    monkeypatch.setattr(
        "goat.insider_scan.openinsider.fetch_screener_filings",
        lambda tickers_list, trade_type, min_value: calls.append(1),
    )
    result = insider_scan.run_holdings_watch(db_conn)
    assert calls == []
    assert result == {"checked_holdings": 0, "new_alerts": [], "recent_filings": []}


def test_run_holdings_watch_handles_total_fetch_failure_gracefully(db_conn, monkeypatch):
    _seed_holding(db_conn, ticker="VRTX")
    monkeypatch.setattr(
        "goat.insider_scan.openinsider.fetch_screener_filings",
        lambda tickers_list, trade_type, min_value: None,
    )
    result = insider_scan.run_holdings_watch(db_conn)  # must not raise
    assert result["new_alerts"] == []


def test_run_holdings_watch_ignores_filing_outside_lookback_window(db_conn, monkeypatch):
    _seed_holding(db_conn, ticker="VRTX")
    stale_date = date.today() - timedelta(days=config_lookback_plus_one())
    monkeypatch.setattr(
        "goat.insider_scan.openinsider.fetch_screener_filings",
        lambda tickers_list, trade_type, min_value: (
            [_sale_row(trade_date=stale_date)] if trade_type == "S" else []
        ),
    )
    result = insider_scan.run_holdings_watch(db_conn)
    assert result["new_alerts"] == []


def config_lookback_plus_one() -> int:
    return goat_config.GOAT_INSIDER_HOLDINGS_WATCH_LOOKBACK_DAYS + 1


def test_run_discovery_scan_stages_new_purchase_candidate(db_conn, monkeypatch):
    monkeypatch.setattr(
        "goat.insider_scan.openinsider.fetch_discovery_purchases",
        lambda: [_purchase_row(ticker="ACME")],
    )
    result = insider_scan.run_discovery_scan(db_conn)
    assert len(result["new_candidates"]) == 1
    row = goat_db.get_goat_pending_candidate(db_conn, "ACME")
    assert row is not None
    assert row["source"] == "goat_insider_discovery"


def test_run_discovery_scan_candidate_detail_includes_pct_owned_change(db_conn, monkeypatch):
    monkeypatch.setattr(
        "goat.insider_scan.openinsider.fetch_discovery_purchases",
        lambda: [_purchase_row(ticker="ACME", pct_owned_change=45.0)],
    )
    result = insider_scan.run_discovery_scan(db_conn)
    assert "(45% of position)" in result["new_candidates"][0]["detail"]


def test_run_discovery_scan_skips_ticker_already_a_holding(db_conn, monkeypatch):
    _seed_holding(db_conn, ticker="ACME")
    monkeypatch.setattr(
        "goat.insider_scan.openinsider.fetch_discovery_purchases",
        lambda: [_purchase_row(ticker="ACME")],
    )
    result = insider_scan.run_discovery_scan(db_conn)
    assert result["new_candidates"] == []
    assert goat_db.get_goat_pending_candidate(db_conn, "ACME") is None


def test_run_discovery_scan_skips_ticker_already_in_watchlist(db_conn, monkeypatch):
    mt_db.upsert_watchlist_row(
        db_conn, ticker="ACME", name="Acme Corp", asset_type="stock", bucket="unassigned",
    )
    monkeypatch.setattr(
        "goat.insider_scan.openinsider.fetch_discovery_purchases",
        lambda: [_purchase_row(ticker="ACME")],
    )
    result = insider_scan.run_discovery_scan(db_conn)
    assert result["new_candidates"] == []
    assert goat_db.get_goat_pending_candidate(db_conn, "ACME") is None


def test_run_discovery_scan_skips_banned_ticker(db_conn, monkeypatch):
    monkeypatch.setattr(goat_config, "GOAT_BANNED_TICKERS", {"ACME"})
    monkeypatch.setattr(
        "goat.insider_scan.openinsider.fetch_discovery_purchases",
        lambda: [_purchase_row(ticker="ACME")],
    )
    result = insider_scan.run_discovery_scan(db_conn)
    assert result["new_candidates"] == []
    assert goat_db.get_goat_pending_candidate(db_conn, "ACME") is None


def test_run_discovery_scan_stays_quiet_on_repeat_run(db_conn, monkeypatch):
    monkeypatch.setattr(
        "goat.insider_scan.openinsider.fetch_discovery_purchases",
        lambda: [_purchase_row(ticker="ACME")],
    )
    insider_scan.run_discovery_scan(db_conn)
    result = insider_scan.run_discovery_scan(db_conn)
    assert result["new_candidates"] == []
    assert len(result["pending_candidates"]) == 1


def test_run_discovery_scan_handles_fetch_failure_gracefully(db_conn, monkeypatch):
    monkeypatch.setattr(
        "goat.insider_scan.openinsider.fetch_discovery_purchases",
        lambda: None,
    )
    result = insider_scan.run_discovery_scan(db_conn)  # must not raise
    assert result["new_candidates"] == []


def test_render_insider_scan_report_lists_alerts_and_pending_candidates():
    watch_result = {
        "checked_holdings": 2,
        "new_alerts": [{"ticker": "VRTX", "message": "Jane Doe (CFO) sold $2,000,000 of VRTX on 2026-08-17"}],
    }
    discovery_result = {
        "pending_candidates": [
            {"ticker": "ACME", "sector_label": "Insider Buy",
             "signal_detail": "John Smith (Director) bought $30,000 of ACME on 2026-08-17",
             "flagged_at": "2026-08-17T00:00:00+00:00"},
        ],
    }
    report = insider_scan.render_insider_scan_report(watch_result, discovery_result)
    assert "VRTX" in report
    assert "2,000,000" in report
    assert "ACME" in report

    empty_watch = {"checked_holdings": 0, "new_alerts": []}
    empty_discovery = {"pending_candidates": []}
    empty_report = insider_scan.render_insider_scan_report(empty_watch, empty_discovery)
    assert "No new insider activity on current holdings." in empty_report
