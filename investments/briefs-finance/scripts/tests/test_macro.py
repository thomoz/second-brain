"""Tests for macro.py — mocked yfinance, FRED no-key path."""

from __future__ import annotations

from datetime import date
from unittest.mock import patch



def test_fetch_yfinance_macro_returns_dict_with_expected_keys():
    """fetch_yfinance_macro returns a dict with all expected macro keys."""
    from scripts.macro import fetch_yfinance_macro
    from scripts.config import MACRO_YFINANCE

    # Patch at the import site (macro.py imports get_close_on_or_before directly)
    with patch("scripts.macro.get_close_on_or_before", return_value=4.5):
        result = fetch_yfinance_macro(date(2025, 8, 30))

    assert isinstance(result, dict)
    for key in MACRO_YFINANCE:
        assert key in result


def test_fred_returns_all_none_without_key():
    """When FRED_API_KEY is empty, all FRED values are None."""
    import scripts.macro as macro_mod
    from scripts.config import FRED_SERIES

    original_key = macro_mod.FRED_API_KEY
    try:
        macro_mod.FRED_API_KEY = ""
        result = macro_mod.fetch_fred_macro(date(2025, 8, 30))
        for key in FRED_SERIES:
            assert result[key] is None
    finally:
        macro_mod.FRED_API_KEY = original_key


def test_fetch_macro_snapshot_merges_both_sources():
    """fetch_macro_snapshot merges yfinance and FRED data."""
    from scripts.macro import fetch_macro_snapshot

    with patch("scripts.macro.fetch_yfinance_macro", return_value={
        "treasury_10y": 4.2, "tbill_3m": 5.0, "vix": 20.0,
        "gold": 1900.0, "usd": 28.0, "bonds_20y": 95.0,
    }), patch("scripts.macro.fetch_fred_macro", return_value={
        "yield_curve": -0.5, "recession_prob": 12.0, "cpi": 3.2, "fed_funds": 5.25,
    }):
        result = fetch_macro_snapshot(date(2025, 8, 30))

    assert result["treasury_10y"] == 4.2
    assert result["vix"] == 20.0
    assert result["yield_curve"] == -0.5
    assert result["cpi_yoy"] == 3.2
