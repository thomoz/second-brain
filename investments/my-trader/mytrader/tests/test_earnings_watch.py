from __future__ import annotations

import sys
import types
from datetime import date, timedelta

from mytrader import config, db, earnings_watch

# conftest.py's autouse fixtures patch earnings_watch.fetch_estimate_snapshot and
# earnings_watch.fetch_new_earnings_8ks to None-returning stubs (module-global) so
# the rest of the suite never hits real network/LLM calls -- save the real functions
# here, at import time before any fixture runs, so the tests below that exercise the
# real functions can restore them. Mirrors test_market_data.py's
# _real_fetch_balance_sheet_financials precedent exactly.
_real_fetch_estimate_snapshot = earnings_watch.fetch_estimate_snapshot
_real_fetch_new_earnings_8ks = earnings_watch.fetch_new_earnings_8ks


def _columnar_8k_index(rows):
    """rows: list of (accession, items, filing_date, primary_document)."""
    return {"filings": {"recent": {
        "form": ["8-K"] * len(rows),
        "accessionNumber": [r[0] for r in rows],
        "items": [r[1] for r in rows],
        "filingDate": [r[2] for r in rows],
        "primaryDocument": [r[3] for r in rows],
        "primaryDocDescription": [""] * len(rows),
        "acceptanceDateTime": [r[2] + "T18:00:00Z" for r in rows],
    }}}


# --- fetch_estimate_snapshot ---------------------------------------------------


class _FakeSeries(dict):
    def get(self, key, default=None):
        return dict.get(self, key, default)


class _FakeFrame:
    """Minimal stand-in for a pandas DataFrame indexed by period, only supporting
    the .empty / "in" / .loc[...] access patterns fetch_estimate_snapshot uses."""

    def __init__(self, rows: dict[str, dict]):
        self._rows = rows

    @property
    def empty(self) -> bool:
        return not self._rows

    def __contains__(self, key):
        return key in self._rows

    class _Loc:
        def __init__(self, rows):
            self._rows = rows

        def __getitem__(self, key):
            return _FakeSeries(self._rows[key])

    @property
    def loc(self):
        return _FakeFrame._Loc(self._rows)

    @property
    def index(self):
        return list(self._rows.keys())


def _install_fake_yfinance_estimates(monkeypatch, *, eps_trend=None, earnings_estimate=None,
                                      revenue_estimate=None, eps_revisions=None):
    class _FakeTicker:
        def __init__(self, symbol):
            self._symbol = symbol

        @property
        def eps_trend(self):
            return eps_trend if eps_trend is not None else _FakeFrame({})

        @property
        def earnings_estimate(self):
            return earnings_estimate if earnings_estimate is not None else _FakeFrame({})

        @property
        def revenue_estimate(self):
            return revenue_estimate if revenue_estimate is not None else _FakeFrame({})

        @property
        def eps_revisions(self):
            return eps_revisions if eps_revisions is not None else _FakeFrame({})

    fake_yf = types.ModuleType("yfinance")
    fake_yf.Ticker = _FakeTicker
    monkeypatch.setitem(sys.modules, "yfinance", fake_yf)


def test_fetch_estimate_snapshot_returns_none_when_eps_trend_empty(monkeypatch):
    monkeypatch.setattr(earnings_watch, "fetch_estimate_snapshot", _real_fetch_estimate_snapshot)
    _install_fake_yfinance_estimates(monkeypatch, eps_trend=_FakeFrame({}))
    assert earnings_watch.fetch_estimate_snapshot("AAPL") is None


def test_fetch_estimate_snapshot_extracts_avg_and_revisions(monkeypatch):
    monkeypatch.setattr(earnings_watch, "fetch_estimate_snapshot", _real_fetch_estimate_snapshot)
    _install_fake_yfinance_estimates(
        monkeypatch,
        eps_trend=_FakeFrame({"0y": {"current": 8.8}}),
        earnings_estimate=_FakeFrame({"0y": {"avg": 8.81}}),
        revenue_estimate=_FakeFrame({"0y": {"avg": 477_000_000_000.0}}),
        eps_revisions=_FakeFrame({"0y": {"upLast30days": 5, "downLast30days": 2}}),
    )
    snapshot = earnings_watch.fetch_estimate_snapshot("AAPL")
    assert snapshot == {
        "eps_estimate_avg": 8.81,
        "revenue_estimate_avg": 477_000_000_000.0,
        "revisions_up_30d": 5,
        "revisions_down_30d": 2,
    }


# --- compute_estimate_trend -----------------------------------------------------


def _seed_history(conn, ticker: str, values: list[tuple[int, float]]):
    """values: list of (days_ago, eps_estimate_avg)."""
    for days_ago, avg in values:
        d = (date.today() - timedelta(days=days_ago)).isoformat()
        db.record_estimate_snapshot(
            conn, ticker=ticker, date=d, eps_estimate_avg=avg,
            revenue_estimate_avg=None, revisions_up_30d=None, revisions_down_30d=None,
        )


def test_compute_estimate_trend_insufficient_history(db_conn):
    _seed_history(db_conn, "KO", [(10, 10.0), (5, 9.9)])  # fewer than MIN_DATAPOINTS
    result = earnings_watch.compute_estimate_trend(db_conn, "KO")
    assert result["verdict"] == "unknown"
    assert "Insufficient history" in result["detail"]


def test_compute_estimate_trend_flags_on_decline(db_conn):
    _seed_history(db_conn, "KO", [(25, 10.0), (20, 9.8), (15, 9.6), (10, 9.5), (5, 9.4)])
    result = earnings_watch.compute_estimate_trend(db_conn, "KO")
    assert result["verdict"] == "flag"
    assert "down" in result["detail"]


def test_compute_estimate_trend_ok_when_stable(db_conn):
    _seed_history(db_conn, "KO", [(25, 10.0), (20, 10.0), (15, 10.0), (10, 10.0), (5, 10.0)])
    result = earnings_watch.compute_estimate_trend(db_conn, "KO")
    assert result["verdict"] == "ok"


# --- fetch_new_earnings_8ks ------------------------------------------------------


def test_fetch_new_earnings_8ks_returns_none_without_cik(db_conn, monkeypatch):
    monkeypatch.setattr(earnings_watch, "fetch_new_earnings_8ks", _real_fetch_new_earnings_8ks)
    monkeypatch.setattr(earnings_watch.sec_filings, "get_cik", lambda conn, ticker: None)
    result = earnings_watch.fetch_new_earnings_8ks("BXB", db_conn, since=date(2026, 1, 1))
    assert result is None


def test_fetch_new_earnings_8ks_filters_non_allowlisted_items(db_conn, monkeypatch):
    monkeypatch.setattr(earnings_watch, "fetch_new_earnings_8ks", _real_fetch_new_earnings_8ks)
    monkeypatch.setattr(earnings_watch.sec_filings, "get_cik", lambda conn, ticker: "21344")
    monkeypatch.setattr(
        earnings_watch.sec_filings, "fetch_filing_index",
        lambda cik: _columnar_8k_index([("acc-1", "5.02", "2026-09-01", "doc1.htm")]),
    )

    def _raise(*a, **k):
        raise AssertionError("should not fetch document for a non-allowlisted 8-K")

    monkeypatch.setattr(earnings_watch.sec_filings, "fetch_filing_document", _raise)
    result = earnings_watch.fetch_new_earnings_8ks("KO", db_conn, since=date(2026, 1, 1))
    assert result == []


def test_fetch_new_earnings_8ks_summarizes_allowlisted_new_filing(db_conn, monkeypatch):
    monkeypatch.setattr(earnings_watch, "fetch_new_earnings_8ks", _real_fetch_new_earnings_8ks)
    monkeypatch.setattr(earnings_watch.sec_filings, "get_cik", lambda conn, ticker: "21344")
    monkeypatch.setattr(
        earnings_watch.sec_filings, "fetch_filing_index",
        lambda cik: _columnar_8k_index([
            ("acc-1", "5.02", "2026-09-01", "doc1.htm"),
            ("acc-2", "2.02,9.01", "2026-09-02", "doc2.htm"),
        ]),
    )
    monkeypatch.setattr(earnings_watch.sec_filings, "fetch_filing_document", lambda cik, acc, doc: "<html>body</html>")
    monkeypatch.setattr(earnings_watch.sec_filings, "strip_html", lambda html: "raw text")
    monkeypatch.setattr(earnings_watch, "_summarize_8k", lambda ticker, items, text: "Results summary.")

    result = earnings_watch.fetch_new_earnings_8ks("KO", db_conn, since=date(2026, 1, 1))
    assert len(result) == 1
    assert result[0]["accession_number"] == "acc-2"
    assert result[0]["items"] == "2.02,9.01"
    assert result[0]["new_this_run"] is True
    assert result[0]["summary"] == "Results summary."


def test_fetch_new_earnings_8ks_does_not_refetch_already_seen_accession(db_conn, monkeypatch):
    monkeypatch.setattr(earnings_watch, "fetch_new_earnings_8ks", _real_fetch_new_earnings_8ks)
    monkeypatch.setattr(earnings_watch.sec_filings, "get_cik", lambda conn, ticker: "21344")
    monkeypatch.setattr(
        earnings_watch.sec_filings, "fetch_filing_index",
        lambda cik: _columnar_8k_index([("acc-2", "2.02", "2026-09-02", "doc2.htm")]),
    )
    db.upsert_earnings_8k_seen(
        db_conn, ticker="KO", accession_number="acc-2", items="2.02",
        filing_date="2026-09-02", summary="Already summarized.",
    )

    def _raise(*a, **k):
        raise AssertionError("should not fetch document for an already-seen accession")

    monkeypatch.setattr(earnings_watch.sec_filings, "fetch_filing_document", _raise)
    result = earnings_watch.fetch_new_earnings_8ks("KO", db_conn, since=date(2026, 1, 1))
    assert len(result) == 1
    assert result[0]["new_this_run"] is False
    assert result[0]["summary"] == "Already summarized."


# --- fetch_industry_context -------------------------------------------------------


def test_fetch_industry_context_returns_none_without_data():
    assert earnings_watch.fetch_industry_context("NVDA", None) is None


def test_fetch_industry_context_returns_none_for_unmapped_industry(monkeypatch):
    from mytrader.market_data import TickerData

    data = TickerData(ticker="XYZ", info={"industry": "Some Unmapped Industry"}, dividends=None)
    assert earnings_watch.fetch_industry_context("XYZ", data) is None


def test_fetch_industry_context_matches_industry_etf(monkeypatch):
    import pandas as pd

    from mytrader.market_data import TickerData

    window = config.GOAT_INDUSTRY_RANK_WINDOW_TRADING_DAYS
    closes = pd.Series([float(i + 1) for i in range(window + 1)])
    monkeypatch.setattr(earnings_watch, "_fetch_close_history", lambda ticker, lookback_days: closes)

    data = TickerData(ticker="NVDA", info={"industry": "Semiconductors"}, dividends=None)
    result = earnings_watch.fetch_industry_context("NVDA", data)
    assert result is not None
    assert result["etf_ticker"] == "SMH"
    assert result["industry_label"] == "Semiconductors"
    assert result["rising"] is True


# --- render_earnings_watch_report -------------------------------------------------


def test_render_report_collapses_no_earnings_data_holding_to_one_line():
    result = {
        "checked_holdings": 1,
        "holdings_results": [{
            "ticker": "PMGOLD.AX", "name": "Perth Mint Gold", "bucket": "3a", "mlp": False,
            "trend": {"verdict": "unknown", "detail": "Insufficient history (0/5)"},
            "eight_ks": None,
            "guidance": {"verdict": "info", "detail": "No material news/event findings this run."},
            "industry_context": None,
        }],
        "new_alerts": [],
    }
    report = earnings_watch.render_earnings_watch_report(result)
    assert "No earnings data available (fund/commodity instrument)." in report
    assert "Estimate trend:" not in report


def test_render_report_shows_full_signal_detail_for_a_real_holding():
    result = {
        "checked_holdings": 1,
        "holdings_results": [{
            "ticker": "KO", "name": "Coca-Cola", "bucket": "1", "mlp": False,
            "trend": {"verdict": "flag", "detail": "EPS estimate down 5.0%"},
            "eight_ks": [{
                "form": "8-K", "accession_number": "acc-2", "items": "2.02", "filing_date": "2026-09-02",
                "summary": "Results summary.", "new_this_run": True,
            }],
            "guidance": {"verdict": "info", "detail": "No material news/event findings this run."},
            "industry_context": None,
        }],
        "new_alerts": [{"ticker": "KO", "source_table": "holdings", "check_name": "earnings_watch_trend",
                         "message": "EPS estimate down 5.0%"}],
    }
    report = earnings_watch.render_earnings_watch_report(result)
    assert "Estimate trend: EPS estimate down 5.0%" in report
    assert "NEW" in report
    assert "New Alerts This Run" in report
    assert "earnings_watch_trend" in report
