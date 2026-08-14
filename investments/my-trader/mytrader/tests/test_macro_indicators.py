from __future__ import annotations

from datetime import date

import pandas as pd

from mytrader import config, macro_indicators

_D = date(2026, 1, 1)  # arbitrary fixed observation date for tests that don't assert on it


def test_check_move_index_unknown_when_yfinance_returns_none(monkeypatch):
    monkeypatch.setattr("mytrader.macro_indicators._yfinance_latest_close", lambda ticker: None)
    result = macro_indicators.check_move_index()
    assert result.verdict == "unknown"


def test_check_move_index_flags_above_threshold(monkeypatch):
    monkeypatch.setattr(
        "mytrader.macro_indicators._yfinance_latest_close",
        lambda ticker: config.MOVE_INDEX_FLAG_LEVEL + 10,
    )
    result = macro_indicators.check_move_index()
    assert result.verdict == "flag"


def test_check_move_index_ok_below_threshold(monkeypatch):
    monkeypatch.setattr(
        "mytrader.macro_indicators._yfinance_latest_close",
        lambda ticker: config.MOVE_INDEX_FLAG_LEVEL - 10,
    )
    result = macro_indicators.check_move_index()
    assert result.verdict == "ok"


def test_check_housing_affordability_unknown_when_fred_unavailable(monkeypatch):
    monkeypatch.setattr("mytrader.macro_indicators.fred_observation_on", lambda series_id, target: None)
    result = macro_indicators.check_housing_affordability()
    assert result.verdict == "unknown"


def test_check_housing_affordability_flags_above_ratio(monkeypatch):
    def _fake(series_id, target):
        if series_id == config.FRED_MEDIAN_HOME_PRICE_SERIES:
            return 500000.0, _D
        if series_id == config.FRED_MEDIAN_HOUSEHOLD_INCOME_SERIES:
            return 80000.0, _D
        return None

    monkeypatch.setattr("mytrader.macro_indicators.fred_observation_on", _fake)
    result = macro_indicators.check_housing_affordability()
    assert result.verdict == "flag"
    assert "as of 2026-01-01" in result.detail


def test_check_housing_affordability_ok_below_ratio(monkeypatch):
    def _fake(series_id, target):
        if series_id == config.FRED_MEDIAN_HOME_PRICE_SERIES:
            return 200000.0, _D
        if series_id == config.FRED_MEDIAN_HOUSEHOLD_INCOME_SERIES:
            return 80000.0, _D
        return None

    monkeypatch.setattr("mytrader.macro_indicators.fred_observation_on", _fake)
    result = macro_indicators.check_housing_affordability()
    assert result.verdict == "ok"


def test_check_consumer_sentiment_unknown_when_fred_unavailable(monkeypatch):
    monkeypatch.setattr("mytrader.macro_indicators.fred_observation_on", lambda series_id, target: None)
    result = macro_indicators.check_consumer_sentiment()
    assert result.verdict == "unknown"


def test_check_consumer_sentiment_flags_at_or_below_threshold(monkeypatch):
    monkeypatch.setattr(
        "mytrader.macro_indicators.fred_observation_on",
        lambda series_id, target: (config.CONSUMER_SENTIMENT_FLAG_LEVEL, _D),
    )
    result = macro_indicators.check_consumer_sentiment()
    assert result.verdict == "flag"
    assert "as of 2026-01-01" in result.detail


def test_check_consumer_sentiment_ok_above_threshold(monkeypatch):
    monkeypatch.setattr(
        "mytrader.macro_indicators.fred_observation_on",
        lambda series_id, target: (config.CONSUMER_SENTIMENT_FLAG_LEVEL + 20, _D),
    )
    result = macro_indicators.check_consumer_sentiment()
    assert result.verdict == "ok"


def test_check_recession_signal_unknown_when_curve_or_prob_missing(monkeypatch):
    def _fake(series_id, target):
        if series_id == config.FRED_YIELD_CURVE_SERIES:
            return None
        return 1.0, _D

    monkeypatch.setattr("mytrader.macro_indicators.fred_observation_on", _fake)
    result = macro_indicators.check_recession_signal()
    assert result.verdict == "unknown"


def test_check_recession_signal_flags_at_or_above_threshold(monkeypatch):
    def _fake_obs(series_id, target):
        if series_id == config.FRED_YIELD_CURVE_SERIES:
            return 0.5, _D
        if series_id == config.FRED_RECESSION_PROB_SERIES:
            return config.RECESSION_PROB_FLAG_PCT, _D
        return None

    monkeypatch.setattr("mytrader.macro_indicators.fred_observation_on", _fake_obs)
    monkeypatch.setattr("mytrader.macro_indicators.fred_value_on", lambda series_id, target: None)
    result = macro_indicators.check_recession_signal()
    assert result.verdict == "flag"
    assert "as of 2026-01-01" in result.detail


def test_check_recession_signal_includes_3m10y_when_available(monkeypatch):
    def _fake_obs(series_id, target):
        if series_id == config.FRED_YIELD_CURVE_SERIES:
            return 0.5, _D
        if series_id == config.FRED_RECESSION_PROB_SERIES:
            return 5.0, _D
        if series_id == config.FRED_YIELD_CURVE_3M10Y_SERIES:
            return 0.84, _D
        return None

    monkeypatch.setattr("mytrader.macro_indicators.fred_observation_on", _fake_obs)
    monkeypatch.setattr("mytrader.macro_indicators.fred_value_on", lambda series_id, target: None)
    result = macro_indicators.check_recession_signal()
    assert "10Y-3M spread +0.84pp" in result.detail
    assert "inverted" not in result.detail
    assert result.verdict == "ok"


def test_check_recession_signal_flags_when_3m10y_inverted_even_if_prob_below_threshold(monkeypatch):
    def _fake_obs(series_id, target):
        if series_id == config.FRED_YIELD_CURVE_SERIES:
            return 0.5, _D
        if series_id == config.FRED_RECESSION_PROB_SERIES:
            return config.RECESSION_PROB_FLAG_PCT - 10.0, _D
        if series_id == config.FRED_YIELD_CURVE_3M10Y_SERIES:
            return -0.2, _D
        return None

    monkeypatch.setattr("mytrader.macro_indicators.fred_observation_on", _fake_obs)
    monkeypatch.setattr("mytrader.macro_indicators.fred_value_on", lambda series_id, target: None)
    result = macro_indicators.check_recession_signal()
    assert "10Y-3M spread -0.20pp (as of 2026-01-01) (inverted)" in result.detail
    assert result.verdict == "flag"


def test_check_recession_signal_classifies_bull_steepener(monkeypatch):
    def _fake_obs(series_id, target):
        if series_id == config.FRED_YIELD_CURVE_SERIES:
            return 0.5, _D
        if series_id == config.FRED_RECESSION_PROB_SERIES:
            return 5.0, _D
        return None

    def _fake_value(series_id, target):
        today = macro_indicators.date.today()
        is_today = target == today
        if series_id == config.FRED_2Y_TREASURY_SERIES:
            return 3.5 if is_today else 4.0  # short falling
        if series_id == config.FRED_10Y_TREASURY_SERIES:
            return 4.0 if is_today else 4.0  # long flat (not rising)
        return None

    monkeypatch.setattr("mytrader.macro_indicators.fred_observation_on", _fake_obs)
    monkeypatch.setattr("mytrader.macro_indicators.fred_value_on", _fake_value)
    result = macro_indicators.check_recession_signal()
    assert "bull steepener" in result.detail


def test_check_recession_signal_classifies_bear_steepener(monkeypatch):
    def _fake_obs(series_id, target):
        if series_id == config.FRED_YIELD_CURVE_SERIES:
            return 0.5, _D
        if series_id == config.FRED_RECESSION_PROB_SERIES:
            return 5.0, _D
        return None

    def _fake_value(series_id, target):
        today = macro_indicators.date.today()
        is_today = target == today
        if series_id == config.FRED_2Y_TREASURY_SERIES:
            return 4.0 if is_today else 4.0  # short flat (not falling)
        if series_id == config.FRED_10Y_TREASURY_SERIES:
            return 4.5 if is_today else 4.0  # long rising
        return None

    monkeypatch.setattr("mytrader.macro_indicators.fred_observation_on", _fake_obs)
    monkeypatch.setattr("mytrader.macro_indicators.fred_value_on", _fake_value)
    result = macro_indicators.check_recession_signal()
    assert "bear steepener" in result.detail


def test_check_recession_signal_no_steepener_classification_when_lookback_data_missing(monkeypatch):
    def _fake_obs(series_id, target):
        if series_id == config.FRED_YIELD_CURVE_SERIES:
            return 0.5, _D
        if series_id == config.FRED_RECESSION_PROB_SERIES:
            return 5.0, _D
        return None

    def _fake_value(series_id, target):
        today = macro_indicators.date.today()
        is_today = target == today
        if series_id in (config.FRED_2Y_TREASURY_SERIES, config.FRED_10Y_TREASURY_SERIES):
            return 4.0 if is_today else None  # lookback missing
        return None

    monkeypatch.setattr("mytrader.macro_indicators.fred_observation_on", _fake_obs)
    monkeypatch.setattr("mytrader.macro_indicators.fred_value_on", _fake_value)
    result = macro_indicators.check_recession_signal()
    assert "spread" in result.detail
    assert "probability" in result.detail
    assert "steepener" not in result.detail


def test_check_inflation_expectations_unknown_when_fred_unavailable(monkeypatch):
    monkeypatch.setattr("mytrader.macro_indicators.fred_observation_on", lambda series_id, target: None)
    result = macro_indicators.check_inflation_expectations()
    assert result.verdict == "unknown"


def test_check_inflation_expectations_flags_at_or_above_threshold(monkeypatch):
    def _fake(series_id, target):
        if series_id == config.FRED_BREAKEVEN_10Y_SERIES:
            return 2.9, _D
        if series_id == config.FRED_BREAKEVEN_5Y5Y_FORWARD_SERIES:
            return config.INFLATION_EXPECTATION_FLAG_PCT, _D
        return None

    monkeypatch.setattr("mytrader.macro_indicators.fred_observation_on", _fake)
    result = macro_indicators.check_inflation_expectations()
    assert result.verdict == "flag"
    assert "as of 2026-01-01" in result.detail


def test_check_inflation_expectations_ok_below_threshold(monkeypatch):
    def _fake(series_id, target):
        if series_id == config.FRED_BREAKEVEN_10Y_SERIES:
            return 2.2, _D
        if series_id == config.FRED_BREAKEVEN_5Y5Y_FORWARD_SERIES:
            return config.INFLATION_EXPECTATION_FLAG_PCT - 0.5, _D
        return None

    monkeypatch.setattr("mytrader.macro_indicators.fred_observation_on", _fake)
    result = macro_indicators.check_inflation_expectations()
    assert result.verdict == "ok"


def test_check_credit_spreads_unknown_when_fred_unavailable(monkeypatch):
    monkeypatch.setattr("mytrader.macro_indicators.fred_observation_on", lambda series_id, target: None)
    result = macro_indicators.check_credit_spreads()
    assert result.verdict == "unknown"


def test_check_credit_spreads_flags_at_or_above_threshold(monkeypatch):
    monkeypatch.setattr(
        "mytrader.macro_indicators.fred_observation_on",
        lambda series_id, target: (config.CREDIT_SPREAD_FLAG_PCT, _D),
    )
    result = macro_indicators.check_credit_spreads()
    assert result.verdict == "flag"
    assert "as of 2026-01-01" in result.detail


def test_check_credit_spreads_ok_below_threshold(monkeypatch):
    monkeypatch.setattr(
        "mytrader.macro_indicators.fred_observation_on",
        lambda series_id, target: (config.CREDIT_SPREAD_FLAG_PCT - 2.0, _D),
    )
    result = macro_indicators.check_credit_spreads()
    assert result.verdict == "ok"


def test_check_australia_cpi_unknown_when_fetch_fails(monkeypatch):
    monkeypatch.setattr("mytrader.macro_indicators.abs_cpi.fetch_australia_cpi_yoy", lambda: None)
    result = macro_indicators.check_australia_cpi()
    assert result.verdict == "unknown"


def test_check_australia_cpi_flags_outside_target_band(monkeypatch):
    monkeypatch.setattr(
        "mytrader.macro_indicators.abs_cpi.fetch_australia_cpi_yoy",
        lambda: (3.8, date(2026, 6, 1)),
    )
    result = macro_indicators.check_australia_cpi()
    assert result.verdict == "flag"
    assert "reference month 2026-06-01" in result.detail


def test_check_australia_cpi_ok_within_target_band(monkeypatch):
    monkeypatch.setattr(
        "mytrader.macro_indicators.abs_cpi.fetch_australia_cpi_yoy",
        lambda: (2.5, date(2026, 6, 1)),
    )
    result = macro_indicators.check_australia_cpi()
    assert result.verdict == "ok"


def test_check_us_cpi_unknown_when_fred_unavailable(monkeypatch):
    monkeypatch.setattr(
        "mytrader.macro_indicators.fred_observation_on", lambda series_id, target, units=None: None
    )
    result = macro_indicators.check_us_cpi()
    assert result.verdict == "unknown"


def test_check_us_cpi_flags_above_band(monkeypatch):
    monkeypatch.setattr(
        "mytrader.macro_indicators.fred_observation_on",
        lambda series_id, target, units=None: (config.US_CPI_TARGET_BAND_HIGH_PCT + 0.5, _D),
    )
    result = macro_indicators.check_us_cpi()
    assert result.verdict == "flag"
    assert "as of 2026-01-01" in result.detail


def test_check_us_cpi_ok_within_band(monkeypatch):
    monkeypatch.setattr(
        "mytrader.macro_indicators.fred_observation_on",
        lambda series_id, target, units=None: (2.0, _D),
    )
    result = macro_indicators.check_us_cpi()
    assert result.verdict == "ok"


def test_check_uk_cpi_unknown_when_ons_unavailable(monkeypatch):
    monkeypatch.setattr("mytrader.macro_indicators.ons_cpi.fetch_uk_cpi_yoy", lambda: None)
    result = macro_indicators.check_uk_cpi()
    assert result.verdict == "unknown"


def test_check_uk_cpi_flags_outside_band(monkeypatch):
    monkeypatch.setattr(
        "mytrader.macro_indicators.ons_cpi.fetch_uk_cpi_yoy",
        lambda: (config.UK_CPI_TARGET_BAND_HIGH_PCT + 0.5, date(2026, 6, 1)),
    )
    result = macro_indicators.check_uk_cpi()
    assert result.verdict == "flag"
    assert "reference month 2026-06-01" in result.detail


def test_check_uk_cpi_ok_within_band(monkeypatch):
    monkeypatch.setattr(
        "mytrader.macro_indicators.ons_cpi.fetch_uk_cpi_yoy",
        lambda: (2.6, date(2026, 6, 1)),
    )
    result = macro_indicators.check_uk_cpi()
    assert result.verdict == "ok"


def test_check_real_yields_unknown_when_fred_unavailable(monkeypatch):
    monkeypatch.setattr("mytrader.macro_indicators.fred_observation_on", lambda series_id, target: None)
    result = macro_indicators.check_real_yields()
    assert result.verdict == "unknown"


def test_check_real_yields_flags_when_negative(monkeypatch):
    monkeypatch.setattr("mytrader.macro_indicators.fred_observation_on", lambda series_id, target: (-0.5, _D))
    result = macro_indicators.check_real_yields()
    assert result.verdict == "flag"
    assert "negative" in result.detail
    assert result.data["direction"] == "negative"


def test_check_real_yields_flags_when_above_high_threshold(monkeypatch):
    monkeypatch.setattr(
        "mytrader.macro_indicators.fred_observation_on",
        lambda series_id, target: (config.REAL_YIELD_FLAG_HIGH_PCT + 0.5, _D),
    )
    result = macro_indicators.check_real_yields()
    assert result.verdict == "flag"
    assert "elevated" in result.detail
    assert result.data["direction"] == "elevated"


def test_check_real_yields_ok_in_between(monkeypatch):
    monkeypatch.setattr("mytrader.macro_indicators.fred_observation_on", lambda series_id, target: (1.0, _D))
    result = macro_indicators.check_real_yields()
    assert result.verdict == "ok"
    assert result.data["direction"] is None


def test_check_dollar_index_unknown_when_value_missing(monkeypatch):
    monkeypatch.setattr("mytrader.macro_indicators.fred_value_on", lambda series_id, target: None)
    result = macro_indicators.check_dollar_index()
    assert result.verdict == "unknown"


def test_check_dollar_index_flags_on_large_move(monkeypatch):
    def _fake(series_id, target):
        today = macro_indicators.date.today()
        return 110.0 if target == today else 100.0

    monkeypatch.setattr("mytrader.macro_indicators.fred_value_on", _fake)
    result = macro_indicators.check_dollar_index()
    assert result.verdict == "flag"
    assert result.data["direction"] == "rising"


def test_check_dollar_index_flags_on_large_negative_move(monkeypatch):
    def _fake(series_id, target):
        today = macro_indicators.date.today()
        return 90.0 if target == today else 100.0

    monkeypatch.setattr("mytrader.macro_indicators.fred_value_on", _fake)
    result = macro_indicators.check_dollar_index()
    assert result.verdict == "flag"
    assert result.data["direction"] == "falling"


def test_check_dollar_index_ok_on_small_move(monkeypatch):
    def _fake(series_id, target):
        today = macro_indicators.date.today()
        return 101.0 if target == today else 100.0

    monkeypatch.setattr("mytrader.macro_indicators.fred_value_on", _fake)
    result = macro_indicators.check_dollar_index()
    assert result.verdict == "ok"
    assert result.data["direction"] is None


def test_check_gold_trend_unknown_when_history_fetch_fails(monkeypatch):
    monkeypatch.setattr("mytrader.macro_indicators._yfinance_history_close", lambda ticker, lookback_days: None)
    result = macro_indicators.check_gold_trend()
    assert result.verdict == "unknown"


def test_check_gold_trend_detects_cross_and_stays_info_verdict(monkeypatch):
    # Small monkeypatched MA windows keep the synthetic series short and the
    # arithmetic hand-verifiable, while still exercising the real rolling-mean +
    # sign-flip cross-detection logic in check_gold_trend() itself.
    monkeypatch.setattr(config, "GOLD_MA_SHORT_DAYS", 2)
    monkeypatch.setattr(config, "GOLD_MA_LONG_DAYS", 5)
    index = pd.date_range("2026-01-01", periods=12, freq="D")
    values = [10, 11, 12, 13, 14, 14, 14, 5, 5, 5, 5, 4.9]
    close = pd.Series(values, index=index)
    monkeypatch.setattr("mytrader.macro_indicators._yfinance_history_close", lambda ticker, lookback_days: close)
    monkeypatch.setattr("mytrader.macro_indicators._yfinance_latest_close", lambda ticker: 61.2)
    monkeypatch.setattr("mytrader.macro_indicators.market_data.fetch_fx_change_pct", lambda base: -0.8)

    result = macro_indicators.check_gold_trend()
    assert result.verdict == "info"
    assert result.data["cross_date"] == "2026-01-08"
    assert result.data["cross_direction"] == "crossed below"
    assert result.data["direction"] == "crossed_below"
    assert "crossed below 200DMA on 2026-01-08" in result.detail
    assert "PMGOLD $61.20 AUD" in result.detail
    assert "AUD/USD 3mo move -0.8%" in result.detail


def test_check_gold_trend_no_cross_in_window(monkeypatch):
    monkeypatch.setattr(config, "GOLD_MA_SHORT_DAYS", 2)
    monkeypatch.setattr(config, "GOLD_MA_LONG_DAYS", 5)
    index = pd.date_range("2026-01-01", periods=8, freq="D")
    values = [10, 11, 12, 13, 14, 15, 16, 17]  # strictly rising -- always above its own rolling mean
    close = pd.Series(values, index=index)
    monkeypatch.setattr("mytrader.macro_indicators._yfinance_history_close", lambda ticker, lookback_days: close)
    monkeypatch.setattr("mytrader.macro_indicators._yfinance_latest_close", lambda ticker: None)
    monkeypatch.setattr("mytrader.macro_indicators.market_data.fetch_fx_change_pct", lambda base: None)

    result = macro_indicators.check_gold_trend()
    assert result.verdict == "info"
    assert result.data["cross_date"] is None
    assert result.data["direction"] is None
    assert "no cross in the past" in result.detail
    assert "PMGOLD price unavailable" in result.detail
    assert "AUD/USD 3mo move unavailable" in result.detail


def test_check_gold_silver_ratio_unknown_when_price_missing(monkeypatch):
    monkeypatch.setattr("mytrader.macro_indicators._yfinance_latest_close", lambda ticker: None)
    result = macro_indicators.check_gold_silver_ratio()
    assert result.verdict == "unknown"


def test_check_gold_silver_ratio_flags_above_high(monkeypatch):
    def _fake(ticker):
        return 4400.0 if ticker == config.GOLD_FUTURES_TICKER else 50.0  # ratio 88

    monkeypatch.setattr("mytrader.macro_indicators._yfinance_latest_close", _fake)
    result = macro_indicators.check_gold_silver_ratio()
    assert result.verdict == "flag"
    assert result.data["direction"] == "high"


def test_check_gold_silver_ratio_flags_below_low(monkeypatch):
    def _fake(ticker):
        return 2000.0 if ticker == config.GOLD_FUTURES_TICKER else 50.0  # ratio 40

    monkeypatch.setattr("mytrader.macro_indicators._yfinance_latest_close", _fake)
    result = macro_indicators.check_gold_silver_ratio()
    assert result.verdict == "flag"
    assert result.data["direction"] == "low"


def test_check_gold_silver_ratio_ok_in_between(monkeypatch):
    def _fake(ticker):
        return 4400.0 if ticker == config.GOLD_FUTURES_TICKER else 65.0  # ratio ~67.7

    monkeypatch.setattr("mytrader.macro_indicators._yfinance_latest_close", _fake)
    result = macro_indicators.check_gold_silver_ratio()
    assert result.verdict == "ok"
    assert result.data["direction"] is None


def test_check_vix_unknown_when_yfinance_returns_none(monkeypatch):
    monkeypatch.setattr("mytrader.macro_indicators._yfinance_latest_close", lambda ticker: None)
    result = macro_indicators.check_vix()
    assert result.verdict == "unknown"


def test_check_vix_flags_above_threshold(monkeypatch):
    monkeypatch.setattr(
        "mytrader.macro_indicators._yfinance_latest_close", lambda ticker: config.VIX_FLAG_LEVEL + 5
    )
    result = macro_indicators.check_vix()
    assert result.verdict == "flag"
    assert result.data["direction"] == "elevated"


def test_check_vix_ok_below_threshold(monkeypatch):
    monkeypatch.setattr(
        "mytrader.macro_indicators._yfinance_latest_close", lambda ticker: config.VIX_FLAG_LEVEL - 5
    )
    result = macro_indicators.check_vix()
    assert result.verdict == "ok"
    assert result.data["direction"] is None


def test_run_all_returns_fourteen_check_results(monkeypatch):
    monkeypatch.setattr("mytrader.macro_indicators._yfinance_latest_close", lambda ticker: None)
    monkeypatch.setattr(
        "mytrader.macro_indicators.fred_observation_on", lambda series_id, target, units=None: None
    )
    monkeypatch.setattr("mytrader.macro_indicators.fred_value_on", lambda series_id, target: None)
    monkeypatch.setattr("mytrader.macro_indicators.abs_cpi.fetch_australia_cpi_yoy", lambda: None)
    monkeypatch.setattr("mytrader.macro_indicators.ons_cpi.fetch_uk_cpi_yoy", lambda: None)
    monkeypatch.setattr("mytrader.macro_indicators._yfinance_history_close", lambda ticker, lookback_days: None)
    monkeypatch.setattr("mytrader.macro_indicators.market_data.fetch_fx_change_pct", lambda base: None)
    results = macro_indicators.run_all()
    assert len(results) == 14
    assert {r.name for r in results} == {
        "move_index", "housing_affordability", "consumer_sentiment", "recession_signal",
        "inflation_expectations", "credit_spreads", "australia_cpi", "us_cpi", "uk_cpi",
        "real_yields", "dollar_index", "gold_trend", "gold_silver_ratio", "vix",
    }
