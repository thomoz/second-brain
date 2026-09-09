# Feature: Goat Sector/Industry Rotation Trend Tracking

> NOTE 2026-09-02: This standalone plan is now the **Part A reference** for the
> combined handoff `investments/goat/industry-pipeline-handoff.md`. Prefer running
> `/plan-feature` on the combined handoff (it folds this together with the
> industry-heartbeat pipeline, which modifies the same files). This plan's task
> breakdown stays valid for the Part A slice. Also see the new "short-window flow"
> open question in the combined handoff before executing Part A.

The following plan should be complete, but validate documentation and codebase patterns
and task sanity before implementing. Pay special attention to naming of existing utils,
types, and models — import from the right files.

## Feature Description

Both `sector-ranking.md` (11 SPDR sector ETFs, 3-month window) and `industry-ranking.md`
(39 Finviz industry ETFs, 6-month window) are pure live-re-fetch snapshots: every run
recomputes each ticker's return and **overwrites** the file, with no memory of the prior
run's numbers. This adds a daily snapshot history (new `goat_rotation_snapshots` table)
plus a "Rotation Flow" report section on both files showing which tickers flipped
Rising/Falling since the last snapshot and a rollup summary of the transitions — the
"which way are trends heading" view Shaun asked for directly.

Prompted by Shaun asking, after the industry ranking shipped: "if SMH drifts down to
just +30%, will that represent a trend and will we see it?" — today's answer is no.
See `investments/goat/rotation-trend-tracking-handoff.md` for full background,
reference-tool screenshots, and the open-questions discussion this plan resolves.

## User Story

As Shaun (advisor-mode Second Brain user)
I want to see which sectors/industries flipped from falling to rising (or vice versa)
since the last snapshot, with a rollup count across the whole universe
So that I can answer "which way are the trends heading" at a glance instead of manually
diffing `git log -p` on the ranking files.

## Problem Statement

`rank_sectors()`/`rank_industries()` already compute a `rising: bool` field
(`return_pct > 0`) on every run, but nothing persists it — each report overwrite loses
the prior run's state. There is no way to answer "how many days has this been falling"
or see a transition table without manual git archaeology, which is an accidental
side effect of vault sync, not a designed feature.

## Solution Statement

Add a new `goat_rotation_snapshots` DB table (one row per ticker per run, generic across
both scopes via a `scope` column). On every `monitor` run (not on-demand `scan-sectors`/
`scan-industries`), after computing each ranking, look up the most recent prior snapshot
for that scope, diff `rising` state per ticker, and render a "Rotation Flow" section
(FROM→TO table + summary rollup) into both `sector-ranking.md` and `industry-ranking.md`
alongside their existing tables. Then insert today's snapshot and prune anything older
than 90 days. No change to the underlying ranking computation
(`rank_sectors`/`rank_industries` stay exactly as they are) — this is additive history
and display only.

**State model: 2-state Rising/Falling** (not the 3-state DOWNHILL/BASE/CLIMBING model
from the handoff's Reference #1) — confirmed with Shaun. Reuses the `rising: bool` field
already computed for free; the 3-state model needs a sourced classification threshold
that doesn't exist anywhere in this repo and is out of scope here.

## Feature Metadata

**Feature Type**: New Capability (sibling extension of an existing pattern)
**Estimated Complexity**: Medium — new DB table + CRUD, new pure-compute module for the
diff/rollup logic, and changes to `cmd_monitor`'s connection lifecycle (industry scan
currently doesn't take a `conn` at all). No new external dependencies.
**Primary Systems Affected**: `investments/goat/` only (`goat/db.py`, `goat/config.py`,
new `goat/rotation_flow.py`, `goat/monitor.py`, `goat/main.py`, tests, `TOOLS.md`).
**Dependencies**: None new.

---

## Decisions Confirmed With Shaun (2026-08-23, this session)

1. **State model: 2-state Rising/Falling**, reusing the existing `rising` bool. No new
   research needed. The 3-state DOWNHILL/BASE/CLIMBING model is explicitly deferred —
   do not build it here.
2. **Comparison granularity: day-over-day.** Both scans already run daily via `monitor`.
3. **Schema: one shared snapshot table** (`scope`, `snapshot_date`, `ticker`, `label`,
   `return_pct`, `rank`, `rising`) rather than two scope-specific tables.
4. **Retention: cap at 90 days**, matching the two existing lookback-window precedents
   in `config.py` (`GOAT_INSIDER_SALE_LOOKBACK_DAYS`, `GOAT_INSIDER_PRICE_STALE_DAYS`).
5. **Write cadence: only the once-daily `monitor` run writes a snapshot.** On-demand
   `scan-sectors`/`scan-industries` compute and render the ranking as before but do NOT
   insert a snapshot row or show a Rotation Flow section (avoids same-day double-counting
   if Shaun runs both `monitor` and an on-demand scan in one day).
6. **Report layout: additive.** Rotation Flow is a new section alongside the existing
   Top 5/Bottom 5/Full Ranking tables, not a replacement.
7. **Filter chips** (per-industry drill-down from the reference screenshot): out of
   scope, not building.

---

## CONTEXT REFERENCES

### Relevant Codebase Files — READ THESE BEFORE IMPLEMENTING

- `investments/goat/rotation-trend-tracking-handoff.md` — full background, both
  reference-tool screenshots' descriptions, and the original open questions (now
  resolved above). Read this first.
- `investments/goat/goat/db.py` (whole file, 335 lines) — every existing table's
  `init_goat_tables` pattern, migration-via-try/except idiom (lines 71–115), and the
  dedup CRUD conventions to mirror: `insert_goat_insider_filing_seen` (lines 224–241,
  `INSERT OR IGNORE` + `rowcount == 1` return), `get_macro_state`/`set_macro_state`
  (lines 282–297, simplest key/value precedent), `replace_sp500_constituents` (lines
  206–217, delete-then-insert-all pattern — NOT what we want here, we want additive
  per-day rows, closer to `insert_goat_insider_filing_seen`'s append-only shape).
- `investments/goat/goat/config.py` lines 43–194 (`GOAT_SECTOR_*`/`GOAT_INDUSTRY_*`
  block) — constant-naming and comment style to match exactly; note
  `GOAT_INSIDER_SALE_LOOKBACK_DAYS` (line 322) and `GOAT_INSIDER_PRICE_STALE_DAYS`
  (line 384) as the 90-day retention precedents cited in Decision #4.
- `investments/goat/goat/sector_rotation.py` (whole file) — `rank_sectors()` output
  shape: `{"ticker", "sector_label", "return_pct", "rising", "rank"}`, `rising` and
  `return_pct` both `None` when data is missing. Do not change this file.
- `investments/goat/goat/industry_rotation.py` (whole file) — same shape with
  `"industry_label"` instead of `"sector_label"`. Do not change this file.
- `investments/goat/goat/monitor.py` (whole file, 379 lines) — specifically:
  - `run_sector_scan` (lines 227–246) and `run_industry_scan` (lines 303–312) — the
    functions whose *output* (the `ranking` list) is the input to the new snapshot/flow
    step. Do not change their signatures or behavior — the snapshot step is a separate
    orchestration call, not baked into these.
  - `render_sector_ranking_report` (lines 249–266) and `render_industry_ranking_report`
    (lines 315–372) — where the new Rotation Flow section gets spliced in.
  - `write_sector_ranking_report`/`write_industry_ranking_report` — unchanged, still
    just `Path.write_text`.
- `investments/goat/goat/main.py` lines 22–49 (`cmd_monitor`) — **must change**: today
  it does `conn = _open_conn()` → `run_monitor` → `run_sector_scan` → `conn.close()` →
  `run_industry_scan()` (no conn). The snapshot step needs `conn` open across both
  sector and industry scans, so `conn.close()` must move to after both.
  `cmd_scan_sectors` (lines 66–84) and `cmd_scan_industries` (lines 87–97) — must NOT
  call the new snapshot step (Decision #5) — leave these two functions unchanged.
- `investments/goat/goat/tests/conftest.py` (whole file) — `db_conn` fixture (real
  SQLite via `scripts.db.get_connection`/`init_db` against a `tmp_path` file, both
  `init_mytrader_tables` and `init_goat_tables` called), the `_isolate_goat_report_path`
  autouse fixture (must add `GOAT_SECTOR_RANKING_MD_PATH` +
  `GOAT_INDUSTRY_RANKING_MD_PATH` if not already isolated — check: currently only
  `GOAT_INDUSTRY_RANKING_MD_PATH` is isolated, `GOAT_SECTOR_RANKING_MD_PATH` is NOT in
  this list, confirm whether existing sector-ranking tests already handle this via
  `monkeypatch` per-test before assuming a gap), and `_no_real_price_history_fetch`
  (global network-call stub — irrelevant to this feature but explains why other tests
  monkeypatch `fetch_close_history`).
- `investments/goat/goat/tests/test_db.py` (whole file) — CRUD test pattern to mirror:
  simple `db_conn`-fixture, function-per-behavior tests, no mocking needed since it's
  real SQLite against a tmp file.
- `investments/goat/goat/tests/test_monitor.py` lines 369–380
  (`test_render_sector_ranking_report_lists_all_rows`) and lines 443–499 (the industry
  section) — exact `result` dict shapes the render functions receive today; the new
  `rotation_flow` key must be optional/additive to these shapes so existing tests keep
  passing unmodified.
- `.agent/plans/goat-industry-rotation-ranking.md` — the direct predecessor plan for
  this exact pair of files; mirror its structure, decision-documentation style, and the
  "Gotcha" callout convention.

### New Files to Create

- `investments/goat/goat/rotation_flow.py` — pure-compute diff/rollup logic (no DB
  access), mirrors `sector_rotation.py`'s "no side effects" module shape.
- `investments/goat/goat/tests/test_rotation_flow.py` — unit tests for the diff/rollup
  logic in isolation.

### Files to Modify

- `investments/goat/goat/db.py` — new table + CRUD functions.
- `investments/goat/goat/config.py` — one new retention constant.
- `investments/goat/goat/monitor.py` — new orchestration function + render-function
  changes.
- `investments/goat/goat/main.py` — `cmd_monitor` connection-lifecycle change.
- `investments/goat/goat/tests/test_db.py` — new CRUD tests.
- `investments/goat/goat/tests/test_monitor.py` — new orchestration + render tests.
- `investments/goat/goat/tests/conftest.py` — only if the sector-ranking report path
  isolation gap noted above turns out to be real (verify first, see Task 6).
- `investments/TOOLS.md` — one-line description tweaks for the two report rows (lines
  ~17–18) noting the new Rotation Flow section; no new CLI command to document.
- `investments/goat/rotation-trend-tracking-handoff.md` — update `## Status` line at
  the top to point at this plan, matching how `industry-rotation-handoff.md`'s Status
  line was written before its own plan superseded it.

### Relevant Documentation

None — this is pure SQLite + Python, no new library, no external API.

### Patterns to Follow

**Table naming/migration:** All Goat tables are `goat_*`, created inside
`init_goat_tables` via `conn.executescript`, called every startup (idempotent
`CREATE TABLE IF NOT EXISTS`). New nullable columns on existing tables use the
try/except `ALTER TABLE` idiom (db.py lines 76–115) — not needed here since this is a
brand-new table, no migration required.

**Dedup-insert idiom (mirror `insert_goat_insider_filing_seen`, db.py:224-241):**
```python
def insert_goat_insider_filing_seen(...) -> bool:
    with conn:
        cur = conn.execute("""INSERT OR IGNORE INTO ... VALUES (...)""", (...))
        return cur.rowcount == 1
```
Use the same shape for snapshot inserts, keyed on a `UNIQUE(scope, snapshot_date,
ticker)` constraint so a same-day double-run of `monitor` cannot create duplicate rows
or crash.

**Config constant comment style (config.py, throughout):** every threshold has a
trailing `#` comment citing either literature or "Shaun's number, date" or "v1/tunable".
The new retention constant should cite Decision #4 above and the two existing 90-day
precedents by name.

**Report render functions build a `lines: list[str]` then `"\n".join(lines) + "\n"`**
(see every `render_*` function in monitor.py) — the new Rotation Flow section is a
`list[str]` fragment spliced into the existing `lines` list, not a separately-rendered
string concatenated differently.

**`date.today().isoformat()`** is used everywhere in this codebase for "today" (no
timezone handling) — e.g. `render_report`, `GOAT_MONITOR_REPORT_PATH` writers. Use the
same for `snapshot_date`. ISO date strings (`YYYY-MM-DD`) sort lexicographically =
chronologically, which the "most recent prior snapshot" query relies on.

---

## IMPLEMENTATION PLAN

### Phase 1: Foundation — DB Schema + Config

**Tasks:**
- Add `goat_rotation_snapshots` table + index to `init_goat_tables`.
- Add CRUD functions to `db.py`.
- Add `GOAT_ROTATION_SNAPSHOT_RETENTION_DAYS` to `config.py`.

### Phase 2: Core Implementation — Diff/Rollup Logic

**Tasks:**
- Build `goat/rotation_flow.py`: pure functions to diff two snapshot sets and produce
  a transitions list + summary rollup string.
- Build the Markdown-fragment renderer for the Rotation Flow section.

### Phase 3: Integration — Wire Into Monitor + CLI

**Tasks:**
- Add the orchestration function in `monitor.py` that ties snapshot lookup → diff →
  insert → prune together for one scope.
- Call it from `cmd_monitor` only (not the on-demand scan commands), for both scopes.
- Splice the Rotation Flow section into both render functions, conditionally on
  `result.get("rotation_flow")` being present.

### Phase 4: Testing & Validation

**Tasks:**
- Unit tests for `db.py` CRUD (insert/dedup/prune/query-most-recent-before).
- Unit tests for `rotation_flow.py` (transitions, summary formatting, no-prior-data
  case, all-missing-data case).
- Integration tests for the new `monitor.py` orchestration function against a real
  `db_conn` fixture (seed a "yesterday" snapshot, run against "today"'s ranking, assert
  transitions found).
- Render tests confirming the Rotation Flow section appears when `rotation_flow` is
  present and is absent/omitted when it isn't (on-demand scan path).
- Full `pytest -q` run.

---

## STEP-BY-STEP TASKS

### Task 1: ADD `goat_rotation_snapshots` table to `investments/goat/goat/db.py`

- **IMPLEMENT**: Inside `init_goat_tables`'s existing `conn.executescript(...)` call
  (db.py lines 17–70), add a new `CREATE TABLE IF NOT EXISTS goat_rotation_snapshots`
  block plus a `CREATE INDEX IF NOT EXISTS` on `(scope, snapshot_date)`:
  ```sql
  CREATE TABLE IF NOT EXISTS goat_rotation_snapshots (
      id              INTEGER PRIMARY KEY AUTOINCREMENT,
      scope           TEXT NOT NULL,
      snapshot_date   TEXT NOT NULL,
      ticker          TEXT NOT NULL,
      label           TEXT NOT NULL,
      return_pct      REAL,
      rank            INTEGER,
      rising          INTEGER,
      created_at      TEXT NOT NULL,
      UNIQUE (scope, snapshot_date, ticker)
  );
  CREATE INDEX IF NOT EXISTS idx_goat_rotation_snapshots_scope_date
      ON goat_rotation_snapshots (scope, snapshot_date);
  ```
- **PATTERN**: Existing `goat_insider_filings_seen` table shape (db.py lines 42–53) —
  same nullable-numeric-columns + `UNIQUE` constraint idiom, adapted to this table's
  own key (`scope, snapshot_date, ticker` instead of `dedup_key`).
- **GOTCHA**: `rank` is a SQLite reserved-ish word in some dialects but is fine as a
  bare column name in SQLite specifically (no quoting needed) — confirmed by SQLite's
  own reserved-word list not including `rank`. If in doubt, verify with a local
  `sqlite3` shell `CREATE TABLE` test before committing to the unquoted name.
- **VALIDATE**: `uv run --directory investments/goat python -c "from scripts.db import get_connection, init_db; from goat.db import init_goat_tables; init_db('/tmp/t.db'); c=get_connection('/tmp/t.db'); init_goat_tables(c); print(c.execute('SELECT name FROM sqlite_master WHERE type=\"table\" AND name=\"goat_rotation_snapshots\"').fetchall())"`

### Task 2: ADD CRUD functions to `investments/goat/goat/db.py`

- **IMPLEMENT**: Four functions, placed after `insert_price_outcome`/
  `get_price_outcomes_for_pattern_analysis` (end of file):
  ```python
  def insert_rotation_snapshots(
      conn: sqlite3.Connection, *, scope: str, snapshot_date: str,
      ranking: list[dict], label_key: str,
  ) -> int:
      """Bulk-inserts one row per ranking entry for this scope/date. UNIQUE(scope,
      snapshot_date, ticker) + INSERT OR IGNORE means a same-day double-run of
      `monitor` is a safe no-op, not a crash or a duplicate. label_key is
      'sector_label' or 'industry_label' -- the two ranking row shapes differ only
      in that key name. Returns the count of rows actually inserted (new)."""
      now = _now()
      inserted = 0
      with conn:
          for row in ranking:
              cur = conn.execute(
                  """INSERT OR IGNORE INTO goat_rotation_snapshots
                     (scope, snapshot_date, ticker, label, return_pct, rank, rising, created_at)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                  (scope, snapshot_date, row["ticker"], row[label_key],
                   row["return_pct"], row["rank"],
                   None if row["rising"] is None else int(row["rising"]), now),
              )
              inserted += cur.rowcount
      return inserted


  def get_rotation_snapshot(
      conn: sqlite3.Connection, *, scope: str, snapshot_date: str
  ) -> list[sqlite3.Row]:
      return conn.execute(
          "SELECT * FROM goat_rotation_snapshots WHERE scope = ? AND snapshot_date = ?",
          (scope, snapshot_date),
      ).fetchall()


  def get_latest_snapshot_date_before(
      conn: sqlite3.Connection, *, scope: str, before_date: str
  ) -> str | None:
      """Most recent snapshot_date strictly before before_date for this scope --
      deliberately not 'yesterday' literally, so gaps (weekends, missed runs) are
      handled by finding whatever the last real snapshot actually was."""
      row = conn.execute(
          """SELECT MAX(snapshot_date) AS d FROM goat_rotation_snapshots
             WHERE scope = ? AND snapshot_date < ?""",
          (scope, before_date),
      ).fetchone()
      return row["d"] if row is not None else None


  def prune_rotation_snapshots(conn: sqlite3.Connection, *, scope: str, cutoff_date: str) -> int:
      """Deletes snapshot rows for this scope strictly older than cutoff_date
      (caller computes cutoff_date = today - retention_days)."""
      with conn:
          cur = conn.execute(
              "DELETE FROM goat_rotation_snapshots WHERE scope = ? AND snapshot_date < ?",
              (scope, cutoff_date),
          )
          return cur.rowcount
  ```
- **PATTERN**: `insert_goat_insider_filing_seen` (db.py:224-241) for the `INSERT OR
  IGNORE` + rowcount idiom; `get_sp500_constituents_fetched_at` (db.py:198-203) for
  the `MAX(...)` single-scalar query shape.
- **IMPORTS**: No new imports — `sqlite3`, `_now()` already in this file.
- **GOTCHA**: `rising` in the `ranking` dicts is a Python `bool | None`, not directly
  SQLite-storable as intended — SQLite would silently store `True`/`False` as `1`/`0`
  anyway (Python bool is an int subclass), but store it explicitly as
  `None if row["rising"] is None else int(row["rising"])` so the column's actual
  stored type is unambiguous when read back and compared in `rotation_flow.py`.
- **VALIDATE**: covered by Task 6's `test_db.py` additions.

### Task 3: ADD retention constant to `investments/goat/goat/config.py`

- **IMPLEMENT**: Add near the end of the file, after `GOAT_INSIDER_PRICE_STALE_DAYS`
  (config.py line 384) or in a new comment block referencing the sector/industry
  rotation section above (lines 43-194) — place wherever reads more naturally, but
  keep it grouped near a comment explaining the feature, matching every other
  constant's style:
  ```python
  # Sector/industry rotation trend tracking (Rotation Flow), per
  # .agent/plans/goat-rotation-trend-tracking.md -- day-over-day Rising/Falling
  # state diff against a new goat_rotation_snapshots table. Shared by both
  # GOAT_SECTOR_ETFS and GOAT_INDUSTRY_ETFS scopes.
  GOAT_ROTATION_SNAPSHOT_RETENTION_DAYS = 90  # matches the two existing 90-day
      # lookback precedents in this file (GOAT_INSIDER_SALE_LOOKBACK_DAYS,
      # GOAT_INSIDER_PRICE_STALE_DAYS) -- Shaun confirmed 2026-08-23, ~50
      # rows/day (11 sectors + 39 industries) keeps this table small regardless.
  ```
- **VALIDATE**: `uv run --directory investments/goat python -c "from goat import config; print(config.GOAT_ROTATION_SNAPSHOT_RETENTION_DAYS)"`

### Task 4: CREATE `investments/goat/goat/rotation_flow.py`

- **IMPLEMENT**: Pure-compute module, no DB/network access (mirrors `sector_rotation.py`
  and `industry_rotation.py`'s "fetch/compute" separation — this module is compute-only,
  the DB read/write lives in `monitor.py`'s orchestration call):
  ```python
  """Day-over-day Rising/Falling transition diff + rollup for Goat's sector/industry
  rotation rankings -- see .agent/plans/goat-rotation-trend-tracking.md. Pure compute,
  no DB access (monitor.py's orchestration layer owns the snapshot read/write)."""

  from __future__ import annotations

  from typing import Any


  def _state_label(rising: bool) -> str:
      return "Rising" if rising else "Falling"


  def compute_flow(
      previous_rows: list[Any], current_ranking: list[dict], *, label_key: str
  ) -> dict[str, Any]:
      """previous_rows: sqlite3.Row-like objects from db.get_rotation_snapshot (or
      [] if no prior snapshot exists for this scope). current_ranking: the raw
      rank_sectors()/rank_industries() output. Tickers with rising is None on
      either side (missing price data) are excluded entirely -- an unknown state
      cannot transition. Returns {"transitions": [...], "summary": str,
      "no_prior_count": int}."""
      previous_by_ticker = {
          row["ticker"]: row["rising"] for row in previous_rows if row["rising"] is not None
      }
      transitions: list[dict[str, Any]] = []
      no_prior_count = 0
      for row in current_ranking:
          if row["rising"] is None:
              continue
          ticker = row["ticker"]
          if ticker not in previous_by_ticker:
              no_prior_count += 1
              continue
          prev_rising = bool(previous_by_ticker[ticker])
          curr_rising = bool(row["rising"])
          if prev_rising == curr_rising:
              continue
          transitions.append({
              "ticker": ticker,
              "label": row[label_key],
              "from_state": _state_label(prev_rising),
              "to_state": _state_label(curr_rising),
          })

      counts: dict[tuple[str, str], int] = {}
      for t in transitions:
          key = (t["from_state"], t["to_state"])
          counts[key] = counts.get(key, 0) + 1
      summary = " · ".join(
          f"{n} {frm} → {to}" for (frm, to), n in sorted(counts.items(), key=lambda kv: -kv[1])
      ) if counts else "No transitions."

      return {"transitions": transitions, "summary": summary, "no_prior_count": no_prior_count}


  def render_flow_section(
      flow: dict[str, Any], *, heading: str, previous_date: str | None, snapshot_date: str,
  ) -> list[str]:
      """Returns a list[str] of markdown lines -- caller splices this into its own
      lines list (matches every render_* function's list-building convention in
      monitor.py)."""
      lines = ["", f"## {heading}"]
      if previous_date is None:
          lines.append(
              f"No prior snapshot yet for this scope -- comparison starts from the "
              f"next run after {snapshot_date}."
          )
          return lines

      lines.append(f"{previous_date} → {snapshot_date}")
      lines.append("")
      lines.append(flow["summary"])
      if flow["transitions"]:
          lines += ["", "| Ticker | Label | From | To |", "|--------|-------|------|----|"]
          for t in flow["transitions"]:
              lines.append(f"| {t['ticker']} | {t['label']} | {t['from_state']} | {t['to_state']} |")
      if flow["no_prior_count"]:
          lines += [
              "",
              f"({flow['no_prior_count']} ticker(s) had no prior snapshot to compare "
              "against and are excluded above.)",
          ]
      return lines
  ```
- **PATTERN**: `sector_rotation.py`/`industry_rotation.py`'s module docstring style
  (first line references the plan doc); `monitor.py`'s `render_*` functions' `lines:
  list[str]` + string-join convention (the caller, not this function, does the final
  join).
- **GOTCHA**: `previous_rows` are `sqlite3.Row` objects (dict-like but not a real
  dict) — indexing via `row["ticker"]` works, but `.get()` does not exist on
  `sqlite3.Row` in this codebase's connection setup (check `scripts/db.py`'s
  `get_connection` for whether `row_factory = sqlite3.Row` is set — every other
  `db.py` function in this file assumes so, e.g. `db.get_open_goat_alert` returns rows
  accessed via `row["ticker"]` elsewhere in monitor.py). Do not call `.get()` on these.
- **VALIDATE**: covered by Task 6's `test_rotation_flow.py`.

### Task 5: ADD orchestration + render changes to `investments/goat/goat/monitor.py`

- **IMPLEMENT**: One new orchestration function plus edits to both render functions.

  New function, placed after `run_industry_scan`/before `render_industry_ranking_report`
  (or anywhere logical near the two scan functions):
  ```python
  def capture_rotation_snapshot(
      conn: sqlite3.Connection, *, scope: str, ranking: list[dict], label_key: str,
  ) -> dict[str, Any]:
      """Called only from cmd_monitor (never the on-demand scan-sectors/
      scan-industries commands, per the plan's Decision #5) -- looks up the most
      recent prior snapshot, diffs it against today's ranking, records today's
      snapshot, and prunes anything past the retention window. Returns the dict
      to merge into the scan result under the 'rotation_flow' key."""
      snapshot_date = date.today().isoformat()
      previous_date = db.get_latest_snapshot_date_before(conn, scope=scope, before_date=snapshot_date)
      previous_rows = (
          db.get_rotation_snapshot(conn, scope=scope, snapshot_date=previous_date)
          if previous_date is not None else []
      )
      flow = rotation_flow.compute_flow(previous_rows, ranking, label_key=label_key)
      db.insert_rotation_snapshots(conn, scope=scope, snapshot_date=snapshot_date, ranking=ranking, label_key=label_key)
      cutoff = (date.today() - timedelta(days=config.GOAT_ROTATION_SNAPSHOT_RETENTION_DAYS)).isoformat()
      db.prune_rotation_snapshots(conn, scope=scope, cutoff_date=cutoff)
      return {"flow": flow, "previous_date": previous_date, "snapshot_date": snapshot_date}
  ```
  Add `from datetime import timedelta` to the existing `from datetime import date`
  import line, and `from . import rotation_flow` to the existing relative import line
  (`from . import config, db, exit_check, industry_rotation, price_history,
  sector_rotation` → add `rotation_flow` alphabetically).

  Edit `render_sector_ranking_report` (monitor.py:249-266): after the intro
  paragraph's `lines` list (before the `| Rank | Ticker | ... |` table header), splice:
  ```python
      rotation_flow_result = result.get("rotation_flow")
      if rotation_flow_result:
          from . import rotation_flow as _rotation_flow
          lines += _rotation_flow.render_flow_section(
              rotation_flow_result["flow"], heading="Rotation Flow",
              previous_date=rotation_flow_result["previous_date"],
              snapshot_date=rotation_flow_result["snapshot_date"],
          )
      lines += ["", "| Rank | Ticker | Sector | Return | Rising |", "|------|--------|--------|--------|--------|"]
  ```
  (Prefer a top-of-file `from . import rotation_flow` alongside the other relative
  imports over the inline import shown above — the inline form here is only to show
  exactly where the splice happens; use the real top-level import in the actual edit.)

  Edit `render_industry_ranking_report` (monitor.py:315-372) the same way, splicing
  the Rotation Flow section after the intro paragraph and before `## Top 5 Rising`.

  Add `from . import rotation_flow` to monitor.py's top-level relative import (once,
  covers both render functions).

- **PATTERN**: Every other `render_*` function's `lines: list[str]` build-then-join
  shape; `run_sector_scan`'s existing `conn` parameter shape for the new function's
  signature.
- **IMPORTS**: `from datetime import date, timedelta` (was just `date`); add
  `rotation_flow` to the `from . import ...` line.
- **GOTCHA**: `capture_rotation_snapshot` must be called AFTER `run_sector_scan`/
  `run_industry_scan` have produced their `ranking` list but BEFORE `conn.close()` —
  see Task 6 for the `cmd_monitor` restructuring this requires.
- **VALIDATE**: covered by Task 7's `test_monitor.py` additions.

### Task 6: UPDATE `investments/goat/goat/main.py`'s `cmd_monitor`

- **IMPLEMENT**: Restructure so `conn` stays open across both scans and the
  snapshot-capture calls, moving `run_industry_scan` to take a `conn` is NOT needed
  (it stays pure-compute per its own docstring) — only the new
  `capture_rotation_snapshot` call needs `conn`, called once per scope after each
  scan's `ranking` is available:
  ```python
  def cmd_monitor(args) -> None:
      from .monitor import (
          capture_rotation_snapshot,
          maybe_notify,
          run_industry_scan,
          run_monitor,
          run_sector_scan,
          write_industry_ranking_report,
          write_report,
          write_sector_candidates_report,
          write_sector_ranking_report,
      )

      conn = _open_conn()
      result = run_monitor(conn)
      sector_result = run_sector_scan(conn)
      sector_result["rotation_flow"] = capture_rotation_snapshot(
          conn, scope="sector", ranking=sector_result["ranking"], label_key="sector_label",
      )
      industry_result = run_industry_scan()  # still no conn needed for the scan itself
      industry_result["rotation_flow"] = capture_rotation_snapshot(
          conn, scope="industry", ranking=industry_result["ranking"], label_key="industry_label",
      )
      conn.close()
      result["new_sector_candidates"] = sector_result["new_candidates"]
      write_report(result)
      write_sector_ranking_report(sector_result)
      write_sector_candidates_report(sector_result)
      write_industry_ranking_report(industry_result)
      maybe_notify(result, new_candidates=sector_result["new_candidates"])
      print(
          f"Goat Monitor complete: {len(result['new_alerts'])} new exit alert(s), "
          f"{len(sector_result['new_candidates'])} new sector candidate(s). "
          f"See investments/goat/goat-report.md"
      )
  ```
  `cmd_scan_sectors` and `cmd_scan_industries` are **not modified** — they keep calling
  `run_sector_scan`/`run_industry_scan` and the existing write functions with no
  `rotation_flow` key, so `result.get("rotation_flow")` is `None` and the render
  functions correctly omit the section (Decision #5).
- **PATTERN**: existing `cmd_monitor` structure (main.py:22-49) — this is a targeted
  reorder/insert, not a rewrite.
- **GOTCHA**: `conn.close()` must move to AFTER both `capture_rotation_snapshot` calls
  (it currently happens right after `run_sector_scan`, before `run_industry_scan` is
  even called) — moving this correctly is the crux of this task.
- **VALIDATE**: `uv run --directory investments/goat python -m pytest -q -k main` (if
  main.py has any direct tests) plus the manual VPS validation commands at the bottom
  of this plan (never run locally against the real DB).

### Task 7: ADD tests

- **IMPLEMENT** in `investments/goat/goat/tests/test_db.py` (append):
  - `test_insert_rotation_snapshots_then_get_finds_them` — insert a 2-row ranking for
    scope "sector", assert `get_rotation_snapshot` returns both with correct fields.
  - `test_insert_rotation_snapshots_twice_same_day_is_idempotent` — insert same
    scope/date/ranking twice, assert second call's returned insert-count is 0 and
    `get_rotation_snapshot` still returns exactly the original row count (no
    duplicates, no crash) — this is the "double-run of monitor" safety guarantee.
  - `test_get_latest_snapshot_date_before_finds_most_recent_prior` — insert snapshots
    on "2026-08-20" and "2026-08-22" for a scope, call
    `get_latest_snapshot_date_before(scope=..., before_date="2026-08-23")`, assert it
    returns "2026-08-22" (the most recent, skipping the gap at 08-21).
  - `test_get_latest_snapshot_date_before_returns_none_when_no_history` — empty table,
    assert `None`.
  - `test_prune_rotation_snapshots_removes_only_older_rows` — insert snapshots on two
    dates, prune with a cutoff between them, assert only the older one is gone.
  - `test_rotation_snapshots_scoped_independently` — insert "sector" and "industry"
    scope rows for the same ticker/date, assert `get_rotation_snapshot` for one scope
    never returns the other's rows.

- **IMPLEMENT** in `investments/goat/goat/tests/test_rotation_flow.py` (new file):
  - `test_compute_flow_detects_rising_to_falling_transition`
  - `test_compute_flow_detects_falling_to_rising_transition`
  - `test_compute_flow_ignores_unchanged_state`
  - `test_compute_flow_excludes_tickers_with_none_rising_on_either_side`
  - `test_compute_flow_counts_no_prior_tickers_separately`
  - `test_compute_flow_summary_format` — assert exact string shape, e.g.
    `"2 Falling → Rising · 1 Rising → Falling"` for a specific mixed input, and
    `"No transitions."` for an empty-transitions input.
  - `test_render_flow_section_no_prior_date_shows_first_run_message`
  - `test_render_flow_section_lists_transitions_and_no_prior_count`

- **IMPLEMENT** in `investments/goat/goat/tests/test_monitor.py` (append, near the
  existing sector/industry scan tests around lines 295-499):
  - `test_capture_rotation_snapshot_first_run_has_no_previous_date` — call against an
    empty `db_conn`, assert `result["previous_date"] is None` and
    `result["flow"]["transitions"] == []`.
  - `test_capture_rotation_snapshot_detects_transition_against_seeded_prior_day` —
    manually call `goat_db.insert_rotation_snapshots` with a "yesterday" date/ranking
    where XLK was falling, then call `capture_rotation_snapshot` with today's ranking
    where XLK is rising, assert the transition appears in `result["flow"]["transitions"]`.
  - `test_capture_rotation_snapshot_writes_todays_snapshot` — after calling, assert
    `goat_db.get_rotation_snapshot(db_conn, scope="sector",
    snapshot_date=date.today().isoformat())` returns the rows just captured.
  - `test_render_sector_ranking_report_includes_rotation_flow_when_present` — pass a
    `result` dict with a `"rotation_flow"` key, assert `"## Rotation Flow"` and the
    summary text appear in the rendered output.
  - `test_render_sector_ranking_report_omits_rotation_flow_when_absent` — existing
    `result` dict shape (no `rotation_flow` key, matches the current
    `test_render_sector_ranking_report_lists_all_rows` fixture) still renders with
    `"## Rotation Flow"` NOT in the output — this is the regression guard proving
    on-demand `scan-sectors` reports are unaffected.
  - Same two pairs (`includes`/`omits`) for `render_industry_ranking_report`.

- **PATTERN**: `test_db.py`'s function-per-behavior style; `test_monitor.py`'s
  `_patch_sector_universe`/`_patch_sector_fetch` monkeypatch helpers for any test that
  needs a real `run_sector_scan`/`run_industry_scan` call rather than a hand-built
  `ranking` list.
- **VALIDATE**: `uv run --directory investments/goat python -m pytest -q`

### Task 8: UPDATE `investments/TOOLS.md`

- **IMPLEMENT**: Adjust the two existing rows (lines 17-18) to mention the new
  Rotation Flow section, e.g. append "(now incl. day-over-day Rotation Flow section)"
  to both the `goat-report.md` and `industry-ranking.md` row descriptions. Check line
  56 (`Goat sector scan (on-demand)`) and 57 (`Goat industry scan (on-demand)`) too —
  these should clarify that the on-demand path does NOT include Rotation Flow
  (Decision #5), e.g. append "(no Rotation Flow snapshot — that's monitor-only)".
- **VALIDATE**: manual read-through, no automated check.

### Task 9: UPDATE `investments/goat/rotation-trend-tracking-handoff.md`

- **IMPLEMENT**: Change the `## Status:` line at the top from "NOT STARTED — handoff
  drafted 2026-08-23. Awaiting `/plan-feature`" to something like "PLANNED — see
  `.agent/plans/goat-rotation-trend-tracking.md` (created 2026-08-23)." Do not delete
  or rewrite the rest of the handoff — it stays as the historical background record
  (matches how `industry-rotation-handoff.md` was left in place after its own plan
  was created, per this repo's existing convention).
- **VALIDATE**: manual read-through.

---

## TESTING STRATEGY

### Unit Tests

- `rotation_flow.py`: pure functions, no fixtures needed beyond hand-built dicts/lists
  (no DB, no network) — see Task 7's `test_rotation_flow.py` list.
- `db.py` CRUD: real SQLite via the existing `db_conn` fixture (this project's
  established pattern — no mocking of SQLite itself anywhere in this codebase).

### Integration Tests

- `monitor.capture_rotation_snapshot` against `db_conn`: seed a prior day via direct
  `db.insert_rotation_snapshots` calls, then call the orchestration function and assert
  on its full return shape (flow + previous_date + snapshot_date) and on the DB state
  afterward (today's snapshot now present).
- Render-function tests confirming the additive/optional nature of the `rotation_flow`
  key — this is the most important regression guard, since it proves on-demand
  `scan-sectors`/`scan-industries` reports (Decision #5) are byte-for-byte unaffected
  by this feature when `rotation_flow` is absent.

### Edge Cases

- Same-day double-run of `monitor` (`cmd_monitor` called twice in one day, e.g. Shaun
  manually re-triggers it) — must not crash, must not duplicate snapshot rows, and the
  second run's flow computation still correctly compares against the actual prior
  day (not today's own just-inserted row), because
  `get_latest_snapshot_date_before` uses a strict `<` on `before_date`.
- First-ever run for a scope (empty `goat_rotation_snapshots` table) — `previous_date`
  is `None`, flow section shows the "no prior snapshot yet" message, no crash on an
  empty `previous_rows` list.
- A ticker present in today's ranking but absent from yesterday's snapshot (e.g. a
  ticker was just added to `GOAT_SECTOR_ETFS`/`GOAT_INDUSTRY_ETFS` config, or its
  price data was `None` yesterday and is populated today) — counted in
  `no_prior_count`, not silently dropped, not crashing on a missing dict key.
- A ticker with `return_pct`/`rising` both `None` today (price fetch failed this run)
  — excluded from flow computation entirely (an unknown state can't "transition"),
  same treatment as the existing ranking tables already give missing data (`"—"`).
- Retention prune deleting rows for one scope must never touch the other scope's rows
  at the same cutoff date — covered by `test_rotation_snapshots_scoped_independently`
  and the scope-filtered `DELETE` in `prune_rotation_snapshots`.

---

## VALIDATION COMMANDS

### Level 1: Syntax & Style

No dedicated linter configured for this package beyond what pytest collection would
already surface (import errors, syntax errors). Run:
```powershell
uv run --directory investments/goat python -c "import goat.rotation_flow, goat.db, goat.monitor, goat.main, goat.config"
```

### Level 2: Unit Tests

```powershell
uv run --directory investments/goat python -m pytest -q
```

### Level 3: Integration Tests

Same command as Level 2 — this project does not separate unit/integration test files
by directory; `test_monitor.py`'s `db_conn`-based tests already are the integration
layer (real SQLite, no DB mocking).

### Level 4: Manual Validation

**Never run these locally against the real DB** — `investments.db` lives only on the
VPS as of 2026-08-23 (see root `CLAUDE.md`). Use `scripts/invoke_investments.ps1`:
```powershell
.\scripts\invoke_investments.ps1 -Package goat -Command "scan-sectors"
.\scripts\invoke_investments.ps1 -Package goat -Command "scan-industries"
```
Confirm both still produce their existing reports with NO Rotation Flow section
(Decision #5 — on-demand path unaffected). Then:
```powershell
.\scripts\invoke_investments.ps1 -Package goat -Command "monitor"
```
Confirm `sector-ranking.md` and `industry-ranking.md` both now show a
"## Rotation Flow" section. First run after deploy will show "No prior snapshot yet"
for both (expected — there is no history before this feature ships). Run `monitor`
again the next day (or manually adjust/inspect the DB) to see an actual transition
table populate.

### Level 5: Additional Validation

Inspect the DB directly on the VPS to confirm snapshot rows and the retention prune
work as expected once enough days have accumulated:
```bash
sqlite3 /path/to/investments.db "SELECT scope, snapshot_date, COUNT(*) FROM goat_rotation_snapshots GROUP BY scope, snapshot_date ORDER BY snapshot_date DESC LIMIT 10;"
```

---

## ACCEPTANCE CRITERIA

- [ ] `goat_rotation_snapshots` table exists with the specified schema and a
      `UNIQUE(scope, snapshot_date, ticker)` constraint.
- [ ] `monitor` (daily cadence) writes one snapshot row per ticker per scope per day,
      idempotently on same-day re-runs.
- [ ] `scan-sectors`/`scan-industries` (on-demand) do NOT write snapshot rows and do
      NOT show a Rotation Flow section — byte-identical behavior to today except for
      whatever incidental data changes normally occur run-to-run.
- [ ] `sector-ranking.md` and `industry-ranking.md`, when generated via `monitor`,
      both show a "## Rotation Flow" section with a FROM→TO table and a summary
      rollup line, additive to (not replacing) their existing tables.
- [ ] First-ever run shows a clear "no prior snapshot" message, not a crash or an
      empty/confusing section.
- [ ] Snapshots older than `GOAT_ROTATION_SNAPSHOT_RETENTION_DAYS` (90) are pruned
      automatically as part of each `monitor` run, scoped independently per scope.
- [ ] All new and existing tests pass: `uv run --directory investments/goat python -m pytest -q`.
- [ ] No change to `rank_sectors`/`rank_industries`/`sector_rotation.py`/
      `industry_rotation.py` — verified by diff, not just by intent.

---

## COMPLETION CHECKLIST

- [ ] Tasks 1–9 completed in order.
- [ ] Each task's validation command run and passed.
- [ ] Full `pytest -q` passes with zero failures.
- [ ] Manual VPS validation (Level 4) run via `invoke_investments.ps1` and both
      report files visually inspected for the new section.
- [ ] `TOOLS.md` and the handoff doc's Status line updated.
- [ ] No changes outside `investments/goat/` and `investments/TOOLS.md`.

---

## NOTES

- This plan deliberately does not touch the 3-state DOWNHILL/BASE/CLIMBING model or
  any streak-counting ("N days rising") feature — both are explicitly out of scope
  per the Decisions section and would need their own follow-up handoff if wanted later
  (the 90-day retention window would already support a streak-count feature without
  schema changes, if that's ever built).
- The retention-prune pattern (`prune_rotation_snapshots`, called every `monitor` run)
  is new to this codebase — no other Goat table currently auto-deletes old rows. Flag
  this explicitly in review since it's a fresh pattern, not a mirrored one.
- `capture_rotation_snapshot`'s placement in `monitor.py` (rather than a new
  `rotation_snapshot_orchestration.py` or similar) matches this codebase's existing
  convention of keeping all cross-cutting orchestration in `monitor.py` (see
  `_stage_new_sector_candidates`, `reconcile_alerts` — neither lives in its own file
  either).
