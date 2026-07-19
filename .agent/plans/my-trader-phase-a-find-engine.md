# Feature: my-trader Phase A — Shared Assessment Engine + Conversational Find

The following plan should be complete, but it's important to validate documentation and
codebase patterns and task sanity before implementing. Pay special attention to naming
of existing utils, types, and models. Import from the right files.

This plan implements **Phase A only**, as scoped in
`investments/my-trader/tool-preplan.md` ("Phase A scope finalized 2026-07-19"). Phases B
(scheduled Monitor + alerting) and C (macro indicators + Briefs Finance ingest→candidate
data-flow) are explicitly out of scope here and get their own `/plan-feature` pass later.

## Feature Description

Shaun runs 5 businesses and wants a personal investing tool that does two things
eventually: (a) screen candidate stocks/ETFs/assets against his own criteria, and (b)
monitor current holdings and watchlist for changes worth knowing about. Phase A builds
the shared foundation both jobs will run on: a 7-check assessment engine, a database of
holdings/watchlist/alert-history (shared with the existing `briefs-finance` tool via a
uv workspace), and a conversational "Find" mode Shaun can invoke by just asking Claude
about a ticker in chat — mirroring how the existing `investments` skill already wraps
`briefs-finance`.

Phase A deliberately does **not** build Monitor (the scheduled/heartbeat-driven job) —
that's Phase B, reusing the same engine built here.

## User Story

As Shaun (multi-business founder building a personal investment tool)
I want to ask Claude "what do you think of TICKER" or "add TICKER to the watchlist" or
"I bought N shares of TICKER at $X" in chat
So that I get a structured assessment against my own criteria (plus Briefs Finance's
score as a secondary input) without doing the research by hand, and my holdings/watchlist
stay accurate without manual file editing

## Problem Statement

Today, `holdings.md` and `potential-holdings.md` in `investments/my-trader/` are
hand-maintained Markdown tables. Assessing a candidate ticker means manually
researching dividend trends, valuation, balance-sheet health, FX exposure, portfolio
concentration, sector/geopolitical risk, and ETF mechanics — one at a time, in
conversation, with no persistence or repeatability. There's also an existing,
working investment tool (`briefs-finance`) whose 0-100% likelihood scoring and ethical
filter should feed into this as a layered input, not be duplicated.

## Solution Statement

Build `investments/my-trader/` as its own uv project, joined into a new root-level uv
workspace alongside `investments/briefs-finance/` so my-trader can `import` (not
subprocess-call) briefs-finance's `db.py`, `config.py`, and `ethical_filter.py`
directly. Both projects share one SQLite database
(`investments/briefs-finance/data/investments.db`); my-trader adds three new tables
(`holdings`, `watchlist`, `alert_history`) to it. A single assessment engine runs 7
checks (dividend trend, valuation, balance sheet/leverage, FX exposure, portfolio
concentration incl. Berkshire overlap, sector/geopolitical risk, ETF mechanics) plus
pulls in briefs-finance's likelihood score when available. Find exposes this
conversationally with two distinct actions (ephemeral lookup vs. explicit
watchlist-add), and a snapshot module auto-regenerates `holdings.md` /
`potential-holdings.md` from the DB after every write so Shaun never edits them by hand
again.

## Feature Metadata

**Feature Type**: New Capability
**Estimated Complexity**: High (new cross-project packaging architecture + 7-check
domain engine + conversational CLI + DB migration), but scope is narrow (no scheduling,
no alerting, no macro indicators — those are Phase B/C)
**Primary Systems Affected**: `investments/briefs-finance/` (packaging changes only,
no behavior changes), new `investments/my-trader/` project, new root-level uv
workspace, new `.claude/skills/my-trader/` skill
**Dependencies**: `yfinance` (already used by briefs-finance), `uv` workspace feature
(installed version 0.11.8, confirmed working — see Gotchas), `hatchling` build backend
(new dependency, added to briefs-finance only)

---

## CONTEXT REFERENCES

### Relevant Codebase Files — READ THESE BEFORE IMPLEMENTING

- `investments/my-trader/tool-preplan.md` — the full, already-resolved spec this plan
  implements. Every "Confirmed 2026-07-19" bullet is a decision already made — don't
  re-litigate it. Re-read the "Phase A scope finalized" section at the bottom before
  starting.
- `investments/my-trader/holdings.md` — target output format for
  `snapshot.regenerate_holdings_md()`. Columns: Ticker, Name, Qty, Mkt Value, Avg
  Price, Unrealized P&L, Bucket.
- `investments/my-trader/potential-holdings.md` — target output format for
  `snapshot.regenerate_watchlist_md()`. Columns: Ticker, Name, Type, Bucket, Dividend,
  10Y Return, Status. Split conceptually into vetted (status='discussed') vs raw
  (status='raw') — see file structure.
- `investments/my-trader/investment-strategy.md` (lines 257-260) — "Companies must
  have the following" criteria (sustainable, competitive edge, pricing power) — Find's
  primary scoring basis per the preplan's "Find/scoring workflow" decision. Lines
  183-256 — leading-indicator checklist and geopolitical risk framing to source
  `checks/sector_risk.py`'s flashpoint map from.
- `investments/briefs-finance/scripts/config.py` (all) — pattern for path constants,
  `load_dotenv`, frozensets for exclusion lists (`DEFENSE_TICKERS`,
  `DEFENSE_REVIEW_TICKERS`). Mirror this shape for `mytrader/config.py`.
- `investments/briefs-finance/scripts/db.py` (all) — pattern for `get_connection()`
  (WAL mode, `Row` factory), `init_db()` using `executescript` with `CREATE TABLE IF
  NOT EXISTS`, `_now()` helper, upsert-by-natural-key functions. Mirror exactly for
  `mytrader/db.py`'s three new tables — call briefs-finance's `get_connection()`
  directly (same DB file), don't reinvent connection handling.
- `investments/briefs-finance/scripts/ethical_filter.py` (all, 21 lines) — import
  `check_ticker()` directly in `engine.py`; don't duplicate `DEFENSE_TICKERS`.
- `investments/briefs-finance/scripts/prices.py` (lines 61-64, `get_asx_fallback`) —
  pattern for ticker fallback-suffix retry; mirror in `mytrader/tickers.py`.
- `investments/briefs-finance/scripts/score.py` (lines 1-16, 43-74) — pattern for
  calling `sdk_compat` from a script two directory levels removed from
  `.claude/scripts/`: `_SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent.parent
  / ".claude" / "scripts"` then `sys.path.insert(0, str(_SCRIPTS_DIR))`. **Path depth
  differs for my-trader** — see Gotchas.
- `investments/briefs-finance/scripts/main.py` (all) — CLI dispatch pattern
  (`argparse` subparsers, one `cmd_*` function per subcommand, lazy imports inside each
  `cmd_*` to keep startup fast). Mirror for `mytrader/main.py`.
- `investments/briefs-finance/scripts/tests/conftest.py` (all) — `tmp_path`-based
  SQLite fixture pattern (`db_path`, `db_conn`, sample-row fixtures). Mirror for
  `mytrader/tests/conftest.py`.
- `investments/briefs-finance/pyproject.toml` (all, 48 lines) — dependency/tool-config
  shape to mirror for `mytrader`'s own `pyproject.toml`, and the file that gets a
  `[build-system]` block added (Task 1.2 below).
- `.claude/skills/investments/SKILL.md` (all) — the exact skill-file shape and
  conversational-trigger pattern to mirror for the new `.claude/skills/my-trader/SKILL.md`.
- `.claude/scripts/sdk_compat.py` — not used directly in Phase A (no LLM calls needed
  for the 7 checks — they're all numeric/rule-based). Briefs-finance's principles
  scoring (which does use it) is reused read-only via the shared DB, not re-invoked.

### New Files to Create

- `pyproject.toml` (repo root) — new uv workspace root, `[tool.uv.workspace]` only
- `investments/my-trader/pyproject.toml` — my-trader project manifest, depends on
  `briefs-finance` via `{ workspace = true }`
- `investments/my-trader/mytrader/__init__.py`
- `investments/my-trader/mytrader/config.py` — paths, thresholds, `BERKSHIRE_HOLDINGS`,
  `SECTOR_FLASHPOINTS` map
- `investments/my-trader/mytrader/tickers.py` — ticker normalization (share-class
  dots→dashes, `.AX` fallback)
- `investments/my-trader/mytrader/market_data.py` — yfinance fetch wrapper
  (`TickerData` dataclass: info, dividends, news, calendar)
- `investments/my-trader/mytrader/db.py` — `holdings` / `watchlist` / `alert_history`
  schema + CRUD, built on briefs-finance's `get_connection()`
- `investments/my-trader/mytrader/checks/__init__.py`
- `investments/my-trader/mytrader/checks/dividend.py`
- `investments/my-trader/mytrader/checks/valuation.py`
- `investments/my-trader/mytrader/checks/balance_sheet.py`
- `investments/my-trader/mytrader/checks/fx.py`
- `investments/my-trader/mytrader/checks/concentration.py`
- `investments/my-trader/mytrader/checks/sector_risk.py`
- `investments/my-trader/mytrader/checks/etf_mechanics.py`
- `investments/my-trader/mytrader/engine.py` — `run_assessment(ticker, conn) -> dict`,
  aggregates all 7 checks + ethical filter + briefs-finance score lookup
- `investments/my-trader/mytrader/find.py` — `lookup_ticker()` (ephemeral),
  `add_to_watchlist()` (persists)
- `investments/my-trader/mytrader/holdings_ops.py` — `add_or_update_holding()` (buy/
  sell/set), named to avoid clashing with the `holdings.md` filename
- `investments/my-trader/mytrader/snapshot.py` — `regenerate_holdings_md()`,
  `regenerate_watchlist_md()`, `regenerate_all()`
- `investments/my-trader/mytrader/seed.py` — one-time idempotent migration of the
  Confirmed So Far table into the DB
- `investments/my-trader/mytrader/main.py` — CLI dispatch
- `investments/my-trader/mytrader/tests/__init__.py`
- `investments/my-trader/mytrader/tests/conftest.py`
- `investments/my-trader/mytrader/tests/test_tickers.py`
- `investments/my-trader/mytrader/tests/test_db.py`
- `investments/my-trader/mytrader/tests/test_checks_dividend.py`
- `investments/my-trader/mytrader/tests/test_checks_valuation.py`
- `investments/my-trader/mytrader/tests/test_checks_balance_sheet.py`
- `investments/my-trader/mytrader/tests/test_checks_fx.py`
- `investments/my-trader/mytrader/tests/test_checks_concentration.py`
- `investments/my-trader/mytrader/tests/test_checks_sector_risk.py`
- `investments/my-trader/mytrader/tests/test_checks_etf_mechanics.py`
- `investments/my-trader/mytrader/tests/test_engine.py`
- `investments/my-trader/mytrader/tests/test_find.py`
- `investments/my-trader/mytrader/tests/test_holdings_ops.py`
- `investments/my-trader/mytrader/tests/test_snapshot.py`
- `investments/my-trader/mytrader/tests/test_seed.py`
- `.claude/skills/my-trader/SKILL.md` — conversational trigger mapping

### Files to Modify

- `investments/briefs-finance/pyproject.toml` — add `[build-system]` (hatchling) +
  `[tool.hatch.build.targets.wheel] packages = ["scripts"]` so it becomes
  workspace-importable. **No changes to its existing dependencies, tool configs, or
  behavior** — `cd investments/briefs-finance && uv run python -m scripts.main ...`
  continues to work identically after this change (verified — see Gotchas).

### Relevant Documentation

- [uv workspaces](https://docs.astral.sh/uv/concepts/projects/workspaces/) — general
  concept reference. **Verify current syntax against installed `uv 0.11.8` at build
  time** — the config shown in this plan (Task 1.1-1.3) was empirically tested against
  this exact installed version in a scratch sandbox and confirmed working (`uv sync`
  resolved both packages, `uv run python -m mytrader.main` successfully imported
  `proj-a`'s `scripts` package), so it should work as-is, but re-run `uv --version` at
  build time and diff against this plan if it differs.
- [yfinance](https://github.com/ranaroussi/yfinance) — `.info` dict fields used below
  (`debtToEquity`, `currentRatio`, `trailingPE`, `forwardPE`, `netExpenseRatio`,
  `quoteType`, `currency`, `sector`, `industry`), `.dividends` (pandas Series),
  `.calendar` (next earnings date), `.news` (list of dicts with `content` key) — all
  empirically verified against live tickers (VRTX, SCHD, HDV, BRK-B, PMGOLD.AX,
  AUDUSD=X) during planning. `.earnings_dates` requires `lxml` (not installed) — **do
  not use it**; `.calendar["Earnings Date"]` gives the next earnings date without the
  extra dependency and is sufficient for Phase A.

### Patterns to Follow

**Naming Conventions:**
- `snake_case` for all Python files/functions, matching briefs-finance throughout.
- Ticker values stored/queried uppercase (briefs-finance does `ticker.upper()`
  everywhere — mirror this in `mytrader/tickers.py::normalize()`).

**Error Handling:**
- yfinance network calls wrapped in broad `try/except Exception: return None` at the
  lowest level (see `prices.py` lines 22-30) — a single flaky ticker must not crash a
  batch assessment. Checks should return a `CheckResult(verdict="unknown", ...)` when
  underlying data is missing, never raise.

**DB Pattern:**
- `INSERT OR REPLACE` / natural-key existence check before insert — never blind
  `INSERT` (see `db.py` `upsert_report`, `upsert_outcome`). `holdings`/`watchlist`
  dedupe on `(ticker, bucket)` — same ticker can legitimately appear twice (PMGOLD
  core + PMGOLD tactical are two rows, same ticker, different bucket — see
  `tool-preplan.md` Bucket 3 discussion).

**CLI Pattern:**
- `argparse` subparsers, one `cmd_*` function per subcommand, imports of the actual
  logic module deferred to inside each `cmd_*` (see `briefs-finance/scripts/main.py`
  lines 9-15) — keeps `--help` fast and avoids importing yfinance/sqlite on every
  invocation.

**Testing Pattern:**
- `tmp_path`-backed SQLite fixtures (`conftest.py`), never touch the real
  `investments.db` in tests.
- **yfinance calls must be mocked in unit tests** — no test may hit the network.
  Pattern: `monkeypatch.setattr(mytrader.market_data, "fetch_ticker_data", lambda
  ticker: TickerData(info={...}, dividends=pd.Series(...), news=[], calendar={}))` or
  patch `yf.Ticker` directly with `unittest.mock.MagicMock` configured with `.info`,
  `.dividends` etc. as needed per test. briefs-finance's test suite doesn't hit
  network either (its yfinance calls are exercised only in Level 4 manual validation)
  — same discipline applies here.

---

## IMPLEMENTATION PLAN

### Phase 1: Foundation (workspace + schema)

Get the packaging/import boundary working end-to-end with trivial content before
writing any real logic — this is the highest-risk part of the plan (cross-project
import + shared venv relocation) and must be validated in the real repo before
building on top of it.

**Tasks:**
- Create root-level uv workspace, add `[build-system]` to briefs-finance
- Scaffold `investments/my-trader/` project skeleton, confirm `uv sync` +
  `uv run python -m mytrader.main` can import `scripts.db` from briefs-finance
- Build `mytrader/db.py` schema (3 new tables in the shared `investments.db`)

### Phase 2: Core Implementation (assessment engine)

**Tasks:**
- `tickers.py` normalization + `market_data.py` yfinance wrapper
- 7 check modules, each independently testable against mocked `TickerData`
- `engine.py` aggregator (checks + ethical filter + briefs-finance score lookup)

### Phase 3: Integration (conversational Find + snapshot + skill)

**Tasks:**
- `find.py` (ephemeral lookup vs. watchlist-add), `holdings_ops.py` (buy/sell/set)
- `snapshot.py` (DB → `holdings.md` / `potential-holdings.md` regeneration)
- `seed.py` (one-time Confirmed-So-Far migration)
- `main.py` CLI + `.claude/skills/my-trader/SKILL.md`

### Phase 4: Testing & Validation

**Tasks:**
- Unit tests for every module (mocked yfinance, tmp_path DB)
- Integration test: seed → find → snapshot round-trip against a temp DB
- Manual validation: live `find` call, then (with Shaun's explicit go-ahead) real
  `seed` run against the actual shared `investments.db`

---

## STEP-BY-STEP TASKS

Execute in order. Each task is atomic and independently testable.

### Task 1.1: CREATE root `pyproject.toml`

- **IMPLEMENT**: New file at repo root:
  ```toml
  [tool.uv.workspace]
  members = ["investments/briefs-finance", "investments/my-trader"]
  ```
- **PATTERN**: Empirically validated in scratch sandbox — a workspace root needs no
  `[project]` table, just `[tool.uv.workspace]`.
- **GOTCHA**: Do **not** add `investments/backtest` or `.claude/scripts` as members —
  the preplan's coupling decision is scoped to briefs-finance + my-trader only; those
  other two projects have their own independent dependency setups (`requirements.txt`
  and a standalone `pyproject.toml`/`uv.lock` respectively) and adding them would be
  unrequested scope creep with real risk of breaking their existing standalone usage.
- **GOTCHA**: Joining the workspace relocates the shared virtualenv to **repo root**
  `.venv/` (confirmed empirically — `uv sync` inside a workspace member creates
  `.venv` at the workspace root, not inside that member's directory). Briefs-finance's
  existing `investments/briefs-finance/.venv/` becomes orphaned dead weight after this
  — it is already gitignored via its own auto-generated `.venv/.gitignore` (contains
  `*`), so leaving it in place is harmless but wasteful; note it for Shaun to delete
  manually (do not `rm -rf` it yourself — destructive, and not required for
  correctness).
- **VALIDATE**: `Test-Path pyproject.toml` (PowerShell) — file exists at repo root.

### Task 1.2: UPDATE `investments/briefs-finance/pyproject.toml`

- **IMPLEMENT**: Add at the end of the file:
  ```toml
  [build-system]
  requires = ["hatchling"]
  build-backend = "hatchling.build"

  [tool.hatch.build.targets.wheel]
  packages = ["scripts"]
  ```
- **PATTERN**: This makes the existing `scripts/` directory (unchanged, no internal
  renames) installable as an editable workspace package whose import name is
  `scripts` — this is exactly what `mytrader` will import from.
- **GOTCHA — naming collision, already resolved by design**: my-trader's own package
  is deliberately named `mytrader/`, **not** `scripts/`, specifically to avoid a
  Python import-name collision with briefs-finance's `scripts` package once both are
  installed into the same shared workspace venv. Do not rename my-trader's package to
  `scripts` even though it would "match the convention" — confirmed via live test that
  two same-named installed packages in one workspace venv is the actual failure mode
  this design avoids.
- **VALIDATE**: No behavior change expected — confirm
  `cd investments/briefs-finance && uv run python -m scripts.main stats` still runs
  successfully after this edit (before Task 1.3's workspace sync even happens, since
  `[build-system]` alone doesn't change standalone `uv run` resolution).

### Task 1.3: CREATE `investments/my-trader/pyproject.toml`

- **IMPLEMENT**:
  ```toml
  [project]
  name = "my-trader"
  version = "0.1.0"
  requires-python = ">=3.12"
  dependencies = [
      "briefs-finance",
      "yfinance>=0.2.40",
      "requests>=2.31.0",
      "python-dotenv>=1.0.0",
      "pandas>=2.0.0",
  ]

  [tool.uv.sources]
  briefs-finance = { workspace = true }

  [project.optional-dependencies]
  dev = ["pytest>=8.0.0", "pytest-mock>=3.12.0", "ruff>=0.2.0", "mypy>=1.8.0"]

  [tool.pytest.ini_options]
  testpaths = ["mytrader/tests"]
  pythonpath = ["."]

  [tool.ruff]
  target-version = "py312"
  line-length = 100

  [tool.mypy]
  python_version = "3.12"
  ignore_missing_imports = true
  ```
- **PATTERN**: Mirrors `investments/briefs-finance/pyproject.toml` structure
  (`briefs-finance/pyproject.toml:1-48`) with the workspace dependency added.
- **VALIDATE**: `cd investments/my-trader; uv sync` — expect it to resolve both
  `my-trader` and (transitively) build+install `briefs-finance` from the workspace, no
  errors, no PyPI lookup for `briefs-finance` (confirm output shows `file://` source,
  not a registry).

### Task 1.4: CREATE `investments/my-trader/mytrader/__init__.py`

- **IMPLEMENT**: Empty file (package marker).
- **VALIDATE**: N/A — covered by Task 1.5's smoke test.

### Task 1.5: SMOKE TEST cross-project import before building real logic

- **IMPLEMENT**: Temporarily add a one-line `investments/my-trader/mytrader/main.py`:
  ```python
  import scripts.config as bf_config
  print(bf_config.DB_PATH)
  ```
- **VALIDATE**: `cd investments/my-trader; uv run python -m mytrader.main` — must
  print the absolute path to `investments/briefs-finance/data/investments.db`. **Do
  not proceed to Task 2.x until this passes** — it's the foundation every later task
  depends on. This file gets overwritten for real in Task 3.6; this task's content is
  disposable scaffolding.

### Task 2.1: CREATE `investments/my-trader/mytrader/config.py`

- **IMPLEMENT**: Path constants (mirror `briefs-finance/scripts/config.py:1-20`,
  importing `DB_PATH` from `scripts.config` rather than redefining it), plus:
  ```python
  BERKSHIRE_HOLDINGS: frozenset[str] = frozenset({
      # Manually maintained — update periodically from Berkshire's 13F filings
      # (quiverquant.com/insiders/berkshire-hathaway or cnbc.com/berkshire-hathaway-portfolio).
      # Last updated: 2026-07-19 (empty — populate before first real Find run).
  })
  SECTOR_FLASHPOINTS: dict[str, str] = {
      "Energy": "Strait of Hormuz / Middle East conflict — ~20M bbl/day transit risk",
      "Semiconductors": "Taiwan/China export-control risk (TSMC, ASML supply chain)",
  }
  DIVIDEND_CUT_THRESHOLD_PCT = -5.0   # TTM vs prior-12mo decline beyond this = "cut"
  PE_RICH_THRESHOLD = 35.0
  PE_CHEAP_THRESHOLD = 12.0
  DEBT_TO_EQUITY_FLAG = 150.0
  CURRENT_RATIO_FLAG = 1.0
  SECTOR_CONCENTRATION_FLAG_PCT = 25.0   # candidate's sector as % of holdings mkt value
  ```
- **IMPORTS**: `from scripts.config import DB_PATH` (cross-project, validated in Task
  1.5).
- **GOTCHA**: `BERKSHIRE_HOLDINGS` starts empty by design — the preplan notes
  Berkshire overlap-checking requires manual 13F research with no free API (yfinance
  doesn't expose 13F filings). Populating it is a manual data-entry step for Shaun,
  not something to fabricate. `checks/concentration.py` must handle the empty-set case
  by reporting `verdict="unknown"` for the Berkshire sub-check, not silently passing.
- **VALIDATE**: `cd investments/my-trader; uv run python -c "from mytrader.config import DB_PATH; print(DB_PATH)"`

### Task 2.2: CREATE `investments/my-trader/mytrader/tickers.py`

- **IMPLEMENT**:
  ```python
  SHARE_CLASS_MAP = {"BRK.B": "BRK-B", "BRK.A": "BRK-A"}

  def normalize(ticker: str) -> str:
      t = ticker.strip().upper()
      return SHARE_CLASS_MAP.get(t, t)

  def asx_variant(ticker: str) -> str:
      return normalize(ticker) + ".AX"
  ```
- **PATTERN**: Mirrors `briefs-finance/scripts/prices.py:61-64` (`get_asx_fallback`)
  but as a pure string function — the actual fallback-retry-on-empty-result logic
  lives in `market_data.py` (Task 2.3), which calls this.
- **GOTCHA**: yfinance requires `BRK-B` not `BRK.B` (verified live) — the "Confirmed
  So Far" table in `tool-preplan.md` uses `BRK.B` throughout; normalize at the
  DB-write boundary too (`find.py`, `holdings_ops.py`, `seed.py`) so stored tickers are
  yfinance-queryable directly without re-normalizing on every read.
- **VALIDATE**: `pytest mytrader/tests/test_tickers.py -v` (Task 4.x) —
  `normalize("BRK.B") == "BRK-B"`, `normalize("vrtx") == "VRTX"`.

### Task 2.3: CREATE `investments/my-trader/mytrader/market_data.py`

- **IMPLEMENT**: `TickerData` dataclass (`ticker`, `info: dict`, `dividends:
  pd.Series`, `news: list[dict]`, `calendar: dict`) and:
  ```python
  def fetch_ticker_data(ticker: str) -> TickerData | None:
      """Fetch yfinance data for a normalized ticker. Tries .AX fallback if the
      primary lookup returns no info. Returns None if both fail."""
  ```
  Also `fetch_fx_change_pct(base: str, quote: str = "AUD", period: str = "3mo") ->
  float | None` using `yf.Ticker(f"{quote}{base}=X").history(period=period)` (verified
  live with `AUDUSD=X`).
- **PATTERN**: Broad `try/except Exception: return None` around every yfinance call
  (mirrors `prices.py:22-30`).
- **GOTCHA**: `t.info` on an invalid/delisted ticker returns a near-empty dict rather
  than raising — check for a minimal required key (e.g. `"regularMarketPrice"` or
  `"quoteType"` present) to detect a real failure vs. a legitimately sparse result;
  don't rely on exceptions alone.
- **VALIDATE**: `pytest mytrader/tests/test_db.py -v` doesn't cover this — add a
  manual Level 4 check only (mocking a live network call in a unit test is explicitly
  disallowed per Testing Pattern above); unit tests for consumers of this module mock
  `fetch_ticker_data` entirely.

### Task 2.4: CREATE `investments/my-trader/mytrader/db.py`

- **IMPLEMENT**: Full schema:
  ```python
  from __future__ import annotations
  import sys
  from pathlib import Path

  _SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent.parent / ".claude" / "scripts"
  sys.path.insert(0, str(_SCRIPTS_DIR))
  from scripts.db import get_connection  # briefs-finance's shared DB connection

  def init_mytrader_tables(conn) -> None:
      with conn:
          conn.executescript("""
              CREATE TABLE IF NOT EXISTS holdings (
                  id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                  ticker              TEXT NOT NULL,
                  name                TEXT,
                  asset_type          TEXT NOT NULL,
                  bucket              TEXT NOT NULL,
                  qty                 REAL NOT NULL,
                  avg_price           REAL NOT NULL,
                  currency            TEXT,
                  last_expense_ratio  REAL,
                  last_checked_at     TEXT,
                  added_at            TEXT NOT NULL,
                  updated_at          TEXT NOT NULL,
                  UNIQUE(ticker, bucket)
              );
              CREATE TABLE IF NOT EXISTS watchlist (
                  id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                  ticker              TEXT NOT NULL,
                  name                TEXT,
                  asset_type          TEXT NOT NULL,
                  bucket              TEXT NOT NULL,
                  status              TEXT NOT NULL DEFAULT 'raw',
                  notes               TEXT,
                  source              TEXT NOT NULL DEFAULT 'manual',
                  last_expense_ratio  REAL,
                  last_checked_at     TEXT,
                  added_at            TEXT NOT NULL,
                  updated_at          TEXT NOT NULL,
                  UNIQUE(ticker, bucket)
              );
              CREATE TABLE IF NOT EXISTS alert_history (
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
  ```
  Plus CRUD: `upsert_holding()`, `upsert_watchlist_row()`, `delete_holding_if_zero()`,
  `get_all_holdings()`, `get_all_watchlist()`, `get_watchlist_row()`,
  `get_holding_row()` — all following the `db.py` upsert-by-natural-key pattern (Task
  2.4 pattern reference above).
- **PATTERN**: `briefs-finance/scripts/db.py:13-18` (`get_connection`), `:21-24`
  (`init_db` shape — but here it's `init_mytrader_tables(conn)` taking an existing
  connection rather than a path, since the connection is already opened against the
  shared DB by briefs-finance's own `get_connection()`).
  `briefs-finance/scripts/db.py:136-162` (`upsert_report`) for the upsert-by-natural-key
  shape — mirror for `upsert_holding`/`upsert_watchlist_row` keyed on `(ticker,
  bucket)`.
- **GOTCHA**: `_SCRIPTS_DIR` path depth is **different from briefs-finance's own**
  `score.py:12` (`parent.parent.parent.parent` = scripts→briefs-finance→investments→
  root, then `/.claude/scripts`). For `mytrader/db.py` at
  `investments/my-trader/mytrader/db.py`, the depth to repo root is the same
  (`mytrader→my-trader→investments→root`), so the same `parent.parent.parent.parent`
  expression is correct — but verify by printing `_SCRIPTS_DIR` and confirming it
  resolves to `.claude/scripts` before relying on it. (This sys.path insert is for
  reaching `.claude/scripts/sdk_compat.py` if ever needed later; Phase A's own checks
  don't need it — only included here for consistency/future-proofing if Phase B/C add
  LLM-scored checks. Skip this import entirely in Task 2.4 if nothing in Phase A
  actually calls `sdk_compat` — check before adding unused code.)
- **VALIDATE**: `pytest mytrader/tests/test_db.py -v`

### Task 2.5-2.11: CREATE the 7 check modules

Each follows the same shape — implement all 7 before `engine.py` (Task 2.12):

```python
@dataclass
class CheckResult:
    name: str
    verdict: str   # "ok" | "flag" | "info" | "unknown"
    detail: str
    data: dict
```

- **Task 2.5** `checks/dividend.py::check(data: TickerData) -> CheckResult` — sum
  `data.dividends` trailing 365 days vs. the prior 365-day window; verdict `"flag"` if
  decline beyond `config.DIVIDEND_CUT_THRESHOLD_PCT`, `"ok"` if growing, `"info"` if
  flat/no dividend history (empty series, e.g. VRTX — verified live, `.dividends`
  returns an empty Series, not an error).
- **Task 2.6** `checks/valuation.py::check(data) -> CheckResult` — `trailingPE`/
  `forwardPE` from `.info` vs. `config.PE_RICH_THRESHOLD` /
  `config.PE_CHEAP_THRESHOLD`; verdict `"unknown"` if PE missing (common for
  non-dividend/loss-making growth names — don't fabricate a verdict).
- **Task 2.7** `checks/balance_sheet.py::check(data) -> CheckResult` — `debtToEquity`
  vs. `config.DEBT_TO_EQUITY_FLAG`, `currentRatio` vs. `config.CURRENT_RATIO_FLAG`;
  flag if either breaches.
- **Task 2.8** `checks/fx.py::check(data) -> CheckResult` — `info.get("currency")`;
  if not `"AUD"`, call `market_data.fetch_fx_change_pct(currency)` and report as
  **`verdict="info"` always** (informational context per the preplan, not a pass/fail
  — see `tool-preplan.md` FX bullet).
- **Task 2.9** `checks/concentration.py::check(data, conn) -> CheckResult` — two
  sub-checks combined in one result's `data` dict: (a) `ticker in
  config.BERKSHIRE_HOLDINGS` (verdict `"unknown"` if `BERKSHIRE_HOLDINGS` is empty —
  see Task 2.1 gotcha), (b) query `mytrader.db.get_all_holdings()`, sum market value
  (`qty * avg_price`, same currency-naivety as the existing `holdings.md` snapshot —
  don't attempt FX-normalized aggregation in Phase A, that's a real gap worth flagging
  in Notes, not silently solving) grouped by `info.get("sector")`, flag if this
  candidate's sector already exceeds `config.SECTOR_CONCENTRATION_FLAG_PCT` of total
  holdings value.
- **Task 2.10** `checks/sector_risk.py::check(data) -> CheckResult` — look up
  `info.get("sector")` / `info.get("industry")` against `config.SECTOR_FLASHPOINTS`;
  verdict `"info"` if a match (informational per preplan framing), `"ok"` otherwise.
- **Task 2.11** `checks/etf_mechanics.py::check(data, existing_row: dict | None) ->
  CheckResult` — only meaningful if `info.get("quoteType") == "ETF"` (verified field
  name live); returns `verdict="unknown"` for non-ETFs. Reads `netExpenseRatio` +
  `category`; if `existing_row` (the DB row, which may carry `last_expense_ratio`) has
  a prior value and it differs, `verdict="flag"` ("expense ratio changed from X% to
  Y%"); if no prior value, `verdict="info"` ("baseline captured: X%") — **Phase A can
  only capture a baseline on first sight; true drift detection activates once Monitor
  (Phase B) runs repeatedly and this function is called again with a populated
  `existing_row`.**

- **GOTCHA (all 7)**: Every check must accept `data: TickerData | None` and return
  `CheckResult(verdict="unknown", detail="No market data available", data={})`
  immediately if `data is None` — `market_data.fetch_ticker_data()` can legitimately
  return `None` (Task 2.3), and checks must not assume it always succeeded.
- **VALIDATE** (each): `pytest mytrader/tests/test_checks_<name>.py -v` — construct a
  `TickerData` by hand with representative `.info`/`.dividends` values (no network),
  assert the expected verdict.

### Task 2.12: CREATE `investments/my-trader/mytrader/engine.py`

- **IMPLEMENT**:
  ```python
  def run_assessment(ticker: str, conn) -> dict:
      normalized = tickers.normalize(ticker)
      data = market_data.fetch_ticker_data(normalized)
      excluded, exclusion_reason = ethical_filter.check_ticker(normalized)  # from scripts.ethical_filter
      existing_row = db.get_holding_row(conn, normalized) or db.get_watchlist_row(conn, normalized)
      results = [
          dividend.check(data), valuation.check(data), balance_sheet.check(data),
          fx.check(data), concentration.check(data, conn), sector_risk.check(data),
          etf_mechanics.check(data, existing_row),
      ]
      briefs_score = _lookup_briefs_finance_score(normalized, conn)
      return {
          "ticker": normalized, "excluded": excluded, "exclusion_reason": exclusion_reason,
          "checks": results, "briefs_finance_score": briefs_score,
          "data_available": data is not None,
      }
  ```
  `_lookup_briefs_finance_score(ticker, conn)` — read-only query against
  briefs-finance's own `likelihood_scores` + `recommendations` tables (already
  imported via `scripts.db`'s connection, same DB file) filtered by ticker; return
  `None` if the ticker has no briefs-finance history — **do not** call
  `scripts.score.compute_score()` to force a fresh LLM-scored evaluation from Find;
  that's an expensive, network-calling side effect Find shouldn't trigger implicitly.
  Layering briefs-finance's score is read-only reuse of whatever already exists.
- **IMPORTS**: `from scripts.ethical_filter import check_ticker as ethical_check`
  (aliased — avoid shadowing `mytrader`'s own per-check `check()` functions).
- **PATTERN**: `briefs-finance/scripts/report.py:13-29` for the "gather from DB,
  return a flat dict" shape.
- **VALIDATE**: `pytest mytrader/tests/test_engine.py -v` — mock
  `market_data.fetch_ticker_data`, assert all 7 checks present in `results["checks"]`,
  assert `excluded=True` for a ticker in `DEFENSE_TICKERS` (e.g. `"LMT"`).

### Task 3.1: CREATE `investments/my-trader/mytrader/find.py`

- **IMPLEMENT**: `lookup_ticker(ticker: str, conn) -> dict` — thin wrapper around
  `engine.run_assessment()`, writes nothing. `add_to_watchlist(ticker: str, name: str,
  asset_type: str, bucket: str, notes: str, conn) -> None` — normalizes ticker,
  `db.upsert_watchlist_row(..., status="discussed", source="manual")`, then calls
  `snapshot.regenerate_all(conn)`.
- **GOTCHA**: `status="discussed"` is the default for anything added via explicit
  `add_to_watchlist` (a human chose to track it) — `status="raw"` is reserved for
  future Phase C's Briefs Finance auto-ingest flow (out of scope here, but the column
  exists now per the preplan's schema requirement — don't write `"raw"` from this
  Phase A code path).
- **VALIDATE**: `pytest mytrader/tests/test_find.py -v`

### Task 3.2: CREATE `investments/my-trader/mytrader/holdings_ops.py`

- **IMPLEMENT**: `add_or_update_holding(ticker, bucket, qty_delta, price, action, conn)`
  — `action="buy"`: if existing `(ticker, bucket)` row, compute new weighted-average
  price (`(old_qty*old_avg + qty_delta*price) / (old_qty+qty_delta)`), else insert new
  row; `action="sell"`: subtract `qty_delta`, delete the row if resulting qty rounds to
  ~0 (use a small epsilon, e.g. `< 1e-6`, given fractional-share holdings like LLY's
  `0.0001`); calls `snapshot.regenerate_all(conn)` at the end either way.
- **GOTCHA**: `holdings.md` shows fractional share quantities down to 4 decimal places
  (LLY: `0.0001`) — don't round qty/avg_price to fewer decimals than the source data
  needs; store as `REAL` and format at snapshot-render time only.
- **VALIDATE**: `pytest mytrader/tests/test_holdings_ops.py -v` — buy-then-buy
  produces correct weighted average; sell-to-zero removes the row.

### Task 3.3: CREATE `investments/my-trader/mytrader/snapshot.py`

- **IMPLEMENT**: `regenerate_holdings_md(conn)` — read `db.get_all_holdings()`, render
  a Markdown table matching `holdings.md`'s exact column order/header, write to
  `investments/my-trader/holdings.md`. `regenerate_watchlist_md(conn)` — read
  `db.get_all_watchlist()`, render matching `potential-holdings.md`'s columns, write
  to `investments/my-trader/potential-holdings.md`. `regenerate_all(conn)` calls both.
- **PATTERN**: Read `holdings.md` and `potential-holdings.md` (already read in full
  during planning — see Context References) for the exact target Markdown shape,
  including the explanatory note line at the top of each file and the "Last
  [auto-]updated: YYYY-MM-DD" footer — update that footer text from "Last manually
  updated" to "Last auto-generated" once the tool takes over, per the preplan's "data
  source of truth" decision.
- **GOTCHA**: Overwrites the file entirely each run (matches the preplan's "the tool
  auto-regenerates... never hand-synced" decision) — this is intentionally
  destructive to manual edits from this point forward. Don't diff-merge; full
  overwrite is correct per spec.
- **VALIDATE**: `pytest mytrader/tests/test_snapshot.py -v` — seed a tmp DB with known
  rows, regenerate into a `tmp_path` file, assert exact Markdown output.

### Task 3.4: CREATE `investments/my-trader/mytrader/seed.py`

- **IMPLEMENT**: `seed_confirmed_holdings(conn)` — idempotent (check `db.get_holding_row`/
  `get_watchlist_row` before each insert, skip if present) inserts:
  - Holdings (from `holdings.md`, Task Context data): LLY (bucket 1, qty 0.0001, avg
    1148.00), LYV (bucket 1, qty 0.4, avg 167.29), V (bucket 1, qty 0.1001, avg
    318.41).
  - Watchlist (from `tool-preplan.md` Confirmed So Far table, `status="discussed"`):
    VRTX (bucket 1), PMGOLD core (bucket 3a), PMGOLD tactical (bucket 3b), BRK.B
    (bucket 1, store normalized as `BRK-B` per Task 2.2), HDV (bucket 1), SCHD (bucket
    1), ASML (bucket 1).
  Calls `snapshot.regenerate_all(conn)` at the end.
- **GOTCHA — do not run this against the real shared DB automatically.** This task's
  code should be written and unit-tested against a `tmp_path` DB (Task 4.x). Running
  it for real against `investments/briefs-finance/data/investments.db` is a Level 4
  manual-validation step requiring Shaun's explicit go-ahead (it's the first write
  ever made to shared production data from this new tool) — see Validation Commands,
  Level 4.
- **VALIDATE**: `pytest mytrader/tests/test_seed.py -v` — running `seed_confirmed_holdings`
  twice against the same tmp DB produces no duplicate rows.

### Task 3.5: CREATE `investments/my-trader/mytrader/main.py`

- **IMPLEMENT**: Replace the Task 1.5 smoke-test stub with real CLI dispatch:
  ```
  uv run python -m mytrader.main find --ticker VRTX
  uv run python -m mytrader.main watchlist-add --ticker VRTX --name "..." --asset-type stock --bucket 1 --notes "..."
  uv run python -m mytrader.main holding-buy --ticker V --bucket 1 --qty 0.1 --price 340
  uv run python -m mytrader.main holding-sell --ticker V --bucket 1 --qty 0.05 --price 350
  uv run python -m mytrader.main snapshot
  uv run python -m mytrader.main seed
  ```
- **PATTERN**: `briefs-finance/scripts/main.py:110-179` (`argparse` subparsers +
  dispatch dict).
- **VALIDATE**: `cd investments/my-trader; uv run python -m mytrader.main --help`
  lists all 6 subcommands.

### Task 3.6: CREATE `.claude/skills/my-trader/SKILL.md`

- **IMPLEMENT**: Mirror `.claude/skills/investments/SKILL.md` structure exactly
  (frontmatter with `name`/`description` + trigger phrases, "Quick Reference" `uv run`
  command block, "Key Paths" section). Trigger phrases: "check TICKER", "what do you
  think of TICKER", "add TICKER to watchlist", "I bought/sold N shares of TICKER",
  "show my holdings", "my-trader". Description must clarify this is **distinct** from
  the existing `investments` skill (briefs-finance) — Find layers briefs-finance's
  score in as one input among several, it doesn't replace that skill.
- **PATTERN**: `.claude/skills/investments/SKILL.md:1-91` (full file, already read).
- **VALIDATE**: Skill triggers correctly on a test phrase like "check VRTX" in a fresh
  session (manual — skills aren't unit-testable).

---

## TESTING STRATEGY

### Unit Tests

Every module in `mytrader/` gets a corresponding `test_*.py`. All yfinance calls
mocked (no network in unit tests — see Testing Pattern above). DB tests use
`tmp_path`-backed SQLite via `conftest.py`, never the real shared DB.

### Integration Tests

One test (`test_seed.py` extended, or a new `test_integration_roundtrip.py`) that:
seeds a tmp DB via `seed_confirmed_holdings()`, calls `find.lookup_ticker()` on a
seeded ticker with mocked market data, calls `snapshot.regenerate_all()`, and asserts
the resulting Markdown files match expected structure. This is the closest thing to an
end-to-end check without hitting real yfinance/OpenAI-style network calls.

### Edge Cases

- Ticker with no dividend history (VRTX — verified empty `.dividends` Series live).
- Ticker with missing PE (loss-making or data-sparse names) — must not crash
  `valuation.check`.
- ASX-suffixed ticker requiring `.AX` fallback (PMGOLD).
- Share-class ticker requiring dot→dash normalization (BRK.B → BRK-B).
- Same ticker in two buckets simultaneously (PMGOLD core + tactical) — `(ticker,
  bucket)` uniqueness must allow this, not collide.
- Selling a holding down to (near-)zero — row must be removed, not left as a
  zero-qty row `holdings.md` would render as a phantom line.
- `add_to_watchlist` called twice for the same `(ticker, bucket)` — must update, not
  duplicate (upsert-by-natural-key).
- Empty `BERKSHIRE_HOLDINGS` config — concentration check must report `"unknown"`,
  not silently claim "no overlap".

---

## VALIDATION COMMANDS

### Level 1: Syntax & Style

```powershell
cd investments/my-trader
uv run ruff check .
uv run mypy mytrader
cd ../briefs-finance
uv run ruff check .   # confirm Task 1.2's pyproject.toml edit didn't break existing lint config
```

### Level 2: Unit Tests

```powershell
cd investments/my-trader
uv run pytest mytrader/tests -v
```

### Level 3: Integration Tests

```powershell
cd investments/my-trader
uv run pytest mytrader/tests/test_seed.py mytrader/tests/test_snapshot.py -v
```

### Level 4: Manual Validation

1. `cd investments/my-trader; uv run python -m mytrader.main find --ticker VRTX` —
   real live yfinance call, eyeball the 7 check results for sanity (no exceptions, no
   `"unknown"` verdicts where data should clearly be available).
2. **Confirm with Shaun before this step** — it's the first write to the shared
   production DB: `cd investments/my-trader; uv run python -m mytrader.main seed`,
   then inspect the regenerated `investments/my-trader/holdings.md` and
   `potential-holdings.md` against their pre-tool manually-maintained versions (diff
   should show only cosmetic formatting/footer changes, same data).
3. In a fresh Claude Code session, say "check VRTX" and confirm the `my-trader` skill
   triggers and returns a sensible conversational summary (not raw JSON dumped to
   chat).

### Level 5: Additional Validation

N/A for Phase A (no MCP servers or external CLI tools involved beyond `uv`/`pytest`/
`ruff`/`mypy`, all already covered above).

---

## ACCEPTANCE CRITERIA

- [ ] Root-level uv workspace exists; `investments/briefs-finance` and
      `investments/my-trader` are both members
- [ ] `cd investments/briefs-finance && uv run python -m scripts.main stats` still
      works identically post-migration (no regression)
- [ ] `mytrader` can `import scripts.db` / `scripts.config` / `scripts.ethical_filter`
      from briefs-finance without subprocess calls
- [ ] `holdings`, `watchlist`, `alert_history` tables exist in the shared
      `investments.db`
- [ ] All 7 assessment checks implemented, unit-tested, and aggregated in
      `engine.run_assessment()`
- [ ] `engine.run_assessment()` includes briefs-finance's likelihood score when
      available, `None` when not, and never triggers a fresh LLM scoring call as a
      side effect
- [ ] Ethical filter (defense/military exclusion) applied to every assessment
- [ ] `find.lookup_ticker()` is read-only (ephemeral); `find.add_to_watchlist()`
      persists and regenerates snapshots
- [ ] `holdings_ops.add_or_update_holding()` handles buy/sell correctly including
      weighted-average-price recomputation and zero-qty row removal
- [ ] `snapshot.regenerate_all()` produces `holdings.md`/`potential-holdings.md`
      matching their existing target format
- [ ] `seed.seed_confirmed_holdings()` is idempotent and, once run for real (Level 4,
      Shaun's go-ahead obtained), correctly migrates the Confirmed So Far table into
      the DB
- [ ] `.claude/skills/my-trader/SKILL.md` exists and triggers conversationally
- [ ] All validation commands (Levels 1-3) pass with zero errors
- [ ] No regressions in `investments/briefs-finance`'s existing test suite or CLI

---

## COMPLETION CHECKLIST

- [ ] All tasks completed in order (Task 1.5's smoke test gate respected before
      proceeding to Phase 2)
- [ ] Each task's validation command passed immediately after that task
- [ ] Full `mytrader` test suite passes
- [ ] `ruff`/`mypy` clean on both `my-trader` and `briefs-finance`
- [ ] Level 4 manual validation completed, including the Shaun-confirmed real `seed`
      run
- [ ] Acceptance criteria all met
- [ ] `investments/my-trader/handoff.md` updated to reflect Phase A completion (not a
      build task per se, but don't leave it stale — it currently says "Tool design
      itself — nothing started")

---

## NOTES

**Known limitations accepted for Phase A (not blockers, documented for later):**
- `checks/concentration.py`'s portfolio-value aggregation is currency-naive (sums
  `qty * avg_price` across USD/AUD holdings without FX normalization) — matches the
  existing hand-maintained `holdings.md`'s own naivety, not a regression, but a real
  gap worth fixing eventually (possibly Phase C, alongside the FX check).
- `BERKSHIRE_HOLDINGS` starts empty — no free API exists for 13F data; this is
  inherently a manually-maintained list until/unless a paid data source is added
  later. Flagged clearly in code and config so it fails loud (`"unknown"` verdict)
  rather than silently wrong.
- `checks/etf_mechanics.py` can only detect expense-ratio *drift* once there are two
  data points for the same ticker — Phase A captures the first baseline; real drift
  detection is a natural Phase B side effect once Monitor runs repeatedly, not
  something Phase A needs to simulate.
- Numeric thresholds in `config.py` (PE bands, debt/equity, concentration %) are
  reasonable starting defaults, explicitly flagged by the preplan as "implementation
  detail... not decided here" — expect Shaun to tune these after seeing real output,
  not treat them as final.

**Confidence score: 8/10** for one-pass implementation success. The two biggest risks
were the uv workspace cross-project import (collision risk + venv relocation) and
yfinance field availability for the 7 checks — both were empirically validated live
against the real installed `uv 0.11.8` and real tickers during planning, not assumed
from training knowledge. Remaining risk is mostly in the volume of near-identical
boilerplate (7 check modules, ~19 test files) where a single execution pass could
introduce small inconsistencies — recommend the execution agent implement and validate
one check module fully (Task 2.5) before batch-producing the remaining six, to lock in
the pattern.
