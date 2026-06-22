"""Tests for sector_map.py."""

from __future__ import annotations


from scripts.sector_map import resolve_sector_etf


def test_resolve_gold_returns_gdx():
    """Gold sector should map to GDX (primary/most liquid)."""
    assert resolve_sector_etf("gold") == "GDX"


def test_resolve_gold_underscore():
    """Underscore variant maps correctly."""
    assert resolve_sector_etf("gold") == "GDX"


def test_resolve_unknown_returns_none():
    """Unknown sector keyword returns None."""
    assert resolve_sector_etf("plumbing") is None


def test_resolve_none_input():
    """None input returns None."""
    assert resolve_sector_etf(None) is None


def test_resolve_defense_returns_none():
    """Defense is explicitly excluded — returns None."""
    assert resolve_sector_etf("defense") is None
    assert resolve_sector_etf("defence") is None


def test_resolve_ai_returns_xlk():
    assert resolve_sector_etf("ai") == "XLK"


def test_resolve_energy_returns_xle():
    assert resolve_sector_etf("energy") == "XLE"


def test_resolve_biotech_returns_xbi():
    assert resolve_sector_etf("biotech") == "XBI"


def test_resolve_case_insensitive():
    """Sector lookup is case-normalised."""
    assert resolve_sector_etf("GOLD") == "GDX"
    assert resolve_sector_etf("Gold") == "GDX"
