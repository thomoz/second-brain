# Insider Trade Outcome Pattern Analysis — Session Handoff

## Status: Implemented 2026-08-20 — see .agent/plans/insider-pattern-analysis.md; full test suite passing (198 goat + 494 my-trader), manual scan-insiders run validated twice with no duplicate work

## What This Is

Shaun wants the insider-scan system to, over time, build a dataset of price
outcomes after insider trades — not just today's live "check my current
candidates" report, but a growing historical record — and periodically mine it
for patterns that distinguish trades where price actually moved in the
signaled direction (buy → rose, sell → fell) from trades where it didn't.
Explicitly scoped to stocks Shaun does **not** hold (market-wide discovery),
not his existing holdings watch (he confirmed this 2026-08-20 — not worried
about held stocks here).

Two things block this today:

1. Price outcomes are computed live each report render and never persisted —
   no historical dataset exists to mine, despite the filing log itself being
   permanent.
2. Sells are not tracked market-wide at all — discovery scan only pulls
   purchases. Sells are only tracked for Shaun's own 8 held tickers (explicitly
   out of scope per this request).

## Current State (grounded in code, checked 2026-08-20)

- `goat_insider_filings_seen` (`investments/goat/goat/db.py:42`) is the
  permanent, append-only filing log — every filing ever seen, deduped by
  `dedup_key`, never deleted. Already has `value` and `pct_owned_change` as
  real numeric columns (not just embedded in text) — usable directly for
  bucket analysis without parsing. Does **not** have `title` (insider's role)
  as its own column yet, though the scraped row dict already carries it
  (`openinsider.py:60`, `_EXPECTED_COLUMNS["Title"]`) — just needs to flow
  through to the insert.
- `goat_pending_candidates` is a review-queue table, not a historical log —
  rows get deleted on `dismiss-candidate`/`promote-candidate`, so it's the
  wrong table to build a pattern dataset from.
- Price-since-trade (`insider_scan.py::_price_move_since`) is a live yfinance
  call at report-render time, computed only for tickers currently in
  `goat_pending_candidates`. No snapshot of the outcome is stored, so once a
  candidate is dismissed/promoted, its outcome is gone forever.
- `openinsider.py` has `fetch_discovery_purchases()` (hits
  `/latest-insider-purchases-25k`) but no sales equivalent. The original
  insider-scanner handoff doc
  (`investments/insider-trading-scanner-handoff.md`) explicitly scoped sells
  out of discovery ("Shaun did not ask for a market-wide sell scan") — that's
  now superseded by this request.
- `price_history.fetch_close_history(ticker, lookback_days)`
  (`investments/goat/goat/price_history.py:11`) is generic — works for any
  ticker, so it can fetch a benchmark (e.g. SPY) the same way it fetches the
  traded stock, with no new plumbing.
- Current confirm-signal threshold (`config.GOAT_INSIDER_PRICE_FLAG_PCT =
  15.0`) is flat regardless of elapsed time — a 15% move gets flagged whether
  it took 2 days or 89 days. Shaun's point (2026-08-20): those aren't equally
  meaningful — a 3% move in 4 days is a fast reaction, a 3% move in 90 days is
  noise.

## Proposed Design

### 1. Track sells market-wide (tracking-only, not a review queue)

Add `fetch_discovery_sales()` mirroring `fetch_discovery_purchases()`, hitting
OpenInsider's `/latest-insider-sales-100k` (confirmed to exist by the original
scanner handoff's research). Unlike buys, market-wide sells shouldn't create
`goat_pending_candidates` rows or fire WhatsApp — there's no "should I act on
this" question for a sell on a stock Shaun doesn't hold, it's purely a data
point for pattern-mining. Log straight to `goat_insider_filings_seen` with
`kind='discovery_sell'`.

### 2. Persist price-outcome snapshots (the actual dataset)

New table, e.g. `goat_insider_price_outcomes`:

```
dedup_key             TEXT NOT NULL   -- FK to goat_insider_filings_seen.dedup_key
ticker                TEXT NOT NULL
trade_type            TEXT NOT NULL   -- P or S
horizon_days          INTEGER NOT NULL
pct_change            REAL            -- raw price move
benchmark_pct_change  REAL            -- SPY's move over the same window
excess_pct_change     REAL            -- pct_change - benchmark_pct_change
snapshot_date         TEXT NOT NULL
PRIMARY KEY (dedup_key, horizon_days)
```

Each nightly `scan-insiders` run "matures" snapshots: for every filing in
`goat_insider_filings_seen` within a max tracking window (say 90 days old)
that has reached a horizon it doesn't yet have a row for (e.g. 1, 3, 7, 14,
30, 90 days), fetch price + SPY over that window and insert. This is
independent of `goat_pending_candidates`'s lifecycle — dismissing or promoting
a candidate no longer destroys its outcome data.

**Why benchmark-excess return, not just raw %**: a pattern of "buys rose 60%
of the time" during a month the whole market rallied isn't an insider-specific
signal, it's market beta. Excess return vs. SPY (or a sector ETF, if coverage
allows) isolates the part attributable to the trade itself. Recommend
surfacing both in the report but treating excess return as the metric that
actually supports a pattern conclusion.

### 3. Time-aware confirmation threshold (replaces the flat 15%)

Shaun's instinct to lower the threshold for early moves is right, but I'd
frame it as a **graduated curve by elapsed days** rather than picking a single
"first week" vs. "14 days" cutoff — that avoids an arbitrary edge exactly at
the boundary (day 6 vs. day 8 shouldn't be treated completely differently).

Shaun's numbers (2026-08-20): "anything over 2.5% for the first 7 days is
fair, then 5% for 7 days, 7.5% for 14 days, 10% for 21, 15% for 28" — read as
sequential blocks (each "X% for N more days" stacking onto the previous
boundary), giving these cumulative day-marks:

| Days since trade | Flag threshold |
|---|---|
| ≤ 7 | 2.5% |
| ≤ 14 | 5% |
| ≤ 28 | 7.5% |
| ≤ 49 | 10% |
| ≤ 77 | 15% (matches current default, reached later than before) |
| > 77 | 15% (unchanged) |

**Confirm this reading during /plan-feature** — the alternative interpretation
(each block's day-count restarting from day 1 rather than stacking) would
produce a different, non-monotonic table and doesn't fit "graduated curve" as
well, so the stacking read above is assumed correct but not yet confirmed
verbatim by Shaun.

Rationale: price moves grow with elapsed time under normal random-walk drift
(roughly proportional to √t), so a flat threshold is implicitly *harder* to
hit early and *easier* to hit late — the opposite of what actually signals
insider-driven conviction. A fast, small move is more likely attributable to
the filing itself; a slow, larger move is more likely just ordinary market
drift. Shaun's numbers keep the bar low for much longer than my original
starting guess (15% isn't required until day 77, not day 30) — reflects his
view that even smaller moves stay meaningful for a longer stretch than I'd
assumed. Still worth revisiting once a few weeks of real snapshot data exists
(which is exactly what the pattern-analysis pass in point 4 would be
positioned to validate).

Apply this in `_confirms_signal`/`_price_note` for the existing report AND
when labeling snapshots "confirmed" in the outcomes table, so both stay
consistent.

### 4. Daily pattern-analysis pass

New report, e.g. `investments/goat/insider-pattern-analysis.md`, regenerated
nightly alongside the existing scan (once enough sample exists — see
guardrails below). Proposed angles to slice by:

- **Trade size** (dollar buckets, e.g. <$50k / $50k–250k / $250k–1M / $1M+) —
  already have `value` as a real column, no parsing needed.
- **Percent of insider's own position** (`pct_owned_change` buckets, e.g.
  <5% / 5–25% / 25–100% / new position) — a "New" position (ΔOwn unparsable,
  no prior reported stake) may behave differently from someone topping up an
  existing stake; already a real column too.
- **Cluster buying** — multiple different insiders at the same company buying
  within a short window (e.g. 7 days) is one of the more commonly cited real
  signals in insider-trading research, distinct from a single isolated buy.
  Derivable from `goat_insider_filings_seen` by grouping on `ticker` +
  `trade_type` + date proximity.
- **Elapsed-time velocity** — how fast a move happened relative to its size
  (this is what point 3's tiered threshold already captures; the pattern
  report would show whether "fast movers" actually correlate with bigger
  eventual 30/90-day moves — i.e. does an early signal predict a later one).
- **Insider title/role** (CEO/CFO/Chair vs. director vs. 10%-owner vs. other)
  — needs `title` added as a real column first (see Current State); research
  generally finds C-suite/officer buys more predictive than director buys,
  worth testing against Shaun's own captured data rather than assuming.
- **Buy vs. sell** — the core comparison Shaun asked for (does the signaled
  direction actually hold).

Deliberately deferred to a later pass (lower expected signal-to-effort, or
blocked on more infrastructure): sector-based slicing (most discovery
candidates are small/micro-cap, so `goat_sp500_constituents` coverage would be
thin), day-of-week/market-regime effects.

### 5. Statistical honesty guardrails

- Gate any reported "pattern" on a minimum sample size per slice (e.g. n≥20)
  — with roughly 15-20 new candidates/day this will take real time to reach
  for finer-grained buckets. That's expected, not a bug.
- The report should say plainly that this is correlational/exploratory on
  Shaun's own captured data, not a validated trading strategy.
- Trade dates in the current dataset only go back to 2026-08-12 — there is
  currently about a week of history. This is a "start the flywheel now"
  build, not something with a backlog to retroactively mine. Set that
  expectation up front so the first few weeks of the new pattern report are
  expected to say "not enough data yet" for most slices.

## Open Questions (resolve during /plan-feature)

1. **Outcome table horizons** — is 1/3/7/14/30/90 days the right snapshot
   schedule, or coarser/finer? More horizons = more nightly yfinance calls per
   tracked filing (currently ~15-20 new filings/day × up to 6 horizons each
   once mature — manageable, but worth sizing explicitly).
2. **Benchmark choice** — SPY for everything, or per-sector ETF where
   available (more precise but only covers S&P500-listed tickers via
   `goat_sp500_constituents`, and most discovery candidates are smaller-cap
   names likely outside that table)?
3. **Max tracking window** — 90 days matches the existing
   `GOAT_INSIDER_SALE_LOOKBACK_DAYS`/`GOAT_INSIDER_PRICE_STALE_DAYS`
   precedent, but is that the right horizon to stop tracking a filing's
   outcome, or should it go longer (180d/365d) given "does insider buying
   predict a rise" is often studied over 6-12 months in the literature?
4. **Minimum sample size for a reported pattern** — proposed n≥20 per slice,
   confirm or adjust.
5. **Cluster-buying window** — proposed 7 days for "multiple insiders same
   ticker" — roughly matches the existing `GOAT_INSIDER_HOLDINGS_WATCH_LOOKBACK_DAYS`/
   `GOAT_INSIDER_DISCOVERY_LOOKBACK_DAYS` precedent (5 days), confirm.
6. **Time-aware threshold tiers** — confirm the stacking-blocks reading of
   Shaun's 2.5/5/7.5/10/15% numbers (→ ≤7/14/28/49/77 day cumulative marks,
   see Design section 3) is what he meant, versus each block restarting from
   day 1. Numbers themselves are Shaun's, not a guess, but the day-mark
   arithmetic derived from his phrasing should be read back to him to confirm
   before implementation.
7. **Does the existing report's 🚩 flag change immediately**, or does the
   time-aware threshold only apply to the new pattern-analysis dataset first
   (so the existing report's flagging behavior doesn't shift without more
   explicit confirmation)?
8. **Where does the new outcomes table live** — `investments.db` (shared with
   my-trader/briefs-finance) like everything else in Goat currently,
   presumably yes, but confirm no reason to split it out.
9. **Sell-side scrape etiquette** — same considerations as the original
   buy-discovery scan (conservative cadence, real User-Agent, stale-cache
   fallback) — mostly reuse `_fetch`'s existing pattern, but confirm
   `/latest-insider-sales-100k`'s actual table shape hasn't diverged from the
   purchases page (should live-check during /plan-feature, same as the
   original scanner's own research step).

## Explicitly Deferred

- Any actual trading/watchlist action driven by pattern findings — this stays
  advisor-notes/research only, same as everywhere else. A discovered pattern
  is something Shaun reads and judges, not something the system acts on.
- Sector-based and day-of-week/market-regime slicing — noted as candidate
  angles above but lower expected value given data coverage gaps; revisit
  once the core 4-5 angles have real volume.
- Backfilling outcome data for filings already dismissed/promoted before this
  system existed — that history is genuinely gone (never snapshotted), not
  recoverable.
- A UI/dashboard beyond the markdown report — matches the rest of the vault's
  markdown-report convention.

## Validation (once built)

```powershell
uv run --directory investments/goat python -m pytest -q

# Exact CLI shape TBD during implementation -- likely folds snapshot
# maturation + the pattern report into the existing scan-insiders command
# as extra steps, rather than a new separate command/timer
uv run --directory investments/goat python -m goat.main scan-insiders
```

## Sources Consulted (2026-08-20)

- `investments/goat/goat/insider_scan.py`, `db.py`, `config.py` — current
  schema, thresholds, and report-rendering logic (this session's earlier
  work, including the sorted-view additions and heading rename).
- `investments/my-trader/mytrader/openinsider.py` — scraper, confirmed
  `title` is already fetched but not persisted, confirmed no sales-discovery
  function exists yet.
- `investments/goat/goat/price_history.py` — confirmed `fetch_close_history`
  is ticker-agnostic, usable for a benchmark fetch with no new plumbing.
- `investments/insider-trading-scanner-handoff.md` — original scanner's
  handoff; confirms `/latest-insider-sales-100k` was already identified as
  OpenInsider's pre-thresholded sales page, and that market-wide sell
  tracking was explicitly out of scope at the time ("Shaun did not ask for a
  market-wide sell scan") — now superseded by this request.
