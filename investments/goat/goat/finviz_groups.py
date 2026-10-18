"""Finviz Groups scraper -- LIVE-VERIFIED 2026-10-18, see
.agent/plans/goat-industry-ranking-full-coverage.md Decision #1. A single free
page (groups.ashx?g=industry&v=140) already aggregates return performance by
industry server-side, covering all 144 Finviz industries in one request -- no
yfinance, no per-stock classification, no pagination, no ticker-watermark
handling (there is no ticker column on this page, only industry names)."""

from __future__ import annotations

from typing import Any

from mytrader.config import FINVIZ_USER_AGENT

from . import config

_HEADERS = {"User-Agent": FINVIZ_USER_AGENT}

# v=140 "Performance" view columns, live-confirmed 2026-10-18. "No." is the
# leading index column -- not extracted.
_PCT_COLUMNS = {
    "Perf Week": "perf_week",
    "Perf Month": "perf_month",
    "Perf Quart": "perf_quarter",
    "Perf Half": "perf_half",
    "Perf Year": "perf_year",
    "Perf YTD": "perf_ytd",
    "Change %": "change_pct",
}

_EXPECTED_HEADERS = [
    "No.", "Name", "Perf Week", "Perf Month", "Perf Quart", "Perf Half",
    "Perf Year", "Perf YTD", "Avg Volume", "Rel Volume", "Change %", "Volume",
]


def _norm(text: str) -> str:
    return " ".join(text.split())


def _parse_pct(text: str) -> float | None:
    """Strip a trailing '%' and parse to float. Finviz's own no-data placeholder
    is a bare '-' -- returns None for that (and for any other unparseable text),
    never raises."""
    text = text.strip()
    if not text or text == "-":
        return None
    try:
        return float(text.rstrip("%"))
    except ValueError:
        return None


def _rows_from_table(table) -> list[dict[str, Any]]:
    header_cells = [_norm(th.get_text(strip=True)) for th in table.find_all("th")]
    col_index = {h: i for i, h in enumerate(header_cells)}

    rows: list[dict[str, Any]] = []
    for tr in table.find_all("tr"):
        cells = tr.find_all("td")
        if len(cells) != len(header_cells):
            continue
        row: dict[str, Any] = {"name": _norm(cells[col_index["Name"]].get_text(strip=True))}
        for header, field in _PCT_COLUMNS.items():
            row[field] = _parse_pct(cells[col_index[header]].get_text(strip=True))
        row["avg_volume"] = _norm(cells[col_index["Avg Volume"]].get_text(strip=True))
        rel_volume_text = _norm(cells[col_index["Rel Volume"]].get_text(strip=True))
        try:
            row["rel_volume"] = float(rel_volume_text)
        except ValueError:
            row["rel_volume"] = None
        row["volume"] = _norm(cells[col_index["Volume"]].get_text(strip=True))
        rows.append(row)
    return rows


def fetch_industry_groups() -> list[dict[str, Any]] | None:
    """Fetch + parse the Finviz Groups industry-performance view. Returns None
    on total failure (bad status code, network exception, or the expected
    12-column table not found at all) -- never []. There is no partial-failure
    case here (one page, one table, not paginated), so the shape is simpler than
    finviz_screener.fetch_screener_universe."""
    import requests
    from bs4 import BeautifulSoup

    try:
        r = requests.get(
            config.GOAT_FINVIZ_GROUPS_URL,
            headers=_HEADERS,
            params={"g": "industry", "v": "140"},
            timeout=30,
        )
    except Exception:
        return None
    if r.status_code != 200:
        return None

    soup = BeautifulSoup(r.text, "html.parser")
    for table in soup.find_all("table"):
        header_cells = [_norm(th.get_text(strip=True)) for th in table.find_all("th")]
        if header_cells == _EXPECTED_HEADERS:
            return _rows_from_table(table)
    return None
