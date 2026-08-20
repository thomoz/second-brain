"""Shared fixtures for goat tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from scripts.db import get_connection, init_db

from mytrader.db import init_mytrader_tables
from goat.db import init_goat_tables


@pytest.fixture
def db_path(tmp_path) -> Path:
    return tmp_path / "test_investments.db"


@pytest.fixture
def db_conn(db_path):
    init_db(db_path)
    conn = get_connection(db_path)
    init_mytrader_tables(conn)
    init_goat_tables(conn)
    yield conn
    conn.close()


@pytest.fixture(autouse=True)
def _isolate_goat_report_path(monkeypatch, tmp_path):
    import goat.config as goat_config
    monkeypatch.setattr(goat_config, "GOAT_MONITOR_REPORT_PATH", tmp_path / "monitor-report.md")
    monkeypatch.setattr(
        goat_config, "GOAT_HEARTBEAT_CANDIDATES_MD_PATH", tmp_path / "heartbeat-candidates-pending-review.md"
    )
    monkeypatch.setattr(
        goat_config, "GOAT_INSIDER_SCAN_REPORT_PATH", tmp_path / "insider-scan-report.md"
    )
    monkeypatch.setattr(
        goat_config, "GOAT_HORMUZ_REPORT_PATH", tmp_path / "hormuz-risk-report.md"
    )
    monkeypatch.setattr(
        goat_config, "GOAT_INSIDER_PATTERN_ANALYSIS_PATH", tmp_path / "insider-pattern-analysis.md"
    )


@pytest.fixture(autouse=True)
def _no_real_price_history_fetch(monkeypatch):
    """Global stub so no test in this suite makes a real yfinance call by
    default -- same class of bug my-trader's conftest.py fixtures exist to
    prevent (see that file's docstrings for the real-corruption incident this
    pattern defends against). Individual tests override with monkeypatch as
    needed."""
    monkeypatch.setattr("goat.price_history.fetch_close_history", lambda ticker, lookback_days: None)
