from __future__ import annotations

from fourteen_crash_signals_daily_check import capex_cashflow


def _cf(fcf: float, capex: float | None = None, period_end: str = "2026-05-31"):
    result = {"free_cash_flow": fcf, "operating_cash_flow": fcf - (capex or 0.0), "period_end": period_end}
    if capex is not None:
        result["capital_expenditure"] = capex
    return result


def test_check_capex_cashflow_flags_when_fcf_negative_and_capex_over_floor(monkeypatch):
    monkeypatch.setattr(
        "fourteen_crash_signals_daily_check.capex_cashflow.market_data.fetch_cash_flow_statement",
        lambda ticker: _cf(-23_686_000_000.0, -55_663_000_000.0),
    )
    results = capex_cashflow.check_capex_cashflow([{"ticker": "ORCL"}])
    assert len(results) == 1
    assert results[0].verdict == "flag"


def test_check_capex_cashflow_ok_when_fcf_negative_but_capex_below_floor(monkeypatch):
    monkeypatch.setattr(
        "fourteen_crash_signals_daily_check.capex_cashflow.market_data.fetch_cash_flow_statement",
        lambda ticker: _cf(-1_000_000.0, -2_000_000.0),
    )
    results = capex_cashflow.check_capex_cashflow([{"ticker": "SMALL"}])
    assert len(results) == 1
    assert results[0].verdict == "ok"


def test_check_capex_cashflow_ok_when_fcf_positive_regardless_of_capex(monkeypatch):
    monkeypatch.setattr(
        "fourteen_crash_signals_daily_check.capex_cashflow.market_data.fetch_cash_flow_statement",
        lambda ticker: _cf(50_000_000_000.0, -55_663_000_000.0),
    )
    results = capex_cashflow.check_capex_cashflow([{"ticker": "AAPL"}])
    assert len(results) == 1
    assert results[0].verdict == "ok"


def test_check_capex_cashflow_skips_ticker_when_fetch_returns_none(monkeypatch):
    monkeypatch.setattr(
        "fourteen_crash_signals_daily_check.capex_cashflow.market_data.fetch_cash_flow_statement",
        lambda ticker: None,
    )
    results = capex_cashflow.check_capex_cashflow([{"ticker": "NODATA"}])
    assert results == []


def test_check_capex_cashflow_empty_watchlist_returns_empty_list(monkeypatch):
    monkeypatch.setattr(
        "fourteen_crash_signals_daily_check.capex_cashflow.market_data.fetch_cash_flow_statement",
        lambda ticker: (_ for _ in ()).throw(AssertionError("should not fetch for empty watchlist")),
    )
    assert capex_cashflow.check_capex_cashflow([]) == []
