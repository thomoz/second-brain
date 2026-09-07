"""Shared fixtures for superinvestor-filings tests. Mirrors goat/goat/tests/conftest.py:
tmp_path-backed DB, report path isolated to tmp_path, and every network entrypoint
stubbed to return None by default (individual tests override with monkeypatch)."""

from __future__ import annotations

from pathlib import Path

import pytest
from scripts.db import get_connection, init_db

from mytrader.db import init_mytrader_tables

from superinvestor_filings.db import init_superinvestor_tables

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def db_path(tmp_path) -> Path:
    return tmp_path / "test_investments.db"


@pytest.fixture
def db_conn(db_path):
    init_db(db_path)
    conn = get_connection(db_path)
    init_mytrader_tables(conn)
    init_superinvestor_tables(conn)
    yield conn
    conn.close()


@pytest.fixture(autouse=True)
def _isolate_report_path(monkeypatch, tmp_path):
    import superinvestor_filings.config as sf_config

    monkeypatch.setattr(
        sf_config, "SUPERINVESTOR_REPORT_PATH", tmp_path / "superinvestor-filings-report.md"
    )
    monkeypatch.setattr(sf_config, "SUPERINVESTOR_SEC_REQUEST_DELAY_SECONDS", 0)


@pytest.fixture(autouse=True)
def _no_real_network(monkeypatch):
    """No test in this suite makes a real SEC/NSE call by default. recent_filings_of_types
    is left real (pure function). Individual tests re-patch the fetch functions with
    fixture data."""
    monkeypatch.setattr("mytrader.sec_filings._fetch_cik_map_bulk", lambda: None)
    monkeypatch.setattr("mytrader.sec_filings.get_cik", lambda conn, ticker: None)
    monkeypatch.setattr("mytrader.sec_filings.fetch_filing_index", lambda cik: None)
    monkeypatch.setattr(
        "mytrader.sec_filings.fetch_filing_document", lambda cik, acc, doc: None
    )
    monkeypatch.setattr(
        "mytrader.sec_filings.fetch_filing_directory_index", lambda cik, acc: None
    )
    monkeypatch.setattr(
        "mytrader.sec_filings.edgar_fulltext_search_hits", lambda *a, **k: None
    )
