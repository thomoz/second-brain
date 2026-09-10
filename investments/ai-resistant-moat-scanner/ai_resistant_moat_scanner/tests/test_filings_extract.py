from __future__ import annotations

from mytrader import sec_filings

from ai_resistant_moat_scanner import filings_extract
from ai_resistant_moat_scanner.tests.conftest import FIXTURES


def _async_return(value):
    async def _fake(*a, **k):
        return value
    return _fake


def test_fetch_10k_sections_against_fixture(monkeypatch):
    html = (FIXTURES / "sec_10k_moat_sample.html").read_text(encoding="utf-8")
    monkeypatch.setattr(sec_filings, "fetch_filing_document", lambda cik, acc, doc: html)
    entry = {"cik": "21344", "accession_number": "acc", "primary_document": "doc.htm", "filing_date": "2026-02-20"}
    sections = filings_extract.fetch_10k_sections(entry)
    assert sections is not None
    assert sections.get("business")
    assert sections.get("risk_factors")


def test_fetch_10k_sections_none_on_fetch_failure(monkeypatch):
    monkeypatch.setattr(sec_filings, "fetch_filing_document", lambda cik, acc, doc: None)
    entry = {"cik": "1", "accession_number": "a", "primary_document": "d", "filing_date": "x"}
    assert filings_extract.fetch_10k_sections(entry) is None


def test_extract_disclosures_coerces_keys_and_keeps_nulls(monkeypatch):
    payload = (
        '```json\n{"recurring_revenue_pct": 92, "nrr_pct": 118.5, "rpo_usd": null, '
        '"rpo_yoy_pct": 12, "customer_count": "1500", "logo_churn_pct": null, '
        '"notes": "strong disclosure"}\n```'
    )
    monkeypatch.setattr(filings_extract, "run_text", _async_return(payload))
    result = filings_extract.extract_disclosures("CRM", {"business": "b", "mda": "m"})
    assert result["recurring_revenue_pct"] == 92.0
    assert result["nrr_pct"] == 118.5
    assert result["rpo_usd"] is None
    assert result["rpo_yoy_pct"] == 12.0
    assert result["customer_count"] == 1500
    assert result["logo_churn_pct"] is None
    assert result["notes"] == "strong disclosure"


def test_extract_disclosures_all_none_when_run_text_raises(monkeypatch):
    async def _boom(*a, **k):
        raise RuntimeError("llm down")

    monkeypatch.setattr(filings_extract, "run_text", _boom)
    result = filings_extract.extract_disclosures("CRM", {"business": "b"})
    assert result["nrr_pct"] is None
    assert result["notes"] == ""
    assert set(result) == set(filings_extract._EXTRACTION_KEYS)


def test_extract_disclosures_all_none_when_no_sections(monkeypatch):
    # run_text stays the conftest raiser -- must not be called.
    result = filings_extract.extract_disclosures("CRM", {})
    assert all(result[k] is None for k in filings_extract._EXTRACTION_KEYS if k != "notes")


def test_latest_10k_none_without_cik(db_conn):
    # conftest stubs sec_filings.get_cik -> None
    assert filings_extract.latest_10k(db_conn, "CRM") is None


def test_paced_filing_index_retries_once_on_none(monkeypatch):
    calls = {"n": 0}

    def _flaky(cik):
        calls["n"] += 1
        return None if calls["n"] == 1 else {"filings": {"recent": {}}}

    monkeypatch.setattr(sec_filings, "fetch_filing_index", _flaky)
    result = filings_extract._paced_filing_index("320193")
    assert calls["n"] == 2
    assert result == {"filings": {"recent": {}}}


def test_paced_filing_document_retries_once_then_gives_up(monkeypatch):
    calls = {"n": 0}

    def _always_none(cik, acc, doc):
        calls["n"] += 1
        return None

    monkeypatch.setattr(sec_filings, "fetch_filing_document", _always_none)
    assert filings_extract._paced_filing_document("1", "a", "d") is None
    assert calls["n"] == 2  # one initial + one retry, then stop
