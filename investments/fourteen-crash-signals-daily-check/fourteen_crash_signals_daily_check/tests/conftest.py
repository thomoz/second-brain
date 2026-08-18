from __future__ import annotations

import pytest
from scripts.db import get_connection, init_db

from goat.db import init_goat_tables
from mytrader.db import init_mytrader_tables

from fourteen_crash_signals_daily_check.db import init_signals_tables


@pytest.fixture
def db_conn(tmp_path):
    db_path = tmp_path / "test_investments.db"
    init_db(db_path)
    conn = get_connection(db_path)
    init_mytrader_tables(conn)
    init_goat_tables(conn)
    init_signals_tables(conn)
    yield conn
    conn.close()


@pytest.fixture(autouse=True)
def _isolate_signals_report_path(monkeypatch, tmp_path):
    import fourteen_crash_signals_daily_check.config as signals_config
    monkeypatch.setattr(signals_config, "SIGNALS_REPORT_PATH", tmp_path / "signals-report.md")
