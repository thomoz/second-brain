from __future__ import annotations

import pandas as pd
from mytrader import db as mt_db

from goat import config as goat_config, db as goat_db, live_monitor, monitor
from goat.live_monitor import _completed_closes_only


def _dates(n: int, start: str = "2026-01-01") -> pd.DatetimeIndex:
    return pd.date_range(start, periods=n, freq="D")


def _flat_history(n: int = goat_config.GOAT_MA_LONG_DAYS, flat_price: float = 100.0) -> pd.Series:
    return pd.Series([flat_price] * n, index=_dates(n))


def _seed_holding(conn, ticker="VRTX", bucket="1"):
    mt_db.upsert_holding(
        conn, ticker=ticker, name="Vertex Pharmaceuticals", asset_type="stock",
        bucket=bucket, qty=1.0, avg_price=100.0,
    )


def test_run_live_monitor_noop_when_both_markets_closed(db_conn, monkeypatch):
    _seed_holding(db_conn)
    monkeypatch.setattr("goat.live_monitor.market_hours.is_asx_open", lambda: False)
    monkeypatch.setattr("goat.live_monitor.market_hours.is_us_market_open", lambda: False)

    def _raise(*a, **k):
        raise AssertionError("fetch_current_price should not be called when both markets are closed")

    monkeypatch.setattr("goat.live_monitor.market_data.fetch_current_price", _raise)

    result = live_monitor.run_live_monitor(db_conn)
    assert result["checked_holdings"] == 0
    assert result["new_alerts"] == []


def test_run_live_monitor_only_checks_matching_market(db_conn, monkeypatch):
    _seed_holding(db_conn, ticker="GGOV.AX", bucket="1")
    _seed_holding(db_conn, ticker="LULU", bucket="1")

    monkeypatch.setattr("goat.live_monitor.market_hours.is_asx_open", lambda: True)
    monkeypatch.setattr("goat.live_monitor.market_hours.is_us_market_open", lambda: False)
    monkeypatch.setattr("goat.live_monitor.market_data.fetch_current_price", lambda t: 100.5)
    monkeypatch.setattr("goat.live_monitor.price_history.fetch_close_history", lambda t, lb: _flat_history())

    result = live_monitor.run_live_monitor(db_conn)
    assert result["checked_holdings"] == 1


def test_run_live_monitor_creates_new_alert_on_flag(db_conn, monkeypatch):
    _seed_holding(db_conn, ticker="LULU", bucket="1")
    monkeypatch.setattr("goat.live_monitor.market_hours.is_asx_open", lambda: False)
    monkeypatch.setattr("goat.live_monitor.market_hours.is_us_market_open", lambda: True)
    monkeypatch.setattr("goat.live_monitor.market_data.fetch_current_price", lambda t: 85.0)
    monkeypatch.setattr("goat.live_monitor.price_history.fetch_close_history", lambda t, lb: _flat_history())

    result = live_monitor.run_live_monitor(db_conn)
    assert len(result["new_alerts"]) == 1
    assert len(goat_db.get_open_goat_alerts(db_conn)) == 1


def test_run_live_monitor_skips_ticker_with_no_live_price(db_conn, monkeypatch):
    _seed_holding(db_conn, ticker="LULU", bucket="1")
    monkeypatch.setattr("goat.live_monitor.market_hours.is_asx_open", lambda: False)
    monkeypatch.setattr("goat.live_monitor.market_hours.is_us_market_open", lambda: True)
    monkeypatch.setattr("goat.live_monitor.market_data.fetch_current_price", lambda t: None)
    monkeypatch.setattr("goat.live_monitor.price_history.fetch_close_history", lambda t, lb: _flat_history())

    result = live_monitor.run_live_monitor(db_conn)  # must not raise
    assert result["checked_holdings"] == 0


def test_live_and_daily_monitor_share_dedup_no_double_alert(db_conn, monkeypatch):
    _seed_holding(db_conn, ticker="LULU", bucket="1")

    # Live check runs first during the trading day and flags.
    monkeypatch.setattr("goat.live_monitor.market_hours.is_asx_open", lambda: False)
    monkeypatch.setattr("goat.live_monitor.market_hours.is_us_market_open", lambda: True)
    monkeypatch.setattr("goat.live_monitor.market_data.fetch_current_price", lambda t: 85.0)
    monkeypatch.setattr("goat.live_monitor.price_history.fetch_close_history", lambda t, lb: _flat_history())
    live_result = live_monitor.run_live_monitor(db_conn)
    assert len(live_result["new_alerts"]) == 1

    # Later that day the daily EOD monitor runs against the same flagging close --
    # must see the already-open alert and stay quiet (shared dedup key).
    flagging_close = pd.Series(
        [100.0] * goat_config.GOAT_MA_LONG_DAYS + [85.0, 85.0], index=_dates(goat_config.GOAT_MA_LONG_DAYS + 2)
    )
    monkeypatch.setattr("goat.monitor.price_history.fetch_close_history", lambda ticker, lookback_days: flagging_close)
    daily_result = monitor.run_monitor(db_conn)
    assert daily_result["new_alerts"] == []
    assert len(goat_db.get_open_goat_alerts(db_conn)) == 1


class TestCompletedClosesOnly:
    def test_drops_trailing_row_matching_today(self, monkeypatch):
        import goat.live_monitor as lm

        class _FixedDatetime:
            @staticmethod
            def now(tz):
                from datetime import datetime as _dt
                return _dt(2026, 1, 3, 12, 0, tzinfo=tz)

        monkeypatch.setattr(lm, "datetime", _FixedDatetime)
        close = pd.Series([1.0, 2.0, 3.0], index=pd.date_range("2026-01-01", periods=3, freq="D"))
        result = _completed_closes_only(close, "UTC")
        assert len(result) == 2
        assert result.iloc[-1] == 2.0

    def test_leaves_series_unchanged_when_last_date_is_not_today(self, monkeypatch):
        import goat.live_monitor as lm

        class _FixedDatetime:
            @staticmethod
            def now(tz):
                from datetime import datetime as _dt
                return _dt(2026, 1, 10, 12, 0, tzinfo=tz)

        monkeypatch.setattr(lm, "datetime", _FixedDatetime)
        close = pd.Series([1.0, 2.0, 3.0], index=pd.date_range("2026-01-01", periods=3, freq="D"))
        result = _completed_closes_only(close, "UTC")
        assert len(result) == 3

    def test_empty_series_returned_unchanged(self):
        close = pd.Series([], dtype=float)
        result = _completed_closes_only(close, "UTC")
        assert result.empty
