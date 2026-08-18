"""Marker 12 -- credit turns in the hot sector while the broad market stays calm (bond
yield vs. Treasury proxy, per-issuer). Two independent sub-problems (Phase 2 handoff,
Marker #12 resolution):

1. Ticker -> bond CUSIP: solved. Corporate bond prospectus filings (424B2/424B5/FWP)
   state "CUSIP No. XXXXXXXXX" on the cover page as a matter of regulatory practice --
   reuses sec_filings.py's CIK/filing-index/document-fetch plumbing (now public). Some
   issuers (private-credit-heavy names, Rule 144A private placements) have no public
   prospectus on EDGAR -- degrades to "no public bond found" for them, an honest gap, not
   a bug.

2. CUSIP -> current yield: NOT solved as of the Phase 2 handoff. FINRA's own Fixed Income
   Data Center and the Morningstar Bond Center mirror are both JS-rendered, not scrapeable
   via plain requests.get(). Four third-party candidate sites were named but none confirmed
   working (Atlantis Data Solutions, Terrapin Finance, Empirasign, Cbonds). TASK: live-
   verify each against a real CUSIP discovered by part 1 above BEFORE trusting
   _fetch_bond_yield_live's implementation here -- see that function's docstring. If none
   pan out, this check falls back to db.get_manual_bond_yield (Shaun enters a reading by
   hand via main.py's `record-bond-yield` subcommand, Task 22)."""

from __future__ import annotations

import re
import sqlite3
from datetime import date, timedelta
from typing import Any

from mytrader import sec_filings
from mytrader.checks import CheckResult
from scripts.macro import fred_value_on

from . import config, db

_CUSIP_RE = re.compile(
    r"CUSIP\s*(?:/\s*ISIN)?\s*(?:No\.?|Numbers?)?[:\s]*([A-Z0-9]{9})\b", re.IGNORECASE
)  # confirmed live 2026-08-18 against real ORCL FWP filings -- the plan's original
   # "CUSIP No. XXXXXXXXX" shape doesn't appear in practice; real filings use
   # "CUSIP / ISIN Numbers:\n<code> / <isin>" instead, hence the "/ ISIN" branch.


_MAX_PROSPECTUS_CANDIDATES_PER_FORM_TYPE = 5  # bound live document fetches per ticker --
    # see _resolve_cusip's GOTCHA on why more than just "the latest" is needed in practice.


def _recent_filing_entries(index: dict[str, Any], form_type: str, limit: int) -> list[dict[str, str]]:
    """Like sec_filings.latest_filing_entry, but returns up to `limit` matches instead of
    just the first -- needed because sec_filings.latest_filing_entry only returns the
    single most recent filing of a form type, and a company can file several FWPs/424Bs
    around one offering event (e.g. a bond term sheet AND a same-week preferred-stock
    term sheet both filed as FWP) where the single most-recent one isn't the bond one."""
    recent = index.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    entries = []
    for i, form in enumerate(forms):
        if form == form_type:
            entries.append({
                "accession_number": recent["accessionNumber"][i],
                "primary_document": recent["primaryDocument"][i],
                "filing_date": recent["filingDate"][i],
            })
            if len(entries) >= limit:
                break
    return entries


def _resolve_cusip(conn: sqlite3.Connection, ticker: str) -> str | None:
    cached = db.get_bond_cusip(conn, ticker)
    if cached is not None:
        return cached["cusip"]  # SIGNALS_BOND_CUSIP_REFRESH_DAYS staleness check: v1
            # skips this (re-resolving only when nothing is cached yet) -- see NOTES.

    cik = sec_filings.get_cik(conn, ticker)
    if cik is None:
        return None
    index = sec_filings.fetch_filing_index(cik)
    if index is None:
        return None

    candidates = []
    for form_type in config.SIGNALS_BOND_PROSPECTUS_FORM_TYPES:
        candidates.extend(_recent_filing_entries(index, form_type, _MAX_PROSPECTUS_CANDIDATES_PER_FORM_TYPE))
    if not candidates:
        return None  # no public prospectus on EDGAR -- e.g. Rule 144A private placement
    candidates.sort(key=lambda c: c["filing_date"], reverse=True)
    # Try candidates newest-first, not just the single latest one -- confirmed live
    # 2026-08-18 against real ORCL filings: the most recent 424B2 (base prospectus
    # supplement) only cross-references "CUSIP number" in prose without listing it,
    # while an FWP (term sheet) filed the same week has the real "CUSIP / ISIN
    # Numbers:" table. Falling through to the next-newest candidate when one doesn't
    # disclose a parseable CUSIP is what makes this actually work in practice, not
    # just pass unit tests against a single fixture.
    for entry in candidates:
        html = sec_filings.fetch_filing_document(cik, entry["accession_number"], entry["primary_document"])
        if html is None:
            continue
        text = sec_filings.strip_html(html)[:5000]  # cover page/term table is near the top
        match = _CUSIP_RE.search(text)
        if match is None:
            continue
        cusip = match.group(1).upper()
        db.upsert_bond_cusip(conn, ticker=ticker, cusip=cusip, accession_number=entry["accession_number"])
        return cusip
    return None  # none of the candidate prospectus filings disclosed a parseable CUSIP


def _fetch_bond_yield_live(cusip: str) -> float | None:
    """SPIKE TASK, do this FIRST before trusting the rest of this function: test each of
    the 4 candidate sites (Atlantis Data Solutions, Terrapin Finance, Empirasign, Cbonds)
    against a real CUSIP from _resolve_cusip() above -- proper request headers, check for
    a JSON/AJAX endpoint behind the page, not just the top-level URL (same approach that
    found SEC EDGAR needs a User-Agent header, see sec_filings.py's module docstring).
    Document findings in this docstring once tested. If a working source is found,
    implement the fetch here. If none pan out (a real, accepted possible outcome per the
    handoff), leave this returning None permanently -- check_credit_spread_issuer already
    falls back to db.get_manual_bond_yield when this returns None, so the marker degrades
    to a semi-automated, manually-entered-yield shape rather than breaking.

    2026-08-18 spike status: got a real CUSIP (68389XDV4, an Oracle note) from
    _resolve_cusip() above to test against. Cbonds' public search URL
    (cbonds.com/search/?query=<cusip>) 404'd on a plain fetch -- no free public lookup at
    that path, would need either a different (undocumented) endpoint or a paid API key,
    neither confirmed. Atlantis Data Solutions, Terrapin Finance, and Empirasign have no
    documented URLs in the source handoff (Empirasign is only noted there as returning a
    403 on a plain fetch, i.e. also not free-and-open) -- guessing at unverified domains
    for a security-scraping spike isn't a sound way to spend this session's remaining
    scope. Shipping the stub per the handoff's own accepted fallback plan (manual-entry
    via record-bond-yield). Revisit as a follow-up with real account/API access to one of
    these vendors, or a confirmed working endpoint, rather than guessing further."""
    return None  # unresolved as of the Phase 2 handoff -- see docstring


def _get_yield(conn: sqlite3.Connection, ticker: str, cusip: str) -> float | None:
    live = _fetch_bond_yield_live(cusip)
    if live is not None:
        return live
    manual = db.get_manual_bond_yield(conn, ticker)
    return manual["yield_pct"] if manual is not None else None


def _check_one_ticker(conn: sqlite3.Connection, ticker: str) -> CheckResult | None:
    cusip = _resolve_cusip(conn, ticker)
    if cusip is None:
        return None
    yield_pct = _get_yield(conn, ticker, cusip)
    if yield_pct is None:
        return CheckResult(
            name="credit_spread_issuer", verdict="unknown",
            detail=f"{ticker}: bond CUSIP {cusip} found, but no live or manually-entered "
                   f"yield reading available -- run `record-bond-yield {ticker} <yield_pct>`",
            data={"ticker": ticker, "cusip": cusip},
        )
    today = date.today()
    treasury_yield = fred_value_on(config.SIGNALS_CREDIT_SPREAD_ISSUER_TREASURY_SERIES, today)
    if treasury_yield is None:
        return CheckResult(
            name="credit_spread_issuer", verdict="unknown",
            detail=f"{ticker}: Treasury yield unavailable (FRED_API_KEY not set, or series unavailable)",
            data={"ticker": ticker, "cusip": cusip},
        )
    spread = yield_pct - treasury_yield
    db.record_issuer_spread(conn, ticker=ticker, spread_value=spread)

    prior = db.get_issuer_spread_near(
        conn, ticker, today - timedelta(days=config.SIGNALS_ISSUER_SPREAD_LOOKBACK_DAYS),
        config.SIGNALS_ISSUER_SPREAD_LOOKBACK_TOLERANCE_DAYS,
    )
    if prior is None:
        return CheckResult(
            name="credit_spread_issuer", verdict="ok",
            detail=f"{ticker}: spread {spread:.2f}pp (baseline, no 90-day-prior reading to "
                   f"compare divergence against yet)",
            data={"ticker": ticker, "cusip": cusip, "spread": spread},
        )
    prior_spread = prior["spread_value"]
    ratio = spread / prior_spread if prior_spread else None
    detail = (
        f"{ticker}: spread {spread:.2f}pp vs {prior_spread:.2f}pp 90 days ago ({ratio:.2f}x)"
        if ratio is not None else f"{ticker}: spread {spread:.2f}pp"
    )
    verdict = "flag" if ratio is not None and ratio >= config.SIGNALS_CREDIT_SPREAD_ISSUER_DIVERGENCE_FLAG_RATIO else "ok"
    return CheckResult(
        name="credit_spread_issuer", verdict=verdict, detail=detail,
        data={"ticker": ticker, "cusip": cusip, "spread": spread, "ratio": ratio},
    )


def check_credit_spread_issuer(conn: sqlite3.Connection, hot_watchlist: list[Any]) -> list[CheckResult]:
    results = []
    for row in hot_watchlist:
        result = _check_one_ticker(conn, row["ticker"])
        if result is not None:
            results.append(result)
    return results
