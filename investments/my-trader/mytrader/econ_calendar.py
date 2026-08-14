"""Upcoming economic-release calendar (CPI, PPI, jobs data) -- added 2026-08-13,
Shaun: "I also need alerts to any major releases that are due within the next 48
hours eg cpi, ppi reports, job data. That way I can deep dive them myself to see if
i need to take action." Distinct from macro_indicators.py's CPI checks, which report
*realized* figures after the fact -- this is forward-looking: what's scheduled to
print in the next 48 hours, not what already printed.

Sourced from FRED's own /fred/releases/dates endpoint (the same api.stlouisfed.org
FRED_API_KEY already used everywhere else in this codebase, e.g. scripts/macro.py's
fred_observation_on) rather than a hardcoded release-id list -- filtered client-side
by release_name keyword match against the three release types Shaun named
explicitly: CPI ("Consumer Price Index"), PPI ("Producer Price Index"), and the
monthly jobs report ("Employment Situation" -- nonfarm payrolls + unemployment rate,
the single most market-moving jobs release). Weekly jobless claims deliberately
excluded -- it fires almost every week, which would spam this section on nearly
every Monitor run rather than flag something rare/notable.

Rendered as a live snapshot every run (not deduped through alert_history like the
per-ticker/macro risk flags) -- same reasoning as opportunity.py's "interesting"
verdict: the same real-world release should keep showing up on every run it falls
within the 48-hour window, not just once.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from scripts.config import FRED_API_KEY

_RELEASE_KEYWORDS = ("Consumer Price Index", "Producer Price Index", "Employment Situation")


def fetch_upcoming_releases(days_ahead: int = 2, today: date | None = None) -> list[dict[str, Any]]:
    """Returns [{"release_name": str, "date": "YYYY-MM-DD", "days_until": int}, ...]
    for CPI/PPI/jobs releases scheduled within the next `days_ahead` days (inclusive
    of today), sorted by date. Empty list if FRED_API_KEY is unset or the request
    fails -- same graceful-degradation pattern as every other FRED-backed check in
    this codebase."""
    if not FRED_API_KEY:
        return []
    start = today or date.today()
    end = start + timedelta(days=days_ahead)
    try:
        import requests

        r = requests.get(
            "https://api.stlouisfed.org/fred/releases/dates",
            params={
                "api_key": FRED_API_KEY,
                "file_type": "json",
                "realtime_start": start.isoformat(),
                "realtime_end": end.isoformat(),
                "include_release_dates_with_no_data": "true",
                "sort_order": "asc",
            },
            timeout=10,
        )
        entries = r.json().get("release_dates", [])
    except Exception:
        return []

    seen: set[tuple[str, str]] = set()
    matched: list[dict[str, Any]] = []
    for e in entries:
        name = e.get("release_name", "")
        release_date_str = e.get("date")
        if not release_date_str or not any(kw.lower() in name.lower() for kw in _RELEASE_KEYWORDS):
            continue
        key = (name, release_date_str)
        if key in seen:
            continue
        seen.add(key)
        release_date = date.fromisoformat(release_date_str)
        matched.append({
            "release_name": name,
            "date": release_date_str,
            "days_until": (release_date - start).days,
        })

    return sorted(matched, key=lambda m: m["date"])
