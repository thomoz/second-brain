# Feature: Universal Insider-Buy Discovery + Live Buy-Cluster & Insider-Flip Alerting

The following plan should be complete, but it's important to validate documentation and
codebase patterns and task sanity before implementing.

Pay special attention to naming of existing utils/types/models. Import from the right
files. In particular: `mytrader` must never import from `goat` (goat depends on
my-trader, not the reverse — see `mytrader/openinsider.py`'s module docstring).

## Feature Description

Fixes two real bugs and ships two new live-alert signals in Goat's insider-trading
scanner (`investments/goat/goat/insider_scan.py`), found while investigating why a real
insider-buy cluster (Upbound Group / UPBD, 6 distinct insiders, $50K–$400K each,
Nov 2–3 2026) never generated a WhatsApp notification:

1. **Bug — discovery scan silently skips held/watchlisted tickers.** `run_discovery_scan`
   drops any ticker already in `holdings.md` or `watchlist.md`, so a ticker on the
   watchlist but not yet held gets **zero** insider-buy coverage today. Shaun wants
   insider-buy coverage to never depend on hold/watch status.
2. **Bug — the discovery feed silently truncates on busy days.** `fetch_discovery_purchases()`
   hits a fixed, unpaginated "latest N" snapshot page
   (`/latest-insider-purchases-25k`) with no date/count params. Smaller trades roll
   off the page before any day's run reads them, with no backfill. Confirmed live on
   the VPS: none of the 6 UPBD Nov 2–3 buys ever reached `goat_insider_filings_seen`,
   even though the scan ran clean every day with no errors.
3. **New feature — live buy-cluster alerting.** `insider_pattern_analysis.py` already
   computes "clustered" (≥2 distinct insiders on the same ticker/direction within a
   window) for its retrospective stats report, but nothing today turns a
   freshly-detected cluster into a live WhatsApp alert, and it mixes buy+sell
   clusters (sells vastly outnumber buys in the dataset, so that number says little
   about buy-clusters specifically). The live alert uses its own 14-day window
   (Shaun 2026-11-08 — deliberately wider than the retrospective report's existing
   7-day window, so a cluster that builds slowly over up to two weeks is still
   caught), a new constant, not the existing `GOAT_INSIDER_CLUSTER_WINDOW_DAYS`.
4. **New feature — insider "flip" alerting.** A distinct signal Shaun flagged
   2026-11-08: the same insider selling, then buying back into the same ticker
   within 90 days, is itself significant regardless of any cluster — a genuine
   reversal of their own prior conviction. Nothing in this codebase detects this
   today; it is wholly new, not an extension of `_compute_clusters`.

## User Story

As Shaun (advisor-mode Second Brain user, Goat insider scanner)
I want every market-wide insider buy to generate coverage regardless of whether I
already hold or watch the ticker, with no silent truncation on busy days, plus a
distinct, immediate WhatsApp alert the moment a second independent insider buys the
same ticker within two weeks, or the same insider buys back a ticker they sold within
three months
So that I never miss a high-conviction insider-buy signal like the UPBD cluster again,
and I can tell "convergent buying by multiple insiders" and "an insider reversing their
own prior sale" apart from an isolated buy at a glance

## Problem Statement

See "Feature Description" above — two bugs plus two new signals from the same
investigation, folded into one build per the existing handoff
(`investments/goat/insider-buy-cluster-alert-handoff.md`) and the follow-up
conversation that added the flip signal and widened the cluster window.

## Solution Statement

1. Rewrite `mytrader.openinsider.fetch_discovery_purchases()` to query the paginated
   `/screener` endpoint with no ticker filter (live-confirmed below to return a real
   market-wide table, not the blank-form fallback), looping pages until a short page
   signals the end — same zero-arg call signature, so the existing call site and test
   mocks need no changes.
2. Remove the `get_holding_row`/`get_watchlist_row` exclusion checks from
   `run_discovery_scan` entirely. Add a narrower, explicit guard that only skips the
   `goat_pending_candidates` INSERT when the ticker is already held (so Shaun is never
   prompted to "add" something he already owns) — the WhatsApp alert and
   `goat_insider_filings_seen` recording still happen unconditionally. Watchlist
   tickers get no special treatment at all (re-promoting an already-watchlisted ticker
   via `promote-candidate` is a harmless idempotent `upsert_watchlist_row`).
3. Add a new buy-only, live cluster detector (`_check_buy_cluster` in
   `insider_scan.py`) that fires once per newly-formed cluster (≥2 distinct insiders
   buying the same ticker within a new, dedicated `GOAT_INSIDER_CLUSTER_ALERT_WINDOW_DAYS`
   constant — 14 days, Shaun 2026-11-08, deliberately separate from and wider than
   the existing 7-day `GOAT_INSIDER_CLUSTER_WINDOW_DAYS` the retrospective report
   uses — **no dollar-value floor**, confirmed with Shaun) via a new, separate
   WhatsApp alert, in addition to (never instead of) the existing per-trade discovery
   alert. Dedup via a new `cluster_alert_fired` column on `goat_insider_filings_seen`.
   **Must be checked from both `run_holdings_watch` and `run_discovery_scan`** — see
   "Patterns to Follow" below for why a single call site would silently miss
   held-ticker clusters.
4. Add a new insider-flip detector (`_check_insider_flip`) that fires the moment the
   *same* insider buys back into a ticker they themselves sold within a new
   `GOAT_INSIDER_FLIP_WINDOW_DAYS` constant (90 days — Shaun 2026-11-08: "people who
   buy not long after they've sold" is significant) — a same-person reversal signal,
   distinct from the buy-cluster (which is about multiple different insiders). Also
   checked from both `run_holdings_watch` and `run_discovery_scan`, fired via its own
   separate WhatsApp alert (`maybe_notify_insider_flips`). Dedup is automatic — a
   flip is only ever evaluated once, at the moment the triggering buy filing is
   first inserted (`newly_seen=True`), same as the existing per-trade discovery
   alert's own dedup.
5. Add a buy-only × cluster-only cross-tab to the retrospective
   `insider-pattern-analysis.md` report so future threshold tuning (window days,
   minimum distinct insiders) is evidence-based once enough buy-cluster volume
   accumulates.

## Feature Metadata

**Feature Type**: Bug Fix (2) + Enhancement (2)
**Estimated Complexity**: Medium-High
**Primary Systems Affected**: `investments/my-trader/mytrader/openinsider.py`,
`investments/goat/goat/insider_scan.py`, `investments/goat/goat/db.py`,
`investments/goat/goat/config.py`, `investments/goat/goat/insider_pattern_analysis.py`,
`investments/goat/goat/main.py`
**Dependencies**: None new. OpenInsider has no official/paid API — `/screener` is the
same free public scrape already used by `fetch_screener_filings`.

---

## CONTEXT REFERENCES

### Relevant Codebase Files — READ THESE BEFORE IMPLEMENTING

- `investments/goat/insider-buy-cluster-alert-handoff.md` — the full handoff this plan
  implements; read first, it has the original investigation and Shaun's framing (note:
  the handoff itself predates the 14-day-window and flip-signal decisions, which were
  made in conversation after it was written — this plan's text is authoritative where
  the two differ).
- `investments/my-trader/mytrader/openinsider.py` (whole file, 219 lines) — the
  scraper. `_SCREENER_DEFAULT_PARAMS` (lines 33–52) is the full form field set that
  must always be sent (OpenInsider silently falls back to a blank form if any field
  is missing — this is the exact bug class Root Cause 2 is adjacent to). `fetch_screener_filings`
  (179–193) is the ticker-scoped precedent to mirror for pagination style and
  trade-type filtering (`xp`/`xs` params, lines 33, 44, 187–188). `fetch_discovery_purchases`
  (196–200) is the function being rewritten. `build_dedup_key` (210–218) is unchanged
  — dedup key composition does not need to know about pagination.
- `investments/goat/goat/insider_scan.py` (whole file, 741 lines) — the single most
  important file in this plan, touched by almost every task:
  - `run_discovery_scan` (187–242): exclusion checks at lines 204–207 are
    removed/narrowed (Task 4); the shared cluster + flip detector calls are added
    around line 219, right after the existing `newly_seen` check for a purchase row
    (Task 5).
  - `run_holdings_watch` (114–184): **this function also needs the same two detector
    calls added**, not just `run_discovery_scan` — see "Patterns to Follow" below for
    why. The purchase branch currently has NO special handling at all (trade_type_code
    == "P" falls straight through to building `detail` and appending to `new_alerts`,
    lines 165–178, with no gating the way the sale branch has at lines 150–163) — the
    new detector calls slot in right after the existing `newly_seen` check (line 141),
    before the `action = "bought" if ...` line (165).
  - `_is_institutional_10pct_filer` (71–84) and its filter ordering (198–203,
    institutional check BEFORE the held/watchlist checks) is the pattern to follow for
    where the new cluster/flip checks slot into `run_discovery_scan`'s loop.
  - `maybe_notify_price_flags` (499–524) is the exact pattern to mirror for the two
    new `maybe_notify_cluster_alerts`/`maybe_notify_insider_flips` functions — same
    `_scripts_dir` sys.path shim, same `send_toast_notification`/
    `send_whatsapp_notification` import, same "only call if non-empty" guard.
  - `_prior_sale_count` (99–111) is the pattern to mirror for a window-bounded DB
    query using ISO-string date comparison (not SQL date functions) — both new
    detectors do the same shape of query.
- `investments/goat/goat/insider_pattern_analysis.py` (whole file, 273 lines) —
  `_compute_clusters` (63–87) is the clustering algorithm being reused (buy-only
  filtered call for the live path, unchanged mixed-direction call for the existing
  "By Cluster" slice). `compute_pattern_analysis` (121–182) is where the new buy-only
  cross-tab slice is added (after the existing `cluster = _bucket_by(...)` line 143).
  `render_pattern_analysis_report` (206–266) is where the new section's rendering
  goes, mirroring the existing `_render_slice("By Cluster", ...)` call (229–234).
  **Not touched by the flip feature** — flip is a live-alert-only signal in this plan,
  no retrospective stat was requested.
- `investments/goat/goat/db.py` — `init_goat_tables` (16–112) for the
  `goat_insider_filings_seen` schema (lines 49–60) and the idempotent
  try/except-OperationalError ALTER TABLE migration pattern (113–187, e.g. lines
  118–122 for the most recent `pct_owned_change` column addition — mirror this
  exactly for the new `cluster_alert_fired` column). `insert_goat_insider_filing_seen`
  (351–369) and `get_recent_insider_filings_seen` (372–382) are the existing
  query/insert pair to mirror for the three new DB functions. `count_insider_sales_since`
  (around line 402, referenced from `_prior_sale_count`) is the exact ISO-string
  date-range query pattern to copy for both `get_insider_buy_filings_in_window` (no
  `kind` filter — see Task 1's GOTCHA) and the new `get_most_recent_insider_sale`.
- `investments/goat/goat/config.py` lines 648–756 — the full insider-scanner config
  block. `GOAT_INSIDER_CLUSTER_WINDOW_DAYS` (line 752, value 7) stays **completely
  untouched** — it remains the retrospective report's own window, used only by
  `insider_pattern_analysis._compute_clusters`. Three brand-new constants are added
  for the live-alert feature (Task 2): `GOAT_INSIDER_CLUSTER_ALERT_WINDOW_DAYS` (14),
  `GOAT_INSIDER_CLUSTER_MIN_DISTINCT_BUYERS` (2), `GOAT_INSIDER_FLIP_WINDOW_DAYS` (90).
  Note the file's established comment convention: every threshold states its
  source/date and whether it's "v1/tunable" — follow this exactly for all three.
- `investments/goat/goat/main.py` lines 251–304 (`cmd_scan_insiders`) — where the
  two new notify functions get wired in, right after the existing
  `maybe_notify_price_flags(newly_flagged)` call (line 295). The cluster/flip event
  lists from `watch_result` and `discovery_result` must be **merged** before
  notifying (Task 7) — both functions can independently produce events now.
- `investments/goat/goat/tests/test_insider_scan.py` (741 lines, read in full before
  changing) — existing test patterns to mirror: `_purchase_row`/`_sale_row` builder
  helpers (lines 18–41), `monkeypatch.setattr("goat.insider_scan.openinsider.fetch_discovery_purchases", lambda: [...])`
  (used throughout, e.g. line 209) is the exact mock target — it must keep working
  unchanged after the rewrite since the function signature/name doesn't change.
  `test_run_discovery_scan_skips_ticker_already_a_holding` (229–237) and
  `test_run_discovery_scan_skips_ticker_already_in_watchlist` (240–250) assert the
  OLD (now-wrong) behavior and must be replaced, not just left passing.
- `investments/goat/goat/tests/conftest.py` — `db_conn` fixture (19–26, real SQLite,
  `mytrader.db.init_mytrader_tables` + `goat.db.init_goat_tables`), the
  `_isolate_goat_report_path` autouse fixture (29–79, redirects every `*_MD_PATH`/
  `*_PATH` constant to `tmp_path` — no new path constants are added by this feature,
  so no new entries needed here), and `_no_real_price_history_fetch` (82–94, blocks
  real yfinance calls — this feature adds no new price fetches, so this fixture needs
  no changes).
- `investments/my-trader/mytrader/tests/test_openinsider.py` — `_FakeResponse`
  (26–29) and `monkeypatch.setattr("requests.get", lambda *a, **k: _FakeResponse(...))`
  (e.g. line 33) is the mock pattern for the new pagination tests. The existing
  `test_fetch_discovery_purchases_parses_table_and_filters_purchase_code` (32–40)
  MUST keep passing unmodified after the rewrite (it mocks `requests.get` with one
  fixed 2-row response and expects exactly 1 purchase row back — the new pagination
  loop must correctly stop after one page here since `len(rows) < cnt`).

### New Files to Create

None — every change is to an existing file.

### Relevant Documentation

None external — this is a pure internal scrape-endpoint change against a page with
no official docs. The live-verification step below (which this plan's author already
ran once) is the only "documentation" that matters here.

### Patterns to Follow

**Live-verification-before-build (mandatory, not optional):** This codebase's own
convention (see `openinsider.py`'s "live-confirmed" comments at lines 20–29) is to
confirm a scrape quirk against the real site before writing code that depends on it,
not to assume from the existing ticker-scoped code path. **Already confirmed for this
plan** via a real `curl` against `openinsider.com/screener` with `s` omitted,
`fd=1`, `vl=25`, `xp=1` and the full `_SCREENER_DEFAULT_PARAMS` field set otherwise
unchanged: the response is a real multi-company results table (CVS, KMI, LKQ, YPF,
GFS, MTDR, and 15 more distinct tickers), not the blank-form fallback. **Re-run this
same live check immediately before writing `fetch_discovery_purchases`'s new body**
(the site's behavior could have drifted since) — do not skip it just because this
plan already ran it once.

**Why the cluster/flip detectors must be called from BOTH `run_holdings_watch` and
`run_discovery_scan` — read this before touching either function:** `cmd_scan_insiders`
calls `run_holdings_watch(conn)` *before* `run_discovery_scan(conn)`. For a currently
**held** ticker, `run_holdings_watch`'s own `fetch_screener_filings` call will already
catch a fresh buy and insert it into `goat_insider_filings_seen` via
`insert_goat_insider_filing_seen` (kind=`"holdings_watch"`) — using the SAME
`dedup_key` formula (`build_dedup_key`) that `run_discovery_scan` would compute for
that identical real-world trade. Because `dedup_key` is a `UNIQUE` column with
`INSERT OR IGNORE`, when `run_discovery_scan` later encounters that same trade in the
market-wide feed, its own `insert_goat_insider_filing_seen` call returns `newly_seen=False`
and the row is skipped (`continue`) **before** any cluster/flip check would run. If
the two detectors were wired up only inside `run_discovery_scan`'s loop, every
held-ticker buy — and therefore every cluster or flip involving a held ticker — would
be silently invisible to this feature, which directly contradicts Shaun's explicit
"I don't want it to matter if I hold the stock" framing. The fix: call
`_check_buy_cluster`/`_check_insider_flip` from inside `run_holdings_watch`'s own
purchase branch too (right after ITS `newly_seen` check succeeds), and make
`get_insider_buy_filings_in_window`/`get_most_recent_insider_sale` query by
`trade_type` only, with **no `kind` filter** — a buy or sell is the same signal
regardless of which of the two scan functions happened to record it first.

**Fail-safe-empty, not a crash:** every scan in this codebase returns `None`/`[]` and
prints a one-line `[goat-insider-scan] ...` message on a fetch failure rather than
raising (see `run_discovery_scan`'s existing `if rows is None: print(...); rows = []`
at lines 189–191, and `cmd_scan_industries_full`'s analogous style). The new
pagination loop must follow this: a failure on page 1 returns `None` (total failure,
matches `_fetch`'s own `None`-on-failure contract); a failure on page 2+ (after page 1
already succeeded) returns what was already gathered rather than discarding it,
with a print warning — never raise.

**ISO-string date range queries, not SQL date functions:** `count_insider_sales_since`
and `_prior_sale_count` compare `trade_date` as plain ISO `YYYY-MM-DD` strings with
`>=`/`<` directly in SQL (these sort/compare correctly as text) rather than using
SQLite's `julianday()`/`date()` functions. Follow this exactly for the three new DB
functions.

**Idempotent ALTER TABLE migration:** every new column on an existing table is added
via a `try: conn.execute("ALTER TABLE ... ADD COLUMN ..."); except sqlite3.OperationalError: pass`
block appended after `init_goat_tables`'s main `executescript`, never by editing the
`CREATE TABLE IF NOT EXISTS` statement itself (existing DBs already have the table
without the new column). See lines 113–187 for five existing examples of this exact
shape.

**Config constant comment convention:** every tunable number in `config.py` gets a
comment stating who decided it, when, and why, and whether it's "v1/tunable" or
based on an external convention — see literally every constant in the file for
examples (e.g. lines 657–662, 673–678). All three new constants' comments must state
the 2026-11-08 Shaun decision they came from.

**`maybe_notify_*` as its own notification path, separate from `monitor.maybe_notify`:**
`maybe_notify_price_flags` (insider_scan.py 499–524) exists precisely because it fires
on a different trigger (a price move crossing a threshold on an already-staged
candidate) than `monitor.maybe_notify` (fires on new alerts/candidates being staged
this run). The cluster alert and the flip alert are two more independent triggers and
must each be their own function, not folded into either existing one or each other.

---

## IMPLEMENTATION PLAN

### Phase 1: Foundation — data layer

**Tasks:**
- Add the `cluster_alert_fired` column + migration to `goat_insider_filings_seen`.
- Add three new DB helper functions: `get_insider_buy_filings_in_window` (no `kind`
  filter), `mark_insider_filings_cluster_alert_fired`, `get_most_recent_insider_sale`.
- Add the three new config constants.

### Phase 2: Core Implementation — the two bug fixes + two new detectors

**Tasks:**
- Rewrite `fetch_discovery_purchases` for paginated, tickerless `/screener` queries.
- Rewrite `run_discovery_scan`'s exclusion logic (remove hold/watchlist skip, add
  held-only pending-candidate-insert guard).
- Add `_check_buy_cluster` and `_check_insider_flip`; wire both into
  `run_discovery_scan`'s purchase handling AND `run_holdings_watch`'s purchase
  branch (see "Patterns to Follow" above — this is not optional for either function).
- Add `maybe_notify_cluster_alerts` and `maybe_notify_insider_flips`.

### Phase 3: Integration — wiring + retrospective report

**Tasks:**
- Merge `watch_result`/`discovery_result`'s cluster+flip event lists in
  `cmd_scan_insiders` and wire both new notify functions in.
- Add the buy-only × cluster-only cross-tab to `insider_pattern_analysis.py`
  (`compute_pattern_analysis` + `render_pattern_analysis_report`).
- Append a status line to `investments/goat/HANDOFF.md`'s top status paragraph per
  this repo's established per-phase convention.

### Phase 4: Testing & Validation

**Tasks:**
- New pagination tests in `mytrader/tests/test_openinsider.py`.
- Replace the two now-wrong exclusion tests in `goat/tests/test_insider_scan.py`;
  add new held-ticker/watchlist-ticker tests, new cluster tests (including the
  held-ticker-via-holdings-watch path), new flip tests.
- New DB tests in `goat/tests/test_db.py`.
- New cross-tab test in `goat/tests/test_insider_pattern_analysis.py`.
- Full suite + ruff + mypy on every changed file.

---

## STEP-BY-STEP TASKS

### Task 1 — UPDATE `investments/goat/goat/db.py`

- **IMPLEMENT**: Add a sixth idempotent migration block (after the existing one
  ending around line 187, for `goat_insider_filings_seen.company_name`):
  ```python
  with conn:
      try:
          conn.execute(
              "ALTER TABLE goat_insider_filings_seen ADD COLUMN cluster_alert_fired INTEGER NOT NULL DEFAULT 0"
          )
      except sqlite3.OperationalError:
          pass
  ```
  Then add three new functions near `insert_goat_insider_filing_seen`/
  `get_recent_insider_filings_seen` (after line 382):
  ```python
  def get_insider_buy_filings_in_window(
      conn: sqlite3.Connection, ticker: str, window_start: str, window_end: str
  ) -> list[sqlite3.Row]:
      """Buy ('P') filings on this ticker with trade_date inside
      [window_start, window_end] (inclusive ISO date strings) -- the candidate set
      _check_buy_cluster evaluates for cluster membership. Deliberately NO `kind`
      filter: a buy is a buy whether it was recorded via run_holdings_watch
      (kind='holdings_watch', for a currently-held ticker) or run_discovery_scan
      (kind='discovery') -- see insider_scan.py's module-level "Patterns to Follow"
      note on why both code paths must be able to see each other's filings here.
      Mirrors count_insider_sales_since's ISO-string range-query style."""
      return conn.execute(
          """SELECT * FROM goat_insider_filings_seen
             WHERE ticker = ? AND trade_type = 'P'
               AND trade_date >= ? AND trade_date <= ?""",
          (ticker, window_start, window_end),
      ).fetchall()


  def mark_insider_filings_cluster_alert_fired(conn: sqlite3.Connection, dedup_keys: list[str]) -> None:
      if not dedup_keys:
          return
      with conn:
          conn.executemany(
              "UPDATE goat_insider_filings_seen SET cluster_alert_fired = 1 WHERE dedup_key = ?",
              [(k,) for k in dedup_keys],
          )


  def get_most_recent_insider_sale(
      conn: sqlite3.Connection, *, ticker: str, insider_name: str, since_date: str, before_date: str
  ) -> sqlite3.Row | None:
      """Most recent 'S' filing by this exact insider on this exact ticker with
      since_date <= trade_date < before_date -- the antecedent sale _check_insider_flip
      looks for when a new buy lands. No `kind` filter for the same reason as
      get_insider_buy_filings_in_window: a sell could have been recorded via either
      run_holdings_watch (ticker held at time of sale) or run_discovery_sell_tracking
      (ticker not held at time of sale) -- together those two paths cover every sell,
      so this query must see both."""
      return conn.execute(
          """SELECT * FROM goat_insider_filings_seen
             WHERE ticker = ? AND insider_name = ? AND trade_type = 'S'
               AND trade_date >= ? AND trade_date < ?
             ORDER BY trade_date DESC LIMIT 1""",
          (ticker, insider_name, since_date, before_date),
      ).fetchone()
  ```
- **PATTERN**: `count_insider_sales_since` (db.py, referenced from
  `insider_scan._prior_sale_count`) for the ISO-string range query;
  `mark_insider_filing_price_flag_notified` (lines 385–389) for the single-row
  UPDATE pattern, extended here to `executemany` for a batch of dedup_keys.
- **GOTCHA**: Do NOT filter `get_insider_buy_filings_in_window` or
  `get_most_recent_insider_sale` by `kind` — this is the single most important
  correctness detail in this entire plan. See the module-level "Patterns to Follow"
  note above for the full reasoning (held-ticker buys/sells can be recorded under
  either `kind='holdings_watch'` or `kind='discovery'`/`'discovery_sell'` depending
  on timing, and both detectors must see all of them regardless).
- **GOTCHA**: `trade_date` is stored as plain `YYYY-MM-DD` text — the `>=`/`<=`/`<`
  comparisons only work correctly because ISO dates sort lexicographically the same
  as chronologically. Do not switch to `julianday()`.
- **VALIDATE**: `uv run --directory investments/goat python -m pytest goat/tests/test_db.py -q`

### Task 2 — UPDATE `investments/goat/goat/config.py`

- **IMPLEMENT**: Add directly below `GOAT_INSIDER_CLUSTER_WINDOW_DAYS` (line 752–755,
  which stays completely unchanged — it remains the retrospective report's own
  window):
  ```python
  GOAT_INSIDER_CLUSTER_ALERT_WINDOW_DAYS = 14  # LIVE buy-cluster WhatsApp alert window
      # -- deliberately separate from and wider than GOAT_INSIDER_CLUSTER_WINDOW_DAYS
      # (7, used only by insider_pattern_analysis's retrospective stat). Shaun
      # 2026-11-08: a cluster can build slowly ("multiple directors buy, but over a
      # two-week period") rather than within a single week, and he explicitly wants
      # the live alert to still catch that. v1/tunable.
  GOAT_INSIDER_CLUSTER_MIN_DISTINCT_BUYERS = 2  # live buy-cluster WhatsApp alert fires
      # the moment a ticker's distinct-insider buy count within
      # GOAT_INSIDER_CLUSTER_ALERT_WINDOW_DAYS reaches this many -- Shaun's explicit
      # call 2026-11-08, matching insider_pattern_analysis._compute_clusters's
      # existing retrospective bar (also 2) rather than setting a stricter live-only
      # threshold. Deliberately NO minimum combined or per-insider dollar value --
      # Shaun 2026-11-08: two directors buying $5k each should alert the same as two
      # buying $500k each. Own constant (not a reuse of _compute_clusters's hardcoded
      # ">= 2") so the live path can be tuned independently later without touching the
      # retrospective report's bar.
  GOAT_INSIDER_FLIP_WINDOW_DAYS = 90  # same insider selling, then buying BACK into the
      # same ticker, within this many days -- Shaun 2026-11-08: "people who buy not
      # long after they've sold" is itself significant, a same-person reversal signal
      # distinct from the multi-insider buy-cluster above. 90 chosen to match two
      # existing precedents in this file for "still a meaningful signal" windows --
      # GOAT_INSIDER_SALE_LOOKBACK_DAYS (repeated-sale pattern detection) and
      # GOAT_INSIDER_PRICE_STALE_DAYS (price move no longer attributable to the
      # trade), both also 90. v1/tunable.
  ```
- **PATTERN**: Match the file's existing comment style exactly (see Task 1's PATTERN
  note on this file's convention) — every number states who/when/why and
  v1/tunable status.
- **GOTCHA**: Do not add a dollar-value config constant for the cluster feature —
  Shaun explicitly confirmed no minimum. Do not reuse
  `GOAT_INSIDER_CLUSTER_WINDOW_DAYS` for the live alert — it must be a new, separate
  constant per Shaun's explicit 14-day decision.
- **VALIDATE**: `uv run --directory investments/goat python -m ruff check goat/config.py`

### Task 3 — UPDATE `investments/my-trader/mytrader/openinsider.py`

- **IMPLEMENT**: Replace `fetch_discovery_purchases` (lines 196–200) with a
  paginated, tickerless `/screener` query:
  ```python
  def fetch_discovery_purchases(
      filing_date_days: int = 5, min_value: float = 25_000, max_pages: int = 10
  ) -> list[dict] | None:
      """Market-wide buy discovery via a tickerless /screener query -- live-confirmed
      2026-11-08 that omitting 's' entirely (while still sending the FULL
      _SCREENER_DEFAULT_PARAMS field set) returns a real multi-company results table,
      not the blank-form fallback fetch_screener_filings's own comments already
      warn about for a malformed ticker-scoped query. Paginated because a
      volume-heavy day's results can exceed one page's cnt=300 cap -- the prior data
      source (/latest-insider-purchases-25k, a fixed unpaginated snapshot) silently
      truncated against exactly this with no backfill (see
      investments/goat/insider-buy-cluster-alert-handoff.md Root Cause 2; confirmed
      live via goat_insider_filings_seen having zero rows for any of UPBD's 6
      Nov 2-3 2026 buys despite a clean daily run).

      filing_date_days defaults to 5 (not 1) deliberately -- a daily job that only
      ever asks for "today" has no backfill if a run is ever missed (VPS downtime,
      etc.), which is the same failure mode as Root Cause 2 itself. 5 matches
      GOAT_INSIDER_DISCOVERY_LOOKBACK_DAYS's existing safety-net value in goat/config.py
      (not imported here -- mytrader must not depend on goat, see this module's
      top-of-file docstring -- so this default is a literal, same convention as
      fetch_screener_filings's own filing_date_days=7 literal default above)."""
      params = dict(_SCREENER_DEFAULT_PARAMS)
      params["vl"] = str(int(min_value / 1000))
      params["xp"] = "1"
      params["fd"] = str(filing_date_days)
      all_rows: list[dict] = []
      for page in range(1, max_pages + 1):
          params["page"] = str(page)
          rows = _fetch(f"{config.OPENINSIDER_BASE_URL}/screener", params=params)
          if rows is None:
              if page == 1:
                  return None
              print(f"[openinsider] discovery pagination stopped early at page {page} (fetch failed) "
                    f"-- returning {len(all_rows)} row(s) gathered so far")
              break
          all_rows.extend(r for r in rows if r["trade_type_code"] == "P")
          if len(rows) < int(params["cnt"]):
              break
      return all_rows
  ```
- **PATTERN**: `fetch_screener_filings` (lines 179–193) for the params-copy +
  `xp`/`fd` override style; the module's own `_SCREENER_DEFAULT_PARAMS` comment
  block (lines 20–32) for why every field must stay present.
- **IMPORTS**: None new — `config`, `_fetch`, `_SCREENER_DEFAULT_PARAMS` all already
  imported/defined in this module.
- **GOTCHA**: Do not add `params["s"]` at all — its absence (not an empty string) is
  what triggers the market-wide result; `_SCREENER_DEFAULT_PARAMS` never included an
  `"s"` key, `fetch_screener_filings` adds it per-call, so simply not adding it here
  is correct and requires no special-casing.
- **GOTCHA**: `max_pages=10` is a safety cap against a runaway loop (e.g. if
  OpenInsider ever ignores `fd` and returns years of history) — not expected to be
  hit in practice at `fd=5`, but must exist so a scrape-behavior change can't hang
  the daily VPS job.
- **GOTCHA**: The existing test
  `test_fetch_discovery_purchases_parses_table_and_filters_purchase_code` (test_openinsider.py
  32–40) mocks `requests.get` to always return the same fixed 2-row HTML. With this
  rewrite, page 1 will return that same 2-row response (1 purchase after filtering),
  and since `2 < cnt(300)`, the loop stops after page 1 — this test must keep
  passing with zero changes. Verify this explicitly, do not just assume it.
- **VALIDATE**: `uv run --directory investments/my-trader python -m pytest mytrader/tests/test_openinsider.py -q`

### Task 4 — UPDATE `investments/goat/goat/insider_scan.py` — remove hold/watchlist exclusion

- **IMPLEMENT**: In `run_discovery_scan` (lines 187–242), replace:
  ```python
  if mt_db.get_holding_row(conn, ticker) is not None:
      continue
  if mt_db.get_watchlist_row(conn, ticker) is not None:
      continue
  if db.get_goat_pending_candidate(conn, ticker) is not None:
      continue
  ```
  with:
  ```python
  is_held = mt_db.get_holding_row(conn, ticker) is not None
  if db.get_goat_pending_candidate(conn, ticker) is not None:
      continue
  ```
  Then further down, where `db.insert_goat_pending_candidate(...)` is called
  (currently lines 227–231), guard it:
  ```python
  if not is_held:
      db.insert_goat_pending_candidate(
          conn, ticker=ticker, sector_label="Insider Buy",
          signal_detail=signal_detail, source="goat_insider_discovery",
          trade_date=row.get("trade_date"), company_name=row.get("company_name"),
      )
  ```
  `new_candidates.append({...})` immediately after stays unconditional (unchanged) —
  this still feeds `maybe_notify`'s WhatsApp alert regardless of held status. Only
  the `goat_pending_candidates` INSERT is held-gated.
- **PATTERN**: This mirrors the handoff's Open Question 4 resolution exactly — "fire
  the discovery/cluster alert regardless of hold status, but skip inserting into
  goat_pending_candidates when the ticker is already held" (Shaun confirmed
  2026-11-08).
- **GOTCHA**: Watchlist tickers get NO special handling at all now — they flow
  through identically to a brand-new ticker (alerted AND inserted into
  `goat_pending_candidates`). This is intentional: re-promoting an
  already-watchlisted ticker via `promote-candidate` is a harmless
  `upsert_watchlist_row` no-op/update, so there's no "odd UX" concern for watchlist
  the way there is for holdings.
- **GOTCHA**: `pending_candidates` in the return dict (built from
  `db.get_all_goat_pending_candidates(conn)` filtered to this source) will now
  correctly NOT include held tickers (since they're never inserted) — this is the
  desired behavior, not a bug to fix.
- **GOTCHA**: Note that for a held ticker, `newly_seen` here will very often already
  be `False` by the time `run_discovery_scan` reaches it, because
  `run_holdings_watch` (called first in `cmd_scan_insiders`) will usually have
  already inserted that exact filing under `kind='holdings_watch'`. That's expected
  and correct — see Task 5's note on why the cluster/flip checks must ALSO live in
  `run_holdings_watch`, not just here.
- **VALIDATE**: `uv run --directory investments/goat python -m pytest goat/tests/test_insider_scan.py -k discovery -q`
  (will fail until Task 8's test updates land — expected at this point in the task
  order)

### Task 5 — UPDATE `investments/goat/goat/insider_scan.py` — add the two shared detectors

- **IMPLEMENT**: Add two new functions near `_prior_sale_count` (after line 111) —
  these are called from BOTH `run_holdings_watch` and `run_discovery_scan` (Task 6):
  ```python
  def _check_buy_cluster(conn: sqlite3.Connection, ticker: str, trade_date_str: str) -> dict[str, Any] | None:
      """Returns a cluster-alert dict the first time this ticker's buy filings within
      GOAT_INSIDER_CLUSTER_ALERT_WINDOW_DAYS of trade_date_str reach
      GOAT_INSIDER_CLUSTER_MIN_DISTINCT_BUYERS distinct insiders; None if the bar
      isn't met, or if every filing in the window already belongs to an
      already-announced cluster (new members still get marked so they stay part of
      the announced group, they just don't re-trigger a notification). Buy-direction
      only, per Shaun 2026-11-08 -- distinct from and does not touch
      insider_pattern_analysis._compute_clusters's own mixed-direction, 7-day-window
      retrospective stat. Caller must have already inserted this ticker's own new
      filing via insert_goat_insider_filing_seen before calling this, so it's
      included in the window query. Called from BOTH run_holdings_watch and
      run_discovery_scan -- see this module's "Patterns to Follow" note for why a
      single call site would miss held-ticker clusters."""
      try:
          trade_date_obj = datetime.strptime(trade_date_str, "%Y-%m-%d").date()
      except (ValueError, TypeError):
          return None
      window_start = (trade_date_obj - timedelta(days=config.GOAT_INSIDER_CLUSTER_ALERT_WINDOW_DAYS)).isoformat()
      window_end = (trade_date_obj + timedelta(days=config.GOAT_INSIDER_CLUSTER_ALERT_WINDOW_DAYS)).isoformat()
      nearby = db.get_insider_buy_filings_in_window(conn, ticker, window_start, window_end)
      distinct_insiders = {r["insider_name"] for r in nearby}
      if len(distinct_insiders) < config.GOAT_INSIDER_CLUSTER_MIN_DISTINCT_BUYERS:
          return None
      dedup_keys = [r["dedup_key"] for r in nearby]
      already_fired = any(r["cluster_alert_fired"] for r in nearby)
      db.mark_insider_filings_cluster_alert_fired(conn, dedup_keys)
      if already_fired:
          return None
      return {
          "ticker": ticker,
          "insiders": sorted(distinct_insiders),
          "titles": sorted({r["title"] for r in nearby if r["title"]}),
          "total_value": sum(r["value"] for r in nearby),
      }


  def _check_insider_flip(
      conn: sqlite3.Connection, ticker: str, insider_name: str, trade_date_str: str
  ) -> dict[str, Any] | None:
      """Returns a flip-alert dict when THIS SAME insider sold this ticker within
      GOAT_INSIDER_FLIP_WINDOW_DAYS before this new buy -- Shaun 2026-11-08: a
      same-person reversal (sell, then buy back) is itself a signal, distinct from
      _check_buy_cluster (which is about multiple DIFFERENT insiders). Fires exactly
      once per qualifying buy filing (dedup is automatic -- this is only ever called
      the moment a buy filing is first inserted, newly_seen=True, same as the
      existing per-trade discovery alert). Called from BOTH run_holdings_watch and
      run_discovery_scan, same reasoning as _check_buy_cluster."""
      try:
          buy_date = datetime.strptime(trade_date_str, "%Y-%m-%d").date()
      except (ValueError, TypeError):
          return None
      since_date = (buy_date - timedelta(days=config.GOAT_INSIDER_FLIP_WINDOW_DAYS)).isoformat()
      prior_sale = db.get_most_recent_insider_sale(
          conn, ticker=ticker, insider_name=insider_name,
          since_date=since_date, before_date=trade_date_str,
      )
      if prior_sale is None:
          return None
      sale_date = datetime.strptime(prior_sale["trade_date"], "%Y-%m-%d").date()
      return {
          "ticker": ticker, "insider_name": insider_name,
          "sale_date": prior_sale["trade_date"], "sale_value": prior_sale["value"],
          "buy_date": trade_date_str, "days_between": (buy_date - sale_date).days,
      }
  ```
- **PATTERN**: `_prior_sale_count` (99–111) for the window-bounded query shape.
- **IMPORTS**: `timedelta` already imported at the top of the file (line 14,
  `from datetime import date, datetime, timedelta`) — no new import needed.
- **GOTCHA**: `_check_insider_flip`'s `before_date=trade_date_str` means a sale ON
  the exact same date as the buy does not count as "prior" (uses `<`, not `<=`, in
  `get_most_recent_insider_sale`) — a same-day sell+buy is a different (likely
  administrative/10b5-1) pattern, not the reversal signal Shaun described.
- **VALIDATE**: No standalone validation yet — these are unused until Task 6 wires
  them in; syntax-check only: `uv run --directory investments/goat python -m ruff check goat/insider_scan.py`

### Task 6 — UPDATE `investments/goat/goat/insider_scan.py` — wire detectors into BOTH scan functions

- **IMPLEMENT**: In `run_discovery_scan`'s loop, immediately after the existing
  `signal_detail = (...)` block and before `db.insert_goat_pending_candidate`
  (i.e. right after the `if not newly_seen: continue` guard confirms this is a
  genuinely new filing), add:
  ```python
  cluster_event = _check_buy_cluster(conn, ticker, row.get("trade_date", ""))
  if cluster_event:
      new_cluster_alerts.append(cluster_event)
  flip_event = _check_insider_flip(conn, ticker, row.get("insider_name", ""), row.get("trade_date", ""))
  if flip_event:
      new_flip_alerts.append(flip_event)
  ```
  Initialize `new_cluster_alerts: list[dict[str, Any]] = []` and
  `new_flip_alerts: list[dict[str, Any]] = []` before the `for row in rows:` loop
  starts, and add `"new_cluster_alerts": new_cluster_alerts` and
  `"new_flip_alerts": new_flip_alerts` to the function's final return dict.

  In `run_holdings_watch` (114–184), the purchase branch currently has no gating at
  all — `trade_type_code == "P"` falls straight through from the `newly_seen` check
  (line 141) to building `detail`/appending to `new_alerts` (165–178). Add the same
  two checks right after the `newly_seen` guard, inside an
  `if row["trade_type_code"] == "P":` block placed alongside (not replacing) the
  existing `if row["trade_type_code"] == "S":` gating block:
  ```python
  if row["trade_type_code"] == "P":
      cluster_event = _check_buy_cluster(conn, row["ticker"], row.get("trade_date", ""))
      if cluster_event:
          new_cluster_alerts.append(cluster_event)
      flip_event = _check_insider_flip(
          conn, row["ticker"], row.get("insider_name", ""), row.get("trade_date", "")
      )
      if flip_event:
          new_flip_alerts.append(flip_event)
  ```
  Initialize both lists at the top of `run_holdings_watch` (alongside the existing
  `new_alerts: list[dict[str, Any]] = []`) and add both keys to its return dict
  (alongside the existing `"checked_holdings"`/`"new_alerts"`/`"recent_filings"`).
- **PATTERN**: `_is_institutional_10pct_filer`'s placement in `run_discovery_scan`'s
  filter chain (198–203) for how a per-row check slots into a loop that already has
  several sequential checks.
- **GOTCHA** (the most important one in this plan — re-read the module-level
  "Patterns to Follow" note before doing this task): skipping the
  `run_holdings_watch` half of this task means every held-ticker cluster/flip is
  silently invisible, because `run_holdings_watch` runs first and will have already
  claimed the `dedup_key` for most held-ticker buys, causing `run_discovery_scan`'s
  own `newly_seen` check to short-circuit before ever reaching its detector calls for
  that trade.
- **GOTCHA**: Order matters within each function — both detector calls must run
  AFTER that function's own `insert_goat_insider_filing_seen` call for the current
  row (already true in both functions, since both already gate on `newly_seen`
  first) so the window query sees the current row's own filing too.
- **GOTCHA**: A ticker that is both held AND the subject of a forming cluster/flip
  still gets the event (neither detector knows or cares about held status) —
  correct per Shaun's confirmation that hold status should never gate alerting.
- **VALIDATE**: `uv run --directory investments/goat python -m pytest goat/tests/test_insider_scan.py -k "cluster or flip" -q`
  (new tests land in Task 8)

### Task 7 — UPDATE `investments/goat/goat/insider_scan.py` — notifications

- **IMPLEMENT**: Add two new functions after `maybe_notify_price_flags` (after line
  524):
  ```python
  def maybe_notify_cluster_alerts(cluster_events: list[dict[str, Any]]) -> None:
      """Fires once per newly-formed insider-buy cluster (see _check_buy_cluster) --
      a WhatsApp alert distinct from, and always in addition to, the normal
      per-trade discovery alert (Shaun 2026-11-08: multiple independent insiders
      buying the same ticker in a short window is a stronger signal than any single
      buy alone, so it earns its own, separate ping rather than being folded into or
      replacing the existing one)."""
      if not cluster_events:
          return
      import sys
      from pathlib import Path

      _scripts_dir = Path(__file__).resolve().parent.parent.parent.parent / ".claude" / "scripts"
      sys.path.insert(0, str(_scripts_dir))
      from notifications import send_toast_notification, send_whatsapp_notification

      summary = f"{len(cluster_events)} new insider buy cluster(s) forming"
      send_toast_notification(
          "Goat Insider Scan", summary + " -- check investments/goat/insider-scan-report.md"
      )
      lines = [f"Goat Insider Cluster Alert: {summary}."]
      for e in cluster_events:
          titles = ", ".join(e["titles"]) if e["titles"] else "role unknown"
          lines.append(
              f"- {e['ticker']}: {len(e['insiders'])} distinct insiders bought within "
              f"{config.GOAT_INSIDER_CLUSTER_ALERT_WINDOW_DAYS} days ({titles}), "
              f"${e['total_value']:,.0f} combined"
          )
      send_whatsapp_notification("\n".join(lines))


  def maybe_notify_insider_flips(flip_events: list[dict[str, Any]]) -> None:
      """Fires once per detected insider flip (see _check_insider_flip) -- a WhatsApp
      alert distinct from, and always in addition to, the normal per-trade discovery
      alert. Shaun 2026-11-08: a same-person sell-then-buy-back reversal is its own
      signal, unrelated to whether a multi-insider cluster is also forming."""
      if not flip_events:
          return
      import sys
      from pathlib import Path

      _scripts_dir = Path(__file__).resolve().parent.parent.parent.parent / ".claude" / "scripts"
      sys.path.insert(0, str(_scripts_dir))
      from notifications import send_toast_notification, send_whatsapp_notification

      summary = f"{len(flip_events)} insider flip(s) detected"
      send_toast_notification(
          "Goat Insider Scan", summary + " -- check investments/goat/insider-scan-report.md"
      )
      lines = [f"Goat Insider Flip Alert: {summary}."]
      for e in flip_events:
          lines.append(
              f"- {e['ticker']}: {e['insider_name']} sold ${e['sale_value']:,.0f} on "
              f"{e['sale_date']}, bought back on {e['buy_date']} "
              f"({e['days_between']}d later)"
          )
      send_whatsapp_notification("\n".join(lines))
  ```
- **PATTERN**: `maybe_notify_price_flags` (499–524), copied almost verbatim for
  both — same sys.path shim, same two-notification-call shape, same "guard on
  empty, return early" style.
- **VALIDATE**: `uv run --directory investments/goat python -m pytest goat/tests/test_insider_scan.py -k notify -q`

### Task 8 — UPDATE `investments/goat/goat/main.py`

- **IMPLEMENT**: In `cmd_scan_insiders` (lines 251–304), add the two new imports
  alongside the existing `insider_scan` imports (around line 253):
  ```python
  from .insider_scan import (
      compute_discovery_price_performance,
      compute_holdings_watch_price_performance,
      mature_price_outcome_snapshots,
      maybe_notify_cluster_alerts,   # new
      maybe_notify_insider_flips,    # new
      maybe_notify_price_flags,
      run_discovery_scan,
      run_discovery_sell_tracking,
      run_holdings_watch,
      write_insider_scan_report,
  )
  ```
  Merge both result dicts' new event lists and call both new notify functions, right
  after the existing `maybe_notify_price_flags(newly_flagged)` line (295):
  ```python
  maybe_notify_price_flags(newly_flagged)
  all_cluster_alerts = watch_result.get("new_cluster_alerts", []) + discovery_result.get("new_cluster_alerts", [])
  all_flip_alerts = watch_result.get("new_flip_alerts", []) + discovery_result.get("new_flip_alerts", [])
  maybe_notify_cluster_alerts(all_cluster_alerts)
  maybe_notify_insider_flips(all_flip_alerts)
  ```
  Also extend the final `print(...)` summary (lines 296–304) to include both new
  counts, e.g. append
  `f", {len(all_cluster_alerts)} new buy cluster(s), {len(all_flip_alerts)} insider flip(s)."`
  to the existing f-string.
- **PATTERN**: Existing `cmd_scan_insiders` structure — every result dict's fields
  are both notified and summarized in the print line; the new fields follow the same
  shape, merged from both scan functions per Task 6's dual-call-site design.
- **VALIDATE**: `uv run --directory investments/goat python -m goat.main scan-insiders`
  (Level 4 manual run against the real VPS DB — see Testing Strategy)

### Task 9 — UPDATE `investments/goat/goat/insider_pattern_analysis.py` — buy-only cross-tab

- **IMPLEMENT**: In `compute_pattern_analysis` (121–182), right after the existing
  `cluster = _bucket_by(rows, lambda r: "Clustered" if clustered.get(r["dedup_key"]) else "Isolated")`
  line (143), add:
  ```python
  buy_rows = [r for r in rows if r["trade_type"] == "P"]
  buy_cluster = _bucket_by(
      buy_rows, lambda r: "Clustered" if clustered.get(r["dedup_key"]) else "Isolated"
  )
  ```
  Add `"buy_cluster": buy_cluster,` to the function's final return dict (alongside
  the existing `"cluster": cluster,` line).
  In `render_pattern_analysis_report` (206–266), add a new section right after the
  existing `By Cluster` block (229–234):
  ```python
  lines += ["", *_render_slice(
      "By Cluster — Buys Only",
      "Same clustering test as 'By Cluster' above, restricted to buy-direction trades "
      "only -- isolates the buy-cluster signal from the much larger sell-cluster "
      "population (sells vastly outnumber buys in this dataset), so a future "
      "cluster-alert threshold can be tuned against buy-only evidence.",
      analysis["buy_cluster"],
  )]
  ```
- **PATTERN**: Exactly mirrors the existing `cluster`/"By Cluster" slice
  (139–143, 229–234) — same `_bucket_by`/`_render_slice` calls, reusing the same
  `clustered` dict already computed once (no second `_compute_clusters` call, no
  extra yfinance/DB cost).
- **GOTCHA**: `clustered` (from `_compute_clusters(list(filings_by_key.values()))`,
  line 137) is computed over ALL filings (both directions) using the existing
  7-day `GOAT_INSIDER_CLUSTER_WINDOW_DAYS` — this is correct and must NOT change,
  and must NOT be confused with the new 14-day `GOAT_INSIDER_CLUSTER_ALERT_WINDOW_DAYS`
  used only by the live detector in `insider_scan.py`. This task touches the
  retrospective report only; it does not use or reference
  `GOAT_INSIDER_CLUSTER_ALERT_WINDOW_DAYS` anywhere.
- **GOTCHA**: This task does NOT add any retrospective stat for the flip signal —
  that wasn't requested and is out of scope (flip is a live-alert-only feature per
  the Solution Statement).
- **VALIDATE**: `uv run --directory investments/goat python -m pytest goat/tests/test_insider_pattern_analysis.py -q`

### Task 10 — UPDATE `investments/goat/HANDOFF.md`

- **IMPLEMENT**: Append one sentence to the top status paragraph (the single
  run-on paragraph starting "## Status:") following its exact established style —
  state what was built/fixed (universal discovery + pagination fix, live buy-cluster
  alert at a 14-day window, live insider-flip alert at a 90-day window), test count
  (fill in actual final count from Task 11), and live-validation status.
- **PATTERN**: Every existing sentence in that paragraph — see the full file for the
  exact register (dense, past-tense, dated, cites the specific functions/configs
  touched).
- **VALIDATE**: Manual read-through only — this is documentation, no executable
  validation.

### Task 11 — Tests

- **CREATE/UPDATE** `investments/my-trader/mytrader/tests/test_openinsider.py`:
  - Add `test_fetch_discovery_purchases_queries_screener_without_ticker_param` —
    monkeypatch `requests.get` to assert the captured `params` dict has no `"s"`
    key and `xp == "1"`.
  - Add `test_fetch_discovery_purchases_paginates_until_short_page` — monkeypatch
    `_fetch` directly to return `["row"] * 300` then `["row"] * 50` (two
    side-effect values; fabricate minimal dict rows with `trade_type_code: "P"`) and
    assert `fetch_discovery_purchases(max_pages=5)` made exactly 2 calls and
    returned all 350 rows.
  - Add `test_fetch_discovery_purchases_stops_at_max_pages` — monkeypatch to always
    return a full page; assert the loop stops at exactly `max_pages` calls, not
    infinitely.
  - Add `test_fetch_discovery_purchases_returns_none_on_first_page_failure` —
    monkeypatch `_fetch` to return `None`; assert the function returns `None`.
  - Add `test_fetch_discovery_purchases_returns_partial_on_later_page_failure` —
    monkeypatch `_fetch` with a side-effect `[full_page, None]`; assert the function
    returns the first page's rows, not `None`.
  - Confirm `test_fetch_discovery_purchases_parses_table_and_filters_purchase_code`
    (existing, 32–40) still passes unmodified — run it explicitly, don't assume.
- **UPDATE** `investments/goat/goat/tests/test_insider_scan.py`:
  - Replace `test_run_discovery_scan_skips_ticker_already_a_holding` (229–237) with
    `test_run_discovery_scan_alerts_on_held_ticker_but_skips_pending_insert` —
    seed a holding on ACME, mock a purchase row on ACME, assert
    `len(result["new_candidates"]) == 1` (alert still fires) AND
    `goat_db.get_goat_pending_candidate(db_conn, "ACME") is None` (not inserted).
  - Replace `test_run_discovery_scan_skips_ticker_already_in_watchlist` (240–250)
    with `test_run_discovery_scan_alerts_and_inserts_for_watchlisted_ticker` —
    seed a watchlist row on ACME, mock a purchase, assert both
    `len(result["new_candidates"]) == 1` AND
    `goat_db.get_goat_pending_candidate(db_conn, "ACME") is not None`.
  - Add `test_check_buy_cluster_fires_on_second_distinct_insider` — two purchase
    rows, same ticker, different `insider_name`, trade dates a few days apart
    (inside the new 14-day window); run `run_discovery_scan` with both rows in one
    `fetch_discovery_purchases` mock return; assert
    `len(result["new_cluster_alerts"]) == 1` and the event's `insiders` list has
    both names.
  - Add `test_check_buy_cluster_catches_a_slow_two_week_formation` — two purchase
    rows 13 days apart (inside the 14-day window but well outside the OLD 7-day
    `GOAT_INSIDER_CLUSTER_WINDOW_DAYS`), different insiders, same ticker; assert the
    cluster still fires — this is the specific scenario Shaun described
    ("multiple directors buy, but over a two-week period") and must be tested
    explicitly, not just inferred from the window-length test above.
  - Add `test_check_buy_cluster_does_not_refire_on_third_insider` — three purchase
    rows (A, B, C) on the same ticker within the window, delivered across two
    separate `run_discovery_scan` calls (A+B in the first call, C in a second call
    on the same `db_conn`); assert the first call's result has 1 cluster alert and
    the second call's result has 0 (the already-fired cluster just gains a member).
  - Add `test_check_buy_cluster_ignores_filings_outside_window` — two purchase rows,
    same ticker, different insiders, trade dates `GOAT_INSIDER_CLUSTER_ALERT_WINDOW_DAYS + 1`
    days apart; assert no cluster alert fires for either.
  - Add `test_check_buy_cluster_does_not_count_sells` — a sell filing plus one
    purchase row on the same ticker; assert no cluster alert fires from the single
    purchase (confirms the `trade_type = 'P'` filter in
    `get_insider_buy_filings_in_window` is doing its job — note per Task 1, this
    query has NO `kind` filter, only a `trade_type` filter, so this test must seed
    the sell via whichever path is simplest, e.g. directly via
    `goat_db.insert_goat_insider_filing_seen(..., trade_type="S", ...)`).
  - **Add `test_check_buy_cluster_fires_for_held_ticker_via_holdings_watch`** — seed
    a holding on ACME, monkeypatch `fetch_screener_filings` to return two purchase
    rows for ACME with different insider names a week apart, run
    `insider_scan.run_holdings_watch(db_conn)` directly (not `run_discovery_scan`),
    assert `len(result["new_cluster_alerts"]) == 1`. This is the critical
    regression test for the dual-call-site design — without Task 6's
    `run_holdings_watch` wiring, this test fails even though the equivalent
    `run_discovery_scan` test passes.
  - Add `test_check_insider_flip_fires_on_buyback_within_window` — seed a prior sell
    filing (`trade_type="S"`, same insider, same ticker, 30 days before) via
    `goat_db.insert_goat_insider_filing_seen`, then mock a purchase row from the
    SAME insider on the SAME ticker; run `run_discovery_scan`; assert
    `len(result["new_flip_alerts"]) == 1` and `days_between == 30`.
  - Add `test_check_insider_flip_ignores_sale_outside_window` — same as above but
    the prior sell is `GOAT_INSIDER_FLIP_WINDOW_DAYS + 1` days before; assert no
    flip alert.
  - Add `test_check_insider_flip_requires_same_insider` — a sell by insider A, then
    a buy by insider B on the same ticker within the window; assert no flip alert
    (this is a buy-cluster candidate, not a flip, if a second A-direction insider
    exists — but on its own, a single different-insider buy is neither).
  - Add `test_check_insider_flip_ignores_a_buy_with_no_prior_sale` — a purchase row
    with no prior sell filing anywhere in history for that insider/ticker; assert no
    flip alert (the ordinary, by-far-most-common case — must not false-positive).
- **CREATE/UPDATE** `investments/goat/goat/tests/test_db.py`:
  - Add tests for `get_insider_buy_filings_in_window` (returns rows inside the
    window, excludes rows outside it, excludes `trade_type != 'P'`, and
    **explicitly asserts it returns rows regardless of `kind`** — seed one
    `kind='discovery'` and one `kind='holdings_watch'` row, both must come back).
  - Add tests for `mark_insider_filings_cluster_alert_fired` (sets the flag on
    exactly the given dedup_keys, no-ops on an empty list).
  - Add tests for `get_most_recent_insider_sale` (returns the most recent qualifying
    sale within the window, excludes a different insider's sale, excludes a sale on
    a different ticker, excludes a sale outside the date range, returns `None` when
    none exists).
  - Add a migration idempotency test: call `init_goat_tables` twice on the same
    connection, assert no exception and the `cluster_alert_fired` column exists
    (mirror whatever existing test covers the `pct_owned_change`/`company_name`
    migrations, if one exists — check first).
- **UPDATE** `investments/goat/goat/tests/test_insider_pattern_analysis.py`:
  - Add a test seeding mixed buy/sell price-outcome rows where a buy pair is
    clustered and a sell pair is clustered; assert `analysis["buy_cluster"]`
    contains only the buy-side bucket counts (the sell cluster must not leak into
    `buy_cluster`'s `n`).

### Task 12 — Full validation pass

- **VALIDATE**: Run every command in the VALIDATION COMMANDS section below in order.

---

## TESTING STRATEGY

### Unit Tests

Every new function gets direct unit coverage per the task list above, using this
codebase's existing `monkeypatch` + real-SQLite-tmp-file (`db_conn` fixture) style —
no new mocking framework, no new fixture infrastructure needed.

### Integration Tests

`run_discovery_scan` and `run_holdings_watch` end-to-end tests (Task 11,
test_insider_scan.py additions) exercise the full path — fetch mock → filter → DB
insert → cluster/flip check → return dict — the same integration-via-unit-test style
this file already uses throughout (there is no separate integration test tier in this
package). The held-ticker-via-`run_holdings_watch` test is the most important
integration test in this plan — it's the one that would silently pass even with a
broken implementation if only `run_discovery_scan` were tested.

### Edge Cases

- A ticker with a cluster AND an institutional-filer buy in the same window (the
  institutional buy is filtered out before `goat_insider_filings_seen` is even
  written — confirm the institutional filer never counts toward
  `distinct_insiders`, since it's dropped before `_check_buy_cluster` ever sees it).
- Unparsable `trade_date` on the triggering row (`_check_buy_cluster`/
  `_check_insider_flip` return `None` immediately, same fail-open posture as
  `_prior_sale_count`).
- Pagination hitting `max_pages` on a genuinely high-volume day — confirm the
  function returns partial data with no exception, not a silent truncation someone
  mistakes for "that's everything."
- A cluster forming right at the edge of the 14-day window (13 vs. 15 days apart) —
  the "slow two-week formation" test above (Task 11) exists specifically to prove
  the window is actually 14 days wide, not accidentally still 7.
- An insider who sells, buys back (flip fires), then sells again and buys back a
  second time within the tracking history — confirm the second flip is evaluated
  independently (uses the MOST RECENT qualifying sale via `ORDER BY trade_date DESC
  LIMIT 1`, not the first-ever one) and still fires, since each buy filing is
  processed exactly once via its own `newly_seen` check.
- A buy that is simultaneously a flip (same insider sold recently) AND part of a
  forming cluster (a different insider also bought recently) — confirm both
  `maybe_notify_cluster_alerts` and `maybe_notify_insider_flips` can fire
  independently for the same underlying filing; they are not mutually exclusive.

---

## VALIDATION COMMANDS

### Level 1: Syntax & Style

```powershell
uv run --directory investments/my-trader python -m ruff check mytrader/openinsider.py
uv run --directory investments/goat python -m ruff check goat/insider_scan.py goat/insider_pattern_analysis.py goat/db.py goat/config.py goat/main.py
uv run --directory investments/my-trader python -m mypy mytrader/openinsider.py
uv run --directory investments/goat python -m mypy goat/insider_scan.py goat/insider_pattern_analysis.py goat/db.py
```

### Level 2: Unit Tests

```powershell
uv run --directory investments/my-trader python -m pytest mytrader/tests/test_openinsider.py -q
uv run --directory investments/goat python -m pytest goat/tests/test_insider_scan.py goat/tests/test_insider_pattern_analysis.py goat/tests/test_db.py -q
```

### Level 3: Integration Tests

```powershell
# Full suite for both affected packages -- zero regressions required
uv run --directory investments/my-trader python -m pytest -q
uv run --directory investments/goat python -m pytest -q
```

### Level 4: Manual Validation

```powershell
# Re-run the live /screener market-wide check immediately before trusting Task 3's
# implementation -- confirm the site behavior hasn't drifted since this plan's own
# verification. Expect a real multi-ticker table, not a blank form.
curl -s -A "Mozilla/5.0 (compatible; SecondBrainGoat/1.0)" "http://openinsider.com/screener?o=&pl=&ph=&ll=&lh=&fd=1&fdr=&td=0&tdr=&fdlyl=&fdlyh=&daysago=&xa=&xd=&xg=&xf=&xm=&xx=&xc=&xw=&excludeDerivRelated=&tmult=&vl=25&vh=&ocl=&och=&sic1=-1&sicl=&sich=&isofficer=&iscob=&isceo=&ispres=&iscoo=&iscfo=&isgc=&isvp=&isdirector=&istenpercent=&isother=&grp=0&nfl=&nfh=&nil=&nih=&nol=&noh=&v2l=&v2h=&oc2l=&oc2h=&sortcol=0&cnt=300&page=1&xp=1&xs=" | grep -o ">Ticker<"

# Real run against the VPS's shared DB via the existing remote-invoke script (per
# this repo's established convention -- see .claude/skills/investments/SKILL.md).
# This is the real Level 4 validation: a live scan-insiders run, inspect
# insider-scan-report.md and insider-pattern-analysis.md for the new cluster
# section, and confirm (or wait for) a real WhatsApp cluster/flip alert if one forms.
scripts/invoke_investments.ps1 -Package goat -Command "scan-insiders"
```

Read the resulting `investments/goat/insider-scan-report.md` and
`investments/goat/insider-pattern-analysis.md` afterward to confirm the new "By
Cluster — Buys Only" section renders sensibly (likely "not enough data yet" at
first, matching this report's own stated expectation for every new slice).

### Level 5: Additional Validation

None applicable (no MCP servers or extra CLI tools relevant to this feature).

---

## ACCEPTANCE CRITERIA

- [ ] `fetch_discovery_purchases()` queries `/screener` with no ticker filter,
      paginates until a short page, and the existing
      `test_fetch_discovery_purchases_parses_table_and_filters_purchase_code` test
      still passes unmodified.
- [ ] `run_discovery_scan` no longer skips held or watchlisted tickers for alerting
      or `goat_insider_filings_seen` recording; it skips only the
      `goat_pending_candidates` INSERT for held tickers.
- [ ] A second distinct insider buying the same ticker within the new **14-day**
      `GOAT_INSIDER_CLUSTER_ALERT_WINDOW_DAYS` of a first fires exactly one new
      `maybe_notify_cluster_alerts` WhatsApp message, separate from and in addition
      to the existing per-trade discovery alert.
- [ ] A cluster forming slowly across up to 14 days (not just within 7) is detected
      — explicitly tested, not just theoretically covered by the window value.
- [ ] A third insider joining an already-announced cluster does not re-fire the
      cluster alert.
- [ ] No minimum dollar value gates the cluster alert.
- [ ] A held ticker's buy-cluster is detected even though it's recorded via
      `run_holdings_watch` (kind='holdings_watch'), not just via `run_discovery_scan`
      — explicitly tested.
- [ ] The same insider buying back a ticker they sold within the new **90-day**
      `GOAT_INSIDER_FLIP_WINDOW_DAYS` fires a distinct `maybe_notify_insider_flips`
      WhatsApp message.
- [ ] A different insider's buy following someone else's sale does NOT count as a
      flip.
- [ ] `insider-pattern-analysis.md` gains a "By Cluster — Buys Only" section.
- [ ] All validation commands in this plan pass with zero errors.
- [ ] No regressions in the existing `my-trader` or `goat` test suites.
- [ ] `investments/goat/HANDOFF.md`'s status paragraph is updated per Task 10.

## COMPLETION CHECKLIST

- [ ] Tasks 1–12 completed in order.
- [ ] Each task's own VALIDATE command passed immediately after that task.
- [ ] Full test suites (both packages) pass.
- [ ] ruff + mypy clean on every changed file.
- [ ] Live `/screener` check re-run and confirmed immediately before Task 3's
      implementation (not just trusted from this plan's earlier run).
- [ ] Manual `scan-insiders` run against the real VPS DB completed and both
      report files inspected.
- [ ] HANDOFF.md status line appended.

---

## NOTES

- **Why `fetch_discovery_purchases` keeps its exact name and zero-arg call
  signature**: every existing test in `test_insider_scan.py` monkeypatches
  `"goat.insider_scan.openinsider.fetch_discovery_purchases"` with a zero-arg
  lambda. Changing the name or requiring arguments at the call site would force
  touching every one of those ~15 test mocks for no behavioral reason — the new
  `filing_date_days`/`min_value`/`max_pages` parameters all have sensible defaults
  specifically so the existing `openinsider.fetch_discovery_purchases()` call in
  `run_discovery_scan` (and every test mock) needs zero changes.
- **Why held-ticker gating is on the INSERT, not the alert**: this is the one place
  this plan deliberately keeps a status-dependent branch, per Shaun's explicit
  2026-11-08 confirmation — it's a UX nicety (don't prompt to "add" something
  already owned), not a coverage gate. Every other exclusion (watchlist, banned
  tickers, institutional 10%-owner filers) either stays fully removed (watchlist) or
  is unrelated to this change (banned tickers, institutional filter — both untouched,
  still apply before either detector ever runs).
- **Why the live cluster alert gets its OWN 14-day window, not a reuse of
  `GOAT_INSIDER_CLUSTER_WINDOW_DAYS`**: originally scoped as a reuse (per the
  handoff's own "Reuse `_compute_clusters`'s windowing logic" framing), but Shaun's
  follow-up explicitly widened this: "I also need it to keep a history, so you can
  see if a cluster buy has happened over more than one day ie maybe multiple
  directors buy, but over a two-week period" and confirmed 14 days specifically.
  The retrospective report's 7-day window is untouched and intentionally stays
  separate — it's a different, pre-existing statistic with its own history, not the
  same constant wearing two hats.
- **Why both detectors must live in `run_holdings_watch` as well as
  `run_discovery_scan`**: this was NOT in the original handoff and is the single
  most important architectural finding of this plan — discovered by tracing
  `dedup_key` collision behavior between the two scan functions (see the
  module-level "Patterns to Follow" note above for the full mechanism). Skipping
  this would make the entire feature silently non-functional for any held ticker,
  which is precisely the class of ticker Shaun was most concerned about fixing
  coverage for in the original handoff.
- **Why "history" doesn't need any new persistence mechanism**: Shaun's requirement
  to "keep a history" so a cluster spanning multiple days/weeks can be detected is
  already satisfied by querying `goat_insider_filings_seen` directly (a durable
  table, not an in-memory/single-run structure) — every prior day's buy filings are
  already there. The only change needed was widening the live detector's own lookup
  window (7 → 14 days) and making sure both recording paths are queried together (no
  `kind` filter), not adding a new history table.
- **Scope explicitly NOT covered by this plan** (confirmed out of scope): sell-side
  discovery (`run_discovery_sell_tracking`) is untouched except as a data source the
  flip detector's `get_most_recent_insider_sale` query reads from; Holdings Watch's
  existing sale-pattern gating (`GOAT_INSIDER_SALE_PCT_THRESHOLD_*`) is untouched;
  no retrospective report section is added for the flip signal (live-alert-only, not
  requested); `GOAT_INSIDER_PURCHASE_MIN_VALUE`/`GOAT_INSIDER_SALE_MIN_VALUE` are
  untouched.
