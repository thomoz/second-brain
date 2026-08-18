from __future__ import annotations

from mytrader.checks import CheckResult

from fourteen_crash_signals_daily_check import config, report


def _make_results():
    credit_spread_result = CheckResult(name="credit_spread_streak", verdict="ok", detail="spread ok", data={})
    margin_debt_result = CheckResult(name="margin_debt_growth", verdict="ok", detail="margin ok", data={})
    insider_trend_results = [
        CheckResult(name="insider_trend", verdict="flag", detail="NVDA selling", data={"ticker": "NVDA"}),
    ]
    market_cap_result = CheckResult(name="market_cap_milestone", verdict="flag", detail="NVDA leads", data={"rung": 5_000_000_000_000})
    return credit_spread_result, margin_debt_result, insider_trend_results, market_cap_result


def test_render_signals_report_includes_all_14_marker_numbers():
    credit_spread_result, margin_debt_result, insider_trend_results, market_cap_result = _make_results()
    output = report.render_signals_report([], credit_spread_result, margin_debt_result, insider_trend_results, market_cap_result)
    for n in range(1, 15):
        assert f"| {n} |" in output, f"marker {n} missing from report"


def test_render_signals_report_placeholder_rows_reference_handoff_doc():
    credit_spread_result, margin_debt_result, insider_trend_results, market_cap_result = _make_results()
    output = report.render_signals_report([], credit_spread_result, margin_debt_result, insider_trend_results, market_cap_result)
    # +1 for the report header's own "Per-marker source" line, beyond one per placeholder row
    assert output.count("14-signals-crash-warning-handoff.md") == len(report._PLACEHOLDER_MARKERS) + 1


def test_render_signals_report_shows_hot_watchlist_table():
    credit_spread_result, margin_debt_result, insider_trend_results, market_cap_result = _make_results()
    watchlist = [{"rank": 1, "ticker": "NVDA", "sector_label": "Technology", "market_cap": 5_000_000_000_000}]
    output = report.render_signals_report(watchlist, credit_spread_result, margin_debt_result, insider_trend_results, market_cap_result)
    assert "NVDA" in output
    assert "$5000B" in output


def test_render_signals_report_empty_watchlist_message():
    credit_spread_result, margin_debt_result, insider_trend_results, market_cap_result = _make_results()
    output = report.render_signals_report([], credit_spread_result, margin_debt_result, insider_trend_results, market_cap_result)
    assert "No hot-watchlist companies resolved this run" in output


def test_write_signals_report_writes_file():
    credit_spread_result, margin_debt_result, insider_trend_results, market_cap_result = _make_results()
    report.write_signals_report([], credit_spread_result, margin_debt_result, insider_trend_results, market_cap_result)
    assert config.SIGNALS_REPORT_PATH.exists()
    assert "14 Crash Signals" in config.SIGNALS_REPORT_PATH.read_text(encoding="utf-8")
