"""Regenerate holdings.md / potential-holdings.md from the shared DB.

The database (shared with briefs-finance) is the source of truth for current holdings
and the watchlist; these files are a glanceable markdown snapshot Shaun actually reads —
he never looks at the database directly. Full overwrite on every run is intentional
(per the "data source of truth" decision in tool-preplan.md) — not a diff/merge.
"""

from __future__ import annotations

import sqlite3
from datetime import date

from . import config, db, market_data


def _current_price(ticker: str) -> float | None:
    data = market_data.fetch_ticker_data(ticker)
    if data is None:
        return None
    return data.info.get("regularMarketPrice") or data.info.get("currentPrice")


def regenerate_holdings_md(conn: sqlite3.Connection) -> None:
    rows = db.get_all_holdings(conn)
    lines = [
        "# Current Holdings",
        "",
        "Auto-generated from the shared database by my-trader — edits here are "
        "overwritten on the next run.",
        "",
        "| Ticker | Name | Qty | Mkt Value | Avg Price | Unrealized P&L | Bucket |",
        "|--------|------|-----|-----------|-----------|-----------------|--------|",
    ]
    for row in rows:
        price = _current_price(row["ticker"])
        cost_basis = row["qty"] * row["avg_price"]
        if price is not None:
            mkt_value = row["qty"] * price
            pnl = mkt_value - cost_basis
            mkt_value_str = f"${mkt_value:,.2f}"
            pnl_str = f"{'+' if pnl >= 0 else ''}${pnl:,.2f}"
        else:
            mkt_value_str = "—"
            pnl_str = "—"
        lines.append(
            f"| {row['ticker']} | {row['name'] or ''} | {row['qty']} | {mkt_value_str} "
            f"| ${row['avg_price']:,.2f} | {pnl_str} | {row['bucket']} |"
        )
    lines.append("")
    lines.append(f"Last auto-generated: {date.today().isoformat()}.")
    config.HOLDINGS_MD_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _format_status(row: sqlite3.Row) -> str:
    if row["notes"]:
        return row["notes"]
    return "Not yet discussed" if row["status"] == "raw" else "Discussed"


def regenerate_watchlist_md(conn: sqlite3.Connection) -> None:
    rows = db.get_all_watchlist(conn)
    lines = [
        "# Potential Holdings (Watchlist)",
        "",
        "Not currently owned — see `holdings.md` for what's actually held. "
        "Auto-generated from the shared database by my-trader — edits here are "
        "overwritten on the next run. Dividend/10Y Return columns are not yet "
        "captured by the DB schema in Phase A — see Status for what's actually known.",
        "",
        "| Ticker | Name | Type | Bucket | Dividend | 10Y Return | Status |",
        "|--------|------|------|--------|----------|------------|--------|",
    ]
    for row in rows:
        lines.append(
            f"| {row['ticker']} | {row['name'] or ''} | {row['asset_type']} | {row['bucket']} "
            f"| — | — | {_format_status(row)} |"
        )
    lines.append("")
    lines.append(f"Last auto-generated: {date.today().isoformat()}.")
    config.WATCHLIST_MD_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def regenerate_all(conn: sqlite3.Connection) -> None:
    regenerate_holdings_md(conn)
    regenerate_watchlist_md(conn)
