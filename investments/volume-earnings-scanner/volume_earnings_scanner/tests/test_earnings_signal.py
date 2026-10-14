from __future__ import annotations

import math

import pandas as pd

from volume_earnings_scanner import config, earnings_signal


def _income_stmt(eps_values: list[float | None]) -> pd.DataFrame:
    cols = [f"col{i}" for i in range(len(eps_values))]
    return pd.DataFrame([eps_values], index=["Diluted EPS"], columns=cols)


def test_fetch_quarterly_eps_history_parses_diluted_eps_row(monkeypatch):
    monkeypatch.setattr("mytrader.yf_retry.call", lambda fn: _income_stmt([2.0, 1.5, 1.0, 0.5, float("nan")]))
    history = earnings_signal.fetch_quarterly_eps_history("ABCD")
    assert history == [2.0, 1.5, 1.0, 0.5, None]


def test_fetch_quarterly_eps_history_returns_none_without_diluted_eps_row(monkeypatch):
    frame = pd.DataFrame([[1.0]], index=["Net Income"], columns=["col0"])
    monkeypatch.setattr("mytrader.yf_retry.call", lambda fn: frame)
    assert earnings_signal.fetch_quarterly_eps_history("ABCD") is None


def test_fetch_quarterly_eps_history_returns_none_on_fetch_error(monkeypatch):
    def boom(fn):
        raise RuntimeError("network down")

    monkeypatch.setattr("mytrader.yf_retry.call", boom)
    assert earnings_signal.fetch_quarterly_eps_history("ABCD") is None


def test_record_eps_fires_when_latest_is_highest(monkeypatch):
    monkeypatch.setattr(config, "VE_EARNINGS_MIN_QUARTERS_FOR_RECORD", 4)
    result = earnings_signal.check_record_earnings("ABCD", [2.0, 1.5, 1.0, 0.8])
    assert result.verdict == "interesting"
    assert result.data["record_eps"] is True


def test_record_eps_does_not_fire_when_not_highest(monkeypatch):
    monkeypatch.setattr(config, "VE_EARNINGS_MIN_QUARTERS_FOR_RECORD", 4)
    monkeypatch.setattr(config, "VE_EARNINGS_MIN_QUARTERS_FOR_YOY_ACCEL", 99)  # disable YoY sub-check
    result = earnings_signal.check_record_earnings("ABCD", [1.0, 2.0, 1.5, 0.8])
    assert result.verdict == "ok"


def test_unknown_below_minimum_usable_quarters(monkeypatch):
    monkeypatch.setattr(config, "VE_EARNINGS_MIN_QUARTERS_FOR_RECORD", 4)
    result = earnings_signal.check_record_earnings("ABCD", [2.0, None, None])
    assert result.verdict == "unknown"


def test_unknown_when_eps_history_is_none():
    result = earnings_signal.check_record_earnings("ABCD", None)
    assert result.verdict == "unknown"


def test_accelerating_yoy_requires_min_quarters(monkeypatch):
    monkeypatch.setattr(config, "VE_EARNINGS_MIN_QUARTERS_FOR_RECORD", 4)
    monkeypatch.setattr(config, "VE_EARNINGS_MIN_QUARTERS_FOR_YOY_ACCEL", 5)
    # Exactly 4 quarters -- record-EPS runs, YoY-accel cannot (needs 5).
    result = earnings_signal.check_record_earnings("ABCD", [1.0, 0.9, 0.8, 0.7])
    assert "accelerating_yoy" not in result.data


def test_accelerating_yoy_fires_on_fastest_positive_growth(monkeypatch):
    monkeypatch.setattr(config, "VE_EARNINGS_MIN_QUARTERS_FOR_RECORD", 4)
    monkeypatch.setattr(config, "VE_EARNINGS_MIN_QUARTERS_FOR_YOY_ACCEL", 5)
    # 5 quarters -> exactly one YoY pair: latest (1.5) vs 4-quarters-ago (1.0) = +50%.
    result = earnings_signal.check_record_earnings("ABCD", [1.5, 1.4, 1.3, 1.2, 1.0])
    assert result.verdict == "interesting"
    assert result.data["accelerating_yoy"] is True
    assert math.isclose(result.data["latest_yoy_growth_pct"], 50.0)


def test_accelerating_yoy_does_not_fire_on_negative_growth(monkeypatch):
    monkeypatch.setattr(config, "VE_EARNINGS_MIN_QUARTERS_FOR_RECORD", 4)
    monkeypatch.setattr(config, "VE_EARNINGS_MIN_QUARTERS_FOR_YOY_ACCEL", 5)
    result = earnings_signal.check_record_earnings("ABCD", [0.5, 0.6, 0.7, 0.8, 1.0])
    assert result.data.get("accelerating_yoy") is False


def test_yoy_math_never_divides_by_zero(monkeypatch):
    monkeypatch.setattr(config, "VE_EARNINGS_MIN_QUARTERS_FOR_RECORD", 4)
    monkeypatch.setattr(config, "VE_EARNINGS_MIN_QUARTERS_FOR_YOY_ACCEL", 5)
    # prior-year quarter is exactly 0 -- must not raise or produce a nonsensical result.
    result = earnings_signal.check_record_earnings("ABCD", [0.1, 0.2, 0.3, 0.4, 0.0])
    assert result.verdict in {"ok", "interesting", "unknown"}  # no exception
