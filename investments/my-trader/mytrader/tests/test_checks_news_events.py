from __future__ import annotations

from mytrader.checks import news_events


def test_check_returns_unknown_when_conn_is_none():
    result = news_events.check("ZIM", None)
    assert result.verdict == "unknown"
    assert "database connection" in result.detail


def test_check_returns_unknown_when_search_fails(db_conn, monkeypatch):
    monkeypatch.setattr(news_events.news_search, "get_news_events_for_ticker", lambda ticker, conn: None)
    result = news_events.check("ZIM", db_conn)
    assert result.verdict == "unknown"
    assert "unavailable" in result.detail


def test_check_passes_through_flag_verdict(db_conn, monkeypatch):
    monkeypatch.setattr(
        news_events.news_search, "get_news_events_for_ticker",
        lambda ticker, conn: {"verdict": "flag", "detail": "Live takeover offer."},
    )
    result = news_events.check("ZIM", db_conn)
    assert result.verdict == "flag"
    assert result.detail == "Live takeover offer."


def test_check_passes_through_info_verdict(db_conn, monkeypatch):
    monkeypatch.setattr(
        news_events.news_search, "get_news_events_for_ticker",
        lambda ticker, conn: {"verdict": "info", "detail": "No material news/event findings this run."},
    )
    result = news_events.check("KO", db_conn)
    assert result.verdict == "info"
