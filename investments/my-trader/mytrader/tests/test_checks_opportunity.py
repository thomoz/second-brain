from __future__ import annotations

from mytrader.checks import opportunity
from mytrader.market_data import TickerData


def test_no_data_returns_unknown():
    assert opportunity.check(None, None, None).verdict == "unknown"


def test_no_signals_returns_ok():
    data = TickerData(ticker="X", info={"trailingPE": 20.0}, dividends=None)
    result = opportunity.check(data, None, None)
    assert result.verdict == "ok"


def test_cheap_pe_flags_interesting():
    data = TickerData(ticker="X", info={"trailingPE": 8.0}, dividends=None)
    result = opportunity.check(data, None, None)
    assert result.verdict == "interesting"
    assert "PE 8.0" in result.detail


def test_strong_momentum_flags_interesting():
    data = TickerData(ticker="X", info={"trailingPE": 20.0}, dividends=None)
    result = opportunity.check(data, None, 12.0)
    assert result.verdict == "interesting"
    assert "3 months" in result.detail


def test_weak_momentum_does_not_flag():
    data = TickerData(ticker="X", info={"trailingPE": 20.0}, dividends=None)
    result = opportunity.check(data, None, 2.0)
    assert result.verdict == "ok"


def test_high_briefs_score_flags_interesting():
    data = TickerData(ticker="X", info={"trailingPE": 20.0}, dividends=None)
    result = opportunity.check(data, {"score": 80, "provisional": False}, None)
    assert result.verdict == "interesting"
    assert "80/100" in result.detail


def test_provisional_briefs_score_noted_in_detail():
    data = TickerData(ticker="X", info={"trailingPE": 20.0}, dividends=None)
    result = opportunity.check(data, {"score": 75, "provisional": True}, None)
    assert result.verdict == "interesting"
    assert "provisional" in result.detail


def test_low_briefs_score_does_not_flag():
    data = TickerData(ticker="X", info={"trailingPE": 20.0}, dividends=None)
    result = opportunity.check(data, {"score": 40, "provisional": False}, None)
    assert result.verdict == "ok"


def test_multiple_signals_all_listed():
    data = TickerData(ticker="X", info={"trailingPE": 8.0}, dividends=None)
    result = opportunity.check(data, {"score": 80, "provisional": False}, 12.0)
    assert result.verdict == "interesting"
    assert "PE" in result.detail
    assert "3 months" in result.detail
    assert "80/100" in result.detail
    assert len(result.data["reasons"]) == 3
