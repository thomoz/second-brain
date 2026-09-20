"""Deterministic pd.Series inputs, no network, no DB -- check_heartbeat_breakout
is pure compute. Redesigned 2026-09-20 (twice, same day): first to drop every
moving-average-relative gate, then to drop the breakout requirement entirely --
the check now looks only at whether the most recent
GOAT_HEARTBEAT_MIN_DURATION_DAYS closes form a tight, smooth base. Whether a
breakout has happened is neither required nor excluded, so there is no "already
broken out" negative-case test below -- that would be testing a gate the check
deliberately does not have.

test_wide_base_does_not_fire and test_spiky_base_does_not_fire are the
load-bearing ones: each base-tightness gate gets a dedicated case where that
gate is the one being proven, so a regression that weakens (or removes) a gate
fails exactly one clearly-named test."""

from __future__ import annotations

import math

import pandas as pd

from goat import config, heartbeat

_BASE_WINDOW = config.GOAT_HEARTBEAT_MIN_DURATION_DAYS  # 63


def _dates(n: int, start: str = "2024-01-01") -> pd.DatetimeIndex:
    return pd.date_range(start, periods=n, freq="D")


def _series(prices: list[float]) -> pd.Series:
    return pd.Series(prices, index=_dates(len(prices)))


def _osc_base(n: int, level: float, amp: float) -> list[float]:
    """A flat base with a small sine oscillation on top -- the webinar's own
    'smooth up-down-up-down' shape, narrow and smooth by construction."""
    return [level + amp * math.sin(i / 3.0) for i in range(n)]


def test_fires_on_tight_smooth_base():
    close = _series(_osc_base(_BASE_WINDOW, 100.0, 0.9))
    result = heartbeat.check_heartbeat_breakout("AAPL", "Technology", close)
    assert result.verdict == "interesting"
    assert result.data["base_range_pct"] <= config.GOAT_HEARTBEAT_BASE_RANGE_MAX_PCT
    assert result.data["base_smoothness_fraction"] >= config.GOAT_HEARTBEAT_BASE_SMOOTHNESS_MIN_FRACTION


def test_wide_base_does_not_fire():
    """The base's high-low close range blows past the tightness ceiling."""
    base = ([100.0, 120.0] * (_BASE_WINDOW // 2 + 1))[:_BASE_WINDOW]
    close = _series(base)
    result = heartbeat.check_heartbeat_breakout("AAPL", "Technology", close)
    assert result.verdict == "ok"
    assert result.data["base_range_pct"] > config.GOAT_HEARTBEAT_BASE_RANGE_MAX_PCT


def test_spiky_base_does_not_fire():
    """Base range stays under the ceiling, but the base is flat for weeks then
    takes one big step up and back -- fewer than the required fraction of days
    sit inside the smooth inner band, so it is not a heartbeat."""
    flat = [100.0] * _BASE_WINDOW
    for i in range(24, 40):
        flat[i] = 112.0
    close = _series(flat)
    result = heartbeat.check_heartbeat_breakout("AAPL", "Technology", close)
    assert result.verdict == "ok"
    assert result.data["base_range_pct"] <= config.GOAT_HEARTBEAT_BASE_RANGE_MAX_PCT
    assert result.data["base_smoothness_fraction"] < config.GOAT_HEARTBEAT_BASE_SMOOTHNESS_MIN_FRACTION


def test_insufficient_history_is_unknown():
    close = _series([100.0] * (_BASE_WINDOW - 1))
    result = heartbeat.check_heartbeat_breakout("AAPL", "Technology", close)
    assert result.verdict == "unknown"


def test_reports_distance_below_base_high_when_not_yet_at_it():
    """A base that ends slightly off its own high -- still fires (a breakout is
    not required), and reports how far below that high it currently sits."""
    base = [100.0] * (_BASE_WINDOW - 1) + [99.0]
    close = _series(base)
    result = heartbeat.check_heartbeat_breakout("AAPL", "Technology", close)
    assert result.verdict == "interesting"
    assert result.data["pct_below_base_high"] == round((100.0 - 99.0) / 100.0 * 100, 2)


def test_fires_even_when_price_is_already_at_its_own_base_high():
    """Proves the check does not exclude a name that has already moved to (or
    through) the top of its base -- a breakout is neither required nor
    disqualifying, only ever not evaluated."""
    base = [100.0] * (_BASE_WINDOW - 1) + [103.0]
    close = _series(base)
    result = heartbeat.check_heartbeat_breakout("AAPL", "Technology", close)
    assert result.verdict == "interesting"
    assert result.data["pct_below_base_high"] <= 0
