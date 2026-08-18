from __future__ import annotations

from datetime import date, timedelta

from fourteen_crash_signals_daily_check import config, credit_spread_issuer, db


def _index(entries: dict[str, list[tuple[str, str, str]]]) -> dict:
    """entries: {form_type: [(accession, primary_doc, filing_date), ...]}"""
    forms, accs, docs, dates = [], [], [], []
    for form_type, rows in entries.items():
        for accession, primary_doc, filing_date in rows:
            forms.append(form_type)
            accs.append(accession)
            docs.append(primary_doc)
            dates.append(filing_date)
    return {"filings": {"recent": {
        "form": forms, "accessionNumber": accs, "primaryDocument": docs, "filingDate": dates,
    }}}


def test_cusip_resolved_and_cached_from_fake_424b2_cover_page(db_conn, monkeypatch):
    monkeypatch.setattr(credit_spread_issuer.sec_filings, "get_cik", lambda conn, ticker: "21344")
    monkeypatch.setattr(
        credit_spread_issuer.sec_filings, "fetch_filing_index",
        lambda cik: _index({"424B2": [("ACC-1", "doc.htm", "2026-02-03")]}),
    )
    monkeypatch.setattr(
        credit_spread_issuer.sec_filings, "fetch_filing_document",
        lambda cik, acc, doc: "CUSIP / ISIN Numbers:\n68389XDV4 / US68389XDV47",
    )
    cusip = credit_spread_issuer._resolve_cusip(db_conn, "ORCL")
    assert cusip == "68389XDV4"
    cached = db.get_bond_cusip(db_conn, "ORCL")
    assert cached["cusip"] == "68389XDV4"


def test_cached_cusip_reused_without_refetching(db_conn, monkeypatch):
    db.upsert_bond_cusip(db_conn, ticker="ORCL", cusip="68389XDV4", accession_number="ACC-1")

    def _raise(*a, **k):
        raise AssertionError("should not fetch when CUSIP is already cached")

    monkeypatch.setattr(credit_spread_issuer.sec_filings, "get_cik", _raise)
    monkeypatch.setattr(credit_spread_issuer.sec_filings, "fetch_filing_index", _raise)
    monkeypatch.setattr(credit_spread_issuer.sec_filings, "fetch_filing_document", _raise)

    cusip = credit_spread_issuer._resolve_cusip(db_conn, "ORCL")
    assert cusip == "68389XDV4"


def test_no_cusip_found_when_no_matching_form_types(db_conn, monkeypatch):
    monkeypatch.setattr(credit_spread_issuer.sec_filings, "get_cik", lambda conn, ticker: "1234")
    monkeypatch.setattr(
        credit_spread_issuer.sec_filings, "fetch_filing_index",
        lambda cik: _index({"10-K": [("ACC-1", "doc.htm", "2026-02-03")]}),
    )
    cusip = credit_spread_issuer._resolve_cusip(db_conn, "CRWV")
    assert cusip is None


def test_falls_through_to_older_candidate_when_newest_has_no_cusip(db_conn, monkeypatch):
    """Regression for the real ORCL case found live 2026-08-18: the newest 424B2 only
    cross-references CUSIP in prose, but an FWP filed one day earlier has the real table."""
    monkeypatch.setattr(credit_spread_issuer.sec_filings, "get_cik", lambda conn, ticker: "21344")
    monkeypatch.setattr(
        credit_spread_issuer.sec_filings, "fetch_filing_index",
        lambda cik: _index({
            "424B2": [("ACC-NEW", "new.htm", "2026-02-03")],
            "FWP": [("ACC-OLD", "old.htm", "2026-02-02")],
        }),
    )

    def _fetch_doc(cik, acc, doc):
        if acc == "ACC-NEW":
            return "See CUSIP number as the applicable series of Notes."
        return "CUSIP / ISIN Numbers:\n68389XDV4 / US68389XDV47"

    monkeypatch.setattr(credit_spread_issuer.sec_filings, "fetch_filing_document", _fetch_doc)
    cusip = credit_spread_issuer._resolve_cusip(db_conn, "ORCL")
    assert cusip == "68389XDV4"


def test_unknown_verdict_with_record_bond_yield_hint_when_no_yield_available(db_conn, monkeypatch):
    monkeypatch.setattr(credit_spread_issuer, "_resolve_cusip", lambda conn, ticker: "68389XDV4")
    monkeypatch.setattr(credit_spread_issuer, "_fetch_bond_yield_live", lambda cusip: None)
    result = credit_spread_issuer._check_one_ticker(db_conn, "ORCL")
    assert result.verdict == "unknown"
    assert "record-bond-yield" in result.detail


def test_manual_yield_used_when_live_fetch_returns_none(db_conn, monkeypatch):
    db.set_manual_bond_yield(db_conn, ticker="ORCL", cusip="68389XDV4", yield_pct=5.75)
    monkeypatch.setattr(credit_spread_issuer, "_resolve_cusip", lambda conn, ticker: "68389XDV4")
    monkeypatch.setattr(credit_spread_issuer, "_fetch_bond_yield_live", lambda cusip: None)
    monkeypatch.setattr(credit_spread_issuer, "fred_value_on", lambda series_id, target: 4.25)
    result = credit_spread_issuer._check_one_ticker(db_conn, "ORCL")
    assert result.data["spread"] == 5.75 - 4.25
    assert result.verdict == "ok"


def test_ok_baseline_on_first_ever_spread_observation(db_conn, monkeypatch):
    monkeypatch.setattr(credit_spread_issuer, "_resolve_cusip", lambda conn, ticker: "68389XDV4")
    monkeypatch.setattr(credit_spread_issuer, "_fetch_bond_yield_live", lambda cusip: 5.75)
    monkeypatch.setattr(credit_spread_issuer, "fred_value_on", lambda series_id, target: 4.25)
    result = credit_spread_issuer._check_one_ticker(db_conn, "ORCL")
    assert result.verdict == "ok"
    assert "baseline" in result.detail


def test_flags_when_spread_at_or_above_divergence_ratio(db_conn, monkeypatch):
    ninety_days_ago = (date.today() - timedelta(days=config.SIGNALS_ISSUER_SPREAD_LOOKBACK_DAYS)).isoformat()
    db_conn.execute(
        "INSERT INTO signals_issuer_spread_history (ticker, spread_value, observed_at) VALUES (?, ?, ?)",
        ("ORCL", 1.0, ninety_days_ago),
    )
    db_conn.commit()
    monkeypatch.setattr(credit_spread_issuer, "_resolve_cusip", lambda conn, ticker: "68389XDV4")
    monkeypatch.setattr(credit_spread_issuer, "_fetch_bond_yield_live", lambda cusip: 5.6)
    monkeypatch.setattr(credit_spread_issuer, "fred_value_on", lambda series_id, target: 4.2)  # spread 1.4, ratio 1.4x
    result = credit_spread_issuer._check_one_ticker(db_conn, "ORCL")
    assert result.verdict == "flag"


def test_ok_when_ratio_below_divergence_threshold(db_conn, monkeypatch):
    ninety_days_ago = (date.today() - timedelta(days=config.SIGNALS_ISSUER_SPREAD_LOOKBACK_DAYS)).isoformat()
    db_conn.execute(
        "INSERT INTO signals_issuer_spread_history (ticker, spread_value, observed_at) VALUES (?, ?, ?)",
        ("ORCL", 1.0, ninety_days_ago),
    )
    db_conn.commit()
    monkeypatch.setattr(credit_spread_issuer, "_resolve_cusip", lambda conn, ticker: "68389XDV4")
    monkeypatch.setattr(credit_spread_issuer, "_fetch_bond_yield_live", lambda cusip: 5.1)
    monkeypatch.setattr(credit_spread_issuer, "fred_value_on", lambda series_id, target: 4.2)  # spread 0.9
    result = credit_spread_issuer._check_one_ticker(db_conn, "ORCL")
    assert result.verdict == "ok"


def test_unknown_when_treasury_yield_unavailable(db_conn, monkeypatch):
    monkeypatch.setattr(credit_spread_issuer, "_resolve_cusip", lambda conn, ticker: "68389XDV4")
    monkeypatch.setattr(credit_spread_issuer, "_fetch_bond_yield_live", lambda cusip: 5.75)
    monkeypatch.setattr(credit_spread_issuer, "fred_value_on", lambda series_id, target: None)
    result = credit_spread_issuer._check_one_ticker(db_conn, "ORCL")
    assert result.verdict == "unknown"
