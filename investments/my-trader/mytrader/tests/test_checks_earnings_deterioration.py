from __future__ import annotations

from mytrader.checks import earnings_deterioration


def test_check_returns_unknown_when_conn_is_none():
    result = earnings_deterioration.check("KO", None, None)
    assert result.verdict == "unknown"
    assert "database connection" in result.detail


def test_check_returns_unknown_when_all_signals_unknown(db_conn, monkeypatch):
    monkeypatch.setattr(
        earnings_deterioration.earnings_watch, "compute_estimate_trend",
        lambda conn, ticker: {"verdict": "unknown", "detail": "Insufficient history (0/5)"},
    )
    monkeypatch.setattr(
        earnings_deterioration.earnings_watch, "fetch_new_earnings_8ks",
        lambda ticker, conn, *, since: None,
    )
    monkeypatch.setattr(
        earnings_deterioration.news_search, "get_earnings_guidance_for_ticker",
        lambda ticker, conn: None,
    )
    result = earnings_deterioration.check("PMGOLD.AX", None, db_conn)
    assert result.verdict == "unknown"


def test_check_flags_when_estimate_trend_flags(db_conn, monkeypatch):
    monkeypatch.setattr(
        earnings_deterioration.earnings_watch, "compute_estimate_trend",
        lambda conn, ticker: {"verdict": "flag", "detail": "EPS estimate down 5.0%"},
    )
    monkeypatch.setattr(
        earnings_deterioration.earnings_watch, "fetch_new_earnings_8ks",
        lambda ticker, conn, *, since: [],
    )
    monkeypatch.setattr(
        earnings_deterioration.news_search, "get_earnings_guidance_for_ticker",
        lambda ticker, conn: {"verdict": "info", "detail": "No material news/event findings this run."},
    )
    result = earnings_deterioration.check("KO", None, db_conn)
    assert result.verdict == "flag"
    assert "Estimate trend" in result.detail
    assert "EPS estimate down 5.0%" in result.detail


def test_check_flags_with_confluence_suffix_when_multiple_signals_fire(db_conn, monkeypatch):
    monkeypatch.setattr(
        earnings_deterioration.earnings_watch, "compute_estimate_trend",
        lambda conn, ticker: {"verdict": "flag", "detail": "EPS estimate down 5.0%"},
    )
    monkeypatch.setattr(
        earnings_deterioration.earnings_watch, "fetch_new_earnings_8ks",
        lambda ticker, conn, *, since: [{
            "form": "8-K", "accession_number": "acc-2", "items": "2.02",
            "filing_date": "2026-09-02", "summary": "Weak results.", "new_this_run": True,
        }],
    )
    monkeypatch.setattr(
        earnings_deterioration.news_search, "get_earnings_guidance_for_ticker",
        lambda ticker, conn: {"verdict": "info", "detail": "No material news/event findings this run."},
    )
    result = earnings_deterioration.check("KO", None, db_conn)
    assert result.verdict == "flag"
    assert "(2 independent signals)" in result.detail


def test_check_ok_when_no_signals_fire(db_conn, monkeypatch):
    monkeypatch.setattr(
        earnings_deterioration.earnings_watch, "compute_estimate_trend",
        lambda conn, ticker: {"verdict": "ok", "detail": "EPS estimate up 1.0%"},
    )
    monkeypatch.setattr(
        earnings_deterioration.earnings_watch, "fetch_new_earnings_8ks",
        lambda ticker, conn, *, since: [],
    )
    monkeypatch.setattr(
        earnings_deterioration.news_search, "get_earnings_guidance_for_ticker",
        lambda ticker, conn: {"verdict": "info", "detail": "No material news/event findings this run."},
    )
    result = earnings_deterioration.check("KO", None, db_conn)
    assert result.verdict == "ok"
