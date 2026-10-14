"""Shared fixtures for Volume-Earnings Scanner tests. Mirrors
ai_resistant_moat_scanner/tests/conftest.py's shape: tmp_path-backed DB, report
paths isolated to tmp_path, and every network entrypoint stubbed by default.

No LLM calls anywhere in this package (unlike the moat scanner), so no
`_raising_run_text` stub is needed."""

from __future__ import annotations

from pathlib import Path

import pytest
from scripts.db import get_connection, init_db

from mytrader.db import init_mytrader_tables

from volume_earnings_scanner.db import init_ve_tables

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def db_path(tmp_path) -> Path:
    return tmp_path / "test_investments.db"


@pytest.fixture
def db_conn(db_path):
    init_db(db_path)
    conn = get_connection(db_path)
    init_mytrader_tables(conn)
    init_ve_tables(conn)
    yield conn
    conn.close()


@pytest.fixture(autouse=True)
def _isolate_report_paths(monkeypatch, tmp_path):
    import volume_earnings_scanner.config as cfg

    monkeypatch.setattr(cfg, "VE_CANDIDATES_MD_PATH", tmp_path / "volume-earnings-candidates-pending-review.md")
    monkeypatch.setattr(cfg, "VE_FETCH_DELAY_SECONDS", 0)
    monkeypatch.setattr(cfg, "VE_FINVIZ_REQUEST_DELAY_SECONDS", 0)


@pytest.fixture(autouse=True)
def _no_real_network(monkeypatch):
    """Default-safe stubs for any test that doesn't explicitly wire its own fakes.
    Deliberately does NOT stub price_history.fetch_close_volume_history or
    earnings_signal.fetch_quarterly_eps_history at this module level -- those are
    the two functions test_price_history.py/test_earnings_signal.py directly unit
    test, each by mocking the lower-level mytrader.yf_retry.call instead (real
    network is still never reached; see those files). scan.py's own tests
    (test_scan.py) explicitly monkeypatch both via their _wire() helper."""
    monkeypatch.setattr(
        "mytrader.finviz_screener.fetch_screener_universe", lambda *a, **k: None
    )
    monkeypatch.setattr("mytrader.market_data.fetch_ticker_data", lambda *a, **k: None)
