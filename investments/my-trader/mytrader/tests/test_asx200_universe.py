from __future__ import annotations

import pytest

from mytrader import asx200_universe

# conftest.py's autouse _no_real_asx200_fetch replaces fetch_asx200_constituents with
# a None-returning stub -- save the real one at import time (before any fixture runs)
# and restore it for this file's direct tests. Same idiom as test_market_data.py:16.
_REAL_FETCH = asx200_universe.fetch_asx200_constituents


@pytest.fixture(autouse=True)
def _restore_real_fetch(monkeypatch):
    monkeypatch.setattr(asx200_universe, "fetch_asx200_constituents", _REAL_FETCH)

# Mirrors the live 2026-08-26 S&P/ASX 200 "Constituent companies" wikitable:
# headers Code / Company / Sector / Market Capitalisation (A$) / Headquarters,
# all-<td> data rows, codes that can be numeric ("360") or alphanumeric ("4DX").
_FAKE_WIKI_HTML = """
<table class="wikitable">
<tr><th>Code</th><th>Company</th><th>Sector</th><th>Market Capitalisation (A$)</th><th>Headquarters</th></tr>
<tr><td>360</td><td>Life360</td><td>Information Technology</td><td>3,420,074,734</td><td>San Mateo, United States</td></tr>
<tr><td>WES[1]</td><td>Wesfarmers</td><td>Consumer Discretionary</td><td>90,000,000,000</td><td>Perth</td></tr>
<tr><td>CBA</td><td>Commonwealth Bank</td><td>Financials</td><td>200,000,000,000</td><td>Sydney</td></tr>
</table>
"""

_ALT_HEADER_HTML = _FAKE_WIKI_HTML.replace("<th>Code</th>", "<th>Symbol</th>")


class _FakeResponse:
    def __init__(self, text: str, status_code: int = 200):
        self.text = text
        self.status_code = status_code


def test_fetch_parses_code_company_sector(monkeypatch):
    monkeypatch.setattr("requests.get", lambda *a, **k: _FakeResponse(_FAKE_WIKI_HTML))
    rows = asx200_universe.fetch_asx200_constituents()
    assert rows is not None
    by_ticker = {r["ticker"]: r for r in rows}
    assert by_ticker["360"]["company"] == "Life360"
    assert by_ticker["360"]["sector"] == "Information Technology"
    assert by_ticker["CBA"]["sector"] == "Financials"


def test_fetch_preserves_numeric_and_alphanumeric_codes(monkeypatch):
    monkeypatch.setattr("requests.get", lambda *a, **k: _FakeResponse(_FAKE_WIKI_HTML))
    rows = asx200_universe.fetch_asx200_constituents()
    assert "360" in {r["ticker"] for r in rows}  # digits NOT stripped


def test_fetch_strips_reference_markers_from_code(monkeypatch):
    monkeypatch.setattr("requests.get", lambda *a, **k: _FakeResponse(_FAKE_WIKI_HTML))
    rows = asx200_universe.fetch_asx200_constituents()
    assert "WES" in {r["ticker"] for r in rows}  # "WES[1]" -> "WES"


def test_fetch_handles_alternate_header_label(monkeypatch):
    monkeypatch.setattr("requests.get", lambda *a, **k: _FakeResponse(_ALT_HEADER_HTML))
    rows = asx200_universe.fetch_asx200_constituents()
    assert rows is not None and "360" in {r["ticker"] for r in rows}


def test_fetch_returns_none_on_missing_table(monkeypatch):
    monkeypatch.setattr("requests.get", lambda *a, **k: _FakeResponse("<html>no table</html>"))
    assert asx200_universe.fetch_asx200_constituents() is None


def test_fetch_returns_none_on_bad_status(monkeypatch):
    monkeypatch.setattr("requests.get", lambda *a, **k: _FakeResponse(_FAKE_WIKI_HTML, status_code=500))
    assert asx200_universe.fetch_asx200_constituents() is None


def test_fetch_returns_none_on_network_error(monkeypatch):
    def _raise(*a, **k):
        raise Exception("network down")

    monkeypatch.setattr("requests.get", _raise)
    assert asx200_universe.fetch_asx200_constituents() is None
