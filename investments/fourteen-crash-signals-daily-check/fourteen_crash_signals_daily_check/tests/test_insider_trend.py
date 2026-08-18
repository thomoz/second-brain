from __future__ import annotations

from fourteen_crash_signals_daily_check import config, db, insider_trend


def _seed_watchlist(conn, tickers):
    db.replace_hot_watchlist(conn, [
        {"ticker": t, "sector_label": "Technology", "market_cap": 1e12, "rank": i + 1}
        for i, t in enumerate(tickers)
    ])


def test_check_insider_trend_empty_when_no_hot_watchlist(db_conn):
    assert insider_trend.check_insider_trend(db_conn) == []


def test_check_insider_trend_unknown_when_both_fetches_fail(db_conn, monkeypatch):
    _seed_watchlist(db_conn, ["NVDA"])
    monkeypatch.setattr(
        "fourteen_crash_signals_daily_check.insider_trend.openinsider.fetch_screener_filings",
        lambda tickers, trade_type, min_value, filing_date_days=7: None,
    )
    results = insider_trend.check_insider_trend(db_conn)
    assert len(results) == 1
    assert results[0].verdict == "unknown"


def test_check_insider_trend_flags_ratio_at_or_above_threshold(db_conn, monkeypatch):
    _seed_watchlist(db_conn, ["NVDA"])

    def _fake(tickers, trade_type, min_value, filing_date_days=7):
        if trade_type == "P":
            return [{"ticker": "NVDA", "value": 100_000.0}]
        return [{"ticker": "NVDA", "value": 100_000.0 * config.SIGNALS_INSIDER_TREND_NET_SELL_FLAG_RATIO}]

    monkeypatch.setattr("fourteen_crash_signals_daily_check.insider_trend.openinsider.fetch_screener_filings", _fake)
    results = insider_trend.check_insider_trend(db_conn)
    assert len(results) == 1
    assert results[0].verdict == "flag"
    assert results[0].data["ratio"] == config.SIGNALS_INSIDER_TREND_NET_SELL_FLAG_RATIO


def test_check_insider_trend_ok_below_threshold(db_conn, monkeypatch):
    _seed_watchlist(db_conn, ["NVDA"])

    def _fake(tickers, trade_type, min_value, filing_date_days=7):
        if trade_type == "P":
            return [{"ticker": "NVDA", "value": 100_000.0}]
        return [{"ticker": "NVDA", "value": 100_000.0}]

    monkeypatch.setattr("fourteen_crash_signals_daily_check.insider_trend.openinsider.fetch_screener_filings", _fake)
    results = insider_trend.check_insider_trend(db_conn)
    assert results[0].verdict == "ok"
    assert results[0].data["ratio"] == 1.0


def test_check_insider_trend_only_purchases_ratio_is_zero_not_error(db_conn, monkeypatch):
    _seed_watchlist(db_conn, ["NVDA"])

    def _fake(tickers, trade_type, min_value, filing_date_days=7):
        if trade_type == "P":
            return [{"ticker": "NVDA", "value": 50_000.0}]
        return []

    monkeypatch.setattr("fourteen_crash_signals_daily_check.insider_trend.openinsider.fetch_screener_filings", _fake)
    results = insider_trend.check_insider_trend(db_conn)
    assert results[0].data["ratio"] == 0.0
    assert results[0].verdict == "ok"


def test_check_insider_trend_only_sales_ratio_is_inf_and_flags(db_conn, monkeypatch):
    _seed_watchlist(db_conn, ["NVDA"])

    def _fake(tickers, trade_type, min_value, filing_date_days=7):
        if trade_type == "S":
            return [{"ticker": "NVDA", "value": 50_000.0}]
        return []

    monkeypatch.setattr("fourteen_crash_signals_daily_check.insider_trend.openinsider.fetch_screener_filings", _fake)
    results = insider_trend.check_insider_trend(db_conn)
    assert results[0].data["ratio"] == float("inf")
    assert results[0].verdict == "flag"


def test_check_insider_trend_omits_ticker_with_zero_activity(db_conn, monkeypatch):
    _seed_watchlist(db_conn, ["NVDA", "MSFT"])

    def _fake(tickers, trade_type, min_value, filing_date_days=7):
        if trade_type == "P":
            return [{"ticker": "NVDA", "value": 50_000.0}]
        return []

    monkeypatch.setattr("fourteen_crash_signals_daily_check.insider_trend.openinsider.fetch_screener_filings", _fake)
    results = insider_trend.check_insider_trend(db_conn)
    assert [r.data["ticker"] for r in results] == ["NVDA"]
