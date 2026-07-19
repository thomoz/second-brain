"""Unified CLI for my-trader."""

from __future__ import annotations

import argparse


def _open_conn():
    from scripts.db import get_connection, init_db

    from .config import DB_PATH
    from .db import init_mytrader_tables

    init_db(DB_PATH)
    conn = get_connection(DB_PATH)
    init_mytrader_tables(conn)
    return conn


def _print_assessment(result: dict) -> None:
    print(f"\n=== {result['ticker']} ===")
    if result["excluded"]:
        print(f"EXCLUDED: {result['exclusion_reason']}")
        return
    if result["exclusion_reason"]:
        print(f"REVIEW: {result['exclusion_reason']}")
    if not result["data_available"]:
        print("No market data available.")
    for check in result["checks"]:
        print(f"  [{check.verdict:<7}] {check.name:<14} {check.detail}")
    if result["briefs_finance_score"] is not None:
        score = result["briefs_finance_score"]
        provisional = " (provisional)" if score["provisional"] else ""
        print(f"\nBriefs Finance score: {score['score']}/100{provisional}")
    else:
        print("\nBriefs Finance score: no history for this ticker")


def cmd_find(args) -> None:
    from .find import lookup_ticker

    conn = _open_conn()
    result = lookup_ticker(args.ticker, conn)
    conn.close()
    _print_assessment(result)


def cmd_watchlist_add(args) -> None:
    from .find import add_to_watchlist

    conn = _open_conn()
    add_to_watchlist(args.ticker, args.name, args.asset_type, args.bucket, args.notes, conn)
    conn.close()
    print(f"Added {args.ticker} to watchlist (bucket {args.bucket}).")


def cmd_holding_buy(args) -> None:
    from .holdings_ops import add_or_update_holding

    conn = _open_conn()
    add_or_update_holding(args.ticker, args.bucket, args.qty, args.price, "buy", conn)
    conn.close()
    print(f"Bought {args.qty} {args.ticker} @ {args.price} (bucket {args.bucket}).")


def cmd_holding_sell(args) -> None:
    from .holdings_ops import add_or_update_holding

    conn = _open_conn()
    add_or_update_holding(args.ticker, args.bucket, args.qty, args.price, "sell", conn)
    conn.close()
    print(f"Sold {args.qty} {args.ticker} @ {args.price} (bucket {args.bucket}).")


def cmd_snapshot(args) -> None:
    from .snapshot import regenerate_all

    conn = _open_conn()
    regenerate_all(conn)
    conn.close()
    print("Regenerated holdings.md and potential-holdings.md.")


def cmd_seed(args) -> None:
    from .seed import seed_confirmed_holdings

    conn = _open_conn()
    seed_confirmed_holdings(conn)
    conn.close()
    print("Seeded confirmed holdings/watchlist into the shared DB.")


def cmd_sync_candidates(args) -> None:
    from .candidate_sync import sync_new_candidates
    from .snapshot import regenerate_all

    conn = _open_conn()
    added = sync_new_candidates(conn)
    if added:
        regenerate_all(conn)
    conn.close()
    print(f"Synced {len(added)} new candidate(s) from Briefs Finance recommendations.")


def cmd_monitor(args) -> None:
    from .monitor import maybe_notify, run_monitor, write_report

    conn = _open_conn()
    result = run_monitor(conn)
    conn.close()
    write_report(result)
    maybe_notify(result)
    print(
        f"Monitor complete: {len(result['new_alerts'])} new alert(s), "
        f"{len(result['open_alerts'])} open. See investments/my-trader/monitor-report.md"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="my-trader — personal investing Find tool")
    subparsers = parser.add_subparsers(dest="command")

    p_find = subparsers.add_parser("find", help="Ephemeral assessment of a ticker")
    p_find.add_argument("--ticker", required=True)

    p_watch = subparsers.add_parser("watchlist-add", help="Add a ticker to the watchlist")
    p_watch.add_argument("--ticker", required=True)
    p_watch.add_argument("--name", required=True)
    p_watch.add_argument("--asset-type", dest="asset_type", required=True)
    p_watch.add_argument("--bucket", required=True)
    p_watch.add_argument("--notes", default="")

    p_buy = subparsers.add_parser("holding-buy", help="Record a buy against a holding")
    p_buy.add_argument("--ticker", required=True)
    p_buy.add_argument("--bucket", required=True)
    p_buy.add_argument("--qty", type=float, required=True)
    p_buy.add_argument("--price", type=float, required=True)

    p_sell = subparsers.add_parser("holding-sell", help="Record a sell against a holding")
    p_sell.add_argument("--ticker", required=True)
    p_sell.add_argument("--bucket", required=True)
    p_sell.add_argument("--qty", type=float, required=True)
    p_sell.add_argument("--price", type=float, required=True)

    subparsers.add_parser("snapshot", help="Regenerate holdings.md / potential-holdings.md from the DB")
    subparsers.add_parser("seed", help="One-time migration of Confirmed So Far rows into the DB")
    subparsers.add_parser("monitor", help="Scheduled re-check of all holdings + vetted watchlist")
    subparsers.add_parser("sync-candidates", help="Pull new Briefs Finance recommendations into the watchlist")

    args = parser.parse_args()

    dispatch = {
        "find": cmd_find,
        "watchlist-add": cmd_watchlist_add,
        "holding-buy": cmd_holding_buy,
        "holding-sell": cmd_holding_sell,
        "snapshot": cmd_snapshot,
        "seed": cmd_seed,
        "monitor": cmd_monitor,
        "sync-candidates": cmd_sync_candidates,
    }

    if args.command in dispatch:
        dispatch[args.command](args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
