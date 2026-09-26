"""Annotates newly-discovered superinvestor filings with the shared chart setup
score/trend note from mytrader.chart_setup_score -- the same 0-100 read
goat.insider_scan attaches to its own discovery candidates, added here
2026-09-26 at Shaun's request ("connect this score part of the tool to the
super-investor-filings-report"). Scoped to `new_filings` only (the handful
surfaced each run), not the full `recent_filings` rolling log (up to 200 rows)
-- a fresh network call per row on every run against a 200-row historical
audit trail isn't worth the cost, and "is this a good moment to look at this"
is most relevant right when a filing is newly surfaced anyway, matching how
Shaun originally framed the ask ("when you discover each insider buy")."""

from __future__ import annotations

from typing import Any

from mytrader import chart_setup_score as css


def annotate_chart_notes(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sets 'chart_note' on each row -- "" when there's no US-resolvable
    ticker (every India/SAST row, and any EDGAR row issuer_lookup couldn't
    resolve) or no usable date, same graceful-degradation pattern as the SEC/
    ASX filing reads elsewhere in this codebase (non-covered tickers fall
    straight back to a no-op, not an error). Prefers `event_date` (the real
    transaction/acquisition date, present on Form 4s) over `filed_date` (the
    filing date, the best available anchor for 13D/G snapshots which have no
    per-transaction date)."""
    for row in rows:
        ticker = row.get("issuer_ticker")
        trade_date = row.get("event_date") or row.get("filed_date")
        if not ticker or not trade_date:
            row["chart_note"] = ""
            continue
        row["chart_note"] = css.build_chart_note(ticker, trade_date)
    return rows
