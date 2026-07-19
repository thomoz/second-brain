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
    assert "debt/equity 50.0" in result.detail
    assert "current ratio 2.00" in result.detail


def test_falls_back_to_roe_when_debt_equity_and_current_ratio_missing():
    data = TickerData(ticker="NU", info={"returnOnEquity": 0.30055}, dividends=None)
    result = balance_sheet.check(data)
    assert result.verdict == "ok"
    assert "return on equity" in result.detail
    assert result.data["return_on_equity_pct"] == 30.05


def test_roe_fallback_flags_when_weak():
    data = TickerData(ticker="X", info={"returnOnEquity": 0.02}, dividends=None)
    assert balance_sheet.check(data).verdict == "flag"


def test_returns_unknown_when_roe_also_missing():
    data = TickerData(ticker="X", info={}, dividends=None)
    assert balance_sheet.check(data).verdict == "unknown"
