# Feature: Fourteen Crash Signals Daily Check — Phase 1 (Core Package + 4 Ready-Now Markers)

The following plan should be complete, but it's important to validate documentation and
codebase patterns and task sanity before implementing. Pay special attention to naming of
existing utils/types/models. Import from the right files.

**This is Plan 1 of a multi-plan roadmap.** The source handoff
(`investments/my-trader/14-signals-crash-warning-handoff.md`) covers all 14 markers, but
only 4 of them plus the shared sector-detection layer are ready to build today without
further source-hunting. See "NOTES — How to create Phase 2 / Phase 3" at the end of this
document for exactly how the remaining markers get planned once this phase ships.

## Feature Description

A new standalone daily-check tool that tracks a subset of the "14-signal crash warning
framework" (per a fact-checked YouTube transcript analysis, see the handoff doc) — dated
markers that preceded both the 2000 NASDAQ top and the 2007 S&P top, now mostly re-firing
around the AI/hyperscaler buildup. This phase builds the package scaffold, a shared
"currently hot sector/company" detection layer every per-issuer marker will eventually read
from, and the 4 markers that have a confirmed, free, programmatically-fetchable data source
today:

- **#14 High-yield credit spread streak** ("the master signal") — FRED `BAMLH0A0HYM2`,
  flags when the spread has closed at/above 3.5% for a sustained ~month.
- **#5 Margin debt YoY growth** — FINRA's own published margin statistics spreadsheet,
  flags extreme YoY growth (the video's own framing: "last seen at the peaks of 2000, 2007,
  and 2021").
- **#8 Insider selling — aggregate 365-day trend** — reuses Goat's existing OpenInsider
  scraper, aggregated (not per-filing like Goat's own holdings-watch) against the new
  dynamic hot-company watchlist below.
- **#10 Most-valuable-company milestone** — tracks the single largest-market-cap S&P 500
  company and flags when it crosses a new round-number market-cap threshold.

Every other marker (1–4 excl. handled above, 6, 7, 9, 11–13) is rendered in the combined
report as "not yet automated" in this phase — never silently dropped, per the handoff's own
"none of the 14 are being written off as manual-only going in" framing.

## User Story

As Shaun (multi-business founder managing his own portfolio)
I want a daily automated check of the crash-warning signals that are cheap and reliable to
automate today, with a shared "what's currently hot" detection layer that the harder,
per-issuer signals can plug into later
So that I get real signal now on the easy 4, without waiting for the harder 10 to be
source-researched and built, and without the tool ever hardcoding today's AI/hyperscaler
names as a permanent assumption

## Problem Statement

The handoff (`14-signals-crash-warning-handoff.md`) fact-checked a 14-marker framework and
resolved every open design question with Shaun across two rounds of discussion, but nothing
has been built yet. Building all 14 in one pass is not realistic: 6 of the markers ("debt
issuance," "vendor financing," "IPO volume," "retail/leveraged ETF flows," "regulator
warnings," "funding-market stress") have no confirmed free structured data source — that's
a research task to run *during* a later build, not something specifiable today.

## Solution Statement

Stand up a new sibling package (`investments/fourteen-crash-signals-daily-check/`,
following the exact `goat`/`my-trader`/`briefs-finance` uv-workspace pattern) with:
1. A **hot-company watchlist layer** (`watchlist.py`) built entirely from existing, already-
   built Goat code (`sector_rotation.rank_sectors` + `sp500_universe`'s cached S&P 500
   constituent/GICS-sector table), ranked by market cap so it resolves to today's actual
   mega-cap AI names without hardcoding a single ticker.
2. Four marker-check modules, each reusing an existing data-fetch pattern from elsewhere in
   this codebase (FRED via `briefs-finance/scripts/macro.py`, XLSX-via-`openpyxl` via
   `mytrader/abs_cpi.py`'s exact shape, OpenInsider via `goat/openinsider.py`, and the
   already-cached S&P 500 universe for market-cap ranking).
3. A combined report (all 14 rows, 4 live + 10 "not yet automated") and a daily WhatsApp
   alert that only fires on a signal's **transition** into a firing state (not a daily dump).
4. A new daily systemd timer, following the exact deployment shape used for
   `second-brain-goat-insider-scan.timer`.

## Feature Metadata

**Feature Type**: New Capability (new package)
**Estimated Complexity**: High (new package scaffold + 4 independent external data
integrations + one shared cross-cutting detection layer), scoped down from the full
14-marker ask to keep this specific plan's task list independently executable in one pass.
**Primary Systems Affected**: New `investments/fourteen-crash-signals-daily-check/` package;
additive-only changes to `investments/goat/goat/openinsider.py` (new optional param) and
`investments/goat/goat/pyproject.toml` (new `[build-system]` section — see Task 2 GOTCHA);
`investments/pyproject.toml` (new workspace member); `investments/TOOLS.md` and
`scripts/deploy.ps1` (documentation/ops housekeeping).
**Dependencies**: `requests`, `openpyxl` (both already transitively available via the
`my-trader` workspace dependency, same as `goat/sp500_universe.py` uses `requests` +
`beautifulsoup4` without declaring them). No genuinely new third-party dependency.

---

## Design Decisions

### Carried over from the handoff (already resolved with Shaun, 2026-08-18)

- Standalone tool, own report, own schedule — not folded into my-trader's Monitor.
- No scoring/recommended-action — reports where each signal stands, alerts on new firing,
  Shaun decides what to do himself.
- Runs daily on the VPS (systemd), report syncs back to the vault via the existing git
  vault-sync mechanism — no new sync mechanism needed.
- Sector-detection is a shared layer every per-issuer marker reads from, refreshed on an
  ongoing basis, never hardcoded to today's AI names.
- Alerting: daily WhatsApp push, short summary + explicit clause only when something is
  *newly* firing. Full 14-row report written every run regardless.

### New decisions this plan resolves (flagged so Shaun can override before `/execute`)

1. **Hot-company watchlist mechanism** (the single biggest open item from the handoff).
   Goat already computes "which of the 11 SPDR sectors are rising" (`sector_rotation.
   rank_sectors`) and already caches the full S&P 500 constituent list with GICS sector
   (`sp500_universe`, `goat_sp500_constituents` table, refreshed weekly). Neither of those
   two, by itself, produces a *concentrated* list of ~8 mega-cap names — "Technology is
   rising" still covers hundreds of S&P 500 names. **Proposed mechanism**: take the S&P 500
   constituents whose GICS sector maps to a currently-rising SPDR sector (exact reuse of
   `heartbeat_scan.py`'s own filter, lines 28-35), fetch each one's market cap via
   `mytrader.market_data.fetch_ticker_data(ticker).info["marketCap"]`, keep only those
   above `SIGNALS_HOT_WATCHLIST_MIN_MARKET_CAP` ($100B — mega-cap floor, keeps this a
   concentrated "who's driving this cycle" list, not a broad sector scan), and take the top
   `SIGNALS_HOT_WATCHLIST_TOP_N` (8) by market cap. Run today, this resolves to
   Nvidia/Microsoft/Meta/Alphabet/Amazon/Oracle-class names without a single hardcoded
   ticker. **v1/tunable, not literature-final** — same status as `GOAT_SECTOR_RANK_WINDOW_
   TRADING_DAYS` — flag for Shaun to sanity-check against the actual output once built
   (Task 12's manual validation step), not something to silently trust.
2. **Marker 14's streak check is new, separate code from the existing `mytrader.
   macro_indicators.check_credit_spreads`.** That existing function (reused verbatim by
   `investment-strategy.md`'s tracking) is a single-day, single-threshold (5.0pp) check for
   a different consumer. This tool's marker 14 needs a *duration* condition (≥3.5% held for
   ~a month) that function doesn't compute. Both checks coexist deliberately, reading the
   same underlying FRED series via the same low-level `fred_series_range`/
   `fred_observation_on` helpers — this is not a duplicate to consolidate, it's two
   different questions against the same data.
3. **Marker 8's numeric "aggregate net-selling" threshold** isn't specified in the handoff
   beyond the shape ("sum sale value vs. purchase value over a trailing 365-day window").
   Proposed: flag a hot-watchlist ticker when trailing-365-day sale value ≥
   `SIGNALS_INSIDER_TREND_NET_SELL_FLAG_RATIO` (3.0) × purchase value over the same window.
   v1/tunable, flagged for Shaun to revisit once he sees real output.
4. **Package name**: directory `investments/fourteen-crash-signals-daily-check/` (Shaun's
   name, spelled out — a bare `14-...` directory would still be a valid path, but the
   Python package inside cannot start with a digit). Python package/import name:
   `fourteen_crash_signals_daily_check` (underscores, valid identifier, used in `pyproject.
   toml`'s `[tool.hatch.build.targets.wheel] packages = [...]`, every internal `from . import
   config` stays relative so this long name is only spelled out in a handful of places —
   `pyproject.toml`, `__init__.py`'s parent references, the systemd `ExecStart` line, and
   `TOOLS.md`).

---

## CONTEXT REFERENCES

### Relevant Codebase Files — READ THESE BEFORE IMPLEMENTING

- `investments/goat/goat/sector_rotation.py` (whole file, 113 lines) — Why: `rank_sectors`
  (lines 30-50) is the exact "which of the 11 SPDR sectors are rising" function to reuse
  as-is (import from `goat.sector_rotation`, do not reimplement); `fetch_all_sector_closes`
  (lines 17-27) is its required input.
- `investments/goat/goat/heartbeat_scan.py` (whole file, 117 lines) — Why: lines 21-35 are
  the *exact* filter (`rank_sectors` → `rising_etf_labels` → filter cached S&P 500
  constituents by `GOAT_GICS_TO_ETF_SECTOR_LABEL`) this plan's `watchlist.py` must mirror,
  before adding the new market-cap ranking step on top.
- `investments/goat/goat/sp500_universe.py` (whole file, 80 lines) — Why:
  `get_or_refresh_sp500_constituents` (lines 60-79) is the cached S&P 500 constituent
  source `watchlist.py` reads from — do not re-scrape Wikipedia independently, this tool
  reads Goat's existing weekly-refreshed cache.
- `investments/goat/goat/db.py` (whole file, 224 lines) — Why: `init_goat_tables` (lines
  15-73, including the two `ALTER TABLE` migration blocks at 60-73) is the exact
  `CREATE TABLE IF NOT EXISTS` + idempotent-migration idiom to mirror in this package's own
  `db.py`; `insert_goat_insider_filing_seen`/`get_recent_insider_filings_seen` (lines
  175-206) is the closest existing CRUD shape to a firing-state table.
- `investments/goat/goat/openinsider.py` (whole file, 190 lines) — Why: `fetch_screener_
  filings` (lines 158-171) is the function this plan extends with a new optional
  `filing_date_days` param (see Task 8) — note `_SCREENER_DEFAULT_PARAMS["fd"]` is
  currently hardcoded to `"7"` (line 36), which is wrong for a 365-day aggregate window.
- `investments/goat/goat/insider_scan.py:56-73` (`run_holdings_watch`) — Why: shows the
  existing per-ticker aggregation shape (`held_tickers = sorted({...})`, one screener call
  for purchases + one for sales) this plan's `insider_trend.py` mirrors, but note this
  plan's check is a 365-day *aggregate sum*, not a per-filing alert — do not copy
  `run_holdings_watch`'s per-row alerting logic verbatim.
- `investments/my-trader/mytrader/abs_cpi.py` (whole file, 75 lines) — Why: the *exact*
  fetch-XLSX-via-`requests`-then-`openpyxl.load_workbook(io.BytesIO(content), data_only=
  True)` pattern to mirror in `margin_debt.py`. This tool's FINRA file is at a fixed URL
  (no month-in-path rollback loop needed, unlike ABS's), so `margin_debt.py` is simpler
  than this file, not more complex.
- `investments/my-trader/mytrader/tests/test_abs_cpi.py` (whole file) — Why: exact test
  pattern for a scraped/parsed spreadsheet — canned `openpyxl.Workbook()` built in-memory,
  `monkeypatch.setattr("requests.get", ...)`. Mirror for `test_margin_debt.py`.
- `investments/briefs-finance/scripts/macro.py` (whole file, 132 lines) — Why:
  `fred_observation_on` (lines 23-65) and `fred_series_range` (lines 68-99) are the two
  functions `credit_spread.py` calls directly (no new FRED-fetch code needed) —
  `fred_series_range` in particular is what makes the streak computation possible (full
  history in a window, not just the latest point).
- `investments/my-trader/mytrader/config.py:166-167` (`FRED_HY_OAS_SERIES`,
  `CREDIT_SPREAD_FLAG_PCT`) — Why: shows the existing FRED series ID to reuse
  (`BAMLH0A0HYM2`) — this plan's own `SIGNALS_CREDIT_SPREAD_STREAK_FLAG_PCT` constant is a
  *different* threshold (3.5, not 5.0) for a different check; do not confuse the two or
  reuse `CREDIT_SPREAD_FLAG_PCT` by mistake.
- `investments/my-trader/mytrader/macro_indicators.py:267-296` (`check_credit_spreads`) —
  Why: read this to understand why this plan does NOT modify or reuse it (see Design
  Decision #2) — it's a different consumer's single-day check, not a duration check.
- `investments/my-trader/mytrader/market_data.py` (lines 1-60 read; full file recommended)
  — Why: `TickerData.info` (line 15) is a raw yfinance `.info` dict — `info["marketCap"]`
  is the field `watchlist.py` and `market_cap_milestone.py` both read. `fetch_ticker_data`
  is the function to call (not shown in the excerpt read — locate and confirm its exact
  signature during Task 4, it takes a single ticker and returns `TickerData | None`).
- `investments/goat/goat/monitor.py:109-153` (`maybe_notify`) — Why: the exact WhatsApp/
  toast notification shape to mirror in this plan's own `alerts.py` — note it now takes
  both `alert_label` and `candidate_label` params (this function evolved twice already,
  2026-08-17 and 2026-08-18 — read the *current* file, not an older plan doc's snapshot of
  it) — this plan writes its own small `maybe_notify`-shaped function rather than importing
  Goat's (see Task 11 GOTCHA for why).
- `investments/goat/goat/main.py:8-19` (`_open_conn`) — Why: the exact cross-package DB-init
  shape (`init_db` → `get_connection` → `init_mytrader_tables` → `init_goat_tables`) this
  plan's `main.py` extends with one more `init_signals_tables` call.
- `investments/goat/goat/tests/conftest.py` (whole file, 48 lines) — Why: `db_conn` fixture
  (lines 19-26) and the report-path-isolation fixture (lines 29-38) — this plan's own
  `conftest.py` mirrors both shapes, initializing `goat`'s tables too (this package reads
  `goat_sp500_constituents` and calls into `goat.openinsider`).
- `investments/goat/pyproject.toml` (whole file, 28 lines) — Why: **has no `[build-system]`
  section** — because nothing currently depends on `goat` as a workspace source. This plan
  is the first thing that will (`fourteen-crash-signals-daily-check` depends on `goat`), so
  Task 2 adds one, mirroring `my-trader/pyproject.toml:38-43` exactly.
- `investments/my-trader/pyproject.toml` (whole file, 44 lines) — Why: lines 38-43 are the
  exact `[build-system]`/`[tool.hatch.build.targets.wheel]` block to copy into `goat/
  pyproject.toml` (Task 2) and to write fresh into this plan's own new `pyproject.toml`
  (Task 1), just with `packages = ["fourteen_crash_signals_daily_check"]`.
- `investments/pyproject.toml` (2 lines) — Why: the workspace members list this plan
  appends to.
- `investments/TOOLS.md` — Why: living doc of every scheduled/manual tool; this plan adds
  one row to the "Automated (scheduled)" table (Task 15).
- `scripts/deploy.ps1:17-25` (`$TIMERS` array) — Why: every timer that touches the repo
  must be listed here so deploy correctly stops/restarts it; this plan adds the new timer
  name (Task 16).
- `scripts/systemd/second-brain-goat-insider-scan.timer` and `.service` — Why: exact
  systemd unit shape to mirror (Task 14); `second-brain-goat-insider-scan.timer:6`'s
  `OnCalendar=*-*-* 21:50:00 UTC` is the cadence precedent to schedule after (this plan
  uses 22:05 UTC, 15 minutes after the insider scan, following the existing 15-minute
  spacing convention between Goat's own daily jobs).
- `investments/my-trader/mytrader/checks/__init__.py` (whole file, 15 lines) — Why:
  `CheckResult` dataclass — every marker-check function in this plan returns one of these
  (`verdict: "ok"|"flag"|"unknown"`), matching `macro_indicators.py`'s own convention for
  FRED-sourced checks.
- `investments/my-trader/14-signals-crash-warning-handoff.md` (whole file) — Why: the
  source design doc this plan formalizes; contains the full per-marker fact-check table and
  both rounds of resolved decisions.

### New Files to Create

- `investments/fourteen-crash-signals-daily-check/pyproject.toml`
- `investments/fourteen-crash-signals-daily-check/fourteen_crash_signals_daily_check/__init__.py`
- `investments/fourteen-crash-signals-daily-check/fourteen_crash_signals_daily_check/config.py`
- `investments/fourteen-crash-signals-daily-check/fourteen_crash_signals_daily_check/db.py`
- `investments/fourteen-crash-signals-daily-check/fourteen_crash_signals_daily_check/watchlist.py`
- `investments/fourteen-crash-signals-daily-check/fourteen_crash_signals_daily_check/credit_spread.py`
- `investments/fourteen-crash-signals-daily-check/fourteen_crash_signals_daily_check/margin_debt.py`
- `investments/fourteen-crash-signals-daily-check/fourteen_crash_signals_daily_check/insider_trend.py`
- `investments/fourteen-crash-signals-daily-check/fourteen_crash_signals_daily_check/market_cap_milestone.py`
- `investments/fourteen-crash-signals-daily-check/fourteen_crash_signals_daily_check/report.py`
- `investments/fourteen-crash-signals-daily-check/fourteen_crash_signals_daily_check/alerts.py`
- `investments/fourteen-crash-signals-daily-check/fourteen_crash_signals_daily_check/main.py`
- `investments/fourteen-crash-signals-daily-check/fourteen_crash_signals_daily_check/tests/__init__.py`
- `investments/fourteen-crash-signals-daily-check/fourteen_crash_signals_daily_check/tests/conftest.py`
- `investments/fourteen-crash-signals-daily-check/fourteen_crash_signals_daily_check/tests/test_watchlist.py`
- `investments/fourteen-crash-signals-daily-check/fourteen_crash_signals_daily_check/tests/test_credit_spread.py`
- `investments/fourteen-crash-signals-daily-check/fourteen_crash_signals_daily_check/tests/test_margin_debt.py`
- `investments/fourteen-crash-signals-daily-check/fourteen_crash_signals_daily_check/tests/test_insider_trend.py`
- `investments/fourteen-crash-signals-daily-check/fourteen_crash_signals_daily_check/tests/test_market_cap_milestone.py`
- `investments/fourteen-crash-signals-daily-check/fourteen_crash_signals_daily_check/tests/test_report.py`
- `investments/fourteen-crash-signals-daily-check/fourteen_crash_signals_daily_check/tests/test_db.py`
- `investments/fourteen-crash-signals-daily-check/fourteen_crash_signals_daily_check/tests/test_alerts.py`
- `scripts/systemd/second-brain-fourteen-signals.timer`
- `scripts/systemd/second-brain-fourteen-signals.service`

### New Files Auto-Generated At Runtime (not created by you, but referenced)

- `investments/fourteen-crash-signals-daily-check/signals-report.md` — written by
  `report.write_signals_report`.

### Files to Modify

- `investments/pyproject.toml` — add new workspace member.
- `investments/goat/pyproject.toml` — add `[build-system]`/`[tool.hatch.build.targets.wheel]`
  section (Task 2).
- `investments/goat/goat/openinsider.py` — `fetch_screener_filings` gets a new optional
  `filing_date_days: int = 7` param (backward-compatible default preserves every existing
  Goat caller's behavior unchanged).
- `investments/goat/goat/tests/test_openinsider.py` — one new regression test for the
  extended param.
- `investments/TOOLS.md` — add one row to the "Automated (scheduled)" table.
- `scripts/deploy.ps1` — add the new timer name to `$TIMERS`.

### Relevant Documentation

- FINRA Margin Statistics page: `https://www.finra.org/rules-guidance/key-topics/margin-
  accounts/margin-statistics` — confirmed (fetched 2026-08-18) direct XLSX download at
  `https://www.finra.org/sites/default/files/2021-03/margin-statistics.xlsx`, columns are
  "Debit balances in securities margin accounts" / "Free credit balances in cash accounts" /
  "Free credit balances in securities margin accounts", monthly data from Jan 1997,
  published "third week of the month following the reference month." **GOTCHA**: the
  `2021-03` segment in the path looks like a CMS upload-date artifact, not a version
  indicator — confirm during Task 6 that this exact URL still serves current data (it did
  as of 2026-08-18) before hardcoding it; if FINRA has since moved the file, the fetch
  degrades to `None` gracefully (same contract as every other scraper in this codebase) and
  the report shows "unavailable," it doesn't crash.
- FRED series `BAMLH0A0HYM2` (ICE BofA US High Yield Index Option-Adjusted Spread) — same
  series already used by `mytrader.config.FRED_HY_OAS_SERIES`; no new series to look up.
- OpenInsider `/screener` endpoint — same endpoint `goat/openinsider.py` already uses; see
  that file's own module docstring (lines 1-26) for the confirmed quirks (space-separated
  tickers, `vl`/`vh` in thousands, full form-field requirement). This plan's only new
  requirement is a wider `fd` (filing-date) window — confirm live during Task 8 whether
  OpenInsider's `cnt=300` row cap truncates a 365-day window against a single high-filing-
  volume mega-cap ticker; if so, treat a capped result as "at least this much activity" (a
  floor, not an exact total) rather than blocking the check on getting a mathematically
  exact sum — still directionally correct for a net-selling trend.

### Patterns to Follow

**XLSX fetch + parse (from `abs_cpi.py:38-74`, simplified — fixed URL, no rollback loop):**
```python
def _fetch_workbook_bytes() -> bytes | None:
    try:
        r = requests.get(config.SIGNALS_MARGIN_DEBT_URL, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code == 200:
            return r.content
    except Exception:
        pass
    return None
```

**FRED range read for a streak (new — no direct precedent, composes two existing
low-level functions from `briefs-finance/scripts/macro.py`):**
```python
from datetime import date, timedelta
history = fred_series_range(
    config.SIGNALS_CREDIT_SPREAD_SERIES, date.today() - timedelta(days=config.SIGNALS_CREDIT_SPREAD_LOOKBACK_DAYS), date.today()
)
# history: list[(date, float)] ascending -- walk backward while value >= threshold
```

**Hot-watchlist ranking (composes `heartbeat_scan.py:21-35`'s filter + a new market-cap sort):**
```python
closes = sector_rotation.fetch_all_sector_closes()
ranking = sector_rotation.rank_sectors(closes)
rising_etf_labels = {row["sector_label"] for row in ranking if row["rising"]}
constituents = goat_sp500_universe.get_or_refresh_sp500_constituents(conn)
candidates = [
    c for c in constituents
    if goat_config.GOAT_GICS_TO_ETF_SECTOR_LABEL.get(c["gics_sector"]) in rising_etf_labels
]
```

**CheckResult return shape (from `macro_indicators.py:267-296`):** every marker-check
function returns `CheckResult(name=..., verdict="ok"|"flag"|"unknown", detail=..., data={...})`
— `"unknown"` on any fetch failure, never raise, never silently treat missing data as `"ok"`.

**INSERT-then-compare-prior-state for "newly firing" (adapted from `goat/db.py:175-192`'s
INSERT OR IGNORE + rowcount idiom, but this is an UPSERT since state must be overwritten
each run, not just deduped once):**
```python
def upsert_signal_state(conn, *, marker_key: str, is_firing: bool, detail: str) -> bool:
    """Returns True if this call flips is_firing from False/absent -> True (a genuine
    new-firing transition worth alerting on)."""
    prior = conn.execute(
        "SELECT is_firing FROM signals_alert_state WHERE marker_key = ?", (marker_key,)
    ).fetchone()
    was_firing = bool(prior["is_firing"]) if prior else False
    with conn:
        conn.execute(
            """INSERT INTO signals_alert_state (marker_key, is_firing, detail, updated_at)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(marker_key) DO UPDATE SET is_firing=excluded.is_firing,
               detail=excluded.detail, updated_at=excluded.updated_at""",
            (marker_key, int(is_firing), detail, _now()),
        )
    return is_firing and not was_firing
```

---

## IMPLEMENTATION PLAN

### Phase 1: Foundation
- Add the new workspace member + `[build-system]` fix on `goat` (Tasks 1-2).
- Package scaffold: `__init__.py`, `config.py`, `db.py` (Tasks 3-5).

### Phase 2: Core Implementation
- `watchlist.py` (hot-company detection layer) (Task 6).
- Four marker-check modules: `credit_spread.py`, `margin_debt.py`, `insider_trend.py`
  (+ the `goat/openinsider.py` extension it needs), `market_cap_milestone.py` (Tasks 7-9).

### Phase 3: Integration
- `report.py` (combined 14-row report, 4 live + 10 placeholders) (Task 10).
- `alerts.py` (transition-only WhatsApp/toast notification) (Task 11).
- `main.py` (CLI wiring, `_open_conn`) (Task 12).

### Phase 4: Testing & Validation
- Unit tests for every module (Task 13).
- Systemd timer/service files (Task 14, files only — no VPS enablement).
- `TOOLS.md` + `deploy.ps1` housekeeping (Tasks 15-16).

---

## STEP-BY-STEP TASKS

Execute in order, top to bottom. Each task is atomic and independently testable.

### Task 1: CREATE `investments/fourteen-crash-signals-daily-check/pyproject.toml`

- **IMPLEMENT**:
  ```toml
  [project]
  name = "fourteen-crash-signals-daily-check"
  version = "0.1.0"
  requires-python = ">=3.12"
  dependencies = [
      "my-trader",
      "goat",
      "requests>=2.31.0",
      "openpyxl>=3.1.0",
  ]

  [tool.uv.sources]
  my-trader = { workspace = true }
  goat = { workspace = true }

  [project.optional-dependencies]
  dev = ["pytest>=8.0.0", "pytest-mock>=3.12.0", "ruff>=0.2.0", "mypy>=1.8.0"]

  [tool.pytest.ini_options]
  testpaths = ["fourteen_crash_signals_daily_check/tests"]
  pythonpath = ["."]

  [tool.ruff]
  target-version = "py312"
  line-length = 100

  [tool.mypy]
  python_version = "3.12"
  ignore_missing_imports = true

  [build-system]
  requires = ["hatchling"]
  build-backend = "hatchling.build"

  [tool.hatch.build.targets.wheel]
  packages = ["fourteen_crash_signals_daily_check"]
  ```
- **PATTERN**: `investments/goat/pyproject.toml` (whole file) for the base shape;
  `investments/my-trader/pyproject.toml:38-43` for the `[build-system]` block.
- **GOTCHA**: `requests` and `openpyxl` are already transitively available via the
  `my-trader` dependency chain (my-trader declares both) — declaring them again here is for
  explicitness/clarity (this package uses both directly, unlike `goat/sp500_universe.py`
  which relies on the transitive availability without declaring), not strictly required by
  the resolver. Keep them declared; do not remove for "already transitive" reasons.
- **VALIDATE**: `uv sync --directory investments` — expect a resolution error at this point
  since `goat`'s `[build-system]` section doesn't exist yet (Task 2) — validate together
  with Task 2.

### Task 2: UPDATE `investments/goat/pyproject.toml` and `investments/pyproject.toml`

- **IMPLEMENT**:
  1. Append to `investments/goat/pyproject.toml` (end of file):
     ```toml
     [build-system]
     requires = ["hatchling"]
     build-backend = "hatchling.build"

     [tool.hatch.build.targets.wheel]
     packages = ["goat"]
     ```
  2. Update `investments/pyproject.toml`:
     ```toml
     [tool.uv.workspace]
     members = ["briefs-finance", "my-trader", "goat", "fourteen-crash-signals-daily-check"]
     ```
- **PATTERN**: `investments/my-trader/pyproject.toml:38-43` (identical block, just a
  different `packages` value).
- **GOTCHA**: This is the first time anything depends on `goat` as a workspace source. If
  `uv sync` still fails after this change, check whether `hatchling` needs an explicit
  `[tool.hatch.build]` `include`/`exclude` for `goat`'s `tests/` or `__pycache__`
  directories (compare against how `my-trader/pyproject.toml`'s equivalent section handles
  its own `tests/` dir — if my-trader's wheel build already excludes tests implicitly via
  hatchling's default package-discovery rules, no extra config is needed here either).
- **VALIDATE**: `uv sync --directory investments` — must succeed cleanly. Then confirm
  nothing in the existing `goat` test suite broke: `uv run --directory investments/goat
  python -m pytest -q`.

### Task 3: CREATE package init + `config.py`

- **IMPLEMENT**:
  - `fourteen_crash_signals_daily_check/__init__.py` — empty file (package marker), matches
    `investments/my-trader/mytrader/__init__.py`.
  - `fourteen_crash_signals_daily_check/config.py`:
    ```python
    from __future__ import annotations

    from pathlib import Path

    from scripts.config import DB_PATH  # noqa: F401  (re-exported for this package's callers)

    SIGNALS_DIR = Path(__file__).resolve().parent.parent  # package -> investments/fourteen-crash-signals-daily-check
    SIGNALS_REPORT_PATH = SIGNALS_DIR / "signals-report.md"

    # Hot-company watchlist -- see plan's Design Decision #1 for full rationale.
    # v1/tunable, same status as GOAT_SECTOR_RANK_WINDOW_TRADING_DAYS.
    SIGNALS_HOT_WATCHLIST_MIN_MARKET_CAP = 100_000_000_000  # $100B mega-cap floor
    SIGNALS_HOT_WATCHLIST_TOP_N = 8  # matches the count of names the video/fact-check
                                        # both actually named (Nvidia, Microsoft, Meta,
                                        # Alphabet, Amazon, Oracle, Coreweave, Palantir)

    # Marker 14 -- high-yield credit spread streak ("the master signal").
    # Deliberately separate from mytrader.config.CREDIT_SPREAD_FLAG_PCT/FRED_HY_OAS_SERIES's
    # existing single-day check -- see Design Decision #2.
    SIGNALS_CREDIT_SPREAD_SERIES = "BAMLH0A0HYM2"  # same FRED series, different threshold/shape
    SIGNALS_CREDIT_SPREAD_STREAK_FLAG_PCT = 3.5  # the video's own historical trigger level
    SIGNALS_CREDIT_SPREAD_STREAK_TRADING_DAYS = 21  # ~1 trading month
    SIGNALS_CREDIT_SPREAD_LOOKBACK_DAYS = 45  # calendar days fetched -- comfortably covers
                                                 # 21 trading days + weekends, same margin
                                                 # philosophy as GOAT_MA_HISTORY_LOOKBACK_DAYS

    # Marker 5 -- margin debt YoY growth, from FINRA's own published spreadsheet.
    SIGNALS_MARGIN_DEBT_URL = "https://www.finra.org/sites/default/files/2021-03/margin-statistics.xlsx"
    SIGNALS_MARGIN_DEBT_YOY_FLAG_PCT = 40.0  # v1/tunable -- video's own framing: extreme
        # YoY growth "last seen at the peaks of 2000, 2007, and 2021"; not a literature-final number.

    # Marker 8 -- insider selling, aggregate 365-day trend against the hot watchlist.
    SIGNALS_INSIDER_TREND_LOOKBACK_DAYS = 365
    SIGNALS_INSIDER_TREND_MIN_VALUE = 1_000  # near-zero floor, same philosophy as
                                                 # GOAT_INSIDER_SALE_MIN_VALUE
    SIGNALS_INSIDER_TREND_NET_SELL_FLAG_RATIO = 3.0  # v1/tunable -- see Design Decision #3

    # Marker 10 -- most-valuable-company milestone.
    SIGNALS_MARKET_CAP_MILESTONE_STEP = 500_000_000_000  # $500B round-number rungs
    ```
- **PATTERN**: `investments/goat/goat/config.py:1-11` (`GOAT_DIR`/report-path idiom, `from
  scripts.config import DB_PATH` re-export) and its comment-density convention throughout
  (every constant gets a "why this number" comment).
- **VALIDATE**: `uv run --directory investments/fourteen-crash-signals-daily-check python -c
  "from fourteen_crash_signals_daily_check import config; print(config.DB_PATH,
  config.SIGNALS_REPORT_PATH)"`

### Task 4: CREATE `db.py`

- **IMPLEMENT**:
  ```python
  from __future__ import annotations

  import sqlite3
  from datetime import datetime, timezone


  def _now() -> str:
      return datetime.now(timezone.utc).isoformat()


  def init_signals_tables(conn: sqlite3.Connection) -> None:
      with conn:
          conn.executescript("""
              CREATE TABLE IF NOT EXISTS signals_hot_watchlist (
                  ticker        TEXT PRIMARY KEY,
                  sector_label  TEXT NOT NULL,
                  market_cap    REAL NOT NULL,
                  rank          INTEGER NOT NULL,
                  computed_at   TEXT NOT NULL
              );
              CREATE TABLE IF NOT EXISTS signals_alert_state (
                  marker_key    TEXT PRIMARY KEY,
                  is_firing     INTEGER NOT NULL,
                  detail        TEXT NOT NULL,
                  updated_at    TEXT NOT NULL
              );
          """)


  def replace_hot_watchlist(conn: sqlite3.Connection, rows: list[dict]) -> None:
      now = _now()
      with conn:
          conn.execute("DELETE FROM signals_hot_watchlist")
          conn.executemany(
              """INSERT INTO signals_hot_watchlist (ticker, sector_label, market_cap, rank, computed_at)
                 VALUES (?, ?, ?, ?, ?)""",
              [(r["ticker"], r["sector_label"], r["market_cap"], r["rank"], now) for r in rows],
          )


  def get_hot_watchlist(conn: sqlite3.Connection) -> list[sqlite3.Row]:
      return conn.execute("SELECT * FROM signals_hot_watchlist ORDER BY rank").fetchall()


  def upsert_signal_state(conn: sqlite3.Connection, *, marker_key: str, is_firing: bool, detail: str) -> bool:
      """Returns True only on a False/absent -> True transition (a genuine new-firing
      event worth alerting on) -- see 'Patterns to Follow' for the full rationale."""
      prior = conn.execute(
          "SELECT is_firing FROM signals_alert_state WHERE marker_key = ?", (marker_key,)
      ).fetchone()
      was_firing = bool(prior["is_firing"]) if prior else False
      with conn:
          conn.execute(
              """INSERT INTO signals_alert_state (marker_key, is_firing, detail, updated_at)
                 VALUES (?, ?, ?, ?)
                 ON CONFLICT(marker_key) DO UPDATE SET is_firing=excluded.is_firing,
                 detail=excluded.detail, updated_at=excluded.updated_at""",
              (marker_key, int(is_firing), detail, _now()),
          )
      return is_firing and not was_firing


  def get_all_signal_states(conn: sqlite3.Connection) -> list[sqlite3.Row]:
      return conn.execute("SELECT * FROM signals_alert_state ORDER BY marker_key").fetchall()
  ```
- **PATTERN**: `investments/goat/goat/db.py:1-73` (`init_goat_tables`'s `executescript` +
  idempotent-migration shape) and `replace_sp500_constituents` (lines 157-168, the
  delete-all-then-insert-all idiom `replace_hot_watchlist` mirrors).
- **GOTCHA**: SQLite's `ON CONFLICT ... DO UPDATE` (upsert) syntax requires SQLite ≥3.24 —
  confirm the Python version's bundled SQLite supports it (Python 3.12+ ships SQLite well
  above this floor; not a real risk, but verify via the Task 5 validation command rather
  than assuming).
- **VALIDATE**: `uv run --directory investments/fourteen-crash-signals-daily-check python -c
  "import sqlite3; from fourteen_crash_signals_daily_check import db; conn = sqlite3.connect(':memory:'); conn.row_factory = sqlite3.Row; db.init_signals_tables(conn); print(db.upsert_signal_state(conn, marker_key='test', is_firing=True, detail='x'))"`
  — must print `True` (first-time firing).

### Task 5: CREATE `watchlist.py`

- **IMPLEMENT**:
  ```python
  from __future__ import annotations

  import sqlite3
  from typing import Any

  from goat import config as goat_config
  from goat import sector_rotation, sp500_universe
  from mytrader import market_data

  from . import config, db


  def compute_hot_watchlist(conn: sqlite3.Connection) -> list[dict[str, Any]]:
      closes = sector_rotation.fetch_all_sector_closes()
      ranking = sector_rotation.rank_sectors(closes)
      rising_etf_labels = {row["sector_label"] for row in ranking if row["rising"]}

      constituents = sp500_universe.get_or_refresh_sp500_constituents(conn)

      candidates: list[dict[str, Any]] = []
      for c in constituents:
          etf_label = goat_config.GOAT_GICS_TO_ETF_SECTOR_LABEL.get(c["gics_sector"])
          if etf_label is None or etf_label not in rising_etf_labels:
              continue
          try:
              data = market_data.fetch_ticker_data(c["ticker"])
          except Exception as e:
              print(f"[fourteen-signals-watchlist] error fetching {c['ticker']}: {e}")
              continue
          if data is None:
              continue
          market_cap = data.info.get("marketCap")
          if market_cap is None or market_cap < config.SIGNALS_HOT_WATCHLIST_MIN_MARKET_CAP:
              continue
          candidates.append({"ticker": c["ticker"], "sector_label": etf_label, "market_cap": market_cap})

      candidates.sort(key=lambda r: -r["market_cap"])
      top = candidates[: config.SIGNALS_HOT_WATCHLIST_TOP_N]
      for i, row in enumerate(top, start=1):
          row["rank"] = i
      return top


  def get_or_refresh_hot_watchlist(conn: sqlite3.Connection) -> list[sqlite3.Row]:
      """Recomputed every call -- unlike Goat's S&P 500 cache, this has no TTL: the
      handoff's own decision is 'refreshed on an ongoing basis', and the only real cost
      here (beyond Goat's already-cached constituent list) is one yfinance .info fetch
      per rising-sector constituent, which for a handful of rising sectors out of 11 is
      cheap enough to do daily."""
      rows = compute_hot_watchlist(conn)
      db.replace_hot_watchlist(conn, rows)
      return db.get_hot_watchlist(conn)
  ```
- **PATTERN**: `investments/goat/goat/heartbeat_scan.py:21-35` (the rising-sector filter to
  mirror exactly) and `investments/goat/goat/sp500_universe.py:60-79` (`get_or_refresh_
  sp500_constituents`, the caching shape this function deliberately does NOT copy — see
  GOTCHA).
- **GOTCHA**: Do not cache this table with a TTL the way `goat_sp500_constituents` is
  cached — recompute on every run (see docstring above). If Shaun later finds the daily
  yfinance-fetch cost too high (a rising sector could have 50+ S&P 500 constituents), a TTL
  cache is a reasonable follow-up, but do not add one speculatively now.
- **GOTCHA**: `market_data.fetch_ticker_data`'s exact signature/behavior wasn't fully read
  in this plan's research pass (only lines 1-60 of `market_data.py` were reviewed) — before
  writing this function, read the rest of that file (or `grep -n "def fetch_ticker_data"
  investments/my-trader/mytrader/market_data.py`) to confirm it takes a bare ticker string
  and returns `TickerData | None` as assumed here, and whether it has its own internal
  caching (the module docstring mentions a `cached_session()` context manager — decide
  whether to use it here to avoid redundant fetches within one run).
- **VALIDATE**: `uv run --directory investments/fourteen-crash-signals-daily-check python -m
  pytest fourteen_crash_signals_daily_check/tests/test_watchlist.py -v` (after Task 13).

### Task 6: CREATE `credit_spread.py` (Marker 14)

- **IMPLEMENT**:
  ```python
  from __future__ import annotations

  from datetime import date, timedelta

  from mytrader.checks import CheckResult
  from scripts.macro import fred_series_range

  from . import config


  def check_credit_spread_streak() -> CheckResult:
      today = date.today()
      history = fred_series_range(
          config.SIGNALS_CREDIT_SPREAD_SERIES,
          today - timedelta(days=config.SIGNALS_CREDIT_SPREAD_LOOKBACK_DAYS),
          today,
      )
      if not history:
          return CheckResult(
              name="credit_spread_streak", verdict="unknown",
              detail="FRED high-yield credit spread data unavailable (FRED_API_KEY not set, or series unavailable)",
          )

      streak_days = 0
      for _, value in reversed(history):  # walk backward from most recent
          if value >= config.SIGNALS_CREDIT_SPREAD_STREAK_FLAG_PCT:
              streak_days += 1
          else:
              break

      latest_date, latest_value = history[-1]
      if streak_days >= config.SIGNALS_CREDIT_SPREAD_STREAK_TRADING_DAYS:
          return CheckResult(
              name="credit_spread_streak", verdict="flag",
              detail=f"ICE BofA US HY OAS at {latest_value:.2f}pp (as of {latest_date.isoformat()}), "
                     f"at/above {config.SIGNALS_CREDIT_SPREAD_STREAK_FLAG_PCT:.1f}pp for {streak_days} "
                     f"trading day(s) -- the video's single most reliable historical marker",
              data={"value": latest_value, "streak_days": streak_days, "as_of": latest_date.isoformat()},
          )
      return CheckResult(
          name="credit_spread_streak", verdict="ok",
          detail=f"ICE BofA US HY OAS at {latest_value:.2f}pp (as of {latest_date.isoformat()}); "
                 f"{streak_days} consecutive day(s) at/above {config.SIGNALS_CREDIT_SPREAD_STREAK_FLAG_PCT:.1f}pp "
                 f"(needs {config.SIGNALS_CREDIT_SPREAD_STREAK_TRADING_DAYS} to flag)",
          data={"value": latest_value, "streak_days": streak_days, "as_of": latest_date.isoformat()},
      )
  ```
- **PATTERN**: `investments/my-trader/mytrader/macro_indicators.py:267-296`
  (`check_credit_spreads`) for the `CheckResult` shape and "unavailable" wording convention
  — but note the streak-walk logic itself has no existing precedent in this codebase (new
  logic, not copied from anywhere).
- **IMPORTS**: `fred_series_range` lives in `investments/briefs-finance/scripts/macro.py` —
  import as `from scripts.macro import fred_series_range` (same cross-package import shape
  `mytrader/macro_indicators.py:64` already uses).
- **GOTCHA**: `fred_series_range` returns ascending `(date, value)` tuples — the streak walk
  must go from the END of the list backward (`reversed(history)`), not the start. Getting
  this backward would silently compute the streak from 45 days ago instead of today.
- **GOTCHA**: If FRED has a gap (a holiday with no observation), `fred_series_range` simply
  omits that date rather than repeating the prior value — the streak count is therefore a
  count of *published observations* meeting the threshold, not literally calendar days.
  This is consistent with how the underlying series behaves (FRED only publishes on
  business days) and matches the video's own "trading days" framing closely enough — do
  not attempt to forward-fill missing days.
- **VALIDATE**: `uv run --directory investments/fourteen-crash-signals-daily-check python -m
  pytest fourteen_crash_signals_daily_check/tests/test_credit_spread.py -v` (after Task 13).

### Task 7: CREATE `margin_debt.py` (Marker 5)

- **IMPLEMENT**:
  ```python
  from __future__ import annotations

  import io
  from datetime import date

  import requests
  from mytrader.checks import CheckResult

  from . import config


  def _fetch_workbook_bytes() -> bytes | None:
      try:
          r = requests.get(config.SIGNALS_MARGIN_DEBT_URL, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
          if r.status_code == 200:
              return r.content
      except Exception:
          pass
      return None


  def fetch_margin_debt_series() -> list[tuple[date, float]] | None:
      """Returns (month, debit-balance-$millions) ascending, or None on any failure.
      Column layout confirmed live 2026-08-18 -- re-verify during implementation (see
      GOTCHA) since it wasn't independently re-checked beyond the page-level column names."""
      content = _fetch_workbook_bytes()
      if content is None:
          return None
      try:
          import openpyxl

          wb = openpyxl.load_workbook(io.BytesIO(content), data_only=True)
          ws = wb.active  # confirm sheet name/index during implementation
          rows: list[tuple[date, float]] = []
          for row in ws.iter_rows(min_row=2, values_only=True):  # confirm header row count
              if row[0] is None or row[1] is None:
                  continue
              month = row[0].date() if hasattr(row[0], "date") else row[0]
              rows.append((month, float(row[1])))
          return rows or None
      except Exception:
          return None


  def check_margin_debt_growth() -> CheckResult:
      series = fetch_margin_debt_series()
      if not series or len(series) < 13:
          return CheckResult(
              name="margin_debt_growth", verdict="unknown",
              detail="FINRA margin debt data unavailable or too short for a YoY comparison",
          )
      latest_month, latest_value = series[-1]
      prior_month, prior_value = series[-13]  # ~12 months prior
      if prior_value == 0:
          return CheckResult(name="margin_debt_growth", verdict="unknown", detail="prior-year value is zero, cannot compute YoY")
      yoy_pct = (latest_value - prior_value) / prior_value * 100
      detail_base = (
          f"Margin debt ${latest_value / 1e6:.2f}T as of {latest_month.isoformat()}, "
          f"{yoy_pct:+.1f}% YoY vs {prior_month.isoformat()}"
      )
      if yoy_pct >= config.SIGNALS_MARGIN_DEBT_YOY_FLAG_PCT:
          return CheckResult(
              name="margin_debt_growth", verdict="flag",
              detail=f"{detail_base} -- growth rate historically seen at cycle peaks (2000, 2007, 2021)",
              data={"value": latest_value, "yoy_pct": yoy_pct, "as_of": latest_month.isoformat()},
          )
      return CheckResult(
          name="margin_debt_growth", verdict="ok", detail=detail_base,
          data={"value": latest_value, "yoy_pct": yoy_pct, "as_of": latest_month.isoformat()},
      )
  ```
- **PATTERN**: `investments/my-trader/mytrader/abs_cpi.py:38-74` (fetch-then-`openpyxl`
  parse shape) — this file is simpler (fixed URL, no month-rollback loop).
- **GOTCHA**: The exact sheet name, header row count, and which column is "Debit balances
  in securities margin accounts" (values are in **millions** of dollars per the page text —
  `latest_value / 1e6` above converts to trillions for display, matching the video's "$1.53T"
  framing) were NOT independently verified against the live file during this planning pass
  (only the page's prose description was fetched, not the spreadsheet itself). **Before
  finalizing this function, download the actual file
  (`requests.get(config.SIGNALS_MARGIN_DEBT_URL)`) and inspect it in a real Python
  session/Excel** to confirm sheet name (`wb.active` may not be correct if there are
  multiple sheets), header row count, and column index — adjust `min_row`/`row[N]` indices
  to match reality rather than trusting the sketch above verbatim.
- **GOTCHA**: `series[-13]` assumes exactly one row per calendar month with no gaps — if
  FINRA's file has any missing months, this naive index offset will compare against the
  wrong month. Add a defensive check (or better: search backward for the row whose month is
  ~365 days before `latest_month`, tolerant of a few weeks either way) rather than trusting
  a fixed positional offset — refine this during implementation once the real file's
  structure is confirmed.
- **VALIDATE**: `uv run --directory investments/fourteen-crash-signals-daily-check python -m
  pytest fourteen_crash_signals_daily_check/tests/test_margin_debt.py -v` (after Task 13);
  also a manual one-off: `uv run --directory investments/fourteen-crash-signals-daily-check
  python -c "from fourteen_crash_signals_daily_check import margin_debt; print(margin_debt.check_margin_debt_growth())"`
  against the live file.

### Task 8: UPDATE `investments/goat/goat/openinsider.py`, CREATE `insider_trend.py` (Marker 8)

- **IMPLEMENT**:
  1. In `openinsider.py`, change `fetch_screener_filings`'s signature (line 158) from:
     ```python
     def fetch_screener_filings(
         tickers_list: list[str], trade_type: str, min_value: float
     ) -> list[dict] | None:
     ```
     to:
     ```python
     def fetch_screener_filings(
         tickers_list: list[str], trade_type: str, min_value: float, filing_date_days: int = 7
     ) -> list[dict] | None:
     ```
     and change the `params["fd"] = ...` line (currently hardcoded `"fd": "7"` inside
     `_SCREENER_DEFAULT_PARAMS`, line 36) so this function overrides it:
     ```python
     params = dict(_SCREENER_DEFAULT_PARAMS)
     params["fd"] = str(filing_date_days)
     params["s"] = " ".join(tickers_list)
     ...
     ```
  2. Create `fourteen_crash_signals_daily_check/insider_trend.py`:
     ```python
     from __future__ import annotations

     import sqlite3
     from typing import Any

     from goat import config as goat_config
     from goat import openinsider
     from mytrader.checks import CheckResult

     from . import config, db


     def check_insider_trend(conn: sqlite3.Connection) -> list[CheckResult]:
         watchlist = db.get_hot_watchlist(conn)
         if not watchlist:
             return []
         tickers = [row["ticker"] for row in watchlist]

         purchases = openinsider.fetch_screener_filings(
             tickers, "P", config.SIGNALS_INSIDER_TREND_MIN_VALUE,
             filing_date_days=config.SIGNALS_INSIDER_TREND_LOOKBACK_DAYS,
         )
         sales = openinsider.fetch_screener_filings(
             tickers, "S", config.SIGNALS_INSIDER_TREND_MIN_VALUE,
             filing_date_days=config.SIGNALS_INSIDER_TREND_LOOKBACK_DAYS,
         )
         if purchases is None and sales is None:
             return [CheckResult(name="insider_trend", verdict="unknown", detail="OpenInsider fetch failed for both purchases and sales")]

         totals: dict[str, dict[str, float]] = {t: {"bought": 0.0, "sold": 0.0} for t in tickers}
         for row in purchases or []:
             totals[row["ticker"]]["bought"] += row["value"]
         for row in sales or []:
             totals[row["ticker"]]["sold"] += row["value"]

         results: list[CheckResult] = []
         for ticker, amounts in totals.items():
             bought, sold = amounts["bought"], amounts["sold"]
             if bought == 0 and sold == 0:
                 continue
             ratio = sold / bought if bought > 0 else (float("inf") if sold > 0 else 0.0)
             detail = (
                 f"{ticker}: ${sold:,.0f} sold vs ${bought:,.0f} bought, trailing "
                 f"{config.SIGNALS_INSIDER_TREND_LOOKBACK_DAYS} days"
             )
             verdict = "flag" if ratio >= config.SIGNALS_INSIDER_TREND_NET_SELL_FLAG_RATIO else "ok"
             results.append(CheckResult(
                 name="insider_trend", verdict=verdict, detail=detail,
                 data={"ticker": ticker, "bought": bought, "sold": sold, "ratio": ratio},
             ))
         return results
     ```
- **PATTERN**: `investments/goat/goat/insider_scan.py:56-73` (`run_holdings_watch`'s
  ticker-set + two-screener-calls shape) — but this is an aggregate sum, not a per-filing
  alert loop; do not copy the dedup/lookback-window logic from that function.
- **GOTCHA**: `_SCREENER_DEFAULT_PARAMS["fd"]` is currently `"7"` at the module level in
  `openinsider.py` (line 36) — confirm OpenInsider's `fd` parameter actually accepts an
  arbitrary day count like `"365"` (not just a small preset list) before relying on this;
  the module's own comment (lines 27-33) implies `fd` is a free integer, but this wasn't
  independently re-verified live during this planning pass. If OpenInsider caps or rejects
  large `fd` values, an alternative is calling the screener with `fd="365"` `td`/`tdr`
  (trade-date-range) params instead — investigate live during implementation.
- **GOTCHA**: A 365-day window against a single high-filing-volume mega-cap ticker may hit
  OpenInsider's `cnt=300` row cap (see this plan's "Relevant Documentation" section) —
  confirm live whether this actually happens for the top hot-watchlist names; if it does,
  treat the capped total as a floor ("at least this much"), not an exact sum, and say so in
  the report detail string rather than presenting a truncated number as precise.
- **VALIDATE**: `uv run --directory investments/goat python -m pytest goat/tests/
  test_openinsider.py -v` (existing Goat tests must still pass unmodified — they call
  `fetch_screener_filings` without the new param, exercising the default `filing_date_days=7`);
  `uv run --directory investments/fourteen-crash-signals-daily-check python -m pytest
  fourteen_crash_signals_daily_check/tests/test_insider_trend.py -v` (after Task 13).

### Task 9: CREATE `market_cap_milestone.py` (Marker 10)

- **IMPLEMENT**:
  ```python
  from __future__ import annotations

  import sqlite3
  from typing import Any

  from goat import sp500_universe
  from mytrader import market_data
  from mytrader.checks import CheckResult

  from . import config


  def check_market_cap_milestone(conn: sqlite3.Connection) -> CheckResult:
      constituents = sp500_universe.get_or_refresh_sp500_constituents(conn)
      if not constituents:
          return CheckResult(name="market_cap_milestone", verdict="unknown", detail="S&P 500 constituent list unavailable")

      leader_ticker, leader_cap = None, 0.0
      for c in constituents:
          try:
              data = market_data.fetch_ticker_data(c["ticker"])
          except Exception:
              continue
          if data is None:
              continue
          cap = data.info.get("marketCap")
          if cap is not None and cap > leader_cap:
              leader_ticker, leader_cap = c["ticker"], cap

      if leader_ticker is None:
          return CheckResult(name="market_cap_milestone", verdict="unknown", detail="could not determine a market-cap leader")

      rung = int(leader_cap // config.SIGNALS_MARKET_CAP_MILESTONE_STEP) * config.SIGNALS_MARKET_CAP_MILESTONE_STEP
      detail = (
          f"{leader_ticker} is the largest S&P 500 company by market cap "
          f"(${leader_cap / 1e12:.2f}T, most recently crossed the ${rung / 1e12:.1f}T rung)"
      )
      return CheckResult(
          name="market_cap_milestone", verdict="flag", detail=detail,
          data={"ticker": leader_ticker, "market_cap": leader_cap, "rung": rung},
      )
  ```
- **PATTERN**: same `market_data.fetch_ticker_data` reuse as `watchlist.py` (Task 5);
  `sp500_universe.get_or_refresh_sp500_constituents` reused directly, same as Task 5 — do
  not build a second S&P 500 fetch path.
- **GOTCHA**: This function fetches every S&P 500 constituent's market cap every run (~500
  yfinance calls) to find the single leader — noticeably more expensive than `watchlist.py`
  (which only fetches the rising-sector subset). Confirm this is acceptable for a once-
  daily job during manual validation (Task 12); if too slow/rate-limited in practice, a
  cheaper follow-up would restrict the scan to a small known mega-cap shortlist (e.g. reuse
  the hot watchlist itself, since the historical marker is specifically about *hyperscaler*
  companies overtaking each other) — but do not narrow the scope speculatively now without
  confirming the full-scan approach is actually a problem.
- **GOTCHA**: `verdict="flag"` is returned unconditionally here (not gated on the rung
  actually being *new* since the last run) — the "is this newly firing" logic belongs in
  `alerts.py`/`db.upsert_signal_state`, keyed on `f"market_cap_milestone:{rung}"`, so a
  repeat run at the same rung does not re-alert. Do not add a home-grown "is this new" check
  inside this function itself — see Task 11.
- **VALIDATE**: `uv run --directory investments/fourteen-crash-signals-daily-check python -m
  pytest fourteen_crash_signals_daily_check/tests/test_market_cap_milestone.py -v` (after
  Task 13).

### Task 10: CREATE `report.py`

- **IMPLEMENT**: Combined 14-row markdown report. All 4 built markers render real data;
  the other 10 render a fixed "not yet automated" placeholder row referencing the handoff
  doc.
  ```python
  from __future__ import annotations

  from datetime import date
  from typing import Any

  from . import config

  _NOT_YET_AUTOMATED = (
      "Not yet automated in this build -- see "
      "investments/my-trader/14-signals-crash-warning-handoff.md for the fact-check "
      "and feasibility notes."
  )

  _PLACEHOLDER_MARKERS = [
      (1, "Record debt issuance, hot sector"),
      (2, "Debt moves off balance sheet"),
      (3, "Seller finances buyer"),
      (4, "Capex outruns cash flow"),
      (6, "Record IPO/equity issuance"),
      (7, "Retail piles into leverage"),
      (9, "The Super Bowl signal"),
      (11, "Regulators sound the alarm"),
      (12, "Credit turns in the hot sector while broad market stays calm"),
      (13, "Funding markets start choking"),
  ]


  def render_signals_report(
      watchlist: list[dict[str, Any]],
      credit_spread_result: Any,
      margin_debt_result: Any,
      insider_trend_results: list[Any],
      market_cap_result: Any,
  ) -> str:
      lines = [
          "# 14 Crash Signals — Daily Check",
          "",
          "Auto-generated daily -- overwritten every run. Advisor notes only; no trade "
          "action is ever suggested here (see SOUL.md). Per-marker source: "
          "investments/my-trader/14-signals-crash-warning-handoff.md.",
          "",
          "## Hot Company Watchlist (shared input for markers 1-4, 8, 11-13)",
          "Dynamically recomputed every run from currently-rising GICS sectors + S&P 500 "
          "mega-cap constituents -- never hardcoded to a fixed ticker list.",
          "",
      ]
      if watchlist:
          lines += ["| Rank | Ticker | Sector | Market Cap |", "|------|--------|--------|------------|"]
          for row in watchlist:
              lines.append(f"| {row['rank']} | {row['ticker']} | {row['sector_label']} | ${row['market_cap'] / 1e9:.0f}B |")
      else:
          lines.append("No hot-watchlist companies resolved this run (no rising sectors, or data unavailable).")

      lines += ["", "## Markers", "", "| # | Marker | Status | Detail |", "|---|--------|--------|--------|"]
      lines.append(f"| 5 | Margin debt YoY growth | {margin_debt_result.verdict} | {margin_debt_result.detail} |")
      for r in insider_trend_results:
          lines.append(f"| 8 | Insider selling ({r.data.get('ticker', '?')}) | {r.verdict} | {r.detail} |")
      if not insider_trend_results:
          lines.append("| 8 | Insider selling (aggregate trend) | ok | No hot-watchlist tickers with insider activity this run. |")
      lines.append(f"| 10 | Most-valuable-company milestone | {market_cap_result.verdict} | {market_cap_result.detail} |")
      lines.append(f"| 14 | High-yield credit spread streak | {credit_spread_result.verdict} | {credit_spread_result.detail} |")
      for num, name in _PLACEHOLDER_MARKERS:
          lines.append(f"| {num} | {name} | n/a | {_NOT_YET_AUTOMATED} |")

      lines += ["", f"Last auto-generated: {date.today().isoformat()}."]
      return "\n".join(lines) + "\n"


  def write_signals_report(*args, **kwargs) -> None:
      config.SIGNALS_REPORT_PATH.write_text(render_signals_report(*args, **kwargs), encoding="utf-8")
  ```
- **PATTERN**: `investments/goat/goat/insider_scan.py:257-323`
  (`render_insider_scan_report`/`write_insider_scan_report`) for the overall "combined
  multi-section markdown, ends with a Last-auto-generated line" shape.
- **GOTCHA**: Marker numbers in the table are NOT in numeric order in the "Markers" section
  as sketched (5, 8, 10, 14 first, then placeholders 1-4/6/7/9/11-13) — consider sorting
  the whole combined list by marker number 1-14 for readability before finalizing (`sorted`
  the placeholder + live rows together by marker number) rather than shipping the sketch's
  build-order grouping verbatim.
- **VALIDATE**: `uv run --directory investments/fourteen-crash-signals-daily-check python -m
  pytest fourteen_crash_signals_daily_check/tests/test_report.py -v` (after Task 13).

### Task 11: CREATE `alerts.py`

- **IMPLEMENT**:
  ```python
  from __future__ import annotations

  import sqlite3
  from typing import Any

  from . import db


  def maybe_notify(conn: sqlite3.Connection, results: list[dict[str, Any]]) -> None:
      """results: list of {'marker_key': str, 'is_firing': bool, 'detail': str}. Fires a
      WhatsApp/toast alert only for entries that newly transitioned into firing this run
      (per db.upsert_signal_state) -- never a daily dump of all 14 rows regardless of
      change, per the handoff's explicit decision."""
      newly_firing = [
          r for r in results
          if db.upsert_signal_state(conn, marker_key=r["marker_key"], is_firing=r["is_firing"], detail=r["detail"])
      ]
      if not newly_firing:
          return

      import sys
      from pathlib import Path

      _scripts_dir = Path(__file__).resolve().parent.parent.parent.parent / ".claude" / "scripts"
      sys.path.insert(0, str(_scripts_dir))
      from notifications import send_toast_notification, send_whatsapp_notification

      summary = f"{len(newly_firing)} crash-warning signal(s) newly firing"
      send_toast_notification("14 Crash Signals", summary + " -- check investments/fourteen-crash-signals-daily-check/")

      lines = [f"14 Crash Signals: {summary}."]
      lines += [f"- {r['detail']}" for r in newly_firing]
      send_whatsapp_notification("\n".join(lines))
  ```
- **PATTERN**: `investments/goat/goat/monitor.py:109-153` (`maybe_notify`) for the
  notifications-import + toast-then-WhatsApp shape.
- **GOTCHA**: This plan writes its own `maybe_notify` rather than importing `goat.monitor.
  maybe_notify` — that function's hardcoded "Goat Monitor" toast title and `alert_label`/
  `candidate_label` parameter shape are specific to Goat's own alert/candidate framing
  (per-ticker exit alerts + staged candidates), which doesn't fit this tool's "named marker
  transitioned to firing" shape. Writing a small parallel function (same *import* pattern,
  different message shape) is the right call here, not a missed reuse opportunity.
- **GOTCHA**: The `_scripts_dir` path-hop count (`parent.parent.parent.parent`) must resolve
  to the repo root's `.claude/scripts` from *this* file's location
  (`investments/fourteen-crash-signals-daily-check/fourteen_crash_signals_daily_check/
  alerts.py`) — count the hops carefully (this file is one directory deeper than `goat/
  goat/monitor.py` was from repo root only if the package dir names differ in depth; both
  are `investments/<pkg-dir>/<pkg-dir>/<file>.py`, i.e. the same depth as `goat/goat/
  monitor.py`, so the same 4-hop count applies — verify by printing `_scripts_dir` and
  confirming it points at the real `.claude/scripts` before trusting it).
- **VALIDATE**: `uv run --directory investments/fourteen-crash-signals-daily-check python -m
  pytest fourteen_crash_signals_daily_check/tests/test_alerts.py -v` (after Task 13, using
  the same `monkeypatch.setitem(sys.modules, "notifications", ...)` fake-module pattern as
  `goat/goat/tests/test_monitor.py`).

### Task 12: CREATE `main.py`

- **IMPLEMENT**:
  ```python
  from __future__ import annotations

  import argparse


  def _open_conn():
      from scripts.db import get_connection, init_db

      from goat.db import init_goat_tables
      from mytrader.db import init_mytrader_tables

      from .config import DB_PATH
      from .db import init_signals_tables

      init_db(DB_PATH)
      conn = get_connection(DB_PATH)
      init_mytrader_tables(conn)
      init_goat_tables(conn)  # needed for goat_sp500_constituents
      init_signals_tables(conn)
      return conn


  def cmd_daily_check(args) -> None:
      from . import credit_spread, insider_trend, margin_debt, market_cap_milestone, report, watchlist
      from .alerts import maybe_notify

      conn = _open_conn()
      hot_watchlist = watchlist.get_or_refresh_hot_watchlist(conn)
      credit_spread_result = credit_spread.check_credit_spread_streak()
      margin_debt_result = margin_debt.check_margin_debt_growth()
      insider_trend_results = insider_trend.check_insider_trend(conn)
      market_cap_result = market_cap_milestone.check_market_cap_milestone(conn)

      report.write_signals_report(
          [dict(r) for r in hot_watchlist], credit_spread_result, margin_debt_result,
          insider_trend_results, market_cap_result,
      )

      alert_inputs = [
          {"marker_key": "credit_spread_streak", "is_firing": credit_spread_result.verdict == "flag", "detail": credit_spread_result.detail},
          {"marker_key": "margin_debt_growth", "is_firing": margin_debt_result.verdict == "flag", "detail": margin_debt_result.detail},
          {"marker_key": "market_cap_milestone:" + str(market_cap_result.data.get("rung")), "is_firing": market_cap_result.verdict == "flag", "detail": market_cap_result.detail},
      ]
      for r in insider_trend_results:
          alert_inputs.append({
              "marker_key": f"insider_trend:{r.data.get('ticker')}",
              "is_firing": r.verdict == "flag", "detail": r.detail,
          })
      maybe_notify(conn, alert_inputs)
      conn.close()
      print(
          f"14 Crash Signals daily check complete: {len(hot_watchlist)} hot-watchlist "
          f"ticker(s), see investments/fourteen-crash-signals-daily-check/signals-report.md"
      )


  def main() -> None:
      parser = argparse.ArgumentParser(description="Fourteen Crash Signals -- daily crash-warning check")
      subparsers = parser.add_subparsers(dest="command")
      subparsers.add_parser("daily-check", help="Run all built markers, write the combined report, alert on new firings")

      args = parser.parse_args()
      if args.command == "daily-check":
          cmd_daily_check(args)
      else:
          parser.print_help()


  if __name__ == "__main__":
      main()
  ```
- **PATTERN**: `investments/goat/goat/main.py:8-45` (`_open_conn`, `cmd_monitor`) for the
  cross-package DB-init + orchestrate-then-report-then-notify shape.
- **GOTCHA**: `market_cap_milestone`'s `marker_key` deliberately includes the rung value
  (`"market_cap_milestone:500000000000"`) so crossing a *new* rung alerts again, while
  staying at the same rung across runs does not re-alert — do not key this purely on
  `"market_cap_milestone"` alone, or it will never re-fire once the first rung is crossed.
- **VALIDATE**: `uv run --directory investments/fourteen-crash-signals-daily-check python -m
  fourteen_crash_signals_daily_check.main daily-check` — must run end-to-end without error
  (live network calls; acceptable for manual validation) and print the summary line.

### Task 13: CREATE test suite

- **IMPLEMENT**: `conftest.py` (mirrors `investments/goat/goat/tests/conftest.py`):
  ```python
  from __future__ import annotations

  from pathlib import Path

  import pytest
  from scripts.db import get_connection, init_db

  from goat.db import init_goat_tables
  from mytrader.db import init_mytrader_tables

  from fourteen_crash_signals_daily_check.db import init_signals_tables


  @pytest.fixture
  def db_conn(tmp_path):
      db_path = tmp_path / "test_investments.db"
      init_db(db_path)
      conn = get_connection(db_path)
      init_mytrader_tables(conn)
      init_goat_tables(conn)
      init_signals_tables(conn)
      yield conn
      conn.close()


  @pytest.fixture(autouse=True)
  def _isolate_signals_report_path(monkeypatch, tmp_path):
      import fourteen_crash_signals_daily_check.config as signals_config
      monkeypatch.setattr(signals_config, "SIGNALS_REPORT_PATH", tmp_path / "signals-report.md")
  ```
  Then per module (mirror the closest existing Goat test file in each case):
  - `test_db.py` — CRUD + the upsert-transition-detection contract (`upsert_signal_state`
    returns `True` only on the False/absent→True transition, `False` on repeat-firing and
    on staying not-firing). Mirror `investments/goat/goat/tests/test_db.py`.
  - `test_watchlist.py` — monkeypatch `goat.sector_rotation.rank_sectors` and `goat.
    sp500_universe.get_or_refresh_sp500_constituents` and `mytrader.market_data.
    fetch_ticker_data` (mirror `investments/goat/goat/tests/test_heartbeat_scan.py`'s
    `_patch_common` style); assert mega-cap floor filtering, top-N truncation, and rank
    ordering.
  - `test_credit_spread.py` — monkeypatch `scripts.macro.fred_series_range` (mirror
    `investments/my-trader/mytrader/tests/test_macro_indicators.py`'s FRED-mocking style);
    cases: streak below threshold, streak at/above threshold for < required days (`ok`),
    streak at/above for ≥ required days (`flag`), empty/`None` history (`unknown`).
  - `test_margin_debt.py` — canned `openpyxl.Workbook()` built in-memory + `monkeypatch.
    setattr("requests.get", ...)` (mirror `test_abs_cpi.py` exactly); cases: normal YoY
    calc, YoY above flag threshold, too-short history (`unknown`), fetch failure
    (`unknown`).
  - `test_insider_trend.py` — monkeypatch `goat.openinsider.fetch_screener_filings`;
    cases: no hot watchlist (empty list, no fetch attempted), aggregate ratio below/at
    threshold, both-fetches-fail (`unknown`), a ticker with zero activity is omitted from
    results entirely.
  - `test_market_cap_milestone.py` — monkeypatch `goat.sp500_universe.get_or_refresh_
    sp500_constituents` and `mytrader.market_data.fetch_ticker_data`; cases: correct
    leader selection among several tickers, correct rung computation, empty constituents
    (`unknown`).
  - `test_report.py` — canned inputs for all 4 live markers + empty watchlist; assert all
    14 marker numbers appear somewhere in the rendered output (a simple `"| {n} |" in
    output for n in range(1, 15)` check is enough), and that the 10 placeholder rows
    reference the handoff doc path.
  - `test_alerts.py` — mirror `investments/goat/goat/tests/test_monitor.py`'s
    `_fake_notifications_module` + `monkeypatch.setitem(sys.modules, "notifications", ...)`
    pattern; cases: first-time firing alerts, repeat firing across two calls does NOT
    re-alert, a transition back to not-firing then firing again DOES re-alert.
- **PATTERN**: `investments/goat/goat/tests/test_heartbeat_scan.py` (whole file, discovery-
  orchestrator monkeypatch style), `investments/goat/goat/tests/test_monitor.py` (`maybe_
  notify` test pattern), `investments/my-trader/mytrader/tests/test_abs_cpi.py` (XLSX
  parsing test pattern), `investments/my-trader/mytrader/tests/test_macro_indicators.py`
  (FRED-mocking pattern).
- **VALIDATE**: `uv run --directory investments/fourteen-crash-signals-daily-check python -m
  pytest -q` (full new-package suite).

### Task 14: CREATE `scripts/systemd/second-brain-fourteen-signals.timer` and `.service`

- **IMPLEMENT**:
  `second-brain-fourteen-signals.service`:
  ```ini
  [Unit]
  Description=Fourteen Crash Signals Daily Check
  After=network.target

  [Service]
  Type=oneshot
  User=secondbrain
  WorkingDirectory=/home/secondbrain/second-brain/investments/fourteen-crash-signals-daily-check
  ExecStart=/home/secondbrain/second-brain/investments/.venv/bin/python -m fourteen_crash_signals_daily_check.main daily-check
  StandardOutput=append:/home/secondbrain/second-brain/investments/fourteen-crash-signals-daily-check/daily_check_runs.log
  StandardError=append:/home/secondbrain/second-brain/investments/fourteen-crash-signals-daily-check/daily_check_runs.log
  ```
  `second-brain-fourteen-signals.timer`:
  ```ini
  [Unit]
  Description=Fourteen Crash Signals Daily Check Timer
  Requires=second-brain-fourteen-signals.service

  [Timer]
  OnCalendar=*-*-* 22:05:00 UTC
  Persistent=true

  [Install]
  WantedBy=timers.target
  ```
- **PATTERN**: `scripts/systemd/second-brain-goat-insider-scan.timer`/`.service` (identical
  shape).
- **GOTCHA**: This is a **manual deployment step** — creating these files does not deploy
  them. Actually registering + enabling the timer on the VPS (`scp` both files,
  `systemctl daemon-reload`, `systemctl enable --now second-brain-fourteen-signals.timer`,
  plus a one-time `uv sync` on the VPS's shared venv to pick up the new workspace member)
  is Shaun's call to run himself or explicitly request as a follow-up — do not attempt this
  from within the plan-execution session.
- **VALIDATE**: N/A (files only).

### Task 15: UPDATE `investments/TOOLS.md`

- **IMPLEMENT**: Add one row to the "Automated (scheduled)" table:
  ```markdown
  | **Fourteen Crash Signals Daily Check** | Tracks 4 of the 14 crash-warning markers (credit spread streak, margin debt YoY, insider selling trend, market-cap milestone) against a dynamically-recomputed hot-company watchlist; other 10 markers pending future phases | VPS systemd (`second-brain-fourteen-signals.timer`) | Daily, 22:05 UTC |
  ```
  Add a manual on-demand row too:
  ```markdown
  | **Fourteen Crash Signals (on-demand)** | Same daily check the timer runs, right now | `uv run --directory investments/fourteen-crash-signals-daily-check python -m fourteen_crash_signals_daily_check.main daily-check` |
  ```
- **PATTERN**: existing table rows' wording/column shape.
- **VALIDATE**: N/A (doc-only).

### Task 16: UPDATE `scripts/deploy.ps1`

- **IMPLEMENT**: Add to the `$TIMERS` array (after `"second-brain-goat-insider-scan.timer"`):
  ```powershell
  "second-brain-goat-insider-scan.timer",
  "second-brain-fourteen-signals.timer"
  ```
- **PATTERN**: `scripts/deploy.ps1:17-25`.
- **GOTCHA**: This array entry only matters once the timer is actually enabled on the VPS
  (Task 14's deferred manual step) — adding it now is safe (the stop/start commands
  already tolerate a not-yet-existing unit via `2>/dev/null || true`, per `Stop-Timers`/
  `Start-Timers`'s existing implementation), and avoids a second forgotten edit later.
- **VALIDATE**: N/A (script-only; no automated test harness for `deploy.ps1` itself).

---

## TESTING STRATEGY

### Unit Tests
Every new module gets unit tests following this project's existing `pytest` + `monkeypatch`
conventions — no live network calls in the automated suite (FRED, FINRA, OpenInsider, and
yfinance calls are all monkeypatched). See Task 13 for the full per-module test list.

### Integration Tests
None planned beyond the orchestrator-level `cmd_daily_check` flow, which is exercised
end-to-end only by Task 12's manual validation (live network) — matches this codebase's
existing "no separate integration tier" precedent (see the insider-scanner plan's own
Testing Strategy section for the same reasoning).

### Edge Cases
- No rising sectors this run — hot watchlist is empty; `insider_trend.check_insider_trend`
  must return `[]` without attempting a fetch.
- FRED/FINRA/OpenInsider/yfinance each independently unavailable — every check degrades to
  `"unknown"`, never raises, never wipes the previous report.
- Credit spread streak exactly at the boundary (streak_days == required days) — must flag,
  not just when strictly greater.
- Margin debt history shorter than 13 months (e.g. a fresh/empty DB on first run) —
  `"unknown"`, not a crash on a negative index.
- Market cap leader changes between runs, but stays within the same $500B rung — a repeat
  `verdict="flag"` from `market_cap_milestone.py` must NOT re-alert (same rung key).
- Insider trend ticker with only purchases and zero sales (`ratio == 0.0`, not a
  divide-by-zero) and the reverse (only sales, zero purchases — `ratio == inf`, must still
  compare correctly against `SIGNALS_INSIDER_TREND_NET_SELL_FLAG_RATIO` without raising).

---

## VALIDATION COMMANDS

### Level 1: Syntax & Style
```powershell
uv run --directory investments/fourteen-crash-signals-daily-check ruff check fourteen_crash_signals_daily_check/
uv run --directory investments/fourteen-crash-signals-daily-check mypy fourteen_crash_signals_daily_check/credit_spread.py fourteen_crash_signals_daily_check/margin_debt.py fourteen_crash_signals_daily_check/insider_trend.py fourteen_crash_signals_daily_check/market_cap_milestone.py fourteen_crash_signals_daily_check/watchlist.py
uv run --directory investments/goat ruff check goat/openinsider.py
```

### Level 2: Unit Tests
```powershell
uv sync --directory investments
uv run --directory investments/fourteen-crash-signals-daily-check python -m pytest -q
uv run --directory investments/goat python -m pytest -q
```

### Level 3: Integration Tests
Covered by Level 2 (see Testing Strategy — no separate tier in this codebase).

### Level 4: Manual Validation
```powershell
uv run --directory investments/fourteen-crash-signals-daily-check python -m fourteen_crash_signals_daily_check.main daily-check
```
Confirm `investments/fourteen-crash-signals-daily-check/signals-report.md` is created with
all 14 marker rows present (4 live, 10 placeholder). Inspect the hot watchlist table and
sanity-check the names against what you'd expect today (Design Decision #1 — this is a
new, unvalidated heuristic; if the output looks wrong, that's exactly what this manual step
is for). Re-run and confirm no duplicate WhatsApp alert fires for an unchanged state.

### Level 5: Additional Validation
N/A — no MCP servers relevant to this feature.

---

## ACCEPTANCE CRITERIA

- [ ] `investments/fourteen-crash-signals-daily-check/` exists as a working uv workspace
      member; `uv sync --directory investments` succeeds from a clean checkout.
- [ ] `daily-check` CLI command runs end-to-end and writes `signals-report.md` with all 14
      marker rows (4 live, 10 "not yet automated" placeholders referencing the handoff doc).
- [ ] Hot-company watchlist resolves to real mega-cap tickers today without any hardcoded
      ticker symbol anywhere in the new package's code.
- [ ] Each of the 4 live markers degrades to `"unknown"` (not a crash, not a false `"ok"`)
      when its upstream data source is unavailable.
- [ ] WhatsApp alert fires only on a marker's transition into `is_firing=True`; an unchanged
      or already-firing state on a subsequent run does not re-alert.
- [ ] Existing `goat` test suite and `fetch_screener_filings` callers are unaffected by the
      new optional `filing_date_days` param (default `7` preserves current behavior).
- [ ] All validation commands pass with zero errors.
- [ ] Systemd timer/service files created (VPS registration + `uv sync` on the VPS left as
      an explicit follow-up for Shaun, per Task 14's GOTCHA).

---

## COMPLETION CHECKLIST

- [ ] All 16 tasks completed in order.
- [ ] Each task's validation command passed immediately after that task.
- [ ] Full new-package test suite passes, plus `goat`'s existing suite still passes
      unmodified.
- [ ] `ruff check` and `mypy` clean on every new/modified module.
- [ ] Manual `daily-check` run confirmed against live data sources; hot watchlist output
      sanity-checked by Shaun (Design Decision #1 is a new heuristic, not a rubber stamp).
- [ ] Acceptance criteria all met.
- [ ] `TOOLS.md` and `deploy.ps1` updated.
- [ ] The "NEXT STEPS FOR SHAUN" block below has been copied into the final `/execute`
      output report, verbatim, as the last thing in the summary — not skipped, not
      paraphrased away. This is how Shaun finds out what to do next; it does not happen
      automatically otherwise.

---

## NEXT STEPS FOR SHAUN (read this once Phase 1 ships)

Phase 1 only covers 4 of the 14 markers. Here's exactly what to do next:

1. **Look at the manual validation output** (Level 4 above) — specifically the hot-company
   watchlist table in `signals-report.md`. Does it contain the names you'd expect right now
   (today: Nvidia/Palantir/Alphabet/Meta/Oracle/Microsoft-type names)? This heuristic
   (Design Decision #1) hasn't been signed off by you yet — this is that sign-off moment.
2. **Decide which slice to build next — Phase 2 or Phase 3** (you don't have to do both, or
   in this order, but Phase 2 is the easier/lower-risk one to do first):
   - **Phase 2** = markers #2, #4, #9, #12. Sources are already identified (SEC EDGAR,
     yfinance cashflow, FINRA TRACE) — mostly codebase-pattern work, not research.
   - **Phase 3** = markers #1, #3, #6, #7, #11, #13. No confirmed free data source for any
     of them yet — needs real source-hunting during planning, not just implementation.
3. **Say so explicitly**, e.g. *"write a handoff doc for phase 2 of the crash signals
   tool, covering markers #2, #4, #9, #12"*. Claude will draft
   `investments/my-trader/14-signals-crash-warning-phase2-handoff.md` (or similar),
   following the same fact-check/decisions format as the Phase 1 handoff
   (`14-signals-crash-warning-handoff.md`).
4. **Once that handoff doc exists and you're happy with it, run `/plan-feature` yourself**
   pointing at it. This step is never auto-triggered — per this project's convention,
   invoking `/plan-feature` is always your call, not something Claude chains into on its
   own after finishing a phase.
5. **The resulting Phase 2 (or 3) plan should read this phase's `db.py`/`config.py`/
   `watchlist.py`** as Context References, and plug into the existing
   `signals_hot_watchlist`/`signals_alert_state` tables rather than re-inventing them.

---

## NOTES

- **Why only 4 of the 14 markers**: see this plan's header and Problem Statement — 6 of the
  remaining 10 have no confirmed free structured data source (a research task, not a spec-
  from-day-one task), and 4 more (#2, #4, #9, #12) depend on the hot-watchlist layer this
  plan builds but need their own per-issuer fetch logic (SEC EDGAR 10-Q parsing, FINRA TRACE
  bond-yield data, Super Bowl ad tracking, bond-yield-vs-Treasury spread) that wasn't
  in scope for "ready to build without further research."
- **Two credit-spread checks now coexist** (`mytrader.macro_indicators.check_credit_
  spreads` at 5.0pp single-day, this plan's `credit_spread.check_credit_spread_streak` at
  3.5pp/21-trading-day-streak) — this is deliberate, not a duplicate to consolidate later
  (see Design Decision #2).
- **The hot-watchlist mechanism (Design Decision #1) is the single least-validated part of
  this plan** — it's a reasonable, reuse-heavy proposal, not something Shaun explicitly
  signed off on in the handoff (which only said the watchlist must exist and must be
  dynamic, not exactly how). Treat Task 12's manual-validation output as the real check on
  whether this heuristic is worth keeping as-is.

## NOTES — How to create Phase 2 / Phase 3

This plan deliberately does not cover markers #1, #2, #3, #4, #6, #7, #9, #11, #12, #13.
Once this phase has shipped and Shaun has seen the hot-watchlist output in practice, the
next phase(s) get created the same way this one was:

1. **Write a new handoff/decisions doc** (not required, but this project's own convention —
   see `14-signals-crash-warning-handoff.md` and the `insider-trading-scanner-handoff.md`
   precedent) covering whichever next slice of markers to tackle. A sensible split:
   - **Phase 2**: the per-issuer markers that reuse this phase's hot-watchlist layer
     directly (#2 off-balance-sheet leases via SEC EDGAR 10-Q/10-K — reuse `mytrader/
     sec_filings.py`'s existing CIK-resolution + filing-fetch pattern; #4 capex-vs-cash-flow
     via yfinance cashflow statements; #12 bond-yield-vs-Treasury proxy via FINRA's free
     TRACE API; #9 Super Bowl ad share, a once-a-year check). This phase's research is
     mostly done (the handoff already names FINRA TRACE, SEC EDGAR, and yfinance cashflow
     as the sources) — writing that plan is mostly codebase-pattern research, not open
     internet research.
   - **Phase 3**: the six markers with no confirmed free structured source (#1, #3, #6, #7,
     #11, #13) — these genuinely need source-hunting during planning itself (the handoff
     flags them as "no single free structured feed found... a daily news/RSS/EDGAR-8-K scan
     against known trigger phrases," which is real design work, not a spec to hand an
     execution agent yet).
2. **Shaun runs `/plan-feature` again**, pointing at whichever doc/description covers that
   next slice — same as this session started. Per this project's own convention
   (`feedback_plan_feature_user_only` in the assistant's memory), invoking `/plan-feature`
   is always Shaun's call, never auto-chained from finishing this phase.
3. **Each new plan should explicitly read this plan's `db.py`/`config.py`/`watchlist.py`**
   (once built) as its own "Context References" — the later phases plug into
   `signals_hot_watchlist` and `signals_alert_state` rather than re-inventing either table.
