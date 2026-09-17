from __future__ import annotations

import pandas as pd
from mytrader.market_data import TickerData

from goat import config, db as goat_db, hated_industries_scan as his


def _dates(n: int, start: str = "2020-01-01") -> pd.DatetimeIndex:
    return pd.date_range(start, periods=n, freq="D")


def _flat_series(n: int, price: float = 100.0) -> pd.Series:
    return pd.Series([price] * n, index=_dates(n))


def _series(prices: list[float]) -> pd.Series:
    return pd.Series(prices, index=_dates(len(prices)))


_MIN_LEN = config.GOAT_INDUSTRY_RANK_WINDOW_TRADING_DAYS + 252 + 20  # room for the drawdown lookup too


def _hated_close(drop_pct: float = 40.0, recent_bounce_pct: float = 0.0) -> pd.Series:
    """Flat at 100 for most of history, then a severe drop that holds (no
    reversal) unless recent_bounce_pct pushes the last few days back up."""
    n = _MIN_LEN
    prices = [100.0] * (n - config.GOAT_HATED_REVERSAL_LOOKBACK_DAYS - 1)
    dropped = 100.0 * (1 - drop_pct / 100.0)
    prices += [dropped] * (config.GOAT_HATED_REVERSAL_LOOKBACK_DAYS + 1)
    if recent_bounce_pct:
        bounced = dropped * (1 + recent_bounce_pct / 100.0)
        prices[-1] = bounced
    return _series(prices)


def _flat_spy() -> pd.Series:
    return _flat_series(_MIN_LEN, 100.0)


def _healthy_ticker_data(ticker: str = "AAPL") -> TickerData:
    return TickerData(
        ticker=ticker, info={"revenueGrowth": 0.10, "earningsGrowth": 0.05}, dividends=None,
    )


def _declining_ticker_data(ticker: str = "AAPL") -> TickerData:
    return TickerData(
        ticker=ticker, info={"revenueGrowth": -0.05, "earningsGrowth": -0.10}, dividends=None,
    )


# --- compute_industry_severity ---------------------------------------------

def test_compute_industry_severity_qualifies_on_severe_underperformance(monkeypatch):
    fake_etfs = {"IGV": "Software - Application", "SMH": "Semiconductors"}
    monkeypatch.setattr(config, "GOAT_INDUSTRY_ETFS", fake_etfs)
    closes = {"IGV": _hated_close(drop_pct=40.0), "SMH": _flat_series(_MIN_LEN)}
    rows = his.compute_industry_severity(closes, _flat_spy())
    igv = next(r for r in rows if r["ticker"] == "IGV")
    assert igv["qualifies"] is True
    assert igv["drawdown_from_high_pct"] < 0
    assert igv["underperformance_3mo"] < 0
    assert igv["underperformance_6mo"] < 0


def test_compute_industry_severity_bottom_5_but_not_severe_enough_does_not_qualify(monkeypatch):
    fake_etfs = {"IGV": "Software - Application", "SMH": "Semiconductors"}
    monkeypatch.setattr(config, "GOAT_INDUSTRY_ETFS", fake_etfs)
    # A mild underperformance -- below every threshold.
    closes = {"IGV": _hated_close(drop_pct=5.0), "SMH": _flat_series(_MIN_LEN)}
    rows = his.compute_industry_severity(closes, _flat_spy())
    igv = next(r for r in rows if r["ticker"] == "IGV")
    assert igv["qualifies"] is False


def test_compute_industry_severity_already_reversing_does_not_qualify(monkeypatch):
    fake_etfs = {"IGV": "Software - Application", "SMH": "Semiconductors"}
    monkeypatch.setattr(config, "GOAT_INDUSTRY_ETFS", fake_etfs)
    # Severe drop, but a sharp recent bounce disqualifies it as "already reversing".
    closes = {
        "IGV": _hated_close(drop_pct=40.0, recent_bounce_pct=20.0),
        "SMH": _flat_series(_MIN_LEN),
    }
    rows = his.compute_industry_severity(closes, _flat_spy())
    igv = next(r for r in rows if r["ticker"] == "IGV")
    assert igv["qualifies"] is False


def test_compute_industry_severity_insufficient_history_degrades_gracefully(monkeypatch):
    fake_etfs = {"IGV": "Software - Application", "SMH": "Semiconductors"}
    monkeypatch.setattr(config, "GOAT_INDUSTRY_ETFS", fake_etfs)
    closes = {"IGV": _series([100.0] * 10), "SMH": _flat_series(_MIN_LEN)}
    rows = his.compute_industry_severity(closes, _flat_spy())  # must not raise
    igv = next(r for r in rows if r["ticker"] == "IGV")
    assert igv["qualifies"] is False
    assert igv["return_pct_6mo"] is None


def test_compute_industry_severity_missing_close_degrades_gracefully(monkeypatch):
    fake_etfs = {"IGV": "Software - Application", "SMH": "Semiconductors"}
    monkeypatch.setattr(config, "GOAT_INDUSTRY_ETFS", fake_etfs)
    rows = his.compute_industry_severity({"IGV": None, "SMH": None}, None)  # must not raise
    assert all(r["qualifies"] is False for r in rows)


# --- classify_industry_narrative --------------------------------------------

def test_classify_industry_narrative_uses_cache_when_fresh(db_conn, monkeypatch):
    goat_db.upsert_hated_narrative_cache(
        db_conn, industry_label="Software - Application", ticker="IGV",
        narrative_thesis="AI fear.", systemic=True, reasoning="Broad.",
        top_holdings=[{"ticker": "CRM", "name": "Salesforce"}],
    )

    def _raise(industry_label, ticker):
        raise AssertionError("should not search when cache is fresh")

    monkeypatch.setattr(his, "_search_industry_narrative", _raise)
    result = his.classify_industry_narrative("Software - Application", "IGV", db_conn)
    assert result["narrative_thesis"] == "AI fear."
    assert result["systemic"] is True
    assert result["top_holdings"] == [{"ticker": "CRM", "name": "Salesforce"}]


def test_classify_industry_narrative_refetches_when_cache_stale(db_conn, monkeypatch):
    from datetime import datetime, timedelta, timezone
    with db_conn:
        db_conn.execute(
            """INSERT INTO goat_hated_industries_narrative_cache
               (industry_label, ticker, narrative_thesis, systemic, reasoning, top_holdings_json, fetched_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                "Software - Application", "IGV", "Old.", 0, "Old reasoning.", "[]",
                (datetime.now(timezone.utc) - timedelta(hours=999)).isoformat(),
            ),
        )
    monkeypatch.setattr(
        his, "_search_industry_narrative",
        lambda industry_label, ticker: {
            "narrative_thesis": "New AI fear.", "systemic": False, "reasoning": "Concentrated.",
            "top_holdings": [{"ticker": "CRM", "name": "Salesforce"}],
        },
    )
    result = his.classify_industry_narrative("Software - Application", "IGV", db_conn)
    assert result["narrative_thesis"] == "New AI fear."
    assert result["systemic"] is False
    cached = goat_db.get_cached_hated_narrative(db_conn, "Software - Application")
    assert cached["narrative_thesis"] == "New AI fear."


def test_classify_industry_narrative_falls_back_to_stale_cache_on_search_failure(db_conn, monkeypatch):
    from datetime import datetime, timedelta, timezone
    with db_conn:
        db_conn.execute(
            """INSERT INTO goat_hated_industries_narrative_cache
               (industry_label, ticker, narrative_thesis, systemic, reasoning, top_holdings_json, fetched_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                "Software - Application", "IGV", "Stale but usable.", None, "Unclear.", "[]",
                (datetime.now(timezone.utc) - timedelta(hours=999)).isoformat(),
            ),
        )
    monkeypatch.setattr(his, "_search_industry_narrative", lambda industry_label, ticker: None)
    result = his.classify_industry_narrative("Software - Application", "IGV", db_conn)
    assert result["narrative_thesis"] == "Stale but usable."
    assert result["systemic"] is None


def test_classify_industry_narrative_returns_none_when_search_fails_and_no_cache(db_conn, monkeypatch):
    monkeypatch.setattr(his, "_search_industry_narrative", lambda industry_label, ticker: None)
    assert his.classify_industry_narrative("Software - Application", "IGV", db_conn) is None


# --- check_fundamentals_divergence ------------------------------------------

def test_check_fundamentals_divergence_all_growing(monkeypatch):
    monkeypatch.setattr(his.market_data, "fetch_ticker_data", lambda t: _healthy_ticker_data(t))
    holdings = [{"ticker": "CRM", "name": "Salesforce"}, {"ticker": "NOW", "name": "ServiceNow"}]
    result = his.check_fundamentals_divergence(holdings)
    assert result["verdict"] == "fundamentals_still_growing"
    assert result["resolved_count"] == 2


def test_check_fundamentals_divergence_all_declining(monkeypatch):
    monkeypatch.setattr(his.market_data, "fetch_ticker_data", lambda t: _declining_ticker_data(t))
    holdings = [{"ticker": "CRM", "name": "Salesforce"}, {"ticker": "NOW", "name": "ServiceNow"}]
    result = his.check_fundamentals_divergence(holdings)
    assert result["verdict"] == "fundamentals_also_declining"


def test_check_fundamentals_divergence_mixed(monkeypatch):
    def _fetch(t):
        return _healthy_ticker_data(t) if t == "CRM" else _declining_ticker_data(t)

    monkeypatch.setattr(his.market_data, "fetch_ticker_data", _fetch)
    holdings = [{"ticker": "CRM", "name": "Salesforce"}, {"ticker": "NOW", "name": "ServiceNow"}]
    result = his.check_fundamentals_divergence(holdings)
    assert result["verdict"] == "mixed"


def test_check_fundamentals_divergence_insufficient_data_below_min_sample(monkeypatch):
    monkeypatch.setattr(his.market_data, "fetch_ticker_data", lambda t: _healthy_ticker_data(t))
    holdings = [{"ticker": "CRM", "name": "Salesforce"}]  # 1 < GOAT_HATED_MIN_CONSTITUENT_FUNDAMENTALS_SAMPLE
    result = his.check_fundamentals_divergence(holdings)
    assert result["verdict"] == "insufficient_data"


def test_check_fundamentals_divergence_drops_ethically_excluded_holding(monkeypatch):
    monkeypatch.setattr(his.market_data, "fetch_ticker_data", lambda t: _healthy_ticker_data(t))
    monkeypatch.setattr(his, "ethical_check", lambda t: (True, "Primary defense/military contractor"))
    holdings = [{"ticker": "LMT", "name": "Lockheed Martin"}]
    result = his.check_fundamentals_divergence(holdings)
    assert result["per_ticker"] == []
    assert result["excluded"] == [{"ticker": "LMT", "review_reason": "Primary defense/military contractor"}]


def test_check_fundamentals_divergence_unresolvable_ticker_is_skipped(monkeypatch):
    monkeypatch.setattr(his.market_data, "fetch_ticker_data", lambda t: None)
    holdings = [{"ticker": "ZZZZ", "name": "Delisted"}]
    result = his.check_fundamentals_divergence(holdings)  # must not raise
    assert result["resolved_count"] == 0
    assert result["verdict"] == "insufficient_data"


# --- run_hated_industries_scan seen-table / dedup ---------------------------

def _patch_scan(monkeypatch, *, qualifying_etfs: dict[str, str]):
    fake_etfs = {"IGV": "Software - Application", "SMH": "Semiconductors"}
    monkeypatch.setattr(config, "GOAT_INDUSTRY_ETFS", fake_etfs)

    def _fake_severity(closes, spy_close):
        rows = []
        for etf_ticker, industry_label in fake_etfs.items():
            rows.append({
                "ticker": etf_ticker, "industry_label": industry_label,
                "return_pct_3mo": -30.0, "return_pct_6mo": -40.0,
                "underperformance_3mo": -30.0, "underperformance_6mo": -40.0,
                "drawdown_from_high_pct": -40.0, "recent_return_pct": 0.0,
                "qualifies": industry_label in qualifying_etfs.values(),
            })
        return rows

    monkeypatch.setattr(his, "compute_industry_severity", _fake_severity)
    monkeypatch.setattr(his.industry_rotation, "fetch_all_industry_closes", lambda: {})
    monkeypatch.setattr(his, "fetch_spy_close", lambda: None)
    monkeypatch.setattr(
        his, "classify_industry_narrative",
        lambda industry_label, ticker, conn: {
            "narrative_thesis": "Test narrative.", "systemic": True,
            "reasoning": "Test.", "top_holdings": [],
        },
    )
    monkeypatch.setattr(
        his, "check_fundamentals_divergence",
        lambda top_holdings: {"verdict": "insufficient_data", "per_ticker": [], "resolved_count": 0, "excluded": []},
    )


def test_run_hated_industries_scan_first_run_produces_new_candidate(db_conn, monkeypatch):
    _patch_scan(monkeypatch, qualifying_etfs={"IGV": "Software - Application"})
    result = his.run_hated_industries_scan(db_conn)
    assert len(result["new_candidates"]) == 1
    assert result["new_candidates"][0]["ticker"] == "IGV"
    assert len(result["flagged"]) == 1


def test_run_hated_industries_scan_second_run_same_industry_no_new_candidate(db_conn, monkeypatch):
    _patch_scan(monkeypatch, qualifying_etfs={"IGV": "Software - Application"})
    his.run_hated_industries_scan(db_conn)
    result = his.run_hated_industries_scan(db_conn)
    assert result["new_candidates"] == []
    assert len(result["flagged"]) == 1


def test_run_hated_industries_scan_dropout_then_requalify_reflags(db_conn, monkeypatch):
    _patch_scan(monkeypatch, qualifying_etfs={"IGV": "Software - Application"})
    his.run_hated_industries_scan(db_conn)  # run 1: flags IGV

    _patch_scan(monkeypatch, qualifying_etfs={})
    result_dropped = his.run_hated_industries_scan(db_conn)  # run 2: IGV drops out
    assert result_dropped["new_candidates"] == []
    assert goat_db.get_hated_industry_seen(db_conn, "Software - Application") is None

    _patch_scan(monkeypatch, qualifying_etfs={"IGV": "Software - Application"})
    result_requalified = his.run_hated_industries_scan(db_conn)  # run 3: re-qualifies
    assert len(result_requalified["new_candidates"]) == 1
    assert result_requalified["new_candidates"][0]["ticker"] == "IGV"


def test_run_hated_industries_scan_zero_qualifying_is_quiet(db_conn, monkeypatch):
    _patch_scan(monkeypatch, qualifying_etfs={})
    result = his.run_hated_industries_scan(db_conn)
    assert result["flagged"] == []
    assert result["new_candidates"] == []


# --- render_hated_industries_report -----------------------------------------

def test_render_hated_industries_report_empty_flagged_shows_clean_message():
    report = his.render_hated_industries_report({"severity": [], "flagged": [], "new_candidates": []})
    assert "No industry cleared the severity gate today." in report


def test_render_hated_industries_report_renders_flagged_industry():
    result = {
        "severity": [],
        "flagged": [{
            "ticker": "IGV", "industry_label": "Software - Application",
            "return_pct_3mo": -25.0, "return_pct_6mo": -35.0,
            "underperformance_3mo": -20.0, "underperformance_6mo": -25.0,
            "drawdown_from_high_pct": -30.0, "recent_return_pct": 1.0,
            "first_flagged_at": "2026-09-16T00:00:00+00:00",
            "narrative": {
                "narrative_thesis": "AI disruption fear.", "systemic": True,
                "reasoning": "Broad-based repricing.", "top_holdings": [{"ticker": "CRM", "name": "Salesforce"}],
            },
            "fundamentals": {
                "verdict": "fundamentals_still_growing",
                "per_ticker": [
                    {"ticker": "CRM", "name": "Salesforce", "revenue_growth": 0.1,
                     "earnings_growth": 0.05, "classification": "growing"},
                ],
                "resolved_count": 1, "excluded": [],
            },
        }],
        "new_candidates": [],
    }
    report = his.render_hated_industries_report(result)
    assert "Software - Application" in report
    assert "AI disruption fear." in report
    assert "industry-wide" in report
    assert "fundamentals still growing" in report
    assert "read-only" in report
    assert "CRM" in report


def test_render_hated_industries_report_null_systemic_reads_as_unclear():
    result = {
        "severity": [],
        "flagged": [{
            "ticker": "IGV", "industry_label": "Software - Application",
            "return_pct_3mo": -25.0, "return_pct_6mo": -35.0,
            "underperformance_3mo": -20.0, "underperformance_6mo": -25.0,
            "drawdown_from_high_pct": -30.0, "recent_return_pct": 1.0,
            "first_flagged_at": "2026-09-16T00:00:00+00:00",
            "narrative": {
                "narrative_thesis": "Unclear cause.", "systemic": None,
                "reasoning": "Thin evidence.", "top_holdings": [],
            },
            "fundamentals": {"verdict": "insufficient_data", "per_ticker": [], "resolved_count": 0, "excluded": []},
        }],
        "new_candidates": [],
    }
    report = his.render_hated_industries_report(result)
    assert "unclear whether industry-wide or concentrated" in report
