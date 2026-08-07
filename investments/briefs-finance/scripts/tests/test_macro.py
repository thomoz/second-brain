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


def test_fred_observation_on_passes_units_param_when_given():
    """units, when provided, is passed straight through to FRED's own API params."""
    import scripts.macro as macro_mod

    captured = {}

    class _Resp:
        def json(self):
            return {"observations": [{"value": "3.46", "date": "2026-06-01"}]}

    def _fake_get(url, params, timeout):
        captured.update(params)
        return _Resp()

    original_key = macro_mod.FRED_API_KEY
    try:
        macro_mod.FRED_API_KEY = "fake-key"
        with patch("scripts.macro.requests.get", _fake_get):
            result = macro_mod.fred_observation_on("CPIAUCSL", date(2026, 7, 30), units="pc1")
    finally:
        macro_mod.FRED_API_KEY = original_key

    assert result == (3.46, date(2026, 6, 1))
    assert captured["units"] == "pc1"


def test_fred_observation_on_omits_units_param_by_default():
    """units is omitted entirely (not sent as None) when not provided, preserving
    every existing caller's behavior."""
    import scripts.macro as macro_mod

    captured = {}

    class _Resp:
        def json(self):
            return {"observations": [{"value": "1.0", "date": "2026-06-01"}]}

    def _fake_get(url, params, timeout):
        captured.update(params)
        return _Resp()

    original_key = macro_mod.FRED_API_KEY
    try:
        macro_mod.FRED_API_KEY = "fake-key"
        with patch("scripts.macro.requests.get", _fake_get):
            macro_mod.fred_observation_on("T10Y2Y", date(2026, 7, 30))
    finally:
        macro_mod.FRED_API_KEY = original_key

    assert "units" not in captured


def test_fred_series_range_returns_ascending_pairs_within_window():
    import scripts.macro as macro_mod

    class _Resp:
        def json(self):
            return {"observations": [
                {"value": "1.0", "date": "2024-01-02"},
                {"value": "1.5", "date": "2024-01-03"},
                {"value": ".", "date": "2024-01-04"},  # unpublished -- must be excluded
            ]}

    captured = {}

    def _fake_get(url, params, timeout):
        captured.update(params)
        captured["timeout"] = timeout
        return _Resp()

    original_key = macro_mod.FRED_API_KEY
    try:
        macro_mod.FRED_API_KEY = "fake-key"
        with patch("scripts.macro.requests.get", _fake_get):
            result = macro_mod.fred_series_range("DGS10", date(2024, 1, 1), date(2024, 1, 31))
    finally:
        macro_mod.FRED_API_KEY = original_key

    assert result == [(date(2024, 1, 2), 1.0), (date(2024, 1, 3), 1.5)]
    assert captured["sort_order"] == "asc"
    assert captured["timeout"] == 30


def test_fred_series_range_returns_none_without_key():
    import scripts.macro as macro_mod

    original_key = macro_mod.FRED_API_KEY
    try:
        macro_mod.FRED_API_KEY = ""
        result = macro_mod.fred_series_range("DGS10", date(2024, 1, 1), date(2024, 1, 31))
    finally:
        macro_mod.FRED_API_KEY = original_key

    assert result is None


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
