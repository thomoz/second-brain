from __future__ import annotations

import json

from ai_resistant_moat_scanner import config, db, filings_extract, qualitative


def _async_return(value):
    async def _fake(*a, **k):
        return value
    return _fake


_RUBRIC = {
    "sub_scores": {k: 10 for k in qualitative._RUBRIC_KEYS},
    "citations": {},
    "anti_signals": [],
    "thesis": "System of record with deep switching costs.",
}


def test_cache_hit_makes_zero_llm_or_fetch_calls(db_conn, monkeypatch):
    entry = {
        "cik": "21344", "accession_number": "acc-1",
        "primary_document": "d.htm", "filing_date": "2026-02-20",
    }
    monkeypatch.setattr(filings_extract, "latest_10k", lambda conn, ticker: entry)

    def _boom(*a, **k):
        raise AssertionError("should not be called on a cache hit")

    monkeypatch.setattr(filings_extract, "fetch_10k_sections", _boom)
    monkeypatch.setattr(filings_extract, "extract_disclosures", _boom)
    monkeypatch.setattr(qualitative, "score_rubric", _boom)

    db.upsert_qualitative_cache(
        db_conn, ticker="CRM", accession_number="acc-1", rubric_version=config.RUBRIC_VERSION,
        extraction_json=json.dumps({"nrr_pct": 120}), rubric_json=json.dumps(_RUBRIC),
        thesis=_RUBRIC["thesis"],
    )

    result = qualitative.get_qualitative(db_conn, "CRM")
    assert result["qualitative_score"] == 100.0
    assert result["extraction"]["nrr_pct"] == 120
    assert result["accession_number"] == "acc-1"


def test_score_rubric_clamps_out_of_range_subscores(monkeypatch):
    payload = json.dumps({
        "system_of_record": 15, "switching_costs": -3, "ecosystem_lockin": 7,
        "regulatory_entrenchment": 5, "workflow_breadth": 4, "mission_criticality": 9,
        "citations": {}, "anti_signals": [], "thesis": "t",
    })
    monkeypatch.setattr(qualitative, "run_text", _async_return(payload))
    rubric = qualitative.score_rubric("CRM", {"business": "b", "risk_factors": "r"}, {})
    assert rubric["sub_scores"]["system_of_record"] == 10
    assert rubric["sub_scores"]["switching_costs"] == 0


def test_score_rubric_none_when_run_text_raises(monkeypatch):
    async def _boom(*a, **k):
        raise RuntimeError("down")

    monkeypatch.setattr(qualitative, "run_text", _boom)
    assert qualitative.score_rubric("CRM", {"business": "b"}, {}) is None


def test_compute_qualitative_score_penalty_is_capped():
    rubric = {"sub_scores": {k: 10 for k in qualitative._RUBRIC_KEYS},
              "anti_signals": ["a", "b", "c", "d"]}
    # raw 100, penalty min(4*8, 30) = 30
    assert qualitative.compute_qualitative_score(rubric) == 70.0


def test_get_qualitative_none_when_no_10k(db_conn, monkeypatch):
    monkeypatch.setattr(filings_extract, "latest_10k", lambda conn, ticker: None)
    assert qualitative.get_qualitative(db_conn, "CRM") is None
