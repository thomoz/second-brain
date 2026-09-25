from __future__ import annotations

import pandas as pd

from mytrader.checks import matt_damon_price_volitility_volume_check as mdpvvc
from mytrader.market_data import TickerData


def test_no_data_returns_unknown():
    assert mdpvvc.check(None).verdict == "unknown"


def test_returns_unknown_when_fetch_fails(monkeypatch):
    monkeypatch.setattr(mdpvvc, "_fetch_price_volume_history", lambda ticker: None)
    data = TickerData(ticker="X", info={}, dividends=None)
    result = mdpvvc.check(data)
    assert result.verdict == "unknown"


def test_returns_unknown_when_too_little_history(monkeypatch):
    short = pd.DataFrame({"Close": [10.0] * 10, "Volume": [1000.0] * 10})
    monkeypatch.setattr(mdpvvc, "_fetch_price_volume_history", lambda ticker: short)
    data = TickerData(ticker="X", info={}, dividends=None)
    result = mdpvvc.check(data)
    assert result.verdict == "unknown"


def _bullish_frame(n: int = 60) -> pd.DataFrame:
    # Accelerating price (quadratic growth), rising volume, flattening volatility --
    # the tail settles into a clean, near-constant daily step so the rolling
    # std-dev of returns trends down into the window under test.
    closes = [100.0 + 0.01 * (i**1.5) for i in range(n)]
    volumes = [1000.0 + 50.0 * i for i in range(n)]
    return pd.DataFrame({"Close": closes, "Volume": volumes})


def test_reports_aligned_bullish_when_price_and_volume_rise_and_volatility_falls(monkeypatch):
    frame = _bullish_frame()
    monkeypatch.setattr(mdpvvc, "_fetch_price_volume_history", lambda ticker: frame)
    data = TickerData(ticker="X", info={}, dividends=None)

    result = mdpvvc.check(data)

    assert result.verdict == "info"
    assert result.data["alignment_short"] == "aligned_bullish"
    assert "10d" in result.detail
    assert "25d" in result.detail


def test_reports_no_read_when_signals_disagree(monkeypatch):
    n = 60
    # Price rises steadily, volume falls steadily -- disagreement.
    closes = [100.0 + i for i in range(n)]
    volumes = [5000.0 - 50.0 * i for i in range(n)]
    frame = pd.DataFrame({"Close": closes, "Volume": volumes})
    monkeypatch.setattr(mdpvvc, "_fetch_price_volume_history", lambda ticker: frame)
    data = TickerData(ticker="X", info={}, dividends=None)

    result = mdpvvc.check(data)

    assert result.data["alignment_short"] == "no_read"


def test_zero_volume_does_not_crash(monkeypatch):
    n = 60
    closes = [100.0 + i for i in range(n)]
    volumes = [0.0] * n
    frame = pd.DataFrame({"Close": closes, "Volume": volumes})
    monkeypatch.setattr(mdpvvc, "_fetch_price_volume_history", lambda ticker: frame)
    data = TickerData(ticker="X", info={}, dividends=None)

    result = mdpvvc.check(data)

    assert result.verdict == "info"
    assert result.data["volume_roc_short"] is None
    assert result.data["alignment_short"] == "unknown"


def test_asx_fallback(monkeypatch):
    import sys
    import types

    frame = _bullish_frame()

    class _FakeTicker:
        def __init__(self, symbol):
            self.symbol = symbol

        def history(self, period, auto_adjust):
            if self.symbol == "AXTICKER.AX":
                return frame
            return pd.DataFrame()

    fake_yf = types.ModuleType("yfinance")
    fake_yf.Ticker = _FakeTicker
    monkeypatch.setitem(sys.modules, "yfinance", fake_yf)

    result = mdpvvc._fetch_price_volume_history("AXTICKER")

    assert result is not None
    assert len(result) == len(frame)
