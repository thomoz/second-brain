from __future__ import annotations

import math

import pandas as pd

from goat import config, heartbeat


def _dates(n: int, start: str = "2020-01-01") -> pd.DatetimeIndex:
    return pd.date_range(start, periods=n, freq="D")


def _noisy_prices(n: int, base: float = 100.0, amplitude: float = 8.0) -> list[float]:
    return [base + amplitude * math.sin(i / 5) for i in range(n)]


def _tight_prices(n: int, base: float, amplitude: float = 0.05) -> list[float]:
    return [base + amplitude * math.sin(i / 3) for i in range(n)]


def _rising_tail(base: float, n: int, jump: float = 20.0, step: float = 1.5) -> list[float]:
    return [base + jump + i * step for i in range(n)]


def _series_from_prices(prices: list[float]) -> pd.Series:
    return pd.Series(prices, index=_dates(len(prices)))


def _heartbeat_series(tail_len: int = 9) -> pd.Series:
    """Long noisy lead-in (establishes a real percentile distribution) -> tight
    63-day consolidation immediately before the cross -> breakout tail long
    enough to be a fresh cross (within GOAT_SECTOR_CROSS_RECENCY_DAYS)."""
    lead = _noisy_prices(280)
    consolidation = _tight_prices(70, base=lead[-1])
    tail = _rising_tail(consolidation[-1], tail_len)
    return _series_from_prices(lead + consolidation + tail)


def _no_squeeze_series(tail_len: int = 9) -> pd.Series:
    """Same shape/length as _heartbeat_series but noisy (not tight) all the way
    up to the cross -- the cross+slope leg alone should still pass, proving the
    heartbeat squeeze leg is what's actually gating."""
    lead = _noisy_prices(350)
    tail = _rising_tail(lead[-1], tail_len)
    return _series_from_prices(lead + tail)


def test_check_heartbeat_breakout_fires_on_squeeze_then_fresh_breakout():
    close = _heartbeat_series()
    result = heartbeat.check_heartbeat_breakout("AAPL", "Technology", close)
    assert result.verdict == "interesting"
    assert result.data["crossed_above"] is True
    assert result.data["slope_up"] is True
    assert result.data["squeeze_fraction"] >= config.GOAT_HEARTBEAT_SQUEEZE_MIN_FRACTION


def test_check_heartbeat_breakout_normal_volatility_does_not_fire():
    close = _no_squeeze_series()
    result = heartbeat.check_heartbeat_breakout("AAPL", "Technology", close)
    assert result.verdict == "ok"
    # the cross+slope leg alone genuinely passes -- proves the squeeze leg is the
    # thing suppressing this, not an accidental failure of the other leg too.
    assert result.data["crossed_above"] is True
    assert result.data["slope_up"] is True
    assert result.data["squeeze_fraction"] < config.GOAT_HEARTBEAT_SQUEEZE_MIN_FRACTION


def test_check_heartbeat_breakout_insufficient_history_is_unknown():
    close = _series_from_prices(_noisy_prices(50))
    result = heartbeat.check_heartbeat_breakout("AAPL", "Technology", close)
    assert result.verdict == "unknown"


def test_check_heartbeat_breakout_stale_cross_does_not_fire():
    close = _heartbeat_series(tail_len=config.GOAT_SECTOR_CROSS_RECENCY_DAYS + 15)
    result = heartbeat.check_heartbeat_breakout("AAPL", "Technology", close)
    assert result.verdict == "ok"


def test_check_heartbeat_breakout_no_cross_in_history_is_ok():
    n = config.GOAT_HEARTBEAT_BBW_PERCENTILE_LOOKBACK_DAYS + config.GOAT_HEARTBEAT_MIN_DURATION_DAYS + 10
    close = pd.Series([100.0] * n, index=_dates(n))
    result = heartbeat.check_heartbeat_breakout("AAPL", "Technology", close)
    assert result.verdict == "ok"
