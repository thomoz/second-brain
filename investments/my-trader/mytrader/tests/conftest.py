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


@pytest.fixture(autouse=True)
def _isolate_snapshot_paths(monkeypatch, tmp_path):
    """Every snapshot-writing config path (HOLDINGS_MD_PATH / WATCHLIST_MD_PATH /
    PENDING_CANDIDATES_MD_PATH) is isolated to tmp_path for every test in the suite,
    globally — not a per-file opt-in helper. Found 2026-07-19: five independently
    copy-pasted per-file versions of this same patching (test_snapshot.py,
    test_monitor.py, test_find.py, test_holdings_ops.py, test_seed.py) drifted out of
    sync when PENDING_CANDIDATES_MD_PATH was added later than the other two — every
    `pytest` run was silently overwriting the real holdings.md/watchlist.md/
    synced-candidates-pending-review.md with near-empty test-fixture data, and one of
    those corrupted states even made it into a real commit. Global autouse means a
    future test file can't reintroduce this by forgetting to call a helper. The
    per-file helpers that still exist are now redundant (re-patching to the same
    value is harmless) — safe to remove in a later cleanup pass, not required for
    correctness now that this exists."""
    import mytrader.config as mt_config
    monkeypatch.setattr(mt_config, "HOLDINGS_MD_PATH", tmp_path / "holdings.md")
    monkeypatch.setattr(mt_config, "WATCHLIST_MD_PATH", tmp_path / "watchlist.md")
    monkeypatch.setattr(mt_config, "PENDING_CANDIDATES_MD_PATH", tmp_path / "synced-candidates-pending-review.md")


@pytest.fixture(autouse=True)
def _no_real_backtest_refresh(monkeypatch):
    """engine.run_assessment() calls _refresh_backtest_for_ticker(), which opens its
    OWN connection to the real shared investments.db via scripts.backtest.run_backtest
    (not the test's tmp_path-backed db_conn) — without this, any test exercising the
    real engine (not just monitor.py's tests, which mock engine.run_assessment
    entirely) would silently write real backtest data to production. Global/autouse
    so a future test file calling run_assessment doesn't reintroduce this by
    forgetting to stub it — the same class of bug as the test_monitor.py real-file
    leak found 2026-07-19."""
    monkeypatch.setattr("mytrader.engine._refresh_backtest_for_ticker", lambda ticker: None)


@pytest.fixture(autouse=True)
def _no_real_recent_return_fetch(monkeypatch):
    """engine.run_assessment() calls return_data.fetch_recent_return_pct(), a real
    yfinance network call (checks/opportunity.py's momentum signal) — global/autouse
    for the same reason as the two fixtures above: don't let a real network call hit
    every test in the suite by default."""
    monkeypatch.setattr("mytrader.engine.return_data.fetch_recent_return_pct", lambda ticker, period="3mo": None)
