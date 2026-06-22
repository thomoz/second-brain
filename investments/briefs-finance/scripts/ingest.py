"""Orchestration: discover PDFs → extract → ethical filter → store in DB."""

from __future__ import annotations

import argparse
import time
from pathlib import Path

from .config import REPORTS_DIR
from .db import get_connection, init_db, upsert_recommendation, upsert_report
from .ethical_filter import check_ticker
from .extract import compute_hash, extract_text
from .llm_extract import extract_recommendations


def discover_pdfs(folder: str | None = None) -> list[Path]:
    """Return all PDF paths in reports dir (optionally filtered by subfolder name)."""
    base = REPORTS_DIR
    if folder:
        base = base / folder
    return sorted(base.rglob("*.pdf"))


def ingest_pdf(pdf_path: Path, dry_run: bool = False, verbose: bool = True) -> dict:
    """Ingest a single PDF: extract, filter, store. Returns status dict."""
    content_hash = compute_hash(pdf_path)
    if not content_hash:
        return {"path": str(pdf_path), "status": "error", "reason": "unreadable"}

    if not dry_run:
        init_db()
        conn = get_connection()
        with conn:
            existing = conn.execute(
                "SELECT id FROM reports WHERE content_hash = ?", (content_hash,)
            ).fetchone()
        conn.close()
        if existing:
            if verbose:
                print(f"  SKIP (duplicate): {pdf_path.name}")
            return {"path": str(pdf_path), "status": "duplicate"}

    raw_text = extract_text(pdf_path)
    if not raw_text.strip():
        return {"path": str(pdf_path), "status": "empty"}

    if dry_run:
        print(f"  DRY RUN: would ingest {pdf_path.name} ({len(raw_text)} chars)")
        return {"path": str(pdf_path), "status": "dry_run"}

    if verbose:
        print(f"  Extracting: {pdf_path.name} ...", end=" ", flush=True)

    data = extract_recommendations(raw_text)

    report_date = data.get("report_date")
    title = data.get("title")
    report_type = data.get("report_type", "thematic")
    series = data.get("series")
    inferred_sector = data.get("inferred_sector")
    recs = data.get("recommendations", [])

    if verbose:
        print(f"{len(recs)} recs | sector={inferred_sector}")

    conn = get_connection()
    with conn:
        report_id = upsert_report(
            conn,
            file_path=str(pdf_path),
            content_hash=content_hash,
            report_date=report_date,
            report_type=report_type,
            series=series,
            title=title,
            inferred_sector=inferred_sector,
            raw_text=raw_text[:50000],  # cap stored text
        )

        stored = 0
        excluded = 0
        for rec in recs:
            ticker = rec.get("ticker", "").strip().upper()
            if not ticker:
                continue
            is_excluded, exclusion_reason = check_ticker(ticker)
            if is_excluded and verbose:
                print(f"    EXCLUDED: {ticker} — {exclusion_reason}")
            upsert_recommendation(
                conn,
                report_id=report_id,
                ticker=ticker,
                company_name=rec.get("company_name"),
                buy_thesis=rec.get("buy_thesis"),
                exit_trigger=rec.get("exit_trigger"),
                excluded=is_excluded,
                exclusion_reason=exclusion_reason,
            )
            if is_excluded:
                excluded += 1
            else:
                stored += 1
    conn.close()

    return {
        "path": str(pdf_path),
        "status": "ok",
        "report_id": report_id,
        "recs": stored,
        "excluded": excluded,
    }


def ingest_all(folder: str | None = None, dry_run: bool = False) -> None:
    pdfs = discover_pdfs(folder)
    print(f"Found {len(pdfs)} PDFs{' in ' + folder if folder else ''}.")
    if not dry_run:
        init_db()

    ok = skip = errors = 0
    for pdf in pdfs:
        result = ingest_pdf(pdf, dry_run=dry_run)
        status = result["status"]
        if status == "ok":
            ok += 1
        elif status == "duplicate":
            skip += 1
        elif status in ("empty", "error"):
            errors += 1
            print(f"  ERROR: {pdf.name} — {result.get('reason', status)}")
        time.sleep(1.0)  # rate-limit LLM calls

    print(f"\nDone. {ok} ingested, {skip} skipped (duplicate), {errors} errors.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest Briefs Finance PDFs into DB")
    parser.add_argument("--path", type=Path, help="Ingest a single PDF file")
    parser.add_argument("--folder", help="Subfolder to scan (e.g. pro-2025)")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing to DB")
    args = parser.parse_args()

    if args.path:
        result = ingest_pdf(args.path, dry_run=args.dry_run)
        print(result)
    else:
        ingest_all(folder=args.folder, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
