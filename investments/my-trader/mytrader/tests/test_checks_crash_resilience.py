from __future__ import annotations

from mytrader.checks import crash_resilience
from mytrader.market_data import TickerData


def test_no_data_returns_unknown():
    assert crash_resilience.check(None).verdict == "unknown"


def test_no_history_returns_info_with_explanation(monkeypatch):
    monkeypatch.setattr("mytrader.crash_windows.fetch_crash_drawdowns", lambda ticker: None)
    data = TickerData(ticker="X", info={}, dividends=None)
    result = crash_resilience.check(data)
    assert result.verdict == "info"
    assert "No historical crash-window data" in result.detail


def test_reports_drawdowns_never_flags(monkeypatch):
    monkeypatch.setattr(
        "mytrader.crash_windows.fetch_crash_drawdowns",
        lambda ticker: [
            {"label": "COVID crash (2020)", "drawdown_pct": -59.1},
            {"label": "2022 bear market", "drawdown_pct": -48.3},
        ],
    )
    data = TickerData(ticker="FIVE", info={}, dividends=None)
    result = crash_resilience.check(data)
    assert result.verdict == "info"
    assert "-59.1%" in result.detail
    assert "-48.3%" in result.detail
    assert len(result.data["drawdowns"]) == 2
