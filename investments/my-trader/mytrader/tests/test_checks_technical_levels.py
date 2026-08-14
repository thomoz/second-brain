from __future__ import annotations

import pandas as pd

from mytrader.checks import technical_levels
from mytrader.market_data import TickerData


def test_no_data_returns_unknown():
    assert technical_levels.check(None).verdict == "unknown"


def test_returns_unknown_when_fetch_fails(monkeypatch):
    monkeypatch.setattr(technical_levels, "_fetch_close_series", lambda ticker: None)
    data = TickerData(ticker="X", info={}, dividends=None)
    result = technical_levels.check(data)
    assert result.verdict == "unknown"


def test_returns_unknown_when_too_little_history(monkeypatch):
    monkeypatch.setattr(technical_levels, "_fetch_close_series", lambda ticker: pd.Series([10.0] * 40))
    data = TickerData(ticker="X", info={}, dividends=None)
    result = technical_levels.check(data)
    assert result.verdict == "unknown"


def test_reports_price_vs_all_three_windows_when_enough_history(monkeypatch):
    # 200 rising closes: last close (current) sits above the mean of every window.
    closes = pd.Series([float(i) for i in range(1, 251)])
    monkeypatch.setattr(technical_levels, "_fetch_close_series", lambda ticker: closes)
    data = TickerData(ticker="AG", info={}, dividends=None)
    result = technical_levels.check(data)
    assert result.verdict == "info"
    assert "50DMA" in result.detail
    assert "150DMA" in result.detail
    assert "200DMA" in result.detail
    assert "above" in result.detail
    assert result.data["current_price"] == 250.0
    assert set(result.data.keys()) == {"current_price", "ma50", "ma150", "ma200"}


def test_reports_only_windows_history_supports(monkeypatch):
    # 60 rows of history -- only the 50DMA window is computable, 150/200 aren't.
    closes = pd.Series([float(i) for i in range(1, 61)])
    monkeypatch.setattr(technical_levels, "_fetch_close_series", lambda ticker: closes)
    data = TickerData(ticker="AG", info={}, dividends=None)
    result = technical_levels.check(data)
    assert result.verdict == "info"
    assert "50DMA" in result.detail
    assert "150DMA" not in result.detail
    assert "200DMA" not in result.detail


def test_reports_below_when_price_under_moving_average(monkeypatch):
    closes = pd.Series([100.0] * 49 + [50.0])  # sharp drop on the last day
    monkeypatch.setattr(technical_levels, "_fetch_close_series", lambda ticker: closes)
    data = TickerData(ticker="AG", info={}, dividends=None)
    result = technical_levels.check(data)
    assert "below" in result.detail
