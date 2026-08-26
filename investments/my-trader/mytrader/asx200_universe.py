"""S&P/ASX 200 constituent universe for the cash-value scan (mytrader/
cash_value_scan.py, see .agent/plans/cash-value-scanner.md). Scrapes Wikipedia's
"Constituent companies" table -- mirrors goat/goat/sp500_universe.py's fetch style
(requests + BeautifulSoup, headers dict, timeout, try/except-returns-None-on-any-
failure).

No DB cache: unlike goat's S&P 500 scan this tool is DB-write-free, so it re-scrapes
each run. A scrape failure just means "no ASX rows this run" -- cash_value_scan.py
notes that inline and still writes the US report.

Live-verified 2026-08-26: one `class="wikitable"` with headers Code / Company /
Sector / Market Capitalisation (A$) / Headquarters, 200 data rows, all cells <td>.
ASX codes are 3 chars and CAN be numeric or alphanumeric ("360" = Life360, "4DX" =
4DMedical, "A2M" = a2 Milk) -- do NOT strip digits. yfinance form is <CODE>.AX,
built by the caller via tickers.asx_variant.
"""

from __future__ import annotations

import re

from . import config, tickers

_HEADERS = {"User-Agent": config.ASX200_USER_AGENT}

_CODE_HEADERS = ("code", "asx code", "symbol", "ticker")
_COMPANY_HEADERS = ("company", "company name", "name")
_SECTOR_HEADERS = ("sector", "gics sector")

_REF_MARKER_RE = re.compile(r"\[[^\]]*\]")  # strip "[1]" / "[note 2]" footnote markers


def _clean_code(text: str) -> str:
    return _REF_MARKER_RE.sub("", text).strip().upper()


def fetch_asx200_constituents() -> list[dict[str, str]] | None:
    import requests
    from bs4 import BeautifulSoup

    try:
        r = requests.get(config.ASX200_WIKI_URL, headers=_HEADERS, timeout=30)
        if r.status_code != 200:
            return None
        soup = BeautifulSoup(r.text, "html.parser")

        table = None
        for candidate in soup.find_all("table", {"class": "wikitable"}):
            headers = [th.get_text(strip=True).lower() for th in candidate.find_all("th")]
            if any(h in _CODE_HEADERS for h in headers):
                table = candidate
                break
        if table is None:
            return None

        header_cells = [th.get_text(strip=True).lower() for th in table.find_all("th")]

        def _col(names: tuple[str, ...]) -> int | None:
            for i, h in enumerate(header_cells):
                if h in names:
                    return i
            return None

        code_i = _col(_CODE_HEADERS)
        company_i = _col(_COMPANY_HEADERS)
        sector_i = _col(_SECTOR_HEADERS)
        if code_i is None:
            return None

        rows: list[dict[str, str]] = []
        for tr in table.find_all("tr")[1:]:  # skip header row
            cells = tr.find_all(["td", "th"])
            if code_i >= len(cells):
                continue
            code = _clean_code(cells[code_i].get_text(strip=True))
            if not code or code.lower() in _CODE_HEADERS:
                continue
            rows.append({
                "ticker": tickers.normalize(code),  # bare code; .AX added by caller
                "company": (
                    cells[company_i].get_text(strip=True)
                    if company_i is not None and company_i < len(cells) else ""
                ),
                "sector": (
                    cells[sector_i].get_text(strip=True)
                    if sector_i is not None and sector_i < len(cells) else ""
                ),
            })
        return rows or None
    except Exception:
        return None
