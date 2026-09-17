"""VPS-side counterpart to ibkr_remote_write.py -- only ever runs on the VPS, invoked
over SSH as `python -m mytrader.ibkr_remote_apply`. Reads a JSON payload (IBKR
positions + account summary, already fetched locally against IB Gateway, plus the
--apply flag) from stdin, then does everything cmd_sync_ibkr (main.py) used to do
after its own fetch step: diff against the VPS's own investments.db, print the
report, and -- only if apply is true -- write corrections/new positions and
regenerate snapshots. This keeps the diff (and what it's compared against) on the
same machine as the database it reads, per
.agent/plans/investments-db-ssh-single-source.md Task 3.1.

A ticker IBKR reports that isn't already tracked is added straight to `holdings`
with bucket "unassigned" (same neutral placeholder already used for GOLD.AX/SOFI/
UBER) -- Shaun's 2026-09-17 call: holdings.md must reflect his real account without
a manual bucket-assignment step gating it. Re-bucketing later is a plain
`holding-buy`/DB edit, same as any other holding. This replaced an earlier design
(staged into a separate ibkr_pending_positions table, requiring `ibkr-assign-bucket`
before it showed up anywhere) -- removed entirely, not just bypassed.

Also commits + pushes holdings.md/watchlist.md immediately when regenerate_all()
touches them, instead of waiting on second-brain-vaultsync.timer's own 2-minute
cycle -- ibkr_remote_write.push_positions_remote's local caller does a `git pull`
right after this process exits, so that pull needs the VPS's commit to already be on
origin by then, not up to 2 minutes later. Scoped to just these two files (same
scoping discipline as run_vault_sync.sh's own SYNC_PATHS) so this never sweeps up
unrelated changes into an ibkr-sync commit. Non-fatal on any git failure (mirrors
run_vault_sync.sh's "push failed (non-fatal)" posture) -- the regular vault-sync
timer will pick up the commit on its own next cycle either way.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone

_SYNC_PATHS = ["holdings.md", "watchlist.md"]


def _commit_and_push_holdings_files() -> None:
    subprocess.run(["git", "add", *_SYNC_PATHS], check=False)
    staged = subprocess.run(["git", "diff", "--quiet", "--cached", "--", *_SYNC_PATHS], check=False)
    if staged.returncode == 0:
        return  # nothing changed in these two files -- nothing to commit
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
    subprocess.run(["git", "commit", "-m", f"ibkr sync {ts}", "--", *_SYNC_PATHS], check=False)
    subprocess.run(["git", "pull", "--no-rebase"], check=False)
    push = subprocess.run(["git", "push", "origin", "HEAD"], check=False)
    if push.returncode != 0:
        print("Note: push to origin failed after IBKR sync -- vault sync will retry within 2 minutes.")


_NEW_POSITION_BUCKET = "unassigned"  # matches the placeholder already used for
    # GOLD.AX/SOFI/UBER -- a real bucket (1/2/3a/3b/4/ai_postcrash) is Shaun's own
    # strategic categorization IBKR has no concept of, and holdings.md must show the
    # real position either way rather than gate on that assignment.


def main() -> None:
    from .db import get_all_holdings, get_holding_row, upsert_holding
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
        print("\nDry run only — no writes made. Re-run with --apply to commit corrections and add new positions.")
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

    added = 0
    for row in diff["new_to_ibkr"]:
        upsert_holding(
            conn, ticker=row["ticker"], name=row["name"], asset_type=row["asset_type"],
            bucket=_NEW_POSITION_BUCKET, qty=row["qty"], avg_price=row["avg_price"],
            currency=row["currency"],
        )
        added += 1

    if corrected or added:
        regenerate_all(conn)
        _commit_and_push_holdings_files()
    conn.close()
    print(
        f"\nApplied: {corrected} correction(s), {added} new position(s) added "
        f"(bucket '{_NEW_POSITION_BUCKET}' — re-bucket them yourself when convenient), "
        f"{len(diff['missing_from_ibkr'])} missing (reported only)."
    )


if __name__ == "__main__":
    main()
