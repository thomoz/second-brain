from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
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
    assert "No insider filings recorded yet for current holdings." in empty_report


def _price_series(days_ago: int, start_price: float, end_price: float) -> tuple[str, pd.Series]:
    """A close series that starts exactly on trade_date (days_ago days back)
    at start_price and sits at end_price for every day since, so
    _price_move_since's on/after-trade_date slice picks up start_price first
    and end_price last -- gives a deterministic pct_change for testing."""
    trade_date = date.today() - timedelta(days=days_ago)
    idx = pd.date_range(trade_date, periods=max(days_ago, 1) + 1, freq="D")
    prices = [start_price] + [end_price] * (len(idx) - 1)
    return trade_date.isoformat(), pd.Series(prices, index=idx)


def test_compute_discovery_price_performance_flags_buy_that_rose_past_threshold(db_conn, monkeypatch):
    trade_date, series = _price_series(days_ago=30, start_price=100.0, end_price=125.0)
    monkeypatch.setattr("goat.insider_scan.price_history.fetch_close_history", lambda t, lb: series)
    candidates = [{"ticker": "ACME", "trade_date": trade_date, "price_flag_notified": 0}]
    result = insider_scan.compute_discovery_price_performance(db_conn, candidates)
    assert "+25.0%" in result[0]["price_note"]
    assert "confirms signal" in result[0]["price_note"]


def test_compute_discovery_price_performance_does_not_flag_below_threshold(db_conn, monkeypatch):
    trade_date, series = _price_series(days_ago=30, start_price=100.0, end_price=105.0)
    monkeypatch.setattr("goat.insider_scan.price_history.fetch_close_history", lambda t, lb: series)
    candidates = [{"ticker": "ACME", "trade_date": trade_date, "price_flag_notified": 0}]
    result = insider_scan.compute_discovery_price_performance(db_conn, candidates)
    assert "confirms signal" not in result[0]["price_note"]


def test_compute_discovery_price_performance_notes_staleness_past_90_days(db_conn, monkeypatch):
    trade_date, series = _price_series(days_ago=95, start_price=100.0, end_price=130.0)
    monkeypatch.setattr("goat.insider_scan.price_history.fetch_close_history", lambda t, lb: series)
    candidates = [{"ticker": "ACME", "trade_date": trade_date, "price_flag_notified": 0}]
    result = insider_scan.compute_discovery_price_performance(db_conn, candidates)
    assert "may not reflect the insider signal anymore" in result[0]["price_note"]


def test_compute_discovery_price_performance_unavailable_without_trade_date(db_conn):
    candidates = [{"ticker": "ACME", "trade_date": None, "price_flag_notified": 0}]
    result = insider_scan.compute_discovery_price_performance(db_conn, candidates)
    assert result[0]["price_note"] == "price unavailable"


def test_compute_discovery_price_performance_unavailable_on_fetch_miss(db_conn, monkeypatch):
    monkeypatch.setattr("goat.insider_scan.price_history.fetch_close_history", lambda t, lb: None)
    candidates = [{"ticker": "ACME", "trade_date": date.today().isoformat(), "price_flag_notified": 0}]
    result = insider_scan.compute_discovery_price_performance(db_conn, candidates)
    assert result[0]["price_note"] == "price unavailable"


def test_compute_discovery_price_performance_marks_newly_flagged_once(db_conn, monkeypatch):
    """Regression test for the 2026-08-18 'notify on crossing' feature: the
    first run over threshold sets newly_flagged + persists the DB guard; a
    second run (flag still up) must not re-fire it."""
    trade_date, series = _price_series(days_ago=30, start_price=100.0, end_price=125.0)
    goat_db.insert_goat_pending_candidate(
        db_conn, ticker="ACME", sector_label="Insider Buy", signal_detail="d",
        source="goat_insider_discovery", trade_date=trade_date,
    )
    monkeypatch.setattr("goat.insider_scan.price_history.fetch_close_history", lambda t, lb: series)

    row = dict(goat_db.get_goat_pending_candidate(db_conn, "ACME"))
    result = insider_scan.compute_discovery_price_performance(db_conn, [row])
    assert result[0]["newly_flagged"] is True
    assert goat_db.get_goat_pending_candidate(db_conn, "ACME")["price_flag_notified"] == 1

    row_again = dict(goat_db.get_goat_pending_candidate(db_conn, "ACME"))
    result_again = insider_scan.compute_discovery_price_performance(db_conn, [row_again])
    assert result_again[0]["newly_flagged"] is False


def test_compute_holdings_watch_price_performance_flags_sale_that_fell(db_conn, monkeypatch):
    trade_date, series = _price_series(days_ago=20, start_price=100.0, end_price=80.0)
    monkeypatch.setattr("goat.insider_scan.price_history.fetch_close_history", lambda t, lb: series)
    filings = [{"ticker": "VRTX", "trade_date": trade_date, "trade_type": "S",
                "dedup_key": "key-1", "price_flag_notified": 0}]
    result = insider_scan.compute_holdings_watch_price_performance(db_conn, filings)
    assert "-20.0%" in result[0]["price_note"]
    assert "confirms signal" in result[0]["price_note"]
    assert result[0]["newly_flagged"] is True


def test_compute_holdings_watch_price_performance_ignores_contrarian_direction(db_conn, monkeypatch):
    # A sale followed by a big price RISE is the contrarian case -- Shaun
    # 2026-08-18 wants only the confirming direction flagged (sale -> fall).
    trade_date, series = _price_series(days_ago=20, start_price=100.0, end_price=130.0)
    monkeypatch.setattr("goat.insider_scan.price_history.fetch_close_history", lambda t, lb: series)
    filings = [{"ticker": "VRTX", "trade_date": trade_date, "trade_type": "S",
                "dedup_key": "key-2", "price_flag_notified": 0}]
    result = insider_scan.compute_holdings_watch_price_performance(db_conn, filings)
    assert "confirms signal" not in result[0]["price_note"]
    assert result[0]["newly_flagged"] is False


def test_compute_holdings_watch_price_performance_does_not_reflag_already_notified(db_conn, monkeypatch):
    trade_date, series = _price_series(days_ago=20, start_price=100.0, end_price=80.0)
    monkeypatch.setattr("goat.insider_scan.price_history.fetch_close_history", lambda t, lb: series)
    filings = [{"ticker": "VRTX", "trade_date": trade_date, "trade_type": "S",
                "dedup_key": "key-3", "price_flag_notified": 1}]
    result = insider_scan.compute_holdings_watch_price_performance(db_conn, filings)
    assert result[0]["newly_flagged"] is False


def _fake_notifications_module(toast_calls, whatsapp_calls):
    import types
    fake_module = types.ModuleType("notifications")
    fake_module.send_toast_notification = lambda *a, **k: toast_calls.append((a, k))
    fake_module.send_whatsapp_notification = lambda *a, **k: whatsapp_calls.append((a, k))
    return fake_module


def test_maybe_notify_price_flags_skips_when_nothing_newly_flagged():
    insider_scan.maybe_notify_price_flags([])  # must not raise, no notification module needed


def test_maybe_notify_price_flags_sends_whatsapp_with_ticker_and_note(monkeypatch):
    import sys
    toast_calls, whatsapp_calls = [], []
    monkeypatch.setitem(sys.modules, "notifications", _fake_notifications_module(toast_calls, whatsapp_calls))

    insider_scan.maybe_notify_price_flags(
        [{"ticker": "ACME", "price_note": "+25.0% since trade \U0001F6A9 confirms signal"}]
    )
    assert len(toast_calls) == 1
    assert len(whatsapp_calls) == 1
    (message,), _kwargs = whatsapp_calls[0]
    assert "ACME" in message
    assert "+25.0% since trade" in message


def test_render_insider_scan_report_includes_price_note_and_recent_filings_section():
    watch_result = {
        "checked_holdings": 1,
        "new_alerts": [],
        "recent_filings": [
            {"ticker": "VRTX", "trade_type": "S", "value": 2_000_000.0,
             "trade_date": "2026-08-01", "price_note": "-22.0% since trade \U0001F6A9 confirms signal"},
        ],
    }
    discovery_result = {
        "pending_candidates": [
            {"ticker": "ACME", "sector_label": "Insider Buy",
             "signal_detail": "John Smith (Director) bought $30,000 of ACME on 2026-08-17",
             "flagged_at": "2026-08-17T00:00:00+00:00", "price_note": "+18.0% since trade \U0001F6A9 confirms signal"},
        ],
    }
    report = insider_scan.render_insider_scan_report(watch_result, discovery_result)
    assert "+18.0% since trade" in report
    assert "-22.0% since trade" in report
    assert "Stocks You Own That Have Had Price Moves Since Insider Buy/Sell Activity" in report
    assert "Sold" in report and "2,000,000" in report
