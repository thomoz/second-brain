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
    from .monitor import maybe_notify, run_monitor, write_report

    conn = _open_conn()
    result = run_monitor(conn)
    conn.close()
    write_report(result)
    maybe_notify(result)
    print(
        f"Goat Monitor complete: {len(result['new_alerts'])} new alert(s), "
        f"{len(result['open_alerts'])} open. See investments/goat/monitor-report.md"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Goat -- sector-rotation + momentum tool")
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("monitor", help="Daily 150DMA exit-rule check against all holdings")

    args = parser.parse_args()
    dispatch = {"monitor": cmd_monitor}
    if args.command in dispatch:
        dispatch[args.command](args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
