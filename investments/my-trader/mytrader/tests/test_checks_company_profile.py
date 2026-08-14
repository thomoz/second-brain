from __future__ import annotations

from mytrader.checks import company_profile
from mytrader.market_data import TickerData


def test_no_data_returns_unknown():
    result = company_profile.check(None)
    assert result.verdict == "unknown"


def test_uses_first_two_sentences_of_business_summary():
    data = TickerData(
        ticker="VRTX",
        info={
            "longBusinessSummary": (
                "Vertex Pharmaceuticals develops therapies for cystic fibrosis. "
                "It also has a pipeline in pain and other diseases. "
                "It was founded in 1989."
            )
        },
        dividends=None,
    )
    result = company_profile.check(data)
    assert result.verdict == "info"
    assert result.detail == (
        "Vertex Pharmaceuticals develops therapies for cystic fibrosis. "
        "It also has a pipeline in pain and other diseases."
    )


def test_abbreviation_in_name_consumes_a_sentence_slot_without_breaking_output():
    """Known, accepted gap: a naive ". " split can't tell "L.P." from a real sentence
    boundary, so a name like EPD's ends up costing one of the two sentence slots --
    real-world confirmed 2026-08-12. Output should still be a correct, complete
    sentence, just shorter than the two-sentence case above."""
    data = TickerData(
        ticker="EPD",
        info={
            "longBusinessSummary": (
                "Enterprise Products Partners L.P. provides midstream energy services. "
                "It operates in four segments."
            )
        },
        dividends=None,
    )
    result = company_profile.check(data)
    assert result.detail == "Enterprise Products Partners L.P. provides midstream energy services."


def test_truncates_long_summary():
    data = TickerData(
        ticker="X", info={"longBusinessSummary": "A" * 500 + ". " + "B" * 500}, dividends=None,
    )
    result = company_profile.check(data)
    assert len(result.detail) <= 400
    assert result.detail.endswith("...")


def test_falls_back_to_sector_industry_when_no_summary():
    data = TickerData(
        ticker="X",
        info={"longName": "Example Corp", "sector": "Energy", "industry": "Oil & Gas Midstream"},
        dividends=None,
    )
    result = company_profile.check(data)
    assert result.verdict == "info"
    assert "Example Corp" in result.detail
    assert "Energy" in result.detail
    assert "Oil & Gas Midstream" in result.detail


def test_unknown_when_nothing_available():
    data = TickerData(ticker="X", info={}, dividends=None)
    result = company_profile.check(data)
    assert result.verdict == "unknown"
