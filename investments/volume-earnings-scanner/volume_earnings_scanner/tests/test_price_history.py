from __future__ import annotations

import pandas as pd

from volume_earnings_scanner import price_history


def _fake_hist(rows: int = 25) -> pd.DataFrame:
    idx = pd.date_range("2026-01-01", periods=rows, freq="D")
    return pd.DataFrame({"Close": [10.0 + i for i in range(rows)], "Volume": [1000 * (i + 1) for i in range(rows)]}, index=idx)


def test_fetch_close_volume_history_returns_close_and_volume(monkeypatch):
    monkeypatch.setattr("mytrader.yf_retry.call", lambda fn: _fake_hist())
    frame = price_history.fetch_close_volume_history("ABCD", 60)
    assert frame is not None
    assert list(frame.columns) == ["Close", "Volume"]
    assert len(frame) == 25


def test_fetch_close_volume_history_falls_back_to_asx_variant(monkeypatch):
    calls = []

    def fake_call(fn):
        calls.append(1)
        if len(calls) == 1:
            return pd.DataFrame({"Close": [], "Volume": []})  # empty -- primary lookup fails
        return _fake_hist(10)

    monkeypatch.setattr("mytrader.yf_retry.call", fake_call)
    frame = price_history.fetch_close_volume_history("XYZ", 60)
    assert frame is not None
    assert len(frame) == 10
    assert len(calls) == 2


def test_fetch_close_volume_history_returns_none_when_both_fail(monkeypatch):
    monkeypatch.setattr("mytrader.yf_retry.call", lambda fn: pd.DataFrame({"Close": [], "Volume": []}))
    assert price_history.fetch_close_volume_history("NOPE", 60) is None
