from __future__ import annotations

from mytrader.checks import balance_sheet
from mytrader.market_data import TickerData


def test_no_data_returns_unknown():
    assert balance_sheet.check(None).verdict == "unknown"


def test_missing_data_returns_unknown():
    data = TickerData(ticker="X", info={}, dividends=None)
    assert balance_sheet.check(data).verdict == "unknown"


def test_high_debt_to_equity_flags():
    data = TickerData(ticker="X", info={"debtToEquity": 200.0, "currentRatio": 2.0}, dividends=None)
    assert balance_sheet.check(data).verdict == "flag"


def test_low_current_ratio_flags():
    data = TickerData(ticker="X", info={"debtToEquity": 50.0, "currentRatio": 0.5}, dividends=None)
    assert balance_sheet.check(data).verdict == "flag"


def test_healthy_balance_sheet_ok():
    data = TickerData(ticker="X", info={"debtToEquity": 50.0, "currentRatio": 2.0}, dividends=None)
    result = balance_sheet.check(data)
    assert result.verdict == "ok"
    assert "Debt/Equity 50.0" in result.detail
    assert "Current Ratio 2.00" in result.detail
    assert "lower is generally safer" in result.detail
    assert "higher is generally safer" in result.detail


def test_falls_back_to_roe_when_debt_equity_and_current_ratio_missing():
    data = TickerData(ticker="NU", info={"returnOnEquity": 0.30055}, dividends=None)
    result = balance_sheet.check(data)
    assert result.verdict == "ok"
    assert "Return on Equity" in result.detail
    assert result.data["return_on_equity_pct"] == 30.05


def test_roe_fallback_flags_when_weak():
    data = TickerData(ticker="X", info={"returnOnEquity": 0.02}, dividends=None)
    assert balance_sheet.check(data).verdict == "flag"


def test_returns_unknown_when_roe_also_missing():
    data = TickerData(ticker="X", info={}, dividends=None)
    assert balance_sheet.check(data).verdict == "unknown"


def test_falls_back_to_derived_roe_from_statements_when_info_roe_missing(monkeypatch):
    """Regression for GROW.L (Molten Ventures) -- .info had none of debtToEquity/
    currentRatio/returnOnEquity, but the raw balance_sheet/financials statements had
    real numbers. See market_data.fetch_balance_sheet_financials."""
    monkeypatch.setattr(
        "mytrader.market_data.fetch_balance_sheet_financials",
        lambda ticker: {"returnOnEquity": 0.0909},
    )
    data = TickerData(ticker="GROW.L", info={}, dividends=None)
    result = balance_sheet.check(data)
    assert result.verdict == "ok"
    assert "derived from balance sheet/income statement" in result.detail
    assert result.data["return_on_equity_pct"] == 9.09


def test_derived_roe_fallback_flags_when_weak(monkeypatch):
    monkeypatch.setattr(
        "mytrader.market_data.fetch_balance_sheet_financials",
        lambda ticker: {"returnOnEquity": 0.02},
    )
    data = TickerData(ticker="X", info={}, dividends=None)
    result = balance_sheet.check(data)
    assert result.verdict == "flag"
    assert "derived from balance sheet/income statement" in result.detail


def test_still_unknown_when_derived_fallback_also_has_no_roe(monkeypatch):
    monkeypatch.setattr(
        "mytrader.market_data.fetch_balance_sheet_financials",
        lambda ticker: {"debtToEquity": 9.9},  # no returnOnEquity key
    )
    data = TickerData(ticker="X", info={}, dividends=None)
    assert balance_sheet.check(data).verdict == "unknown"


def test_info_roe_present_does_not_trigger_derived_fallback(monkeypatch):
    """When .info already has a usable ROE, the statements fallback must not even be
    consulted -- keeps the cheap path cheap."""
    def _raise(ticker):
        raise AssertionError("should not fetch statements when .info already has ROE")

    monkeypatch.setattr("mytrader.market_data.fetch_balance_sheet_financials", _raise)
    data = TickerData(ticker="NU", info={"returnOnEquity": 0.30055}, dividends=None)
    result = balance_sheet.check(data)
    assert result.verdict == "ok"
    assert "derived" not in result.detail
