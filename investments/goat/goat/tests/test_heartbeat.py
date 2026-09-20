"""Deterministic pd.Series inputs, no network, no DB -- check_heartbeat_breakout
is pure compute. Redesigned 2026-09-20 (five times, same day): drop every
moving-average-relative gate; drop the breakout requirement entirely; extend
the base window 63 -> 126 trading days (a real false positive -- BAC/CAH each
rallied then reversed sharply within a 3-month window and still read as a
tight, 100%-smooth base); reject a base that has broken down; and require a
real swing rhythm, not a single directional move (prompted by real "great
heartbeat" chart examples Shaun shared -- XLE/SMH/XBI -- whose common thread
was several repeated up-down swings, not just a narrow overall range).

Fixtures that expect "interesting" now use a bigger oscillation amplitude
(3.0, not the original 0.9) so they clear GOAT_HEARTBEAT_SWING_MIN_REVERSAL_PCT
and register enough swings -- range/smoothness still pass comfortably at this
amplitude (well under the 15%/8% ceilings).

Whether a breakout (above the base) has happened is neither required nor
excluded, so there is no "already broken out" negative-case test below -- that
would be testing a gate the check deliberately does not have. Breaking DOWN
below the base and lacking swing rhythm ARE gates -- see
test_recent_breakdown_below_settled_base_does_not_fire and
test_single_arc_lacks_enough_swings_does_not_fire.

test_wide_base_does_not_fire and test_spiky_base_does_not_fire are the
load-bearing ones: each base-tightness gate gets a dedicated case where that
gate is the one being proven, so a regression that weakens (or removes) a gate
fails exactly one clearly-named test."""

from __future__ import annotations

import math

import pandas as pd

from goat import config, heartbeat

_BASE_WINDOW = config.GOAT_HEARTBEAT_MIN_DURATION_DAYS  # 126


def _dates(n: int, start: str = "2024-01-01") -> pd.DatetimeIndex:
    return pd.date_range(start, periods=n, freq="D")


def _series(prices: list[float]) -> pd.Series:
    return pd.Series(prices, index=_dates(len(prices)))


def _osc_base(n: int, level: float, amp: float) -> list[float]:
    """A flat base with a sine oscillation on top -- the webinar's own 'smooth
    up-down-up-down' shape, narrow and smooth by construction. amp=3.0 (the
    default call site value used below) clears the 3% swing-reversal threshold
    with margin while staying well inside the 15%/8% range/smoothness ceilings."""
    return [level + amp * math.sin(i / 3.0) for i in range(n)]


def test_fires_on_tight_smooth_base():
    close = _series(_osc_base(_BASE_WINDOW, 100.0, 3.0))
    result = heartbeat.check_heartbeat_breakout("AAPL", "Technology", close)
    assert result.verdict == "interesting"
    assert result.data["base_range_pct"] <= config.GOAT_HEARTBEAT_BASE_RANGE_MAX_PCT
    assert result.data["base_smoothness_fraction"] >= config.GOAT_HEARTBEAT_BASE_SMOOTHNESS_MIN_FRACTION
    assert result.data["broke_down"] is False
    assert result.data["swing_count"] >= config.GOAT_HEARTBEAT_MIN_SWINGS


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
    sit inside the smooth inner band, so it is not a heartbeat. Spike width is
    proportional to the base window (1/4 of it), matching the original 16-of-63
    ratio the old 63-day fixture used."""
    spike_days = _BASE_WINDOW // 4
    flat = [100.0] * _BASE_WINDOW
    for i in range(_BASE_WINDOW // 4, _BASE_WINDOW // 4 + spike_days):
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
    """The settled (older) part of the base oscillates between ~97 and ~103;
    the most recent GOAT_HEARTBEAT_BREAKDOWN_RECENT_DAYS sit flat at 99.5 --
    below the base's own top (so a breakout is correctly reported as not
    having happened yet) but still above the settled floor (so this is NOT a
    breakdown and the check still fires)."""
    recent_days = config.GOAT_HEARTBEAT_BREAKDOWN_RECENT_DAYS
    settled = _osc_base(_BASE_WINDOW - recent_days, 100.0, 3.0)
    recent = [99.5] * recent_days
    close = _series(settled + recent)
    result = heartbeat.check_heartbeat_breakout("AAPL", "Technology", close)
    assert result.verdict == "interesting"
    assert result.data["broke_down"] is False
    base_high = max(settled + recent)
    assert result.data["pct_below_base_high"] == round((base_high - 99.5) / base_high * 100, 2)
    assert result.data["pct_below_base_high"] > 0


def test_fires_even_when_price_is_already_at_its_own_base_high():
    """Proves the check does not exclude a name that has already moved to (or
    through) the top of its base -- a breakout is neither required nor
    disqualifying, only ever not evaluated. The base itself still needs real
    swing rhythm to fire, so this oscillates like the other positive cases,
    with one final day set as a fresh high."""
    settled = _osc_base(_BASE_WINDOW - 1, 100.0, 3.0)
    final_high = max(settled) + 0.5
    close = _series(settled + [final_high])
    result = heartbeat.check_heartbeat_breakout("AAPL", "Technology", close)
    assert result.verdict == "interesting"
    assert result.data["pct_below_base_high"] <= 0
    assert result.data["broke_down"] is False


def test_recent_breakdown_below_settled_base_does_not_fire():
    """The settled (older) part of the base is a tight, smooth, swinging
    oscillation -- on its own this would fire. But the most recent
    GOAT_HEARTBEAT_BREAKDOWN_RECENT_DAYS have dropped to 97, below that settled
    floor: a real breakdown, not a heartbeat, regardless of the overall range/
    smoothness/swing stats still technically passing."""
    recent_days = config.GOAT_HEARTBEAT_BREAKDOWN_RECENT_DAYS
    settled = _osc_base(_BASE_WINDOW - recent_days, 100.0, 3.0)
    recent = [96.0] * recent_days
    close = _series(settled + recent)
    result = heartbeat.check_heartbeat_breakout("AAPL", "Technology", close)
    assert result.verdict == "ok"
    assert result.data["broke_down"] is True
    assert "breakdown" in result.detail


def test_single_arc_lacks_enough_swings_does_not_fire():
    """A clean, single up-move then single down-move (no repeated rhythm) --
    narrow (6% range), 100% smooth, and not broken down (ends back at its
    starting level), so the older gates alone would pass this. This is
    exactly the BAC/CAH failure mode in miniature: one directional round-trip
    that stays inside tolerance is not a heartbeat, and only the swing-count
    gate catches it."""
    n = _BASE_WINDOW // 2
    up = [97.0 + 6.0 * i / (n - 1) for i in range(n)]
    down = [103.0 - 6.0 * i / (n - 1) for i in range(n)]
    close = _series(up + down)
    result = heartbeat.check_heartbeat_breakout("AAPL", "Technology", close)
    assert result.verdict == "ok"
    assert result.data["base_range_pct"] <= config.GOAT_HEARTBEAT_BASE_RANGE_MAX_PCT
    assert result.data["base_smoothness_fraction"] >= config.GOAT_HEARTBEAT_BASE_SMOOTHNESS_MIN_FRACTION
    assert result.data["broke_down"] is False
    assert result.data["swing_count"] < config.GOAT_HEARTBEAT_MIN_SWINGS
    assert "rhythm" in result.detail


def test_count_swings_ignores_noise_below_threshold():
    """Day-to-day wiggles smaller than the reversal threshold (here ~0.5%,
    well under the 3% default) must never register as their own swings."""
    noisy_flat = _series([100.0 + (0.5 if i % 2 == 0 else -0.5) for i in range(40)])
    assert heartbeat._count_swings(noisy_flat, config.GOAT_HEARTBEAT_SWING_MIN_REVERSAL_PCT) == 0


def test_count_swings_counts_genuine_reversals():
    """Three clear legs (up 10%, down 10%, up 10%) -- two confirmed reversals."""
    close = _series([100.0, 110.0, 99.0, 108.9])
    assert heartbeat._count_swings(close, config.GOAT_HEARTBEAT_SWING_MIN_REVERSAL_PCT) == 2
