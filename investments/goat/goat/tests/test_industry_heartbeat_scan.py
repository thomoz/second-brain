from __future__ import annotations

import pandas as pd
from mytrader import db as mt_db
from mytrader.checks import CheckResult
from mytrader.market_data import TickerData

from goat import db as goat_db, industry_heartbeat_scan


_GATED_INDUSTRIES = ["Semiconductors"]

_CONSTITUENTS = [
    {"ticker": "NVDA", "company": "Nvidia Corp", "market": "US", "industry_label": "Semiconductors"},
    {"ticker": "AMD", "company": "Advanced Micro Devices", "market": "US", "industry_label": "Semiconductors"},
]


def _fake_price_volume_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {"Close": [100.0, 101.0], "Volume": [1000.0, 1100.0]},
        index=pd.date_range("2026-01-01", periods=2),
    )


def _healthy_ticker_data() -> TickerData:
    return TickerData(
        ticker="NVDA",
        info={"debtToEquity": 50.0, "totalCash": 1_000_000_000, "freeCashflow": 100_000_000,
              "operatingCashflow": 100_000_000},
        dividends=None,
    )


def _insolvent_ticker_data() -> TickerData:
    return TickerData(
        ticker="NVDA",
        info={"debtToEquity": 300.0, "totalCash": 10_000_000, "freeCashflow": -100_000_000,
              "operatingCashflow": -80_000_000},
        dividends=None,
    )


def _patch_common(
    monkeypatch, constituents=None, fetch_close=None, breakout_check=None, ticker_data=None,
    gated_industries=None,
):
    monkeypatch.setattr(
        "goat.industry_heartbeat_scan._compute_gated_industries",
        lambda: gated_industries if gated_industries is not None else _GATED_INDUSTRIES,
    )
    monkeypatch.setattr(
        "goat.industry_heartbeat_scan.industry_constituents.get_or_refresh_industry_constituents",
        lambda conn, industry_label: constituents if constituents is not None else _CONSTITUENTS,
    )
    monkeypatch.setattr(
        "goat.industry_heartbeat_scan.price_history.fetch_close_volume_history",
        fetch_close if fetch_close is not None else (lambda ticker, lookback_days: _fake_price_volume_frame()),
    )
    monkeypatch.setattr(
        "goat.industry_heartbeat_scan.heartbeat.check_heartbeat_breakout",
        breakout_check if breakout_check is not None else (
            lambda ticker, label, close, volume: CheckResult(
                name="heartbeat_breakout", verdict="interesting", detail=f"{ticker} heartbeat signal",
            )
        ),
    )
    monkeypatch.setattr(
        "goat.industry_heartbeat_scan.market_data.fetch_ticker_data",
        ticker_data if ticker_data is not None else (lambda ticker: _healthy_ticker_data()),
    )


def test_run_industry_heartbeat_scan_computes_gate_when_industries_none(db_conn, monkeypatch):
    calls = {"n": 0}

    def _tracking_gate():
        calls["n"] += 1
        return _GATED_INDUSTRIES

    _patch_common(monkeypatch)
    monkeypatch.setattr("goat.industry_heartbeat_scan._compute_gated_industries", _tracking_gate)
    industry_heartbeat_scan.run_industry_heartbeat_scan(db_conn, industries=None)
    assert calls["n"] == 1


def test_run_industry_heartbeat_scan_industries_override_bypasses_gate_computation(db_conn, monkeypatch):
    calls = {"n": 0}

    def _tracking_gate():
        calls["n"] += 1
        return _GATED_INDUSTRIES

    _patch_common(monkeypatch)
    monkeypatch.setattr("goat.industry_heartbeat_scan._compute_gated_industries", _tracking_gate)
    result = industry_heartbeat_scan.run_industry_heartbeat_scan(db_conn, industries=["Semiconductors"])
    assert calls["n"] == 0
    assert result["gated_industries"] == ["Semiconductors"]


def test_run_industry_heartbeat_scan_stages_new_candidates(db_conn, monkeypatch):
    _patch_common(monkeypatch)
    result = industry_heartbeat_scan.run_industry_heartbeat_scan(db_conn, industries=["Semiconductors"])
    assert result["scanned"] == 2
    assert len(result["new_candidates"]) == 2
    row = goat_db.get_goat_pending_candidate(db_conn, "NVDA")
    assert row is not None
    assert row["source"] == "goat_industry_heartbeat_scan"


def test_run_industry_heartbeat_scan_dedups_against_holding(db_conn, monkeypatch):
    _patch_common(monkeypatch)
    mt_db.upsert_holding(
        db_conn, ticker="NVDA", name="Nvidia Corp", asset_type="stock",
        bucket="1", qty=1.0, avg_price=100.0,
    )
    result = industry_heartbeat_scan.run_industry_heartbeat_scan(db_conn, industries=["Semiconductors"])
    tickers_out = {c["ticker"] for c in result["new_candidates"]}
    assert "NVDA" not in tickers_out
    assert goat_db.get_goat_pending_candidate(db_conn, "NVDA") is None


def test_run_industry_heartbeat_scan_dedups_against_watchlist(db_conn, monkeypatch):
    _patch_common(monkeypatch)
    mt_db.upsert_watchlist_row(
        db_conn, ticker="NVDA", name="Nvidia Corp", asset_type="stock", bucket="unassigned",
    )
    result = industry_heartbeat_scan.run_industry_heartbeat_scan(db_conn, industries=["Semiconductors"])
    tickers_out = {c["ticker"] for c in result["new_candidates"]}
    assert "NVDA" not in tickers_out


def test_run_industry_heartbeat_scan_stays_quiet_on_repeat_run(db_conn, monkeypatch):
    _patch_common(monkeypatch)
    industry_heartbeat_scan.run_industry_heartbeat_scan(db_conn, industries=["Semiconductors"])
    result = industry_heartbeat_scan.run_industry_heartbeat_scan(db_conn, industries=["Semiconductors"])
    assert result["new_candidates"] == []
    assert len(result["pending_candidates"]) == 2


def test_run_industry_heartbeat_scan_suppresses_staging_on_insolvency_risk(db_conn, monkeypatch):
    _patch_common(monkeypatch, ticker_data=lambda ticker: _insolvent_ticker_data())
    result = industry_heartbeat_scan.run_industry_heartbeat_scan(db_conn, industries=["Semiconductors"])
    assert result["new_candidates"] == []


def test_run_industry_heartbeat_scan_skips_ticker_with_no_price_history(db_conn, monkeypatch):
    _patch_common(monkeypatch, fetch_close=lambda ticker, lookback_days: None)
    result = industry_heartbeat_scan.run_industry_heartbeat_scan(db_conn, industries=["Semiconductors"])
    assert result["scanned"] == 0
    assert result["new_candidates"] == []


def test_render_industry_heartbeat_candidates_report_lists_pending_rows():
    result = {
        "scanned": 2, "gated_industries": ["Semiconductors"],
        "pending_candidates": [
            {"ticker": "NVDA", "company_name": "Nvidia Corp", "sector_label": "Semiconductors",
             "signal_detail": "heartbeat signal", "flagged_at": "2026-10-01T00:00:00+00:00"},
        ],
    }
    report = industry_heartbeat_scan.render_industry_heartbeat_candidates_report(result)
    assert "NVDA" in report
    assert "Nvidia Corp" in report
    assert "Semiconductors" in report
