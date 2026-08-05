"""News/event search check -- live catalysts (M&A offers, litigation, credit-rating
actions, leadership turnover, short-seller reports) that fundamentals-only checks
structurally cannot see. Added 2026-08-05 after comparing a ZIM deep-dive against a
third-party video: yfinance's own news feed (already fetched into TickerData.news,
previously unused by any check) carried none of ZIM's live Hapag-Lloyd takeover
story -- confirmed live, its 10 most recent items were generic Zacks-style market
recaps -- but a single web search surfaced it immediately, including a live rival
counter-bid (Sakal Group, $37.50/share) that even the video didn't have. yfinance's
news feed isn't the right data source for this; see mytrader/news_search.py for why
this uses sdk_compat's WebSearch tool instead (Codex CLI's own web_search, flat-rate
on the ChatGPT subscription under the active backend, not a new paid search API).

Opt-in, Find-only (see engine.run_assessment's include_news_events param, defaulted
False) -- same reasoning as principles_fit.py's Find-only gating: an LLM+web-search
call per ticker is too costly/slow for Monitor's daily re-check of 50+ holdings/
watchlist rows, and this is exactly the kind of thing you want on an explicit deep
dive, not a silent daily poll.

Verdict is "flag" (not "info") when something material turns up -- unlike
price_action/crash_resilience, which are deliberately never signals, a live takeover
offer, fraud allegation, or credit downgrade is real information that should suppress
opportunity.py's "looks cheap" framing via its existing risk-flag gate (Marks/
Munger risk-first: don't call something an opportunity while something unresolved
and material is happening). This check is included in engine.run_assessment's
other_checks list (not appended after, like principles_fit) specifically so
opportunity.py's gate sees it.

Known limitation: an LLM-judged "is this material" call, not a hard threshold --
same class of judgment call as principles_fit's scoring, not a numeric check like
balance_sheet.py. Search quality/recency also depends entirely on what Codex's
web_search tool surfaces on a given run; not a guaranteed-complete news feed.

Confirmed gap, not just a general caveat (2026-08-05): ZIM's Hapag-Lloyd deal drew a
real rival $37.50/share counter-bid from the Sakal Group, findable via a single plain
web search. The prompt was updated to explicitly ask about a "counter-bid"/"rival
bid" on top of an existing deal (see news_search.py's _SEARCH_PROMPT), but two
independent live runs after that change still both came back "no evidence found of a
rival bid" -- Codex CLI's web_search tool appears to be drawing on a different or
less-fresh index/result set than the WebSearch tool available directly in Claude
Code, at least for this story. This isn't a prompt-wording problem (both runs did
search the right terms) -- it's a backend-level gap between what Codex's search
surfaces and what's actually out there. Decided 2026-08-05 not to keep tuning the
prompt against this -- documenting it here instead. The check still reliably catches
the primary deal/leadership/litigation/credit signals; treat it as a strong first
pass, not a substitute for checking fast-moving developing situations directly.
"""

from __future__ import annotations

import sqlite3

from .. import news_search
from . import CheckResult


def check(ticker: str, conn: sqlite3.Connection | None) -> CheckResult:
    if conn is None:
        return CheckResult(name="news_events", verdict="unknown", detail="No database connection available")

    result = news_search.get_news_events_for_ticker(ticker, conn)
    if result is None:
        return CheckResult(
            name="news_events", verdict="unknown",
            detail="News/event search unavailable this run (search or LLM call failed)",
        )

    return CheckResult(name="news_events", verdict=result["verdict"], detail=result["detail"])
