from __future__ import annotations

import pandas as pd
from mytrader import db as mt_db
from mytrader.checks import CheckResult
from mytrader.market_data import TickerData

from goat import db as goat_db, heartbeat_scan

_RISING_RANKING = [{"ticker": "XLK", "sector_label": "Technology", "return_pct": 10.0, "rising": True}]

_CONSTITUENTS = [
    {"ticker": "AAPL", "security": "Apple Inc.", "gics_sector": "Information Technology", "fetched_at": "x"},
    {"ticker": "XOM", "security": "Exxon Mobil", "gics_sector": "Energy", "fetched_at": "x"},
]

_LSE_CONSTITUENTS = [
    {"ticker": "BMS", "company": "Braemar Plc", "icb_sector": "Software & computer services", "fetched_at": "x"},
]


def _fake_close() -> pd.Series:
    return pd.Series([100.0, 101.0], index=pd.date_range("2026-01-01", periods=2))


def _fake_price_volume_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {"Close": [100.0, 101.0], "Volume": [1000.0, 1100.0]},
        index=pd.date_range("2026-01-01", periods=2),
    )


def _healthy_ticker_data() -> TickerData:
    return TickerData(
        ticker="AAPL",
        info={"debtToEquity": 50.0, "totalCash": 1_000_000_000, "freeCashflow": 100_000_000,
              "operatingCashflow": 100_000_000},
        dividends=None,
    )


def _insolvent_ticker_data() -> TickerData:
    return TickerData(
        ticker="AAPL",
        info={"debtToEquity": 300.0, "totalCash": 10_000_000, "freeCashflow": -100_000_000,
              "operatingCashflow": -80_000_000},
        dividends=None,
    )


def _patch_common(
    monkeypatch, constituents=None, lse_constituents=None,
    fetch_close=None, breakout_check=None, ticker_data=None,
):
    monkeypatch.setattr("goat.heartbeat_scan.sector_rotation.fetch_all_sector_closes", lambda: {})
    monkeypatch.setattr("goat.heartbeat_scan.sector_rotation.rank_sectors", lambda closes: _RISING_RANKING)
    monkeypatch.setattr(
        "goat.heartbeat_scan.sp500_universe.get_or_refresh_sp500_constituents",
        lambda conn: constituents if constituents is not None else _CONSTITUENTS,
    )
    monkeypatch.setattr(
        "goat.heartbeat_scan.ftse100_universe.get_or_refresh_ftse100_constituents",
        lambda conn: lse_constituents if lse_constituents is not None else [],
    )
    monkeypatch.setattr(
        "goat.heartbeat_scan.price_history.fetch_close_volume_history",
        fetch_close if fetch_close is not None else (lambda ticker, lookback_days: _fake_price_volume_frame()),
    )
    monkeypatch.setattr(
        "goat.heartbeat_scan.heartbeat.check_heartbeat_breakout",
        breakout_check if breakout_check is not None else (
            lambda ticker, sector_label, close, volume: CheckResult(
                name="heartbeat_breakout", verdict="interesting", detail=f"{ticker} heartbeat signal",
            )
        ),
    )
    monkeypatch.setattr(
        "goat.heartbeat_scan.market_data.fetch_ticker_data",
        ticker_data if ticker_data is not None else (lambda ticker: _healthy_ticker_data()),
    )


def test_run_heartbeat_scan_stages_new_candidate_in_rising_sector(db_conn, monkeypatch):
    _patch_common(monkeypatch)
    result = heartbeat_scan.run_heartbeat_scan(db_conn)
    assert result["scanned"] == 1  # only AAPL -- XOM (Energy) is filtered before any fetch
    assert len(result["new_candidates"]) == 1
    assert result["new_candidates"][0]["ticker"] == "AAPL"
    row = goat_db.get_goat_pending_candidate(db_conn, "AAPL")
    assert row is not None
    assert row["source"] == "goat_heartbeat_scan"


def test_run_heartbeat_scan_filters_non_rising_sector_before_any_fetch(db_conn, monkeypatch):
    calls = []

    def _tracking_fetch(ticker, lookback_days):
        calls.append(ticker)
        return _fake_price_volume_frame()

    _patch_common(monkeypatch, fetch_close=_tracking_fetch)
    heartbeat_scan.run_heartbeat_scan(db_conn)
    assert "XOM" not in calls
    assert calls == ["AAPL"]


def test_run_heartbeat_scan_skips_ticker_already_a_holding(db_conn, monkeypatch):
    _patch_common(monkeypatch)
    mt_db.upsert_holding(
        db_conn, ticker="AAPL", name="Apple Inc.", asset_type="stock",
        bucket="1", qty=1.0, avg_price=100.0,
    )
    result = heartbeat_scan.run_heartbeat_scan(db_conn)
    assert result["new_candidates"] == []
    assert goat_db.get_goat_pending_candidate(db_conn, "AAPL") is None


def test_run_heartbeat_scan_skips_ticker_already_in_watchlist(db_conn, monkeypatch):
    _patch_common(monkeypatch)
    mt_db.upsert_watchlist_row(
        db_conn, ticker="AAPL", name="Apple Inc.", asset_type="stock", bucket="unassigned",
    )
    result = heartbeat_scan.run_heartbeat_scan(db_conn)
    assert result["new_candidates"] == []
    assert goat_db.get_goat_pending_candidate(db_conn, "AAPL") is None


def test_run_heartbeat_scan_stays_quiet_on_repeat_run(db_conn, monkeypatch):
    _patch_common(monkeypatch)
    heartbeat_scan.run_heartbeat_scan(db_conn)
    result = heartbeat_scan.run_heartbeat_scan(db_conn)
    assert result["new_candidates"] == []
    assert len(result["pending_candidates"]) == 1


def test_run_heartbeat_scan_suppresses_staging_on_insolvency_risk(db_conn, monkeypatch):
    _patch_common(monkeypatch, ticker_data=lambda ticker: _insolvent_ticker_data())
    result = heartbeat_scan.run_heartbeat_scan(db_conn)
    assert result["new_candidates"] == []
    assert goat_db.get_goat_pending_candidate(db_conn, "AAPL") is None


def test_run_heartbeat_scan_skips_ticker_with_no_price_history(db_conn, monkeypatch):
    _patch_common(monkeypatch, fetch_close=lambda ticker, lookback_days: None)
    result = heartbeat_scan.run_heartbeat_scan(db_conn)  # must not raise
    assert result["scanned"] == 0
    assert result["new_candidates"] == []


def test_run_heartbeat_scan_skips_unmapped_gics_sector(db_conn, monkeypatch):
    unmapped = [{"ticker": "XYZ", "security": "Mystery Corp", "gics_sector": "Not A Real Sector", "fetched_at": "x"}]
    _patch_common(monkeypatch, constituents=unmapped)
    result = heartbeat_scan.run_heartbeat_scan(db_conn)  # must not crash
    assert result["scanned"] == 0
    assert result["new_candidates"] == []


def test_run_heartbeat_scan_skips_unmapped_icb_sector(db_conn, monkeypatch):
    unmapped = [{"ticker": "XYZ", "company": "Mystery PLC", "icb_sector": "Not A Real Sector", "fetched_at": "x"}]
    _patch_common(monkeypatch, constituents=[], lse_constituents=unmapped)
    result = heartbeat_scan.run_heartbeat_scan(db_conn)  # must not crash
    assert result["scanned"] == 0
    assert result["new_candidates"] == []


def test_run_heartbeat_scan_stages_candidates_from_both_us_and_lse_legs(db_conn, monkeypatch):
    _patch_common(monkeypatch, lse_constituents=_LSE_CONSTITUENTS)
    result = heartbeat_scan.run_heartbeat_scan(db_conn)
    assert result["scanned"] == 2  # AAPL (US) + BMS.L (LSE) -- XOM filtered, non-rising sector
    tickers_out = {c["ticker"] for c in result["new_candidates"]}
    assert tickers_out == {"AAPL", "BMS.L"}


def test_run_heartbeat_scan_qualifies_lse_ticker_with_l_suffix(db_conn, monkeypatch):
    _patch_common(monkeypatch, constituents=[], lse_constituents=_LSE_CONSTITUENTS)
    result = heartbeat_scan.run_heartbeat_scan(db_conn)
    assert result["new_candidates"][0]["ticker"] == "BMS.L"
    row = goat_db.get_goat_pending_candidate(db_conn, "BMS.L")
    assert row is not None
    assert row["company_name"] == "Braemar Plc"


def test_run_heartbeat_scan_populates_exchange_from_ticker_data(db_conn, monkeypatch):
    def _exchange_ticker_data(ticker):
        data = _healthy_ticker_data()
        data.info["fullExchangeName"] = "London Stock Exchange"
        return data

    _patch_common(
        monkeypatch, constituents=[], lse_constituents=_LSE_CONSTITUENTS,
        ticker_data=_exchange_ticker_data,
    )
    heartbeat_scan.run_heartbeat_scan(db_conn)
    row = goat_db.get_goat_pending_candidate(db_conn, "BMS.L")
    assert row["exchange"] == "London Stock Exchange"


def test_render_heartbeat_candidates_report_lists_pending_rows():
    result = {
        "scanned": 42, "rising_sectors": ["Technology"],
        "pending_candidates": [
            {"ticker": "AAPL", "company_name": "Apple Inc.", "sector_label": "Technology",
             "signal_detail": "heartbeat signal", "flagged_at": "2026-08-17T00:00:00+00:00"},
        ],
    }
    report = heartbeat_scan.render_heartbeat_candidates_report(result)
    assert "AAPL" in report
    assert "Apple Inc." in report
    assert "heartbeat signal" in report
    assert "42" in report


def test_render_heartbeat_candidates_report_shows_exchange_column_and_na_when_missing():
    result = {
        "scanned": 2, "rising_sectors": ["Technology"],
        "pending_candidates": [
            {"ticker": "BMS.L", "company_name": "Braemar Plc", "sector_label": "Technology",
             "signal_detail": "heartbeat signal", "flagged_at": "2026-10-01T00:00:00+00:00",
             "exchange": "London Stock Exchange"},
            {"ticker": "AAPL", "company_name": "Apple Inc.", "sector_label": "Technology",
             "signal_detail": "heartbeat signal", "flagged_at": "2026-08-17T00:00:00+00:00"},
        ],
    }
    report = heartbeat_scan.render_heartbeat_candidates_report(result)
    assert "| Ticker | Company | Exchange | Sector | Signal | Flagged |" in report
    assert "London Stock Exchange" in report
    assert "| AAPL | Apple Inc. | n/a |" in report
