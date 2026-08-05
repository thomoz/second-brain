from __future__ import annotations

from datetime import datetime, timedelta, timezone

from mytrader import db, news_search

# conftest.py's autouse _no_real_news_events_search fixture patches
# news_search.get_news_events_for_ticker to a None-returning stub (module-global,
# since mytrader.checks.news_events.news_search IS mytrader.news_search -- same
# module object, same situation as test_sec_filings.py). Save the real function here,
# at import time before any fixture runs, so tests below that exercise the real
# orchestrator can restore it.
_real_get_news_events_for_ticker = news_search.get_news_events_for_ticker


def test_parse_json_strips_markdown_fences():
    raw = '```json\n{"material": true, "detail": "x", "findings": []}\n```'
    assert news_search._parse_json(raw) == {"material": True, "detail": "x", "findings": []}


def test_format_detail_combines_summary_and_findings():
    result = {"detail": "Live takeover situation.", "findings": ["Hapag-Lloyd $35 offer", "Rival $37.50 bid"]}
    detail = news_search._format_detail(result)
    assert detail.startswith("Live takeover situation.")
    assert "Hapag-Lloyd $35 offer" in detail
    assert "Rival $37.50 bid" in detail


def test_format_detail_falls_back_to_default_when_empty():
    assert news_search._format_detail({"detail": "", "findings": []}) == "No material news/event findings this run."


def test_get_news_events_uses_cache_when_fresh(db_conn, monkeypatch):
    db.upsert_news_events_cache(db_conn, ticker="ZIM", verdict="flag", detail="Cached takeover detail.")

    def _raise(ticker):
        raise AssertionError("should not search when cache is fresh")

    monkeypatch.setattr(news_search, "_search_news_events", _raise)
    monkeypatch.setattr(news_search, "get_news_events_for_ticker", _real_get_news_events_for_ticker)
    result = news_search.get_news_events_for_ticker("ZIM", db_conn)
    assert result == {"verdict": "flag", "detail": "Cached takeover detail."}


def test_get_news_events_refetches_when_cache_stale(db_conn, monkeypatch):
    with db_conn:
        db_conn.execute(
            "INSERT INTO news_events_cache (ticker, verdict, detail, fetched_at) VALUES (?, ?, ?, ?)",
            ("ZIM", "info", "Old.", (datetime.now(timezone.utc) - timedelta(hours=999)).isoformat()),
        )
    monkeypatch.setattr(
        news_search, "_search_news_events",
        lambda ticker: {"material": True, "detail": "New takeover news.", "findings": []},
    )
    monkeypatch.setattr(news_search, "get_news_events_for_ticker", _real_get_news_events_for_ticker)
    result = news_search.get_news_events_for_ticker("ZIM", db_conn)
    assert result == {"verdict": "flag", "detail": "New takeover news."}
    cached = db.get_cached_news_events(db_conn, "ZIM")
    assert cached["verdict"] == "flag"
    assert cached["detail"] == "New takeover news."


def test_get_news_events_falls_back_to_stale_cache_on_search_failure(db_conn, monkeypatch):
    with db_conn:
        db_conn.execute(
            "INSERT INTO news_events_cache (ticker, verdict, detail, fetched_at) VALUES (?, ?, ?, ?)",
            ("ZIM", "info", "Stale but usable.", (datetime.now(timezone.utc) - timedelta(hours=999)).isoformat()),
        )
    monkeypatch.setattr(news_search, "_search_news_events", lambda ticker: None)
    monkeypatch.setattr(news_search, "get_news_events_for_ticker", _real_get_news_events_for_ticker)
    result = news_search.get_news_events_for_ticker("ZIM", db_conn)
    assert result == {"verdict": "info", "detail": "Stale but usable."}


def test_get_news_events_returns_none_when_search_fails_and_no_cache(db_conn, monkeypatch):
    monkeypatch.setattr(news_search, "_search_news_events", lambda ticker: None)
    monkeypatch.setattr(news_search, "get_news_events_for_ticker", _real_get_news_events_for_ticker)
    assert news_search.get_news_events_for_ticker("ZIM", db_conn) is None


def test_get_news_events_verdict_info_when_not_material(db_conn, monkeypatch):
    monkeypatch.setattr(
        news_search, "_search_news_events",
        lambda ticker: {"material": False, "detail": "", "findings": []},
    )
    monkeypatch.setattr(news_search, "get_news_events_for_ticker", _real_get_news_events_for_ticker)
    result = news_search.get_news_events_for_ticker("KO", db_conn)
    assert result == {"verdict": "info", "detail": "No material news/event findings this run."}
