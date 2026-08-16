from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from goat import market_hours


def _utc(y, mo, d, h, mi):
    return datetime(y, mo, d, h, mi, tzinfo=ZoneInfo("UTC"))


def test_classify_market_asx_suffix():
    assert market_hours.classify_market("GGOV.AX") == "ASX"
    assert market_hours.classify_market("ggov.ax") == "ASX"  # case-insensitive


def test_classify_market_bare_ticker_is_us():
    assert market_hours.classify_market("LULU") == "US"


def test_asx_open_during_sydney_trading_hours():
    # 2026-08-17 is a Monday; Sydney is UTC+10 in August (no DST) -- 02:00 UTC
    # = 12:00 Sydney local, inside the 10am-4pm window.
    assert market_hours.is_asx_open(_utc(2026, 8, 17, 2, 0)) is True


def test_asx_closed_outside_trading_hours():
    # 23:00 UTC 2026-08-16 = 09:00 Sydney local on 2026-08-17 -- before 10am open.
    assert market_hours.is_asx_open(_utc(2026, 8, 16, 23, 0)) is False


def test_asx_closed_on_weekend():
    # 2026-08-15 is a Saturday; 02:00 UTC = 12:00 Sydney local, would otherwise
    # be inside trading hours if not for the weekend check.
    assert market_hours.is_asx_open(_utc(2026, 8, 15, 2, 0)) is False


def test_us_market_open_during_ny_trading_hours():
    # 2026-08-17 Monday; US Eastern is UTC-4 in August (EDT) -- 15:00 UTC =
    # 11:00 EDT, inside the 9:30am-4pm window.
    assert market_hours.is_us_market_open(_utc(2026, 8, 17, 15, 0)) is True


def test_us_market_closed_outside_trading_hours():
    # 03:00 UTC = 23:00 EDT the prior day -- well outside trading hours.
    assert market_hours.is_us_market_open(_utc(2026, 8, 17, 3, 0)) is False


def test_asx_and_us_hours_never_overlap():
    # Spot-check across a full day in 5-min increments that both are never
    # simultaneously True (Sydney daytime is US nighttime and vice versa).
    start = _utc(2026, 8, 17, 0, 0)
    for i in range(288):  # 24h in 5-min steps
        t = start + timedelta(minutes=5 * i)
        assert not (market_hours.is_asx_open(t) and market_hours.is_us_market_open(t))
