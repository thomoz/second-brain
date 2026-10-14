from __future__ import annotations

import pandas as pd
from mytrader.db import upsert_holding, upsert_watchlist_row
from mytrader.market_data import TickerData

from volume_earnings_scanner import config, db, earnings_signal, price_history, scan, universe

_NOT_RECORD_EPS = [0.5, 1.0, 1.5, 2.0]  # latest is the LOWEST -- never a record
_RECORD_EPS = [2.0, 1.5, 1.0, 0.8]  # latest is the HIGHEST -- always a record

_FLAT_VOLUME_LEN = config.VE_VOLUME_AVG_WINDOW_DAYS + 1


def _flat_volume() -> pd.Series:
    return pd.Series([100_000] * _FLAT_VOLUME_LEN)


def _spiking_volume() -> pd.Series:
    return pd.Series([100_000] * (_FLAT_VOLUME_LEN - 1) + [500_000])


def _frame(volume: pd.Series) -> pd.DataFrame:
    return pd.DataFrame({"Close": pd.Series([10.0] * len(volume)), "Volume": volume})


_GOOD_FLOOR_INFO = {"averageVolume": 200_000, "marketCap": 500_000_000.0, "regularMarketPrice": 10.0}
_BAD_FLOOR_INFO = {"averageVolume": 200_000, "marketCap": 5_000_000_000.0, "regularMarketPrice": 10.0}  # too big

_FIXTURES: dict[str, dict] = {
    "VOLONLY": {"volume": _spiking_volume(), "eps": _NOT_RECORD_EPS, "info": _GOOD_FLOOR_INFO},
    "EARNONLY": {"volume": _flat_volume(), "eps": _RECORD_EPS, "info": _GOOD_FLOOR_INFO},
    "BOTH": {"volume": _spiking_volume(), "eps": _RECORD_EPS, "info": _GOOD_FLOOR_INFO},
    "NOSIGNAL": {"volume": _flat_volume(), "eps": _NOT_RECORD_EPS, "info": _GOOD_FLOOR_INFO},
    "HELD1": {"volume": _spiking_volume(), "eps": _NOT_RECORD_EPS, "info": _GOOD_FLOOR_INFO},
    "WATCH1": {"volume": _spiking_volume(), "eps": _NOT_RECORD_EPS, "info": _GOOD_FLOOR_INFO},
    "NOFLOOR": {"volume": _spiking_volume(), "eps": _NOT_RECORD_EPS, "info": _BAD_FLOOR_INFO},
    "LMT": {"volume": _spiking_volume(), "eps": _RECORD_EPS, "info": _GOOD_FLOOR_INFO},
}


def _wire(monkeypatch, tickers: list[str]) -> None:
    screened = [{"ticker": t, "company": f"{t} Co", "market_cap_text": "500.00M"} for t in tickers]
    monkeypatch.setattr(universe, "get_scan_universe", lambda conn: {
        "screened": screened, "slice_today": tickers, "slice_index": 0, "finviz_failed": False,
    })
    monkeypatch.setattr(
        price_history, "fetch_close_volume_history",
        lambda ticker, lookback_days: _frame(_FIXTURES[ticker]["volume"]),
    )
    monkeypatch.setattr(
        earnings_signal, "fetch_quarterly_eps_history",
        lambda ticker: _FIXTURES[ticker]["eps"],
    )
    monkeypatch.setattr(
        "mytrader.market_data.fetch_ticker_data",
        lambda ticker: TickerData(ticker=ticker, info=_FIXTURES[ticker]["info"], dividends=None),
    )


def test_scan_stages_volume_only_signal(db_conn, monkeypatch):
    _wire(monkeypatch, ["VOLONLY"])
    result = scan.run_scan(db_conn)
    staged = {r["ticker"]: r for r in db.get_all_ve_pending_candidates(db_conn)}
    assert staged["VOLONLY"]["signal_type"] == "volume"
    assert "VOLONLY" in {c["ticker"] for c in result["new_candidates"]}


def test_scan_stages_earnings_only_signal(db_conn, monkeypatch):
    _wire(monkeypatch, ["EARNONLY"])
    result = scan.run_scan(db_conn)
    staged = {r["ticker"]: r for r in db.get_all_ve_pending_candidates(db_conn)}
    assert staged["EARNONLY"]["signal_type"] == "earnings"
    assert "EARNONLY" in {c["ticker"] for c in result["new_candidates"]}


def test_scan_marks_both_signals_and_prefixes_detail(db_conn, monkeypatch):
    _wire(monkeypatch, ["BOTH"])
    result = scan.run_scan(db_conn)
    staged = {r["ticker"]: r for r in db.get_all_ve_pending_candidates(db_conn)}
    assert staged["BOTH"]["signal_type"] == "both"
    assert staged["BOTH"]["signal_detail"].startswith("BOTH SIGNALS -- ")
    assert result["new_candidates"][0]["signal_type"] == "both"


def test_scan_no_signal_never_staged(db_conn, monkeypatch):
    _wire(monkeypatch, ["NOSIGNAL"])
    result = scan.run_scan(db_conn)
    assert db.get_all_ve_pending_candidates(db_conn) == []
    assert result["new_candidates"] == []


def test_scan_excludes_defense_ticker_entirely(db_conn, monkeypatch):
    _wire(monkeypatch, ["LMT"])
    result = scan.run_scan(db_conn)
    assert db.get_all_ve_pending_candidates(db_conn) == []
    assert result["scanned"] == 0  # dropped before the scanned counter increments


def test_scan_never_stages_a_held_ticker(db_conn, monkeypatch):
    _wire(monkeypatch, ["HELD1"])
    upsert_holding(db_conn, ticker="HELD1", name="Held Co", asset_type="stock", bucket="1", qty=10, avg_price=5.0)
    result = scan.run_scan(db_conn)
    assert db.get_all_ve_pending_candidates(db_conn) == []
    assert result["new_candidates"] == []


def test_scan_never_stages_a_watchlisted_ticker(db_conn, monkeypatch):
    _wire(monkeypatch, ["WATCH1"])
    upsert_watchlist_row(db_conn, ticker="WATCH1", name=None, asset_type="stock", bucket="unassigned")
    result = scan.run_scan(db_conn)
    assert db.get_all_ve_pending_candidates(db_conn) == []
    assert result["new_candidates"] == []


def test_scan_never_stages_a_ticker_failing_the_precise_floor(db_conn, monkeypatch):
    _wire(monkeypatch, ["NOFLOOR"])
    result = scan.run_scan(db_conn)
    assert db.get_all_ve_pending_candidates(db_conn) == []
    assert result["new_candidates"] == []


def test_scan_is_idempotent_no_double_insert(db_conn, monkeypatch):
    _wire(monkeypatch, ["VOLONLY"])
    first = scan.run_scan(db_conn)
    n_first = len(db.get_all_ve_pending_candidates(db_conn))
    second = scan.run_scan(db_conn)
    assert n_first == 1
    assert len(db.get_all_ve_pending_candidates(db_conn)) == n_first  # no double-insert
    assert first["new_candidates"] and second["new_candidates"] == []  # already staged, not re-alerted
