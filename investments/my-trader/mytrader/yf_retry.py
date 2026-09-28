"""Retry-with-backoff wrapper for yfinance calls, specifically for
YFRateLimitError.

Real outage caught 2026-09-28: every yfinance fetch_* function in this
codebase gives up immediately on ANY exception, including a rate limit that
clears within minutes -- that's why every one of ~310 Discovery candidates in
Goat's insider-scan-report.md showed "price unavailable" on the same run.
Confirmed live the same day: Yahoo Finance has no official API and no paid
tier that raises this limit (yfinance scrapes the same public endpoints
regardless of payment) -- backoff-and-retry is the correct, standard way to
handle a free/unofficial rate-limited API, not a workaround.

goat imports this directly (`from mytrader import yf_retry`) rather than
getting its own copy -- unlike a market-specific universe scraper (see the LSE
heartbeat handoff's "second copy per market" discussion), this is a generic
technical utility with no market-specific logic, the same class of shared
helper tickers.py's asx_variant()/lse_variant() already are.
"""

from __future__ import annotations

import time
from typing import Callable, TypeVar

T = TypeVar("T")

RETRY_DELAYS_SECONDS = (5, 15, 45)  # 3 retries -- Yahoo's rate-limit windows are
                                     # typically short (minutes, not hours), so
                                     # this absorbs a transient 429 without
                                     # materially slowing a job that fetches
                                     # dozens/hundreds of tickers in sequence.


def call(fn: Callable[[], T]) -> T:
    """Call fn() (a zero-arg callable wrapping one yfinance operation), retrying
    with backoff specifically on YFRateLimitError. Re-raises the last error if
    every retry also rate-limits, so the caller's own existing
    `try: ... except Exception: continue`/`return None` fallback still applies
    unchanged -- this only gives a *transient* rate limit one more chance
    before that fallback kicks in, it doesn't change behavior for any other
    exception (network error, bad ticker, etc.)."""
    from yfinance.exceptions import YFRateLimitError

    last_error: YFRateLimitError | None = None
    for delay in (0, *RETRY_DELAYS_SECONDS):
        if delay:
            time.sleep(delay)
        try:
            return fn()
        except YFRateLimitError as e:
            last_error = e
            continue
    raise last_error
