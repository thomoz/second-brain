from __future__ import annotations

from mytrader.checks import valuation
from mytrader.market_data import TickerData


def test_no_data_returns_unknown():
    assert valuation.check(None).verdict == "unknown"


def test_missing_pe_returns_unknown():
    data = TickerData(ticker="X", info={}, dividends=None)
    assert valuation.check(data).verdict == "unknown"


def test_rich_pe_flags():
    data = TickerData(ticker="X", info={"trailingPE": 40.0}, dividends=None)
    assert valuation.check(data).verdict == "flag"


def test_cheap_pe_ok():
    data = TickerData(ticker="X", info={"trailingPE": 10.0}, dividends=None)
    assert valuation.check(data).verdict == "ok"


def test_normal_pe_ok():
    data = TickerData(ticker="X", info={"trailingPE": 20.0}, dividends=None)
    assert valuation.check(data).verdict == "ok"


def test_falls_back_to_forward_pe():
    data = TickerData(ticker="X", info={"forwardPE": 45.0}, dividends=None)
    assert valuation.check(data).verdict == "flag"
