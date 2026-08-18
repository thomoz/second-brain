from __future__ import annotations

from fourteen_crash_signals_daily_check import lease_commitment


def _index(filing_type="10-K", accession="ACC-1", filing_date="2026-02-20"):
    return {"filings": {"recent": {
        "form": [filing_type], "accessionNumber": [accession],
        "primaryDocument": ["doc.htm"], "filingDate": [filing_date],
    }}}


def _install_fetch(monkeypatch, *, cik="21344", index=None, html="<html>lease text</html>"):
    monkeypatch.setattr(lease_commitment.sec_filings, "get_cik", lambda conn, ticker: cik)
    monkeypatch.setattr(lease_commitment.sec_filings, "fetch_filing_index", lambda cik: index)
    monkeypatch.setattr(lease_commitment.sec_filings, "fetch_filing_document", lambda cik, acc, doc: html)


def test_first_observation_returns_ok_regardless_of_figure_size(db_conn, monkeypatch):
    _install_fetch(monkeypatch, index=_index())
    monkeypatch.setattr(lease_commitment, "_find_lease_note_window", lambda text: "window text")
    monkeypatch.setattr(lease_commitment, "_summarize_lease_figure", lambda ticker, text: 50_000_000_000.0)

    results = lease_commitment.check_lease_commitments(db_conn, [{"ticker": "ORCL"}])
    assert len(results) == 1
    assert results[0].verdict == "ok"
    assert "growth_pct" not in results[0].data


def test_second_observation_with_high_growth_flags(db_conn, monkeypatch):
    from fourteen_crash_signals_daily_check import db as db_mod

    db_mod.upsert_lease_commitment_history(
        db_conn, ticker="ORCL", accession_number="ACC-OLD", figure=1_000_000_000.0, filing_date="2025-11-01",
    )
    _install_fetch(monkeypatch, index=_index(accession="ACC-NEW"))
    monkeypatch.setattr(lease_commitment, "_find_lease_note_window", lambda text: "window text")
    monkeypatch.setattr(lease_commitment, "_summarize_lease_figure", lambda ticker, text: 2_000_000_000.0)

    results = lease_commitment.check_lease_commitments(db_conn, [{"ticker": "ORCL"}])
    assert len(results) == 1
    assert results[0].verdict == "flag"
    assert results[0].data["growth_pct"] == 100.0


def test_second_observation_with_low_growth_stays_ok(db_conn, monkeypatch):
    from fourteen_crash_signals_daily_check import db as db_mod

    db_mod.upsert_lease_commitment_history(
        db_conn, ticker="ORCL", accession_number="ACC-OLD", figure=1_000_000_000.0, filing_date="2025-11-01",
    )
    _install_fetch(monkeypatch, index=_index(accession="ACC-NEW"))
    monkeypatch.setattr(lease_commitment, "_find_lease_note_window", lambda text: "window text")
    monkeypatch.setattr(lease_commitment, "_summarize_lease_figure", lambda ticker, text: 1_100_000_000.0)

    results = lease_commitment.check_lease_commitments(db_conn, [{"ticker": "ORCL"}])
    assert len(results) == 1
    assert results[0].verdict == "ok"
    assert results[0].data["growth_pct"] == 10.0


def test_same_accession_reuses_cached_figure_without_refetching(db_conn, monkeypatch):
    from fourteen_crash_signals_daily_check import db as db_mod

    db_mod.upsert_lease_commitment_history(
        db_conn, ticker="ORCL", accession_number="ACC-1", figure=1_000_000_000.0, filing_date="2025-11-01",
    )
    monkeypatch.setattr(lease_commitment.sec_filings, "get_cik", lambda conn, ticker: "21344")
    monkeypatch.setattr(lease_commitment.sec_filings, "fetch_filing_index", lambda cik: _index(accession="ACC-1"))

    def _raise(*a, **k):
        raise AssertionError("should not fetch document when accession is unchanged")

    monkeypatch.setattr(lease_commitment.sec_filings, "fetch_filing_document", _raise)

    def _raise_summarize(*a, **k):
        raise AssertionError("should not call the LLM when accession is unchanged")

    monkeypatch.setattr(lease_commitment, "_summarize_lease_figure", _raise_summarize)

    results = lease_commitment.check_lease_commitments(db_conn, [{"ticker": "ORCL"}])
    assert len(results) == 1
    assert results[0].data["growth_pct"] == 0.0
    assert results[0].verdict == "ok"


def test_ticker_with_no_cik_is_silently_skipped(db_conn, monkeypatch):
    monkeypatch.setattr(lease_commitment.sec_filings, "get_cik", lambda conn, ticker: None)
    results = lease_commitment.check_lease_commitments(db_conn, [{"ticker": "UNKNOWN"}])
    assert results == []


def test_ticker_with_no_matching_heading_is_silently_skipped(db_conn, monkeypatch):
    _install_fetch(monkeypatch, index=_index())
    monkeypatch.setattr(lease_commitment, "_find_lease_note_window", lambda text: None)
    results = lease_commitment.check_lease_commitments(db_conn, [{"ticker": "ORCL"}])
    assert results == []
