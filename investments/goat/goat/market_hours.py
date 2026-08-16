"""Market-hours gating for Goat's intraday live check -- decides which holdings'
market is currently open, so the live-check poller only fetches/checks tickers
whose market is genuinely trading right now. See HANDOFF.md's "Intraday 150DMA
Alerting" section, resolved design questions 2-3."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from . import config


def _is_open(now: datetime | None, tz_name: str, open_hm: tuple[int, int], close_hm: tuple[int, int]) -> bool:
    tz = ZoneInfo(tz_name)
    local = (now or datetime.now(tz)).astimezone(tz)
    if local.weekday() >= 5:  # Saturday=5, Sunday=6
        return False
    open_t = local.replace(hour=open_hm[0], minute=open_hm[1], second=0, microsecond=0)
    close_t = local.replace(hour=close_hm[0], minute=close_hm[1], second=0, microsecond=0)
    return open_t <= local <= close_t


def is_asx_open(now: datetime | None = None) -> bool:
    """`now` must be tz-aware if provided -- naive datetimes misbehave under
    .astimezone(). Defaults to the real current time in the ASX's own timezone."""
    return _is_open(now, config.GOAT_ASX_TZ, config.GOAT_ASX_MARKET_OPEN, config.GOAT_ASX_MARKET_CLOSE)


def is_us_market_open(now: datetime | None = None) -> bool:
    """`now` must be tz-aware if provided -- naive datetimes misbehave under
    .astimezone(). Defaults to the real current time in the US market's own timezone."""
    return _is_open(now, config.GOAT_US_TZ, config.GOAT_US_MARKET_OPEN, config.GOAT_US_MARKET_CLOSE)


def classify_market(ticker: str) -> str:
    """'ASX' or 'US', from the ticker's own .AX suffix -- matches the real
    holdings-table convention (see investments/my-trader/holdings.md: GGOV.AX
    vs. bare AG/LULU/V) and mytrader.tickers.asx_variant's own assumption."""
    return "ASX" if ticker.strip().upper().endswith(".AX") else "US"
