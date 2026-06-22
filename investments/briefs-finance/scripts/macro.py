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


def fred_value_on(series_id: str, target: date) -> float | None:
    """Fetch most recent FRED observation on or before target date."""
    if not FRED_API_KEY:
        return None
    from datetime import timedelta
    try:
        r = requests.get(
            "https://api.stlouisfed.org/fred/series/observations",
            params={
                "series_id": series_id,
                "observation_start": (target - timedelta(days=45)).isoformat(),
                "observation_end": target.isoformat(),
                "sort_order": "desc",
                "limit": 1,
                "api_key": FRED_API_KEY,
                "file_type": "json",
            },
            timeout=10,
        )
        obs = r.json().get("observations", [])
        val = obs[0]["value"] if obs else None
        return float(val) if val and val != "." else None
    except Exception:
        return None


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
