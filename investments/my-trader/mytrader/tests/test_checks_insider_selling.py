from __future__ import annotations

from mytrader.checks import insider_selling


def test_check_returns_unknown_when_fetch_fails(monkeypatch):
    monkeypatch.setattr(insider_selling.openinsider, "fetch_screener_filings", lambda *a, **k: None)
    result = insider_selling.check("CVX")
    assert result.verdict == "unknown"
    assert "unavailable" in result.detail


def test_check_returns_ok_when_no_sales(monkeypatch):
    monkeypatch.setattr(insider_selling.openinsider, "fetch_screener_filings", lambda *a, **k: [])
    result = insider_selling.check("CVX")
    assert result.verdict == "ok"
    assert "No open-market insider sale filings" in result.detail


def test_check_flags_when_sale_crosses_pct_threshold(monkeypatch):
    rows = [
        {
            "insider_name": "Wirth Michael K", "value": 50_000_000.0,
            "trade_date": "2026-08-10", "pct_owned_change": -92.0,
        },
    ]
    monkeypatch.setattr(insider_selling.openinsider, "fetch_screener_filings", lambda *a, **k: rows)
    result = insider_selling.check("CVX")
    assert result.verdict == "flag"
    assert "Wirth Michael K" in result.detail
    assert "92% of position" in result.detail
    assert result.data["flagged_count"] == 1


def test_check_stays_ok_when_sale_below_pct_threshold(monkeypatch):
    rows = [
        {
            "insider_name": "Small Seller", "value": 5_000.0,
            "trade_date": "2026-08-10", "pct_owned_change": -0.5,
        },
    ]
    monkeypatch.setattr(insider_selling.openinsider, "fetch_screener_filings", lambda *a, **k: rows)
    result = insider_selling.check("CVX")
    assert result.verdict == "ok"
    assert result.data["flagged_count"] == 0


def test_check_stays_ok_when_pct_unparsable_fail_open(monkeypatch):
    rows = [
        {"insider_name": "New Holder", "value": 9_000_000.0, "trade_date": "2026-08-10", "pct_owned_change": None},
    ]
    monkeypatch.setattr(insider_selling.openinsider, "fetch_screener_filings", lambda *a, **k: rows)
    result = insider_selling.check("CVX")
    assert result.verdict == "ok"
    assert "New Holder" in result.detail


def test_check_passes_lookback_and_min_value_config_to_fetch(monkeypatch):
    captured = {}

    def _fake(tickers_list, trade_type, min_value, filing_date_days=7):
        captured["tickers_list"] = tickers_list
        captured["trade_type"] = trade_type
        captured["min_value"] = min_value
        captured["filing_date_days"] = filing_date_days
        return []

    monkeypatch.setattr(insider_selling.openinsider, "fetch_screener_filings", _fake)
    insider_selling.check("CVX")
    assert captured["tickers_list"] == ["CVX"]
    assert captured["trade_type"] == "S"
    assert captured["min_value"] == insider_selling.config.INSIDER_SELLING_MIN_VALUE
    assert captured["filing_date_days"] == insider_selling.config.INSIDER_SELLING_LOOKBACK_DAYS
