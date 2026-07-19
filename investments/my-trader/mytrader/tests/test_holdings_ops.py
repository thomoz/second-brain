from __future__ import annotations

import pytest

from mytrader import db, holdings_ops


def _patch_snapshot(monkeypatch, tmp_path):
    import mytrader.config as mt_config
    monkeypatch.setattr(mt_config, "HOLDINGS_MD_PATH", tmp_path / "holdings.md")
    monkeypatch.setattr(mt_config, "WATCHLIST_MD_PATH", tmp_path / "potential-holdings.md")
    monkeypatch.setattr("mytrader.market_data.fetch_ticker_data", lambda ticker: None)


def test_buy_creates_new_holding(db_conn, monkeypatch, tmp_path):
    _patch_snapshot(monkeypatch, tmp_path)
    holdings_ops.add_or_update_holding(
        "V", "1", 0.1, 340.0, "buy", db_conn, name="Visa Inc", asset_type="stock"
    )
    row = db.get_holding_row(db_conn, "V", "1")
    assert row["qty"] == 0.1
    assert row["avg_price"] == 340.0


def test_buy_then_buy_computes_weighted_average(db_conn, monkeypatch, tmp_path):
    _patch_snapshot(monkeypatch, tmp_path)
    holdings_ops.add_or_update_holding(
        "V", "1", 0.1, 300.0, "buy", db_conn, name="Visa Inc", asset_type="stock"
    )
    holdings_ops.add_or_update_holding("V", "1", 0.1, 340.0, "buy", db_conn)
    row = db.get_holding_row(db_conn, "V", "1")
    assert row["qty"] == pytest.approx(0.2)
    assert row["avg_price"] == pytest.approx(320.0)


def test_sell_reduces_qty(db_conn, monkeypatch, tmp_path):
    _patch_snapshot(monkeypatch, tmp_path)
    holdings_ops.add_or_update_holding(
        "V", "1", 0.2, 300.0, "buy", db_conn, name="Visa Inc", asset_type="stock"
    )
    holdings_ops.add_or_update_holding("V", "1", 0.05, 350.0, "sell", db_conn)
    row = db.get_holding_row(db_conn, "V", "1")
    assert row["qty"] == pytest.approx(0.15)


def test_sell_to_zero_removes_row(db_conn, monkeypatch, tmp_path):
    _patch_snapshot(monkeypatch, tmp_path)
    holdings_ops.add_or_update_holding(
        "LLY", "1", 0.0001, 1148.0, "buy", db_conn, name="Eli Lilly", asset_type="stock"
    )
    holdings_ops.add_or_update_holding("LLY", "1", 0.0001, 1200.0, "sell", db_conn)
    assert db.get_holding_row(db_conn, "LLY", "1") is None


def test_sell_without_existing_holding_raises(db_conn, monkeypatch, tmp_path):
    _patch_snapshot(monkeypatch, tmp_path)
    with pytest.raises(ValueError):
        holdings_ops.add_or_update_holding("XYZ", "1", 1.0, 10.0, "sell", db_conn)


def test_invalid_action_raises(db_conn, monkeypatch, tmp_path):
    _patch_snapshot(monkeypatch, tmp_path)
    with pytest.raises(ValueError):
        holdings_ops.add_or_update_holding("V", "1", 1.0, 10.0, "hold", db_conn)


def test_same_ticker_two_buckets_tracked_separately(db_conn, monkeypatch, tmp_path):
    _patch_snapshot(monkeypatch, tmp_path)
    holdings_ops.add_or_update_holding(
        "PMGOLD", "3a", 10.0, 57.56, "buy", db_conn, name="Perth Mint Gold", asset_type="etf"
    )
    holdings_ops.add_or_update_holding(
        "PMGOLD", "3b", 5.0, 57.56, "buy", db_conn, name="Perth Mint Gold", asset_type="etf"
    )
    core = db.get_holding_row(db_conn, "PMGOLD", "3a")
    tactical = db.get_holding_row(db_conn, "PMGOLD", "3b")
    assert core["qty"] == 10.0
    assert tactical["qty"] == 5.0
