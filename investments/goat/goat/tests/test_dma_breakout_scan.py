from __future__ import annotations

import pandas as pd
from mytrader import db as mt_db
from mytrader.market_data import TickerData

from goat import config, db as goat_db, dma_breakout_scan


def _dates(n: int, start: str = "2020-01-01") -> pd.DatetimeIndex:
    return pd.date_range(start, periods=n, freq="D")


def _series_with_cross(
    ma_days: int, days_since_cross: int, crossed_above: bool = True,
) -> pd.Series:
    """Mirrors test_sector_rotation._series_with_cross, generalized over ma_days:
    sits below (or above) its ma_days-day MA, then jumps so the close crosses
    exactly `days_since_cross` trading days before the series' last row, and
    stays on that side through to the end so the MA itself slopes up (or down,
    for crossed_above=False)."""
    lead_in = ma_days + config.GOAT_SECTOR_SLOPE_LOOKBACK_DAYS + 20
    pre_price = 90.0 if crossed_above else 110.0
    post_price = 130.0 if crossed_above else 70.0
    prices = [pre_price] * lead_in + [post_price] * (days_since_cross + 1)
    return pd.Series(prices, index=_dates(len(prices)))


def _declining_then_spike_series(ma_days: int, days_since_cross: int = 1, spike: float = 50.0) -> pd.Series:
    """Mirrors test_sector_rotation._declining_then_spike_series, generalized over
    ma_days: a steadily declining price series (so the MA is clearly sloping down)
    with a recent upward spike that crosses the close back above the MA
    `days_since_cross` trading days ago, but too small/recent to have turned the
    MA's own slope up yet -- proves check_ma_cross withholds 'interesting' on a
    fresh cross when the MA is still sloping down (the slope gate added
    2026-09-16, matching check_sector_breakout's own requirement)."""
    n_decline = ma_days + 100
    prices = [200.0 - i * 0.3 for i in range(n_decline)]
    spike_pos = len(prices) - 1 - days_since_cross
    for i in range(spike_pos, len(prices)):
        prices[i] = prices[spike_pos - 1] + spike
    return pd.Series(prices, index=_dates(len(prices)))


def _healthy_ticker_data(ticker: str = "AAPL") -> TickerData:
    return TickerData(
        ticker=ticker,
        info={
            "debtToEquity": 50.0, "totalCash": 1_000_000_000, "freeCashflow": 100_000_000,
            "operatingCashflow": 100_000_000, "marketCap": 500_000_000.0, "averageVolume": 500_000,
            "fullExchangeName": "NasdaqGS",
        },
        dividends=None,
    )


def _insolvent_ticker_data(ticker: str = "AAPL") -> TickerData:
    return TickerData(
        ticker=ticker,
        info={
            "debtToEquity": 300.0, "totalCash": 10_000_000, "freeCashflow": -100_000_000,
            "operatingCashflow": -80_000_000, "marketCap": 500_000_000.0, "averageVolume": 500_000,
        },
        dividends=None,
    )


# --- check_ma_cross -----------------------------------------------------

def test_check_ma_cross_fresh_cross_above_150_is_interesting():
    close = _series_with_cross(150, days_since_cross=config.GOAT_DMA_BREAKOUT_CROSS_RECENCY_DAYS)
    result = dma_breakout_scan.check_ma_cross("AAPL", "Technology", close, 150, config.GOAT_DMA_BREAKOUT_CROSS_RECENCY_DAYS)
    assert result.verdict == "interesting"
    assert result.data["crossed_above"] is True
    assert result.data["ma_days"] == 150


def test_check_ma_cross_fresh_cross_above_200_is_interesting():
    close = _series_with_cross(200, days_since_cross=config.GOAT_DMA_BREAKOUT_CROSS_RECENCY_DAYS)
    result = dma_breakout_scan.check_ma_cross("AAPL", "Technology", close, 200, config.GOAT_DMA_BREAKOUT_CROSS_RECENCY_DAYS)
    assert result.verdict == "interesting"
    assert result.data["crossed_above"] is True
    assert result.data["ma_days"] == 200


def test_check_ma_cross_150_and_200_are_reported_independently():
    """A series just long enough for a real 150-day check but too short for a
    200-day one (min_len = ma_days + GOAT_SECTOR_SLOPE_LOOKBACK_DAYS) -- proves
    ma_days is a genuine per-call parameter, not shared state."""
    close = _series_with_cross(150, days_since_cross=config.GOAT_DMA_BREAKOUT_CROSS_RECENCY_DAYS)
    result_150 = dma_breakout_scan.check_ma_cross(
        "AAPL", "Technology", close, 150, config.GOAT_DMA_BREAKOUT_CROSS_RECENCY_DAYS
    )
    result_200 = dma_breakout_scan.check_ma_cross(
        "AAPL", "Technology", close, 200, config.GOAT_DMA_BREAKOUT_CROSS_RECENCY_DAYS
    )
    assert result_150.verdict == "interesting"
    assert result_200.verdict == "unknown"


def test_check_ma_cross_stale_cross_does_not_fire():
    close = _series_with_cross(150, days_since_cross=config.GOAT_DMA_BREAKOUT_CROSS_RECENCY_DAYS + 5)
    result = dma_breakout_scan.check_ma_cross("AAPL", "Technology", close, 150, config.GOAT_DMA_BREAKOUT_CROSS_RECENCY_DAYS)
    assert result.verdict == "ok"


def test_check_ma_cross_does_not_fire_when_ma_slope_is_down():
    """Slope gate added 2026-09-16 at Shaun's request: a fresh cross above a
    still-falling MA no longer counts as 'interesting' -- matches
    check_sector_breakout's own wrong-slope test."""
    close = _declining_then_spike_series(150, days_since_cross=1)
    result = dma_breakout_scan.check_ma_cross("AAPL", "Technology", close, 150, config.GOAT_DMA_BREAKOUT_CROSS_RECENCY_DAYS)
    assert result.verdict == "ok"
    assert result.data["crossed_above"] is True
    assert result.data["slope_up"] is False


def test_check_ma_cross_no_cross_in_history_is_ok():
    n = 150 + config.GOAT_SECTOR_SLOPE_LOOKBACK_DAYS + 30
    close = pd.Series([100.0] * n, index=_dates(n))
    result = dma_breakout_scan.check_ma_cross("AAPL", "Technology", close, 150, config.GOAT_DMA_BREAKOUT_CROSS_RECENCY_DAYS)
    assert result.verdict == "ok"


def test_check_ma_cross_insufficient_history_is_unknown():
    close = pd.Series([100.0] * 10, index=_dates(10))
    result = dma_breakout_scan.check_ma_cross("AAPL", "Technology", close, 150, config.GOAT_DMA_BREAKOUT_CROSS_RECENCY_DAYS)
    assert result.verdict == "unknown"


# --- passes_liquidity_floor -----------------------------------------------

def test_passes_liquidity_floor_below_market_cap_fails():
    data = TickerData(ticker="X", info={"marketCap": 1_000.0, "averageVolume": 500_000}, dividends=None)
    assert dma_breakout_scan.passes_liquidity_floor("US", data) is False


def test_passes_liquidity_floor_below_avg_volume_fails():
    data = TickerData(ticker="X", info={"marketCap": 500_000_000.0, "averageVolume": 100}, dividends=None)
    assert dma_breakout_scan.passes_liquidity_floor("US", data) is False


def test_passes_liquidity_floor_missing_info_fields_fails():
    data = TickerData(ticker="X", info={}, dividends=None)
    assert dma_breakout_scan.passes_liquidity_floor("US", data) is False


def test_passes_liquidity_floor_none_data_fails():
    assert dma_breakout_scan.passes_liquidity_floor("US", None) is False


def test_passes_liquidity_floor_passes_both():
    data = _healthy_ticker_data()
    assert dma_breakout_scan.passes_liquidity_floor("US", data) is True


def test_passes_liquidity_floor_uses_per_market_threshold():
    # Between the (equal) USD/AUD floors and a value that's still above the floor either way --
    # this just proves the market branch is read, not a numeric distinction (both floors are 300M today).
    data = TickerData(
        ticker="X", info={"marketCap": config.GOAT_DMA_BREAKOUT_MIN_MARKET_CAP_AUD, "averageVolume": 500_000},
        dividends=None,
    )
    assert dma_breakout_scan.passes_liquidity_floor("ASX", data) is True
    data_below = TickerData(
        ticker="X", info={"marketCap": config.GOAT_DMA_BREAKOUT_MIN_MARKET_CAP_AUD - 1, "averageVolume": 500_000},
        dividends=None,
    )
    assert dma_breakout_scan.passes_liquidity_floor("ASX", data_below) is False


# --- fetch_universe_constituents -------------------------------------------

def test_fetch_universe_constituents_combines_us_and_asx(db_conn, monkeypatch):
    monkeypatch.setattr(
        "goat.dma_breakout_scan.sp500_universe.get_or_refresh_sp500_constituents",
        lambda conn: [{"ticker": "AAPL", "security": "Apple Inc.", "gics_sector": "Information Technology"}],
    )
    monkeypatch.setattr(
        "goat.dma_breakout_scan.asx200_universe.fetch_asx200_constituents",
        lambda: [{"ticker": "XRO", "company": "Xero", "sector": "Technology"}],
    )
    rows = dma_breakout_scan.fetch_universe_constituents(db_conn)
    tickers_seen = {r["ticker"] for r in rows}
    assert "AAPL" in tickers_seen
    assert "XRO.AX" in tickers_seen  # .AX-suffixed, not bare


def test_fetch_universe_constituents_drops_ethical_filter_excluded(db_conn, monkeypatch):
    monkeypatch.setattr(
        "goat.dma_breakout_scan.sp500_universe.get_or_refresh_sp500_constituents",
        lambda conn: [{"ticker": "AAPL", "security": "Apple Inc.", "gics_sector": "Information Technology"}],
    )
    monkeypatch.setattr("goat.dma_breakout_scan.asx200_universe.fetch_asx200_constituents", lambda: None)
    monkeypatch.setattr("goat.config.GOAT_DMA_BREAKOUT_ETF_UNIVERSE", {})
    monkeypatch.setattr(
        "goat.dma_breakout_scan.ethical_check", lambda bare: (True, "Primary defense/military contractor")
    )
    rows = dma_breakout_scan.fetch_universe_constituents(db_conn)
    assert rows == []


def test_fetch_universe_constituents_asx_scrape_failure_yields_us_only(db_conn, monkeypatch):
    monkeypatch.setattr(
        "goat.dma_breakout_scan.sp500_universe.get_or_refresh_sp500_constituents",
        lambda conn: [{"ticker": "AAPL", "security": "Apple Inc.", "gics_sector": "Information Technology"}],
    )
    monkeypatch.setattr("goat.dma_breakout_scan.asx200_universe.fetch_asx200_constituents", lambda: None)
    monkeypatch.setattr("goat.config.GOAT_DMA_BREAKOUT_ETF_UNIVERSE", {})
    rows = dma_breakout_scan.fetch_universe_constituents(db_conn)  # must not crash
    assert [r["ticker"] for r in rows] == ["AAPL"]


def test_fetch_universe_constituents_adds_etf_bucket(db_conn, monkeypatch):
    monkeypatch.setattr(
        "goat.dma_breakout_scan.sp500_universe.get_or_refresh_sp500_constituents",
        lambda conn: [],
    )
    monkeypatch.setattr("goat.dma_breakout_scan.asx200_universe.fetch_asx200_constituents", lambda: None)
    fake_etfs = {"SPY": "Broad Market", "XLI": "Industrials", "ITA": "Aerospace & Defense"}
    monkeypatch.setattr("goat.config.GOAT_DMA_BREAKOUT_ETF_UNIVERSE", fake_etfs)
    rows = dma_breakout_scan.fetch_universe_constituents(db_conn)
    by_ticker = {r["ticker"]: r for r in rows}

    assert by_ticker["SPY"]["market"] == "ETF"
    assert by_ticker["SPY"]["company"] == ""
    assert by_ticker["SPY"]["review_reason"] is None

    assert "XLI" not in by_ticker  # banned everywhere else in goat, must be excluded here too

    assert by_ticker["ITA"]["review_reason"] == "REVIEW: defense-themed ETF"


# --- passes_liquidity_floor (ETF branch) ------------------------------------

def test_passes_liquidity_floor_etf_below_aum_fails():
    data = TickerData(ticker="X", info={"totalAssets": 10_000_000.0, "averageVolume": 500_000}, dividends=None)
    assert dma_breakout_scan.passes_liquidity_floor("ETF", data) is False


def test_passes_liquidity_floor_etf_above_aum_passes():
    data = TickerData(ticker="X", info={"totalAssets": 100_000_000.0, "averageVolume": 500_000}, dividends=None)
    assert dma_breakout_scan.passes_liquidity_floor("ETF", data) is True


def test_passes_liquidity_floor_etf_missing_total_assets_fails():
    data = TickerData(ticker="X", info={"averageVolume": 500_000}, dividends=None)
    assert dma_breakout_scan.passes_liquidity_floor("ETF", data) is False


def test_passes_liquidity_floor_etf_below_avg_volume_fails():
    data = TickerData(ticker="X", info={"totalAssets": 100_000_000.0, "averageVolume": 100}, dividends=None)
    assert dma_breakout_scan.passes_liquidity_floor("ETF", data) is False


# --- run_dma_breakout_scan --------------------------------------------------

_US_CONSTITUENTS = [{"ticker": "AAPL", "security": "Apple Inc.", "gics_sector": "Information Technology"}]


def _interesting_close() -> pd.Series:
    return _series_with_cross(150, days_since_cross=config.GOAT_DMA_BREAKOUT_CROSS_RECENCY_DAYS)


def _patch_common(
    monkeypatch, constituents=None, fetch_close=None, ticker_data=None, etf_universe=None,
    industry_map=None,
):
    monkeypatch.setattr(
        "goat.dma_breakout_scan.sp500_universe.get_or_refresh_sp500_constituents",
        lambda conn: constituents if constituents is not None else _US_CONSTITUENTS,
    )
    monkeypatch.setattr("goat.dma_breakout_scan.asx200_universe.fetch_asx200_constituents", lambda: None)
    # ETF universe left empty by default -- keeps every pre-existing US/ASX-only test
    # isolated from the real 57-ticker GOAT_DMA_BREAKOUT_ETF_UNIVERSE; tests exercising
    # the ETF bucket monkeypatch it explicitly before calling _patch_common.
    if etf_universe is not None:
        monkeypatch.setattr("goat.dma_breakout_scan.config.GOAT_DMA_BREAKOUT_ETF_UNIVERSE", etf_universe)
    else:
        monkeypatch.setattr("goat.dma_breakout_scan.config.GOAT_DMA_BREAKOUT_ETF_UNIVERSE", {})
    monkeypatch.setattr(
        "goat.dma_breakout_scan.price_history.fetch_close_history",
        fetch_close if fetch_close is not None else (lambda ticker, lookback_days: _interesting_close()),
    )
    monkeypatch.setattr(
        "goat.dma_breakout_scan.market_data.fetch_ticker_data",
        ticker_data if ticker_data is not None else (lambda ticker: _healthy_ticker_data(ticker)),
    )
    # No industry filter by default (industry_map=None -> unfiltered, matching
    # pre-filter behavior) -- keeps every pre-existing test isolated from the new
    # industry-rotation gate; tests exercising it opt in explicitly.
    monkeypatch.setattr(
        "goat.dma_breakout_scan.fetch_top_industry_map", lambda conn: industry_map,
    )


# --- fetch_top_industry_map -------------------------------------------------

def test_fetch_top_industry_map_returns_none_when_no_snapshot_exists(db_conn):
    assert dma_breakout_scan.fetch_top_industry_map(db_conn) is None


def test_fetch_top_industry_map_unions_top_n_industries(db_conn, monkeypatch):
    monkeypatch.setattr(config, "GOAT_DMA_BREAKOUT_TOP_INDUSTRY_COUNT", 2)
    goat_db.insert_rotation_snapshots(
        db_conn, scope="industry_full", snapshot_date="2026-10-20",
        rows=[
            {"ticker": "Semiconductors", "name": "Semiconductors", "rank": 1},
            {"ticker": "Gold", "name": "Gold", "rank": 2},
            {"ticker": "Airlines", "name": "Airlines", "rank": 3},
        ],
        label_key="name",
    )

    def _fake_get_or_refresh(conn, industry_label):
        return {
            "Semiconductors": [{"ticker": "NVDA"}],
            "Gold": [{"ticker": "NST.AX"}],
            "Airlines": [{"ticker": "LUV"}],
        }[industry_label]

    monkeypatch.setattr(
        "goat.dma_breakout_scan.industry_constituents.get_or_refresh_industry_constituents",
        _fake_get_or_refresh,
    )
    result = dma_breakout_scan.fetch_top_industry_map(db_conn)
    # Airlines (rank 3) excluded by the top-2 cutoff; values are each ticker's
    # actual Finviz industry, not just a flat allow-set.
    assert result == {"NVDA": "Semiconductors", "NST.AX": "Gold"}


def test_run_dma_breakout_scan_stages_new_candidate(db_conn, monkeypatch):
    _patch_common(monkeypatch)
    result = dma_breakout_scan.run_dma_breakout_scan(db_conn)
    assert result["scanned"] == 1
    assert len(result["new_candidates"]) == 1
    assert result["new_candidates"][0]["ticker"] == "AAPL"
    row = goat_db.get_goat_pending_candidate(db_conn, "AAPL")
    assert row is not None
    assert row["source"] == "goat_dma_breakout_scan"
    assert row["company_name"] == "Apple Inc."
    assert row["exchange"] == "NasdaqGS"


def test_run_dma_breakout_scan_clears_never_reviewed_candidate_from_previous_run(db_conn, monkeypatch):
    """Changed 2026-10-20 at Shaun's request: every run now starts fresh rather than
    carrying a never-reviewed candidate forward for up to 3 days -- a candidate from
    the immediately prior run (not just an old/stale one) must be cleared, scoped to
    this source only (other Goat scans' pending candidates are untouched)."""
    goat_db.insert_goat_pending_candidate(
        db_conn, ticker="PRIOR_RUN", sector_label="Technology", signal_detail="old",
        source="goat_dma_breakout_scan",
    )
    goat_db.insert_goat_pending_candidate(
        db_conn, ticker="OTHERSCAN", sector_label="Technology", signal_detail="old",
        source="goat_sector_rotation",
    )
    _patch_common(monkeypatch, constituents=[])

    dma_breakout_scan.run_dma_breakout_scan(db_conn)

    assert goat_db.get_goat_pending_candidate(db_conn, "PRIOR_RUN") is None
    assert goat_db.get_goat_pending_candidate(db_conn, "OTHERSCAN") is not None


def test_run_dma_breakout_scan_skips_ticker_already_a_holding_ax_suffixed(db_conn, monkeypatch):
    _patch_common(
        monkeypatch,
        constituents=[],
    )
    monkeypatch.setattr("goat.dma_breakout_scan.asx200_universe.fetch_asx200_constituents",
                         lambda: [{"ticker": "XRO", "company": "Xero", "sector": "Technology"}])
    mt_db.upsert_holding(
        db_conn, ticker="XRO.AX", name="Xero", asset_type="stock", bucket="1", qty=1.0, avg_price=100.0,
    )
    result = dma_breakout_scan.run_dma_breakout_scan(db_conn)
    assert result["new_candidates"] == []
    assert goat_db.get_goat_pending_candidate(db_conn, "XRO.AX") is None


def test_run_dma_breakout_scan_skips_ticker_already_watchlisted(db_conn, monkeypatch):
    _patch_common(monkeypatch)
    mt_db.upsert_watchlist_row(
        db_conn, ticker="AAPL", name="Apple Inc.", asset_type="stock", bucket="unassigned",
    )
    result = dma_breakout_scan.run_dma_breakout_scan(db_conn)
    assert result["new_candidates"] == []
    assert goat_db.get_goat_pending_candidate(db_conn, "AAPL") is None


def test_run_dma_breakout_scan_skips_ticker_staged_by_another_source(db_conn, monkeypatch):
    _patch_common(monkeypatch)
    goat_db.insert_goat_pending_candidate(
        db_conn, ticker="AAPL", sector_label="Technology",
        signal_detail="heartbeat signal", source="goat_heartbeat_scan",
    )
    result = dma_breakout_scan.run_dma_breakout_scan(db_conn)
    assert result["new_candidates"] == []
    assert result["already_staged_elsewhere"] == 1
    row = goat_db.get_goat_pending_candidate(db_conn, "AAPL")
    assert row["source"] == "goat_heartbeat_scan"  # untouched, not overwritten


def test_run_dma_breakout_scan_suppresses_staging_on_insolvency_risk(db_conn, monkeypatch):
    _patch_common(monkeypatch, ticker_data=lambda ticker: _insolvent_ticker_data(ticker))
    result = dma_breakout_scan.run_dma_breakout_scan(db_conn)
    assert result["new_candidates"] == []
    assert goat_db.get_goat_pending_candidate(db_conn, "AAPL") is None


def test_run_dma_breakout_scan_suppresses_staging_when_liquidity_floor_fails(db_conn, monkeypatch):
    thin_data = TickerData(
        ticker="AAPL", info={"marketCap": 1_000.0, "averageVolume": 100}, dividends=None,
    )
    _patch_common(monkeypatch, ticker_data=lambda ticker: thin_data)
    result = dma_breakout_scan.run_dma_breakout_scan(db_conn)
    assert result["new_candidates"] == []
    assert goat_db.get_goat_pending_candidate(db_conn, "AAPL") is None


def test_run_dma_breakout_scan_skips_ticker_with_no_price_history(db_conn, monkeypatch):
    _patch_common(monkeypatch, fetch_close=lambda ticker, lookback_days: None)
    result = dma_breakout_scan.run_dma_breakout_scan(db_conn)  # must not raise
    assert result["scanned"] == 0
    assert result["new_candidates"] == []


def test_run_dma_breakout_scan_restages_same_ticker_on_repeat_run_without_duplicating(db_conn, monkeypatch):
    """Changed 2026-10-20: with the fresh-start-every-run behavior, a ticker that's
    still genuinely interesting gets re-staged each run (it's cleared and reinserted,
    not suppressed as 'already pending from last time') -- but never duplicated."""
    _patch_common(monkeypatch)
    dma_breakout_scan.run_dma_breakout_scan(db_conn)
    result = dma_breakout_scan.run_dma_breakout_scan(db_conn)
    assert len(result["new_candidates"]) == 1
    assert result["new_candidates"][0]["ticker"] == "AAPL"
    assert len(result["pending_candidates"]) == 1


def _etf_ticker_data(ticker: str) -> TickerData:
    return TickerData(
        ticker=ticker,
        info={
            "totalAssets": 100_000_000.0, "averageVolume": 500_000,
            "longName": "Test Fund", "quoteType": "ETF",
            "fullExchangeName": "NYSEArca",
        },
        dividends=None,
    )


def test_run_dma_breakout_scan_stages_etf_candidate_with_longname_fallback(db_conn, monkeypatch):
    _patch_common(
        monkeypatch, constituents=[], ticker_data=lambda ticker: _etf_ticker_data(ticker),
        etf_universe={"SPY": "Broad Market"},
    )
    result = dma_breakout_scan.run_dma_breakout_scan(db_conn)
    assert len(result["new_candidates"]) == 1
    assert result["new_candidates"][0]["ticker"] == "SPY"
    assert result["new_candidates"][0]["company"] == "Test Fund"
    row = goat_db.get_goat_pending_candidate(db_conn, "SPY")
    assert row["company_name"] == "Test Fund"


def test_run_dma_breakout_scan_never_stages_banned_etf_ticker(db_conn, monkeypatch):
    _patch_common(
        monkeypatch, constituents=[], ticker_data=lambda ticker: _etf_ticker_data(ticker),
        etf_universe={"XLI": "Industrials"},
    )
    result = dma_breakout_scan.run_dma_breakout_scan(db_conn)
    assert result["new_candidates"] == []
    assert goat_db.get_goat_pending_candidate(db_conn, "XLI") is None


# --- run_dma_breakout_scan industry filter ----------------------------------

def test_run_dma_breakout_scan_stages_when_industry_in_allow_set(db_conn, monkeypatch):
    _patch_common(monkeypatch, industry_map={"AAPL": "Semiconductors"})
    result = dma_breakout_scan.run_dma_breakout_scan(db_conn)
    assert len(result["new_candidates"]) == 1
    assert result["new_candidates"][0]["ticker"] == "AAPL"
    assert result["new_candidates"][0]["sector_label"] == "Semiconductors"
    assert result["filtered_by_industry"] == 0
    assert result["industry_filter_applied"] is True


def test_run_dma_breakout_scan_filters_when_industry_not_in_allow_set(db_conn, monkeypatch):
    _patch_common(monkeypatch, industry_map={"NOT-AAPL": "Gold"})
    result = dma_breakout_scan.run_dma_breakout_scan(db_conn)
    assert result["new_candidates"] == []
    assert result["filtered_by_industry"] == 1
    assert goat_db.get_goat_pending_candidate(db_conn, "AAPL") is None


def test_run_dma_breakout_scan_etf_exempt_from_industry_filter(db_conn, monkeypatch):
    _patch_common(
        monkeypatch, constituents=[], ticker_data=lambda ticker: _etf_ticker_data(ticker),
        etf_universe={"SPY": "Broad Market"}, industry_map={},
    )
    result = dma_breakout_scan.run_dma_breakout_scan(db_conn)
    assert len(result["new_candidates"]) == 1
    assert result["new_candidates"][0]["ticker"] == "SPY"
    assert result["filtered_by_industry"] == 0


def test_run_dma_breakout_scan_unfiltered_when_no_snapshot_exists(db_conn, monkeypatch):
    _patch_common(monkeypatch)  # industry_map=None default -- no snapshot yet
    result = dma_breakout_scan.run_dma_breakout_scan(db_conn)
    assert result["industry_filter_applied"] is False
    assert len(result["new_candidates"]) == 1


# --- render_dma_breakout_candidates_report ----------------------------------

def test_render_dma_breakout_candidates_report_lists_pending_rows():
    result = {
        "scanned": 700, "asx_unavailable": False, "already_staged_elsewhere": 0,
        "pending_candidates": [
            {"ticker": "AAPL", "sector_label": "Technology", "signal_detail": "DMA breakout signal",
             "company_name": "Apple Inc.", "exchange": "NasdaqGS", "flagged_at": "2026-09-16T00:00:00+00:00"},
        ],
    }
    report = dma_breakout_scan.render_dma_breakout_candidates_report(result)
    assert "AAPL" in report
    assert "Apple Inc." in report
    assert "NasdaqGS" in report
    assert "DMA breakout signal" in report
    assert "700" in report


def test_render_dma_breakout_candidates_report_missing_company_name_and_exchange_show_na():
    result = {
        "scanned": 700, "asx_unavailable": False, "already_staged_elsewhere": 0,
        "pending_candidates": [
            {"ticker": "AAPL", "sector_label": "Technology", "signal_detail": "DMA breakout signal",
             "flagged_at": "2026-09-16T00:00:00+00:00"},
        ],
    }
    report = dma_breakout_scan.render_dma_breakout_candidates_report(result)
    assert "| AAPL | n/a | n/a |" in report


def test_render_dma_breakout_candidates_report_surfaces_asx_unavailable_banner():
    result = {"scanned": 500, "asx_unavailable": True, "already_staged_elsewhere": 0, "pending_candidates": []}
    report = dma_breakout_scan.render_dma_breakout_candidates_report(result)
    assert "ASX 200 universe unavailable" in report


def test_render_dma_breakout_candidates_report_surfaces_already_staged_elsewhere_count():
    result = {"scanned": 500, "asx_unavailable": False, "already_staged_elsewhere": 3, "pending_candidates": []}
    report = dma_breakout_scan.render_dma_breakout_candidates_report(result)
    assert "3 ticker(s)" in report


def test_render_dma_breakout_candidates_report_shows_industry_filter_unavailable_banner():
    result = {
        "scanned": 500, "asx_unavailable": False, "already_staged_elsewhere": 0,
        "industry_filter_applied": False, "filtered_by_industry": 0, "pending_candidates": [],
    }
    report = dma_breakout_scan.render_dma_breakout_candidates_report(result)
    assert "Industry-rotation filter unavailable" in report


def test_render_dma_breakout_candidates_report_shows_filtered_by_industry_count():
    result = {
        "scanned": 500, "asx_unavailable": False, "already_staged_elsewhere": 0,
        "industry_filter_applied": True, "filtered_by_industry": 4, "pending_candidates": [],
    }
    report = dma_breakout_scan.render_dma_breakout_candidates_report(result)
    assert "4 ticker(s) crossed but were filtered out" in report


def test_render_dma_breakout_candidates_report_sorts_newest_cross_first():
    result = {
        "scanned": 500, "asx_unavailable": False, "already_staged_elsewhere": 0,
        "pending_candidates": [
            {"ticker": "STALE", "sector_label": "Technology",
             "signal_detail": "STALE (Technology): crossed above its 150-day MA 9 trading day(s) ago, "
                               "now +1.0% above it (MA currently rising) -- DMA breakout discovery signal; "
                               "survival context: n/a",
             "flagged_at": "2026-09-10T00:00:00+00:00"},
            {"ticker": "FRESH", "sector_label": "Technology",
             "signal_detail": "FRESH (Technology): crossed above its 200-day MA 0 trading day(s) ago, "
                               "now +0.2% above it (MA currently falling) -- DMA breakout discovery signal; "
                               "survival context: n/a",
             "flagged_at": "2026-09-16T00:00:00+00:00"},
            {"ticker": "BOTH", "sector_label": "Technology",
             "signal_detail": "BOTH (Technology): crossed above its 150-day MA 4 trading day(s) ago, "
                               "now +2.0% above it (MA currently rising) -- DMA breakout discovery signal; "
                               "BOTH (Technology): crossed above its 200-day MA 6 trading day(s) ago, "
                               "now +3.0% above it (MA currently rising) -- DMA breakout discovery signal; "
                               "survival context: n/a",
             "flagged_at": "2026-09-14T00:00:00+00:00"},
        ],
    }
    report = dma_breakout_scan.render_dma_breakout_candidates_report(result)
    fresh_pos, both_pos, stale_pos = report.index("FRESH"), report.index("BOTH"), report.index("STALE")
    assert fresh_pos < both_pos < stale_pos
