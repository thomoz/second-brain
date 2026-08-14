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
    assert mlp_filter.detect({"longName": "Alerian MLP ETF", "quoteType": "ETF"}) is None


def test_falls_back_to_short_name():
    assert mlp_filter.detect({"shortName": "Sunoco LP", "quoteType": "EQUITY"}) == "Sunoco LP"


def test_returns_none_when_no_name_available():
    assert mlp_filter.detect({"quoteType": "EQUITY"}) is None
