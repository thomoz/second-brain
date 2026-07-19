"""One-time idempotent migration of tool-preplan.md's Confirmed So Far table into the DB.

Do not run against the real shared investments.db without Shaun's explicit go-ahead —
this is the first write ever made to shared production data from this tool.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from . import db, snapshot, tickers

_HOLDINGS: list[dict[str, Any]] = [
    dict(ticker="LLY", name="Eli Lilly & Co", asset_type="stock", bucket="1",
         qty=0.0001, avg_price=1148.00, currency="USD"),
    dict(ticker="LYV", name="Live Nation Entertainment Inc", asset_type="stock", bucket="1",
         qty=0.4, avg_price=167.29, currency="USD"),
    dict(ticker="V", name="Visa Inc (Class A)", asset_type="stock", bucket="1",
         qty=0.1001, avg_price=318.41, currency="USD"),
]

_WATCHLIST: list[dict[str, Any]] = [
    dict(ticker="VRTX", name="Vertex Pharmaceuticals Inc", asset_type="stock", bucket="1",
         notes="Good candidate — CF franchise moat/pricing power, non-cyclical; watch "
               "patent cliff timeline and drug-pricing policy risk"),
    dict(ticker="PMGOLD", name="Perth Mint Gold Structured Product", asset_type="etf", bucket="3a",
         notes="Confirmed — never-sell ballast, hold/sell rule = no formal rule "
               "(periodic check-in)"),
    dict(ticker="PMGOLD", name="Perth Mint Gold Structured Product", asset_type="etf", bucket="3b",
         notes="Confirmed — same vehicle as core sleeve, tracked separately; "
               "conditions-dependent, hold/sell rule = no formal rule (periodic check-in) to start"),
    dict(ticker="BRK.B", name="Berkshire Hathaway Inc (Class B)", asset_type="stock", bucket="1",
         notes="Good candidate — proven capital allocation, diversified moats; watch "
               "succession (Abel) and index-fund overlap"),
    dict(ticker="HDV", name="iShares Core High Dividend ETF", asset_type="etf", bucket="1",
         notes="Candidate — quality/moat + high-dividend screen; broader than staples "
               "(24% staples, 24% healthcare, 20% energy). Check top-10 holdings + "
               "Berkshire overlap before committing"),
    dict(ticker="SCHD", name="Schwab US Dividend Equity ETF", asset_type="etf", bucket="1",
         notes="Candidate — dividend aristocrats-style ETF; not yet deeply discussed "
               "(no mechanics/overlap review done)"),
    dict(ticker="ASML", name="ASML Holding NV", asset_type="stock", bucket="1",
         notes="Strong Bucket 1 fit: sole global EUV lithography supplier (genuine "
               "hardware monopoly), structural chip-demand tailwind, real pricing power. "
               "Watch-outs are political/timing, not quality: export-control risk (China), "
               "semiconductor capex cyclicality, customer concentration"),
]

# Raw/not-yet-discussed candidates carried over from potential-holdings.md's Raw tier
# (2026-07-19 snapshot) — status="raw" preserves the discussed-vs-raw distinction the
# manual file used. Dual-ticker rows (VOO/VTI, VGS/VAS) are split into separate rows
# since the DB schema is one ticker per row. Bucket "unassigned" mirrors the manual
# file's "Needs bucket decision" rows.
_RAW_WATCHLIST: list[dict[str, Any]] = [
    dict(ticker="IXI.AX", name="iShares Global Consumer Staples ETF", asset_type="etf", bucket="1",
         notes="Not yet discussed. Fee 0.41%"),
    dict(ticker="VDC", name="Vanguard Consumer Staples ETF", asset_type="etf", bucket="1",
         notes="Not yet discussed. Fee 0.09%"),
    dict(ticker="XLP", name="Consumer Staples Select Sector SPDR ETF", asset_type="etf", bucket="1",
         notes="Not yet discussed. Fee 0.08%; also flagged for bucket re-homing"),
    dict(ticker="DG", name="Dollar General", asset_type="stock", bucket="1",
         notes="Not yet discussed. Dollar-store category"),
    dict(ticker="DLTR", name="Dollar Tree", asset_type="stock", bucket="1",
         notes="Not yet discussed. Dollar-store category"),
    dict(ticker="FIVE", name="Five Below", asset_type="stock", bucket="1",
         notes="Not yet discussed. Dollar-store category"),
    dict(ticker="OLLI", name="Ollie's Bargain Outlet", asset_type="stock", bucket="1",
         notes="Not yet discussed. Dollar-store category"),
    dict(ticker="DOLLARAMA", name="Dollarama Inc", asset_type="stock", bucket="1",
         notes="Not yet discussed. Dollar-store category — \"taking over reject shop\""),
    dict(ticker="WFC", name="Wells Fargo & Co", asset_type="stock", bucket="1",
         notes="Not yet discussed"),
    dict(ticker="UBER", name="Uber Technologies", asset_type="stock", bucket="1",
         notes="Not yet discussed. Flagged as a \"likely growth stock\""),
    dict(ticker="JOBY", name="Joby Aviation", asset_type="stock", bucket="1",
         notes="Not yet discussed. Speculative"),
    dict(ticker="MCD", name="McDonald's Corp", asset_type="stock", bucket="1",
         notes="Not yet discussed. Flagged \"defensive?\""),
    dict(ticker="KO", name="Coca-Cola Co", asset_type="stock", bucket="1",
         notes="Not yet discussed. Flagged \"defensive?\""),
    dict(ticker="VOO", name="Vanguard S&P 500 ETF", asset_type="etf", bucket="1",
         notes="Not yet discussed. Broad index option — pick one (paired with VTI), "
               "depends on broker/domicile"),
    dict(ticker="VTI", name="Vanguard Total US Market ETF", asset_type="etf", bucket="1",
         notes="Not yet discussed. Broad index option — pick one (paired with VOO), "
               "depends on broker/domicile"),
    dict(ticker="VGS", name="Vanguard MSCI World ETF (ASX, AU-domiciled)", asset_type="etf", bucket="1",
         notes="Not yet discussed. Broad index option — pick one (paired with VAS), "
               "depends on broker/domicile"),
    dict(ticker="VAS", name="Vanguard ASX300 ETF (ASX, AU-domiciled)", asset_type="etf", bucket="1",
         notes="Not yet discussed. Broad index option — pick one (paired with VGS), "
               "depends on broker/domicile"),
    dict(ticker="TSLA", name="Tesla Inc", asset_type="stock", bucket="1",
         notes="Not yet discussed. Previously held, position closed 2026-07-19; "
               "growth/volatile, not a classic moat-pricing-power profile"),
    dict(ticker="MCHI", name="iShares MSCI China ETF", asset_type="etf", bucket="unassigned",
         notes="Not yet discussed. Thematic/geopolitical bet"),
    dict(ticker="GRID", name="First Trust NASDAQ Clean Edge Smart Grid ETF", asset_type="etf", bucket="unassigned",
         notes="Not yet discussed. Sector/thematic"),
    dict(ticker="XLU", name="Utilities Select Sector SPDR ETF", asset_type="etf", bucket="unassigned",
         notes="Not yet discussed. Sector/thematic"),
    dict(ticker="VT", name="Vanguard Total World Stock ETF", asset_type="etf", bucket="unassigned",
         notes="Not yet discussed. Broad world exposure"),
    dict(ticker="GDX", name="VanEck Gold Miners ETF", asset_type="etf", bucket="2",
         notes="Not yet discussed. Gold miners — separate product from gold itself "
               "(PMGOLD), higher volatility"),
    dict(ticker="NEM", name="Newmont Corp", asset_type="stock", bucket="2",
         notes="Not yet discussed. Individual gold miner"),
    dict(ticker="GOLD", name="Barrick Gold Corp", asset_type="stock", bucket="2",
         notes="Not yet discussed. Individual gold miner"),
    dict(ticker="AEM", name="Agnico Eagle Mines", asset_type="stock", bucket="2",
         notes="Not yet discussed. Individual gold miner"),
    dict(ticker="LAND", name="Gladstone Land Corp", asset_type="reit", bucket="2",
         notes="Not yet discussed. Farmland REIT"),
    dict(ticker="FPI", name="Farmland Partners Inc", asset_type="reit", bucket="2",
         notes="Not yet discussed. Farmland REIT — has a 2018 governance flag on record"),
    dict(ticker="TLT", name="iShares 20+ Year Treasury Bond ETF", asset_type="etf", bucket="2",
         notes="Not yet discussed. Situational — only helps in deflationary/rate-cutting "
               "crashes, not inflationary ones (e.g. 2022)"),
    dict(ticker="WM", name="Waste Management Inc", asset_type="stock", bucket="2",
         notes="Not yet discussed. Flagged for possible re-homing to Bucket 1 "
               "(defensive utility-like business)"),
    dict(ticker="PALI", name="Palisades Goldcorp Ltd", asset_type="stock", bucket="2",
         notes="Not yet discussed (previously mislabeled as vetted, corrected 2026-07-19). "
               "Holds equity/warrant stakes in 100+ junior miners — diversified "
               "critical-metals exposure, not a pure gold play. Should be sized very "
               "small if ever confirmed"),
]


def _seed_watchlist(conn: sqlite3.Connection, rows: list[dict[str, Any]], status: str) -> None:
    for w in rows:
        normalized = tickers.normalize(w["ticker"])
        if db.get_watchlist_row(conn, normalized, w["bucket"]) is not None:
            continue
        db.upsert_watchlist_row(
            conn, ticker=normalized, name=w["name"], asset_type=w["asset_type"],
            bucket=w["bucket"], status=status, notes=w["notes"], source="manual",
        )


def seed_confirmed_holdings(conn: sqlite3.Connection) -> None:
    """Idempotent — skips any (ticker, bucket) row that already exists."""
    for h in _HOLDINGS:
        normalized = tickers.normalize(h["ticker"])
        if db.get_holding_row(conn, normalized, h["bucket"]) is not None:
            continue
        db.upsert_holding(
            conn, ticker=normalized, name=h["name"], asset_type=h["asset_type"],
            bucket=h["bucket"], qty=h["qty"], avg_price=h["avg_price"], currency=h["currency"],
        )

    _seed_watchlist(conn, _WATCHLIST, status="discussed")
    _seed_watchlist(conn, _RAW_WATCHLIST, status="raw")

    snapshot.regenerate_all(conn)
