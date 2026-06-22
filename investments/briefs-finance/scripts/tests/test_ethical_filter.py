"""Tests for ethical_filter.py."""

from __future__ import annotations

from scripts.ethical_filter import check_ticker


def test_lmt_excluded():
    """LMT is a primary defense contractor — must be excluded."""
    excluded, reason = check_ticker("LMT")
    assert excluded is True
    assert reason is not None
    assert "defense" in reason.lower() or "military" in reason.lower()


def test_rtx_excluded():
    excluded, reason = check_ticker("RTX")
    assert excluded is True


def test_aapl_allowed():
    """Apple has no defense exclusion."""
    excluded, reason = check_ticker("AAPL")
    assert excluded is False
    assert reason is None


def test_ba_flagged_not_excluded():
    """Boeing is borderline — flagged for review, not auto-excluded."""
    excluded, reason = check_ticker("BA")
    assert excluded is False
    assert reason is not None
    assert "REVIEW" in reason


def test_pltr_flagged_not_excluded():
    """Palantir is borderline — flagged, not excluded."""
    excluded, reason = check_ticker("PLTR")
    assert excluded is False
    assert reason is not None
    assert "REVIEW" in reason


def test_asx_suffix_stripped():
    """ASX suffix (.AX) should be stripped before checking."""
    excluded, reason = check_ticker("LMT.AX")
    assert excluded is True


def test_lowercase_input():
    """Lowercase ticker input is normalised."""
    excluded, reason = check_ticker("lmt")
    assert excluded is True


def test_kgc_allowed():
    excluded, reason = check_ticker("KGC")
    assert excluded is False
    assert reason is None
