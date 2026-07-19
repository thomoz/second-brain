from __future__ import annotations

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
