# Goat — Session Handoff

## Status: Phase 1 complete 2026-08-11 — see `.agent/plans/goat-phase1-150dma-exit-check.md` (150DMA holdings exit check). `investments/goat/` is a working uv workspace member; `python -m goat.main monitor` runs against the real shared DB, checks all holdings, writes only to `goat_alert_history` and `investments/goat/monitor-report.md`. systemd units exist but are NOT enabled on the VPS — needs Shaun's explicit go-ahead. Phases 2/3 not yet planned — run `/plan-feature` against this handoff again when ready.

## What This Is

A sector-rotation + momentum tool, named after the Goat's Academy webinar it's based
on. Source notes: `investments/my-trader/transcripts/lesson-extraction/goat-academy-webinar-1.md`

Genuinely different from my-trader/briefs-finance's fundamentals-driven, single-stock
value investing — this is technical/momentum-driven and operates at the sector level
first, individual stock level second. Kept as its **own package** (`investments/goat/`,
sibling to `briefs-finance/` and `my-trader/`) rather than folded into either, precisely
because the philosophies are different enough that mixing them would blur design
decisions already made deliberately elsewhere (see below).

## Context

**my-trader today**: fundamentals/quality-driven, single-stock picks graded against
Shaun's own criteria plus 9 value-investor frameworks (Graham, Buffett, Lynch, etc.).
`checks/price_action.py` has an explicit, deliberate design decision that **price
momentum is not a signal** — `verdict` is always `"info"`, never `"flag"` or
`"interesting"`, directly citing Graham's own principle file ("price momentum does not
[matter]").

**Goat (from the notes)**: sector-rotation + momentum-breakout investing. Three steps:
1. **Read the scoreboard** — find rising industries/sectors (follow institutional
   money), buy an index fund of that sector rather than picking individual stocks.
   Within a chosen sector, the entry signal on an individual stock/index is a
   "heartbeat" pattern: a smooth, low-volatility sideways consolidation for a minimum
   of ~3 months (longer is better — cited examples had 2-4 years of consolidation
   before a 10x move), followed by a breakout above the 50-day moving average with the
   50DMA itself turning from sloping down to sloping up. Risk-management check on the
   underlying fundamentals, in priority order: debt (zero is best) → cash runway in
   years → margins → revenue growth → cash generation — essentially "how unlikely is
   bankruptcy," not a valuation judgment.
2. **You don't have to pick stocks** — industries/sectors move together; a falling
   stock usually means the whole sector is falling, so rotate to whichever sector is
   rising rather than trying to time an individual name.
3. **The exit matters most** — the #1 investor mistake is holding a winner until it
   becomes a loser. Exit rule: sell when price drops "reasonably below" the 150-day
   moving average (allow for the price to dip through it briefly and recover — this
   isn't a same-day trigger).

Paid apps Shaun's notes reference (context only, not being adopted): TradeVision
($24.99/mo, general market view) and Winston App ($57/mo, finds index funds by
sector). Everything below is scoped to be buildable for free with what's already
available (yfinance + FRED, no new paid dependency), same philosophy as
briefs-finance/my-trader.

**Real connection already observed live**: the LULU chart Shaun screenshotted earlier
in the same conversation that produced this handoff (50 SMA + 150 MA both plotted,
"just crossed over the 50 day moving average") is this exact framework already being
applied manually, before these notes were even shared. Good validation this is a real,
currently-manual workflow worth automating, not a hypothetical.

## Shaun's three direct questions (answered in conversation, captured here for the plan)

1. **"Is there a free way to see which sectors are rising/falling?"** — Yes. The 11
   SPDR Select Sector ETFs (XLK tech, XLF financials, XLE energy, XLV healthcare, XLY
   discretionary, XLP staples, XLI industrials, XLB materials, XLU utilities, XLRE
   real estate, XLC communication) are all free on yfinance. Comparing relative
   performance/relative strength across them over a rolling window (e.g. 3-month)
   answers "where is money rotating into" without any paid tool.
2. **"Can it scan for stocks with the heartbeat pattern that just crossed the 50DMA?"**
   — Yes, technically, but this is the harder half — see Phase 3 and the open question
   on candidate universe below. The moving-average/cross-detection logic already
   exists in my-trader (`gold_technicals.py` + `macro_indicators.py`'s
   `check_gold_trend()` sign-flip cross detection) and generalizes directly to any
   ticker's 50DMA — worth reusing/porting rather than reinventing (see "Reuse vs.
   standalone" below). The "heartbeat" (low-volatility consolidation for 1-3+ months)
   needs a new, concrete definition — see Phase 3.
3. **"Should it auto-run daily?"** — Recommended split cadence, not a single answer:
   the holdings 150DMA exit check (Phase 1) is cheap and should run daily, same
   cadence as my-trader's Monitor. The sector-rotation ranking (Phase 2) is also cheap
   (11 ETF price fetches) and can run daily. The stock/heartbeat scanner (Phase 3) is
   the expensive, unresolved piece — see Open Questions.

## Reuse vs. standalone — RESOLVED 2026-08-11

**Decision: (a) Goat depends on my-trader as a workspace package.** Add `"goat"` to
`investments/pyproject.toml`'s `[tool.uv.workspace] members`, have Goat import
`mytrader.market_data` / the moving-average logic directly. Simplest to build now;
accepted coupling to my-trader's internals as the tradeoff.

**Data storage — RESOLVED 2026-08-11: new tables inside the existing
`investments/briefs-finance/data/investments.db`**, not a separate DB file — chosen
specifically so sector/stock data can be combined/joined with my-trader's holdings
data later if useful. Goat still must NOT write into the existing `holdings`/`watchlist`
tables (those stay my-trader's) — this is new Goat-specific tables in the same file,
not new rows in existing tables. Phase 1's 150DMA check reads my-trader's holdings
for reference; Goat's own scan results/pending-candidates go in its own new tables.

## Remaining Steps

### Phase 1 — Holdings 150DMA exit check (build first — cheapest, highest value, matches "exit matters most")

- Reads my-trader's holdings (`db.get_all_holdings(conn)` — read-only cross-package
  access, resolved by whichever option above is chosen)
- For each holding: fetch price history, compute 150-day MA, determine if price is
  "reasonably below" it — needs a concrete threshold, not just "any dip below" (the
  notes explicitly warn price can dip through and recover). Candidate approaches to
  resolve during planning: a %-below threshold (e.g. >2-3% below), and/or a
  minimum-consecutive-days-below requirement, to avoid a single noisy day firing an
  alert that reverses tomorrow.
- This is a genuine "the exit rule fired" event, not neutral info, unlike
  `price_action.py`'s deliberate neutrality — this check exists specifically *because*
  Shaun wants this rule enforced, not just observed. Needs its own dedup mechanism
  (either reuse my-trader's `alert_history` pattern against a Goat-specific
  ticker/source_table, or a Goat-native equivalent, depending on the reuse decision
  above)
- Cadence: **daily** — cheap (one price history fetch per holding); my-trader's
  `snapshot.py` already fetches a live price for every holding daily for the P&L
  column and records it to `holdings_price_history` — worth checking whether that
  data can be read directly instead of a second fetch

### Phase 2 — Sector rotation ranking (build second — cheap, standalone)

- Fetch the 11 SPDR Select Sector ETFs via yfinance, rank by relative performance
  over a rolling window (window length TBD during planning — the notes' own
  "heartbeat" cited multi-month-to-multi-year timeframes, so a single 3-month window
  is a starting guess, not settled)
- Output: which sector(s) are "rising" vs "falling" — this becomes the candidate
  filter Phase 3 uses, rather than Phase 3 scanning the whole market blindly
- **RESOLVED 2026-08-11 — Phase 2 is also a standalone signal, not just a filter.**
  Shaun wants both: individual stocks found within hot sectors (Phase 3), AND the
  sector ETF itself surfaced as a real candidate when it's showing strength — an ETF
  looking good is itself a sign the sector is heating up. This means Phase 2 needs its
  own opportunity-style signal (not just a plain info report as originally scoped) —
  likely the same heartbeat/50DMA-cross detection logic from Phase 3, applied to the
  11 sector ETFs directly rather than only to individual stocks within them. Needs
  scoping during planning: does Phase 2 reuse Phase 3's pattern-detection code on ETFs,
  or run it in parallel on both?
- Cadence: daily is cheap (11 tickers), but the *signal* itself is inherently
  slow-moving (sector rotation happens over weeks/months) — daily computation is fine,
  but don't expect the ranking to change often, and don't alert on every tiny reorder

### Phase 3 — Stock/index "heartbeat" scanner within rising sectors (build last — hardest, most open questions)

- For each candidate ticker (see Open Questions on where this list comes from):
  fetch price history, detect:
  1. A "heartbeat" consolidation — low-volatility sideways range sustained for a
     minimum duration (notes say 1-3 months minimum, longer is better). Needs a
     concrete definition during planning — e.g. rolling price range as a % of mean
     staying under some threshold over a rolling window, or an ATR-based flatness
     measure. This is the single most underspecified part of the whole framework and
     needs real research/backtesting before picking a number, same discipline
     `opportunity.py`'s thresholds went through in my-trader (sourced from real
     principles/methodology, not invented) — don't just guess a number and ship it.
  2. Confirmation the 50DMA has turned from sloping down to sloping up (compare
     50DMA today vs. N days ago — same shape as my-trader's `check_recession_signal()`
     today/prior lookback comparison)
  3. Confirmation price has just crossed above the 50DMA (reuse the existing
     sign-flip cross-detection logic directly)
- Fundamentals risk filter, applied after the technical pattern fires (per the notes'
  own ordering — technical signal first, then a survival check, not the other way
  around): debt (low/zero preferred), cash runway, margins, revenue growth, cash
  generation. Several of these already exist as raw numbers in my-trader's
  `balance_sheet.py`/`valuation.py` and could be reused/ported; "cash runway in years"
  specifically does **not** exist anywhere in my-trader today and would be new
  (relevant mainly for cash-burning, not-yet-profitable companies — a different
  company profile than most of what my-trader's existing 9 value frameworks are built
  around)
- Output: **do not write into my-trader's `watchlist.md`/`holdings.md` directly** —
  same precedent as my-trader's own `candidate_sync.py`, land in Goat's own
  pending-review staging file/table, explicit promote/dismiss action required. If
  "promote" ever means "add to my-trader's watchlist," that's a cross-package write
  and needs its own explicit design, not an assumption.
- **Candidate universe — RESOLVED 2026-08-11: (c) scrape S&P 500 constituents**
  (e.g. Wikipedia's S&P 500 table) tagged by GICS sector, for real new-idea discovery
  rather than being limited to my-trader's existing watchlist/holdings.
- **Cadence — RESOLVED 2026-08-11: weekly scheduled scan, plus on-demand trigger.**
  Matches the existing Monitor (scheduled) / Find (on-demand) split already used by
  my-trader — e.g. "scan tech sector for heartbeat setups" callable anytime, such as
  when news moves a sector, in addition to the automatic weekly run.

## Explicitly deferred (do not build as part of this handoff)

- Any automatic buy/sell action of any kind — advisor-notes-only, same as
  my-trader/briefs-finance (SOUL.md), regardless of how mechanical the framework's own
  rules sound
- A true portfolio-of-sector-ETFs product (the notes describe *buying the sector
  index fund itself* as the actual investment vehicle, not just using sector rotation
  to pick individual stocks within it) — worth explicitly asking Shaun during planning
  whether Phase 2's output is meant to inform "buy XLK itself" as a real candidate
  action, or purely as a filter for Phase 3's stock scan. The conversation that
  produced this handoff leaned toward the latter but never explicitly confirmed it.

## Validation (once built)

```powershell
# Add goat to the workspace first
# investments/pyproject.toml: members = ["briefs-finance", "my-trader", "goat"]

uv sync --directory investments/goat --extra dev
uv run --directory investments/goat python -m pytest -q

# Exact CLI shape TBD during implementation
uv run --directory investments/goat python -m goat.main monitor
uv run --directory investments/goat python -m goat.main scan
```

## Open Questions for Shaun

**Resolved 2026-08-11** (answers captured inline above where relevant):

1. ~~Reuse strategy~~ → (a) workspace dependency on my-trader.
2. ~~Phase 3's candidate universe~~ → (c) scrape S&P 500 constituents (e.g. Wikipedia),
   tagged by GICS sector.
3. ~~Does Phase 2 ever become a standalone buy candidate?~~ → Yes, both: individual
   stocks (Phase 3) AND the sector ETF itself when it's showing strength (Phase 2
   needs its own opportunity-style signal, not just a filter).
4. ~~Cadence for Phase 3~~ → weekly scheduled scan + on-demand trigger (Monitor/Find
   split, same as my-trader).
5. ~~Where does Goat's data live?~~ → new tables inside the existing
   `investments/briefs-finance/data/investments.db` (not a separate DB file), chosen
   to keep the option of combining/joining with my-trader's data later.

**Still open — needs real research/backtesting during `/plan-feature`, not a snap
preference call:**

1. **"Heartbeat" consolidation threshold** — genuinely unresearched. Needs either
   real backtesting against historical 10x-mover examples (as the notes themselves
   cite, informally) or at minimum a documented, sourced definition before shipping a
   number, same discipline `opportunity.py`'s thresholds went through in my-trader
   after being called out for inventing numbers the first time.
2. **150DMA "reasonably below" threshold for the holdings exit check** — needs a
   specific % and/or consecutive-days rule, not left as "reasonably" in the shipped
   code.
3. **Sector-ranking window length** (Phase 2) — 3-month starting guess, not confirmed.
