from __future__ import annotations

import sys
import types

from mytrader import market_data
from mytrader.market_data import TickerData


def _counting_stub(calls: list[str]):
    def _stub(ticker: str) -> TickerData | None:
        calls.append(ticker)
        return TickerData(ticker=ticker, info={"regularMarketPrice": 1.0}, dividends=None)

    return _stub


def test_fetch_ticker_data_without_session_calls_fetch_one_every_time(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr("mytrader.market_data._fetch_one", _counting_stub(calls))
    market_data.fetch_ticker_data("VRTX")
    market_data.fetch_ticker_data("VRTX")
    assert len(calls) == 2


def test_fetch_ticker_data_within_session_caches(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr("mytrader.market_data._fetch_one", _counting_stub(calls))
    with market_data.cached_session():
        market_data.fetch_ticker_data("VRTX")
        market_data.fetch_ticker_data("VRTX")
    assert len(calls) == 1


def test_cached_session_resets_after_context_exits(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr("mytrader.market_data._fetch_one", _counting_stub(calls))
    with market_data.cached_session():
        market_data.fetch_ticker_data("VRTX")
    market_data.fetch_ticker_data("VRTX")
    assert len(calls) == 2


def test_cache_keyed_by_normalized_ticker(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr("mytrader.market_data._fetch_one", _counting_stub(calls))
    with market_data.cached_session():
        market_data.fetch_ticker_data("brk.b")
        market_data.fetch_ticker_data("BRK-B")
    assert len(calls) == 1


def test_looks_valid_rejects_quote_type_none_placeholder():
    """yfinance's failure-mode info dict for a nonexistent symbol carries the literal
    string "NONE" for quoteType, not Python None -- must not be treated as valid."""
    assert market_data._looks_valid({"quoteType": "NONE"}) is False
    assert market_data._looks_valid({}) is False


def test_looks_valid_accepts_real_quote_type():
    assert market_data._looks_valid({"quoteType": "ETF"}) is True
    assert market_data._looks_valid({"regularMarketPrice": 13.49}) is True


def test_fetch_ticker_data_falls_back_to_asx_when_bare_lookup_is_placeholder(monkeypatch):
    """End-to-end: a bare lookup that only returns yfinance's quoteType="NONE"
    placeholder (nonexistent symbol) must not short-circuit the .AX fallback --
    regression test for the XMET (Betashares Energy Transition Metals ETF) bug found
    live 2026-08-04, see market_data._looks_valid's docstring."""
    class _FakeTicker:
        def __init__(self, symbol):
            self._symbol = symbol

        @property
        def info(self):
            return {"quoteType": "NONE"} if self._symbol == "XMET" else {"quoteType": "ETF"}

        dividends = None
        news = []
        calendar = {}

    fake_yf = types.ModuleType("yfinance")
    fake_yf.Ticker = _FakeTicker
    monkeypatch.setitem(sys.modules, "yfinance", fake_yf)

    data = market_data.fetch_ticker_data("XMET")
    assert data is not None
    assert data.info["quoteType"] == "ETF"
