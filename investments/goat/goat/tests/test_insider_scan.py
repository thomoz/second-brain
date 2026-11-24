from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
from mytrader import db as mt_db

from goat import config as goat_config, db as goat_db, insider_scan


def _seed_holding(conn, ticker="VRTX", bucket="1"):
    mt_db.upsert_holding(
        conn, ticker=ticker, name="Vertex Pharmaceuticals", asset_type="stock",
        bucket=bucket, qty=1.0, avg_price=100.0,
    )


def _sale_row(ticker="VRTX", trade_date=None, value=2_000_000.0, pct_owned_change=None):
    return {
        "ticker": ticker,
        "filing_date": (trade_date or date.today()).isoformat(),
        "trade_date": (trade_date or date.today()).isoformat(),
        "insider_name": "Jane Doe",
        "title": "CFO",
        "trade_type_code": "S",
        "value": value,
        "pct_owned_change": pct_owned_change,
    }


def _purchase_row(ticker="ACME", trade_date=None, value=30_000.0, pct_owned_change=None, owned=None, price=None):
    row = {
        "ticker": ticker,
        "filing_date": (trade_date or date.today()).isoformat(),
        "trade_date": (trade_date or date.today()).isoformat(),
        "insider_name": "John Smith",
        "title": "Director",
        "trade_type_code": "P",
        "value": value,
        "pct_owned_change": pct_owned_change,
    }
    if owned is not None:
        row["owned"] = owned
    if price is not None:
        row["price"] = price
    return row


def test_run_holdings_watch_alerts_on_new_sale_filing(db_conn, monkeypatch):
    _seed_holding(db_conn, ticker="VRTX")
    monkeypatch.setattr(
        "goat.insider_scan.openinsider.fetch_screener_filings",
        lambda tickers_list, trade_type, min_value: [_sale_row()] if trade_type == "S" else [],
    )
    result = insider_scan.run_holdings_watch(db_conn)
    assert len(result["new_alerts"]) == 1
    assert "VRTX" in result["new_alerts"][0]["message"]
    assert "2,000,000" in result["new_alerts"][0]["message"]


def test_run_holdings_watch_message_includes_pct_owned_change_when_present(db_conn, monkeypatch):
    _seed_holding(db_conn, ticker="VRTX")
    monkeypatch.setattr(
        "goat.insider_scan.openinsider.fetch_screener_filings",
        lambda tickers_list, trade_type, min_value: (
            [_sale_row(pct_owned_change=-91.0)] if trade_type == "S" else []
        ),
    )
    result = insider_scan.run_holdings_watch(db_conn)
    assert "(91% of position)" in result["new_alerts"][0]["message"]


def test_run_holdings_watch_message_omits_pct_clause_when_none(db_conn, monkeypatch):
    _seed_holding(db_conn, ticker="VRTX")
    monkeypatch.setattr(
        "goat.insider_scan.openinsider.fetch_screener_filings",
        lambda tickers_list, trade_type, min_value: (
            [_sale_row(pct_owned_change=None)] if trade_type == "S" else []
        ),
    )
    result = insider_scan.run_holdings_watch(db_conn)
    assert "of position" not in result["new_alerts"][0]["message"]


def test_run_holdings_watch_suppresses_first_sale_under_10pct_threshold(db_conn, monkeypatch):
    _seed_holding(db_conn, ticker="VRTX")
    monkeypatch.setattr(
        "goat.insider_scan.openinsider.fetch_screener_filings",
        lambda tickers_list, trade_type, min_value: (
            [_sale_row(pct_owned_change=-5.0)] if trade_type == "S" else []
        ),
    )
    result = insider_scan.run_holdings_watch(db_conn)
    assert result["new_alerts"] == []


def test_run_holdings_watch_alerts_first_sale_at_10pct_threshold(db_conn, monkeypatch):
    _seed_holding(db_conn, ticker="VRTX")
    monkeypatch.setattr(
        "goat.insider_scan.openinsider.fetch_screener_filings",
        lambda tickers_list, trade_type, min_value: (
            [_sale_row(pct_owned_change=-10.0)] if trade_type == "S" else []
        ),
    )
    result = insider_scan.run_holdings_watch(db_conn)
    assert len(result["new_alerts"]) == 1


def test_run_holdings_watch_alerts_repeat_sale_above_1pct_when_prior_sale_within_90_days(db_conn, monkeypatch):
    _seed_holding(db_conn, ticker="VRTX")
    prior_date = (date.today() - timedelta(days=30)).isoformat()
    goat_db.insert_goat_insider_filing_seen(
        db_conn, dedup_key="prior-sale-key", ticker="VRTX", filing_date=prior_date,
        trade_date=prior_date, insider_name="Jane Doe", trade_type="S", value=50_000.0,
        kind="holdings_watch", pct_owned_change=-3.0,
    )
    monkeypatch.setattr(
        "goat.insider_scan.openinsider.fetch_screener_filings",
        lambda tickers_list, trade_type, min_value: (
            [_sale_row(pct_owned_change=-2.0)] if trade_type == "S" else []
        ),
    )
    result = insider_scan.run_holdings_watch(db_conn)
    assert len(result["new_alerts"]) == 1
    assert "cumulative exit risk" in result["new_alerts"][0]["message"]


def test_run_holdings_watch_suppresses_repeat_sale_under_1pct_threshold(db_conn, monkeypatch):
    _seed_holding(db_conn, ticker="VRTX")
    prior_date = (date.today() - timedelta(days=30)).isoformat()
    goat_db.insert_goat_insider_filing_seen(
        db_conn, dedup_key="prior-sale-key-2", ticker="VRTX", filing_date=prior_date,
        trade_date=prior_date, insider_name="Jane Doe", trade_type="S", value=50_000.0,
        kind="holdings_watch", pct_owned_change=-3.0,
    )
    monkeypatch.setattr(
        "goat.insider_scan.openinsider.fetch_screener_filings",
        lambda tickers_list, trade_type, min_value: (
            [_sale_row(pct_owned_change=-0.5)] if trade_type == "S" else []
        ),
    )
    result = insider_scan.run_holdings_watch(db_conn)
    assert result["new_alerts"] == []


def test_run_holdings_watch_ignores_prior_sale_outside_90_day_window(db_conn, monkeypatch):
    _seed_holding(db_conn, ticker="VRTX")
    old_date = (date.today() - timedelta(days=120)).isoformat()
    goat_db.insert_goat_insider_filing_seen(
        db_conn, dedup_key="old-sale-key", ticker="VRTX", filing_date=old_date,
        trade_date=old_date, insider_name="Jane Doe", trade_type="S", value=50_000.0,
        kind="holdings_watch", pct_owned_change=-3.0,
    )
    monkeypatch.setattr(
        "goat.insider_scan.openinsider.fetch_screener_filings",
        lambda tickers_list, trade_type, min_value: (
            [_sale_row(pct_owned_change=-2.0)] if trade_type == "S" else []
        ),
    )
    result = insider_scan.run_holdings_watch(db_conn)
    assert result["new_alerts"] == []  # treated as a first sale (10% bar) -- the 120-day-old sale doesn't count


def test_run_holdings_watch_stays_quiet_on_repeat_run(db_conn, monkeypatch):
    _seed_holding(db_conn, ticker="VRTX")
    monkeypatch.setattr(
        "goat.insider_scan.openinsider.fetch_screener_filings",
        lambda tickers_list, trade_type, min_value: [_sale_row()] if trade_type == "S" else [],
    )
    insider_scan.run_holdings_watch(db_conn)
    result = insider_scan.run_holdings_watch(db_conn)
    assert result["new_alerts"] == []


def test_run_holdings_watch_skips_fetch_when_no_holdings(db_conn, monkeypatch):
    calls = []
    monkeypatch.setattr(
        "goat.insider_scan.openinsider.fetch_screener_filings",
        lambda tickers_list, trade_type, min_value: calls.append(1),
    )
    result = insider_scan.run_holdings_watch(db_conn)
    assert calls == []
    assert result == {
        "checked_holdings": 0, "new_alerts": [], "recent_filings": [],
        "new_cluster_alerts": [], "new_flip_alerts": [], "context_rows": [],
    }


def test_run_holdings_watch_handles_total_fetch_failure_gracefully(db_conn, monkeypatch):
    _seed_holding(db_conn, ticker="VRTX")
    monkeypatch.setattr(
        "goat.insider_scan.openinsider.fetch_screener_filings",
        lambda tickers_list, trade_type, min_value: None,
    )
    result = insider_scan.run_holdings_watch(db_conn)  # must not raise
    assert result["new_alerts"] == []


def test_run_holdings_watch_ignores_filing_outside_lookback_window(db_conn, monkeypatch):
    _seed_holding(db_conn, ticker="VRTX")
    stale_date = date.today() - timedelta(days=config_lookback_plus_one())
    monkeypatch.setattr(
        "goat.insider_scan.openinsider.fetch_screener_filings",
        lambda tickers_list, trade_type, min_value: (
            [_sale_row(trade_date=stale_date)] if trade_type == "S" else []
        ),
    )
    result = insider_scan.run_holdings_watch(db_conn)
    assert result["new_alerts"] == []


def config_lookback_plus_one() -> int:
    return goat_config.GOAT_INSIDER_HOLDINGS_WATCH_LOOKBACK_DAYS + 1


def test_run_holdings_watch_includes_late_filed_old_trade(db_conn, monkeypatch):
    # Shaun 2026-11-09: the lookback gate must check filing_date, not trade_date
    # -- fetch_screener_filings's own fd= param is filing-date-scoped, so a Form 4
    # filed a few days late (past the legal 2-business-day window, same shape as
    # the UPBD regression -- filed 2-3 days after trading) must still get
    # through, even though the trade itself is now older than the lookback
    # window measured from today. Checking trade_date here silently dropped
    # exactly this case.
    _seed_holding(db_conn, ticker="VRTX")
    lookback = goat_config.GOAT_INSIDER_HOLDINGS_WATCH_LOOKBACK_DAYS
    filing_date = date.today() - timedelta(days=lookback)  # filing itself still fresh
    old_trade_date = filing_date - timedelta(days=2)  # traded 2 days before filing (prompt)
    row = _sale_row(ticker="VRTX", trade_date=old_trade_date)
    row["filing_date"] = filing_date.isoformat()
    monkeypatch.setattr(
        "goat.insider_scan.openinsider.fetch_screener_filings",
        lambda tickers_list, trade_type, min_value: ([row] if trade_type == "S" else []),
    )
    result = insider_scan.run_holdings_watch(db_conn)
    assert len(result["new_alerts"]) == 1


def test_run_holdings_watch_excludes_months_late_catch_up_filing(db_conn, monkeypatch):
    # Shaun 2026-11-09: "don't they have to file within 48 hours?" -- a filing
    # that's fresh (within the lookback) but reports a trade from months ago is
    # not the UPBD case (filed 2-3 days late), it's a chronically-late filer
    # whose "signal" isn't real-time any more. Confirmed live: VISM (78/217 days
    # late), YPF (103), TRAD (204/251), VRNS (259).
    _seed_holding(db_conn, ticker="VRTX")
    filing_date = date.today()
    months_late_trade_date = filing_date - timedelta(days=120)
    row = _sale_row(ticker="VRTX", trade_date=months_late_trade_date)
    row["filing_date"] = filing_date.isoformat()
    monkeypatch.setattr(
        "goat.insider_scan.openinsider.fetch_screener_filings",
        lambda tickers_list, trade_type, min_value: ([row] if trade_type == "S" else []),
    )
    result = insider_scan.run_holdings_watch(db_conn)
    assert result["new_alerts"] == []


def test_run_discovery_scan_stages_new_purchase_candidate(db_conn, monkeypatch):
    monkeypatch.setattr(
        "goat.insider_scan.openinsider.fetch_discovery_purchases",
        lambda: [_purchase_row(ticker="ACME")],
    )
    result = insider_scan.run_discovery_scan(db_conn)
    assert len(result["new_candidates"]) == 1
    row = goat_db.get_goat_pending_candidate(db_conn, "ACME")
    assert row is not None
    assert row["source"] == "goat_insider_discovery"


def test_run_discovery_scan_includes_late_filed_old_trade(db_conn, monkeypatch):
    # Same reasoning as test_run_holdings_watch_includes_late_filed_old_trade --
    # fetch_discovery_purchases's fd= param is filing-date-scoped specifically to
    # backfill late filings, so the freshness gate downstream must check
    # filing_date too, not trade_date -- but the filing must still have been
    # prompt (traded only 2 days before filing, same shape as UPBD).
    filing_date = date.today() - timedelta(days=goat_config.GOAT_INSIDER_DISCOVERY_LOOKBACK_DAYS)
    old_trade_date = filing_date - timedelta(days=2)
    row = _purchase_row(ticker="ACME", trade_date=old_trade_date)
    row["filing_date"] = filing_date.isoformat()
    monkeypatch.setattr(
        "goat.insider_scan.openinsider.fetch_discovery_purchases",
        lambda: [row],
    )
    result = insider_scan.run_discovery_scan(db_conn)
    assert len(result["new_candidates"]) == 1


def test_run_discovery_scan_excludes_months_late_catch_up_filing(db_conn, monkeypatch):
    # Shaun 2026-11-09: a fresh filing_date alone isn't enough -- a trade from
    # months ago, only now catching up on paperwork, isn't a real-time signal.
    # Confirmed live: VISM (78/217 days late), YPF (103), TRAD (204/251), VRNS (259).
    filing_date = date.today()
    months_late_trade_date = filing_date - timedelta(days=120)
    row = _purchase_row(ticker="ACME", trade_date=months_late_trade_date)
    row["filing_date"] = filing_date.isoformat()
    monkeypatch.setattr(
        "goat.insider_scan.openinsider.fetch_discovery_purchases",
        lambda: [row],
    )
    result = insider_scan.run_discovery_scan(db_conn)
    assert result["new_candidates"] == []


def test_run_discovery_scan_candidate_detail_includes_pct_owned_change(db_conn, monkeypatch):
    monkeypatch.setattr(
        "goat.insider_scan.openinsider.fetch_discovery_purchases",
        lambda: [_purchase_row(ticker="ACME", pct_owned_change=45.0)],
    )
    result = insider_scan.run_discovery_scan(db_conn)
    assert "(45% of position)" in result["new_candidates"][0]["detail"]


def test_run_discovery_scan_alerts_on_held_ticker_but_skips_pending_insert(db_conn, monkeypatch):
    _seed_holding(db_conn, ticker="ACME")
    monkeypatch.setattr(
        "goat.insider_scan.openinsider.fetch_discovery_purchases",
        lambda: [_purchase_row(ticker="ACME")],
    )
    result = insider_scan.run_discovery_scan(db_conn)
    assert len(result["new_candidates"]) == 1
    assert goat_db.get_goat_pending_candidate(db_conn, "ACME") is None


def test_run_discovery_scan_alerts_and_inserts_for_watchlisted_ticker(db_conn, monkeypatch):
    mt_db.upsert_watchlist_row(
        db_conn, ticker="ACME", name="Acme Corp", asset_type="stock", bucket="unassigned",
    )
    monkeypatch.setattr(
        "goat.insider_scan.openinsider.fetch_discovery_purchases",
        lambda: [_purchase_row(ticker="ACME")],
    )
    result = insider_scan.run_discovery_scan(db_conn)
    assert len(result["new_candidates"]) == 1
    assert goat_db.get_goat_pending_candidate(db_conn, "ACME") is not None


def test_run_discovery_scan_skips_banned_ticker(db_conn, monkeypatch):
    monkeypatch.setattr(goat_config, "GOAT_BANNED_TICKERS", {"ACME"})
    monkeypatch.setattr(
        "goat.insider_scan.openinsider.fetch_discovery_purchases",
        lambda: [_purchase_row(ticker="ACME")],
    )
    result = insider_scan.run_discovery_scan(db_conn)
    assert result["new_candidates"] == []
    assert goat_db.get_goat_pending_candidate(db_conn, "ACME") is None


def _inst_purchase_row(ticker, insider_name, title):
    row = _purchase_row(ticker=ticker)
    row["insider_name"] = insider_name
    row["title"] = title
    return row


def test_is_institutional_10pct_filer_classification():
    inst = insider_scan._is_institutional_10pct_filer
    # dropped: corporate-designator name + bare "10%" / remarks title
    assert inst("Metlife Investment Management, LLC", "10%") is True
    assert inst("Saba Capital Management, L.P.", "10%") is True
    assert inst("Winmill & Co. Inc", 'See "Explanation of Responses"') is True
    assert inst("Cascade Investment, L.L.C.", "10%") is True
    assert inst("Donegal Mutual Insurance Co", "10%") is True
    assert inst("B&R Technology Sponsor LLC (Cayman)", "10%") is True
    assert inst("Goldentree Asset Management LP", "10%") is True
    # kept: individuals (no corporate designator), even at 10%
    assert inst("Lynch Timothy P", "10%") is False
    assert inst("Rady Ernest S", "Exec COB, 10%") is False
    assert inst("Chernett Jorey", "10%") is False
    # kept: entity that also holds a board seat
    assert inst("Haveli Investments, L.P.", "Dir, 10%") is False
    assert inst("Perceptive Advisors LLC", "Dir") is False
    # kept: empty / missing name
    assert inst("", "10%") is False


def test_run_discovery_scan_skips_institutional_10pct_filer(db_conn, monkeypatch):
    monkeypatch.setattr(
        "goat.insider_scan.openinsider.fetch_discovery_purchases",
        lambda: [_inst_purchase_row("CHI", "Metlife Investment Management, LLC", "10%")],
    )
    result = insider_scan.run_discovery_scan(db_conn)
    assert result["new_candidates"] == []
    assert goat_db.get_goat_pending_candidate(db_conn, "CHI") is None
    # dropped before any goat_insider_filings_seen row is written
    assert goat_db.get_recent_insider_filings_seen(db_conn, kind="discovery") == []


def test_run_discovery_scan_keeps_individual_10pct_owner(db_conn, monkeypatch):
    monkeypatch.setattr(
        "goat.insider_scan.openinsider.fetch_discovery_purchases",
        lambda: [_inst_purchase_row("AEON", "Lynch Timothy P", "10%")],
    )
    result = insider_scan.run_discovery_scan(db_conn)
    assert len(result["new_candidates"]) == 1
    assert goat_db.get_goat_pending_candidate(db_conn, "AEON") is not None


def test_run_discovery_scan_keeps_entity_filer_with_board_seat(db_conn, monkeypatch):
    monkeypatch.setattr(
        "goat.insider_scan.openinsider.fetch_discovery_purchases",
        lambda: [_inst_purchase_row("BLND", "Haveli Investments, L.P.", "Dir, 10%")],
    )
    result = insider_scan.run_discovery_scan(db_conn)
    assert len(result["new_candidates"]) == 1


def test_run_discovery_scan_institutional_filter_can_be_disabled(db_conn, monkeypatch):
    monkeypatch.setattr(goat_config, "GOAT_INSIDER_DISCOVERY_EXCLUDE_INSTITUTIONAL_10PCT", False)
    monkeypatch.setattr(
        "goat.insider_scan.openinsider.fetch_discovery_purchases",
        lambda: [_inst_purchase_row("CHI", "Metlife Investment Management, LLC", "10%")],
    )
    result = insider_scan.run_discovery_scan(db_conn)
    assert len(result["new_candidates"]) == 1


def test_run_discovery_scan_stays_quiet_on_repeat_run(db_conn, monkeypatch):
    monkeypatch.setattr(
        "goat.insider_scan.openinsider.fetch_discovery_purchases",
        lambda: [_purchase_row(ticker="ACME")],
    )
    insider_scan.run_discovery_scan(db_conn)
    result = insider_scan.run_discovery_scan(db_conn)
    # Each run clears + re-stages pending_candidates from scratch (Shaun 2026-11-09,
    # same precedent as dma_breakout_scan) -- an already-seen filing isn't newly_seen
    # on the second run, so it isn't re-staged. Report shows the latest day's trade
    # data scraped, not an accumulating backlog of never-reviewed candidates.
    assert result["new_candidates"] == []
    assert result["pending_candidates"] == []


def test_run_discovery_scan_handles_fetch_failure_gracefully(db_conn, monkeypatch):
    monkeypatch.setattr(
        "goat.insider_scan.openinsider.fetch_discovery_purchases",
        lambda: None,
    )
    result = insider_scan.run_discovery_scan(db_conn)  # must not raise
    assert result["new_candidates"] == []


def test_check_buy_cluster_fires_on_second_distinct_insider(db_conn, monkeypatch):
    today = date.today()
    row_a = _purchase_row(ticker="ACME", trade_date=today)
    row_a["insider_name"] = "John Smith"
    row_b = _purchase_row(ticker="ACME", trade_date=today - timedelta(days=3))
    row_b["insider_name"] = "Jane Doe"
    monkeypatch.setattr(
        "goat.insider_scan.openinsider.fetch_discovery_purchases",
        lambda: [row_a, row_b],
    )
    result = insider_scan.run_discovery_scan(db_conn)
    assert len(result["new_cluster_alerts"]) == 1
    assert set(result["new_cluster_alerts"][0]["insiders"]) == {"John Smith", "Jane Doe"}


def test_check_buy_cluster_catches_a_slow_two_week_formation(db_conn, monkeypatch):
    # The older leg is seeded directly into goat_insider_filings_seen (as if
    # captured by a prior day's run when it was still fresh) rather than
    # returned from today's fetch_discovery_purchases mock -- a 13-day-old row
    # would never survive run_discovery_scan's own 5-day freshness lookback
    # (GOAT_INSIDER_DISCOVERY_LOOKBACK_DAYS), which is a separate concern from
    # _check_buy_cluster's 14-day cluster window.
    today = date.today()
    old_date = today - timedelta(days=13)
    goat_db.insert_goat_insider_filing_seen(
        db_conn, dedup_key="slow-cluster-key", ticker="ACME", filing_date=old_date.isoformat(),
        trade_date=old_date.isoformat(), insider_name="Jane Doe", trade_type="P",
        value=30_000.0, kind="discovery",
    )
    row_a = _purchase_row(ticker="ACME", trade_date=today)
    row_a["insider_name"] = "John Smith"
    monkeypatch.setattr(
        "goat.insider_scan.openinsider.fetch_discovery_purchases",
        lambda: [row_a],
    )
    result = insider_scan.run_discovery_scan(db_conn)
    assert len(result["new_cluster_alerts"]) == 1


def test_check_buy_cluster_does_not_refire_on_third_insider(db_conn, monkeypatch):
    today = date.today()
    row_a = _purchase_row(ticker="ACME", trade_date=today)
    row_a["insider_name"] = "John Smith"
    row_b = _purchase_row(ticker="ACME", trade_date=today)
    row_b["insider_name"] = "Jane Doe"
    monkeypatch.setattr(
        "goat.insider_scan.openinsider.fetch_discovery_purchases",
        lambda: [row_a, row_b],
    )
    first_result = insider_scan.run_discovery_scan(db_conn)
    assert len(first_result["new_cluster_alerts"]) == 1

    row_c = _purchase_row(ticker="ACME", trade_date=today)
    row_c["insider_name"] = "Sam Third"
    monkeypatch.setattr(
        "goat.insider_scan.openinsider.fetch_discovery_purchases",
        lambda: [row_c],
    )
    second_result = insider_scan.run_discovery_scan(db_conn)
    assert len(second_result["new_cluster_alerts"]) == 0


def test_check_buy_cluster_ignores_filings_outside_window(db_conn, monkeypatch):
    # Older leg seeded directly, same reasoning as the slow-formation test above
    # -- it's older than the discovery scan's own 5-day freshness lookback too.
    today = date.today()
    old_date = today - timedelta(days=goat_config.GOAT_INSIDER_CLUSTER_ALERT_WINDOW_DAYS + 1)
    goat_db.insert_goat_insider_filing_seen(
        db_conn, dedup_key="outside-window-key", ticker="ACME", filing_date=old_date.isoformat(),
        trade_date=old_date.isoformat(), insider_name="Jane Doe", trade_type="P",
        value=30_000.0, kind="discovery",
    )
    row_a = _purchase_row(ticker="ACME", trade_date=today)
    row_a["insider_name"] = "John Smith"
    monkeypatch.setattr(
        "goat.insider_scan.openinsider.fetch_discovery_purchases",
        lambda: [row_a],
    )
    result = insider_scan.run_discovery_scan(db_conn)
    assert result["new_cluster_alerts"] == []


def test_check_buy_cluster_does_not_count_sells(db_conn, monkeypatch):
    today = date.today()
    goat_db.insert_goat_insider_filing_seen(
        db_conn, dedup_key="sell-key", ticker="ACME", filing_date=today.isoformat(),
        trade_date=today.isoformat(), insider_name="Jane Doe", trade_type="S",
        value=50_000.0, kind="discovery_sell",
    )
    row_a = _purchase_row(ticker="ACME", trade_date=today)
    row_a["insider_name"] = "John Smith"
    monkeypatch.setattr(
        "goat.insider_scan.openinsider.fetch_discovery_purchases",
        lambda: [row_a],
    )
    result = insider_scan.run_discovery_scan(db_conn)
    assert result["new_cluster_alerts"] == []


def test_check_buy_cluster_fires_for_held_ticker_via_holdings_watch(db_conn, monkeypatch):
    _seed_holding(db_conn, ticker="ACME")
    today = date.today()
    row_a = _purchase_row(ticker="ACME", trade_date=today)
    row_a["insider_name"] = "John Smith"
    row_b = _purchase_row(ticker="ACME", trade_date=today - timedelta(days=3))
    row_b["insider_name"] = "Jane Doe"
    monkeypatch.setattr(
        "goat.insider_scan.openinsider.fetch_screener_filings",
        lambda tickers_list, trade_type, min_value: [row_a, row_b] if trade_type == "P" else [],
    )
    result = insider_scan.run_holdings_watch(db_conn)
    assert len(result["new_cluster_alerts"]) == 1


def test_check_insider_flip_fires_on_buyback_within_window(db_conn, monkeypatch):
    today = date.today()
    sale_date = (today - timedelta(days=30)).isoformat()
    goat_db.insert_goat_insider_filing_seen(
        db_conn, dedup_key="flip-sale-key", ticker="ACME", filing_date=sale_date,
        trade_date=sale_date, insider_name="John Smith", trade_type="S",
        value=50_000.0, kind="discovery_sell",
    )
    row = _purchase_row(ticker="ACME", trade_date=today, value=92_000.0, owned="10,000", price="10.00")
    row["insider_name"] = "John Smith"
    row["company_name"] = "Acme Corporation"
    monkeypatch.setattr(
        "goat.insider_scan.openinsider.fetch_discovery_purchases",
        lambda: [row],
    )
    result = insider_scan.run_discovery_scan(db_conn)
    assert len(result["new_flip_alerts"]) == 1
    flip = result["new_flip_alerts"][0]
    assert flip["days_between"] == 30
    assert flip["company_name"] == "Acme Corporation"
    assert flip["buy_value"] == 92_000.0
    assert flip["pct_of_position_value"] == 92.0


def test_check_insider_flip_ignores_sale_outside_window(db_conn, monkeypatch):
    today = date.today()
    sale_date = (today - timedelta(days=goat_config.GOAT_INSIDER_FLIP_WINDOW_DAYS + 1)).isoformat()
    goat_db.insert_goat_insider_filing_seen(
        db_conn, dedup_key="flip-old-sale-key", ticker="ACME", filing_date=sale_date,
        trade_date=sale_date, insider_name="John Smith", trade_type="S",
        value=50_000.0, kind="discovery_sell",
    )
    row = _purchase_row(ticker="ACME", trade_date=today)
    row["insider_name"] = "John Smith"
    monkeypatch.setattr(
        "goat.insider_scan.openinsider.fetch_discovery_purchases",
        lambda: [row],
    )
    result = insider_scan.run_discovery_scan(db_conn)
    assert result["new_flip_alerts"] == []


def test_check_insider_flip_requires_same_insider(db_conn, monkeypatch):
    today = date.today()
    sale_date = (today - timedelta(days=30)).isoformat()
    goat_db.insert_goat_insider_filing_seen(
        db_conn, dedup_key="flip-other-sale-key", ticker="ACME", filing_date=sale_date,
        trade_date=sale_date, insider_name="Jane Doe", trade_type="S",
        value=50_000.0, kind="discovery_sell",
    )
    row = _purchase_row(ticker="ACME", trade_date=today)
    row["insider_name"] = "John Smith"
    monkeypatch.setattr(
        "goat.insider_scan.openinsider.fetch_discovery_purchases",
        lambda: [row],
    )
    result = insider_scan.run_discovery_scan(db_conn)
    assert result["new_flip_alerts"] == []


def test_check_insider_flip_ignores_a_buy_with_no_prior_sale(db_conn, monkeypatch):
    row = _purchase_row(ticker="ACME", trade_date=date.today())
    row["insider_name"] = "John Smith"
    monkeypatch.setattr(
        "goat.insider_scan.openinsider.fetch_discovery_purchases",
        lambda: [row],
    )
    result = insider_scan.run_discovery_scan(db_conn)
    assert result["new_flip_alerts"] == []


def test_maybe_notify_insider_flips_includes_company_value_and_position_pct(monkeypatch):
    # Shaun 2026-11-24: the flip alert needs the company name, the dollar value
    # of the buy-back, and what % of the insider's total position in the
    # company that buy-back represents -- same metric as _pct_of_position_value.
    import sys
    toast_calls, whatsapp_calls = [], []
    monkeypatch.setitem(sys.modules, "notifications", _fake_notifications_module(toast_calls, whatsapp_calls))

    insider_scan.maybe_notify_insider_flips([{
        "ticker": "ACME", "company_name": "Acme Corporation", "insider_name": "John Smith",
        "sale_date": "2026-10-25", "sale_value": 50_000.0,
        "buy_date": "2026-11-24", "buy_value": 92_000.0,
        "pct_of_position_value": 92.0, "days_between": 30,
    }])
    assert len(whatsapp_calls) == 1
    (message,), _kwargs = whatsapp_calls[0]
    assert "ACME (Acme Corporation)" in message
    assert "John Smith sold $50,000 on 2026-10-25" in message
    assert "bought back $92,000 on 2026-11-24" in message
    assert "92% of their position in the company" in message
    assert "30d later" in message


def test_maybe_notify_insider_flips_omits_position_pct_when_unknown(monkeypatch):
    import sys
    toast_calls, whatsapp_calls = [], []
    monkeypatch.setitem(sys.modules, "notifications", _fake_notifications_module(toast_calls, whatsapp_calls))

    insider_scan.maybe_notify_insider_flips([{
        "ticker": "ACME", "company_name": None, "insider_name": "John Smith",
        "sale_date": "2026-10-25", "sale_value": 50_000.0,
        "buy_date": "2026-11-24", "buy_value": 92_000.0,
        "pct_of_position_value": None, "days_between": 30,
    }])
    (message,), _kwargs = whatsapp_calls[0]
    assert "of their position in the company" not in message
    assert "ACME:" in message


def test_render_insider_scan_report_lists_alerts_and_pending_candidates():
    watch_result = {
        "checked_holdings": 2,
        "new_alerts": [{"ticker": "VRTX", "message": "Jane Doe (CFO) sold $2,000,000 of VRTX on 2026-08-17"}],
    }
    discovery_result = {
        "pending_candidates": [
            {"ticker": "ACME", "sector_label": "Insider Buy",
             "signal_detail": "John Smith (Director) bought $30,000 of ACME on 2026-08-17",
             "flagged_at": "2026-08-17T00:00:00+00:00"},
        ],
    }
    report = insider_scan.render_insider_scan_report(watch_result, discovery_result)
    assert "VRTX" in report
    assert "2,000,000" in report
    assert "ACME" in report

    empty_watch = {"checked_holdings": 0, "new_alerts": []}
    empty_discovery = {"pending_candidates": []}
    empty_report = insider_scan.render_insider_scan_report(empty_watch, empty_discovery)
    assert "No new insider activity on current holdings." in empty_report
    assert "No insider filings recorded yet for current holdings." in empty_report


def test_render_discovery_rows_includes_trade_date_column():
    """Real gap caught 2026-10-01: Discovery Candidates tables had no dedicated
    Trade Date column -- the insider's actual trade date was only buried inside
    the long Signal sentence, unlike the Holdings Filings tables which already
    show it as its own column. Fixed by adding one, sourced from the same
    trade_date DB column already used for sorting (by_date)."""
    watch_result = {"checked_holdings": 0, "new_alerts": []}
    discovery_result = {
        "pending_candidates": [
            {"ticker": "ACME", "sector_label": "Insider Buy",
             "signal_detail": "John Smith (Director) bought $30,000 of ACME on 2026-08-17",
             "flagged_at": "2026-08-17T00:00:00+00:00", "trade_date": "2026-08-17"},
        ],
    }
    report = insider_scan.render_insider_scan_report(watch_result, discovery_result)
    assert "| Ticker | Sector | Signal | Trade Date | Price Since Trade | Flagged |" in report
    assert "| ACME | Insider Buy | John Smith (Director) bought $30,000 of ACME on 2026-08-17 | 2026-08-17 |" in report


def test_render_discovery_rows_shows_na_when_trade_date_missing():
    watch_result = {"checked_holdings": 0, "new_alerts": []}
    discovery_result = {
        "pending_candidates": [
            {"ticker": "ACME", "sector_label": "Insider Buy", "signal_detail": "detail",
             "flagged_at": "2026-08-17T00:00:00+00:00"},
        ],
    }
    report = insider_scan.render_insider_scan_report(watch_result, discovery_result)
    assert "| ACME | Insider Buy | detail | n/a |" in report


def _price_series(days_ago: int, start_price: float, end_price: float) -> tuple[str, pd.Series]:
    """A close series that starts exactly on trade_date (days_ago days back)
    at start_price and sits at end_price for every day since, so
    _price_move_since's on/after-trade_date slice picks up start_price first
    and end_price last -- gives a deterministic pct_change for testing."""
    trade_date = date.today() - timedelta(days=days_ago)
    idx = pd.date_range(trade_date, periods=max(days_ago, 1) + 1, freq="D")
    prices = [start_price] + [end_price] * (len(idx) - 1)
    return trade_date.isoformat(), pd.Series(prices, index=idx)


def test_compute_discovery_price_performance_includes_chart_note_in_price_note(db_conn, monkeypatch):
    """One shared fetch now feeds both the price-move calc and the chart
    note (2026-09-26, see _price_move_since's docstring) -- a single series,
    flat at 100.0 except a clearly-higher latest close, gives a deterministic
    +% move (from the flat trade-date price to that latest close) *and* a
    deterministic 'above its MAs' trend read from the same data."""
    idx = pd.date_range(end=date.today(), periods=260, freq="D")
    prices = [100.0] * 260
    prices[-1] = 117.4  # latest close, clearly above the flat 100.0 MAs
    series = pd.Series(prices, index=idx)
    trade_date = (date.today() - timedelta(days=10)).isoformat()

    monkeypatch.setattr("mytrader.chart_setup_score.fetch_close", lambda t, lookback_days=None: series)
    candidates = [{"ticker": "THM", "trade_date": trade_date, "price_flag_notified": 0}]
    result = insider_scan.compute_discovery_price_performance(db_conn, candidates)
    assert "+17.4%" in result[0]["price_note"]
    assert "above 150DMA" in result[0]["price_note"]
    assert "above 200DMA" in result[0]["price_note"]
    assert "chart setup score" in result[0]["price_note"]


def test_compute_discovery_price_performance_flags_buy_that_rose_past_threshold(db_conn, monkeypatch):
    trade_date, series = _price_series(days_ago=30, start_price=100.0, end_price=125.0)
    monkeypatch.setattr("mytrader.chart_setup_score.fetch_close", lambda t, lookback_days=None: series)
    candidates = [{"ticker": "ACME", "trade_date": trade_date, "price_flag_notified": 0}]
    result = insider_scan.compute_discovery_price_performance(db_conn, candidates)
    assert "+25.0%" in result[0]["price_note"]
    assert "confirms signal" in result[0]["price_note"]


def test_compute_discovery_price_performance_does_not_flag_below_threshold(db_conn, monkeypatch):
    trade_date, series = _price_series(days_ago=30, start_price=100.0, end_price=105.0)
    monkeypatch.setattr("mytrader.chart_setup_score.fetch_close", lambda t, lookback_days=None: series)
    candidates = [{"ticker": "ACME", "trade_date": trade_date, "price_flag_notified": 0}]
    result = insider_scan.compute_discovery_price_performance(db_conn, candidates)
    assert "confirms signal" not in result[0]["price_note"]


def test_compute_discovery_price_performance_notes_staleness_past_90_days(db_conn, monkeypatch):
    trade_date, series = _price_series(days_ago=95, start_price=100.0, end_price=130.0)
    monkeypatch.setattr("mytrader.chart_setup_score.fetch_close", lambda t, lookback_days=None: series)
    candidates = [{"ticker": "ACME", "trade_date": trade_date, "price_flag_notified": 0}]
    result = insider_scan.compute_discovery_price_performance(db_conn, candidates)
    assert "may not reflect the insider signal anymore" in result[0]["price_note"]


def test_compute_discovery_price_performance_unavailable_without_trade_date(db_conn):
    candidates = [{"ticker": "ACME", "trade_date": None, "price_flag_notified": 0}]
    result = insider_scan.compute_discovery_price_performance(db_conn, candidates)
    assert result[0]["price_note"] == "price unavailable"


def test_compute_discovery_price_performance_unavailable_on_fetch_miss(db_conn, monkeypatch):
    monkeypatch.setattr("mytrader.chart_setup_score.fetch_close", lambda t, lookback_days=None: None)
    candidates = [{"ticker": "ACME", "trade_date": date.today().isoformat(), "price_flag_notified": 0}]
    result = insider_scan.compute_discovery_price_performance(db_conn, candidates)
    assert result[0]["price_note"] == "price unavailable"


def test_compute_discovery_price_performance_marks_newly_flagged_once(db_conn, monkeypatch):
    """Regression test for the 2026-08-18 'notify on crossing' feature: the
    first run over threshold sets newly_flagged + persists the DB guard; a
    second run (flag still up) must not re-fire it."""
    trade_date, series = _price_series(days_ago=30, start_price=100.0, end_price=125.0)
    goat_db.insert_goat_pending_candidate(
        db_conn, ticker="ACME", sector_label="Insider Buy", signal_detail="d",
        source="goat_insider_discovery", trade_date=trade_date,
    )
    monkeypatch.setattr("mytrader.chart_setup_score.fetch_close", lambda t, lookback_days=None: series)

    row = dict(goat_db.get_goat_pending_candidate(db_conn, "ACME"))
    result = insider_scan.compute_discovery_price_performance(db_conn, [row])
    assert result[0]["newly_flagged"] is True
    assert goat_db.get_goat_pending_candidate(db_conn, "ACME")["price_flag_notified"] == 1

    row_again = dict(goat_db.get_goat_pending_candidate(db_conn, "ACME"))
    result_again = insider_scan.compute_discovery_price_performance(db_conn, [row_again])
    assert result_again[0]["newly_flagged"] is False


def test_compute_holdings_watch_price_performance_flags_sale_that_fell(db_conn, monkeypatch):
    trade_date, series = _price_series(days_ago=20, start_price=100.0, end_price=80.0)
    monkeypatch.setattr("mytrader.chart_setup_score.fetch_close", lambda t, lookback_days=None: series)
    filings = [{"ticker": "VRTX", "trade_date": trade_date, "trade_type": "S",
                "dedup_key": "key-1", "price_flag_notified": 0}]
    result = insider_scan.compute_holdings_watch_price_performance(db_conn, filings)
    assert "-20.0%" in result[0]["price_note"]
    assert "confirms signal" in result[0]["price_note"]
    assert result[0]["newly_flagged"] is True


def test_compute_holdings_watch_price_performance_ignores_contrarian_direction(db_conn, monkeypatch):
    # A sale followed by a big price RISE is the contrarian case -- Shaun
    # 2026-08-18 wants only the confirming direction flagged (sale -> fall).
    trade_date, series = _price_series(days_ago=20, start_price=100.0, end_price=130.0)
    monkeypatch.setattr("mytrader.chart_setup_score.fetch_close", lambda t, lookback_days=None: series)
    filings = [{"ticker": "VRTX", "trade_date": trade_date, "trade_type": "S",
                "dedup_key": "key-2", "price_flag_notified": 0}]
    result = insider_scan.compute_holdings_watch_price_performance(db_conn, filings)
    assert "confirms signal" not in result[0]["price_note"]
    assert result[0]["newly_flagged"] is False


def test_compute_holdings_watch_price_performance_does_not_reflag_already_notified(db_conn, monkeypatch):
    trade_date, series = _price_series(days_ago=20, start_price=100.0, end_price=80.0)
    monkeypatch.setattr("mytrader.chart_setup_score.fetch_close", lambda t, lookback_days=None: series)
    filings = [{"ticker": "VRTX", "trade_date": trade_date, "trade_type": "S",
                "dedup_key": "key-3", "price_flag_notified": 1}]
    result = insider_scan.compute_holdings_watch_price_performance(db_conn, filings)
    assert result[0]["newly_flagged"] is False


def _fake_notifications_module(toast_calls, whatsapp_calls):
    import types
    fake_module = types.ModuleType("notifications")
    fake_module.send_toast_notification = lambda *a, **k: toast_calls.append((a, k))
    fake_module.send_whatsapp_notification = lambda *a, **k: whatsapp_calls.append((a, k))
    return fake_module


def test_maybe_notify_price_flags_skips_when_nothing_newly_flagged():
    insider_scan.maybe_notify_price_flags([])  # must not raise, no notification module needed


def test_maybe_notify_price_flags_sends_whatsapp_with_ticker_and_note(monkeypatch):
    import sys
    toast_calls, whatsapp_calls = [], []
    monkeypatch.setitem(sys.modules, "notifications", _fake_notifications_module(toast_calls, whatsapp_calls))

    insider_scan.maybe_notify_price_flags(
        [{
            "ticker": "ACME", "price_note": "+25.0% since trade \U0001F6A9 confirms signal",
            "trade_date": "2026-08-20", "days_since": 18, "company_name": "Acme Corporation",
        }]
    )
    assert len(toast_calls) == 1
    assert len(whatsapp_calls) == 1
    (message,), _kwargs = whatsapp_calls[0]
    assert "ACME" in message
    assert "Acme Corporation" in message
    assert "+25.0% since trade" in message
    assert "18d ago" in message
    assert "2026-08-20" in message


def test_maybe_notify_cluster_alerts_includes_per_buy_detail(monkeypatch):
    # Shaun 2026-11-10: the aggregate insiders/titles/total_value summary alone
    # hid whether a cluster is one big CEO buy plus a token director nibble, or
    # several meaningfully-sized buys -- the alert needs the same per-buy detail
    # as a discovery candidate's signal_detail so he can judge significance from
    # the WhatsApp message alone, without having to check the report.
    import sys
    toast_calls, whatsapp_calls = [], []
    monkeypatch.setitem(sys.modules, "notifications", _fake_notifications_module(toast_calls, whatsapp_calls))
    monkeypatch.setattr(insider_scan, "_fetch_cluster_ticker_data", lambda ticker: None)
    monkeypatch.setattr(insider_scan, "_brief_company_description", lambda data: "Rents furniture and electronics to consumers.")

    insider_scan.maybe_notify_cluster_alerts([{
        "ticker": "UPBD", "company_name": "Upbound Group, Inc.",
        "insiders": ["John Smith", "Jane Doe"], "titles": ["CEO", "Dir"],
        "total_value": 150000.0,
        "rows": [
            {"insider_name": "John Smith", "title": "CEO", "value": 100000.0,
             "trade_date": "2026-11-02", "pct_owned_change": 11.0, "pct_of_position_value": 23.0},
            {"insider_name": "Jane Doe", "title": "Dir", "value": 50000.0,
             "trade_date": "2026-11-03", "pct_owned_change": None, "pct_of_position_value": None},
        ],
    }])
    assert len(whatsapp_calls) == 1
    (message,), _kwargs = whatsapp_calls[0]
    assert "UPBD" in message
    assert "John Smith (CEO) bought $100,000 of UPBD (11% of position, 23% of their total stake) on 2026-11-02" in message
    assert "Jane Doe (Dir) bought $50,000 of UPBD on 2026-11-03" in message
    assert "Upbound Group, Inc." in message
    assert "Rents furniture and electronics to consumers." in message


def test_position_size_clause_combines_delta_and_total_stake():
    assert insider_scan._position_size_clause(
        {"pct_owned_change": 11.0, "pct_of_position_value": 23.0}
    ) == " (11% of position, 23% of their total stake)"


def test_position_size_clause_omits_missing_pieces():
    assert insider_scan._position_size_clause({"pct_owned_change": None, "pct_of_position_value": 23.0}) == " (23% of their total stake)"
    assert insider_scan._position_size_clause({"pct_owned_change": 11.0, "pct_of_position_value": None}) == " (11% of position)"
    assert insider_scan._position_size_clause({"pct_owned_change": None, "pct_of_position_value": None}) == ""


def test_pct_of_position_value_computes_trade_share_of_total_stake():
    # $100k buy, 10,000 shares owned after at $50/share = $500k total stake -> 20%
    row = {"owned": "10,000", "price": "$50.00", "value": 100_000.0}
    assert insider_scan._pct_of_position_value(row) == 20.0


def test_pct_of_position_value_well_defined_for_brand_new_position():
    # Unlike OpenInsider's own ΔOwn ("New" -> undefined), a brand-new position
    # is by definition 100% of the insider's current stake.
    row = {"owned": "1,000", "price": "$10.00", "value": 10_000.0}
    assert insider_scan._pct_of_position_value(row) == 100.0


def test_pct_of_position_value_none_when_fields_missing_or_unparsable():
    assert insider_scan._pct_of_position_value({"owned": None, "price": "$50.00", "value": 100_000.0}) is None
    assert insider_scan._pct_of_position_value({"owned": "10,000", "price": None, "value": 100_000.0}) is None
    assert insider_scan._pct_of_position_value({"owned": "10,000", "price": "$50.00", "value": None}) is None
    assert insider_scan._pct_of_position_value({"owned": "n/a", "price": "$50.00", "value": 100_000.0}) is None


def test_run_discovery_scan_buy_persists_pct_owned_change(db_conn, monkeypatch):
    # Pre-existing gap fixed 2026-11-19 alongside pct_of_position_value: the
    # discovery-scan buy insert never passed pct_owned_change through, so any
    # buy first recorded via discovery (not holdings_watch) always stored NULL
    # here even though OpenInsider reported a real ΔOwn for it.
    row = _purchase_row(pct_owned_change=12.5)
    monkeypatch.setattr("goat.insider_scan.openinsider.fetch_discovery_purchases", lambda: [row])
    insider_scan.run_discovery_scan(db_conn)
    stored = db_conn.execute(
        "SELECT pct_owned_change FROM goat_insider_filings_seen WHERE ticker = 'ACME'"
    ).fetchone()
    assert stored["pct_owned_change"] == 12.5


def test_brief_company_description_uses_first_sentence_of_summary():
    from mytrader.market_data import TickerData

    data = TickerData(
        ticker="NEM",
        info={"longBusinessSummary": "Newmont is a gold miner. It also produces copper and silver."},
        dividends=None,
    )
    assert insider_scan._brief_company_description(data) == "Newmont is a gold miner."


def test_brief_company_description_falls_back_to_sector_industry():
    from mytrader.market_data import TickerData

    data = TickerData(ticker="NEM", info={"sector": "Basic Materials", "industry": "Gold"}, dividends=None)
    assert insider_scan._brief_company_description(data) == "Basic Materials / Gold"


def test_brief_company_description_returns_none_when_data_is_none():
    assert insider_scan._brief_company_description(None) is None


def test_brief_company_description_pulls_in_next_sentence_after_bare_corp_suffix():
    # Real case caught live 2026-11-18 (STUB): the summary's first ". " split
    # falls right after "Inc", leaving just the bare company name with zero
    # actual description unless the next sentence is pulled in too.
    from mytrader.market_data import TickerData

    data = TickerData(
        ticker="STUB",
        info={"longBusinessSummary": "StubHub Holdings, Inc. operates a ticketing marketplace worldwide. It was founded in 2000."},
        dividends=None,
    )
    result = insider_scan._brief_company_description(data)
    assert result == "StubHub Holdings, Inc. operates a ticketing marketplace worldwide."


def test_fetch_cluster_ticker_data_retries_once_after_rate_limit_then_succeeds(monkeypatch):
    # Real case caught live 2026-11-18: a cluster alert's description fetch came
    # back None for every ticker because the scan had already burned through
    # yfinance's rate limit earlier in the same run, even though the identical
    # call succeeded seconds later outside that run.
    from mytrader.market_data import TickerData

    sleep_calls = []
    monkeypatch.setattr(insider_scan.time, "sleep", lambda s: sleep_calls.append(s))
    responses = iter([None, TickerData(ticker="NEM", info={"longBusinessSummary": "Newmont is a gold miner."}, dividends=None)])
    monkeypatch.setattr("mytrader.market_data.fetch_ticker_data", lambda ticker: next(responses))

    data = insider_scan._fetch_cluster_ticker_data("NEM")
    assert data is not None and data.info["longBusinessSummary"] == "Newmont is a gold miner."
    assert sleep_calls == [20]


def test_fetch_cluster_ticker_data_returns_none_when_retry_also_fails(monkeypatch):
    monkeypatch.setattr(insider_scan.time, "sleep", lambda s: None)
    monkeypatch.setattr("mytrader.market_data.fetch_ticker_data", lambda ticker: None)
    assert insider_scan._fetch_cluster_ticker_data("NEM") is None


def test_fetch_cluster_ticker_data_returns_none_on_exception(monkeypatch):
    def _raise(ticker):
        raise RuntimeError("yfinance unavailable")

    monkeypatch.setattr("mytrader.market_data.fetch_ticker_data", _raise)
    assert insider_scan._fetch_cluster_ticker_data("NEM") is None


def test_is_biotech_or_pharma_matches_known_industries():
    from mytrader.market_data import TickerData

    biotech = TickerData(ticker="XYZ", info={"industry": "Biotechnology"}, dividends=None)
    drugmaker = TickerData(ticker="XYZ", info={"industry": "Drug Manufacturers - Specialty & Generic"}, dividends=None)
    assert insider_scan._is_biotech_or_pharma(biotech) is True
    assert insider_scan._is_biotech_or_pharma(drugmaker) is True


def test_is_biotech_or_pharma_false_for_other_healthcare_and_missing_data():
    from mytrader.market_data import TickerData

    # Medical devices/pharmacy retail/hospitals are Healthcare-sector but NOT
    # what Shaun asked to exclude -- only the specific biotech/pharma industries.
    med_device = TickerData(ticker="XYZ", info={"sector": "Healthcare", "industry": "Medical Devices"}, dividends=None)
    pharmacy_retail = TickerData(ticker="XYZ", info={"sector": "Healthcare", "industry": "Pharmaceutical Retailers"}, dividends=None)
    assert insider_scan._is_biotech_or_pharma(med_device) is False
    assert insider_scan._is_biotech_or_pharma(pharmacy_retail) is False
    assert insider_scan._is_biotech_or_pharma(None) is False  # fail open, never silently hide on a fetch failure


def test_maybe_notify_cluster_alerts_hides_biotech_but_keeps_other_tickers(monkeypatch):
    from mytrader.market_data import TickerData

    import sys
    toast_calls, whatsapp_calls = [], []
    monkeypatch.setitem(sys.modules, "notifications", _fake_notifications_module(toast_calls, whatsapp_calls))
    fetched = {
        "MRNA": TickerData(ticker="MRNA", info={"industry": "Biotechnology"}, dividends=None),
        "UPBD": TickerData(ticker="UPBD", info={"industry": "Rental & Leasing Services"}, dividends=None),
    }
    monkeypatch.setattr(insider_scan, "_fetch_cluster_ticker_data", lambda ticker: fetched[ticker])

    insider_scan.maybe_notify_cluster_alerts([
        {"ticker": "MRNA", "company_name": "Moderna, Inc.", "insiders": ["A", "B"], "titles": [],
         "total_value": 50000.0, "rows": []},
        {"ticker": "UPBD", "company_name": "Upbound Group, Inc.", "insiders": ["C", "D"], "titles": [],
         "total_value": 150000.0, "rows": []},
    ])
    assert len(whatsapp_calls) == 1
    (message,), _kwargs = whatsapp_calls[0]
    assert "MRNA" not in message
    assert "Moderna" not in message
    assert "UPBD" in message
    assert "1 new insider buy cluster(s) forming" in message  # count reflects post-filter, not the raw 2


def test_maybe_notify_cluster_alerts_silent_when_every_event_is_biotech(monkeypatch):
    from mytrader.market_data import TickerData

    import sys
    toast_calls, whatsapp_calls = [], []
    monkeypatch.setitem(sys.modules, "notifications", _fake_notifications_module(toast_calls, whatsapp_calls))
    monkeypatch.setattr(
        insider_scan, "_fetch_cluster_ticker_data",
        lambda ticker: TickerData(ticker=ticker, info={"industry": "Biotechnology"}, dividends=None),
    )

    insider_scan.maybe_notify_cluster_alerts([
        {"ticker": "MRNA", "company_name": "Moderna, Inc.", "insiders": ["A", "B"], "titles": [],
         "total_value": 50000.0, "rows": []},
    ])
    assert whatsapp_calls == []
    assert toast_calls == []


def test_threshold_for_days_boundaries():
    cases = [
        (7, 2.5), (8, 5.0), (14, 5.0), (15, 7.5), (21, 7.5),
        (22, 10.0), (28, 10.0), (29, 12.5), (100, 12.5),
    ]
    for days, expected in cases:
        assert insider_scan._threshold_for_days(days) == expected


def test_run_holdings_watch_persists_title(db_conn, monkeypatch):
    _seed_holding(db_conn, ticker="VRTX")
    monkeypatch.setattr(
        "goat.insider_scan.openinsider.fetch_screener_filings",
        lambda tickers_list, trade_type, min_value: [_sale_row()] if trade_type == "S" else [],
    )
    insider_scan.run_holdings_watch(db_conn)
    rows = goat_db.get_recent_insider_filings_seen(db_conn, kind="holdings_watch")
    assert rows[0]["title"] == "CFO"


def test_run_discovery_scan_persists_title(db_conn, monkeypatch):
    monkeypatch.setattr(
        "goat.insider_scan.openinsider.fetch_discovery_purchases",
        lambda: [_purchase_row(ticker="ACME")],
    )
    insider_scan.run_discovery_scan(db_conn)
    rows = goat_db.get_recent_insider_filings_seen(db_conn, kind="discovery")
    assert rows[0]["title"] == "Director"


def _sell_row(ticker="ZETA", trade_date=None, value=200_000.0, pct_owned_change=-15.0):
    return {
        "ticker": ticker,
        "filing_date": (trade_date or date.today()).isoformat(),
        "trade_date": (trade_date or date.today()).isoformat(),
        "insider_name": "Sam Sell",
        "title": "CEO",
        "trade_type_code": "S",
        "value": value,
        "pct_owned_change": pct_owned_change,
    }


def test_run_discovery_sell_tracking_tracks_new_sale(db_conn, monkeypatch):
    monkeypatch.setattr(
        "goat.insider_scan.openinsider.fetch_discovery_sales",
        lambda: [_sell_row()],
    )
    result = insider_scan.run_discovery_sell_tracking(db_conn)
    assert result["tracked"] == 1
    rows = goat_db.get_recent_insider_filings_seen(db_conn, kind="discovery_sell")
    assert len(rows) == 1
    assert rows[0]["ticker"] == "ZETA"
    assert rows[0]["title"] == "CEO"


def test_run_discovery_sell_tracking_creates_no_pending_candidate(db_conn, monkeypatch):
    monkeypatch.setattr(
        "goat.insider_scan.openinsider.fetch_discovery_sales",
        lambda: [_sell_row(ticker="ZETA")],
    )
    insider_scan.run_discovery_sell_tracking(db_conn)
    assert goat_db.get_goat_pending_candidate(db_conn, "ZETA") is None


def test_run_discovery_sell_tracking_skips_held_ticker(db_conn, monkeypatch):
    _seed_holding(db_conn, ticker="ZETA")
    monkeypatch.setattr(
        "goat.insider_scan.openinsider.fetch_discovery_sales",
        lambda: [_sell_row(ticker="ZETA")],
    )
    result = insider_scan.run_discovery_sell_tracking(db_conn)
    assert result["tracked"] == 0
    assert goat_db.get_recent_insider_filings_seen(db_conn, kind="discovery_sell") == []


def test_run_discovery_sell_tracking_respects_lookback_window(db_conn, monkeypatch):
    stale_date = date.today() - timedelta(days=config_lookback_plus_one())
    monkeypatch.setattr(
        "goat.insider_scan.openinsider.fetch_discovery_sales",
        lambda: [_sell_row(trade_date=stale_date)],
    )
    result = insider_scan.run_discovery_sell_tracking(db_conn)
    assert result["tracked"] == 0


def test_run_discovery_sell_tracking_includes_late_filed_old_trade(db_conn, monkeypatch):
    # Same reasoning as the two late-filing tests above -- fetch_discovery_sales's
    # "latest" results are filing-date ordered, so the freshness gate must check
    # filing_date, not trade_date -- but the filing must still have been prompt.
    filing_date = date.today() - timedelta(days=goat_config.GOAT_INSIDER_DISCOVERY_LOOKBACK_DAYS)
    old_trade_date = filing_date - timedelta(days=2)
    row = _sell_row(trade_date=old_trade_date)
    row["filing_date"] = filing_date.isoformat()
    monkeypatch.setattr(
        "goat.insider_scan.openinsider.fetch_discovery_sales",
        lambda: [row],
    )
    result = insider_scan.run_discovery_sell_tracking(db_conn)
    assert result["tracked"] == 1


def test_run_discovery_sell_tracking_excludes_months_late_catch_up_filing(db_conn, monkeypatch):
    # Shaun 2026-11-09: same promptness requirement as the buy-side gates.
    filing_date = date.today()
    months_late_trade_date = filing_date - timedelta(days=120)
    row = _sell_row(trade_date=months_late_trade_date)
    row["filing_date"] = filing_date.isoformat()
    monkeypatch.setattr(
        "goat.insider_scan.openinsider.fetch_discovery_sales",
        lambda: [row],
    )
    result = insider_scan.run_discovery_sell_tracking(db_conn)
    assert result["tracked"] == 0


def test_run_discovery_sell_tracking_handles_fetch_failure_gracefully(db_conn, monkeypatch):
    monkeypatch.setattr(
        "goat.insider_scan.openinsider.fetch_discovery_sales",
        lambda: None,
    )
    result = insider_scan.run_discovery_sell_tracking(db_conn)  # must not raise
    assert result["tracked"] == 0


def test_run_discovery_sell_tracking_is_a_no_op_on_repeat_run(db_conn, monkeypatch):
    monkeypatch.setattr(
        "goat.insider_scan.openinsider.fetch_discovery_sales",
        lambda: [_sell_row()],
    )
    insider_scan.run_discovery_sell_tracking(db_conn)
    result = insider_scan.run_discovery_sell_tracking(db_conn)
    assert result["tracked"] == 0


def test_price_at_horizon_matures_at_exact_horizon(db_conn, monkeypatch):
    trade_date, series = _price_series(days_ago=30, start_price=100.0, end_price=125.0)
    monkeypatch.setattr("goat.insider_scan.price_history.fetch_close_history", lambda t, lb: series)
    result = insider_scan._price_at_horizon("ACME", trade_date, 7)
    assert result is not None
    assert result["pct_change"] == 25.0  # series is flat at end_price from day 1 onward


def test_price_at_horizon_returns_none_when_horizon_not_reached(db_conn):
    trade_date = date.today().isoformat()  # 0 days elapsed
    result = insider_scan._price_at_horizon("ACME", trade_date, 7)
    assert result is None


def test_price_at_horizon_returns_none_on_price_fetch_miss(db_conn, monkeypatch):
    trade_date = (date.today() - timedelta(days=30)).isoformat()
    monkeypatch.setattr("goat.insider_scan.price_history.fetch_close_history", lambda t, lb: None)
    result = insider_scan._price_at_horizon("ACME", trade_date, 7)
    assert result is None


def test_mature_price_outcome_snapshots_matures_reachable_horizons_only(db_conn, monkeypatch):
    trade_date, series = _price_series(days_ago=35, start_price=100.0, end_price=110.0)
    goat_db.insert_goat_insider_filing_seen(
        db_conn, dedup_key="k1", ticker="ACME", filing_date=trade_date, trade_date=trade_date,
        insider_name="Jane Doe", trade_type="P", value=50000.0, kind="discovery",
    )
    monkeypatch.setattr("goat.insider_scan.price_history.fetch_close_history", lambda t, lb: series)
    result = insider_scan.mature_price_outcome_snapshots(db_conn)
    # 35 days old -- horizons 1/3/7/14/30 reachable, 90/180 not yet.
    assert result["matured"] == 5
    captured = goat_db.get_captured_horizons(db_conn, "k1")
    assert captured == {1, 3, 7, 14, 30}


def test_mature_price_outcome_snapshots_skips_already_captured_horizons(db_conn, monkeypatch):
    trade_date, series = _price_series(days_ago=35, start_price=100.0, end_price=110.0)
    goat_db.insert_goat_insider_filing_seen(
        db_conn, dedup_key="k1", ticker="ACME", filing_date=trade_date, trade_date=trade_date,
        insider_name="Jane Doe", trade_type="P", value=50000.0, kind="discovery",
    )
    monkeypatch.setattr("goat.insider_scan.price_history.fetch_close_history", lambda t, lb: series)
    insider_scan.mature_price_outcome_snapshots(db_conn)
    result = insider_scan.mature_price_outcome_snapshots(db_conn)
    assert result["matured"] == 0


def test_mature_price_outcome_snapshots_skips_filings_past_max_tracking_window(db_conn, monkeypatch):
    trade_date, series = _price_series(days_ago=181, start_price=100.0, end_price=110.0)
    goat_db.insert_goat_insider_filing_seen(
        db_conn, dedup_key="k1", ticker="ACME", filing_date=trade_date, trade_date=trade_date,
        insider_name="Jane Doe", trade_type="P", value=50000.0, kind="discovery",
    )
    monkeypatch.setattr("goat.insider_scan.price_history.fetch_close_history", lambda t, lb: series)
    result = insider_scan.mature_price_outcome_snapshots(db_conn)
    assert result["matured"] == 0


def test_mature_price_outcome_snapshots_boundary_at_180_days_still_matures(db_conn, monkeypatch):
    trade_date, series = _price_series(days_ago=180, start_price=100.0, end_price=110.0)
    goat_db.insert_goat_insider_filing_seen(
        db_conn, dedup_key="k1", ticker="ACME", filing_date=trade_date, trade_date=trade_date,
        insider_name="Jane Doe", trade_type="P", value=50000.0, kind="discovery",
    )
    monkeypatch.setattr("goat.insider_scan.price_history.fetch_close_history", lambda t, lb: series)
    result = insider_scan.mature_price_outcome_snapshots(db_conn)
    assert result["matured"] > 0


def test_mature_price_outcome_snapshots_computes_excess_pct_change_against_benchmark(db_conn, monkeypatch):
    trade_date, ticker_series = _price_series(days_ago=10, start_price=100.0, end_price=120.0)
    _, spy_series = _price_series(days_ago=10, start_price=400.0, end_price=408.0)  # SPY +2%

    def _fake_fetch(ticker, lookback_days):
        return spy_series if ticker == "SPY" else ticker_series

    goat_db.insert_goat_insider_filing_seen(
        db_conn, dedup_key="k1", ticker="ACME", filing_date=trade_date, trade_date=trade_date,
        insider_name="Jane Doe", trade_type="P", value=50000.0, kind="discovery",
    )
    monkeypatch.setattr("goat.insider_scan.price_history.fetch_close_history", _fake_fetch)
    insider_scan.mature_price_outcome_snapshots(db_conn)
    row = db_conn.execute(
        "SELECT * FROM goat_insider_price_outcomes WHERE dedup_key = ? AND horizon_days = ?", ("k1", 7)
    ).fetchone()
    assert row["pct_change"] == 20.0
    assert row["benchmark_pct_change"] == 2.0
    assert row["excess_pct_change"] == 18.0


def test_mature_price_outcome_snapshots_caches_benchmark_fetch_within_a_run(db_conn, monkeypatch):
    trade_date, series = _price_series(days_ago=10, start_price=100.0, end_price=110.0)
    goat_db.insert_goat_insider_filing_seen(
        db_conn, dedup_key="k1", ticker="ACME", filing_date=trade_date, trade_date=trade_date,
        insider_name="Jane Doe", trade_type="P", value=50000.0, kind="discovery",
    )
    goat_db.insert_goat_insider_filing_seen(
        db_conn, dedup_key="k2", ticker="ZETA", filing_date=trade_date, trade_date=trade_date,
        insider_name="John Smith", trade_type="P", value=50000.0, kind="discovery",
    )
    calls = []

    def _fake_fetch(ticker, lookback_days):
        calls.append(ticker)
        return series

    monkeypatch.setattr("goat.insider_scan.price_history.fetch_close_history", _fake_fetch)
    insider_scan.mature_price_outcome_snapshots(db_conn)
    spy_calls = [c for c in calls if c == "SPY"]
    # days_ago=10 -> only horizons 1/3/7 are reachable. Same trade_date -> each
    # horizon's SPY fetch is cached across both filings, so SPY is fetched once
    # per reachable horizon (3), not once per filing*horizon (would be 6).
    reachable_horizons = [h for h in goat_config.GOAT_INSIDER_OUTCOME_HORIZONS_DAYS if h <= 10]
    assert len(spy_calls) == len(reachable_horizons)


def test_render_insider_scan_report_includes_price_note_and_recent_filings_section():
    watch_result = {
        "checked_holdings": 1,
        "new_alerts": [],
        "recent_filings": [
            {"ticker": "VRTX", "trade_type": "S", "value": 2_000_000.0,
             "trade_date": "2026-08-01", "price_note": "-22.0% since trade \U0001F6A9 confirms signal"},
        ],
    }
    discovery_result = {
        "pending_candidates": [
            {"ticker": "ACME", "sector_label": "Insider Buy",
             "signal_detail": "John Smith (Director) bought $30,000 of ACME on 2026-08-17",
             "flagged_at": "2026-08-17T00:00:00+00:00", "price_note": "+18.0% since trade \U0001F6A9 confirms signal"},
        ],
    }
    report = insider_scan.render_insider_scan_report(watch_result, discovery_result)
    assert "+18.0% since trade" in report
    assert "-22.0% since trade" in report
    assert "Stocks You Own That Have Had Price Moves Since Insider Buy/Sell Activity" in report
    assert "Sold" in report and "2,000,000" in report
