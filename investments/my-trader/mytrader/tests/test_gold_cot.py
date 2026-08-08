from __future__ import annotations

import pandas as pd
import pytest

from mytrader import config, gold_cot


def _dates(n: int, start: str = "2020-01-03") -> pd.DatetimeIndex:
    return pd.date_range(start, periods=n, freq="W-FRI")


def test_cot_index_series_matches_hand_computed_percentile():
    # Window of 5: values 100,200,150,50,300 -> min=50, max=300, span=250.
    # Last value 300 -> index = (300-50)/250*100 = 100.0 (at the top of its own range).
    net = pd.Series([100.0, 200.0, 150.0, 50.0, 300.0], index=_dates(5))
    index_series = gold_cot.cot_index_series(net, lookback_periods=5)
    assert index_series.iloc[-1] == pytest.approx(100.0)


def test_cot_index_series_midpoint_value():
    net = pd.Series([0.0, 100.0, 50.0], index=_dates(3))
    index_series = gold_cot.cot_index_series(net, lookback_periods=3)
    # min=0, max=100, current=50 -> (50-0)/100*100 = 50.0
    assert index_series.iloc[-1] == pytest.approx(50.0)


def test_cot_index_series_nan_before_lookback_warmup():
    net = pd.Series([1.0, 2.0, 3.0], index=_dates(3))
    index_series = gold_cot.cot_index_series(net, lookback_periods=5)
    assert index_series.isna().all()


def test_cot_index_series_nan_when_range_is_zero():
    net = pd.Series([100.0, 100.0, 100.0], index=_dates(3))
    index_series = gold_cot.cot_index_series(net, lookback_periods=3)
    assert pd.isna(index_series.iloc[-1])


def test_classify_cot_state_extreme_long():
    assert gold_cot.classify_cot_state(config.COT_EXTREME_LONG_PCT) == "extreme_long"
    assert gold_cot.classify_cot_state(100.0) == "extreme_long"


def test_classify_cot_state_extreme_short():
    assert gold_cot.classify_cot_state(config.COT_EXTREME_SHORT_PCT) == "extreme_short"
    assert gold_cot.classify_cot_state(0.0) == "extreme_short"


def test_classify_cot_state_neutral_in_between():
    assert gold_cot.classify_cot_state(50.0) == "neutral"


def test_compute_today_cot_returns_none_when_fetch_fails(monkeypatch):
    monkeypatch.setattr(gold_cot, "_fetch_cot_history", lambda: None)
    assert gold_cot.compute_today_cot() is None


def test_compute_today_cot_returns_none_when_insufficient_history(monkeypatch):
    short_series = pd.Series([1.0] * 10, index=_dates(10))
    monkeypatch.setattr(gold_cot, "_fetch_cot_history", lambda: short_series)
    assert gold_cot.compute_today_cot() is None


def test_compute_today_cot_returns_state_and_index(monkeypatch):
    # 156+ weeks, last value pinned to the top of its own range -> extreme_long.
    values = [100.0] * (config.COT_LOOKBACK_WEEKS - 1) + [1000.0]
    net = pd.Series(values, index=_dates(len(values)))
    monkeypatch.setattr(gold_cot, "_fetch_cot_history", lambda: net)
    result = gold_cot.compute_today_cot()
    assert result is not None
    assert result["state"] == "extreme_long"
    assert result["cot_index"] == pytest.approx(100.0)


def test_check_cot_positioning_unknown_when_fetch_fails(monkeypatch):
    monkeypatch.setattr(gold_cot, "compute_today_cot", lambda: None)
    result = gold_cot.check_cot_positioning()
    assert result.verdict == "unknown"
    assert result.name == "cot_positioning"


def test_check_cot_positioning_flags_extreme_with_direction(monkeypatch):
    monkeypatch.setattr(
        gold_cot, "compute_today_cot",
        lambda: {"cot_index": 95.0, "state": "extreme_long", "as_of": "2026-08-01"},
    )
    result = gold_cot.check_cot_positioning()
    assert result.verdict == "flag"
    assert result.data["direction"] == "extreme_long"
    assert "crowded-positioning" in result.detail


def test_check_cot_positioning_ok_when_neutral(monkeypatch):
    monkeypatch.setattr(
        gold_cot, "compute_today_cot",
        lambda: {"cot_index": 50.0, "state": "neutral", "as_of": "2026-08-01"},
    )
    result = gold_cot.check_cot_positioning()
    assert result.verdict == "ok"
    assert result.data["direction"] is None
