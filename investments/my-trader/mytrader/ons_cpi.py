"""UK CPI (annual rate, all items), read directly from the ONS's stable CSV
generator endpoint. Unlike ABS's file (mytrader/abs_cpi.py, which embeds the release
month in its URL), this URL never changes -- it always serves the latest data
appended to the same time series (series D7G7, dataset MM23), so no month-rollback
logic is needed.

The file contains both annual summary rows (e.g. "1989","5.2") and monthly rows
(e.g. "2026 JUN","2.6") in one series -- this module reads the latest monthly row,
since that's the freshest available reading.
"""

from __future__ import annotations

import csv
import io
from datetime import date

import requests

_ONS_CSV_URL = (
    "https://www.ons.gov.uk/generator?format=csv&uri="
    "/economy/inflationandpriceindices/timeseries/d7g7/mm23"
)

_MONTH_ABBR = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}


def fetch_uk_cpi_yoy() -> tuple[float, date] | None:
    """Returns (headline YoY % change, reference month) for the latest monthly row,
    or None if unreachable/unparseable."""
    try:
        r = requests.get(_ONS_CSV_URL, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code != 200:
            return None
        reader = csv.reader(io.StringIO(r.text))
        last_date, last_value = None, None
        for row in reader:
            if len(row) < 2:
                continue
            parts = row[0].strip().split()
            if len(parts) != 2 or parts[1] not in _MONTH_ABBR:
                continue
            try:
                last_date = date(int(parts[0]), _MONTH_ABBR[parts[1]], 1)
                last_value = float(row[1].strip())
            except ValueError:
                continue
        if last_date is None or last_value is None:
            return None
        return last_value, last_date
    except Exception:
        return None
