from __future__ import annotations

from fourteen_crash_signals_daily_check import seller_financing


def test_verdict_always_unknown():
    result = seller_financing.check_seller_financing([{"ticker": "NVDA"}])
    assert result.verdict == "unknown"
    result_empty = seller_financing.check_seller_financing([])
    assert result_empty.verdict == "unknown"


def test_detail_names_every_ticker_in_nonempty_watchlist():
    result = seller_financing.check_seller_financing([{"ticker": "NVDA"}, {"ticker": "MSFT"}])
    assert "NVDA" in result.detail
    assert "MSFT" in result.detail


def test_detail_degrades_gracefully_when_watchlist_empty():
    result = seller_financing.check_seller_financing([])
    assert "No automatable source exists" in result.detail
    assert "news-scan the current hot watchlist yourself" not in result.detail


def test_data_tickers_matches_input_exactly():
    result = seller_financing.check_seller_financing([{"ticker": "NVDA"}, {"ticker": "MSFT"}])
    assert result.data["tickers"] == ["NVDA", "MSFT"]
