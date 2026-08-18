from __future__ import annotations

from mytrader.checks import CheckResult

from fourteen_crash_signals_daily_check import config, report


def _make_results():
    credit_spread_result = CheckResult(name="credit_spread_streak", verdict="ok", detail="spread ok", data={"watch": False})
    margin_debt_result = CheckResult(name="margin_debt_growth", verdict="ok", detail="margin ok", data={})
    insider_trend_results = [
        CheckResult(name="insider_trend", verdict="flag", detail="NVDA selling", data={"ticker": "NVDA"}),
    ]
    market_cap_result = CheckResult(name="market_cap_milestone", verdict="flag", detail="NVDA leads", data={"rung": 5_000_000_000_000})
    lease_commitment_results = [
        CheckResult(name="lease_commitments", verdict="ok", detail="ORCL leases ok", data={"ticker": "ORCL"}),
    ]
    capex_cashflow_results = [
        CheckResult(name="capex_cashflow", verdict="flag", detail="ORCL FCF negative", data={"ticker": "ORCL"}),
    ]
    super_bowl_result = CheckResult(name="super_bowl_signal", verdict="unknown", detail="44 days away", data={"days_left": 44})
    credit_spread_issuer_results = [
        CheckResult(name="credit_spread_issuer", verdict="ok", detail="ORCL spread ok", data={"ticker": "ORCL"}),
    ]
    return (
        credit_spread_result, margin_debt_result, insider_trend_results, market_cap_result,
        lease_commitment_results, capex_cashflow_results, super_bowl_result, credit_spread_issuer_results,
    )


def test_render_signals_report_includes_all_14_marker_numbers():
    results = _make_results()
    output = report.render_signals_report([], *results)
    for n in range(1, 15):
        assert f"| {n} |" in output, f"marker {n} missing from report"


def test_render_signals_report_placeholder_rows_reference_handoff_doc():
    results = _make_results()
    output = report.render_signals_report([], *results)
    # +1 for the report header's own "Per-marker source" line, beyond one per placeholder row
    assert output.count("14-signals-crash-warning-handoff.md") == len(report._PLACEHOLDER_MARKERS) + 1


def test_render_signals_report_shows_hot_watchlist_table():
    results = _make_results()
    watchlist = [{"rank": 1, "ticker": "NVDA", "sector_label": "Technology", "market_cap": 5_000_000_000_000}]
    output = report.render_signals_report(watchlist, *results)
    assert "NVDA" in output
    assert "$5000B" in output


def test_render_signals_report_empty_watchlist_message():
    results = _make_results()
    output = report.render_signals_report([], *results)
    assert "No hot-watchlist companies resolved this run" in output


def test_write_signals_report_writes_file():
    results = _make_results()
    report.write_signals_report([], *results)
    assert config.SIGNALS_REPORT_PATH.exists()
    assert "14 Crash Signals" in config.SIGNALS_REPORT_PATH.read_text(encoding="utf-8")


def test_markers_2_4_9_12_render_real_rows_not_placeholder():
    results = _make_results()
    output = report.render_signals_report([], *results)
    assert "ORCL leases ok" in output
    assert "ORCL FCF negative" in output
    assert "44 days away" in output
    assert "ORCL spread ok" in output


def test_markers_still_pending_render_placeholder():
    results = _make_results()
    output = report.render_signals_report([], *results)
    for n in (1, 3, 6, 7, 11, 13):
        assert f"| {n} |" in output
        assert report._NOT_YET_AUTOMATED.split(" -- see")[0] in output


def test_marker_14_watch_suffix_appears_when_watch_true():
    (
        _, margin_debt_result, insider_trend_results, market_cap_result,
        lease_commitment_results, capex_cashflow_results, super_bowl_result, credit_spread_issuer_results,
    ) = _make_results()
    credit_spread_result = CheckResult(
        name="credit_spread_streak", verdict="ok", detail="spread 3.3pp -- WATCH: within 0.2pp of the flag threshold",
        data={"watch": True},
    )
    output = report.render_signals_report(
        [], credit_spread_result, margin_debt_result, insider_trend_results, market_cap_result,
        lease_commitment_results, capex_cashflow_results, super_bowl_result, credit_spread_issuer_results,
    )
    assert "(WATCH)" in output


def test_marker_14_no_watch_suffix_when_watch_false():
    results = _make_results()
    output = report.render_signals_report([], *results)
    assert "(WATCH)" not in output


def test_markers_2_4_12_render_empty_list_message_when_no_results():
    (
        credit_spread_result, margin_debt_result, insider_trend_results, market_cap_result,
        _, _, super_bowl_result, _,
    ) = _make_results()
    output = report.render_signals_report(
        [], credit_spread_result, margin_debt_result, insider_trend_results, market_cap_result,
        [], [], super_bowl_result, [],
    )
    assert "No hot-watchlist tickers with a resolvable lease-commitment reading this run." in output
    assert "No hot-watchlist tickers with a resolvable cash-flow statement this run." in output
    assert "No hot-watchlist tickers with a resolvable bond CUSIP this run." in output
