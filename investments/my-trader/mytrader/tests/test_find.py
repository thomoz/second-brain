from __future__ import annotations

from mytrader import find


def _patch_snapshot(monkeypatch, tmp_path):
    import mytrader.config as mt_config
    monkeypatch.setattr(mt_config, "HOLDINGS_MD_PATH", tmp_path / "holdings.md")
    monkeypatch.setattr(mt_config, "WATCHLIST_MD_PATH", tmp_path / "watchlist.md")
    monkeypatch.setattr(mt_config, "PENDING_CANDIDATES_MD_PATH", tmp_path / "synced-candidates-pending-review.md")
    monkeypatch.setattr("mytrader.market_data.fetch_ticker_data", lambda ticker: None)


def test_lookup_ticker_persists_nothing(db_conn, monkeypatch):
    monkeypatch.setattr("mytrader.market_data.fetch_ticker_data", lambda ticker: None)
    find.lookup_ticker("VRTX", db_conn)
    assert db_conn.execute("SELECT COUNT(*) AS n FROM watchlist").fetchone()["n"] == 0
    assert db_conn.execute("SELECT COUNT(*) AS n FROM holdings").fetchone()["n"] == 0


def test_add_to_watchlist_persists_row(db_conn, monkeypatch, tmp_path):
    _patch_snapshot(monkeypatch, tmp_path)
    find.add_to_watchlist("vrtx", "Vertex Pharmaceuticals", "stock", "1", "test notes", db_conn)

    row = db_conn.execute("SELECT * FROM watchlist WHERE ticker = 'VRTX'").fetchone()
    assert row is not None
    assert row["status"] == "discussed"
    assert row["notes"] == "test notes"
    assert (tmp_path / "watchlist.md").exists()


def test_add_to_watchlist_upserts_not_duplicates(db_conn, monkeypatch, tmp_path):
    _patch_snapshot(monkeypatch, tmp_path)
    find.add_to_watchlist("VRTX", "Vertex Pharmaceuticals", "stock", "1", "first", db_conn)
    find.add_to_watchlist("VRTX", "Vertex Pharmaceuticals", "stock", "1", "second", db_conn)

    rows = db_conn.execute("SELECT * FROM watchlist WHERE ticker = 'VRTX'").fetchall()
    assert len(rows) == 1
    assert rows[0]["notes"] == "second"
