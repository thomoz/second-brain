# Feature: Goat Phase 1 — Holdings 150DMA Exit Check

The following plan should be complete, but it's important that you validate documentation and codebase patterns and task sanity before you start implementing.

Pay special attention to naming of existing utils, types, and models. Import from the right files etc.

This plan covers **Phase 1 only** of `investments/goat/HANDOFF.md`'s 3-phase Goat scope (confirmed with Shaun 2026-08-11). Phase 2 (sector rotation ranking) and Phase 3 (S&P 500 heartbeat scanner) are **out of scope** — when ready, run `/plan-feature` again against the same `investments/goat/HANDOFF.md`, which will pick up with the workspace/DB scaffolding this phase creates already in place.

## Feature Description

A new sibling package `investments/goat/` (uv workspace member, alongside `briefs-finance/` and `my-trader/`) whose first and only deliverable is a daily check that reads every one of Shaun's existing holdings from the shared `investments.db`, computes each ticker's 150-day moving average from real price history, and raises an advisor-only alert when the holding's exit rule fires: the daily close has stayed **≥6% below its 150-day MA for 2+ consecutive trading days**. This operationalizes the single sell rule from the "Goat Academy" webinar notes ("the exit matters most... sell when price drops reasonably below the 150-day moving average") that my-trader's own value-investing framework has no equivalent of today.

## User Story

As Shaun, holding a portfolio of individual stocks/ETFs tracked in my-trader's `holdings` table
I want a daily automated check that tells me when a holding has fallen meaningfully below its 150-day moving average
So that I catch the "hold a winner until it becomes a loser" mistake the webinar explicitly calls out as the #1 investor error, without having to eyeball a chart for every holding myself

## Problem Statement

my-trader's `checks/price_action.py` deliberately treats price momentum as `verdict="info"` only, by design (Graham's own principle: "price momentum does not matter" — see `investments/briefs-finance/principles/graham.md`). That's correct for my-trader's fundamentals-first philosophy, but it means **no part of the existing toolchain currently implements a trend-following exit rule** — a genuinely different, complementary signal Shaun wants, not a contradiction of my-trader's existing design. Building it inside my-trader would blur that deliberate separation (see HANDOFF.md's "Genuinely different... philosophies are different enough that mixing them would blur design decisions already made deliberately elsewhere").

## Solution Statement

Build Goat as its own workspace package that **depends on my-trader as a library** (read-only: `db.get_all_holdings()`) but writes to its own new DB tables and its own new report file — never touching my-trader's `holdings.md`/`watchlist.md`/`monitor-report.md`/`alert_history` rows. Reuse my-trader's already-proven patterns almost verbatim: `db.py`'s table-creation/migration shape, `alert_history`-style dedup (own table, same shape), `monitor.py`'s alert-reconcile/report-render/toast-notify pipeline, `main.py`'s argparse CLI dispatch shape, and `gold_technicals.py`/`macro_indicators.py`'s moving-average and sign-flip cross-detection math (rolling mean + `dropna().gt(0)/lt(0)` sign diff). The one genuinely new piece is the "≥6% below MA for 2+ consecutive days" exit-rule detector itself.

## Feature Metadata

**Feature Type**: New Capability (new package)
**Estimated Complexity**: Medium (mostly pattern-reuse from a mature sibling package; the new surface area is small — one detector function, one DB table set, one CLI, one report)
**Primary Systems Affected**: New `investments/goat/` package; `investments/pyproject.toml` (add workspace member); `investments/briefs-finance/data/investments.db` (new tables only); no changes to any existing my-trader file
**Dependencies**: `my-trader` (workspace dependency, read-only DB access to `holdings`), `yfinance` (already a my-trader dependency, needed again here), `pandas` (already a my-trader dependency)

---

## CONTEXT REFERENCES

### Relevant Codebase Files — READ THESE BEFORE IMPLEMENTING

- `investments/goat/HANDOFF.md` (full file) — Why: the source design doc this plan implements; all "RESOLVED 2026-08-11" decisions in it are binding (workspace dependency, DB co-location, no direct watchlist/holdings writes).
- `investments/my-trader/transcripts/lesson-extraction/goat-academy-webinar-1.md` (full file, 41 lines) — Why: the original source notes; Step 3 ("The Exit Matters") is the literal rule this phase implements.
- `investments/pyproject.toml` (lines 1-2) — Why: workspace root; `members = ["briefs-finance", "my-trader"]` — add `"goat"` here, nothing else in this file changes.
- `investments/my-trader/pyproject.toml` (full file, 36 lines) — Why: the exact shape Goat's own `pyproject.toml` must mirror: `dependencies = ["my-trader", ...]`, `[tool.uv.sources] my-trader = { workspace = true }`, `[project.optional-dependencies] dev = [...]`, `[tool.pytest.ini_options] testpaths = ["goat/tests"]` + `pythonpath = ["."]`, `[tool.ruff] target-version = "py312"` / `line-length = 100`. Note: my-trader's `pyproject.toml` has **no `[build-system]` section** — it's consumed purely as a workspace source, not built as an installable wheel with a declared package dir. Mirror that (leaner than briefs-finance's hatchling setup).
- `investments/my-trader/mytrader/db.py` (full file, 541 lines) — Why: the exact schema/CRUD shape to mirror for Goat's own tables:
  - `init_mytrader_tables(conn)` (lines 27-145) — one `conn.executescript("""CREATE TABLE IF NOT EXISTS ...""")` block, no schema-version table, additive-column migrations done separately via `PRAGMA table_info(...)` (see `_ensure_watchlist_return_columns`, lines 13-24) — Goat won't need this migration pattern yet (greenfield schema) but should know it exists for future columns.
  - `get_all_holdings(conn) -> list[sqlite3.Row]` (lines 168-169) — `SELECT * FROM holdings ORDER BY ticker, bucket`. This is the exact, only my-trader read Goat needs: `from mytrader import db as mt_db; mt_db.get_all_holdings(conn)`.
  - `alert_history` table schema (lines 60-69): `id, ticker, source_table, check_name, severity, message, created_at, acknowledged`.
  - `get_open_alert(conn, ticker, source_table, check_name)` (lines 305-317) — dedup lookup, deliberately excludes `message` from the dedup key (see docstring) so a drifting message text doesn't spuriously re-alert.
  - `insert_alert(conn, *, ticker, source_table, check_name, severity, message)` (lines 320-331).
  - `acknowledge_alert(conn, alert_id)` (lines 334-336).
  - `get_open_alerts(conn)` (lines 339-342).
  - `_now()` (lines 9-10) — `datetime.now(timezone.utc).isoformat()`, used for every timestamp column.
- `investments/my-trader/mytrader/gold_technicals.py` (full file, 170 lines) — Why: `moving_average_series(close: pd.Series, days: int) -> pd.Series` (lines 35-36) is `close.rolling(days).mean()` — directly reusable for the 150-day MA. `compute_trend()` (lines 77-92) shows the `ma_x_rising` idiom: `ma.iloc[-1] > ma.iloc[-6]` (today vs. 5 trading days prior) — not needed for Phase 1's exit rule itself but useful context for the "MA sloping up/down" idea Phase 3 will need later.
- `investments/my-trader/mytrader/macro_indicators.py` (lines 399-416, 502-560ish) — Why:
  - `_yfinance_history_close(ticker: str, lookback_days: int)` (lines 399-416) — the exact fetch-and-clean pattern to port: `yf.Ticker(ticker).history(start=..., auto_adjust=True)["Close"]`, tz-naive index, returns `None` on empty/failure. Port this into Goat rather than importing it (it's module-private in macro_indicators.py).
  - `check_gold_trend()`'s sign-flip cross detection (lines 526-531):
    ```python
    diff = (close - ma_long).dropna()
    sign = diff.gt(0).astype(int) - diff.lt(0).astype(int)
    sign_changed = sign.diff().fillna(0) != 0
    sign_changes = sign[sign_changed]
    ```
    Not directly needed for the exit-rule detector itself (which is a %-below-threshold check, not a cross-detector), but this is the established idiom for "how many trading days has X held a state" if the consecutive-days-below-threshold logic ends up wanting a similar vectorized shape rather than a manual loop.
- `investments/my-trader/mytrader/config.py` (read in full; 501 lines) — Why: **this is the citation-style pattern every new threshold constant must follow.** Every flag threshold in this file has a comment explaining where the number came from (a named methodology, a live-verified reading, or an explicit "best-guess default, ship and tune" admission) — e.g. lines 68-70 (`OPPORTUNITY_GRAHAM_NUMBER_MAX`, cited to `graham.md`), lines 497-500 (`COT_EXTREME_LONG_PCT`, cited to "Williams' own convention"). Goat's new `GOAT_150DMA_FLAG_PCT` / `GOAT_150DMA_MIN_CONSECUTIVE_DAYS` constants must be commented in this same style, citing Stan Weinstein's Stage Analysis 6% lower-envelope convention (see Notes section below) — do not invent a number without a comment explaining its source, this is an established, enforced project convention.
- `investments/my-trader/mytrader/monitor.py` (full file, 235 lines) — Why: this is THE reference implementation for Goat's own `monitor.py`, mirror its shape closely:
  - `_reconcile_alerts(ticker, source_table, checks, conn)` (lines 47-65) — the exact alert-open/auto-acknowledge loop against `alert_history` (or Goat's equivalent table). Goat needs its own ~15-line copy of this function against its own alert table — it's module-private in my-trader, not importable.
  - `run_monitor(conn)` (lines 91-149) — the per-holding loop shape: `market_data.cached_session()` context manager wraps the loop (not strictly needed for Goat's single-fetch-per-ticker case, but check whether `investments/my-trader/mytrader/market_data.py`'s `cached_session()` is reusable/importable if Goat's loop grows — see `market_data.py:24-36`), try/except per-row so one ticker's fetch failure doesn't kill the whole run (see lines 104-109), returns a result dict consumed by `render_report`.
  - `render_report(result) -> str` (lines 152-213) and `write_report(result) -> None` (lines 216-217) — the exact markdown-report-string-building shape; Goat should produce an analogous `goat-monitor-report.md` (or similar name — confirm during implementation, see Notes) via `config.GOAT_MONITOR_REPORT_PATH.write_text(...)`.
  - `maybe_notify(result)` (lines 220-234) — **GOTCHA**: locates `.claude/scripts` via `Path(__file__).resolve().parent.parent.parent.parent / ".claude" / "scripts"` (4 `.parent` hops from `investments/my-trader/mytrader/monitor.py`, landing at repo root). A Goat file at `investments/goat/goat/monitor.py` is at the exact same directory depth, so the identical 4-hop expression is correct — copy verbatim, but a task below explicitly verifies this against Goat's real final file path rather than assuming.
- `investments/my-trader/mytrader/main.py` (full file, 347 lines) — Why: `_open_conn()` (lines 8-17) and the argparse subparser/dispatch-dict shape (lines 252-346, especially `cmd_monitor` lines 238-249 as the closest analog) are the exact CLI pattern Goat's `goat/main.py` must mirror 1:1.
- `.claude/scripts/notifications.py` (lines 1-36) — Why: `send_toast_notification(title: str, message: str, duration: int = 5) -> bool` (lines 25-35) — the exact function `maybe_notify` imports and calls; Windows toast with console fallback on non-Windows (relevant since Goat also runs on the Linux VPS via systemd).
- `investments/briefs-finance/scripts/db.py` (lines 1-18) — Why: `get_connection(db_path)` / `init_db(db_path)` are the shared low-level connection helpers every package (`my-trader`, and now `goat`) calls before running its own `init_*_tables(conn)`. Goat's `_open_conn()` needs `from scripts.db import get_connection, init_db` exactly like my-trader's does.
- `investments/briefs-finance/scripts/config.py` (lines 1-21) — Why: `DB_PATH = DATA_DIR / "investments.db"` (line 16) — the single shared DB file every package points at; `PROJECT_ROOT = _HERE.parent.parent.parent` (line 13) shows the depth-counting convention for locating the repo root from a script file, same idea `monitor.py`'s `maybe_notify` 4-hop path uses.
- `investments/my-trader/mytrader/config.py` (lines 1-14 specifically) — Why: shows the `from scripts.config import DB_PATH  # noqa: F401` re-export idiom (line 8) and `MY_TRADER_DIR = Path(__file__).resolve().parent.parent` (line 10) path-constant pattern Goat's own `config.py` should mirror (`GOAT_DIR`, `GOAT_MONITOR_REPORT_PATH`, etc.).
- `scripts/systemd/second-brain-mytrader-monitor.timer` and `.service` (both full files) — Why: the exact systemd unit shape for a new `second-brain-goat-monitor.timer`/`.service` pair — `OnCalendar=*-*-* 21:30:00 UTC` + `Persistent=true` for the timer; `Type=oneshot`, `WorkingDirectory=/home/secondbrain/second-brain/investments/goat`, `ExecStart=.../investments/.venv/bin/python -m goat.main monitor` for the service (same shared venv, confirmed in research: one venv for the whole `investments/` workspace, not per-package).
- `investments/my-trader/mytrader/tests/conftest.py` (full file, 142 lines) — Why: Goat's own `tests/conftest.py` must mirror the `db_path`/`db_conn` fixture shape (lines 13-26) exactly, extended to also call Goat's own `init_goat_tables(conn)` after `init_mytrader_tables(conn)` (both write to the same file in real usage, so a test connection needing cross-package reads should initialize both table sets). **GOTCHA** (see lines 29-142 and their docstrings): this file's entire back half is autouse fixtures added *after* real production files/DB rows got silently corrupted by unstubbed tests — Goat's conftest must include an equivalent autouse fixture stubbing its own yfinance history-fetch helper, and must isolate whatever report-file path Goat writes (mirroring `_isolate_snapshot_paths`, lines 29-47) from day one, not as a follow-up fix.
- `investments/my-trader/mytrader/tests/test_monitor.py` (lines 1-80 read; full file recommended) — Why: closest existing test file to what Goat's `test_monitor.py` should look like — same autouse-fixture-heavy shape, `_fake_result()` helper pattern (lines 50-58), `_seed_holding()` helper (lines 61-65), and `test_run_monitor_creates_new_alert_for_first_flag` (lines 68-78) as the exact test-shape template for "first flag creates one alert" / dedup / auto-acknowledge behavior.
- `investments/my-trader/mytrader/checks/__init__.py` (full file, 15 lines) — Why: the `CheckResult` dataclass (`name: str, verdict: str, detail: str, data: dict`) — Goat's exit-check detector should return this same shape (import directly: `from mytrader.checks import CheckResult`) so `_reconcile_alerts`-equivalent logic and report rendering can treat it identically to my-trader's own checks, even though Goat's alert table is separate.

### New Files to Create

- `investments/goat/pyproject.toml` — workspace member manifest (mirrors `investments/my-trader/pyproject.toml`'s shape).
- `investments/goat/goat/__init__.py` — empty, package marker.
- `investments/goat/goat/config.py` — `DB_PATH` re-export, `GOAT_DIR`, `GOAT_MONITOR_REPORT_PATH`, `GOAT_150DMA_FLAG_PCT`, `GOAT_150DMA_MIN_CONSECUTIVE_DAYS`, `GOAT_MA_LONG_DAYS = 150`, `GOAT_MA_HISTORY_LOOKBACK_DAYS` (calendar days to fetch — must comfortably exceed 150 trading days, mirror `GOLD_MA_HISTORY_LOOKBACK_DAYS = 500`'s margin).
- `investments/goat/goat/db.py` — `init_goat_tables(conn)` (new `goat_alert_history` table — see Notes on why a separate table from my-trader's `alert_history` rather than reusing it), `get_open_goat_alert`, `insert_goat_alert`, `acknowledge_goat_alert`, `get_open_goat_alerts` (mirrors `mytrader/db.py`'s alert functions 1:1, scoped to Goat's own table).
- `investments/goat/goat/price_history.py` — `fetch_close_history(ticker: str, lookback_days: int) -> pd.Series | None` (ports `macro_indicators._yfinance_history_close`'s logic).
- `investments/goat/goat/exit_check.py` — the core new logic: `check_150dma_exit(ticker: str, close: pd.Series) -> CheckResult`, implementing the ≥6%-below-MA-for-2+-consecutive-closes rule (see Notes for the exact algorithm).
- `investments/goat/goat/monitor.py` — `run_monitor(conn) -> dict`, `render_report(result) -> str`, `write_report(result) -> None`, `maybe_notify(result) -> None`, `_reconcile_alerts(...)` (mirrors `mytrader/monitor.py`'s shape, scoped to holdings-only, one check).
- `investments/goat/goat/main.py` — argparse CLI, `monitor` subcommand only for Phase 1 (mirrors `mytrader/main.py`'s `_open_conn()` + dispatch-dict shape; `_open_conn()` must call both `mt_db.init_mytrader_tables(conn)` — needed for `get_all_holdings` to work against a fresh DB — and `goat_db.init_goat_tables(conn)`).
- `investments/goat/goat/tests/__init__.py` — empty.
- `investments/goat/goat/tests/conftest.py` — `db_path`/`db_conn` fixtures (calls both `init_mytrader_tables` and `init_goat_tables`), autouse yfinance-history stub, autouse report-path isolation.
- `investments/goat/goat/tests/test_exit_check.py` — unit tests for the detector: flags at exactly the threshold, doesn't flag on a single-day dip, flags after 2 consecutive qualifying closes, doesn't flag when price recovers above the MA before 2 days elapse (the exact whipsaw scenario the source notes warn about).
- `investments/goat/goat/tests/test_db.py` — Goat alert table CRUD + dedup round-trip (mirrors `mytrader/tests/test_db.py`'s alert-history tests).
- `investments/goat/goat/tests/test_monitor.py` — mirrors `mytrader/tests/test_monitor.py`'s shape: first-flag creates alert, repeat run stays quiet, recovery auto-acknowledges.
- `investments/goat/goat/monitor-report.md` — generated output file (not hand-written; created by `write_report`, add a placeholder or generate once during manual validation).
- `scripts/systemd/second-brain-goat-monitor.timer` — new systemd timer (mirrors `second-brain-mytrader-monitor.timer`).
- `scripts/systemd/second-brain-goat-monitor.service` — new systemd service (mirrors `second-brain-mytrader-monitor.service`, `ExecStart=.../python -m goat.main monitor`, `WorkingDirectory=.../investments/goat`).

### Files to Update

- `investments/pyproject.toml` — add `"goat"` to `[tool.uv.workspace] members`.
- `investments/goat/HANDOFF.md` — update `## Status:` line from "Not started" to "Phase 1 planned, see `.agent/plans/goat-phase1-150dma-exit-check.md`" once this plan exists (and to "Phase 1 complete" after implementation + validation pass, per this repo's own handoff-lifecycle convention observed across `.agent/plans/completed/`).

### Relevant Documentation

No external library documentation needed beyond what my-trader already depends on and uses identically (`yfinance`, `pandas.Series.rolling`) — this phase is pure pattern-reuse from a mature sibling package, not new-library integration. The one external research input already resolved is cited inline in Notes below (Stan Weinstein Stage Analysis / whipsaw-filter convention for the 150DMA threshold).

### Patterns to Follow

**Naming Conventions:**
- Snake_case functions/modules, matching my-trader throughout (`fetch_close_history`, `check_150dma_exit`, `init_goat_tables`).
- Config constants SCREAMING_SNAKE_CASE with a sourced-rationale comment, matching `mytrader/config.py` exactly (see `GOAT_150DMA_FLAG_PCT` in Notes).
- CLI subcommands kebab-case matching my-trader's (`monitor`, not `run-monitor`).

**Error Handling:**
- Every yfinance fetch wrapped in `try/except Exception: return None`, matching `_yfinance_history_close`'s and `_fetch_ohlcv`'s shape — never let one ticker's fetch failure raise past the caller.
- Monitor's per-holding loop wraps each row in its own `try/except`, printing `[goat-monitor] error checking {ticker}: {e}` and continuing (mirrors `mytrader/monitor.py:104-117`) — one bad ticker must never abort the whole run.
- Missing/insufficient price history (fewer than 150 trading days) returns `CheckResult(verdict="unknown", ...)`, matching `check_gold_trend`'s `verdict="unknown"` on total fetch failure — never a flag on missing data.

**Logging Pattern:**
- Plain `print(f"[goat-monitor] ...")` prefixed messages to stdout/stderr, captured by the systemd service's `StandardOutput=append:.../monitor_runs.log` redirect — matches `mytrader/monitor.py`'s `print(f"[monitor] error ...")` calls exactly, no logging framework in use anywhere in this codebase.

**Other Relevant Patterns:**
- `with conn:` context-manager blocks around every write (auto-commits/rolls back), never a bare `conn.commit()` call — consistent across every function in `mytrader/db.py`.
- `conn.close()` is always the caller's (CLI command's) responsibility, never the library function's — every `cmd_*` in `main.py` opens via `_open_conn()` and explicitly closes.
- Docstrings that explain *why*, not *what*, including dated decisions ("RESOLVED 2026-08-11", "confirmed 2026-07-19") — match this style for any non-obvious Goat decision, especially the threshold sourcing.

---

## IMPLEMENTATION PLAN

### Phase 1: Foundation (workspace + schema)

**Tasks:**
- Add `goat` to the uv workspace.
- Scaffold `investments/goat/` package structure with `pyproject.toml` mirroring my-trader's.
- Define `goat/config.py` path/threshold constants.
- Define `goat/db.py` schema (`goat_alert_history` table) + CRUD + dedup functions.
- Wire up `goat/tests/conftest.py` fixtures.

### Phase 2: Core Implementation (the exit-rule detector)

**Tasks:**
- Implement `goat/price_history.py`'s yfinance fetch helper.
- Implement `goat/exit_check.py`'s `check_150dma_exit()` — the actual new logic (150-day rolling MA, %-below computation, consecutive-day counting).
- Unit test the detector exhaustively against synthetic price series (this is the highest-risk piece of new logic in the whole phase — cover the exact whipsaw scenario the source notes warn about).

### Phase 3: Integration (monitor + CLI + alerting)

**Tasks:**
- Implement `goat/monitor.py` (`run_monitor`, `_reconcile_alerts`, `render_report`, `write_report`, `maybe_notify`).
- Implement `goat/main.py` CLI (`monitor` subcommand).
- Add systemd timer/service units (VPS deployment — not activated in this phase without Shaun's explicit go-ahead, see Notes).

### Phase 4: Testing & Validation

**Tasks:**
- Full unit test suite (detector, db, monitor).
- Manual validation: run `python -m goat.main monitor` against the real DB (read-only against holdings) once, inspect the generated report, confirm no writes landed in any my-trader table/file.
- Confirm `uv sync` / workspace resolution works cleanly from a fresh checkout.

---

## STEP-BY-STEP TASKS

IMPORTANT: Execute every task in order, top to bottom. Each task is atomic and independently testable.

### UPDATE `investments/pyproject.toml`

- **IMPLEMENT**: Add `"goat"` to `[tool.uv.workspace] members` — becomes `members = ["briefs-finance", "my-trader", "goat"]`.
- **PATTERN**: `investments/pyproject.toml:1-2` (current 2-line file).
- **VALIDATE**: `uv sync --directory investments` (should fail cleanly at this point since `investments/goat/pyproject.toml` doesn't exist yet — this task alone isn't independently runnable; validate together with the next task).

### CREATE `investments/goat/pyproject.toml`

- **IMPLEMENT**: Mirror `investments/my-trader/pyproject.toml`'s exact shape:
  ```toml
  [project]
  name = "goat"
  version = "0.1.0"
  requires-python = ">=3.12"
  dependencies = [
      "my-trader",
      "yfinance>=0.2.40",
      "pandas>=2.0.0",
  ]

  [tool.uv.sources]
  my-trader = { workspace = true }

  [project.optional-dependencies]
  dev = ["pytest>=8.0.0", "pytest-mock>=3.12.0", "ruff>=0.2.0", "mypy>=1.8.0"]

  [tool.pytest.ini_options]
  testpaths = ["goat/tests"]
  pythonpath = ["."]

  [tool.ruff]
  target-version = "py312"
  line-length = 100

  [tool.mypy]
  python_version = "3.12"
  ignore_missing_imports = true
  ```
- **GOTCHA**: No `[build-system]` section — matches my-trader's leaner shape (consumed as a workspace source only, not built as an installable wheel). Do not copy briefs-finance's hatchling `[build-system]` block.
- **GOTCHA**: `dependencies` needs `"my-trader"` (not `"briefs-finance"`) as the workspace dependency — Goat imports `mytrader.db`/`mytrader.checks`, not briefs-finance's scripts directly (though `my-trader` itself already depends on `briefs-finance`, so `scripts.db`/`scripts.config` are transitively available).
- **VALIDATE**: `uv sync --directory investments/goat --extra dev` — should resolve cleanly and create/update the shared `investments/.venv`.

### CREATE `investments/goat/goat/__init__.py`

- **IMPLEMENT**: Empty file (package marker), matching `investments/my-trader/mytrader/__init__.py`.
- **VALIDATE**: `python -c "import goat"` succeeds from within the venv (after the next few files exist enough to not error on import).

### CREATE `investments/goat/goat/config.py`

- **IMPLEMENT**:
  ```python
  """Path constants and thresholds for Goat Phase 1 -- the 150-day-MA holdings exit check."""

  from __future__ import annotations

  from pathlib import Path

  from scripts.config import DB_PATH  # noqa: F401  (re-exported for goat callers)

  GOAT_DIR = Path(__file__).resolve().parent.parent  # goat -> investments/goat
  GOAT_MONITOR_REPORT_PATH = GOAT_DIR / "monitor-report.md"

  # 150-day-MA exit check, per investments/goat/HANDOFF.md Phase 1 -- the source
  # webinar notes only say "reasonably below" with no number. Synthesized from two
  # sourced technical-analysis conventions (researched 2026-08-11, no exact
  # precedent exists for this specific rule -- flagged as v1/tunable, not literature-
  # final):
  #   - Stan Weinstein's Stage Analysis uses a 6% lower envelope below a security's
  #     long moving average (his version: 30-week MA on broad market indices) as a
  #     breakdown/health threshold -- the closest well-documented match to this
  #     exact "MA-based exit" framework. Applied here to the 150-day MA on
  #     individual holdings, not Weinstein's original 30-week/index context, so
  #     treat the % as a reasonable starting point, not a proven-for-this-exact-use
  #     constant.
  #   - Standard whipsaw-avoidance practice across trend-following systems requires
  #     2+ consecutive daily closes past a moving-average threshold before treating
  #     it as a real signal (not a single noisy day) -- matches the source notes'
  #     own warning: "sometimes prices break through it slightly but come back up
  #     above."
  GOAT_MA_LONG_DAYS = 150
  GOAT_MA_HISTORY_LOOKBACK_DAYS = 400  # calendar days fetched -- comfortably exceeds
                                          # 150 trading days (~7 months) plus margin
                                          # for weekends/holidays and the lookback
                                          # needed to check "2+ consecutive days",
                                          # same margin philosophy as
                                          # GOLD_MA_HISTORY_LOOKBACK_DAYS (500 for a
                                          # 200-day MA).
  GOAT_150DMA_FLAG_PCT = 6.0  # close must be this many % below the 150DMA to count
                                # as a qualifying day (Weinstein's 6% lower-envelope
                                # convention).
  GOAT_150DMA_MIN_CONSECUTIVE_DAYS = 2  # must hold for this many consecutive
                                           # trading days before flagging (standard
                                           # whipsaw filter).
  ```
- **PATTERN**: `investments/my-trader/mytrader/config.py:1-14` (the `MY_TRADER_DIR`/`DB_PATH` re-export idiom) and lines 358-501 (the citation-comment style — every threshold below its own multi-line sourced rationale).
- **IMPORTS**: `from scripts.config import DB_PATH` — this only resolves once `goat`'s `pyproject.toml` dependency on `my-trader` (which itself depends on `briefs-finance`, whose `scripts` package holds `config.py`) is set up and `uv sync` has run.
- **GOTCHA**: Do not write `6.0` / `2` as bare literals anywhere else in the codebase — always reference `config.GOAT_150DMA_FLAG_PCT` / `config.GOAT_150DMA_MIN_CONSECUTIVE_DAYS` so the values stay single-sourced and easy to tune later (matches every other threshold in `mytrader/config.py`).
- **VALIDATE**: `python -c "from goat import config; print(config.DB_PATH, config.GOAT_150DMA_FLAG_PCT)"`.

### CREATE `investments/goat/goat/db.py`

- **IMPLEMENT**:
  ```python
  """goat_alert_history schema + CRUD -- Goat's own alert table, kept separate from
  my-trader's alert_history (see plan Notes for why) but built on the same shared
  investments.db connection."""

  from __future__ import annotations

  import sqlite3
  from datetime import datetime, timezone


  def _now() -> str:
      return datetime.now(timezone.utc).isoformat()


  def init_goat_tables(conn: sqlite3.Connection) -> None:
      with conn:
          conn.executescript("""
              CREATE TABLE IF NOT EXISTS goat_alert_history (
                  id              INTEGER PRIMARY KEY AUTOINCREMENT,
                  ticker          TEXT NOT NULL,
                  source_table    TEXT NOT NULL,
                  check_name      TEXT NOT NULL,
                  severity        TEXT NOT NULL,
                  message         TEXT NOT NULL,
                  created_at      TEXT NOT NULL,
                  acknowledged    INTEGER NOT NULL DEFAULT 0
              );
          """)


  def get_open_goat_alert(
      conn: sqlite3.Connection, ticker: str, source_table: str, check_name: str
  ) -> sqlite3.Row | None:
      """Mirrors mytrader.db.get_open_alert's dedup shape exactly -- message
      deliberately excluded from the dedup key for the same reason (see that
      function's docstring)."""
      return conn.execute(
          """SELECT * FROM goat_alert_history
             WHERE ticker = ? AND source_table = ? AND check_name = ? AND acknowledged = 0
             ORDER BY created_at DESC LIMIT 1""",
          (ticker, source_table, check_name),
      ).fetchone()


  def insert_goat_alert(
      conn: sqlite3.Connection, *, ticker: str, source_table: str,
      check_name: str, severity: str, message: str,
  ) -> None:
      now = _now()
      with conn:
          conn.execute(
              """INSERT INTO goat_alert_history
                 (ticker, source_table, check_name, severity, message, created_at, acknowledged)
                 VALUES (?, ?, ?, ?, ?, ?, 0)""",
              (ticker, source_table, check_name, severity, message, now),
          )


  def acknowledge_goat_alert(conn: sqlite3.Connection, alert_id: int) -> None:
      with conn:
          conn.execute("UPDATE goat_alert_history SET acknowledged = 1 WHERE id = ?", (alert_id,))


  def get_open_goat_alerts(conn: sqlite3.Connection) -> list[sqlite3.Row]:
      return conn.execute(
          "SELECT * FROM goat_alert_history WHERE acknowledged = 0 ORDER BY created_at DESC"
      ).fetchall()
  ```
- **PATTERN**: `investments/my-trader/mytrader/db.py:60-69` (schema), `:305-342` (the four alert functions) — copied near-verbatim, table name swapped.
- **VALIDATE**: covered by `test_db.py` below.

### CREATE `investments/goat/goat/price_history.py`

- **IMPLEMENT**:
  ```python
  """Price history fetch for Goat's technical checks."""

  from __future__ import annotations

  from datetime import date, timedelta

  import pandas as pd


  def fetch_close_history(ticker: str, lookback_days: int) -> pd.Series | None:
      """Long-range daily close history for a single ticker. Mirrors
      mytrader.macro_indicators._yfinance_history_close -- ported rather than
      imported since that function is module-private to macro_indicators.py."""
      import yfinance as yf

      try:
          start = (date.today() - timedelta(days=lookback_days)).isoformat()
          hist = yf.Ticker(ticker).history(start=start, auto_adjust=True)
          if hist.empty:
              return None
          close = hist["Close"]
          if getattr(close.index, "tz", None) is not None:
              close.index = close.index.tz_localize(None)
          return close
      except Exception:
          return None
  ```
- **PATTERN**: `investments/my-trader/mytrader/macro_indicators.py:399-416` (`_yfinance_history_close`), functionally identical port.
- **GOTCHA**: ASX-listed holdings need `.AX` suffix handling for yfinance — check how `investments/my-trader/mytrader/tickers.py`'s `normalize()` and/or `crash_windows._fetch_close_series`'s ASX fallback logic handles this (referenced in the macro_indicators docstring at line 401-402: "simplified since futures/index tickers never need the .AX equity fallback... ASX-listed stocks" carries that fallback). **Read `investments/my-trader/mytrader/crash_windows.py`'s `_fetch_close_series` before implementing this function** — Goat's holdings include real ASX-listed stocks/ETFs (unlike gold's futures-only ticker), so the simplified gold version is NOT sufficient here; the ASX `.AX` fallback logic must be ported too, not just the futures-ticker happy path.
- **VALIDATE**: `python -c "from goat.price_history import fetch_close_history; s = fetch_close_history('AAPL', 400); print(len(s), s.iloc[-1])"` (real network call, manual sanity check only, not part of the automated suite).

### CREATE `investments/goat/goat/exit_check.py`

- **IMPLEMENT**: `check_150dma_exit(ticker: str, close: pd.Series) -> CheckResult`:
  1. If `len(close) < config.GOAT_MA_LONG_DAYS`, return `CheckResult(name="below_150dma", verdict="unknown", detail=f"{ticker}: insufficient price history for a {config.GOAT_MA_LONG_DAYS}-day MA")`.
  2. Compute `ma = close.rolling(config.GOAT_MA_LONG_DAYS).mean()`.
  3. Compute `pct_below = (ma - close) / ma * 100` (positive when price is below the MA) over the full aligned series, `.dropna()` to drop the leading NaN block.
  4. A day "qualifies" when `pct_below >= config.GOAT_150DMA_FLAG_PCT`.
  5. Check whether the **most recent `config.GOAT_150DMA_MIN_CONSECUTIVE_DAYS` days** (the tail of the qualifying boolean series) are *all* qualifying — i.e. `qualifies.tail(N).all()` where `N = config.GOAT_150DMA_MIN_CONSECUTIVE_DAYS` — this is the "flag now" condition, not "has this ever happened in history."
  6. If flagged: `CheckResult(name="below_150dma", verdict="flag", detail=f"{ticker}: closed {pct_below.iloc[-1]:.1f}% below its {config.GOAT_MA_LONG_DAYS}-day MA for {config.GOAT_150DMA_MIN_CONSECUTIVE_DAYS}+ consecutive days -- exit-rule threshold (Stage Analysis 6% envelope) triggered", data={"pct_below": ..., "ma": ..., "price": ...})`.
  7. Else: `CheckResult(name="below_150dma", verdict="ok", detail=f"{ticker}: {pct_below.iloc[-1]:.1f}% {'below' if pct_below.iloc[-1] > 0 else 'above'} its {config.GOAT_MA_LONG_DAYS}-day MA", data={...})`.
- **PATTERN**: `investments/my-trader/mytrader/macro_indicators.py:502-560`'s `check_gold_trend()` overall shape (fetch → compute → build `CheckResult` with `data` dict) — but note this is a **%-below-threshold-for-N-days** check, not a cross-detector, so the sign-flip cross-detection logic (lines 526-531) is NOT the right template for the core condition; only its general "vectorized pandas over the aligned series" style is relevant.
- **GOTCHA**: Use **daily close**, never intraday high/low — confirmed as the standard, less-noisy convention across every technical-analysis source found during research. `close` passed in is already the `Close` column from `price_history.fetch_close_history`, so this should be automatic as long as nothing upstream substitutes a different price field.
- **GOTCHA**: `pct_below.tail(N).all()` requires at least `N` non-NaN values to be meaningful — guard against a ticker with barely enough history to compute the MA at all (i.e. `len(close) >= config.GOAT_MA_LONG_DAYS + config.GOAT_150DMA_MIN_CONSECUTIVE_DAYS`, not just `>= GOAT_MA_LONG_DAYS`), otherwise `tail(2)` could silently include a NaN-adjacent boundary row and produce a wrong flag/no-flag call right at the edge of available history.
- **VALIDATE**: unit tests below.

### CREATE `investments/goat/goat/tests/__init__.py`

- **IMPLEMENT**: Empty file.

### CREATE `investments/goat/goat/tests/conftest.py`

- **IMPLEMENT**:
  ```python
  """Shared fixtures for goat tests."""

  from __future__ import annotations

  from pathlib import Path

  import pytest
  from scripts.db import get_connection, init_db

  from mytrader.db import init_mytrader_tables
  from goat.db import init_goat_tables


  @pytest.fixture
  def db_path(tmp_path) -> Path:
      return tmp_path / "test_investments.db"


  @pytest.fixture
  def db_conn(db_path):
      init_db(db_path)
      conn = get_connection(db_path)
      init_mytrader_tables(conn)
      init_goat_tables(conn)
      yield conn
      conn.close()


  @pytest.fixture(autouse=True)
  def _isolate_goat_report_path(monkeypatch, tmp_path):
      import goat.config as goat_config
      monkeypatch.setattr(goat_config, "GOAT_MONITOR_REPORT_PATH", tmp_path / "monitor-report.md")


  @pytest.fixture(autouse=True)
  def _no_real_price_history_fetch(monkeypatch):
      """Global stub so no test in this suite makes a real yfinance call by
      default -- same class of bug my-trader's conftest.py fixtures exist to
      prevent (see that file's docstrings for the real-corruption incident this
      pattern defends against). Individual tests override with monkeypatch as
      needed."""
      monkeypatch.setattr("goat.price_history.fetch_close_history", lambda ticker, lookback_days: None)
  ```
- **PATTERN**: `investments/my-trader/mytrader/tests/conftest.py:13-47` (fixture shapes) and its docstrings (lines 33-43) explaining *why* every one of these is autouse, not opt-in.
- **GOTCHA**: This is the single most important gotcha in the whole plan — **do not skip the autouse network/path-isolation fixtures "to save time," even though Phase 1 has far less surface area than my-trader**. The exact bug class (`_isolate_snapshot_paths`'s docstring) that corrupted real production files in this repo once already is trivially repeatable here if `GOAT_MONITOR_REPORT_PATH` isn't isolated from day one.
- **VALIDATE**: covered implicitly by every other test file importing these fixtures.

### CREATE `investments/goat/goat/tests/test_exit_check.py`

- **IMPLEMENT**: Build synthetic `pd.Series` price histories (e.g. `pd.date_range` index + constructed float lists, or `pd.Series(np.linspace(...))`) covering:
  1. Flat price exactly at the MA → `verdict == "ok"`.
  2. Price ≥6% below MA for exactly 2 consecutive days (today and yesterday) → `verdict == "flag"`.
  3. Price ≥6% below MA for only 1 day (today qualifies, yesterday didn't) → `verdict == "ok"` (whipsaw case — the exact scenario the source notes warn about).
  4. Price crossed 6% below 3 days ago but recovered above threshold yesterday and today → `verdict == "ok"` (confirms the check looks at the *current* tail state, not "ever happened").
  5. Insufficient history (`len(close) < 150`) → `verdict == "unknown"`.
- **PATTERN**: `investments/my-trader/mytrader/mytrader/tests/test_gold_technicals.py` and `test_macro_indicators.py` for synthetic-series construction conventions (check actual file for the idiom used, e.g. `pd.Series` with a `pd.date_range` index).
- **VALIDATE**: `uv run --directory investments/goat python -m pytest goat/tests/test_exit_check.py -v`

### CREATE `investments/goat/goat/tests/test_db.py`

- **IMPLEMENT**: Round-trip tests mirroring `investments/my-trader/mytrader/tests/test_db.py`'s alert-history section: insert → `get_open_goat_alert` finds it; acknowledge → `get_open_goat_alert` returns `None`; `get_open_goat_alerts` lists all unacknowledged rows across tickers.
- **PATTERN**: `investments/my-trader/mytrader/tests/test_db.py` (read the alert_history-specific tests before writing these — reuse the same structure).
- **VALIDATE**: `uv run --directory investments/goat python -m pytest goat/tests/test_db.py -v`

### CREATE `investments/goat/goat/monitor.py`

- **IMPLEMENT**:
  ```python
  """Goat Monitor -- scheduled daily 150DMA exit-rule check against every my-trader
  holding. Read-only against my-trader's holdings table; writes only to Goat's own
  goat_alert_history table and goat-monitor-report.md. Never touches my-trader's
  alert_history, monitor-report.md, holdings.md, or watchlist.md."""

  from __future__ import annotations

  import sqlite3
  from datetime import date
  from typing import Any

  from mytrader import db as mt_db
  from mytrader.checks import CheckResult

  from . import config, db, exit_check, price_history

  SEVERITY = "flag"
  SOURCE_TABLE = "holdings"


  def _reconcile_alerts(
      ticker: str, checks: list[CheckResult], conn: sqlite3.Connection
  ) -> list[dict[str, Any]]:
      new_alerts: list[dict[str, Any]] = []
      for check in checks:
          existing = db.get_open_goat_alert(conn, ticker, SOURCE_TABLE, check.name)
          if check.verdict == "flag":
              if existing is None:
                  db.insert_goat_alert(
                      conn, ticker=ticker, source_table=SOURCE_TABLE,
                      check_name=check.name, severity=SEVERITY, message=check.detail,
                  )
                  new_alerts.append({
                      "ticker": ticker, "source_table": SOURCE_TABLE,
                      "check_name": check.name, "message": check.detail,
                  })
          elif existing is not None:
              db.acknowledge_goat_alert(conn, existing["id"])
      return new_alerts


  def run_monitor(conn: sqlite3.Connection) -> dict[str, Any]:
      holdings = mt_db.get_all_holdings(conn)

      new_alerts: list[dict[str, Any]] = []
      checked = 0
      for row in holdings:
          ticker = row["ticker"]
          try:
              close = price_history.fetch_close_history(ticker, config.GOAT_MA_HISTORY_LOOKBACK_DAYS)
              if close is None:
                  print(f"[goat-monitor] no price history for {ticker}, skipping")
                  continue
              check = exit_check.check_150dma_exit(ticker, close)
              new_alerts.extend(_reconcile_alerts(ticker, [check], conn))
              checked += 1
          except Exception as e:
              print(f"[goat-monitor] error checking {ticker}: {e}")

      return {
          "checked_holdings": checked,
          "new_alerts": new_alerts,
          "open_alerts": [dict(a) for a in db.get_open_goat_alerts(conn)],
      }


  def render_report(result: dict[str, Any]) -> str:
      lines = [
          "# Goat Monitor Report",
          "",
          "Auto-generated by Goat Monitor -- overwritten every run. Advisor notes "
          "only; no trade action is ever suggested here (see SOUL.md).",
          "",
          f"## Run: {date.today().isoformat()}",
          f"Checked {result['checked_holdings']} holding(s) against the 150-day "
          "moving-average exit rule.",
          "",
          "### New Alerts This Run",
      ]
      if result["new_alerts"]:
          for a in result["new_alerts"]:
              lines.append(f"- **{a['ticker']}** -- {a['message']}")
      else:
          lines.append("No new material changes.")
      lines += ["", "### All Open Alerts"]
      if result["open_alerts"]:
          for a in result["open_alerts"]:
              lines.append(f"- **{a['ticker']}** -- {a['message']} (first flagged {a['created_at'][:10]})")
      else:
          lines.append("None.")
      lines += ["", f"Last auto-generated: {date.today().isoformat()}."]
      return "\n".join(lines) + "\n"


  def write_report(result: dict[str, Any]) -> None:
      config.GOAT_MONITOR_REPORT_PATH.write_text(render_report(result), encoding="utf-8")


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
          "Goat Monitor",
          f"{n} holding(s) below 150DMA exit threshold -- check investments/goat/monitor-report.md",
      )
  ```
- **PATTERN**: `investments/my-trader/mytrader/monitor.py` throughout (structure, not literal content — Goat's version is deliberately smaller: one check, holdings-only, no watchlist/opportunities/candidate-sync/gold-outlook sections).
- **GOTCHA** (verify before finalizing): confirm `Path(__file__).resolve().parent.parent.parent.parent` from `investments/goat/goat/monitor.py` actually lands at the repo root — run `python -c "from pathlib import Path; print(Path('investments/goat/goat/monitor.py').resolve().parent.parent.parent.parent)"` and compare against the repo root path. This mirrors `mytrader/monitor.py:226`'s hop count exactly (`investments/my-trader/mytrader/monitor.py` is the same depth as `investments/goat/goat/monitor.py`), but confirm directly rather than trusting the analogy — a wrong hop count fails silently (wrong `sys.path.insert`, `ImportError` on `notifications`) only when `new_alerts` is non-empty, which won't show up in most manual test runs.
- **VALIDATE**: covered by `test_monitor.py` below; hop-count check via the one-liner above.

### CREATE `investments/goat/goat/tests/test_monitor.py`

- **IMPLEMENT**: Mirror `investments/my-trader/mytrader/tests/test_monitor.py`'s shape:
  1. `test_run_monitor_creates_new_alert_for_first_flag` — seed a holding via `mt_db.upsert_holding(...)`, stub `goat.price_history.fetch_close_history` to return a synthetic series that trips the exit rule, assert `len(result["new_alerts"]) == 1` and `len(goat_db.get_open_goat_alerts(conn)) == 1`.
  2. `test_run_monitor_stays_quiet_on_repeat_flag` — run twice with the same flagging series, assert the second run's `new_alerts` is empty (dedup working).
  3. `test_run_monitor_auto_acknowledges_on_recovery` — flag once, then re-run with a non-flagging series, assert the open alert count drops to 0.
  4. `test_run_monitor_skips_ticker_with_no_price_history` — stub fetch to return `None` for one ticker among several, assert the run completes and `checked_holdings` excludes it, no exception propagates.
- **PATTERN**: `investments/my-trader/mytrader/tests/test_monitor.py:1-80` (`_seed_holding` helper, autouse fixture shape, assertion style).
- **VALIDATE**: `uv run --directory investments/goat python -m pytest goat/tests/test_monitor.py -v`

### CREATE `investments/goat/goat/main.py`

- **IMPLEMENT**:
  ```python
  """Unified CLI for Goat."""

  from __future__ import annotations

  import argparse


  def _open_conn():
      from scripts.db import get_connection, init_db

      from .config import DB_PATH
      from .db import init_goat_tables
      from mytrader.db import init_mytrader_tables

      init_db(DB_PATH)
      conn = get_connection(DB_PATH)
      init_mytrader_tables(conn)  # needed for get_all_holdings() to work against a fresh DB
      init_goat_tables(conn)
      return conn


  def cmd_monitor(args) -> None:
      from .monitor import maybe_notify, run_monitor, write_report

      conn = _open_conn()
      result = run_monitor(conn)
      conn.close()
      write_report(result)
      maybe_notify(result)
      print(
          f"Goat Monitor complete: {len(result['new_alerts'])} new alert(s), "
          f"{len(result['open_alerts'])} open. See investments/goat/monitor-report.md"
      )


  def main() -> None:
      parser = argparse.ArgumentParser(description="Goat -- sector-rotation + momentum tool")
      subparsers = parser.add_subparsers(dest="command")
      subparsers.add_parser("monitor", help="Daily 150DMA exit-rule check against all holdings")

      args = parser.parse_args()
      dispatch = {"monitor": cmd_monitor}
      if args.command in dispatch:
          dispatch[args.command](args)
      else:
          parser.print_help()


  if __name__ == "__main__":
      main()
  ```
- **PATTERN**: `investments/my-trader/mytrader/main.py:1-17` (`_open_conn`), `:238-346` (`cmd_monitor` + `main()` dispatch shape) — Goat's version is a strict subset (one subcommand only).
- **VALIDATE**: `uv run --directory investments/goat python -m goat.main monitor` — real run against the live shared DB (read-only against holdings, writes only to `goat_alert_history` + `investments/goat/monitor-report.md`). Confirm afterward via `git status` / `git diff` that no file under `investments/my-trader/` changed.

### CREATE `scripts/systemd/second-brain-goat-monitor.timer` and `.service`

- **IMPLEMENT**: Timer — identical shape to `second-brain-mytrader-monitor.timer`, same `OnCalendar` time or a few minutes after (avoid exact simultaneous start with my-trader's monitor — stagger by e.g. 5 minutes: `OnCalendar=*-*-* 21:35:00 UTC`) since both hit yfinance and the same SQLite file (WAL mode handles concurrent readers/writers, but staggering avoids unnecessary contention). Service — `WorkingDirectory=/home/secondbrain/second-brain/investments/goat`, `ExecStart=/home/secondbrain/second-brain/investments/.venv/bin/python -m goat.main monitor`, `StandardOutput=append:/home/secondbrain/second-brain/investments/goat/monitor_runs.log` (matching path pattern), `StandardError=` same.
- **PATTERN**: `scripts/systemd/second-brain-mytrader-monitor.timer` and `.service` (both full files, reproduced verbatim above in Context References).
- **GOTCHA**: **Do not enable/start this unit on the VPS as part of this implementation task.** Creating the unit files is in scope; deploying and `systemctl enable --now`-ing them on the live VPS is a separate, explicit action requiring Shaun's go-ahead per this project's own risk conventions (a scheduled unattended job hitting the shared production DB) — surface this as a manual follow-up step in the completion report, not an auto-deployed change.
- **VALIDATE**: `systemd-analyze verify scripts/systemd/second-brain-goat-monitor.service` if run on a machine with systemd available (otherwise, visual diff against the my-trader pair is sufficient at plan-execution time).

---

## TESTING STRATEGY

### Unit Tests

- `test_exit_check.py` — pure-function tests against synthetic `pd.Series`, no DB/network — the highest-value tests in this phase since the detector is the one genuinely new algorithm. Must cover: flag case, single-day-whipsaw non-flag case, recovered-then-flagged-earlier non-flag case, insufficient-history unknown case, and the exact threshold boundary (`pct_below == 6.0` exactly — confirm `>=` vs `>` behavior deliberately, matching whichever the implementation task picks).
- `test_db.py` — Goat's alert CRUD/dedup round-trip against a `tmp_path` DB.

### Integration Tests

- `test_monitor.py` — full `run_monitor()` round-trip against a `db_conn` fixture with a real (test-DB) holding row and a stubbed price-history fetch, covering the alert lifecycle (first flag → dedup on repeat → auto-acknowledge on recovery) end-to-end through `_reconcile_alerts`.

### Edge Cases

- Ticker with zero price history available (delisted/typo) → `verdict="unknown"`, run continues for other holdings.
- Holding present in `holdings` table more than once across different buckets (same ticker, different bucket — my-trader's `UNIQUE(ticker, bucket)` constraint allows this) → confirm Goat checks/alerts per (ticker, bucket) pair correctly and doesn't collapse or double-count; **decide during implementation** whether the alert dedup key should include bucket (my-trader's own `alert_history` dedup key is `(ticker, source_table, check_name)` — no bucket — so a ticker held in two buckets shares one alert row today; mirror that same behavior for consistency unless a reason emerges not to).
- Empty holdings table (fresh DB, nothing seeded yet) → `run_monitor` returns `checked_holdings: 0`, empty report, no error.
- A holding's price recovers to exactly the threshold boundary and hovers there run-to-run → confirm no alert-flapping (open→ack→open→ack every single day) — this is exactly what the 2-day consecutive requirement exists to dampen; a boundary-hugging synthetic series is a good stress test to add to `test_monitor.py` if time allows (not strictly required for Phase 1 sign-off, flag as a nice-to-have).

---

## VALIDATION COMMANDS

### Level 1: Syntax & Style

```powershell
uv run --directory investments/goat ruff check goat/
uv run --directory investments/goat mypy goat/
```

### Level 2: Unit Tests

```powershell
uv sync --directory investments/goat --extra dev
uv run --directory investments/goat python -m pytest -q
```

### Level 3: Integration Tests

Covered by `test_monitor.py` within the same `pytest -q` run above (this project doesn't separate unit/integration test commands elsewhere in the codebase — confirmed by my-trader's single `pytest -q` convention).

### Level 4: Manual Validation

```powershell
# Confirm the workspace resolves cleanly end-to-end from the root
uv sync --directory investments

# Real run against the live shared DB
uv run --directory investments/goat python -m goat.main monitor

# Confirm no my-trader files changed
git status investments/my-trader/
git diff investments/my-trader/

# Inspect the generated report
cat investments/goat/monitor-report.md
```

Confirm at least one holding's real 150DMA math looks sane by spot-checking against a chart (e.g. Yahoo Finance) for one or two tickers in `holdings.md` — the automated tests validate the algorithm against synthetic data, but a real-data sanity check catches unit/scaling mistakes synthetic tests can't (e.g. `pct_below` sign flipped, wrong rolling window).

### Level 5: Additional Validation

Not applicable — no MCP servers or additional CLI tooling relevant to this phase.

---

## ACCEPTANCE CRITERIA

- [ ] `investments/goat/` exists as a working uv workspace member; `uv sync --directory investments` succeeds from a clean checkout.
- [ ] `check_150dma_exit()` correctly implements: daily close input, ≥6% below 150-day MA, sustained for 2+ consecutive trading days, `unknown` verdict on insufficient history.
- [ ] `python -m goat.main monitor` runs end-to-end against the real shared DB: reads holdings (read-only), writes only to `goat_alert_history` and `investments/goat/monitor-report.md`.
- [ ] No my-trader file (`holdings.md`, `watchlist.md`, `monitor-report.md`, `alert_history` table, any `.py` file) is modified by any Goat code path.
- [ ] Alert dedup/auto-acknowledge lifecycle works: first flag creates one alert, repeat runs stay quiet, recovery auto-acknowledges, a later re-flag raises a fresh alert.
- [ ] All new thresholds (`GOAT_150DMA_FLAG_PCT`, `GOAT_150DMA_MIN_CONSECUTIVE_DAYS`) are documented in `config.py` with sourced rationale comments, matching the project's existing convention.
- [ ] Full test suite passes: `uv run --directory investments/goat python -m pytest -q`.
- [ ] `ruff check` and `mypy` pass clean.
- [ ] `investments/goat/HANDOFF.md`'s status line is updated to reflect Phase 1 completion.
- [ ] systemd unit files exist and are structurally correct but are **not** enabled on the VPS without a separate explicit confirmation from Shaun.

## COMPLETION CHECKLIST

- [ ] All tasks completed in order
- [ ] Each task's validation command passed immediately after that task
- [ ] Full test suite passes (unit + integration, single `pytest -q` run)
- [ ] `ruff check` / `mypy` clean
- [ ] Manual validation (`python -m goat.main monitor` against the real DB) confirms holdings are read correctly and no my-trader file is touched
- [ ] Acceptance criteria all met
- [ ] HANDOFF.md status line updated

---

## NOTES

**Why a separate `goat_alert_history` table instead of reusing my-trader's `alert_history`?** My-trader's `_reconcile_alerts` and its `alert_history` table are module-private/owned by my-trader's own Monitor loop; sharing the literal table would mean Goat's writes show up in my-trader's own `get_open_alerts()`/report rendering unexpectedly (a `source_table="holdings"` row from Goat would be indistinguishable from a my-trader-originated one without an additional discriminator column that doesn't exist today). A separate table keeps the "Goat writes only to its own tables" boundary the HANDOFF.md establishes for `pending_candidates`-equivalent staging, applied here to alerts too — cheap to add, avoids a schema migration on my-trader's existing table, and keeps the two packages' failure/ownership boundaries clean. If this proves annoying in practice (e.g. Shaun wants one unified alert view across both tools), a follow-up phase could add a small `UNION`-based read helper without changing either table's schema.

**150DMA threshold sourcing (researched 2026-08-11):** The source webinar notes give no number, only "reasonably below... sometimes prices break through it slightly but come back up above." Research found no single well-documented framework using exactly "150-day MA + reasonably below" as its stated rule. The closest documented analogue is Stan Weinstein's Stage Analysis, which uses a **6% lower envelope** below a security's long moving average (his own version uses a 30-week MA on broad market indices, not a 150-day MA on individual equities) as a breakdown/health threshold — cited via Bulkowski's "Weinstein Stops" writeup and TraderLion's Stage Analysis guide. Mark Minervini's Trend Template uses the 150/200-day MAs as entry filters, not an exit rule, and his own stop-loss guidance (5-8% below entry, or a break of the 50-day EMA) doesn't map onto "% below the 150DMA" either — not directly reusable. Standard whipsaw-avoidance practice across trend-following systems (StockCharts/SystemTrader) requires 2+ consecutive daily closes past a threshold before treating a moving-average violation as real, which matches the source notes' own explicit warning. **v1 rule, flagged as tunable, not literature-final**: close ≥6% below the 150-day MA, sustained for 2+ consecutive trading days. Revisit once Goat has run for a few months of real data — the threshold was designed around a 30-week/broad-index context, not a 150-day/individual-equity one, so it is a reasonable starting point rather than a validated constant.

**Scope boundary — what this plan explicitly does NOT build:** Phase 2 (11 SPDR sector ETF rotation ranking) and Phase 3 (S&P 500 heartbeat-pattern scanner) are out of scope, per Shaun's explicit confirmation (2026-08-11: "Phase 1" only for this plan, "then... do a feature plan on the same handoff" for later phases). When ready, running `/plan-feature` again against `investments/goat/HANDOFF.md` will produce the next plan — the workspace member, DB co-location pattern, and package structure this phase creates should make that plan meaningfully lighter (no re-litigating the reuse-vs-standalone or DB-location questions, both already resolved and now implemented).

**Deployment is scoped to "files exist," not "unit enabled."** Per this project's own "actions with care" conventions (an unattended scheduled job writing to the shared production DB is not a fully reversible/low-blast-radius action), the systemd timer/service files are created but not activated as part of this implementation — surface enabling them as an explicit next step for Shaun to approve separately, likely alongside a short observation period of manual `python -m goat.main monitor` runs first.

**Confidence Score: 8/10** for one-pass implementation success. The package-scaffolding, DB, monitor, and CLI layers are near-mechanical ports of a mature, well-tested sibling package with exact file:line references given throughout — low risk. The one piece with real implementation risk is `exit_check.py`'s consecutive-day-counting logic interacting correctly with `pandas`' NaN-handling at the history-length boundary (flagged explicitly as a GOTCHA above) and the ASX `.AX` ticker-suffix handling in `price_history.py` (flagged as needing a read of `crash_windows.py` before implementing, not just the simpler gold futures pattern) — these are the two spots most likely to need a debugging pass beyond the plan's literal instructions.
