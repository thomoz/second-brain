"""Shared fixtures for AI-Resistant Moat Scanner tests. Mirrors
superinvestor-filings + goat conftest shape: tmp_path-backed DB, report paths
isolated to tmp_path, and every network / LLM entrypoint stubbed by default.

`run_text` is stubbed to an async fn that RAISES, so any code path that forgets to
stub its own LLM call fails loudly rather than hanging or hitting a real backend.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from scripts.db import get_connection, init_db

from mytrader.db import init_mytrader_tables

from ai_resistant_moat_scanner.db import init_moat_tables

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def db_path(tmp_path) -> Path:
    return tmp_path / "test_investments.db"


@pytest.fixture
def db_conn(db_path):
    init_db(db_path)
    conn = get_connection(db_path)
    init_mytrader_tables(conn)
    init_moat_tables(conn)
    yield conn
    conn.close()


@pytest.fixture(autouse=True)
def _isolate_report_paths(monkeypatch, tmp_path):
    import ai_resistant_moat_scanner.config as cfg

    monkeypatch.setattr(cfg, "MOAT_SCAN_REPORT_PATH", tmp_path / "moat-scan-report.md")
    monkeypatch.setattr(cfg, "MOAT_CANDIDATES_MD_PATH", tmp_path / "moat-candidates-pending-review.md")
    monkeypatch.setattr(cfg, "MOAT_SEC_REQUEST_DELAY_SECONDS", 0)
    monkeypatch.setattr(cfg, "MOAT_FETCH_DELAY_SECONDS", 0)
    monkeypatch.setattr(cfg, "MOAT_FINVIZ_REQUEST_DELAY_SECONDS", 0)


async def _raising_run_text(*args, **kwargs):
    raise AssertionError("un-stubbed LLM call in a test -- stub run_text explicitly")


@pytest.fixture(autouse=True)
def _no_real_network(monkeypatch):
    monkeypatch.setattr("mytrader.sec_filings._fetch_cik_map_bulk", lambda: None)
    monkeypatch.setattr("mytrader.sec_filings.get_cik", lambda conn, ticker: None)
    monkeypatch.setattr("mytrader.sec_filings.fetch_filing_index", lambda cik: None)
    monkeypatch.setattr(
        "mytrader.sec_filings.fetch_filing_document", lambda cik, acc, doc: None
    )
    monkeypatch.setattr(
        "mytrader.finviz_screener.fetch_screener_universe", lambda *a, **k: None
    )
    monkeypatch.setattr("mytrader.market_data.fetch_ticker_data", lambda *a, **k: None)
    monkeypatch.setattr(
        "mytrader.market_data.fetch_income_statement_history", lambda *a, **k: None
    )
    monkeypatch.setattr(
        "ai_resistant_moat_scanner.filings_extract.run_text", _raising_run_text
    )
    monkeypatch.setattr(
        "ai_resistant_moat_scanner.qualitative.run_text", _raising_run_text
    )
