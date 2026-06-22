"""Unified CLI for Briefs Finance investment tool."""

from __future__ import annotations

import argparse
from pathlib import Path


def cmd_ingest(args) -> None:
    from .ingest import ingest_all, ingest_pdf
    if args.path:
        result = ingest_pdf(Path(args.path), dry_run=args.dry_run)
        print(result)
    else:
        ingest_all(folder=getattr(args, "folder", None), dry_run=args.dry_run)


def cmd_backtest(args) -> None:
    from .backtest import print_stats, run_backtest
    if args.stats:
        print_stats()
    else:
        run_backtest(ticker_filter=getattr(args, "ticker", None))


def cmd_score(args) -> None:
    from .score import score_all, score_ticker
    if getattr(args, "ticker", None):
        score_ticker(args.ticker)
    elif getattr(args, "all", False):
        score_all()
    elif getattr(args, "report_id", None):
        from .db import get_connection, init_db
        from .score import compute_score
        init_db()
        conn = get_connection()
        recs = conn.execute(
            "SELECT id FROM recommendations WHERE report_id = ? AND excluded = 0",
            (args.report_id,),
        ).fetchall()
        for rec in recs:
            result = compute_score(rec["id"], conn)
            print(f"{result.get('ticker')}: {result.get('score')}/100")
        conn.close()
    else:
        print("Specify --ticker, --all, or --report-id")


def cmd_assess(args) -> None:
    from .report import assess_ticker
    output = getattr(args, "output", "terminal")
    output_dir = Path(args.output_dir) if getattr(args, "output_dir", None) else None
    assess_ticker(args.ticker, output_mode=output, output_dir=output_dir)


def cmd_context(args) -> None:
    """Show sector ETF + macro context for a ticker's recommendation(s)."""
    from .db import get_connection, init_db
    init_db()
    conn = get_connection()
    rows = conn.execute("""
        SELECT r.ticker, rep.report_date, rep.inferred_sector,
               sc.sector_etf, sc.etf_return_6m, sc.stock_vs_sector_6m,
               ms.treasury_10y, ms.vix, ms.gold_price
        FROM recommendations r
        JOIN reports rep ON rep.id = r.report_id
        LEFT JOIN sector_context sc ON sc.recommendation_id = r.id
        LEFT JOIN macro_snapshot ms ON ms.report_id = rep.id
        WHERE r.ticker = ? AND r.excluded = 0
        ORDER BY rep.report_date DESC
    """, (args.ticker.upper(),)).fetchall()
    conn.close()
    if not rows:
        print(f"No data for {args.ticker}")
        return
    for row in rows:
        print(f"\n{row['report_date']} | Sector: {row['inferred_sector']} | ETF: {row['sector_etf']}")
        print(f"  ETF 6m: {row['etf_return_6m']:+.1f}% | Alpha: {row['stock_vs_sector_6m']:+.1f}%" if row["etf_return_6m"] is not None else "  Sector: data pending")
        print(f"  10Y: {row['treasury_10y']:.2f}% | VIX: {row['vix']:.1f} | Gold: {row['gold_price']:.2f}" if row["treasury_10y"] is not None else "  Macro: data pending")


def cmd_stats(args) -> None:
    from .backtest import print_stats
    print_stats()


def cmd_excluded(args) -> None:
    from .db import get_connection, init_db
    init_db()
    conn = get_connection()
    rows = conn.execute("""
        SELECT r.ticker, r.company_name, r.exclusion_reason, rep.report_date, rep.title
        FROM recommendations r
        JOIN reports rep ON rep.id = r.report_id
        WHERE r.excluded = 1
        ORDER BY r.ticker
    """).fetchall()
    conn.close()
    if not rows:
        print("No excluded stocks.")
        return
    print(f"\n{'='*60}")
    print(f"Excluded Defense/Military Stocks ({len(rows)} total)")
    print("="*60)
    for row in rows:
        print(f"  {row['ticker']:<8} {row['report_date']} | {row['title'][:50]}")
        print(f"           Reason: {row['exclusion_reason']}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Briefs Finance Investment Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  ingest   Ingest PDF reports into database
  backtest Backtest historical recommendations against market
  score    Compute 0-100 likelihood scores
  assess   Full assessment for a ticker (default command)
  context  Show sector + macro context for a ticker
  stats    Full track record summary
  excluded List all defense-filtered stocks
        """,
    )
    subparsers = parser.add_subparsers(dest="command")

    # ingest
    p_ingest = subparsers.add_parser("ingest", help="Ingest PDF reports")
    p_ingest.add_argument("--path", help="Single PDF to ingest")
    p_ingest.add_argument("--folder", help="Subfolder to scan (e.g. pro-2025)")
    p_ingest.add_argument("--dry-run", action="store_true")

    # backtest
    p_backtest = subparsers.add_parser("backtest", help="Backtest recommendations")
    p_backtest.add_argument("--ticker", help="Specific ticker to backtest")
    p_backtest.add_argument("--stats", action="store_true", help="Show statistics")

    # score
    p_score = subparsers.add_parser("score", help="Compute likelihood scores")
    p_score.add_argument("--ticker", help="Score a specific ticker")
    p_score.add_argument("--report-id", type=int, dest="report_id")
    p_score.add_argument("--all", action="store_true")

    # assess
    p_assess = subparsers.add_parser("assess", help="Full assessment for a ticker")
    p_assess.add_argument("--ticker", required=True)
    p_assess.add_argument("--output", choices=["terminal", "markdown", "html"], default="terminal")
    p_assess.add_argument("--output-dir", dest="output_dir", help="Override output directory")

    # context
    p_context = subparsers.add_parser("context", help="Sector + macro context")
    p_context.add_argument("--ticker", required=True)

    # stats
    subparsers.add_parser("stats", help="Track record summary")

    # excluded
    subparsers.add_parser("excluded", help="List defense-filtered stocks")

    args = parser.parse_args()

    dispatch = {
        "ingest": cmd_ingest,
        "backtest": cmd_backtest,
        "score": cmd_score,
        "assess": cmd_assess,
        "context": cmd_context,
        "stats": cmd_stats,
        "excluded": cmd_excluded,
    }

    if args.command in dispatch:
        dispatch[args.command](args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
