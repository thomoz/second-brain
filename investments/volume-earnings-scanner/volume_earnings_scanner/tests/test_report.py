from __future__ import annotations

from volume_earnings_scanner import config, report


def _result(pending: list[dict], **overrides) -> dict:
    base = {
        "scanned": 10, "slice_index": 0, "slices": 5, "screened_total": 50,
        "finviz_failed": False, "pending_candidates": pending,
    }
    base.update(overrides)
    return base


def test_render_candidates_report_lists_pending_rows():
    pending = [
        {"ticker": "ABCD", "company_name": "ABCD Inc", "signal_type": "both",
         "signal_detail": "BOTH SIGNALS -- test", "flagged_at": "2026-10-14T00:00:00+00:00"},
    ]
    text = report.render_candidates_report(_result(pending))
    assert "ABCD" in text
    assert "BOTH SIGNALS" in text
    assert "both" in text


def test_render_candidates_report_empty_shows_none_row():
    text = report.render_candidates_report(_result([]))
    assert "_(none)_" in text


def test_render_candidates_report_notes_finviz_failure():
    text = report.render_candidates_report(_result([], finviz_failed=True))
    assert "Finviz screen fetch failed" in text


def test_write_candidates_report_writes_to_configured_path():
    report.write_candidates_report(_result([]))
    assert config.VE_CANDIDATES_MD_PATH.exists()
    assert "Pending Review" in config.VE_CANDIDATES_MD_PATH.read_text(encoding="utf-8")
