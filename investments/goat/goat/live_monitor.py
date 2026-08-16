"""Goat's intraday 150DMA live check -- runs frequently during market hours
(see market_hours.py) and reuses the exact same goat_alert_history dedup as
the daily monitor (monitor.reconcile_alerts) so the two checks can never
double-alert for the same crossing. See investments/goat/HANDOFF.md's
"Intraday 150DMA Alerting" section."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd
from mytrader import db as mt_db, market_data

from . import config, db, exit_check, market_hours, price_history
from .monitor import reconcile_alerts


def _completed_closes_only(close: pd.Series, tz_name: str) -> pd.Series:
    """Defensive guard: yfinance daily history can include a partial,
    still-updating bar for the current trading day when fetched mid-session.
    The 150-day MA must only ever be built from completed days (see
    exit_check.check_150dma_exit_live's docstring), so drop the trailing row
    if its date matches "today" in the ticker's own exchange-local calendar
    day. close.index is tz-naive by the time price_history.fetch_close_history
    returns it (see that function's tz_localize(None) call), so compare
    against a tz-aware "today" computed in the exchange's own timezone, not
    the machine's local/UTC date."""
    if close.empty:
        return close
    today_local = datetime.now(ZoneInfo(tz_name)).date()
    if close.index[-1].date() == today_local:
        return close.iloc[:-1]
    return close


def run_live_monitor(conn: sqlite3.Connection) -> dict[str, Any]:
    asx_open = market_hours.is_asx_open()
    us_open = market_hours.is_us_market_open()

    new_alerts: list[dict[str, Any]] = []
    checked = 0

    if asx_open or us_open:
        holdings = mt_db.get_all_holdings(conn)
        for row in holdings:
            ticker = row["ticker"]
            market = market_hours.classify_market(ticker)
            if (market == "ASX" and not asx_open) or (market == "US" and not us_open):
                continue
            tz_name = config.GOAT_ASX_TZ if market == "ASX" else config.GOAT_US_TZ
            try:
                live_price = market_data.fetch_current_price(ticker)
                if live_price is None:
                    print(f"[goat-live-monitor] no live price for {ticker}, skipping")
                    continue
                close = price_history.fetch_close_history(ticker, config.GOAT_MA_HISTORY_LOOKBACK_DAYS)
                if close is None:
                    print(f"[goat-live-monitor] no price history for {ticker}, skipping")
                    continue
                close = _completed_closes_only(close, tz_name)
                check = exit_check.check_150dma_exit_live(ticker, close, live_price)
                new_alerts.extend(reconcile_alerts(ticker, [check], conn))
                checked += 1
            except Exception as e:
                print(f"[goat-live-monitor] error checking {ticker}: {e}")

    return {
        "checked_holdings": checked,
        "new_alerts": new_alerts,
        "open_alerts": [dict(a) for a in db.get_open_goat_alerts(conn)],
    }
