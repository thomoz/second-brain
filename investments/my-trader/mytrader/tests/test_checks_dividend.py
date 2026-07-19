from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd

from mytrader.checks import dividend
from mytrader.market_data import TickerData


def _dividend_data(payments: list[tuple[int, float]]) -> TickerData:
    """payments: list of (days_ago, amount)."""
    now = datetime.now()
    dates = [now - timedelta(days=d) for d, _ in payments]
    amounts = [a for _, a in payments]
    series = pd.Series(amounts, index=pd.DatetimeIndex(dates))
    return TickerData(ticker="TEST", info={}, dividends=series)


def test_no_data_returns_unknown():
    assert dividend.check(None).verdict == "unknown"


def test_empty_dividends_returns_info():
    data = TickerData(ticker="VRTX", info={}, dividends=pd.Series(dtype=float))
    result = dividend.check(data)
    assert result.verdict == "info"
    assert "No dividend history" in result.detail


def test_growing_dividend_returns_ok():
    data = _dividend_data([(30, 1.0), (120, 1.0), (395, 0.8), (500, 0.8)])
    assert dividend.check(data).verdict == "ok"


def test_dividend_cut_returns_flag():
    data = _dividend_data([(30, 0.5), (120, 0.5), (395, 1.0), (500, 1.0)])
    result = dividend.check(data)
    assert result.verdict == "flag"


def test_flat_dividend_returns_info():
    data = _dividend_data([(30, 1.0), (395, 1.0)])
    result = dividend.check(data)
    assert result.verdict == "info"
