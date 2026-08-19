"""Marker 6 -- record IPO/equity issuance. Market-wide, not per-issuer (hot-watchlist
mega-caps aren't IPO candidates) -- no hot_watchlist parameter needed. Uses the same
edgar_fulltext_search_count helper as Marker #1 (see debt_issuance.py / sec_filings.py),
but compares a trailing window against the SAME CALENDAR WINDOW one year prior (a direct
YoY comparison, mirroring mytrader.margin_debt's own YoY shape) rather than a rolling
multi-period baseline -- confirmed live 2026-08-18 this is a real, moving signal: S-1
filings over an identical 18-day August window differ meaningfully year over year (85 in
2026 vs 145 in 2025) -- notably LOWER in 2026, a reminder this metric doesn't move
monotonically upward and a naive "always flag on growth" implementation would need real
data, not an assumption, to calibrate.

Two sub-signals, both flagged independently then combined: S-1 (intent-to-register --
used by a long tail of small-cap/shell registrants too, a pace/activity proxy not a
"big-name IPO" proxy) and 424B4 (final IPO prospectus, i.e. actually priced -- a cleaner,
stronger filter, confirmed live and queryable the same way)."""

from __future__ import annotations

from datetime import date, timedelta

from mytrader import sec_filings
from mytrader.checks import CheckResult

from . import config


def _windowed_count(forms: str, start: date, end: date) -> int | None:
    return sec_filings.edgar_fulltext_search_count(forms, startdt=start, enddt=end)


def _sub_signal(forms: str, label: str) -> tuple[str, bool] | None:
    today = date.today()
    window_start = today - timedelta(days=config.SIGNALS_IPO_FILING_WINDOW_DAYS)
    current = _windowed_count(forms, window_start, today)
    if current is None:
        return None
    prior_end = today - timedelta(days=365)
    prior_start = prior_end - timedelta(days=config.SIGNALS_IPO_FILING_WINDOW_DAYS)
    prior = _windowed_count(forms, prior_start, prior_end)
    if prior is None:
        return f"{label}: {current} filing(s) (no prior-year comparison available)", False

    ratio = current / prior if prior else None
    flagged = ratio is not None and ratio >= config.SIGNALS_IPO_FILING_FLAG_RATIO
    detail = (
        f"{label}: {current} filing(s) in the trailing {config.SIGNALS_IPO_FILING_WINDOW_DAYS}d "
        f"vs {prior} in the same window a year ago"
        + (f" ({ratio:.2f}x)" if ratio is not None else "")
    )
    return detail, flagged


def check_ipo_issuance() -> CheckResult:
    s1_result = _sub_signal("S-1", "S-1 (intent to register)")
    b4_result = _sub_signal("424B4", "424B4 (priced IPO)")
    if s1_result is None and b4_result is None:
        return CheckResult(
            name="ipo_issuance", verdict="unknown",
            detail="EDGAR full-text search unavailable for both S-1 and 424B4 sub-signals",
        )
    details = [r[0] for r in (s1_result, b4_result) if r is not None]
    flagged = any(r[1] for r in (s1_result, b4_result) if r is not None)
    return CheckResult(
        name="ipo_issuance", verdict="flag" if flagged else "ok",
        detail="; ".join(details),
        data={"s1": s1_result, "424b4": b4_result},
    )
