"""Marker 7 -- retail piles into leverage. NOTE (read before enabling this in
main.py's daily run -- flagged for Shaun's explicit sign-off, see this plan's NOTES):
this measures CBOE equity options positioning (the put/call ratio), a DIFFERENT
mechanism than the source video's framing (record ETF inflows / leveraged-fund flows).
No free structured fund-flow feed was reachable (ICI's stats page 403'd; yfinance's
shares-outstanding history returned None for leveraged ETF tickers) -- this is a
related-but-not-identical proxy: a low put/call ratio (more speculative call-buying)
is a reasonable signal of retail leverage-seeking behavior, not the same thing as fund
inflows.

Data source, confirmed live 2026-08-18 during Phase 3 planning (an upgrade over the
Phase 3 handoff's own "needs a live spike" assessment): cboe.com's daily options
market-statistics page is server-rendered by Next.js and embeds a JSON blob inside a
`self.__next_f.push(...)` script tag containing `"ratios":[{"name":"EQUITY PUT/CALL
RATIO","value":"0.65"}, ...]` -- NOT HTML-table-only as the handoff assumed. A single
targeted regex against the escaped JSON text extracts the field directly (mirrors
credit_spread_issuer.py's _CUSIP_RE -- regex out the one field needed, don't parse the
whole document). CBOE exposes no historical series for this ratio (today's reading
only) -- this package accumulates its own daily history via signals_putcall_history,
the same "no source-side history, build our own" shape credit_spread_issuer.py uses for
Marker #12's spread history."""

from __future__ import annotations

import re
import sqlite3
import statistics

import requests
from mytrader.checks import CheckResult

from . import config, db

_CBOE_URL = "https://www.cboe.com/us/options/market_statistics/daily/"
_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
# EQUITY PUT/CALL RATIO's escaped-JSON field, confirmed live 2026-08-18 against the real
# page: ...\"name\":\"EQUITY PUT/CALL RATIO\",\"value\":\"0.65\"... -- match the escaped
# quotes literally (\\\") since the page embeds JSON-as-a-JS-string-literal, not raw JSON.
_PUTCALL_RE = re.compile(
    r'EQUITY PUT/CALL RATIO\\+"\s*,\s*\\+"value\\+"\s*:\s*\\+"([0-9.]+)\\+"'
)


def _fetch_putcall_ratio_live() -> float | None:
    try:
        r = requests.get(_CBOE_URL, headers=_HEADERS, timeout=20)
        if r.status_code != 200:
            return None
        match = _PUTCALL_RE.search(r.text)
        if match is None:
            return None
        return float(match.group(1))
    except Exception:
        return None


def check_retail_leverage(conn: sqlite3.Connection) -> CheckResult:
    ratio = _fetch_putcall_ratio_live()
    if ratio is None:
        return CheckResult(
            name="retail_leverage", verdict="unknown",
            detail="CBOE equity put/call ratio unavailable this run (fetch or parse failed)",
        )

    history_window = max(config.SIGNALS_PUTCALL_MIN_HISTORY_DAYS * 3, 90)
    prior_rows = db.get_putcall_history(conn, history_window)
    db.record_putcall_ratio(conn, ratio=ratio)

    if len(prior_rows) < config.SIGNALS_PUTCALL_MIN_HISTORY_DAYS:
        return CheckResult(
            name="retail_leverage", verdict="unknown",
            detail=f"Equity put/call ratio {ratio:.2f} -- accumulating baseline, "
                   f"day {len(prior_rows) + 1} of {config.SIGNALS_PUTCALL_MIN_HISTORY_DAYS} "
                   f"(different mechanism than ETF/fund-flow data -- see module docstring)",
            data={"ratio": ratio, "history_days": len(prior_rows)},
        )

    prior_values = [row["ratio"] for row in prior_rows]
    mean = statistics.mean(prior_values)
    stdev = statistics.pstdev(prior_values)
    zscore = (ratio - mean) / stdev if stdev else 0.0
    flagged = stdev > 0 and zscore <= config.SIGNALS_PUTCALL_FLAG_ZSCORE
    detail = (
        f"Equity put/call ratio {ratio:.2f} (z={zscore:.2f} vs trailing "
        f"{len(prior_values)}d mean {mean:.2f}) -- options positioning proxy, not the "
        f"video's ETF/fund-flow mechanism"
    )
    return CheckResult(
        name="retail_leverage", verdict="flag" if flagged else "ok", detail=detail,
        data={"ratio": ratio, "zscore": zscore, "mean": mean},
    )
