from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from mytrader import chart_setup_score as css


def _flat_series(days: int, price: float) -> pd.Series:
    idx = pd.date_range(end=date.today(), periods=days, freq="D")
    return pd.Series([price] * days, index=idx)


def _rising_setup_series(days: int = 300) -> pd.Series:
    """A steadily-rising close series (so 150/200DMA are both below current
    price and both sloping up -- 'confirmed Stage 2') with the last 90 days
    dipping to a low right before recovering to the current high -- so a
    trade dated near the low reads as 'bought into weakness'."""
    idx = pd.date_range(end=date.today(), periods=days, freq="D")
    prices = [50.0 + i * 0.3 for i in range(days - 90)]
    dip_and_recover = [prices[-1] - 5 + abs(i - 45) * 0.15 for i in range(90)]
    return pd.Series(prices + dip_and_recover, index=idx)


def test_trend_context_reports_position_vs_all_three_mas():
    series = _flat_series(260, 100.0)
    series.iloc[-1] = 110.0
    context = css.trend_context(series)
    assert "above 50DMA" in context
    assert "above 150DMA" in context
    assert "above 200DMA" in context


def test_trend_context_empty_on_insufficient_history():
    assert css.trend_context(_flat_series(30, 100.0)) == ""


def test_trend_context_empty_on_none():
    assert css.trend_context(None) == ""


def test_trend_context_reports_below_when_price_under_the_ma():
    series = _flat_series(260, 100.0)
    series.iloc[-1] = 90.0
    context = css.trend_context(series)
    assert "below 200DMA" in context


def test_chart_setup_score_none_on_insufficient_history():
    assert css.chart_setup_score(_flat_series(100, 100.0), date.today().isoformat()) is None


def test_chart_setup_score_none_on_none_close():
    assert css.chart_setup_score(None, date.today().isoformat()) is None


def test_chart_setup_score_none_on_unparsable_trade_date():
    assert css.chart_setup_score(_rising_setup_series(), "not-a-date") is None


def test_chart_setup_score_scores_a_fresh_confirmed_uptrend_bought_into_weakness():
    series = _rising_setup_series()
    trade_date = (date.today() - timedelta(days=45)).isoformat()  # the dip's low point
    result = css.chart_setup_score(series, trade_date)
    assert result is not None
    assert 0 <= result["score"] <= 100
    assert "trend" in result["breakdown"]
    assert "entry" in result["breakdown"]
    assert "momentum" in result["breakdown"]
    assert "extension" in result["breakdown"]
    assert result["score"] >= 50  # rising trend + bought at the dip's low


def test_chart_setup_score_penalizes_below_trend_and_chased_entry():
    idx = pd.date_range(end=date.today(), periods=300, freq="D")
    prices = [150.0 - i * 0.3 for i in range(300)]  # steadily falling
    series = pd.Series(prices, index=idx)
    trade_date = (date.today() - timedelta(days=5)).isoformat()  # bought near a recent high
    result = css.chart_setup_score(series, trade_date)
    assert result is not None
    assert result["score"] < 40


def test_build_chart_note_combines_trend_and_score(monkeypatch):
    series = _rising_setup_series()
    trade_date = (date.today() - timedelta(days=45)).isoformat()
    monkeypatch.setattr(css, "fetch_close", lambda ticker, lookback_days=None: series)
    note = css.build_chart_note("ACME", trade_date)
    assert "DMA" in note
    assert "chart setup score" in note


def test_build_chart_note_empty_on_fetch_miss(monkeypatch):
    monkeypatch.setattr(css, "fetch_close", lambda ticker, lookback_days=None: None)
    assert css.build_chart_note("ACME", date.today().isoformat()) == ""
