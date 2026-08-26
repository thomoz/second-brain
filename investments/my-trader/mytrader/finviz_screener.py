"""Finviz screener HTML-table scraper -- the US universe for the cash-value scan
(mytrader/cash_value_scan.py, see .agent/plans/cash-value-scanner.md). Mirrors
openinsider.py's direct-fetch style (requests + BeautifulSoup, headers dict,
timeout, try/except-returns-None-on-any-failure). Coarse Price/Cash prefilter only
-- the precise net-cash test runs later in the yfinance enrichment pass.

Live-verified 2026-08-26: the Overview view (v=111) renders ~20 <table> elements,
3-4 of which carry the exact results-column <th> set (a wrapper table also holds a
single giant concatenated mega-row). _parse_page picks the candidate table that
yields the most clean rows, and only accepts a <tr> whose <td> count matches the
header <td> count -- both defend against that wrapper table.

Finviz WATERMARKS the ticker symbol for unauthenticated HTML requests -- it doubles
the first character (AAPL -> AAAPL, MSFT -> MMSFT, F -> FF, AA -> AAA, BRK-B ->
BBRK-B). Company name / sector / market cap / price are all served correctly;
only the ticker cell is corrupted. Verified deterministic and stable across
requests over 11 known tickers incl. single-letter and doubled-first-letter edge
cases (2026-08-26), so _descramble_ticker just strips one leading duplicate. This
was not in .agent/plans/cash-value-scanner.md -- found during execution when a
live parse returned "AAAPL" for Apple. If Finviz ever changes the watermark
scheme, the descramble degrades safely: a wrong ticker fails the downstream
yfinance lookup and is dropped, it does not produce wrong data.
"""

from __future__ import annotations

import time

from . import config, tickers

_HEADERS = {"User-Agent": config.FINVIZ_USER_AGENT}

# v=111 "Overview" columns, live-confirmed 2026-08-26. Header label is "Change %"
# (not "Change") and there is a leading "No." index column -- neither is extracted.
_EXPECTED_COLUMNS = {
    "Ticker": "ticker",
    "Company": "company",
    "Sector": "sector",
    "Industry": "industry",
    "Country": "country",
    "Market Cap": "market_cap_text",
    "Price": "price_text",
}

# Present on every real Finviz screener page (in the "#N / M Total" results-count
# line) regardless of result count -- its absence means the response isn't a real
# screener results page (blocked, captcha, layout change) => None, not [].
_RESULTS_PAGE_MARKER = "Total"


def _fetch_page(row_offset: int) -> str | None:
    import requests

    params = {
        "v": "111",
        "f": config.FINVIZ_SCREENER_FILTERS,
        "o": "pricecash",
        "r": str(row_offset),
    }
    try:
        r = requests.get(config.FINVIZ_SCREENER_URL, headers=_HEADERS, params=params, timeout=30)
        if r.status_code != 200:
            return None
        return r.text
    except Exception:
        return None


def _norm(text: str) -> str:
    return " ".join(text.split())


def _descramble_ticker(text: str) -> str:
    """Undo Finviz's unauthenticated-request watermark (first character doubled).
    See the module docstring. Strips exactly one leading duplicate character."""
    if len(text) >= 2 and text[0] == text[1]:
        return text[1:]
    return text


def _looks_like_ticker(text: str) -> bool:
    """Finviz tickers are short and alphabetic (occasionally a dotted share class,
    e.g. BRK.B). A pure-digit cell is the "No." index column; anything with spaces
    or long is a parse artefact (the wrapper table's mega-row)."""
    if not text or len(text) > 8:
        return False
    stripped = text.replace(".", "").replace("-", "")
    return stripped.isalpha()


def _rows_from_table(table) -> list[dict]:
    header_cells = [_norm(th.get_text(strip=True)) for th in table.find_all("th")]
    col_index = {
        _EXPECTED_COLUMNS[h]: i for i, h in enumerate(header_cells) if h in _EXPECTED_COLUMNS
    }
    if "ticker" not in col_index or "market_cap_text" not in col_index:
        return []

    rows: list[dict] = []
    for tr in table.find_all("tr"):
        cells = tr.find_all("td")
        # Only accept a row whose column count matches this table's header exactly --
        # the wrapper table's concatenated mega-row has ~220 cells and is rejected here.
        if len(cells) != len(header_cells):
            continue
        ticker_text = cells[col_index["ticker"]].get_text(strip=True)
        if not _looks_like_ticker(ticker_text):
            continue
        row = {"ticker": tickers.normalize(_descramble_ticker(ticker_text))}
        for field, idx in col_index.items():
            if field == "ticker":
                continue
            row[field] = _norm(cells[idx].get_text(strip=True))
        rows.append(row)
    return rows


def _parse_page(html: str) -> list[dict] | None:
    """One page's data rows. [] = a valid screener page with no rows (end of
    pagination); None = the response isn't a real screener results page at all."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")

    best: list[dict] = []
    saw_candidate_table = False
    for table in soup.find_all("table"):
        headers = {_norm(th.get_text(strip=True)) for th in table.find_all("th")}
        if "Ticker" not in headers or "Market Cap" not in headers:
            continue
        saw_candidate_table = True
        rows = _rows_from_table(table)
        # Dedup within this table (a wrapper table nests the real one, so the same
        # <tr> can be reached twice) and keep the table that yields the most rows.
        seen: set[str] = set()
        deduped = [r for r in rows if not (r["ticker"] in seen or seen.add(r["ticker"]))]
        if len(deduped) > len(best):
            best = deduped

    if best:
        return best
    if saw_candidate_table or _RESULTS_PAGE_MARKER in html:
        return []  # real screener page, just no rows on/after this offset
    return None


def fetch_screener_universe() -> list[dict] | None:
    """Paginate the coarse Finviz screen. Returns the deduped list of rows, or None
    if the FIRST page fails (total failure -- the caller serves a stale report). A
    later-page failure stops pagination early and returns what was gathered so far
    (a partial coarse list is fine -- the precise test runs downstream anyway)."""
    all_rows: list[dict] = []
    seen: set[str] = set()
    for page in range(config.FINVIZ_MAX_PAGES):
        offset = 1 + page * config.FINVIZ_SCREENER_ROWS_PER_PAGE
        html = _fetch_page(offset)
        if html is None:
            if page == 0:
                return None
            break
        parsed = _parse_page(html)
        if parsed is None:
            if page == 0:
                return None
            break
        if not parsed:
            break
        new = [r for r in parsed if r["ticker"] not in seen]
        if not new:
            break  # page repeated (offset past the end) -- stop
        for r in new:
            seen.add(r["ticker"])
        all_rows.extend(new)
        if len(parsed) < config.FINVIZ_SCREENER_ROWS_PER_PAGE:
            break  # short page = last page
        if page < config.FINVIZ_MAX_PAGES - 1:
            time.sleep(config.FINVIZ_REQUEST_DELAY_SECONDS)
    return all_rows
