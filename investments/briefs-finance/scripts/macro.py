"""Macro snapshot: yfinance proxies + optional FRED API."""

from __future__ import annotations

from datetime import date

import requests

from .config import FRED_API_KEY, FRED_SERIES, MACRO_YFINANCE
from .prices import get_close_on_or_before


def fetch_yfinance_macro(snapshot_date: date) -> dict[str, float | None]:
    """Fetch macro indicators via yfinance, looking BACK to snapshot_date."""
    result: dict[str, float | None] = {}
    for key, symbol in MACRO_YFINANCE.items():
        # Indices (VIX, T-note yields) need auto_adjust=False — no corporate actions
        is_index = symbol.startswith("^")
        result[key] = get_close_on_or_before(symbol, snapshot_date, auto_adjust=not is_index)
    return result


def fred_observation_on(
    series_id: str, target: date, units: str | None = None
) -> tuple[float, date] | None:
    """Fetch most recent FRED (value, observation_date) on or before target date.

    800-day lookback covers annual series with FRED's typical ~19-month publication
    lag (e.g. MEHOINUSA672N median household income), not just monthly series like
    UMCSENT/RECPROUSM156N. sort_order=desc + limit=1 means a wider window only reaches
    further back for the latest value -- it never returns something staler than what a
    narrower window would have found, so widening is safe for every existing caller.

    units: optional FRED transformation code (e.g. "pc1" = percent change from year
    ago) passed straight through to FRED's API -- lets a raw index series like
    CPIAUCSL return a ready-made YoY % without a second manual lookback query. Omitted
    by default, preserving every existing caller's behavior (FRED's own default is
    "lin", the untransformed level).
    """
    if not FRED_API_KEY:
        return None
    from datetime import timedelta
    try:
        params = {
            "series_id": series_id,
            "observation_start": (target - timedelta(days=800)).isoformat(),
            "observation_end": target.isoformat(),
            "sort_order": "desc",
            "limit": 1,
            "api_key": FRED_API_KEY,
            "file_type": "json",
        }
        if units is not None:
            params["units"] = units
        r = requests.get(
            "https://api.stlouisfed.org/fred/series/observations",
            params=params,
            timeout=10,
        )
        obs = r.json().get("observations", [])
        if not obs or obs[0]["value"] == ".":
            return None
        return float(obs[0]["value"]), date.fromisoformat(obs[0]["date"])
    except Exception:
        return None


def fred_series_range(
    series_id: str, start: date, end: date
) -> list[tuple[date, float]] | None:
    """Full published-observation history for series_id between start/end
    (inclusive), ascending by date. Distinct from fred_observation_on's
    single-latest-point-on-or-before lookup -- gold_backtest.py needs the whole
    daily history, not just the most recent value. Returns plain (date, value)
    tuples, not a pandas Series -- briefs-finance declares no pandas dependency;
    the caller (mytrader, which does) converts.
    """
    if not FRED_API_KEY:
        return None
    try:
        params = {
            "series_id": series_id,
            "observation_start": start.isoformat(),
            "observation_end": end.isoformat(),
            "sort_order": "asc",
            "limit": 100000,
            "api_key": FRED_API_KEY,
            "file_type": "json",
        }
        r = requests.get(
            "https://api.stlouisfed.org/fred/series/observations",
            params=params, timeout=30,
        )
        obs = r.json().get("observations", [])
        result = [(date.fromisoformat(o["date"]), float(o["value"]))
                  for o in obs if o["value"] != "."]
        return result if result else None
    except Exception:
        return None


def fred_value_on(series_id: str, target: date) -> float | None:
    """Fetch most recent FRED observation value on or before target date."""
    result = fred_observation_on(series_id, target)
    return result[0] if result else None


def fetch_fred_macro(snapshot_date: date) -> dict[str, float | None]:
    """Fetch FRED indicators. All None if FRED_API_KEY not set."""
    if not FRED_API_KEY:
        return {k: None for k in FRED_SERIES}
    return {key: fred_value_on(series_id, snapshot_date) for key, series_id in FRED_SERIES.items()}


def fetch_macro_snapshot(snapshot_date: date) -> dict[str, float | None]:
    """Combined yfinance + FRED macro snapshot for a given date."""
    yf_data = fetch_yfinance_macro(snapshot_date)
    fred_data = fetch_fred_macro(snapshot_date)

    return {
        "treasury_10y": yf_data.get("treasury_10y"),
        "tbill_3m": yf_data.get("tbill_3m"),
        "vix": yf_data.get("vix"),
        "gold_price": yf_data.get("gold"),
        "usd_strength": yf_data.get("usd"),
        "bonds_20y": yf_data.get("bonds_20y"),
        "yield_curve": fred_data.get("yield_curve"),
        "recession_prob": fred_data.get("recession_prob"),
        "cpi_yoy": fred_data.get("cpi"),
        "fed_funds": fred_data.get("fed_funds"),
    }
