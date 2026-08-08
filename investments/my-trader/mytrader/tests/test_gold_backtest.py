from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pandas as pd
import pytest

from mytrader import config, db, gold_backtest


def _dates(n: int, start: str = "2020-01-01") -> pd.DatetimeIndex:
    return pd.date_range(start, periods=n, freq="D")


# -- Episode finders ---------------------------------------------------------

def test_find_real_yield_episodes_flags_negative_and_elevated_with_gap_merge(monkeypatch):
    monkeypatch.setattr(config, "GOLD_BACKTEST_MIN_EPISODE_GAP_DAYS", 10)
    dates = pd.to_datetime([
        "2020-01-01", "2020-01-05",   # negative cluster -> merged into 1 episode
        "2020-03-01",                  # negative, far away -> separate episode
        "2020-05-01", "2020-05-03",   # elevated cluster -> merged into 1 episode
    ])
    values = [-0.5, -0.6, -0.4, 2.5, 2.6]
    series = pd.Series(values, index=dates)

    episodes = gold_backtest.find_real_yield_episodes(series)

    negative = sorted(e.occurred_on for e in episodes if e.direction == "negative")
    elevated = sorted(e.occurred_on for e in episodes if e.direction == "elevated")
    assert negative == [date(2020, 1, 1), date(2020, 3, 1)]
    assert elevated == [date(2020, 5, 1)]
    assert all(e.signal == "real_yields" for e in episodes)


def test_find_dollar_index_episodes_flags_large_move_and_merges_consecutive_days(monkeypatch):
    monkeypatch.setattr(config, "DXY_LOOKBACK_DAYS", 5)
    monkeypatch.setattr(config, "DXY_FLAG_MOVE_PCT", 3.0)
    monkeypatch.setattr(config, "GOLD_BACKTEST_MIN_EPISODE_GAP_DAYS", 15)
    dates = _dates(20)
    values = [100.0] * 10 + [110.0] * 10  # +10% jump, persists -> many consecutive flagged days
    series = pd.Series(values, index=dates)

    episodes = gold_backtest.find_dollar_index_episodes(series)

    rising = [e for e in episodes if e.direction == "rising"]
    falling = [e for e in episodes if e.direction == "falling"]
    assert len(rising) == 1
    assert rising[0].occurred_on == dates[10].date()
    assert falling == []


def test_find_gold_trend_episodes_detects_every_sign_flip_no_merge(monkeypatch):
    monkeypatch.setattr(config, "GOLD_MA_LONG_DAYS", 3)
    dates = _dates(9)
    values = [10.0, 11.0, 12.0, 5.0, 5.0, 6.0, 20.0, 20.0, 21.0]
    close = pd.Series(values, index=dates)

    episodes = gold_backtest.find_gold_trend_episodes(close)

    assert len(episodes) == 2  # no gap-merge -- both flips reported
    assert episodes[0] == gold_backtest.Episode(dates[3].date(), "gold_trend", "crossed_below")
    assert episodes[1] == gold_backtest.Episode(dates[5].date(), "gold_trend", "crossed_above")


def test_find_gold_silver_ratio_episodes_flags_high_and_low(monkeypatch):
    monkeypatch.setattr(config, "GOLD_SILVER_RATIO_FLAG_HIGH", 3.0)
    monkeypatch.setattr(config, "GOLD_SILVER_RATIO_FLAG_LOW", 2.0)
    monkeypatch.setattr(config, "GOLD_BACKTEST_MIN_EPISODE_GAP_DAYS", 10)
    dates = _dates(4)
    gold = pd.Series([10.0, 10.0, 10.0, 10.0], index=dates)
    silver = pd.Series([2.0, 2.0, 5.0, 5.0], index=dates)  # ratio: 5, 5, 2, 2

    episodes = gold_backtest.find_gold_silver_ratio_episodes(gold, silver)

    high = [e for e in episodes if e.direction == "high"]
    low = [e for e in episodes if e.direction == "low"]
    assert len(high) == 1 and high[0].occurred_on == dates[0].date()
    assert len(low) == 1 and low[0].occurred_on == dates[2].date()


def test_find_vix_episodes_flags_elevated_with_gap_merge(monkeypatch):
    monkeypatch.setattr(config, "VIX_FLAG_LEVEL", 30.0)
    monkeypatch.setattr(config, "GOLD_BACKTEST_MIN_EPISODE_GAP_DAYS", 10)
    dates = _dates(5)
    vix = pd.Series([20.0, 20.0, 35.0, 36.0, 20.0], index=dates)

    episodes = gold_backtest.find_vix_episodes(vix)

    assert len(episodes) == 1
    assert episodes[0] == gold_backtest.Episode(dates[2].date(), "vix", "elevated")


# -- Forward-return future-date guards ---------------------------------------

def test_compute_forward_return_calendar_returns_none_for_future_target():
    dates = _dates(10)
    close = pd.Series([100.0 + i for i in range(10)], index=dates)
    # Requesting a 12-month-ahead return from the last available date is far
    # beyond the fetched series' range -- must be excluded, never fabricated
    # from today's price via asof()'s silent last-value fallback.
    result = gold_backtest.compute_forward_return_calendar(close, dates[-1].date(), 12)
    assert result is None


def test_compute_forward_return_calendar_returns_value_within_range():
    dates = pd.to_datetime(["2020-01-01", "2020-02-01"])
    close = pd.Series([100.0, 110.0], index=dates)
    result = gold_backtest.compute_forward_return_calendar(close, date(2020, 1, 1), 1)
    assert result == pytest.approx(10.0)


def test_compute_forward_return_trading_days_returns_none_past_series_end():
    close = pd.Series([100.0, 101.0, 102.0], index=_dates(3))
    assert gold_backtest.compute_forward_return_trading_days(close, 2, 1) is None
    assert gold_backtest.compute_forward_return_trading_days(close, 1, 5) is None


def test_compute_forward_return_trading_days_returns_known_value():
    close = pd.Series([100.0, 110.0, 121.0], index=_dates(3))
    assert gold_backtest.compute_forward_return_trading_days(close, 0, 1) == pytest.approx(10.0)
    assert gold_backtest.compute_forward_return_trading_days(close, 0, 2) == pytest.approx(21.0)


# -- State classifiers --------------------------------------------------------

def test_state_ma_trend_labels_above_below_equal():
    dates = _dates(6)
    close = pd.Series([10.0, 10.0, 10.0, 20.0, 10.0, 5.0], index=dates)
    state = gold_backtest.state_ma_trend(close, 3)
    assert state.iloc[2] == "equal"   # close=10 vs ma3=mean(10,10,10)=10
    assert state.iloc[3] == "above"   # close=20 vs ma3=mean(10,10,20)=13.33
    assert state.iloc[4] == "below"   # close=10 vs ma3=mean(10,20,10)=13.33


def test_state_macd_histogram_sign(monkeypatch):
    monkeypatch.setattr(config, "GOLD_TA_MACD_FAST_DAYS", 2)
    monkeypatch.setattr(config, "GOLD_TA_MACD_SLOW_DAYS", 3)
    monkeypatch.setattr(config, "GOLD_TA_MACD_SIGNAL_DAYS", 2)
    # Clean linear trend (not accelerating/decelerating) -- fast EMA leads slow
    # EMA consistently in the trend direction, so histogram sign is stable by
    # the last point (an exponential-shaped series has an early sign transient
    # that isn't a simple mirror image between up/down).
    rising = pd.Series([10.0 * (i + 1) for i in range(8)], index=_dates(8))
    falling = pd.Series([10.0 * (8 - i) for i in range(8)], index=_dates(8))
    assert gold_backtest.state_macd_histogram(rising).iloc[-1] == "positive"
    assert gold_backtest.state_macd_histogram(falling).iloc[-1] == "negative"


def test_state_macd_crossover(monkeypatch):
    monkeypatch.setattr(config, "GOLD_TA_MACD_FAST_DAYS", 2)
    monkeypatch.setattr(config, "GOLD_TA_MACD_SLOW_DAYS", 3)
    monkeypatch.setattr(config, "GOLD_TA_MACD_SIGNAL_DAYS", 2)
    rising = pd.Series([10.0 * (i + 1) for i in range(8)], index=_dates(8))
    falling = pd.Series([10.0 * (8 - i) for i in range(8)], index=_dates(8))
    assert gold_backtest.state_macd_crossover(rising).iloc[-1] == "above"
    assert gold_backtest.state_macd_crossover(falling).iloc[-1] == "below"


def test_state_rsi_zone_three_way_split(monkeypatch):
    monkeypatch.setattr(config, "GOLD_TA_RSI_BULLISH_ABOVE", 55.0)
    monkeypatch.setattr(config, "GOLD_TA_RSI_BEARISH_BELOW", 45.0)
    rising = pd.Series([float(i) for i in range(1, 20)], index=_dates(19))
    falling = pd.Series([float(i) for i in range(19, 0, -1)], index=_dates(19))
    # Symmetric small alternation converges RSI toward 50 (neutral band).
    neutral = pd.Series(
        [100.0 + (2 if i % 2 == 0 else -2) for i in range(40)], index=_dates(40)
    )
    assert gold_backtest.state_rsi_zone(rising).iloc[-1] == "elevated"
    assert gold_backtest.state_rsi_zone(falling).iloc[-1] == "depressed"
    assert gold_backtest.state_rsi_zone(neutral).iloc[-1] == "neutral"


def test_state_stochastic_crossover_above(monkeypatch):
    monkeypatch.setattr(config, "GOLD_TA_STOCH_PERIOD_DAYS", 3)
    monkeypatch.setattr(config, "GOLD_TA_STOCH_SMOOTHING_DAYS", 2)
    # k rises from 50 to 100 across the smoothing window -> d (2-period avg of k)
    # lags behind at 75 -> k > d -> "above".
    df = pd.DataFrame(
        {
            "High": [10.0, 10.0, 15.0, 15.0], "Low": [8.0, 8.0, 8.0, 8.0],
            "Close": [9.0, 9.0, 11.5, 15.0],
        },
        index=_dates(4),
    )
    state = gold_backtest.state_stochastic_crossover(df)
    assert state.iloc[-1] == "above"


def test_state_stochastic_crossover_below(monkeypatch):
    monkeypatch.setattr(config, "GOLD_TA_STOCH_PERIOD_DAYS", 3)
    monkeypatch.setattr(config, "GOLD_TA_STOCH_SMOOTHING_DAYS", 2)
    df = pd.DataFrame(
        {
            "High": [15.0, 15.0, 12.0, 10.0], "Low": [10.0, 10.0, 9.0, 8.0],
            "Close": [14.0, 14.0, 10.5, 8.0],
        },
        index=_dates(4),
    )
    state = gold_backtest.state_stochastic_crossover(df)
    assert state.iloc[-1] == "below"


def test_state_cot_positioning_forward_fills_weekly_reading_onto_daily_index():
    # Enough weekly points to clear the real (bound-at-def-time) default lookback,
    # ending at the bottom of its own range -> extreme_short.
    values = [1000.0] * (config.COT_LOOKBACK_WEEKS - 1) + [0.0]
    net = pd.Series(values, index=pd.date_range("2000-01-07", periods=len(values), freq="W-FRI"))
    last_report_date = net.index[-1]
    # Daily index spanning a few days before and after the last weekly release --
    # every day on/after the release must forward-fill to the same state, days
    # strictly before it (this synthetic net series' very first date) get None.
    daily_index = pd.date_range(last_report_date - pd.Timedelta(days=2), periods=5, freq="D")

    state = gold_backtest.state_cot_positioning(daily_index, net)

    assert list(state.loc[daily_index >= last_report_date]) == ["extreme_short"] * 3
    assert state.iloc[0] is None or pd.isna(state.iloc[0])


def test_state_cot_positioning_returns_none_before_any_release():
    net = pd.Series([100.0] * config.COT_LOOKBACK_WEEKS, index=pd.date_range("2020-01-03", periods=config.COT_LOOKBACK_WEEKS, freq="W-FRI"))
    daily_index = pd.date_range("2015-01-01", periods=3, freq="D")  # long before any COT data exists
    state = gold_backtest.state_cot_positioning(daily_index, net)
    assert state.isna().all() or all(v is None for v in state)


# -- State-conditioned sample-size correctness --------------------------------

def test_compute_state_conditioned_stats_uses_every_day_state_holds():
    n = 12
    dates = _dates(n + 1)
    close = pd.Series([100.0 + i for i in range(n + 1)], index=dates)
    # State "above" holds for the first n days; last day has no state (excluded).
    state = pd.Series(["above"] * n + ["below"], index=dates)

    stats = gold_backtest.compute_state_conditioned_stats(
        state, close, 1, dates[0].date(), dates[-1].date()
    )

    # Every day the state held (n days) contributes one forward-return sample,
    # not just the day the state started -- proves this is genuinely different
    # from episode-based (start-only) counting.
    assert stats["above"]["n"] == n


# -- Daily-refresh cache ------------------------------------------------------

def _seed_result() -> dict:
    return {
        ("vix", "elevated", "day", 1): {
            "n": 5, "mean": 1.0, "median": 1.0, "win_rate": 60.0, "best": 2.0, "worst": -1.0,
            "baseline": {"n": 100, "mean": 0.1, "median": 0.1, "win_rate": 50.0},
        },
    }


def test_get_cached_or_refresh_uses_fresh_cache_without_refetching(db_conn, monkeypatch):
    db.upsert_gold_backtest_results(db_conn, _seed_result())

    def _boom():
        raise AssertionError("run_backtest should not be called when cache is fresh")

    monkeypatch.setattr(gold_backtest, "run_backtest", _boom)
    result = gold_backtest.get_cached_or_refresh(db_conn, max_age_days=1)
    assert result[("vix", "elevated", "day", 1)]["n"] == 5


def test_get_cached_or_refresh_refetches_when_stale(db_conn, monkeypatch):
    db.upsert_gold_backtest_results(db_conn, _seed_result())
    stale = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    with db_conn:
        db_conn.execute("UPDATE gold_backtest_results SET computed_at = ?", (stale,))

    fresh_result = {
        ("real_yields", "negative", "day", 1): {
            "n": 3, "mean": 2.0, "median": 2.0, "win_rate": 66.7, "best": 3.0, "worst": 1.0,
            "baseline": {"n": 50, "mean": 0.2, "median": 0.2, "win_rate": 55.0},
        },
    }
    monkeypatch.setattr(gold_backtest, "run_backtest", lambda: fresh_result)

    result = gold_backtest.get_cached_or_refresh(db_conn, max_age_days=1)

    assert result == fresh_result
    rows = db.get_gold_backtest_results(db_conn)
    # upsert_gold_backtest_results is a merge, not a full resync -- the stale
    # vix row persists alongside the freshly-computed real_yields row.
    assert {r["signal"] for r in rows} == {"vix", "real_yields"}
    fresh_row = next(r for r in rows if r["signal"] == "real_yields")
    assert (datetime.now(timezone.utc) - datetime.fromisoformat(fresh_row["computed_at"])) < timedelta(minutes=1)
