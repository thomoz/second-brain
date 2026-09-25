from __future__ import annotations

import pandas as pd

from mytrader import matt_damon_price_volitility_volume_check_backtest as backtest


def _bullish_frame(n: int = 60) -> pd.DataFrame:
    dates = pd.date_range("2024-01-01", periods=n, freq="D")
    closes = [100.0 + 0.01 * (i**1.5) for i in range(n)]
    volumes = [1000.0 + 50.0 * i for i in range(n)]
    return pd.DataFrame({"Close": closes, "Volume": volumes}, index=dates)


def test_confluence_state_series_labels_clear_bullish_run():
    frame = _bullish_frame()
    state = backtest._confluence_state_series(frame, window=10)
    assert state.iloc[-1] == "aligned_bullish"


def test_price_roc_only_state_series_labels_up_down():
    dates = pd.date_range("2024-01-01", periods=30, freq="D")
    rising = pd.Series([100.0 + i for i in range(30)], index=dates)
    falling = pd.Series([200.0 - i for i in range(30)], index=dates)

    up_state = backtest._price_roc_only_state_series(rising, window=10)
    down_state = backtest._price_roc_only_state_series(falling, window=10)

    assert up_state.iloc[-1] == "up"
    assert down_state.iloc[-1] == "down"


def test_state_conditioned_raw_returns_pools_correctly():
    dates = pd.date_range("2024-01-01", periods=6, freq="D")
    close = pd.Series([100.0, 105.0, 110.0, 120.0, 90.0, 95.0], index=dates)
    state = pd.Series(["a", "a", "b", "a", "b", "unknown"], index=dates)

    raw = backtest._state_conditioned_raw_returns(state, close, n_days=1)

    # position 0 ("a"): 100 -> 105 = +5.0%; position 1 ("a"): 105 -> 110 = +4.76...%
    assert raw["a"][0] == 5.0
    assert round(raw["a"][1], 2) == 4.76
    # position 2 ("b"): 110 -> 120 = +9.09...%
    assert round(raw["b"][0], 2) == 9.09
    assert "unknown" not in raw


def test_baseline_raw_returns_matches_length_minus_horizon():
    dates = pd.date_range("2024-01-01", periods=10, freq="D")
    close = pd.Series([float(100 + i) for i in range(10)], index=dates)

    returns = backtest._baseline_raw_returns(close, n_days=2)

    assert len(returns) == 8  # last 2 rows have no forward target


def test_pool_stats_empty_returns_none_fields():
    stats = backtest._pool_stats([])
    assert stats["n"] == 0
    assert stats["mean"] is None


def test_pool_stats_computes_distribution():
    stats = backtest._pool_stats([10.0, -5.0, 20.0])
    assert stats["n"] == 3
    assert stats["mean"] == round((10.0 - 5.0 + 20.0) / 3, 2)
    assert stats["win_rate"] == round(2 / 3 * 100, 1)
    assert stats["best"] == 20.0
    assert stats["worst"] == -5.0
