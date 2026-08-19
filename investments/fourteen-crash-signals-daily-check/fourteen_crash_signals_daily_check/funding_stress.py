"""Marker 13 -- funding markets start choking. Zero new DB state -- mirrors
credit_spread.py's own "recompute entirely from a live FRED history fetch every run"
pattern exactly, confirmed live 2026-08-18 (Phase 3 handoff): all series fetched via
scripts.macro.fred_series_range, the exact function credit_spread.py already imports.

Primary signal: DCPN3M - DTB3 (3-Month AA Nonfinancial Commercial Paper Rate minus
3-Month Treasury Bill rate), a direct funding-market-stress spread -- widens when
short-term lenders demand more premium to fund non-bank borrowers, the textbook
mechanism the video describes (e.g. the 2007 Bear Stearns fund episode). Flagged on a
z-score vs. its own trailing year, not a fixed absolute level, since "normal" for this
spread shifts with the broader rate environment.

Secondary corroboration: STLFSI4 (St. Louis Fed) and NFCI (Chicago Fed), two
independent broad financial-stress indices -- flag if either also crosses its own
z-score threshold, corroborating rather than replacing the primary spread signal.
"""

from __future__ import annotations

import statistics
from datetime import date, timedelta

from mytrader.checks import CheckResult
from scripts.macro import fred_series_range

from . import config


def _zscore_of_latest(history: list[tuple[date, float]]) -> tuple[float, float] | None:
    """Returns (latest_value, zscore) using the full history's own mean/stdev, or None
    if there are fewer than 2 points (stdev undefined) or stdev is 0 (flat series)."""
    if len(history) < 2:
        return None
    values = [v for _, v in history]
    mean = statistics.mean(values)
    stdev = statistics.pstdev(values)
    if stdev == 0:
        return None
    latest = values[-1]
    return latest, (latest - mean) / stdev


def _fetch_spread_zscore() -> tuple[float, float] | None:
    cp_series, tbill_series = config.SIGNALS_FUNDING_SPREAD_SERIES
    today = date.today()
    start = today - timedelta(days=config.SIGNALS_FUNDING_SPREAD_LOOKBACK_DAYS)
    cp_history = fred_series_range(cp_series, start, today)
    tbill_history = fred_series_range(tbill_series, start, today)
    if not cp_history or not tbill_history:
        return None
    tbill_by_date = dict(tbill_history)
    spread_history = [
        (d, v - tbill_by_date[d]) for d, v in cp_history if d in tbill_by_date
    ]
    return _zscore_of_latest(spread_history)


def _fetch_index_zscore(series_id: str) -> tuple[float, float] | None:
    today = date.today()
    start = today - timedelta(days=config.SIGNALS_FUNDING_SPREAD_LOOKBACK_DAYS)
    history = fred_series_range(series_id, start, today)
    if not history:
        return None
    return _zscore_of_latest(history)


def check_funding_stress() -> CheckResult:
    spread_result = _fetch_spread_zscore()
    if spread_result is None:
        return CheckResult(
            name="funding_stress", verdict="unknown",
            detail="FRED commercial-paper/Treasury spread data unavailable "
                   "(FRED_API_KEY not set, series unavailable, or insufficient history)",
        )
    spread_value, spread_z = spread_result
    spread_flag = spread_z >= config.SIGNALS_FUNDING_SPREAD_FLAG_ZSCORE

    index_flags = []
    for series_id in config.SIGNALS_FUNDING_STRESS_INDEX_SERIES:
        idx_result = _fetch_index_zscore(series_id)
        if idx_result is not None:
            idx_value, idx_z = idx_result
            if idx_z >= config.SIGNALS_FUNDING_STRESS_FLAG_ZSCORE:
                index_flags.append(f"{series_id}={idx_value:.3f} (z={idx_z:.2f})")

    detail = (
        f"CP-Treasury spread (DCPN3M-DTB3) {spread_value:.2f}pp (z={spread_z:.2f} vs "
        f"trailing {config.SIGNALS_FUNDING_SPREAD_LOOKBACK_DAYS}d)"
    )
    if index_flags:
        detail += f"; corroborating stress index(es) elevated: {', '.join(index_flags)}"
    verdict = "flag" if spread_flag or index_flags else "ok"
    return CheckResult(
        name="funding_stress", verdict=verdict, detail=detail,
        data={"spread": spread_value, "spread_zscore": spread_z, "index_flags": index_flags},
    )
