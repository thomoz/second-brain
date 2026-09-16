# Feature: Goat DMA Breakout Scanner

The following plan should be complete, but it's important to validate documentation and
codebase patterns and task sanity before implementing. Pay special attention to naming
of existing utils/types/models — import from the right files, and note the `.AX`-suffix
ticker convention flagged as a GOTCHA in Task 2 before writing any dedup code.

## Feature Description

A new daily discovery scan inside the existing `goat` package that flags any US
(S&P 500) or Australian (ASX 200) stock whose closing price has just crossed above its
150-day or 200-day moving average — a plain, direct "opportunity found" signal, distinct
from the two existing-but-different checks already in `goat` (Heartbeat Scan's compound
base+breakout pattern, and Monitor's existing-holdings-only downside 150DMA exit alert).

## User Story

As Shaun (advisor-mode Second Brain user)
I want a daily scan across the whole S&P 500 + ASX 200 universe for stocks that just
crossed above their 150DMA or 200DMA
So that I get a broad "worth a look" discovery list every morning without having to spot
these crossovers myself on individual charts

## Problem Statement

Shaun asked "do we have a tool that looks for stocks that have just broken above the
150DMA or 200DMA?" and the answer was no — the two existing MA-cross tools in `goat`
solve different, narrower problems (Heartbeat Scan requires a whole compound base
pattern within rising sectors only; Monitor's exit check only watches tickers Shaun
already holds/watches, and only for the *downside* cross). There is no broad, simple,
upside-only discovery scan.

## Solution Statement

Add a new module `goat/dma_breakout_scan.py` that reuses the codebase's established
sign-flip cross-detection idiom (`sector_rotation.check_sector_breakout`), applied
per-stock to a combined S&P 500 + ASX 200 universe, for the 150-day and 200-day MAs
independently. Gate noise with an ethical filter, a liquidity/market-cap floor, and the
existing fundamentals-survival-context insolvency suppression. Stage genuinely new hits
into the existing `goat_pending_candidates` table (`source="goat_dma_breakout_scan"`),
render a pending-review markdown report, and fire the existing WhatsApp+toast
`maybe_notify` pattern on a fresh-hit day. Wire a new CLI subcommand, VPS systemd timer,
and `investments/TOOLS.md` entries — no new package, no new database.

## Feature Metadata

**Feature Type**: New Capability
**Estimated Complexity**: Medium
**Primary Systems Affected**: `investments/goat` package (new module + config + CLI +
tests), VPS systemd (new timer/service), `investments/TOOLS.md`, `scripts/deploy.ps1`
**Dependencies**: None new — reuses `yfinance` (via `goat/price_history.py` and
`mytrader/market_data.py`), `pandas`, existing `mytrader`/`goat` modules.

---

## CONTEXT REFERENCES

### Relevant Codebase Files — READ THESE BEFORE IMPLEMENTING

- `investments/goat/goat/sector_rotation.py` (lines 53-113, `check_sector_breakout`) —
  **the exact sign-flip cross-detection idiom to parameterize and reuse**: `diff = close
  - ma`, `sign = diff.gt(0).astype(int) - diff.lt(0).astype(int)`, `sign_changed =
  sign.diff().fillna(0) != 0`, last sign-change date, `trading_days_since_cross =
  (len(close) - 1) - cross_pos`, `fresh = trading_days_since_cross <= recency_days`.
  Verdict convention: `"interesting"` on a fresh qualifying cross, `"ok"` otherwise,
  `"unknown"` on insufficient history. This tool's `check_ma_cross` is this function
  generalized over `ma_days` instead of hardcoded to 50.
- `investments/goat/goat/heartbeat.py` (lines 1-33, module docstring) — **explicit,
  deliberate policy**: this codebase intentionally keeps independent copies of the
  cross-detection idiom (`macro_indicators.check_gold_trend`,
  `sector_rotation.check_sector_breakout`, and now this new one) rather than factoring
  them into a shared helper. Do **not** refactor `sector_rotation.py` or `heartbeat.py`
  to import from the new module or vice versa. Writing one clean parameterized function
  *inside* `dma_breakout_scan.py` (called once for 150, once for 200) is fine and is the
  correct internal shape.
- `investments/goat/goat/heartbeat_scan.py` (whole file, 117 lines) — **the orchestrator
  shape to mirror almost exactly**: loop a universe, `price_history.fetch_close_history`
  per ticker, run the check, on a hit fetch `market_data.fetch_ticker_data` once and run
  `fundamentals_context.compute_survival_context`, suppress on `insolvency_risk`, dedup
  via `mt_db.get_holding_row` / `mt_db.get_watchlist_row` /
  `db.get_goat_pending_candidate`, stage via `db.insert_goat_pending_candidate`, return a
  result dict, render + write a pending-review markdown table. `render_...`/`write_...`
  function pair pattern at lines 85-117 — copy verbatim shape (table header `| Ticker |
  Sector | Signal | Flagged |`, `Last auto-generated:` footer).
- `investments/goat/goat/monitor.py` (lines 155-207, `maybe_notify`) — reuse directly
  (import from `goat.monitor`, do not reimplement). Call as `maybe_notify({"new_alerts":
  []}, new_candidates=result["new_candidates"], candidate_label="new DMA breakout
  candidate(s)")` — same call shape as `cmd_scan_heartbeat` in `main.py` line 108-111.
  Silent (returns immediately) when both `new_alerts` and `candidates` are empty — do
  not add a separate silence check in the new module.
- `investments/goat/goat/db.py` (lines 157-180, `get_goat_pending_candidate` /
  `insert_goat_pending_candidate` / `get_all_goat_pending_candidates`) — the existing
  generic staging table, reused as-is. **`ticker` is `UNIQUE` with no `source` in the
  key** (line 30 of the `CREATE TABLE` in this file) — a ticker already staged by
  Heartbeat Scan (or any other source) must be skipped here too, exactly like
  `heartbeat_scan.py` line 63 (`if db.get_goat_pending_candidate(conn, ticker) is not
  None: continue`). Surface this in the report text (see Task 5) so a "0 new" day with a
  nonzero cross count isn't mysterious.
- `investments/goat/goat/price_history.py` (whole file, 35 lines,
  `fetch_close_history(ticker, lookback_days) -> pd.Series | None`) — reuse as-is. It
  already tries `tickers.normalize(ticker)` then `tickers.asx_variant(ticker)` as an
  automatic fallback, but pass the already-fully-qualified ticker (see Task 2's GOTCHA)
  so it matches on the first attempt rather than relying on the fallback.
- `investments/goat/goat/sp500_universe.py` (whole file,
  `get_or_refresh_sp500_constituents(conn) -> list[sqlite3.Row]`) — reuse as-is for the
  US leg. Each row has `ticker`, `security`, `gics_sector`. Cached in
  `goat_sp500_constituents`, refreshed every `GOAT_SP500_CACHE_TTL_DAYS` (7).
- `investments/my-trader/mytrader/asx200_universe.py` (whole file,
  `fetch_asx200_constituents() -> list[dict] | None`) — reuse as-is for the AU leg. Each
  dict has `ticker` (bare code, e.g. `"CBA"`), `company`, `sector`. **No DB cache** — this
  re-scrapes Wikipedia every run (unlike `sp500_universe`); returns `None` on scrape
  failure — handle as "AU leg unavailable this run", do not crash the whole scan (mirror
  `cash_value_scan.run_scan` line 226-233's `if asx_coarse is not None else ([], 0)`
  pattern).
- `investments/my-trader/mytrader/cash_value_scan.py` — the **combined US+ASX
  broad-universe scan precedent** to mirror for structure, not import from (my-trader
  cannot import from `goat` — wrong dependency direction; this new module lives in
  `goat` and imports `mytrader.asx200_universe` directly, same direction
  `openinsider.py`'s move already established):
  - Lines 160-161: `yf_ticker = bare if market == "US" else tickers.asx_variant(bare)` —
    **the ASX ticker-qualification pattern to copy exactly** (see Task 2 GOTCHA — in
    this new tool the qualified ticker *is* `ticker`, not a separate `yf_ticker`, because
    it must match how my-trader's holdings/watchlist tables key ASX rows).
  - Lines 217-254 (`run_scan`): the combined-universe + `cached_session()` +
    per-market-enrichment shape.
  - Line 238 (`asx_usable < len(asx_coarse) * config.CASH_VALUE_DEGRADED_ASX_MIN_FRACTION`)
    — the degraded-run tripwire; **not needed here** (this tool is price-history-only
    for the bulk of the universe, not a `.info` call per name, so it's far lighter than
    Cash-Value Scan's ~700 sequential `.info` fetches — see handoff doc point 7). Do not
    port this tripwire.
  - Lines 168-170 (`ethical_check(bare)` → `excluded, review_reason`): the ethical-filter
    call shape to copy — `excluded=True` rows are dropped entirely (never shown, never
    checked further); `review_reason` (a `"REVIEW: ..."` string or `None`) is carried
    into the result/report as a tag, not used to drop the row.
- `O:\AI\Dynamous\Courses\second-brain-workshop\scripts\ethical_filter.py` — **wrong
  path, does not exist**. The real module is
  `investments/briefs-finance/scripts/ethical_filter.py` (`check_ticker(ticker) ->
  tuple[bool, str | None]`), imported everywhere else in this workspace as `from
  scripts.ethical_filter import check_ticker` (a shared `scripts` top-level package
  resolved via the uv workspace, same as `scripts.config.DB_PATH` in
  `goat/config.py` line 7) — import it exactly that way, do not construct a path to
  `investments/briefs-finance/`.
- `investments/goat/goat/fundamentals_context.py` (whole file,
  `compute_survival_context(ticker, data) -> dict`) — reuse as-is. `data` is a
  `mytrader.market_data.TickerData | None`. Returns a dict with `insolvency_risk: bool`
  and `summary: str`. Only `insolvency_risk` gates staging (suppress, don't stage); the
  rest is informational, appended to `signal_detail` exactly like
  `heartbeat_scan.py` line 66: `f"{check.detail}; survival context: {context['summary']}"`.
- `investments/my-trader/mytrader/market_data.py` (lines 13-19 `TickerData`, line 25
  `cached_session()`, line 71 `fetch_ticker_data(ticker) -> TickerData | None`) —
  `fetch_ticker_data` already does its own `.AX` fallback internally, but (matching the
  ticker-qualification GOTCHA below) call it with the already-qualified ticker for AU
  rows to avoid any ambiguity with a same-symbol US ticker. Wrap the whole scan's
  fundamentals-lookup calls in `with market_data.cached_session():` — cheap here since
  it's only called on actual cross hits, not the full universe, but costs nothing to
  include and matches the codebase's established pattern (`cash_value_scan.py` line
  228).
- `investments/my-trader/mytrader/tickers.py` (whole file, 15 lines) —
  `normalize(ticker) -> str` (uppercase + `BRK.B`→`BRK-B` style share-class map),
  `asx_variant(ticker) -> str` (`normalize(ticker) + ".AX"`).
- `investments/my-trader/mytrader/checks/__init__.py` (whole file) — `CheckResult`
  dataclass: `name: str`, `verdict: str` (`"ok" | "flag" | "interesting" | "unknown"` in
  practice — this tool only ever produces `"interesting"`, `"ok"`, `"unknown"`, never
  `"flag"`, matching `sector_rotation`/`heartbeat`'s own opportunity-signal convention),
  `detail: str`, `data: dict`.
- `investments/my-trader/mytrader/db.py` (search `get_holding_row`, `get_watchlist_row`,
  `get_all_holdings`, `get_all_watchlist`) — dedup lookups, imported as `from mytrader
  import db as mt_db` (the established alias in every `goat` module that touches
  my-trader's tables).
- `investments/my-trader/mytrader/config.py` (lines 402, `GOLD_MA_HISTORY_LOOKBACK_DAYS
  = 500`) and `investments/goat/goat/config.py` (line 240,
  `GOAT_HEARTBEAT_HISTORY_LOOKBACK_DAYS = 500`) — the precedent for 500 calendar days of
  history for a 200-day-MA-class check; reuse 500 (a new named constant, same number)
  per the handoff doc's explicit instruction.
- `investments/goat/goat/config.py` (whole file) — every new constant goes here (see
  Task 1). Follow the file's existing comment style: a `#`-block above each constant
  explaining the number's provenance and whether it's tunable.
- `investments/goat/goat/main.py` (whole file, 297 lines) — CLI dispatch pattern.
  `cmd_scan_heartbeat` (lines 100-117) is the closest template: open conn via
  `_open_conn()`, run the scan, close conn, write the report, call `maybe_notify` with a
  scan-specific `candidate_label`, print a one-line summary. `main()` (lines 235-296):
  add a new `subparsers.add_parser("scan-dma-breakout", help="...")` and a
  `dispatch["scan-dma-breakout"] = cmd_scan_dma_breakout` entry.
- `investments/goat/goat/tests/conftest.py` (whole file) — shared fixtures:
  `db_conn` (fresh sqlite DB with `init_mytrader_tables` + `init_goat_tables`),
  `_isolate_goat_report_path` (autouse, monkeypatches report path constants to
  `tmp_path` — **add the new `GOAT_DMA_BREAKOUT_CANDIDATES_MD_PATH` constant to this
  fixture**, line ~30-47, or every new test will write into the real repo file),
  `_no_real_price_history_fetch` (autouse, stubs `goat.price_history.fetch_close_history`
  globally so no test hits real yfinance by default).
- `investments/goat/goat/tests/test_heartbeat_scan.py` (whole file, 152 lines) — the
  orchestration test pattern to mirror: a `_patch_common(monkeypatch, ...)` helper that
  monkeypatches every network/DB-adjacent call, then tests for: stages a new candidate,
  skips a ticker already a holding, skips a ticker already watchlisted, stays quiet on
  repeat run (no re-staging), suppresses staging on insolvency risk, skips a ticker with
  no price history (must not crash), skips an unmapped/malformed universe row (must not
  crash), and a `render_..._report` test.
- `investments/goat/goat/tests/test_sector_rotation.py` (whole file, 120 lines) — the
  **cross-detection unit-test pattern** to mirror for `check_ma_cross`:
  `_series_with_cross(days_since_cross, rising, crossed_above)` and
  `_declining_then_spike_series(...)` series-builder helpers, then one test per verdict
  branch (fresh rising cross → `"interesting"`, stale cross → `"ok"`, cross with MA still
  falling — **note**: this tool does NOT gate on slope, so the equivalent test here
  should assert `"interesting"` fires *regardless* of slope, unlike
  `check_sector_breakout`'s own wrong-slope test — see Task 2's `2a` design decision),
  downside cross → `"ok"`, no cross in history → `"ok"`, insufficient history →
  `"unknown"`.
- `investments/goat/pyproject.toml` — no changes needed (module lives inside the
  existing `goat` package, no new dependency).
- `scripts/systemd/second-brain-goat-heartbeat-scan.timer` and `.service` — copy
  near-verbatim (see Task 8).
- `scripts/deploy.ps1` (lines 17-29, `$TIMERS`) — add the new timer name to this array
  (see Task 8).
- `investments/TOOLS.md` (lines 12-47) — add rows to the "Daily Read" table and the
  "Automated (scheduled)" table (see Task 9).
- `investments/goat/goat/holdings.md`, `investments/my-trader/watchlist.md` — **read
  these to confirm the GOTCHA below before writing any code**: `investments/my-trader/watchlist.md`
  line 19 (`XRO.AX`) and `investments/my-trader/holdings.md` lines 7/11/12/15
  (`GOLD.AX`, `OOO.AX`, `PMGOLD.AX`, `URNM.AX`) — my-trader's holdings/watchlist tables
  store ASX tickers **with the `.AX` suffix**, not the bare exchange code.

### New Files to Create

- `investments/goat/goat/dma_breakout_scan.py` — the scan module (see Task 2-5).
- `investments/goat/goat/tests/test_dma_breakout_scan.py` — unit + orchestration tests
  (see Task 10).
- `scripts/systemd/second-brain-goat-dma-breakout-scan.timer` — new VPS timer (Task 8).
- `scripts/systemd/second-brain-goat-dma-breakout-scan.service` — new VPS service (Task 8).

### Patterns to Follow

**Naming convention**: `GOAT_DMA_BREAKOUT_*` prefix for every new config constant,
matching `GOAT_HEARTBEAT_*` / `GOAT_SECTOR_*` / `GOAT_INSIDER_*` per-feature prefixing
already used throughout `goat/config.py`.

**Error handling**: per-ticker `try/except Exception as e: print(f"[goat-dma-breakout-scan]
error checking {ticker}: {e}")` inside the scan loop — one bad ticker must never sink the
whole run (see `heartbeat_scan.py` lines 42-73, `cash_value_scan.py` line 210-211).

**Logging**: `print(f"[goat-dma-breakout-scan] ...")` prefix convention, matching every
other `goat` module's bracketed-module-name log prefix.

**Report file convention**: `# <Title> — Pending Review` heading, an explanatory
paragraph naming what triggers a row and how to act on it (`promote-candidate` /
`dismiss-candidate`), a markdown table, `Last auto-generated: {date}.` footer — see
`heartbeat_scan.py` lines 85-110 and `monitor.py` lines 286-305 for two near-identical
examples to copy.

**Other Relevant Patterns**:
- Every DB-touching function takes `conn: sqlite3.Connection` as an explicit first
  parameter (no module-global connection anywhere in this codebase).
- `from __future__ import annotations` is the first line of every module in this
  workspace.
- Module docstrings in this codebase are long and explain *why*, including prior
  decisions/history and what NOT to do — see `heartbeat.py`'s docstring as the deepest
  example. Write a proportionate one for `dma_breakout_scan.py` (what this tool is, how
  it differs from Heartbeat Scan and Monitor's exit check, the "independent 150/200
  checks, not a gate" design decision, and the ticker-qualification GOTCHA).

---

## IMPLEMENTATION PLAN

### Phase 1: Foundation

Add every new config constant to `goat/config.py`. No code logic yet — this phase just
establishes the tunable surface the rest of the feature reads from.

### Phase 2: Core Implementation

Build `dma_breakout_scan.py`: universe fetch, the parameterized cross-check, and the
per-ticker orchestration loop (price fetch → cross check → liquidity/survival gates →
dedup → stage).

### Phase 3: Integration

Wire the report render/write functions, the CLI subcommand in `main.py`, and
`maybe_notify`.

### Phase 4: Testing & Validation

Unit-test `check_ma_cross` against hand-built price series (mirroring
`test_sector_rotation.py`); orchestration-test `run_dma_breakout_scan` against mocked
universe/price/fundamentals calls (mirroring `test_heartbeat_scan.py`); run the real CLI
command once against live data via `invoke_investments.ps1` and manually inspect the
output report.

---

## STEP-BY-STEP TASKS

Execute in order. Each task is atomic and independently testable.

### Task 1: ADD config constants to `investments/goat/goat/config.py`

- **IMPLEMENT**: Append a new commented section (after the Hormuz section at the end of
  the file, following the file's existing per-feature section-comment style):
  ```python
  # DMA Breakout Scanner, per investments/goat/dma-breakout-scanner-handoff.md and
  # .agent/plans/goat-dma-breakout-scanner.md -- a broad discovery scan (S&P 500 +
  # ASX 200) for stocks that just crossed ABOVE their 150-day or 200-day MA. Distinct
  # from GOAT_SECTOR_MA_SHORT_DAYS (50DMA, Heartbeat Scan's entry signal) and
  # GOAT_MA_LONG_DAYS (150DMA, Monitor's holdings-only DOWNSIDE exit check) -- this is
  # a plain upside cross, two independent checks (150 AND 200 are each reported, not
  # gated together), no base-pattern requirement, no rising-sector filter, whole
  # universe not just holdings/watchlist.
  GOAT_DMA_BREAKOUT_MA_DAYS: tuple[int, int] = (150, 200)
  GOAT_DMA_BREAKOUT_HISTORY_LOOKBACK_DAYS = 500  # calendar days -- same margin
      # philosophy as GOAT_HEARTBEAT_HISTORY_LOOKBACK_DAYS / GOLD_MA_HISTORY_LOOKBACK_DAYS
      # (mytrader/config.py), sized for a 200-day MA + slope + recency margin.
  GOAT_DMA_BREAKOUT_CROSS_RECENCY_DAYS = 10  # a cross older than this no longer counts
      # as "just crossed" -- same number and same reasoning as
      # GOAT_SECTOR_CROSS_RECENCY_DAYS (Shaun's own words describing the LULU chart
      # that originally prompted the cross-detection idiom). v1/tunable -- a 150/200DMA
      # is slower-moving than a 50DMA, so this may need widening after the first live
      # run; start here for consistency with every other cross check in this codebase.
  GOAT_DMA_BREAKOUT_MIN_MARKET_CAP_USD = 300_000_000.0  # liquidity/quality floor for
      # US names -- a raw cross-detection scan over ~500 S&P 500 names is already
      # large-cap by construction, but this also gates the ASX 200's long tail.
      # Deliberately higher than CASH_VALUE_MICRO_CAP_TAG_USD (50M, a TAG not a floor
      # on a value screen that wants to see micro-caps) -- this is a discovery scan
      # meant to surface tradeable opportunities. v1/tunable, not literature-final.
  GOAT_DMA_BREAKOUT_MIN_MARKET_CAP_AUD = 300_000_000.0  # same number/reasoning as the
      # USD floor -- both universes are already large/mid-cap index constituents, so a
      # single round number for both currencies is fine (this is a coarse quality
      # floor, not a precise cross-currency comparison).
  GOAT_DMA_BREAKOUT_MIN_AVG_VOLUME = 100_000  # shares/day -- matches Finviz's own
      # sh_avgvol_o100 filter already used by finviz_screener.py for the same
      # liquidity-floor purpose, applied here via yfinance's averageVolume field
      # instead of a Finviz screener param since this scan's universe comes from
      # S&P 500 / ASX 200 constituent lists, not a Finviz screen.
  GOAT_DMA_BREAKOUT_CANDIDATES_MD_PATH = GOAT_DIR / "dma-breakout-candidates-pending-review.md"
  ```
- **PATTERN**: `goat/config.py` lines 240-254 (`GOAT_HEARTBEAT_HISTORY_LOOKBACK_DAYS`
  section) for comment density/style; line 90-91 for the `*_MD_PATH` constant pattern.
- **GOTCHA**: `GOAT_DIR` is already defined at the top of the file (line 9) — do not
  redefine it.
- **VALIDATE**: `python -c "from goat import config; print(config.GOAT_DMA_BREAKOUT_MA_DAYS, config.GOAT_DMA_BREAKOUT_CANDIDATES_MD_PATH)"`
  run via `uv run --directory investments/goat python -c "..."` (see repo-wide convention
  — never run a package against the live DB locally, but a bare import with no DB touch
  is safe locally).

### Task 2: CREATE `investments/goat/goat/dma_breakout_scan.py` — universe fetch + cross check

- **IMPLEMENT**: Module docstring (see "Other Relevant Patterns" above for required
  content). Then:

  ```python
  from __future__ import annotations

  import sqlite3
  from datetime import date
  from typing import Any

  import pandas as pd
  from mytrader import asx200_universe, db as mt_db, market_data, tickers
  from mytrader.checks import CheckResult
  from scripts.ethical_filter import check_ticker as ethical_check

  from . import config, db, fundamentals_context, price_history, sp500_universe


  def fetch_universe_constituents(conn: sqlite3.Connection) -> list[dict[str, Any]]:
      """Combined S&P 500 + ASX 200 universe, each row already ticker-qualified (see
      module GOTCHA) and ethical-filtered. US tickers come from the cached
      goat_sp500_constituents table; ASX tickers are re-scraped from Wikipedia every
      run (asx200_universe has no DB cache) and returned as [] (not None/crash) on a
      scrape failure -- see run_dma_breakout_scan's asx-unavailable handling."""
      rows: list[dict[str, Any]] = []

      for c in sp500_universe.get_or_refresh_sp500_constituents(conn):
          bare = c["ticker"]
          excluded, review_reason = ethical_check(bare)
          if excluded:
              continue
          rows.append({
              "ticker": tickers.normalize(bare), "label": c["gics_sector"],
              "market": "US", "review_reason": review_reason,
          })

      asx_constituents = asx200_universe.fetch_asx200_constituents()
      for c in (asx_constituents or []):
          bare = c["ticker"]
          excluded, review_reason = ethical_check(bare)
          if excluded:
              continue
          rows.append({
              "ticker": tickers.asx_variant(bare), "label": c["sector"] or "ASX (sector unavailable)",
              "market": "ASX", "review_reason": review_reason,
          })

      return rows
  ```

- **PATTERN**: `mytrader/cash_value_scan.py` lines 217-233 (`run_scan`'s two-universe
  fetch) for the "ASX unavailable → empty list, not a crash" handling; lines 165-170 for
  the `ethical_check` call shape.
- **IMPORTS**: `mytrader.asx200_universe`, `mytrader.db as mt_db`, `mytrader.market_data`,
  `mytrader.tickers`, `mytrader.checks.CheckResult`, `scripts.ethical_filter.check_ticker`
  (see CONTEXT REFERENCES — this is the shared `briefs-finance/scripts` package, not a
  local `scripts/` dir), `goat.config`, `goat.db`, `goat.fundamentals_context`,
  `goat.price_history`, `goat.sp500_universe`.
- **GOTCHA (ticker qualification — read before writing any dedup/staging code)**:
  `investments/my-trader/watchlist.md` and `holdings.md` store ASX tickers **with the
  `.AX` suffix** (e.g. `XRO.AX`, `GOLD.AX` — confirmed by grep, see CONTEXT REFERENCES).
  `mt_db.get_holding_row` / `get_watchlist_row` / `db.get_goat_pending_candidate` all key
  on an exact ticker string. If this module used the bare ASX code (`"XRO"`) as its
  canonical `ticker` anywhere, dedup against holdings/watchlist would silently fail to
  match and a held/watchlisted ASX ticker could be re-staged as if new. `tickers.asx_variant(bare)`
  is applied once, at universe-fetch time (above), so every downstream call
  (`price_history.fetch_close_history`, `market_data.fetch_ticker_data`,
  `mt_db.get_holding_row`, `db.get_goat_pending_candidate`,
  `db.insert_goat_pending_candidate`) uses the same already-qualified ticker string
  consistently. Do not introduce a separate `bare`/`yf_ticker` split the way
  `cash_value_scan.py` does — that tool's `ticker` column deliberately stays bare for
  its own report display purposes and is a report-only tool with no dedup requirement;
  this tool's staged rows must match my-trader's actual stored format.
- **VALIDATE**: `uv run --directory investments/goat pytest goat/tests/test_dma_breakout_scan.py -k fetch_universe -x`
  (test written in Task 10).

### Task 3: ADD `check_ma_cross` to `dma_breakout_scan.py`

- **IMPLEMENT**:
  ```python
  def check_ma_cross(ticker: str, label: str, close: pd.Series, ma_days: int, recency_days: int) -> CheckResult:
      """Flags 'interesting' when `ticker` crossed ABOVE its `ma_days`-day MA within
      the last `recency_days` trading days -- a plain, direct upside cross with no
      slope/base-pattern gate (unlike sector_rotation.check_sector_breakout and
      heartbeat.check_heartbeat_breakout, which both require the MA to also be
      sloping up -- see module docstring's design-decision note). MA slope is still
      computed and included in `data`/`detail` as informational context only."""
      name = f"dma_{ma_days}_cross"
      min_len = ma_days + config.GOAT_SECTOR_SLOPE_LOOKBACK_DAYS
      if len(close) < min_len:
          return CheckResult(
              name=name, verdict="unknown",
              detail=f"{ticker} ({label}): insufficient price history for a "
                     f"{ma_days}-day MA",
          )

      ma = close.rolling(ma_days).mean()
      diff = (close - ma).dropna()
      sign = diff.gt(0).astype(int) - diff.lt(0).astype(int)
      sign_changed = sign.diff().fillna(0) != 0
      sign_changes = sign[sign_changed]

      slope_up = bool(ma.iloc[-1] > ma.iloc[-1 - config.GOAT_SECTOR_SLOPE_LOOKBACK_DAYS])

      if sign_changes.empty:
          return CheckResult(
              name=name, verdict="ok",
              detail=f"{ticker} ({label}): no {ma_days}-day MA cross in available "
                     f"history; MA currently {'rising' if slope_up else 'falling'}",
          )

      cross_date = sign_changes.index[-1]
      crossed_above = bool(sign_changes.iloc[-1] > 0)
      cross_pos = close.index.get_loc(cross_date)
      trading_days_since_cross = (len(close) - 1) - cross_pos
      fresh = trading_days_since_cross <= recency_days

      data = {
          "ma_days": ma_days, "cross_date": cross_date.date().isoformat(),
          "crossed_above": crossed_above,
          "trading_days_since_cross": trading_days_since_cross, "slope_up": slope_up,
          "pct_above_ma_now": round(float((close.iloc[-1] / ma.iloc[-1] - 1) * 100), 2),
      }

      if crossed_above and fresh:
          detail = (
              f"{ticker} ({label}): crossed above its {ma_days}-day MA "
              f"{trading_days_since_cross} trading day(s) ago, now "
              f"{data['pct_above_ma_now']:+.1f}% above it (MA currently "
              f"{'rising' if slope_up else 'falling'}) -- DMA breakout discovery signal"
          )
          return CheckResult(name=name, verdict="interesting", detail=detail, data=data)

      direction = "crossed above" if crossed_above else "crossed below"
      return CheckResult(
          name=name, verdict="ok",
          detail=f"{ticker} ({label}): {direction} its {ma_days}-day MA "
                 f"{trading_days_since_cross} trading day(s) ago -- not (yet) a fresh "
                 f"breakout",
          data=data,
      )
  ```
- **PATTERN**: `sector_rotation.py` lines 53-112 (`check_sector_breakout`) — this is
  that function generalized over `ma_days`/`recency_days` with the slope requirement
  removed from the pass condition (per handoff point `2a`: slope is informational only,
  never a gate, unlike `check_sector_breakout`/`check_heartbeat_breakout`).
  `check_name` is `f"dma_{ma_days}_cross"` (e.g. `"dma_150_cross"`, `"dma_200_cross"`) —
  distinct names since this function is called twice per ticker (once per MA) and the
  two results must not collide if ever passed through `goat_alert_history`-style dedup
  (not used by this feature today, but keep names distinct for future-safety and log
  clarity).
- **GOTCHA**: Do not import this function's logic from or export it to
  `sector_rotation.py`/`heartbeat.py` — see `heartbeat.py`'s module docstring
  (CONTEXT REFERENCES) for why duplication is the deliberate, accepted pattern here.
- **VALIDATE**: `uv run --directory investments/goat pytest goat/tests/test_dma_breakout_scan.py -k check_ma_cross -v`

### Task 4: ADD liquidity/quality gate helper to `dma_breakout_scan.py`

- **IMPLEMENT**:
  ```python
  def passes_liquidity_floor(market: str, data) -> bool:
      """`data` is a mytrader.market_data.TickerData | None. Returns False (fails the
      floor) when data or the required .info fields are missing -- an unusable ticker
      is never staged, matching cash_value_scan.compute_cash_value_metrics's
      None-on-missing-data posture."""
      if data is None:
          return False
      info = data.info
      market_cap = info.get("marketCap")
      avg_volume = info.get("averageVolume")
      if market_cap is None or avg_volume is None:
          return False
      floor = (
          config.GOAT_DMA_BREAKOUT_MIN_MARKET_CAP_USD if market == "US"
          else config.GOAT_DMA_BREAKOUT_MIN_MARKET_CAP_AUD
      )
      return market_cap >= floor and avg_volume >= config.GOAT_DMA_BREAKOUT_MIN_AVG_VOLUME
  ```
- **PATTERN**: `cash_value_scan.py` lines 153-156 (`micro_floor` per-market selection)
  for the `market == "US"` ternary shape; `compute_cash_value_metrics` (lines 44-90) for
  the "return early/False on missing required `.info` fields" posture.
- **VALIDATE**: `uv run --directory investments/goat pytest goat/tests/test_dma_breakout_scan.py -k liquidity -v`

### Task 5: ADD `run_dma_breakout_scan` orchestrator to `dma_breakout_scan.py`

- **IMPLEMENT**:
  ```python
  def run_dma_breakout_scan(conn: sqlite3.Connection) -> dict[str, Any]:
      constituents = fetch_universe_constituents(conn)
      asx_unavailable = not any(c["market"] == "ASX" for c in constituents)

      scanned = 0
      already_staged_elsewhere = 0
      new_candidates: list[dict[str, Any]] = []

      with market_data.cached_session():
          for c in constituents:
              ticker, label, market = c["ticker"], c["label"], c["market"]
              try:
                  close = price_history.fetch_close_history(
                      ticker, config.GOAT_DMA_BREAKOUT_HISTORY_LOOKBACK_DAYS
                  )
                  if close is None:
                      continue
                  scanned += 1

                  hits = [
                      check_ma_cross(ticker, label, close, ma_days, config.GOAT_DMA_BREAKOUT_CROSS_RECENCY_DAYS)
                      for ma_days in config.GOAT_DMA_BREAKOUT_MA_DAYS
                  ]
                  interesting = [h for h in hits if h.verdict == "interesting"]
                  if not interesting:
                      continue

                  if mt_db.get_holding_row(conn, ticker) is not None:
                      continue
                  if mt_db.get_watchlist_row(conn, ticker) is not None:
                      continue
                  if db.get_goat_pending_candidate(conn, ticker) is not None:
                      already_staged_elsewhere += 1
                      continue

                  data = market_data.fetch_ticker_data(ticker)
                  if not passes_liquidity_floor(market, data):
                      continue
                  context = fundamentals_context.compute_survival_context(ticker, data)
                  if context["insolvency_risk"]:
                      print(f"[goat-dma-breakout-scan] {ticker} suppressed -- near-term insolvency risk")
                      continue

                  signal_detail = "; ".join(h.detail for h in interesting)
                  if c["review_reason"]:
                      signal_detail += f"; {c['review_reason']}"
                  signal_detail += f"; survival context: {context['summary']}"

                  db.insert_goat_pending_candidate(
                      conn, ticker=ticker, sector_label=label,
                      signal_detail=signal_detail, source="goat_dma_breakout_scan",
                  )
                  new_candidates.append({"ticker": ticker, "sector_label": label, "detail": signal_detail})
              except Exception as e:
                  print(f"[goat-dma-breakout-scan] error checking {ticker}: {e}")

      return {
          "scanned": scanned,
          "asx_unavailable": asx_unavailable,
          "already_staged_elsewhere": already_staged_elsewhere,
          "new_candidates": new_candidates,
          "pending_candidates": [
              dict(r) for r in db.get_all_goat_pending_candidates(conn)
              if r["source"] == "goat_dma_breakout_scan"
          ],
      }
  ```
- **PATTERN**: `heartbeat_scan.py` lines 21-82 (`run_heartbeat_scan`) — near-identical
  shape (fetch universe → loop → cheap check first → expensive fundamentals call only on
  a hit → dedup → stage → return result dict with `pending_candidates` filtered by
  `source`).
- **GOTCHA**: `already_staged_elsewhere` (a genuinely-new codebase field, no existing
  precedent) exists specifically to make the "0 new but nonzero crosses found" case
  legible in the report per the handoff doc's explicit ask (point 8 / the `UNIQUE
  ticker` constraint note in CONTEXT REFERENCES) — surface it in
  `render_dma_breakout_candidates_report` (Task 6), do not drop it silently.
- **GOTCHA**: `market_data.fetch_ticker_data` is only called on an actual cross hit
  (inside the `if not interesting: continue` guard), not for every one of the ~700
  universe tickers — this keeps the run's total `.info` call count small (see handoff
  point 7: this tool is lighter than Cash-Value Scan precisely because of this).
- **VALIDATE**: `uv run --directory investments/goat pytest goat/tests/test_dma_breakout_scan.py -k run_dma_breakout_scan -v`

### Task 6: ADD render/write report functions to `dma_breakout_scan.py`

- **IMPLEMENT**:
  ```python
  def render_dma_breakout_candidates_report(result: dict[str, Any]) -> str:
      lines = [
          "# DMA Breakout Candidates — Pending Review",
          "",
          "Auto-generated by Goat's daily DMA breakout scan -- a stock across the "
          "S&P 500 + ASX 200 universe whose close just crossed ABOVE its 150-day or "
          "200-day moving average (checked independently; a name can fire on one, "
          "the other, or both), with fundamentals survival context attached for you "
          "to judge yourself. Broader and simpler than heartbeat-candidates-pending-"
          "review.md -- no base pattern required, no rising-sector filter, whole "
          "universe not just holdings/watchlist. Review each one and either "
          "`promote-candidate` (writes it into my-trader's real watchlist, labeled "
          "Goat-approved) or `dismiss-candidate` (discards it). Edits here are "
          "overwritten on the next `scan-dma-breakout` run.",
          "",
          f"Scanned {result['scanned']} ticker(s) across the combined universe.",
      ]
      if result["asx_unavailable"]:
          lines.append("> ASX 200 universe unavailable this run (Wikipedia scrape failed) -- US-only scan.")
      if result["already_staged_elsewhere"]:
          lines.append(
              f"{result['already_staged_elsewhere']} ticker(s) crossed but were already "
              "staged by another Goat scan (a ticker can only be pending from one "
              "source at a time) -- not double-counted below."
          )
      lines += [
          "",
          "| Ticker | Sector | Signal | Flagged |",
          "|--------|--------|--------|---------|",
      ]
      for row in result["pending_candidates"]:
          lines.append(
              f"| {row['ticker']} | {row['sector_label']} | {row['signal_detail']} "
              f"| {row['flagged_at'][:10]} |"
          )
      lines += ["", f"Last auto-generated: {date.today().isoformat()}."]
      return "\n".join(lines) + "\n"


  def write_dma_breakout_candidates_report(result: dict[str, Any]) -> None:
      config.GOAT_DMA_BREAKOUT_CANDIDATES_MD_PATH.write_text(
          render_dma_breakout_candidates_report(result), encoding="utf-8"
      )
  ```
- **PATTERN**: `heartbeat_scan.py` lines 85-117 (`render_heartbeat_candidates_report` /
  `write_heartbeat_candidates_report`) — copy structure, table shape, and footer
  verbatim; only the intro paragraph and the two extra banner lines
  (`asx_unavailable`, `already_staged_elsewhere`) are new.
- **VALIDATE**: `uv run --directory investments/goat pytest goat/tests/test_dma_breakout_scan.py -k render -v`

### Task 7: WIRE the CLI subcommand in `investments/goat/goat/main.py`

- **IMPLEMENT**: Add a new `cmd_scan_dma_breakout` function (place after
  `cmd_scan_heartbeat`, before `cmd_scan_insiders`):
  ```python
  def cmd_scan_dma_breakout(args) -> None:
      from .dma_breakout_scan import run_dma_breakout_scan, write_dma_breakout_candidates_report
      from .monitor import maybe_notify

      conn = _open_conn()
      result = run_dma_breakout_scan(conn)
      conn.close()
      write_dma_breakout_candidates_report(result)
      maybe_notify(
          {"new_alerts": []}, new_candidates=result["new_candidates"],
          candidate_label="new DMA breakout candidate(s)",
      )
      print(
          f"DMA breakout scan complete: scanned {result['scanned']} ticker(s), "
          f"{len(result['new_candidates'])} new candidate(s), "
          f"{result['already_staged_elsewhere']} already staged elsewhere. "
          f"See investments/goat/dma-breakout-candidates-pending-review.md"
      )
  ```
  Then in `main()`:
  - After the `scan-heartbeat` `subparsers.add_parser` call (line ~254), add:
    ```python
    subparsers.add_parser(
        "scan-dma-breakout",
        help="On-demand discovery scan: S&P 500 + ASX 200 names that just crossed above their 150-day or 200-day MA",
    )
    ```
  - In the `dispatch` dict (line ~278-288), add: `"scan-dma-breakout": cmd_scan_dma_breakout,`
- **PATTERN**: `main.py` lines 100-117 (`cmd_scan_heartbeat`) — copy shape exactly, same
  `_open_conn()` / run / close / write / `maybe_notify` / print-summary sequence.
- **VALIDATE**: `uv run --directory investments/goat python -m goat.main --help` (locally
  — help text only, no DB/network touch) should list `scan-dma-breakout`.

### Task 8: ADD VPS systemd timer + service, deploy script entry

- **IMPLEMENT**:
  - `scripts/systemd/second-brain-goat-dma-breakout-scan.service`:
    ```ini
    [Unit]
    Description=Goat DMA Breakout Scan
    After=network.target

    [Service]
    Type=oneshot
    User=secondbrain
    WorkingDirectory=/home/secondbrain/second-brain/investments/goat
    ExecStart=/home/secondbrain/second-brain/investments/.venv/bin/python -m goat.main scan-dma-breakout
    StandardOutput=append:/home/secondbrain/second-brain/investments/goat/dma_breakout_scan_runs.log
    StandardError=append:/home/secondbrain/second-brain/investments/goat/dma_breakout_scan_runs.log
    ```
  - `scripts/systemd/second-brain-goat-dma-breakout-scan.timer`:
    ```ini
    [Unit]
    Description=Goat DMA Breakout Scan Timer
    Requires=second-brain-goat-dma-breakout-scan.service

    [Timer]
    OnCalendar=*-*-* 22:55:00 UTC
    Persistent=true

    [Install]
    WantedBy=timers.target
    ```
  - `scripts/deploy.ps1` — add `"second-brain-goat-dma-breakout-scan.timer",` to the
    `$TIMERS` array (after `"second-brain-goat-heartbeat-scan.timer",` at line 23).
- **PATTERN**: `scripts/systemd/second-brain-goat-heartbeat-scan.{timer,service}`
  (CONTEXT REFERENCES) — copied near-verbatim, only the description, `ExecStart`
  subcommand, log filename, and `OnCalendar` time differ.
- **GOTCHA**: `22:55 UTC` is chosen (per handoff point 9) to run right after Heartbeat
  Scan (`22:45`) and before the Moat Scan (`23:30`) — so a ticker Heartbeat Scan staged
  that same morning is correctly seen as `already_staged_elsewhere` here, not raced.
  These files are not actually installed/enabled by this plan (that's a manual VPS step
  Shaun runs himself — see Deployment notes below); creating the files is the repo-side
  deliverable.
- **VALIDATE**: No automated validation (systemd unit files aren't executable locally on
  Windows) — visually diff against `second-brain-goat-heartbeat-scan.{timer,service}` to
  confirm only the intended lines differ.

### Task 9: UPDATE `investments/TOOLS.md`

- **IMPLEMENT**: Add one row to the "Daily Read" table (after the Goat Heartbeat Scan
  row, line 25):
  ```
  | [investments/goat/dma-breakout-candidates-pending-review.md](goat/dma-breakout-candidates-pending-review.md) | Goat DMA Breakout Scan (daily, ~22:55 UTC) | [→](#goat-dma-breakout-scan) |
  ```
  Add one row to the "Automated (scheduled)" table (after the Goat Heartbeat Scan row,
  line 42), following that row's exact column shape (anchor id, description, VPS
  systemd unit name, schedule, output path). Add one row to "Manual / on-demand only"
  (after the my-trader Find/watchlist-ops rows), following that table's shape:
  ```
  | **Goat DMA breakout scan** | On-demand discovery scan (also runs daily) | `-Package goat -Command "scan-dma-breakout"` | `investments/goat/dma-breakout-candidates-pending-review.md` |
  ```
- **PATTERN**: `TOOLS.md` line 21 (Goat Heartbeat Scan's Daily Read row) and line 42
  (its Automated row) — copy the exact column/anchor shape.
- **VALIDATE**: Manual read-through — confirm the new anchor id referenced in the Daily
  Read row matches the `<a id="...">` added to the Automated row.

### Task 10: CREATE `investments/goat/goat/tests/test_dma_breakout_scan.py`

- **IMPLEMENT**: Mirror `test_sector_rotation.py`'s series-builder helpers
  (`_dates`, `_series_with_cross`, `_declining_then_spike_series` — adapted to take
  `ma_days` as a parameter instead of hardcoding `GOAT_SECTOR_MA_SHORT_DAYS`) for
  `check_ma_cross` unit tests, and `test_heartbeat_scan.py`'s `_patch_common` +
  `db_conn`/`monkeypatch` pattern for `run_dma_breakout_scan` orchestration tests.
  Minimum test list:
  - `check_ma_cross` — fresh cross above 150 → `"interesting"`; fresh cross above 200
    (not 150) on the same series → 150 check `"ok"`/200 check `"interesting"`
    (construct two series or call twice against one series sized to only cross the
    200DMA); stale cross (older than `GOAT_DMA_BREAKOUT_CROSS_RECENCY_DAYS`) →
    `"ok"`; **cross with MA still sloping down → still `"interesting"`** (this is the
    test that proves the "slope is informational, not a gate" design decision — the
    one meaningful behavioral difference from `check_sector_breakout`); no cross in
    history → `"ok"`; insufficient history → `"unknown"`.
  - `passes_liquidity_floor` — below market-cap floor → `False`; below avg-volume
    floor → `False`; missing `.info` fields → `False`; passes both → `True`; per-market
    threshold selection (US vs ASX) uses the right constant.
  - `fetch_universe_constituents` — combines US + ASX rows; ASX ticker is
    `.AX`-suffixed; ethical-filter-excluded tickers are dropped entirely; ASX scrape
    failure (`asx200_universe.fetch_asx200_constituents` returns `None`) yields
    US-only rows, no crash.
  - `run_dma_breakout_scan` — stages a new candidate; skips a ticker already a holding
    (use an `.AX`-suffixed ticker to prove the GOTCHA fix, e.g. seed
    `mt_db.upsert_holding(db_conn, ticker="XRO.AX", ...)` then assert an XRO.AX
    universe row is skipped); skips a ticker already watchlisted; skips (and counts in
    `already_staged_elsewhere`) a ticker already staged by a different source (seed
    `goat.db.insert_goat_pending_candidate(db_conn, ticker=..., source="goat_heartbeat_scan")`
    directly); suppresses staging on insolvency risk; suppresses staging when the
    liquidity floor fails even though the cross itself fired; skips a ticker with no
    price history without crashing; stays quiet on a repeat run (no re-staging).
  - `render_dma_breakout_candidates_report` — lists pending rows; surfaces the
    `asx_unavailable` banner when set; surfaces the `already_staged_elsewhere` count
    when nonzero.
- **PATTERN**: `test_sector_rotation.py` (whole file) + `test_heartbeat_scan.py` (whole
  file) — both fully read in CONTEXT REFERENCES above.
- **GOTCHA**: Add `GOAT_DMA_BREAKOUT_CANDIDATES_MD_PATH` to `conftest.py`'s
  `_isolate_goat_report_path` fixture (see CONTEXT REFERENCES) as part of this task —
  otherwise `write_dma_breakout_candidates_report` tests write into the real repo file.
- **VALIDATE**: `uv run --directory investments/goat pytest goat/tests/test_dma_breakout_scan.py -v`

---

## TESTING STRATEGY

### Unit Tests

`check_ma_cross` and `passes_liquidity_floor` are pure functions (no I/O) — test with
hand-built `pd.Series`/dict fixtures, no mocking needed, following
`test_sector_rotation.py`'s style exactly.

### Integration Tests

`run_dma_breakout_scan` against a real (test) sqlite DB (`db_conn` fixture) with every
network call (`price_history.fetch_close_history`, `market_data.fetch_ticker_data`,
`sp500_universe.get_or_refresh_sp500_constituents`,
`asx200_universe.fetch_asx200_constituents`) monkeypatched, following
`test_heartbeat_scan.py`'s `_patch_common` pattern. No test in this suite should ever
hit real yfinance/Wikipedia — `conftest.py`'s autouse `_no_real_price_history_fetch`
fixture already defends the price-history call; extend the same discipline to every
other new external call in this module's own tests.

### Edge Cases

- Ticker crosses 200DMA but not 150DMA on the same run (must report only the 200 hit).
- Ticker crosses both (must report both in `signal_detail`).
- ASX ticker held under its `.AX`-suffixed form (the GOTCHA fix) — must be excluded from
  staging.
- Ticker already staged by Heartbeat Scan under a different `source` — must be skipped
  here and counted in `already_staged_elsewhere`, not silently dropped from the report.
- ASX Wikipedia scrape fails entirely for a run — US leg must still complete and write a
  report with an `asx_unavailable` banner, not crash the whole scan.
- Ticker has enough history for a 150DMA but not a 200DMA (e.g. a recent IPO/listing) —
  the 200 check must return `"unknown"` without crashing the 150 check.

---

## VALIDATION COMMANDS

### Level 1: Syntax & Style

```
uv run --directory investments/goat ruff check goat/dma_breakout_scan.py goat/main.py goat/config.py
uv run --directory investments/goat mypy goat/dma_breakout_scan.py
```

### Level 2: Unit Tests

```
uv run --directory investments/goat pytest goat/tests/test_dma_breakout_scan.py -v
```

### Level 3: Integration Tests

```
uv run --directory investments/goat pytest goat/tests -v
```
(full package suite — confirms nothing in the existing `goat` suite regressed, e.g. the
`conftest.py` fixture edit in Task 10.)

### Level 4: Manual Validation

**Do not run this locally against the real `investments.db`** — per
`investments/TOOLS.md` and `CLAUDE.md`, that DB is VPS-only as of 2026-08-23. Once
deployed:
```powershell
.\scripts\invoke_investments.ps1 -Package goat -Command "scan-dma-breakout"
```
Expected: `investments/goat/dma-breakout-candidates-pending-review.md` is written; a
WhatsApp+toast alert fires only if at least one genuinely new candidate was staged;
console summary line prints scanned/new/already-staged-elsewhere counts.

### Level 5: Additional Validation

Manually inspect the first live report for: any ASX ticker showing a plausible sector
label (proves the `.AX`/sector-string handling), no duplicate rows vs.
`heartbeat-candidates-pending-review.md` (proves the `UNIQUE ticker` dedup), and a
sane total scanned count (~700, matching S&P 500 + ASX 200 combined, modulo ethical-filter
exclusions and any ASX scrape failure).

---

## ACCEPTANCE CRITERIA

- [ ] `check_ma_cross` correctly fires on a fresh upside cross regardless of MA slope
      (slope is informational only, never a gate).
- [ ] 150DMA and 200DMA are checked and reported independently per ticker.
- [ ] Combined US + ASX 200 universe is scanned; ASX tickers are ticker-qualified with
      `.AX` consistently through fetch, dedup, and staging.
- [ ] Ethical filter drops excluded tickers entirely and tags borderline ones.
- [ ] Liquidity/market-cap floor suppresses illiquid/small-cap noise.
- [ ] Fundamentals survival-context insolvency suppression is applied, matching
      Heartbeat Scan's gate.
- [ ] A ticker already held, watchlisted, or already staged by another Goat scan is
      never re-staged; the "already staged elsewhere" case is visible in the report,
      not silently dropped.
- [ ] `scan-dma-breakout` CLI subcommand works end-to-end (writes report, fires
      `maybe_notify` only on a fresh hit, silent on zero).
- [ ] All validation commands pass with zero errors.
- [ ] `investments/TOOLS.md` and `scripts/deploy.ps1` updated.
- [ ] New VPS systemd timer/service files created (not installed — that's Shaun's
      manual VPS step).

## COMPLETION CHECKLIST

- [ ] All 10 tasks completed in order.
- [ ] Each task's validation command passed immediately after that task.
- [ ] Full `goat` test suite passes (no regressions).
- [ ] `ruff`/`mypy` clean on all touched/new files.
- [ ] Manual VPS run (`invoke_investments.ps1 -Package goat -Command "scan-dma-breakout"`)
      confirmed working, once deployed.
- [ ] Acceptance criteria all met.

---

## NOTES

- **Deployment is a separate, explicit follow-up step** — building this plan does not
  deploy anything. After implementation + tests pass, Shaun runs the normal
  commit/push/`deploy.ps1` flow, then manually `sudo systemctl enable --now
  second-brain-goat-dma-breakout-scan.timer` on the VPS (mirrors how the Goat Heartbeat
  Quiet Redesign's timer install was left as a manual step — see
  `project_goat_heartbeat_quiet_redesign` memory precedent).
- **`GOAT_DMA_BREAKOUT_CROSS_RECENCY_DAYS` (10) and the liquidity floor numbers
  (`$300M`/`A$300M`/`100k avg volume`) are v1/tunable**, per this codebase's established
  "start conservative, tune from real output" precedent (Cash-Value Scan's threshold,
  Moat Scan's stage threshold, Heartbeat Scan's whole quiet-leg redesign). Expect to
  revisit after the first few live runs — do not treat these as final without evidence.
- **The `sector_label` design decision (handoff point 4) is resolved by NOT using the
  `GOAT_GICS_TO_ETF_SECTOR_LABEL` mapping at all** for this tool — it stores the raw
  GICS sector string (US) or raw Wikipedia ASX sector string (AU) directly as
  `sector_label`. This sidesteps the mismatch entirely (that mapping only exists because
  Heartbeat Scan needs to compare against the 11-ETF sector-rotation ranking; this tool
  has no such rising-sector filter) and costs nothing — `goat_pending_candidates.sector_label`
  is a free-text `NOT NULL` column with no foreign-key/enum constraint.
- **MLP filter**: confirmed not needed (handoff point 6) — MLPs are rare inside S&P 500 /
  ASX 200 index constituent lists; no filter added.
