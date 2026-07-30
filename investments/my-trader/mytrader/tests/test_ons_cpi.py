from __future__ import annotations

from datetime import date

from mytrader import ons_cpi

_FAKE_CSV = '''"Title","CPI ANNUAL RATE 00: ALL ITEMS 2015=100"
"CDID","D7G7"
"Source dataset ID","MM23"
"PreUnit",""
"Unit","%"
"Release date","22-07-2026"
"Next release","19 August 2026"
"Important notes",
"1989","5.2"
"1990","7.0"
"2026 APR","2.8"
"2026 MAY","2.8"
"2026 JUN","2.6"
'''


class _Resp:
    def __init__(self, status_code, text):
        self.status_code = status_code
        self.text = text


def test_fetch_uk_cpi_yoy_returns_latest_monthly_row(monkeypatch):
    monkeypatch.setattr(ons_cpi.requests, "get", lambda url, timeout, headers: _Resp(200, _FAKE_CSV))
    result = ons_cpi.fetch_uk_cpi_yoy()
    assert result == (2.6, date(2026, 6, 1))


def test_fetch_uk_cpi_yoy_ignores_annual_rows(monkeypatch):
    # Ensure the 1989/1990 annual-only rows (no month) don't get picked as "latest"
    csv_annual_only = '"Title","x"\n"1989","5.2"\n"1990","7.0"\n'
    monkeypatch.setattr(ons_cpi.requests, "get", lambda url, timeout, headers: _Resp(200, csv_annual_only))
    assert ons_cpi.fetch_uk_cpi_yoy() is None


def test_fetch_uk_cpi_yoy_returns_none_on_non_200(monkeypatch):
    monkeypatch.setattr(ons_cpi.requests, "get", lambda url, timeout, headers: _Resp(404, ""))
    assert ons_cpi.fetch_uk_cpi_yoy() is None


def test_fetch_uk_cpi_yoy_returns_none_on_request_exception(monkeypatch):
    def _raise(url, timeout, headers):
        raise ConnectionError("network down")

    monkeypatch.setattr(ons_cpi.requests, "get", _raise)
    assert ons_cpi.fetch_uk_cpi_yoy() is None
