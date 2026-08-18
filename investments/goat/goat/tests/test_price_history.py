from __future__ import annotations

import sys
import types

import pandas as pd

from goat import price_history

_real_fetch_close_history = price_history.fetch_close_history


def _install_fake_yfinance(monkeypatch, history: pd.DataFrame):
    class _FakeTicker:
        def __init__(self, symbol):
            self._symbol = symbol

        def history(self, start=None, auto_adjust=True):
            return history

    fake_yf = types.ModuleType("yfinance")
    fake_yf.Ticker = _FakeTicker
    monkeypatch.setitem(sys.modules, "yfinance", fake_yf)


def test_fetch_close_history_drops_trailing_nan_row(monkeypatch):
    """Regression for the sector-ranking '+nan%' bug (2026-08-18): yfinance can
    return a placeholder row for the most recent trading day with Close=NaN
    (confirmed live against XLK) -- that row must be dropped, not left to
    propagate NaN into iloc[-1] and every downstream pct-change calculation."""
    idx = pd.date_range("2026-08-10", periods=6, freq="D")
    hist = pd.DataFrame(
        {"Close": [186.3, 186.1, 188.9, 190.8, 190.0, float("nan")]}, index=idx
    )
    _install_fake_yfinance(monkeypatch, hist)
    monkeypatch.setattr(price_history, "fetch_close_history", _real_fetch_close_history)

    close = price_history.fetch_close_history("XLK", lookback_days=30)

    assert close is not None
    assert not close.isna().any()
    assert close.iloc[-1] == 190.0


def test_fetch_close_history_returns_none_when_all_nan(monkeypatch):
    idx = pd.date_range("2026-08-10", periods=2, freq="D")
    hist = pd.DataFrame({"Close": [float("nan"), float("nan")]}, index=idx)
    _install_fake_yfinance(monkeypatch, hist)
    monkeypatch.setattr(price_history, "fetch_close_history", _real_fetch_close_history)

    assert price_history.fetch_close_history("XLK", lookback_days=30) is None


def test_fetch_close_history_returns_none_when_empty(monkeypatch):
    _install_fake_yfinance(monkeypatch, pd.DataFrame())
    monkeypatch.setattr(price_history, "fetch_close_history", _real_fetch_close_history)

    assert price_history.fetch_close_history("XLK", lookback_days=30) is None
