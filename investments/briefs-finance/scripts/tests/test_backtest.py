"""Tests for backtest.py — pure math (no network calls)."""

from __future__ import annotations

from datetime import date
from unittest.mock import patch

import pytest

from scripts.prices import compute_return_pct


def test_compute_return_pct_positive():
    """Simple positive return calculation."""
    result = compute_return_pct(100.0, 110.0)
    assert result == pytest.approx(10.0, rel=1e-4)


def test_compute_return_pct_negative():
    result = compute_return_pct(100.0, 80.0)
    assert result == pytest.approx(-20.0, rel=1e-4)


def test_compute_return_pct_zero():
    """Zero return when prices are equal."""
    result = compute_return_pct(100.0, 100.0)
    assert result == pytest.approx(0.0, abs=1e-4)


def test_compute_return_pct_none_start():
    """None start price returns None."""
    assert compute_return_pct(None, 110.0) is None


def test_compute_return_pct_none_end():
    assert compute_return_pct(100.0, None) is None


def test_compute_return_pct_both_none():
    assert compute_return_pct(None, None) is None


def test_compute_return_pct_zero_start():
    """Zero start price returns None (division guard)."""
    assert compute_return_pct(0.0, 10.0) is None


def test_stock_vs_sector_alpha():
    """Stock +10%, ETF +5% → alpha +5%."""
    stock_return = compute_return_pct(100.0, 110.0)   # +10%
    etf_return = compute_return_pct(30.0, 31.5)       # +5%
    alpha = stock_return - etf_return if stock_return is not None and etf_return is not None else None
    assert alpha == pytest.approx(5.0, abs=0.01)


def test_empty_yfinance_returns_none():
    """yfinance returning empty hist → None price."""
    from scripts.prices import get_close_on_or_after

    mock_ticker = type("T", (), {
        "history": lambda self, **kwargs: type("H", (), {"empty": True})()
    })()

    with patch("yfinance.Ticker", return_value=mock_ticker):
        result = get_close_on_or_after("FAKE", date(2025, 1, 1))
    assert result is None
