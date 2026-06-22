"""Backtest historical recommendations: prices, sector ETF context, macro snapshot."""

from __future__ import annotations

import argparse
import time
from datetime import date, datetime

from .db import (
    get_connection,
    init_db,
    upsert_macro_snapshot,
    upsert_outcome,
    upsert_sector_context,
)
from .macro import fetch_macro_snapshot
from .prices import compute_return_pct, get_asx_fallback, get_close_on_or_after, get_sp500_on_or_after
from .sector_map import fetch_sector_prices, resolve_sector_etf


def _parse_date(date_str: str | None) -> date | None:
    if not date_str:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m", "%d/%m/%Y"):
        try:
            return datetime.strptime(date_str[:10], fmt).date()
        except ValueError:
            continue
    return None


def _is_future(d: date | None, buffer_days: int = 2) -> bool:
    if d is None:
        return True
    return (d - date.today()).days >= -buffer_days


def backtest_recommendation(rec_row: dict, report_date_str: str | None, inferred_sector: str | None, conn) -> None:
    """Fetch and store outcome + sector context for one recommendation."""
    from dateutil.relativedelta import relativedelta

    rec_id = rec_row["id"]
    ticker = rec_row["ticker"]
    rec_date = _parse_date(report_date_str)
    if _is_future(rec_date):
        return

    # --- Stock prices ---
    price_rec = get_close_on_or_after(ticker, rec_date)
    if price_rec is None:
        price_rec = get_asx_fallback(ticker, rec_date)
    time.sleep(0.5)

    def _stock_price(months: int) -> float | None:
        target = rec_date + relativedelta(months=months)
        if _is_future(target):
            return None
        p = get_close_on_or_after(ticker, target)
        if p is None:
            p = get_asx_fallback(ticker, target)
        return p

    price_3m = _stock_price(3)
    time.sleep(0.5)
    price_6m = _stock_price(6)
    time.sleep(0.5)
    price_12m = _stock_price(12)
    time.sleep(0.5)

    # --- S&P 500 benchmark ---
    sp_rec = get_sp500_on_or_after(rec_date)
    sp_3m = get_sp500_on_or_after(rec_date + relativedelta(months=3)) if not _is_future(rec_date + relativedelta(months=3)) else None
    sp_6m = get_sp500_on_or_after(rec_date + relativedelta(months=6)) if not _is_future(rec_date + relativedelta(months=6)) else None
    sp_12m = get_sp500_on_or_after(rec_date + relativedelta(months=12)) if not _is_future(rec_date + relativedelta(months=12)) else None

    ret_3m = compute_return_pct(price_rec, price_3m)
    ret_6m = compute_return_pct(price_rec, price_6m)
    ret_12m = compute_return_pct(price_rec, price_12m)
    sp_ret_3m = compute_return_pct(sp_rec, sp_3m)
    sp_ret_6m = compute_return_pct(sp_rec, sp_6m)
    sp_ret_12m = compute_return_pct(sp_rec, sp_12m)

    vs_sp_3m = (ret_3m - sp_ret_3m) if ret_3m is not None and sp_ret_3m is not None else None
    vs_sp_6m = (ret_6m - sp_ret_6m) if ret_6m is not None and sp_ret_6m is not None else None
    vs_sp_12m = (ret_12m - sp_ret_12m) if ret_12m is not None and sp_ret_12m is not None else None

    upsert_outcome(
        conn,
        recommendation_id=rec_id,
        price_at_rec=price_rec,
        price_3m=price_3m,
        price_6m=price_6m,
        price_12m=price_12m,
        sp500_at_rec=sp_rec,
        sp500_3m=sp_3m,
        sp500_6m=sp_6m,
        sp500_12m=sp_12m,
        return_3m=ret_3m,
        return_6m=ret_6m,
        return_12m=ret_12m,
        vs_sp500_3m=vs_sp_3m,
        vs_sp500_6m=vs_sp_6m,
        vs_sp500_12m=vs_sp_12m,
    )

    # --- Sector ETF context ---
    etf = resolve_sector_etf(inferred_sector)
    if etf:
        etf_prices = fetch_sector_prices(etf, rec_date)
        etf_ret_3m = compute_return_pct(etf_prices["etf_price_at_rec"], etf_prices["etf_price_3m"])
        etf_ret_6m = compute_return_pct(etf_prices["etf_price_at_rec"], etf_prices["etf_price_6m"])
        etf_ret_12m = compute_return_pct(etf_prices["etf_price_at_rec"], etf_prices["etf_price_12m"])
        svs_3m = (ret_3m - etf_ret_3m) if ret_3m is not None and etf_ret_3m is not None else None
        svs_6m = (ret_6m - etf_ret_6m) if ret_6m is not None and etf_ret_6m is not None else None
        svs_12m = (ret_12m - etf_ret_12m) if ret_12m is not None and etf_ret_12m is not None else None
        upsert_sector_context(
            conn,
            recommendation_id=rec_id,
            sector_etf=etf,
            **etf_prices,
            etf_return_3m=etf_ret_3m,
            etf_return_6m=etf_ret_6m,
            etf_return_12m=etf_ret_12m,
            stock_vs_sector_3m=svs_3m,
            stock_vs_sector_6m=svs_6m,
            stock_vs_sector_12m=svs_12m,
        )


def run_backtest(ticker_filter: str | None = None) -> None:
    init_db()
    conn = get_connection()

    query = """
        SELECT r.id, r.ticker, r.report_id, r.excluded,
               rep.report_date, rep.inferred_sector, rep.id AS rep_id
        FROM recommendations r
        JOIN reports rep ON rep.id = r.report_id
        WHERE r.excluded = 0
    """
    params: list = []
    if ticker_filter:
        query += " AND r.ticker = ?"
        params.append(ticker_filter.upper())

    recs = conn.execute(query, params).fetchall()

    # Track which reports already have macro snapshots
    macro_done: set[int] = set()
    existing_macro = conn.execute("SELECT report_id FROM macro_snapshot").fetchall()
    macro_done.update(row["report_id"] for row in existing_macro)

    # Track which recs already have outcomes
    existing_outcomes = conn.execute("SELECT recommendation_id FROM outcomes").fetchall()
    done_ids = {row["recommendation_id"] for row in existing_outcomes}

    print(f"Backtesting {len(recs)} recommendations ({len(done_ids)} already done)...")

    for rec in recs:
        rec_dict = dict(rec)
        if rec_dict["id"] in done_ids and not ticker_filter:
            continue
        print(f"  {rec_dict['ticker']} (report {rec_dict['report_id']}, date {rec_dict['report_date']})")
        with conn:
            backtest_recommendation(rec_dict, rec_dict["report_date"], rec_dict["inferred_sector"], conn)

            # Macro snapshot per report (skip if already done)
            rep_id = rec_dict["rep_id"]
            if rep_id not in macro_done:
                rec_date = _parse_date(rec_dict["report_date"])
                if rec_date:
                    snapshot = fetch_macro_snapshot(rec_date)
                    upsert_macro_snapshot(
                        conn,
                        report_id=rep_id,
                        snapshot_date=rec_date.isoformat(),
                        **snapshot,
                    )
                    macro_done.add(rep_id)

    conn.close()
    print("Backtest complete.")


def print_stats() -> None:
    conn = get_connection()

    all_outcomes = conn.execute("""
        SELECT o.return_6m, o.vs_sp500_6m, sc.etf_return_6m, sc.stock_vs_sector_6m,
               rep.inferred_sector, r.ticker
        FROM outcomes o
        JOIN recommendations r ON r.id = o.recommendation_id
        JOIN reports rep ON rep.id = r.report_id
        LEFT JOIN sector_context sc ON sc.recommendation_id = r.id
        WHERE r.excluded = 0
    """).fetchall()

    total = len(all_outcomes)
    backtested = [r for r in all_outcomes if r["return_6m"] is not None]
    beat_sp = [r for r in backtested if r["vs_sp500_6m"] is not None and r["vs_sp500_6m"] > 0]
    sector_rose = [r for r in backtested if r["etf_return_6m"] is not None and r["etf_return_6m"] > 0]
    beat_sector = [r for r in backtested if r["stock_vs_sector_6m"] is not None and r["stock_vs_sector_6m"] > 0]

    print("\n=== Briefs Finance Track Record ===")
    print(f"Total recommendations: {total}")
    print(f"Backtested (6m data available): {len(backtested)}")
    if backtested:
        print(f"Beat S&P 500 at 6m: {len(beat_sp)}/{len(backtested)} ({len(beat_sp)/len(backtested)*100:.1f}%)")
    if sector_rose:
        print(f"Sector ETF rose (thesis validated): {len(sector_rose)}/{len(backtested)} ({len(sector_rose)/len(backtested)*100:.1f}%)")
    if beat_sector:
        print(f"Stock beat sector ETF (alpha): {len(beat_sector)}/{len(backtested)} ({len(beat_sector)/len(backtested)*100:.1f}%)")

    # Best/worst
    with_returns = [(r["ticker"], r["return_6m"], r["vs_sp500_6m"]) for r in backtested if r["return_6m"] is not None]
    if with_returns:
        best = max(with_returns, key=lambda x: x[1])
        worst = min(with_returns, key=lambda x: x[1])
        print(f"\nBest 6m return:  {best[0]} +{best[1]:.1f}% (vs S&P: {best[2]:+.1f}%)" if best[2] else f"\nBest 6m return: {best[0]} +{best[1]:.1f}%")
        print(f"Worst 6m return: {worst[0]} {worst[1]:.1f}% (vs S&P: {worst[2]:+.1f}%)" if worst[2] else f"\nWorst 6m return: {worst[0]} {worst[1]:.1f}%")

    # Sector breakdown
    sector_counts: dict[str, dict] = {}
    for r in backtested:
        sector = r["inferred_sector"] or "unknown"
        if sector not in sector_counts:
            sector_counts[sector] = {"total": 0, "beat": 0}
        sector_counts[sector]["total"] += 1
        if r["vs_sp500_6m"] is not None and r["vs_sp500_6m"] > 0:
            sector_counts[sector]["beat"] += 1

    if sector_counts:
        print("\n--- Per-Sector Breakdown ---")
        for sector, c in sorted(sector_counts.items(), key=lambda x: -x[1]["total"]):
            pct = c["beat"] / c["total"] * 100 if c["total"] else 0
            print(f"  {sector:<20} {c['beat']}/{c['total']} beat S&P ({pct:.0f}%)")

    conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Backtest Briefs Finance recommendations")
    parser.add_argument("--ticker", help="Backtest a specific ticker only")
    parser.add_argument("--stats", action="store_true", help="Show track record statistics")
    args = parser.parse_args()

    if args.stats:
        print_stats()
    else:
        run_backtest(ticker_filter=args.ticker)


if __name__ == "__main__":
    main()
