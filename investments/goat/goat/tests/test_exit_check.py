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


def test_flat_price_at_ma_is_ok():
    close = _flat_then([100.0, 100.0])
    result = exit_check.check_150dma_exit("FLAT", close)
    assert result.verdict == "ok"


def test_flags_when_below_threshold_for_two_consecutive_days():
    close = _flat_then([85.0, 85.0])
    result = exit_check.check_150dma_exit("DROP", close)
    assert result.verdict == "flag"
    assert result.data["pct_below"] >= config.GOAT_150DMA_FLAG_PCT


def test_does_not_flag_on_single_day_whipsaw():
    """Only today qualifies, yesterday didn't -- the exact whipsaw case the
    source notes warn about ("sometimes prices break through it slightly but
    come back up above")."""
    close = _flat_then([100.0, 85.0])
    result = exit_check.check_150dma_exit("WHIPSAW", close)
    assert result.verdict == "ok"


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
