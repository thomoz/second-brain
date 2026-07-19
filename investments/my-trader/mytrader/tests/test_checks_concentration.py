from __future__ import annotations

from mytrader import db
from mytrader.checks import concentration
from mytrader.market_data import TickerData


def test_no_data_returns_unknown():
    assert concentration.check(None, None).verdict == "unknown"


def test_empty_berkshire_holdings_returns_unknown(db_conn, monkeypatch):
    monkeypatch.setattr("mytrader.config.BERKSHIRE_HOLDINGS", frozenset())
    data = TickerData(ticker="VRTX", info={}, dividends=None)
    result = concentration.check(data, db_conn)
    assert result.data["berkshire"]["verdict"] == "unknown"


def test_berkshire_overlap_flags(db_conn, monkeypatch):
    monkeypatch.setattr("mytrader.config.BERKSHIRE_HOLDINGS", frozenset({"AAPL"}))
    data = TickerData(ticker="AAPL", info={}, dividends=None)
    result = concentration.check(data, db_conn)
    assert result.data["berkshire"]["verdict"] == "flag"
    assert result.verdict == "flag"


def test_sector_concentration_flags_when_over_threshold(db_conn, monkeypatch):
    monkeypatch.setattr("mytrader.config.BERKSHIRE_HOLDINGS", frozenset({"XXXX"}))
    db.upsert_holding(db_conn, ticker="V", name="Visa", asset_type="stock", bucket="1", qty=10, avg_price=100)
    monkeypatch.setattr(
        "mytrader.market_data.fetch_ticker_data",
        lambda ticker: TickerData(ticker=ticker, info={"sector": "Financial Services"}, dividends=None),
    )
    data = TickerData(ticker="MA", info={"sector": "Financial Services"}, dividends=None)
    result = concentration.check(data, db_conn)
    assert result.data["sector"]["verdict"] == "flag"


def test_sector_concentration_ok_when_no_overlap(db_conn, monkeypatch):
    monkeypatch.setattr("mytrader.config.BERKSHIRE_HOLDINGS", frozenset({"XXXX"}))
    db.upsert_holding(db_conn, ticker="V", name="Visa", asset_type="stock", bucket="1", qty=10, avg_price=100)
    monkeypatch.setattr(
        "mytrader.market_data.fetch_ticker_data",
        lambda ticker: TickerData(ticker=ticker, info={"sector": "Financial Services"}, dividends=None),
    )
    data = TickerData(ticker="VRTX", info={"sector": "Healthcare"}, dividends=None)
    result = concentration.check(data, db_conn)
    assert result.data["sector"]["verdict"] == "ok"


def test_no_existing_holdings_returns_info_for_sector(db_conn, monkeypatch):
    monkeypatch.setattr("mytrader.config.BERKSHIRE_HOLDINGS", frozenset({"XXXX"}))
    data = TickerData(ticker="VRTX", info={"sector": "Healthcare"}, dividends=None)
    result = concentration.check(data, db_conn)
    assert result.data["sector"]["verdict"] == "info"
