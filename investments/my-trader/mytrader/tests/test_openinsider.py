from __future__ import annotations

from mytrader import openinsider

_FAKE_HTML = """
<table class="tinytable">
<tr>
<th>X</th><th>Filing Date</th><th>Trade Date</th><th>Ticker</th><th>Company Name</th>
<th>Insider Name</th><th>Title</th><th>Trade Type</th><th>Price</th><th>Qty</th>
<th>Owned</th><th>ΔOwn</th><th>Value</th>
</tr>
<tr>
<td></td><td>2026-08-15</td><td>2026-08-14</td><td>AAPL</td><td>Apple Inc.</td>
<td>Jane Doe</td><td>CFO</td><td>P - Purchase</td><td>$150.00</td><td>1,000</td>
<td>10,000</td><td>+10%</td><td>$150,000</td>
</tr>
<tr>
<td></td><td>2026-08-15</td><td>2026-08-14</td><td>BRK.B</td><td>Berkshire Hathaway</td>
<td>John Smith</td><td>Director</td><td>S - Sale</td><td>$400.00</td><td>5,000</td>
<td>50,000</td><td>-9%</td><td>$2,000,000</td>
</tr>
</table>
"""


class _FakeResponse:
    def __init__(self, text: str, status_code: int = 200):
        self.text = text
        self.status_code = status_code


def test_fetch_discovery_purchases_parses_table_and_filters_purchase_code(monkeypatch):
    monkeypatch.setattr("requests.get", lambda *a, **k: _FakeResponse(_FAKE_HTML))
    rows = openinsider.fetch_discovery_purchases()
    assert rows is not None
    assert len(rows) == 1
    assert rows[0]["ticker"] == "AAPL"
    assert rows[0]["trade_type_code"] == "P"
    assert rows[0]["value"] == 150_000.0
    assert rows[0]["pct_owned_change"] == 10.0


def test_fetch_discovery_sales_parses_table_and_filters_sale_code(monkeypatch):
    monkeypatch.setattr("requests.get", lambda *a, **k: _FakeResponse(_FAKE_HTML))
    rows = openinsider.fetch_discovery_sales()
    assert rows is not None
    assert len(rows) == 1
    assert rows[0]["ticker"] == "BRK-B"
    assert rows[0]["trade_type_code"] == "S"
    assert rows[0]["value"] == 2_000_000.0


def test_fetch_discovery_sales_returns_none_on_missing_table(monkeypatch):
    monkeypatch.setattr("requests.get", lambda *a, **k: _FakeResponse("<html>no table</html>"))
    assert openinsider.fetch_discovery_sales() is None


def test_fetch_discovery_sales_returns_none_on_bad_status(monkeypatch):
    monkeypatch.setattr("requests.get", lambda *a, **k: _FakeResponse(_FAKE_HTML, status_code=500))
    assert openinsider.fetch_discovery_sales() is None


def test_fetch_discovery_sales_returns_none_on_network_error(monkeypatch):
    def _raise(*a, **k):
        raise Exception("network down")

    monkeypatch.setattr("requests.get", _raise)
    assert openinsider.fetch_discovery_sales() is None


def test_parse_table_reads_pct_owned_change_for_sale_row(monkeypatch):
    monkeypatch.setattr("requests.get", lambda *a, **k: _FakeResponse(_FAKE_HTML))
    rows = openinsider.fetch_screener_filings(["BRK-B"], "S", 100_000)
    assert rows[0]["pct_owned_change"] == -9.0


def test_parse_table_treats_new_position_as_none(monkeypatch):
    html = _FAKE_HTML.replace(">+10%<", ">New<")
    monkeypatch.setattr("requests.get", lambda *a, **k: _FakeResponse(html))
    rows = openinsider.fetch_discovery_purchases()
    assert rows[0]["pct_owned_change"] is None


def test_parse_table_treats_unparsable_pct_as_none(monkeypatch):
    html = _FAKE_HTML.replace(">+10%<", "><")
    monkeypatch.setattr("requests.get", lambda *a, **k: _FakeResponse(html))
    rows = openinsider.fetch_discovery_purchases()
    assert rows[0]["pct_owned_change"] is None


def test_fetch_discovery_purchases_returns_none_on_missing_table(monkeypatch):
    monkeypatch.setattr("requests.get", lambda *a, **k: _FakeResponse("<html>no table</html>"))
    assert openinsider.fetch_discovery_purchases() is None


def test_fetch_discovery_purchases_returns_none_on_bad_status(monkeypatch):
    monkeypatch.setattr("requests.get", lambda *a, **k: _FakeResponse(_FAKE_HTML, status_code=500))
    assert openinsider.fetch_discovery_purchases() is None


def test_fetch_discovery_purchases_returns_none_on_network_error(monkeypatch):
    def _raise(*a, **k):
        raise Exception("network down")

    monkeypatch.setattr("requests.get", _raise)
    assert openinsider.fetch_discovery_purchases() is None


def test_fetch_screener_filings_builds_correct_params(monkeypatch):
    captured = {}

    def _fake_get(url, headers=None, params=None, timeout=None):
        captured["params"] = params
        return _FakeResponse(_FAKE_HTML)

    monkeypatch.setattr("requests.get", _fake_get)
    openinsider.fetch_screener_filings(["AAPL", "MSFT"], "P", 25_000)
    assert captured["params"]["s"] == "AAPL MSFT"  # space-separated, not comma
    assert captured["params"]["vl"] == "25"  # thousands of dollars, not raw dollars
    assert captured["params"]["xp"] == "1"
    assert captured["params"]["xs"] == ""


def test_fetch_screener_filings_returns_empty_list_without_request_when_no_tickers(monkeypatch):
    calls = []
    monkeypatch.setattr("requests.get", lambda *a, **k: calls.append(1))
    result = openinsider.fetch_screener_filings([], "P", 25_000)
    assert result == []
    assert calls == []


def test_fetch_screener_filings_filters_to_requested_trade_type(monkeypatch):
    monkeypatch.setattr("requests.get", lambda *a, **k: _FakeResponse(_FAKE_HTML))
    rows = openinsider.fetch_screener_filings(["AAPL", "BRK-B"], "S", 100_000)
    assert len(rows) == 1
    assert rows[0]["ticker"] == "BRK-B"


def test_parse_table_normalizes_dotted_tickers(monkeypatch):
    monkeypatch.setattr("requests.get", lambda *a, **k: _FakeResponse(_FAKE_HTML))
    rows = openinsider.fetch_screener_filings(["BRK-B"], "S", 100_000)
    assert rows[0]["ticker"] == "BRK-B"


def test_build_dedup_key_is_stable_and_order_sensitive():
    row = {
        "ticker": "AAPL", "filing_date": "2026-08-15", "trade_date": "2026-08-14",
        "insider_name": "Jane Doe", "trade_type_code": "P", "value": 150000.0,
    }
    key1 = openinsider.build_dedup_key(row)
    key2 = openinsider.build_dedup_key(dict(row))
    assert key1 == key2

    changed = dict(row, value=200000.0)
    assert openinsider.build_dedup_key(changed) != key1
