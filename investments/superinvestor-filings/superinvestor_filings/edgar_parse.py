"""Structured parsers for the EDGAR fast-disclosure forms this scanner tracks:
Forms 3/4/5 (ownershipDocument XML) and Schedule 13D/13G (structured XML post
2024-12-18, cover-page text fallback for older amendments). Pure functions, no
network, never raise -- any unparsable field comes back as None (module policy
mirrors mytrader.sec_filings)."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from typing import Any

# P = open-market buy, S = open-market sell -- the two codes that carry a conviction
# signal. A/M/G/F (grant / option exercise / gift / tax-withholding) are still
# recorded but never form the alert headline (see edgar_monitor).
HEADLINE_TRANSACTION_CODES = frozenset({"P", "S"})

_TRUE_VALUES = frozenset({"1", "true"})
_CUSIP_RE = re.compile(
    r"cusip\s*(?:number|no\.?|#)?\s*:?\s*([0-9A-Z]{9})\b", re.IGNORECASE
)
_PCT_RE = re.compile(
    r"percent\s+of\s+class[^:]{0,90}:\s*([0-9]+(?:\.[0-9]+)?)\s*%", re.IGNORECASE
)
_AGG_AMOUNT_RE = re.compile(
    r"aggregate\s+amount\s+beneficially\s+owned[^:]{0,90}:\s*([0-9][0-9,]*)", re.IGNORECASE
)
_ISSUER_NAME_RE = re.compile(
    r"name\s+of\s+issuer[^:\n]{0,15}:\s*([^\n]{2,90})", re.IGNORECASE
)


def _strip_ns(tag: str) -> str:
    return tag.split("}")[-1]


def _child(elem: ET.Element | None, name: str) -> ET.Element | None:
    if elem is None:
        return None
    for c in elem:
        if _strip_ns(c.tag) == name:
            return c
    return None


def _find(elem: ET.Element | None, *names: str) -> ET.Element | None:
    cur = elem
    for n in names:
        cur = _child(cur, n)
        if cur is None:
            return None
    return cur


def _find_text(elem: ET.Element | None, *names: str) -> str | None:
    node = _find(elem, *names)
    if node is not None and node.text and node.text.strip():
        return node.text.strip()
    return None


def _iter_named(elem: ET.Element | None, name: str):
    if elem is None:
        return
    for c in elem:
        if _strip_ns(c.tag) == name:
            yield c


def _to_float(raw: str | None) -> float | None:
    if raw is None:
        return None
    cleaned = raw.replace(",", "").replace("%", "").replace("$", "").strip()
    try:
        return float(cleaned)
    except ValueError:
        return None


def parse_ownership_form(xml_text: str) -> dict[str, Any] | None:
    """Forms 3/4/5. Returns issuer + reporting-owner identity and a
    transaction-by-transaction list (empty for a Form 3 holdings-only filing).
    issuer_ticker comes straight from issuerTradingSymbol -- no lookup needed."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return None
    if _strip_ns(root.tag) != "ownershipDocument":
        return None

    issuer = _child(root, "issuer")
    owner_names: list[str] = []
    owner_ciks: list[str] = []
    is_ten_pct_owner = False
    for ro in _iter_named(root, "reportingOwner"):
        name = _find_text(ro, "reportingOwnerId", "rptOwnerName")
        cik = _find_text(ro, "reportingOwnerId", "rptOwnerCik")
        if name:
            owner_names.append(name)
        if cik:
            owner_ciks.append(cik)
        flag = _find_text(ro, "reportingOwnerRelationship", "isTenPercentOwner")
        if flag is not None and flag.strip().lower() in _TRUE_VALUES:
            is_ten_pct_owner = True

    transactions: list[dict[str, Any]] = []
    for table_name in ("nonDerivativeTable", "derivativeTable"):
        table = _child(root, table_name)
        txn_name = "nonDerivativeTransaction" if table_name == "nonDerivativeTable" else "derivativeTransaction"
        for txn in _iter_named(table, txn_name):
            code = _find_text(txn, "transactionCoding", "transactionCode")
            transactions.append({
                "code": code,
                "date": _find_text(txn, "transactionDate", "value"),
                "shares": _to_float(_find_text(txn, "transactionAmounts", "transactionShares", "value")),
                "price": _to_float(
                    _find_text(txn, "transactionAmounts", "transactionPricePerShare", "value")
                ),
                "shares_owned_after": _to_float(
                    _find_text(txn, "postTransactionAmounts", "sharesOwnedFollowingTransaction", "value")
                ),
            })

    return {
        "issuer_name": _find_text(issuer, "issuerName"),
        "issuer_cik": _find_text(issuer, "issuerCik"),
        "issuer_ticker": _find_text(issuer, "issuerTradingSymbol"),
        "owner_name": owner_names[0] if owner_names else None,
        "owner_cik": owner_ciks[0] if owner_ciks else None,
        "is_ten_pct_owner": is_ten_pct_owner,
        "transactions": transactions,
    }


def _parse_13dg_structured(xml_text: str) -> dict[str, Any] | None:
    """Structured Schedule 13D/G XML (SEC format effective 2024-12-18). The exact
    element names are not fully verified against the SEC technical spec, so this
    walks every leaf element and matches by a normalised local name containing a
    known substring -- tolerant of schema variation. Returns None if the doc is not
    XML or exposes none of the target fields."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return None

    leaves: dict[str, str] = {}
    for el in root.iter():
        if list(el):  # not a leaf
            continue
        if el.text and el.text.strip():
            leaves.setdefault(_strip_ns(el.tag).lower(), el.text.strip())

    def _first_matching(*substrings: str) -> str | None:
        for key, val in leaves.items():
            if all(s in key for s in substrings):
                return val
        return None

    issuer_name = _first_matching("issuer", "name") or _first_matching("subjectcompany", "name")
    issuer_cik = _first_matching("issuer", "cik") or _first_matching("subjectcompany", "cik")
    cusip = _first_matching("cusip")
    shares = _to_float(
        _first_matching("aggregate", "amount") or _first_matching("amountbeneficiallyowned")
    )
    pct_owned = _to_float(
        _first_matching("percent", "class") or _first_matching("percentofclass")
    )

    if not any([issuer_name, issuer_cik, cusip, shares is not None, pct_owned is not None]):
        return None
    return {
        "issuer_name": issuer_name,
        "issuer_cik": issuer_cik,
        "cusip": cusip[:9] if cusip else None,
        "shares": shares,
        "pct_owned": pct_owned,
    }


def parse_schedule_13dg(doc_text: str) -> dict[str, Any] | None:
    """Schedule 13D / 13G / 13D-A / 13G-A. Tries the structured-XML parse first, then
    falls back to a targeted regex over the stripped cover-page text (older
    amendments of pre-2024 filings). Any field may be None; never raises."""
    stripped = doc_text.lstrip()
    if stripped.startswith("<?xml") or stripped.startswith("<edgarSubmission") or (
        stripped.startswith("<") and "edgarSubmission" in stripped[:2000]
    ):
        structured = _parse_13dg_structured(doc_text)
        if structured is not None:
            return structured

    # Text fallback -- import here so a pure-XML path never needs beautifulsoup4.
    from mytrader.sec_filings import strip_html

    text = strip_html(doc_text) if "<" in doc_text else doc_text
    collapsed = re.sub(r"\s+", " ", text)

    pct_match = _PCT_RE.search(collapsed)
    agg_match = _AGG_AMOUNT_RE.search(collapsed)
    cusip_match = _CUSIP_RE.search(collapsed)
    issuer_match = _ISSUER_NAME_RE.search(text)  # newline-anchored -- not the collapsed form

    pct_owned = _to_float(pct_match.group(1)) if pct_match else None
    shares = _to_float(agg_match.group(1)) if agg_match else None
    cusip = cusip_match.group(1) if cusip_match else None
    issuer_name = None
    if issuer_match:
        issuer_name = issuer_match.group(1).strip().rstrip(".").strip() or None

    if pct_owned is None and shares is None and cusip is None and issuer_name is None:
        return None
    return {
        "issuer_name": issuer_name,
        "issuer_cik": None,
        "cusip": cusip,
        "shares": shares,
        "pct_owned": pct_owned,
    }


def classify_material_crossing(
    form_type: str, pct_owned: float | None, prior_pct_owned: float | None
) -> str | None:
    """'5% cross' / '10% cross' / 'below 5%' / None. `prior_pct_owned` is the most
    recent percent this scanner previously recorded for the same filer + issuer
    (db.get_last_pct_owned). On the first-ever observation of a pair there is no
    prior: an initial 13D/13G is a fresh 5% (or 10%) crossing by definition; an
    amendment with no prior stays None."""
    if pct_owned is None:
        return None
    is_amendment = form_type.strip().endswith("/A")

    if prior_pct_owned is None:
        if is_amendment:
            # A 13D/G *amendment* implies a prior >= 5% filing by convention (you
            # only amend a schedule you were required to file). So an amendment now
            # reporting < 5%, even on the first time this scanner sees the pair, is a
            # drop through the threshold -- a near/full exit, the handoff's
            # highest-value 13G event. >= 5% with no prior stays None (could be a
            # routine holding-steady amendment).
            return "below 5%" if pct_owned < 5.0 else None
        if pct_owned >= 10.0:
            return "10% cross"
        if pct_owned >= 5.0:
            return "5% cross"
        return None

    if prior_pct_owned < 10.0 <= pct_owned:
        return "10% cross"
    if prior_pct_owned < 5.0 <= pct_owned:
        return "5% cross"
    if prior_pct_owned >= 5.0 > pct_owned:
        return "below 5%"
    return None
