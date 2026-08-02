from __future__ import annotations

from mytrader.checks import CheckResult, opportunity
from mytrader.market_data import TickerData

_OK = CheckResult(name="valuation", verdict="ok", detail="fine")
_FLAG = CheckResult(name="balance_sheet", verdict="flag", detail="debt/equity above threshold")
_VALUATION_FLAG = CheckResult(name="valuation", verdict="flag", detail="PE above rich threshold")
_CONCENTRATION_FLAG = CheckResult(name="concentration", verdict="flag", detail="sector concentration")


def test_no_data_returns_unknown():
    assert opportunity.check(None, [], None, None).verdict == "unknown"


def test_no_signals_returns_ok():
    data = TickerData(ticker="X", info={"trailingPE": 20.0}, dividends=None)
    result = opportunity.check(data, [_OK], None, None)
    assert result.verdict == "ok"


def test_active_flag_elsewhere_suppresses_everything():
    """Marks/Munger risk-first gate: don't call it an opportunity while something
    else is actively flagged wrong, no matter how cheap/strong the other signals."""
    data = TickerData(
        ticker="X", info={"trailingPE": 8.0, "priceToBook": 1.0, "pegRatio": 0.5, "returnOnEquity": 0.30},
        dividends=None,
    )
    result = opportunity.check(data, [_FLAG], {"score": 90, "provisional": False}, -20.0)
    assert result.verdict == "ok"
    assert "Active risk flag" in result.detail


def test_concentration_flag_does_not_suppress():
    """Shaun explicitly ruled sector concentration out of scope here."""
    data = TickerData(ticker="X", info={"trailingPE": 8.0, "priceToBook": 1.0}, dividends=None)
    result = opportunity.check(data, [_CONCENTRATION_FLAG], None, None)
    assert result.verdict == "interesting"


def test_graham_number_flags_interesting():
    data = TickerData(ticker="X", info={"trailingPE": 10.0, "priceToBook": 1.5}, dividends=None)
    result = opportunity.check(data, [_OK], None, None)
    assert result.verdict == "interesting"
    assert "Graham" in result.detail
    assert "15.0" in result.detail  # 10.0 * 1.5


def test_graham_ignores_implausible_priceToBook():
    """Real bug caught 2026-07-19: BRK-B's yfinance priceToBook was 0.00097 (a
    dual-share-class data mismatch — bookValue returned was BRK-A's, price was
    BRK-B's), which would otherwise make an already-not-cheap PE 14.6 stock fire the
    Graham leg on garbage data. Falls back to the plain-PE leg, which correctly
    doesn't fire either since 14.6 > PE_CHEAP_THRESHOLD (12.0)."""
    data = TickerData(ticker="BRK-B", info={"trailingPE": 14.6, "priceToBook": 0.00097}, dividends=None)
    result = opportunity.check(data, [_OK], None, None)
    assert result.verdict == "ok"


def test_graham_falls_back_to_pe_when_pb_unavailable():
    data = TickerData(ticker="X", info={"trailingPE": 8.0}, dividends=None)
    result = opportunity.check(data, [_OK], None, None)
    assert result.verdict == "interesting"
    assert "Graham" in result.detail
    assert "P/B unavailable" in result.detail


def test_graham_pe_fallback_ignores_negative_pe():
    """Real bug caught 2026-07-19 during a full-watchlist sweep: TLT (bond ETF) showed
    trailingPE -4226.0, which satisfied `pe <= PE_CHEAP_THRESHOLD` and fired the Graham
    fallback leg as if a deeply negative (loss-making) PE were a bargain. LAND and JOBY
    showed the same pattern with smaller negative PEs."""
    data = TickerData(ticker="TLT", info={"trailingPE": -4226.0}, dividends=None)
    result = opportunity.check(data, [_OK], None, None)
    assert result.verdict == "ok"


def test_lynch_peg_flags_interesting():
    data = TickerData(ticker="X", info={"trailingPE": 20.0, "pegRatio": 0.8}, dividends=None)
    result = opportunity.check(data, [_OK], None, None)
    assert result.verdict == "interesting"
    assert "Lynch" in result.detail


def test_lynch_peg_above_one_does_not_flag():
    data = TickerData(ticker="X", info={"trailingPE": 20.0, "pegRatio": 1.5}, dividends=None)
    result = opportunity.check(data, [_OK], None, None)
    assert result.verdict == "ok"


def test_buffett_smith_quality_at_fair_price_flags_interesting():
    data = TickerData(ticker="X", info={"trailingPE": 20.0, "returnOnEquity": 0.20}, dividends=None)
    result = opportunity.check(data, [_OK], None, None)
    assert result.verdict == "interesting"
    assert "Buffett/Smith" in result.detail


def test_buffett_smith_quality_suppressed_when_already_rich():
    data = TickerData(ticker="X", info={"trailingPE": 60.0, "returnOnEquity": 0.30}, dividends=None)
    result = opportunity.check(data, [_OK], None, None)
    assert "Buffett/Smith" not in result.detail


def test_marks_neilson_dip_flags_interesting_when_nothing_else_wrong():
    data = TickerData(ticker="X", info={"trailingPE": 20.0}, dividends=None)
    result = opportunity.check(data, [_OK], None, -15.0)
    assert result.verdict == "interesting"
    assert "Marks/Neilson" in result.detail


def test_rising_price_alone_no_longer_flags():
    """Graham: 'price momentum does not [matter]' for value signals. A plain price
    rise with no other supporting signal should not be called an opportunity."""
    data = TickerData(ticker="X", info={"trailingPE": 20.0}, dividends=None)
    result = opportunity.check(data, [_OK], None, 18.6)
    assert result.verdict == "ok"


def test_high_briefs_score_flags_interesting():
    data = TickerData(ticker="X", info={"trailingPE": 20.0}, dividends=None)
    result = opportunity.check(data, [_OK], {"score": 80, "provisional": False}, None)
    assert result.verdict == "interesting"
    assert "Briefs Finance" in result.detail
    assert "80/100" in result.detail


def test_low_briefs_score_does_not_flag():
    data = TickerData(ticker="X", info={"trailingPE": 20.0}, dividends=None)
    result = opportunity.check(data, [_OK], {"score": 40, "provisional": False}, None)
    assert result.verdict == "ok"


def test_multiple_signals_note_confluence():
    data = TickerData(
        ticker="X", info={"trailingPE": 10.0, "priceToBook": 1.0, "pegRatio": 0.5},
        dividends=None,
    )
    result = opportunity.check(data, [_OK], {"score": 80, "provisional": False}, None)
    assert result.verdict == "interesting"
    assert "3 independent signals" in result.detail
    assert len(result.data["reasons"]) == 3


def test_crash_discount_fit_flags_interesting_when_rich_but_high_roe():
    """Shaun 2026-08-02: 'if fundamentals show good but price is too high, that's a
    potentially good crash discount buy' -- rich PE alone should no longer suppress
    the signal outright when nothing else is wrong and ROE clears the quality bar."""
    data = TickerData(ticker="X", info={"trailingPE": 60.0, "returnOnEquity": 0.30}, dividends=None)
    result = opportunity.check(data, [_VALUATION_FLAG], None, None)
    assert result.verdict == "interesting"
    assert "Crash-discount fit" in result.detail
    assert "ROE 30.0%" in result.detail
    assert "PE 60.0" in result.detail


def test_crash_discount_fit_does_not_flag_without_strong_roe():
    data = TickerData(ticker="X", info={"trailingPE": 60.0, "returnOnEquity": 0.05}, dividends=None)
    result = opportunity.check(data, [_VALUATION_FLAG], None, None)
    assert result.verdict == "ok"
    assert "Crash-discount fit" not in result.detail


def test_crash_discount_fit_suppressed_by_a_real_other_flag():
    """Rich valuation alone routes to the crash-discount branch, but a genuine
    problem elsewhere (not valuation, not concentration) still suppresses everything
    -- being expensive AND having a real issue is not a crash-discount candidate."""
    data = TickerData(ticker="X", info={"trailingPE": 60.0, "returnOnEquity": 0.30}, dividends=None)
    result = opportunity.check(data, [_VALUATION_FLAG, _FLAG], None, None)
    assert result.verdict == "ok"
    assert "Active risk flag" in result.detail


def test_crash_discount_fit_includes_crash_resilience_note_when_available():
    data = TickerData(ticker="X", info={"trailingPE": 60.0, "returnOnEquity": 0.30}, dividends=None)
    crash_check = CheckResult(
        name="crash_resilience", verdict="info", detail="2022 bear market -16.7%",
        data={"drawdowns": [{"label": "2022 bear market", "drawdown_pct": -16.7}]},
    )
    result = opportunity.check(data, [_VALUATION_FLAG, crash_check], None, None)
    assert result.verdict == "interesting"
    assert "2022 bear market -16.7%" in result.detail
