from __future__ import annotations

from datetime import date

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


def test_run_all_returns_four_check_results(monkeypatch):
    monkeypatch.setattr("mytrader.macro_indicators._yfinance_latest_close", lambda ticker: None)
    monkeypatch.setattr("mytrader.macro_indicators.fred_observation_on", lambda series_id, target: None)
    results = macro_indicators.run_all()
    assert len(results) == 4
    assert {r.name for r in results} == {
        "move_index", "housing_affordability", "consumer_sentiment", "recession_signal",
    }
