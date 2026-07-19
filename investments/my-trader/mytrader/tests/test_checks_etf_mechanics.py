from __future__ import annotations

from mytrader.checks import etf_mechanics
from mytrader.market_data import TickerData


def test_no_data_returns_unknown():
    assert etf_mechanics.check(None, None).verdict == "unknown"


def test_non_etf_returns_unknown():
    data = TickerData(ticker="X", info={"quoteType": "EQUITY"}, dividends=None)
    assert etf_mechanics.check(data, None).verdict == "unknown"


def test_first_sight_captures_baseline():
    data = TickerData(ticker="SCHD", info={"quoteType": "ETF", "netExpenseRatio": 0.06}, dividends=None)
    result = etf_mechanics.check(data, None)
    assert result.verdict == "info"
    assert "Baseline captured" in result.detail


def test_expense_ratio_drift_flags():
    data = TickerData(ticker="SCHD", info={"quoteType": "ETF", "netExpenseRatio": 0.10}, dividends=None)
    existing_row = {"last_expense_ratio": 0.06}
    result = etf_mechanics.check(data, existing_row)
    assert result.verdict == "flag"


def test_unchanged_expense_ratio_returns_info():
    data = TickerData(ticker="SCHD", info={"quoteType": "ETF", "netExpenseRatio": 0.06}, dividends=None)
    existing_row = {"last_expense_ratio": 0.06}
    result = etf_mechanics.check(data, existing_row)
    assert result.verdict == "info"
