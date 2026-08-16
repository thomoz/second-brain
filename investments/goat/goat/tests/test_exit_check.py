from __future__ import annotations

import pandas as pd

from goat import config, exit_check


def _dates(n: int, start: str = "2026-01-01") -> pd.DatetimeIndex:
    return pd.date_range(start, periods=n, freq="D")


def _flat_then(tail_prices: list[float], flat_price: float = 100.0) -> pd.Series:
    """GOAT_MA_LONG_DAYS days at `flat_price`, followed by `tail_prices` -- the
    flat lead-in keeps the 150-day rolling MA stable (~flat_price) regardless of
    what the tail does, so each test only has to reason about the tail."""
    n_flat = config.GOAT_MA_LONG_DAYS
    prices = [flat_price] * n_flat + tail_prices
    return pd.Series(prices, index=_dates(len(prices)))


def test_price_above_ma_is_ok():
    """With GOAT_150DMA_FLAG_PCT at 0.0 (Shaun's 2026-08-16 override, see
    config.py), a price sitting exactly AT the MA now also qualifies as a flag
    ("at or below" -- zero buffer means even touching it counts, matching "as
    soon as it crosses, not X% after"). Only strictly ABOVE the MA is "ok"."""
    close = _flat_then([100.5, 100.5])
    result = exit_check.check_150dma_exit("ABOVE", close)
    assert result.verdict == "ok"


def test_flags_when_below_threshold_for_two_consecutive_days():
    close = _flat_then([85.0, 85.0])
    result = exit_check.check_150dma_exit("DROP", close)
    assert result.verdict == "flag"
    assert result.data["pct_below"] >= config.GOAT_150DMA_FLAG_PCT


def test_flags_immediately_on_single_qualifying_day():
    """Only today qualifies, yesterday didn't. Originally this was the whipsaw
    case that stayed unflagged (source notes warn "sometimes prices break
    through it slightly but come back up above") -- Shaun explicitly overrode
    the whipsaw filter 2026-08-16 (GOAT_150DMA_MIN_CONSECUTIVE_DAYS: 2 -> 1,
    GOAT_150DMA_FLAG_PCT: 6.0 -> 0.0) wanting the earliest possible alert and
    knowingly accepting this exact false-positive risk in exchange for speed."""
    close = _flat_then([100.0, 85.0])
    result = exit_check.check_150dma_exit("IMMEDIATE", close)
    assert result.verdict == "flag"


def test_does_not_flag_when_recovered_before_two_days_elapse():
    """Dropped 3 days ago, recovered above threshold for the most recent 2 days --
    confirms the check looks at the *current* tail state, not "ever happened"."""
    close = _flat_then([85.0, 100.0, 100.0])
    result = exit_check.check_150dma_exit("RECOVERED", close)
    assert result.verdict == "ok"


def test_insufficient_history_is_unknown():
    close = pd.Series([100.0] * 50, index=_dates(50))
    result = exit_check.check_150dma_exit("NEWLISTING", close)
    assert result.verdict == "unknown"


def test_flags_at_the_threshold_boundary_using_gte_not_gt():
    """Solve for the tail price where the last day's %-below-MA lands almost
    exactly on GOAT_150DMA_FLAG_PCT (accounting for the two tail points' own
    dilution of the rolling MA), then nudge a hair either side -- confirms the
    detector's `>=` comparison is inclusive at the boundary rather than requiring
    a strict `>`."""
    n_flat = config.GOAT_MA_LONG_DAYS
    w = config.GOAT_150DMA_MIN_CONSECUTIVE_DAYS  # tail points inside the last window
    p = config.GOAT_150DMA_FLAG_PCT
    k = 1 - p / 100
    x_at_threshold = k * (n_flat - w) * 100 / (n_flat - k * w)

    close_flag = _flat_then([x_at_threshold - 0.01, x_at_threshold - 0.01])
    assert exit_check.check_150dma_exit("AT_OR_BELOW", close_flag).verdict == "flag"

    close_ok = _flat_then([x_at_threshold + 0.5, x_at_threshold + 0.5])
    assert exit_check.check_150dma_exit("JUST_ABOVE", close_ok).verdict == "ok"


# --- check_150dma_exit_live -----------------------------------------------


def _flat_history(n: int = config.GOAT_MA_LONG_DAYS, flat_price: float = 100.0) -> pd.Series:
    return pd.Series([flat_price] * n, index=_dates(n))


def test_live_price_above_ma_is_ok():
    close = _flat_history()
    result = exit_check.check_150dma_exit_live("ABOVE", close, live_price=100.5)
    assert result.verdict == "ok"


def test_live_price_at_or_below_ma_flags_immediately():
    """With GOAT_150DMA_MIN_CONSECUTIVE_DAYS == 1 (current live config value), a
    single live price at/below the MA flags immediately, same semantics as the
    daily check's test_flags_immediately_on_single_qualifying_day."""
    close = _flat_history()
    result = exit_check.check_150dma_exit_live("DROP", close, live_price=85.0)
    assert result.verdict == "flag"
    assert result.data["pct_below"] >= config.GOAT_150DMA_FLAG_PCT


def test_live_check_does_not_let_live_price_affect_the_ma():
    """Regression test for the GOTCHA in exit_check.check_150dma_exit_live's
    docstring: the 150-day MA must come only from `close` (completed days), never
    from `live_price`. Must fail if someone "fixes" the implementation by
    concatenating live_price onto close before computing the rolling mean."""
    close = _flat_history(flat_price=100.0)
    result = exit_check.check_150dma_exit_live("WILD", close, live_price=1.0)
    assert result.data["ma"] == 100.0


def test_live_check_insufficient_history_is_unknown():
    close = pd.Series([100.0] * 50, index=_dates(50))
    result = exit_check.check_150dma_exit_live("NEWLISTING", close, live_price=80.0)
    assert result.verdict == "unknown"


def test_live_check_persistence_across_prior_completed_days_and_today(monkeypatch):
    """Even though the live default for GOAT_150DMA_MIN_CONSECUTIVE_DAYS is 1,
    prove the n_prior_needed generalization holds for N=2: today's live price
    qualifying alone is not enough if the prior completed day didn't also
    qualify, and vice versa -- both must qualify to flag."""
    monkeypatch.setattr(config, "GOAT_150DMA_MIN_CONSECUTIVE_DAYS", 2)

    # Prior completed day (yesterday) already qualifies (85, well below the 100
    # flat MA); today's live price also qualifies -- must flag.
    close_both_qualify = _flat_then([85.0])
    result = exit_check.check_150dma_exit_live("BOTH", close_both_qualify, live_price=85.0)
    assert result.verdict == "flag"

    # Prior completed day recovered (100.5, above MA); only today's live price
    # qualifies -- must NOT flag, since persistence requires both days.
    close_prior_recovered = _flat_then([100.5])
    result = exit_check.check_150dma_exit_live("TODAY_ONLY", close_prior_recovered, live_price=85.0)
    assert result.verdict == "ok"
