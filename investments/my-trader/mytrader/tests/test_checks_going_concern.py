from __future__ import annotations

from mytrader.checks import going_concern
from mytrader.market_data import TickerData


def test_no_data_returns_unknown():
    assert going_concern.check(None).verdict == "unknown"


def test_missing_cash_and_fcf_returns_unknown():
    data = TickerData(ticker="X", info={}, dividends=None)
    assert going_concern.check(data).verdict == "unknown"


def test_positive_fcf_is_ok_regardless_of_cash_balance():
    data = TickerData(ticker="X", info={"totalCash": 1_000_000, "freeCashflow": 5_000_000}, dividends=None)
    result = going_concern.check(data)
    assert result.verdict == "ok"
    assert "cash-generative" in result.detail
    assert result.data["runway_months"] is None


def test_short_runway_flags_bankruptcy_risk():
    """CoreWeave-style case Shaun described: ~3 months of cash runway. currentRatio
    set to a normal industrial value so this isn't mistaken for the bank/lender
    carve-out below -- CoreWeave is not a bank."""
    data = TickerData(
        ticker="X",
        info={
            "totalCash": 300_000_000, "freeCashflow": -1_200_000_000,  # $100M/mo burn
            "currentRatio": 1.5,
        },
        dividends=None,
    )
    result = going_concern.check(data)
    assert result.verdict == "flag"
    assert "BANKRUPTCY RISK" in result.detail
    assert result.data["runway_months"] == 3.0


def test_comfortable_runway_is_ok():
    data = TickerData(
        ticker="X",
        info={
            "totalCash": 2_400_000_000, "freeCashflow": -1_200_000_000,  # 24 months
            "currentRatio": 1.5,
        },
        dividends=None,
    )
    result = going_concern.check(data)
    assert result.verdict == "ok"
    assert "No near-term bankruptcy risk" in result.detail
    assert result.data["runway_months"] == 24.0


def test_runway_exactly_at_flag_threshold_flags():
    data = TickerData(
        ticker="X",
        info={
            "totalCash": 1_200_000_000, "freeCashflow": -1_200_000_000,  # 12 months
            "currentRatio": 1.5,
        },
        dividends=None,
    )
    assert going_concern.check(data).verdict == "flag"


def test_falls_back_to_annual_cash_flow_statement_when_info_fcf_missing(monkeypatch):
    monkeypatch.setattr(
        "mytrader.market_data.fetch_cash_flow_statement",
        lambda ticker: {"free_cash_flow": -600_000_000.0},
    )
    data = TickerData(ticker="X", info={"totalCash": 300_000_000, "currentRatio": 1.5}, dividends=None)
    result = going_concern.check(data)
    assert result.verdict == "flag"
    assert "annual FCF" in result.detail
    assert result.data["runway_months"] == 6.0


def test_info_fcf_present_does_not_trigger_annual_fallback(monkeypatch):
    def _raise(ticker):
        raise AssertionError("should not fetch annual statement when .info already has freeCashflow")

    monkeypatch.setattr("mytrader.market_data.fetch_cash_flow_statement", _raise)
    data = TickerData(ticker="X", info={"totalCash": 300_000_000, "freeCashflow": 5_000_000}, dividends=None)
    result = going_concern.check(data)
    assert result.verdict == "ok"


def test_still_unknown_when_annual_fallback_also_has_no_fcf(monkeypatch):
    monkeypatch.setattr("mytrader.market_data.fetch_cash_flow_statement", lambda ticker: None)
    data = TickerData(ticker="X", info={"totalCash": 300_000_000}, dividends=None)
    assert going_concern.check(data).verdict == "unknown"


def test_bank_lender_profile_never_flags_bankruptcy_risk():
    """SOFI-style false positive: debtToEquity/currentRatio both absent (same
    financial-sector signal balance_sheet.py uses) means loan origination/sale
    activity is inflating the apparent burn, not real cash depletion -- the
    runway figure is still shown, just never verdicted "flag"."""
    data = TickerData(
        ticker="SOFI",
        info={"totalCash": 3_367_000_000, "freeCashflow": -3_996_000_000},  # ~10.1mo runway
        dividends=None,
    )
    result = going_concern.check(data)
    assert result.verdict == "ok"
    assert "not flagged as bankruptcy risk" in result.detail
    assert "bank/lender profile" in result.detail
    assert result.data["runway_months"] == 10.1


def test_bank_lender_profile_with_only_debt_to_equity_present_still_flags():
    """Carve-out requires BOTH ratios missing -- a lender with a real current
    ratio populated (not a bank-charter edge case) still gets the normal flag."""
    data = TickerData(
        ticker="X",
        info={
            "totalCash": 300_000_000, "freeCashflow": -1_200_000_000,  # 3mo runway
            "currentRatio": 1.2,
        },
        dividends=None,
    )
    result = going_concern.check(data)
    assert result.verdict == "flag"
    assert "BANKRUPTCY RISK" in result.detail
