# Feature: my-trader Phase B — Scheduled Monitor

The following plan should be complete, but it's important to validate documentation and
codebase patterns and task sanity before implementing. Pay special attention to naming
of existing utils, types, and models. Import from the right files.

This plan implements **Phase B only**, as scoped in
`investments/my-trader/tool-preplan.md` ("Phase A scope finalized 2026-07-19" section,
Phase B bullet): "Monitor as a scheduled job (heartbeat-style), calling the same
assessment engine built in Phase A; alert thresholds; toast+file output (reuses
`send_toast_notification`)." Phase C (5 macro indicators, Briefs Finance
ingest→candidate data-flow) is explicitly out of scope here and gets its own
`/plan-feature` pass later.

## Feature Description

Phase A (`.agent/plans/my-trader-phase-a-find-engine.md`, committed `fdaa39d`) built the
shared 7-check assessment engine and a conversational, on-demand "Find" — Shaun asks
about a ticker in chat and gets a one-off assessment. It deliberately did not build the
other half of the tool's purpose: unattended, scheduled re-checking of what Shaun
already owns or is watching. Phase B builds that "Monitor" — a scheduled job (like the
existing `heartbeat.py`) that re-runs the same assessment engine against every current
holding and every vetted watchlist candidate, surfaces only genuinely new
material-change alerts (high-bar, quiet-when-nothing-changed), writes them to a
standalone report file, and pings a bare toast notification when something needs a
look.

## User Story

As Shaun (multi-business founder who doesn't want to remember to manually re-check his
portfolio)
I want Monitor to run automatically on a schedule and re-assess everything I hold or am
watching
So that I find out about a dividend cut, a stretched valuation, a leverage flag, or an
ETF expense-ratio change without having to ask Claude about each ticker myself — and I'm
not pinged unless something actually changed

## Problem Statement

Find (Phase A) only runs when Shaun explicitly asks about a ticker in chat. Nothing
currently re-checks his 3 existing holdings (LLY, LYV, V) or his 7 vetted watchlist
candidates (VRTX, PMGOLD core+tactical, BRK-B, HDV, SCHD, ASML) after the fact. A
dividend cut, an earnings-driven valuation shift, or a balance-sheet deterioration on an
already-held position would go unnoticed unless Shaun happened to ask about that exact
ticker again.

## Solution Statement

Add `investments/my-trader/mytrader/monitor.py`: a `run_monitor(conn)` function that
iterates every row in `holdings` plus every `watchlist` row with `status="discussed"`
(never `"raw"` — Monitor doesn't discover new candidates, per the preplan's "explicitly
out of scope" note), calls the existing `engine.run_assessment()` for each, and
reconciles each check's `"flag"` verdicts against a new alert-dedup layer on the
existing (currently-unused) `alert_history` table: a check that newly flags creates one
alert and is reported; a check that keeps flagging on a later run stays quiet (already
open); a check that stops flagging auto-closes its open alert so a future re-flag
raises fresh. Results are written to a new standalone
`investments/my-trader/monitor-report.md` (full overwrite each run, mirrors
`snapshot.py`'s pattern) and, only if there's at least one new alert, a bare toast via
the existing `send_toast_notification` (`.claude/scripts/notifications.py`, already
wired into `heartbeat.py` — reused, not reimplemented). A new CLI subcommand
(`monitor`) and new Windows Task Scheduler + systemd timer/service entries wire it up to
run once daily, unattended, mirroring `heartbeat.py`'s and `memory_reflect.py`'s
existing scheduling patterns exactly.

A small, tightly-scoped addition to `market_data.py` (an opt-in per-run cache) prevents
Monitor from causing an O(n²) yfinance call blowup: `concentration.check()` already
re-fetches every existing holding's data for every ticker it assesses (fine for a
single Find call against 3 holdings; not fine when Monitor loops over ~10 rows,
each triggering a re-fetch of all 3 holdings again). The cache is off by default and
only active inside a context manager Monitor explicitly enters, so Find's and the
existing test suite's behavior is unchanged.

## Feature Metadata

**Feature Type**: New Capability
**Estimated Complexity**: Medium (one new core module + one schema-adjacent DB
extension + one small existing-file addition + CLI/scheduling wiring; no new domain
checks, no new external data sources — Phase B is orchestration over Phase A's engine,
not new assessment logic)
**Primary Systems Affected**: `investments/my-trader/mytrader/` (new `monitor.py`,
extended `db.py`, extended `config.py`, extended `main.py`, extended `market_data.py`),
`scripts/setup_scheduler_windows.ps1`, `scripts/systemd/` (two new files), `scripts/deploy.ps1`,
`.claude/skills/my-trader/SKILL.md`, `.gitignore`
**Dependencies**: None new — reuses `yfinance` (already a my-trader dependency),
`.claude/scripts/notifications.py` (already exists, already used by `heartbeat.py`)

---

## CONTEXT REFERENCES

### Relevant Codebase Files — READ THESE BEFORE IMPLEMENTING

- `investments/my-trader/tool-preplan.md` (lines 105-234, "What we know so far" +
  "Assessment Checks" + "Monitoring Indicators") and lines 469-505 ("Phase A scope
  finalized") — every "Confirmed 2026-07-19" bullet relevant to Monitor is already
  decided, don't re-litigate: trigger model (heartbeat-style scheduled), output channel
  (standalone file only, no daily-log/WhatsApp push), scope of "adjustment" (advisor
  note only, never a trade suggestion), alert philosophy (high-bar, material-changes-only,
  quiet runs stay quiet), Monitor's two jobs (current holdings + vetted watchlist,
  explicitly NOT proactive discovery of new candidates), Monitor alert signal (file +
  reused `send_toast_notification`).
- `.agent/plans/my-trader-phase-a-find-engine.md` (full file, already read this
  session) — the Phase A plan this one continues from; explains the uv workspace
  cross-project import pattern (Task 1.1-1.5, Task 2.4's `_SCRIPTS_DIR` gotcha) that
  this plan's new cross-project import (for `notifications.py`) must mirror exactly.
- `investments/my-trader/mytrader/engine.py` (all, 59 lines) — `run_assessment(ticker,
  conn) -> dict` is the function Monitor calls per row, unmodified. Returns
  `{"ticker", "excluded", "exclusion_reason", "checks": [CheckResult, ...],
  "briefs_finance_score", "data_available"}`.
- `investments/my-trader/mytrader/checks/__init__.py` (all, 14 lines) — `CheckResult`
  dataclass: `name`, `verdict` (`"ok"|"flag"|"info"|"unknown"`), `detail`, `data`. Only
  `verdict == "flag"` should ever create a Monitor alert.
- `investments/my-trader/mytrader/checks/etf_mechanics.py` (all) — its `data` dict
  carries `expense_ratio` when known; Monitor needs this value to call
  `db.touch_checked()` so a *later* run can detect real drift (Phase A could only ever
  capture a baseline — this is the "Monitor running repeatedly" case the Phase A plan's
  Task 2.11 note anticipated).
- `investments/my-trader/mytrader/db.py` (all, 160 lines) — `_now()` helper,
  `get_all_holdings`/`get_all_watchlist` (already exist, use directly), the
  `INSERT OR REPLACE`-by-natural-key upsert pattern (`upsert_holding`,
  `upsert_watchlist_row`) to mirror for the new alert functions and `touch_checked`.
  **`alert_history` table already exists** (created in Phase A, currently unused by any
  code) — schema: `id, ticker, source_table, check_name, severity, message, created_at,
  acknowledged`. Do not alter this schema; Phase B is the first code to actually use it.
- `investments/my-trader/mytrader/market_data.py` (all, 67 lines) — `TickerData`
  dataclass, `fetch_ticker_data(ticker) -> TickerData | None`, `_fetch_one`,
  `fetch_fx_change_pct`. The cache addition (Task 2.1 below) wraps `fetch_ticker_data`
  only; `_fetch_one` and `fetch_fx_change_pct` are untouched.
- `investments/my-trader/mytrader/checks/concentration.py` (all, 72 lines, especially
  lines 36-44) — the exact loop (`for row in holdings: ... market_data.fetch_ticker_data(row["ticker"])`)
  that makes Monitor's per-run cache worth adding — without it, an N-row Monitor run
  costs N × (1 + len(holdings)) yfinance calls instead of just the number of unique
  tickers touched.
- `investments/my-trader/mytrader/snapshot.py` (all, 87 lines) — the exact "gather from
  DB, render Markdown, full overwrite, `Last auto-generated: <date>` footer" pattern to
  mirror for `monitor.render_report()` / `write_report()`. Monitor also calls
  `snapshot.regenerate_all(conn)` at the end of its run (holdings/watchlist
  `last_checked_at` changed, worth a fresh snapshot even though the visible
  `holdings.md`/`potential-holdings.md` columns don't currently show that field).
- `investments/my-trader/mytrader/main.py` (all, 141 lines) — `_open_conn()` helper
  (reuse as-is), `cmd_*`/`argparse` subparser dispatch pattern (lines 39-137) to mirror
  for the new `monitor` subcommand. Lazy imports inside each `cmd_*` — keep this
  convention for `cmd_monitor` too.
- `investments/my-trader/mytrader/config.py` (all, 29 lines) — `MY_TRADER_DIR`,
  `HOLDINGS_MD_PATH`, `WATCHLIST_MD_PATH` pattern to mirror for the new
  `MONITOR_REPORT_PATH`.
- `investments/my-trader/mytrader/tests/conftest.py` (all, 26 lines) — `db_conn`
  fixture (tmp_path-backed, both briefs-finance + mytrader tables initialised); every
  new test file uses this, never the real shared DB.
- `investments/my-trader/mytrader/tests/test_engine.py` (all, 56 lines) — the
  `monkeypatch.setattr("mytrader.market_data.fetch_ticker_data", ...)` mocking pattern;
  `test_monitor.py` mocks `engine.run_assessment` at a higher level instead (Monitor
  doesn't need to re-mock yfinance, it needs to control what `run_assessment` returns
  per ticker to drive the alert-reconciliation logic deterministically).
- `.claude/scripts/heartbeat.py` (lines 1-14 docstring, 519-545 `run_heartbeat`'s
  active-hours + interval gate, 824-834 the `HEARTBEAT_OK` vs. alert branch that calls
  `send_toast_notification`) — the "scheduled job, gate if needed, call
  `send_toast_notification` only when there's something to say" shape Monitor mirrors
  at a smaller scale. Monitor does **not** need heartbeat's active-hours gate or
  interval gate — it's invoked once daily by the OS scheduler directly (see Task 4.1),
  not on a tight poll loop — but it does mirror the "only notify if something changed"
  branching.
- `.claude/scripts/notifications.py` (all, 46 lines) — `send_toast_notification(title,
  message, duration=5)`. Import this cross-project exactly the way `mytrader/db.py`
  imports `scripts.db` (see Task 2.4's `_SCRIPTS_DIR` gotcha in the Phase A plan) —
  same path depth math applies (`mytrader/monitor.py` → `mytrader` → `my-trader` →
  `investments` → repo root → `.claude/scripts`), so `parent.parent.parent.parent` from
  `monitor.py`'s own file is correct.
- `scripts/setup_scheduler_windows.ps1` (all, 53 lines) — `Register-ScheduledTask`
  pattern (lines 20-27, the daily `memory_reflect.py` task, is the closest match —
  once-daily, not repeating, unlike heartbeat's 30-min repetition).
- `scripts/systemd/second-brain-reflect.timer` + `.service` (both, already read) — the
  exact once-daily systemd pattern to mirror, **including the `OnCalendar=*-*-* HH:MM:00
  UTC` convention** (reflect's 08:00 AEST is expressed as `22:00:00 UTC` the prior day —
  no DST compensation, matches this repo's existing simplification, don't try to fix
  that here).
- `scripts/deploy.ps1` (all, 20 lines) — stops/restarts `second-brain-heartbeat.timer`
  around the VPS git pull; Task 4.3 below extends this to also stop/restart the new
  Monitor timer, same shape.
- `.gitignore` (all, 45 lines, especially line 14
  `.claude/scripts/heartbeat_runs.log`) — the exact per-service runs-log gitignore
  convention to mirror for the new `investments/my-trader/monitor_runs.log`.
- `.claude/skills/my-trader/SKILL.md` (all, 100 lines, especially the "Known
  Limitations (Phase A)" section which currently says "Monitor (scheduled daily
  re-check of all holdings/watchlist) is Phase B, not yet built") — update this file
  once Monitor exists (Task 4.4).

### New Files to Create

- `investments/my-trader/mytrader/monitor.py` — `run_monitor(conn) -> dict`,
  `render_report(result) -> str`, `write_report(result) -> None`,
  `maybe_notify(result) -> None`
- `investments/my-trader/mytrader/tests/test_monitor.py`
- `investments/my-trader/mytrader/tests/test_market_data.py` (Phase A never added one —
  Phase B's cache addition is the first behavior in `market_data.py` worth unit-testing
  directly)
- `scripts/systemd/second-brain-mytrader-monitor.timer`
- `scripts/systemd/second-brain-mytrader-monitor.service`

### Files to Modify

- `investments/my-trader/mytrader/db.py` — add `get_open_alert`, `insert_alert`,
  `acknowledge_alert`, `get_open_alerts`, `touch_checked`
- `investments/my-trader/mytrader/config.py` — add `MONITOR_REPORT_PATH`
- `investments/my-trader/mytrader/market_data.py` — add `cached_session()` context
  manager + module-level opt-in cache inside `fetch_ticker_data`
- `investments/my-trader/mytrader/main.py` — add `monitor` subcommand + `cmd_monitor`
- `scripts/setup_scheduler_windows.ps1` — add `SecondBrain-MyTraderMonitor` task
- `scripts/deploy.ps1` — stop/restart the new timer alongside the heartbeat timer
- `.gitignore` — add `investments/my-trader/monitor_runs.log`
- `.claude/skills/my-trader/SKILL.md` — document the `monitor` command, remove the
  "not yet built" limitation note, add a "Monitor" section

### Relevant Documentation

None new — Phase B introduces no new external libraries or APIs. `yfinance` and the
Windows Task Scheduler / systemd patterns are already established and documented in the
Phase A plan and the existing scheduler files respectively.

### Patterns to Follow

**Naming Conventions:**
- `snake_case` throughout, matching all of Phase A.
- New DB functions named as verbs on the natural-key/entity, matching existing
  `upsert_holding`/`delete_holding_if_zero` style: `get_open_alert`, `insert_alert`,
  `acknowledge_alert`, `get_open_alerts`, `touch_checked`.

**Error Handling:**
- `market_data.fetch_ticker_data` already wraps yfinance calls in broad
  `try/except Exception: return None` — Monitor's per-row loop does not need its own
  try/except around `engine.run_assessment()` for *data* failures (checks already
  degrade to `verdict="unknown"` on missing data, per Phase A's contract). It should
  still not let one row's *unexpected* exception (e.g. a DB error) kill the whole run —
  wrap each row's processing in `run_monitor`'s loop in a narrow
  `try/except Exception` that logs (`print`) and continues to the next row, mirroring
  `heartbeat.py`'s `_gather_emails`/`_gather_calendar` per-integration isolation
  (lines 160-210).

**DB Pattern:**
- `alert_history` dedup key for "is this already open" is `(ticker, source_table,
  check_name)` filtered to `acknowledged = 0`, **not** an exact `message` match — the
  message text can drift run-to-run (e.g. a PE ratio nudging from 35.2 to 35.4) without
  that being a *new* material event; only a flag→ok→flag transition should raise a new
  alert. This is the core design decision this plan makes that isn't explicitly spelled
  out in `tool-preplan.md` (which left "exact numeric thresholds... implementation
  detail" but didn't address dedup granularity) — document this choice in Task 2.2's
  `GOTCHA` and in the module docstring, since it's the kind of thing a future session
  could second-guess without the reasoning in front of it.
- Auto-acknowledge (not delete) an alert once its check stops flagging — preserves
  history in `alert_history` for later reference, and re-flagging after that creates a
  fresh row rather than reviving the old one. No manual "acknowledge" CLI action exists
  in Phase B (not requested by the preplan) — acknowledgment is entirely
  system-driven based on verdict transitions.

**CLI Pattern:**
- `argparse` subparser + `cmd_monitor(args)` + lazy imports inside the function, exactly
  matching `main.py`'s existing 5 subcommands (Task reference: `main.py:39-91`,
  `main.py:93-137` for the dispatch table and parser registration shape).

**Testing Pattern:**
- `tmp_path`-backed SQLite via the existing `db_conn` fixture — never the real shared
  DB (unchanged from Phase A).
- `test_monitor.py` mocks at the `engine.run_assessment` level
  (`monkeypatch.setattr("mytrader.monitor.engine.run_assessment", lambda ticker, conn: {...})`)
  rather than mocking yfinance — Monitor's own logic (alert reconciliation, report
  rendering, notify-or-not) is what needs coverage here; the 7 checks and yfinance
  fetching are already covered by Phase A's test suite and don't need re-testing
  through Monitor.
- `test_market_data.py` mocks `market_data._fetch_one` (patch the private helper
  directly, since that's the thing `cached_session()` is meant to reduce calls to) and
  asserts call counts with/without the context manager active.
- `maybe_notify`'s cross-project `notifications` import is a deferred `import` inside
  the function body (same as `mytrader/db.py`'s pattern) — to mock it in a test, use
  `monkeypatch.setitem(sys.modules, "notifications", <fake module with a
  send_toast_notification stub>)` *before* calling `maybe_notify`, since `sys.modules`
  caching means the deferred import will resolve to the stub instead of re-inserting
  the real `.claude/scripts` path and importing the real module. Document this as a
  test-writing gotcha in Task 3.4 — it's a slightly unusual mocking shape and worth
  getting right the first time rather than debugging an import-order surprise.

---

## IMPLEMENTATION PLAN

### Phase 1: Foundation (DB alert layer + cache + config)

Get the pieces Monitor depends on working and unit-tested in isolation before writing
the orchestration logic that ties them together.

**Tasks:**
- Add `MONITOR_REPORT_PATH` to `config.py`
- Add the 5 new alert/touch functions to `db.py`, unit-tested
- Add `cached_session()` to `market_data.py`, unit-tested

### Phase 2: Core Implementation (Monitor orchestration)

**Tasks:**
- `monitor.py`: `run_monitor()`, `_process_row()`, `_reconcile_alerts()`
- `monitor.py`: `render_report()`, `write_report()`, `maybe_notify()`

### Phase 3: Integration (CLI + skill doc)

**Tasks:**
- `main.py` `monitor` subcommand
- Update `.claude/skills/my-trader/SKILL.md`

### Phase 4: Scheduling & Deployment

**Tasks:**
- Windows Task Scheduler entry
- systemd timer + service
- `deploy.ps1` extension
- `.gitignore` extension

### Phase 5: Testing & Validation

**Tasks:**
- Unit tests for every new function
- Manual validation: real `monitor` run against a scratch/tmp DB, then (with Shaun's
  go-ahead) against the real shared DB

---

## STEP-BY-STEP TASKS

Execute in order. Each task is atomic and independently testable.

### Task 1.1: UPDATE `investments/my-trader/mytrader/config.py`

- **IMPLEMENT**: Add below `WATCHLIST_MD_PATH`:
  ```python
  MONITOR_REPORT_PATH = MY_TRADER_DIR / "monitor-report.md"
  ```
- **PATTERN**: `config.py:10-11` (`HOLDINGS_MD_PATH`, `WATCHLIST_MD_PATH`).
- **VALIDATE**: `cd investments/my-trader; uv run python -c "from mytrader.config import MONITOR_REPORT_PATH; print(MONITOR_REPORT_PATH)"`

### Task 1.2: UPDATE `investments/my-trader/mytrader/db.py`

- **IMPLEMENT**: Add after the existing `upsert_watchlist_row` function:
  ```python
  def get_open_alert(
      conn: sqlite3.Connection, ticker: str, source_table: str, check_name: str
  ) -> sqlite3.Row | None:
      """Most recent unacknowledged alert for this (ticker, source_table, check_name),
      or None. Dedup key deliberately excludes `message` — a check's message text can
      drift run-to-run (e.g. a PE ratio nudging) without that being a new material
      event; only a flag->ok->flag transition should raise a fresh alert."""
      return conn.execute(
          """SELECT * FROM alert_history
             WHERE ticker = ? AND source_table = ? AND check_name = ? AND acknowledged = 0
             ORDER BY created_at DESC LIMIT 1""",
          (ticker, source_table, check_name),
      ).fetchone()


  def insert_alert(
      conn: sqlite3.Connection, *, ticker: str, source_table: str,
      check_name: str, severity: str, message: str,
  ) -> None:
      now = _now()
      with conn:
          conn.execute(
              """INSERT INTO alert_history
                 (ticker, source_table, check_name, severity, message, created_at, acknowledged)
                 VALUES (?, ?, ?, ?, ?, ?, 0)""",
              (ticker, source_table, check_name, severity, message, now),
          )


  def acknowledge_alert(conn: sqlite3.Connection, alert_id: int) -> None:
      with conn:
          conn.execute("UPDATE alert_history SET acknowledged = 1 WHERE id = ?", (alert_id,))


  def get_open_alerts(conn: sqlite3.Connection) -> list[sqlite3.Row]:
      return conn.execute(
          "SELECT * FROM alert_history WHERE acknowledged = 0 ORDER BY created_at DESC"
      ).fetchall()


  def touch_checked(
      conn: sqlite3.Connection, table: str, ticker: str, bucket: str,
      last_expense_ratio: float | None,
  ) -> None:
      """Update last_checked_at (and last_expense_ratio if the check produced one) for
      a holdings/watchlist row. `table` must be "holdings" or "watchlist" — always a
      hardcoded literal from monitor.py's own call sites, never external input."""
      assert table in ("holdings", "watchlist"), f"invalid table: {table!r}"
      now = _now()
      with conn:
          if last_expense_ratio is not None:
              conn.execute(
                  f"UPDATE {table} SET last_checked_at = ?, last_expense_ratio = ? "
                  f"WHERE ticker = ? AND bucket = ?",
                  (now, last_expense_ratio, ticker, bucket),
              )
          else:
              conn.execute(
                  f"UPDATE {table} SET last_checked_at = ? WHERE ticker = ? AND bucket = ?",
                  (now, ticker, bucket),
              )
  ```
- **PATTERN**: `db.py`'s existing upsert functions (`upsert_holding` lines 87-118) for
  the `with conn:` transactional-write shape; `get_holding_row`/`get_watchlist_row`
  (lines 59-76) for the parameterized-query read shape.
- **GOTCHA**: The `alert_history` table (schema at `db.py:46-55`) already exists from
  Phase A — do not re-create or alter it, `init_mytrader_tables` already handles it via
  `CREATE TABLE IF NOT EXISTS`.
- **GOTCHA**: `touch_checked`'s f-string table name is intentionally not
  parameterized (SQLite doesn't allow parameterizing identifiers) — the `assert`
  is the safety boundary. Never call this with a `table` value that traces back to
  user/external input.
- **VALIDATE**: `pytest mytrader/tests/test_db.py -v` (extend the existing file with new
  test functions for these 5 — see Task 5.1).

### Task 1.3: UPDATE `investments/my-trader/mytrader/market_data.py`

- **IMPLEMENT**: Add near the top (after the `TickerData` dataclass, before
  `_looks_valid`):
  ```python
  from contextlib import contextmanager

  _cache: dict[str, TickerData | None] | None = None


  @contextmanager
  def cached_session():
      """Enable an in-memory per-run cache for fetch_ticker_data. Off by default (module
      global stays None) — Find and the existing test suite are unaffected unless this
      context is explicitly entered. Monitor uses this to avoid an O(n^2) yfinance call
      blowup: concentration.check() re-fetches every existing holding for every ticker
      it assesses, and Monitor calls run_assessment() once per holding+watchlist row."""
      global _cache
      _cache = {}
      try:
          yield
      finally:
          _cache = None
  ```
  Then change `fetch_ticker_data` to:
  ```python
  def fetch_ticker_data(ticker: str) -> TickerData | None:
      """Fetch yfinance data for a normalized ticker. Tries .AX fallback if the
      primary lookup returns no info. Returns None if both fail. Cached for the
      duration of a cached_session() context, if one is active."""
      normalized = tickers.normalize(ticker)
      if _cache is not None and normalized in _cache:
          return _cache[normalized]
      data = _fetch_one(normalized)
      if data is None:
          data = _fetch_one(tickers.asx_variant(ticker))
      if _cache is not None:
          _cache[normalized] = data
      return data
  ```
- **PATTERN**: N/A — this is new behavior, not mirrored from elsewhere in the codebase.
  Keep the diff minimal: only `fetch_ticker_data`'s body changes, `_fetch_one` and
  `fetch_fx_change_pct` are untouched.
- **GOTCHA**: Existing tests that do
  `monkeypatch.setattr("mytrader.market_data.fetch_ticker_data", lambda ticker: ...)`
  (e.g. `test_engine.py`, `test_snapshot.py`, `test_find.py`) replace the whole function
  object — the cache logic inside the real `fetch_ticker_data` never runs for those
  tests, so this change cannot break them. Confirm this by re-running the full Phase A
  suite after this task (see Task 5.1's validation).
- **VALIDATE**: `pytest mytrader/tests/test_market_data.py -v` (new file, Task 5.2) plus
  `pytest mytrader/tests -v` (full suite, confirm zero regressions).

---

### Task 2.1: CREATE `investments/my-trader/mytrader/monitor.py`

- **IMPLEMENT**: Full module:
  ```python
  """Monitor — scheduled re-check of all holdings + vetted watchlist candidates.

  Runs Find's same assessment engine against every current holding and every watchlist
  row marked status="discussed" (never "raw" — Monitor doesn't proactively discover new
  candidates, per tool-preplan.md's "Monitor's scope" decision). High-bar alerting: a
  check flipping to verdict="flag" for the first time (no existing open alert of that
  check_name for that ticker) creates a new alert and is surfaced; repeat runs of an
  already-flagged condition stay quiet. When a previously flagged check stops flagging,
  its open alert is auto-acknowledged so a future re-flag raises a fresh one. Output is
  a standalone file only (monitor-report.md) plus a bare toast notification when there's
  at least one new alert — no Second Brain daily-log or WhatsApp push, per
  tool-preplan.md's "output channel" decision.
  """

  from __future__ import annotations

  import sqlite3
  from datetime import date
  from typing import Any

  from . import config, db, engine, market_data, snapshot

  SEVERITY = "flag"  # Phase B keeps severity simple: every alert comes from a
                      # "flag" verdict. Refining severity tiers is a later tuning task.


  def _reconcile_alerts(
      ticker: str, source_table: str, checks: list, conn: sqlite3.Connection
  ) -> list[dict[str, Any]]:
      new_alerts: list[dict[str, Any]] = []
      for check in checks:
          existing = db.get_open_alert(conn, ticker, source_table, check.name)
          if check.verdict == "flag":
              if existing is None:
                  db.insert_alert(
                      conn, ticker=ticker, source_table=source_table,
                      check_name=check.name, severity=SEVERITY, message=check.detail,
                  )
                  new_alerts.append({
                      "ticker": ticker, "source_table": source_table,
                      "check_name": check.name, "message": check.detail,
                  })
          elif existing is not None:
              db.acknowledge_alert(conn, existing["id"])
      return new_alerts


  def _process_row(
      row: sqlite3.Row, source_table: str, conn: sqlite3.Connection
  ) -> list[dict[str, Any]]:
      ticker = row["ticker"]
      bucket = row["bucket"]
      result = engine.run_assessment(ticker, conn)
      new_alerts = _reconcile_alerts(ticker, source_table, result["checks"], conn)

      etf_check = next((c for c in result["checks"] if c.name == "etf_mechanics"), None)
      expense_ratio = etf_check.data.get("expense_ratio") if etf_check else None
      db.touch_checked(conn, source_table, ticker, bucket, expense_ratio)

      return new_alerts


  def run_monitor(conn: sqlite3.Connection) -> dict[str, Any]:
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

      snapshot.regenerate_all(conn)

      return {
          "checked_holdings": len(holdings),
          "checked_watchlist": len(watchlist),
          "new_alerts": new_alerts,
          "open_alerts": [dict(a) for a in db.get_open_alerts(conn)],
      }


  def render_report(result: dict[str, Any]) -> str:
      lines = [
          "# my-trader Monitor Report",
          "",
          "Auto-generated by Monitor — overwritten every run. Advisor notes only; "
          "no trade action is ever suggested here (see SOUL.md).",
          "",
          f"## Run: {date.today().isoformat()}",
          f"Checked {result['checked_holdings']} holding(s), "
          f"{result['checked_watchlist']} watchlist candidate(s).",
          "",
          "### New Alerts This Run",
      ]
      if result["new_alerts"]:
          for a in result["new_alerts"]:
              lines.append(f"- **{a['ticker']}** ({a['source_table']}) — {a['check_name']}: {a['message']}")
      else:
          lines.append("No new material changes.")
      lines += ["", "### All Open Alerts"]
      if result["open_alerts"]:
          for a in result["open_alerts"]:
              lines.append(
                  f"- **{a['ticker']}** ({a['source_table']}) — {a['check_name']}: "
                  f"{a['message']} (first flagged {a['created_at'][:10]})"
              )
      else:
          lines.append("None.")
      lines += ["", f"Last auto-generated: {date.today().isoformat()}."]
      return "\n".join(lines) + "\n"


  def write_report(result: dict[str, Any]) -> None:
      config.MONITOR_REPORT_PATH.write_text(render_report(result), encoding="utf-8")


  def maybe_notify(result: dict[str, Any]) -> None:
      if not result["new_alerts"]:
          return
      import sys
      from pathlib import Path

      _scripts_dir = Path(__file__).resolve().parent.parent.parent.parent / ".claude" / "scripts"
      sys.path.insert(0, str(_scripts_dir))
      from notifications import send_toast_notification

      n = len(result["new_alerts"])
      send_toast_notification(
          "my-trader Monitor",
          f"{n} item(s) flagged — check investments/my-trader/monitor-report.md",
      )
  ```
- **IMPORTS**: `from . import config, db, engine, market_data, snapshot` — all relative,
  matching Phase A's convention (`engine.py:10` does the same for `db, market_data,
  tickers`).
- **PATTERN**: `snapshot.py`'s full-overwrite-Markdown-with-footer shape for
  `render_report`/`write_report`; `mytrader/db.py`'s `_SCRIPTS_DIR` cross-project import
  gotcha (Phase A plan Task 2.4) for `maybe_notify`'s deferred `notifications` import.
- **GOTCHA**: `_process_row`'s per-row `try/except` in `run_monitor` must stay narrow —
  wrap only the call to `_process_row`, not the whole loop, so one bad ticker doesn't
  skip the rest. This mirrors `heartbeat.py`'s `_gather_emails`/`_gather_calendar`
  per-integration isolation (each integration's `try/except` is independent).
  **Note**: `engine.run_assessment()` and the checks it calls already degrade
  gracefully on missing *market data* (return `verdict="unknown"`, never raise) — this
  try/except is a defense-in-depth guard against *unexpected* failures (e.g. a DB
  error), not the primary way missing yfinance data gets handled.
- **VALIDATE**: `pytest mytrader/tests/test_monitor.py -v` (Task 5.3)

---

### Task 3.1: UPDATE `investments/my-trader/mytrader/main.py`

- **IMPLEMENT**: Add a `cmd_monitor` function (near the other `cmd_*` functions):
  ```python
  def cmd_monitor(args) -> None:
      from .monitor import maybe_notify, run_monitor, write_report

      conn = _open_conn()
      result = run_monitor(conn)
      conn.close()
      write_report(result)
      maybe_notify(result)
      print(
          f"Monitor complete: {len(result['new_alerts'])} new alert(s), "
          f"{len(result['open_alerts'])} open. See investments/my-trader/monitor-report.md"
      )
  ```
  Register the subparser (alongside the existing `subparsers.add_parser("snapshot", ...)`
  / `subparsers.add_parser("seed", ...)` lines):
  ```python
  subparsers.add_parser("monitor", help="Scheduled re-check of all holdings + vetted watchlist")
  ```
  Add `"monitor": cmd_monitor` to the `dispatch` dict.
- **PATTERN**: `main.py:75-90` (`cmd_snapshot`, `cmd_seed`) for the exact
  open-conn/call/close/print shape; `main.py:119-120` for subparser registration.
- **VALIDATE**: `cd investments/my-trader; uv run python -m mytrader.main --help` lists
  `monitor` alongside the existing 6 subcommands.

### Task 3.2: UPDATE `.claude/skills/my-trader/SKILL.md`

- **IMPLEMENT**: Add to the "Quick Reference" command block:
  ```powershell
  # Scheduled re-check of all holdings + vetted watchlist (also runs automatically —
  # see scripts/setup_scheduler_windows.ps1 / scripts/systemd/second-brain-mytrader-monitor.timer)
  uv run --directory investments/my-trader python -m mytrader.main monitor
  ```
  Add a new "## Monitor" section (after "## Two Distinct Find Actions") summarizing:
  runs daily on schedule, checks holdings + watchlist rows with `status="discussed"`,
  high-bar alerting (only new flag→ok→flag transitions notify), output at
  `investments/my-trader/monitor-report.md`, toast-only when there's a new alert, never
  suggests a trade action.
  Remove the "Monitor (scheduled daily re-check of all holdings/watchlist) is Phase B,
  not yet built" line from "Known Limitations (Phase A)" and replace with a note that
  Phase B is now built, Phase C (macro indicators, Briefs Finance ingest integration) is
  still pending.
- **PATTERN**: `SKILL.md`'s existing section structure (frontmatter unchanged — trigger
  phrases don't need updating since Monitor is schedule-driven, not conversational).
- **VALIDATE**: Manual read-through — no command executes here.

---

### Task 4.1: UPDATE `scripts/setup_scheduler_windows.ps1`

- **IMPLEMENT**: Add after the existing `SecondBrain-Reflection` block:
  ```powershell
  # my-trader Monitor — daily at 07:30 (after US markets close, before Shaun's day starts)
  $mtPython = Join-Path $ProjectPath "investments\.venv\Scripts\python.exe"
  $mtAction = New-ScheduledTaskAction -Execute $mtPython `
      -Argument "-m mytrader.main monitor" `
      -WorkingDirectory (Join-Path $ProjectPath "investments\my-trader")
  $mtTrigger = New-ScheduledTaskTrigger -Daily -At "07:30"
  Register-ScheduledTask -TaskName "SecondBrain-MyTraderMonitor" -Action $mtAction `
      -Trigger $mtTrigger -RunLevel Limited -Force
  Write-Output "Registered: SecondBrain-MyTraderMonitor"
  ```
- **PATTERN**: `setup_scheduler_windows.ps1:20-27` (`SecondBrain-Reflection`, the
  closest existing analog — once-daily, not repeating like Heartbeat/VaultSync).
- **GOTCHA**: my-trader's Python lives at `investments\.venv\Scripts\python.exe` (the
  uv workspace root is `investments/`, confirmed to exist — **different venv** from
  `.claude\scripts\.venv\` that the other three tasks use). `-WorkingDirectory` must be
  `investments\my-trader` (not the repo root) so `-m mytrader.main` resolves the same
  way it does under `uv run` in Task 1.5's original smoke test.
- **VALIDATE**: `Test-Path "$ProjectPath\investments\.venv\Scripts\python.exe"` returns
  `True` before registering (sanity check the venv exists — it does, confirmed during
  planning). After running the updated script as Administrator:
  `Get-ScheduledTask -TaskName "SecondBrain-MyTraderMonitor"` shows the task registered.

### Task 4.2: CREATE `scripts/systemd/second-brain-mytrader-monitor.timer`

- **IMPLEMENT**:
  ```ini
  [Unit]
  Description=my-trader Monitor Timer
  Requires=second-brain-mytrader-monitor.service

  [Timer]
  OnCalendar=*-*-* 21:30:00 UTC
  Persistent=true

  [Install]
  WantedBy=timers.target
  ```
- **PATTERN**: `scripts/systemd/second-brain-reflect.timer` (identical shape).
- **GOTCHA**: `21:30:00 UTC` = 07:30 AEST (UTC+10) — matches Task 4.1's Windows trigger
  time. No DST compensation, same simplification the existing `reflect.timer` already
  makes (AEDT is UTC+11 part of the year) — not a new problem introduced here.
- **VALIDATE**: N/A (deployed via `scp`/git pull to VPS, activated in Task 4.2's
  companion service file's manual validation step, Level 4).

### Task 4.3: CREATE `scripts/systemd/second-brain-mytrader-monitor.service`

- **IMPLEMENT**:
  ```ini
  [Unit]
  Description=my-trader Monitor
  After=network.target

  [Service]
  Type=oneshot
  User=secondbrain
  WorkingDirectory=/home/secondbrain/second-brain/investments/my-trader
  ExecStart=/home/secondbrain/second-brain/investments/.venv/bin/python -m mytrader.main monitor
  StandardOutput=append:/home/secondbrain/second-brain/investments/my-trader/monitor_runs.log
  StandardError=append:/home/secondbrain/second-brain/investments/my-trader/monitor_runs.log
  ```
- **PATTERN**: `scripts/systemd/second-brain-reflect.service` (identical shape, no
  `EnvironmentFile`/`AGENT_INVOKED_BY` needed — Monitor doesn't call an LLM or touch
  `soul-protect.py`-guarded files, unlike heartbeat/reflection).
- **GOTCHA**: `WorkingDirectory` is `investments/my-trader` (not the repo root, unlike
  the heartbeat/reflect services) — matches the Windows task's `-WorkingDirectory` in
  Task 4.1, for the same `-m mytrader.main` resolution reason.
- **VALIDATE**: On the VPS (Level 4, after `deploy.ps1` has pulled these files):
  `sudo systemctl daemon-reload && sudo systemctl enable --now second-brain-mytrader-monitor.timer`,
  then `sudo systemctl status second-brain-mytrader-monitor.timer` shows it active/waiting.

### Task 4.4: UPDATE `scripts/deploy.ps1`

- **IMPLEMENT**: Add stop/restart calls for the new timer alongside the existing
  heartbeat timer calls:
  ```powershell
  Write-Host "Stopping heartbeat timer..."
  ssh $VPS "sudo systemctl stop second-brain-heartbeat.timer"
  ssh $VPS "sudo systemctl stop second-brain-mytrader-monitor.timer 2>/dev/null || true"
  ```
  and
  ```powershell
  Write-Host "Restarting heartbeat timer..."
  ssh $VPS "sudo systemctl start second-brain-heartbeat.timer"
  ssh $VPS "sudo systemctl start second-brain-mytrader-monitor.timer 2>/dev/null || true"
  ```
- **PATTERN**: `deploy.ps1:10-11, 16-17` (existing heartbeat stop/start calls).
- **GOTCHA**: `2>/dev/null || true` guards the first deploy after this change, before
  the timer has been enabled on the VPS yet (Task 4.3's manual `systemctl enable` step)
  — without it, `deploy.ps1` would fail on a VPS that doesn't have the unit installed
  yet. Once Task 4.3's Level 4 step has run for real, this is a no-op safety net, not a
  permanent workaround.
- **VALIDATE**: Manual read-through; exercised for real on the next actual deploy
  (Level 4).

### Task 4.5: UPDATE `.gitignore`

- **IMPLEMENT**: Add near the existing `.claude/scripts/heartbeat_runs.log` line:
  ```
  investments/my-trader/monitor_runs.log
  ```
- **PATTERN**: `.gitignore:14-16` (the three existing `*_runs.log` entries).
- **VALIDATE**: `git check-ignore investments/my-trader/monitor_runs.log` (after Task
  4.3's VPS log file would exist) returns the path, confirming it's ignored. Locally,
  `git status` should not show this file if it happens to exist from a manual test run
  (Task 5.4).

---

### Task 5.1: EXTEND `investments/my-trader/mytrader/tests/test_db.py`

- **IMPLEMENT**: Add test functions (using the existing `db_conn` fixture):
  - `test_get_open_alert_returns_none_when_no_alert`
  - `test_insert_alert_then_get_open_alert_finds_it`
  - `test_acknowledge_alert_removes_it_from_open_query` — insert, acknowledge, assert
    `get_open_alert` now returns `None` and `get_open_alerts()` no longer includes it
  - `test_touch_checked_updates_holdings_row` — seed a holding via `db.upsert_holding`,
    call `touch_checked(conn, "holdings", ticker, bucket, 0.05)`, assert
    `get_holding_row` shows updated `last_checked_at` and `last_expense_ratio`
  - `test_touch_checked_updates_watchlist_row` — same for `watchlist`
  - `test_touch_checked_preserves_expense_ratio_when_none_passed` — call with
    `last_expense_ratio=None`, assert the prior value (if any) is untouched, only
    `last_checked_at` changes
- **VALIDATE**: `pytest mytrader/tests/test_db.py -v`

### Task 5.2: CREATE `investments/my-trader/mytrader/tests/test_market_data.py`

- **IMPLEMENT**:
  - `test_fetch_ticker_data_without_session_calls_fetch_one_every_time` — monkeypatch
    `mytrader.market_data._fetch_one` with a call-counting stub, call
    `fetch_ticker_data("VRTX")` twice outside any `cached_session()`, assert the stub
    was called twice (2 calls per invocation since `_fetch_one` is also tried for the
    `.AX` fallback if the first returns `None` — configure the stub to return a valid
    `TickerData` on first call so only 1 call happens per `fetch_ticker_data` call, 2
    total).
  - `test_fetch_ticker_data_within_session_caches` — same stub, wrap two
    `fetch_ticker_data("VRTX")` calls in `with market_data.cached_session():`, assert
    the stub was called exactly once total.
  - `test_cached_session_resets_after_context_exits` — call once inside a session, exit,
    call again outside — assert the second call triggers a fresh `_fetch_one` call (cache
    doesn't leak across sessions).
  - `test_cache_keyed_by_normalized_ticker` — call `fetch_ticker_data("brk.b")` then
    `fetch_ticker_data("BRK-B")` inside one session, assert only 1 underlying call (both
    normalize to the same cache key).
- **PATTERN**: `mytrader/tests/test_engine.py`'s `monkeypatch.setattr` shape, applied to
  `_fetch_one` instead of `fetch_ticker_data` this time (need to observe call counts on
  the function the cache wraps, not the cache-wrapped function itself).
- **VALIDATE**: `pytest mytrader/tests/test_market_data.py -v`

### Task 5.3: CREATE `investments/my-trader/mytrader/tests/test_monitor.py`

- **IMPLEMENT**:
  - A small local helper to build a fake `engine.run_assessment` return dict with a
    controllable list of `CheckResult`s (import `CheckResult` from `mytrader.checks`).
  - `test_run_monitor_creates_new_alert_for_first_flag` — seed one holding, monkeypatch
    `mytrader.monitor.engine.run_assessment` to return one `flag` check, run
    `run_monitor(conn)`, assert `result["new_alerts"]` has 1 entry and
    `db.get_open_alerts(conn)` has 1 row.
  - `test_run_monitor_stays_quiet_on_repeat_flag` — run `run_monitor` twice with the
    same flag-returning mock, assert the second run's `result["new_alerts"]` is empty
    (already open) but `result["open_alerts"]` still has exactly 1 entry (not
    duplicated).
  - `test_run_monitor_acknowledges_when_flag_clears` — first run flags, second run's
    mock returns `verdict="ok"` for that check, assert `get_open_alerts(conn)` is now
    empty after the second run.
  - `test_run_monitor_reflags_after_acknowledge` — three runs: flag, then clear
    (acknowledges), then flag again — assert the third run's `new_alerts` has 1 entry
    (a *new* alert, not a revival of the acknowledged one) and there are 2 total rows in
    `alert_history` for that ticker/check (one acknowledged, one open).
  - `test_run_monitor_only_checks_discussed_watchlist_rows` — seed one `status="raw"`
    watchlist row and one `status="discussed"` row, assert `result["checked_watchlist"]
    == 1`.
  - `test_run_monitor_calls_touch_checked` — assert `last_checked_at` is non-null on the
    holding row after `run_monitor` runs (via `db.get_holding_row`).
  - `test_render_report_lists_new_and_open_alerts` — construct a `result` dict by hand,
    assert `render_report()`'s output contains expected ticker/check_name/message
    substrings and the "No new material changes." / "None." fallback text when lists are
    empty.
  - `test_write_report_writes_to_configured_path` — monkeypatch
    `mytrader.monitor.config.MONITOR_REPORT_PATH` to a `tmp_path` file, call
    `write_report(result)`, assert the file exists and its content matches
    `render_report(result)`.
  - `test_maybe_notify_skips_when_no_new_alerts` — monkeypatch
    `sys.modules["notifications"]` to a fake module with a call-recording
    `send_toast_notification`, call `maybe_notify({"new_alerts": []})`, assert the fake
    was never called.
  - `test_maybe_notify_calls_toast_when_new_alerts_present` — same fake module setup,
    call with a non-empty `new_alerts` list, assert the fake was called once with a
    message mentioning the alert count.
- **PATTERN**: `mytrader/tests/test_engine.py`'s `monkeypatch.setattr` + `db_conn`
  fixture shape.
- **GOTCHA**: See "Testing Pattern" section above for the exact
  `monkeypatch.setitem(sys.modules, "notifications", ...)` mechanics needed for the
  `maybe_notify` tests — get this right the first time rather than debugging import
  order.
- **VALIDATE**: `pytest mytrader/tests/test_monitor.py -v`

### Task 5.4: MANUAL VALIDATION

1. `cd investments/my-trader; uv run pytest mytrader/tests -v` — full suite (Phase A's
   67 tests + Phase B's new tests), zero failures, zero regressions.
2. `cd investments/my-trader; uv run ruff check .` and `uv run mypy mytrader` — clean.
3. `cd investments/my-trader; uv run python -m mytrader.main monitor` — real run against
   the actual shared `investments.db` (already seeded from Phase A's Level 4 step, or
   ask Shaun to confirm `seed` has run for real first if not). Eyeball
   `investments/my-trader/monitor-report.md` afterward: correct holding/watchlist
   counts, sensible (or empty) alert list, no exceptions in the console output.
4. Run `monitor` a second time immediately — confirm the console/report shows the same
   `open_alerts` count as run 1 but `new_alerts` is empty this time (proves the dedup
   logic works against real data, not just mocks).
5. **Confirm with Shaun before this step** — first time scheduling tasks run
   unattended: register the Windows Task Scheduler entry (Task 4.1, run
   `setup_scheduler_windows.ps1` as Administrator) and/or deploy + enable the systemd
   timer on the VPS (Task 4.3's manual step), then wait for (or manually trigger) one
   real scheduled run and confirm `monitor_runs.log` / Task Scheduler history shows a
   clean exit.
6. In a fresh Claude Code session, ask "what's my-trader Monitor showing" or similar and
   confirm the `my-trader` skill can read and summarize `monitor-report.md`
   conversationally (manual — skills aren't unit-testable).

---

## TESTING STRATEGY

### Unit Tests

Every new/modified function gets direct coverage: `db.py`'s 5 new functions (Task 5.1),
`market_data.py`'s cache behavior (Task 5.2), `monitor.py`'s full alert-lifecycle state
machine (Task 5.3). All DB tests use the existing `db_conn` tmp_path fixture. No test
hits real yfinance or the real shared `investments.db`.

### Integration Tests

`test_monitor.py`'s multi-run tests (`test_run_monitor_stays_quiet_on_repeat_flag`,
`test_run_monitor_acknowledges_when_flag_clears`,
`test_run_monitor_reflags_after_acknowledge`) are effectively integration tests of the
full alert lifecycle against a real (tmp_path) SQLite DB, exercising `db.py` + `monitor.py`
together across multiple `run_monitor()` calls — the closest thing to an end-to-end
check without hitting real yfinance.

### Edge Cases

- A ticker with zero flagged checks (all `ok`/`info`/`unknown`) — `new_alerts` stays
  empty, `open_alerts` unaffected, no toast.
- A ticker that flags on check A but not check B — only check A gets an alert; B stays
  untouched (no phantom alert, no phantom acknowledge of something never flagged).
- Same ticker appearing in both `holdings` and `watchlist` (edge case, not expected in
  practice but not structurally prevented) — `source_table` is part of the dedup key, so
  a holdings-side flag and a watchlist-side flag for the same ticker/check are tracked
  independently, not conflated.
- A `watchlist` row with `status="raw"` — never checked by Monitor, never appears in
  `checked_watchlist` count or alerts, per the preplan's explicit scope limit.
- Empty `holdings` and `watchlist` tables (e.g. a fresh DB before `seed` has run) —
  `run_monitor` completes cleanly with `checked_holdings=0`, `checked_watchlist=0`,
  empty alert lists, a valid (if sparse) report file, no toast.
- `_process_row` raising an unexpected exception for one ticker — the run continues for
  remaining tickers (Task 2.1's per-row `try/except`), the report reflects however many
  rows succeeded.

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
uv run pytest mytrader/tests/test_monitor.py mytrader/tests/test_market_data.py -v
```

### Level 4: Manual Validation

See Task 5.4 above (real `monitor` run against the shared DB, repeat-run dedup check,
Shaun-confirmed scheduler registration).

### Level 5: Additional Validation

N/A for Phase B (no MCP servers or external CLI tools involved beyond `uv`/`pytest`/
`ruff`/`mypy`/`systemctl`, all already covered above).

---

## ACCEPTANCE CRITERIA

- [ ] `monitor.py` exists with `run_monitor`, `render_report`, `write_report`,
      `maybe_notify`
- [ ] Monitor checks every `holdings` row and every `watchlist` row with
      `status="discussed"` (never `"raw"`)
- [ ] Monitor reuses `engine.run_assessment()` unmodified — no duplicated check logic
- [ ] A check's first `"flag"` verdict for a given (ticker, source_table, check_name)
      creates exactly one `alert_history` row and appears in that run's `new_alerts`
- [ ] A repeated `"flag"` verdict for an already-open alert does not create a duplicate
      row or a repeat notification
- [ ] A check clearing from `"flag"` to non-`"flag"` auto-acknowledges its open alert
- [ ] A check re-flagging after being cleared creates a fresh alert (not a revival)
- [ ] `monitor-report.md` is written on every run (full overwrite), showing this run's
      new alerts and all currently-open alerts
- [ ] `send_toast_notification` fires only when `new_alerts` is non-empty, reused
      unmodified from `.claude/scripts/notifications.py`
- [ ] No daily-log or WhatsApp push from Monitor (per the "output channel" decision) —
      confirm no call to `append_to_daily_log` or `send_whatsapp_notification` exists
      anywhere in `monitor.py`
- [ ] `cached_session()` reduces yfinance calls for a multi-row Monitor run without
      changing Find's or any existing test's behavior
- [ ] `mytrader.main monitor` CLI subcommand works
- [ ] Windows Task Scheduler + systemd timer/service entries exist and (Level 4,
      Shaun's go-ahead) are registered/enabled for real
- [ ] `deploy.ps1` stops/restarts the new timer alongside the heartbeat timer
- [ ] All validation commands (Levels 1-3) pass with zero errors
- [ ] No regressions in Phase A's existing 67 tests

---

## COMPLETION CHECKLIST

- [ ] All tasks completed in order
- [ ] Each task's validation command passed immediately after that task
- [ ] Full `mytrader` test suite passes (Phase A + Phase B tests together)
- [ ] `ruff`/`mypy` clean
- [ ] Level 4 manual validation completed, including Shaun-confirmed scheduler
      registration
- [ ] Acceptance criteria all met
- [ ] `investments/my-trader/handoff.md` updated to reflect Phase B completion (currently
      says Phase B "not started")
- [ ] `.claude/skills/my-trader/SKILL.md` updated (Task 3.2)

---

## NOTES

**Known limitations accepted for Phase B (not blockers, documented for later):**
- Alert severity is a single flat value (`"flag"`) — the `alert_history.severity` column
  exists for future tiering (e.g. distinguishing a dividend cut from a mild valuation
  drift) but Phase B doesn't implement that distinction. Matches Phase A's own pattern of
  deferring threshold/tuning decisions until there's real output to react to.
- No manual "acknowledge" CLI action — acknowledgment is entirely automatic
  (verdict-transition-driven). If a flagged condition is something Shaun consciously
  decides to ignore going forward (not just "not yet dealt with"), there's currently no
  way to silence it without the underlying check itself clearing. Worth a future
  enhancement if it becomes annoying in practice, not needed for Phase B's scope.
- Scheduling cadence (once daily, 07:30 AEST) is a reasonable default, not a decision
  from `tool-preplan.md` (which left this as build-time detail). Easy to change later by
  editing the Task Scheduler trigger / systemd `OnCalendar` value directly — no code
  change needed.
- The `cached_session()` cache is process-lifetime-scoped and per-run only — it does not
  persist across separate `monitor` invocations (each scheduled run gets a fresh cache).
  This is intentional: stale cached prices across runs would be a correctness bug, not
  an optimization.
- DST is not compensated in the systemd `OnCalendar=... UTC` timer — matches the
  existing `second-brain-reflect.timer`'s own simplification, not a new gap introduced
  by this plan.

**Confidence score: 8/10** for one-pass implementation success. Phase B is
lower-complexity than Phase A (no new external data/API surface, no new domain checks)
but introduces one genuinely new design decision not fully specified in
`tool-preplan.md` — the alert dedup/reconciliation state machine (Task 2.1,
`_reconcile_alerts`) — which this plan has fully specified and test-covered (Task 5.3)
rather than leaving to the execution agent to invent. The other main risk is the
cross-project `notifications` import inside `maybe_notify` and its slightly unusual test
mocking shape (`sys.modules` injection) — flagged explicitly in the Testing Pattern
section and Task 5.3's gotcha to avoid an execution-time surprise.
