"""Marker 10 -- most-valuable-company milestone (e.g. Cisco passing Microsoft
17 days before the 2000 NASDAQ peak; Nvidia hitting $5.5T in 2026). Finds the
market-cap leader within the shared hot-company watchlist (watchlist.py's top-N
mega-cap names in whichever sector is currently rising) rather than scanning
the full ~500-name S&P 500 constituent list -- Shaun's own correction,
2026-08-18: a full-universe scan took ~16 minutes in practice (one sequential
yfinance call per ticker), and the marker's own historical grounding (Cisco
overtaking Microsoft was itself a hot-sector story, not a broad-market event)
supports narrowing scope this way. Reusing the watchlist means this check costs
zero extra yfinance calls beyond what watchlist.py already paid for. "Newly
firing" (a rung that wasn't already crossed on a prior run) is handled by
main.py/alerts.py's marker_key, not inside this function -- see the Phase 1
plan's Task 9 GOTCHA."""

from __future__ import annotations

from typing import Any

from mytrader.checks import CheckResult

from . import config


def check_market_cap_milestone(hot_watchlist: list[Any]) -> CheckResult:
    """hot_watchlist: the same rows watchlist.get_or_refresh_hot_watchlist
    produces (list[sqlite3.Row] or list[dict], each with 'ticker' and
    'market_cap')."""
    if not hot_watchlist:
        return CheckResult(
            name="market_cap_milestone", verdict="unknown",
            detail="hot-company watchlist is empty this run (no rising sectors, or data unavailable)",
        )

    leader = max(hot_watchlist, key=lambda row: row["market_cap"])
    leader_ticker, leader_cap = leader["ticker"], leader["market_cap"]

    rung = int(leader_cap // config.SIGNALS_MARKET_CAP_MILESTONE_STEP) * config.SIGNALS_MARKET_CAP_MILESTONE_STEP
    detail = (
        f"{leader_ticker} is the largest company in the current hot-sector watchlist "
        f"(${leader_cap / 1e12:.2f}T, most recently crossed the ${rung / 1e12:.1f}T rung)"
    )
    return CheckResult(
        name="market_cap_milestone", verdict="flag", detail=detail,
        data={"ticker": leader_ticker, "market_cap": leader_cap, "rung": rung},
    )
