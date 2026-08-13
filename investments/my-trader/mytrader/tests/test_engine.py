from __future__ import annotations

from mytrader import engine
from mytrader.checks import CheckResult
from mytrader.market_data import TickerData


def test_run_assessment_includes_all_ten_checks(db_conn, monkeypatch):
    monkeypatch.setattr(
        "mytrader.market_data.fetch_ticker_data",
        lambda ticker: TickerData(ticker=ticker, info={"sector": "Healthcare", "trailingPE": 20.0}, dividends=None),
    )
    result = engine.run_assessment("VRTX", db_conn)
    assert result["ticker"] == "VRTX"
    assert len(result["checks"]) == 12
    assert {c.name for c in result["checks"]} == {
        "company_profile", "dividend", "valuation", "balance_sheet", "fx", "concentration",
        "sector_risk", "etf_mechanics", "opportunity", "price_action",
        "crash_resilience", "technical_levels",
    }
    assert result["excluded"] is False
    assert result["data_available"] is True


def test_run_assessment_excludes_defense_ticker(db_conn, monkeypatch):
    monkeypatch.setattr("mytrader.market_data.fetch_ticker_data", lambda ticker: None)
    result = engine.run_assessment("LMT", db_conn)
    assert result["excluded"] is True
    assert result["exclusion_reason"] is not None
    assert result["data_available"] is False
    assert result["briefs_finance_score"] is None


def test_run_assessment_normalizes_share_class_ticker(db_conn, monkeypatch):
    monkeypatch.setattr("mytrader.market_data.fetch_ticker_data", lambda ticker: None)
    result = engine.run_assessment("BRK.B", db_conn)
    assert result["ticker"] == "BRK-B"


def test_run_assessment_looks_up_briefs_finance_score(db_conn, monkeypatch):
    monkeypatch.setattr("mytrader.market_data.fetch_ticker_data", lambda ticker: None)
    with db_conn:
        cur = db_conn.execute(
            """INSERT INTO reports (file_path, content_hash, report_date, ingested_at)
               VALUES ('x', 'hash1', '2026-01-01', datetime('now'))"""
        )
        report_id = cur.lastrowid
        cur = db_conn.execute(
            """INSERT INTO recommendations (report_id, ticker, excluded, extracted_at)
               VALUES (?, 'VRTX', 0, datetime('now'))""",
            (report_id,),
        )
        rec_id = cur.lastrowid
        db_conn.execute(
            """INSERT INTO likelihood_scores
               (recommendation_id, score, provisional, computed_at)
               VALUES (?, 72, 0, '2026-07-01T00:00:00')""",
            (rec_id,),
        )
    result = engine.run_assessment("VRTX", db_conn)
    assert result["briefs_finance_score"] == {"score": 72, "provisional": False, "computed_at": "2026-07-01T00:00:00"}


def test_run_assessment_computes_score_when_ticker_has_recommendation_but_no_score(db_conn, monkeypatch):
    monkeypatch.setattr("mytrader.market_data.fetch_ticker_data", lambda ticker: None)
    with db_conn:
        cur = db_conn.execute(
            """INSERT INTO reports (file_path, content_hash, report_date, ingested_at)
               VALUES ('x', 'hash1', '2026-01-01', datetime('now'))"""
        )
        report_id = cur.lastrowid
        db_conn.execute(
            """INSERT INTO recommendations (report_id, ticker, buy_thesis, excluded, extracted_at)
               VALUES (?, 'NU', 'digital bank thesis', 0, datetime('now'))""",
            (report_id,),
        )

    def _fake_compute_score(recommendation_id, conn):
        conn.execute(
            """INSERT INTO likelihood_scores
               (recommendation_id, score, provisional, computed_at)
               VALUES (?, 55, 1, '2026-07-19T00:00:00')""",
            (recommendation_id,),
        )
        return {"score": 55, "provisional": True}

    monkeypatch.setattr("scripts.score.compute_score", _fake_compute_score)

    result = engine.run_assessment("NU", db_conn)
    assert result["briefs_finance_score"] == {"score": 55, "provisional": True, "computed_at": "2026-07-19T00:00:00"}


def test_run_assessment_calls_backtest_refresh_for_ticker(db_conn, monkeypatch):
    monkeypatch.setattr("mytrader.market_data.fetch_ticker_data", lambda ticker: None)
    calls = []
    monkeypatch.setattr("mytrader.engine._refresh_backtest_for_ticker", lambda ticker: calls.append(ticker))

    engine.run_assessment("VRTX", db_conn)

    assert calls == ["VRTX"]


def test_refresh_backtest_for_ticker_swallows_exceptions(monkeypatch):
    def _boom(ticker_filter=None):
        raise RuntimeError("network blew up")

    monkeypatch.setattr("scripts.backtest.run_backtest", _boom)
    engine._refresh_backtest_for_ticker("VRTX")  # must not raise


def test_run_assessment_passes_other_checks_and_score_to_opportunity_check(db_conn, monkeypatch):
    monkeypatch.setattr(
        "mytrader.market_data.fetch_ticker_data",
        lambda ticker: TickerData(ticker=ticker, info={"trailingPE": 8.0}, dividends=None),
    )
    monkeypatch.setattr(
        "mytrader.engine._lookup_or_compute_briefs_finance_score",
        lambda ticker, conn: {"score": 85, "provisional": False, "computed_at": "x"},
    )
    monkeypatch.setattr("mytrader.engine.return_data.fetch_recent_return_pct", lambda ticker, period="3mo": -15.0)

    result = engine.run_assessment("VRTX", db_conn)

    opp = next(c for c in result["checks"] if c.name == "opportunity")
    assert opp.verdict == "interesting"
    assert "Graham" in opp.detail
    assert "Marks/Neilson" in opp.detail
    assert "Briefs Finance" in opp.detail
    assert "85/100" in opp.detail


def test_run_assessment_rich_valuation_alone_no_longer_blanket_suppresses(db_conn, monkeypatch):
    """End-to-end: a rich-PE valuation flag with no ROE data doesn't fire the
    crash-discount leg (nothing to judge quality on), but it no longer produces the
    generic 'Active risk flag' suppression message either — valuation is its own
    branch now (see checks/opportunity.py, 2026-08-02: 'if fundamentals show good but
    price is too high, that's a potentially good crash discount buy')."""
    monkeypatch.setattr(
        "mytrader.market_data.fetch_ticker_data",
        lambda ticker: TickerData(ticker=ticker, info={"trailingPE": 60.0}, dividends=None),
    )
    monkeypatch.setattr(
        "mytrader.engine._lookup_or_compute_briefs_finance_score",
        lambda ticker, conn: {"score": 90, "provisional": False, "computed_at": "x"},
    )
    monkeypatch.setattr("mytrader.engine.return_data.fetch_recent_return_pct", lambda ticker, period="3mo": -15.0)

    result = engine.run_assessment("VRTX", db_conn)

    valuation_check = next(c for c in result["checks"] if c.name == "valuation")
    assert valuation_check.verdict == "flag"
    opp = next(c for c in result["checks"] if c.name == "opportunity")
    assert opp.verdict == "ok"
    assert "crash-discount candidate" in opp.detail


def test_run_assessment_crash_discount_fit_fires_with_real_valuation_flag(db_conn, monkeypatch):
    """End-to-end: rich PE + strong ROE, nothing else flagged, actually fires the new
    crash-discount signal through the real engine wiring, not just opportunity.py in
    isolation."""
    monkeypatch.setattr(
        "mytrader.market_data.fetch_ticker_data",
        lambda ticker: TickerData(
            ticker=ticker, info={"trailingPE": 60.0, "returnOnEquity": 0.30}, dividends=None
        ),
    )
    monkeypatch.setattr(
        "mytrader.engine._lookup_or_compute_briefs_finance_score", lambda ticker, conn: None
    )
    monkeypatch.setattr("mytrader.engine.return_data.fetch_recent_return_pct", lambda ticker, period="3mo": None)

    result = engine.run_assessment("VRTX", db_conn)

    opp = next(c for c in result["checks"] if c.name == "opportunity")
    assert opp.verdict == "interesting"
    assert "Crash-discount fit" in opp.detail


def test_run_assessment_fetches_distinct_1mo_and_3mo_returns_for_price_action(db_conn, monkeypatch):
    """Real gap caught 2026-07-19: DG was up +11.4% over 1 month but only -0.1% over
    3 months (the whole move happened recently) -- a single 3-month window hides
    this. price_action now gets both windows fetched independently."""
    monkeypatch.setattr(
        "mytrader.market_data.fetch_ticker_data",
        lambda ticker: TickerData(ticker=ticker, info={"trailingPE": 17.8}, dividends=None),
    )

    def _fake_recent_return(ticker, period="3mo"):
        return {"1mo": 11.4, "3mo": -0.1}[period]

    monkeypatch.setattr("mytrader.engine.return_data.fetch_recent_return_pct", _fake_recent_return)

    result = engine.run_assessment("DG", db_conn)

    price_action_check = next(c for c in result["checks"] if c.name == "price_action")
    assert price_action_check.verdict == "info"
    assert "1mo +11.4%" in price_action_check.detail
    assert "3mo -0.1%" in price_action_check.detail


def test_run_assessment_excludes_principles_fit_by_default(db_conn, monkeypatch):
    """principles_fit is 9 extra LLM calls -- opt-in only, so Monitor's daily re-check
    of every holding + discussed watchlist row (which never passes the flag) stays
    unaffected."""
    monkeypatch.setattr("mytrader.market_data.fetch_ticker_data", lambda ticker: None)
    result = engine.run_assessment("VRTX", db_conn)
    assert "principles_fit" not in {c.name for c in result["checks"]}
    assert len(result["checks"]) == 12


def test_run_assessment_includes_principles_fit_when_opted_in(db_conn, monkeypatch):
    monkeypatch.setattr(
        "mytrader.market_data.fetch_ticker_data",
        lambda ticker: TickerData(ticker=ticker, info={"trailingPE": 20.0}, dividends=None),
    )
    monkeypatch.setattr(
        "mytrader.engine.principles_fit.check",
        lambda *a, **k: CheckResult(name="principles_fit", verdict="info", detail="stub"),
    )
    result = engine.run_assessment("VRTX", db_conn, include_principles_fit=True)
    assert "principles_fit" in {c.name for c in result["checks"]}
    assert len(result["checks"]) == 13


def test_run_assessment_includes_news_events_when_opted_in(db_conn, monkeypatch):
    monkeypatch.setattr(
        "mytrader.market_data.fetch_ticker_data",
        lambda ticker: TickerData(ticker=ticker, info={"trailingPE": 20.0}, dividends=None),
    )
    monkeypatch.setattr(
        "mytrader.engine.news_events.check",
        lambda *a, **k: CheckResult(name="news_events", verdict="info", detail="stub"),
    )
    result = engine.run_assessment("VRTX", db_conn, include_news_events=True)
    assert "news_events" in {c.name for c in result["checks"]}
    assert len(result["checks"]) == 13


def test_news_events_flag_suppresses_opportunity(db_conn, monkeypatch):
    """A material news_events flag should gate opportunity.py the same way a
    dividend/balance-sheet flag does — confirms news_events is wired into
    other_checks (ahead of opportunity), not appended after like principles_fit."""
    monkeypatch.setattr(
        "mytrader.market_data.fetch_ticker_data",
        lambda ticker: TickerData(
            ticker=ticker,
            info={"trailingPE": 5.0, "priceToBook": 0.5, "returnOnEquity": 0.30},
            dividends=None,
        ),
    )
    monkeypatch.setattr(
        "mytrader.engine.news_events.check",
        lambda *a, **k: CheckResult(name="news_events", verdict="flag", detail="Live takeover offer"),
    )
    result = engine.run_assessment("VRTX", db_conn, include_news_events=True)
    opportunity_result = next(c for c in result["checks"] if c.name == "opportunity")
    assert opportunity_result.verdict == "ok"
    assert "Active risk flag" in opportunity_result.detail


def test_run_assessment_skips_mlp_entirely(db_conn, monkeypatch):
    """Shaun's standing preference: MLPs get flagged, not deep-dived -- no checks run,
    no backtest refresh, no briefs-finance score compute (confirmed 2026-08-12)."""
    monkeypatch.setattr(
        "mytrader.market_data.fetch_ticker_data",
        lambda ticker: TickerData(
            ticker=ticker, info={"longName": "Enterprise Products Partners L.P.", "quoteType": "EQUITY"},
            dividends=None,
        ),
    )
    backtest_calls = []
    monkeypatch.setattr("mytrader.engine._refresh_backtest_for_ticker", lambda ticker: backtest_calls.append(ticker))
    score_calls = []
    monkeypatch.setattr(
        "mytrader.engine._lookup_or_compute_briefs_finance_score",
        lambda ticker, conn: score_calls.append(ticker),
    )

    result = engine.run_assessment("EPD", db_conn)

    assert result["mlp"] is True
    assert result["mlp_name"] == "Enterprise Products Partners L.P."
    assert result["checks"] == []
    assert result["briefs_finance_score"] is None
    assert backtest_calls == []
    assert score_calls == []


def test_run_assessment_does_not_flag_non_mlp_or_mlp_holding_etf(db_conn, monkeypatch):
    monkeypatch.setattr(
        "mytrader.market_data.fetch_ticker_data",
        lambda ticker: TickerData(
            ticker=ticker, info={"longName": "Alerian MLP ETF", "quoteType": "ETF"}, dividends=None,
        ),
    )
    result = engine.run_assessment("AMLP", db_conn)
    assert result.get("mlp") is None
    assert len(result["checks"]) > 0


def test_run_assessment_score_stays_none_when_no_recommendation_exists(db_conn, monkeypatch):
    monkeypatch.setattr("mytrader.market_data.fetch_ticker_data", lambda ticker: None)
    calls = []
    monkeypatch.setattr("scripts.score.compute_score", lambda rec_id, conn: calls.append(rec_id))

    result = engine.run_assessment("ZZZZ", db_conn)

    assert result["briefs_finance_score"] is None
    assert calls == []
