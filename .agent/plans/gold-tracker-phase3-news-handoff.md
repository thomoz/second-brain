# Handoff: Gold Outlook Phase 3 — News/Catalyst Awareness

## Status: Not started — design proposed 2026-08-07, ready for `/plan-feature`

## Context

Shaun reviewed a real Gold Outlook run where gold actually had a bullish day, but the
Today/Tomorrow section called "bearish lean (6/8)". Root-caused (see conversation
2026-08-07): the read wasn't wrong on its own terms, but two structural gaps made a
weak, borderline call look more confident than it was —

1. Every technical signal's edge over baseline was a few basis points (0.04-0.07% vs
   a 0.06% baseline) with win-rates barely above a coin flip (51-55%) — a real but
   tiny historical edge, not a strong call.
2. The Outlook has **zero live news/event awareness** — it only sees yesterday's
   closing price state and macro data, never a same-day catalyst (Fed comment,
   geopolitical event, surprise data release, big single-day yield/dollar move,
   central-bank gold buying).

Shaun: "Combination of historical data and the chart tools that master investors use
along with news that can affect the price action should be enough to give it more
confidence." Historical data (`gold_backtest.py`) and chart tools
(`gold_technicals.py`) are already built (Phase 1 + 2, shipped 2026-08-07). This
phase adds the missing third leg: live news/catalyst awareness, specifically for
gold — not a new backtested vote, but a visible confidence caveat and context line
so a day like this one is flagged rather than presented as a clean, confident split.

## Design (recommended — resolve any open items at `/plan-feature` time)

### What it is NOT

- **Not a new vote in `_synthesize_label`'s bullish/bearish tally.** Every existing
  component in Today/Tomorrow, This Week, and This Month carries a real historical
  N and win-rate (see Phase 2's design principle: "transparent synthesis, never a
  bare invented percentage"). An LLM's same-day news judgment has no historical
  track record to check itself against — folding it into the same vote as the
  backtested components would quietly break that discipline. It stays a clearly
  separate, clearly-labeled line.
- **Not a buy/sell directive.** Same SOUL.md constraint as every other check in this
  tool — a news summary + directional lean is advisory context, not an instruction.

### What it is

A new module, `mytrader/gold_news.py`, mirroring the existing
`mytrader/news_search.py` pattern (sdk_compat + WebSearch, JSON response, DB cache)
but tailored to gold-relevant catalysts instead of single-ticker corporate events:

- **Search prompt** (new, gold-specific — distinct from `news_search.py`'s
  M&A/lawsuit/credit-downgrade/leadership/short-seller prompt, which is aimed at
  individual stocks) should cover, in the same "report only real evidence, no
  speculation" style as the existing prompt:
  1. Federal Reserve / major central bank rate decisions, comments, or policy
     surprises in roughly the last 24-48 hours
  2. Geopolitical escalation or de-escalation likely to move safe-haven demand
  3. Surprise macro data releases (CPI, jobs, GDP) materially different from
     consensus, in roughly the last 24-48 hours
  4. Central bank gold buying/selling reported recently (a slower-moving but
     real driver — see `investment-strategy.md`/gold research already in this repo)
  5. Unusually large single-day gold ETF flows or notable institutional gold
     buying/selling reported in the news
- **Response shape**: `{"material": bool, "direction": "bullish"|"bearish"|"neutral", "detail": str, "findings": [...]}`
  — adds a `direction` field on top of `news_search.py`'s existing
  `{"material", "detail", "findings"}` shape, since (unlike the per-ticker check,
  which only needs "is this material") gold's news needs a same-day directional
  lean to be useful alongside the Today/Tomorrow and This Week sections.
- **Caching**: new `gold_news_cache` table, a single-row cache (not per-ticker —
  there's only ever one "gold" to check), same time-based TTL philosophy as
  `news_events_cache` (no version identifier to key off, so plain TTL). Suggested
  starting value: reuse `NEWS_EVENTS_CACHE_HOURS` (20.0) — same "roughly once a
  day" cadence Monitor already runs at. Confirm at planning time whether gold
  news specifically warrants a shorter TTL (e.g. 6-8h) given it's meant to catch
  same-day catalysts, vs. the per-ticker check's slower-moving corporate events.
- **Model tier**: new `GOLD_NEWS_SUMMARY_MODEL` constant, reusing
  `NEWS_EVENTS_SUMMARY_MODEL`'s already-locked-in "sonnet" tier as a starting
  default (same precedent as `ASX_ANNOUNCEMENT_SUMMARY_MODEL` reusing
  `SEC_FILING_SUMMARY_MODEL`'s tier) — not a fresh evaluation.
- **Cost**: safe to run automatically in Monitor (unlike the per-ticker
  `news_events` check, which is deliberately Find-only/opt-in because it doesn't
  scale to 50+ holdings/watchlist rows daily) — this is exactly ONE search per
  Monitor run, not one per ticker, so the cost profile is a single Find-time call,
  once a day.

### Wiring

- `gold_outlook.build_outlook()` gains one more call,
  `gold_news.get_gold_news(conn)`, wrapped in the same
  graceful-degradation try/except already used for the backtest fetch — a failed
  news search must never take down the rest of the outlook.
- `build_today_read()` and `build_week_read()` each take the news result and:
  - Append a `"News Catalyst: ..."` note (only when `material=True`; otherwise
    omit the line entirely rather than noting "nothing found" — keeps the file
    readable on quiet days).
  - When material, append a caveat to the `confidence` string, e.g. `"... —
    live news catalyst found, may not be reflected in the historical-lean read
    above"` — this is the direct fix for today's miss: a materially bullish
    catalyst would have visibly flagged the bearish-lean read as potentially
    stale, rather than presenting it as a clean 6/8 split.
- `build_month_read()` does **not** get a news line — a same-day catalyst has
  nothing meaningful to say about a 1-month horizon, same reasoning Phase 2
  already applied to keep technical-indicator backtests capped at 1 month (see
  `.agent/plans/gold-tracker-phase2-outlook.md`'s NOTES).
- `render_outlook_markdown()` renders the new note/caveat under Today/Tomorrow and
  This Week only.

### New files / files to update

- `mytrader/gold_news.py` (new) — search prompt, JSON parsing, cache read/write,
  `get_gold_news(conn) -> dict | None` returning
  `{"verdict": "flag"|"info", "direction": "bullish"|"bearish"|"neutral"|None, "detail": str}`.
- `mytrader/db.py` — new `gold_news_cache` table (single-row) + CRUD, mirroring
  `get_cached_news_events`/`upsert_news_events_cache`.
- `mytrader/config.py` — `GOLD_NEWS_SUMMARY_MODEL`, `GOLD_NEWS_CACHE_HOURS`.
- `mytrader/gold_outlook.py` — wire in `gold_news.get_gold_news()`, extend
  `build_today_read()`/`build_week_read()`/`render_outlook_markdown()`.
- Tests: `mytrader/tests/test_gold_news.py` (mirror `test_news_search.py`'s
  cache-fresh/cache-stale/search-fails-with-stale-fallback/search-fails-no-cache
  pattern), plus `test_gold_outlook.py` additions confirming the news line is
  excluded from `_synthesize_label`'s vote tally and absent from the Month section.
- `.claude/skills/my-trader/SKILL.md` — extend the "Gold Outlook" section.

## Open Questions (resolve at `/plan-feature` time)

1. **Cache TTL**: reuse 20h (`NEWS_EVENTS_CACHE_HOURS`) or go shorter (6-8h) given
   gold news is meant to catch same-day catalysts specifically?
2. **Direction on the "material" bar**: should a `material=True` but
   `direction="neutral"` result (e.g. "Fed held rates as expected, no surprise")
   still render a News Catalyst line, or only when direction is bullish/bearish?
   Leaning toward: only render when direction is bullish or bearish — a
   confirmed-no-surprise event isn't useful context to surface.
3. **Search prompt breadth**: the 5 categories above are a first-pass list of what
   "master investors" watch for gold specifically — worth a quick gut-check against
   `investment-strategy.md`/existing gold research in this repo before locking the
   prompt wording, same way Phase 1's macro thresholds were checked against
   `tool-preplan.md` before shipping.

## Non-goals

- No buy/sell directive anywhere (unchanged project-wide constraint).
- Not a replacement for the existing backtest-grounded vote — purely additive
  context + a confidence caveat.
- Not extended to This Month (see Wiring above).
- Not a general market-news feed — scoped specifically to catalysts that move gold,
  reusing the existing per-ticker `news_events` search infrastructure/pattern
  rather than building a new search mechanism from scratch.
