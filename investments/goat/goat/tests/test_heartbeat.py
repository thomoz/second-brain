"""Deterministic pd.Series inputs, no network, no DB -- check_heartbeat_breakout
is pure compute. Every base-leg gate gets a dedicated case where that gate is the
one being proven, with the breakout leg still passing, so a regression that
weakens (or removes) a gate fails exactly one clearly-named test.

test_wide_base_does_not_fire is the load-bearing one: the original bug was a
consolidation leg that could never PASS; the subtler future bug is a leg that
never FAILS. It proves the leg actually gates (handoff Q7)."""

from __future__ import annotations

import math

import pandas as pd

from goat import config, heartbeat

_BASE_WINDOW = config.GOAT_HEARTBEAT_MIN_DURATION_DAYS  # 63
_MIN_LEN = (
    config.GOAT_MA_LONG_DAYS
    + _BASE_WINDOW
    + config.GOAT_HEARTBEAT_MA_LONG_SLOPE_LOOKBACK_DAYS
    + config.GOAT_SECTOR_CROSS_RECENCY_DAYS
)  # 243


def _dates(n: int, start: str = "2024-01-01") -> pd.DatetimeIndex:
    return pd.date_range(start, periods=n, freq="D")


def _series(prices: list[float]) -> pd.Series:
    return pd.Series(prices, index=_dates(len(prices)))


def _ramp(n: int, start: float, end: float) -> list[float]:
    return [start + (end - start) * i / (n - 1) for i in range(n)]


def _osc_base(n: int, start: float, end: float, amp: float) -> list[float]:
    """A base that drifts linearly start -> end with a small sine oscillation on
    top. A gentle downward drift keeps the closes below the lagging 50-day MA
    through the back half of the window, so the only fresh 50DMA cross is the
    breakout tail (a purely centered oscillation chops across the flat MA and
    produces spurious mid-base crosses)."""
    return [start + (end - start) * i / (n - 1) + amp * math.sin(i / 3.0) for i in range(n)]


def _breakout_tail(n: int, level: float, jump: float, step: float = 1.4) -> list[float]:
    return [level + jump + i * step for i in range(n)]


def _drop_tail(n: int, level: float, drop: float, step: float = 1.4) -> list[float]:
    return [level - drop - i * step for i in range(n)]


def _valid_heartbeat(
    *,
    lead_start: float = 74.0,
    lead_end: float = 107.0,
    base_start: float = 101.0,
    base_end: float = 98.5,
    base_amp: float = 0.9,
    tail_n: int = 6,
    tail_jump: float = 4.0,
) -> pd.Series:
    """~215-day rising lead-in (150-day MA slopes up, ends below the base) ->
    ~63-day tight base drifting gently down and sitting on/above a flat-to-rising
    150-day MA while below the elevated 50-day MA -> short steep breakout tail
    that crosses back above the 50-day MA. Every `data` metric of this series
    sits comfortably mid-gate; each negative case below perturbs exactly one
    input."""
    lead = _ramp(215, lead_start, lead_end)
    base = _osc_base(_BASE_WINDOW + 1, base_start, base_end, base_amp)
    tail = _breakout_tail(tail_n, base[-1], tail_jump)
    return _series(lead + base + tail)


def test_fires_on_tight_base_then_fresh_breakout():
    result = heartbeat.check_heartbeat_breakout("AAPL", "Technology", _valid_heartbeat())
    assert result.verdict == "interesting"
    assert result.data["crossed_above"] is True
    assert result.data["slope_up"] is True
    assert result.data["ma150_slope_up"] is True
    assert result.data["base_range_pct"] <= config.GOAT_HEARTBEAT_BASE_RANGE_MAX_PCT
    assert result.data["base_smoothness_fraction"] >= config.GOAT_HEARTBEAT_BASE_SMOOTHNESS_MIN_FRACTION
    assert result.data["base_below_ma50_fraction"] >= config.GOAT_HEARTBEAT_BASE_BELOW_MA50_MIN_FRACTION
    assert result.data["max_dip_below_ma150_pct"] <= config.GOAT_HEARTBEAT_MA_LONG_TOLERANCE_PCT


def test_wide_base_does_not_fire():
    """Gating-proof regression test (handoff Q7). The breakout leg still passes;
    the base's high-low close range blows past the tightness ceiling, so the
    verdict must stay 'ok'."""
    close = _valid_heartbeat(base_start=108.0, base_end=92.0, base_amp=2.0, tail_jump=7.0)
    result = heartbeat.check_heartbeat_breakout("AAPL", "Technology", close)
    assert result.verdict == "ok"
    assert result.data["crossed_above"] is True
    assert result.data["slope_up"] is True
    assert result.data["base_range_pct"] > config.GOAT_HEARTBEAT_BASE_RANGE_MAX_PCT


def test_spiky_base_does_not_fire():
    """Base range stays under the ceiling, but the base is flat for weeks then
    takes one big step up and back -- fewer than the required fraction of days
    sit inside the smooth inner band, so it is not a heartbeat."""
    flat = [100.0] * _BASE_WINDOW
    for i in range(24, 40):
        flat[i] = 112.0
    base = flat + [flat[-1]]
    close = _series(_ramp(215, 78.0, 100.0) + base + _breakout_tail(6, base[-1], 4.0))
    result = heartbeat.check_heartbeat_breakout("AAPL", "Technology", close)
    assert result.verdict == "ok"
    assert result.data["crossed_above"] is True
    assert result.data["base_range_pct"] <= config.GOAT_HEARTBEAT_BASE_RANGE_MAX_PCT
    assert result.data["base_smoothness_fraction"] < config.GOAT_HEARTBEAT_BASE_SMOOTHNESS_MIN_FRACTION


def test_price_below_150dma_during_base_does_not_fire():
    """Tight base, but a descending lead-in leaves the base sitting well below
    its 150-day MA -- the worst dip is past the tolerance."""
    close = _valid_heartbeat(lead_start=130.0, lead_end=101.0)
    result = heartbeat.check_heartbeat_breakout("AAPL", "Technology", close)
    assert result.verdict == "ok"
    assert result.data["crossed_above"] is True
    assert result.data["max_dip_below_ma150_pct"] > config.GOAT_HEARTBEAT_MA_LONG_TOLERANCE_PCT


def test_falling_150dma_does_not_fire():
    """Tight base, but the lead-in rose to a peak and has been falling since, so
    the 150-day MA is still sloping down at the breakout."""
    lead = _ramp(120, 74.0, 118.0) + _ramp(95, 118.0, 106.0)
    base = _osc_base(_BASE_WINDOW + 1, 101.0, 98.5, 0.9)
    close = _series(lead + base + _breakout_tail(6, base[-1], 4.0))
    result = heartbeat.check_heartbeat_breakout("AAPL", "Technology", close)
    assert result.verdict == "ok"
    assert result.data["crossed_above"] is True
    assert result.data["ma150_slope_up"] is False


def test_base_spent_above_ma50_does_not_fire():
    """Tight base near/above a rising 150-day MA, but a low lead-in leaves price
    sitting mostly ABOVE the 50-day MA through the base (only a final dip crosses
    down), so the tail's cross-up is not a genuine reclaim of the 50."""
    n_flat = _BASE_WINDOW + 1 - 7
    base = [100.0 + 0.4 * math.sin(i / 3.0) for i in range(n_flat)]
    base += [100.0 - 0.9 * (j + 1) for j in range(7)]
    close = _series(_ramp(215, 78.0, 94.0) + base + _breakout_tail(6, base[-1], 5.0))
    result = heartbeat.check_heartbeat_breakout("AAPL", "Technology", close)
    assert result.verdict == "ok"
    assert result.data["crossed_above"] is True
    assert result.data["base_below_ma50_fraction"] < config.GOAT_HEARTBEAT_BASE_BELOW_MA50_MIN_FRACTION


def test_insufficient_history_is_unknown():
    close = _series([100.0] * (_MIN_LEN - 1))
    result = heartbeat.check_heartbeat_breakout("AAPL", "Technology", close)
    assert result.verdict == "unknown"


def test_stale_cross_does_not_fire():
    close = _valid_heartbeat(tail_n=config.GOAT_SECTOR_CROSS_RECENCY_DAYS + 12)
    result = heartbeat.check_heartbeat_breakout("AAPL", "Technology", close)
    assert result.verdict == "ok"
    assert result.data["trading_days_since_cross"] > config.GOAT_SECTOR_CROSS_RECENCY_DAYS


def test_no_cross_in_history_is_ok():
    close = _series([100.0] * (_MIN_LEN + 25))
    result = heartbeat.check_heartbeat_breakout("AAPL", "Technology", close)
    assert result.verdict == "ok"


def test_downside_cross_does_not_fire():
    base = _osc_base(_BASE_WINDOW + 1, 101.0, 100.0, 0.8)
    close = _series(_ramp(215, 80.0, 101.0) + base + _drop_tail(6, base[-1], 5.0))
    result = heartbeat.check_heartbeat_breakout("AAPL", "Technology", close)
    assert result.verdict == "ok"
    assert result.data["crossed_above"] is False
