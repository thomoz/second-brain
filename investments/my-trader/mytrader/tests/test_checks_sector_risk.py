from __future__ import annotations

from mytrader.checks import sector_risk
from mytrader.market_data import TickerData


def test_no_data_returns_unknown():
    assert sector_risk.check(None).verdict == "unknown"


def test_known_flashpoint_sector_returns_info():
    data = TickerData(ticker="X", info={"sector": "Energy"}, dividends=None)
    result = sector_risk.check(data)
    assert result.verdict == "info"
    assert "Strait of Hormuz" in result.detail


def test_known_flashpoint_industry_returns_info():
    data = TickerData(ticker="X", info={"sector": "Technology", "industry": "Semiconductors"}, dividends=None)
    result = sector_risk.check(data)
    assert result.verdict == "info"


def test_unknown_sector_returns_ok():
    data = TickerData(ticker="X", info={"sector": "Healthcare"}, dividends=None)
    assert sector_risk.check(data).verdict == "ok"
