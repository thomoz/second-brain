# Feature: Insider Trade Outcome Pattern Analysis

The following plan should be complete, but it's important to validate documentation and
codebase patterns and task sanity before implementing.

Pay special attention to naming of existing utils/types/models. Import from the right
files etc. This is an extension of the existing Goat insider-trading scanner
(`investments/goat/goat/insider_scan.py`) — most new code lives alongside it, not in a
new package.

## Feature Description

Today Goat's insider-scan report computes each candidate's price-since-trade move live,
every run, and throws it away — nothing is ever persisted, so there is no historical
dataset to learn from. This feature adds: (1) market-wide sell tracking (buys only exist
today), (2) a permanent price-outcome snapshot table so historical performance survives
candidate dismiss/promote, (3) a time-aware confirmation threshold that treats a fast
small move as more meaningful than a slow large one, and (4) a nightly pattern-analysis
report that slices the growing dataset (trade size, % of position, cluster buying,
elapsed-time velocity, insider title, buy-vs-sell) with statistical-honesty guardrails
(n≥20 gating, explicit "correlational, not a strategy" framing).

## User Story

As Shaun (advisor-mode investor using Goat for market-wide insider-trade discovery)
I want the system to persist price outcomes after every insider filing and periodically
mine that history for patterns
So that I can eventually judge which kinds of insider trades (by size, role, cluster,
speed of price reaction) actually tend to predict a real price move, instead of relying
on gut feel on a report that forgets everything once a candidate is dismissed.

## Problem Statement

Two things block this today (confirmed in `insider-pattern-analysis-handoff.md`,
grounded in code 2026-08-20):
1. Price outcomes are computed live at report-render time and never persisted — no
   historical dataset exists to mine.
2. Sells are not tracked market-wide at all — `openinsider.fetch_discovery_purchases()`
   only pulls purchases; market-wide sell tracking was explicitly deferred by the
   original scanner's handoff, and that deferral is now superseded by this request.

## Solution Statement

Add a permanent `goat_insider_price_outcomes` snapshot table matured nightly (1/3/7/14/
30/90/180-day horizons, vs. SPY benchmark for excess return), a `fetch_discovery_sales()`
scraper + tracking-only ingestion path (`kind='discovery_sell'`, no candidate/no
WhatsApp), a graduated time-aware confirmation threshold (replaces the flat 15%,
applied immediately to both the live report and the new dataset), and a new
`insider-pattern-analysis.md` report that slices the market-wide (non-held) dataset by
the angles above, gated on a minimum sample size per slice.

## Feature Metadata

**Feature Type**: Enhancement (extends existing Goat insider scanner)
**Estimated Complexity**: Medium-High (new table + maturation job + new scraper +
threshold semantics change + new report — but every piece mirrors an existing pattern
in this codebase, no new architecture)
**Primary Systems Affected**: `investments/goat/goat/` (db.py, config.py,
insider_scan.py, main.py), `investments/my-trader/mytrader/openinsider.py`
**Dependencies**: yfinance (via existing `price_history.fetch_close_history`), pandas
(already a dependency), OpenInsider's `/latest-insider-sales-100k` page (new endpoint,
same scraper as existing `/latest-insider-purchases-25k`)

---

## RESOLVED DECISIONS (Shaun, 2026-08-20 — supersede the handoff doc's open questions)

1. **Time-aware threshold tiers** (replaces the handoff doc's original 2.5/5/7.5/10/15%
   guess entirely — this is Shaun's own corrected table, not a re-derivation of the
   handoff's numbers):

   | Days since trade | Threshold |
   |---|---|
   | ≤ 7 | 2.5% |
   | ≤ 14 | 5% |
   | ≤ 21 | 7.5% |
   | ≤ 28 | 10% |
   | > 28 | 12.5% |

2. **Applies immediately** to the *existing* live insider-scan report's 🚩 flag (both
   Holdings Watch and Discovery sections), not deferred to the new dataset only.
3. **Max tracking window: 180 days** (raised from the handoff's original 90-day
   proposal). `GOAT_INSIDER_OUTCOME_HORIZONS_DAYS` extended to include 180 as a horizon
   (not just 90) so the extended window is actually captured, not just cut off.
4. Everything else in the handoff's "Proposed Design" / other open questions is accepted
   as default and not re-litigated below: horizons 1/3/7/14/30/90/(+180) days, SPY-only
   benchmark (not per-sector), n≥20 minimum sample per pattern slice, 7-day cluster
   window, shared `investments.db`, sells are tracking-only (no candidate/no WhatsApp).
5. `GOAT_INSIDER_PRICE_STALE_DAYS` (90, the existing "may not reflect the insider signal
   anymore" annotation) is **unchanged** — it's tied to `GOAT_INSIDER_SALE_LOOKBACK_DAYS`
   for repeated-sale detection, a different concern from the outcomes table's own
   180-day max-tracking-window. Do not conflate the two.

---

## CONTEXT REFERENCES

### Relevant Codebase Files — READ THESE BEFORE IMPLEMENTING

- `investments/goat/goat/db.py` (whole file, 278 lines) — `init_goat_tables` (lines
  15-95) shows the exact idempotent migration pattern (`ALTER TABLE ... ADD COLUMN`
  wrapped in `try/except sqlite3.OperationalError: pass`) to follow for adding `title`
  to `goat_insider_filings_seen`, and the `executescript` block (17-59) for adding the
  new `goat_insider_price_outcomes` table. `insert_goat_insider_filing_seen` (204-221)
  is the function whose signature must grow a `title` param. `count_insider_sales_since`
  (244-259) is the closest existing precedent for a windowed COUNT query, useful as a
  pattern for `get_captured_horizons`/cluster-detection queries.
- `investments/goat/goat/config.py` (lines 240-247) — `GOAT_INSIDER_PRICE_FLAG_PCT` and
  `GOAT_INSIDER_PRICE_STALE_DAYS` are the two constants being touched/added-alongside.
  Every constant in this file has a comment explaining its provenance (Shaun's own
  number vs. v1/tunable vs. literature-sourced) — match that convention for every new
  constant.
- `investments/goat/goat/insider_scan.py` (whole file, 511 lines) — this is where most
  new code goes.
  - `_within_lookback` (23-28), `_price_move_since` (178-206): existing date-window and
    price-fetch helpers. `_price_move_since` computes move to *today's latest close*;
    the new maturation job needs a **different** helper that computes move to a *fixed
    horizon date* (trade_date + N days), not today — do not reuse `_price_move_since`
    for this, write a new function (see Task list).
  - `_confirms_signal` (209-218) and `_price_note` (221-229): currently take a flat
    `threshold: float`. Must change to derive the threshold from `days_since` via the
    new tiered lookup — **both** the existing report path (`compute_discovery_price_
    performance` line 232, `compute_holdings_watch_price_performance` line 260) and the
    new outcome-snapshot labeling must call through the same tiered function so they
    can never drift apart (this is exactly what Shaun's "apply immediately" resolves).
  - `run_discovery_scan` (128-175): pattern to mirror for the new
    `run_discovery_sell_tracking` — note it explicitly skips held/watchlisted/
    already-pending tickers; the new sell-tracking function should skip **held**
    tickers only (Shaun: "not worried about held stocks here" — those are already
    covered by `run_holdings_watch`'s own S-filing handling) but does **not** need the
    watchlist/pending-candidate skip since it never creates a `goat_pending_candidates`
    row.
  - `render_insider_scan_report` (348-504): the footer text at line 445
    (`f"{config.GOAT_INSIDER_PRICE_FLAG_PCT:.0f}%+"`) references the constant being
    removed — must be rewritten to describe the tiered thresholds instead of a single
    number.
- `investments/goat/goat/main.py` — `cmd_scan_insiders` (103-146) is the wiring point:
  add sell-tracking + snapshot-maturation + pattern-report calls here, per the
  handoff's own note that this "likely folds ... into the existing scan-insiders
  command as extra steps, rather than a new separate command/timer." `_open_conn`
  (8-19) shows the standard DB bootstrap; reuse it, don't duplicate.
- `investments/my-trader/mytrader/openinsider.py` (whole file, 197 lines) —
  `fetch_discovery_purchases` (181-185) is the exact function to mirror for
  `fetch_discovery_sales` (just swap the URL path and the trade-type filter — `_fetch`
  and `_parse_table` are already generic/reusable, no changes needed there).
  `_EXPECTED_COLUMNS` (54-67) already includes `"Title": "title"` — confirms `title` is
  already parsed into every row dict, just never persisted downstream.
- `investments/goat/goat/price_history.py` (whole file, 35 lines) —
  `fetch_close_history(ticker, lookback_days)` is ticker-agnostic (works for `"SPY"`
  with no new plumbing) and already falls back to the ASX `.AX` variant — the new
  horizon-fetch helper should call this the same way `_price_move_since` does.
- `investments/goat/goat/tests/conftest.py` (whole file) — `db_conn` fixture,
  `_isolate_goat_report_path` (must add `GOAT_INSIDER_PATTERN_ANALYSIS_PATH` to this
  list — see Task list), and `_no_real_price_history_fetch` (autouse stub on
  `goat.price_history.fetch_close_history` — every new test that needs real price data
  must explicitly `monkeypatch.setattr` it, same as all existing insider_scan tests do).
- `investments/goat/goat/tests/test_insider_scan.py` (whole file, 458 lines) — read in
  full before touching `insider_scan.py`. Verified during planning: none of the
  existing threshold-dependent tests (`test_compute_discovery_price_performance_flags_
  buy_that_rose_past_threshold` at 30 days/25% rise, `..._does_not_flag_below_threshold`
  at 30 days/5% rise, `..._notes_staleness_past_90_days` at 95 days/30% rise,
  `test_compute_holdings_watch_price_performance_flags_sale_that_fell` at 20 days/-20%)
  break under the new tiered thresholds — 30/95/20-day cases all fall on the same side
  of both the old flat 15% and the new tier (12.5% tail, or 7.5% at ≤21 days) as before.
  Confirm this stays true after implementing, don't assume it silently.
- `investments/my-trader/mytrader/tests/test_openinsider.py` (lines 1-70 read) —
  `_FAKE_HTML` fixture + `test_fetch_discovery_purchases_parses_table_and_filters_
  purchase_code` (32-40) is the exact pattern to mirror for
  `test_fetch_discovery_sales_...` (the existing fake HTML already contains one P row
  and one S row, so the sales-side test can reuse `_FAKE_HTML` directly, just asserting
  on the S row instead).
- `investments/goat/goat/tests/test_db.py` (lines 1-60 read) — CRUD test pattern
  (insert-then-get, twice-is-a-no-op) to mirror for the new price-outcomes table tests.
- `investments/goat/insider-scan-report.md` — spot-checked for real OpenInsider title
  values (2026-08-20 live report): `CFO`, `Dir`, `COO`, `Exec COB`, `Chief Strategy
  Officer`, `Pres`, `See Remarks`. Use this to ground the title-bucket classifier (see
  Task list) — do not invent title strings from imagination.
- `investments/TOOLS.md` (lines 19, 34) — the Goat Insider Scan row's description must
  be updated once behavior changes (sell tracking, tiered threshold, pattern report) —
  this file says "update this file whenever a tool's schedule or command changes."
- `investments/goat/insider-pattern-analysis-handoff.md` — the source handoff. Update
  its `## Status` line (line 3) once this plan exists, per this repo's own convention
  of keeping handoff status lines current (see recent commit
  `de4d15d docs(investments): fix stale handoff-doc status lines`).

### New Files to Create

- `investments/goat/goat/insider_pattern_analysis.py` — `compute_pattern_analysis`,
  `render_pattern_analysis_report`, `write_pattern_analysis_report`.
- `investments/goat/goat/tests/test_insider_pattern_analysis.py` — unit tests for the
  above.

### Files needing no changes but verified during planning as safe to depend on

- `investments/goat/goat/tests/test_insider_scan.py` (existing tests won't break, see
  above) — will still be **extended** with new tests, not just left alone.

### Documentation / External Research

- OpenInsider `/latest-insider-sales-100k` — the original insider-scanner handoff
  (`investments/insider-trading-scanner-handoff.md`) already identified this as
  OpenInsider's pre-thresholded market-wide sales page (mirrors `/latest-insider-
  purchases-25k`'s $25k pre-threshold, this one pre-thresholded at $100k). A live fetch
  to confirm the table's column shape was attempted during planning and failed
  (connection refused from the planning sandbox — network-level, not a scraper bug).
  **Do a live spot-check of this URL as the first implementation step** (a plain
  `requests.get` or browser view, not a plan-time blocker) before writing
  `fetch_discovery_sales` — `_parse_table` is already header-driven/generic (matches
  `_EXPECTED_COLUMNS` by header text, not fixed column position), so it will work as
  long as the page's table has a `<th>Ticker</th>` header, which is near-certain since
  OpenInsider renders all its listing pages through the same table component. If the
  live check finds actual differences, adjust `_EXPECTED_COLUMNS` usage accordingly —
  don't just assume and skip the check.

### Patterns to Follow

**Config constant provenance comments** (every constant in `goat/config.py` explains
*why* its value is what it is and who set it) — e.g. `config.py:240-243`:
```python
GOAT_INSIDER_PRICE_FLAG_PCT = 15.0  # Shaun 2026-08-18: flag price-since-trade moves
    # at +/-15% in the direction that CONFIRMS the insider signal only ...
```
New constants must follow this exactly, citing Shaun's 2026-08-20 decision where
applicable (see RESOLVED DECISIONS above).

**Idempotent SQLite migration pattern** (`db.py:60-95`):
```python
with conn:
    try:
        conn.execute("ALTER TABLE goat_insider_filings_seen ADD COLUMN pct_owned_change REAL")
    except sqlite3.OperationalError:
        pass
```

**"Fail open" on unparsable data** — `_pct_owned_change_clause` (insider_scan.py:31-40),
`_prior_sale_count` (43-55): never let a parsing gap silently drop or corrupt a real
signal; omit the enriching detail instead. Apply the same philosophy to horizon
maturation: if a price fetch fails for one horizon, skip just that horizon (leave it
unmatured, retry next run), never raise, never write a null/zero row that looks like a
real 0% outcome.

**DB-only vs. network-call separation** (`insider_scan.py` docstring lines 1-7, and
`compute_discovery_price_performance`'s own docstring at 232-242): `run_*` functions
that touch the DB stay network-free and cheap to test; price/network calls live in
separately-testable `compute_*`/new `mature_*` functions. Keep this split for the new
sell-tracking and maturation functions too.

**Report generation style** (`render_insider_scan_report`, `insider_scan.py:348-504`):
markdown headers, an explanatory sentence under each section, a table with a fixed
header constant (`_DISCOVERY_HEADER`/`_HOLDINGS_HEADER` pattern), "No X yet" fallback
text when a section/slice is empty. Mirror this for
`render_pattern_analysis_report` — including the advisor-notes-only, no-trade-action
framing every Goat report carries (see `insider_scan.py:353`).

---

## IMPLEMENTATION PLAN

### Phase 1: Schema + Config Foundation

- Add `title` column migration + thread `title` through
  `insert_goat_insider_filing_seen` and both existing call sites
  (`run_holdings_watch`, `run_discovery_scan`).
- Add `goat_insider_price_outcomes` table.
- Add new config constants (tiers, tail threshold, horizons, max tracking days,
  benchmark ticker, min sample size, cluster window, pattern report path); remove
  `GOAT_INSIDER_PRICE_FLAG_PCT` (fully superseded).

### Phase 2: Tiered Threshold (existing report, applied immediately)

- New `_threshold_for_days(days_since: int) -> float` in `insider_scan.py`, walking
  `config.GOAT_INSIDER_PRICE_FLAG_TIERS` then falling back to
  `config.GOAT_INSIDER_PRICE_FLAG_PCT_TAIL`.
- Change `_confirms_signal`/`_price_note` to use it instead of a flat `threshold` param.
- Update `render_insider_scan_report`'s footer text (line ~445) to describe the tiers
  instead of a single percentage.

### Phase 3: Market-Wide Sell Tracking

- `fetch_discovery_sales()` in `mytrader/openinsider.py`.
- `run_discovery_sell_tracking(conn)` in `insider_scan.py` — tracking-only, `kind=
  'discovery_sell'`, skips held tickers, no `goat_pending_candidates` row, no
  `maybe_notify`/WhatsApp.
- Wire into `cmd_scan_insiders`.

### Phase 4: Price-Outcome Snapshot Maturation

- New horizon-fixed price-fetch helper (distinct from `_price_move_since`).
- `mature_price_outcome_snapshots(conn)` — iterates filings within the 180-day max
  tracking window, matures any not-yet-captured horizon that's been reached, computes
  ticker + SPY move + excess return, persists via new `db.py` CRUD, with an
  in-run SPY-fetch cache to avoid redundant yfinance calls.
- Wire into `cmd_scan_insiders`.

### Phase 5: Pattern-Analysis Report

- `insider_pattern_analysis.py`: `compute_pattern_analysis` (queries
  `goat_insider_price_outcomes` joined to `goat_insider_filings_seen`, filtered to
  `kind IN ('discovery', 'discovery_sell')` only — market-wide, per the handoff's
  explicit "not his existing holdings watch" scoping), sliced by trade size, %-of-
  position, cluster buying/selling, elapsed-time velocity, insider title/role, buy vs.
  sell — each slice gated on `GOAT_INSIDER_PATTERN_MIN_SAMPLE`.
- `render_pattern_analysis_report` / `write_pattern_analysis_report`.
- Wire into `cmd_scan_insiders`; add path to `conftest.py`'s
  `_isolate_goat_report_path`.

### Phase 6: Wiring, Docs, Tests

- Update `cmd_scan_insiders` print summary.
- Update `TOOLS.md` Goat Insider Scan row.
- Update `insider-pattern-analysis-handoff.md`'s Status line.
- Full test pass across all phases.

---

## STEP-BY-STEP TASKS

### UPDATE investments/goat/goat/db.py

- **IMPLEMENT**: Add a new idempotent migration block (mirroring lines 79-95) adding
  `title TEXT` to `goat_insider_filings_seen`, defaulting existing rows to `''` (SQLite
  `ALTER TABLE ADD COLUMN` with no `NOT NULL DEFAULT` needed here since the field is
  informational-only, same nullability posture as `pct_owned_change`).
- **IMPLEMENT**: Add `goat_insider_price_outcomes` to the `executescript` block (new
  table, no migration needed — it doesn't exist in any prior DB):
  ```sql
  CREATE TABLE IF NOT EXISTS goat_insider_price_outcomes (
      dedup_key             TEXT NOT NULL,
      ticker                TEXT NOT NULL,
      trade_type            TEXT NOT NULL,
      horizon_days          INTEGER NOT NULL,
      pct_change            REAL,
      benchmark_pct_change  REAL,
      excess_pct_change     REAL,
      snapshot_date         TEXT NOT NULL,
      PRIMARY KEY (dedup_key, horizon_days)
  );
  ```
- **IMPLEMENT**: `insert_goat_insider_filing_seen` gains `title: str = ""` param,
  inserted into the new column. Update the INSERT statement's column list + VALUES.
- **IMPLEMENT**: `get_captured_horizons(conn, dedup_key) -> set[int]` — `SELECT
  horizon_days FROM goat_insider_price_outcomes WHERE dedup_key = ?`, return as a set
  for O(1) membership checks in the maturation loop.
- **IMPLEMENT**: `insert_price_outcome(conn, *, dedup_key, ticker, trade_type,
  horizon_days, pct_change, benchmark_pct_change, excess_pct_change, snapshot_date) ->
  None` — `INSERT OR IGNORE` (PK is `dedup_key, horizon_days`; a horizon is immutable
  once matured, no update path needed — mirrors `insert_goat_insider_filing_seen`'s own
  `INSERT OR IGNORE` philosophy).
- **IMPLEMENT**: `get_price_outcomes_for_pattern_analysis(conn) -> list[sqlite3.Row]` —
  join query: `SELECT o.*, f.value, f.pct_owned_change, f.title, f.trade_date, f.
  insider_name, f.kind FROM goat_insider_price_outcomes o JOIN goat_insider_filings_seen
  f ON o.dedup_key = f.dedup_key WHERE f.kind IN ('discovery', 'discovery_sell')`.
- **IMPLEMENT**: `get_filings_for_cluster_detection(conn, ticker, trade_type,
  around_date, window_days) -> list[sqlite3.Row]` — or fold cluster detection into a
  single query over `get_recent_insider_filings_seen`-style access in
  `insider_pattern_analysis.py` instead (implementer's call — a dedicated DB helper is
  cleaner if the query is reused across multiple slices, otherwise compute in Python
  from `get_price_outcomes_for_pattern_analysis`'s already-fetched rows to avoid N+1
  queries per filing).
- **PATTERN**: `db.py:60-95` (migration), `db.py:204-221` (insert w/ optional field),
  `db.py:244-259` (windowed COUNT query).
- **GOTCHA**: SQLite has no `ADD COLUMN IF NOT EXISTS` — the try/except pattern is
  mandatory, and it must run every `init_goat_tables` call (idempotent), not just once.
- **VALIDATE**: `uv run --directory investments/goat python -m pytest goat/tests/test_db.py -q`

### UPDATE investments/goat/goat/config.py

- **IMPLEMENT**: Remove `GOAT_INSIDER_PRICE_FLAG_PCT` (fully superseded). Keep
  `GOAT_INSIDER_PRICE_STALE_DAYS` untouched (unchanged, see RESOLVED DECISIONS #5).
- **IMPLEMENT**: Add, with provenance comments matching this file's existing style:
  ```python
  GOAT_INSIDER_PRICE_FLAG_TIERS: list[tuple[int, float]] = [
      (7, 2.5), (14, 5.0), (21, 7.5), (28, 10.0),
  ]  # (max_days_since_trade, threshold_pct), ascending. Shaun's own numbers,
     # 2026-08-20 -- supersedes the old flat GOAT_INSIDER_PRICE_FLAG_PCT (15.0)
     # immediately, applied to BOTH the live insider-scan report's confirms-signal
     # flag AND the price-outcomes dataset's "confirmed" labeling, so the two never
     # drift apart. A fast, small move is treated as more meaningful than a slow,
     # large one (price moves grow with elapsed time under normal random-walk
     # drift, so a flat threshold was implicitly biased the wrong way).
  GOAT_INSIDER_PRICE_FLAG_PCT_TAIL = 12.5  # threshold once days_since_trade exceeds
      # the last tier's max_days (28) -- Shaun's number, 2026-08-20.

  GOAT_INSIDER_OUTCOME_HORIZONS_DAYS: list[int] = [1, 3, 7, 14, 30, 90, 180]  # snapshot
      # schedule for goat_insider_price_outcomes. Includes 180 to match the max
      # tracking window below (Shaun 2026-08-20: raised from 90 -> 180 days) --
      # without a matching 180d horizon the extended window would collect no new
      # snapshot past day 90, defeating the point of the extension.
  GOAT_INSIDER_OUTCOME_MAX_TRACKING_DAYS = 180  # Shaun 2026-08-20: raised from the
      # handoff doc's original 90-day proposal to better match how insider-trading
      # literature typically studies outcomes (6-12 months) -- filings older than
      # this stop maturing new snapshot horizons. Distinct from
      # GOAT_INSIDER_PRICE_STALE_DAYS (90, unchanged) -- that constant is about the
      # existing report's "may be stale" annotation for repeated-sale-pattern
      # detection, a different concern.
  GOAT_INSIDER_OUTCOME_BENCHMARK_TICKER = "SPY"  # excess-return benchmark for every
      # slice -- SPY-only, not per-sector (most discovery candidates are smaller-cap
      # names outside goat_sp500_constituents coverage anyway). "Buys rose 60% of
      # the time" during a market rally isn't an insider-specific signal without
      # this -- excess return isolates the trade-attributable part.
  GOAT_INSIDER_PATTERN_MIN_SAMPLE = 20  # minimum filings in a slice before the
      # pattern report states a conclusion instead of "not enough data yet". Trade
      # dates only go back to 2026-08-12 as of this build -- most slices are
      # expected to say "not enough data yet" for the first several weeks, that's
      # expected, not a bug.
  GOAT_INSIDER_CLUSTER_WINDOW_DAYS = 7  # multiple distinct insiders on the same
      # ticker/trade_type within this many days counts as cluster buying/selling --
      # v1/tunable, rounded up slightly from the GOAT_INSIDER_HOLDINGS_WATCH_
      # LOOKBACK_DAYS/GOAT_INSIDER_DISCOVERY_LOOKBACK_DAYS precedent (5 days).

  GOAT_INSIDER_PATTERN_ANALYSIS_PATH = GOAT_DIR / "insider-pattern-analysis.md"
  ```
- **PATTERN**: `config.py:240-247` (the block being replaced/extended).
- **VALIDATE**: `uv run --directory investments/goat python -c "from goat import config; print(config.GOAT_INSIDER_PRICE_FLAG_TIERS)"`

### UPDATE investments/goat/goat/insider_scan.py

- **IMPLEMENT**: `_threshold_for_days(days_since: int) -> float`:
  ```python
  def _threshold_for_days(days_since: int) -> float:
      for max_days, pct in config.GOAT_INSIDER_PRICE_FLAG_TIERS:
          if days_since <= max_days:
              return pct
      return config.GOAT_INSIDER_PRICE_FLAG_PCT_TAIL
  ```
- **IMPLEMENT**: `_confirms_signal(trade_type_code, pct_change, days_since)` — replace
  the `threshold: float` param with `days_since: int`, calling `_threshold_for_days`
  internally. Update both call sites (`_price_note`, and anywhere else that called
  `_confirms_signal(..., config.GOAT_INSIDER_PRICE_FLAG_PCT)` directly).
- **IMPLEMENT**: `_price_note(pct_change, days_since, trade_type_code)` — drop the now-
  implicit threshold arg from its internal `_confirms_signal` call (days_since already
  a param); keep the staleness clause using `config.GOAT_INSIDER_PRICE_STALE_DAYS`
  unchanged.
- **IMPLEMENT**: `fetch_discovery_sales` import — `from mytrader import openinsider`
  already imported at line 18, `openinsider.fetch_discovery_sales` becomes callable
  the same way `openinsider.fetch_discovery_purchases` is at line 129.
- **IMPLEMENT**: `run_discovery_sell_tracking(conn) -> dict[str, Any]`:
  ```python
  def run_discovery_sell_tracking(conn: sqlite3.Connection) -> dict[str, Any]:
      """Market-wide sell tracking, data-only -- explicitly no
      goat_pending_candidates row and no WhatsApp notify (Shaun 2026-08-20: there's
      no 'should I act on this' question for a sell on a stock he doesn't hold,
      it's purely a data point for insider_pattern_analysis). Held tickers are
      skipped -- those sells are already covered by run_holdings_watch."""
      held_tickers = {row["ticker"] for row in mt_db.get_all_holdings(conn)}
      rows = openinsider.fetch_discovery_sales()
      if rows is None:
          print("[goat-insider-scan] OpenInsider sell-discovery fetch failed")
          return {"tracked": 0}

      tracked = 0
      for row in rows:
          if not _within_lookback(row.get("trade_date", ""), config.GOAT_INSIDER_DISCOVERY_LOOKBACK_DAYS):
              continue
          if row["ticker"] in held_tickers:
              continue
          dedup_key = openinsider.build_dedup_key(row)
          newly_seen = db.insert_goat_insider_filing_seen(
              conn, dedup_key=dedup_key, ticker=row["ticker"],
              filing_date=row.get("filing_date", ""), trade_date=row.get("trade_date", ""),
              insider_name=row.get("insider_name", ""), trade_type=row["trade_type_code"],
              value=row["value"], kind="discovery_sell",
              pct_owned_change=row.get("pct_owned_change"), title=row.get("title", ""),
          )
          if newly_seen:
              tracked += 1
      return {"tracked": tracked}
  ```
- **IMPLEMENT**: Thread `title=row.get("title", "")` into the two *existing*
  `insert_goat_insider_filing_seen` call sites too (`run_holdings_watch` line ~78-83,
  `run_discovery_scan` line ~149-154) — this is the "add title as a real column"
  half of the handoff's Current State observation, applies to buys and holdings-watch
  filings as well, not just the new sell path.
- **IMPLEMENT**: New fixed-horizon price helper (do NOT reuse `_price_move_since`,
  which measures to *today*, not a fixed horizon):
  ```python
  def _price_at_horizon(ticker: str, trade_date_str: str, horizon_days: int) -> dict[str, Any] | None:
      """pct_change from the close on/after trade_date_str to the close on/after
      trade_date_str + horizon_days -- distinct from _price_move_since, which
      measures to *today's* latest close. Returns None on unparsable date or a
      price-fetch/window miss; callers must treat that as 'not yet maturable',
      not zero."""
      try:
          trade_date_obj = datetime.strptime(trade_date_str, "%Y-%m-%d").date()
      except (ValueError, TypeError):
          return None
      target_date = trade_date_obj + timedelta(days=horizon_days)
      days_since_trade = (date.today() - trade_date_obj).days
      if days_since_trade < horizon_days:
          return None  # horizon not reached yet

      close = price_history.fetch_close_history(ticker, days_since_trade + 10)
      if close is None or close.empty:
          return None
      start_slice = close[close.index >= pd.Timestamp(trade_date_obj)]
      end_slice = close[close.index >= pd.Timestamp(target_date)]
      if start_slice.empty or end_slice.empty:
          return None
      start_price = float(start_slice.iloc[0])
      end_price = float(end_slice.iloc[0])
      if start_price == 0:
          return None
      return {"pct_change": (end_price - start_price) / start_price * 100}
  ```
- **IMPLEMENT**: `mature_price_outcome_snapshots(conn) -> dict[str, Any]`:
  ```python
  def mature_price_outcome_snapshots(conn: sqlite3.Connection) -> dict[str, Any]:
      """Nightly job: for every filing within GOAT_INSIDER_OUTCOME_MAX_TRACKING_DAYS
      of its trade date, insert any not-yet-captured horizon that's been reached.
      Independent of goat_pending_candidates' lifecycle -- dismissing/promoting a
      candidate no longer destroys its outcome history."""
      matured = 0
      benchmark_cache: dict[tuple[str, int], float | None] = {}
      filings = db.get_recent_insider_filings_seen(conn, limit=100000)  # or a new
          # db.get_filings_within_days(conn, max_days) if 100000 feels like an abuse
          # of an existing function's limit param -- implementer's call, but must
          # cover the full max-tracking-window population, not just "recent 50".
      for filing in filings:
          if not _within_lookback(filing["trade_date"], config.GOAT_INSIDER_OUTCOME_MAX_TRACKING_DAYS):
              continue
          captured = db.get_captured_horizons(conn, filing["dedup_key"])
          for horizon in config.GOAT_INSIDER_OUTCOME_HORIZONS_DAYS:
              if horizon in captured:
                  continue
              outcome = _price_at_horizon(filing["ticker"], filing["trade_date"], horizon)
              if outcome is None:
                  continue
              cache_key = (filing["trade_date"], horizon)
              if cache_key not in benchmark_cache:
                  bm = _price_at_horizon(
                      config.GOAT_INSIDER_OUTCOME_BENCHMARK_TICKER, filing["trade_date"], horizon
                  )
                  benchmark_cache[cache_key] = bm["pct_change"] if bm else None
              benchmark_pct = benchmark_cache[cache_key]
              excess_pct = (
                  outcome["pct_change"] - benchmark_pct if benchmark_pct is not None else None
              )
              db.insert_price_outcome(
                  conn, dedup_key=filing["dedup_key"], ticker=filing["ticker"],
                  trade_type=filing["trade_type"], horizon_days=horizon,
                  pct_change=outcome["pct_change"], benchmark_pct_change=benchmark_pct,
                  excess_pct_change=excess_pct, snapshot_date=date.today().isoformat(),
              )
              matured += 1
      return {"matured": matured}
  ```
  **GOTCHA**: `_within_lookback` is direction-agnostic ("within N days of today", used
  today for *future*-safe freshness checks) — confirm it behaves correctly here too
  (filing 179 days old → within 180-day lookback → True; 181 days old → False). Verify
  with a unit test at the exact boundary (179/180/181 days).
- **IMPLEMENT**: Update `render_insider_scan_report`'s footer (~line 445) — replace
  `f"{config.GOAT_INSIDER_PRICE_FLAG_PCT:.0f}%+"` with a tier-describing string, e.g.
  `"a threshold that starts at 2.5% within 7 days and widens to 12.5% after 28 days"`
  (derive the text from `config.GOAT_INSIDER_PRICE_FLAG_TIERS` +
  `GOAT_INSIDER_PRICE_FLAG_PCT_TAIL` programmatically if you want it to never drift
  out of sync with the config, rather than hardcoding the English description).
- **PATTERN**: `insider_scan.py:128-175` (`run_discovery_scan`, mirror for sell
  tracking), `insider_scan.py:178-206` (`_price_move_since`, contrast with new
  `_price_at_horizon`), `insider_scan.py:209-229` (threshold functions being changed).
- **VALIDATE**: `uv run --directory investments/goat python -m pytest goat/tests/test_insider_scan.py -q`

### UPDATE investments/my-trader/mytrader/openinsider.py

- **IMPLEMENT**:
  ```python
  def fetch_discovery_sales() -> list[dict] | None:
      rows = _fetch(f"{config.OPENINSIDER_BASE_URL}/latest-insider-sales-100k")
      if rows is None:
          return None
      return [r for r in rows if r["trade_type_code"] == "S"]
  ```
- **PATTERN**: `openinsider.py:181-185` (`fetch_discovery_purchases`) — identical
  shape, different URL path and trade-type filter.
- **GOTCHA**: Live-verify `/latest-insider-sales-100k`'s table shape first (see
  Documentation section above) — if OpenInsider's sales page uses different header
  text for any column, `_EXPECTED_COLUMNS`/`_parse_table` may need a column-name
  alias, not just a URL swap.
- **VALIDATE**: `uv run --directory investments/my-trader python -m pytest mytrader/tests/test_openinsider.py -q`

### UPDATE investments/goat/goat/main.py

- **IMPLEMENT**: In `cmd_scan_insiders` (103-146), after the existing
  `run_discovery_scan`/price-performance calls and before `conn.close()`:
  ```python
  sell_tracking_result = insider_scan.run_discovery_sell_tracking(conn)
  maturation_result = insider_scan.mature_price_outcome_snapshots(conn)
  ```
  After `conn.close()` (or before it, matching whichever the pattern-analysis function
  needs — it reads via its own `_open_conn`-style connection, or reuse the same `conn`
  before closing, implementer's call for consistency with how `write_insider_scan_
  report` is called outside the `conn` scope already):
  ```python
  from .insider_pattern_analysis import compute_pattern_analysis, write_pattern_analysis_report
  pattern_analysis = compute_pattern_analysis(conn)  # call before conn.close() if it needs conn
  write_pattern_analysis_report(pattern_analysis)
  ```
- **IMPLEMENT**: Extend the final `print(...)` summary to mention sell-tracking count,
  snapshots matured, and the new report path.
- **PATTERN**: `main.py:103-146` (existing `cmd_scan_insiders`), `main.py:8-19`
  (`_open_conn`).
- **VALIDATE**: `uv run --directory investments/goat python -m goat.main scan-insiders`
  (manual run — inspect `investments/goat/insider-scan-report.md` and the new
  `investments/goat/insider-pattern-analysis.md` for sane output, no exceptions).

### CREATE investments/goat/goat/insider_pattern_analysis.py

- **IMPLEMENT**: `_classify_trade_size(value: float) -> str` — buckets: `"<$50k"`,
  `"$50k-250k"`, `"$250k-1M"`, `"$1M+"`.
- **IMPLEMENT**: `_classify_pct_owned(pct: float | None) -> str` — buckets: `"New"`
  (pct is None), `"<5%"`, `"5-25%"`, `"25-100%"` (use `abs(pct)` since sells are
  negative).
- **IMPLEMENT**: `_classify_title(title: str) -> str` — buckets: `"Officer/Chair"`,
  `"Director"`, `"10% Owner"`, `"Other"`. Ground the keyword matching in the *real*
  title strings observed in `insider-scan-report.md` during planning (`CFO`, `Dir`,
  `COO`, `Exec COB`, `Chief Strategy Officer`, `Pres`, `See Remarks`) — e.g. substring
  match on `{"CEO", "CFO", "COO", "CTO", "Pres", "Chief", "COB"}` → Officer/Chair;
  `"Dir"` → Director; `"10%"` → 10% Owner; everything else (including `"See Remarks"`)
  → Other. Do not assume OpenInsider uses full words like "Chairman" — the live data
  uses abbreviations.
- **IMPLEMENT**: Cluster detection — for each filing, count *distinct* `insider_name`
  values on the same `ticker` + `trade_type` with `trade_date` within
  `config.GOAT_INSIDER_CLUSTER_WINDOW_DAYS` of this filing's own `trade_date` (both
  directions). A filing is "clustered" if that count is ≥ 2. Compute this once over the
  full filing set for the report (not per-row DB queries — O(n²) over a dataset that's
  currently ~15-20/day is fine, revisit only if it becomes a real perf problem).
- **IMPLEMENT**: Elapsed-time velocity slice — cross-reference each filing's early
  horizon (7d) `excess_pct_change` sign against its later horizon (30d and/or 90d)
  `excess_pct_change` sign; report what fraction of "confirmed-early" filings (7d
  crossed the tier threshold) also ended up excess-positive (buys)/excess-negative
  (sells) at 30d/90d.
- **IMPLEMENT**: `compute_pattern_analysis(conn) -> dict[str, Any]` — pulls
  `db.get_price_outcomes_for_pattern_analysis(conn)`, applies each slice above, and for
  every slice: if `n < config.GOAT_INSIDER_PATTERN_MIN_SAMPLE`, the slice's result is
  `{"status": "insufficient_data", "n": n}`; otherwise a real stats dict (e.g. `{"n":
  n, "pct_direction_confirmed": ..., "avg_excess_pct_change": ...}` — implementer's
  call on exact stat shape per slice, but every slice must carry `n` and a plain-
  English confirm-rate at minimum).
- **IMPLEMENT**: `render_pattern_analysis_report(analysis: dict) -> str` — markdown,
  mirroring `render_insider_scan_report`'s style: header, one explanatory sentence per
  section, "not enough data yet (n=X, need {MIN_SAMPLE})" fallback per slice, and an
  explicit disclaimer paragraph near the top: *"This report is correlational/
  exploratory on Shaun's own captured OpenInsider data, not a validated trading
  strategy — no trade action is ever suggested here (see SOUL.md). Trade dates in the
  dataset only go back to 2026-08-12; most slices are expected to need real time
  before a pattern is statistically meaningful."*
- **IMPLEMENT**: `write_pattern_analysis_report(analysis: dict) -> None` — writes to
  `config.GOAT_INSIDER_PATTERN_ANALYSIS_PATH`, same `write_text(..., encoding="utf-8")`
  idiom as `write_insider_scan_report`.
- **PATTERN**: `insider_scan.py:348-511` (`render_insider_scan_report`/
  `write_insider_scan_report`) for report structure; `insider_scan.py:31-40`
  (`_pct_owned_change_clause`) for the "fail open, omit rather than guess" philosophy
  applied to bucket classification of missing/odd data.
- **VALIDATE**: `uv run --directory investments/goat python -m pytest goat/tests/test_insider_pattern_analysis.py -q`

### UPDATE investments/goat/goat/tests/conftest.py

- **IMPLEMENT**: Add to `_isolate_goat_report_path`:
  ```python
  monkeypatch.setattr(
      goat_config, "GOAT_INSIDER_PATTERN_ANALYSIS_PATH", tmp_path / "insider-pattern-analysis.md"
  )
  ```
- **PATTERN**: `conftest.py:29-42` (existing fixture, same shape for each new report
  path).
- **VALIDATE**: implicit — covered by the full suite run below.

### UPDATE investments/goat/goat/tests/test_insider_scan.py

- **IMPLEMENT**: Add tests for:
  - `_threshold_for_days` boundary values: 7→2.5, 8→5.0, 14→5.0, 15→7.5, 21→7.5,
    22→10.0, 28→10.0, 29→12.5, 100→12.5.
  - `title` persists through `run_holdings_watch` and `run_discovery_scan` (assert via
    `goat_db.get_recent_insider_filings_seen`/`get_goat_pending_candidate` that the
    stored row's `title` column matches the fixture's `"CFO"`/`"Director"`).
  - `run_discovery_sell_tracking`: stages nothing in `goat_pending_candidates`, no
    `maybe_notify`/notification call needed (function doesn't call it), inserts into
    `goat_insider_filings_seen` with `kind='discovery_sell'`, skips a ticker that's a
    current holding, respects the discovery lookback window, handles fetch failure
    (`None`) gracefully, is a no-op on repeat runs (dedup via `dedup_key`).
  - `_price_at_horizon`: matures correctly at exact horizon, returns `None` when
    horizon not yet reached (days_since_trade < horizon_days), returns `None` on a
    price-fetch miss.
  - `mature_price_outcome_snapshots`: matures the right set of horizons for a filing at
    a given age (e.g. a 35-day-old filing should have 1/3/7/14/30 matured, not 90/180),
    skips horizons already captured (no duplicate `INSERT`/no re-fetch — assert fetch
    call count), skips filings older than
    `GOAT_INSIDER_OUTCOME_MAX_TRACKING_DAYS` (179/180/181-day boundary), computes
    `excess_pct_change` correctly against a mocked SPY series, and caches the
    benchmark fetch within a single run (same `(trade_date, horizon)` pair fetched
    once even across multiple filings sharing that trade_date+horizon).
- **PATTERN**: existing tests in this file, e.g. `test_run_discovery_scan_skips_ticker_
  already_a_holding` (229-237) for the sell-tracking held-ticker-skip test;
  `test_compute_discovery_price_performance_marks_newly_flagged_once` (357-376) for the
  dedup-guard testing style; `_price_series` helper (308-316) reusable/adaptable for
  `_price_at_horizon` tests.
- **VALIDATE**: `uv run --directory investments/goat python -m pytest goat/tests/test_insider_scan.py -q -v`

### UPDATE investments/goat/goat/tests/test_db.py

- **IMPLEMENT**: Tests for the `title` column migration/persistence,
  `get_captured_horizons` (empty → returns `set()`; after insert → contains the
  horizon), `insert_price_outcome` (insert-then-query works; inserting the same
  `dedup_key`+`horizon_days` twice is a no-op, mirroring `test_insert_goat_pending_
  candidate_twice_is_a_no_op`), `get_price_outcomes_for_pattern_analysis` (returns
  joined rows with `value`/`title`/`kind` present; excludes `kind='holdings_watch'`
  rows).
- **PATTERN**: `test_db.py:45-60` (`test_insert_goat_pending_candidate_then_get_finds_
  it` / twice-is-a-no-op pattern).
- **VALIDATE**: `uv run --directory investments/goat python -m pytest goat/tests/test_db.py -q -v`

### UPDATE investments/my-trader/mytrader/tests/test_openinsider.py

- **IMPLEMENT**: `test_fetch_discovery_sales_parses_table_and_filters_sale_code` —
  reuse `_FAKE_HTML` (already contains a `BRK.B` sale row), assert `ticker == "BRK.B"`
  (or its normalized form), `trade_type_code == "S"`, `value == 2_000_000.0`. Plus the
  same failure-mode tests as `fetch_discovery_purchases` (missing table, bad status,
  network error) — mirror lines 63-78.
- **PATTERN**: `test_openinsider.py:32-78` (the whole `fetch_discovery_purchases` test
  block).
- **VALIDATE**: `uv run --directory investments/my-trader python -m pytest mytrader/tests/test_openinsider.py -q -v`

### UPDATE investments/TOOLS.md

- **IMPLEMENT**: Extend the "Goat Insider Scan" row's description (line 19) to mention:
  market-wide sell tracking (data-only, no candidates/alerts), the tiered confirmation
  threshold (2.5%→12.5% graduated by elapsed days, replacing the flat 15%), and the new
  nightly `insider-pattern-analysis.md` report. Add a "Goat insider pattern analysis"
  row to the Manual/on-demand table only if you also expose it as a standalone
  subcommand — per this plan's Phase 6 wiring, it is NOT a standalone subcommand
  (folded into `scan-insiders`), so no new row is needed there, only the schedule-table
  description update.
- **VALIDATE**: manual read-through, no automated check for a markdown doc.

### UPDATE investments/goat/insider-pattern-analysis-handoff.md

- **IMPLEMENT**: Change line 3 `## Status: Not started — design discussed 2026-08-20,
  ready for /plan-feature (Shaun to run in a separate session)` to `## Status:
  Planned 2026-08-20 — see .agent/plans/insider-pattern-analysis.md` (or `Implemented`
  + a completion date, once `/execute` actually finishes it — whichever is accurate at
  the time this line is edited).
- **VALIDATE**: manual read-through.

---

## TESTING STRATEGY

### Unit Tests

Every new function gets direct unit-test coverage following this codebase's existing
`pytest` + `monkeypatch` + `db_conn` fixture conventions (no new test framework, no new
fixture patterns beyond what `conftest.py` already provides). DB-only functions
(`run_discovery_sell_tracking`'s DB writes, `db.py` CRUD) are tested without mocking
network calls; price-fetch-dependent functions (`_price_at_horizon`,
`mature_price_outcome_snapshots`) mock `goat.insider_scan.price_history.fetch_close_
history` via `monkeypatch.setattr`, exactly like every existing price-performance test
in `test_insider_scan.py` does.

### Integration Tests

No dedicated integration-test tier exists in this codebase beyond the unit tests above
(confirmed — `investments/goat` has no `test_main.py` / CLI-level test file; `main.py`
is validated by manual runs, not automated tests, matching the existing convention for
every other `cmd_*` function in this file). Manual validation (Level 4 below) is this
feature's integration check.

### Edge Cases

- Filing with unparsable/missing `trade_date` — must never crash `mature_price_outcome_
  snapshots` or `run_discovery_sell_tracking` (mirrors `_within_lookback`'s existing
  fail-safe `except (ValueError, TypeError): return True` behavior).
- A ticker that gets delisted/has no yfinance data mid-tracking-window — `_price_at_
  horizon` returns `None`, that horizon is simply never matured (retried indefinitely
  on future runs until the 180-day window closes it out — acceptable, matches this
  codebase's existing "fail open, never guess" philosophy).
- A filing exactly at a tier boundary (7, 14, 21, 28 days) — inclusive per the RESOLVED
  DECISIONS table (`≤ 7` means day 7 itself gets the 2.5% tier, not 5%).
- A filing exactly at the 180-day max-tracking-window boundary — day 180 itself should
  still mature (inclusive), day 181 should not.
- `pct_owned_change` of `None` ("New" position) in the pattern report's %-of-position
  slice — must bucket as `"New"`, not crash or silently drop the row from the dataset
  entirely (it should still count in trade-size/title/buy-vs-sell slices, just not
  contribute to the %-of-position slice's non-New buckets).
- Two insiders at the same company, same day, same trade_type — cluster detection must
  count them as 2 distinct (by `insider_name`), not 1.
- Sell tracked for a ticker Shaun happens to hold — must be excluded (silently skipped,
  not double-logged under a different `kind`), per the held-ticker skip in
  `run_discovery_sell_tracking`.

---

## VALIDATION COMMANDS

Execute every command to ensure zero regressions and 100% feature correctness.

### Level 1: Syntax & Style

No dedicated linter/formatter config was found for `investments/goat` or
`investments/my-trader` beyond what `pytest`'s own collection enforces (import errors
surface as collection failures). If a `ruff`/`black` config is discovered during
implementation that this plan missed, run it — otherwise this level is a no-op beyond
Level 2's collection step.

### Level 2: Unit Tests

```powershell
uv run --directory investments/goat python -m pytest -q
uv run --directory investments/my-trader python -m pytest -q
```

### Level 3: Integration Tests

N/A — see Testing Strategy above (no CLI-level automated test tier in this codebase).

### Level 4: Manual Validation

```powershell
uv run --directory investments/goat python -m goat.main scan-insiders
```
Then read:
- `investments/goat/insider-scan-report.md` — confirm the footer no longer references
  a flat 15%, confirm 🚩 flags still render sensibly on real current data.
- `investments/goat/insider-pattern-analysis.md` — confirm it's created, confirm
  slices with insufficient sample say so plainly (expected for most/all slices this
  early — dataset only starts 2026-08-12), confirm no exception was thrown mid-run.

Run it a second time immediately after and confirm: no duplicate `goat_insider_price_
outcomes` rows, no duplicate `discovery_sell` filings logged, `mature_price_outcome_
snapshots`'s "matured" count drops to (near) 0 on the second run for filings whose
reachable horizons haven't changed.

### Level 5: Additional Validation

None applicable (no MCP servers relevant to this feature).

---

## ACCEPTANCE CRITERIA

- [ ] `goat_insider_filings_seen.title` persists real title values from OpenInsider for
  both buys and sells, holdings-watch and discovery.
- [ ] `fetch_discovery_sales()` returns S-type rows from `/latest-insider-sales-100k`,
  verified against a live spot-check (not assumed).
- [ ] Market-wide sells are logged (`kind='discovery_sell'`) but never create a
  `goat_pending_candidates` row and never trigger a WhatsApp/toast notification.
- [ ] Held tickers are excluded from sell tracking (no duplicate/conflicting `kind` on
  the same `dedup_key` from both `run_holdings_watch` and `run_discovery_sell_tracking`).
- [ ] The tiered threshold (2.5/5/7.5/10/12.5% at ≤7/14/21/28/>28 days) is live in
  **both** the existing insider-scan report's 🚩 flag and the outcomes dataset's
  "confirmed" labeling, with no flat `GOAT_INSIDER_PRICE_FLAG_PCT` remaining anywhere.
- [ ] `goat_insider_price_outcomes` snapshots persist across `goat_pending_candidates`
  dismiss/promote — a dismissed candidate's outcome history is still queryable.
- [ ] Horizons mature correctly at 1/3/7/14/30/90/180 days, respecting the 180-day max
  tracking window boundary.
- [ ] `insider-pattern-analysis.md` is generated nightly (folded into `scan-insiders`),
  slices by trade size / %-of-position / cluster / velocity / title / buy-vs-sell, each
  gated on n≥20, with an explicit correlational-not-a-strategy disclaimer.
- [ ] All existing `test_insider_scan.py` tests still pass unmodified (confirmed
  compatible with the tiered threshold during planning) plus new tests for every
  function added above.
- [ ] `TOOLS.md` and the source handoff's Status line are updated.

---

## COMPLETION CHECKLIST

- [ ] All tasks completed in order (Phase 1 → 6)
- [ ] Each task's validation command passed immediately after that task
- [ ] Full test suite passes: `uv run --directory investments/goat python -m pytest -q`
  and `uv run --directory investments/my-trader python -m pytest -q`
- [ ] Manual `scan-insiders` run (Level 4) completed twice, second run shows no
  duplicate work
- [ ] Both new report files read sanely by a human (Shaun)
- [ ] Acceptance criteria all met
- [ ] `TOOLS.md` + handoff Status line updated

---

## NOTES

- **Why not reuse `_price_move_since` for horizon snapshots**: it deliberately measures
  to *today's* latest close (for the live "where does this stand right now" report
  column); the outcomes table needs a *fixed* point-in-time snapshot at exactly N days
  post-trade, which is a different query shape entirely (see `_price_at_horizon` above).
  Conflating the two would make outcomes non-reproducible (a "30-day" snapshot's value
  would silently drift depending on what day `mature_price_outcome_snapshots` happened
  to run).
- **Why sells skip held tickers rather than just relying on `dedup_key` collision**:
  `dedup_key` is identical regardless of `kind` (built purely from ticker/dates/
  insider/type/value), so if both `run_holdings_watch` and an unfiltered `run_
  discovery_sell_tracking` raced to insert the same filing, whichever ran first would
  win the `kind` label via `INSERT OR IGNORE` — silently mislabeling a holdings-watch
  filing as `discovery_sell` (or vice versa) depending on call order. Filtering held
  tickers out of the sell-tracking path up front avoids this ambiguity entirely and
  matches the handoff's own scoping ("not worried about held stocks here").
  - This also matters for `compute_pattern_analysis`'s `kind IN ('discovery',
    'discovery_sell')` filter staying a clean, unambiguous "market-wide only" dataset.
- **Confidence score: 7/10** for one-pass implementation success. The schema/config/
  threshold/sell-tracking pieces (Phases 1-3) are low-risk, mirror existing patterns
  almost exactly, and are well-covered by the existing test suite's own precedent. The
  main risk areas: (a) the live `/latest-insider-sales-100k` shape was never actually
  confirmed during planning (network-blocked) — budget time for a real spot-check and
  possible `_EXPECTED_COLUMNS` adjustment; (b) `mature_price_outcome_snapshots`'s exact
  data-fetching-population strategy (`get_recent_insider_filings_seen(limit=100000)` is
  a placeholder — a cleaner dedicated query may be warranted) is left as an implementer
  judgment call rather than fully specified; (c) `insider_pattern_analysis.py`'s exact
  per-slice stat shape is deliberately left with some latitude ("implementer's call")
  since the handoff itself treats this as an evolving/tunable report, not a fixed spec.
