"""IBKR Holdings Sync -- read-only, on-demand connection to a locally running IB
Gateway instance (see ibkr-sync-handoff.md and .agent/plans/ibkr-holdings-sync.md).
Local-only, never wired into monitor.py or any systemd unit -- it depends on Shaun
having IB Gateway open and logged in on his own machine, which is never true on the
VPS and isn't reliably true locally at any automated cadence either.

Real I/O (the `ib_async` socket connection) is isolated behind `_connect()` and the
two `fetch_*()` functions, same shape as gold_cot.py's single-real-I/O-boundary
pattern -- `compute_diff()` is a pure function tested directly with plain data.

Known gaps, not solvable without live-account confirmation (see ibkr-sync-handoff.md
Open Questions):
- Dual-class tickers (e.g. BRK.B) may come back from IBKR as "BRK B" (space) rather
  than "BRK.B" -- tickers.normalize() doesn't handle a space variant. Shaun holds no
  dual-class shares today, so this is untested against real data.
- IBKR's avgCost for stocks may already include per-share commission depending on
  account settings -- a known IBKR quirk, not a bug here.
"""

from __future__ import annotations

from typing import Any, Callable, TypeVar

from . import config, tickers

_EPSILON_QTY = 1e-6
_EPSILON_PRICE = 1e-4  # looser than qty: IBKR's commission-inclusive avgCost may
                        # legitimately differ slightly from a manually-tracked
                        # avg_price without that being a real mismatch worth flagging.

T = TypeVar("T")


def _connect():
    from ib_async import IB

    ib = IB()
    ib.connect(config.IBKR_HOST, config.IBKR_PORT, clientId=config.IBKR_CLIENT_ID)
    return ib


def _with_connection(fn: Callable[[Any], T]) -> T:
    """Connect, run fn(ib), always disconnect -- shared by both fetch functions
    rather than duplicating connect/disconnect boilerplate."""
    ib = _connect()
    try:
        return fn(ib)
    finally:
        ib.disconnect()


def map_ibkr_ticker(symbol: str, exchange: str, currency: str) -> str:
    """Map an IBKR Contract's symbol/exchange/currency to the ticker string
    my-trader expects elsewhere (holdings table, tickers.py). Best-guess logic,
    confirm against Shaun's real account before trusting it for a new asset class
    (see module docstring)."""
    if currency == "AUD" or exchange == "ASX":
        return tickers.asx_variant(symbol)
    return tickers.normalize(symbol)


def fetch_positions() -> list[dict[str, Any]]:
    """Real positions from IB Gateway, mapped to the shape holdings rows use.
    `name` is unavailable from ib.positions() alone -- left None, same as
    holdings_ops.add_or_update_holding already tolerates."""

    def _fetch(ib) -> list[dict[str, Any]]:
        results = []
        for pos in ib.positions():
            contract = pos.contract
            results.append({
                "ticker": map_ibkr_ticker(contract.symbol, contract.exchange, contract.currency),
                "name": None,
                "qty": pos.position,
                "avg_price": pos.avgCost,
                "currency": contract.currency,
                "asset_type": "stock",
                "exchange_raw": contract.exchange,
            })
        return results

    return _with_connection(_fetch)


def fetch_account_summary() -> dict[str, str] | None:
    """NetLiquidation + TotalCashValue -- print-only context, never persisted
    (holdings.md has no column for it, and this wasn't asked to be tracked over
    time). Returns None on failure."""

    def _fetch(ib) -> dict[str, str] | None:
        rows = ib.accountSummary()
        wanted = {"NetLiquidation", "TotalCashValue"}
        found = {row.tag: row for row in rows if row.tag in wanted}
        if "NetLiquidation" not in found:
            return None
        return {
            "net_liquidation": found["NetLiquidation"].value,
            "total_cash": found.get("TotalCashValue").value if "TotalCashValue" in found else None,
            "currency": found["NetLiquidation"].currency,
        }

    try:
        return _with_connection(_fetch)
    except Exception:
        return None


def compute_diff(
    ibkr_positions: list[dict[str, Any]], holdings: list[Any]
) -> dict[str, list[dict[str, Any]]]:
    """Pure, no I/O -- classify IBKR's real positions against my-trader's tracked
    `holdings` table by ticker into four buckets:
    - matched_with_mismatch: ticker in both, qty or avg_price differs beyond tolerance
    - matched_no_change: ticker in both, values agree
    - new_to_ibkr: ticker in IBKR positions, not tracked in holdings at all
    - missing_from_ibkr: ticker tracked in holdings, not reported by IBKR

    `holdings` rows are sqlite3.Row objects (or any mapping supporting ["ticker"] /
    ["qty"] / ["avg_price"]) from db.get_all_holdings(). A ticker held across
    multiple buckets in `holdings` is compared against its first match only --
    IBKR itself has no concept of my-trader's bucket split."""
    holdings_by_ticker = {}
    for row in holdings:
        holdings_by_ticker.setdefault(row["ticker"], row)

    ibkr_by_ticker = {p["ticker"]: p for p in ibkr_positions}

    matched_with_mismatch = []
    matched_no_change = []
    new_to_ibkr = []
    missing_from_ibkr = []

    for ticker, ibkr_row in ibkr_by_ticker.items():
        holding_row = holdings_by_ticker.get(ticker)
        if holding_row is None:
            new_to_ibkr.append(ibkr_row)
            continue
        qty_diff = abs(ibkr_row["qty"] - holding_row["qty"]) > _EPSILON_QTY
        price_diff = abs(ibkr_row["avg_price"] - holding_row["avg_price"]) > _EPSILON_PRICE
        entry = {
            "ticker": ticker,
            "ibkr_qty": ibkr_row["qty"],
            "ibkr_avg_price": ibkr_row["avg_price"],
            "holdings_qty": holding_row["qty"],
            "holdings_avg_price": holding_row["avg_price"],
            "bucket": holding_row["bucket"],
        }
        if qty_diff or price_diff:
            matched_with_mismatch.append(entry)
        else:
            matched_no_change.append(entry)

    for ticker, holding_row in holdings_by_ticker.items():
        if ticker not in ibkr_by_ticker:
            missing_from_ibkr.append({
                "ticker": ticker, "qty": holding_row["qty"],
                "avg_price": holding_row["avg_price"], "bucket": holding_row["bucket"],
            })

    return {
        "matched_with_mismatch": matched_with_mismatch,
        "matched_no_change": matched_no_change,
        "new_to_ibkr": new_to_ibkr,
        "missing_from_ibkr": missing_from_ibkr,
    }
