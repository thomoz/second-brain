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
    from . import (
        alerts,
        capex_cashflow,
        credit_spread,
        credit_spread_issuer,
        db,
        insider_trend,
        lease_commitment,
        margin_debt,
        market_cap_milestone,
        report,
        super_bowl,
        watchlist,
    )
    from .alerts import maybe_notify

    conn = _open_conn()
    hot_watchlist = watchlist.get_or_refresh_hot_watchlist(conn)
    credit_spread_result = credit_spread.check_credit_spread_streak()
    margin_debt_result = margin_debt.check_margin_debt_growth()
    insider_trend_results = insider_trend.check_insider_trend(conn)
    market_cap_result = market_cap_milestone.check_market_cap_milestone(hot_watchlist)
    lease_commitment_results = lease_commitment.check_lease_commitments(conn, hot_watchlist)
    capex_cashflow_results = capex_cashflow.check_capex_cashflow(hot_watchlist)
    super_bowl_result = super_bowl.check_super_bowl_signal()
    credit_spread_issuer_results = credit_spread_issuer.check_credit_spread_issuer(conn, hot_watchlist)

    report.write_signals_report(
        [dict(r) for r in hot_watchlist], credit_spread_result, margin_debt_result,
        insider_trend_results, market_cap_result,
        lease_commitment_results, capex_cashflow_results, super_bowl_result, credit_spread_issuer_results,
    )

    alert_inputs = [
        {"marker_key": "margin_debt_growth", "is_firing": margin_debt_result.verdict == "flag", "detail": margin_debt_result.detail},
        {"marker_key": "market_cap_milestone:" + str(market_cap_result.data.get("rung")), "is_firing": market_cap_result.verdict == "flag", "detail": market_cap_result.detail},
        {"marker_key": "super_bowl_signal", "is_firing": super_bowl_result.verdict == "flag", "detail": super_bowl_result.detail},
    ]
    for r in insider_trend_results:
        alert_inputs.append({
            "marker_key": f"insider_trend:{r.data.get('ticker')}",
            "is_firing": r.verdict == "flag", "detail": r.detail,
        })
    for r in lease_commitment_results:
        alert_inputs.append({
            "marker_key": f"lease_commitments:{r.data.get('ticker')}",
            "is_firing": r.verdict == "flag", "detail": r.detail,
        })
    for r in capex_cashflow_results:
        alert_inputs.append({
            "marker_key": f"capex_cashflow:{r.data.get('ticker')}",
            "is_firing": r.verdict == "flag", "detail": r.detail,
        })
    for r in credit_spread_issuer_results:
        alert_inputs.append({
            "marker_key": f"credit_spread_issuer:{r.data.get('ticker')}",
            "is_firing": r.verdict == "flag", "detail": r.detail,
        })
    maybe_notify(conn, alert_inputs)

    db.upsert_signal_state(
        conn, marker_key="credit_spread_streak",
        is_firing=credit_spread_result.verdict == "flag", detail=credit_spread_result.detail,
    )
    alerts.notify_credit_spread_streak_daily(credit_spread_result)

    conn.close()
    print(
        f"14 Crash Signals daily check complete: {len(hot_watchlist)} hot-watchlist "
        f"ticker(s), see investments/fourteen-crash-signals-daily-check/signals-report.md"
    )


def cmd_record_bond_yield(args) -> None:
    from . import db

    conn = _open_conn()
    db.set_manual_bond_yield(conn, ticker=args.ticker.upper(), cusip=args.cusip, yield_pct=args.yield_pct)
    conn.close()
    print(f"Recorded manual bond yield for {args.ticker.upper()}: {args.yield_pct}%")


def main() -> None:
    parser = argparse.ArgumentParser(description="Fourteen Crash Signals -- daily crash-warning check")
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("daily-check", help="Run all built markers, write the combined report, alert on new firings")

    record_bond_yield_parser = subparsers.add_parser(
        "record-bond-yield",
        help="Manually record a bond yield reading for Marker #12 (fallback when no live source is available)",
    )
    record_bond_yield_parser.add_argument("ticker", help="Issuer ticker, e.g. ORCL")
    record_bond_yield_parser.add_argument("yield_pct", type=float, help="Current yield, as a percent, e.g. 5.75")
    record_bond_yield_parser.add_argument("--cusip", default=None, help="Optional CUSIP for reference")

    args = parser.parse_args()
    if args.command == "daily-check":
        cmd_daily_check(args)
    elif args.command == "record-bond-yield":
        cmd_record_bond_yield(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
