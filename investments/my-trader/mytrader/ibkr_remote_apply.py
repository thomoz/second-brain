"""VPS-side counterpart to ibkr_remote_write.py -- only ever runs on the VPS, invoked
over SSH as `python -m mytrader.ibkr_remote_apply`. Reads a JSON payload (IBKR
positions + account summary, already fetched locally against IB Gateway, plus the
--apply flag) from stdin, then does everything cmd_sync_ibkr (main.py) used to do
after its own fetch step: diff against the VPS's own investments.db, print the
report, and -- only if apply is true -- write corrections/staged positions and
regenerate snapshots. This keeps the diff (and what it's compared against) on the
same machine as the database it reads, per
.agent/plans/investments-db-ssh-single-source.md Task 3.1.
"""

from __future__ import annotations

import json
import sys


def main() -> None:
    from .db import get_all_holdings, get_holding_row, insert_ibkr_pending_position, upsert_holding
    from .ibkr_sync import compute_diff
    from .main import _open_conn
    from .snapshot import regenerate_all

    payload = json.load(sys.stdin)
    positions = payload["positions"]
    summary = payload.get("summary")
    apply = payload.get("apply", False)

    if summary is not None:
        cash_part = (
            f", TotalCashValue {summary['total_cash']} {summary['currency']}"
            if summary.get("total_cash") is not None else ""
        )
        print(f"Account summary: NetLiquidation {summary['net_liquidation']} {summary['currency']}{cash_part}")
    else:
        print("Account summary: unavailable.")

    print(f"\nFound {len(positions)} IBKR position(s).")

    conn = _open_conn()
    holdings = get_all_holdings(conn)
    diff = compute_diff(positions, holdings)

    print(f"\nMatched, no change ({len(diff['matched_no_change'])}):")
    for row in diff["matched_no_change"]:
        print(f"  {row['ticker']}: qty {row['holdings_qty']}, avg_price {row['holdings_avg_price']}")

    print(f"\nMatched, mismatch ({len(diff['matched_with_mismatch'])}):")
    for row in diff["matched_with_mismatch"]:
        print(
            f"  {row['ticker']} (bucket {row['bucket']}): tracked qty={row['holdings_qty']} "
            f"avg_price={row['holdings_avg_price']} -> IBKR qty={row['ibkr_qty']} "
            f"avg_price={row['ibkr_avg_price']}"
        )

    print(f"\nNew to IBKR, not tracked ({len(diff['new_to_ibkr'])}):")
    for row in diff["new_to_ibkr"]:
        print(f"  {row['ticker']}: qty {row['qty']}, avg_price {row['avg_price']}")

    print(f"\nTracked but missing from IBKR ({len(diff['missing_from_ibkr'])}):")
    for row in diff["missing_from_ibkr"]:
        print(
            f"  {row['ticker']} (bucket {row['bucket']}): qty {row['qty']} — sold outside "
            "this tool, or run holding-sell if confirmed"
        )

    if not apply:
        conn.close()
        print("\nDry run only — no writes made. Re-run with --apply to commit corrections and stage new positions.")
        return

    corrected = 0
    for row in diff["matched_with_mismatch"]:
        existing = get_holding_row(conn, row["ticker"], row["bucket"])
        upsert_holding(
            conn, ticker=row["ticker"], name=existing["name"], asset_type=existing["asset_type"],
            bucket=row["bucket"], qty=row["ibkr_qty"], avg_price=row["ibkr_avg_price"],
            currency=existing["currency"], last_expense_ratio=existing["last_expense_ratio"],
        )
        corrected += 1

    staged = 0
    for row in diff["new_to_ibkr"]:
        insert_ibkr_pending_position(
            conn, ticker=row["ticker"], name=row["name"], qty=row["qty"], avg_price=row["avg_price"],
            currency=row["currency"], asset_type=row["asset_type"], exchange_raw=row["exchange_raw"],
        )
        staged += 1

    if corrected:
        regenerate_all(conn)
    conn.close()
    print(
        f"\nApplied: {corrected} correction(s), {staged} new position(s) staged, "
        f"{len(diff['missing_from_ibkr'])} missing (reported only)."
    )


if __name__ == "__main__":
    main()
