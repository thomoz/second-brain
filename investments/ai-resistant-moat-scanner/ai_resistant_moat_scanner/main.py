"""CLI for the AI-Resistant Moat Scanner.

Subcommands:
  scan                              run the daily scan (universe slice + seed + staged)
  promote-candidate --ticker X      write a staged candidate into my-trader's watchlist
  dismiss-candidate --ticker X      discard a staged candidate

Never run locally via `uv run --directory investments/ai-resistant-moat-scanner ...`
-- that creates a fresh empty local investments.db. All real runs go through
scripts/invoke_investments.ps1 against the VPS.

DATED CAVEAT: the AI-resistance rubric (config.RUBRIC_VERSION) encodes a 2026 view of
what AI can and cannot cheaply rebuild -- revisit it, do not treat it as permanent.
"""

from __future__ import annotations

import argparse


def _open_conn():
    from scripts.db import get_connection, init_db

    from mytrader.db import init_mytrader_tables

    from .config import DB_PATH
    from .db import init_moat_tables

    init_db(DB_PATH)
    conn = get_connection(DB_PATH)
    init_mytrader_tables(conn)  # sec_cik_map + holdings + watchlist
    init_moat_tables(conn)
    return conn


def cmd_scan(args) -> None:
    from . import notify, report, scan

    conn = _open_conn()
    result = scan.run_scan(conn)
    conn.close()
    report.write_report(result)
    report.write_candidates_report(result)
    notify.maybe_notify(result["new_candidates"])
    print(
        f"AI-Resistant Moat scan complete: scanned {result['scanned']}, "
        f"{len(result['new_candidates'])} new candidate(s), "
        f"{len(result['pending_candidates'])} pending. See "
        f"investments/ai-resistant-moat-scanner/moat-candidates-pending-review.md"
    )


def cmd_promote_candidate(args) -> None:
    from mytrader.db import upsert_watchlist_row
    from mytrader.snapshot import regenerate_all

    from .db import delete_moat_pending_candidate, get_moat_pending_candidate

    conn = _open_conn()
    ticker = args.ticker.strip().upper()
    pending = get_moat_pending_candidate(conn, ticker)
    if pending is None:
        conn.close()
        print(f"No pending AI-moat candidate found for {ticker}.")
        return

    # Deliberate, explicit exception to "this package never writes into my-trader's
    # tables" -- mirrors goat.main.cmd_promote_candidate. Only this command, only on
    # explicit user action, ever writes my-trader's watchlist.
    upsert_watchlist_row(
        conn,
        ticker=ticker,
        name=None,
        asset_type=args.asset_type,
        bucket=args.bucket,
        status=args.status,
        notes=f"AI-moat-approved — {pending['thesis']}",
        source="ai_resistant_moat",
    )
    delete_moat_pending_candidate(conn, ticker)
    regenerate_all(conn)  # refresh my-trader's watchlist.md so the promoted row shows
    conn.close()
    print(f"Promoted {ticker} to my-trader's watchlist (bucket {args.bucket}), labeled AI-moat-approved.")


def cmd_dismiss_candidate(args) -> None:
    from .db import delete_moat_pending_candidate

    conn = _open_conn()
    ticker = args.ticker.strip().upper()
    count = delete_moat_pending_candidate(conn, ticker)
    conn.close()
    print(f"Dismissed {count} pending AI-moat candidate(s) for {ticker}.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="AI-Resistant Moat Scanner -- ranks US-listed firms by AI-durable embedded-software moat"
    )
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("scan", help="Run the daily moat scan (universe slice + seed + staged names)")

    p_promote = subparsers.add_parser(
        "promote-candidate", help="Write a pending AI-moat candidate into my-trader's real watchlist",
    )
    p_promote.add_argument("--ticker", required=True)
    p_promote.add_argument("--bucket", default="unassigned")
    p_promote.add_argument("--asset-type", dest="asset_type", default="stock")
    p_promote.add_argument("--status", default="raw", choices=["raw", "discussed"])

    p_dismiss = subparsers.add_parser(
        "dismiss-candidate", help="Discard a pending AI-moat candidate (no watchlist write)",
    )
    p_dismiss.add_argument("--ticker", required=True)

    args = parser.parse_args()
    dispatch = {
        "scan": cmd_scan,
        "promote-candidate": cmd_promote_candidate,
        "dismiss-candidate": cmd_dismiss_candidate,
    }
    if args.command in dispatch:
        dispatch[args.command](args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
