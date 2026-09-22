from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

from goat.staleness_check import WatchedReport, check_stale_reports


def _touch(path, age_days: float = 0.0, reference: datetime | None = None):
    path.write_text("content", encoding="utf-8")
    reference = reference or datetime.now(timezone.utc)
    mtime = (reference - timedelta(days=age_days)).timestamp()
    os.utime(path, (mtime, mtime))


def test_fresh_report_is_not_flagged(tmp_path):
    p = tmp_path / "fresh.md"
    _touch(p, age_days=0.5)
    warnings = check_stale_reports((WatchedReport(p, 2, "Fresh Tool"),))
    assert warnings == []


def test_stale_report_is_flagged(tmp_path):
    p = tmp_path / "stale.md"
    _touch(p, age_days=5)
    warnings = check_stale_reports((WatchedReport(p, 2, "Stale Tool"),))
    assert len(warnings) == 1
    assert "Stale Tool" in warnings[0]
    assert "stale.md" in warnings[0]
    assert "5d ago" in warnings[0]


def test_report_exactly_at_boundary_is_not_flagged(tmp_path):
    """age > max_age_days is the gate (strictly greater), not >= -- ordinary daily
    timing jitter around the exact cadence must never false-positive. `now` is
    pinned to the same instant used to compute the mtime -- two independent
    datetime.now() calls a few microseconds apart would make "exactly 2 days old"
    flaky by definition."""
    p = tmp_path / "boundary.md"
    now = datetime.now(timezone.utc)
    _touch(p, age_days=2, reference=now)
    warnings = check_stale_reports((WatchedReport(p, 2, "Boundary Tool"),), now=now)
    assert warnings == []


def test_missing_report_is_flagged(tmp_path):
    p = tmp_path / "does-not-exist.md"
    warnings = check_stale_reports((WatchedReport(p, 2, "Missing Tool"),))
    assert len(warnings) == 1
    assert "missing entirely" in warnings[0]


def test_multiple_reports_only_stale_ones_flagged(tmp_path):
    fresh = tmp_path / "fresh.md"
    stale = tmp_path / "stale.md"
    _touch(fresh, age_days=0.1)
    _touch(stale, age_days=10)
    warnings = check_stale_reports((
        WatchedReport(fresh, 2, "Fresh Tool"),
        WatchedReport(stale, 2, "Stale Tool"),
    ))
    assert len(warnings) == 1
    assert "Stale Tool" in warnings[0]


def test_default_watched_reports_list_is_nonempty_and_unique_paths():
    from goat.staleness_check import WATCHED_REPORTS

    assert len(WATCHED_REPORTS) >= 10
    paths = [r.path for r in WATCHED_REPORTS]
    assert len(paths) == len(set(paths))
