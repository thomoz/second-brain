from __future__ import annotations

from itertools import product

import pytest

from mytrader import finviz_screener

# conftest.py's autouse _no_real_finviz_fetch replaces fetch_screener_universe with a
# None-returning stub -- save the real one at import time and restore it for this
# file's pagination tests. Same idiom as test_market_data.py:16.
_REAL_FETCH_UNIVERSE = finviz_screener.fetch_screener_universe


@pytest.fixture(autouse=True)
def _restore_real_fetch_universe(monkeypatch):
    monkeypatch.setattr(finviz_screener, "fetch_screener_universe", _REAL_FETCH_UNIVERSE)

# Alpha-only synthetic tickers whose first two chars differ, so _descramble_ticker
# leaves them untouched and they stay distinct for pagination-count assertions.
_SYNTH = [f"{a}{b}{c}" for a, b, c in product("ABCDEFGHJK", repeat=3) if a != b]

# Mirrors the live 2026-08-26 Finviz Overview (v=111) shape: a nav table with an
# unrelated header, then the results table (leading "No." column, "Change %" not
# "Change", tickers watermarked by a doubled first character). Three data rows plus
# the repeated <th> row Finviz emits.
_FAKE_PAGE_HTML = """
<table><tr><th>Overview</th><th>Valuation</th></tr><tr><td>nav</td><td>row</td></tr></table>
<table>
<tr><th>No.</th><th>Ticker</th><th>Company</th><th>Sector</th><th>Industry</th>
<th>Country</th><th>Market Cap</th><th>P/E</th><th>Price</th><th>Change %</th><th>Volume</th></tr>
<tr><td>1</td><td>AAAL</td><td>American Airlines Group Inc</td><td>Industrials</td>
<td>Airlines</td><td>USA</td><td>9.23B</td><td>-</td><td>13.95</td><td>2.35%</td><td>66,763,117</td></tr>
<tr><td>2</td><td>BBRK.B</td><td>Berkshire Hathaway</td><td>Financial</td>
<td>Insurance</td><td>USA</td><td>900.00B</td><td>10.0</td><td>400.00</td><td>0.10%</td><td>3,000,000</td></tr>
<tr><td>3</td><td>KKO</td><td>Coca-Cola Co</td><td>Consumer Defensive</td>
<td>Beverages</td><td>USA</td><td>250.00B</td><td>25.0</td><td>60.00</td><td>-0.20%</td><td>12,000,000</td></tr>
</table>
"""

_NO_DATA_HTML = """
<html><body>
<div>#0 / 0 Total</div>
<table>
<tr><th>No.</th><th>Ticker</th><th>Company</th><th>Sector</th><th>Industry</th>
<th>Country</th><th>Market Cap</th><th>P/E</th><th>Price</th><th>Change %</th><th>Volume</th></tr>
</table>
</body></html>
"""


class _FakeResponse:
    def __init__(self, text: str, status_code: int = 200):
        self.text = text
        self.status_code = status_code


# --- _parse_page --------------------------------------------------------------

def test_parse_page_extracts_ticker_sector_marketcap(monkeypatch):
    rows = finviz_screener._parse_page(_FAKE_PAGE_HTML)
    assert rows is not None
    by_company = {r["company"]: r for r in rows}
    aal = by_company["American Airlines Group Inc"]
    assert aal["ticker"] == "AAL"  # watermark (AAAL) removed
    assert aal["sector"] == "Industrials"
    assert aal["market_cap_text"] == "9.23B"
    assert aal["price_text"] == "13.95"


def test_parse_page_descrambles_and_normalizes_dotted_ticker():
    rows = finviz_screener._parse_page(_FAKE_PAGE_HTML)
    brk = next(r for r in rows if r["company"] == "Berkshire Hathaway")
    assert brk["ticker"] == "BRK-B"  # BBRK.B -> BRK.B -> BRK-B


def test_parse_page_returns_empty_list_when_no_data_rows_but_page_is_valid():
    assert finviz_screener._parse_page(_NO_DATA_HTML) == []


def test_parse_page_returns_none_when_not_a_screener_page():
    assert finviz_screener._parse_page("<html><body>nope</body></html>") is None


def test_parse_page_ignores_the_mega_row_wrapper_table():
    # The live page nests the results table inside a wrapper table that also holds
    # one giant concatenated <tr>. Simulate: wrap the results table and prepend a
    # mega-row with far more <td> than the header.
    mega = "<tr>" + "".join(f"<td>x{i}</td>" for i in range(50)) + "</tr>"
    wrapped = _FAKE_PAGE_HTML.replace(
        "<table>\n<tr><th>No.</th>",
        f"<table>{mega}<table>\n<tr><th>No.</th>",
    ) + "</table>"
    rows = finviz_screener._parse_page(wrapped)
    assert {r["ticker"] for r in rows} == {"AAL", "BRK-B", "KO"}


# --- fetch_screener_universe -------------------------------------------------

def _page_with(tickers: list[str]) -> str:
    body = "".join(
        f"<tr><td>{i}</td><td>{t}</td><td>Co {t}</td><td>Tech</td><td>SW</td>"
        f"<td>USA</td><td>1.00B</td><td>-</td><td>5.00</td><td>0%</td><td>100</td></tr>"
        for i, t in enumerate(tickers, 1)
    )
    return (
        "<table><tr><th>No.</th><th>Ticker</th><th>Company</th><th>Sector</th>"
        "<th>Industry</th><th>Country</th><th>Market Cap</th><th>P/E</th><th>Price</th>"
        f"<th>Change %</th><th>Volume</th></tr>{body}</table>"
    )


def test_fetch_screener_universe_paginates_until_short_page(monkeypatch):
    full1 = _SYNTH[0:20]
    full2 = _SYNTH[20:40]
    short3 = _SYNTH[40:45]
    requested: list[int] = []

    def fake_fetch(offset: int) -> str:
        requested.append(offset)
        return {1: _page_with(full1), 21: _page_with(full2), 41: _page_with(short3)}[offset]

    monkeypatch.setattr(finviz_screener, "_fetch_page", fake_fetch)
    monkeypatch.setattr(finviz_screener.time, "sleep", lambda *_: None)
    rows = finviz_screener.fetch_screener_universe()
    assert len(rows) == 45
    assert 61 not in requested


def test_fetch_screener_universe_returns_none_when_first_page_fails(monkeypatch):
    monkeypatch.setattr(finviz_screener, "_fetch_page", lambda offset: None)
    monkeypatch.setattr(finviz_screener.time, "sleep", lambda *_: None)
    assert finviz_screener.fetch_screener_universe() is None


def test_fetch_screener_universe_stops_early_and_returns_partial_on_later_failure(monkeypatch):
    full1 = _SYNTH[0:20]

    def fake_fetch(offset: int):
        return _page_with(full1) if offset == 1 else None

    monkeypatch.setattr(finviz_screener, "_fetch_page", fake_fetch)
    monkeypatch.setattr(finviz_screener.time, "sleep", lambda *_: None)
    rows = finviz_screener.fetch_screener_universe()
    assert rows is not None and len(rows) == 20


def test_fetch_screener_universe_dedupes_across_pages(monkeypatch):
    page = _page_with(_SYNTH[0:20])

    def fake_fetch(offset: int):
        return page  # every page identical -> second page is all duplicates

    monkeypatch.setattr(finviz_screener, "_fetch_page", fake_fetch)
    monkeypatch.setattr(finviz_screener.time, "sleep", lambda *_: None)
    rows = finviz_screener.fetch_screener_universe()
    assert len(rows) == 20  # the repeated page breaks the loop, no duplicates


def test_fetch_screener_universe_sleeps_between_pages_not_after_last(monkeypatch):
    full1 = _SYNTH[0:20]
    short2 = _SYNTH[20:23]
    calls = {"n": 0}

    def fake_fetch(offset: int):
        return {1: _page_with(full1), 21: _page_with(short2)}[offset]

    monkeypatch.setattr(finviz_screener, "_fetch_page", fake_fetch)
    monkeypatch.setattr(finviz_screener.time, "sleep", lambda *_: calls.__setitem__("n", calls["n"] + 1))
    finviz_screener.fetch_screener_universe()
    assert calls["n"] == 1  # slept once (after page 1), not after the short page 2


def test_descramble_ticker_edge_cases():
    assert finviz_screener._descramble_ticker("AAAPL") == "AAPL"
    assert finviz_screener._descramble_ticker("FF") == "F"
    assert finviz_screener._descramble_ticker("AAA") == "AA"
    assert finviz_screener._descramble_ticker("BBRK-B") == "BRK-B"
    assert finviz_screener._descramble_ticker("XOM") == "XOM"  # not doubled -> untouched


def test_fetch_page_returns_none_on_bad_status(monkeypatch):
    monkeypatch.setattr("requests.get", lambda *a, **k: _FakeResponse("x", status_code=503))
    assert finviz_screener._fetch_page(1) is None


def test_fetch_page_returns_none_on_network_error(monkeypatch):
    def _raise(*a, **k):
        raise Exception("boom")

    monkeypatch.setattr("requests.get", _raise)
    assert finviz_screener._fetch_page(1) is None
