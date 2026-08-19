"""Marker 3 -- seller finances buyer (vendor/circular financing, e.g. Nvidia's $30B
OpenAI stake, the Nvidia+Microsoft+Anthropic deal, Coreweave's unsold-capacity
commitment). No free structured source exists for this -- confirmed by live-testing
EDGAR full-text search for vendor-financing-shaped phrases during the Phase 3 handoff
(e.g. "capacity purchase agreement" in 8-Ks returned 7 hits, dominated by an unrelated
Alaska Air Group filing, not tech vendor-financing deals). There is no XBRL tag, form
type, or SIC-scoped search that captures "Company A invests in Company B who then buys
Company A's product" as a discrete, structured fact -- every real example was identified
from trade-press coverage of a specific named deal, not a queryable dataset.

Same shape as Marker #9 before it shipped real date-logic: a permanent
verdict="unknown" maintained flag, not a placeholder for more research -- this is the
honest, final answer for this marker, confirmed with Shaun 2026-08-18 (Phase 3 handoff).
No polling cadence makes this into real automation; there is nothing to poll."""

from __future__ import annotations

from typing import Any

from mytrader.checks import CheckResult


def check_seller_financing(hot_watchlist: list[Any]) -> CheckResult:
    tickers = [row["ticker"] for row in hot_watchlist]
    if tickers:
        detail = (
            "No automatable source exists for vendor/circular-financing deals -- "
            f"periodically news-scan the current hot watchlist yourself: {', '.join(tickers)}"
        )
    else:
        detail = (
            "No automatable source exists for vendor/circular-financing deals, and no "
            "hot-watchlist companies are resolved this run to suggest news-scanning."
        )
    return CheckResult(
        name="seller_financing", verdict="unknown", detail=detail,
        data={"tickers": tickers},
    )
