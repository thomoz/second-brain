from __future__ import annotations

from mytrader.checks import fx
from mytrader.market_data import TickerData


def test_no_data_returns_unknown():
    assert fx.check(None).verdict == "unknown"


def test_aud_denominated_skips_fx_lookup(monkeypatch):
    called = False

    def fake_fetch(*args, **kwargs):
        nonlocal called
        called = True
        return 1.0

    monkeypatch.setattr("mytrader.market_data.fetch_fx_change_pct", fake_fetch)
    data = TickerData(ticker="X", info={"currency": "AUD"}, dividends=None)
    result = fx.check(data)
    assert result.verdict == "info"
    assert called is False


def test_usd_denominated_calls_fx_lookup(monkeypatch):
    monkeypatch.setattr("mytrader.market_data.fetch_fx_change_pct", lambda base, **kw: 3.5)
    data = TickerData(ticker="X", info={"currency": "USD"}, dividends=None)
    result = fx.check(data)
    assert result.verdict == "info"
    assert result.data["fx_change_pct_3mo"] == 3.5


def test_fx_lookup_failure_still_info(monkeypatch):
    monkeypatch.setattr("mytrader.market_data.fetch_fx_change_pct", lambda base, **kw: None)
    data = TickerData(ticker="X", info={"currency": "USD"}, dividends=None)
    result = fx.check(data)
    assert result.verdict == "info"
    assert "unavailable" in result.detail
