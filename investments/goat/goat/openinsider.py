"""OpenInsider.com scraper -- Goat insider trading scanner. Scrapes SEC Form 4
open-market insider purchase/sale filings (aggregated by OpenInsider, no official
free API exists), mirroring sp500_universe.py's direct-fetch style (requests +
BeautifulSoup, headers dict, timeout, try/except-returns-None-on-any-failure)."""

from __future__ import annotations

from mytrader import tickers

from . import config

_HEADERS = {"User-Agent": config.GOAT_OPENINSIDER_USER_AGENT}

# /screener ignores a bare s=/vl= query -- it silently falls back to rendering
# the blank search form unless the FULL form field set is present (confirmed
# live 2026-08-17; the handoff doc's s/vl/td/tdr-only assumption was wrong).
# Two more live-confirmed quirks baked in here:
#  - "vl"/"vh" ("Traded K$" per the form's own label) are in THOUSANDS of
#    dollars, not raw dollars -- fetch_screener_filings divides by 1000.
#  - multiple tickers must be SPACE-separated in "s", not comma-separated
#    (comma makes OpenInsider treat the whole string as one unresolvable
#    ticker/CIK and silently fall back to the blank form, same failure mode
#    as an omitted field).
# Trade-type filtering is two boolean checkboxes (xp=Purchase, xs=Sale), not a
# single param -- fetch_screener_filings sets whichever one matches the
# requested trade_type.
_SCREENER_DEFAULT_PARAMS = {
    "o": "", "pl": "", "ph": "", "ll": "", "lh": "",
    # fd="7" (filing date within the last week, OpenInsider's tightest preset
    # above our own 5-day GOAT_INSIDER_HOLDINGS_WATCH_LOOKBACK_DAYS) -- without
    # this, a near-zero dollar floor (GOAT_INSIDER_SALE_MIN_VALUE) pulls the
    # ticker's ENTIRE multi-year filing history and hits the cnt cap (confirmed
    # live 2026-08-17: AAPL alone maxed out cnt=300 with fd="0"/all-dates).
    # Our own long-range 90-day pattern history lives in goat_insider_filings_seen,
    # not in this live fetch, so we only ever need "is there anything fresh".
    "fd": "7", "fdr": "", "td": "0", "tdr": "", "fdlyl": "", "fdlyh": "", "daysago": "",
    "xa": "", "xd": "", "xg": "", "xf": "", "xm": "", "xx": "", "xc": "", "xw": "",
    "excludeDerivRelated": "", "tmult": "",
    "vh": "", "ocl": "", "och": "",
    "sic1": "-1", "sicl": "", "sich": "",
    "isofficer": "", "iscob": "", "isceo": "", "ispres": "", "iscoo": "", "iscfo": "",
    "isgc": "", "isvp": "", "isdirector": "", "istenpercent": "", "isother": "",
    "grp": "0", "nfl": "", "nfh": "", "nil": "", "nih": "", "nol": "", "noh": "",
    "v2l": "", "v2h": "", "oc2l": "", "oc2h": "",
    "sortcol": "0", "cnt": "300", "page": "1",
}

_EXPECTED_COLUMNS = {
    "Filing Date": "filing_date",
    "Trade Date": "trade_date",
    "Ticker": "ticker",
    "Company Name": "company_name",
    "Insider Name": "insider_name",
    "Title": "title",
    "Trade Type": "trade_type",
    "Price": "price",
    "Qty": "qty",
    "Owned": "owned",
    "ΔOwn": "pct_owned_change",
    "Value": "value",
}


def _parse_money(text: str) -> float | None:
    if not text:
        return None
    cleaned = text.strip().replace("$", "").replace(",", "").replace("+", "")
    if not cleaned or cleaned in {"N/A", "-"}:
        return None
    try:
        # OpenInsider signs Value/Qty negative for sales (a share-count
        # decrease) -- we only ever want the trade's dollar magnitude.
        return abs(float(cleaned))
    except ValueError:
        return None


def _parse_pct_owned_change(text: str) -> float | None:
    """OpenInsider's ΔOwn column -- the insider's stake change as a % of their
    own prior holding (e.g. "-91%" for a sale of 91% of their position),
    distinct from GOAT_INSIDER_*_MIN_VALUE's raw dollar thresholds. "New"
    means no prior reported stake (a brand-new position), so % is undefined --
    returns None, same as any other unparsable value (fail open: never blocks
    the alert, the message clause is just omitted)."""
    if not text or text.strip() in {"New", "N/A", "-"}:
        return None
    cleaned = text.strip().replace("%", "").replace("+", "")
    try:
        return float(cleaned)
    except ValueError:
        return None


def _parse_table(html: str) -> list[dict] | None:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    table = None
    for candidate in soup.find_all("table"):
        headers = [th.get_text(strip=True) for th in candidate.find_all("th")]
        if "Ticker" in headers:
            table = candidate
            break
    if table is None:
        return None

    header_cells = table.find_all("th")
    col_index: dict[str, int] = {}
    for i, th in enumerate(header_cells):
        # OpenInsider's header cells use non-breaking spaces ("Filing\xa0Date"),
        # not regular spaces -- normalize whitespace before comparing.
        text = " ".join(th.get_text(strip=True).split())
        if text in _EXPECTED_COLUMNS:
            col_index[_EXPECTED_COLUMNS[text]] = i

    rows: list[dict] = []
    for tr in table.find_all("tr"):
        cells = tr.find_all("td")
        if not cells or "ticker" not in col_index or col_index["ticker"] >= len(cells):
            continue
        ticker_text = cells[col_index["ticker"]].get_text(strip=True)
        if not ticker_text:
            continue

        row: dict = {"ticker": tickers.normalize(ticker_text)}
        for field, idx in col_index.items():
            if field == "ticker" or idx >= len(cells):
                continue
            row[field] = cells[idx].get_text(strip=True)

        trade_type_text = row.get("trade_type", "")
        row["trade_type_code"] = trade_type_text.split(" - ")[0].split(" ")[0].strip() if trade_type_text else ""

        value = _parse_money(row.get("value", ""))
        if value is None:
            continue
        row["value"] = value

        row["pct_owned_change"] = _parse_pct_owned_change(row.get("pct_owned_change", ""))

        rows.append(row)

    return rows or None


def _fetch(url: str, params: dict | None = None) -> list[dict] | None:
    import requests

    try:
        r = requests.get(url, headers=_HEADERS, params=params, timeout=30)
        if r.status_code != 200:
            return None
        return _parse_table(r.text)
    except Exception:
        return None


def fetch_screener_filings(
    tickers_list: list[str], trade_type: str, min_value: float, filing_date_days: int = 7
) -> list[dict] | None:
    if not tickers_list:
        return []
    params = dict(_SCREENER_DEFAULT_PARAMS)
    params["s"] = " ".join(tickers_list)
    params["vl"] = str(int(min_value / 1000))
    params["xp"] = "1" if trade_type == "P" else ""
    params["xs"] = "1" if trade_type == "S" else ""
    params["fd"] = str(filing_date_days)
    rows = _fetch(f"{config.GOAT_OPENINSIDER_BASE_URL}/screener", params=params)
    if rows is None:
        return None
    return [r for r in rows if r["trade_type_code"] == trade_type]


def fetch_discovery_purchases() -> list[dict] | None:
    rows = _fetch(f"{config.GOAT_OPENINSIDER_BASE_URL}/latest-insider-purchases-25k")
    if rows is None:
        return None
    return [r for r in rows if r["trade_type_code"] == "P"]


def build_dedup_key(row: dict) -> str:
    return "|".join([
        row["ticker"],
        row.get("filing_date", ""),
        row.get("trade_date", ""),
        row.get("insider_name", ""),
        row["trade_type_code"],
        f"{row['value']:.2f}",
    ])
