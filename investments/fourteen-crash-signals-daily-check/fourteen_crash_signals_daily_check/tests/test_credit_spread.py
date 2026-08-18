from __future__ import annotations

from datetime import date, timedelta

from fourteen_crash_signals_daily_check import config, credit_spread


def _history(values_from_oldest_to_newest: list[float]) -> list[tuple[date, float]]:
    today = date.today()
    n = len(values_from_oldest_to_newest)
    return [
        (today - timedelta(days=(n - 1 - i)), v)
        for i, v in enumerate(values_from_oldest_to_newest)
    ]


def test_check_credit_spread_streak_unknown_when_fred_unavailable(monkeypatch):
    monkeypatch.setattr("fourteen_crash_signals_daily_check.credit_spread.fred_series_range", lambda series_id, start, end: None)
    result = credit_spread.check_credit_spread_streak()
    assert result.verdict == "unknown"


def test_check_credit_spread_streak_ok_when_below_threshold(monkeypatch):
    monkeypatch.setattr(
        "fourteen_crash_signals_daily_check.credit_spread.fred_series_range",
        lambda series_id, start, end: _history([2.7, 2.7, 2.7]),
    )
    result = credit_spread.check_credit_spread_streak()
    assert result.verdict == "ok"
    assert result.data["streak_days"] == 0


def test_check_credit_spread_streak_ok_when_streak_too_short(monkeypatch):
    values = [3.6] * (config.SIGNALS_CREDIT_SPREAD_STREAK_TRADING_DAYS - 1)
    monkeypatch.setattr(
        "fourteen_crash_signals_daily_check.credit_spread.fred_series_range",
        lambda series_id, start, end: _history(values),
    )
    result = credit_spread.check_credit_spread_streak()
    assert result.verdict == "ok"
    assert result.data["streak_days"] == config.SIGNALS_CREDIT_SPREAD_STREAK_TRADING_DAYS - 1


def test_check_credit_spread_streak_flags_at_exact_boundary(monkeypatch):
    values = [3.6] * config.SIGNALS_CREDIT_SPREAD_STREAK_TRADING_DAYS
    monkeypatch.setattr(
        "fourteen_crash_signals_daily_check.credit_spread.fred_series_range",
        lambda series_id, start, end: _history(values),
    )
    result = credit_spread.check_credit_spread_streak()
    assert result.verdict == "flag"
    assert result.data["streak_days"] == config.SIGNALS_CREDIT_SPREAD_STREAK_TRADING_DAYS


def test_check_credit_spread_streak_breaks_on_a_dip_below_threshold(monkeypatch):
    values = [3.6] * config.SIGNALS_CREDIT_SPREAD_STREAK_TRADING_DAYS + [2.0, 3.9]
    monkeypatch.setattr(
        "fourteen_crash_signals_daily_check.credit_spread.fred_series_range",
        lambda series_id, start, end: _history(values),
    )
    result = credit_spread.check_credit_spread_streak()
    assert result.data["streak_days"] == 1  # only the most recent day counts, the dip reset the streak


def test_check_credit_spread_streak_watch_true_when_value_in_watch_band(monkeypatch):
    monkeypatch.setattr(
        "fourteen_crash_signals_daily_check.credit_spread.fred_series_range",
        lambda series_id, start, end: _history([3.3, 3.3, 3.3]),
    )
    result = credit_spread.check_credit_spread_streak()
    assert result.verdict == "ok"
    assert result.data["watch"] is True
    assert "WATCH" in result.detail


def test_check_credit_spread_streak_watch_false_when_value_below_watch_band(monkeypatch):
    monkeypatch.setattr(
        "fourteen_crash_signals_daily_check.credit_spread.fred_series_range",
        lambda series_id, start, end: _history([2.7, 2.7, 2.7]),
    )
    result = credit_spread.check_credit_spread_streak()
    assert result.verdict == "ok"
    assert result.data["watch"] is False
    assert "WATCH" not in result.detail


def test_check_credit_spread_streak_flag_path_unaffected_by_watch_tier(monkeypatch):
    values = [3.6] * config.SIGNALS_CREDIT_SPREAD_STREAK_TRADING_DAYS
    monkeypatch.setattr(
        "fourteen_crash_signals_daily_check.credit_spread.fred_series_range",
        lambda series_id, start, end: _history(values),
    )
    result = credit_spread.check_credit_spread_streak()
    assert result.verdict == "flag"
    assert "watch" not in result.data
