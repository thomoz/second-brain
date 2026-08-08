"""COT (Commitments of Traders) large-speculator positioning for COMEX gold
futures, read from the CFTC's public Socrata API (free, no login/API key
required, confirmed live 2026-08-08). Positioning/sentiment data this feature
had zero coverage of before this module -- identified as a real gap in
conversation (see .agent/plans/gold-tracker-phase2-outlook.md history):
everything else in the Gold Outlook is derived from price or macro-economic
data; this is the first signal built from what large speculators are actually
doing with their capital.

Weekly cadence (CFTC publishes every Friday, data as-of the prior Tuesday) --
distinct from every other signal in this feature, which is daily or has daily
proxies. The COT Index (Larry Williams' original formulation, a standard,
widely-cited methodology -- not an invented threshold) turns the raw net
non-commercial position into a 0-100 rolling percentile over a trailing
COT_LOOKBACK_WEEKS window. Crowded positioning (index >= 90 or <= 10) is the
classic contrarian read large speculators themselves watch -- whether it's
actually bullish or bearish for forward returns is NOT assumed here; that's
determined empirically by gold_backtest.py's state-conditioned backtest and
gold_outlook.py's win-rate-based direction, same as every other signal.
"""

from __future__ import annotations

import pandas as pd
import requests

from . import config
from .checks import CheckResult


def _fetch_cot_history() -> pd.Series | None:
    """Full weekly net non-commercial ("large speculator") position history for
    COMEX gold futures, ascending by report date. Net = long - short contracts
    (spread positions excluded, matching the standard COT Index convention)."""
    try:
        params = {
            "$where": f"market_and_exchange_names='{config.COT_MARKET_NAME}'",
            "$order": "report_date_as_yyyy_mm_dd ASC",
            "$limit": "5000",
            "$select": "report_date_as_yyyy_mm_dd,noncomm_positions_long_all,noncomm_positions_short_all",
        }
        r = requests.get(config.COT_API_URL, params=params, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code != 200:
            return None
        rows = r.json()
        if not rows:
            return None
        dates = [pd.Timestamp(row["report_date_as_yyyy_mm_dd"][:10]) for row in rows]
        net = [
            float(row["noncomm_positions_long_all"]) - float(row["noncomm_positions_short_all"])
            for row in rows
        ]
        return pd.Series(net, index=pd.DatetimeIndex(dates))
    except Exception:
        return None


def cot_index_series(net: pd.Series, lookback_periods: int = config.COT_LOOKBACK_WEEKS) -> pd.Series:
    """Larry Williams' COT Index: (current - rolling_min) / (rolling_max -
    rolling_min) * 100 over a trailing lookback_periods (weekly reports)
    window. 100 = current net position is the most bullish (longest) it's
    been in the lookback window; 0 = most bearish (shortest). NaN until
    lookback_periods of history exist, and wherever the window's range is 0
    (min == max, degenerate)."""
    rolling_min = net.rolling(lookback_periods, min_periods=lookback_periods).min()
    rolling_max = net.rolling(lookback_periods, min_periods=lookback_periods).max()
    span = rolling_max - rolling_min
    return ((net - rolling_min) / span * 100).where(span != 0)


def classify_cot_state(index_value: float) -> str:
    if index_value >= config.COT_EXTREME_LONG_PCT:
        return "extreme_long"
    if index_value <= config.COT_EXTREME_SHORT_PCT:
        return "extreme_short"
    return "neutral"


def compute_today_cot() -> dict | None:
    net = _fetch_cot_history()
    if net is None or len(net) < config.COT_LOOKBACK_WEEKS:
        return None
    index_series = cot_index_series(net)
    latest = index_series.dropna()
    if latest.empty:
        return None
    value = float(latest.iloc[-1])
    as_of = latest.index[-1].date()
    return {"cot_index": round(value, 1), "state": classify_cot_state(value), "as_of": as_of.isoformat()}


def check_cot_positioning() -> CheckResult:
    result = compute_today_cot()
    if result is None:
        return CheckResult(
            name="cot_positioning", verdict="unknown",
            detail="CFTC COT data unavailable (fetch failed or insufficient history)",
        )
    state = result["state"]
    direction = state if state != "neutral" else None
    detail = (
        f"Large speculators' COT Index at {result['cot_index']} (as of {result['as_of']}, "
        f"{config.COT_LOOKBACK_WEEKS}-week lookback)"
    )
    if state != "neutral":
        detail += f" -- {state.replace('_', ' ')}, a classic crowded-positioning read"
    verdict = "flag" if state != "neutral" else "ok"
    return CheckResult(
        name="cot_positioning", verdict=verdict, detail=detail,
        data={"cot_index": result["cot_index"], "as_of": result["as_of"], "direction": direction},
    )
