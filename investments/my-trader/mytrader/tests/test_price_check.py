from __future__ import annotations

import types

from mytrader import db, price_check


def _disable_list_sync(monkeypatch):
    """Tests below set up price_checks DB state directly and exercise the
    crossing-detection half of run_price_check in isolation from the
    list-parsing/sync half (covered separately by its own tests) -- mirrors
    sync_price_checks_from_list's own unit tests not needing a real market
    fetch."""
    monkeypatch.setattr(
        "mytrader.price_check.sync_price_checks_from_list",
        lambda conn, rows: {"added": [], "updated": [], "removed": []},
    )
    monkeypatch.setattr("mytrader.price_check.parse_price_check_list", lambda text: [])
    import pathlib
    monkeypatch.setattr(
        "mytrader.price_check.config.PRICE_CHECK_LIST_PATH",
        pathlib.Path("/nonexistent/price-check-list.md"),
    )


# --- parse_price_check_list -----------------------------------------------


def test_parse_price_check_list_parses_rows():
    text = (
        "# Price Check List\n\n"
        "Some prose explaining the file.\n\n"
        "| Ticker | Target Price | Name |\n"
        "|--------|---------------|------|\n"
        "| AAPL | 200 | Apple Inc. |\n"
        "| tsla | 450.50 | |\n"
    )
    rows = price_check.parse_price_check_list(text)
    assert rows == [
        {"ticker": "AAPL", "target_price": 200.0, "name": "Apple Inc."},
        {"ticker": "TSLA", "target_price": 450.50, "name": None},
    ]


def test_parse_price_check_list_strips_dollar_signs_and_commas():
    text = "| Ticker | Target Price | Name |\n|---|---|---|\n| AAPL | $1,234.50 | |\n"
    rows = price_check.parse_price_check_list(text)
    assert rows[0]["target_price"] == 1234.50


def test_parse_price_check_list_skips_unparsable_price_row_without_crashing():
    text = (
        "| Ticker | Target Price | Name |\n|---|---|---|\n"
        "| AAPL | not-a-number | Apple |\n"
        "| MSFT | 400 | Microsoft |\n"
    )
    rows = price_check.parse_price_check_list(text)
    assert [r["ticker"] for r in rows] == ["MSFT"]


def test_parse_price_check_list_empty_table_returns_empty():
    text = "| Ticker | Target Price | Name |\n|---|---|---|\n"
    assert price_check.parse_price_check_list(text) == []


def test_parse_price_check_list_ignores_non_table_prose():
    text = "Just some notes, no table here.\n"
    assert price_check.parse_price_check_list(text) == []


# --- sync_price_checks_from_list -------------------------------------------


def test_sync_adds_new_tickers_with_null_baseline(db_conn):
    result = price_check.sync_price_checks_from_list(
        db_conn, [{"ticker": "AAPL", "target_price": 200.0, "name": "Apple Inc."}]
    )
    assert result["added"] == ["AAPL"]
    row = db.get_price_check(db_conn, "AAPL")
    assert row["target_price"] == 200.0
    assert row["last_side"] is None


def test_sync_removes_tickers_no_longer_in_the_list(db_conn):
    db.upsert_price_check(db_conn, ticker="AAPL", name=None, target_price=200.0)
    result = price_check.sync_price_checks_from_list(db_conn, [])
    assert result["removed"] == ["AAPL"]
    assert db.get_price_check(db_conn, "AAPL") is None


def test_sync_target_price_change_resets_baseline(db_conn):
    db.upsert_price_check(db_conn, ticker="AAPL", name="Apple Inc.", target_price=200.0)
    db.update_price_check_side(db_conn, "AAPL", side="above", price=210.0)

    result = price_check.sync_price_checks_from_list(
        db_conn, [{"ticker": "AAPL", "target_price": 250.0, "name": "Apple Inc."}]
    )
    assert result["updated"] == ["AAPL"]
    row = db.get_price_check(db_conn, "AAPL")
    assert row["target_price"] == 250.0
    assert row["last_side"] is None  # re-baselined


def test_sync_name_only_change_does_not_reset_baseline(db_conn):
    """A cosmetic edit (name changed, target_price unchanged) must not wipe an
    already-established crossing baseline -- only a target_price change
    should."""
    db.upsert_price_check(db_conn, ticker="AAPL", name="Apple", target_price=200.0)
    db.update_price_check_side(db_conn, "AAPL", side="above", price=210.0)

    result = price_check.sync_price_checks_from_list(
        db_conn, [{"ticker": "AAPL", "target_price": 200.0, "name": "Apple Inc."}]
    )
    assert result == {"added": [], "updated": [], "removed": []}
    row = db.get_price_check(db_conn, "AAPL")
    assert row["name"] == "Apple Inc."
    assert row["last_side"] == "above"  # untouched
    assert row["last_price"] == 210.0


def test_sync_unchanged_row_leaves_baseline_untouched(db_conn):
    db.upsert_price_check(db_conn, ticker="AAPL", name="Apple Inc.", target_price=200.0)
    db.update_price_check_side(db_conn, "AAPL", side="above", price=210.0)

    result = price_check.sync_price_checks_from_list(
        db_conn, [{"ticker": "AAPL", "target_price": 200.0, "name": "Apple Inc."}]
    )
    assert result == {"added": [], "updated": [], "removed": []}
    row = db.get_price_check(db_conn, "AAPL")
    assert row["last_side"] == "above"
    assert row["last_price"] == 210.0


# --- run_price_check (crossing detection) -----------------------------------


def test_run_price_check_reads_and_syncs_the_list_file(db_conn, monkeypatch, tmp_path):
    list_path = tmp_path / "price-check-list.md"
    list_path.write_text(
        "| Ticker | Target Price | Name |\n|---|---|---|\n| AAPL | 200 | Apple Inc. |\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("mytrader.price_check.config.PRICE_CHECK_LIST_PATH", list_path)
    monkeypatch.setattr("mytrader.price_check.market_data.fetch_current_price", lambda ticker: 210.0)

    result = price_check.run_price_check(db_conn)

    assert db.get_price_check(db_conn, "AAPL") is not None
    assert result["checked"][0]["ticker"] == "AAPL"
    assert result["crossed"] == []  # first sighting -- baseline only


def test_run_price_check_missing_list_file_degrades_to_empty(db_conn, monkeypatch, tmp_path):
    monkeypatch.setattr(
        "mytrader.price_check.config.PRICE_CHECK_LIST_PATH", tmp_path / "does-not-exist.md",
    )
    result = price_check.run_price_check(db_conn)
    assert result == {"checked": [], "crossed": []}


def test_run_price_check_first_run_establishes_baseline_without_crossing(db_conn, monkeypatch):
    db.upsert_price_check(db_conn, ticker="AAPL", name="Apple Inc.", target_price=200.0)
    _disable_list_sync(monkeypatch)
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
    _disable_list_sync(monkeypatch)
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
    _disable_list_sync(monkeypatch)
    monkeypatch.setattr("mytrader.price_check.market_data.fetch_current_price", lambda ticker: 205.0)

    result = price_check.run_price_check(db_conn)

    assert len(result["crossed"]) == 1
    assert result["crossed"][0]["from_side"] == "below"
    assert result["crossed"][0]["side"] == "above"


def test_run_price_check_stays_quiet_when_side_unchanged(db_conn, monkeypatch):
    db.upsert_price_check(db_conn, ticker="AAPL", name=None, target_price=200.0)
    db.update_price_check_side(db_conn, "AAPL", side="above", price=210.0)
    _disable_list_sync(monkeypatch)
    monkeypatch.setattr("mytrader.price_check.market_data.fetch_current_price", lambda ticker: 212.0)

    result = price_check.run_price_check(db_conn)

    assert result["crossed"] == []
    assert result["checked"][0]["side"] == "above"


def test_run_price_check_fires_again_on_a_second_crossing_back(db_conn, monkeypatch):
    """Unlike a one-time breakout alert, a price check is a live watch level --
    crossing back and forth must alert every time, not just once."""
    db.upsert_price_check(db_conn, ticker="AAPL", name=None, target_price=200.0)
    db.update_price_check_side(db_conn, "AAPL", side="above", price=210.0)
    _disable_list_sync(monkeypatch)

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
    _disable_list_sync(monkeypatch)
    monkeypatch.setattr("mytrader.price_check.market_data.fetch_current_price", lambda ticker: None)

    result = price_check.run_price_check(db_conn)

    assert result["crossed"] == []
    assert result["checked"][0]["price"] is None
    row = db.get_price_check(db_conn, "AAPL")
    assert row["last_side"] is None  # never updated, nothing to persist


def test_run_price_check_price_exactly_at_target_counts_as_above(db_conn, monkeypatch):
    db.upsert_price_check(db_conn, ticker="AAPL", name=None, target_price=200.0)
    _disable_list_sync(monkeypatch)
    monkeypatch.setattr("mytrader.price_check.market_data.fetch_current_price", lambda ticker: 200.0)

    result = price_check.run_price_check(db_conn)
    assert result["checked"][0]["side"] == "above"


# --- report + notify ---------------------------------------------------------


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
    assert "price-check-list.md is empty" in report
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
