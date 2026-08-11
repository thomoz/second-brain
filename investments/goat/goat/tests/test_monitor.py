from __future__ import annotations

import sys
import types

import pandas as pd
from mytrader import db as mt_db

from goat import db as goat_db, monitor


def _dates(n: int, start: str = "2026-01-01") -> pd.DatetimeIndex:
    return pd.date_range(start, periods=n, freq="D")


def _flagging_series(flat_price: float = 100.0, drop_price: float = 80.0) -> pd.Series:
    prices = [flat_price] * 150 + [drop_price, drop_price]
    return pd.Series(prices, index=_dates(len(prices)))


def _non_flagging_series(flat_price: float = 100.0) -> pd.Series:
    prices = [flat_price] * 152
    return pd.Series(prices, index=_dates(len(prices)))


def _seed_holding(conn, ticker="VRTX", bucket="1"):
    mt_db.upsert_holding(
        conn, ticker=ticker, name="Vertex Pharmaceuticals", asset_type="stock",
        bucket=bucket, qty=1.0, avg_price=100.0,
    )


def test_run_monitor_creates_new_alert_for_first_flag(db_conn, monkeypatch):
    _seed_holding(db_conn)
    monkeypatch.setattr(
        "goat.monitor.price_history.fetch_close_history",
        lambda ticker, lookback_days: _flagging_series(),
    )
    result = monitor.run_monitor(db_conn)
    assert len(result["new_alerts"]) == 1
    assert len(goat_db.get_open_goat_alerts(db_conn)) == 1
    assert result["checked_holdings"] == 1


def test_run_monitor_stays_quiet_on_repeat_flag(db_conn, monkeypatch):
    _seed_holding(db_conn)
    monkeypatch.setattr(
        "goat.monitor.price_history.fetch_close_history",
        lambda ticker, lookback_days: _flagging_series(),
    )
    monitor.run_monitor(db_conn)
    result = monitor.run_monitor(db_conn)
    assert result["new_alerts"] == []
    assert len(result["open_alerts"]) == 1


def test_run_monitor_auto_acknowledges_on_recovery(db_conn, monkeypatch):
    _seed_holding(db_conn)
    monkeypatch.setattr(
        "goat.monitor.price_history.fetch_close_history",
        lambda ticker, lookback_days: _flagging_series(),
    )
    monitor.run_monitor(db_conn)
    monkeypatch.setattr(
        "goat.monitor.price_history.fetch_close_history",
        lambda ticker, lookback_days: _non_flagging_series(),
    )
    result = monitor.run_monitor(db_conn)
    assert result["open_alerts"] == []
    assert goat_db.get_open_goat_alerts(db_conn) == []


def test_run_monitor_skips_ticker_with_no_price_history(db_conn, monkeypatch):
    _seed_holding(db_conn, ticker="VRTX", bucket="1")
    _seed_holding(db_conn, ticker="MSFT", bucket="1")

    def _fake_fetch(ticker, lookback_days):
        return None if ticker == "VRTX" else _non_flagging_series()

    monkeypatch.setattr("goat.monitor.price_history.fetch_close_history", _fake_fetch)
    result = monitor.run_monitor(db_conn)  # must not raise
    assert result["checked_holdings"] == 1


def test_render_report_lists_new_and_open_alerts():
    result = {
        "checked_holdings": 3,
        "new_alerts": [{"ticker": "VRTX", "message": "closed 8.0% below its 150-day MA"}],
        "open_alerts": [
            {"ticker": "VRTX", "message": "closed 8.0% below its 150-day MA",
             "created_at": "2026-08-11T00:00:00+00:00"}
        ],
    }
    report = monitor.render_report(result)
    assert "VRTX" in report
    assert "8.0% below" in report
    assert "3 holding(s)" in report

    empty = {"checked_holdings": 0, "new_alerts": [], "open_alerts": []}
    empty_report = monitor.render_report(empty)
    assert "No new material changes." in empty_report
    assert "None." in empty_report


def test_write_report_writes_to_configured_path(tmp_path, monkeypatch):
    report_path = tmp_path / "monitor-report.md"
    monkeypatch.setattr("goat.monitor.config.GOAT_MONITOR_REPORT_PATH", report_path)
    result = {"checked_holdings": 0, "new_alerts": [], "open_alerts": []}
    monitor.write_report(result)
    assert report_path.exists()
    assert report_path.read_text(encoding="utf-8") == monitor.render_report(result)


def test_maybe_notify_skips_when_no_new_alerts(monkeypatch):
    calls = []
    fake_module = types.ModuleType("notifications")
    fake_module.send_toast_notification = lambda *a, **k: calls.append((a, k))
    monkeypatch.setitem(sys.modules, "notifications", fake_module)

    monitor.maybe_notify({"new_alerts": []})
    assert calls == []


def test_maybe_notify_calls_toast_when_new_alerts_present(monkeypatch):
    calls = []
    fake_module = types.ModuleType("notifications")
    fake_module.send_toast_notification = lambda *a, **k: calls.append((a, k))
    monkeypatch.setitem(sys.modules, "notifications", fake_module)

    monitor.maybe_notify({"new_alerts": [{"ticker": "VRTX", "message": "closed 8.0% below its 150-day MA"}]})
    assert len(calls) == 1
    args, kwargs = calls[0]
    assert any("1" in str(a) for a in args)
