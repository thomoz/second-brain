from __future__ import annotations

from volume_earnings_scanner import config, db, universe

_SCREEN_1_ROWS = [
    {"ticker": "AAA", "company": "AAA Inc", "market_cap_text": "100.00M"},
    {"ticker": "SHARED", "company": "Shared Co", "market_cap_text": "200.00M"},
]
_SCREEN_2_ROWS = [
    {"ticker": "BBB", "company": "BBB Inc", "market_cap_text": "500.00M"},
    {"ticker": "SHARED", "company": "Shared Co (dup)", "market_cap_text": "200.00M"},
]


def test_fetch_screened_universe_merges_and_dedupes(monkeypatch):
    calls = iter([_SCREEN_1_ROWS, _SCREEN_2_ROWS])
    monkeypatch.setattr(
        "mytrader.finviz_screener.fetch_screener_universe", lambda *a, **k: next(calls)
    )
    rows = universe.fetch_screened_universe()
    assert {r["ticker"] for r in rows} == {"AAA", "SHARED", "BBB"}
    # first screen's copy of a shared ticker wins (setdefault)
    shared = next(r for r in rows if r["ticker"] == "SHARED")
    assert shared["company"] == "Shared Co"


def test_fetch_screened_universe_returns_none_only_if_all_screens_fail(monkeypatch):
    monkeypatch.setattr("mytrader.finviz_screener.fetch_screener_universe", lambda *a, **k: None)
    assert universe.fetch_screened_universe() is None


def test_fetch_screened_universe_partial_failure_still_returns_rows(monkeypatch):
    calls = iter([_SCREEN_1_ROWS, None])
    monkeypatch.setattr(
        "mytrader.finviz_screener.fetch_screener_universe", lambda *a, **k: next(calls)
    )
    rows = universe.fetch_screened_universe()
    assert {r["ticker"] for r in rows} == {"AAA", "SHARED"}


def test_get_or_refresh_screened_universe_falls_back_to_stale_cache(db_conn, monkeypatch):
    db.replace_universe_cache(db_conn, [{"ticker": "OLD", "company": "Old Co", "market_cap_text": "1.00M"}])
    monkeypatch.setattr(universe, "fetch_screened_universe", lambda: None)

    rows, finviz_failed = universe.get_or_refresh_screened_universe(db_conn)
    assert finviz_failed is False  # cache existed, so not a hard failure
    assert {r["ticker"] for r in rows} == {"OLD"}


def test_get_or_refresh_screened_universe_fails_with_no_cache(db_conn, monkeypatch):
    monkeypatch.setattr(universe, "fetch_screened_universe", lambda: None)
    rows, finviz_failed = universe.get_or_refresh_screened_universe(db_conn)
    assert rows == []
    assert finviz_failed is True


def test_get_scan_universe_slices_deterministically(db_conn, monkeypatch):
    db.replace_universe_cache(db_conn, [
        {"ticker": t, "company": "", "market_cap_text": ""} for t in ("AAA", "BBB", "CCC", "DDD", "EEE")
    ])
    monkeypatch.setattr(config, "VE_UNIVERSE_SLICES", 5)
    result = universe.get_scan_universe(db_conn)
    assert len(result["screened"]) == 5
    assert 0 <= result["slice_index"] < 5
    assert len(result["slice_today"]) == 1  # 5 names / 5 slices
