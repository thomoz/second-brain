"""Buy/sell operations on holdings — conversational, no separate CLI form or manual DB edit."""

from __future__ import annotations

import sqlite3

from . import db, snapshot, tickers

_EPSILON = 1e-6


def add_or_update_holding(
    ticker: str,
    bucket: str,
    qty_delta: float,
    price: float,
    action: str,
    conn: sqlite3.Connection,
    *,
    name: str | None = None,
    asset_type: str = "stock",
    currency: str | None = None,
) -> None:
    """action: 'buy' or 'sell'. Buy recomputes the weighted-average price; sell
    subtracts qty and removes the row once it rounds to (near-)zero — fractional-share
    holdings (e.g. LLY's 0.0001) need an epsilon comparison, not exact-zero."""
    normalized = tickers.normalize(ticker)
    existing = db.get_holding_row(conn, normalized, bucket)

    if action == "buy":
        if existing:
            old_qty = existing["qty"]
            old_avg = existing["avg_price"]
            new_qty = old_qty + qty_delta
            new_avg = (old_qty * old_avg + qty_delta * price) / new_qty
            db.upsert_holding(
                conn, ticker=normalized, name=name or existing["name"],
                asset_type=asset_type or existing["asset_type"], bucket=bucket,
                qty=new_qty, avg_price=new_avg,
                currency=currency or existing["currency"],
                last_expense_ratio=existing["last_expense_ratio"],
            )
        else:
            db.upsert_holding(
                conn, ticker=normalized, name=name, asset_type=asset_type,
                bucket=bucket, qty=qty_delta, avg_price=price, currency=currency,
            )
    elif action == "sell":
        if not existing:
            raise ValueError(f"No existing holding for {normalized} in bucket {bucket} to sell")
        new_qty = existing["qty"] - qty_delta
        db.upsert_holding(
            conn, ticker=normalized, name=existing["name"], asset_type=existing["asset_type"],
            bucket=bucket, qty=new_qty, avg_price=existing["avg_price"],
            currency=existing["currency"], last_expense_ratio=existing["last_expense_ratio"],
        )
        db.delete_holding_if_zero(conn, normalized, bucket, epsilon=_EPSILON)
    else:
        raise ValueError(f"Unknown action: {action!r} (expected 'buy' or 'sell')")

    snapshot.regenerate_all(conn)
