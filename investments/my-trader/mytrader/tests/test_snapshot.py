from __future__ import annotations

from mytrader import db, snapshot
from mytrader.market_data import TickerData


def _patch_paths(monkeypatch, tmp_path):
    import mytrader.config as mt_config
    holdings_path = tmp_path / "holdings.md"
    watchlist_path = tmp_path / "watchlist.md"
    pending_path = tmp_path / "synced-candidates-pending-review.md"
    monkeypatch.setattr(mt_config, "HOLDINGS_MD_PATH", holdings_path)
    monkeypatch.setattr(mt_config, "WATCHLIST_MD_PATH", watchlist_path)
    monkeypatch.setattr(mt_config, "PENDING_CANDIDATES_MD_PATH", pending_path)
    return holdings_path, watchlist_path, pending_path


def test_regenerate_holdings_md_matches_expected(db_conn, monkeypatch, tmp_path):
    holdings_path, _, _ = _patch_paths(monkeypatch, tmp_path)
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
    holdings_path, _, _ = _patch_paths(monkeypatch, tmp_path)
    monkeypatch.setattr("mytrader.market_data.fetch_ticker_data", lambda ticker: None)

    db.upsert_holding(db_conn, ticker="V", name="Visa Inc", asset_type="stock", bucket="1", qty=0.1, avg_price=318.41)
    snapshot.regenerate_holdings_md(db_conn)

    content = holdings_path.read_text(encoding="utf-8")
    assert "| V | Visa Inc | 0.1 | — | $318.41 | — | 1 |" in content


def test_regenerate_holdings_md_records_price_snapshot(db_conn, monkeypatch, tmp_path):
    _patch_paths(monkeypatch, tmp_path)
    monkeypatch.setattr(
        "mytrader.market_data.fetch_ticker_data",
        lambda ticker: TickerData(ticker=ticker, info={"regularMarketPrice": 340.0}, dividends=None),
    )

    db.upsert_holding(db_conn, ticker="V", name="Visa Inc", asset_type="stock", bucket="1", qty=0.1, avg_price=318.41)
    snapshot.regenerate_holdings_md(db_conn)

    rows = db.get_price_history(db_conn, "V", "1")
    assert len(rows) == 1
    assert rows[0]["price"] == 340.0
    assert rows[0]["qty"] == 0.1
    assert rows[0]["mkt_value"] == 34.0


def test_regenerate_holdings_md_skips_price_snapshot_when_price_missing(db_conn, monkeypatch, tmp_path):
    _patch_paths(monkeypatch, tmp_path)
    monkeypatch.setattr("mytrader.market_data.fetch_ticker_data", lambda ticker: None)

    db.upsert_holding(db_conn, ticker="V", name="Visa Inc", asset_type="stock", bucket="1", qty=0.1, avg_price=318.41)
    snapshot.regenerate_holdings_md(db_conn)

    assert db.get_price_history(db_conn, "V", "1") == []


def test_regenerate_watchlist_md_matches_expected(db_conn, monkeypatch, tmp_path):
    _, watchlist_path, _ = _patch_paths(monkeypatch, tmp_path)

    db.upsert_watchlist_row(
        db_conn, ticker="VRTX", name="Vertex Pharmaceuticals Inc", asset_type="stock", bucket="1",
        status="discussed", notes="Good candidate",
    )
    snapshot.regenerate_watchlist_md(db_conn)

    content = watchlist_path.read_text(encoding="utf-8")
    assert "| VRTX | Vertex Pharmaceuticals Inc | stock | 1 | — | — | Good candidate |" in content


def test_regenerate_watchlist_md_raw_status_placeholder(db_conn, monkeypatch, tmp_path):
    _, watchlist_path, _ = _patch_paths(monkeypatch, tmp_path)

    db.upsert_watchlist_row(
        db_conn, ticker="DG", name="Dollar General", asset_type="stock", bucket="1",
    )
    snapshot.regenerate_watchlist_md(db_conn)

    content = watchlist_path.read_text(encoding="utf-8")
    assert "| DG | Dollar General | stock | 1 | — | — | Not yet discussed |" in content


def test_regenerate_watchlist_md_splits_post_crash_ai_section(db_conn, monkeypatch, tmp_path):
    _, watchlist_path, _ = _patch_paths(monkeypatch, tmp_path)

    db.upsert_watchlist_row(
        db_conn, ticker="VRTX", name="Vertex Pharmaceuticals Inc", asset_type="stock", bucket="1",
        status="discussed", notes="Good candidate",
    )
    db.upsert_watchlist_row(
        db_conn, ticker="NVDA", name="Nvidia", asset_type="stock", bucket="ai_postcrash",
        status="raw", notes="AI boom leader",
    )
    snapshot.regenerate_watchlist_md(db_conn)

    content = watchlist_path.read_text(encoding="utf-8")
    assert "## Watchlist" in content
    assert "## Post-Crash AI Watch" in content
    watchlist_section, postcrash_section = content.split("## Post-Crash AI Watch")
    assert "VRTX" in watchlist_section
    assert "NVDA" not in watchlist_section
    assert "NVDA" in postcrash_section


def test_regenerate_watchlist_md_splits_bucket_4_section(db_conn, monkeypatch, tmp_path):
    _, watchlist_path, _ = _patch_paths(monkeypatch, tmp_path)

    db.upsert_watchlist_row(
        db_conn, ticker="VRTX", name="Vertex Pharmaceuticals Inc", asset_type="stock", bucket="1",
        status="discussed", notes="Good candidate",
    )
    db.upsert_watchlist_row(
        db_conn, ticker="KO", name="Coca-Cola Co", asset_type="stock", bucket="4",
        status="raw", notes="Buy at a crash discount",
    )
    snapshot.regenerate_watchlist_md(db_conn)

    content = watchlist_path.read_text(encoding="utf-8")
    assert "## Bucket 4 — Crash Discount Buys" in content
    watchlist_section, rest = content.split("## Bucket 4 — Crash Discount Buys")
    assert "VRTX" in watchlist_section
    assert "KO" not in watchlist_section
    assert "KO" in rest


def test_regenerate_all_writes_all_three_files(db_conn, monkeypatch, tmp_path):
    holdings_path, watchlist_path, pending_path = _patch_paths(monkeypatch, tmp_path)
    monkeypatch.setattr("mytrader.market_data.fetch_ticker_data", lambda ticker: None)

    snapshot.regenerate_all(db_conn)

    assert holdings_path.exists()
    assert watchlist_path.exists()
    assert pending_path.exists()


def test_regenerate_pending_candidates_md_lists_rows(db_conn, monkeypatch, tmp_path):
    _, _, pending_path = _patch_paths(monkeypatch, tmp_path)

    db.insert_pending_candidate(
        db_conn, ticker="NVDA", company_name="Nvidia", buy_thesis="AI chip demand",
    )
    snapshot.regenerate_pending_candidates_md(db_conn)

    content = pending_path.read_text(encoding="utf-8")
    assert "NVDA" in content
    assert "Nvidia" in content
    assert "AI chip demand" in content
    assert "promote-candidate" in content
