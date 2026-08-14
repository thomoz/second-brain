from __future__ import annotations

import pandas as pd
import pytest

from mytrader import config, gold_backtest, gold_cot, gold_outlook
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
        "seasonality": {"n": 10, "mean": 1.0, "median": 1.0, "win_rate": 70.0},
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


def test_horizon_read_excludes_oscillators_from_vote_but_keeps_them_as_context():
    states = {"ma20_trend": "above", "rsi_zone": "elevated", "macd_histogram": "positive"}
    backtest_results = {
        ("ma20_trend", "above", "day", 1): {"n": 500, "mean": 0.1, "baseline": {"mean": 0.05}, "win_rate": 58.0},
        ("rsi_zone", "elevated", "day", 1): {"n": 400, "mean": 0.2, "baseline": {"mean": 0.05}, "win_rate": 70.0},
        ("macd_histogram", "positive", "day", 1): {"n": 300, "mean": 0.15, "baseline": {"mean": 0.05}, "win_rate": 65.0},
    }
    read = gold_outlook._horizon_read(states, backtest_results, "day", 1)
    # Only the trend filter votes -- the two oscillators, despite having real
    # backtest data (even stronger win-rates than ma20_trend here), must be
    # excluded from components/weights and surfaced only as context.
    assert set(read["components"]) == {"ma20_trend"}
    assert set(read["weights"]) == {"ma20_trend"}
    assert len(read["notes"]) == 1
    assert len(read["context_notes"]) == 2
    assert all("context only, not counted in the lean" in n for n in read["context_notes"])


def test_horizon_read_ignores_neutral_and_none_states():
    states = {"rsi_zone": "neutral", "macd_histogram": "flat", "ma20_trend": "equal", "vix": None}
    backtest_results = {
        ("rsi_zone", "neutral", "day", 1): {"n": 100, "mean": 5.0, "baseline": {"mean": 0.0}, "win_rate": 70.0},
    }
    read = gold_outlook._horizon_read(states, backtest_results, "day", 1)
    assert read["components"] == {}


# -- _label / _weight -------------------------------------------------------

def test_label_uses_win_rate_above_50_as_bullish():
    assert gold_outlook._label(50.1) == "bullish"
    assert gold_outlook._label(49.9) == "bearish"
    assert gold_outlook._label(50.0) == "bearish"  # exactly 50 -- weight is 0 either way


def test_weight_is_distance_from_50_and_symmetric():
    assert gold_outlook._weight(50.0) == 0.0
    assert gold_outlook._weight(63.0) == pytest.approx(13.0)
    assert gold_outlook._weight(37.0) == pytest.approx(13.0)


# -- _synthesize_label -----------------------------------------------------

def test_synthesize_label_counts_and_labels_correctly():
    assert gold_outlook._synthesize_label({}, {}) == "insufficient historical data for today's active signals"

    # Equal weights -- headcount and weighted-edge outcome agree.
    bullish_lean = gold_outlook._synthesize_label(
        {"a": "bullish", "b": "bullish", "c": "bearish"}, {"a": 5.0, "b": 5.0, "c": 5.0}
    )
    assert bullish_lean == "bullish lean (2/3 signals, 67% of weighted edge)"

    bearish_lean = gold_outlook._synthesize_label(
        {"a": "bearish", "b": "bearish", "c": "bullish"}, {"a": 5.0, "b": 5.0, "c": 5.0}
    )
    assert bearish_lean == "bearish lean (2/3 signals, 67% of weighted edge)"

    even_mix = gold_outlook._synthesize_label({"a": "bullish", "b": "bearish"}, {"a": 5.0, "b": 5.0})
    assert even_mix == "mixed (1 bullish / 1 bearish, evenly weighted)"

    no_edge = gold_outlook._synthesize_label({"a": "bullish", "b": "bearish"}, {"a": 0.0, "b": 0.0})
    assert "mixed, no net edge" in no_edge


def test_synthesize_label_a_strong_minority_signal_can_outweigh_a_weak_majority():
    # 3 near-coin-flip bearish signals (weight 1 each) outnumbered but outweighed
    # by 1 strong bullish signal (weight 13) -- the core fix this change makes:
    # a real edge shouldn't lose to a headcount of noise.
    components = {"a": "bearish", "b": "bearish", "c": "bearish", "d": "bullish"}
    weights = {"a": 1.0, "b": 1.0, "c": 1.0, "d": 13.0}
    label = gold_outlook._synthesize_label(components, weights)
    assert label.startswith("bullish lean")


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


def test_live_state_cot_positioning_matches_gold_backtest_state():
    # Enough weekly history to clear cot_index_series's real (unpatchable-by-config,
    # bound-at-def-time) default lookback warmup, ending at the top of its own
    # range -> extreme_long, matching gold_cot.classify_cot_state(100.0) exactly.
    values = [100.0] * (config.COT_LOOKBACK_WEEKS - 1) + [1000.0]
    net = pd.Series(values, index=pd.date_range("2000-01-07", periods=len(values), freq="W-FRI"))
    daily_index = pd.date_range(net.index[-1], periods=3, freq="D")

    expected = gold_backtest.state_cot_positioning(daily_index, net).iloc[-1]
    assert expected == "extreme_long" == gold_cot.classify_cot_state(100.0)

    macro_checks_extreme = _macro_checks(cot_positioning="extreme_long")
    live_states_extreme = gold_outlook._live_signal_states(_technicals(), macro_checks_extreme)
    assert live_states_extreme["cot_positioning"] == "extreme_long" == expected

    # A neutral live reading (direction=None, e.g. cot_index sitting mid-range)
    # is never added to states -- matches how every other "neutral" state is
    # excluded from the vote.
    macro_checks_neutral = _macro_checks(cot_positioning=None)
    live_states_neutral = gold_outlook._live_signal_states(_technicals(), macro_checks_neutral)
    assert "cot_positioning" not in live_states_neutral


def test_cot_positioning_votes_directly_not_as_context():
    states = {"cot_positioning": "extreme_long"}
    backtest_results = {
        ("cot_positioning", "extreme_long", "day", 1): {
            "n": 184, "mean": 0.13, "baseline": {"mean": 0.06}, "win_rate": 56.5,
        },
    }
    read = gold_outlook._horizon_read(states, backtest_results, "day", 1)
    assert read["components"] == {"cot_positioning": "bullish"}
    assert read["context_notes"] == []


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

    assert "N=1, avg move 100.0%" in today["notes"][-1]
    assert "N=1, avg move 200.0%" in week["notes"][-1]
    assert any("N=1, avg move 300.0%" in n for n in month["notes"])


def test_build_month_read_includes_seasonality_in_weighted_vote():
    # Seasonality win_rate=70 (bullish, weight=20) should outweigh a single weak
    # bearish macro signal (win_rate=51, weight=1) in the month lean.
    technicals = _technicals(seasonality={"n": 20, "mean": 2.0, "median": 2.0, "win_rate": 70.0})
    backtest_results = {
        ("vix", "elevated", "month", 1): {"n": 50, "mean": -0.1, "baseline": {"mean": 0.0}, "win_rate": 51.0},
    }
    month = gold_outlook.build_month_read(technicals, _macro_checks(vix="elevated"), backtest_results)
    assert month["direction_guess"].startswith("bullish lean")
    assert any("calendar month" in n and "70.0% of years" in n for n in month["notes"])


def test_build_month_read_skips_seasonality_without_win_rate():
    technicals = _technicals(seasonality={"n": 0, "mean": None, "median": None, "win_rate": None})
    month = gold_outlook.build_month_read(technicals, [], {})
    assert "seasonality" not in month["components"]


# -- Markdown rendering -------------------------------------------------------

def test_render_outlook_markdown_includes_all_three_horizon_sections():
    outlook = {
        "as_of": "2026-08-07",
        "today": {
            "direction_guess": "bullish lean (1/1)", "confidence": "low", "notes": ["note1"],
            "context_notes": ["ctx1"],
            "expected_move_dollars": 10.0, "expected_move_pct": 1.0,
            "resistance": 110.0, "support": 90.0, "volume_note": "above-average volume",
        },
        "week": {"direction_guess": "mixed", "confidence": "medium", "notes": ["note2"], "context_notes": []},
        "month": {"direction_guess": "bearish lean (1/1)", "confidence": "high", "notes": ["note3"], "context_notes": []},
    }
    markdown = gold_outlook.render_outlook_markdown(outlook)
    assert "### Today / Tomorrow" in markdown
    assert "### This Week" in markdown
    assert "### This Month" in markdown
    assert "note1" in markdown and "note2" in markdown and "note3" in markdown
    assert "ctx1" in markdown
    assert "Never a buy/sell recommendation." in markdown


def test_write_outlook_writes_to_configured_path(tmp_path, monkeypatch):
    monkeypatch.setattr("mytrader.gold_outlook.config.MY_TRADER_DIR", tmp_path)
    outlook = {
        "as_of": "2026-08-07",
        "today": {
            "direction_guess": "mixed", "confidence": "low", "notes": [], "context_notes": [],
            "expected_move_dollars": 1.0, "expected_move_pct": 1.0,
            "resistance": 1.0, "support": 1.0, "volume_note": "below-average volume",
        },
        "week": {"direction_guess": "mixed", "confidence": "medium", "notes": [], "context_notes": []},
        "month": {"direction_guess": "mixed", "confidence": "high", "notes": [], "context_notes": []},
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


def test_build_outlook_merges_cot_check_into_the_vote(monkeypatch):
    monkeypatch.setattr(
        "mytrader.gold_outlook.gold_technicals.compute_today_technicals", lambda: _technicals()
    )
    monkeypatch.setattr(
        "mytrader.gold_cot.check_cot_positioning",
        lambda: CheckResult(
            name="cot_positioning", verdict="flag", detail="extreme long",
            data={"direction": "extreme_long"},
        ),
    )
    backtest_results = {
        ("cot_positioning", "extreme_long", "day", 1): {
            "n": 184, "mean": 0.13, "baseline": {"mean": 0.06}, "win_rate": 56.5,
        },
    }
    monkeypatch.setattr(
        "mytrader.gold_outlook.gold_backtest.get_cached_or_refresh", lambda conn: backtest_results
    )
    outlook = gold_outlook.build_outlook(conn=None, macro_checks=[])
    assert outlook is not None
    assert "cot_positioning" in outlook["today"]["components"]
    assert outlook["today"]["components"]["cot_positioning"] == "bullish"


def test_build_outlook_degrades_gracefully_when_cot_check_raises(monkeypatch):
    monkeypatch.setattr(
        "mytrader.gold_outlook.gold_technicals.compute_today_technicals", lambda: _technicals()
    )

    def _boom():
        raise RuntimeError("CFTC unreachable")

    monkeypatch.setattr("mytrader.gold_cot.check_cot_positioning", _boom)
    monkeypatch.setattr("mytrader.gold_outlook.gold_backtest.get_cached_or_refresh", lambda conn: {})
    outlook = gold_outlook.build_outlook(conn=None, macro_checks=[])  # must not raise
    assert outlook is not None
