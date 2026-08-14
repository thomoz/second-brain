from __future__ import annotations

import sys
import types

import pandas as pd

from mytrader import market_data
from mytrader.market_data import TickerData

# conftest.py's autouse _no_real_balance_sheet_statement_fetch fixture patches
# market_data.fetch_balance_sheet_financials to a None-returning stub -- save the
# real function here, at import time before any fixture runs, so the tests below
# that exercise the real implementation can restore it (same pattern as
# test_sec_filings.py / test_news_search.py).
_real_fetch_balance_sheet_financials = market_data.fetch_balance_sheet_financials


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


def test_fetch_current_price_returns_none_when_no_data(monkeypatch):
    monkeypatch.setattr("mytrader.market_data.fetch_ticker_data", lambda ticker: None)
    assert market_data.fetch_current_price("VRTX") is None


def test_fetch_current_price_prefers_regular_market_price(monkeypatch):
    monkeypatch.setattr(
        "mytrader.market_data.fetch_ticker_data",
        lambda ticker: TickerData(
            ticker=ticker, info={"regularMarketPrice": 19.14, "currentPrice": 19.0}, dividends=None
        ),
    )
    assert market_data.fetch_current_price("AG") == 19.14


def test_fetch_current_price_falls_back_to_current_price(monkeypatch):
    monkeypatch.setattr(
        "mytrader.market_data.fetch_ticker_data",
        lambda ticker: TickerData(ticker=ticker, info={"currentPrice": 19.0}, dividends=None),
    )
    assert market_data.fetch_current_price("AG") == 19.0


def _install_fake_yfinance(monkeypatch, balance_sheet=None, financials=None):
    class _FakeTicker:
        def __init__(self, symbol):
            self._symbol = symbol

        @property
        def balance_sheet(self):
            return balance_sheet if balance_sheet is not None else pd.DataFrame()

        @property
        def financials(self):
            return financials if financials is not None else pd.DataFrame()

    fake_yf = types.ModuleType("yfinance")
    fake_yf.Ticker = _FakeTicker
    monkeypatch.setitem(sys.modules, "yfinance", fake_yf)


def test_fetch_balance_sheet_financials_computes_de_and_roe(monkeypatch):
    """Regression fixture for GROW.L (Molten Ventures) -- confirmed live 2026-08-06:
    .info's debtToEquity/currentRatio/returnOnEquity were all None, but these same
    figures were present in the raw statements."""
    bs = pd.DataFrame(
        {pd.Timestamp("2026-03-31"): [130_800_000.0, 1_323_800_000.0]},
        index=["Total Debt", "Stockholders Equity"],
    )
    fin = pd.DataFrame({pd.Timestamp("2026-03-31"): [120_300_000.0]}, index=["Net Income"])
    _install_fake_yfinance(monkeypatch, balance_sheet=bs, financials=fin)
    monkeypatch.setattr(market_data, "fetch_balance_sheet_financials", _real_fetch_balance_sheet_financials)

    result = market_data.fetch_balance_sheet_financials("GROW.L")
    assert result["debtToEquity"] == round(130_800_000.0 / 1_323_800_000.0 * 100, 2)
    assert result["returnOnEquity"] == 120_300_000.0 / 1_323_800_000.0


def test_fetch_balance_sheet_financials_returns_none_when_equity_missing(monkeypatch):
    bs = pd.DataFrame({pd.Timestamp("2026-03-31"): [130_800_000.0]}, index=["Total Debt"])
    _install_fake_yfinance(monkeypatch, balance_sheet=bs)
    monkeypatch.setattr(market_data, "fetch_balance_sheet_financials", _real_fetch_balance_sheet_financials)
    assert market_data.fetch_balance_sheet_financials("X") is None


def test_fetch_balance_sheet_financials_returns_none_when_statement_empty(monkeypatch):
    _install_fake_yfinance(monkeypatch)
    monkeypatch.setattr(market_data, "fetch_balance_sheet_financials", _real_fetch_balance_sheet_financials)
    assert market_data.fetch_balance_sheet_financials("X") is None


def test_fetch_balance_sheet_financials_partial_when_financials_missing(monkeypatch):
    bs = pd.DataFrame(
        {pd.Timestamp("2026-03-31"): [130_800_000.0, 1_323_800_000.0]},
        index=["Total Debt", "Stockholders Equity"],
    )
    _install_fake_yfinance(monkeypatch, balance_sheet=bs)
    monkeypatch.setattr(market_data, "fetch_balance_sheet_financials", _real_fetch_balance_sheet_financials)
    result = market_data.fetch_balance_sheet_financials("X")
    assert "debtToEquity" in result
    assert "returnOnEquity" not in result
