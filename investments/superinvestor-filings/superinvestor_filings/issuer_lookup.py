"""Issuer CIK -> ticker resolution for the superinvestor-filings scanner. Thin
wrapper over mytrader.db's sec_cik_map reverse lookup, with the Form 4 issuer-ticker
hint taking precedence (an ownershipDocument carries issuerTradingSymbol directly, so
no lookup is needed for Form 3/4/5)."""

from __future__ import annotations

import sqlite3

from mytrader.db import get_ticker_for_cik


def resolve_ticker(
    conn: sqlite3.Connection,
    issuer_cik: str | None,
    issuer_ticker_hint: str | None = None,
) -> str | None:
    hint = (issuer_ticker_hint or "").strip().upper()
    if hint:
        return hint
    if issuer_cik:
        try:
            return get_ticker_for_cik(conn, issuer_cik)
        except (ValueError, sqlite3.Error):
            return None
    return None
