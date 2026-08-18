from __future__ import annotations

from fourteen_crash_signals_daily_check import config, market_cap_milestone

_WATCHLIST = [
    {"ticker": "SMALL", "sector_label": "Energy", "market_cap": 200_000_000_000.0, "rank": 2},
    {"ticker": "BIG", "sector_label": "Technology", "market_cap": 3_200_000_000_000.0, "rank": 1},
]


def test_check_market_cap_milestone_selects_correct_leader():
    result = market_cap_milestone.check_market_cap_milestone(_WATCHLIST)
    assert result.data["ticker"] == "BIG"
    assert result.verdict == "flag"


def test_check_market_cap_milestone_computes_correct_rung():
    result = market_cap_milestone.check_market_cap_milestone(_WATCHLIST)
    expected_rung = 6 * config.SIGNALS_MARKET_CAP_MILESTONE_STEP  # 3.2T -> $3.0T rung (500B steps)
    assert result.data["rung"] == expected_rung


def test_check_market_cap_milestone_unknown_when_watchlist_empty():
    result = market_cap_milestone.check_market_cap_milestone([])
    assert result.verdict == "unknown"


def test_check_market_cap_milestone_works_with_sqlite_rows(db_conn):
    from fourteen_crash_signals_daily_check import db

    db.replace_hot_watchlist(db_conn, [
        {"ticker": "NVDA", "sector_label": "Technology", "market_cap": 5_000_000_000_000.0, "rank": 1},
        {"ticker": "MSFT", "sector_label": "Technology", "market_cap": 3_000_000_000_000.0, "rank": 2},
    ])
    rows = db.get_hot_watchlist(db_conn)
    result = market_cap_milestone.check_market_cap_milestone(rows)
    assert result.data["ticker"] == "NVDA"
