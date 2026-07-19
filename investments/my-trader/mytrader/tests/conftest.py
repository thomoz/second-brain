"""Shared fixtures for my-trader tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from scripts.db import get_connection, init_db

from mytrader.db import init_mytrader_tables


@pytest.fixture
def db_path(tmp_path) -> Path:
    """tmp_path-backed SQLite DB for testing — never the real shared investments.db."""
    return tmp_path / "test_investments.db"


@pytest.fixture
def db_conn(db_path):
    """Initialised test DB connection with both briefs-finance and mytrader tables."""
    init_db(db_path)
    conn = get_connection(db_path)
    init_mytrader_tables(conn)
    yield conn
    conn.close()
