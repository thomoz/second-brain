"""Unified CLI for Goat."""

from __future__ import annotations

import argparse


def _open_conn():
    from scripts.db import get_connection, init_db

    from .config import DB_PATH
    from .db import init_goat_tables
    from mytrader.db import init_mytrader_tables

    init_db(DB_PATH)
    conn = get_connection(DB_PATH)
    init_mytrader_tables(conn)  # needed for get_all_holdings() to work against a fresh DB
    init_goat_tables(conn)
    return conn


def cmd_monitor(args) -> None:
    from .monitor import (
        maybe_notify,
        run_monitor,
        run_sector_scan,
        write_report,
        write_sector_candidates_report,
        write_sector_ranking_report,
    )

    conn = _open_conn()
    result = run_monitor(conn)
    sector_result = run_sector_scan(conn)
    conn.close()
    result["new_sector_candidates"] = sector_result["new_candidates"]
    write_report(result)
    write_sector_ranking_report(sector_result)
    write_sector_candidates_report(sector_result)
    maybe_notify(result, new_sector_candidates=len(sector_result["new_candidates"]))
    print(
        f"Goat Monitor complete: {len(result['new_alerts'])} new exit alert(s), "
        f"{len(sector_result['new_candidates'])} new sector candidate(s). "
        f"See investments/goat/monitor-report.md"
    )


def cmd_scan_sectors(args) -> None:
    from .monitor import run_sector_scan, write_sector_candidates_report, write_sector_ranking_report

    conn = _open_conn()
    result = run_sector_scan(conn)
    conn.close()
    write_sector_ranking_report(result)
    write_sector_candidates_report(result)
    print(
        f"Sector scan complete: {len(result['new_candidates'])} new candidate(s), "
        f"{len(result['pending_candidates'])} pending. "
        f"See investments/goat/sector-ranking.md and sector-candidates-pending-review.md"
    )


def cmd_promote_candidate(args) -> None:
    from mytrader.db import upsert_watchlist_row
    from mytrader.snapshot import regenerate_all

    from .db import delete_goat_pending_candidate, get_goat_pending_candidate

    conn = _open_conn()
    ticker = args.ticker.strip().upper()
    pending = get_goat_pending_candidate(conn, ticker)
    if pending is None:
        conn.close()
        print(f"No pending Goat sector candidate found for {ticker}.")
        return

    # Deliberate, explicit exception to "Goat never writes into my-trader's
    # tables" -- see .agent/plans/goat-phase2-sector-rotation-ranking.md,
    # "THREE DECISIONS RESOLVED" #3. Only this command, only on explicit user
    # action, ever writes into my-trader's watchlist table.
    upsert_watchlist_row(
        conn, ticker=ticker, name=None, asset_type=args.asset_type,
        bucket=args.bucket, status=args.status,
        notes=f"Goat-approved sector rotation candidate — {pending['signal_detail']}",
        source="goat_sector_rotation",
    )
    delete_goat_pending_candidate(conn, ticker)
    regenerate_all(conn)  # refreshes my-trader's watchlist.md so the promoted row is visible
    conn.close()
    print(f"Promoted {ticker} to my-trader's watchlist (bucket {args.bucket}), labeled Goat-approved.")


def cmd_dismiss_candidate(args) -> None:
    from .db import delete_goat_pending_candidate

    conn = _open_conn()
    ticker = args.ticker.strip().upper()
    count = delete_goat_pending_candidate(conn, ticker)
    conn.close()
    print(f"Dismissed {count} pending Goat candidate(s) for {ticker}.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Goat -- sector-rotation + momentum tool")
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("monitor", help="Daily 150DMA exit-rule check against all holdings + sector rotation scan")
    subparsers.add_parser(
        "scan-sectors",
        help="On-demand sector rotation ranking + breakout scan (also runs daily as part of monitor)",
    )

    p_promote = subparsers.add_parser(
        "promote-candidate", help="Write a pending Goat sector candidate into my-trader's real watchlist",
    )
    p_promote.add_argument("--ticker", required=True)
    p_promote.add_argument("--bucket", default="unassigned")
    p_promote.add_argument("--asset-type", dest="asset_type", default="etf")
    p_promote.add_argument("--status", default="raw", choices=["raw", "discussed"])

    p_dismiss = subparsers.add_parser(
        "dismiss-candidate", help="Discard a pending Goat sector candidate (Goat-only, no watchlist write)",
    )
    p_dismiss.add_argument("--ticker", required=True)

    args = parser.parse_args()
    dispatch = {
        "monitor": cmd_monitor,
        "scan-sectors": cmd_scan_sectors,
        "promote-candidate": cmd_promote_candidate,
        "dismiss-candidate": cmd_dismiss_candidate,
    }
    if args.command in dispatch:
        dispatch[args.command](args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
