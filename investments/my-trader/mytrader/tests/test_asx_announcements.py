from __future__ import annotations

import pathlib

from mytrader import asx_announcements, config, db

_FIXTURES = pathlib.Path(__file__).parent / "fixtures"

# conftest.py's autouse _no_real_asx_announcement_fetch fixture patches
# asx_announcements.get_announcement_summaries_for_ticker to a None-returning stub
# (module-global, since mytrader.checks.principles_fit.asx_announcements IS
# mytrader.asx_announcements -- same module object). Save the real function here, at
# import time before any fixture runs, so the tests below that exercise the real
# orchestrator can restore it.
_real_get_announcement_summaries_for_ticker = asx_announcements.get_announcement_summaries_for_ticker


def test_is_asx_ticker_true_for_dot_ax_suffix():
    assert asx_announcements._is_asx_ticker("BXB.AX") is True
    assert asx_announcements._is_asx_ticker("bxb.ax") is True


def test_is_asx_ticker_false_for_us_ticker():
    assert asx_announcements._is_asx_ticker("KO") is False


def test_bare_asx_code_strips_suffix():
    assert asx_announcements._bare_asx_code("BXB.AX") == "BXB"


def test_get_announcement_summaries_returns_none_immediately_for_non_asx_ticker(db_conn, monkeypatch):
    def _raise(*a, **k):
        raise AssertionError("should not fetch for a non-ASX ticker")

    monkeypatch.setattr(asx_announcements, "_fetch_announcements_list", _raise)
    monkeypatch.setattr(
        asx_announcements, "get_announcement_summaries_for_ticker",
        _real_get_announcement_summaries_for_ticker,
    )
    assert asx_announcements.get_announcement_summaries_for_ticker("KO", db_conn) is None


def test_parse_announcements_html_against_real_fixture():
    html = (_FIXTURES / "asx_announcements_list_WES.html").read_text(encoding="utf-8")
    rows = asx_announcements._parse_announcements_html(html)
    assert len(rows) > 0
    assert all(row["title"] and row["ids_id"] for row in rows)


def test_select_target_announcements_finds_annual_and_half_year_against_real_fixture():
    html = (_FIXTURES / "asx_announcements_list_WES.html").read_text(encoding="utf-8")
    rows = asx_announcements._parse_announcements_html(html)
    selected = asx_announcements._select_target_announcements(rows, config.ASX_ANNOUNCEMENT_TYPES)
    assert "Annual Report" in selected
    assert "annual report" in selected["Annual Report"]["title"].lower()
    assert "Half-Year Report" in selected
    assert selected["Half-Year Report"]["ids_id"]


def test_resolve_pdf_url_against_real_fixture(monkeypatch):
    html = (_FIXTURES / "asx_interstitial_WES.html").read_text(encoding="utf-8")

    class _Resp:
        status_code = 200
        text = html

    monkeypatch.setattr(asx_announcements.requests, "get", lambda *a, **k: _Resp())
    url = asx_announcements._resolve_pdf_url("02986758")
    assert url == "https://announcements.asx.com.au/asxpdf/20250828/pdf/06ng4fzmsdcdcb.pdf"


def test_extract_sections_against_real_bxb_half_year_fixture():
    text = (_FIXTURES / "asx_half_year_report_BXB.txt").read_text(encoding="utf-8")
    sections = asx_announcements._extract_sections(text)
    assert sections.get("review_of_operations")
    assert "review of operations" in sections["review_of_operations"].lower()


def test_extract_sections_against_real_wes_annual_fixture():
    text = (_FIXTURES / "asx_annual_report_WES.txt").read_text(encoding="utf-8")
    sections = asx_announcements._extract_sections(text)
    assert sections.get("operating_and_financial_review")
    assert "operating and financial review" in sections["operating_and_financial_review"].lower()


def test_find_heading_index_skips_isolated_toc_occurrence():
    # A lone early mention far ahead of a dense repeating cluster should be treated
    # as a TOC line, not the real section start -- see the module docstring for the
    # real WES evidence this heuristic was built against.
    text = "See Risk Management on page 5.\n" + ("x" * 6000) + "Risk Management\nReal content here."
    idx = asx_announcements._find_heading_index(text.lower(), "risk management")
    assert text[idx:].startswith("Risk Management\nReal content here.")


def test_find_heading_index_uses_first_occurrence_when_only_one():
    text = "intro text\nReview of Operations\nreal content"
    idx = asx_announcements._find_heading_index(text.lower(), "review of operations")
    assert text[idx:].startswith("Review of Operations\nreal content")


def test_summarize_sections_returns_none_on_empty_input():
    assert asx_announcements._summarize_sections("BXB.AX", "Half-Year Report", {}) is None
    assert asx_announcements._summarize_sections("BXB.AX", "Half-Year Report", {"review_of_operations": "   "}) is None


def test_get_announcement_summaries_uses_cache_when_announcement_id_unchanged(db_conn, monkeypatch):
    monkeypatch.setattr(
        asx_announcements, "_fetch_announcements_list",
        lambda code, year: [{"title": "2026 Half Year Accounts", "ids_id": "IDS-1"}],
    )
    db.upsert_asx_summary_cache(
        db_conn, ticker="BXB.AX", announcement_type="Half-Year Report",
        announcement_id="IDS-1", summary="Cached summary.",
    )

    def _raise(*a, **k):
        raise AssertionError("should not resolve/fetch a PDF when cache is fresh")

    monkeypatch.setattr(asx_announcements, "_resolve_pdf_url", _raise)

    monkeypatch.setattr(
        asx_announcements, "get_announcement_summaries_for_ticker",
        _real_get_announcement_summaries_for_ticker,
    )
    result = asx_announcements.get_announcement_summaries_for_ticker("BXB.AX", db_conn)
    assert result == {"Half-Year Report": "Cached summary."}


def test_get_announcement_summaries_refetches_on_new_announcement_id(db_conn, monkeypatch):
    monkeypatch.setattr(
        asx_announcements, "_fetch_announcements_list",
        lambda code, year: [{"title": "2026 Half Year Accounts", "ids_id": "IDS-2"}],
    )
    db.upsert_asx_summary_cache(
        db_conn, ticker="BXB.AX", announcement_type="Half-Year Report",
        announcement_id="IDS-1", summary="Old summary.",
    )
    monkeypatch.setattr(asx_announcements, "_resolve_pdf_url", lambda ids_id: "https://example.com/x.pdf")
    monkeypatch.setattr(asx_announcements, "_fetch_pdf_bytes", lambda url: b"%PDF-fake")
    monkeypatch.setattr(asx_announcements, "_extract_pdf_text", lambda pdf_bytes: "Review of Operations real content.")
    monkeypatch.setattr(asx_announcements, "_extract_sections", lambda text: {"review_of_operations": "real content"})
    monkeypatch.setattr(asx_announcements, "_summarize_sections", lambda ticker, label, sections: "New summary.")

    monkeypatch.setattr(
        asx_announcements, "get_announcement_summaries_for_ticker",
        _real_get_announcement_summaries_for_ticker,
    )
    result = asx_announcements.get_announcement_summaries_for_ticker("BXB.AX", db_conn)
    assert result == {"Half-Year Report": "New summary."}
    cached = db.get_cached_asx_summary(db_conn, "BXB.AX", "Half-Year Report")
    assert cached["announcement_id"] == "IDS-2"
    assert cached["summary"] == "New summary."


def test_get_announcement_summaries_falls_back_to_stale_cache_on_fetch_failure(db_conn, monkeypatch):
    monkeypatch.setattr(
        asx_announcements, "_fetch_announcements_list",
        lambda code, year: [{"title": "2026 Half Year Accounts", "ids_id": "IDS-2"}],
    )
    db.upsert_asx_summary_cache(
        db_conn, ticker="BXB.AX", announcement_type="Half-Year Report",
        announcement_id="IDS-1", summary="Stale summary.",
    )
    monkeypatch.setattr(asx_announcements, "_resolve_pdf_url", lambda ids_id: None)

    monkeypatch.setattr(
        asx_announcements, "get_announcement_summaries_for_ticker",
        _real_get_announcement_summaries_for_ticker,
    )
    result = asx_announcements.get_announcement_summaries_for_ticker("BXB.AX", db_conn)
    assert result == {"Half-Year Report": "Stale summary."}


def test_get_announcement_summaries_falls_back_to_previous_year_when_type_missing(db_conn, monkeypatch):
    def _fetch(code, year):
        if year == 2026:
            return [{"title": "Notification of cessation of securities", "ids_id": "IDS-OTHER"}]
        return [{"title": "2025 Annual Report (including Appendix 4E)", "ids_id": "IDS-ANNUAL-2025"}]

    monkeypatch.setattr(asx_announcements, "_fetch_announcements_list", _fetch)
    monkeypatch.setattr(asx_announcements, "_resolve_pdf_url", lambda ids_id: "https://example.com/x.pdf")
    monkeypatch.setattr(asx_announcements, "_fetch_pdf_bytes", lambda url: b"%PDF-fake")
    monkeypatch.setattr(asx_announcements, "_extract_pdf_text", lambda pdf_bytes: "Operating and Financial Review real content.")
    monkeypatch.setattr(asx_announcements, "_extract_sections", lambda text: {"operating_and_financial_review": "real content"})
    monkeypatch.setattr(asx_announcements, "_summarize_sections", lambda ticker, label, sections: "Annual summary.")

    monkeypatch.setattr(
        asx_announcements, "get_announcement_summaries_for_ticker",
        _real_get_announcement_summaries_for_ticker,
    )
    result = asx_announcements.get_announcement_summaries_for_ticker("WES.AX", db_conn)
    assert result == {"Annual Report": "Annual summary."}
