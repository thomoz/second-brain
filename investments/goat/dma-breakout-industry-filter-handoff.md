# DMA Breakout — Industry Filter — Handoff

## Status: NOT BUILT — drafted 2026-10-20 from Shaun's request. Research-only
pass so far — awaiting Shaun's manual `/plan-feature` run against this doc
before any code.

## Why This Exists

`dma-breakout-candidates-pending-review.md` currently lists every S&P 500 +
ASX 200 + curated-ETF name that crossed above its 150/200-day MA that day —
Shaun's complaint: too many rows to realistically review (~100+ some days).
Shaun's ask: only stage a candidate if its Finviz industry is also in the
**top 36 of 144** industries in `industry-ranking-full.md` that day (ranked by
Perf Week, `GOAT_INDUSTRY_FULL_PRIMARY_WINDOW`) — i.e. only show breakouts in
industries where money is actually rotating in right now.

## The Taxonomy Mismatch (the actual blocker)

`dma_breakout_scan.py`'s `fetch_universe_constituents` tags every candidate
with **GICS sector** (11 broad buckets — `c["gics_sector"]` from
`sp500_universe.py`, `c["sector"]` from `asx200_universe.py`), not Finviz's
144-industry taxonomy that `industry-ranking-full.md` ranks. There is no
existing per-ticker mapping from ticker → one of the 144 Finviz industries.

**Good news found during research: most of the plumbing already exists.**
`investments/goat/goat/industry_constituents.py` already does exactly this
lookup, just scoped to the 39 ETF-backed industries used by the narrower
`industry-ranking.md`:

- `fetch_industry_constituents_us(industry_label)` → looks up
  `config.GOAT_FINVIZ_INDUSTRY_SLUGS[industry_label]`, calls
  `mytrader.finviz_screener.fetch_screener_universe(filters=f"{slug},sh_avgvol_o100,sh_price_o1")`
  → list of US tickers in that industry.
- `get_asx_industry_constituents(industry_label)` → pure dict lookup over the
  hand-curated `config.GOAT_ASX_INDUSTRY_CONSTITUENTS`.
- `get_or_refresh_industry_constituents(conn, industry_label)` → wraps both,
  with a 7-day DB cache (`GOAT_INDUSTRY_CONSTITUENTS_CACHE_TTL_DAYS`) for the
  US leg via `db.replace_industry_constituents`/`db.get_industry_constituents`.

**The actual gap**: `GOAT_FINVIZ_INDUSTRY_SLUGS` only has ~39 entries (the
ETF-backed industries) out of Finviz's 144. Any of the day's top-36 industries
that isn't one of those 39 will have no slug → `fetch_industry_constituents_us`
returns `None` (logged, not a crash) → that industry silently contributes zero
US tickers to the allow-set, even if it's genuinely top-ranked.

**So this is not a new scraper** — it's (a) extending `GOAT_FINVIZ_INDUSTRY_SLUGS`
to cover enough of the other ~105 industries that the top-36 on a typical day
actually resolve to a slug, and (b) wiring `dma_breakout_scan.py` to build an
allow-set from the day's top-36 and filter against it. ASX coverage will stay
thin regardless — `GOAT_ASX_INDUSTRY_CONSTITUENTS` is hand-curated and almost
certainly doesn't cover most of the 105 new industries; that's an accepted gap,
not something to fix here (see Open Question 3).

## Proposed Approach

1. **New config constant**: `GOAT_DMA_BREAKOUT_TOP_INDUSTRY_COUNT = 36`.
2. **Read the day's ranking, don't re-scrape it.** `industry_rotation_full.py`
   already persists each day's full 144-industry ranking into
   `goat_rotation_snapshots` (`scope="industry_full"`, via
   `capture_full_industry_snapshot`). Read the top 36 industry names from
   there (most recent snapshot) rather than having `dma_breakout_scan.py`
   re-fetch `finviz_groups.fetch_industry_groups()` itself — avoids a second
   Finviz Groups network call and avoids any dependency on
   `industry-ranking-full.md`'s file-write timing specifically (decouples
   from the retime question below). Confirm `goat_rotation_snapshots` schema
   supports "give me the latest run's top-N by rank for scope=industry_full"
   cheaply (it should — `rank` is already a stored column).
3. **Build the allow-set**: for each of the top-36 industry names, call
   `get_or_refresh_industry_constituents(conn, industry_label)` (cached, so
   this is cheap after the first call of the day) and union the returned
   tickers into one set.
4. **Filter in `run_dma_breakout_scan`**: after the existing `check_ma_cross`
   gate passes, add a check that `ticker in allow_set` before staging —
   everything else about the function (liquidity floor, ethical filter,
   holdings/watchlist dedup, insolvency suppression) stays as-is.
5. **ETF rows**: `config.GOAT_DMA_BREAKOUT_ETF_UNIVERSE` rows (market="ETF")
   have no natural Finviz-industry membership. Recommend exempting ETF rows
   from this filter entirely (always eligible, as today) — flagged as Open
   Question 2, not a default to just ship silently.

## Retiming (`dma-breakout-scan` after `industry-full-scan`)

Current timers: `second-brain-goat-industry-full-scan.timer` at 21:40 UTC,
`second-brain-goat-dma-breakout-scan.timer` at 22:55 UTC — already a 75-minute
gap, which in practice is almost certainly enough. But if step 2 above reads
`goat_rotation_snapshots` directly (not the rendered .md file), the ordering
dependency becomes "has today's `industry_full` snapshot been captured yet,"
which is worth making explicit rather than relying on a clock gap:

- Add `After=second-brain-goat-industry-full-scan.service` to
  `second-brain-goat-dma-breakout-scan.service` (belt-and-suspenders — doesn't
  change the clock time, just guarantees ordering if either job's run time
  drifts).
- Decide what `run_dma_breakout_scan` does if no `industry_full` snapshot
  exists yet for today (first-ever run, or industry-full-scan failed) — fail
  open (skip the industry filter, stage everything, matching today's
  behavior) or fail closed (stage nothing). Recommend fail open with a logged
  warning, consistent with this module's existing "never silently stage zero
  when something upstream breaks" posture (see `asx_unavailable` handling).

## Open Questions (resolve during `/plan-feature`)

1. **How many of the ~105 missing Finviz slugs actually need filling in?**
   Pull a handful of real `industry-ranking-full.md` runs and check how many
   top-36 industries already have a `GOAT_FINVIZ_INDUSTRY_SLUGS` entry today
   vs. not — that tells you the real size of the data-entry task before
   committing to "fill them all in."
2. **ETF rows: exempt from the filter, or drop the industry-filter idea for
   ETFs specifically?** Recommended default above is "always eligible."
3. **ASX coverage gap — acceptable, or does `GOAT_ASX_INDUSTRY_CONSTITUENTS`
   need expanding too?** Given Finviz's industry taxonomy is US-market-centric,
   recommend accepting thin/no ASX coverage for most of the top-36 on any
   given day rather than trying to hand-curate 100+ more ASX industry lists.
4. **Confirm `goat_rotation_snapshots` can cheaply answer "top 36 by rank for
   the latest `industry_full` run"** — read `db.py`'s schema/query helpers for
   that table before assuming a new query function isn't needed.
5. **Does a ticker needing a fresh (uncached) `get_or_refresh_industry_constituents`
   call for all 36 industries on the same run add meaningful runtime?** First
   run after this ships will cold-fetch all 36; after that, the 7-day TTL
   means most days should mostly hit cache. Worth timing the first real run.

## Relevant Codebase Files — READ THESE DURING `/plan-feature`

- `investments/goat/goat/dma_breakout_scan.py` (whole file) — the function
  being extended (`run_dma_breakout_scan`, `fetch_universe_constituents`).
- `investments/goat/goat/industry_constituents.py` (whole file) — the
  per-industry constituent lookup to reuse as-is.
- `investments/goat/goat/industry_rotation_full.py` (whole file) — where the
  top-36 ranking and `goat_rotation_snapshots` (`scope="industry_full"`)
  persistence already happens; confirms `GOAT_INDUSTRY_FULL_PRIMARY_WINDOW`
  ("perf_week") is the ranking basis.
- `investments/goat/goat/config.py` — `GOAT_FINVIZ_INDUSTRY_SLUGS` (line
  ~199, currently 39 entries), `GOAT_ASX_INDUSTRY_CONSTITUENTS` (line ~277),
  `GOAT_DMA_BREAKOUT_*` constants (line ~783+), `GOAT_INDUSTRY_FULL_PRIMARY_WINDOW`
  (line 256).
- `investments/goat/goat/db.py` — `goat_rotation_snapshots` schema/query
  helpers, `get_industry_constituents`/`replace_industry_constituents`,
  `insert_goat_pending_candidate`.
- `investments/goat/goat/finviz_groups.py` — confirms the industry label
  strings Finviz Groups returns (`_norm`'d) line up with
  `GOAT_FINVIZ_INDUSTRY_SLUGS` keys (e.g. `"Aerospace & Defense"`).
- `mytrader/finviz_screener.py` — `fetch_screener_universe`, the actual
  Finviz-screener HTTP call reused for any new slug.
- `scripts/systemd/second-brain-goat-dma-breakout-scan.service` and
  `second-brain-goat-industry-full-scan.service` — add the `After=` ordering
  here if step 2's snapshot-read approach is adopted.

## Validation (once built)

```powershell
uv run --directory investments/goat python -m pytest -q
```

Manual: run `scan-industries-full` then `scan-dma-breakout` (via
`invoke_investments.ps1`, never locally against the real DB) on the same day
and confirm `dma-breakout-candidates-pending-review.md` only contains tickers
whose industry appears in that day's `industry-ranking-full.md` top 36 —
spot-check 2-3 included and 2-3 excluded candidates by hand against both
files before trusting the output.
