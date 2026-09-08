"""CLI for the superinvestor fast-disclosure filings scanner.

Subcommands:
  scan                 run both legs: US SEC EDGAR + India BSE SEBI SAST
  scan --edgar-only    US SEC EDGAR leg only
  scan --india-only    India BSE SEBI SAST leg only
  resolve-ciks         print (entity name, CIK) pairs EDGAR full-text search returns
                       for a tracked investor's name -- for manual config editing;
                       never writes config

Never run locally via `uv run --directory investments/superinvestor-filings ...` --
that creates a fresh empty local investments.db. All real runs go through
scripts/invoke_investments.ps1 against the VPS.
"""

from __future__ import annotations

import argparse


def _open_conn():
    from scripts.db import get_connection, init_db

    from mytrader.db import init_mytrader_tables

    from .config import DB_PATH
    from .db import init_superinvestor_tables

    init_db(DB_PATH)
    conn = get_connection(DB_PATH)
    init_mytrader_tables(conn)  # sec_cik_map + sync_state
    init_superinvestor_tables(conn)
    return conn


def cmd_scan(args) -> None:
    from . import config, db, notify, report
    from .edgar_monitor import scan_edgar
    from .sast_monitor import scan_india

    # A bare `scan` runs both legs; --edgar-only / --india-only restrict it.
    run_edgar = not args.india_only
    run_india = not args.edgar_only

    conn = _open_conn()
    result: dict = {"new_filings": [], "recent_filings": [], "first_seed": False}
    if run_edgar:
        edgar_result = scan_edgar(conn)
        result["new_filings"] += edgar_result["new_filings"]
        result["first_seed"] = result["first_seed"] or edgar_result["first_seed"]
    if run_india:
        india_result = scan_india(conn)
        result["new_filings"] += india_result["new_filings"]
        result["first_seed"] = result["first_seed"] or india_result["first_seed"]
    # The report always shows the full picture from the seen-log (both legs), not
    # just the leg that ran this time -- the two timers overwrite the same file.
    result["recent_filings"] = [
        dict(r) for r in db.get_recent_superinvestor_filings_seen(conn, limit=200)
    ]
    conn.close()

    report.write_report(result)
    notify.send_digest(result["new_filings"])

    seed_note = " (first-run seed complete, no alerts)" if result["first_seed"] else ""
    print(
        f"Superinvestor filings scan complete: {len(result['new_filings'])} new "
        f"filing(s){seed_note}. See {config.SUPERINVESTOR_REPORT_PATH.name}"
    )


def cmd_resolve_ciks(args) -> None:
    from mytrader import sec_filings

    from . import config

    forms = ",".join(sorted(config.SUPERINVESTOR_EDGAR_FORMS | {"13F-HR"}))
    for filer_key, cfg in config.SUPERINVESTOR_TRACKED.items():
        name = filer_key if args.name is None else args.name
        print(f"\n== {filer_key} ({cfg['display']}) -- searching EDGAR for '{name}' ==")
        hits = sec_filings.edgar_fulltext_search_hits(forms, entity_name=name)
        if hits is None:
            print("  (search failed -- no results)")
            continue
        seen: set[tuple[str, str]] = set()
        for hit in hits:
            names = hit.get("display_names") or []
            ciks = hit.get("ciks") or []
            for i, disp in enumerate(names):
                cik = ciks[i] if i < len(ciks) else (ciks[0] if ciks else "")
                pair = (disp, cik)
                if pair in seen:
                    continue
                seen.add(pair)
                print(f"  {disp}  ->  CIK {cik}")
        if not seen:
            print("  (no entity/CIK pairs found)")
        if args.name is not None:
            break


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Superinvestor fast-disclosure filings scanner (SEC EDGAR + SEBI SAST)"
    )
    subparsers = parser.add_subparsers(dest="command")

    p_scan = subparsers.add_parser("scan", help="Poll tracked filers for new fast-disclosure filings")
    p_scan.add_argument("--edgar-only", action="store_true", help="Run the US / SEC EDGAR leg only")
    p_scan.add_argument("--india-only", action="store_true", help="Run the India / BSE SEBI SAST leg only")

    p_resolve = subparsers.add_parser(
        "resolve-ciks",
        help="Print (entity name, CIK) pairs EDGAR full-text search returns for a filer name",
    )
    p_resolve.add_argument("--name", default=None, help="Entity name to search (default: each tracked filer_key)")

    args = parser.parse_args()
    dispatch = {"scan": cmd_scan, "resolve-ciks": cmd_resolve_ciks}
    if args.command in dispatch:
        dispatch[args.command](args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
