# Feature: my-trader Phase C — Macro Monitoring Indicators + Briefs Finance Candidate Sync

The following plan should be complete, but it's important to validate documentation and
codebase patterns and task sanity before implementing. Pay special attention to naming
of existing utils, types, and models. Import from the right files.

This plan implements **Phase C only**, as scoped in
`investments/my-trader/tool-preplan.md` ("Phase A scope finalized 2026-07-19" section,
Phase C bullet): "the 5 Monitoring Indicators (macro), Briefs Finance ingest→candidate
data-flow integration." Both pieces ride on the existing daily `monitor` job built in
Phase B (`.agent/plans/my-trader-phase-b-monitor.md`, committed) — **no new scheduled
task, Windows Task Scheduler entry, or systemd timer/service is created in this phase.**

## Feature Description

Two independent additions to the existing `mytrader.main monitor` command:

1. **Macro Monitoring Indicators** — four new portfolio-wide (not per-ticker) checks
   covering the 5 indicators confirmed in `tool-preplan.md`'s "Monitoring Indicators"
   section (MOVE index, housing price-to-income ratio, University of Michigan Consumer
   Sentiment Index, NY Fed recession-probability model, and the bull/bear-steepener
   distinction — the last of these is explicitly a *refinement folded into* the
   recession-probability check's detail text, not a fifth standalone flaggable check,
   per that section's own wording: "not independently verified as its own tested
   signal — flagged as a refinement to fold into the existing bullet"). These run once
   per Monitor invocation (not once per holding/watchlist row) and reuse the exact same
   `alert_history` dedup/reconciliation machinery Phase B already built for per-ticker
   checks, via a sentinel `ticker="MACRO"`, `source_table="macro"`.
2. **Briefs Finance ingest→candidate data-flow** — a new sync step that reads
   briefs-finance's `recommendations` table (populated by `investments/briefs-finance`'s
   existing `ingest` command) for new, non-excluded rows and inserts them into
   my-trader's `watchlist` as `status="raw"` candidates (never `"discussed"` — that
   stays a human/Find decision), so a newly ingested report's tickers become visible
   Find candidates automatically instead of sitting passively in briefs-finance's own
   DB until Shaun happens to ask about that exact ticker.

## User Story

As Shaun (multi-business founder who wants his investing tool to watch macro conditions
and surface new candidates without him having to remember to check either)
I want Monitor's daily run to also track known market-timing/valuation indicators and
pull in any new tickers briefs-finance has recently extracted from an ingested report
So that a Sahm-Rule-style threshold crossing or a stretched housing-affordability ratio
gets flagged the same way a dividend cut on an existing holding does, and a freshly
ingested Briefs Finance report's stock picks show up in `potential-holdings.md` for
review instead of requiring him to separately dig through briefs-finance's own output

## Problem Statement

Monitor (Phase B) only re-checks tickers Shaun already explicitly added — it has no
visibility into market-wide leading indicators (yield curve, consumer sentiment,
housing affordability, bond-market volatility) even though `tool-preplan.md` and
`investment-strategy.md`'s vetted "Lessons: Reading Late-Cycle / Recession Warning
Signals" section both call this out as a real, decided requirement. Separately, when
Shaun runs `briefs-finance`'s `ingest` command on a new PDF report, any tickers it
extracts sit in the `recommendations` table with no path into my-trader's watchlist —
Shaun would have to remember to look them up individually via Find.

## Solution Statement

Add `mytrader/macro_indicators.py` with four `CheckResult`-returning functions (MOVE
index, housing price-to-income, consumer sentiment, recession-probability +
steepener-refinement), reusing `scripts.macro.fred_value_on` (briefs-finance's existing
generic single-series FRED point-read helper — already handles the
`FRED_API_KEY`-not-set graceful-degradation case, no new environment-variable handling
needed) for the three FRED-backed indicators and a small direct `yfinance` history read
for the MOVE index. `run_monitor()` calls these once per run (not per-row) and feeds the
results through the *existing* `_reconcile_alerts()` function using a `"MACRO"`/`"macro"`
sentinel ticker/source_table pair — no new dedup logic, full reuse of Phase B's
alert-lifecycle state machine.

Add `mytrader/candidate_sync.py` with `sync_new_candidates(conn) -> list[dict]`, which
reads `recommendations` rows with `id` greater than a stored watermark (a new
`sync_state` key/value table, generic enough for future watermarks) and `excluded = 0`
(briefs-finance's own ethical-filter exclusion, already computed at ingest time — no
duplicate ethical-filter call needed, satisfying `tool-preplan.md`'s "ethical filter
inherited" decision by construction), skips anything already in `holdings` or
`watchlist` under any bucket, and inserts the rest as `watchlist` rows with
`status="raw"`, `bucket="unassigned"` (mirrors `seed.py`'s existing convention for
undecided-bucket raw candidates — see `seed.py:97-104`), `source="briefs_finance_ingest"`.
`run_monitor()` calls this once at the start of every run (the sync *is* the "automatic"
part — no separate schedule needed, satisfying the "not sit passively... until Shaun
happens to ask" requirement using the schedule that already exists).

Both additions extend `render_report()`'s output with two new sections and extend
`main.py` with one new CLI subcommand (`sync-candidates`, for manual/ad-hoc triggering
independent of a full Monitor run — mirrors the existing `snapshot`/`seed` subcommands'
manual-trigger role).

## Feature Metadata

**Feature Type**: Enhancement (extends existing Monitor job; no new domain the checks
touch, no new scheduled infrastructure)
**Estimated Complexity**: Medium (two new modules, both consumed by the same existing
`run_monitor()` call site; one schema addition; several new external-data integration
points with real threshold-calibration uncertainty — see NOTES)
**Primary Systems Affected**: `investments/my-trader/mytrader/` (new `macro_indicators.py`,
new `candidate_sync.py`, extended `monitor.py`, `db.py`, `config.py`, `main.py`),
`.claude/skills/my-trader/SKILL.md`
**Dependencies**: None new — reuses `yfinance` (already a my-trader dependency),
`requests` (already a my-trader dependency, transitively used by `scripts.macro`), and
briefs-finance's existing `scripts/macro.py` (`fred_value_on`) and `scripts/config.py`
(`FRED_API_KEY`) via the uv workspace path import already established in Phase A/B.

---

## CONTEXT REFERENCES

### Relevant Codebase Files — READ THESE BEFORE IMPLEMENTING

- `investments/my-trader/tool-preplan.md` (lines 255-330, "Assessment Checks" +
  "Monitoring Indicators" sections; lines 469-505, "Phase A scope finalized") — the
  five confirmed Monitoring Indicators and their exact confirmed framing (MOVE index,
  housing price-to-income, UMich sentiment, NY Fed recession model, bull/bear
  steepener-as-refinement). Every design decision below traces back to specific
  sentences in these sections — don't re-derive or re-litigate them.
- `investments/my-trader/investment-strategy.md` (lines 157-256, the two "Lessons"
  sections on late-cycle warning signals) — the existing leading-indicator checklist
  this phase extends (yield curve, Sahm Rule, Buffett Indicator, CAPE, HY credit
  spreads, GPR index are *not* rebuilt here — only the 4 items `tool-preplan.md`
  surfaced later, on 2026-07-18, that aren't already covered). Lines 292-296 record the
  most recent real-world snapshot values (Buffett Indicator ~240%, CAPE ~41.8, Sahm
  0.47) — useful context for sanity-checking new threshold defaults, not something to
  fetch/replicate.
- `.agent/plans/my-trader-phase-b-monitor.md` (full file, already built/committed) —
  the alert-reconciliation state machine (`_reconcile_alerts`), the report-rendering
  pattern, the `cached_session()` pattern, and the CLI-subcommand pattern this plan
  extends rather than reinvents. Read this before touching `monitor.py` — every change
  below is additive to what Phase B already built.
- `investments/my-trader/mytrader/monitor.py` (all, 140 lines) — `_reconcile_alerts`
  (lines 27-45) is called unmodified with a new sentinel ticker/source_table; `run_monitor`
  (lines 63-87) gets two new calls added (`candidate_sync.sync_new_candidates` at the
  start, macro checks via `_reconcile_alerts` before/after the existing holdings/watchlist
  loop); `render_report` (lines 90-118) gets two new sections; `write_report`/`maybe_notify`
  are extended, not replaced.
- `investments/my-trader/mytrader/db.py` (all, 223 lines) — `get_open_alert`/`insert_alert`/
  `acknowledge_alert`/`get_open_alerts` (lines 162-199) are reused unmodified for macro
  alerts (called with `ticker="MACRO"`, `source_table="macro"`). `upsert_watchlist_row`
  (lines 128-159) and `get_watchlist_row`/`get_holding_row` (lines 59-76, note: calling
  with `bucket=None` searches across all buckets — this is what `candidate_sync`'s
  dedup check needs) are reused unmodified for candidate sync. New functions
  (`get_sync_watermark`, `set_sync_watermark`) go in this file, matching its existing
  function-per-concern style.
- `investments/my-trader/mytrader/config.py` (all, 30 lines) — existing threshold
  constants (`PE_RICH_THRESHOLD`, `DIVIDEND_CUT_THRESHOLD_PCT`, etc., lines 25-30) are
  the pattern to mirror for the new macro threshold constants — same file, same
  "reasonable default, documented, tune later" convention already established by Phase A.
- `investments/my-trader/mytrader/checks/__init__.py` (all, 14 lines) — the shared
  `CheckResult` dataclass (`name`, `verdict`, `detail`, `data`) that `macro_indicators.py`'s
  four functions return, exactly like the 7 existing per-ticker checks in `checks/`.
  `macro_indicators.py` itself lives at `mytrader/macro_indicators.py`, **not** inside
  `mytrader/checks/`, because these aren't per-ticker checks called from
  `engine.run_assessment()` — they're Monitor-only, called once per run, never from Find.
- `investments/my-trader/mytrader/checks/concentration.py` (all, 72 lines) — the
  pattern for a check with sub-components combined into one overall verdict (lines
  57-61's `overall_verdict` logic) — not directly reused, but the closest existing
  example of "several related signals, one `CheckResult`," which
  `check_recession_signal()` below follows for folding the steepener classification
  into the same check as the raw spread/probability numbers.
- `investments/my-trader/mytrader/tests/test_monitor.py` (all, 194 lines) — the
  `monkeypatch.setattr("mytrader.monitor.engine.run_assessment", ...)` pattern (e.g.
  lines 38-49) is the exact shape to mirror for mocking `macro_indicators.check_*` and
  `candidate_sync.sync_new_candidates` inside `test_monitor.py`'s new/extended tests —
  patch at `mytrader.monitor.<module>.<function>`, not at the source module, since
  `monitor.py` imports these as `from . import macro_indicators, candidate_sync` (module
  references, not `from x import y` — confirm this import style when writing Task 2.1,
  it's what makes `mytrader.monitor.macro_indicators.check_move_index` patchable).
  Lines 12-17's `_no_real_yfinance` autouse fixture already stubs
  `market_data.fetch_ticker_data` for every test in this file — the new macro/sync
  tests inherit this for free, but must separately stub `macro_indicators`'s FRED/MOVE
  calls (different code path, not covered by that fixture).
- `investments/my-trader/mytrader/tests/test_db.py` (all, 145 lines) — the extension
  pattern (Task 5.1 in the Phase B plan added 6 new test functions to this same file
  for the alert/touch functions) to mirror for the 2 new watermark functions.
- `investments/my-trader/mytrader/tests/conftest.py` (all, 26 lines) — `db_conn`
  fixture (tmp_path-backed, both briefs-finance + mytrader tables initialised via
  `init_db` + `init_mytrader_tables`) — every new test uses this, never the real shared
  DB. Note it already calls briefs-finance's own `init_db`, so the `reports`/
  `recommendations` tables `candidate_sync` tests need already exist in this fixture —
  no conftest changes needed.
- `investments/my-trader/mytrader/find.py` (lines 23-25) — the existing comment
  `"'raw' is reserved for a future Phase C auto-ingest flow"` — this plan is that
  Phase C; confirms `status="raw"` (not `"discussed"`) is the correct status for synced
  candidates, already anticipated by Phase A's own code comment.
- `investments/my-trader/mytrader/seed.py` (lines 97-104, `_RAW_WATCHLIST`'s
  `bucket="unassigned"` rows) — the existing convention for a watchlist row whose
  bucket hasn't been decided yet, reused as the default bucket for
  `candidate_sync`-inserted rows (briefs-finance's `recommendations` table has no
  bucket concept — Bucket 1/2/3 is a my-trader-only classification a human assigns).
- `investments/briefs-finance/scripts/macro.py` (all, 73 lines) — `fred_value_on`
  (lines 23-46) is the exact function `macro_indicators.py` imports directly (not the
  whole `fetch_macro_snapshot`, which is report-scoped and writes to
  `macro_snapshot` — a table `candidate_sync`/`macro_indicators` never touches).
  Already returns `None` gracefully if `FRED_API_KEY` is unset (line 25) or the HTTP
  call fails (lines 45-46, broad `except Exception`) — `macro_indicators.py`'s checks
  inherit this degrade-to-`"unknown"` behavior for free by checking for `None`, exactly
  like `sector_risk.check()` does for missing `data.info` (`checks/sector_risk.py:10-11`).
- `investments/briefs-finance/scripts/config.py` (lines 31-45) — `FRED_SERIES` already
  defines `"yield_curve": "T10Y2Y"` and `"recession_prob": "RECPROUSM156N"`. This plan
  **duplicates** these two series-ID strings as my-trader-local constants
  (`FRED_YIELD_CURVE_SERIES`, `FRED_RECESSION_PROB_SERIES` in `mytrader/config.py`)
  rather than importing briefs-finance's `FRED_SERIES` dict — that dict is shaped for
  `fetch_fred_macro`'s bulk multi-series-in-one-call use (report-ingestion-time
  snapshot), whereas `macro_indicators.py` needs individual point-in-time reads at two
  different dates (today + a lookback date) for the steepener comparison, which is a
  different access pattern. Document this duplication explicitly in
  `macro_indicators.py`'s module docstring so a future reader doesn't "fix" it into a
  fragile cross-import.
- `investments/briefs-finance/scripts/db.py` (lines 39-49, `recommendations` table
  schema; lines 165-191, `upsert_recommendation`) — `candidate_sync.py` reads this
  table directly via raw SQL (`id`, `ticker`, `company_name`, `buy_thesis`, `excluded`
  columns) rather than importing a briefs-finance query helper, since no existing
  helper does "all recommendations after watermark ID" — this is new query shape,
  scoped to `candidate_sync.py` only. Tests seed rows via briefs-finance's own
  `upsert_report`/`upsert_recommendation` (lines 136-191) — never hand-roll `INSERT`
  statements against this table, since `foreign_keys=ON` (line 17) means a
  `recommendations` row needs a real `reports.id` to satisfy the FK.
- `investments/my-trader/mytrader/main.py` (all, 157 lines) — `cmd_snapshot`
  (lines 75-81) and `cmd_seed` (lines 84-90) are the closest pattern for the new
  `cmd_sync_candidates` (open conn, call, close, print summary, lazy import inside the
  function). Subparser registration at lines 133-135, dispatch dict at lines 139-147.
- `.claude/skills/my-trader/SKILL.md` (all, 123 lines, especially lines 107-116 "Known
  Limitations (Phase A)" which currently says "Phase C (macro indicators, Briefs
  Finance ingest→candidate data-flow) is still pending, not yet planned") — update this
  file once Phase C exists (Task 3.2).

### New Files to Create

- `investments/my-trader/mytrader/macro_indicators.py` — `check_move_index()`,
  `check_housing_affordability()`, `check_consumer_sentiment()`,
  `check_recession_signal()` — each returns a `CheckResult`, no arguments (portfolio-wide,
  not per-ticker).
- `investments/my-trader/mytrader/candidate_sync.py` — `sync_new_candidates(conn) ->
  list[dict]`.
- `investments/my-trader/mytrader/tests/test_macro_indicators.py`
- `investments/my-trader/mytrader/tests/test_candidate_sync.py`

### Files to Modify

- `investments/my-trader/mytrader/db.py` — add `get_sync_watermark`, `set_sync_watermark`;
  add `sync_state` table to `init_mytrader_tables`'s schema script.
- `investments/my-trader/mytrader/config.py` — add macro threshold/series-ID constants
  (see Task 1.1).
- `investments/my-trader/mytrader/monitor.py` — `run_monitor()` calls
  `candidate_sync.sync_new_candidates()` at the start and the 4 macro checks via
  `_reconcile_alerts("MACRO", "macro", [...], conn)` before the existing holdings/watchlist
  loop; `render_report()` gains two new sections; result dict gains `synced_candidates`
  and `macro_checks` keys.
- `investments/my-trader/mytrader/main.py` — add `sync-candidates` subcommand.
- `investments/my-trader/mytrader/tests/test_monitor.py` — extend for the new
  `run_monitor`/`render_report` behavior.
- `investments/my-trader/mytrader/tests/test_db.py` — extend for the 2 new watermark
  functions.
- `.claude/skills/my-trader/SKILL.md` — document macro indicators + candidate sync,
  update "Known Limitations" (Phase C is no longer "not yet planned").

### Relevant Documentation

None new — Phase C introduces no new external libraries. `yfinance` and FRED's REST API
(`https://api.stlouisfed.org/fred/series/observations`) are already integrated via
`scripts/macro.py`; this plan calls that existing integration point rather than adding
a new one. FRED series IDs used (`UMCSENT`, `MSPUS`, `MEHOINUSA672N`, `DGS2`, `DGS10`,
plus the two already-used `T10Y2Y`/`RECPROUSM156N`) should be spot-checked against
https://fred.stlouisfed.org at build time (Task 1.1's validation) — this plan's author
could not browse live during planning; see NOTES for the explicit confidence caveat.

### Patterns to Follow

**Naming Conventions:**
- `snake_case` throughout, matching Phases A/B.
- Check functions named `check_<indicator>()`, no arguments (distinguishes from the
  existing per-ticker `check(data, ...)` signature in `checks/*.py` — these are
  deliberately not that signature, since they're not per-ticker).
- Config constants for a new indicator grouped as `<INDICATOR>_<THING>`, e.g.
  `MOVE_INDEX_TICKER`, `MOVE_INDEX_FLAG_LEVEL` — mirrors existing
  `DIVIDEND_CUT_THRESHOLD_PCT`/`PE_RICH_THRESHOLD` grouping.

**Error Handling:**
- Every macro check function must independently degrade to `verdict="unknown"` on
  missing data (FRED key unset, HTTP failure, yfinance returning nothing) — never raise.
  Matches every existing check in `checks/*.py`. `run_monitor`'s existing per-row
  `try/except` (Phase B, `monitor.py:70-77`) is defense-in-depth for *unexpected*
  failures only, same as Phase B's own contract — the macro checks and
  `sync_new_candidates` should not rely on that as their primary error handling.
- `sync_new_candidates` wraps its own body in the same per-call `try/except Exception:
  print(...)` shape at the `run_monitor` call site (one line, matching how holdings/
  watchlist rows are isolated at `monitor.py:70-77`) so a briefs-finance DB read failure
  doesn't kill the whole Monitor run.

**DB Pattern:**
- `sync_state` is a generic `key TEXT PRIMARY KEY, value TEXT NOT NULL` table — not
  hardcoded to recommendation-sync only, in case a future watermark is needed. Use
  `INSERT OR REPLACE INTO sync_state (key, value) VALUES (?, ?)` — matches
  briefs-finance's own `upsert_outcome`/`upsert_sector_context` idiom
  (`scripts/db.py:194-223`) rather than introducing an `ON CONFLICT DO UPDATE` style
  not otherwise used in this codebase.
- Macro alerts use `ticker="MACRO"`, `source_table="macro"` as a fixed sentinel pair —
  document this clearly in `monitor.py`'s docstring since `alert_history.ticker` is
  otherwise always a real ticker symbol; a future reader filtering `alert_history` by
  looking for real tickers only should know to exclude/include this sentinel
  deliberately depending on intent.

**CLI Pattern:**
- `argparse` subparser + `cmd_sync_candidates(args)` + lazy import inside the function,
  matching `main.py`'s existing 7 subcommands.

**Testing Pattern:**
- `tmp_path`-backed SQLite via the existing `db_conn` fixture — never the real shared DB.
- `test_macro_indicators.py` monkeypatches `mytrader.macro_indicators.fred_value_on`
  and a small `_yfinance_latest`-style helper (see Task 2.1) — never hits real FRED/
  yfinance in tests.
- `test_candidate_sync.py` seeds `recommendations` rows via briefs-finance's own
  `scripts.db.upsert_report`/`upsert_recommendation` (never hand-rolled SQL, to respect
  the FK and stay consistent with how that table is written for real).
- `test_monitor.py`'s new/extended tests monkeypatch
  `mytrader.monitor.macro_indicators.check_move_index` (and the other 3) plus
  `mytrader.monitor.candidate_sync.sync_new_candidates` at the `monitor` module's own
  reference to them (see the GOTCHA above about import style).

---

## IMPLEMENTATION PLAN

### Phase 1: Foundation (DB watermark table + config constants)

**Tasks:**
- Add `sync_state` table + `get_sync_watermark`/`set_sync_watermark` to `db.py`, unit-tested
- Add macro threshold/series-ID constants to `config.py`

### Phase 2: Core Implementation (macro indicators + candidate sync modules)

**Tasks:**
- `macro_indicators.py`: 4 check functions, unit-tested
- `candidate_sync.py`: `sync_new_candidates()`, unit-tested

### Phase 3: Integration (wire into Monitor + CLI + skill doc)

**Tasks:**
- `monitor.py`: call both new modules from `run_monitor()`, extend `render_report()`
- `main.py`: `sync-candidates` subcommand
- Update `.claude/skills/my-trader/SKILL.md`

### Phase 4: Testing & Validation

**Tasks:**
- Unit tests for every new function
- Extend `test_monitor.py` for the new `run_monitor`/`render_report` behavior
- Manual validation: real `monitor` run against a scratch/tmp DB, then (with Shaun's
  go-ahead) against the real shared DB — specifically check whether `^MOVE` actually
  resolves via yfinance and whether FRED_API_KEY is set in this environment, since both
  are real open questions from planning (see NOTES)

---

## STEP-BY-STEP TASKS

Execute in order. Each task is atomic and independently testable.

### Task 1.1: UPDATE `investments/my-trader/mytrader/config.py`

- **IMPLEMENT**: Add below the existing threshold constants (after
  `SECTOR_CONCENTRATION_FLAG_PCT`):
  ```python
  # Phase C — macro monitoring indicators (tool-preplan.md "Monitoring Indicators",
  # confirmed 2026-07-19). Thresholds below are best-guess defaults set during planning
  # without live data access — sanity-check against real fetched values at Task 5.4's
  # manual validation step and tune if obviously wrong, same as PE_RICH_THRESHOLD etc.
  # above were always understood to be starting points, not final.
  MOVE_INDEX_TICKER = "^MOVE"  # ICE BofA MOVE Index — confirm this resolves via
                                # yfinance at Task 2.1's validation step; if it doesn't,
                                # check_move_index() must still degrade to "unknown"
                                # gracefully rather than blocking the rest of Phase C.
  MOVE_INDEX_FLAG_LEVEL = 140.0  # tool-preplan.md notes MOVE was "confirmed low as of
                                   # early 2026 (lowest since 2021)" — no crisis-level
                                   # reading to calibrate against during planning.

  FRED_MEDIAN_HOME_PRICE_SERIES = "MSPUS"
  FRED_MEDIAN_HOUSEHOLD_INCOME_SERIES = "MEHOINUSA672N"
  HOUSING_P2I_FLAG_RATIO = 5.0  # tool-preplan.md: ratio "~5x" currently vs "~2.5-3x
                                  # considered affordable by convention" (fact-checked
                                  # 2026-07-18) — flag at the current stretched level.

  FRED_CONSUMER_SENTIMENT_SERIES = "UMCSENT"
  CONSUMER_SENTIMENT_FLAG_LEVEL = 50.0  # tool-preplan.md: record low 44.8 (May 2026),
                                          # recovered to 49.5 (Jun 2026) — set just above
                                          # the recovered reading so a re-decline back
                                          # toward the record low would flag.

  FRED_YIELD_CURVE_SERIES = "T10Y2Y"       # matches briefs-finance's own
  FRED_RECESSION_PROB_SERIES = "RECPROUSM156N"  # FRED_SERIES values — see module
                                                  # docstring in macro_indicators.py for
                                                  # why these are duplicated, not imported.
  FRED_2Y_TREASURY_SERIES = "DGS2"
  FRED_10Y_TREASURY_SERIES = "DGS10"
  RECESSION_PROB_FLAG_PCT = 20.0  # tool-preplan.md: NY Fed model "~25-30% 12-month
                                    # recession probability as of mid-2026" — flag below
                                    # that observed level so Monitor already flags today.
  STEEPENER_LOOKBACK_DAYS = 90  # window for comparing short/long-end direction to
                                  # classify bull vs. bear steepening.
  ```
- **PATTERN**: `config.py:25-30` (existing threshold constants' style/comment density).
- **GOTCHA**: `FRED_YIELD_CURVE_SERIES`/`FRED_RECESSION_PROB_SERIES` intentionally
  duplicate string values already present in
  `investments/briefs-finance/scripts/config.py`'s `FRED_SERIES` dict — this is a
  deliberate, documented small duplication (see CONTEXT REFERENCES above), not an
  oversight to "fix" by importing that dict.
- **VALIDATE**: `cd investments/my-trader; uv run python -c "from mytrader import config; print(config.MOVE_INDEX_TICKER, config.HOUSING_P2I_FLAG_RATIO)"`

### Task 1.2: UPDATE `investments/my-trader/mytrader/db.py`

- **IMPLEMENT**: Add to `init_mytrader_tables`'s `executescript` call (inside the same
  triple-quoted string, after the `alert_history` table definition):
  ```sql
  CREATE TABLE IF NOT EXISTS sync_state (
      key             TEXT PRIMARY KEY,
      value           TEXT NOT NULL
  );
  ```
  Add after the existing `touch_checked` function:
  ```python
  def get_sync_watermark(conn: sqlite3.Connection, key: str) -> str | None:
      row = conn.execute("SELECT value FROM sync_state WHERE key = ?", (key,)).fetchone()
      return row["value"] if row else None


  def set_sync_watermark(conn: sqlite3.Connection, key: str, value: str) -> None:
      with conn:
          conn.execute(
              "INSERT OR REPLACE INTO sync_state (key, value) VALUES (?, ?)",
              (key, value),
          )
  ```
- **PATTERN**: `db.py:196-199` (`get_open_alerts`, simple parameterized read) for the
  getter; briefs-finance's `scripts/db.py:194-208` (`upsert_outcome`'s `INSERT OR
  REPLACE` idiom) for the setter.
- **VALIDATE**: `pytest mytrader/tests/test_db.py -v` (extend with 2 new test functions,
  see Task 4.1).

### Task 2.1: CREATE `investments/my-trader/mytrader/macro_indicators.py`

- **IMPLEMENT**: Full module:
  ```python
  """Macro monitoring indicators — portfolio-wide (not per-ticker) leading indicators
  for Monitor. Distinct from checks/*.py's 7 per-ticker checks: these run once per
  Monitor invocation, never from Find, and are reconciled against alert_history using
  a "MACRO"/"macro" sentinel ticker/source_table (see monitor.py) rather than a real
  ticker. Covers the 5 indicators confirmed in tool-preplan.md's "Monitoring Indicators"
  section (2026-07-19): MOVE index, housing price-to-income ratio, University of
  Michigan Consumer Sentiment Index, NY Fed recession-probability model, and the
  bull/bear-steepener distinction — the last is folded into check_recession_signal()'s
  detail text rather than being a 5th standalone check, per that section's own note
  that it's "a refinement to fold into the existing bullet," not an independently
  tested signal.

  FRED_YIELD_CURVE_SERIES/FRED_RECESSION_PROB_SERIES in config.py intentionally
  duplicate string values already present in briefs-finance's own
  scripts/config.py:FRED_SERIES — that dict is shaped for fetch_fred_macro()'s bulk
  multi-series report-ingestion-time snapshot, while this module needs individual
  point-in-time reads at two different dates (today + a lookback date, for the
  steepener comparison), a different access pattern. Duplicating two short strings was
  judged simpler than reshaping shared code across two independently-versioned projects.
  """

  from __future__ import annotations

  from datetime import date, timedelta

  from scripts.macro import fred_value_on

  from . import config
  from .checks import CheckResult


  def _yfinance_latest_close(ticker: str) -> float | None:
      import yfinance as yf

      try:
          hist = yf.Ticker(ticker).history(period="5d")
          if hist.empty:
              return None
          return float(hist["Close"].iloc[-1])
      except Exception:
          return None


  def check_move_index() -> CheckResult:
      value = _yfinance_latest_close(config.MOVE_INDEX_TICKER)
      if value is None:
          return CheckResult(
              name="move_index", verdict="unknown",
              detail=f"{config.MOVE_INDEX_TICKER} data unavailable via yfinance",
          )
      if value >= config.MOVE_INDEX_FLAG_LEVEL:
          return CheckResult(
              name="move_index", verdict="flag",
              detail=f"MOVE index at {value:.1f}, at/above the "
                     f"{config.MOVE_INDEX_FLAG_LEVEL:.0f} bond-market-stress threshold",
              data={"value": value},
          )
      return CheckResult(
          name="move_index", verdict="ok",
          detail=f"MOVE index at {value:.1f}, below the flag threshold",
          data={"value": value},
      )


  def check_housing_affordability() -> CheckResult:
      today = date.today()
      price = fred_value_on(config.FRED_MEDIAN_HOME_PRICE_SERIES, today)
      income = fred_value_on(config.FRED_MEDIAN_HOUSEHOLD_INCOME_SERIES, today)
      if not price or not income:
          return CheckResult(
              name="housing_affordability", verdict="unknown",
              detail="FRED median home price / household income data unavailable "
                     "(FRED_API_KEY not set, or series unavailable)",
          )
      ratio = round(price / income, 2)
      if ratio >= config.HOUSING_P2I_FLAG_RATIO:
          return CheckResult(
              name="housing_affordability", verdict="flag",
              detail=f"Housing price-to-income ratio at {ratio}x, at/above the "
                     f"{config.HOUSING_P2I_FLAG_RATIO}x stress threshold",
              data={"ratio": ratio},
          )
      return CheckResult(
          name="housing_affordability", verdict="ok",
          detail=f"Housing price-to-income ratio at {ratio}x",
          data={"ratio": ratio},
      )


  def check_consumer_sentiment() -> CheckResult:
      value = fred_value_on(config.FRED_CONSUMER_SENTIMENT_SERIES, date.today())
      if value is None:
          return CheckResult(
              name="consumer_sentiment", verdict="unknown",
              detail="FRED UMich consumer sentiment data unavailable "
                     "(FRED_API_KEY not set, or series unavailable)",
          )
      if value <= config.CONSUMER_SENTIMENT_FLAG_LEVEL:
          return CheckResult(
              name="consumer_sentiment", verdict="flag",
              detail=f"UMich consumer sentiment at {value:.1f}, at/below the "
                     f"{config.CONSUMER_SENTIMENT_FLAG_LEVEL:.0f} stress threshold",
              data={"value": value},
          )
      return CheckResult(
          name="consumer_sentiment", verdict="ok",
          detail=f"UMich consumer sentiment at {value:.1f}",
          data={"value": value},
      )


  def check_recession_signal() -> CheckResult:
      today = date.today()
      prior = today - timedelta(days=config.STEEPENER_LOOKBACK_DAYS)

      curve_now = fred_value_on(config.FRED_YIELD_CURVE_SERIES, today)
      recession_prob = fred_value_on(config.FRED_RECESSION_PROB_SERIES, today)
      if curve_now is None or recession_prob is None:
          return CheckResult(
              name="recession_signal", verdict="unknown",
              detail="FRED yield-curve / recession-probability data unavailable "
                     "(FRED_API_KEY not set, or series unavailable)",
          )

      short_now = fred_value_on(config.FRED_2Y_TREASURY_SERIES, today)
      short_prior = fred_value_on(config.FRED_2Y_TREASURY_SERIES, prior)
      long_now = fred_value_on(config.FRED_10Y_TREASURY_SERIES, today)
      long_prior = fred_value_on(config.FRED_10Y_TREASURY_SERIES, prior)

      steepener = None
      if None not in (short_now, short_prior, long_now, long_prior):
          short_falling = short_now < short_prior
          long_rising = long_now > long_prior
          if short_falling and not long_rising:
              steepener = "bull steepener (short rates falling — benign, Fed-cut-driven)"
          elif long_rising and not short_falling:
              steepener = ("bear steepener (long rates rising — inflation/debt-concern "
                            "driven, historically the more concerning pattern)")
          elif short_falling and long_rising:
              steepener = "mixed steepening (both ends moving)"

      detail = f"10Y-2Y spread {curve_now:+.2f}pp, recession probability {recession_prob:.1f}%"
      if steepener:
          detail += f"; {steepener}"

      verdict = "flag" if recession_prob >= config.RECESSION_PROB_FLAG_PCT else "ok"
      return CheckResult(
          name="recession_signal", verdict=verdict, detail=detail,
          data={"yield_curve": curve_now, "recession_prob": recession_prob, "steepener": steepener},
      )


  def run_all() -> list[CheckResult]:
      return [
          check_move_index(),
          check_housing_affordability(),
          check_consumer_sentiment(),
          check_recession_signal(),
      ]
  ```
- **IMPORTS**: `from scripts.macro import fred_value_on` — cross-project import, same
  uv-workspace mechanism already used elsewhere (e.g. `engine.py:8`'s
  `from scripts.ethical_filter import check_ticker`) — this one is a plain package
  import (no `sys.path` manipulation needed, unlike `monitor.py`'s `maybe_notify`
  which reaches into `.claude/scripts`, a directory *outside* the uv workspace).
- **PATTERN**: `checks/sector_risk.py:9-30` for the "return early with `unknown` verdict
  on missing data, otherwise compute and classify" shape, applied here with no `data`
  argument.
- **GOTCHA**: `^MOVE` may not reliably resolve via yfinance (untested during planning —
  no live network access in this session). `check_move_index()` must degrade to
  `"unknown"` if `_yfinance_latest_close` returns `None`, which it already does by
  design — this is not a blocker, just something to actually observe at Task 5.4's
  manual validation and note in `handoff.md` if it turns out `^MOVE` never resolves
  (in which case this indicator simply stays permanently `"unknown"`, same as
  `concentration.check()`'s Berkshire sub-check already does when
  `BERKSHIRE_HOLDINGS` is empty).
- **GOTCHA**: All four threshold constants in `config.py` are best-guess defaults set
  without live data access — do not treat them as validated. Flag any run where a
  check immediately flags on first real execution as *possibly* a miscalibrated
  threshold rather than a genuine new alert, and mention this explicitly to Shaun during
  Task 5.4's manual validation rather than silently accepting the first real output.
- **VALIDATE**: `pytest mytrader/tests/test_macro_indicators.py -v` (Task 4.2).

### Task 2.2: CREATE `investments/my-trader/mytrader/candidate_sync.py`

- **IMPLEMENT**: Full module:
  ```python
  """Briefs Finance ingest -> my-trader candidate sync (tool-preplan.md "Briefs Finance
  report integration", confirmed 2026-07-19).

  Reads briefs-finance's recommendations table for rows newer than a stored watermark
  (sync_state key "briefs_finance_last_recommendation_id") and inserts each into
  my-trader's watchlist as status="raw" (never "discussed" -- see find.py's own
  "reserved for a future Phase C auto-ingest flow" comment; a human still has to
  actually discuss a candidate before Monitor's assessment loop picks it up, since that
  loop filters to status="discussed" only). Bucket defaults to "unassigned" (matches
  seed.py's existing convention -- briefs-finance's recommendations table has no bucket
  concept, that's a my-trader-only classification a human assigns).

  Ethical filtering is inherited, not re-applied: recommendations.excluded is already
  computed by briefs-finance's own ingest_pdf() via check_ticker() at ingest time
  (scripts/ingest.py:86), so filtering WHERE excluded = 0 here satisfies
  tool-preplan.md's "ethical filter inherited" decision without a second ethical-filter
  call.
  """

  from __future__ import annotations

  import sqlite3
  from typing import Any

  from . import db, tickers

  _WATERMARK_KEY = "briefs_finance_last_recommendation_id"


  def sync_new_candidates(conn: sqlite3.Connection) -> list[dict[str, Any]]:
      last_id = int(db.get_sync_watermark(conn, _WATERMARK_KEY) or 0)
      rows = conn.execute(
          """SELECT id, ticker, company_name, buy_thesis FROM recommendations
             WHERE id > ? AND excluded = 0 ORDER BY id""",
          (last_id,),
      ).fetchall()

      added: list[dict[str, Any]] = []
      max_id = last_id
      for row in rows:
          max_id = max(max_id, row["id"])
          normalized = tickers.normalize(row["ticker"])
          if db.get_holding_row(conn, normalized) is not None:
              continue
          if db.get_watchlist_row(conn, normalized) is not None:
              continue
          db.upsert_watchlist_row(
              conn, ticker=normalized, name=row["company_name"], asset_type="stock",
              bucket="unassigned", status="raw", notes=row["buy_thesis"] or "",
              source="briefs_finance_ingest",
          )
          added.append({"ticker": normalized, "company_name": row["company_name"]})

      if max_id > last_id:
          db.set_sync_watermark(conn, _WATERMARK_KEY, str(max_id))
      return added
  ```
- **IMPORTS**: `from . import db, tickers` — relative, matching Phase A/B's convention.
  No new cross-project import beyond what `db.py`/`tickers.py` already need — this
  module reads `recommendations` via the connection it's handed (already the shared
  briefs-finance+mytrader DB, per `main.py`'s `_open_conn`), not via a fresh connection.
- **PATTERN**: `db.get_watchlist_row`/`get_holding_row` called with `bucket=None`
  (the default) intentionally searches across *all* buckets for that ticker
  (`db.py:64-66`, `74-76`) — this is exactly the "already tracked under some bucket,
  skip" dedup check needed here, not a bug to "fix" by passing a bucket.
- **GOTCHA**: `asset_type="stock"` is hardcoded — briefs-finance's `recommendations`
  table has no asset-type column, and its PDF sources are typically individual stock
  picks (per `ingest.py`'s own recommendation-extraction prompt intent). If a future
  report recommends an ETF, this would mislabel it; not a blocker for Phase C (the
  `asset_type` field is display-only in `potential-holdings.md`'s snapshot, not used by
  any check), but worth a one-line note in `handoff.md` at completion.
- **VALIDATE**: `pytest mytrader/tests/test_candidate_sync.py -v` (Task 4.3).

### Task 3.1: UPDATE `investments/my-trader/mytrader/monitor.py`

- **IMPLEMENT**: Add to the imports:
  ```python
  from . import candidate_sync, config, db, engine, macro_indicators, market_data, snapshot
  ```
  Add a new constant near `SEVERITY`:
  ```python
  MACRO_TICKER = "MACRO"
  MACRO_SOURCE_TABLE = "macro"
  ```
  Update `run_monitor`:
  ```python
  def run_monitor(conn: sqlite3.Connection) -> dict[str, Any]:
      try:
          synced_candidates = candidate_sync.sync_new_candidates(conn)
      except Exception as e:
          print(f"[monitor] error syncing briefs-finance candidates: {e}")
          synced_candidates = []

      holdings = db.get_all_holdings(conn)
      watchlist = [w for w in db.get_all_watchlist(conn) if w["status"] == "discussed"]

      new_alerts: list[dict[str, Any]] = []
      with market_data.cached_session():
          for row in holdings:
              try:
                  new_alerts.extend(_process_row(row, "holdings", conn))
              except Exception as e:
                  print(f"[monitor] error checking holding {row['ticker']}: {e}")
          for row in watchlist:
              try:
                  new_alerts.extend(_process_row(row, "watchlist", conn))
              except Exception as e:
                  print(f"[monitor] error checking watchlist {row['ticker']}: {e}")

      try:
          macro_checks = macro_indicators.run_all()
      except Exception as e:
          print(f"[monitor] error running macro indicators: {e}")
          macro_checks = []
      new_alerts.extend(_reconcile_alerts(MACRO_TICKER, MACRO_SOURCE_TABLE, macro_checks, conn))

      snapshot.regenerate_all(conn)

      return {
          "checked_holdings": len(holdings),
          "checked_watchlist": len(watchlist),
          "new_alerts": new_alerts,
          "open_alerts": [dict(a) for a in db.get_open_alerts(conn)],
          "macro_checks": [
              {"name": c.name, "verdict": c.verdict, "detail": c.detail} for c in macro_checks
          ],
          "synced_candidates": synced_candidates,
      }
  ```
  Update `render_report` — insert two new sections after "### All Open Alerts" and
  before the "Last auto-generated" footer line:
  ```python
      lines += ["", "### Macro Indicators (this run)"]
      if result["macro_checks"]:
          for c in result["macro_checks"]:
              lines.append(f"- **{c['name']}** [{c['verdict']}] — {c['detail']}")
      else:
          lines.append("Unavailable this run.")

      lines += ["", "### New Candidates Synced From Briefs Finance"]
      if result["synced_candidates"]:
          for cand in result["synced_candidates"]:
              lines.append(f"- **{cand['ticker']}** — {cand['company_name'] or '(no name)'}")
      else:
          lines.append("None this run.")
  ```
  (Insert these two blocks between the existing `"### All Open Alerts"` block and the
  final `lines += ["", f"Last auto-generated: ..."]` line — do not reorder the existing
  sections.)
- **PATTERN**: `monitor.py:63-87` (`run_monitor`, existing structure — every new call is
  additive, wrapped in the same per-concern `try/except Exception: print(...)` shape
  already used for the holdings/watchlist loop bodies) and `monitor.py:90-118`
  (`render_report`, existing section-per-concern list-building shape).
- **GOTCHA**: `_reconcile_alerts` (unmodified, `monitor.py:27-45`) is generic over
  `ticker`/`source_table`/`checks` already — calling it with `MACRO_TICKER`/
  `MACRO_SOURCE_TABLE` requires no changes to that function. This is the reuse payoff
  planned in the Feature Description — confirm no edits are needed to
  `_reconcile_alerts` itself.
- **GOTCHA**: Macro checks do **not** go through `_process_row`/`touch_checked` (that
  function's `table` parameter asserts `table in ("holdings", "watchlist")` —
  `db.py:389`, unchanged in Phase C — passing `"macro"` there would raise). Macro
  checks only go through `_reconcile_alerts`, never `touch_checked`.
- **VALIDATE**: `pytest mytrader/tests/test_monitor.py -v` (Task 4.4, extends existing
  file).

### Task 3.2: UPDATE `investments/my-trader/mytrader/main.py`

- **IMPLEMENT**: Add a `cmd_sync_candidates` function (near the other `cmd_*` functions):
  ```python
  def cmd_sync_candidates(args) -> None:
      from .candidate_sync import sync_new_candidates
      from .snapshot import regenerate_all

      conn = _open_conn()
      added = sync_new_candidates(conn)
      if added:
          regenerate_all(conn)
      conn.close()
      print(f"Synced {len(added)} new candidate(s) from Briefs Finance recommendations.")
  ```
  Register the subparser:
  ```python
  subparsers.add_parser("sync-candidates", help="Pull new Briefs Finance recommendations into the watchlist")
  ```
  Add `"sync-candidates": cmd_sync_candidates` to the `dispatch` dict.
- **PATTERN**: `main.py:75-81` (`cmd_snapshot`) for the open-conn/call/close/print shape.
- **GOTCHA**: Unlike `cmd_monitor`, this subcommand only regenerates snapshots if
  candidates were actually added (`if added:`) — avoids an unnecessary yfinance-hitting
  `snapshot.regenerate_all` call (which re-fetches current prices for every holding,
  `snapshot.py:17-21`) on a no-op sync.
- **VALIDATE**: `cd investments/my-trader; uv run python -m mytrader.main --help` lists
  `sync-candidates` alongside the existing 7 subcommands.

### Task 3.3: UPDATE `.claude/skills/my-trader/SKILL.md`

- **IMPLEMENT**: Add to the "Quick Reference" command block:
  ```powershell
  # Pull new Briefs Finance recommendations into the watchlist as raw candidates
  # (also runs automatically as part of `monitor`, this is for manual/ad-hoc triggering)
  uv run --directory investments/my-trader python -m mytrader.main sync-candidates
  ```
  Add a new "## Macro Monitoring Indicators" section (after "## Monitor") summarizing:
  4 portfolio-wide checks run once per Monitor invocation (MOVE index, housing
  price-to-income, UMich consumer sentiment, recession-probability + steepener
  classification), same high-bar alert-dedup mechanism as the per-ticker checks (via a
  `"MACRO"`/`"macro"` sentinel), shown in `monitor-report.md`'s "Macro Indicators"
  section every run regardless of flag status (unlike per-ticker checks, which are only
  shown when flagged/open).
  Add a new "## Briefs Finance Candidate Sync" section (after the macro section)
  summarizing: runs automatically as part of every `monitor` invocation (also
  manually triggerable via `sync-candidates`), pulls new non-excluded
  `recommendations` rows into the watchlist as `status="raw"` (not `"discussed"` —
  still requires Shaun/Find to actually vet a candidate before Monitor starts
  re-checking it), watermarked so re-runs don't reprocess the same recommendations.
  Update "## Known Limitations (Phase A)" — rename section or add a "Phase C" note
  replacing the "still pending, not yet planned" line with: macro threshold constants
  are best-guess defaults set without live data access, tune after real output is
  observed; `candidate_sync` hardcodes `asset_type="stock"` since briefs-finance's
  `recommendations` table has no asset-type column; MOVE index may permanently read
  `"unknown"` if `^MOVE` doesn't resolve via yfinance (confirm during Level 4
  validation).
- **PATTERN**: `SKILL.md`'s existing section structure.
- **VALIDATE**: Manual read-through — no command executes here.

---

### Task 4.1: EXTEND `investments/my-trader/mytrader/tests/test_db.py`

- **IMPLEMENT**: Add test functions:
  - `test_get_sync_watermark_returns_none_when_unset`
  - `test_set_sync_watermark_then_get_returns_value`
  - `test_set_sync_watermark_overwrites_existing_value`
- **VALIDATE**: `pytest mytrader/tests/test_db.py -v`

### Task 4.2: CREATE `investments/my-trader/mytrader/tests/test_macro_indicators.py`

- **IMPLEMENT**:
  - `test_check_move_index_unknown_when_yfinance_returns_none` — monkeypatch
    `mytrader.macro_indicators._yfinance_latest_close` to return `None`, assert
    `verdict == "unknown"`.
  - `test_check_move_index_flags_above_threshold` / `test_check_move_index_ok_below_threshold`
    — monkeypatch the same helper to return values above/below
    `config.MOVE_INDEX_FLAG_LEVEL`.
  - `test_check_housing_affordability_unknown_when_fred_unavailable` — monkeypatch
    `mytrader.macro_indicators.fred_value_on` to return `None`, assert `"unknown"`.
  - `test_check_housing_affordability_flags_above_ratio` / `..._ok_below_ratio` —
    monkeypatch `fred_value_on` with a stub returning different values depending on
    the `series_id` argument (price series vs. income series) to produce a controlled
    ratio above/below `config.HOUSING_P2I_FLAG_RATIO`.
  - `test_check_consumer_sentiment_unknown_when_fred_unavailable` /
    `..._flags_at_or_below_threshold` / `..._ok_above_threshold`.
  - `test_check_recession_signal_unknown_when_curve_or_prob_missing`.
  - `test_check_recession_signal_flags_at_or_above_threshold`.
  - `test_check_recession_signal_classifies_bull_steepener` — stub `fred_value_on` so
    short-end (`DGS2`) falls and long-end (`DGS10`) doesn't rise between the two dates
    queried, assert `"bull steepener"` appears in the detail text.
  - `test_check_recession_signal_classifies_bear_steepener` — inverse of the above.
  - `test_check_recession_signal_no_steepener_classification_when_lookback_data_missing`
    — stub `fred_value_on` to return `None` for the lookback-date calls only, assert
    the detail text still contains the spread/probability numbers but no steepener
    phrase (graceful partial degradation).
  - `test_run_all_returns_four_check_results`.
- **PATTERN**: `mytrader/tests/test_engine.py`'s `monkeypatch.setattr` shape, applied to
  `mytrader.macro_indicators.fred_value_on` and `mytrader.macro_indicators._yfinance_latest_close`.
  For stubbing `fred_value_on` differently per `series_id`, use a small local function
  (`def _fake(series_id, target): return {"DGS2": ..., "DGS10": ...}.get(series_id)`)
  rather than a fixed-return lambda.
- **VALIDATE**: `pytest mytrader/tests/test_macro_indicators.py -v`

### Task 4.3: CREATE `investments/my-trader/mytrader/tests/test_candidate_sync.py`

- **IMPLEMENT**:
  - A local helper seeding one `reports` row + one or more `recommendations` rows via
    `scripts.db.upsert_report`/`upsert_recommendation` (imported directly — these
    already exist and are already tested by briefs-finance's own test suite).
  - `test_sync_new_candidates_inserts_new_watchlist_row` — seed one non-excluded
    recommendation, call `sync_new_candidates(db_conn)`, assert 1 item returned and
    `db.get_watchlist_row(db_conn, ticker)` has `status == "raw"`,
    `source == "briefs_finance_ingest"`, `bucket == "unassigned"`.
  - `test_sync_new_candidates_skips_excluded_recommendations` — seed one recommendation
    with `excluded=True`, assert it's not added.
  - `test_sync_new_candidates_skips_ticker_already_in_holdings` — seed a holding for
    the same ticker first, assert it's skipped.
  - `test_sync_new_candidates_skips_ticker_already_in_watchlist` — seed a watchlist row
    (any bucket/status) for the same ticker first, assert it's skipped.
  - `test_sync_new_candidates_advances_watermark_and_does_not_reprocess` — call
    `sync_new_candidates` twice with no new recommendations added between calls,
    assert the second call returns `[]`.
  - `test_sync_new_candidates_only_processes_rows_after_watermark` — seed 2
    recommendations, sync once (watermark advances past both), seed a 3rd, sync again,
    assert only the 3rd is returned the second time.
  - `test_sync_new_candidates_uses_empty_notes_when_buy_thesis_is_none` — seed a
    recommendation with `buy_thesis=None`, assert the resulting watchlist row's
    `notes` is `""`, not `None`.
- **PATTERN**: `mytrader/tests/conftest.py`'s `db_conn` fixture (already initializes
  both briefs-finance and mytrader tables, satisfying the `recommendations` table's FK
  to `reports`).
- **VALIDATE**: `pytest mytrader/tests/test_candidate_sync.py -v`

### Task 4.4: EXTEND `investments/my-trader/mytrader/tests/test_monitor.py`

- **IMPLEMENT**: Add a new autouse-adjacent fixture or per-test monkeypatch stubbing
  `mytrader.monitor.macro_indicators.run_all` to return `[]` and
  `mytrader.monitor.candidate_sync.sync_new_candidates` to return `[]` **by default**
  in every existing test in this file (so Phase B's already-passing tests keep passing
  unchanged) — add this as a second autouse fixture alongside `_no_real_yfinance`
  (`test_monitor.py:12-17`):
  ```python
  @pytest.fixture(autouse=True)
  def _no_macro_or_sync_by_default(monkeypatch):
      monkeypatch.setattr("mytrader.monitor.macro_indicators.run_all", lambda: [])
      monkeypatch.setattr("mytrader.monitor.candidate_sync.sync_new_candidates", lambda conn: [])
  ```
  Add new test functions (each overrides one of the two autouse stubs above via a
  fresh `monkeypatch.setattr` call inside the test body):
  - `test_run_monitor_includes_macro_alert_for_first_flag` — override
    `macro_indicators.run_all` to return
    `[CheckResult(name="recession_signal", verdict="flag", detail="...")]`, assert one
    new alert appears with `ticker == "MACRO"`, `source_table == "macro"`.
  - `test_run_monitor_macro_alert_stays_quiet_on_repeat_flag` — same pattern as the
    existing `test_run_monitor_stays_quiet_on_repeat_flag` (lines 51-62), applied to a
    macro check across two `run_monitor` calls.
  - `test_run_monitor_includes_synced_candidates_in_result` — override
    `candidate_sync.sync_new_candidates` to return
    `[{"ticker": "NVDA", "company_name": "NVIDIA Corp"}]`, assert
    `result["synced_candidates"]` matches.
  - `test_render_report_includes_macro_and_candidate_sections` — construct a `result`
    dict by hand including `macro_checks` and `synced_candidates` keys, assert the
    rendered report contains expected substrings for both new sections and the
    `"Unavailable this run." "None this run."` fallback text when both are empty.
  - Update `_fake_result` or the existing render-report test's hand-built `result`
    dicts as needed to include the two new required keys (`macro_checks`,
    `synced_candidates`) — every existing call site that builds a `result` dict by hand
    for `render_report`/`write_report` tests needs these keys now, since `render_report`
    will KeyError without them.
- **PATTERN**: `test_monitor.py:12-17` (existing autouse fixture) for the new autouse
  fixture; `test_monitor.py:51-62` for the repeat-flag-stays-quiet pattern reused for
  macro alerts.
- **GOTCHA**: The existing `test_render_report_lists_new_and_open_alerts` (lines
  137-161) and `test_write_report_writes_to_configured_path` (lines 164-170) build
  `result` dicts by hand without `macro_checks`/`synced_candidates` keys — these will
  break once `render_report` reads those keys unconditionally. Update both existing
  dicts to include `"macro_checks": []` and `"synced_candidates": []` as part of this
  task (not a new test, a required fix to existing tests) — call this out explicitly
  when implementing so it isn't missed as a "pre-existing test failure."
- **VALIDATE**: `pytest mytrader/tests/test_monitor.py -v`

### Task 4.5: MANUAL VALIDATION

1. `cd investments/my-trader; uv run pytest mytrader/tests -v` — full suite (Phase A +
   B's ~87 tests plus Phase C's new tests), zero failures, zero regressions.
2. `cd investments/my-trader; uv run ruff check .` and `uv run mypy mytrader` — clean.
3. Check whether `FRED_API_KEY` is set in this environment
   (`investments/briefs-finance/.env` — see `.env.example`'s documented variable). If
   unset, the 3 FRED-backed macro checks will all read `"unknown"` in a real run — this
   is expected graceful degradation, not a bug, but confirm this is understood before
   treating a real run's all-`"unknown"` macro section as broken.
4. `cd investments/my-trader; uv run python -c "import yfinance as yf; h = yf.Ticker('^MOVE').history(period='5d'); print(h)"`
   — confirm whether `^MOVE` actually returns data. If it comes back empty, note this
   in `handoff.md` at completion (the check itself doesn't need code changes either
   way — it already degrades to `"unknown"` — but it's worth Shaun knowing which of the
   4 macro checks are actually live vs. permanently `"unknown"`).
5. `cd investments/my-trader; uv run python -m mytrader.main sync-candidates` — real run
   against the actual shared `investments.db`. If briefs-finance has any existing
   `recommendations` rows from prior ingests, confirm some reasonable subset appear as
   new `"raw"` watchlist rows in `potential-holdings.md` afterward (eyeball the file).
   Run a second time immediately — confirm `0` new candidates the second time (proves
   the watermark works against real data).
6. `cd investments/my-trader; uv run python -m mytrader.main monitor` — real run against
   the actual shared DB. Eyeball `investments/my-trader/monitor-report.md`: the new
   "Macro Indicators" section should show 4 entries (some possibly `"unknown"` per
   steps 3-4 above), and "New Candidates Synced" should show `"None this run."` if step
   5 already consumed the backlog.
7. In a fresh Claude Code session, ask "what's my-trader Monitor showing" or similar and
   confirm the `my-trader` skill can read and summarize the new report sections
   conversationally (manual — skills aren't unit-testable).

---

## TESTING STRATEGY

### Unit Tests

Every new function gets direct coverage: `db.py`'s 2 new watermark functions (Task
4.1), `macro_indicators.py`'s 4 check functions across unknown/ok/flag branches plus
the steepener classification's 3 outcomes (Task 4.2), `candidate_sync.py`'s dedup/
watermark/exclusion logic (Task 4.3). All DB-touching tests use the existing `db_conn`
tmp_path fixture. No test hits real yfinance, real FRED, or the real shared
`investments.db`.

### Integration Tests

`test_monitor.py`'s extended tests (Task 4.4) exercise `monitor.py` + `db.py` +
(mocked) `macro_indicators.py`/`candidate_sync.py` together — the same shape as Phase
B's own multi-run alert-lifecycle tests, extended to cover the macro sentinel path.
`test_candidate_sync.py`'s watermark tests are effectively integration tests against a
real (tmp_path) SQLite DB spanning briefs-finance's `recommendations` table and
my-trader's `watchlist`/`sync_state` tables together.

### Edge Cases

- All 4 macro checks return `"unknown"` (FRED_API_KEY unset AND `^MOVE` unresolvable)
  — `run_monitor` still completes cleanly, `_reconcile_alerts` sees no `"flag"`
  verdicts, no macro alerts, no crash.
- A macro check that was previously flagging clears to `"ok"`/`"unknown"` — its open
  `alert_history` row (sentinel ticker) gets auto-acknowledged, same as a per-ticker
  check clearing (already covered by `_reconcile_alerts`'s existing, unmodified logic
  — worth a smoke-test but not a new code path).
- `sync_new_candidates` runs against a `recommendations` table with zero rows (e.g. a
  scratch DB before any `ingest` has run) — returns `[]`, watermark stays at `0`, no
  crash.
- A recommendation's `ticker` needs normalization (e.g. lowercase from a sloppy LLM
  extraction) — `tickers.normalize()` handles this the same way every other entry
  point does; not a new code path but worth one assertion in
  `test_sync_new_candidates_inserts_new_watchlist_row`.
- Two recommendations in the same ingest batch share a ticker (e.g. the same stock
  mentioned in two different report sections) — the second is skipped by the
  "already in watchlist" check after the first is inserted, since both are processed
  in the same `sync_new_candidates` call and the DB write happens per-row before the
  next iteration's dedup check runs.
- `candidate_sync` raises an unexpected exception (e.g. a DB error) — `run_monitor`'s
  wrapping `try/except` (Task 3.1) logs and continues to the rest of the run rather
  than aborting Monitor entirely, mirroring the existing per-row isolation pattern.

---

## VALIDATION COMMANDS

### Level 1: Syntax & Style

```powershell
cd investments/my-trader
uv run ruff check .
uv run mypy mytrader
```

### Level 2: Unit Tests

```powershell
cd investments/my-trader
uv run pytest mytrader/tests -v
```

### Level 3: Integration Tests

```powershell
cd investments/my-trader
uv run pytest mytrader/tests/test_monitor.py mytrader/tests/test_candidate_sync.py mytrader/tests/test_macro_indicators.py -v
```

### Level 4: Manual Validation

See Task 4.5 above (real `sync-candidates` and `monitor` runs against the shared DB,
`^MOVE`/`FRED_API_KEY` live-behavior confirmation, repeat-run watermark/dedup checks).

### Level 5: Additional Validation

N/A for Phase C (no MCP servers or external CLI tools involved beyond `uv`/`pytest`/
`ruff`/`mypy`, all already covered above).

---

## ACCEPTANCE CRITERIA

- [ ] `macro_indicators.py` exists with `check_move_index`, `check_housing_affordability`,
      `check_consumer_sentiment`, `check_recession_signal`, `run_all`
- [ ] Each macro check independently degrades to `verdict="unknown"` on missing data,
      never raises
- [ ] `check_recession_signal`'s detail text includes a bull/bear-steepener
      classification when lookback data is available, and omits it (without erroring)
      when it isn't
- [ ] `candidate_sync.py` exists with `sync_new_candidates(conn) -> list[dict]`
- [ ] `sync_new_candidates` only processes `recommendations` rows with `excluded = 0`
      and `id` greater than the stored watermark
- [ ] `sync_new_candidates` skips any ticker already present in `holdings` or
      `watchlist` under any bucket
- [ ] Synced candidates are inserted with `status="raw"`, `bucket="unassigned"`,
      `source="briefs_finance_ingest"` — never `status="discussed"`
- [ ] `run_monitor()` calls `candidate_sync.sync_new_candidates()` once per run and the
      4 macro checks once per run (not once per holding/watchlist row)
- [ ] Macro check flag-transitions reuse `_reconcile_alerts()` unmodified via the
      `"MACRO"`/`"macro"` sentinel — no new alert-dedup logic written
- [ ] `monitor-report.md` shows a "Macro Indicators" section every run (even when all 4
      are `"unknown"`) and a "New Candidates Synced From Briefs Finance" section every
      run (even when empty)
- [ ] `mytrader.main sync-candidates` CLI subcommand works standalone (without running
      the full `monitor` command)
- [ ] No new scheduled task, Windows Task Scheduler entry, or systemd timer/service is
      created — both features ride on Monitor's existing daily schedule
- [ ] All validation commands (Levels 1-3) pass with zero errors
- [ ] No regressions in Phase A + B's existing ~87 tests

---

## COMPLETION CHECKLIST

- [ ] All tasks completed in order
- [ ] Each task's validation command passed immediately after that task
- [ ] Full `mytrader` test suite passes (Phase A + B + C tests together)
- [ ] `ruff`/`mypy` clean
- [ ] Level 4 manual validation completed, including the `^MOVE`/`FRED_API_KEY`
      live-behavior checks (Task 4.5 steps 3-4) — record findings in `handoff.md`
- [ ] Acceptance criteria all met
- [ ] `investments/my-trader/handoff.md` updated to reflect Phase C completion, noting
      which macro indicators turned out to be live vs. permanently `"unknown"` in this
      environment, and that thresholds are unvalidated defaults pending real-world
      observation
- [ ] `.claude/skills/my-trader/SKILL.md` updated (Task 3.3)

---

## NOTES

**Known limitations accepted for Phase C (not blockers, documented for later):**
- All 4 macro threshold constants (`MOVE_INDEX_FLAG_LEVEL`, `HOUSING_P2I_FLAG_RATIO`,
  `CONSUMER_SENTIMENT_FLAG_LEVEL`, `RECESSION_PROB_FLAG_PCT`) were set during planning
  without live data access — they're reasonable starting points grounded in
  `tool-preplan.md`'s own fact-checked figures, but genuinely unvalidated against a
  real fetch. Matches Phase A's own accepted pattern for `PE_RICH_THRESHOLD` etc.
- The MOVE index's yfinance availability (`^MOVE`) is a real open question this plan
  could not resolve during planning (no live network access). The check degrades
  gracefully either way, but Shaun should know at completion whether this indicator is
  actually live or permanently `"unknown"` in practice.
- `RECPROUSM156N` (already used by briefs-finance as `"recession_prob"`) is the
  Chauvet-Piger smoothed recession-probability series, not necessarily the exact NY Fed
  Estrella-Mishkin term-spread model `tool-preplan.md` names — this plan treats it as
  an acceptable proxy per `tool-preplan.md`'s own instruction to "reconcile with the
  existing yield-curve bullet rather than treating as fully separate," but a future
  session could swap in a more precisely-matching FRED series if one is identified.
- `candidate_sync` hardcodes `asset_type="stock"` since briefs-finance's
  `recommendations` table carries no asset-type field — a rare mislabeled ETF
  recommendation is a cosmetic snapshot-display issue only, not a functional one (no
  check branches on `asset_type`).
- No manual "un-sync" or "reject candidate" action exists — once synced, a `"raw"`
  candidate sits in the watchlist until a human either promotes it (Find's existing
  `add_to_watchlist`, which upserts by the same natural key and would flip it to
  `"discussed"`) or ignores it indefinitely. Not requested by `tool-preplan.md`, not
  needed for Phase C's scope.
- Portfolio concentration's existing currency-naivety and Berkshire-holdings-list gaps
  (both already documented in `SKILL.md`'s "Known Limitations") are unrelated to Phase
  C and untouched by this plan.

**Confidence score: 6/10** for one-pass implementation success. The code-structure risk
is low — this phase is almost entirely new, additive, self-contained modules following
patterns Phase A/B already established, with no risky changes to existing per-ticker
check logic. The real risk is external-data uncertainty this plan's author could not
resolve without live network access during planning: whether `^MOVE` resolves via
yfinance at all, whether the exact FRED series IDs chosen (`MSPUS`,
`MEHOINUSA672N`, `UMCSENT`, `DGS2`, `DGS10`) are correct and current, and whether the
four threshold defaults are remotely sane against real fetched values. None of these
block implementation (every check degrades gracefully to `"unknown"` on bad data), but
they mean Task 4.5's manual validation step is doing more real verification work than
is typical for this codebase's other phases, and the execution agent should expect to
spend real time there rather than treating it as a formality.
