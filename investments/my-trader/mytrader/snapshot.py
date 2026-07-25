"""Regenerate holdings.md / watchlist.md from the shared DB.

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


def _format_dividend(value: float | None) -> str:
    return "—" if value is None else f"{value:.2f}%"


def _format_ten_year_return(value: float | None) -> str:
    return "—" if value is None else f"{value:+.0f}%"


def _watchlist_table(rows: list[sqlite3.Row]) -> list[str]:
    lines = [
        "| Ticker | Name | Type | Bucket | Dividend | 10Y Return | Status |",
        "|--------|------|------|--------|----------|------------|--------|",
    ]
    for row in rows:
        dividend = _format_dividend(row["dividend_yield_pct"])
        ten_year = _format_ten_year_return(row["ten_year_return_pct"])
        lines.append(
            f"| {row['ticker']} | {row['name'] or ''} | {row['asset_type']} | {row['bucket']} "
            f"| {dividend} | {ten_year} | {_format_status(row)} |"
        )
    return lines


def regenerate_watchlist_md(conn: sqlite3.Connection) -> None:
    rows = db.get_all_watchlist(conn)
    postcrash = [r for r in rows if r["bucket"] == config.AI_POSTCRASH_BUCKET]
    crash_discount = [r for r in rows if r["bucket"] == config.CRASH_DISCOUNT_BUCKET]
    main_rows = [
        r for r in rows
        if r["bucket"] not in (config.AI_POSTCRASH_BUCKET, config.CRASH_DISCOUNT_BUCKET)
    ]

    lines = [
        "# Potential Holdings (Watchlist)",
        "",
        "Not currently owned — see `holdings.md` for what's actually held. "
        "Auto-generated from the shared database by my-trader — edits here are "
        "overwritten on the next run. Dividend/10Y Return columns are fetched via "
        "yfinance and cached on refresh-watchlist-data (not live-updated every run) "
        "— 10Y Return is an adjusted-close approximation of total return, not a "
        "precise dividend-reinvestment calculation.",
        "",
        "## Watchlist",
        "",
    ]
    lines += _watchlist_table(main_rows)
    lines += [
        "",
        "## Bucket 4 — Crash Discount Buys",
        "",
        "Great, durable companies highly likely to still be around long-term — "
        "waiting for a crash-driven discount to enter rather than buying at today's "
        "price. Not timed around a specific bubble like Post-Crash AI Watch below, "
        "and not a sell-after-recovery trade like Bucket 2. Once actually bought, "
        "migrate to Bucket 1.",
        "",
    ]
    lines += _watchlist_table(crash_discount)
    lines += [
        "",
        "## Post-Crash AI Watch",
        "",
        "Major AI-boom names with real moats (chip/foundry monopoly, hyperscaler "
        "platform dominance) — deliberately not buying at current AI-bubble "
        "valuations. Revisit if/when the sector corrects.",
        "",
    ]
    lines += _watchlist_table(postcrash)
    lines.append("")
    lines.append(f"Last auto-generated: {date.today().isoformat()}.")
    config.WATCHLIST_MD_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def regenerate_pending_candidates_md(conn: sqlite3.Connection) -> None:
    rows = db.get_all_pending_candidates(conn)
    lines = [
        "# Synced Candidates — Pending Review",
        "",
        "Auto-generated from Briefs Finance's `recommendations` table by "
        "`sync-candidates` (runs automatically once a day as part of Monitor, also "
        "runnable on demand). Nothing here is part of the real watchlist yet. Review "
        "each one and either `promote-candidate` (moves it into `watchlist.md`) or "
        "`dismiss-candidate` (discards it). Edits here are overwritten on the next "
        "`sync-candidates`/`snapshot`/`monitor` run.",
        "",
        "| Ticker | Company | Thesis | Synced |",
        "|--------|---------|--------|--------|",
    ]
    for row in rows:
        lines.append(
            f"| {row['ticker']} | {row['company_name'] or ''} | {row['buy_thesis'] or ''} "
            f"| {row['synced_at'][:10]} |"
        )
    lines.append("")
    lines.append(f"Last auto-generated: {date.today().isoformat()}.")
    config.PENDING_CANDIDATES_MD_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def regenerate_all(conn: sqlite3.Connection) -> None:
    regenerate_holdings_md(conn)
    regenerate_watchlist_md(conn)
    regenerate_pending_candidates_md(conn)
