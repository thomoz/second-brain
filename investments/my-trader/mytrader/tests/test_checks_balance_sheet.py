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
    assert balance_sheet.check(data).verdict == "ok"
