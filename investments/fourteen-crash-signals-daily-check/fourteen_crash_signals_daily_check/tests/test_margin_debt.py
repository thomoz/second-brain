from __future__ import annotations

import io

import openpyxl

from fourteen_crash_signals_daily_check import config, margin_debt


def _build_fake_workbook_bytes(rows: list[tuple]) -> bytes:
    """Mirrors the real FINRA 'Customer Margin Balances' sheet shape confirmed
    live 2026-08-18: one header row, column A = 'YYYY-MM' string, column B =
    debit balance in $ millions, rows in DESCENDING date order (newest first)."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Customer Margin Balances"
    ws.append(["Year-Month", "Debit Balances in Customers' Securities Margin Accounts",
                "Free Credit Balances in Customers' Cash Accounts",
                "Free Credit Balances in Customers' Securities Margin Accounts"])
    for row in rows:
        ws.append(list(row))
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _descending_months(latest_year: int, latest_month: int, values: list[float]) -> list[tuple]:
    """values[0] is the latest month, walking backward one month per entry."""
    rows = []
    y, m = latest_year, latest_month
    for v in values:
        rows.append((f"{y:04d}-{m:02d}", v, None, None))
        m -= 1
        if m == 0:
            m, y = 12, y - 1
    return rows


def test_fetch_margin_debt_series_parses_and_sorts_ascending(monkeypatch):
    rows = _descending_months(2026, 7, [1_417_225.0, 1_502_072.0, 1_415_557.0])
    fake_bytes = _build_fake_workbook_bytes(rows)
    monkeypatch.setattr(margin_debt, "_fetch_workbook_bytes", lambda: fake_bytes)

    series = margin_debt.fetch_margin_debt_series()
    assert series is not None
    assert [m.isoformat() for m, _ in series] == ["2026-05-01", "2026-06-01", "2026-07-01"]
    assert series[-1] == (series[-1][0], 1_417_225.0)


def test_fetch_margin_debt_series_returns_none_on_fetch_failure(monkeypatch):
    monkeypatch.setattr(margin_debt, "_fetch_workbook_bytes", lambda: None)
    assert margin_debt.fetch_margin_debt_series() is None


def test_check_margin_debt_growth_unknown_when_fetch_fails(monkeypatch):
    monkeypatch.setattr(margin_debt, "fetch_margin_debt_series", lambda: None)
    result = margin_debt.check_margin_debt_growth()
    assert result.verdict == "unknown"


def test_check_margin_debt_growth_unknown_when_too_short_for_yoy(monkeypatch):
    rows = _descending_months(2026, 7, [1_400_000.0])
    fake_bytes = _build_fake_workbook_bytes(rows)
    monkeypatch.setattr(margin_debt, "_fetch_workbook_bytes", lambda: fake_bytes)
    result = margin_debt.check_margin_debt_growth()
    assert result.verdict == "unknown"


def test_check_margin_debt_growth_computes_yoy_and_ok_below_threshold(monkeypatch):
    # 13 months back-to-back, latest = 1,100,000 vs a year ago 1,000,000 -> +10% YoY
    values = [1_100_000.0] + [1_000_000.0] * 12
    rows = _descending_months(2026, 7, values)
    fake_bytes = _build_fake_workbook_bytes(rows)
    monkeypatch.setattr(margin_debt, "_fetch_workbook_bytes", lambda: fake_bytes)
    result = margin_debt.check_margin_debt_growth()
    assert result.verdict == "ok"
    assert round(result.data["yoy_pct"], 1) == 10.0


def test_check_margin_debt_growth_flags_above_threshold(monkeypatch):
    latest = 1_000_000.0 * (1 + config.SIGNALS_MARGIN_DEBT_YOY_FLAG_PCT / 100 + 0.05)
    values = [latest] + [1_000_000.0] * 12
    rows = _descending_months(2026, 7, values)
    fake_bytes = _build_fake_workbook_bytes(rows)
    monkeypatch.setattr(margin_debt, "_fetch_workbook_bytes", lambda: fake_bytes)
    result = margin_debt.check_margin_debt_growth()
    assert result.verdict == "flag"
