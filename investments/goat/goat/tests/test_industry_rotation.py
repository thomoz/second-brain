from __future__ import annotations

import pandas as pd

from goat import config, industry_rotation


def _dates(n: int, start: str = "2026-01-01") -> pd.DatetimeIndex:
    return pd.date_range(start, periods=n, freq="D")


def _flat_then_move(n_flat: int, tail_prices: list[float], flat_price: float = 100.0) -> pd.Series:
    prices = [flat_price] * n_flat + tail_prices
    return pd.Series(prices, index=_dates(len(prices)))


def test_rank_industries_orders_by_window_return_missing_data_sorts_last():
    window = config.GOAT_INDUSTRY_RANK_WINDOW_TRADING_DAYS
    up = _flat_then_move(0, [100.0] * window + [110.0])
    down = _flat_then_move(0, [100.0] * window + [95.0])
    flat = _flat_then_move(0, [100.0] * window + [100.0])

    closes = {
        "ITA": up, "JETS": down, "CARZ": flat, "KBWB": None,
    }
    fake_etfs = {
        "ITA": "Aerospace & Defense", "JETS": "Airlines",
        "CARZ": "Auto Manufacturers", "KBWB": "Banks - Diversified",
    }
    import goat.config as goat_config
    orig = goat_config.GOAT_INDUSTRY_ETFS
    goat_config.GOAT_INDUSTRY_ETFS = fake_etfs
    try:
        rows = industry_rotation.rank_industries(closes)
    finally:
        goat_config.GOAT_INDUSTRY_ETFS = orig

    assert [r["ticker"] for r in rows] == ["ITA", "CARZ", "JETS", "KBWB"]
    assert rows[-1]["return_pct"] is None
    assert rows[-1]["rank"] == 4
    assert rows[0]["rising"] is True
    assert rows[2]["rising"] is False
    assert rows[0]["industry_label"] == "Aerospace & Defense"
