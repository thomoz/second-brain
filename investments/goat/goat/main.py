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
    maybe_notify(result, new_candidates=sector_result["new_candidates"])
    print(
        f"Goat Monitor complete: {len(result['new_alerts'])} new exit alert(s), "
        f"{len(sector_result['new_candidates'])} new sector candidate(s). "
        f"See investments/goat/monitor-report.md"
    )


def cmd_check_live(args) -> None:
    from .live_monitor import run_live_monitor
    from .monitor import maybe_notify

    conn = _open_conn()
    result = run_live_monitor(conn)
    conn.close()
    maybe_notify(result)
    print(
        f"Goat live check complete: checked {result['checked_holdings']} open-market "
        f"holding(s), {len(result['new_alerts'])} new alert(s)."
    )


def cmd_scan_sectors(args) -> None:
    from .monitor import (
        maybe_notify,
        run_sector_scan,
        write_sector_candidates_report,
        write_sector_ranking_report,
    )

    conn = _open_conn()
    result = run_sector_scan(conn)
    conn.close()
    write_sector_ranking_report(result)
    write_sector_candidates_report(result)
    maybe_notify({"new_alerts": []}, new_candidates=result["new_candidates"])
    print(
        f"Sector scan complete: {len(result['new_candidates'])} new candidate(s), "
        f"{len(result['pending_candidates'])} pending. "
        f"See investments/goat/sector-ranking.md and sector-candidates-pending-review.md"
    )


def cmd_scan_heartbeat(args) -> None:
    from .heartbeat_scan import run_heartbeat_scan, write_heartbeat_candidates_report
    from .monitor import maybe_notify

    conn = _open_conn()
    result = run_heartbeat_scan(conn)
    conn.close()
    write_heartbeat_candidates_report(result)
    maybe_notify(
        {"new_alerts": []}, new_candidates=result["new_candidates"],
        candidate_label="new S&P 500 heartbeat candidate(s)",
    )
    print(
        f"Heartbeat scan complete: scanned {result['scanned']} ticker(s) across "
        f"{len(result['rising_sectors'])} rising sector(s), "
        f"{len(result['new_candidates'])} new candidate(s). "
        f"See investments/goat/heartbeat-candidates-pending-review.md"
    )


def cmd_scan_insiders(args) -> None:
    from .insider_pattern_analysis import compute_pattern_analysis, write_pattern_analysis_report
    from .insider_scan import (
        compute_discovery_price_performance,
        compute_holdings_watch_price_performance,
        mature_price_outcome_snapshots,
        maybe_notify_price_flags,
        run_discovery_scan,
        run_discovery_sell_tracking,
        run_holdings_watch,
        write_insider_scan_report,
    )
    from .monitor import maybe_notify

    conn = _open_conn()
    watch_result = run_holdings_watch(conn)
    discovery_result = run_discovery_scan(conn)
    sell_tracking_result = run_discovery_sell_tracking(conn)
    # Price-since-trade is recalculated fresh every run (Shaun 2026-08-18) --
    # network calls, so deliberately kept outside run_discovery_scan/
    # run_holdings_watch (DB-only, cheap, easy to test without mocking yfinance).
    # conn stays open here: these also persist the price_flag_notified guard
    # (see their docstrings) so the "just confirmed the signal" ping fires once.
    discovery_result["pending_candidates"] = compute_discovery_price_performance(
        conn, discovery_result["pending_candidates"]
    )
    watch_result["recent_filings"] = compute_holdings_watch_price_performance(
        conn, watch_result.get("recent_filings") or []
    )
    maturation_result = mature_price_outcome_snapshots(conn)
    pattern_analysis = compute_pattern_analysis(conn)
    conn.close()
    write_insider_scan_report(watch_result, discovery_result)
    write_pattern_analysis_report(pattern_analysis)
    maybe_notify(
        {"new_alerts": watch_result["new_alerts"]},
        new_candidates=discovery_result["new_candidates"],
        alert_label="insider P/S filing(s) on current holdings",
        candidate_label="new insider discovery candidate(s)",
    )
    newly_flagged = (
        [r for r in discovery_result["pending_candidates"] if r.get("newly_flagged")]
        + [r for r in watch_result["recent_filings"] if r.get("newly_flagged")]
    )
    maybe_notify_price_flags(newly_flagged)
    print(
        f"Insider scan complete: {len(watch_result['new_alerts'])} holdings-watch alert(s), "
        f"{len(discovery_result['new_candidates'])} new discovery candidate(s), "
        f"{len(newly_flagged)} price move(s) newly confirmed the signal, "
        f"{sell_tracking_result['tracked']} market-wide sell(s) tracked, "
        f"{maturation_result['matured']} price-outcome snapshot(s) matured. "
        f"See investments/goat/insider-scan-report.md and "
        f"investments/goat/insider-pattern-analysis.md"
    )


def cmd_scan_hormuz(args) -> None:
    from .hormuz_risk import maybe_notify, run_hormuz_scan, write_hormuz_report

    conn = _open_conn()
    result = run_hormuz_scan(conn)
    conn.close()
    write_hormuz_report(result)
    maybe_notify(result["new_alerts"])
    print(
        f"Hormuz risk scan complete: {len(result['new_alerts'])} new flag(s). "
        f"See investments/goat/hormuz-risk-report.md"
    )


def cmd_promote_candidate(args) -> None:
    from mytrader.db import upsert_watchlist_row
    from mytrader.snapshot import regenerate_all

    from . import config
    from .db import delete_goat_pending_candidate, get_goat_pending_candidate

    conn = _open_conn()
    ticker = args.ticker.strip().upper()
    if ticker in config.GOAT_BANNED_TICKERS:
        conn.close()
        print(f"{ticker} is banned (see GOAT_BANNED_TICKERS) and cannot be promoted.")
        return
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
    subparsers.add_parser(
        "check-live",
        help="Intraday 150DMA live-price check against currently-open-market holdings",
    )
    subparsers.add_parser(
        "scan-heartbeat",
        help="On-demand S&P 500 heartbeat-pattern scan within currently-rising sectors",
    )
    subparsers.add_parser(
        "scan-insiders",
        help="Daily OpenInsider Form 4 scan -- holdings-watch (P/S on held tickers) + market-wide $25k+ purchase discovery",
    )
    subparsers.add_parser(
        "scan-hormuz",
        help="Strait of Hormuz war-risk check -- BWET tanker-freight ETF move + LMA JWC Listed Areas circular change",
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
        "check-live": cmd_check_live,
        "scan-heartbeat": cmd_scan_heartbeat,
        "scan-insiders": cmd_scan_insiders,
        "scan-hormuz": cmd_scan_hormuz,
        "promote-candidate": cmd_promote_candidate,
        "dismiss-candidate": cmd_dismiss_candidate,
    }
    if args.command in dispatch:
        dispatch[args.command](args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
