from __future__ import annotations

import pandas as pd
import pytest

from mytrader import config, gold_technicals


def _dates(n: int, start: str = "2026-01-01") -> pd.DatetimeIndex:
    return pd.date_range(start, periods=n, freq="D")


def test_moving_average_series_matches_hand_computed_mean():
    close = pd.Series([10.0, 20.0, 30.0, 40.0, 50.0], index=_dates(5))
    ma = gold_technicals.moving_average_series(close, 3)
    # window of 3: NaN, NaN, mean(10,20,30)=20, mean(20,30,40)=30, mean(30,40,50)=40
    assert ma.iloc[2] == 20.0
    assert ma.iloc[3] == 30.0
    assert ma.iloc[4] == 40.0


def test_rsi_series_all_gains_reaches_100():
    # Monotonic increase after the first point -> avg_loss is exactly 0 for every
    # window once warmed up, so RS = avg_gain / 0 = inf, RSI = 100 - 100/(1+inf) = 100
    # exactly, regardless of the actual gain magnitudes.
    close = pd.Series([float(i) for i in range(1, 12)], index=_dates(11))
    rsi = gold_technicals.rsi_series(close, period=3)
    assert rsi.iloc[-1] == pytest.approx(100.0)


def test_rsi_series_all_losses_reaches_0():
    # Mirror image: avg_gain is exactly 0 once warmed up -> RS = 0 -> RSI = 0 exactly.
    close = pd.Series([float(i) for i in range(11, 0, -1)], index=_dates(11))
    rsi = gold_technicals.rsi_series(close, period=3)
    assert rsi.iloc[-1] == pytest.approx(0.0)


def _ewm_adjust_false(values: list[float], alpha: float) -> list[float]:
    """Independent (non-pandas) recursive EMA reference implementation --
    EMA[0] = values[0], EMA[t] = alpha*values[t] + (1-alpha)*EMA[t-1] -- the exact
    definition pandas' ewm(adjust=False) uses, computed here by hand so the test
    doesn't just re-call the code under test."""
    out = [values[0]]
    for v in values[1:]:
        out.append(alpha * v + (1 - alpha) * out[-1])
    return out


def test_macd_series_matches_hand_computed_ema_recursion(monkeypatch):
    monkeypatch.setattr(config, "GOLD_TA_MACD_FAST_DAYS", 2)
    monkeypatch.setattr(config, "GOLD_TA_MACD_SLOW_DAYS", 3)
    monkeypatch.setattr(config, "GOLD_TA_MACD_SIGNAL_DAYS", 2)
    prices = [10.0, 12.0, 11.0]
    close = pd.Series(prices, index=_dates(3))

    alpha_fast = 2 / (2 + 1)
    alpha_slow = 2 / (3 + 1)
    alpha_signal = 2 / (2 + 1)
    ema_fast = _ewm_adjust_false(prices, alpha_fast)
    ema_slow = _ewm_adjust_false(prices, alpha_slow)
    macd_line = [f - s for f, s in zip(ema_fast, ema_slow)]
    signal_line = _ewm_adjust_false(macd_line, alpha_signal)
    histogram = [m - s for m, s in zip(macd_line, signal_line)]

    result = gold_technicals.macd_series(close)
    for i in range(3):
        assert result["macd"].iloc[i] == pytest.approx(macd_line[i])
        assert result["signal"].iloc[i] == pytest.approx(signal_line[i])
        assert result["histogram"].iloc[i] == pytest.approx(histogram[i])


def test_compute_macd_histogram_rising_flag():
    # histogram strictly increasing at the end -> histogram_rising True.
    close = pd.Series([10.0, 10.0, 10.0, 12.0, 20.0], index=_dates(5))
    result = gold_technicals.compute_macd(close)
    assert bool(result["histogram_rising"]) is True


def test_stochastic_series_at_period_high_is_100(monkeypatch):
    monkeypatch.setattr(config, "GOLD_TA_STOCH_PERIOD_DAYS", 3)
    monkeypatch.setattr(config, "GOLD_TA_STOCH_SMOOTHING_DAYS", 1)
    df = pd.DataFrame(
        {"High": [10.0, 12.0, 15.0], "Low": [8.0, 9.0, 9.0], "Close": [9.0, 11.0, 15.0]},
        index=_dates(3),
    )
    result = gold_technicals.stochastic_series(df)
    # low_min(3)=8, high_max(3)=15, close=15 -> k = (15-8)/(15-8)*100 = 100
    assert result["k"].iloc[-1] == pytest.approx(100.0)
    assert result["d"].iloc[-1] == pytest.approx(100.0)  # smoothing=1 -> d == k


def test_atr_series_matches_known_true_range():
    df = pd.DataFrame(
        {
            "High": [10.0, 12.0, 11.0],
            "Low": [8.0, 9.0, 9.0],
            "Close": [9.0, 11.0, 10.0],
        },
        index=_dates(3),
    )
    # period=1 -> alpha=1 -> ewm(adjust=False) output equals the raw true-range
    # series exactly (no smoothing memory carried forward).
    # row0: prev_close NaN -> tr = High-Low = 2
    # row1: prev_close=9 -> max(12-9, |12-9|, |9-9|) = max(3,3,0) = 3
    # row2: prev_close=11 -> max(11-9, |11-11|, |9-11|) = max(2,0,2) = 2
    atr = gold_technicals.atr_series(df, period=1)
    assert atr.iloc[0] == pytest.approx(2.0)
    assert atr.iloc[1] == pytest.approx(3.0)
    assert atr.iloc[2] == pytest.approx(2.0)


def test_compute_bollinger_width_widens_with_variance(monkeypatch):
    monkeypatch.setattr(config, "GOLD_TA_BOLLINGER_PERIOD_DAYS", 4)
    monkeypatch.setattr(config, "GOLD_TA_BOLLINGER_STD_MULTIPLIER", 2.0)
    low_variance = pd.Series([100.0, 100.5, 99.5, 100.0], index=_dates(4))
    high_variance = pd.Series([100.0, 110.0, 90.0, 100.0], index=_dates(4))

    low_result = gold_technicals.compute_bollinger(low_variance)
    high_result = gold_technicals.compute_bollinger(high_variance)

    assert high_result["width_pct"] > low_result["width_pct"]


def test_compute_levels_within_window(monkeypatch):
    monkeypatch.setattr(config, "GOLD_TA_LEVEL_LOOKBACK_DAYS", 3)
    df = pd.DataFrame(
        {
            "High": [999.0, 999.0, 15.0, 20.0, 18.0],
            "Low": [1.0, 1.0, 10.0, 12.0, 11.0],
            "Close": [500.0, 500.0, 12.0, 18.0, 15.0],
            "Volume": [0, 0, 0, 0, 0],
        },
        index=_dates(5),
    )
    result = gold_technicals.compute_levels(df)
    # Only the last 3 rows are in the lookback window -- the 999/1 outliers in the
    # first two rows must be excluded.
    assert result["resistance"] == 20.0
    assert result["support"] == 10.0


def test_compute_volume_context_above_and_below_average(monkeypatch):
    monkeypatch.setattr(config, "GOLD_TA_VOLUME_AVG_DAYS", 3)
    above_df = pd.DataFrame({"Volume": [100.0, 100.0, 100.0, 400.0]}, index=_dates(4))
    below_df = pd.DataFrame({"Volume": [100.0, 100.0, 100.0, 10.0]}, index=_dates(4))

    above_result = gold_technicals.compute_volume_context(above_df)
    below_result = gold_technicals.compute_volume_context(below_df)

    assert above_result["above_average"] is True
    assert below_result["above_average"] is False


def test_compute_seasonality_filters_matching_month_across_years():
    dates = pd.to_datetime(["2024-12-31", "2025-01-31", "2025-12-31", "2026-01-31"])
    close = pd.Series([100.0, 110.0, 200.0, 180.0], index=dates)
    from datetime import date as _date

    result = gold_technicals.compute_seasonality(close, _date(2026, 1, 15))
    # Jan 2025 return: (110-100)/100*100 = 10.0; Jan 2026 return: (180-200)/200*100 = -10.0
    assert result["n"] == 2
    assert result["mean"] == pytest.approx(0.0)
    assert result["median"] == pytest.approx(0.0)


def test_compute_today_technicals_returns_none_when_history_too_short(monkeypatch):
    short_df = pd.DataFrame(
        {
            "Open": [1.0] * 5, "High": [1.0] * 5, "Low": [1.0] * 5,
            "Close": [1.0] * 5, "Volume": [1.0] * 5,
        },
        index=_dates(5),
    )
    monkeypatch.setattr(gold_technicals, "_fetch_ohlcv", lambda ticker, start: short_df)
    assert gold_technicals.compute_today_technicals() is None


def test_compute_today_technicals_returns_none_when_fetch_fails(monkeypatch):
    monkeypatch.setattr(gold_technicals, "_fetch_ohlcv", lambda ticker, start: None)
    assert gold_technicals.compute_today_technicals() is None
