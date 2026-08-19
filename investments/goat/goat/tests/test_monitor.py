from __future__ import annotations

import sys
import types

import pandas as pd
from mytrader import db as mt_db

from goat import config as goat_config, db as goat_db, monitor


def _dates(n: int, start: str = "2026-01-01") -> pd.DatetimeIndex:
    return pd.date_range(start, periods=n, freq="D")


def _flagging_series(flat_price: float = 100.0, drop_price: float = 80.0) -> pd.Series:
    prices = [flat_price] * 150 + [drop_price, drop_price]
    return pd.Series(prices, index=_dates(len(prices)))


def _non_flagging_series(flat_price: float = 100.0) -> pd.Series:
    # 150 flat days establish the MA, then two days slightly ABOVE it -- with
    # GOAT_150DMA_FLAG_PCT at 0.0 (Shaun's 2026-08-16 override), a price sitting
    # exactly ON the MA now also qualifies as a flag ("at or below"), so this
    # must be strictly above flat_price to represent genuine recovery.
    prices = [flat_price] * 150 + [flat_price + 0.5, flat_price + 0.5]
    return pd.Series(prices, index=_dates(len(prices)))


def _seed_holding(conn, ticker="VRTX", bucket="1"):
    mt_db.upsert_holding(
        conn, ticker=ticker, name="Vertex Pharmaceuticals", asset_type="stock",
        bucket=bucket, qty=1.0, avg_price=100.0,
    )


def _seed_watchlist(conn, ticker="MCD", bucket="1", status="raw"):
    mt_db.upsert_watchlist_row(
        conn, ticker=ticker, name="McDonald's Corp", asset_type="stock",
        bucket=bucket, status=status,
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


def test_run_monitor_creates_new_alert_for_raw_watchlist_ticker(db_conn, monkeypatch):
    """Shaun 2026-08-19: watchlist coverage must include status="raw" rows (not
    just "discussed", unlike mytrader's own Monitor) so he can be prompted to
    discuss a not-yet-vetted candidate the moment it breaks its 150DMA."""
    _seed_watchlist(db_conn, ticker="MCD", status="raw")
    monkeypatch.setattr(
        "goat.monitor.price_history.fetch_close_history",
        lambda ticker, lookback_days: _flagging_series(),
    )
    result = monitor.run_monitor(db_conn)
    assert len(result["new_alerts"]) == 1
    assert result["new_alerts"][0]["ticker"] == "MCD"
    assert result["new_alerts"][0]["source_table"] == "watchlist"
    assert result["checked_watchlist"] == 1
    assert result["checked_holdings"] == 0


def test_run_monitor_dedups_holding_and_watchlist_alerts_independently(db_conn, monkeypatch):
    """A ticker held AND separately watchlisted (e.g. re-added at a different
    bucket) must not have its watchlist alert suppressed just because the
    holdings alert already fired, or vice versa -- source_table keeps the two
    dedup states independent."""
    _seed_holding(db_conn, ticker="VRTX", bucket="1")
    _seed_watchlist(db_conn, ticker="VRTX", bucket="2", status="raw")
    monkeypatch.setattr(
        "goat.monitor.price_history.fetch_close_history",
        lambda ticker, lookback_days: _flagging_series(),
    )
    result = monitor.run_monitor(db_conn)
    assert len(result["new_alerts"]) == 2
    assert {a["source_table"] for a in result["new_alerts"]} == {"holdings", "watchlist"}
    assert len(result["open_alerts"]) == 2


def test_run_monitor_watchlist_alert_stays_quiet_on_repeat_flag(db_conn, monkeypatch):
    _seed_watchlist(db_conn, ticker="MCD", status="discussed")
    monkeypatch.setattr(
        "goat.monitor.price_history.fetch_close_history",
        lambda ticker, lookback_days: _flagging_series(),
    )
    monitor.run_monitor(db_conn)
    result = monitor.run_monitor(db_conn)
    assert result["new_alerts"] == []
    assert len(result["open_alerts"]) == 1


def test_render_report_lists_new_and_open_alerts():
    result = {
        "checked_holdings": 3,
        "checked_watchlist": 5,
        "new_alerts": [
            {"ticker": "VRTX", "source_table": "holdings", "message": "closed 8.0% below its 150-day MA"},
            {"ticker": "MCD", "source_table": "watchlist", "message": "closed 9.0% below its 150-day MA"},
        ],
        "open_alerts": [
            {"ticker": "VRTX", "source_table": "holdings", "message": "closed 8.0% below its 150-day MA",
             "created_at": "2026-08-11T00:00:00+00:00"}
        ],
    }
    report = monitor.render_report(result)
    assert "VRTX" in report
    assert "8.0% below" in report
    assert "3 holding(s)" in report
    assert "5 watchlist ticker(s)" in report
    assert "MCD" in report
    assert "(watchlist)" in report
    assert "(holdings)" in report

    empty = {"checked_holdings": 0, "checked_watchlist": 0, "new_alerts": [], "open_alerts": []}
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


def _fake_notifications_module(toast_calls, whatsapp_calls):
    fake_module = types.ModuleType("notifications")
    fake_module.send_toast_notification = lambda *a, **k: toast_calls.append((a, k))
    fake_module.send_whatsapp_notification = lambda *a, **k: whatsapp_calls.append((a, k))
    return fake_module


def test_maybe_notify_skips_when_no_new_alerts(monkeypatch):
    toast_calls, whatsapp_calls = [], []
    monkeypatch.setitem(sys.modules, "notifications", _fake_notifications_module(toast_calls, whatsapp_calls))

    monitor.maybe_notify({"new_alerts": []})
    assert toast_calls == []
    assert whatsapp_calls == []


def test_maybe_notify_calls_toast_when_new_alerts_present(monkeypatch):
    toast_calls, whatsapp_calls = [], []
    monkeypatch.setitem(sys.modules, "notifications", _fake_notifications_module(toast_calls, whatsapp_calls))

    monitor.maybe_notify({"new_alerts": [{"ticker": "VRTX", "message": "closed 8.0% below its 150-day MA"}]})
    assert len(toast_calls) == 1
    args, kwargs = toast_calls[0]
    assert any("1" in str(a) for a in args)


def test_maybe_notify_fires_on_sector_candidates_alone(monkeypatch):
    toast_calls, whatsapp_calls = [], []
    monkeypatch.setitem(sys.modules, "notifications", _fake_notifications_module(toast_calls, whatsapp_calls))

    candidates = [
        {"ticker": "XLK", "sector_label": "Technology", "detail": "XLK breakout detail"},
        {"ticker": "XLI", "sector_label": "Industrials", "detail": "XLI breakout detail"},
    ]
    monitor.maybe_notify({"new_alerts": []}, new_candidates=candidates)
    assert len(toast_calls) == 1
    assert len(whatsapp_calls) == 1


def test_maybe_notify_whatsapp_message_names_ticker_and_sector_for_candidates(monkeypatch):
    """Regression test for the 2026-08-17 gap: a candidate notification used to
    say only "N new sector breakout candidate(s)" with no way to tell which
    ticker/sector fired, forcing a manual check of the report file."""
    toast_calls, whatsapp_calls = [], []
    monkeypatch.setitem(sys.modules, "notifications", _fake_notifications_module(toast_calls, whatsapp_calls))

    candidates = [{"ticker": "XLI", "sector_label": "Industrials", "detail": "crossed above its 50-day MA"}]
    monitor.maybe_notify({"new_alerts": []}, new_candidates=candidates)
    (message,), _kwargs = whatsapp_calls[0]
    assert "XLI" in message
    assert "Industrials" in message
    assert "crossed above its 50-day MA" in message


def test_maybe_notify_skips_when_no_candidates_and_no_alerts():
    monitor.maybe_notify({"new_alerts": []}, new_candidates=[])  # must not raise, no notification module needed


def test_maybe_notify_sends_whatsapp_with_ticker_detail(monkeypatch):
    toast_calls, whatsapp_calls = [], []
    monkeypatch.setitem(sys.modules, "notifications", _fake_notifications_module(toast_calls, whatsapp_calls))

    monitor.maybe_notify({"new_alerts": [{"ticker": "VRTX", "message": "closed 8.0% below its 150-day MA"}]})
    assert len(whatsapp_calls) == 1
    (message,), _kwargs = whatsapp_calls[0]
    assert "VRTX" in message
    assert "150-day MA" in message


def test_maybe_notify_labels_watchlist_alerts_distinctly_from_holdings(monkeypatch):
    toast_calls, whatsapp_calls = [], []
    monkeypatch.setitem(sys.modules, "notifications", _fake_notifications_module(toast_calls, whatsapp_calls))

    monitor.maybe_notify({
        "new_alerts": [
            {"ticker": "VRTX", "source_table": "holdings", "message": "closed 8.0% below its 150-day MA"},
            {"ticker": "MCD", "source_table": "watchlist", "message": "closed 9.0% below its 150-day MA"},
        ],
    })
    (message,), _kwargs = whatsapp_calls[0]
    assert "2 ticker(s)" in message
    assert "VRTX (holdings)" in message
    assert "MCD (watchlist)" in message


def test_maybe_notify_uses_custom_alert_label(monkeypatch):
    toast_calls, whatsapp_calls = [], []
    monkeypatch.setitem(sys.modules, "notifications", _fake_notifications_module(toast_calls, whatsapp_calls))

    monitor.maybe_notify(
        {"new_alerts": [{"ticker": "VRTX", "message": "sold $2,000,000 of VRTX"}]},
        alert_label="insider P/S filing(s) on current holdings",
    )
    (message,), _kwargs = whatsapp_calls[0]
    assert "insider P/S filing(s) on current holdings" in message
    assert "below 150DMA exit threshold" not in message


def test_maybe_notify_uses_custom_candidate_label(monkeypatch):
    """Regression test for the 2026-08-18 fix: candidate_label used to be
    hardcoded to "sector breakout candidate(s)" regardless of what actually
    triggered the notify (e.g. insider discovery buys, heartbeat picks) --
    see maybe_notify's docstring."""
    toast_calls, whatsapp_calls = [], []
    monkeypatch.setitem(sys.modules, "notifications", _fake_notifications_module(toast_calls, whatsapp_calls))

    candidates = [{"ticker": "ACME", "sector_label": "Insider Buy", "detail": "bought $30,000 of ACME"}]
    monitor.maybe_notify(
        {"new_alerts": []}, new_candidates=candidates,
        candidate_label="new insider discovery candidate(s)",
    )
    (message,), _kwargs = whatsapp_calls[0]
    assert "new insider discovery candidate(s)" in message
    assert "sector breakout candidate" not in message


# --- Phase 2: sector rotation scan --------------------------------------------

_FAKE_SECTOR_ETFS = {"XLK": "Technology", "XLF": "Financials"}


def _breakout_series() -> pd.Series:
    ma_days = goat_config.GOAT_SECTOR_MA_SHORT_DAYS
    lead_in = ma_days + goat_config.GOAT_SECTOR_SLOPE_LOOKBACK_DAYS + 20
    prices = [90.0] * lead_in + [130.0] * 2
    return pd.Series(prices, index=_dates(len(prices)))


def _quiet_sector_series() -> pd.Series:
    n = goat_config.GOAT_SECTOR_MA_SHORT_DAYS + goat_config.GOAT_SECTOR_SLOPE_LOOKBACK_DAYS + 30
    return pd.Series([100.0] * n, index=_dates(n))


def _patch_sector_universe(monkeypatch):
    monkeypatch.setattr(goat_config, "GOAT_SECTOR_ETFS", _FAKE_SECTOR_ETFS)


def _patch_sector_fetch(monkeypatch, breakout_ticker="XLK"):
    def _fake_fetch(ticker, lookback_days):
        return _breakout_series() if ticker == breakout_ticker else _quiet_sector_series()

    monkeypatch.setattr("goat.sector_rotation.price_history.fetch_close_history", _fake_fetch)


def test_run_sector_scan_stages_new_candidate_on_fresh_breakout(db_conn, monkeypatch):
    _patch_sector_universe(monkeypatch)
    _patch_sector_fetch(monkeypatch)

    result = monitor.run_sector_scan(db_conn)
    assert len(result["new_candidates"]) == 1
    assert result["new_candidates"][0]["ticker"] == "XLK"
    assert goat_db.get_goat_pending_candidate(db_conn, "XLK") is not None


def test_run_sector_scan_skips_ticker_already_a_holding(db_conn, monkeypatch):
    _patch_sector_universe(monkeypatch)
    _patch_sector_fetch(monkeypatch)
    mt_db.upsert_holding(
        db_conn, ticker="XLK", name="Technology Select Sector SPDR", asset_type="etf",
        bucket="1", qty=1.0, avg_price=100.0,
    )

    result = monitor.run_sector_scan(db_conn)
    assert result["new_candidates"] == []
    assert goat_db.get_goat_pending_candidate(db_conn, "XLK") is None


def test_run_sector_scan_skips_ticker_already_in_watchlist(db_conn, monkeypatch):
    _patch_sector_universe(monkeypatch)
    _patch_sector_fetch(monkeypatch)
    mt_db.upsert_watchlist_row(
        db_conn, ticker="XLK", name="Technology Select Sector SPDR", asset_type="etf",
        bucket="unassigned",
    )

    result = monitor.run_sector_scan(db_conn)
    assert result["new_candidates"] == []
    assert goat_db.get_goat_pending_candidate(db_conn, "XLK") is None


def test_run_sector_scan_stays_quiet_on_repeat_run(db_conn, monkeypatch):
    _patch_sector_universe(monkeypatch)
    _patch_sector_fetch(monkeypatch)

    monitor.run_sector_scan(db_conn)
    result = monitor.run_sector_scan(db_conn)
    assert result["new_candidates"] == []
    assert len(result["pending_candidates"]) == 1


def test_render_sector_ranking_report_lists_all_rows():
    result = {
        "ranking": [
            {"rank": 1, "ticker": "XLK", "sector_label": "Technology", "return_pct": 12.3, "rising": True},
            {"rank": 2, "ticker": "XLF", "sector_label": "Financials", "return_pct": None, "rising": None},
        ],
    }
    report = monitor.render_sector_ranking_report(result)
    assert "XLK" in report
    assert "+12.3%" in report
    assert "XLF" in report


def test_render_sector_candidates_report_lists_pending_rows():
    result = {
        "pending_candidates": [
            {"ticker": "XLK", "sector_label": "Technology", "signal_detail": "breakout",
             "flagged_at": "2026-08-11T00:00:00+00:00"},
        ],
    }
    report = monitor.render_sector_candidates_report(result)
    assert "XLK" in report
    assert "breakout" in report


def test_promote_workflow_writes_to_mytrader_watchlist_and_clears_pending(db_conn):
    """Mirrors main.py's cmd_promote_candidate logic at the db/function level --
    cmd_promote_candidate itself owns its own connection lifecycle and isn't
    trivially testable against a fixture connection (matches this project's
    existing convention of not testing argparse-wired cmd_* functions directly)."""
    goat_db.insert_goat_pending_candidate(
        db_conn, ticker="XLK", sector_label="Technology",
        signal_detail="XLK crossed above its 50-day MA 2 trading day(s) ago",
    )
    pending = goat_db.get_goat_pending_candidate(db_conn, "XLK")
    mt_db.upsert_watchlist_row(
        db_conn, ticker="XLK", name=None, asset_type="etf", bucket="unassigned",
        status="raw", notes=f"Goat-approved sector rotation candidate — {pending['signal_detail']}",
        source="goat_sector_rotation",
    )
    goat_db.delete_goat_pending_candidate(db_conn, "XLK")

    row = mt_db.get_watchlist_row(db_conn, "XLK")
    assert row is not None
    assert row["source"] == "goat_sector_rotation"
    assert "Goat-approved" in row["notes"]
    assert goat_db.get_goat_pending_candidate(db_conn, "XLK") is None


def test_dismiss_workflow_removes_pending_only_no_watchlist_write(db_conn):
    goat_db.insert_goat_pending_candidate(
        db_conn, ticker="XLK", sector_label="Technology", signal_detail="detail",
    )
    count = goat_db.delete_goat_pending_candidate(db_conn, "XLK")
    assert count == 1
    assert goat_db.get_goat_pending_candidate(db_conn, "XLK") is None
    assert mt_db.get_watchlist_row(db_conn, "XLK") is None
