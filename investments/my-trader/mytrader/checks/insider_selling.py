"""Insider selling check -- Find-only deep-dive read of this ticker's own recent
open-market Form 4 sales (OpenInsider). Added 2026-08-19 after Shaun asked whether
Chevron's Michael Wirth selling 90%+ of his CVX position would have been caught by
the existing insider-trading tooling -- it wouldn't have: goat's Holdings Watch
(goat/insider_scan.py) only tracks tickers Shaun already holds, so a red flag on a
ticker he's *considering* buying was invisible. This check closes that gap at Find
time (see engine.run_assessment's include_insider_selling param), the same
"look before you buy" placement as news_events.py/principles_fit.py.

Reuses mytrader.openinsider's screener scraper directly (moved here from goat
2026-08-19 -- goat and fourteen_crash_signals_daily_check both already depend on
my-trader, not the reverse, so this was the correct import direction; both
packages' own call sites were updated to `from mytrader import openinsider`).

Deliberately simpler than goat's insider_scan.run_holdings_watch: a one-shot
lookback (config.INSIDER_SELLING_LOOKBACK_DAYS, 30 days -- wider than goat's 5-day
incremental-poll window, since Find has no persisted state between runs to catch
what a narrow window would miss) with a single pct-of-position flag threshold, not
goat's first-sale/repeat-sale two-tier gate (that gate needs cross-run history a
one-shot check doesn't have). Every qualifying sale in the window is reported in
the detail regardless of whether it individually flags.

Verdict is "flag" (not "info") when it fires, participating in opportunity.py's
existing risk-flag gate -- same reasoning as news_events.py: a large insider sale
is real information that should suppress a "looks cheap" read, not just a
footnote."""

from __future__ import annotations

from .. import config, openinsider
from . import CheckResult


def check(ticker: str) -> CheckResult:
    rows = openinsider.fetch_screener_filings(
        [ticker], "S", config.INSIDER_SELLING_MIN_VALUE,
        filing_date_days=config.INSIDER_SELLING_LOOKBACK_DAYS,
    )
    if rows is None:
        return CheckResult(
            name="insider_selling", verdict="unknown",
            detail="OpenInsider fetch failed -- insider-selling data unavailable this run",
        )
    if not rows:
        return CheckResult(
            name="insider_selling", verdict="ok",
            detail=f"No open-market insider sale filings in the trailing "
                   f"{config.INSIDER_SELLING_LOOKBACK_DAYS} days",
        )

    flagged = [
        r for r in rows
        if r.get("pct_owned_change") is not None
        and abs(r["pct_owned_change"]) >= config.INSIDER_SELLING_FLAG_PCT_THRESHOLD
    ]
    lines = []
    for r in sorted(rows, key=lambda r: r.get("trade_date", ""), reverse=True):
        pct_clause = (
            f" ({abs(r['pct_owned_change']):.0f}% of position)"
            if r.get("pct_owned_change") is not None else ""
        )
        lines.append(
            f"{r.get('insider_name', 'Unknown insider')} sold ${r['value']:,.0f}{pct_clause} "
            f"on {r.get('trade_date', 'unknown date')}"
        )
    verdict = "flag" if flagged else "ok"
    return CheckResult(
        name="insider_selling", verdict=verdict, detail="; ".join(lines),
        data={"sales": rows, "flagged_count": len(flagged)},
    )
