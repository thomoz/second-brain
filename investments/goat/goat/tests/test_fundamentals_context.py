from __future__ import annotations

from mytrader.market_data import TickerData

from goat import fundamentals_context


def _data(info: dict) -> TickerData:
    return TickerData(ticker="TEST", info=info, dividends=None)


def test_normal_profitable_company_is_not_insolvency_risk():
    data = _data({
        "debtToEquity": 45.2, "totalCash": 5_000_000_000, "freeCashflow": 1_000_000_000,
        "grossMargins": 0.421, "operatingMargins": 0.28, "revenueGrowth": 0.081,
        "operatingCashflow": 2_000_000_000,
    })
    result = fundamentals_context.compute_survival_context("TEST", data)
    assert result["insolvency_risk"] is False
    assert result["cash_runway_years"] is None  # cash-generative, not cash-burning
    assert "debt/equity 45.2" in result["summary"]
    assert "cash generative" in result["summary"]


def test_cash_burning_short_runway_and_high_debt_is_insolvency_risk():
    data = _data({
        "debtToEquity": 200.0, "totalCash": 50_000_000, "freeCashflow": -100_000_000,
        "operatingCashflow": -80_000_000,
    })
    result = fundamentals_context.compute_survival_context("TEST", data)
    assert result["cash_runway_years"] == 0.5
    assert result["insolvency_risk"] is True
    assert "insolvency risk" in result["summary"]


def test_cash_burning_but_low_debt_is_not_insolvency_risk():
    data = _data({
        "debtToEquity": 10.0, "totalCash": 50_000_000, "freeCashflow": -100_000_000,
        "operatingCashflow": -80_000_000,
    })
    result = fundamentals_context.compute_survival_context("TEST", data)
    assert result["cash_runway_years"] == 0.5
    assert result["insolvency_risk"] is False


def test_cash_generative_company_runway_is_none_not_unavailable():
    data = _data({
        "debtToEquity": 50.0, "totalCash": 1_000_000_000, "freeCashflow": 200_000_000,
        "operatingCashflow": 300_000_000,
    })
    result = fundamentals_context.compute_survival_context("TEST", data)
    assert result["cash_runway_years"] is None
    assert "cash generative" in result["summary"]


def test_empty_info_defaults_safe_no_false_positive_insolvency():
    data = _data({})
    result = fundamentals_context.compute_survival_context("TEST", data)
    assert result["debt_to_equity"] is None
    assert result["cash_runway_years"] is None
    assert result["insolvency_risk"] is False


def test_none_data_returns_safe_defaults():
    result = fundamentals_context.compute_survival_context("TEST", None)
    assert result["insolvency_risk"] is False
    assert result["debt_to_equity"] is None
    assert "no fundamentals data available" in result["summary"]


def test_falls_back_to_balance_sheet_financials_when_debt_to_equity_missing(monkeypatch):
    data = _data({"totalCash": 50_000_000, "freeCashflow": -100_000_000, "operatingCashflow": -80_000_000})
    monkeypatch.setattr(
        "goat.fundamentals_context.market_data.fetch_balance_sheet_financials",
        lambda ticker: {"debtToEquity": 300.0},
    )
    result = fundamentals_context.compute_survival_context("TEST", data)
    assert result["debt_to_equity"] == 300.0
    assert result["insolvency_risk"] is True
