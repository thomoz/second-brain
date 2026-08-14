from __future__ import annotations

from mytrader import ibkr_sync


def test_map_ibkr_ticker_us_listed_passthrough():
    assert ibkr_sync.map_ibkr_ticker("AAPL", "NASDAQ", "USD") == "AAPL"


def test_map_ibkr_ticker_aud_currency_maps_to_asx_variant():
    assert ibkr_sync.map_ibkr_ticker("PMGOLD", "ASX", "AUD") == "PMGOLD.AX"


def test_map_ibkr_ticker_asx_exchange_maps_to_asx_variant_even_if_currency_missing():
    assert ibkr_sync.map_ibkr_ticker("IXI", "ASX", "") == "IXI.AX"


def test_map_ibkr_ticker_normalizes_share_class():
    assert ibkr_sync.map_ibkr_ticker("BRK.B", "NYSE", "USD") == "BRK-B"


class _Row(dict):
    """Plain dict standing in for a sqlite3.Row -- supports row["key"] access."""


def _holding(ticker, qty, avg_price, bucket="1"):
    return _Row(ticker=ticker, qty=qty, avg_price=avg_price, bucket=bucket)


def _ibkr_position(ticker, qty, avg_price, currency="USD", exchange_raw="NASDAQ"):
    return {
        "ticker": ticker, "name": None, "qty": qty, "avg_price": avg_price,
        "currency": currency, "asset_type": "stock", "exchange_raw": exchange_raw,
    }


def test_compute_diff_matched_no_change():
    positions = [_ibkr_position("AAPL", 10.0, 150.0)]
    holdings = [_holding("AAPL", 10.0, 150.0)]

    diff = ibkr_sync.compute_diff(positions, holdings)

    assert len(diff["matched_no_change"]) == 1
    assert diff["matched_with_mismatch"] == []
    assert diff["new_to_ibkr"] == []
    assert diff["missing_from_ibkr"] == []


def test_compute_diff_matched_with_mismatch_on_qty():
    positions = [_ibkr_position("AAPL", 12.0, 150.0)]
    holdings = [_holding("AAPL", 10.0, 150.0)]

    diff = ibkr_sync.compute_diff(positions, holdings)

    assert len(diff["matched_with_mismatch"]) == 1
    entry = diff["matched_with_mismatch"][0]
    assert entry["ibkr_qty"] == 12.0
    assert entry["holdings_qty"] == 10.0
    assert diff["matched_no_change"] == []


def test_compute_diff_matched_with_mismatch_on_avg_price():
    positions = [_ibkr_position("AAPL", 10.0, 160.0)]
    holdings = [_holding("AAPL", 10.0, 150.0)]

    diff = ibkr_sync.compute_diff(positions, holdings)

    assert len(diff["matched_with_mismatch"]) == 1
    assert diff["matched_no_change"] == []


def test_compute_diff_new_to_ibkr():
    positions = [_ibkr_position("MSFT", 5.0, 300.0)]
    holdings = []

    diff = ibkr_sync.compute_diff(positions, holdings)

    assert len(diff["new_to_ibkr"]) == 1
    assert diff["new_to_ibkr"][0]["ticker"] == "MSFT"
    assert diff["matched_with_mismatch"] == []
    assert diff["matched_no_change"] == []
    assert diff["missing_from_ibkr"] == []


def test_compute_diff_missing_from_ibkr():
    positions = []
    holdings = [_holding("KO", 20.0, 55.0)]

    diff = ibkr_sync.compute_diff(positions, holdings)

    assert len(diff["missing_from_ibkr"]) == 1
    assert diff["missing_from_ibkr"][0]["ticker"] == "KO"
    assert diff["new_to_ibkr"] == []


def test_compute_diff_epsilon_tolerance_treats_tiny_diff_as_no_change():
    positions = [_ibkr_position("AAPL", 10.0000001, 150.00001)]
    holdings = [_holding("AAPL", 10.0, 150.0)]

    diff = ibkr_sync.compute_diff(positions, holdings)

    assert len(diff["matched_no_change"]) == 1
    assert diff["matched_with_mismatch"] == []
