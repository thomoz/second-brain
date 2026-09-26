from __future__ import annotations

from superinvestor_filings import report


def _alert(**kw):
    base = dict(
        filer_key="pabrai", filer_display="Mohnish Pabrai / Dalal Street",
        form_type="SC 13G", issuer="RAIN",
        summary="SC 13G on RAIN (5.2% of class, filed 2026-09-05) [5% cross]",
        raw_url="https://www.sec.gov/Archives/edgar/data/1549575/000.../primary_doc.xml",
        material_crossing="5% cross", pct_owned=5.2, shares=2_750_000.0,
        filed_date="2026-09-05", event_date=None,
    )
    base.update(kw)
    return base


def test_render_groups_by_investor_and_lists_filings():
    result = {
        "new_filings": [_alert(), _alert(issuer="AMR", summary="Form 4 on AMR (sold 40,000 sh)")],
        "recent_filings": [_alert()],
        "first_seed": False,
    }
    md = report.render_report(result)
    assert "### Mohnish Pabrai / Dalal Street -- 2 new" in md
    assert "SC 13G on RAIN" in md
    assert "Form 4 on AMR" in md
    assert "All Recent Filings" in md


def test_render_shows_chart_note_when_present():
    result = {
        "new_filings": [_alert(chart_note="above 150DMA (+3.2%) | chart setup score 78/100 (trend 40/40 ...)")],
        "recent_filings": [],
        "first_seed": False,
    }
    md = report.render_report(result)
    assert "Chart: above 150DMA" in md
    assert "chart setup score 78/100" in md


def test_render_omits_chart_line_when_note_empty():
    result = {"new_filings": [_alert(chart_note="")], "recent_filings": [], "first_seed": False}
    md = report.render_report(result)
    assert "Chart:" not in md


def test_recent_filings_table_shows_source_column():
    result = {
        "new_filings": [],
        "recent_filings": [
            {"source": "edgar", "filer_display": "Mohnish Pabrai / Dalal Street",
             "form_type": "SC 13G/A", "issuer": "AMR", "pct_owned": 4.76,
             "material_crossing": "below 5%", "filed_date": "2026-08-13"},
            {"source": "sast", "filer_display": "Mohnish Pabrai / Dalal Street",
             "form_type": "SAST Reg 29(2)", "issuer": "Rain Industries Ltd",
             "filed_date": "2026-09-06"},
        ],
        "first_seed": False,
    }
    md = report.render_report(result)
    assert "US EDGAR" in md
    assert "IN BSE SAST" in md
    assert "SAST Reg 29(2)" in md


# --- _issuer_cell -------------------------------------------------------------


def test_issuer_cell_combines_name_and_ticker_when_both_known():
    row = {"issuer": "LEN", "issuer_ticker": "LEN", "issuer_name": "Lennar Corp"}
    assert report._issuer_cell(row) == "Lennar Corp (LEN)"


def test_issuer_cell_falls_back_to_issuer_when_no_name():
    row = {"issuer": "LEN", "issuer_ticker": "LEN", "issuer_name": None}
    assert report._issuer_cell(row) == "LEN"


def test_issuer_cell_sast_row_with_no_ticker_shows_full_name_unchanged():
    # India/SAST rows never resolve a ticker -- `issuer` is already the full
    # company name (SLONGNAME) in that case, see sast_monitor.scan_india.
    row = {"issuer": "Rain Industries Ltd", "issuer_ticker": None, "issuer_name": None}
    assert report._issuer_cell(row) == "Rain Industries Ltd"


def test_issuer_cell_skips_duplicate_parens_when_name_equals_ticker():
    row = {"issuer": "unknown issuer", "issuer_ticker": None, "issuer_name": "unknown issuer"}
    assert report._issuer_cell(row) == "unknown issuer"


def test_render_how_to_read_caveat_present():
    md = report.render_report({"new_filings": [], "recent_filings": [], "first_seed": False})
    assert "still waits for the quarterly cycle" in md
    assert "no trade action is ever suggested here (see SOUL.md)" in md


def test_render_empty_new_filings_message():
    md = report.render_report({"new_filings": [], "recent_filings": [], "first_seed": False})
    assert "No new fast-disclosure filings since the last run." in md


def test_render_first_seed_note():
    md = report.render_report({"new_filings": [], "recent_filings": [], "first_seed": True})
    assert "First run" in md
    assert "no alert was sent" in md


def test_write_report_writes_file(tmp_path, monkeypatch):
    import superinvestor_filings.config as sf_config

    target = tmp_path / "superinvestor-filings-report.md"
    monkeypatch.setattr(sf_config, "SUPERINVESTOR_REPORT_PATH", target)
    report.write_report({"new_filings": [], "recent_filings": [], "first_seed": False})
    assert target.exists()
    assert "Superinvestor Fast-Disclosure Filings" in target.read_text(encoding="utf-8")
