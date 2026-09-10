from __future__ import annotations

import json

from ai_resistant_moat_scanner import config, scoring

_QUANT = {
    "quant_score": 70.0,
    "sub_scores": {"gross_margin": 80.0},
    "gross_margin": 0.72,
    "fcf_margin": 0.18,
    "operating_margin": 0.2,
    "rule_of_40": 45.0,
    "worst_revenue_yoy": -2.0,
    "market_cap": 5e9,
    "currency": "USD",
    "sector": "Technology",
    "disclosure_bonus": 2.0,
}

_QUAL = {
    "qualitative_score": 90.0,
    "sub_scores": {k: 9 for k in scoring._RUBRIC_KEYS},
    "anti_signals": ["one"],
    "thesis": "Deeply embedded system of record.",
    "citations": {},
    "filing_date": "2026-02-20",
}


def test_blend_score_is_50_50():
    assert scoring.blend_score(70.0, 90.0) == 80.0
    assert config.MOAT_BLEND_QUANT_WEIGHT == 0.5


def test_assemble_row_with_qualitative():
    row = scoring.assemble_row("CRM", "Software - Application", "Salesforce", _QUANT, _QUAL, ["held"])
    assert row["moat_score"] == 80.0
    assert row["stageable"] is True
    assert row["qualitative_score"] == 90.0
    assert row["tags"] == ["held"]
    parsed = json.loads(row["sub_scores_json"])
    assert parsed["qualitative"]["system_of_record"] == 9
    assert parsed["anti_signals"] == ["one"]


def test_assemble_row_without_qualitative_is_not_stageable():
    row = scoring.assemble_row("XYZ", "seed / not screened", "XYZ Corp", _QUANT, None, [])
    assert row["moat_score"] is None
    assert row["stageable"] is False
    assert row["qualitative_score"] is None
    assert json.loads(row["sub_scores_json"])["qualitative"]["system_of_record"] is None
