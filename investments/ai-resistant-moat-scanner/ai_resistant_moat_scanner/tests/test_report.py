from __future__ import annotations

from ai_resistant_moat_scanner import config, report

_ROW_SCORED: dict = {
    "ticker": "CRM", "company": "Salesforce", "industry": "Software - Application",
    "moat_score": 88.5, "quant_score": 82.0, "qualitative_score": 95.0,
    "rubric_sub_scores": {k: 9 for k in (
        "system_of_record", "switching_costs", "ecosystem_lockin",
        "regulatory_entrenchment", "workflow_breadth", "mission_criticality")},
    "anti_signals": ["some risk"], "thesis": "Embedded system of record.",
    "tags": ["held"], "worst_revenue_yoy": -1.5,
}
_ROW_NO_10K: dict = {
    "ticker": "XYZ", "company": "XYZ Corp", "industry": "seed / not screened",
    "moat_score": None, "quant_score": 60.0, "qualitative_score": None,
    "rubric_sub_scores": {}, "anti_signals": [], "thesis": "No 10-K.", "tags": [],
    "worst_revenue_yoy": None,
}


def _result(**over):
    base = {
        "scanned": 2, "slice_index": 0, "slices": 5, "screened_total": 40,
        "finviz_failed": False, "rows": [_ROW_SCORED, _ROW_NO_10K],
        "new_candidates": [], "pending_candidates": [],
    }
    base.update(over)
    return base


def test_render_report_has_caveat_disclaimer_and_rows():
    out = report.render_report(_result())
    assert config.RUBRIC_VERSION in out
    assert "SOUL.md" in out
    assert "| CRM |" in out
    assert "n/a (no 10-K)" in out


def test_write_report_stale_banner_is_non_stacking(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "MOAT_SCAN_REPORT_PATH", tmp_path / "moat-scan-report.md")
    stale = _result(finviz_failed=True, rows=[])
    report.write_report(stale)
    report.write_report(stale)
    text = (tmp_path / "moat-scan-report.md").read_text(encoding="utf-8")
    assert text.count("STALE -- Finviz screen fetch failed") == 1


def test_render_candidates_report_lists_pending_and_instructions():
    result = _result(pending_candidates=[{
        "ticker": "NOW", "industry": "Software - Application", "moat_score": 91.0,
        "quant_score": 88.0, "qualitative_score": 94.0, "thesis": "Workflow system of record.",
        "flagged_at": "2026-09-09T00:00:00+00:00",
    }])
    out = report.render_candidates_report(result)
    assert "promote-candidate" in out and "dismiss-candidate" in out
    assert "| NOW |" in out
    assert "2026-09-09" in out
