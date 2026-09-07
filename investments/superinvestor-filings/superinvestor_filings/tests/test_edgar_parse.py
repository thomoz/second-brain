from __future__ import annotations

import pathlib

from superinvestor_filings import edgar_parse

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


def test_parse_form4_transactions_and_identity():
    xml = (FIXTURES / "form4_sample.xml").read_text(encoding="utf-8")
    parsed = edgar_parse.parse_ownership_form(xml)
    assert parsed is not None
    assert parsed["issuer_ticker"] == "AMR"
    assert parsed["issuer_name"].startswith("Alpha Metallurgical")
    assert parsed["owner_name"] == "Dalal Street, LLC"
    assert parsed["is_ten_pct_owner"] is True
    assert len(parsed["transactions"]) == 1
    txn = parsed["transactions"][0]
    assert txn["code"] == "S"
    assert txn["date"] == "2026-09-02"
    assert txn["shares"] == 40000.0
    assert txn["price"] == 200.0
    assert txn["shares_owned_after"] == 100000.0


def test_parse_ownership_form_rejects_non_ownership_xml():
    assert edgar_parse.parse_ownership_form("<edgarSubmission></edgarSubmission>") is None
    assert edgar_parse.parse_ownership_form("not xml at all") is None


def test_parse_schedule_13g_structured():
    xml = (FIXTURES / "sc13g_structured_sample.xml").read_text(encoding="utf-8")
    parsed = edgar_parse.parse_schedule_13dg(xml)
    assert parsed is not None
    assert parsed["pct_owned"] == 5.2
    assert parsed["shares"] == 2750000.0
    assert parsed["issuer_cik"] == "0000866787"
    assert parsed["cusip"] == "123456789"


def test_parse_schedule_13g_text_fallback():
    htm = (FIXTURES / "sc13g_text_sample.htm").read_text(encoding="utf-8")
    parsed = edgar_parse.parse_schedule_13dg(htm)
    assert parsed is not None
    assert parsed["pct_owned"] == 4.2
    assert parsed["shares"] == 1234567.0
    assert parsed["cusip"] == "987654321"
    assert parsed["issuer_name"] == "Frontier Coal Holdings Corp"


def test_parse_schedule_13dg_returns_none_when_nothing_parseable():
    assert edgar_parse.parse_schedule_13dg("<html><body>nothing useful here</body></html>") is None


def test_classify_material_crossing_cases():
    assert edgar_parse.classify_material_crossing("SC 13G", 5.2, 4.9) == "5% cross"
    assert edgar_parse.classify_material_crossing("SC 13G/A", 10.4, 9.5) == "10% cross"
    assert edgar_parse.classify_material_crossing("SC 13G/A", 4.2, 6.0) == "below 5%"
    assert edgar_parse.classify_material_crossing("SC 13G/A", 7.0, 6.0) is None
    assert edgar_parse.classify_material_crossing("SC 13G", 3.1, None) is None


def test_classify_material_crossing_initial_filing_no_prior():
    assert edgar_parse.classify_material_crossing("SC 13G", 5.5, None) == "5% cross"
    assert edgar_parse.classify_material_crossing("SC 13D", 11.0, None) == "10% cross"
    assert edgar_parse.classify_material_crossing("SC 13G/A", 5.5, None) is None
    assert edgar_parse.classify_material_crossing("SC 13G", None, None) is None
