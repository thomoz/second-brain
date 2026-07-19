from __future__ import annotations

from mytrader import tickers


def test_normalize_uppercases():
    assert tickers.normalize("vrtx") == "VRTX"


def test_normalize_strips_whitespace():
    assert tickers.normalize("  vrtx  ") == "VRTX"


def test_normalize_maps_share_class():
    assert tickers.normalize("BRK.B") == "BRK-B"
    assert tickers.normalize("brk.a") == "BRK-A"


def test_asx_variant_appends_suffix():
    assert tickers.asx_variant("pmgold") == "PMGOLD.AX"
