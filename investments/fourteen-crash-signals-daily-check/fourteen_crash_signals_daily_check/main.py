"""CLI for the Fourteen Crash Signals daily check."""

from __future__ import annotations

import argparse


def _open_conn():
    from scripts.db import get_connection, init_db

    from goat.db import init_goat_tables
    from mytrader.db import init_mytrader_tables

    from .config import DB_PATH
    from .db import init_signals_tables

    init_db(DB_PATH)
    conn = get_connection(DB_PATH)
    init_mytrader_tables(conn)
    init_goat_tables(conn)  # needed for goat_sp500_constituents
    init_signals_tables(conn)
    return conn


def cmd_daily_check(args) -> None:
    from . import credit_spread, insider_trend, margin_debt, market_cap_milestone, report, watchlist
    from .alerts import maybe_notify

    conn = _open_conn()
    hot_watchlist = watchlist.get_or_refresh_hot_watchlist(conn)
    credit_spread_result = credit_spread.check_credit_spread_streak()
    margin_debt_result = margin_debt.check_margin_debt_growth()
    insider_trend_results = insider_trend.check_insider_trend(conn)
    market_cap_result = market_cap_milestone.check_market_cap_milestone(hot_watchlist)

    report.write_signals_report(
        [dict(r) for r in hot_watchlist], credit_spread_result, margin_debt_result,
        insider_trend_results, market_cap_result,
    )

    alert_inputs = [
        {"marker_key": "credit_spread_streak", "is_firing": credit_spread_result.verdict == "flag", "detail": credit_spread_result.detail},
        {"marker_key": "margin_debt_growth", "is_firing": margin_debt_result.verdict == "flag", "detail": margin_debt_result.detail},
        {"marker_key": "market_cap_milestone:" + str(market_cap_result.data.get("rung")), "is_firing": market_cap_result.verdict == "flag", "detail": market_cap_result.detail},
    ]
    for r in insider_trend_results:
        alert_inputs.append({
            "marker_key": f"insider_trend:{r.data.get('ticker')}",
            "is_firing": r.verdict == "flag", "detail": r.detail,
        })
    maybe_notify(conn, alert_inputs)
    conn.close()
    print(
        f"14 Crash Signals daily check complete: {len(hot_watchlist)} hot-watchlist "
        f"ticker(s), see investments/fourteen-crash-signals-daily-check/signals-report.md"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Fourteen Crash Signals -- daily crash-warning check")
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("daily-check", help="Run all built markers, write the combined report, alert on new firings")

    args = parser.parse_args()
    if args.command == "daily-check":
        cmd_daily_check(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
