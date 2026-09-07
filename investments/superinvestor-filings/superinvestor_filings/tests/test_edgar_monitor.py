from __future__ import annotations

import pathlib
from datetime import date, timedelta

import pytest
from mytrader.db import get_sync_watermark, set_sync_watermark

from superinvestor_filings import config, db, edgar_monitor

FIXTURES = pathlib.Path(__file__).parent / "fixtures"
FORM4_XML = (FIXTURES / "form4_sample.xml").read_text(encoding="utf-8")
SC13G_XML = (FIXTURES / "sc13g_structured_sample.xml").read_text(encoding="utf-8")


@pytest.fixture(autouse=True)
def _single_tracked_filer(monkeypatch):
    monkeypatch.setattr(config, "SUPERINVESTOR_TRACKED", {
        "pabrai": {
            "display": "Mohnish Pabrai / Dalal Street",
            "edgar_ciks": ["1549575"],
            "india_aliases": [],
        }
    })


def _index(forms, accessions, docs, dates):
    return {"filings": {"recent": {
        "form": list(forms),
        "accessionNumber": list(accessions),
        "primaryDocument": list(docs),
        "primaryDocDescription": ["" for _ in forms],
        "filingDate": list(dates),
        "acceptanceDateTime": [d + "T18:00:00.000Z" for d in dates],
    }}}


def _one_form4(filing_date=None):
    fd = filing_date or date.today().isoformat()
    if not isinstance(fd, str):
        fd = fd.isoformat()
    return _index(["4"], ["0001549575-26-000010"], ["form4.xml"], [fd])


def _seed_done(conn):
    set_sync_watermark(conn, config.SUPERINVESTOR_FIRST_SEED_WATERMARK, "done")


def test_new_form4_appears_in_new_filings_and_seen_log(db_conn, monkeypatch):
    _seed_done(db_conn)
    monkeypatch.setattr("mytrader.sec_filings.fetch_filing_index", lambda cik: _one_form4())
    monkeypatch.setattr("mytrader.sec_filings.fetch_filing_document", lambda c, a, d: FORM4_XML)

    result = edgar_monitor.scan_edgar(db_conn)
    assert len(result["new_filings"]) == 1
    alert = result["new_filings"][0]
    assert "AMR" in alert["summary"]
    assert "sold 40,000 sh" in alert["summary"]
    assert "[>10% owner]" in alert["summary"]
    assert db.count_seen(db_conn) == 1


def test_same_filing_is_quiet_on_repeat_run(db_conn, monkeypatch):
    _seed_done(db_conn)
    monkeypatch.setattr("mytrader.sec_filings.fetch_filing_index", lambda cik: _one_form4())
    monkeypatch.setattr("mytrader.sec_filings.fetch_filing_document", lambda c, a, d: FORM4_XML)

    edgar_monitor.scan_edgar(db_conn)
    result = edgar_monitor.scan_edgar(db_conn)
    assert result["new_filings"] == []
    assert db.count_seen(db_conn) == 1


def test_first_run_seeds_silently_then_alerts_on_next_new_filing(db_conn, monkeypatch):
    assert get_sync_watermark(db_conn, config.SUPERINVESTOR_FIRST_SEED_WATERMARK) is None
    monkeypatch.setattr("mytrader.sec_filings.fetch_filing_index", lambda cik: _one_form4())
    monkeypatch.setattr("mytrader.sec_filings.fetch_filing_document", lambda c, a, d: FORM4_XML)

    seed = edgar_monitor.scan_edgar(db_conn)
    assert seed["first_seed"] is True
    assert seed["new_filings"] == []
    assert db.count_seen(db_conn) == 1
    assert get_sync_watermark(db_conn, config.SUPERINVESTOR_FIRST_SEED_WATERMARK) is not None

    # a genuinely new filing on the next run alerts
    monkeypatch.setattr(
        "mytrader.sec_filings.fetch_filing_index",
        lambda cik: _index(["SC 13G"], ["0001549575-26-000011"], ["primary_doc.xml"],
                           [date.today().isoformat()]),
    )
    monkeypatch.setattr("mytrader.sec_filings.fetch_filing_document", lambda c, a, d: SC13G_XML)
    run2 = edgar_monitor.scan_edgar(db_conn)
    assert run2["first_seed"] is False
    assert len(run2["new_filings"]) == 1
    assert "5% cross" in run2["new_filings"][0]["summary"]


def test_first_seed_watermark_set_even_when_no_filings(db_conn, monkeypatch):
    monkeypatch.setattr("mytrader.sec_filings.fetch_filing_index", lambda cik:
                        _index([], [], [], []))
    result = edgar_monitor.scan_edgar(db_conn)
    assert result["first_seed"] is True
    assert get_sync_watermark(db_conn, config.SUPERINVESTOR_FIRST_SEED_WATERMARK) is not None


def test_filer_skipped_on_fetch_failure_without_crashing(db_conn, monkeypatch):
    _seed_done(db_conn)
    monkeypatch.setattr("mytrader.sec_filings.fetch_filing_index", lambda cik: None)
    result = edgar_monitor.scan_edgar(db_conn)  # must not raise
    assert result["new_filings"] == []
    assert db.count_seen(db_conn) == 0


def test_filing_outside_lookback_window_is_ignored(db_conn, monkeypatch):
    _seed_done(db_conn)
    stale = (date.today() - timedelta(days=config.SUPERINVESTOR_LOOKBACK_DAYS + 5)).isoformat()
    monkeypatch.setattr("mytrader.sec_filings.fetch_filing_index", lambda cik: _one_form4(stale))
    monkeypatch.setattr("mytrader.sec_filings.fetch_filing_document", lambda c, a, d: FORM4_XML)
    result = edgar_monitor.scan_edgar(db_conn)
    assert result["new_filings"] == []
    assert db.count_seen(db_conn) == 0


def test_non_tracked_form_is_ignored(db_conn, monkeypatch):
    _seed_done(db_conn)
    monkeypatch.setattr(
        "mytrader.sec_filings.fetch_filing_index",
        lambda cik: _index(["13F-HR"], ["0001549575-26-000099"], ["primary_doc.xml"],
                           [date.today().isoformat()]),
    )
    result = edgar_monitor.scan_edgar(db_conn)
    assert result["new_filings"] == []
    assert db.count_seen(db_conn) == 0
