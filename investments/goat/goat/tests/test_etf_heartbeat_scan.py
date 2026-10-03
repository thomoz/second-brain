from __future__ import annotations

import pandas as pd
from mytrader import db as mt_db
from mytrader.checks import CheckResult
from mytrader.market_data import TickerData

from goat import config as goat_config, db as goat_db, etf_heartbeat_scan


_FAKE_ETF_UNIVERSE = {"XLK": "Technology", "ITA": "Aerospace & Defense", "XLI": "Industrials"}


def _fake_price_volume_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {"Close": [100.0, 101.0], "Volume": [1000.0, 1100.0]},
        index=pd.date_range("2026-01-01", periods=2),
    )


def _etf_ticker_data(ticker: str = "XLK", total_assets: float = 1_000_000_000.0) -> TickerData:
    return TickerData(
        ticker=ticker,
        info={
            "quoteType": "ETF", "averageVolume": 500_000, "totalAssets": total_assets,
            "fullExchangeName": "NYSEArca",
        },
        dividends=None,
    )


def _patch_common(monkeypatch, fetch_close=None, breakout_check=None, ticker_data=None):
    monkeypatch.setattr(goat_config, "GOAT_DMA_BREAKOUT_ETF_UNIVERSE", _FAKE_ETF_UNIVERSE)
    monkeypatch.setattr(
        "goat.etf_heartbeat_scan.price_history.fetch_close_volume_history",
        fetch_close if fetch_close is not None else (lambda ticker, lookback_days: _fake_price_volume_frame()),
    )
    monkeypatch.setattr(
        "goat.etf_heartbeat_scan.heartbeat.check_heartbeat_breakout",
        breakout_check if breakout_check is not None else (
            lambda ticker, label, close, volume: CheckResult(
                name="heartbeat_breakout", verdict="interesting", detail=f"{ticker} heartbeat signal",
            )
        ),
    )
    monkeypatch.setattr(
        "goat.etf_heartbeat_scan.market_data.fetch_ticker_data",
        ticker_data if ticker_data is not None else (lambda ticker: _etf_ticker_data(ticker)),
    )


def test_run_etf_heartbeat_scan_unconditional_no_sector_filter(db_conn, monkeypatch):
    _patch_common(monkeypatch)
    result = etf_heartbeat_scan.run_etf_heartbeat_scan(db_conn)
    assert result["scanned"] == 2  # XLK + XLK's industry-sibling ITA -- XLI banned (see below)
    tickers_out = {c["ticker"] for c in result["new_candidates"]}
    assert tickers_out == {"XLK", "ITA"}


def test_run_etf_heartbeat_scan_skips_banned_ticker(db_conn, monkeypatch):
    monkeypatch.setattr(goat_config, "GOAT_BANNED_TICKERS", {"XLI"})
    _patch_common(monkeypatch)
    calls = []

    def _tracking_fetch(ticker, lookback_days):
        calls.append(ticker)
        return _fake_price_volume_frame()

    _patch_common(monkeypatch, fetch_close=_tracking_fetch)
    etf_heartbeat_scan.run_etf_heartbeat_scan(db_conn)
    assert "XLI" not in calls


def test_run_etf_heartbeat_scan_respects_aum_liquidity_floor(db_conn, monkeypatch):
    monkeypatch.setattr(goat_config, "GOAT_BANNED_TICKERS", {"XLI"})
    _patch_common(monkeypatch, ticker_data=lambda ticker: _etf_ticker_data(ticker, total_assets=1_000.0))
    result = etf_heartbeat_scan.run_etf_heartbeat_scan(db_conn)
    assert result["new_candidates"] == []


def test_run_etf_heartbeat_scan_dedups_against_holding(db_conn, monkeypatch):
    monkeypatch.setattr(goat_config, "GOAT_BANNED_TICKERS", {"XLI"})
    _patch_common(monkeypatch)
    mt_db.upsert_holding(
        db_conn, ticker="XLK", name="Technology Select Sector SPDR", asset_type="etf",
        bucket="1", qty=1.0, avg_price=100.0,
    )
    result = etf_heartbeat_scan.run_etf_heartbeat_scan(db_conn)
    tickers_out = {c["ticker"] for c in result["new_candidates"]}
    assert "XLK" not in tickers_out


def test_run_etf_heartbeat_scan_stays_quiet_on_repeat_run(db_conn, monkeypatch):
    monkeypatch.setattr(goat_config, "GOAT_BANNED_TICKERS", {"XLI"})
    _patch_common(monkeypatch)
    etf_heartbeat_scan.run_etf_heartbeat_scan(db_conn)
    result = etf_heartbeat_scan.run_etf_heartbeat_scan(db_conn)
    assert result["new_candidates"] == []
    assert len(result["pending_candidates"]) == 2


def test_run_etf_heartbeat_scan_stages_with_correct_source(db_conn, monkeypatch):
    monkeypatch.setattr(goat_config, "GOAT_BANNED_TICKERS", {"XLI"})
    _patch_common(monkeypatch)
    etf_heartbeat_scan.run_etf_heartbeat_scan(db_conn)
    row = goat_db.get_goat_pending_candidate(db_conn, "XLK")
    assert row is not None
    assert row["source"] == "goat_etf_heartbeat_scan"


def test_render_etf_heartbeat_candidates_report_lists_pending_rows():
    result = {
        "scanned": 3,
        "pending_candidates": [
            {"ticker": "XLK", "sector_label": "Technology", "signal_detail": "heartbeat signal",
             "flagged_at": "2026-10-01T00:00:00+00:00"},
        ],
    }
    report = etf_heartbeat_scan.render_etf_heartbeat_candidates_report(result)
    assert "XLK" in report
    assert "Technology" in report
    assert "3" in report
