from __future__ import annotations

import sys
import types

import pytest

from mytrader import db, monitor
from mytrader.checks import CheckResult


@pytest.fixture(autouse=True)
def _no_real_yfinance(monkeypatch):
    """run_monitor() calls snapshot.regenerate_all() at the end of every run, which
    hits market_data.fetch_ticker_data for real unless stubbed — mirrors
    test_snapshot.py's own mocking pattern so these tests stay hermetic and fast."""
    monkeypatch.setattr("mytrader.market_data.fetch_ticker_data", lambda ticker: None)


@pytest.fixture(autouse=True)
def _no_macro_or_sync_by_default(monkeypatch):
    monkeypatch.setattr("mytrader.monitor.macro_indicators.run_all", lambda: [])
    monkeypatch.setattr("mytrader.monitor.candidate_sync.sync_new_candidates", lambda conn: [])


def _fake_result(checks: list[CheckResult]) -> dict:
    return {
        "ticker": "VRTX",
        "excluded": False,
        "exclusion_reason": None,
        "checks": checks,
        "briefs_finance_score": None,
        "data_available": True,
    }


def _seed_holding(conn, ticker="VRTX", bucket="1"):
    db.upsert_holding(
        conn, ticker=ticker, name="Vertex Pharmaceuticals", asset_type="stock",
        bucket=bucket, qty=1.0, avg_price=100.0,
    )


def test_run_monitor_creates_new_alert_for_first_flag(db_conn, monkeypatch):
    _seed_holding(db_conn)
    monkeypatch.setattr(
        "mytrader.monitor.engine.run_assessment",
        lambda ticker, conn: _fake_result(
            [CheckResult(name="dividend", verdict="flag", detail="Dividend cut")]
        ),
    )
    result = monitor.run_monitor(db_conn)
    assert len(result["new_alerts"]) == 1
    assert len(db.get_open_alerts(db_conn)) == 1


def test_run_monitor_stays_quiet_on_repeat_flag(db_conn, monkeypatch):
    _seed_holding(db_conn)
    monkeypatch.setattr(
        "mytrader.monitor.engine.run_assessment",
        lambda ticker, conn: _fake_result(
            [CheckResult(name="dividend", verdict="flag", detail="Dividend cut")]
        ),
    )
    monitor.run_monitor(db_conn)
    result = monitor.run_monitor(db_conn)
    assert result["new_alerts"] == []
    assert len(result["open_alerts"]) == 1


def test_run_monitor_acknowledges_when_flag_clears(db_conn, monkeypatch):
    _seed_holding(db_conn)
    monkeypatch.setattr(
        "mytrader.monitor.engine.run_assessment",
        lambda ticker, conn: _fake_result(
            [CheckResult(name="dividend", verdict="flag", detail="Dividend cut")]
        ),
    )
    monitor.run_monitor(db_conn)
    monkeypatch.setattr(
        "mytrader.monitor.engine.run_assessment",
        lambda ticker, conn: _fake_result(
            [CheckResult(name="dividend", verdict="ok", detail="Dividend stable")]
        ),
    )
    monitor.run_monitor(db_conn)
    assert db.get_open_alerts(db_conn) == []


def test_run_monitor_reflags_after_acknowledge(db_conn, monkeypatch):
    _seed_holding(db_conn)
    flag_check = lambda ticker, conn: _fake_result(  # noqa: E731
        [CheckResult(name="dividend", verdict="flag", detail="Dividend cut")]
    )
    ok_check = lambda ticker, conn: _fake_result(  # noqa: E731
        [CheckResult(name="dividend", verdict="ok", detail="Dividend stable")]
    )
    monkeypatch.setattr("mytrader.monitor.engine.run_assessment", flag_check)
    monitor.run_monitor(db_conn)  # run 1: flag
    monkeypatch.setattr("mytrader.monitor.engine.run_assessment", ok_check)
    monitor.run_monitor(db_conn)  # run 2: clear
    monkeypatch.setattr("mytrader.monitor.engine.run_assessment", flag_check)
    result = monitor.run_monitor(db_conn)  # run 3: reflag

    assert len(result["new_alerts"]) == 1
    rows = db_conn.execute(
        "SELECT * FROM alert_history WHERE ticker = ? AND check_name = ?",
        ("VRTX", "dividend"),
    ).fetchall()
    assert len(rows) == 2
    acknowledged = [r["acknowledged"] for r in rows]
    assert sorted(acknowledged) == [0, 1]


def test_run_monitor_only_checks_discussed_watchlist_rows(db_conn, monkeypatch):
    db.upsert_watchlist_row(
        db_conn, ticker="SCHD", name="Schwab Dividend", asset_type="etf", bucket="1",
        status="raw",
    )
    db.upsert_watchlist_row(
        db_conn, ticker="HDV", name="iShares High Div", asset_type="etf", bucket="1",
        status="discussed",
    )
    monkeypatch.setattr(
        "mytrader.monitor.engine.run_assessment",
        lambda ticker, conn: _fake_result([]),
    )
    result = monitor.run_monitor(db_conn)
    assert result["checked_watchlist"] == 1


def test_run_monitor_calls_touch_checked(db_conn, monkeypatch):
    _seed_holding(db_conn)
    monkeypatch.setattr(
        "mytrader.monitor.engine.run_assessment",
        lambda ticker, conn: _fake_result([]),
    )
    monitor.run_monitor(db_conn)
    row = db.get_holding_row(db_conn, "VRTX", "1")
    assert row["last_checked_at"] is not None


def test_render_report_lists_new_and_open_alerts():
    result = {
        "checked_holdings": 3,
        "checked_watchlist": 7,
        "new_alerts": [
            {"ticker": "VRTX", "source_table": "holdings", "check_name": "dividend", "message": "Dividend cut"}
        ],
        "open_alerts": [
            {
                "ticker": "VRTX", "source_table": "holdings", "check_name": "dividend",
                "message": "Dividend cut", "created_at": "2026-07-19T00:00:00+00:00",
            }
        ],
        "macro_checks": [],
        "synced_candidates": [],
    }
    report = monitor.render_report(result)
    assert "VRTX" in report
    assert "dividend" in report
    assert "Dividend cut" in report
    assert "3 holding(s)" in report
    assert "7 watchlist candidate(s)" in report

    empty = {
        "checked_holdings": 0, "checked_watchlist": 0, "new_alerts": [], "open_alerts": [],
        "macro_checks": [], "synced_candidates": [],
    }
    empty_report = monitor.render_report(empty)
    assert "No new material changes." in empty_report
    assert "None." in empty_report


def test_write_report_writes_to_configured_path(tmp_path, monkeypatch):
    report_path = tmp_path / "monitor-report.md"
    monkeypatch.setattr("mytrader.monitor.config.MONITOR_REPORT_PATH", report_path)
    result = {
        "checked_holdings": 0, "checked_watchlist": 0, "new_alerts": [], "open_alerts": [],
        "macro_checks": [], "synced_candidates": [],
    }
    monitor.write_report(result)
    assert report_path.exists()
    assert report_path.read_text(encoding="utf-8") == monitor.render_report(result)


def test_run_monitor_includes_macro_alert_for_first_flag(db_conn, monkeypatch):
    monkeypatch.setattr(
        "mytrader.monitor.macro_indicators.run_all",
        lambda: [CheckResult(name="recession_signal", verdict="flag", detail="Recession risk rising")],
    )
    result = monitor.run_monitor(db_conn)
    assert len(result["new_alerts"]) == 1
    assert result["new_alerts"][0]["ticker"] == "MACRO"
    assert result["new_alerts"][0]["source_table"] == "macro"


def test_run_monitor_macro_alert_stays_quiet_on_repeat_flag(db_conn, monkeypatch):
    monkeypatch.setattr(
        "mytrader.monitor.macro_indicators.run_all",
        lambda: [CheckResult(name="recession_signal", verdict="flag", detail="Recession risk rising")],
    )
    monitor.run_monitor(db_conn)
    result = monitor.run_monitor(db_conn)
    assert result["new_alerts"] == []
    assert len(result["open_alerts"]) == 1


def test_run_monitor_includes_synced_candidates_in_result(db_conn, monkeypatch):
    monkeypatch.setattr(
        "mytrader.monitor.candidate_sync.sync_new_candidates",
        lambda conn: [{"ticker": "NVDA", "company_name": "NVIDIA Corp"}],
    )
    result = monitor.run_monitor(db_conn)
    assert result["synced_candidates"] == [{"ticker": "NVDA", "company_name": "NVIDIA Corp"}]


def test_render_report_includes_macro_and_candidate_sections():
    result = {
        "checked_holdings": 0, "checked_watchlist": 0, "new_alerts": [], "open_alerts": [],
        "macro_checks": [{"name": "move_index", "verdict": "ok", "detail": "MOVE index at 90.0"}],
        "synced_candidates": [{"ticker": "NVDA", "company_name": "NVIDIA Corp"}],
    }
    report = monitor.render_report(result)
    assert "### Macro Indicators (this run)" in report
    assert "move_index" in report
    assert "### New Candidates Synced From Briefs Finance" in report
    assert "NVDA" in report

    empty = {
        "checked_holdings": 0, "checked_watchlist": 0, "new_alerts": [], "open_alerts": [],
        "macro_checks": [], "synced_candidates": [],
    }
    empty_report = monitor.render_report(empty)
    assert "Unavailable this run." in empty_report
    assert "None this run." in empty_report


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

    monitor.maybe_notify({"new_alerts": [{"ticker": "VRTX", "source_table": "holdings",
                                           "check_name": "dividend", "message": "Dividend cut"}]})
    assert len(calls) == 1
    args, kwargs = calls[0]
    assert any("1" in str(a) for a in args)
