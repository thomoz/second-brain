from __future__ import annotations

from mytrader.db import upsert_watchlist_row
from mytrader.market_data import TickerData

from ai_resistant_moat_scanner import config, db, quant, qualitative, scan, universe
from ai_resistant_moat_scanner.qualitative import _RUBRIC_KEYS

_SCREENED = [
    {"ticker": "CRM", "company": "Salesforce", "industry": "Software - Application", "sector": "Technology"},
    {"ticker": "LMT", "company": "Lockheed", "industry": "Software - Application", "sector": "Technology"},
    {"ticker": "HELD1", "company": "Held Co", "industry": "Software - Infrastructure", "sector": "Technology"},
    {"ticker": "NOQUAL", "company": "No Filing Co", "industry": "Consulting Services", "sector": "Technology"},
]


def _quant_dict(score):
    return {
        "quant_score": score,
        "sub_scores": {"gross_margin": 90.0},
        "worst_revenue_yoy": 3.0,
        "gross_margin": 0.8,
        "fcf_margin": 0.2,
        "market_cap": 5e9,
        "currency": "USD",
        "disclosure_bonus": 0.0,
    }


def _qual_dict(score):
    return {
        "qualitative_score": score,
        "sub_scores": {k: 9 for k in _RUBRIC_KEYS},
        "anti_signals": [],
        "thesis": "Embedded system of record.",
        "citations": {},
        "extraction": {"nrr_pct": 120},
        "accession_number": "acc-1",
        "filing_date": "2026-02-20",
    }


def _wire(monkeypatch, db_conn):
    monkeypatch.setattr(config, "MOAT_SEED_TICKERS", ("CRM",))
    monkeypatch.setattr(universe, "get_scan_universe", lambda conn: {
        "screened": _SCREENED,
        "seed": ["CRM"],
        "slice_today": [r["ticker"] for r in _SCREENED],
        "slice_index": 0,
        "finviz_failed": False,
    })
    monkeypatch.setattr(
        "mytrader.market_data.fetch_ticker_data",
        lambda t: TickerData(ticker=t, info={"shortName": t, "marketCap": 5e9}, dividends=None),
    )
    monkeypatch.setattr("mytrader.market_data.fetch_income_statement_history", lambda t: None)
    monkeypatch.setattr(quant, "compute_quant_metrics", lambda data, extraction, hist: _quant_dict(85.0))
    monkeypatch.setattr(
        qualitative, "get_qualitative",
        lambda conn, ticker: None if ticker == "NOQUAL" else _qual_dict(95.0),
    )


def test_scan_stages_high_scorer_and_reports_it(db_conn, monkeypatch):
    _wire(monkeypatch, db_conn)
    result = scan.run_scan(db_conn)

    staged = {r["ticker"] for r in db.get_all_moat_pending_candidates(db_conn)}
    assert "CRM" in staged
    assert "CRM" in {c["ticker"] for c in result["new_candidates"]}
    # blended 0.5*85 + 0.5*95 = 90
    crm_row = next(r for r in result["rows"] if r["ticker"] == "CRM")
    assert crm_row["moat_score"] == 90.0


def test_scan_excludes_defense_ticker_entirely(db_conn, monkeypatch):
    _wire(monkeypatch, db_conn)
    result = scan.run_scan(db_conn)
    assert "LMT" not in {r["ticker"] for r in result["rows"]}


def test_scan_scores_but_never_stages_a_held_ticker(db_conn, monkeypatch):
    _wire(monkeypatch, db_conn)
    from mytrader.db import upsert_holding

    upsert_holding(db_conn, ticker="HELD1", name="Held Co", asset_type="stock",
                   bucket="1", qty=10, avg_price=100.0)
    result = scan.run_scan(db_conn)

    assert "HELD1" in {r["ticker"] for r in result["rows"]}
    assert "HELD1" not in {r["ticker"] for r in db.get_all_moat_pending_candidates(db_conn)}


def test_scan_never_stages_a_watchlisted_ticker(db_conn, monkeypatch):
    _wire(monkeypatch, db_conn)
    upsert_watchlist_row(db_conn, ticker="CRM", name=None, asset_type="stock", bucket="unassigned")
    result = scan.run_scan(db_conn)
    assert "CRM" not in {r["ticker"] for r in db.get_all_moat_pending_candidates(db_conn)}
    assert "CRM" not in {c["ticker"] for c in result["new_candidates"]}


def test_scan_row_present_but_not_staged_when_qualitative_missing(db_conn, monkeypatch):
    _wire(monkeypatch, db_conn)
    result = scan.run_scan(db_conn)
    noqual = next(r for r in result["rows"] if r["ticker"] == "NOQUAL")
    assert noqual["moat_score"] is None
    assert "NOQUAL" not in {r["ticker"] for r in db.get_all_moat_pending_candidates(db_conn)}


def test_scan_is_idempotent_no_double_insert(db_conn, monkeypatch):
    _wire(monkeypatch, db_conn)
    first = scan.run_scan(db_conn)
    n_first = len(db.get_all_moat_pending_candidates(db_conn))
    second = scan.run_scan(db_conn)
    assert n_first >= 1
    assert len(db.get_all_moat_pending_candidates(db_conn)) == n_first  # no double-insert
    assert first["new_candidates"] and second["new_candidates"] == []  # already staged, not re-alerted
