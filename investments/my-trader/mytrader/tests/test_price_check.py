from __future__ import annotations

import types

from mytrader import db, price_check


def test_run_price_check_first_run_establishes_baseline_without_crossing(db_conn, monkeypatch):
    db.upsert_price_check(db_conn, ticker="AAPL", name="Apple Inc.", target_price=200.0)
    monkeypatch.setattr("mytrader.price_check.market_data.fetch_current_price", lambda ticker: 210.0)

    result = price_check.run_price_check(db_conn)

    assert result["crossed"] == []
    assert result["checked"][0]["side"] == "above"
    row = db.get_price_check(db_conn, "AAPL")
    assert row["last_side"] == "above"
    assert row["last_price"] == 210.0


def test_run_price_check_fires_on_crossing_above_to_below(db_conn, monkeypatch):
    db.upsert_price_check(db_conn, ticker="AAPL", name="Apple Inc.", target_price=200.0)
    db.update_price_check_side(db_conn, "AAPL", side="above", price=210.0)
    monkeypatch.setattr("mytrader.price_check.market_data.fetch_current_price", lambda ticker: 195.0)

    result = price_check.run_price_check(db_conn)

    assert len(result["crossed"]) == 1
    c = result["crossed"][0]
    assert c["ticker"] == "AAPL"
    assert c["from_side"] == "above"
    assert c["side"] == "below"
    assert c["price"] == 195.0


def test_run_price_check_fires_on_crossing_below_to_above(db_conn, monkeypatch):
    db.upsert_price_check(db_conn, ticker="AAPL", name=None, target_price=200.0)
    db.update_price_check_side(db_conn, "AAPL", side="below", price=190.0)
    monkeypatch.setattr("mytrader.price_check.market_data.fetch_current_price", lambda ticker: 205.0)

    result = price_check.run_price_check(db_conn)

    assert len(result["crossed"]) == 1
    assert result["crossed"][0]["from_side"] == "below"
    assert result["crossed"][0]["side"] == "above"


def test_run_price_check_stays_quiet_when_side_unchanged(db_conn, monkeypatch):
    db.upsert_price_check(db_conn, ticker="AAPL", name=None, target_price=200.0)
    db.update_price_check_side(db_conn, "AAPL", side="above", price=210.0)
    monkeypatch.setattr("mytrader.price_check.market_data.fetch_current_price", lambda ticker: 212.0)

    result = price_check.run_price_check(db_conn)

    assert result["crossed"] == []
    assert result["checked"][0]["side"] == "above"


def test_run_price_check_fires_again_on_a_second_crossing_back(db_conn, monkeypatch):
    """Unlike a one-time breakout alert, a price check is a live watch level --
    crossing back and forth must alert every time, not just once."""
    db.upsert_price_check(db_conn, ticker="AAPL", name=None, target_price=200.0)
    db.update_price_check_side(db_conn, "AAPL", side="above", price=210.0)

    monkeypatch.setattr("mytrader.price_check.market_data.fetch_current_price", lambda ticker: 195.0)
    first = price_check.run_price_check(db_conn)
    assert len(first["crossed"]) == 1

    monkeypatch.setattr("mytrader.price_check.market_data.fetch_current_price", lambda ticker: 205.0)
    second = price_check.run_price_check(db_conn)
    assert len(second["crossed"]) == 1
    assert second["crossed"][0]["from_side"] == "below"
    assert second["crossed"][0]["side"] == "above"


def test_run_price_check_skips_ticker_with_no_price_data(db_conn, monkeypatch):
    db.upsert_price_check(db_conn, ticker="AAPL", name=None, target_price=200.0)
    monkeypatch.setattr("mytrader.price_check.market_data.fetch_current_price", lambda ticker: None)

    result = price_check.run_price_check(db_conn)

    assert result["crossed"] == []
    assert result["checked"][0]["price"] is None
    row = db.get_price_check(db_conn, "AAPL")
    assert row["last_side"] is None  # never updated, nothing to persist


def test_run_price_check_price_exactly_at_target_counts_as_above(db_conn, monkeypatch):
    db.upsert_price_check(db_conn, ticker="AAPL", name=None, target_price=200.0)
    monkeypatch.setattr("mytrader.price_check.market_data.fetch_current_price", lambda ticker: 200.0)

    result = price_check.run_price_check(db_conn)
    assert result["checked"][0]["side"] == "above"


def test_render_price_check_report_lists_rows_and_crossings():
    result = {
        "checked": [
            {"ticker": "AAPL", "name": "Apple Inc.", "target_price": 200.0, "price": 195.0, "side": "below", "crossed": True},
        ],
        "crossed": [
            {"ticker": "AAPL", "name": "Apple Inc.", "target_price": 200.0, "price": 195.0,
             "side": "below", "from_side": "above"},
        ],
    }
    report = price_check.render_price_check_report(result)
    assert "AAPL" in report
    assert "200.00" in report
    assert "195.00" in report
    assert "above -> below" in report


def test_render_price_check_report_handles_empty_list():
    result = {"checked": [], "crossed": []}
    report = price_check.render_price_check_report(result)
    assert "No price checks set" in report
    assert "No crossings this run." in report


def test_maybe_notify_sends_whatsapp_and_toast_on_crossing(monkeypatch):
    sent = {}

    def _fake_send_whatsapp(message, chat_id=""):
        sent["whatsapp"] = message
        return True

    def _fake_send_toast(title, message, duration=5):
        sent["toast"] = (title, message)
        return True

    fake_module = types.ModuleType("notifications")
    fake_module.send_whatsapp_notification = _fake_send_whatsapp
    fake_module.send_toast_notification = _fake_send_toast
    monkeypatch.setitem(__import__("sys").modules, "notifications", fake_module)

    result = {
        "checked": [],
        "crossed": [
            {"ticker": "AAPL", "name": "Apple Inc.", "target_price": 200.0, "price": 195.0,
             "side": "below", "from_side": "above"},
        ],
    }
    price_check.maybe_notify(result)
    assert "AAPL" in sent["whatsapp"]
    assert "Price Check" == sent["toast"][0]


def test_maybe_notify_stays_quiet_with_no_crossings(monkeypatch):
    calls = []
    fake_module = types.ModuleType("notifications")
    fake_module.send_whatsapp_notification = lambda *a, **k: calls.append("whatsapp")
    fake_module.send_toast_notification = lambda *a, **k: calls.append("toast")
    monkeypatch.setitem(__import__("sys").modules, "notifications", fake_module)

    price_check.maybe_notify({"checked": [], "crossed": []})
    assert calls == []
