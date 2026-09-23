from __future__ import annotations

import io
import json

from scripts.db import get_connection

from mytrader import db, ibkr_remote_apply
from mytrader import main as mt_main


def _stdin_payload(monkeypatch, positions, apply=True, summary=None):
    payload = json.dumps({"positions": positions, "summary": summary, "apply": apply})
    monkeypatch.setattr("sys.stdin", io.StringIO(payload))


def _no_git_push(monkeypatch):
    monkeypatch.setattr(
        "mytrader.ibkr_remote_apply.subprocess.run",
        lambda *args, **kwargs: type("R", (), {"returncode": 0})(),
    )


def test_missing_from_ibkr_holding_is_removed_on_apply(db_conn, db_path, monkeypatch, capsys):
    db.upsert_holding(
        db_conn, ticker="URNM.AX", name=None, asset_type="stock", bucket="1",
        qty=300.0, avg_price=10.32, currency="AUD",
    )
    monkeypatch.setattr(mt_main, "_open_conn", lambda: db_conn)
    _no_git_push(monkeypatch)
    _stdin_payload(monkeypatch, positions=[], apply=True)

    ibkr_remote_apply.main()  # main() closes db_conn itself -- reopen for assertions

    reopened = get_connection(db_path)
    assert db.get_holding_row(reopened, "URNM.AX", "1") is None
    reopened.close()
    out = capsys.readouterr().out
    assert "1 position(s) removed" in out


def test_missing_from_ibkr_holding_is_not_removed_on_dry_run(db_conn, db_path, monkeypatch, capsys):
    db.upsert_holding(
        db_conn, ticker="NVDA", name=None, asset_type="stock", bucket="unassigned",
        qty=5.0, avg_price=217.37, currency="USD",
    )
    monkeypatch.setattr(mt_main, "_open_conn", lambda: db_conn)
    _stdin_payload(monkeypatch, positions=[], apply=False)

    ibkr_remote_apply.main()

    reopened = get_connection(db_path)
    assert db.get_holding_row(reopened, "NVDA", "unassigned") is not None
    reopened.close()
    out = capsys.readouterr().out
    assert "would be removed with --apply" in out


def test_matched_holdings_are_untouched_on_apply(db_conn, db_path, monkeypatch, capsys):
    db.upsert_holding(
        db_conn, ticker="AAPL", name="Apple Inc.", asset_type="stock", bucket="1",
        qty=10.0, avg_price=150.0, currency="USD",
    )
    monkeypatch.setattr(mt_main, "_open_conn", lambda: db_conn)
    _no_git_push(monkeypatch)
    _stdin_payload(
        monkeypatch,
        positions=[{
            "ticker": "AAPL", "name": None, "qty": 10.0, "avg_price": 150.0,
            "currency": "USD", "asset_type": "stock", "exchange_raw": "NASDAQ",
        }],
        apply=True,
    )

    ibkr_remote_apply.main()

    reopened = get_connection(db_path)
    row = db.get_holding_row(reopened, "AAPL", "1")
    assert row is not None
    assert row["qty"] == 10.0
    reopened.close()
    out = capsys.readouterr().out
    assert "0 position(s) removed" in out
