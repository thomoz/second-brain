"""Marker 5 -- margin debt YoY growth, from FINRA's own published spreadsheet
(no official free API). Sheet layout confirmed live 2026-08-18 against the real
file: single sheet "Customer Margin Balances", header row 1, one data row per
month from column B ("Debit Balances in Customers' Securities Margin Accounts",
$ millions) -- data rows are in DESCENDING date order (newest first), and column
A is a "YYYY-MM" string, not a date/datetime cell."""

from __future__ import annotations

import io
from datetime import date, timedelta

import requests
from mytrader.checks import CheckResult

from . import config

_PRIOR_YEAR_TOLERANCE_DAYS = 20  # monthly buckets stored as the 1st of each month --
    # 365 days back from the latest month can land up to ~2 weeks either side of the
    # "same calendar month a year ago" row depending on month lengths, so an exact-day
    # match is too strict; this tolerance is generous enough to always find the right
    # month while still rejecting a search that lands on the wrong year entirely.


def _fetch_workbook_bytes() -> bytes | None:
    try:
        r = requests.get(config.SIGNALS_MARGIN_DEBT_URL, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code == 200:
            return r.content
    except Exception:
        pass
    return None


def _parse_year_month(text: object) -> date | None:
    if not isinstance(text, str):
        return None
    try:
        year, month = text.strip().split("-")
        return date(int(year), int(month), 1)
    except (ValueError, AttributeError):
        return None


def fetch_margin_debt_series() -> list[tuple[date, float]] | None:
    """Returns (month, debit-balance-$millions) ascending by date, or None on
    any failure. The source file itself is descending (newest first) -- this
    function re-sorts so every caller can rely on ascending order."""
    content = _fetch_workbook_bytes()
    if content is None:
        return None
    try:
        import openpyxl

        wb = openpyxl.load_workbook(io.BytesIO(content), data_only=True)
        ws = wb.active
        rows: list[tuple[date, float]] = []
        for row in ws.iter_rows(min_row=2, values_only=True):
            if row[0] is None or row[1] is None:
                continue
            month = _parse_year_month(row[0])
            if month is None:
                continue
            rows.append((month, float(row[1])))
        rows.sort(key=lambda r: r[0])
        return rows or None
    except Exception:
        return None


def _find_prior_year_row(
    series: list[tuple[date, float]], latest_month: date
) -> tuple[date, float] | None:
    """Closest row to exactly 365 days before latest_month, within
    _PRIOR_YEAR_TOLERANCE_DAYS -- tolerant of monthly-bucket drift rather than
    trusting a fixed positional offset (a gap in the published history would
    silently misalign a fixed series[-13] index)."""
    target = latest_month - timedelta(days=365)
    best: tuple[date, float] | None = None
    best_diff: int | None = None
    for month, value in series[:-1]:
        diff = abs((month - target).days)
        if best_diff is None or diff < best_diff:
            best_diff, best = diff, (month, value)
    if best is None or best_diff is None or best_diff > _PRIOR_YEAR_TOLERANCE_DAYS:
        return None
    return best


def check_margin_debt_growth() -> CheckResult:
    series = fetch_margin_debt_series()
    if not series or len(series) < 2:
        return CheckResult(
            name="margin_debt_growth", verdict="unknown",
            detail="FINRA margin debt data unavailable or too short for a YoY comparison",
        )
    latest_month, latest_value = series[-1]
    prior = _find_prior_year_row(series, latest_month)
    if prior is None:
        return CheckResult(
            name="margin_debt_growth", verdict="unknown",
            detail=f"No FINRA margin debt row found close enough to one year before {latest_month.isoformat()}",
        )
    prior_month, prior_value = prior
    if prior_value == 0:
        return CheckResult(name="margin_debt_growth", verdict="unknown", detail="prior-year value is zero, cannot compute YoY")

    yoy_pct = (latest_value - prior_value) / prior_value * 100
    detail_base = (
        f"Margin debt ${latest_value / 1e6:.2f}T as of {latest_month.isoformat()}, "
        f"{yoy_pct:+.1f}% YoY vs {prior_month.isoformat()}"
    )
    if yoy_pct >= config.SIGNALS_MARGIN_DEBT_YOY_FLAG_PCT:
        return CheckResult(
            name="margin_debt_growth", verdict="flag",
            detail=f"{detail_base} -- growth rate historically seen at cycle peaks (2000, 2007, 2021)",
            data={"value": latest_value, "yoy_pct": yoy_pct, "as_of": latest_month.isoformat()},
        )
    return CheckResult(
        name="margin_debt_growth", verdict="ok", detail=detail_base,
        data={"value": latest_value, "yoy_pct": yoy_pct, "as_of": latest_month.isoformat()},
    )
