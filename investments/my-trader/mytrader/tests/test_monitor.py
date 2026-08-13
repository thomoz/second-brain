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
def _isolate_snapshot_paths(monkeypatch, tmp_path):
    """run_monitor() calls snapshot.regenerate_all() at the end of every run, which
    writes to config.HOLDINGS_MD_PATH / WATCHLIST_MD_PATH / PENDING_CANDIDATES_MD_PATH.
    Without this, every test in this file silently overwrites the REAL
    holdings.md/watchlist.md/synced-candidates-pending-review.md with test-fixture
    data — discovered 2026-07-19 after a real commit accidentally captured files
    emptied by exactly this gap (test_snapshot.py's own _patch_paths already covered
    this for its own tests; this file never had the equivalent)."""
    import mytrader.config as mt_config
    monkeypatch.setattr(mt_config, "HOLDINGS_MD_PATH", tmp_path / "holdings.md")
    monkeypatch.setattr(mt_config, "WATCHLIST_MD_PATH", tmp_path / "watchlist.md")
    monkeypatch.setattr(mt_config, "PENDING_CANDIDATES_MD_PATH", tmp_path / "synced-candidates-pending-review.md")


@pytest.fixture(autouse=True)
def _no_macro_or_sync_by_default(monkeypatch):
    monkeypatch.setattr("mytrader.monitor.macro_indicators.run_all", lambda: [])
    monkeypatch.setattr("mytrader.monitor.candidate_sync.sync_new_candidates", lambda conn: [])


@pytest.fixture(autouse=True)
def _no_real_econ_calendar_by_default(monkeypatch):
    """run_monitor() calls econ_calendar.fetch_upcoming_releases() every run, which
    hits FRED's live API when FRED_API_KEY is set -- stub it the same way as the
    macro/candidate-sync/gold-outlook fixtures above so these tests stay hermetic."""
    monkeypatch.setattr("mytrader.monitor.econ_calendar.fetch_upcoming_releases", lambda: [])


@pytest.fixture(autouse=True)
def _no_real_gold_outlook_by_default(monkeypatch):
    """run_monitor() calls gold_outlook.build_outlook() every run, which does a
    real yfinance/FRED fetch + full historical backtest when not stubbed --
    global/autouse for the same reason as the macro/candidate-sync fixture above:
    don't let a slow real network call hit every test in this file by default."""
    monkeypatch.setattr("mytrader.monitor.gold_outlook.build_outlook", lambda conn, macro_checks: None)


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
        "opportunities": [],
        "holdings_report": [],
    }
    report = monitor.render_report(result)
    assert "VRTX" in report
    assert "dividend" in report
    assert "Dividend cut" in report
    assert "3 holding(s)" in report
    assert "7 watchlist candidate(s)" in report

    empty = {
        "checked_holdings": 0, "checked_watchlist": 0, "new_alerts": [], "open_alerts": [],
        "macro_checks": [], "synced_candidates": [], "opportunities": [], "holdings_report": [],
    }
    empty_report = monitor.render_report(empty)
    assert "No new material changes." in empty_report
    assert "None." in empty_report
    assert "No holdings tracked." in empty_report


def _holding_entry(**overrides) -> dict:
    base = {
        "ticker": "VRTX", "name": "Vertex Pharmaceuticals", "bucket": "1",
        "qty": 1.0, "avg_price": 100.0,
        "current_price": 110.0, "mkt_value": 110.0, "pnl": 10.0, "pnl_pct": 10.0,
        "pct_of_portfolio": 50.0,
        "mlp": False, "mlp_name": None,
        "open_alerts": [],
        "checks": [
            {"name": "dividend", "verdict": "ok", "detail": "Dividend stable"},
            {"name": "valuation", "verdict": "flag", "detail": "PE 40 above rich threshold"},
        ],
    }
    base.update(overrides)
    return base


def test_render_report_lists_each_holding_with_its_checks():
    """Added 2026-08-13, Shaun: "the monitor report doesn't list my Holdings, or
    give a report for each holding" -- every tracked holding + all its check
    results should render, not just alerts/opportunities."""
    result = {
        "checked_holdings": 1, "checked_watchlist": 0, "new_alerts": [], "open_alerts": [],
        "macro_checks": [], "synced_candidates": [], "opportunities": [],
        "holdings_report": [_holding_entry()],
    }
    report = monitor.render_report(result)
    assert "### Holdings (this run)" in report
    assert "**VRTX** (Vertex Pharmaceuticals, Long-term hold" in report
    assert "[ok] dividend: Dividend stable" in report
    assert "[flag] valuation: PE 40 above rich threshold" in report


def test_render_report_shows_current_price_and_pnl():
    result = {
        "checked_holdings": 1, "checked_watchlist": 0, "new_alerts": [], "open_alerts": [],
        "macro_checks": [], "synced_candidates": [], "opportunities": [],
        "holdings_report": [_holding_entry(qty=40.0, avg_price=19.06, current_price=19.14,
                                             mkt_value=765.6, pnl=3.2, pnl_pct=0.4, pct_of_portfolio=8.9)],
    }
    report = monitor.render_report(result)
    assert "40.0 @ avg $19.06" in report
    assert "now $19.14" in report
    assert "+$3.20" in report
    assert "(+0.4%)" in report
    assert "8.9% of tracked portfolio" in report


def test_render_report_shows_negative_pnl_and_missing_price():
    result = {
        "checked_holdings": 2, "checked_watchlist": 0, "new_alerts": [], "open_alerts": [],
        "macro_checks": [], "synced_candidates": [], "opportunities": [],
        "holdings_report": [
            _holding_entry(ticker="LULU", current_price=121.30, mkt_value=606.35, pnl=-36.70, pnl_pct=-5.7),
            _holding_entry(ticker="OOO", current_price=None, mkt_value=None, pnl=None, pnl_pct=None,
                            pct_of_portfolio=None),
        ],
    }
    report = monitor.render_report(result)
    assert "$-36.70" in report  # same sign convention as snapshot.py's own P&L formatting
    assert "(-5.7%)" in report
    assert "current price unavailable" in report


def test_render_report_shows_bottom_line_summary():
    flagged = _holding_entry(checks=[
        {"name": "valuation", "verdict": "flag", "detail": "rich"},
        {"name": "balance_sheet", "verdict": "flag", "detail": "weak"},
    ])
    clean = _holding_entry(ticker="V", checks=[{"name": "dividend", "verdict": "ok", "detail": "fine"}])
    opportunity = _holding_entry(ticker="AG", checks=[
        {"name": "opportunity", "verdict": "interesting", "detail": "dip"},
    ])
    result = {
        "checked_holdings": 3, "checked_watchlist": 0, "new_alerts": [], "open_alerts": [],
        "macro_checks": [], "synced_candidates": [], "opportunities": [],
        "holdings_report": [flagged, clean, opportunity],
    }
    report = monitor.render_report(result)
    assert "Bottom line: 2 flag(s) active (valuation, balance_sheet) — worth a look." in report
    assert "Bottom line: Nothing notable this run." in report
    assert "Bottom line: 1 opportunity signal(s) (opportunity), no active flags." in report


def test_render_report_shows_open_alerts_inline():
    result = {
        "checked_holdings": 1, "checked_watchlist": 0, "new_alerts": [], "open_alerts": [],
        "macro_checks": [], "synced_candidates": [], "opportunities": [],
        "holdings_report": [_holding_entry(open_alerts=[
            {"check_name": "balance_sheet", "message": "debt/equity too high", "created_at": "2026-08-07T00:00:00"},
        ])],
    }
    report = monitor.render_report(result)
    assert "OPEN ALERT (balance_sheet, since 2026-08-07): debt/equity too high" in report

    no_alerts_result = {
        "checked_holdings": 1, "checked_watchlist": 0, "new_alerts": [], "open_alerts": [],
        "macro_checks": [], "synced_candidates": [], "opportunities": [],
        "holdings_report": [_holding_entry(open_alerts=[])],
    }
    assert "Open alerts: none" in monitor.render_report(no_alerts_result)


def test_render_report_suppresses_not_an_etf_noise_line():
    result = {
        "checked_holdings": 1, "checked_watchlist": 0, "new_alerts": [], "open_alerts": [],
        "macro_checks": [], "synced_candidates": [], "opportunities": [],
        "holdings_report": [_holding_entry(checks=[
            {"name": "dividend", "verdict": "ok", "detail": "Dividend stable"},
            {"name": "etf_mechanics", "verdict": "unknown", "detail": "Not an ETF"},
        ])],
    }
    report = monitor.render_report(result)
    assert "etf_mechanics" not in report
    assert "Not an ETF" not in report


def test_render_report_clarifies_opportunity_signal_on_existing_holding():
    result = {
        "checked_holdings": 1, "checked_watchlist": 0, "new_alerts": [], "open_alerts": [],
        "macro_checks": [], "synced_candidates": [], "opportunities": [],
        "holdings_report": [_holding_entry(checks=[
            {"name": "opportunity", "verdict": "interesting", "detail": "PE cheap"},
        ])],
    }
    report = monitor.render_report(result)
    assert "you already hold this — reads as an add-to-position signal, not a new-buy signal" in report


def test_render_report_shows_mlp_skip_in_holdings_section():
    result = {
        "checked_holdings": 1, "checked_watchlist": 0, "new_alerts": [], "open_alerts": [],
        "macro_checks": [], "synced_candidates": [], "opportunities": [],
        "holdings_report": [
            {
                "ticker": "EPD", "name": "Enterprise Products Partners", "bucket": "1",
                "qty": 10.0, "avg_price": 30.0, "mlp": True,
                "mlp_name": "Enterprise Products Partners L.P.", "checks": [],
            },
        ],
    }
    report = monitor.render_report(result)
    assert "MLP — skipped: Enterprise Products Partners L.P." in report


def test_render_report_lists_upcoming_releases_before_holdings():
    result = {
        "checked_holdings": 0, "checked_watchlist": 0, "new_alerts": [], "open_alerts": [],
        "macro_checks": [], "synced_candidates": [], "opportunities": [], "holdings_report": [],
        "upcoming_releases": [
            {"release_name": "Consumer Price Index", "date": "2026-08-14", "days_until": 1},
            {"release_name": "Employment Situation", "date": "2026-08-13", "days_until": 0},
        ],
    }
    report = monitor.render_report(result)
    assert "### Upcoming Economic Releases (next 48h)" in report
    assert "Consumer Price Index" in report
    assert "tomorrow" in report
    assert "Employment Situation" in report
    assert "today" in report
    assert report.index("### Upcoming Economic Releases") < report.index("### Holdings (this run)")

    empty = {
        "checked_holdings": 0, "checked_watchlist": 0, "new_alerts": [], "open_alerts": [],
        "macro_checks": [], "synced_candidates": [], "opportunities": [], "holdings_report": [],
        "upcoming_releases": [],
    }
    empty_report = monitor.render_report(empty)
    assert "No CPI/PPI/jobs releases scheduled in the next 48 hours." in empty_report


def test_run_monitor_includes_upcoming_releases(db_conn, monkeypatch):
    monkeypatch.setattr(
        "mytrader.monitor.econ_calendar.fetch_upcoming_releases",
        lambda: [{"release_name": "Producer Price Index", "date": "2026-08-14", "days_until": 1}],
    )
    result = monitor.run_monitor(db_conn)
    assert result["upcoming_releases"] == [
        {"release_name": "Producer Price Index", "date": "2026-08-14", "days_until": 1}
    ]


def test_run_monitor_survives_econ_calendar_error(db_conn, monkeypatch):
    def _boom():
        raise RuntimeError("network down")

    monkeypatch.setattr("mytrader.monitor.econ_calendar.fetch_upcoming_releases", _boom)
    result = monitor.run_monitor(db_conn)  # must not raise
    assert result["upcoming_releases"] == []


def test_run_monitor_includes_holdings_report(db_conn, monkeypatch):
    _seed_holding(db_conn)
    monkeypatch.setattr(
        "mytrader.monitor.engine.run_assessment",
        lambda ticker, conn: _fake_result(
            [CheckResult(name="dividend", verdict="ok", detail="Dividend stable")]
        ),
    )
    result = monitor.run_monitor(db_conn)
    assert len(result["holdings_report"]) == 1
    h = result["holdings_report"][0]
    assert h["ticker"] == "VRTX"
    assert h["bucket"] == "1"
    assert h["checks"] == [{"name": "dividend", "verdict": "ok", "detail": "Dividend stable"}]
    # market_data.fetch_ticker_data is stubbed to None by the module-level
    # _no_real_yfinance fixture -- current_price/mkt_value/pnl/pct all degrade to None.
    assert h["current_price"] is None
    assert h["pnl"] is None
    assert h["pct_of_portfolio"] is None
    assert h["open_alerts"] == []


def test_run_monitor_computes_pnl_and_pct_of_portfolio(db_conn, monkeypatch):
    _seed_holding(db_conn, ticker="VRTX", bucket="1")
    monkeypatch.setattr(
        "mytrader.monitor.engine.run_assessment",
        lambda ticker, conn: _fake_result([]),
    )
    monkeypatch.setattr("mytrader.monitor.market_data.fetch_current_price", lambda ticker: 150.0)
    result = monitor.run_monitor(db_conn)
    h = result["holdings_report"][0]
    # _seed_holding uses qty=1.0, avg_price=100.0 -- cost basis 100, mkt value 150.
    assert h["current_price"] == 150.0
    assert h["mkt_value"] == 150.0
    assert h["pnl"] == 50.0
    assert h["pnl_pct"] == 50.0
    assert h["pct_of_portfolio"] == 100.0  # only holding tracked, so it's 100% of the total


def test_run_monitor_attaches_open_alert_to_matching_holding(db_conn, monkeypatch):
    _seed_holding(db_conn, ticker="VRTX", bucket="1")
    monkeypatch.setattr(
        "mytrader.monitor.engine.run_assessment",
        lambda ticker, conn: _fake_result(
            [CheckResult(name="balance_sheet", verdict="flag", detail="debt too high")]
        ),
    )
    result = monitor.run_monitor(db_conn)
    h = result["holdings_report"][0]
    assert len(h["open_alerts"]) == 1
    assert h["open_alerts"][0]["check_name"] == "balance_sheet"
    assert h["open_alerts"][0]["message"] == "debt too high"


def test_write_report_writes_to_configured_path(tmp_path, monkeypatch):
    report_path = tmp_path / "monitor-report.md"
    monkeypatch.setattr("mytrader.monitor.config.MONITOR_REPORT_PATH", report_path)
    result = {
        "checked_holdings": 0, "checked_watchlist": 0, "new_alerts": [], "open_alerts": [],
        "macro_checks": [], "synced_candidates": [], "opportunities": [],
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


def test_run_monitor_persists_macro_snapshot(db_conn, monkeypatch):
    """checks/principles_fit.py reads this cache instead of re-fetching MOVE/FRED/
    ABS/ONS live on every Find call — Monitor is what keeps it fresh, once a day."""
    monkeypatch.setattr(
        "mytrader.monitor.macro_indicators.run_all",
        lambda: [
            CheckResult(name="move_index", verdict="ok", detail="MOVE at 90.0"),
            CheckResult(name="recession_signal", verdict="flag", detail="Recession risk rising"),
        ],
    )
    monitor.run_monitor(db_conn)
    rows = db.get_macro_snapshot(db_conn)
    assert {r["name"] for r in rows} == {"move_index", "recession_signal"}


def test_run_monitor_skips_macro_snapshot_persist_when_indicators_fail(db_conn, monkeypatch):
    monkeypatch.setattr(
        "mytrader.monitor.macro_indicators.run_all",
        lambda: (_ for _ in ()).throw(RuntimeError("network down")),
    )
    monitor.run_monitor(db_conn)  # must not raise
    assert db.get_macro_snapshot(db_conn) == []


def test_run_monitor_calls_candidate_sync_and_includes_result(db_conn, monkeypatch):
    """candidate_sync now runs automatically once per Monitor run again (re-added
    2026-07-19, same day it was first removed) — safe because it only ever writes to
    the separate pending_candidates staging area, never to the watchlist directly."""
    monkeypatch.setattr(
        "mytrader.monitor.candidate_sync.sync_new_candidates",
        lambda conn: [{"ticker": "NVDA", "company_name": "NVIDIA Corp"}],
    )
    result = monitor.run_monitor(db_conn)
    assert result["synced_candidates"] == [{"ticker": "NVDA", "company_name": "NVIDIA Corp"}]


def test_render_report_includes_macro_and_synced_candidates_sections():
    result = {
        "checked_holdings": 0, "checked_watchlist": 0, "new_alerts": [], "open_alerts": [],
        "macro_checks": [{"name": "move_index", "verdict": "ok", "detail": "MOVE index at 90.0"}],
        "synced_candidates": [{"ticker": "NVDA", "company_name": "NVIDIA Corp"}],
        "opportunities": [{"ticker": "NU", "detail": "PE 8.0 at/below cheap threshold (12.0)"}],
        "gold_outlook_available": True,
    }
    report = monitor.render_report(result)
    assert "### Macro Indicators (this run)" in report
    assert "move_index" in report
    assert "### New Candidates Synced (Pending Review)" in report
    assert "NVDA" in report
    assert "synced-candidates-pending-review.md" in report
    assert "### Watchlist Opportunities (this run)" in report
    assert "NU" in report
    assert "PE 8.0" in report
    assert "### Gold Outlook" in report
    assert "gold-outlook.md" in report

    empty = {
        "checked_holdings": 0, "checked_watchlist": 0, "new_alerts": [], "open_alerts": [],
        "macro_checks": [], "synced_candidates": [], "opportunities": [],
        "gold_outlook_available": False,
    }
    empty_report = monitor.render_report(empty)
    assert "Unavailable this run." in empty_report
    assert "None this run." in empty_report
    assert "Nothing standing out this run." in empty_report


def test_run_monitor_includes_gold_outlook_available_when_build_succeeds(db_conn, monkeypatch):
    monkeypatch.setattr(
        "mytrader.monitor.gold_outlook.build_outlook",
        lambda conn, macro_checks: {"as_of": "2026-08-07"},
    )
    written = []
    monkeypatch.setattr("mytrader.monitor.gold_outlook.write_outlook", lambda outlook: written.append(outlook))
    result = monitor.run_monitor(db_conn)
    assert result["gold_outlook_available"] is True
    assert written == [{"as_of": "2026-08-07"}]


def test_run_monitor_gold_outlook_unavailable_when_build_returns_none(db_conn, monkeypatch):
    monkeypatch.setattr("mytrader.monitor.gold_outlook.build_outlook", lambda conn, macro_checks: None)
    result = monitor.run_monitor(db_conn)
    assert result["gold_outlook_available"] is False


def test_run_monitor_survives_gold_outlook_error(db_conn, monkeypatch):
    def _boom(conn, macro_checks):
        raise RuntimeError("network down")

    monkeypatch.setattr("mytrader.monitor.gold_outlook.build_outlook", _boom)
    result = monitor.run_monitor(db_conn)  # must not raise
    assert result["gold_outlook_available"] is False


def test_run_monitor_includes_watchlist_opportunity(db_conn, monkeypatch):
    db.upsert_watchlist_row(
        db_conn, ticker="NU", name="Nu Holdings", asset_type="stock", bucket="1",
        status="discussed",
    )
    monkeypatch.setattr(
        "mytrader.monitor.engine.run_assessment",
        lambda ticker, conn: _fake_result(
            [CheckResult(name="opportunity", verdict="interesting", detail="PE 8.0 at/below cheap threshold")]
        ),
    )
    result = monitor.run_monitor(db_conn)
    assert result["opportunities"] == [{"ticker": "NU", "detail": "PE 8.0 at/below cheap threshold"}]


def test_run_monitor_excludes_non_interesting_opportunity(db_conn, monkeypatch):
    db.upsert_watchlist_row(
        db_conn, ticker="NU", name="Nu Holdings", asset_type="stock", bucket="1",
        status="discussed",
    )
    monkeypatch.setattr(
        "mytrader.monitor.engine.run_assessment",
        lambda ticker, conn: _fake_result(
            [CheckResult(name="opportunity", verdict="ok", detail="No standout positive signal this run")]
        ),
    )
    result = monitor.run_monitor(db_conn)
    assert result["opportunities"] == []


def test_run_monitor_holdings_never_produce_opportunities(db_conn, monkeypatch):
    """Opportunity signals only make sense for things you don't yet own — a holding
    with an "interesting" opportunity check result should never surface in the
    Watchlist Opportunities section."""
    _seed_holding(db_conn)
    monkeypatch.setattr(
        "mytrader.monitor.engine.run_assessment",
        lambda ticker, conn: _fake_result(
            [CheckResult(name="opportunity", verdict="interesting", detail="PE 8.0 at/below cheap threshold")]
        ),
    )
    result = monitor.run_monitor(db_conn)
    assert result["opportunities"] == []


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
