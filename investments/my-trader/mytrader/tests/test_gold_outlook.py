from __future__ import annotations

import pandas as pd

from mytrader import config, gold_backtest, gold_outlook
from mytrader.checks import CheckResult


def _dates(n: int, start: str = "2020-01-01") -> pd.DatetimeIndex:
    return pd.date_range(start, periods=n, freq="D")


def _technicals(**overrides) -> dict:
    base = {
        "trend": {
            "price": 100.0, "price_above_ma20": True, "price_above_ma50": True,
            "price_above_ma200": True,
        },
        "macd": {"macd": 1.0, "signal": 0.5, "histogram": 0.5},
        "rsi": 60.0,
        "stochastic": {"k": 80.0, "d": 60.0},
        "atr": 2.0,
        "levels": {"resistance": 110.0, "support": 90.0},
        "volume": {"above_average": True},
        "seasonality": {"n": 10, "mean": 1.0, "median": 1.0},
    }
    base.update(overrides)
    return base


def _macro_check(name: str, direction: str | None) -> CheckResult:
    return CheckResult(
        name=name, verdict="flag" if direction else "ok", detail="", data={"direction": direction},
    )


def _macro_checks(**directions: str | None) -> list[CheckResult]:
    return [_macro_check(name, direction) for name, direction in directions.items()]


# -- _horizon_read -------------------------------------------------------

def test_horizon_read_scores_only_entries_with_historical_data():
    states = {"vix": "elevated", "real_yields": "negative", "dollar_index": "rising"}
    backtest_results = {
        ("vix", "elevated", "day", 1): {
            "n": 10, "mean": 1.0, "baseline": {"mean": 0.1}, "win_rate": 60.0,
        },
        # real_yields present in states but absent from backtest_results entirely.
        ("dollar_index", "rising", "day", 1): {
            "n": 0, "mean": None, "baseline": {"mean": None}, "win_rate": None,
        },
    }
    read = gold_outlook._horizon_read(states, backtest_results, "day", 1)
    # Only vix has real (n>0) historical data -- real_yields (no row at all) and
    # dollar_index (n=0 row) must both be silently omitted, never scored as 0/neutral.
    assert set(read["components"]) == {"vix"}
    assert read["components"]["vix"] == "bullish"


def test_horizon_read_ignores_neutral_and_none_states():
    states = {"rsi_zone": "neutral", "macd_histogram": "flat", "ma20_trend": "equal", "vix": None}
    backtest_results = {
        ("rsi_zone", "neutral", "day", 1): {"n": 100, "mean": 5.0, "baseline": {"mean": 0.0}, "win_rate": 70.0},
    }
    read = gold_outlook._horizon_read(states, backtest_results, "day", 1)
    assert read["components"] == {}


# -- _synthesize_label -----------------------------------------------------

def test_synthesize_label_counts_and_labels_correctly():
    assert gold_outlook._synthesize_label({}) == "insufficient historical data for today's active signals"

    bullish_lean = gold_outlook._synthesize_label({"a": "bullish", "b": "bullish", "c": "bearish"})
    assert bullish_lean == "bullish lean (2/3)"

    bearish_lean = gold_outlook._synthesize_label({"a": "bearish", "b": "bearish", "c": "bullish"})
    assert bearish_lean == "bearish lean (2/3)"

    mixed = gold_outlook._synthesize_label({"a": "bullish", "b": "bearish"})
    assert mixed == "mixed (1 bullish / 1 bearish / 0 neutral)"


# -- Cross-module state-string consistency (the single most important test in
# this feature -- see .agent/plans/gold-tracker-phase2-outlook.md Task 4.1's
# GOTCHA: a silent string mismatch here means a signal just vanishes from the
# outlook with no error anywhere). -----------------------------------------

def test_live_state_ma20_trend_matches_gold_backtest_state_ma_trend():
    close = pd.Series([10.0, 10.0, 20.0], index=_dates(3))  # ma(2) at idx2 = 15, close=20 -> above
    expected = gold_backtest.state_ma_trend(close, 2).iloc[-1]
    technicals = _technicals(trend={
        "price": 20.0, "price_above_ma20": True, "price_above_ma50": True, "price_above_ma200": True,
    })
    live_states = gold_outlook._live_signal_states(technicals, [])
    assert live_states["ma20_trend"] == expected == "above"

    close_below = pd.Series([10.0, 10.0, 5.0], index=_dates(3))  # ma(2)=10, close=5 -> below
    expected_below = gold_backtest.state_ma_trend(close_below, 2).iloc[-1]
    technicals_below = _technicals(trend={
        "price": 5.0, "price_above_ma20": False, "price_above_ma50": True, "price_above_ma200": True,
    })
    live_states_below = gold_outlook._live_signal_states(technicals_below, [])
    assert live_states_below["ma20_trend"] == expected_below == "below"


def test_live_state_ma50_trend_matches_gold_backtest_state_ma_trend():
    close = pd.Series([10.0, 10.0, 20.0], index=_dates(3))
    expected = gold_backtest.state_ma_trend(close, 2).iloc[-1]
    technicals = _technicals(trend={
        "price": 20.0, "price_above_ma20": True, "price_above_ma50": True, "price_above_ma200": True,
    })
    live_states = gold_outlook._live_signal_states(technicals, [])
    assert live_states["ma50_trend"] == expected == "above"


def test_live_state_macd_histogram_matches_gold_backtest_state(monkeypatch):
    monkeypatch.setattr(config, "GOLD_TA_MACD_FAST_DAYS", 2)
    monkeypatch.setattr(config, "GOLD_TA_MACD_SLOW_DAYS", 3)
    monkeypatch.setattr(config, "GOLD_TA_MACD_SIGNAL_DAYS", 2)
    close = pd.Series([10.0 * (i + 1) for i in range(8)], index=_dates(8))  # rising -> positive histogram
    expected = gold_backtest.state_macd_histogram(close).iloc[-1]
    technicals = _technicals(macd={"macd": 1.0, "signal": 0.5, "histogram": 0.5})  # positive
    live_states = gold_outlook._live_signal_states(technicals, [])
    assert live_states["macd_histogram"] == expected == "positive"


def test_live_state_macd_crossover_matches_gold_backtest_state(monkeypatch):
    monkeypatch.setattr(config, "GOLD_TA_MACD_FAST_DAYS", 2)
    monkeypatch.setattr(config, "GOLD_TA_MACD_SLOW_DAYS", 3)
    monkeypatch.setattr(config, "GOLD_TA_MACD_SIGNAL_DAYS", 2)
    close = pd.Series([10.0 * (i + 1) for i in range(8)], index=_dates(8))
    expected = gold_backtest.state_macd_crossover(close).iloc[-1]
    technicals = _technicals(macd={"macd": 1.0, "signal": 0.5, "histogram": 0.5})  # macd > signal
    live_states = gold_outlook._live_signal_states(technicals, [])
    assert live_states["macd_crossover"] == expected == "above"


def test_live_state_rsi_zone_matches_gold_backtest_state(monkeypatch):
    monkeypatch.setattr(config, "GOLD_TA_RSI_BULLISH_ABOVE", 55.0)
    monkeypatch.setattr(config, "GOLD_TA_RSI_BEARISH_BELOW", 45.0)
    close = pd.Series([float(i) for i in range(1, 20)], index=_dates(19))  # monotonic gains -> RSI 100
    expected = gold_backtest.state_rsi_zone(close).iloc[-1]
    technicals = _technicals(rsi=100.0)
    live_states = gold_outlook._live_signal_states(technicals, [])
    assert live_states["rsi_zone"] == expected == "elevated"


def test_live_state_stochastic_crossover_matches_gold_backtest_state(monkeypatch):
    monkeypatch.setattr(config, "GOLD_TA_STOCH_PERIOD_DAYS", 3)
    monkeypatch.setattr(config, "GOLD_TA_STOCH_SMOOTHING_DAYS", 2)
    df = pd.DataFrame(
        {
            "High": [10.0, 10.0, 15.0, 15.0], "Low": [8.0, 8.0, 8.0, 8.0],
            "Close": [9.0, 9.0, 11.5, 15.0],
        },
        index=_dates(4),
    )  # k=100, d=75 -> above
    expected = gold_backtest.state_stochastic_crossover(df).iloc[-1]
    technicals = _technicals(stochastic={"k": 100.0, "d": 75.0})
    live_states = gold_outlook._live_signal_states(technicals, [])
    assert live_states["stochastic_crossover"] == expected == "above"


def test_live_state_macro_signals_match_gold_backtest_episode_directions(monkeypatch):
    monkeypatch.setattr(config, "GOLD_BACKTEST_MIN_EPISODE_GAP_DAYS", 10)
    monkeypatch.setattr(config, "REAL_YIELD_FLAG_NEGATIVE_PCT", 0.0)
    monkeypatch.setattr(config, "VIX_FLAG_LEVEL", 30.0)
    monkeypatch.setattr(config, "GOLD_SILVER_RATIO_FLAG_HIGH", 80.0)
    monkeypatch.setattr(config, "GOLD_SILVER_RATIO_FLAG_LOW", 50.0)

    real_yield_series = pd.Series([-0.5], index=_dates(1))
    real_yield_episodes = gold_backtest.find_real_yield_episodes(real_yield_series)
    vix_series = pd.Series([35.0], index=_dates(1))
    vix_episodes = gold_backtest.find_vix_episodes(vix_series)
    gold = pd.Series([4400.0], index=_dates(1))
    silver = pd.Series([50.0], index=_dates(1))  # ratio 88 -> high
    ratio_episodes = gold_backtest.find_gold_silver_ratio_episodes(gold, silver)

    macro_checks = _macro_checks(
        real_yields="negative", dollar_index="rising", gold_trend="crossed_below",
        gold_silver_ratio="high", vix="elevated",
    )
    live_states = gold_outlook._live_signal_states(_technicals(), macro_checks)

    assert live_states["real_yields"] == real_yield_episodes[0].direction == "negative"
    assert live_states["vix"] == vix_episodes[0].direction == "elevated"
    assert live_states["gold_silver_ratio"] == ratio_episodes[0].direction == "high"
    assert live_states["dollar_index"] == "rising"
    assert live_states["gold_trend"] == "crossed_below"


# -- Horizon builders query distinct horizons --------------------------------

def test_build_today_week_month_reads_query_different_horizons():
    technicals = _technicals()
    macro_checks: list[CheckResult] = []
    backtest_results = {
        ("vix", "elevated", "day", 1): {"n": 1, "mean": 100.0, "baseline": {"mean": 0.0}, "win_rate": 100.0},
        ("vix", "elevated", "day", 5): {"n": 1, "mean": 200.0, "baseline": {"mean": 0.0}, "win_rate": 100.0},
        ("vix", "elevated", "month", 1): {"n": 1, "mean": 300.0, "baseline": {"mean": 0.0}, "win_rate": 100.0},
    }
    macro_checks = _macro_checks(vix="elevated")

    today = gold_outlook.build_today_read(technicals, macro_checks, backtest_results)
    week = gold_outlook.build_week_read(technicals, macro_checks, backtest_results)
    month = gold_outlook.build_month_read(technicals, macro_checks, backtest_results)

    assert "N=1, mean 100.0%" in today["notes"][-1]
    assert "N=1, mean 200.0%" in week["notes"][-1]
    assert any("N=1, mean 300.0%" in n for n in month["notes"])


# -- Markdown rendering -------------------------------------------------------

def test_render_outlook_markdown_includes_all_three_horizon_sections():
    outlook = {
        "as_of": "2026-08-07",
        "today": {
            "direction_guess": "bullish lean (1/1)", "confidence": "low", "notes": ["note1"],
            "expected_move_dollars": 10.0, "expected_move_pct": 1.0,
            "resistance": 110.0, "support": 90.0, "volume_note": "above-average volume",
        },
        "week": {"direction_guess": "mixed", "confidence": "medium", "notes": ["note2"]},
        "month": {"direction_guess": "bearish lean (1/1)", "confidence": "high", "notes": ["note3"]},
    }
    markdown = gold_outlook.render_outlook_markdown(outlook)
    assert "### Today / Tomorrow" in markdown
    assert "### This Week" in markdown
    assert "### This Month" in markdown
    assert "note1" in markdown and "note2" in markdown and "note3" in markdown
    assert "Never a buy/sell recommendation." in markdown


def test_write_outlook_writes_to_configured_path(tmp_path, monkeypatch):
    monkeypatch.setattr("mytrader.gold_outlook.config.MY_TRADER_DIR", tmp_path)
    outlook = {
        "as_of": "2026-08-07",
        "today": {
            "direction_guess": "mixed", "confidence": "low", "notes": [],
            "expected_move_dollars": 1.0, "expected_move_pct": 1.0,
            "resistance": 1.0, "support": 1.0, "volume_note": "below-average volume",
        },
        "week": {"direction_guess": "mixed", "confidence": "medium", "notes": []},
        "month": {"direction_guess": "mixed", "confidence": "high", "notes": []},
    }
    gold_outlook.write_outlook(outlook)
    assert (tmp_path / "gold-outlook.md").exists()


# -- build_outlook orchestration ----------------------------------------------

def test_build_outlook_returns_none_when_technicals_unavailable(monkeypatch):
    monkeypatch.setattr("mytrader.gold_outlook.gold_technicals.compute_today_technicals", lambda: None)
    assert gold_outlook.build_outlook(conn=None, macro_checks=[]) is None


def test_build_outlook_degrades_when_backtest_unavailable(monkeypatch):
    monkeypatch.setattr(
        "mytrader.gold_outlook.gold_technicals.compute_today_technicals", lambda: _technicals()
    )

    def _boom(conn):
        raise RuntimeError("network down")

    monkeypatch.setattr("mytrader.gold_outlook.gold_backtest.get_cached_or_refresh", _boom)
    outlook = gold_outlook.build_outlook(conn=None, macro_checks=[])
    assert outlook is not None
    assert outlook["today"]["direction_guess"] == "insufficient historical data for today's active signals"
