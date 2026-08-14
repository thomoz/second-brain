from __future__ import annotations

from mytrader import mlp_filter


def test_detects_period_style_lp_suffix():
    assert mlp_filter.detect({"longName": "Enterprise Products Partners L.P.", "quoteType": "EQUITY"}) == (
        "Enterprise Products Partners L.P."
    )


def test_detects_comma_style_lp_suffix():
    assert mlp_filter.detect({"longName": "Kimbell Royalty Partners, LP", "quoteType": "EQUITY"}) == (
        "Kimbell Royalty Partners, LP"
    )


def test_detects_bare_lp_suffix():
    assert mlp_filter.detect({"longName": "Energy Transfer LP", "quoteType": "EQUITY"}) == "Energy Transfer LP"


def test_does_not_flag_ordinary_corporation():
    assert mlp_filter.detect({"longName": "Energy Fuels Inc.", "quoteType": "EQUITY"}) is None


def test_does_not_flag_a_fund_even_with_mlp_in_the_name():
    # "Alerian MLP ETF" ends in "ETF", not "LP" -- never matches regardless of
    # quoteType. AMLP is a C-corp fund and genuinely doesn't issue K-1s.
    assert mlp_filter.detect({"longName": "Alerian MLP ETF", "quoteType": "ETF"}) is None


def test_flags_a_commodity_pool_fund_despite_etf_quote_type():
    """Real gap caught live 2026-08-14 against CPER: yfinance labels it
    quoteType="ETF", but it's organized and taxed as a limited partnership and
    genuinely issues a Schedule K-1 (confirmed via USCF's own K-1 info page) --
    exactly what this filter exists to catch. An earlier version blanket-exempted
    quoteType=="ETF", which let this slip through."""
    assert mlp_filter.detect(
        {"longName": "United States Copper Index Fund, LP", "quoteType": "ETF"}
    ) == "United States Copper Index Fund, LP"


def test_falls_back_to_short_name():
    assert mlp_filter.detect({"shortName": "Sunoco LP", "quoteType": "EQUITY"}) == "Sunoco LP"


def test_returns_none_when_no_name_available():
    assert mlp_filter.detect({"quoteType": "EQUITY"}) is None
