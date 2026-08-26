from __future__ import annotations

import pytest

from mytrader import cash_value_scan, config, db as mt_db
from mytrader.market_data import TickerData


def _td(ticker: str, **info) -> TickerData:
    return TickerData(ticker=ticker, info=info, dividends=None)


# --- compute_cash_value_metrics -------------------------------------------

def test_computes_ratio_and_ev_for_cash_rich_name():
    m = cash_value_scan.compute_cash_value_metrics(_td(
        "X", marketCap=100e6, totalCash=120e6, totalDebt=20e6,
        operatingCashflow=5e6, freeCashflow=4e6, sector="Technology",
    ))
    assert m is not None
    assert m["net_cash"] == 100e6
    assert m["cash_ratio"] == pytest.approx(1.0)
    assert m["ev"] == pytest.approx(0.0)
    assert m["cash_flow_ok"] is True
    assert m["cash_flow_source"] == "info"


def test_returns_none_when_market_cap_missing():
    assert cash_value_scan.compute_cash_value_metrics(
        _td("X", totalCash=100e6, totalDebt=1e6)
    ) is None


def test_returns_none_when_total_debt_missing():
    assert cash_value_scan.compute_cash_value_metrics(
        _td("X", marketCap=100e6, totalCash=100e6)
    ) is None


def test_cash_ratio_above_one_when_trading_below_net_cash():
    m = cash_value_scan.compute_cash_value_metrics(_td(
        "X", marketCap=80e6, totalCash=120e6, totalDebt=10e6,
        operatingCashflow=1e6, freeCashflow=1e6,
    ))
    assert m["cash_ratio"] > 1
    assert m["ev"] < 0
    assert m["ev_pct_of_mcap"] < 0
    assert m["fcf_yield_on_ev"] is None  # ev <= 0 -> undefined


def test_cash_flow_falls_back_to_annual_when_info_missing(monkeypatch):
    monkeypatch.setattr(
        "mytrader.market_data.fetch_cash_flow_statement",
        lambda ticker: {"operating_cash_flow": 3e6, "free_cash_flow": 2e6},
    )
    m = cash_value_scan.compute_cash_value_metrics(_td(
        "X", marketCap=100e6, totalCash=90e6, totalDebt=1e6,
    ))
    assert m["cash_flow_ok"] is True
    assert m["cash_flow_source"] == "annual"
    assert m["operating_cash_flow"] == 3e6


def test_cash_flow_not_ok_when_fcf_negative():
    m = cash_value_scan.compute_cash_value_metrics(_td(
        "X", marketCap=100e6, totalCash=90e6, totalDebt=1e6,
        operatingCashflow=5e6, freeCashflow=-1e6,
    ))
    assert m["cash_flow_ok"] is False


# --- _passes -------------------------------------------------------------

def _metrics(ratio=0.9, cash_flow_ok=True, sector="Technology"):
    return {"cash_ratio": ratio, "cash_flow_ok": cash_flow_ok, "sector": sector}


def test_passes_requires_ratio_and_cashflow_and_sector():
    assert cash_value_scan._passes(_metrics()) is True
    assert cash_value_scan._passes(None) is False


def test_rejects_financial_services_sector():
    assert cash_value_scan._passes(_metrics(sector="Financial Services")) is False
    assert cash_value_scan._passes(_metrics(sector="Financials")) is False
    assert cash_value_scan._passes(_metrics(sector="Real Estate")) is False


def test_rejects_below_threshold_ratio():
    assert cash_value_scan._passes(_metrics(ratio=0.79)) is False
    assert cash_value_scan._passes(_metrics(ratio=0.80)) is True


def test_rejects_when_cash_flow_not_ok():
    assert cash_value_scan._passes(_metrics(cash_flow_ok=False)) is False


# --- run_scan ----------------------------------------------------------

_QUALIFIER = dict(marketCap=100e6, totalCash=130e6, totalDebt=10e6,
                  operatingCashflow=6e6, freeCashflow=5e6, sector="Technology",
                  financialCurrency="USD", revenueGrowth=0.03)
_FAILS_RATIO = dict(marketCap=100e6, totalCash=40e6, totalDebt=10e6,
                    operatingCashflow=6e6, freeCashflow=5e6, sector="Technology",
                    financialCurrency="USD")


def _patch_universes(monkeypatch, *, us, asx, ticker_map):
    monkeypatch.setattr("mytrader.finviz_screener.fetch_screener_universe", lambda: us)
    monkeypatch.setattr("mytrader.asx200_universe.fetch_asx200_constituents", lambda: asx)
    monkeypatch.setattr(
        "mytrader.market_data.fetch_ticker_data",
        lambda t: ticker_map.get(t),
    )


def test_run_scan_filters_ranks_and_tags(db_conn, monkeypatch):
    mt_db.upsert_holding(db_conn, ticker="GEM", name="Gem Co", asset_type="stock",
                         bucket="1", qty=1, avg_price=1)
    mt_db.upsert_watchlist_row(db_conn, ticker="WCH", name="Watch Co",
                               asset_type="stock", bucket="unassigned")
    us = [
        {"ticker": "GEM", "company": "Gem Co", "sector": "Technology"},
        {"ticker": "WCH", "company": "Watch Co", "sector": "Technology"},
        {"ticker": "LOW", "company": "Low Ratio Co", "sector": "Technology"},
        {"ticker": "LMT", "company": "Defense Co", "sector": "Industrials"},
    ]
    asx = [{"ticker": "AAA", "company": "Aussie Co", "sector": "Materials"}]
    tmap = {
        # cash ratios: GEM 190/100 = 1.9, WCH 120/100 = 1.2, AAA 120/50 = 2.4
        "GEM": _td("GEM", **{**_QUALIFIER, "marketCap": 100e6, "totalCash": 190e6, "totalDebt": 0}),
        "WCH": _td("WCH", **_QUALIFIER),
        "LOW": _td("LOW", **_FAILS_RATIO),
        "LMT": _td("LMT", **_QUALIFIER),
        "AAA.AX": _td("AAA.AX", **{**_QUALIFIER, "financialCurrency": "AUD",
                                   "marketCap": 50e6, "totalCash": 130e6, "totalDebt": 10e6}),
    }
    _patch_universes(monkeypatch, us=us, asx=asx, ticker_map=tmap)

    result = cash_value_scan.run_scan(db_conn)
    assert result["stale"] is False
    tickers_out = [r["ticker"] for r in result["rows"]]
    assert tickers_out == ["AAA", "GEM", "WCH"]  # LOW filtered, LMT excluded, sorted by ratio desc
    assert result["qualifying_count"] == 3
    gem = next(r for r in result["rows"] if r["ticker"] == "GEM")
    assert "held" in gem["tags"]
    wch = next(r for r in result["rows"] if r["ticker"] == "WCH")
    assert "watchlist" in wch["tags"]
    aaa = next(r for r in result["rows"] if r["ticker"] == "AAA")
    assert aaa["market"] == "ASX"
    assert "micro" in aaa["tags"]  # 50M AUD < A$75M floor


def test_run_scan_returns_stale_when_finviz_fails(db_conn, monkeypatch):
    monkeypatch.setattr("mytrader.finviz_screener.fetch_screener_universe", lambda: None)
    result = cash_value_scan.run_scan(db_conn)
    assert result["stale"] is True


def test_run_scan_notes_asx_unavailable_when_wiki_fails(db_conn, monkeypatch):
    us = [{"ticker": "GEM", "company": "Gem Co", "sector": "Technology"}]
    _patch_universes(monkeypatch, us=us, asx=None, ticker_map={"GEM": _td("GEM", **_QUALIFIER)})
    result = cash_value_scan.run_scan(db_conn)
    assert result["asx_unavailable"] is True
    assert [r["ticker"] for r in result["rows"]] == ["GEM"]


def test_run_scan_caps_at_max_rows_and_reports_overflow(db_conn, monkeypatch):
    monkeypatch.setattr(config, "CASH_VALUE_REPORT_MAX_ROWS", 2)
    us = [{"ticker": f"T{i}", "company": f"Co {i}", "sector": "Technology"} for i in range(5)]
    tmap = {
        f"T{i}": _td(f"T{i}", **{**_QUALIFIER, "totalCash": (100 + i * 10) * 1e6})
        for i in range(5)
    }
    _patch_universes(monkeypatch, us=us, asx=None, ticker_map=tmap)
    result = cash_value_scan.run_scan(db_conn)
    assert len(result["rows"]) == 2
    assert result["overflow"] == 3
    assert result["qualifying_count"] == 5


# --- render_report / write_report ---------------------------------------

def _result(rows, **over):
    base = {
        "stale": False, "rows": rows, "overflow": 0, "qualifying_count": len(rows),
        "asx_unavailable": False, "us_scanned": 400, "asx_scanned": 200,
    }
    base.update(over)
    return base


def _rendered_row(ticker="GEM", **over):
    m = cash_value_scan.compute_cash_value_metrics(_td(ticker, **_QUALIFIER))
    row = {"ticker": ticker, "yf_ticker": ticker, "company": "Gem Co", "market": "US",
           "review_reason": None, "tags": [], **m}
    row.update(over)
    row["read"] = cash_value_scan._plain_english_read(row)
    return row


def test_render_includes_run_date_and_advisor_disclaimer():
    out = cash_value_scan.render_report(_result([_rendered_row()]))
    assert "# Cash 80% Trading Value" in out
    assert "## Run:" in out
    assert "Advisor notes only" in out
    assert "GEM" in out


def test_render_lists_tags_and_shrinking_revenue():
    row = _rendered_row(tags=["held", "micro", "shrinking revenue"])
    out = cash_value_scan.render_report(_result([row]))
    assert "held, micro, shrinking revenue" in out


def test_render_shows_asx_unavailable_note():
    out = cash_value_scan.render_report(_result([_rendered_row()], asx_unavailable=True))
    assert "ASX universe unavailable this run" in out


def test_render_no_qualifiers():
    out = cash_value_scan.render_report(_result([]))
    assert "No companies qualify this run." in out


def test_render_below_net_cash_row_does_not_crash():
    row = _rendered_row(ticker="BNC", marketCap=None)  # override after compute
    m = cash_value_scan.compute_cash_value_metrics(_td("BNC", **{
        **_QUALIFIER, "marketCap": 80e6, "totalCash": 120e6, "totalDebt": 5e6,
    }))
    row = {"ticker": "BNC", "yf_ticker": "BNC", "company": "Below Net Cash Co",
           "market": "US", "review_reason": None, "tags": [], **m}
    row["read"] = cash_value_scan._plain_english_read(row)
    out = cash_value_scan.render_report(_result([row]))
    assert "below net cash" in out
    assert "n/a" in out  # FCF yld on EV


def test_write_stale_banner_prepends_to_existing_report():
    path = config.CASH_VALUE_REPORT_PATH
    path.write_text("# Cash 80% Trading Value\n\noriginal body\n", encoding="utf-8")
    cash_value_scan.write_report({"stale": True})
    out = path.read_text(encoding="utf-8")
    assert out.startswith("> STALE - Finviz fetch failed")
    assert "original body" in out


def test_write_stale_banner_does_not_stack():
    path = config.CASH_VALUE_REPORT_PATH
    path.write_text("# Cash 80% Trading Value\n\nbody\n", encoding="utf-8")
    cash_value_scan.write_report({"stale": True})
    cash_value_scan.write_report({"stale": True})
    out = path.read_text(encoding="utf-8")
    assert out.count("STALE - Finviz fetch failed") == 1
    assert "body" in out


def test_write_stale_banner_with_no_prior_report():
    path = config.CASH_VALUE_REPORT_PATH
    assert not path.exists()
    cash_value_scan.write_report({"stale": True})
    out = path.read_text(encoding="utf-8")
    assert "No prior report to show." in out


def test_write_report_writes_full_report_when_not_stale():
    cash_value_scan.write_report(_result([_rendered_row()]))
    out = config.CASH_VALUE_REPORT_PATH.read_text(encoding="utf-8")
    assert "# Cash 80% Trading Value" in out
    assert "| Ticker | Company |" in out
