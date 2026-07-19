from __future__ import annotations

from mytrader import db, snapshot
from mytrader.market_data import TickerData


def _patch_paths(monkeypatch, tmp_path):
    import mytrader.config as mt_config
    holdings_path = tmp_path / "holdings.md"
    watchlist_path = tmp_path / "potential-holdings.md"
    monkeypatch.setattr(mt_config, "HOLDINGS_MD_PATH", holdings_path)
    monkeypatch.setattr(mt_config, "WATCHLIST_MD_PATH", watchlist_path)
    return holdings_path, watchlist_path


def test_regenerate_holdings_md_matches_expected(db_conn, monkeypatch, tmp_path):
    holdings_path, _ = _patch_paths(monkeypatch, tmp_path)
    monkeypatch.setattr(
        "mytrader.market_data.fetch_ticker_data",
        lambda ticker: TickerData(ticker=ticker, info={"regularMarketPrice": 340.0}, dividends=None),
    )

    db.upsert_holding(db_conn, ticker="V", name="Visa Inc", asset_type="stock", bucket="1", qty=0.1, avg_price=318.41)
    snapshot.regenerate_holdings_md(db_conn)

    content = holdings_path.read_text(encoding="utf-8")
    assert "| V | Visa Inc | 0.1 | $34.00 | $318.41 | +$2.16 | 1 |" in content
    assert "Last auto-generated:" in content


def test_regenerate_holdings_md_handles_missing_price(db_conn, monkeypatch, tmp_path):
    holdings_path, _ = _patch_paths(monkeypatch, tmp_path)
    monkeypatch.setattr("mytrader.market_data.fetch_ticker_data", lambda ticker: None)

    db.upsert_holding(db_conn, ticker="V", name="Visa Inc", asset_type="stock", bucket="1", qty=0.1, avg_price=318.41)
    snapshot.regenerate_holdings_md(db_conn)

    content = holdings_path.read_text(encoding="utf-8")
    assert "| V | Visa Inc | 0.1 | — | $318.41 | — | 1 |" in content


def test_regenerate_watchlist_md_matches_expected(db_conn, monkeypatch, tmp_path):
    _, watchlist_path = _patch_paths(monkeypatch, tmp_path)

    db.upsert_watchlist_row(
        db_conn, ticker="VRTX", name="Vertex Pharmaceuticals Inc", asset_type="stock", bucket="1",
        status="discussed", notes="Good candidate",
    )
    snapshot.regenerate_watchlist_md(db_conn)

    content = watchlist_path.read_text(encoding="utf-8")
    assert "| VRTX | Vertex Pharmaceuticals Inc | stock | 1 | — | — | Good candidate |" in content


def test_regenerate_watchlist_md_raw_status_placeholder(db_conn, monkeypatch, tmp_path):
    _, watchlist_path = _patch_paths(monkeypatch, tmp_path)

    db.upsert_watchlist_row(
        db_conn, ticker="DG", name="Dollar General", asset_type="stock", bucket="1",
    )
    snapshot.regenerate_watchlist_md(db_conn)

    content = watchlist_path.read_text(encoding="utf-8")
    assert "| DG | Dollar General | stock | 1 | — | — | Not yet discussed |" in content


def test_regenerate_all_writes_both_files(db_conn, monkeypatch, tmp_path):
    holdings_path, watchlist_path = _patch_paths(monkeypatch, tmp_path)
    monkeypatch.setattr("mytrader.market_data.fetch_ticker_data", lambda ticker: None)

    snapshot.regenerate_all(db_conn)

    assert holdings_path.exists()
    assert watchlist_path.exists()
