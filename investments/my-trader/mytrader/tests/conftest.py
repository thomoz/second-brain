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


@pytest.fixture(autouse=True)
def _no_real_crash_drawdown_fetch(monkeypatch):
    """engine.run_assessment() calls checks/crash_resilience.check(), which does its
    own multi-year yfinance history() fetch via crash_windows.fetch_crash_drawdowns()
    — global/autouse for the same reason as the two fixtures above."""
    monkeypatch.setattr("mytrader.checks.crash_resilience.crash_windows.fetch_crash_drawdowns", lambda ticker: None)


@pytest.fixture(autouse=True)
def _no_real_sec_filing_fetch(monkeypatch):
    """principles_fit.check() calls sec_filings.get_filing_summaries_for_ticker(),
    which does real SEC EDGAR HTTP + LLM calls when conn is not None -- global/autouse
    for the same reason as the three fixtures above: don't let a real network/LLM
    call hit every test in the suite that exercises the real check by default."""
    monkeypatch.setattr(
        "mytrader.checks.principles_fit.sec_filings.get_filing_summaries_for_ticker",
        lambda ticker, conn: None,
    )


@pytest.fixture(autouse=True)
def _no_real_asx_announcement_fetch(monkeypatch):
    """principles_fit.check() calls asx_announcements.get_announcement_summaries_
    for_ticker(), which does real ASX HTTP + LLM calls when conn is not None --
    global/autouse for the same reason as _no_real_sec_filing_fetch above."""
    monkeypatch.setattr(
        "mytrader.checks.principles_fit.asx_announcements.get_announcement_summaries_for_ticker",
        lambda ticker, conn: None,
    )


@pytest.fixture(autouse=True)
def _no_real_etf_funds_data_fetch(monkeypatch):
    """etf_mechanics.check() calls _fetch_funds_data() for every ETF ticker (top
    holdings/sector weightings context, added 2026-08-04) -- a real yfinance network
    call -- global/autouse for the same reason as the fixtures above."""
    monkeypatch.setattr("mytrader.checks.etf_mechanics._fetch_funds_data", lambda ticker: None)


@pytest.fixture(autouse=True)
def _no_real_news_events_search(monkeypatch):
    """checks/news_events.check() calls news_search.get_news_events_for_ticker(),
    which does a real sdk_compat WebSearch+LLM call when conn is not None --
    global/autouse for the same reason as _no_real_sec_filing_fetch above."""
    monkeypatch.setattr(
        "mytrader.checks.news_events.news_search.get_news_events_for_ticker",
        lambda ticker, conn: None,
    )


@pytest.fixture(autouse=True)
def _no_real_balance_sheet_statement_fetch(monkeypatch):
    """checks/balance_sheet.check() calls market_data.fetch_balance_sheet_financials()
    as a second-tier ROE fallback (added 2026-08-06) whenever .info has none of
    debtToEquity/currentRatio/returnOnEquity -- a real yfinance network call --
    global/autouse for the same reason as the fixtures above."""
    monkeypatch.setattr("mytrader.market_data.fetch_balance_sheet_financials", lambda ticker: None)


@pytest.fixture(autouse=True)
def _no_real_cot_fetch(monkeypatch):
    """gold_outlook.build_outlook() calls gold_cot.check_cot_positioning() every
    run (added 2026-08-08), which does a real CFTC network fetch when not
    stubbed -- global/autouse for the same reason as the fixtures above: don't
    let a real network call hit every test in the suite that exercises
    build_outlook by default. Patches the underlying fetch (not
    check_cot_positioning itself), so test_gold_cot.py's own direct tests of
    check_cot_positioning/compute_today_cot -- which patch those functions
    directly -- aren't clobbered by this fixture running first."""
    monkeypatch.setattr("mytrader.gold_cot._fetch_cot_history", lambda: None)


@pytest.fixture(autouse=True)
def _no_real_technical_levels_fetch(monkeypatch):
    """engine.run_assessment() calls checks/technical_levels.check() (added
    2026-08-13), which does its own yfinance history() fetch via
    technical_levels._fetch_close_series() -- global/autouse for the same reason as
    _no_real_crash_drawdown_fetch above."""
    monkeypatch.setattr("mytrader.checks.technical_levels._fetch_close_series", lambda ticker: None)


@pytest.fixture(autouse=True)
def _no_real_ibkr_connection(monkeypatch):
    """ibkr_sync fetch functions connect to a real local IB Gateway socket via
    ib_async -- there is no CI/local Gateway running during pytest, so an unstubbed
    real call would hang or error. Stubbing _connect() (the sole real-I/O boundary,
    same shape as gold_cot._fetch_cot_history) means tests that exercise
    fetch_positions()/fetch_account_summary() directly still need their own
    monkeypatch of ib.positions()/ib.accountSummary() -- this fixture only prevents
    an accidental real socket connection from any test in the suite by default."""

    def _raise_no_gateway():
        raise ConnectionError("no real IB Gateway available in tests")

    monkeypatch.setattr("mytrader.ibkr_sync._connect", _raise_no_gateway)
