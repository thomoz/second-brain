from __future__ import annotations

from mytrader.checks import price_action


def test_no_data_returns_unknown():
    assert price_action.check(None, None).verdict == "unknown"


def test_shows_both_windows():
    result = price_action.check(11.4, -0.1)
    assert result.verdict == "info"
    assert "1mo +11.4%" in result.detail
    assert "3mo -0.1%" in result.detail


def test_verdict_is_never_flag_or_interesting_regardless_of_magnitude():
    """Not a buy/sell signal — Graham: 'price momentum does not matter' for value
    signals. This check only ever reports, never judges."""
    assert price_action.check(500.0, 500.0).verdict == "info"
    assert price_action.check(-90.0, -90.0).verdict == "info"


def test_shows_only_available_window():
    result = price_action.check(11.4, None)
    assert result.verdict == "info"
    assert "1mo +11.4%" in result.detail
    assert "3mo" not in result.detail
