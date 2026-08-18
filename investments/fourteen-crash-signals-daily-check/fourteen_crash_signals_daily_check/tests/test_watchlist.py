from __future__ import annotations

from mytrader.market_data import TickerData

from fourteen_crash_signals_daily_check import config, watchlist

_RISING_RANKING = [{"ticker": "XLK", "sector_label": "Technology", "return_pct": 10.0, "rising": True}]

_CONSTITUENTS = [
    {"ticker": "MEGA", "security": "Mega Corp", "gics_sector": "Information Technology", "fetched_at": "x"},
    {"ticker": "SMALL", "security": "Small Corp", "gics_sector": "Information Technology", "fetched_at": "x"},
    {"ticker": "XOM", "security": "Exxon Mobil", "gics_sector": "Energy", "fetched_at": "x"},
]

_CAPS = {
    "MEGA": 3_000_000_000_000,
    "SMALL": 10_000_000_000,  # below the $100B mega-cap floor
}


def _fake_ticker_data(ticker):
    cap = _CAPS.get(ticker)
    if cap is None:
        return None
    return TickerData(ticker=ticker, info={"marketCap": cap}, dividends=None)


def _patch_common(monkeypatch, constituents=None, ticker_data=None):
    monkeypatch.setattr("fourteen_crash_signals_daily_check.watchlist.sector_rotation.fetch_all_sector_closes", lambda: {})
    monkeypatch.setattr("fourteen_crash_signals_daily_check.watchlist.sector_rotation.rank_sectors", lambda closes: _RISING_RANKING)
    monkeypatch.setattr(
        "fourteen_crash_signals_daily_check.watchlist.sp500_universe.get_or_refresh_sp500_constituents",
        lambda conn: constituents if constituents is not None else _CONSTITUENTS,
    )
    monkeypatch.setattr(
        "fourteen_crash_signals_daily_check.watchlist.market_data.fetch_ticker_data",
        ticker_data if ticker_data is not None else _fake_ticker_data,
    )


def test_compute_hot_watchlist_filters_by_rising_sector_and_market_cap(db_conn, monkeypatch):
    _patch_common(monkeypatch)
    rows = watchlist.compute_hot_watchlist(db_conn)
    assert [r["ticker"] for r in rows] == ["MEGA"]  # SMALL below floor, XOM not in a rising sector


def test_compute_hot_watchlist_ranks_by_market_cap_descending(db_conn, monkeypatch):
    constituents = [
        {"ticker": "A", "security": "A", "gics_sector": "Information Technology", "fetched_at": "x"},
        {"ticker": "B", "security": "B", "gics_sector": "Information Technology", "fetched_at": "x"},
    ]
    caps = {"A": 200_000_000_000, "B": 400_000_000_000}
    _patch_common(monkeypatch, constituents=constituents, ticker_data=lambda t: TickerData(ticker=t, info={"marketCap": caps[t]}, dividends=None))
    rows = watchlist.compute_hot_watchlist(db_conn)
    assert [r["ticker"] for r in rows] == ["B", "A"]
    assert [r["rank"] for r in rows] == [1, 2]


def test_compute_hot_watchlist_truncates_to_top_n(db_conn, monkeypatch):
    constituents = [
        {"ticker": f"T{i}", "security": f"T{i}", "gics_sector": "Information Technology", "fetched_at": "x"}
        for i in range(config.SIGNALS_HOT_WATCHLIST_TOP_N + 3)
    ]
    _patch_common(
        monkeypatch, constituents=constituents,
        ticker_data=lambda t: TickerData(ticker=t, info={"marketCap": 200_000_000_000}, dividends=None),
    )
    rows = watchlist.compute_hot_watchlist(db_conn)
    assert len(rows) == config.SIGNALS_HOT_WATCHLIST_TOP_N


def test_compute_hot_watchlist_empty_when_no_rising_sectors(db_conn, monkeypatch):
    monkeypatch.setattr("fourteen_crash_signals_daily_check.watchlist.sector_rotation.fetch_all_sector_closes", lambda: {})
    monkeypatch.setattr("fourteen_crash_signals_daily_check.watchlist.sector_rotation.rank_sectors", lambda closes: [])
    monkeypatch.setattr(
        "fourteen_crash_signals_daily_check.watchlist.sp500_universe.get_or_refresh_sp500_constituents",
        lambda conn: _CONSTITUENTS,
    )
    rows = watchlist.compute_hot_watchlist(db_conn)
    assert rows == []


def test_get_or_refresh_hot_watchlist_persists_to_db(db_conn, monkeypatch):
    _patch_common(monkeypatch)
    rows = watchlist.get_or_refresh_hot_watchlist(db_conn)
    assert [r["ticker"] for r in rows] == ["MEGA"]
