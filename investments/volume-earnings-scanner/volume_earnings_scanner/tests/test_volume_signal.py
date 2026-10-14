from __future__ import annotations

import pandas as pd

from volume_earnings_scanner import config, volume_signal


def _volume_series(trailing_avg: float, today: float, window: int = 20) -> pd.Series:
    values = [trailing_avg] * window + [today]
    return pd.Series(values)


def test_volume_spike_fires_at_or_above_threshold(monkeypatch):
    monkeypatch.setattr(config, "VE_VOLUME_SPIKE_RATIO_THRESHOLD", 3.0)
    monkeypatch.setattr(config, "VE_VOLUME_AVG_WINDOW_DAYS", 20)
    volume = _volume_series(trailing_avg=100_000, today=300_000)
    close = pd.Series([1.0] * len(volume))
    result = volume_signal.check_volume_spike("ABCD", close, volume)
    assert result.verdict == "interesting"
    assert result.data["ratio"] == 3.0


def test_volume_spike_does_not_fire_below_threshold(monkeypatch):
    monkeypatch.setattr(config, "VE_VOLUME_SPIKE_RATIO_THRESHOLD", 3.0)
    monkeypatch.setattr(config, "VE_VOLUME_AVG_WINDOW_DAYS", 20)
    volume = _volume_series(trailing_avg=100_000, today=250_000)
    close = pd.Series([1.0] * len(volume))
    result = volume_signal.check_volume_spike("ABCD", close, volume)
    assert result.verdict == "ok"


def test_volume_spike_unknown_on_insufficient_history(monkeypatch):
    monkeypatch.setattr(config, "VE_VOLUME_AVG_WINDOW_DAYS", 20)
    volume = pd.Series([100_000] * 5)  # fewer than window + 1
    close = pd.Series([1.0] * len(volume))
    result = volume_signal.check_volume_spike("ABCD", close, volume)
    assert result.verdict == "unknown"


def test_volume_spike_unknown_on_zero_trailing_average(monkeypatch):
    monkeypatch.setattr(config, "VE_VOLUME_AVG_WINDOW_DAYS", 3)
    volume = pd.Series([0, 0, 0, 500])
    close = pd.Series([1.0] * len(volume))
    result = volume_signal.check_volume_spike("ABCD", close, volume)
    assert result.verdict == "unknown"
