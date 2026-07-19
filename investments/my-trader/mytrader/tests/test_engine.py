from __future__ import annotations

from mytrader import engine
from mytrader.market_data import TickerData


def test_run_assessment_includes_all_seven_checks(db_conn, monkeypatch):
    monkeypatch.setattr(
        "mytrader.market_data.fetch_ticker_data",
        lambda ticker: TickerData(ticker=ticker, info={"sector": "Healthcare", "trailingPE": 20.0}, dividends=None),
    )
    result = engine.run_assessment("VRTX", db_conn)
    assert result["ticker"] == "VRTX"
    assert len(result["checks"]) == 7
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


def test_run_assessment_score_stays_none_when_no_recommendation_exists(db_conn, monkeypatch):
    monkeypatch.setattr("mytrader.market_data.fetch_ticker_data", lambda ticker: None)
    calls = []
    monkeypatch.setattr("scripts.score.compute_score", lambda rec_id, conn: calls.append(rec_id))

    result = engine.run_assessment("ZZZZ", db_conn)

    assert result["briefs_finance_score"] is None
    assert calls == []
