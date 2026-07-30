from __future__ import annotations

import io
from datetime import date, datetime

import openpyxl

from mytrader import abs_cpi


def _build_fake_workbook_bytes(rows: list[tuple]) -> bytes:
    """Build a minimal xlsx matching the real ABS Data1 sheet shape: 9 metadata
    header rows (content irrelevant to parsing), then one data row per month with
    column 0 = date, column 10 = Australia YoY % change."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Data1"
    for _ in range(9):
        ws.append([None] * 11)
    for row in rows:
        ws.append(list(row))
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_month_url_formats_correctly():
    assert abs_cpi._month_url(2026, 6) == (
        "https://www.abs.gov.au/statistics/economy/price-indexes-and-inflation/"
        "consumer-price-index-australia/jun-2026/640101.xlsx"
    )
    assert abs_cpi._month_url(2026, 1) == (
        "https://www.abs.gov.au/statistics/economy/price-indexes-and-inflation/"
        "consumer-price-index-australia/jan-2026/640101.xlsx"
    )


def test_fetch_workbook_bytes_returns_current_month_on_success(monkeypatch):
    calls = []

    class _Resp:
        status_code = 200
        content = b"fake-bytes"

    def _fake_get(url, timeout, headers):
        calls.append(url)
        return _Resp()

    monkeypatch.setattr(abs_cpi.requests, "get", _fake_get)
    result = abs_cpi._fetch_workbook_bytes()
    assert result == b"fake-bytes"
    assert len(calls) == 1


def test_fetch_workbook_bytes_falls_back_to_previous_month(monkeypatch):
    calls = []

    class _Resp:
        def __init__(self, status_code):
            self.status_code = status_code
            self.content = b"fake-bytes"

    def _fake_get(url, timeout, headers):
        calls.append(url)
        # First call (current month) 404s, second call (prior month) succeeds
        return _Resp(404) if len(calls) == 1 else _Resp(200)

    monkeypatch.setattr(abs_cpi.requests, "get", _fake_get)
    result = abs_cpi._fetch_workbook_bytes()
    assert result == b"fake-bytes"
    assert len(calls) == 2


def test_fetch_workbook_bytes_returns_none_after_exhausting_tries(monkeypatch):
    class _Resp:
        status_code = 404
        content = b""

    monkeypatch.setattr(abs_cpi.requests, "get", lambda url, timeout, headers: _Resp())
    result = abs_cpi._fetch_workbook_bytes()
    assert result is None
    assert abs_cpi._MONTH_ROLLBACK_TRIES > 0


def test_fetch_workbook_bytes_returns_none_on_request_exception(monkeypatch):
    def _raise(url, timeout, headers):
        raise ConnectionError("network down")

    monkeypatch.setattr(abs_cpi.requests, "get", _raise)
    assert abs_cpi._fetch_workbook_bytes() is None


def test_fetch_australia_cpi_yoy_parses_real_workbook_shape(monkeypatch):
    rows = [
        (datetime(2026, 5, 1),) + (None,) * 9 + (4.0,) + (None,) * 16,
        (datetime(2026, 6, 1),) + (None,) * 9 + (3.8,) + (None,) * 16,
    ]
    fake_bytes = _build_fake_workbook_bytes(rows)
    monkeypatch.setattr(abs_cpi, "_fetch_workbook_bytes", lambda: fake_bytes)

    result = abs_cpi.fetch_australia_cpi_yoy()
    assert result == (3.8, date(2026, 6, 1))


def test_fetch_australia_cpi_yoy_returns_none_when_fetch_fails(monkeypatch):
    monkeypatch.setattr(abs_cpi, "_fetch_workbook_bytes", lambda: None)
    assert abs_cpi.fetch_australia_cpi_yoy() is None


def test_fetch_australia_cpi_yoy_returns_none_on_unparseable_bytes(monkeypatch):
    monkeypatch.setattr(abs_cpi, "_fetch_workbook_bytes", lambda: b"not a real xlsx")
    assert abs_cpi.fetch_australia_cpi_yoy() is None
