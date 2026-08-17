from __future__ import annotations

from datetime import datetime, timedelta, timezone

from goat import config, db, sp500_universe

_FAKE_HTML = """
<table id="constituents">
<tr><th>Symbol</th><th>Security</th><th>GICS Sector</th></tr>
<tr><td>AAPL</td><td>Apple Inc.</td><td>Information Technology</td></tr>
<tr><td>BRK.B</td><td>Berkshire Hathaway</td><td>Financials</td></tr>
<tr><td>XOM</td><td>Exxon Mobil</td><td>Energy</td></tr>
</table>
"""


class _FakeResponse:
    def __init__(self, text: str, status_code: int = 200):
        self.text = text
        self.status_code = status_code


def test_fetch_sp500_constituents_parses_table_and_normalizes_dot_tickers(monkeypatch):
    monkeypatch.setattr("requests.get", lambda *a, **k: _FakeResponse(_FAKE_HTML))
    rows = sp500_universe.fetch_sp500_constituents()
    assert rows is not None
    tickers_out = {r["ticker"] for r in rows}
    assert "AAPL" in tickers_out
    assert "BRK-B" in tickers_out  # normalized from BRK.B
    assert "BRK.B" not in tickers_out
    row = next(r for r in rows if r["ticker"] == "XOM")
    assert row["gics_sector"] == "Energy"


def test_fetch_sp500_constituents_returns_none_on_missing_table(monkeypatch):
    monkeypatch.setattr("requests.get", lambda *a, **k: _FakeResponse("<html>no table</html>"))
    assert sp500_universe.fetch_sp500_constituents() is None


def test_fetch_sp500_constituents_returns_none_on_bad_status(monkeypatch):
    monkeypatch.setattr("requests.get", lambda *a, **k: _FakeResponse(_FAKE_HTML, status_code=500))
    assert sp500_universe.fetch_sp500_constituents() is None


def test_fetch_sp500_constituents_returns_none_on_network_error(monkeypatch):
    def _raise(*a, **k):
        raise Exception("network down")

    monkeypatch.setattr("requests.get", _raise)
    assert sp500_universe.fetch_sp500_constituents() is None


def test_get_or_refresh_scrapes_when_cache_missing(db_conn, monkeypatch):
    monkeypatch.setattr(sp500_universe, "fetch_sp500_constituents", lambda: [
        {"ticker": "AAPL", "security": "Apple Inc.", "gics_sector": "Information Technology"},
    ])
    rows = sp500_universe.get_or_refresh_sp500_constituents(db_conn)
    assert [r["ticker"] for r in rows] == ["AAPL"]


def test_get_or_refresh_uses_cache_when_fresh(db_conn, monkeypatch):
    db.replace_sp500_constituents(db_conn, [
        {"ticker": "AAPL", "security": "Apple Inc.", "gics_sector": "Information Technology"},
    ])

    def _fail_if_called():
        raise AssertionError("should not re-scrape when cache is fresh")

    monkeypatch.setattr(sp500_universe, "fetch_sp500_constituents", _fail_if_called)
    rows = sp500_universe.get_or_refresh_sp500_constituents(db_conn)
    assert [r["ticker"] for r in rows] == ["AAPL"]


def test_get_or_refresh_rescrapes_when_stale(db_conn, monkeypatch):
    db.replace_sp500_constituents(db_conn, [
        {"ticker": "AAPL", "security": "Apple Inc.", "gics_sector": "Information Technology"},
    ])
    stale_time = (
        datetime.now(timezone.utc) - timedelta(days=config.GOAT_SP500_CACHE_TTL_DAYS + 1)
    ).isoformat()
    with db_conn:
        db_conn.execute("UPDATE goat_sp500_constituents SET fetched_at = ?", (stale_time,))

    monkeypatch.setattr(sp500_universe, "fetch_sp500_constituents", lambda: [
        {"ticker": "MSFT", "security": "Microsoft", "gics_sector": "Information Technology"},
    ])
    rows = sp500_universe.get_or_refresh_sp500_constituents(db_conn)
    assert [r["ticker"] for r in rows] == ["MSFT"]


def test_get_or_refresh_falls_back_to_stale_cache_on_scrape_failure(db_conn, monkeypatch):
    db.replace_sp500_constituents(db_conn, [
        {"ticker": "AAPL", "security": "Apple Inc.", "gics_sector": "Information Technology"},
    ])
    stale_time = (
        datetime.now(timezone.utc) - timedelta(days=config.GOAT_SP500_CACHE_TTL_DAYS + 1)
    ).isoformat()
    with db_conn:
        db_conn.execute("UPDATE goat_sp500_constituents SET fetched_at = ?", (stale_time,))

    monkeypatch.setattr(sp500_universe, "fetch_sp500_constituents", lambda: None)
    rows = sp500_universe.get_or_refresh_sp500_constituents(db_conn)
    assert [r["ticker"] for r in rows] == ["AAPL"]  # stale cache still returned


def test_get_or_refresh_returns_empty_list_when_no_cache_and_scrape_fails(db_conn, monkeypatch):
    monkeypatch.setattr(sp500_universe, "fetch_sp500_constituents", lambda: None)
    rows = sp500_universe.get_or_refresh_sp500_constituents(db_conn)
    assert rows == []
