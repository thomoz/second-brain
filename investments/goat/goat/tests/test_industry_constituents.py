from __future__ import annotations

from goat import config as goat_config, industry_constituents


_FAKE_SLUGS = {"Semiconductors": "ind_semiconductors"}
_FAKE_ASX = {"NST": "Gold", "EVN": "Gold", "CBA": "Banks - Diversified"}


def _patch_universe(monkeypatch):
    monkeypatch.setattr(goat_config, "GOAT_FINVIZ_INDUSTRY_SLUGS", _FAKE_SLUGS)
    monkeypatch.setattr(goat_config, "GOAT_ASX_INDUSTRY_CONSTITUENTS", _FAKE_ASX)


def test_fetch_industry_constituents_us_returns_none_for_unmapped_slug(monkeypatch):
    _patch_universe(monkeypatch)
    result = industry_constituents.fetch_industry_constituents_us("Not A Real Industry")
    assert result is None


def test_fetch_industry_constituents_us_calls_finviz_screener_with_slug_and_liquidity_filter(monkeypatch):
    _patch_universe(monkeypatch)
    captured = {}

    def _fake_fetch_screener_universe(filters=None, sort="pricecash"):
        captured["filters"] = filters
        return [{"ticker": "NVDA", "company": "Nvidia Corp"}]

    monkeypatch.setattr(
        "goat.industry_constituents.finviz_screener.fetch_screener_universe",
        _fake_fetch_screener_universe,
    )
    result = industry_constituents.fetch_industry_constituents_us("Semiconductors")
    assert captured["filters"] == "ind_semiconductors,sh_avgvol_o100,sh_price_o1"
    assert result == [{"ticker": "NVDA", "company": "Nvidia Corp", "market": "US"}]


def test_get_asx_industry_constituents_returns_curated_entries_for_known_industry(monkeypatch):
    _patch_universe(monkeypatch)
    result = industry_constituents.get_asx_industry_constituents("Gold")
    tickers_out = {r["ticker"] for r in result}
    assert tickers_out == {"NST.AX", "EVN.AX"}
    assert all(r["market"] == "ASX" for r in result)


def test_get_asx_industry_constituents_returns_empty_for_uncurated_industry(monkeypatch):
    _patch_universe(monkeypatch)
    result = industry_constituents.get_asx_industry_constituents("Airlines")
    assert result == []


def test_get_or_refresh_industry_constituents_combines_us_and_asx(db_conn, monkeypatch):
    _patch_universe(monkeypatch)
    monkeypatch.setattr(
        "goat.industry_constituents.finviz_screener.fetch_screener_universe",
        lambda filters=None, sort="pricecash": [{"ticker": "NVDA", "company": "Nvidia Corp"}],
    )
    result = industry_constituents.get_or_refresh_industry_constituents(db_conn, "Semiconductors")
    tickers_out = {r["ticker"] for r in result}
    assert "NVDA" in tickers_out  # US leg


def test_get_or_refresh_industry_constituents_combines_asx_leg_for_gold(db_conn, monkeypatch):
    _patch_universe(monkeypatch)
    monkeypatch.setattr(
        "goat.industry_constituents.finviz_screener.fetch_screener_universe",
        lambda filters=None, sort="pricecash": None,
    )
    result = industry_constituents.get_or_refresh_industry_constituents(db_conn, "Gold")
    tickers_out = {r["ticker"] for r in result}
    assert tickers_out == {"NST.AX", "EVN.AX"}  # US leg empty (no slug for "Gold" in fake map)


def test_get_or_refresh_industry_constituents_falls_back_to_cache_on_fetch_failure(db_conn, monkeypatch):
    _patch_universe(monkeypatch)
    calls = {"n": 0}

    def _fake_fetch_screener_universe(filters=None, sort="pricecash"):
        calls["n"] += 1
        if calls["n"] == 1:
            return [{"ticker": "NVDA", "company": "Nvidia Corp"}]
        return None  # second (stale-refresh) call fails

    monkeypatch.setattr(
        "goat.industry_constituents.finviz_screener.fetch_screener_universe",
        _fake_fetch_screener_universe,
    )
    first = industry_constituents.get_or_refresh_industry_constituents(db_conn, "Semiconductors")
    assert any(r["ticker"] == "NVDA" for r in first)

    monkeypatch.setattr("goat.industry_constituents.config.GOAT_INDUSTRY_CONSTITUENTS_CACHE_TTL_DAYS", -1)
    second = industry_constituents.get_or_refresh_industry_constituents(db_conn, "Semiconductors")
    assert any(r["ticker"] == "NVDA" for r in second)  # stale cache kept, not wiped
