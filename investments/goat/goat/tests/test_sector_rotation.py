from __future__ import annotations

import pandas as pd

from goat import config, sector_rotation


def _dates(n: int, start: str = "2026-01-01") -> pd.DatetimeIndex:
    return pd.date_range(start, periods=n, freq="D")


def _flat_then_move(n_flat: int, tail_prices: list[float], flat_price: float = 100.0) -> pd.Series:
    prices = [flat_price] * n_flat + tail_prices
    return pd.Series(prices, index=_dates(len(prices)))


def _series_with_cross(
    days_since_cross: int, rising: bool = True, crossed_above: bool = True,
) -> pd.Series:
    """Builds a series that sits below its 50DMA, then jumps (or drops) so the
    close crosses the 50DMA exactly `days_since_cross` trading days before the
    series' last row, and stays on that side of the MA through to the end so the
    50DMA itself slopes up. Only used for rising=True scenarios -- see
    `_declining_then_spike_series` for the wrong-slope (rising=False) case, which
    needs a genuinely different construction (a sustained decline the recent spike
    hasn't yet reversed), not just a smaller jump."""
    assert rising, "use _declining_then_spike_series for a falling-MA scenario"
    ma_days = config.GOAT_SECTOR_MA_SHORT_DAYS
    lead_in = ma_days + config.GOAT_SECTOR_SLOPE_LOOKBACK_DAYS + 20
    pre_price = 90.0 if crossed_above else 110.0
    post_price = 130.0 if crossed_above else 70.0

    prices = [pre_price] * lead_in + [post_price] * (days_since_cross + 1)
    return pd.Series(prices, index=_dates(len(prices)))


def _declining_then_spike_series(days_since_cross: int = 1, n_decline: int = 250, spike: float = 20.0) -> pd.Series:
    """A steadily declining price series (so the 50DMA is clearly sloping down)
    with a recent upward spike that crosses the close back above the 50DMA
    `days_since_cross` trading days ago -- the spike is too small/recent to have
    turned the MA's own slope yet, so this is a genuine "crossed above, but MA
    still falling" case (unlike a plain smaller jump, which nudges the MA up
    immediately since it's already inside the rolling window)."""
    prices = [200.0 - i * 0.3 for i in range(n_decline)]
    spike_pos = len(prices) - 1 - days_since_cross
    for i in range(spike_pos, len(prices)):
        prices[i] = prices[spike_pos - 1] + spike
    return pd.Series(prices, index=_dates(len(prices)))


def test_rank_sectors_orders_by_window_return_missing_data_sorts_last():
    window = config.GOAT_SECTOR_RANK_WINDOW_TRADING_DAYS
    up = _flat_then_move(0, [100.0] * window + [110.0])
    down = _flat_then_move(0, [100.0] * window + [95.0])
    flat = _flat_then_move(0, [100.0] * window + [100.0])

    closes = {
        "XLK": up, "XLF": down, "XLE": flat, "XLV": None,
    }
    fake_etfs = {"XLK": "Technology", "XLF": "Financials", "XLE": "Energy", "XLV": "Health Care"}
    import goat.config as goat_config
    orig = goat_config.GOAT_SECTOR_ETFS
    goat_config.GOAT_SECTOR_ETFS = fake_etfs
    try:
        rows = sector_rotation.rank_sectors(closes)
    finally:
        goat_config.GOAT_SECTOR_ETFS = orig

    assert [r["ticker"] for r in rows] == ["XLK", "XLE", "XLF", "XLV"]
    assert rows[-1]["return_pct"] is None
    assert rows[-1]["rank"] == 4
    assert rows[0]["rising"] is True
    assert rows[2]["rising"] is False


def test_check_sector_breakout_fires_on_fresh_cross_with_rising_ma():
    close = _series_with_cross(days_since_cross=config.GOAT_SECTOR_CROSS_RECENCY_DAYS, rising=True, crossed_above=True)
    result = sector_rotation.check_sector_breakout("XLK", "Technology", close)
    assert result.verdict == "interesting"
    assert result.data["crossed_above"] is True
    assert result.data["slope_up"] is True


def test_check_sector_breakout_stale_cross_does_not_fire():
    close = _series_with_cross(
        days_since_cross=config.GOAT_SECTOR_CROSS_RECENCY_DAYS + 5, rising=True, crossed_above=True,
    )
    result = sector_rotation.check_sector_breakout("XLK", "Technology", close)
    assert result.verdict == "ok"


def test_check_sector_breakout_wrong_slope_does_not_fire():
    close = _declining_then_spike_series(days_since_cross=1)
    result = sector_rotation.check_sector_breakout("XLK", "Technology", close)
    assert result.verdict == "ok"
    assert result.data["crossed_above"] is True
    assert result.data["slope_up"] is False


def test_check_sector_breakout_downside_cross_does_not_fire():
    close = _series_with_cross(days_since_cross=1, rising=True, crossed_above=False)
    result = sector_rotation.check_sector_breakout("XLK", "Technology", close)
    assert result.verdict == "ok"
    assert result.data["crossed_above"] is False


def test_check_sector_breakout_no_cross_in_history_is_ok():
    close = pd.Series(
        [100.0] * (config.GOAT_SECTOR_MA_SHORT_DAYS + config.GOAT_SECTOR_SLOPE_LOOKBACK_DAYS + 30),
        index=_dates(config.GOAT_SECTOR_MA_SHORT_DAYS + config.GOAT_SECTOR_SLOPE_LOOKBACK_DAYS + 30),
    )
    result = sector_rotation.check_sector_breakout("XLK", "Technology", close)
    assert result.verdict == "ok"


def test_check_sector_breakout_insufficient_history_is_unknown():
    close = pd.Series([100.0] * 10, index=_dates(10))
    result = sector_rotation.check_sector_breakout("XLK", "Technology", close)
    assert result.verdict == "unknown"
