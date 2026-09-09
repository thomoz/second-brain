---
name: quiet-picks
description: >
  Pick the top 3 "quiet" stock ideas from today's investment reports for Shaun -
  candidates that (1) look like a possibly-good buy on the signals already in the
  reports, and (2) are NOT on anyone's radar (little or no recent mainstream news
  or sell-side/analyst coverage). Triggers on "quiet picks", "quiet buys",
  "under the radar picks", "off-radar picks", "hidden gems", "sleeper picks",
  "/quiet-picks". Selection criteria live in this file and are meant to be
  edited and extended over time.
---

# Quiet Picks

## What this does

On a trigger phrase, scan today's investment report files, build a candidate pool,
apply the selection criteria below, run a "not on the radar" news check on the
survivors, and present the top 3 with the reasoning for each.

**Trigger phrases** (any of these, case-insensitive): `quiet picks`, `quiet buys`,
`under the radar picks`, `off-radar picks`, `off radar picks`, `hidden gems`,
`sleeper picks`, `/quiet-picks`.

To change the trigger phrase: edit the `description` frontmatter above and this
list. It is a one-line edit - just tell me the new phrase.

Advisor mode only. This surfaces names worth a closer look. It never suggests a
trade, and nothing is added to the watchlist unless Shaun explicitly says so
afterward.

---

## Sources - today's candidate pool

Read these report files (all are git-tracked and synced locally, so no VPS call is
needed to build the pool). Each one has a `## Run: YYYY-MM-DD` or
`Last auto-generated: YYYY-MM-DD` line - check it first.

| File | What it contributes |
|------|---------------------|
| `investments/my-trader/synced-candidates-pending-review.md` | Briefs Finance recommendations, each with a written thesis. Highest-quality pool - already curated. |
| `investments/goat/insider-scan-report.md` | Market-wide $25k+ open-market insider buys. Use the "Discovery Candidates - By Trade Date" section for the freshest. Note the "price since trade" column and the `🚩 confirms signal` marker. |
| `investments/goat/sector-candidates-pending-review.md` | Fresh sector-ETF 50DMA breakouts plus a mirror of the insider-buy list. |
| `investments/goat/heartbeat-candidates-pending-review.md` | Weekly S&P 500 consolidation-then-breakout pattern hits (often empty midweek - the scan runs Saturdays). |
| `investments/my-trader/my-trader-report.md` | "Watchlist opportunities this run" - `opportunity` signals firing on existing watchlist rows. |
| `investments/goat/sector-ranking.md`, `investments/goat/industry-ranking.md`, `investments/goat/goat-report.md` | Context only: which sectors/industries are currently Rising, and the 150DMA exit-alert list (used as a disqualifier in Criterion 2). |

**Always exclude** any ticker already in `investments/my-trader/holdings.md` (Shaun
owns it). Tickers already on `investments/my-trader/watchlist.md` are allowed but
flag them as "already on your watchlist" and rank them lower - the point is to find
things not yet on the radar, including his own.

---

## Selection criteria (EDIT THIS SECTION)

A candidate must pass **every** Core criterion. When Shaun asks to tweak the
selection, edit here.

### Core criteria (all active)

1. **Has a real "possible buy" signal.** At least one of:
   - a Briefs Finance likelihood score of 60% or higher (shown in
     `synced-candidates-pending-review.md`, or compute it with a my-trader Find
     deep dive - see Workflow step 5); OR
   - a my-trader `opportunity` signal has fired for it (Graham / Lynch /
     Buffett-Smith / Marks-Neilson / score - visible in `my-trader-report.md` or a
     Find run); OR
   - it sits in a currently-Rising sector **and** industry (per
     `sector-ranking.md` / `industry-ranking.md`) with a fresh 50DMA breakout
     flagged by Goat; OR
   - an insider buy the market has since confirmed (`🚩 confirms signal`, i.e.
     price up since the trade) **and** the buyer is a CEO/CFO/Chair or there are
     multiple insiders or the buy is $250k or larger. A lone small director
     purchase does not count.
   - Direction: more independent signals firing together is better (confluence).

2. **Trend is intact - last close at or above the 150-day moving average.**
   Check via a my-trader Find `technical_levels` line, or Goat data. **Disqualify
   immediately** if the ticker appears on any 150DMA exit-alert list in
   `goat-report.md`.
   - Direction: price above the 150DMA is good (Goat's own exit rule says below =
     get out, so below = do not buy either).

3. **Not an MLP and not defense/military.** Drop at once if the legal name ends in
   `L.P.` / `LP` / `L.L.P.` (Shaun does not want K-1 tax forms), or if it is a
   defense contractor (ethical filter). When in doubt about MLP status, a
   my-trader Find run will flag it.
   - Direction: a normal C-corp in a non-defense business is good.

4. **Investable, not a lottery ticket.** Not a sub-$100M nano-cap shell, not a
   fresh de-SPAC with no operating history, share price not under about $2. This
   is a judgement call - err toward excluding the obviously speculative.
   - Direction: an established operating business with liquidity is good.

5. **Off the radar.** Little or no recent mainstream news or sell-side coverage.
   See the dedicated check below. This is the criterion Shaun cares most about and
   it is non-negotiable.
   - Direction: less attention is better here (the whole point is finding things
     before the crowd).

### Parked criteria (NOT active - move up to Core to enable)

- **Outside industries Shaun already owns.** Exclude any candidate whose industry
  matches an industry already represented in `holdings.md`.
  Wrinkle: `holdings.md` has no industry column, so each current holding's
  industry has to be resolved first (from a my-trader Find run, or a quick
  lookup). Flip this to Core when Shaun says "only pick outside what I own".

- _(room for more - add as Shaun requests them)_

### How to add a criterion

Add a numbered bullet under **Core criteria** with three lines:
the rule in one sentence, a `Check:` line stating exactly how to verify it and
from which file or tool, and a `Direction:` line stating which way is good (per
Shaun's check-interpretation convention - full metric names, not abbreviations,
plus a which-way-is-good clause).

---

## Workflow

1. **Freshness.** Read the run-date line in each source file. If the newest is not
   today's date, say so and proceed with the newest available (the VPS timers
   generate these daily around 07:35 Sydney; before that, yesterday's is newest).

2. **Build the raw pool.** Union of tickers across the source files, minus
   everything in `holdings.md`.

3. **Cheap filter pass (no web, no VPS).** Apply Core criteria 1 through 4 using
   only what is already written in the report files. Keep clear passes and
   plausible passes. Target a shortlist of roughly 6 to 10.

4. **Radar check.** Run the "not on the radar" check (below) on each shortlisted
   ticker. Drop anything clearly on the radar.

5. **Optional deep dive.** For the survivors, to firm up "possible buy" confidence,
   run a my-trader Find on the final 3 to 5:
   `.\scripts\invoke_investments.ps1 -Package my-trader -Command "find --ticker TICKER"`
   (runs on the VPS, slower). This adds the full 7-check assessment plus the
   Briefs Finance score, and will catch an MLP that slipped through.

6. **Rank and present the top 3.** If fewer than 3 survive, present what there is
   and say why the field was thin. If Shaun asked for a different number ("top 5")
   or a specific source, honour that over the defaults.

---

## The "not on the radar" check

For each shortlisted ticker, use WebSearch (and WebFetch if useful) on the company
name and ticker, focused on the last ~14 days.

**On the radar - exclude** if any of:
- mainstream finance press coverage in the window (Bloomberg, Reuters, CNBC, WSJ,
  Barron's, MarketWatch, Yahoo Finance or Motley Fool feature, Seeking Alpha
  front-page);
- a sell-side analyst initiated, upgraded, or downgraded it recently;
- it shows up in "best stocks to buy now" / "top picks" listicles;
- retail or social buzz (r/wallstreetbets, StockTwits trending, "meme stock");
- a large catalyst headline in the window: earnings surprise, M&A, guidance
  change, FDA decision, major contract win, activist campaign.

**Off the radar - keep** if coverage is limited to:
- the Form 4 insider-buy filing itself and sites that only aggregate insider
  filings (openinsider, etc.);
- routine dividend or buyback declarations, scheduled earnings-date notices;
- minor local or trade press;
- nothing at all.

**Grey area:** thin coverage but one recent mainstream mention - note it, keep the
ticker eligible, let it rank lower.

Record one line of evidence per ticker either way, so the output shows the
reasoning.

---

## Output format

Rate the output against "would this help Shaun decide what to look at next". Keep
it scannable.

```
# Quiet Picks - <date>
Sources: <report files used, each with its run date>
Funnel: <N> in pool -> <M> after criteria -> <K> after radar check

## 1. TICKER - Company Name
- What it does: <one line>
- Why it's a possible buy: <specific signals with numbers, e.g. "Briefs Finance
  score 72%; CEO bought $1.0M on 2026-08-20, now +7.8%; Semiconductors industry
  ranked #1 rising; last close 4% above its 150-day moving average">
- Off the radar: <evidence, e.g. "no mainstream coverage in the last 14 days;
  only openinsider aggregation plus a routine quarterly dividend notice">
- Risks / caveats: <valuation, size, sector risk, thin data, whatever applies>
- Source: <which report file it came from>

## 2. TICKER - Company Name
...

## 3. TICKER - Company Name
...

## Considered and dropped
- TICKER - on the radar (CNBC feature 2026-08-24)
- TICKER - below its 150-day moving average
- TICKER - structured as an MLP
- TICKER - no real "possible buy" signal, just a small director purchase
```

---

## Notes and guardrails

- Advisor only. No buy/sell directive anywhere in the output.
- Nothing is written to the watchlist. If Shaun wants one added afterward he will
  say "add TICKER to the watchlist" - that is a separate my-trader action.
- This is a triage step, not a substitute for a full my-trader Find deep dive.
- The insider-scan list can run to 200+ tickers. Do not try to web-check them all -
  the cheap filter pass in Workflow step 3 is what gets the shortlist down to a
  sane size before any web searches happen.

---

## Change log

- 2026-08-26 - created. Core criteria 1 to 5. "Outside industries already owned"
  parked as an inactive criterion pending Shaun's call.
