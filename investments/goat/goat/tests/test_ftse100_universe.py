from __future__ import annotations

from datetime import datetime, timedelta, timezone

from goat import config, db, ftse100_universe

_FAKE_HTML = """
<table class="wikitable">
<tr><th>Company</th><th>Ticker</th><th>FTSE industry classification benchmark sector</th></tr>
<tr><td>3i</td><td>III</td><td>Financial services</td></tr>
<tr><td>Admiral Group</td><td>ADM</td><td>Insurance</td></tr>
<tr><td>Rio Tinto</td><td>RIO</td><td>Mining</td></tr>
</table>
"""


class _FakeResponse:
    def __init__(self, text: str, status_code: int = 200):
        self.text = text
        self.status_code = status_code


def test_fetch_ftse100_constituents_parses_table_and_normalizes_tickers(monkeypatch):
    monkeypatch.setattr("requests.get", lambda *a, **k: _FakeResponse(_FAKE_HTML))
    rows = ftse100_universe.fetch_ftse100_constituents()
    assert rows is not None
    tickers_out = {r["ticker"] for r in rows}
    assert "III" in tickers_out
    assert "RIO" in tickers_out
    row = next(r for r in rows if r["ticker"] == "ADM")
    assert row["company"] == "Admiral Group"
    assert row["icb_sector"] == "Insurance"


def test_fetch_ftse100_constituents_returns_none_on_missing_table(monkeypatch):
    monkeypatch.setattr("requests.get", lambda *a, **k: _FakeResponse("<html>no table</html>"))
    assert ftse100_universe.fetch_ftse100_constituents() is None


def test_fetch_ftse100_constituents_returns_none_on_bad_status(monkeypatch):
    monkeypatch.setattr("requests.get", lambda *a, **k: _FakeResponse(_FAKE_HTML, status_code=500))
    assert ftse100_universe.fetch_ftse100_constituents() is None


def test_fetch_ftse100_constituents_returns_none_on_network_error(monkeypatch):
    def _raise(*a, **k):
        raise Exception("network down")

    monkeypatch.setattr("requests.get", _raise)
    assert ftse100_universe.fetch_ftse100_constituents() is None


def test_get_or_refresh_scrapes_when_cache_missing(db_conn, monkeypatch):
    monkeypatch.setattr(ftse100_universe, "fetch_ftse100_constituents", lambda: [
        {"ticker": "III", "company": "3i", "icb_sector": "Financial services"},
    ])
    rows = ftse100_universe.get_or_refresh_ftse100_constituents(db_conn)
    assert [r["ticker"] for r in rows] == ["III"]


def test_get_or_refresh_uses_cache_when_fresh(db_conn, monkeypatch):
    db.replace_ftse100_constituents(db_conn, [
        {"ticker": "III", "company": "3i", "icb_sector": "Financial services"},
    ])

    def _fail_if_called():
        raise AssertionError("should not re-scrape when cache is fresh")

    monkeypatch.setattr(ftse100_universe, "fetch_ftse100_constituents", _fail_if_called)
    rows = ftse100_universe.get_or_refresh_ftse100_constituents(db_conn)
    assert [r["ticker"] for r in rows] == ["III"]


def test_get_or_refresh_rescrapes_when_stale(db_conn, monkeypatch):
    db.replace_ftse100_constituents(db_conn, [
        {"ticker": "III", "company": "3i", "icb_sector": "Financial services"},
    ])
    stale_time = (
        datetime.now(timezone.utc) - timedelta(days=config.GOAT_FTSE100_CACHE_TTL_DAYS + 1)
    ).isoformat()
    with db_conn:
        db_conn.execute("UPDATE goat_ftse100_constituents SET fetched_at = ?", (stale_time,))

    monkeypatch.setattr(ftse100_universe, "fetch_ftse100_constituents", lambda: [
        {"ticker": "RIO", "company": "Rio Tinto", "icb_sector": "Mining"},
    ])
    rows = ftse100_universe.get_or_refresh_ftse100_constituents(db_conn)
    assert [r["ticker"] for r in rows] == ["RIO"]


def test_get_or_refresh_falls_back_to_stale_cache_on_scrape_failure(db_conn, monkeypatch):
    db.replace_ftse100_constituents(db_conn, [
        {"ticker": "III", "company": "3i", "icb_sector": "Financial services"},
    ])
    stale_time = (
        datetime.now(timezone.utc) - timedelta(days=config.GOAT_FTSE100_CACHE_TTL_DAYS + 1)
    ).isoformat()
    with db_conn:
        db_conn.execute("UPDATE goat_ftse100_constituents SET fetched_at = ?", (stale_time,))

    monkeypatch.setattr(ftse100_universe, "fetch_ftse100_constituents", lambda: None)
    rows = ftse100_universe.get_or_refresh_ftse100_constituents(db_conn)
    assert [r["ticker"] for r in rows] == ["III"]  # stale cache still returned


def test_get_or_refresh_returns_empty_list_when_no_cache_and_scrape_fails(db_conn, monkeypatch):
    monkeypatch.setattr(ftse100_universe, "fetch_ftse100_constituents", lambda: None)
    rows = ftse100_universe.get_or_refresh_ftse100_constituents(db_conn)
    assert rows == []
