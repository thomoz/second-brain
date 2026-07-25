from __future__ import annotations

import sys
import types

import pandas as pd

from mytrader import crash_windows


def _install_fake_yfinance(monkeypatch, hist: pd.DataFrame):
    class _FakeTicker:
        def __init__(self, symbol):
            pass

        def history(self, start, auto_adjust):
            return hist

    fake_yf = types.ModuleType("yfinance")
    fake_yf.Ticker = _FakeTicker
    monkeypatch.setitem(sys.modules, "yfinance", fake_yf)


def test_fetch_close_series_returns_none_on_empty_history(monkeypatch):
    # Tests the private _fetch_close_series helper directly, not the public
    # fetch_crash_drawdowns wrapper -- conftest.py's global
    # _no_real_crash_drawdown_fetch fixture stubs the latter for every test by
    # default (same pattern as test_return_data.py's fetch_recent_return_pct split).
    _install_fake_yfinance(monkeypatch, pd.DataFrame())
    assert crash_windows._fetch_close_series("NOPE") is None


def test_fetch_close_series_returns_close_column(monkeypatch):
    dates = pd.to_datetime(["2021-06-01", "2021-11-16"])
    hist = pd.DataFrame({"Close": [100.0, 200.0]}, index=dates)
    _install_fake_yfinance(monkeypatch, hist)

    close = crash_windows._fetch_close_series("SYNTH")

    assert close is not None
    assert close.iloc[-1] == 200.0


def test_drawdown_computes_known_peak_to_trough():
    # Peaks 200 on 2021-11-16 (matching the start of the 2022 bear market window),
    # falls to a 100 trough on 2022-07-01, partially recovers to 145 by year end.
    # Expected: (100/200 - 1) * 100 = -50.0%.
    dates = pd.to_datetime(
        ["2021-06-01", "2021-11-16", "2022-01-01", "2022-07-01", "2022-12-31", "2023-01-01"]
    )
    closes = [100.0, 200.0, 180.0, 100.0, 140.0, 145.0]
    close = pd.Series(closes, index=dates)

    assert crash_windows._drawdown(close, "2021-10-01", "2022-12-31") == -50.0


def test_drawdown_returns_none_when_window_has_no_data():
    # Ticker "IPO'd" 2021-06-01 -- windows entirely before that (2008, Dec 2018,
    # COVID) have no data in the slice and must be skipped, not error.
    dates = pd.to_datetime(["2021-06-01", "2021-11-16"])
    close = pd.Series([100.0, 200.0], index=dates)

    assert crash_windows._drawdown(close, "2007-10-01", "2009-03-09") is None
