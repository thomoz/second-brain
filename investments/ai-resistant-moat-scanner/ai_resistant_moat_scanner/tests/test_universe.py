from __future__ import annotations

import pytest

from mytrader import finviz_screener

from ai_resistant_moat_scanner import config, db, universe
from ai_resistant_moat_scanner.tests.conftest import FIXTURES

# conftest._no_real_network stubs finviz_screener.fetch_screener_universe -- restore
# the real (pagination) implementation for this file and drive it via _fetch_page.
_REAL_FETCH_UNIVERSE = finviz_screener.fetch_screener_universe


@pytest.fixture(autouse=True)
def _restore_real_fetch_universe(monkeypatch):
    monkeypatch.setattr(finviz_screener, "fetch_screener_universe", _REAL_FETCH_UNIVERSE)
    monkeypatch.setattr(
        "ai_resistant_moat_scanner.universe.finviz_screener.fetch_screener_universe",
        _REAL_FETCH_UNIVERSE,
    )


def test_fetch_screened_universe_parses_fixture_and_filters_to_target_industries(monkeypatch):
    html = (FIXTURES / "finviz_moat_screener_page.html").read_text(encoding="utf-8")
    monkeypatch.setattr(finviz_screener, "_fetch_page", lambda *a, **k: html)
    monkeypatch.setattr(finviz_screener.time, "sleep", lambda *_: None)

    rows = universe.fetch_screened_universe()
    assert rows, "fixture should yield at least one target-industry row"
    assert all(r["industry"] in config.MOAT_TARGET_INDUSTRIES for r in rows)
    assert all(r["ticker"] and r["ticker"].isalnum() for r in rows)


def test_fetch_screened_universe_none_when_every_screen_fails(monkeypatch):
    monkeypatch.setattr(finviz_screener, "_fetch_page", lambda *a, **k: None)
    monkeypatch.setattr(finviz_screener.time, "sleep", lambda *_: None)
    assert universe.fetch_screened_universe() is None


def test_universe_cache_stale_fallback(db_conn, monkeypatch):
    db.replace_universe_cache(db_conn, [
        {"ticker": "CRM", "company": "Salesforce", "industry": "Software - Application", "sector": "Technology"},
    ])
    # Force staleness + make the refresh fail; cached rows must still come back.
    monkeypatch.setattr(config, "MOAT_UNIVERSE_CACHE_TTL_DAYS", -1)
    monkeypatch.setattr(universe, "fetch_screened_universe", lambda: None)

    rows, finviz_failed = universe.get_or_refresh_screened_universe(db_conn)
    assert [r["ticker"] for r in rows] == ["CRM"]
    assert finviz_failed is False  # a cache existed, so not a hard failure


def test_get_scan_universe_finviz_failed_when_no_cache(db_conn, monkeypatch):
    monkeypatch.setattr(universe, "fetch_screened_universe", lambda: None)
    result = universe.get_scan_universe(db_conn)
    assert result["screened"] == []
    assert result["finviz_failed"] is True
    assert result["seed"] == list(config.MOAT_SEED_TICKERS)


def test_slice_math_partitions_whole_set_over_n_days(db_conn, monkeypatch):
    rows = [
        {"ticker": f"T{i:03d}", "company": "c", "industry": "Software - Application", "sector": "Technology"}
        for i in range(23)
    ]
    monkeypatch.setattr(universe, "fetch_screened_universe", lambda: rows)
    monkeypatch.setattr(config, "MOAT_UNIVERSE_CACHE_TTL_DAYS", -1)

    all_tickers = sorted(r["ticker"] for r in rows)
    covered: set[str] = set()
    n = config.MOAT_UNIVERSE_SLICES
    for idx in range(n):
        slice_i = all_tickers[idx::n]
        assert not (set(slice_i) & covered)  # disjoint
        covered |= set(slice_i)
    assert covered == set(all_tickers)

    result = universe.get_scan_universe(db_conn)
    assert 0 <= result["slice_index"] < n
    assert set(result["slice_today"]) <= set(all_tickers)
