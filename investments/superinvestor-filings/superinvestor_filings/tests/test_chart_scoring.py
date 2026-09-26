from __future__ import annotations

from superinvestor_filings import chart_scoring


def test_annotate_chart_notes_skips_row_with_no_ticker():
    rows = [{"issuer": "BSE 500325", "issuer_ticker": None, "event_date": None, "filed_date": "2026-09-20"}]
    result = chart_scoring.annotate_chart_notes(rows)
    assert result[0]["chart_note"] == ""


def test_annotate_chart_notes_skips_row_with_no_date():
    rows = [{"issuer": "LEN", "issuer_ticker": "LEN", "event_date": None, "filed_date": None}]
    result = chart_scoring.annotate_chart_notes(rows)
    assert result[0]["chart_note"] == ""


def test_annotate_chart_notes_calls_build_chart_note_with_ticker_and_date(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "superinvestor_filings.chart_scoring.css.build_chart_note",
        lambda ticker, trade_date_str: calls.append((ticker, trade_date_str)) or "a note",
    )
    rows = [{"issuer_ticker": "LEN", "event_date": "2026-09-18", "filed_date": "2026-09-20"}]
    result = chart_scoring.annotate_chart_notes(rows)
    assert calls == [("LEN", "2026-09-18")]  # event_date preferred over filed_date
    assert result[0]["chart_note"] == "a note"


def test_annotate_chart_notes_falls_back_to_filed_date_when_no_event_date(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "superinvestor_filings.chart_scoring.css.build_chart_note",
        lambda ticker, trade_date_str: calls.append((ticker, trade_date_str)) or "a note",
    )
    rows = [{"issuer_ticker": "LEN", "event_date": None, "filed_date": "2026-09-20"}]
    chart_scoring.annotate_chart_notes(rows)
    assert calls == [("LEN", "2026-09-20")]


def test_annotate_chart_notes_returns_the_same_list_object():
    rows = [{"issuer_ticker": None, "event_date": None, "filed_date": None}]
    assert chart_scoring.annotate_chart_notes(rows) is rows
