"""US / SEC EDGAR leg of the superinvestor fast-disclosure scanner. For each tracked
investor, for each of their CIKs, poll the submissions feed for the fast-disclosure
form set, parse each genuinely-new filing, and build a grouped alert. Control flow
mirrors goat.insider_scan.run_holdings_watch (fetch -> per-row dedup-key ->
insert_*_seen returns newly_seen -> continue if not new -> else build an alert)."""

from __future__ import annotations

import sqlite3
import time
from datetime import date, datetime, timedelta, timezone
from typing import Any

from mytrader import sec_filings
from mytrader.config import SEC_ARCHIVES_URL_TEMPLATE
from mytrader.db import get_sync_watermark, set_sync_watermark

from . import config, db, edgar_parse, issuer_lookup

_OWNERSHIP_FORMS = {"3", "4", "4/A", "5"}
_SCHEDULE_FORMS = {
    "SC 13D", "SC 13D/A", "SC 13G", "SC 13G/A",
    "SCHEDULE 13D", "SCHEDULE 13D/A", "SCHEDULE 13G", "SCHEDULE 13G/A",
}


def _canonical_form(form: str) -> str:
    """EDGAR labels the same Schedule 13D/G family both "SC 13G/A" (legacy) and
    "SCHEDULE 13G/A" (post-2024 structured submissions). Collapse to the short form
    so the dedup key and the report never split one form family in two."""
    return form.replace("SCHEDULE ", "SC ", 1) if form.startswith("SCHEDULE ") else form


def build_dedup_key(source: str, filer_key: str, form_type: str, issuer: str, accession: str) -> str:
    return "|".join([source, filer_key, form_type, issuer or "", accession or ""])


def _archive_url(cik: str, accession: str, document: str) -> str:
    return SEC_ARCHIVES_URL_TEMPLATE.format(
        cik=str(int(cik)), accession_no_dashes=accession.replace("-", ""), document=document,
    )


def _resolve_ownership_xml(cik: str, accession: str, primary_document: str) -> str | None:
    text = sec_filings.fetch_filing_document(cik, accession, primary_document)
    if text and "<ownershipDocument" in text[:5000]:
        return text
    index = sec_filings.fetch_filing_directory_index(cik, accession)
    if index:
        for item in index.get("directory", {}).get("item", []):
            name = item.get("name", "")
            low = name.lower()
            if low.endswith(".xml") and not low.startswith("xsl"):
                alt = sec_filings.fetch_filing_document(cik, accession, name)
                if alt and "<ownershipDocument" in alt[:5000]:
                    return alt
    return text


def _resolve_schedule_text(cik: str, accession: str, primary_document: str) -> str | None:
    primary = sec_filings.fetch_filing_document(cik, accession, primary_document)
    if primary_document.lower().endswith(".xml"):
        return primary
    index = sec_filings.fetch_filing_directory_index(cik, accession)
    if index:
        for item in index.get("directory", {}).get("item", []):
            name = item.get("name", "")
            low = name.lower()
            if low.endswith(".xml") and not low.startswith("xsl"):
                alt = sec_filings.fetch_filing_document(cik, accession, name)
                if alt:
                    return alt
    return primary


def _summarize_ownership(parsed: dict[str, Any], form_type: str) -> tuple[str, str | None, str | None]:
    """Returns (human summary, combined transaction code(s), most-recent txn date)."""
    txns = parsed.get("transactions", [])
    headline = [t for t in txns if t.get("code") in edgar_parse.HEADLINE_TRANSACTION_CODES]
    dates = sorted(t["date"] for t in headline if t.get("date"))
    event_date = dates[-1] if dates else None

    if not headline:
        if form_type == "3":
            return "new >10% beneficial-owner position disclosed", None, None
        return "no open-market buy/sell in this filing", None, event_date

    parts: list[str] = []
    codes: list[str] = []
    for code in ("P", "S"):
        matching = [t for t in headline if t["code"] == code]
        if not matching:
            continue
        total_shares = sum(t["shares"] or 0.0 for t in matching)
        prices = [t["price"] for t in matching if t["price"] is not None]
        verb = "bought" if code == "P" else "sold"
        price_clause = f" @ USD {prices[-1]:,.2f}" if prices else ""
        parts.append(f"{verb} {total_shares:,.0f} sh{price_clause}")
        codes.append(code)
    return "; ".join(parts), "/".join(codes), event_date


def _process_ownership(
    conn: sqlite3.Connection, filer_key: str, filer_display: str, cik: str, filing: dict[str, str]
) -> dict[str, Any] | None:
    accession = filing["accession_number"]
    form_type = filing["form"]
    filed_date = filing["filing_date"]
    xml_text = _resolve_ownership_xml(cik, accession, filing["primary_document"])
    parsed = edgar_parse.parse_ownership_form(xml_text) if xml_text else None

    issuer_name = parsed.get("issuer_name") if parsed else None
    issuer_ticker = issuer_lookup.resolve_ticker(
        conn, parsed.get("issuer_cik") if parsed else None,
        parsed.get("issuer_ticker") if parsed else None,
    )
    issuer_label = issuer_ticker or issuer_name or "unknown issuer"

    summary_body, txn_codes, event_date = ("filing details unavailable", None, None)
    is_ten_pct = False
    if parsed:
        summary_body, txn_codes, event_date = _summarize_ownership(parsed, form_type)
        is_ten_pct = bool(parsed.get("is_ten_pct_owner"))

    material_crossing = "10% cross" if form_type == "3" else None

    dedup_key = build_dedup_key("edgar", filer_key, form_type, issuer_label, accession)
    newly_seen = db.insert_superinvestor_filing_seen(
        conn, dedup_key=dedup_key, source="edgar", filer_key=filer_key,
        filer_display=filer_display, form_type=f"Form {form_type}", issuer=issuer_label,
        issuer_ticker=issuer_ticker, accession=accession, event_date=event_date,
        filed_date=filed_date, shares=None, pct_owned=None, pct_owned_change=None,
        material_crossing=material_crossing, transaction_code=txn_codes,
        raw_url=_archive_url(cik, accession, filing["primary_document"]),
    )
    if not newly_seen:
        return None

    line = f"Form {form_type} on {issuer_label} ({summary_body}"
    if event_date:
        line += f", txn {event_date}"
    line += f", filed {filed_date})"
    if is_ten_pct:
        line += " [>10% owner]"
    return {
        "filer_key": filer_key, "filer_display": filer_display,
        "form_type": f"Form {form_type}", "issuer": issuer_label,
        "issuer_ticker": issuer_ticker, "filed_date": filed_date, "event_date": event_date,
        "material_crossing": material_crossing, "summary": line,
        "raw_url": _archive_url(cik, accession, filing["primary_document"]),
    }


def _process_schedule(
    conn: sqlite3.Connection, filer_key: str, filer_display: str, cik: str, filing: dict[str, str]
) -> dict[str, Any] | None:
    accession = filing["accession_number"]
    form_type = _canonical_form(filing["form"])
    filed_date = filing["filing_date"]
    doc_text = _resolve_schedule_text(cik, accession, filing["primary_document"])
    parsed = edgar_parse.parse_schedule_13dg(doc_text) if doc_text else None

    issuer_name = parsed.get("issuer_name") if parsed else None
    issuer_cik = parsed.get("issuer_cik") if parsed else None
    issuer_ticker = issuer_lookup.resolve_ticker(conn, issuer_cik, None)
    issuer_label = issuer_ticker or issuer_name or "unknown issuer"

    pct_owned = parsed.get("pct_owned") if parsed else None
    shares = parsed.get("shares") if parsed else None

    prior_pct = db.get_last_pct_owned(conn, filer_key, issuer_label)
    material_crossing = edgar_parse.classify_material_crossing(form_type, pct_owned, prior_pct)
    pct_change = (pct_owned - prior_pct) if (pct_owned is not None and prior_pct is not None) else None

    dedup_key = build_dedup_key("edgar", filer_key, form_type, issuer_label, accession)
    newly_seen = db.insert_superinvestor_filing_seen(
        conn, dedup_key=dedup_key, source="edgar", filer_key=filer_key,
        filer_display=filer_display, form_type=form_type, issuer=issuer_label,
        issuer_ticker=issuer_ticker, accession=accession, event_date=None,
        filed_date=filed_date, shares=shares, pct_owned=pct_owned,
        pct_owned_change=pct_change, material_crossing=material_crossing,
        transaction_code=None,
        raw_url=_archive_url(cik, accession, filing["primary_document"]),
    )
    if not newly_seen:
        return None

    bits: list[str] = []
    if pct_owned is not None:
        bits.append(f"{pct_owned:.1f}% of class")
    if shares is not None:
        bits.append(f"{shares:,.0f} sh")
    detail = ", ".join(bits) if bits else "details in filing"
    line = f"{form_type} on {issuer_label} ({detail}, filed {filed_date})"
    if material_crossing:
        line += f" [{material_crossing}]"
    return {
        "filer_key": filer_key, "filer_display": filer_display,
        "form_type": form_type, "issuer": issuer_label, "issuer_ticker": issuer_ticker,
        "filed_date": filed_date, "event_date": None,
        "material_crossing": material_crossing, "summary": line,
        "raw_url": _archive_url(cik, accession, filing["primary_document"]),
    }


def scan_edgar(conn: sqlite3.Connection) -> dict[str, Any]:
    # Force the sec_cik_map refresh once so issuer_lookup sees a populated table on a
    # fresh DB (ticker value is irrelevant here -- it is the refresh side-effect we want).
    try:
        sec_filings.get_cik(conn, "AAPL")
    except Exception:
        pass

    first_seed = get_sync_watermark(conn, config.SUPERINVESTOR_FIRST_SEED_WATERMARK) is None
    since = date.today() - timedelta(days=config.SUPERINVESTOR_LOOKBACK_DAYS)

    new_filings: list[dict[str, Any]] = []
    for filer_key, cfg in config.SUPERINVESTOR_TRACKED.items():
        filer_display = cfg["display"]
        for cik in cfg["edgar_ciks"]:
            index = sec_filings.fetch_filing_index(cik)
            if index is None:
                print(f"[superinvestor-scan] no submissions for {filer_key} CIK {cik} -- skipped")
                continue
            filings = sec_filings.recent_filings_of_types(
                index, config.SUPERINVESTOR_EDGAR_FORMS, since
            )
            for filing in filings:
                form_type = filing["form"]
                if form_type in _OWNERSHIP_FORMS:
                    alert = _process_ownership(conn, filer_key, filer_display, cik, filing)
                elif form_type in _SCHEDULE_FORMS:
                    alert = _process_schedule(conn, filer_key, filer_display, cik, filing)
                else:
                    alert = None
                if alert is not None and not first_seed:
                    new_filings.append(alert)
                time.sleep(config.SUPERINVESTOR_SEC_REQUEST_DELAY_SECONDS)

    if first_seed:
        set_sync_watermark(
            conn, config.SUPERINVESTOR_FIRST_SEED_WATERMARK,
            datetime.now(timezone.utc).isoformat(),
        )

    recent = [dict(r) for r in db.get_recent_superinvestor_filings_seen(conn, source="edgar", limit=100)]
    return {"new_filings": new_filings, "recent_filings": recent, "first_seed": first_seed}
