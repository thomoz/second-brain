"""Australia CPI (headline, YoY) -- direct from the ABS's own published spreadsheet,
not FRED's OECD-relay copy (verified 2026-07-30: FRED's AUSCPIALLQINMEI was 18+
months stale). ABS publishes a fresh xlsx each release with the release month
embedded in the URL path (e.g. .../jun-2026/640101.xlsx) -- there is no permanent
URL, so _fetch_workbook_bytes() walks backward from the current month (bounded) until
a file resolves, self-healing against release-day timing without a hardcoded
release calendar.

Data1 sheet layout (verified 2026-07-30 against the June 2026 release, 9 metadata
header rows then one data row per month): column 0 = date, column 1 = Australia CPI
index level, column 10 = Australia % change from corresponding month of previous
year (the headline YoY figure this module returns).
"""

from __future__ import annotations

import io
from calendar import month_name
from datetime import date

import requests

_ABS_URL_TEMPLATE = (
    "https://www.abs.gov.au/statistics/economy/price-indexes-and-inflation/"
    "consumer-price-index-australia/{month}-{year}/640101.xlsx"
)
_MONTH_ROLLBACK_TRIES = 4  # ABS publishes ~4 weeks after month-end -- try the
                             # current month first, then step back.
_DATA_SHEET = "Data1"
_HEADER_ROWS = 9
_AUSTRALIA_YOY_COL = 10


def _month_url(year: int, month: int) -> str:
    return _ABS_URL_TEMPLATE.format(month=month_name[month][:3].lower(), year=year)


def _fetch_workbook_bytes() -> bytes | None:
    today = date.today()
    year, month = today.year, today.month
    for _ in range(_MONTH_ROLLBACK_TRIES):
        try:
            r = requests.get(_month_url(year, month), timeout=15, headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code == 200:
                return r.content
        except Exception:
            pass
        month -= 1
        if month == 0:
            month, year = 12, year - 1
    return None


def fetch_australia_cpi_yoy() -> tuple[float, date] | None:
    """Returns (headline YoY % change, reference month) for the latest available
    ABS release, or None if unreachable/unparseable."""
    content = _fetch_workbook_bytes()
    if content is None:
        return None
    try:
        import openpyxl

        wb = openpyxl.load_workbook(io.BytesIO(content), data_only=True)
        ws = wb[_DATA_SHEET]
        last_date, last_value = None, None
        for row in ws.iter_rows(min_row=_HEADER_ROWS + 1, values_only=True):
            if row[0] is None or row[_AUSTRALIA_YOY_COL] is None:
                continue
            last_date, last_value = row[0], row[_AUSTRALIA_YOY_COL]
        if last_date is None or last_value is None:
            return None
        return float(last_value), last_date.date()
    except Exception:
        return None
