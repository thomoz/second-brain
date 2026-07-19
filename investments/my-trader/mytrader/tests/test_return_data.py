from __future__ import annotations

from mytrader import db, return_data
from mytrader.market_data import TickerData


def test_fetch_dividend_yield_pct_returns_none_when_no_data(monkeypatch):
    monkeypatch.setattr("mytrader.return_data.market_data.fetch_ticker_data", lambda t: None)
    assert return_data.fetch_dividend_yield_pct("VRTX") is None


def test_fetch_dividend_yield_pct_returns_none_when_missing_field(monkeypatch):
    monkeypatch.setattr(
        "mytrader.return_data.market_data.fetch_ticker_data",
        lambda t: TickerData(ticker=t, info={}, dividends=None),
    )
    assert return_data.fetch_dividend_yield_pct("VRTX") is None


def test_fetch_dividend_yield_pct_prefers_trailing_fraction_when_populated(monkeypatch):
    # trailingAnnualDividendYield is a fraction (needs *100) — verified against real
    # MSFT data 2026-07-19: trailingAnnualDividendYield=0.008875592 -> 0.89%.
    monkeypatch.setattr(
        "mytrader.return_data.market_data.fetch_ticker_data",
        lambda t: TickerData(
            ticker=t,
            info={"trailingAnnualDividendYield": 0.008875592, "dividendYield": 0.92},
            dividends=None,
        ),
    )
    assert return_data.fetch_dividend_yield_pct("MSFT") == 0.89


def test_fetch_dividend_yield_pct_falls_back_to_forward_percent_when_trailing_is_zero(monkeypatch):
    # trailingAnnualDividendYield=0.0 is how ETFs like HDV commonly come back from
    # Yahoo despite having a real yield — dividendYield is already a direct percent
    # number (2.9 means 2.9%, not a fraction), verified against real HDV data.
    monkeypatch.setattr(
        "mytrader.return_data.market_data.fetch_ticker_data",
        lambda t: TickerData(
            ticker=t,
            info={"trailingAnnualDividendYield": 0.0, "dividendYield": 2.9},
            dividends=None,
        ),
    )
    assert return_data.fetch_dividend_yield_pct("HDV") == 2.9


def test_fetch_dividend_yield_pct_falls_back_when_trailing_field_missing(monkeypatch):
    monkeypatch.setattr(
        "mytrader.return_data.market_data.fetch_ticker_data",
        lambda t: TickerData(ticker=t, info={"dividendYield": 2.85}, dividends=None),
    )
    assert return_data.fetch_dividend_yield_pct("HDV") == 2.85


def test_fetch_dividend_yield_pct_rejects_implausibly_high_value(monkeypatch):
    monkeypatch.setattr(
        "mytrader.return_data.market_data.fetch_ticker_data",
        lambda t: TickerData(ticker=t, info={"dividendYield": 92.0}, dividends=None),
    )
    assert return_data.fetch_dividend_yield_pct("MSFT") is None


def test_fetch_ten_year_return_pct_returns_none_on_empty_history(monkeypatch):
    import types

    class _FakeTicker:
        def __init__(self, symbol):
            pass

        def history(self, period, auto_adjust):
            import pandas as pd
            return pd.DataFrame()

    fake_yf = types.ModuleType("yfinance")
    fake_yf.Ticker = _FakeTicker
    monkeypatch.setitem(__import__("sys").modules, "yfinance", fake_yf)

    assert return_data.fetch_ten_year_return_pct("NOPE") is None


def test_fetch_ten_year_return_pct_computes_cumulative_return(monkeypatch):
    import types

    import pandas as pd

    class _FakeTicker:
        def __init__(self, symbol):
            self.symbol = symbol

        def history(self, period, auto_adjust):
            return pd.DataFrame({"Close": [100.0, 200.0]})

    fake_yf = types.ModuleType("yfinance")
    fake_yf.Ticker = _FakeTicker
    monkeypatch.setitem(__import__("sys").modules, "yfinance", fake_yf)

    assert return_data.fetch_ten_year_return_pct("VRTX") == 100.0


def test_fetch_recent_return_pct_computes_cumulative_return(monkeypatch):
    # Calls _fetch_cumulative_return_pct directly, not the public
    # fetch_recent_return_pct wrapper -- conftest.py's global
    # _no_real_recent_return_fetch fixture stubs the latter (accessed via
    # mytrader.engine.return_data.fetch_recent_return_pct, which mutates the shared
    # return_data module attribute) for every test by default, since engine.py calls
    # it as a real network fetch. The underlying helper is untouched by that stub.
    import types

    import pandas as pd

    class _FakeTicker:
        def __init__(self, symbol):
            self.symbol = symbol

        def history(self, period, auto_adjust):
            assert period == "3mo"
            return pd.DataFrame({"Close": [100.0, 115.0]})

    fake_yf = types.ModuleType("yfinance")
    fake_yf.Ticker = _FakeTicker
    monkeypatch.setitem(__import__("sys").modules, "yfinance", fake_yf)

    assert return_data._fetch_cumulative_return_pct("VRTX", "3mo") == 15.0


def test_refresh_watchlist_return_data_updates_rows(db_conn, monkeypatch):
    db.upsert_watchlist_row(
        db_conn, ticker="VRTX", name="Vertex Pharmaceuticals", asset_type="stock", bucket="1",
    )
    monkeypatch.setattr("mytrader.return_data.fetch_dividend_yield_pct", lambda t: 1.5)
    monkeypatch.setattr("mytrader.return_data.fetch_ten_year_return_pct", lambda t: 458.0)

    updated = return_data.refresh_watchlist_return_data(db_conn)

    assert updated == 1
    row = db.get_watchlist_row(db_conn, "VRTX", "1")
    assert row["dividend_yield_pct"] == 1.5
    assert row["ten_year_return_pct"] == 458.0
    assert row["return_data_updated_at"] is not None


def test_refresh_watchlist_return_data_counts_zero_when_nothing_found(db_conn, monkeypatch):
    db.upsert_watchlist_row(
        db_conn, ticker="VRTX", name="Vertex Pharmaceuticals", asset_type="stock", bucket="1",
    )
    monkeypatch.setattr("mytrader.return_data.fetch_dividend_yield_pct", lambda t: None)
    monkeypatch.setattr("mytrader.return_data.fetch_ten_year_return_pct", lambda t: None)

    updated = return_data.refresh_watchlist_return_data(db_conn)

    assert updated == 0
