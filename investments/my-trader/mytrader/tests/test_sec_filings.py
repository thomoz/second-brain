from __future__ import annotations

import pathlib

from mytrader import db, sec_filings

_FIXTURES = pathlib.Path(__file__).parent / "fixtures"

# conftest.py's autouse _no_real_sec_filing_fetch fixture patches
# sec_filings.get_filing_summaries_for_ticker to a None-returning stub (module-global,
# since mytrader.checks.principles_fit.sec_filings IS mytrader.sec_filings -- same
# module object). Save the real function here, at import time before any fixture
# runs, so the tests below that exercise the real orchestrator can restore it.
_real_get_filing_summaries_for_ticker = sec_filings.get_filing_summaries_for_ticker


def test_get_cik_returns_none_when_ticker_not_in_map(db_conn, monkeypatch):
    monkeypatch.setattr(sec_filings, "_fetch_cik_map_bulk", lambda: {"KO": "21344"})
    assert sec_filings.get_cik(db_conn, "BXB") is None


def test_refresh_cik_map_skips_when_fresh(db_conn, monkeypatch):
    from datetime import datetime, timezone

    db.set_sync_watermark(db_conn, "sec_cik_map_refreshed_at", datetime.now(timezone.utc).isoformat())

    def _raise():
        raise AssertionError("should not fetch when watermark is fresh")

    monkeypatch.setattr(sec_filings, "_fetch_cik_map_bulk", _raise)
    sec_filings._refresh_cik_map_if_stale(db_conn)  # should not raise


def test_refresh_cik_map_fetches_when_stale_or_missing(db_conn, monkeypatch):
    monkeypatch.setattr(sec_filings, "_fetch_cik_map_bulk", lambda: {"KO": "21344"})
    sec_filings.get_cik(db_conn, "KO")
    assert db.get_cik_for_ticker(db_conn, "KO") == "21344"
    assert db.get_sync_watermark(db_conn, "sec_cik_map_refreshed_at") is not None


def test_split_by_item_10k():
    text = (
        "Item 1. Business text here.\n"
        "Item 1A. Risk Factors text here.\n"
        "Item 7. MD&A text here.\n"
    )
    items = sec_filings._split_by_item(text)
    assert items["1"].lstrip().startswith("Item 1. Business")
    assert items["1A"].lstrip().startswith("Item 1A. Risk Factors")
    assert items["7"].lstrip().startswith("Item 7. MD&A")


def test_split_by_part_and_item_10q_disambiguates_part_i_and_ii():
    text = (
        "PART I FINANCIAL INFORMATION\n"
        "Item 2. MD&A real text here.\n"
        "PART II OTHER INFORMATION\n"
        "Item 1A. Risk Factors real text here.\n"
    )
    sections = sec_filings._extract_10q_sections(text)
    assert "MD&A real text" in sections["mda"]
    assert "Risk Factors real text" in sections["risk_factors"]
    assert "MD&A" not in sections["risk_factors"]


def test_extract_10k_sections_against_real_fixture():
    html = (_FIXTURES / "sec_10k_sample.html").read_text(encoding="utf-8")
    sections = sec_filings._extract_sections(html, "10-K")
    assert sections.get("business")
    assert sections.get("risk_factors")
    assert sections.get("mda")
    assert sections.get("financial_statements")


def test_extract_10q_sections_against_real_fixture():
    html = (_FIXTURES / "sec_10q_sample.html").read_text(encoding="utf-8")
    sections = sec_filings._extract_sections(html, "10-Q")
    assert sections.get("mda")
    assert sections.get("risk_factors")
    assert sections.get("financial_statements")


def test_extract_def14a_sections_against_real_fixture():
    html = (_FIXTURES / "sec_def14a_sample.html").read_text(encoding="utf-8")
    sections = sec_filings._extract_sections(html, "DEF 14A")
    assert any(sections.values())


def test_summarize_sections_returns_none_on_empty_input():
    assert sec_filings._summarize_sections("KO", "10-K", {}) is None
    assert sec_filings._summarize_sections("KO", "10-K", {"business": "   "}) is None


def test_get_filing_summaries_returns_none_for_unmapped_ticker(db_conn, monkeypatch):
    monkeypatch.setattr(sec_filings, "get_cik", lambda conn, ticker: None)
    monkeypatch.setattr(sec_filings, "get_filing_summaries_for_ticker", _real_get_filing_summaries_for_ticker)
    assert sec_filings.get_filing_summaries_for_ticker("BXB", db_conn) is None


def test_get_filing_summaries_uses_cache_when_accession_unchanged(db_conn, monkeypatch):
    monkeypatch.setattr(sec_filings, "get_cik", lambda conn, ticker: "21344")
    monkeypatch.setattr(
        sec_filings, "fetch_filing_index",
        lambda cik: {"filings": {"recent": {
            "form": ["10-K"], "accessionNumber": ["ACC-1"], "primaryDocument": ["doc.htm"],
            "filingDate": ["2026-02-20"],
        }}},
    )
    db.upsert_filing_summary_cache(
        db_conn, ticker="KO", filing_type="10-K", accession_number="ACC-1", summary="Cached summary.",
    )

    def _raise(*a, **k):
        raise AssertionError("should not fetch document when cache is fresh")

    monkeypatch.setattr(sec_filings, "fetch_filing_document", _raise)

    monkeypatch.setattr(sec_filings, "get_filing_summaries_for_ticker", _real_get_filing_summaries_for_ticker)
    result = sec_filings.get_filing_summaries_for_ticker("KO", db_conn)
    assert result == {"10-K": "Cached summary."}


def test_get_filing_summaries_refetches_on_new_accession(db_conn, monkeypatch):
    monkeypatch.setattr(sec_filings, "get_cik", lambda conn, ticker: "21344")
    monkeypatch.setattr(
        sec_filings, "fetch_filing_index",
        lambda cik: {"filings": {"recent": {
            "form": ["10-K"], "accessionNumber": ["ACC-2"], "primaryDocument": ["doc.htm"],
            "filingDate": ["2026-02-20"],
        }}},
    )
    db.upsert_filing_summary_cache(
        db_conn, ticker="KO", filing_type="10-K", accession_number="ACC-1", summary="Old summary.",
    )
    monkeypatch.setattr(sec_filings, "fetch_filing_document", lambda cik, acc, doc: "<html>real</html>")
    monkeypatch.setattr(sec_filings, "_extract_sections", lambda html, ft: {"business": "New content."})
    monkeypatch.setattr(sec_filings, "_summarize_sections", lambda ticker, ft, sections: "New summary.")

    monkeypatch.setattr(sec_filings, "get_filing_summaries_for_ticker", _real_get_filing_summaries_for_ticker)
    result = sec_filings.get_filing_summaries_for_ticker("KO", db_conn)
    assert result == {"10-K": "New summary."}
    cached = db.get_cached_filing_summary(db_conn, "KO", "10-K")
    assert cached["accession_number"] == "ACC-2"
    assert cached["summary"] == "New summary."


def test_get_filing_summaries_falls_back_to_stale_cache_on_fetch_failure(db_conn, monkeypatch):
    monkeypatch.setattr(sec_filings, "get_cik", lambda conn, ticker: "21344")
    monkeypatch.setattr(
        sec_filings, "fetch_filing_index",
        lambda cik: {"filings": {"recent": {
            "form": ["10-K"], "accessionNumber": ["ACC-2"], "primaryDocument": ["doc.htm"],
            "filingDate": ["2026-02-20"],
        }}},
    )
    db.upsert_filing_summary_cache(
        db_conn, ticker="KO", filing_type="10-K", accession_number="ACC-1", summary="Stale summary.",
    )
    monkeypatch.setattr(sec_filings, "fetch_filing_document", lambda cik, acc, doc: None)

    monkeypatch.setattr(sec_filings, "get_filing_summaries_for_ticker", _real_get_filing_summaries_for_ticker)
    result = sec_filings.get_filing_summaries_for_ticker("KO", db_conn)
    assert result == {"10-K": "Stale summary."}


class _FakeSearchResponse:
    def __init__(self, status_code: int, payload: dict | None = None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload


def test_edgar_fulltext_search_count_returns_total_value(monkeypatch):
    def _fake_get(url, params=None, headers=None, timeout=None):
        assert "q" not in params  # GOTCHA regression -- q must never be sent
        assert params["ciks"] == "0001341439"  # zero-padded from raw "1341439"
        return _FakeSearchResponse(200, {"hits": {"total": {"value": 42, "relation": "eq"}}})

    monkeypatch.setattr(sec_filings.requests, "get", _fake_get)
    count = sec_filings.edgar_fulltext_search_count("424B2,424B5,FWP", cik="1341439")
    assert count == 42


def test_edgar_fulltext_search_count_none_on_non_200(monkeypatch):
    monkeypatch.setattr(sec_filings.requests, "get", lambda *a, **k: _FakeSearchResponse(500))
    assert sec_filings.edgar_fulltext_search_count("S-1") is None


def test_edgar_fulltext_search_count_none_on_exception(monkeypatch):
    def _raise(*a, **k):
        raise ConnectionError("boom")

    monkeypatch.setattr(sec_filings.requests, "get", _raise)
    assert sec_filings.edgar_fulltext_search_count("S-1") is None


def test_edgar_fulltext_search_count_no_cik_param_when_omitted(monkeypatch):
    def _fake_get(url, params=None, headers=None, timeout=None):
        assert "ciks" not in params  # market-wide query, Marker #6's shape
        return _FakeSearchResponse(200, {"hits": {"total": {"value": 85, "relation": "eq"}}})

    monkeypatch.setattr(sec_filings.requests, "get", _fake_get)
    assert sec_filings.edgar_fulltext_search_count("S-1") == 85
