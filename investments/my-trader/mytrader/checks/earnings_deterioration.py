"""Earnings Deterioration Watch check -- Find/Monitor opt-in wrapper around
mytrader/earnings_watch.py's 3 signal functions (estimate trend, earnings-relevant
8-Ks, guidance/commentary search). See earnings_watch.py's module docstring for the
full feature description and cost reasoning.

One CheckResult, itemized per signal (Decision #3 in
.agent/plans/earnings-deterioration-watch.md) -- mirrors checks/opportunity.py's own
"reasons list + (N independent signals) suffix" shape exactly, rather than adding 3
new top-level check names to every run_assessment call site/test. `.data["signals"]`
carries the full structured per-signal dict for the daily report renderer's reuse.

Aggregate verdict: "flag" if any sub-signal flagged, "unknown" if ALL sub-signals are
unknown/no-data (the natural ETF/commodity-trust degradation path -- no special-case
ETF branch), else "ok".

Note: the estimate-trend signal reads db.get_estimate_history, which a fresh Find
lookup on a ticker with no recorded daily snapshots will usually find empty --
compute_estimate_trend correctly reads "insufficient history" in that case, not a
bug. The trend signal is inherently more of a Monitor/daily-job signal than a
one-shot Find one, but stays wired into Find for consistency, and a ticker Shaun
already holds (and the daily Earnings Watch job has been running against) WILL have
real history by the time Find is used on it.

Opt-in, Find-only (see engine.run_assessment's include_earnings_watch param,
defaulted False) -- same LLM+WebSearch-per-ticker cost reasoning as
checks/news_events.py's own module docstring; the standalone daily job
(earnings_watch.run_earnings_watch) is the scheduled, holdings-only counterpart,
never folded into Monitor's own re-check loop.
"""

from __future__ import annotations

import sqlite3
from datetime import date, timedelta

from .. import config, earnings_watch, news_search
from . import CheckResult


def check(ticker: str, data, conn: sqlite3.Connection | None) -> CheckResult:
    if conn is None:
        return CheckResult(
            name="earnings_deterioration", verdict="unknown",
            detail="No database connection available",
        )

    signals: dict[str, object] = {}
    reasons: list[str] = []
    any_known = False

    trend = earnings_watch.compute_estimate_trend(conn, ticker)
    signals["estimate_trend"] = trend
    if trend["verdict"] != "unknown":
        any_known = True
    if trend["verdict"] == "flag":
        reasons.append(f"Estimate trend: {trend['detail']}")

    since = date.today() - timedelta(days=config.EARNINGS_WATCH_8K_LOOKBACK_DAYS)
    eight_ks = earnings_watch.fetch_new_earnings_8ks(ticker, conn, since=since)
    signals["8k_filings"] = eight_ks
    if eight_ks is not None:
        any_known = True
        if eight_ks:
            items = "; ".join(
                f"{f['form']} ({f['items']}) filed {f['filing_date']}" for f in eight_ks
            )
            reasons.append(f"Earnings-relevant 8-K(s): {items}")

    guidance = news_search.get_earnings_guidance_for_ticker(ticker, conn)
    signals["guidance"] = guidance
    if guidance is not None:
        any_known = True
        if guidance["verdict"] == "flag":
            reasons.append(f"Guidance/commentary: {guidance['detail']}")

    if reasons:
        confluence = f" ({len(reasons)} independent signals)" if len(reasons) > 1 else ""
        return CheckResult(
            name="earnings_deterioration", verdict="flag",
            detail="; ".join(reasons) + confluence, data={"signals": signals},
        )
    if not any_known:
        return CheckResult(
            name="earnings_deterioration", verdict="unknown",
            detail="No earnings-deterioration data available this run (no estimate "
                   "history, no SEC CIK match, guidance search unavailable)",
            data={"signals": signals},
        )
    return CheckResult(
        name="earnings_deterioration", verdict="ok",
        detail="No earnings-deterioration signals this run", data={"signals": signals},
    )
