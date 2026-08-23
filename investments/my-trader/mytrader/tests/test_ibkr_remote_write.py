from __future__ import annotations

import json

from mytrader.ibkr_sync import compute_diff


def _ibkr_position(ticker, qty, avg_price, currency="USD", exchange_raw="NASDAQ"):
    return {
        "ticker": ticker, "name": None, "qty": qty, "avg_price": avg_price,
        "currency": currency, "asset_type": "stock", "exchange_raw": exchange_raw,
    }


def test_positions_round_trip_through_json_without_type_loss():
    """positions crosses the local->VPS SSH boundary as JSON (see ibkr_remote_write.py /
    ibkr_remote_apply.py) -- confirm the shape fetch_positions() actually returns
    (str/float/None fields, no Decimal/datetime) survives serialize/deserialize intact,
    since compute_diff() relies on qty/avg_price staying numeric, not becoming strings."""
    positions = [
        _ibkr_position("AAPL", 10.0, 150.25),
        _ibkr_position("PMGOLD.AX", 5.5, 32.1, currency="AUD", exchange_raw="ASX"),
    ]

    payload = json.dumps({"positions": positions, "summary": None, "apply": False})
    restored = json.loads(payload)["positions"]

    assert restored == positions
    assert isinstance(restored[0]["qty"], float)
    assert isinstance(restored[0]["avg_price"], float)
    assert restored[0]["name"] is None


def test_restored_positions_still_work_with_compute_diff():
    positions = [_ibkr_position("AAPL", 10.0, 150.0)]
    payload = json.dumps({"positions": positions, "summary": None, "apply": False})
    restored = json.loads(payload)["positions"]

    holdings = [{"ticker": "AAPL", "qty": 10.0, "avg_price": 150.0, "bucket": "1"}]
    diff = compute_diff(restored, holdings)

    assert len(diff["matched_no_change"]) == 1
    assert diff["matched_with_mismatch"] == []
