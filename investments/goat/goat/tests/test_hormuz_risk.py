from __future__ import annotations

import pandas as pd

from goat import config as goat_config, db as goat_db, hormuz_risk


def _dates(n: int, start: str = "2026-08-01") -> pd.DatetimeIndex:
    return pd.date_range(start, periods=n, freq="D")


def _bwet_series(start_price: float, end_price: float, days: int) -> pd.Series:
    prices = [start_price] + [end_price] * (days - 1)
    return pd.Series(prices, index=_dates(days))


def test_check_bwet_shipping_risk_flags_large_move(monkeypatch):
    series = _bwet_series(20.0, 25.0, goat_config.GOAT_BWET_LOOKBACK_DAYS + 1)  # +25%
    monkeypatch.setattr("goat.hormuz_risk._yfinance_history_close", lambda t, lb: series)
    result = hormuz_risk.check_bwet_shipping_risk()
    assert result.verdict == "flag"
    assert "+25.0%" in result.detail


def test_check_bwet_shipping_risk_does_not_flag_small_move(monkeypatch):
    series = _bwet_series(20.0, 21.0, goat_config.GOAT_BWET_LOOKBACK_DAYS + 1)  # +5%
    monkeypatch.setattr("goat.hormuz_risk._yfinance_history_close", lambda t, lb: series)
    result = hormuz_risk.check_bwet_shipping_risk()
    assert result.verdict == "ok"


def test_check_bwet_shipping_risk_unknown_on_fetch_miss(monkeypatch):
    monkeypatch.setattr("goat.hormuz_risk._yfinance_history_close", lambda t, lb: None)
    result = hormuz_risk.check_bwet_shipping_risk()
    assert result.verdict == "unknown"


def test_yfinance_history_close_drops_trailing_nan_row(monkeypatch):
    """Regression test for the 2026-08-18 fix: a thinly-traded ticker (BWET)
    can return a trailing NaN row for a still-settling session, which used
    to propagate through iloc[-1] as a silent NaN 'latest price'."""
    idx = _dates(3)
    df = pd.DataFrame({"Close": [20.0, 21.0, float("nan")]}, index=idx)

    class _FakeTicker:
        def __init__(self, ticker):
            pass

        def history(self, start=None, auto_adjust=None):
            return df

    monkeypatch.setattr("yfinance.Ticker", _FakeTicker)
    close = hormuz_risk._yfinance_history_close("BWET", 30)
    assert close is not None
    assert not close.isna().any()
    assert float(close.iloc[-1]) == 21.0


def test_check_jwc_listed_areas_reports_info_on_first_check(db_conn, monkeypatch):
    monkeypatch.setattr(
        "goat.hormuz_risk.lma_jwc.fetch_listed_areas_snapshot",
        lambda: {"jwla_number": "034", "section_text": "Listed Areas prose"},
    )
    result = hormuz_risk.check_jwc_listed_areas(db_conn)
    assert result.verdict == "info"
    assert "JWLA-034" in result.detail
    assert goat_db.get_macro_state(db_conn, "hormuz_jwla_number") == "034"


def test_check_jwc_listed_areas_ok_when_unchanged(db_conn, monkeypatch):
    goat_db.set_macro_state(db_conn, "hormuz_jwla_number", "034")
    monkeypatch.setattr(
        "goat.hormuz_risk.lma_jwc.fetch_listed_areas_snapshot",
        lambda: {"jwla_number": "034", "section_text": "Listed Areas prose"},
    )
    result = hormuz_risk.check_jwc_listed_areas(db_conn)
    assert result.verdict == "ok"


def test_check_jwc_listed_areas_flags_on_number_change(db_conn, monkeypatch):
    goat_db.set_macro_state(db_conn, "hormuz_jwla_number", "034")
    monkeypatch.setattr(
        "goat.hormuz_risk.lma_jwc.fetch_listed_areas_snapshot",
        lambda: {"jwla_number": "035", "section_text": "New Listed Areas prose"},
    )
    result = hormuz_risk.check_jwc_listed_areas(db_conn)
    assert result.verdict == "flag"
    assert "JWLA-034 -> JWLA-035" in result.detail
    assert goat_db.get_macro_state(db_conn, "hormuz_jwla_number") == "035"


def test_check_jwc_listed_areas_unknown_on_fetch_failure(db_conn, monkeypatch):
    monkeypatch.setattr("goat.hormuz_risk.lma_jwc.fetch_listed_areas_snapshot", lambda: None)
    result = hormuz_risk.check_jwc_listed_areas(db_conn)
    assert result.verdict == "unknown"


def test_run_hormuz_scan_reconciles_flag_into_alert_history(db_conn, monkeypatch):
    series = _bwet_series(20.0, 25.0, goat_config.GOAT_BWET_LOOKBACK_DAYS + 1)
    monkeypatch.setattr("goat.hormuz_risk._yfinance_history_close", lambda t, lb: series)
    monkeypatch.setattr(
        "goat.hormuz_risk.lma_jwc.fetch_listed_areas_snapshot",
        lambda: {"jwla_number": "034", "section_text": "prose"},
    )
    result = hormuz_risk.run_hormuz_scan(db_conn)
    assert len(result["new_alerts"]) == 1
    assert result["new_alerts"][0]["ticker"] == "HORMUZ"
    assert len(goat_db.get_open_goat_alerts(db_conn)) == 1

    # Repeat run with the same flagging state must not re-alert.
    result_again = hormuz_risk.run_hormuz_scan(db_conn)
    assert result_again["new_alerts"] == []


def test_render_hormuz_report_shows_verdict_and_excerpt():
    from mytrader.checks import CheckResult

    result = {
        "checks": [
            CheckResult(name="bwet_shipping_risk", verdict="flag", detail="BWET +25.0% move", data={}),
            CheckResult(
                name="jwc_listed_areas", verdict="info", detail="Current JWC circular: JWLA-034",
                data={"section_excerpt": "Listed Areas prose about the Gulf"},
            ),
        ],
    }
    report = hormuz_risk.render_hormuz_report(result)
    assert "BWET +25.0% move" in report
    assert "JWLA-034" in report
    assert "Listed Areas prose about the Gulf" in report
    assert "FLAG" in report
    assert "INFO" in report


def _fake_notifications_module(toast_calls, whatsapp_calls):
    import types
    fake_module = types.ModuleType("notifications")
    fake_module.send_toast_notification = lambda *a, **k: toast_calls.append((a, k))
    fake_module.send_whatsapp_notification = lambda *a, **k: whatsapp_calls.append((a, k))
    return fake_module


def test_maybe_notify_skips_when_no_new_alerts():
    hormuz_risk.maybe_notify([])  # must not raise, no notification module needed


def test_maybe_notify_sends_whatsapp_without_holdings_wording(monkeypatch):
    """Regression test: this must NOT reuse monitor.maybe_notify's hardcoded
    "{n} holding(s) {label}" template -- Hormuz checks aren't holdings."""
    import sys
    toast_calls, whatsapp_calls = [], []
    monkeypatch.setitem(sys.modules, "notifications", _fake_notifications_module(toast_calls, whatsapp_calls))

    hormuz_risk.maybe_notify([{"ticker": "HORMUZ", "message": "BWET +41.2% over 14 days"}])
    assert len(toast_calls) == 1
    assert len(whatsapp_calls) == 1
    (message,), _kwargs = whatsapp_calls[0]
    assert "BWET +41.2% over 14 days" in message
    assert "holding(s)" not in message
