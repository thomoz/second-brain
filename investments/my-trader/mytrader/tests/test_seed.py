from __future__ import annotations

from mytrader import db, seed


def _patch(monkeypatch, tmp_path):
    import mytrader.config as mt_config
    monkeypatch.setattr(mt_config, "HOLDINGS_MD_PATH", tmp_path / "holdings.md")
    monkeypatch.setattr(mt_config, "WATCHLIST_MD_PATH", tmp_path / "watchlist.md")
    monkeypatch.setattr("mytrader.market_data.fetch_ticker_data", lambda ticker: None)


def test_seed_confirmed_holdings_inserts_expected_rows(db_conn, monkeypatch, tmp_path):
    _patch(monkeypatch, tmp_path)
    seed.seed_confirmed_holdings(db_conn)

    holdings = db.get_all_holdings(db_conn)
    watchlist = db.get_all_watchlist(db_conn)
    assert len(holdings) == 3
    assert len(watchlist) == len(seed._WATCHLIST) + len(seed._RAW_WATCHLIST)

    tickers_seen = {row["ticker"] for row in holdings}
    assert tickers_seen == {"LLY", "LYV", "V"}

    assert db.get_watchlist_row(db_conn, "BRK-B", "1") is not None
    assert db.get_watchlist_row(db_conn, "PMGOLD", "3a") is not None
    assert db.get_watchlist_row(db_conn, "PMGOLD", "3b") is not None

    discussed = [row for row in watchlist if row["status"] == "discussed"]
    raw = [row for row in watchlist if row["status"] == "raw"]
    assert len(discussed) == len(seed._WATCHLIST)
    assert len(raw) == len(seed._RAW_WATCHLIST)

    dg = db.get_watchlist_row(db_conn, "DG", "1")
    assert dg is not None
    assert dg["status"] == "raw"

    voo = db.get_watchlist_row(db_conn, "VOO", "1")
    vti = db.get_watchlist_row(db_conn, "VTI", "1")
    assert voo is not None
    assert vti is not None


def test_seed_confirmed_holdings_is_idempotent(db_conn, monkeypatch, tmp_path):
    _patch(monkeypatch, tmp_path)
    seed.seed_confirmed_holdings(db_conn)
    seed.seed_confirmed_holdings(db_conn)

    assert len(db.get_all_holdings(db_conn)) == 3
    assert len(db.get_all_watchlist(db_conn)) == len(seed._WATCHLIST) + len(seed._RAW_WATCHLIST)
