from __future__ import annotations

from mytrader.checks import etf_mechanics
from mytrader.market_data import TickerData


def test_no_data_returns_unknown():
    assert etf_mechanics.check(None, None).verdict == "unknown"


def test_non_etf_returns_unknown():
    data = TickerData(ticker="X", info={"quoteType": "EQUITY"}, dividends=None)
    assert etf_mechanics.check(data, None).verdict == "unknown"


def test_first_sight_captures_baseline():
    data = TickerData(
        ticker="SCHD", info={"quoteType": "ETF", "netExpenseRatio": 0.06, "totalAssets": 6e10},
        dividends=None,
    )
    result = etf_mechanics.check(data, None)
    assert result.verdict == "info"
    assert "Expense ratio 0.06%" in result.detail
    assert "AUM $" in result.detail


def test_expense_ratio_drift_flags():
    data = TickerData(
        ticker="SCHD", info={"quoteType": "ETF", "netExpenseRatio": 0.10, "totalAssets": 6e10},
        dividends=None,
    )
    existing_row = {"last_expense_ratio": 0.06}
    result = etf_mechanics.check(data, existing_row)
    assert result.verdict == "flag"
    assert "changed from 0.0600 to 0.1000" in result.detail


def test_unchanged_expense_ratio_returns_info():
    data = TickerData(
        ticker="SCHD", info={"quoteType": "ETF", "netExpenseRatio": 0.06, "totalAssets": 6e10},
        dividends=None,
    )
    existing_row = {"last_expense_ratio": 0.06}
    result = etf_mechanics.check(data, existing_row)
    assert result.verdict == "info"


def test_rich_expense_ratio_flags():
    data = TickerData(
        ticker="X", info={"quoteType": "ETF", "netExpenseRatio": 1.25, "totalAssets": 6e10},
        dividends=None,
    )
    result = etf_mechanics.check(data, None)
    assert result.verdict == "flag"
    assert "Expense ratio 1.25% at/above 1.0%" in result.detail
    assert "/10 —" in result.detail


def test_cheap_expense_ratio_does_not_flag():
    data = TickerData(
        ticker="X", info={"quoteType": "ETF", "netExpenseRatio": 0.03, "totalAssets": 6e10},
        dividends=None,
    )
    result = etf_mechanics.check(data, None)
    assert result.verdict == "info"


def test_small_aum_flags_closure_risk():
    data = TickerData(
        ticker="X", info={"quoteType": "ETF", "netExpenseRatio": 0.5, "totalAssets": 20_000_000},
        dividends=None,
    )
    result = etf_mechanics.check(data, None)
    assert result.verdict == "flag"
    assert "AUM $20,000,000 below $50,000,000" in result.detail
    assert "closure-risk" in result.detail


def test_healthy_aum_does_not_flag():
    data = TickerData(
        ticker="X", info={"quoteType": "ETF", "netExpenseRatio": 0.5, "totalAssets": 129_000_000},
        dividends=None,
    )
    result = etf_mechanics.check(data, None)
    assert result.verdict == "info"


def test_missing_expense_ratio_and_aum_still_returns_info():
    """AU-domiciled ETFs: yfinance leaves netExpenseRatio unpopulated (confirmed live
    against XMET/PMGOLD/IXI.AX) -- must degrade gracefully, not error or flag."""
    data = TickerData(ticker="X", info={"quoteType": "ETF"}, dividends=None)
    result = etf_mechanics.check(data, None)
    assert result.verdict == "info"
    assert "Expense ratio unavailable" in result.detail
    assert "AUM unavailable" in result.detail


def test_holdings_context_included_when_available(monkeypatch):
    import pandas as pd

    class _FakeFundsData:
        top_holdings = pd.DataFrame(
            {"Name": ["Nvidia Corp", "Apple Inc"], "Holding Percent": [0.075, 0.066]},
            index=["NVDA", "AAPL"],
        )
        sector_weightings = {"technology": 0.5, "energy": 0.1}

    monkeypatch.setattr("mytrader.checks.etf_mechanics._fetch_funds_data", lambda ticker: _FakeFundsData())
    data = TickerData(
        ticker="IVV", info={"quoteType": "ETF", "netExpenseRatio": 0.03, "totalAssets": 8.8e11},
        dividends=None,
    )
    result = etf_mechanics.check(data, None)
    assert "top holdings: Nvidia Corp (7.5%), Apple Inc (6.6%)" in result.detail
    assert "dominant sector: Technology (50%)" in result.detail


def test_holdings_context_absent_degrades_silently():
    """Default autouse fixture stubs _fetch_funds_data to None -- confirms the check
    still works without holdings context, no crash."""
    data = TickerData(
        ticker="X", info={"quoteType": "ETF", "netExpenseRatio": 0.06, "totalAssets": 6e10},
        dividends=None,
    )
    result = etf_mechanics.check(data, None)
    assert result.verdict == "info"
    assert "top holdings" not in result.detail
