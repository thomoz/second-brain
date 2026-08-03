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

    principles = next((c for c in result["checks"] if c.name == "principles_fit"), None)
    if principles is not None and principles.data.get("results"):
        macro_as_of = principles.data.get("macro_snapshot_as_of")
        macro_note = f" (macro regime as of {macro_as_of})" if macro_as_of else " (no cached macro snapshot — run Monitor at least once)"
        print(f"\nPrinciples fit (Find's own read, graded against all 9 frameworks{macro_note}):")
        for p in sorted(principles.data["results"], key=lambda r: r["score"], reverse=True):
            print(f"  {p['principle']:<10}: {p['score']:>3}/100 — {p['reasoning']}")
        filing_types = principles.data.get("filing_types_used") or []
        if filing_types:
            print(f"  (includes SEC filing read: {', '.join(filing_types)})")


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


def cmd_watchlist_remove(args) -> None:
    from .db import delete_watchlist_row
    from .snapshot import regenerate_all
    from .tickers import normalize

    conn = _open_conn()
    ticker = normalize(args.ticker)
    count = delete_watchlist_row(conn, ticker, args.bucket)
    if count:
        regenerate_all(conn)
    conn.close()
    print(f"Removed {count} watchlist row(s) for {ticker}.")


def cmd_watchlist_move_bucket(args) -> None:
    from .db import (
        delete_watchlist_row, get_all_watchlist, get_watchlist_row,
        update_watchlist_return_data, upsert_watchlist_row,
    )
    from .snapshot import regenerate_all
    from .tickers import normalize

    conn = _open_conn()
    ticker = normalize(args.ticker)

    if args.from_bucket is not None:
        row = get_watchlist_row(conn, ticker, args.from_bucket)
    else:
        matches = [w for w in get_all_watchlist(conn) if w["ticker"] == ticker]
        if len(matches) > 1:
            buckets = ", ".join(m["bucket"] for m in matches)
            conn.close()
            print(f"{ticker} exists in multiple buckets ({buckets}) — specify --from-bucket.")
            return
        row = matches[0] if matches else None

    if row is None:
        conn.close()
        print(f"No watchlist row found for {ticker}.")
        return

    delete_watchlist_row(conn, ticker, row["bucket"])
    upsert_watchlist_row(
        conn, ticker=ticker, name=row["name"], asset_type=row["asset_type"],
        bucket=args.to_bucket, status=row["status"], notes=row["notes"],
        source=row["source"], last_expense_ratio=row["last_expense_ratio"],
    )
    if row["dividend_yield_pct"] is not None or row["ten_year_return_pct"] is not None:
        update_watchlist_return_data(
            conn, ticker, args.to_bucket, row["dividend_yield_pct"], row["ten_year_return_pct"],
        )
    regenerate_all(conn)
    conn.close()
    print(f"Moved {ticker} from bucket {row['bucket']} to {args.to_bucket}.")


def cmd_refresh_watchlist_data(args) -> None:
    from .return_data import refresh_watchlist_return_data
    from .snapshot import regenerate_all

    conn = _open_conn()
    updated = refresh_watchlist_return_data(conn)
    regenerate_all(conn)
    conn.close()
    print(f"Refreshed dividend/10Y return data for {updated} watchlist row(s) with data found.")


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
    print("Regenerated holdings.md, watchlist.md, and synced-candidates-pending-review.md.")


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
    print(
        f"Synced {len(added)} new candidate(s) from Briefs Finance into "
        f"synced-candidates-pending-review.md — review and promote-candidate the ones you want."
    )


def cmd_promote_candidate(args) -> None:
    from .db import delete_pending_candidate, get_pending_candidate, upsert_watchlist_row
    from .snapshot import regenerate_all
    from .tickers import normalize

    conn = _open_conn()
    ticker = normalize(args.ticker)
    pending = get_pending_candidate(conn, ticker)
    if pending is None:
        conn.close()
        print(f"No pending candidate found for {ticker}.")
        return

    upsert_watchlist_row(
        conn, ticker=ticker, name=pending["company_name"], asset_type=args.asset_type,
        bucket=args.bucket, status=args.status, notes=pending["buy_thesis"] or "",
        source=pending["source"],
    )
    delete_pending_candidate(conn, ticker)
    regenerate_all(conn)
    conn.close()
    print(f"Promoted {ticker} to watchlist (bucket {args.bucket}, status {args.status}).")


def cmd_dismiss_candidate(args) -> None:
    from .db import delete_pending_candidate
    from .snapshot import regenerate_all
    from .tickers import normalize

    conn = _open_conn()
    ticker = normalize(args.ticker)
    count = delete_pending_candidate(conn, ticker)
    if count:
        regenerate_all(conn)
    conn.close()
    print(f"Dismissed {count} pending candidate(s) for {ticker}.")


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

    p_watch_remove = subparsers.add_parser("watchlist-remove", help="Remove a ticker from the watchlist")
    p_watch_remove.add_argument("--ticker", required=True)
    p_watch_remove.add_argument("--bucket", default=None, help="Omit to remove from every bucket")

    p_watch_move = subparsers.add_parser("watchlist-move-bucket", help="Move a watchlist ticker to a different bucket")
    p_watch_move.add_argument("--ticker", required=True)
    p_watch_move.add_argument("--to-bucket", dest="to_bucket", required=True)
    p_watch_move.add_argument(
        "--from-bucket", dest="from_bucket", default=None,
        help="Omit if the ticker exists in exactly one bucket",
    )

    subparsers.add_parser(
        "refresh-watchlist-data",
        help="Fetch dividend yield + 10Y return for every watchlist row via yfinance",
    )

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

    subparsers.add_parser("snapshot", help="Regenerate holdings.md / watchlist.md from the DB")
    subparsers.add_parser("seed", help="One-time migration of Confirmed So Far rows into the DB")
    subparsers.add_parser("monitor", help="Scheduled re-check of all holdings + vetted watchlist")
    subparsers.add_parser(
        "sync-candidates",
        help="Pull new Briefs Finance recommendations into synced-candidates-pending-review.md",
    )

    p_promote = subparsers.add_parser(
        "promote-candidate", help="Move a pending synced candidate into the real watchlist",
    )
    p_promote.add_argument("--ticker", required=True)
    p_promote.add_argument("--bucket", default="unassigned")
    p_promote.add_argument("--asset-type", dest="asset_type", default="stock")
    p_promote.add_argument("--status", default="raw", choices=["raw", "discussed"])

    p_dismiss = subparsers.add_parser(
        "dismiss-candidate", help="Discard a pending synced candidate without adding it to the watchlist",
    )
    p_dismiss.add_argument("--ticker", required=True)

    args = parser.parse_args()

    dispatch = {
        "find": cmd_find,
        "watchlist-add": cmd_watchlist_add,
        "watchlist-remove": cmd_watchlist_remove,
        "watchlist-move-bucket": cmd_watchlist_move_bucket,
        "holding-buy": cmd_holding_buy,
        "holding-sell": cmd_holding_sell,
        "snapshot": cmd_snapshot,
        "seed": cmd_seed,
        "monitor": cmd_monitor,
        "sync-candidates": cmd_sync_candidates,
        "promote-candidate": cmd_promote_candidate,
        "dismiss-candidate": cmd_dismiss_candidate,
        "refresh-watchlist-data": cmd_refresh_watchlist_data,
    }

    if args.command in dispatch:
        dispatch[args.command](args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
