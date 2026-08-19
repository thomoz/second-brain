from __future__ import annotations

from fourteen_crash_signals_daily_check import db


def test_replace_and_get_hot_watchlist(db_conn):
    db.replace_hot_watchlist(db_conn, [
        {"ticker": "NVDA", "sector_label": "Technology", "market_cap": 5e12, "rank": 1},
        {"ticker": "MSFT", "sector_label": "Technology", "market_cap": 3e12, "rank": 2},
    ])
    rows = db.get_hot_watchlist(db_conn)
    assert [r["ticker"] for r in rows] == ["NVDA", "MSFT"]


def test_replace_hot_watchlist_clears_prior_rows(db_conn):
    db.replace_hot_watchlist(db_conn, [{"ticker": "NVDA", "sector_label": "Technology", "market_cap": 5e12, "rank": 1}])
    db.replace_hot_watchlist(db_conn, [{"ticker": "ORCL", "sector_label": "Technology", "market_cap": 1e12, "rank": 1}])
    rows = db.get_hot_watchlist(db_conn)
    assert [r["ticker"] for r in rows] == ["ORCL"]


def test_upsert_signal_state_true_only_on_absent_to_firing_transition(db_conn):
    assert db.upsert_signal_state(db_conn, marker_key="m1", is_firing=True, detail="first fire") is True


def test_upsert_signal_state_false_on_repeat_firing(db_conn):
    db.upsert_signal_state(db_conn, marker_key="m1", is_firing=True, detail="first fire")
    assert db.upsert_signal_state(db_conn, marker_key="m1", is_firing=True, detail="still firing") is False


def test_upsert_signal_state_false_when_staying_not_firing(db_conn):
    assert db.upsert_signal_state(db_conn, marker_key="m1", is_firing=False, detail="ok") is False
    assert db.upsert_signal_state(db_conn, marker_key="m1", is_firing=False, detail="still ok") is False


def test_upsert_signal_state_refires_after_returning_to_not_firing(db_conn):
    db.upsert_signal_state(db_conn, marker_key="m1", is_firing=True, detail="fire")
    db.upsert_signal_state(db_conn, marker_key="m1", is_firing=False, detail="resolved")
    assert db.upsert_signal_state(db_conn, marker_key="m1", is_firing=True, detail="fire again") is True


def test_get_all_signal_states_orders_by_marker_key(db_conn):
    db.upsert_signal_state(db_conn, marker_key="zzz", is_firing=True, detail="z")
    db.upsert_signal_state(db_conn, marker_key="aaa", is_firing=True, detail="a")
    rows = db.get_all_signal_states(db_conn)
    assert [r["marker_key"] for r in rows] == ["aaa", "zzz"]


def test_upsert_lease_commitment_history_inserts(db_conn):
    db.upsert_lease_commitment_history(
        db_conn, ticker="ORCL", accession_number="ACC-1", figure=1.5e9, filing_date="2026-06-30",
    )
    row = db.get_lease_commitment_history(db_conn, "ORCL")
    assert row["accession_number"] == "ACC-1"
    assert row["figure"] == 1.5e9
    assert row["filing_date"] == "2026-06-30"


def test_upsert_lease_commitment_history_overwrites_on_conflict(db_conn):
    db.upsert_lease_commitment_history(
        db_conn, ticker="ORCL", accession_number="ACC-1", figure=1.5e9, filing_date="2026-06-30",
    )
    db.upsert_lease_commitment_history(
        db_conn, ticker="ORCL", accession_number="ACC-2", figure=2.0e9, filing_date="2026-09-30",
    )
    row = db.get_lease_commitment_history(db_conn, "ORCL")
    assert row["accession_number"] == "ACC-2"
    assert row["figure"] == 2.0e9
    assert row["filing_date"] == "2026-09-30"


def test_get_lease_commitment_history_none_when_absent(db_conn):
    assert db.get_lease_commitment_history(db_conn, "ORCL") is None


def test_upsert_bond_cusip_inserts(db_conn):
    db.upsert_bond_cusip(db_conn, ticker="ORCL", cusip="68389XBM1", accession_number="ACC-1")
    row = db.get_bond_cusip(db_conn, "ORCL")
    assert row["cusip"] == "68389XBM1"
    assert row["accession_number"] == "ACC-1"


def test_upsert_bond_cusip_overwrites_on_conflict(db_conn):
    db.upsert_bond_cusip(db_conn, ticker="ORCL", cusip="68389XBM1", accession_number="ACC-1")
    db.upsert_bond_cusip(db_conn, ticker="ORCL", cusip="68389XBN9", accession_number="ACC-2")
    row = db.get_bond_cusip(db_conn, "ORCL")
    assert row["cusip"] == "68389XBN9"
    assert row["accession_number"] == "ACC-2"


def test_get_bond_cusip_none_when_absent(db_conn):
    assert db.get_bond_cusip(db_conn, "ORCL") is None


def test_record_issuer_spread_inserts(db_conn):
    from datetime import date

    db.record_issuer_spread(db_conn, ticker="ORCL", spread_value=1.25)
    row = db.get_issuer_spread_near(db_conn, "ORCL", date.today(), tolerance_days=0)
    assert row["spread_value"] == 1.25


def test_record_issuer_spread_overwrites_same_day(db_conn):
    db.record_issuer_spread(db_conn, ticker="ORCL", spread_value=1.25)
    db.record_issuer_spread(db_conn, ticker="ORCL", spread_value=1.50)
    from datetime import date

    row = db.get_issuer_spread_near(db_conn, "ORCL", date.today(), tolerance_days=0)
    assert row["spread_value"] == 1.50


def test_get_issuer_spread_near_exact_match(db_conn):
    from datetime import date

    target = date(2026, 5, 1)
    db_conn.execute(
        "INSERT INTO signals_issuer_spread_history (ticker, spread_value, observed_at) VALUES (?, ?, ?)",
        ("ORCL", 1.1, "2026-05-01"),
    )
    db_conn.commit()
    row = db.get_issuer_spread_near(db_conn, "ORCL", target, tolerance_days=10)
    assert row["spread_value"] == 1.1


def test_get_issuer_spread_near_closest_within_tolerance(db_conn):
    from datetime import date

    for d, v in (("2026-04-25", 1.0), ("2026-05-05", 2.0)):
        db_conn.execute(
            "INSERT INTO signals_issuer_spread_history (ticker, spread_value, observed_at) VALUES (?, ?, ?)",
            ("ORCL", v, d),
        )
    db_conn.commit()
    row = db.get_issuer_spread_near(db_conn, "ORCL", date(2026, 5, 1), tolerance_days=10)
    assert row["spread_value"] == 2.0  # 2026-05-05 is 4 days away, closer than 2026-04-25's 6 days


def test_get_issuer_spread_near_none_outside_tolerance(db_conn):
    from datetime import date

    db_conn.execute(
        "INSERT INTO signals_issuer_spread_history (ticker, spread_value, observed_at) VALUES (?, ?, ?)",
        ("ORCL", 1.0, "2026-01-01"),
    )
    db_conn.commit()
    row = db.get_issuer_spread_near(db_conn, "ORCL", date(2026, 5, 1), tolerance_days=10)
    assert row is None


def test_get_issuer_spread_near_none_when_empty(db_conn):
    from datetime import date

    assert db.get_issuer_spread_near(db_conn, "ORCL", date(2026, 5, 1), tolerance_days=10) is None


def test_set_manual_bond_yield_inserts(db_conn):
    db.set_manual_bond_yield(db_conn, ticker="ORCL", cusip="68389XBM1", yield_pct=5.75)
    row = db.get_manual_bond_yield(db_conn, "ORCL")
    assert row["yield_pct"] == 5.75
    assert row["cusip"] == "68389XBM1"


def test_set_manual_bond_yield_overwrites_on_conflict(db_conn):
    db.set_manual_bond_yield(db_conn, ticker="ORCL", cusip="68389XBM1", yield_pct=5.75)
    db.set_manual_bond_yield(db_conn, ticker="ORCL", cusip=None, yield_pct=6.00)
    row = db.get_manual_bond_yield(db_conn, "ORCL")
    assert row["yield_pct"] == 6.00
    assert row["cusip"] is None


def test_get_manual_bond_yield_none_when_absent(db_conn):
    assert db.get_manual_bond_yield(db_conn, "ORCL") is None


def test_record_and_get_putcall_ratio(db_conn):
    db.record_putcall_ratio(db_conn, ratio=0.65)
    rows = db.get_putcall_history(db_conn, since_days=30)
    assert len(rows) == 1
    assert rows[0]["ratio"] == 0.65


def test_record_putcall_ratio_upserts_same_day(db_conn):
    db.record_putcall_ratio(db_conn, ratio=0.65)
    db.record_putcall_ratio(db_conn, ratio=0.70)
    rows = db.get_putcall_history(db_conn, since_days=30)
    assert len(rows) == 1
    assert rows[0]["ratio"] == 0.70


def test_get_putcall_history_excludes_rows_older_than_since_days(db_conn):
    db_conn.execute(
        "INSERT INTO signals_putcall_history (observed_at, ratio) VALUES (?, ?)",
        ("2020-01-01", 0.5),
    )
    db_conn.commit()
    db.record_putcall_ratio(db_conn, ratio=0.65)
    rows = db.get_putcall_history(db_conn, since_days=30)
    assert len(rows) == 1
    assert rows[0]["ratio"] == 0.65


def test_has_seen_regulator_alert_false_before_true_after(db_conn):
    assert db.has_seen_regulator_alert(db_conn, "guid-1") is False
    db.mark_regulator_alert_seen(db_conn, guid="guid-1", source="sec", title="Statement")
    assert db.has_seen_regulator_alert(db_conn, "guid-1") is True


def test_mark_regulator_alert_seen_twice_does_not_raise(db_conn):
    db.mark_regulator_alert_seen(db_conn, guid="guid-1", source="sec", title="Statement")
    db.mark_regulator_alert_seen(db_conn, guid="guid-1", source="sec", title="Statement")
    assert db.has_seen_regulator_alert(db_conn, "guid-1") is True


def test_record_issuer_spread_keys_by_local_date_not_utc(db_conn, monkeypatch):
    """Regression for the 2026-08-19 bug: record_issuer_spread previously keyed its
    daily row to datetime.now(timezone.utc)[:10], which lags local date.today() for
    part of the day in Sydney (UTC+10/+11) -- a write made in that window was invisible
    to a same-day, 0-tolerance lookup keyed on the local date. Force UTC and local dates
    to disagree and confirm the row still lands on today's local date."""
    from datetime import date, datetime, timedelta, timezone

    class _FakeDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            real_now = datetime.now(tz)
            if tz is timezone.utc:
                return real_now - timedelta(days=1)  # simulate UTC lagging local by a day
            return real_now

    monkeypatch.setattr(db, "datetime", _FakeDateTime)
    db.record_issuer_spread(db_conn, ticker="ORCL", spread_value=1.25)
    row = db.get_issuer_spread_near(db_conn, "ORCL", date.today(), tolerance_days=0)
    assert row is not None
    assert row["spread_value"] == 1.25
    assert row["observed_at"] == date.today().isoformat()
