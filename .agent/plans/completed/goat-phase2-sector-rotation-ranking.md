# Feature: Goat Phase 2 — Sector Rotation Ranking + Breakout Candidates

The following plan should be complete, but it's important that you validate documentation and codebase patterns and task sanity before you start implementing.

Pay special attention to naming of existing utils, types, and models. Import from the right files etc.

This plan covers **Phase 2 only** of `investments/goat/HANDOFF.md`'s 3-phase Goat scope. Phase 1 (150-day-MA holdings exit check) shipped 2026-08-11 — confirmed complete and working at planning time (18/18 tests passing, `python -m goat.main monitor` runs live against the real DB, real alert already fired on ETPMAG). Phase 3 (S&P 500 heartbeat-pattern scanner) is **out of scope** — when ready, run `/plan-feature` again against `investments/goat/HANDOFF.md`.

## Feature Description

Extend Goat with a daily sector-rotation scan: fetch the 11 SPDR Select Sector ETFs, rank them by trailing relative performance (which sectors institutional money is rotating into vs. out of), and detect a genuine breakout signal on each ETF (price just crossed above its 50-day MA, with the 50DMA itself now sloping up — the literal Step 1 "easiest buy rule" from the source webinar notes). A fresh breakout becomes a real, actionable candidate Shaun can review and promote directly into my-trader's watchlist (labeled as Goat-sourced) or dismiss — not just a line in a report.

## User Story

As Shaun, wanting to "follow the institutional money" into rotating sectors without picking individual stocks first
I want a daily ranking of the 11 sector ETFs plus an alert when one of them has a genuine, fresh technical breakout
So that I can see where money is rotating and act on a real sector-level candidate, exactly as the webinar's Step 1/Step 2 describe, without eyeballing 11 charts myself

## Problem Statement

Phase 1 answered "when do I sell a holding" (the exit rule). Nothing in Goat (or my-trader, which deliberately treats price momentum as non-actionable) yet answers the webinar's first two steps — "which sectors are rising" and "is now a technically confirmed entry point" — despite Shaun already doing this manually (the LULU chart example that prompted this whole feature: "just crossed over the 50 day moving average").

## Solution Statement

Add one new module, `investments/goat/goat/sector_rotation.py`, that fetches all 11 SPDR sector ETFs' close-price history (reusing Phase 1's `price_history.fetch_close_history` as-is — it already handles the ticker fetch/ASX-fallback/error shape these ETFs need, even though none of them actually need the ASX leg), computes (a) each ETF's trailing N-trading-day relative return for the ranking table, and (b) a 50DMA cross+slope breakout signal per ETF using the same sign-flip cross-detection idiom already proven in `macro_indicators.check_gold_trend()`. A fresh, still-rising breakout (crossed within the last `GOAT_SECTOR_CROSS_RECENCY_DAYS` trading days) that isn't already a holding, watchlist row, or pending candidate gets staged into a new `goat_pending_candidates` table. `promote-candidate` writes the ETF directly into my-trader's real `watchlist` table via `mytrader.db.upsert_watchlist_row()` — a **deliberate, explicit, user-confirmed exception** to HANDOFF.md's earlier "Goat never writes into my-trader's tables" rule, scoped to this one command only, with `source="goat_sector_rotation"` and notes prefixed `"Goat-approved sector rotation candidate"` so it's always identifiable in `watchlist.md`. `dismiss-candidate` stays Goat-only (deletes the pending row, no cross-package write). All of this runs as part of the existing `monitor` command (same cadence as Phase 1 — cheap, daily) plus a new on-demand `scan-sectors` subcommand.

## Feature Metadata

**Feature Type**: Enhancement (extends the Phase 1 `investments/goat/` package — no new workspace member, no new sibling package)
**Estimated Complexity**: Medium — the ranking and cross+slope detector are near-mechanical reuses of Phase 1/gold-technicals patterns; the one genuinely new piece of complexity is the cross-package `promote-candidate` write and the "don't re-flag something already promoted/dismissed while the signal is still true" dedup logic.
**Primary Systems Affected**: `investments/goat/goat/` (new `sector_rotation.py`, `db.py`/`config.py`/`monitor.py`/`main.py` extensions); `investments/briefs-finance/data/investments.db` (new `goat_pending_candidates` table; one new *type* of write — via `promote-candidate` only — into the existing `watchlist` table); no changes to any `my-trader` `.py` file.
**Dependencies**: None beyond what Phase 1 already added (`yfinance`, `pandas`, `mytrader` workspace dependency).

---

## THREE DECISIONS RESOLVED WITH SHAUN DURING THIS PLANNING SESSION (2026-08-11) — BINDING

HANDOFF.md left these open; do not re-litigate them during implementation:

1. **Phase 2's per-ETF signal is scoped to 50DMA cross-detection + 50DMA slope-turning-up only.** The "heartbeat" consolidation pattern (low-volatility sideways range sustained 1-3+ months) stays entirely deferred to Phase 3, where it remains the acknowledged hardest, unresearched part of the whole project — Phase 2 must not invent a heartbeat threshold to satisfy this phase. When Phase 3 eventually defines the heartbeat pattern from real research, it can optionally be layered onto the sector ETFs too as a cheap follow-on; that is explicitly not this phase's job.
2. **A fresh breakout becomes a real, actionable candidate** (not just an informational report line) — staged into a new `goat_pending_candidates` table, rendered as its own pending-review markdown file, with `promote-candidate`/`dismiss-candidate` CLI commands mirroring my-trader's `candidate_sync.py` → `promote-candidate`/`dismiss-candidate` UX.
3. **`promote-candidate` writes directly into my-trader's real `watchlist` table** (`mytrader.db.upsert_watchlist_row()`), not a Goat-only confirmed list. Shaun's explicit words: "write it into the watchlist, and maybe mention it's been goat-approved." This is a **narrow, explicit, user-triggered exception** to the "Goat never writes into my-trader's tables" rule from HANDOFF.md's "Reuse vs. standalone" section — that rule still governs every *other* Goat write (the 150DMA exit check, the ranking computation, the pending-candidates table itself); only this one command, only on explicit user action, ever touches `watchlist`. Every promoted row must be identifiable as Goat-sourced: `source="goat_sector_rotation"` column value + a `"Goat-approved sector rotation candidate"` notes prefix, so a future read of `watchlist.md` never confuses this with a manually-researched pick.

---

## CONTEXT REFERENCES

### Relevant Codebase Files — READ THESE BEFORE IMPLEMENTING

- `investments/goat/HANDOFF.md` (full file) — Why: source design doc. Phase 2 section (lines 117-136) is what this plan implements; the "RESOLVED 2026-08-11" decisions on reuse-as-workspace-dependency and DB co-location still apply unchanged.
- `.agent/plans/completed/goat-phase1-150dma-exit-check.md` (full file) — Why: the Phase 1 plan this one extends; every file it created is a dependency here. Read its "NOTES" section for the `goat_alert_history`-vs-`alert_history` separate-table reasoning — the same reasoning applies to `goat_pending_candidates` vs. `pending_candidates`.
- `investments/goat/goat/config.py` (full file, current 43 lines) — Why: append new constants here, following the exact citation-comment style already established (see `GOAT_150DMA_FLAG_PCT`'s block comment).
- `investments/goat/goat/db.py` (full file, current 68 lines) — Why: append `goat_pending_candidates` schema + CRUD here, mirroring the existing `goat_alert_history` CRUD functions' shape exactly (same file, same style, same `with conn:` pattern).
- `investments/goat/goat/price_history.py` (full file, 33 lines) — Why: `fetch_close_history(ticker, lookback_days) -> pd.Series | None` is reused **as-is, unmodified** for every one of the 11 sector ETFs — no new fetch function needed. It already tries the ticker as-is first (which is all these US-listed ETFs ever need) before falling back to `.AX`.
- `investments/goat/goat/exit_check.py` (full file, 55 lines) — Why: the `CheckResult`-building style (`from mytrader.checks import CheckResult`, `data={...}` dict, `verdict` string) to mirror exactly in the new breakout-detector function.
- `investments/goat/goat/monitor.py` (full file, 114 lines) — Why: `run_monitor()`, `render_report()`, `write_report()`, `maybe_notify()` all need companion/extended versions for the sector scan — read this file in full before writing the Phase 2 additions so the two flows (150DMA exit vs. sector rotation) stay visually/structurally consistent in the same file.
- `investments/goat/goat/main.py` (full file, 51 lines) — Why: `_open_conn()` and the argparse dispatch-dict shape — add `scan-sectors`, `promote-candidate`, `dismiss-candidate` subcommands here, following the exact shape.
- `investments/my-trader/mytrader/macro_indicators.py` (lines 502-572, `check_gold_trend()`) — Why: the sign-flip cross-detection idiom (`diff.gt(0).astype(int) - diff.lt(0).astype(int)`, `.diff().fillna(0) != 0`) is the exact pattern to port for the 50DMA cross event — port it, do not import (module-private, and Goat needs it against a 50-day MA, not 200-day).
- `investments/my-trader/mytrader/gold_technicals.py` (lines 77-92, `compute_trend()`) — Why: the `ma50_rising` idiom (`ma50.iloc[-1] > ma50.iloc[-6]`, i.e. today vs. `GOLD_TA_MA_FAST_DAYS`-equivalent lookback) is the exact "MA sloping up" test to reuse for the slope-turn leg of the breakout signal.
- `investments/my-trader/mytrader/checks/opportunity.py` (full file, 167 lines) — Why: **the verdict-semantics precedent to follow.** This codebase's established convention (confirmed by this file) is `verdict="interesting"` for a genuine positive/opportunity signal, `verdict="flag"` reserved for risk warnings, `verdict="info"` for neutral facts, `verdict="unknown"` for missing data. The new sector breakout detector must use `verdict="interesting"` on a fresh fires-condition, matching this convention — **not** `"flag"` (Phase 1's exit check correctly uses `"flag"` because it IS a risk/exit warning; this is the opposite kind of signal).
- `investments/my-trader/mytrader/candidate_sync.py` (full file, 64 lines) — Why: the exact dedup-then-insert shape to mirror for staging a new sector candidate: check `get_holding_row`, then `get_watchlist_row`, then the pending-candidate table, only insert if all three miss. Goat's version substitutes `get_goat_pending_candidate` for the third check but reads my-trader's `holdings`/`watchlist` tables identically (read-only, already an established cross-package pattern — Phase 1's `run_monitor()` already reads `mt_db.get_all_holdings()`).
- `investments/my-trader/mytrader/db.py` (lines 74-81, `pending_candidates` schema; lines 159-184, `get_holding_row`/`get_watchlist_row`/`get_all_holdings`; lines 228-260ish, `upsert_watchlist_row`; lines 262-288, pending-candidate CRUD) — Why: `upsert_watchlist_row(conn, *, ticker, name, asset_type, bucket, status="raw", notes=None, source="manual", last_expense_ratio=None)` is the exact function `promote-candidate` calls; `pending_candidates`' schema/CRUD shape (`id, ticker UNIQUE, company_name, buy_thesis, source, synced_at`, `INSERT OR IGNORE`) is the exact shape `goat_pending_candidates` mirrors (with sector-specific columns instead of `company_name`/`buy_thesis`).
- `investments/my-trader/mytrader/main.py` (lines 174-225, `cmd_sync_candidates`/`cmd_promote_candidate`/`cmd_dismiss_candidate`; lines 427-438, their argparse subparsers) — Why: the exact CLI shape `goat/main.py`'s new subcommands mirror — `promote-candidate` takes `--ticker`, `--bucket` (default `"unassigned"`), `--asset-type` (default here should be `"etf"`, not my-trader's `"stock"` default, since every Goat sector candidate is by definition an ETF), `--status` (default `"raw"`, choices `["raw", "discussed"]`); `dismiss-candidate` takes just `--ticker`.
- `investments/my-trader/mytrader/snapshot.py` (lines 146-168, `regenerate_pending_candidates_md()`) — Why: the exact markdown-table-rendering shape for the new `sector-candidates-pending-review.md`.
- `investments/briefs-finance/scripts/config.py` (`SECTOR_ETF_MAP`, lines 47-78) — Why: **do not reuse this** — confirmed by inspection it's a different, thematic ETF map (gold/uranium/AI/etc. for briefs-finance's report-sector inference), not the standard 11 GICS-aligned SPDR sector ETFs Goat needs. Goat's `GOAT_SECTOR_ETFS` must be its own new constant, not derived from this.
- `investments/goat/goat/tests/conftest.py` (full file, 42 lines) — Why: the `db_conn` fixture already calls both `init_mytrader_tables` and `init_goat_tables` — extending `init_goat_tables` to also create `goat_pending_candidates` means no conftest change is needed for the new table itself, but the autouse `_no_real_price_history_fetch` fixture already stubs `goat.price_history.fetch_close_history` globally — sector-rotation tests inherit this for free and must override it per-ticker via `monkeypatch` (see `test_run_monitor_skips_ticker_with_no_price_history`'s `_fake_fetch` pattern in `test_monitor.py` for the exact per-ticker-branching-stub idiom to copy).
- `investments/goat/goat/tests/test_monitor.py` (full file, 134 lines) — Why: `_seed_holding()`, `_flagging_series()`/`_non_flagging_series()`, and the per-ticker-branching `_fake_fetch` idiom (lines 73-82) are all directly reusable/adaptable patterns for the new sector-scan tests.
- `investments/my-trader/mytrader/checks/__init__.py` (full file, 15 lines) — Why: `CheckResult` dataclass — reused directly (`from mytrader.checks import CheckResult`), same as Phase 1's `exit_check.py` already does.

### New Files to Create

- `investments/goat/goat/sector_rotation.py` — `rank_sectors(closes: dict[str, pd.Series]) -> list[dict]` (relative performance ranking) and `check_sector_breakout(ticker: str, sector_label: str, close: pd.Series) -> CheckResult` (50DMA cross+slope detector), plus a `fetch_all_sector_closes() -> dict[str, pd.Series | None]` orchestration helper.
- `investments/goat/goat/tests/test_sector_rotation.py` — unit tests for both functions against synthetic series.
- `investments/goat/sector-ranking.md` — generated output (not hand-written; created by a new `write_sector_ranking_report()` in `monitor.py`).
- `investments/goat/sector-candidates-pending-review.md` — generated output (created by a new `write_sector_candidates_report()`).

### Files to Update

- `investments/goat/goat/config.py` — append `GOAT_SECTOR_ETFS`, `GOAT_SECTOR_HISTORY_LOOKBACK_DAYS`, `GOAT_SECTOR_RANK_WINDOW_TRADING_DAYS`, `GOAT_SECTOR_MA_SHORT_DAYS`, `GOAT_SECTOR_SLOPE_LOOKBACK_DAYS`, `GOAT_SECTOR_CROSS_RECENCY_DAYS`, `GOAT_SECTOR_RANKING_MD_PATH`, `GOAT_SECTOR_CANDIDATES_MD_PATH`.
- `investments/goat/goat/db.py` — append `goat_pending_candidates` table to `init_goat_tables()`'s `executescript`, plus `get_goat_pending_candidate`, `get_all_goat_pending_candidates`, `insert_goat_pending_candidate`, `delete_goat_pending_candidate` CRUD functions.
- `investments/goat/goat/monitor.py` — add `run_sector_scan(conn) -> dict`, `render_sector_ranking_report(result) -> str`, `write_sector_ranking_report(result) -> None`, `render_sector_candidates_report(conn) -> str`, `write_sector_candidates_report(conn) -> None`; extend `render_report()`/`maybe_notify()` (or add sibling functions) so `monitor-report.md` gets a short "### Sector Rotation" pointer section and the toast notification mentions new sector candidates alongside new exit alerts.
- `investments/goat/goat/main.py` — add `cmd_scan_sectors`, `cmd_promote_candidate`, `cmd_dismiss_candidate`; extend `cmd_monitor` to also call `run_sector_scan`; add all three to the argparse subparsers + dispatch dict.
- `investments/goat/goat/tests/test_db.py` — extend with `goat_pending_candidates` CRUD round-trip tests (mirrors Phase 1's `goat_alert_history` tests).
- `investments/goat/goat/tests/test_monitor.py` — extend with `run_sector_scan` integration tests (dedup against holdings/watchlist/pending, fresh-breakout staging, promote/dismiss lifecycle).
- `investments/goat/HANDOFF.md` — update `## Status:` line to reflect Phase 2 completion once implemented + validated (matches Phase 1's own lifecycle convention).

### Relevant Documentation

No external library documentation needed — pure reuse of `yfinance`/`pandas` patterns already proven in Phase 1 and in `macro_indicators.py`/`gold_technicals.py`. The 11 SPDR Select Sector ETF tickers themselves (XLK, XLF, XLE, XLV, XLY, XLP, XLI, XLB, XLU, XLRE, XLC) are State Street's own standard, free, GICS-aligned sector fund family — already identified in HANDOFF.md's answer to Shaun's Q1, no further research needed to confirm the list.

### Patterns to Follow

**Naming Conventions:**
- Same as Phase 1: snake_case functions/modules, SCREAMING_SNAKE_CASE config constants with sourced-rationale comments, kebab-case CLI subcommands (`scan-sectors`, `promote-candidate`, `dismiss-candidate` — matching my-trader's own naming for the latter two exactly, so the same mental model transfers).

**Error Handling:**
- Same as Phase 1: every fetch wrapped so one ETF's failure doesn't abort the scan (`fetch_all_sector_closes()` loops with try/except per ticker, matching `run_monitor()`'s per-holding try/except at `monitor.py:47-58`); missing/insufficient history returns `verdict="unknown"`, never a flag/interesting call on partial data.

**Logging Pattern:**
- Same `print(f"[goat-monitor] ...")` prefix convention, extended for the sector scan's own messages (e.g. `print(f"[goat-sector-scan] no price history for {ticker}, skipping")`).

**Other Relevant Patterns:**
- `with conn:` context-manager writes, `conn.close()` is the CLI command's responsibility — identical to Phase 1, no deviation.
- The one deliberate deviation from "Goat never writes into my-trader's tables" (the `promote-candidate` command) must be visually unmissable in the code: a comment directly above the `upsert_watchlist_row(...)` call citing this plan's "THREE DECISIONS RESOLVED" section, so a future reader never mistakes it for an accidental boundary violation.

---

## IMPLEMENTATION PLAN

### Phase 1: Foundation (schema + config)

**Tasks:**
- Append `GOAT_SECTOR_*` constants to `goat/config.py`.
- Append `goat_pending_candidates` schema + CRUD to `goat/db.py`.

### Phase 2: Core Implementation (ranking + breakout detector)

**Tasks:**
- Implement `goat/sector_rotation.py`: `fetch_all_sector_closes()`, `rank_sectors()`, `check_sector_breakout()`.
- Unit test both functions exhaustively against synthetic series — the breakout detector's recency-window + slope-turn interaction is the highest-risk new logic in this phase, same class of risk Phase 1's consecutive-day counter was.

### Phase 3: Integration (monitor + candidate staging + CLI)

**Tasks:**
- Implement `goat/monitor.py`'s `run_sector_scan()` (fetch → rank → detect → dedup-and-stage new candidates), report renderers, and extended `maybe_notify()`.
- Implement `goat/main.py`'s `scan-sectors`, `promote-candidate`, `dismiss-candidate` subcommands; wire `cmd_monitor` to also run the sector scan.

### Phase 4: Testing & Validation

**Tasks:**
- Full unit + integration test suite.
- Manual validation: run `python -m goat.main monitor` against the real DB, inspect `sector-ranking.md` and `sector-candidates-pending-review.md`, confirm no unexpected my-trader writes occurred (only via an explicit `promote-candidate` call, never from `monitor`).
- Manually run `promote-candidate` once against a real (or manually-seeded) pending row and confirm the resulting `watchlist.md` row is clearly Goat-labeled.

---

## STEP-BY-STEP TASKS

IMPORTANT: Execute every task in order, top to bottom. Each task is atomic and independently testable.

### UPDATE `investments/goat/goat/config.py`

- **IMPLEMENT**: Append below the existing Phase 1 constants:
  ```python
  # Sector rotation ranking + breakout signal, per investments/goat/HANDOFF.md Phase 2.
  # Scope resolved with Shaun 2026-08-11: this signal is 50DMA cross-detection +
  # 50DMA slope-turn ONLY -- the "heartbeat" consolidation pattern stays deferred to
  # Phase 3 (unresearched, acknowledged hardest part of the project). Do not add a
  # heartbeat/consolidation threshold here.
  GOAT_SECTOR_ETFS: dict[str, str] = {
      "XLK": "Technology", "XLF": "Financials", "XLE": "Energy",
      "XLV": "Health Care", "XLY": "Consumer Discretionary", "XLP": "Consumer Staples",
      "XLI": "Industrials", "XLB": "Materials", "XLU": "Utilities",
      "XLRE": "Real Estate", "XLC": "Communication Services",
  }  # The 11 SPDR Select Sector ETFs -- State Street's own standard, free,
     # GICS-aligned sector-rotation universe. Per HANDOFF.md's answer to Shaun's Q1
     # ("is there a free way to see which sectors are rising/falling?").

  GOAT_SECTOR_HISTORY_LOOKBACK_DAYS = 400  # calendar days -- same margin philosophy
                                              # as GOAT_MA_HISTORY_LOOKBACK_DAYS,
                                              # comfortably exceeds the rank window +
                                              # 50-day MA + slope lookback below.
  GOAT_SECTOR_RANK_WINDOW_TRADING_DAYS = 63  # ~3 calendar months of trading days --
                                                # v1 starting guess per HANDOFF.md
                                                # (Shaun's own webinar notes cite
                                                # multi-month-to-multi-year heartbeat
                                                # timeframes but state no exact
                                                # rank-window number) -- flagged
                                                # tunable, not literature-final.
  GOAT_SECTOR_MA_SHORT_DAYS = 50  # the moving average whose cross/slope IS the entry
                                     # signal per the webinar notes (Step 1) --
                                     # distinct from exit_check's 150-day exit MA.
  GOAT_SECTOR_SLOPE_LOOKBACK_DAYS = 5  # today vs. N trading days ago -- same idiom
                                          # as gold_technicals.compute_trend's
                                          # ma50_rising check (ma.iloc[-1] >
                                          # ma.iloc[-6]).
  GOAT_SECTOR_CROSS_RECENCY_DAYS = 10  # a cross older than this no longer counts as
                                          # "just crossed" (Shaun's own words
                                          # describing the LULU chart that prompted
                                          # this feature) -- keeps the breakout signal
                                          # a fresh event rather than a standing
                                          # condition that would re-fire indefinitely.
                                          # v1/tunable, not literature-sourced.

  GOAT_SECTOR_RANKING_MD_PATH = GOAT_DIR / "sector-ranking.md"
  GOAT_SECTOR_CANDIDATES_MD_PATH = GOAT_DIR / "sector-candidates-pending-review.md"
  ```
- **PATTERN**: `goat/config.py`'s existing citation-comment style (lines 12-42) — every threshold gets its own sourced/reasoned comment, matching the project-wide convention enforced in `mytrader/config.py`.
- **VALIDATE**: `python -c "from goat import config; print(len(config.GOAT_SECTOR_ETFS), config.GOAT_SECTOR_RANK_WINDOW_TRADING_DAYS)"` → expect `11 63`.

### UPDATE `investments/goat/goat/db.py`

- **IMPLEMENT**: Add to the `executescript` block inside `init_goat_tables()`:
  ```python
  CREATE TABLE IF NOT EXISTS goat_pending_candidates (
      id              INTEGER PRIMARY KEY AUTOINCREMENT,
      ticker          TEXT NOT NULL UNIQUE,
      sector_label    TEXT NOT NULL,
      signal_detail   TEXT NOT NULL,
      source          TEXT NOT NULL DEFAULT 'goat_sector_rotation',
      flagged_at      TEXT NOT NULL
  );
  ```
  Then append CRUD functions after the existing alert functions:
  ```python
  def get_goat_pending_candidate(conn: sqlite3.Connection, ticker: str) -> sqlite3.Row | None:
      return conn.execute(
          "SELECT * FROM goat_pending_candidates WHERE ticker = ?", (ticker,)
      ).fetchone()


  def get_all_goat_pending_candidates(conn: sqlite3.Connection) -> list[sqlite3.Row]:
      return conn.execute(
          "SELECT * FROM goat_pending_candidates ORDER BY ticker"
      ).fetchall()


  def insert_goat_pending_candidate(
      conn: sqlite3.Connection, *, ticker: str, sector_label: str,
      signal_detail: str, source: str = "goat_sector_rotation",
  ) -> None:
      with conn:
          conn.execute(
              """INSERT OR IGNORE INTO goat_pending_candidates
                 (ticker, sector_label, signal_detail, source, flagged_at)
                 VALUES (?, ?, ?, ?, ?)""",
              (ticker, sector_label, signal_detail, source, _now()),
          )


  def delete_goat_pending_candidate(conn: sqlite3.Connection, ticker: str) -> int:
      with conn:
          cur = conn.execute(
              "DELETE FROM goat_pending_candidates WHERE ticker = ?", (ticker,)
          )
          return cur.rowcount
  ```
- **PATTERN**: `mytrader/db.py:74-81` (schema shape), `:262-288` (pending-candidate CRUD shape) — near-verbatim, `company_name`/`buy_thesis` swapped for `sector_label`/`signal_detail`, and `synced_at` renamed `flagged_at` (Goat's candidates are self-generated signals, not externally "synced" the way briefs-finance recommendations are — naming reflects that distinction).
- **VALIDATE**: covered by `test_db.py` additions below.

### CREATE `investments/goat/goat/sector_rotation.py`

- **IMPLEMENT**:
  ```python
  """Sector rotation ranking + breakout signal for the 11 SPDR Select Sector ETFs --
  Goat Phase 2. See goat/config.py for GOAT_SECTOR_* threshold sourcing. Scope is
  deliberately limited to 50DMA cross-detection + slope-turn only -- the "heartbeat"
  consolidation pattern stays deferred to Phase 3 (see this feature's plan doc,
  "THREE DECISIONS RESOLVED" section)."""

  from __future__ import annotations

  from typing import Any

  import pandas as pd
  from mytrader.checks import CheckResult

  from . import config, price_history


  def fetch_all_sector_closes() -> dict[str, pd.Series | None]:
      closes: dict[str, pd.Series | None] = {}
      for ticker in config.GOAT_SECTOR_ETFS:
          try:
              closes[ticker] = price_history.fetch_close_history(
                  ticker, config.GOAT_SECTOR_HISTORY_LOOKBACK_DAYS
              )
          except Exception as e:
              print(f"[goat-sector-scan] error fetching {ticker}: {e}")
              closes[ticker] = None
      return closes


  def rank_sectors(closes: dict[str, pd.Series | None]) -> list[dict[str, Any]]:
      window = config.GOAT_SECTOR_RANK_WINDOW_TRADING_DAYS
      rows: list[dict[str, Any]] = []
      for ticker, sector_label in config.GOAT_SECTOR_ETFS.items():
          close = closes.get(ticker)
          if close is None or len(close) < window + 1:
              rows.append({
                  "ticker": ticker, "sector_label": sector_label,
                  "return_pct": None, "rising": None,
              })
              continue
          pct = float((close.iloc[-1] / close.iloc[-(window + 1)] - 1) * 100)
          rows.append({
              "ticker": ticker, "sector_label": sector_label,
              "return_pct": pct, "rising": pct > 0,
          })
      # Rows with no data sort last, not first/interspersed.
      rows.sort(key=lambda r: (r["return_pct"] is None, -(r["return_pct"] or 0)))
      for i, row in enumerate(rows, start=1):
          row["rank"] = i
      return rows


  def check_sector_breakout(ticker: str, sector_label: str, close: pd.Series) -> CheckResult:
      """Flags 'interesting' (never 'flag' -- this is an opportunity signal, not a
      risk warning, matching mytrader/checks/opportunity.py's verdict convention)
      when `ticker` crossed above its 50-day MA within the last
      GOAT_SECTOR_CROSS_RECENCY_DAYS trading days AND the 50DMA itself is currently
      sloping up -- the webinar's literal Step 1 entry rule."""
      min_len = config.GOAT_SECTOR_MA_SHORT_DAYS + config.GOAT_SECTOR_SLOPE_LOOKBACK_DAYS
      if len(close) < min_len:
          return CheckResult(
              name="sector_breakout", verdict="unknown",
              detail=f"{ticker} ({sector_label}): insufficient price history for a "
                     f"{config.GOAT_SECTOR_MA_SHORT_DAYS}-day MA",
          )

      ma50 = close.rolling(config.GOAT_SECTOR_MA_SHORT_DAYS).mean()
      diff = (close - ma50).dropna()
      sign = diff.gt(0).astype(int) - diff.lt(0).astype(int)
      sign_changed = sign.diff().fillna(0) != 0
      sign_changes = sign[sign_changed]

      slope_up = bool(
          ma50.iloc[-1] > ma50.iloc[-1 - config.GOAT_SECTOR_SLOPE_LOOKBACK_DAYS]
      )

      if sign_changes.empty:
          return CheckResult(
              name="sector_breakout", verdict="ok",
              detail=f"{ticker} ({sector_label}): no 50DMA cross in available history; "
                     f"MA currently {'rising' if slope_up else 'falling'}",
          )

      cross_date = sign_changes.index[-1]
      crossed_above = bool(sign_changes.iloc[-1] > 0)
      cross_pos = close.index.get_loc(cross_date)
      trading_days_since_cross = (len(close) - 1) - cross_pos
      fresh = trading_days_since_cross <= config.GOAT_SECTOR_CROSS_RECENCY_DAYS

      data = {
          "cross_date": cross_date.date().isoformat(), "crossed_above": crossed_above,
          "trading_days_since_cross": trading_days_since_cross, "slope_up": slope_up,
      }

      if crossed_above and slope_up and fresh:
          detail = (
              f"{ticker} ({sector_label}): crossed above its "
              f"{config.GOAT_SECTOR_MA_SHORT_DAYS}-day MA {trading_days_since_cross} "
              f"trading day(s) ago, MA now sloping up -- breakout entry signal "
              f"(webinar Step 1)"
          )
          return CheckResult(name="sector_breakout", verdict="interesting", detail=detail, data=data)

      direction = "crossed above" if crossed_above else "crossed below"
      return CheckResult(
          name="sector_breakout", verdict="ok",
          detail=f"{ticker} ({sector_label}): {direction} its "
                 f"{config.GOAT_SECTOR_MA_SHORT_DAYS}-day MA {trading_days_since_cross} "
                 f"trading day(s) ago (MA {'rising' if slope_up else 'falling'}) -- "
                 f"not (yet) a fresh rising breakout",
          data=data,
      )
  ```
- **PATTERN**: `macro_indicators.py:526-531` (sign-flip cross idiom, ported not imported — module-private there, and this version is scoped to a 50-day MA); `gold_technicals.py:90-91` (`ma50_rising` slope idiom); `exit_check.py`'s overall `CheckResult`-building shape; `opportunity.py`'s `verdict="interesting"` convention (see Context References above for why `"flag"` would be semantically wrong here).
- **GOTCHA**: Use `close.index.get_loc(cross_date)` for a **trading-day** position count, not a calendar-day `.days` delta — weekends/holidays would otherwise inflate the recency window and make `GOAT_SECTOR_CROSS_RECENCY_DAYS` mean something different than intended.
- **GOTCHA**: `rank_sectors()`'s sort key `(r["return_pct"] is None, -(r["return_pct"] or 0))` deliberately sorts `None` (missing-data) rows to the end regardless of the `or 0` fallback used only for the numeric part of the tuple — verify this with a unit test (a `None`-return row mixed with real positive/negative rows) since a subtly wrong sort key here would silently misrank sectors.
- **VALIDATE**: unit tests below.

### CREATE `investments/goat/goat/tests/test_sector_rotation.py`

- **IMPLEMENT**: Synthetic `pd.Series` tests covering:
  1. `rank_sectors()`: 3 synthetic closes with known window returns (+10%, -5%, flat) → assert rank order and `rising` flags; one `None` close mixed in → assert it sorts last with `return_pct is None`.
  2. `check_sector_breakout()`: flat-then-rising series with a cross exactly `GOAT_SECTOR_CROSS_RECENCY_DAYS` trading days ago and MA rising → `verdict == "interesting"`.
  3. Same shape but cross `GOAT_SECTOR_CROSS_RECENCY_DAYS + 1` days ago → `verdict == "ok"` (stale cross, not fresh).
  4. Fresh cross above but MA still falling (e.g. a brief spike) → `verdict == "ok"` (slope gate fails).
  5. Crossed *below* recently → `verdict == "ok"` (wrong direction, never flags on a downside cross).
  6. No cross anywhere in history → `verdict == "ok"`.
  7. Insufficient history (`len(close) < min_len`) → `verdict == "unknown"`.
- **PATTERN**: `goat/tests/test_exit_check.py` (not yet read in full, but same synthetic-series-construction idiom as `test_monitor.py`'s `_dates()`/`_flagging_series()` helpers) — reuse/adapt those helper shapes.
- **VALIDATE**: `uv run --directory investments/goat python -m pytest goat/tests/test_sector_rotation.py -v`

### UPDATE `investments/goat/goat/monitor.py`

- **IMPLEMENT**: Append (do not modify the existing Phase 1 functions):
  ```python
  from . import sector_rotation  # add to existing "from . import config, db, exit_check, price_history"
  from mytrader import db as mt_db  # already imported


  def _stage_new_sector_candidates(
      checks: list[tuple[str, str, CheckResult]], conn: sqlite3.Connection
  ) -> list[dict[str, Any]]:
      """checks: list of (ticker, sector_label, CheckResult). Mirrors
      candidate_sync.sync_new_candidates's three-way dedup (holding / watchlist /
      already-pending) before staging a new candidate -- prevents an
      already-promoted or still-active ETF from being re-staged every run while its
      breakout condition remains true."""
      new_candidates: list[dict[str, Any]] = []
      for ticker, sector_label, check in checks:
          if check.verdict != "interesting":
              continue
          if mt_db.get_holding_row(conn, ticker) is not None:
              continue
          if mt_db.get_watchlist_row(conn, ticker) is not None:
              continue
          if db.get_goat_pending_candidate(conn, ticker) is not None:
              continue
          db.insert_goat_pending_candidate(
              conn, ticker=ticker, sector_label=sector_label, signal_detail=check.detail,
          )
          new_candidates.append({"ticker": ticker, "sector_label": sector_label, "detail": check.detail})
      return new_candidates


  def run_sector_scan(conn: sqlite3.Connection) -> dict[str, Any]:
      closes = sector_rotation.fetch_all_sector_closes()
      ranking = sector_rotation.rank_sectors(closes)

      breakout_checks = []
      for ticker, sector_label in config.GOAT_SECTOR_ETFS.items():
          close = closes.get(ticker)
          if close is None:
              print(f"[goat-sector-scan] no price history for {ticker}, skipping breakout check")
              continue
          check = sector_rotation.check_sector_breakout(ticker, sector_label, close)
          breakout_checks.append((ticker, sector_label, check))

      new_candidates = _stage_new_sector_candidates(breakout_checks, conn)

      return {
          "ranking": ranking,
          "new_candidates": new_candidates,
          "pending_candidates": [dict(r) for r in db.get_all_goat_pending_candidates(conn)],
      }


  def render_sector_ranking_report(result: dict[str, Any]) -> str:
      lines = [
          "# Goat Sector Rotation Ranking",
          "",
          "Auto-generated by Goat Monitor -- overwritten every run. Relative "
          f"performance over the trailing {config.GOAT_SECTOR_RANK_WINDOW_TRADING_DAYS} "
          "trading days across the 11 SPDR Select Sector ETFs. Advisor notes only; "
          "no trade action is ever suggested here (see SOUL.md).",
          "",
          "| Rank | Ticker | Sector | Return | Rising |",
          "|------|--------|--------|--------|--------|",
      ]
      for row in result["ranking"]:
          ret = f"{row['return_pct']:+.1f}%" if row["return_pct"] is not None else "—"
          rising = ("Yes" if row["rising"] else "No") if row["rising"] is not None else "—"
          lines.append(f"| {row['rank']} | {row['ticker']} | {row['sector_label']} | {ret} | {rising} |")
      lines += ["", f"Last auto-generated: {date.today().isoformat()}."]
      return "\n".join(lines) + "\n"


  def write_sector_ranking_report(result: dict[str, Any]) -> None:
      config.GOAT_SECTOR_RANKING_MD_PATH.write_text(
          render_sector_ranking_report(result), encoding="utf-8"
      )


  def render_sector_candidates_report(result: dict[str, Any]) -> str:
      lines = [
          "# Sector Breakout Candidates — Pending Review",
          "",
          "Auto-generated by Goat Monitor -- a fresh 50DMA-cross-and-rising breakout "
          "on a sector ETF (webinar Step 1). Review each one and either "
          "`promote-candidate` (writes it into my-trader's real watchlist, labeled "
          "Goat-approved) or `dismiss-candidate` (discards it). Edits here are "
          "overwritten on the next `monitor`/`scan-sectors` run.",
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


  def write_sector_candidates_report(result: dict[str, Any]) -> None:
      config.GOAT_SECTOR_CANDIDATES_MD_PATH.write_text(
          render_sector_candidates_report(result), encoding="utf-8"
      )
  ```
  Then **update** (not append) the existing `render_report()` to insert a short pointer section before the final `"Last auto-generated"` line:
  ```python
  "",
  "### Sector Rotation",
  f"{len(result.get('new_sector_candidates', []))} new breakout candidate(s) this run. "
  "See sector-ranking.md and sector-candidates-pending-review.md.",
  ```
  and **update** `maybe_notify()` to accept an optional second count and combine both into one toast message (signature becomes `maybe_notify(result: dict, new_sector_candidates: int = 0) -> None`), firing when either is non-empty.
- **PATTERN**: existing Phase 1 `run_monitor()`/`render_report()`/`write_report()`/`maybe_notify()` in the same file (lines 42-114) — new functions mirror their structure closely; `mytrader/candidate_sync.py`'s dedup shape for `_stage_new_sector_candidates`.
- **GOTCHA**: `_stage_new_sector_candidates` reads `mt_db.get_watchlist_row(conn, ticker)` with no `bucket` argument — confirm this correctly matches "ticker exists in watchlist under ANY bucket" (it does, per `db.py:169-174`'s `bucket=None` branch) so a promoted candidate can never be re-staged regardless of which bucket it landed in.
- **VALIDATE**: covered by `test_monitor.py` additions below.

### UPDATE `investments/goat/goat/main.py`

- **IMPLEMENT**: Add:
  ```python
  def cmd_scan_sectors(args) -> None:
      from .monitor import run_sector_scan, write_sector_candidates_report, write_sector_ranking_report

      conn = _open_conn()
      result = run_sector_scan(conn)
      conn.close()
      write_sector_ranking_report(result)
      write_sector_candidates_report(result)
      print(
          f"Sector scan complete: {len(result['new_candidates'])} new candidate(s), "
          f"{len(result['pending_candidates'])} pending. "
          f"See investments/goat/sector-ranking.md and sector-candidates-pending-review.md"
      )


  def cmd_promote_candidate(args) -> None:
      from .db import delete_goat_pending_candidate, get_goat_pending_candidate
      from mytrader.db import upsert_watchlist_row

      conn = _open_conn()
      ticker = args.ticker.strip().upper()
      pending = get_goat_pending_candidate(conn, ticker)
      if pending is None:
          conn.close()
          print(f"No pending Goat sector candidate found for {ticker}.")
          return

      # Deliberate, explicit exception to "Goat never writes into my-trader's
      # tables" -- see this feature's plan doc, "THREE DECISIONS RESOLVED" #3.
      # Only this command, only on explicit user action.
      upsert_watchlist_row(
          conn, ticker=ticker, name=None, asset_type=args.asset_type,
          bucket=args.bucket, status=args.status,
          notes=f"Goat-approved sector rotation candidate — {pending['signal_detail']}",
          source="goat_sector_rotation",
      )
      delete_goat_pending_candidate(conn, ticker)
      conn.close()
      print(f"Promoted {ticker} to my-trader's watchlist (bucket {args.bucket}), labeled Goat-approved.")


  def cmd_dismiss_candidate(args) -> None:
      from .db import delete_goat_pending_candidate

      conn = _open_conn()
      ticker = args.ticker.strip().upper()
      count = delete_goat_pending_candidate(conn, ticker)
      conn.close()
      print(f"Dismissed {count} pending Goat candidate(s) for {ticker}.")
  ```
  Update `cmd_monitor` to also run the sector scan and pass its new-candidate count into `maybe_notify`:
  ```python
  def cmd_monitor(args) -> None:
      from .monitor import maybe_notify, run_monitor, run_sector_scan, write_report, write_sector_candidates_report, write_sector_ranking_report

      conn = _open_conn()
      result = run_monitor(conn)
      sector_result = run_sector_scan(conn)
      conn.close()
      write_report(result)
      write_sector_ranking_report(sector_result)
      write_sector_candidates_report(sector_result)
      maybe_notify(result, new_sector_candidates=len(sector_result["new_candidates"]))
      print(
          f"Goat Monitor complete: {len(result['new_alerts'])} new exit alert(s), "
          f"{len(sector_result['new_candidates'])} new sector candidate(s). "
          f"See investments/goat/monitor-report.md"
      )
  ```
  Add subparsers + dispatch entries:
  ```python
  subparsers.add_parser("scan-sectors", help="On-demand sector rotation ranking + breakout scan (also runs daily as part of monitor)")

  p_promote = subparsers.add_parser("promote-candidate", help="Write a pending Goat sector candidate into my-trader's real watchlist")
  p_promote.add_argument("--ticker", required=True)
  p_promote.add_argument("--bucket", default="unassigned")
  p_promote.add_argument("--asset-type", dest="asset_type", default="etf")
  p_promote.add_argument("--status", default="raw", choices=["raw", "discussed"])

  p_dismiss = subparsers.add_parser("dismiss-candidate", help="Discard a pending Goat sector candidate (Goat-only, no watchlist write)")
  p_dismiss.add_argument("--ticker", required=True)
  ```
  and add `"scan-sectors": cmd_scan_sectors, "promote-candidate": cmd_promote_candidate, "dismiss-candidate": cmd_dismiss_candidate` to the `dispatch` dict.
- **PATTERN**: `mytrader/main.py:174-225` (`cmd_sync_candidates`/`cmd_promote_candidate`/`cmd_dismiss_candidate`) and `:427-438` (their subparsers) — same shape, cross-package `upsert_watchlist_row` import is the one deliberate difference.
- **GOTCHA**: `args.asset_type` defaults to `"etf"` here (not my-trader's own `"stock"` default) — every Goat sector candidate is definitionally an ETF; do not copy my-trader's default verbatim.
- **VALIDATE**: `uv run --directory investments/goat python -m goat.main scan-sectors` — real run against the live shared DB (read-only against holdings/watchlist for dedup, writes only to `goat_pending_candidates` + the two new `.md` files). Confirm via `git status`/`git diff` that no my-trader file changed. Separately: `uv run --directory investments/goat python -m goat.main monitor` still runs end-to-end with both checks combined.

### UPDATE `investments/goat/goat/tests/test_db.py`

- **IMPLEMENT**: Round-trip tests for `goat_pending_candidates`, mirroring the existing `goat_alert_history` tests in this file: insert → `get_goat_pending_candidate` finds it; insert same ticker twice → `INSERT OR IGNORE` means second insert is a no-op (assert only one row, original `signal_detail` preserved); delete → `get_goat_pending_candidate` returns `None`; `get_all_goat_pending_candidates` lists all rows ticker-sorted.
- **VALIDATE**: `uv run --directory investments/goat python -m pytest goat/tests/test_db.py -v`

### UPDATE `investments/goat/goat/tests/test_monitor.py`

- **IMPLEMENT**: Add tests mirroring the existing Phase 1 test shapes in this file:
  1. `test_run_sector_scan_stages_new_candidate_on_fresh_breakout` — monkeypatch `goat.monitor.sector_rotation.fetch_all_sector_closes` (or patch `price_history.fetch_close_history` per-ticker) to return one ETF with a fresh-breakout series and the rest flat/no-signal; assert `len(result["new_candidates"]) == 1` and it's in `goat_pending_candidates`.
  2. `test_run_sector_scan_skips_ticker_already_a_holding` — seed the breakout ETF into `holdings` via `mt_db.upsert_holding`; assert it is NOT staged despite a firing breakout condition.
  3. `test_run_sector_scan_skips_ticker_already_in_watchlist` — same, via `mt_db.upsert_watchlist_row`.
  4. `test_run_sector_scan_stays_quiet_on_repeat_run` — run twice with the same firing series; assert the second run's `new_candidates` is empty (already-pending dedup).
  5. `test_cmd_promote_candidate_writes_to_mytrader_watchlist` (or a direct function-level test if CLI-level testing isn't this project's convention — confirm against existing test files first, mirror whichever level `mytrader`'s own `cmd_promote_candidate` is tested at, if at all) — seed a pending candidate, promote it, assert `mt_db.get_watchlist_row(conn, ticker)` now returns a row with `source == "goat_sector_rotation"` and `"Goat-approved"` in `notes`, and the pending row is gone.
  6. `test_cmd_dismiss_candidate_removes_pending_only` — seed a pending candidate, dismiss it, assert it's gone from `goat_pending_candidates` and nothing was written to `watchlist`.
- **PATTERN**: existing Phase 1 tests in this same file (`_seed_holding`, monkeypatch-per-ticker idiom).
- **GOTCHA**: check whether `mytrader`'s own test suite tests `main.py`'s `cmd_*` functions directly or only the underlying `db`/`candidate_sync`/`monitor` functions — if the established project convention is "don't test argparse-wired CLI functions directly, test the underlying logic," write tests 5-6 against equivalent standalone logic instead of importing `goat.main.cmd_promote_candidate` (which does its own `_open_conn()`/`conn.close()` and isn't trivially testable against a fixture connection without refactoring) — confirm this convention before deciding the exact test shape for 5-6, don't just guess.
- **VALIDATE**: `uv run --directory investments/goat python -m pytest goat/tests/test_monitor.py -v`

---

## TESTING STRATEGY

### Unit Tests
- `test_sector_rotation.py` — pure-function tests, no DB/network, covering ranking sort order (including missing-data handling) and every branch of the breakout detector (fresh+flag, stale, wrong-slope, wrong-direction, no-cross, insufficient-history).
- `test_db.py` additions — `goat_pending_candidates` CRUD/dedup round-trip.

### Integration Tests
- `test_monitor.py` additions — `run_sector_scan()` full round-trip including the three-way dedup against `holdings`/`watchlist`/already-pending, and the promote/dismiss lifecycle's effect on both `goat_pending_candidates` and my-trader's `watchlist` table.

### Edge Cases
- All 11 ETFs fail to fetch (network down) → `run_sector_scan` returns an empty-but-valid ranking (all `return_pct: None`), zero new candidates, no exception.
- A ticker breaks out, gets staged, then Shaun promotes it — next run's breakout condition is still true (still within the recency window) — confirm it is NOT re-staged (watchlist dedup check catches it).
- A ticker breaks out, gets staged, Shaun dismisses it, and the condition is STILL true on the next run (still within `GOAT_SECTOR_CROSS_RECENCY_DAYS`) — this WILL re-stage it (no tombstone mechanism in this phase). Document as a known v1 limitation (see Notes) rather than solving here — the 10-trading-day recency window naturally bounds how long this can repeat.
- Two ETFs fire in the same run — confirm both get staged independently (no accidental single-candidate assumption anywhere in `_stage_new_sector_candidates`).

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
Covered by the same `pytest -q` run (project convention — no separate integration command, confirmed by Phase 1's plan and my-trader's own single-command convention).

### Level 4: Manual Validation
```powershell
# Real run against the live shared DB
uv run --directory investments/goat python -m goat.main scan-sectors
cat investments/goat/sector-ranking.md
cat investments/goat/sector-candidates-pending-review.md

# Combined monitor run (both Phase 1 exit check + Phase 2 sector scan)
uv run --directory investments/goat python -m goat.main monitor
cat investments/goat/monitor-report.md

# Confirm no unexpected my-trader writes from monitor/scan-sectors alone
git status investments/my-trader/
git diff investments/my-trader/

# If at least one real candidate is pending, manually promote it and confirm the
# watchlist.md row is clearly Goat-labeled
uv run --directory investments/goat python -m goat.main promote-candidate --ticker <TICKER> --bucket unassigned
git diff investments/my-trader/watchlist.md   # should show exactly one new/updated row, source goat_sector_rotation
```
Spot-check at least one ETF's real 50DMA/ranking math against a chart (e.g. Yahoo Finance) — automated tests validate against synthetic data only.

### Level 5: Additional Validation
Not applicable.

---

## ACCEPTANCE CRITERIA

- [ ] `rank_sectors()` correctly ranks all 11 SPDR sector ETFs by trailing `GOAT_SECTOR_RANK_WINDOW_TRADING_DAYS`-day return, missing-data tickers sorted last.
- [ ] `check_sector_breakout()` fires `verdict="interesting"` only when: crossed above the 50-day MA, within `GOAT_SECTOR_CROSS_RECENCY_DAYS` trading days, AND the 50DMA is currently sloping up — all three conditions required, verified by unit tests covering each failing independently.
- [ ] A fresh breakout not already a holding/watchlist row/pending candidate is staged into `goat_pending_candidates` exactly once (verified dedup on repeat runs).
- [ ] `promote-candidate` writes into my-trader's real `watchlist` table with `source="goat_sector_rotation"` and a `"Goat-approved"`-prefixed notes string; `dismiss-candidate` never writes to `watchlist`.
- [ ] `python -m goat.main monitor` runs both the Phase 1 exit check and the Phase 2 sector scan in one invocation, writing `monitor-report.md`, `sector-ranking.md`, and `sector-candidates-pending-review.md`.
- [ ] No my-trader file/table is modified by any Goat code path EXCEPT via an explicit `promote-candidate` invocation.
- [ ] All new thresholds documented in `config.py` with sourced/reasoned rationale comments, matching Phase 1's established convention.
- [ ] Full test suite passes: `uv run --directory investments/goat python -m pytest -q`.
- [ ] `ruff check` and `mypy` pass clean.
- [ ] `investments/goat/HANDOFF.md`'s status line updated to reflect Phase 2 completion.

## COMPLETION CHECKLIST

- [ ] All tasks completed in order
- [ ] Each task's validation command passed immediately after that task
- [ ] Full test suite passes (single `pytest -q` run)
- [ ] `ruff check` / `mypy` clean
- [ ] Manual validation (`scan-sectors` and `monitor`) confirms real output and correct DB-write boundaries
- [ ] A real (or manually-seeded) promote-candidate call confirmed to produce a correctly-labeled `watchlist.md` row
- [ ] Acceptance criteria all met
- [ ] HANDOFF.md status line updated

---

## NOTES

**Why `goat_pending_candidates` is a separate table from my-trader's `pending_candidates`, same reasoning as Phase 1's `goat_alert_history`:** keeps Goat's writes scoped to its own tables (the DB-boundary rule this plan otherwise fully respects, `promote-candidate` being the one narrow exception), and the two staging tables have genuinely different shapes (`company_name`/`buy_thesis`/externally-`synced_at` vs. `sector_label`/`signal_detail`/self-generated `flagged_at`).

**The `promote-candidate` boundary exception is intentionally narrow and loud.** Every other Goat write path (150DMA exit alerts, sector ranking computation, pending-candidate staging) still fully respects "Goat never writes into my-trader's tables." Only this one explicit, user-triggered command crosses it, and it's documented as such at three levels: this plan's "THREE DECISIONS RESOLVED" section, a code comment directly above the `upsert_watchlist_row()` call, and the acceptance criteria's explicit carve-out. If this pattern needs to extend further (e.g. Phase 3's stock candidates also promoting into the watchlist), that should cite this same precedent rather than being decided fresh.

**Known v1 limitation — dismissed candidates can resurrect within the recency window.** Because `check_sector_breakout`'s fire condition is recomputed fresh every run (not a one-time event flag), dismissing a candidate while its underlying breakout condition remains true (within `GOAT_SECTOR_CROSS_RECENCY_DAYS` trading days of the actual cross) will cause it to be re-staged on the next run. This is bounded (worst case: re-appears daily for up to ~10 trading days after the actual cross event, then stops naturally as the cross ages out of the recency window) and considered acceptable for v1 rather than adding a dismissal-tombstone mechanism now. A follow-up could add a `dismissed_until`/tombstone column if this proves annoying in practice — not built here to avoid over-engineering a v1.

**Sector-ranking window (63 trading days) and cross-recency window (10 trading days) are both v1/tunable, not literature-final** — same "ship a reasoned default, flag it for tuning after real data" discipline Phase 1's 150DMA thresholds followed. Revisit both once Goat has run for a few weeks against real sector data.

**Confidence Score: 7/10** for one-pass implementation success. The ranking and cross+slope detector are near-mechanical ports of already-proven Phase 1/`gold_technicals`/`macro_indicators` patterns — low risk. The two spots most likely to need a debugging pass: (1) the three-way dedup interacting correctly with the recency window at the exact moment of promote/dismiss (the "resurrection" edge case documented above as accepted, but verify the *other* dedup paths — holding/watchlist — are airtight, since those are NOT supposed to ever resurrect); (2) `rank_sectors()`'s sort-key handling of missing-data tickers, flagged explicitly as needing its own unit test rather than trusting the tuple-sort idiom to be obviously correct on first read.
