# Feature: Fourteen Crash Signals Daily Check — Phase 2 (Markers #2, #4, #9, #12 + Marker #14 Watch Tier)

The following plan should be complete, but it's important to validate documentation and
codebase patterns and task sanity before implementing. Pay special attention to naming of
existing utils/types/models. Import from the right files.

**Source**: `investments/my-trader/14-signals-crash-warning-phase2-handoff.md` — both
rounds of discussion are resolved and the doc is marked "ready for `/plan-feature`."
**Prerequisite context**: `.agent/plans/fourteen-crash-signals-phase1-core-signals.md`
(the shipped Phase 1 plan) and its own "NOTES — How to create Phase 2 / Phase 3" section,
which named this exact slice as the natural Phase 2.

## Feature Description

Phase 1 shipped a new `investments/fourteen-crash-signals-daily-check/` package tracking 4
of the 14 crash-warning markers (credit spread streak, margin debt YoY, insider selling
trend, market-cap milestone) plus a shared "hot company watchlist" layer, with the other 10
markers rendered as `"Not yet automated"` placeholder rows in the daily report. This phase
replaces 4 of those placeholders with real `CheckResult`-shaped checks:

- **#2 Off-balance-sheet lease commitments** — SEC EDGAR 10-K/10-Q "Leases" footnote,
  LLM-extracted dollar figure, flagged on ≥50% quarter-over-quarter growth.
- **#4 Capex outruns cash flow** — yfinance annual cash-flow statement, flagged on negative
  Free Cash Flow while Capital Expenditure is large (a single-period unsustainability check,
  not a two-period growth-gap).
- **#9 The Super Bowl signal** — an honest scope-down to a date-proximity reminder + manual
  check-flag (no structured free data source exists for "% of ads that were AI-related").
- **#12 Credit turns in the hot sector** — bond CUSIP auto-discovered via SEC EDGAR
  prospectus filings, yield sourced either from a live scrape (implementation-time spike,
  outcome genuinely unresolved as of the handoff) or a manual-entry fallback, spread vs.
  Treasury, flagged on a 90-day divergence ratio.

Plus one scope addition to the **already-shipped** Marker #14 (credit spread streak),
requested by Shaun mid-discussion while resolving Marker #12's threshold:

- A **"watch" tier** — `data={"watch": True}` (verdict stays `"ok"`, confirmed with Shaun
  2026-08-18) when the spread is ≥3.2% (within 0.3pp of the 3.5pp flag threshold) but hasn't
  crossed it.
- A **daily repeat WhatsApp alert** while the streak continues ("day N and counting"), a
  deliberate one-marker exception to `alerts.py`'s transition-only rule.

## User Story

As Shaun (multi-business founder managing his own portfolio)
I want the 4 markers whose data sources are now confirmed feasible (per live research in the
Phase 2 handoff) automated and wired into the existing daily report/alert, plus a daily
reminder while the credit-spread streak is actively firing
So that more of the 14-signal framework moves from "not yet automated" to real signal,
without pretending markers that resist clean automation (#9, and half of #12) are more
automated than they actually are.

## Problem Statement

Phase 1's own scope decision deferred markers #2, #4, #9, #12 to a later phase because they
needed per-issuer fetch logic (SEC EDGAR extraction, yfinance cash-flow statements, a
bond-yield source) rather than being "ready to build without further research." The Phase 2
handoff did that research across two rounds with Shaun and resolved every open question
except one genuinely unresolved sub-problem (Marker #12's bond-yield lookup), which the
handoff itself recommends treating as an implementation-time live-verification spike with a
documented manual-entry fallback, not a blocker.

## Solution Statement

Four new marker-check modules plug into the existing `signals_hot_watchlist` table (markers
#2, #4, #12 are per-issuer, reading the same top-10 mega-cap watchlist Phase 1 already
computes) or need no watchlist at all (#9, broad-market). Two of the four reuse and extend
`mytrader/sec_filings.py`'s existing SEC EDGAR plumbing (making several of its helpers
public across the package boundary, and teaching its 10-K/10-Q extractors to also capture
the Financial Statements section, which they currently skip). One reuses/extends
`mytrader/market_data.py` with a new yfinance cash-flow fetch. `report.py`/`main.py` get
real rows in place of 4 placeholders. `credit_spread.py`/`alerts.py` get the Marker #14
watch-tier + daily-repeat-alert addition. No new systemd timer/service is needed — this
extends the same `daily-check` command the already-deployed
`second-brain-fourteen-signals.timer` already runs.

## Feature Metadata

**Feature Type**: Enhancement (extends an already-shipped package)
**Estimated Complexity**: High — one cross-package rename affecting two callers, a new
LLM-structured-extraction path, a new financial-statement fetch, and one component
(Marker #12's yield lookup) with a genuinely unresolved data source requiring an
implementation-time verification spike, not a fully pre-specifiable task.
**Primary Systems Affected**: `investments/fourteen-crash-signals-daily-check/` (all
modules), `investments/my-trader/mytrader/sec_filings.py`,
`investments/my-trader/mytrader/market_data.py`, `investments/TOOLS.md`.
**Dependencies**: `requests`, `beautifulsoup4`, `openpyxl` (all already present via the
`my-trader`/`goat` workspace deps — no new package additions needed), `yfinance`,
`sdk_compat`/Pi (model-agnostic LLM backend, per this project's architecture rule).

---

## CONTEXT REFERENCES

### Relevant Codebase Files — READ THESE BEFORE IMPLEMENTING

- `investments/my-trader/14-signals-crash-warning-phase2-handoff.md` (whole file, esp.
  "ROUND 2 — Resolved decisions") — the authoritative source for every design decision in
  this plan. Do not re-litigate a decision already made here.
- `investments/fourteen-crash-signals-daily-check/fourteen_crash_signals_daily_check/config.py`
  (whole file) — existing constants block style (`SIGNALS_*` prefix, "why this number"
  comment on every threshold) to mirror for new constants.
- `.../db.py` (whole file) — existing `signals_hot_watchlist`/`signals_alert_state` schema +
  `upsert_signal_state`'s transition-detection shape to mirror for the new tables.
- `.../watchlist.py` (whole file) — `get_or_refresh_hot_watchlist(conn)` is the shared input
  markers #2, #4, #12 all read from; do not recompute it independently.
- `.../credit_spread.py` (whole file, 54 lines) — the function this plan adds the watch tier
  to; also the `CheckResult`/FRED-helper pattern every marker in this package follows.
- `.../margin_debt.py` (whole file) — best existing example of "fetch external source,
  degrade to `unknown` on any failure, compute YoY-style comparison with a tolerance window"
  — the closest existing precedent for Marker #2's growth-comparison shape.
- `.../insider_trend.py` (whole file) — best existing example of "one `CheckResult` per
  hot-watchlist ticker, skip tickers with nothing to report" — the shape markers #2, #4, #12
  all follow (return `list[CheckResult]`, not a single `CheckResult`).
- `.../market_cap_milestone.py` (whole file) — simplest existing example of consuming
  `hot_watchlist` rows directly.
- `.../alerts.py` (whole file, 39 lines) — `maybe_notify`'s transition-only alert shape; this
  plan adds a deliberate exception alongside it, not a replacement.
- `.../report.py` (whole file) — `_PLACEHOLDER_MARKERS` list (markers 2, 4, 9, 12 currently
  in it) and `render_signals_report`'s row-assembly shape.
- `.../main.py` (whole file) — `cmd_daily_check`'s orchestration order and `alert_inputs`
  list shape.
- `.../tests/conftest.py` (whole file) — `db_conn` fixture (in-memory-per-test sqlite,
  `init_signals_tables` called) and the autouse `_isolate_signals_report_path` fixture.
- `.../tests/test_credit_spread.py` (whole file) — monkeypatch-at-module-level test pattern
  (`monkeypatch.setattr("fourteen_crash_signals_daily_check.credit_spread.fred_series_range", ...)`)
  every new test file in this plan should follow.
- `investments/my-trader/mytrader/sec_filings.py` (whole file, 319 lines) — the module this
  plan partially publicizes and extends. Read the module docstring (lines 1-17) and every
  function; markers #2 and #12 both build directly on `get_cik`/`fetch_filing_index`/
  `latest_filing_entry`/`fetch_filing_document`/`strip_html` (renamed in Task 1).
- `investments/my-trader/mytrader/tests/test_sec_filings.py` (whole file) — every test that
  references the 5 functions Task 1 renames; all of them need call-site updates.
- `investments/my-trader/mytrader/market_data.py` lines 114-155
  (`fetch_balance_sheet_financials`) — the exact try/except/return-`None` shape and
  docstring style to mirror for the new `fetch_cash_flow_statement`.
- `investments/my-trader/mytrader/tests/test_market_data.py` lines 141-180 (the
  `fetch_balance_sheet_financials` tests) and whatever `_install_fake_yfinance`
  helper/fixture those tests use earlier in the same file — mirror this fixture shape for
  the new cash-flow tests (fake a `t.cashflow` `pandas.DataFrame` the same way `t.balance_sheet`
  is faked).
- `investments/my-trader/mytrader/checks/__init__.py` (whole file, 15 lines) — `CheckResult`'s
  documented `verdict` contract (`"ok"|"flag"|"info"|"unknown"`). Confirmed with Shaun
  2026-08-18: the Marker #14 watch tier does **not** add a 5th value — it stays
  `verdict="ok"` with `data={"watch": True}`, so this file needs no change.
- `investments/briefs-finance/scripts/macro.py` — `fred_series_range` (already imported by
  `credit_spread.py`) and `fred_value_on` (needed new by `credit_spread_issuer.py` for the
  single-date Treasury yield lookup — signature: `fred_value_on(series_id: str, target: date) -> float | None`).
- `investments/my-trader/mytrader/config.py` lines 137-138 (`FRED_2Y_TREASURY_SERIES`,
  `FRED_10Y_TREASURY_SERIES`) — exist already, but this plan's v1 uses a fixed
  `SIGNALS_CREDIT_SPREAD_ISSUER_TREASURY_SERIES = "DGS10"` constant in the *new* package's
  own `config.py` rather than importing these — see Task 3's NOTE on why per-bond
  maturity-matching is out of scope for v1.
- `investments/briefs-finance/scripts/llm_extract.py` (whole file, 75 lines) — the existing
  pattern for "prompt an LLM for a single structured value via `sdk_compat.run_text`, parse
  the response, degrade to a sentinel on failure" — the closest existing precedent for
  Marker #2's `_summarize_lease_figure` (that one parses JSON; this one parses a bare
  number-or-`NONE`, simpler).
- `investments/my-trader/mytrader/sec_filings.py` lines 193-216
  (`_find_def14a_heading_index`) — the exact heuristic (last ALL-CAPS occurrence, trailing
  window, fallback to plain last-occurrence) Marker #2's own lease-note heading search
  mirrors. This helper itself is **not** renamed public and **not** reused directly (it's
  DEF-14A-specific, takes a pre-lowered `lower_text` param) — `lease_commitment.py` writes
  its own small version of the same heuristic against its own heading phrases.
- `investments/goat/goat/openinsider.py` lines 158-172 (`fetch_screener_filings`) — already
  reused as-is by `insider_trend.py`; no changes needed here, listed only so the pattern of
  "reuse an existing scraper function unmodified" is visible for comparison against Marker
  #12, which needs genuinely new fetch code (no existing bond-data scraper anywhere in this
  codebase).
- `investments/fourteen-crash-signals-daily-check/pyproject.toml` (whole file) — confirms
  `requests`/`openpyxl` are direct deps and `my-trader`/`goat` are workspace deps (so
  `beautifulsoup4`, imported transitively via `mytrader.sec_filings`, resolves through the
  shared workspace venv without a new dependency declaration — same as `mytrader.market_data`
  and `goat.openinsider` are already imported without redeclaring their deps).
- `investments/TOOLS.md` line 20 (the Fourteen Crash Signals row) and line 41 (the on-demand
  run command row) — both need updating once markers 2/4/9/12 go live.

### New Files to Create

- `investments/fourteen-crash-signals-daily-check/fourteen_crash_signals_daily_check/capex_cashflow.py`
  — Marker #4 check.
- `.../fourteen_crash_signals_daily_check/super_bowl.py` — Marker #9 check.
- `.../fourteen_crash_signals_daily_check/lease_commitment.py` — Marker #2 check.
- `.../fourteen_crash_signals_daily_check/credit_spread_issuer.py` — Marker #12 check.
- `.../fourteen_crash_signals_daily_check/tests/test_capex_cashflow.py`
- `.../fourteen_crash_signals_daily_check/tests/test_super_bowl.py`
- `.../fourteen_crash_signals_daily_check/tests/test_lease_commitment.py`
- `.../fourteen_crash_signals_daily_check/tests/test_credit_spread_issuer.py`

### Patterns to Follow

**Naming conventions**: `SIGNALS_*` prefix for every new config constant, each with a
trailing "why this number" comment (`config.py` — every existing constant follows this).
Module-level check functions named `check_<marker_name>`; per-ticker helpers prefixed `_`.

**Error handling**: Never raise from a check function. Any fetch/parse failure degrades to
either `verdict="unknown"` (source genuinely unreachable) or a silently-skipped ticker within
a `list[CheckResult]` (source reachable, this specific ticker has nothing to report — see
`insider_trend.py`'s `if bought == 0 and sold == 0: continue`). Every external `requests`
call and every yfinance call is wrapped in `try/except Exception: return None`
(`market_data.py`, `sec_filings.py`, `margin_debt.py` all do this identically).

**Logging pattern**: `print(f"[fourteen-signals-<module>] error ...: {e}")` for genuine
errors worth a log line (see `watchlist.py:35`) — not used for expected "nothing to report"
cases.

**DB pattern**: `INSERT ... ON CONFLICT(...) DO UPDATE` upserts wrapped in `with conn:` for
every new table (see `db.py`'s `upsert_signal_state`), never a separate
`SELECT`-then-`INSERT`-or-`UPDATE` branch.

**Cross-package imports**: `from mytrader import sec_filings` / `from mytrader import
market_data` / `from mytrader.checks import CheckResult` / `from scripts.macro import
fred_value_on` — the exact shape every existing module in this package already uses.

**Testing pattern**: `monkeypatch.setattr("fourteen_crash_signals_daily_check.<module>.<fn>",
...)` (module-path string form) for functions called via `from X import Y` inside the
module under test; `db_conn` fixture from `conftest.py` for any test touching the database.

---

## IMPLEMENTATION PLAN

### Phase 1: Foundation — cross-package renames + new schema/config

Make `sec_filings.py`'s low-level primitives usable from outside the `mytrader` package
(needed by both Marker #2 and Marker #12), extend its 10-K/10-Q extractors to capture the
Financial Statements section (needed by Marker #2), and add every new config constant and DB
table this phase's markers need.

### Phase 2: Core Implementation — the 4 markers, simplest first

Build `capex_cashflow.py` (Marker #4, no new tables, single yfinance fetch) and
`super_bowl.py` (Marker #9, no fetch at all, pure date logic) first as low-risk validations
of the wiring. Then `lease_commitment.py` (Marker #2, medium complexity — SEC extraction +
LLM structured-extraction + new history table). Then `credit_spread_issuer.py` (Marker #12,
highest complexity — CUSIP auto-discovery is deterministic and fully specified, but the
yield-lookup half requires an implementation-time live-verification spike per the handoff).

### Phase 3: Integration — Marker #14 enhancement + report/alert wiring

Add the watch tier to `credit_spread.py` and the daily-repeat alert to `alerts.py`
(independent of the 4 new markers, but grouped here since it touches the same files the
integration step below also touches). Wire all 4 new markers into `report.py` (replacing
placeholder rows) and `main.py` (calling the checks, feeding `alert_inputs`).

### Phase 4: Testing & Validation

Unit tests for every new function (mirroring the monkeypatch style of the existing test
suite), full-suite regression run, and a manual `daily-check` run against real external
sources to confirm the report renders correctly end-to-end.

---

## STEP-BY-STEP TASKS

IMPORTANT: Execute every task in order, top to bottom. Each task is atomic and independently
testable.

### Task 1: UPDATE `investments/my-trader/mytrader/sec_filings.py` — publicize 5 helpers, capture Financial Statements section

- **IMPLEMENT**: Rename 5 module-level functions by dropping their leading underscore, and
  update every internal call site within this same file to the new name:
  - `_get_cik` → `get_cik`
  - `_fetch_filing_index` → `fetch_filing_index`
  - `_fetch_filing_document` → `fetch_filing_document`
  - `_strip_html` → `strip_html`
  - `_latest_filing_entry` → `latest_filing_entry`

  Internal call sites to update (all within `get_filing_summaries_for_ticker`,
  `_extract_sections`, `_refresh_cik_map_if_stale`'s caller chain):
  ```python
  def _get_cik(conn: sqlite3.Connection, ticker: str) -> str | None:  # docstring/body unchanged
  ```
  becomes `def get_cik(...)`. Everywhere `_get_cik(conn, ticker.upper())` is called, use
  `get_cik(...)`. Same mechanical rename for the other 4 — grep the file for each
  underscore-prefixed name after renaming its definition to catch every call site (the
  definitions are at lines 76, 83, 94, 109, 125 respectively; call sites are within
  `get_filing_summaries_for_ticker` at lines 282-316 and `_extract_sections` at line 239).

  Then extend the two 10-K/10-Q extractors to also capture the Financial Statements section
  (currently only Business/Risk Factors/MD&A are kept — the Leases footnote Marker #2 needs
  lives inside Financial Statements, not MD&A):
  ```python
  def _extract_10k_sections(text: str) -> dict[str, str]:
      items = _split_by_item(text)
      sections = {}
      if "1" in items:
          sections["business"] = items["1"]
      if "1A" in items:
          sections["risk_factors"] = items["1A"]
      if "7" in items:
          sections["mda"] = items["7"]
      if "8" in items:
          sections["financial_statements"] = items["8"]
      return sections


  def _extract_10q_sections(text: str) -> dict[str, str]:
      parts = _split_by_part(text)
      part1_items = _split_by_item(parts.get("I", ""))
      part2_items = _split_by_item(parts.get("II", ""))
      sections = {}
      if "2" in part1_items:
          sections["mda"] = part1_items["2"]
      if "1A" in part2_items:
          sections["risk_factors"] = part2_items["1A"]
      if "1" in part1_items:
          sections["financial_statements"] = part1_items["1"]
      return sections
  ```
- **PATTERN**: The renames are purely mechanical — no logic changes, so behavior for
  existing callers (`get_filing_summaries_for_ticker`, and its own callers in
  `checks/principles_fit.py`) is unchanged.
- **GOTCHA**: The Phase 2 handoff's own text only explicitly names 4 functions to rename
  (`_get_cik`, `_fetch_filing_index`, `_fetch_filing_document`, `_strip_html`) in its "Also
  found" bullet — but both Marker #2 (`_latest_10k_or_10q` in `lease_commitment.py`, Task 12)
  and Marker #12 (`_resolve_cusip` in `credit_spread_issuer.py`, Task 14) also need
  `_latest_filing_entry` from outside the package (to find the most recent 10-K/10-Q, or the
  most recent 424B2/424B5/FWP, by form type). Rename this 5th function too — the handoff's
  list wasn't exhaustive, this is a real gap found during planning.
- **GOTCHA**: `_extract_sections` (the dispatcher that calls `_strip_html` then
  `_extract_10k_sections`/`_extract_10q_sections`/`_extract_def14a_sections`) stays private —
  only the 5 named functions become public. Do not rename `_extract_sections`,
  `_split_by_item`, `_split_by_part`, `_summarize_sections`, `_find_def14a_heading_index`, or
  `_extract_def14a_sections` — none of them are needed from outside this module.
- **VALIDATE**: `uv run --directory investments/my-trader python -c "from mytrader import
  sec_filings; assert sec_filings.get_cik and sec_filings.fetch_filing_index and
  sec_filings.fetch_filing_document and sec_filings.strip_html and
  sec_filings.latest_filing_entry; print('OK')"`

### Task 2: UPDATE `investments/my-trader/mytrader/tests/test_sec_filings.py` — fix renamed references

- **IMPLEMENT**: Every `monkeypatch.setattr(sec_filings, "_get_cik", ...)` /
  `"_fetch_filing_index"` / `"_fetch_filing_document"` string and every direct
  `sec_filings._get_cik(...)` call in this file must drop the leading underscore to match
  Task 1's renames. Specific lines to update (as read at plan-writing time — re-grep before
  editing in case line numbers have shifted): 19, 30, 36, 93, 94, 99, 101, 114, 116, 122,
  124, 133, 137, 146, 148, 157, 159. `_strip_html` and `_latest_filing_entry` are not
  referenced in this test file today, so no change needed for those two beyond confirming
  that stays true.
- **PATTERN**: `test_extract_10k_sections_against_real_fixture` (line 66-71) and
  `test_extract_10q_sections_against_real_fixture` (line 74-78) should also gain an
  assertion that `sections.get("financial_statements")` is now present, confirming Task 1's
  new extraction — the existing fixtures at `investments/my-trader/mytrader/tests/fixtures/
  sec_10k_sample.html` / `sec_10q_sample.html` already contain Item 8 / Part I Item 1 text
  (real filings always do) even though nothing asserted on it before.
- **GOTCHA**: `test_extract_10k_sections_against_real_fixture` and
  `test_extract_10q_sections_against_real_fixture` call `sec_filings._extract_sections`
  directly (still private, unchanged) — only the outer `_get_cik`/`_fetch_filing_index`/
  `_fetch_filing_document` monkeypatch targets in the other tests need updating.
- **VALIDATE**: `uv run --directory investments/my-trader python -m pytest
  mytrader/tests/test_sec_filings.py -v`

### Task 3: UPDATE `.../fourteen_crash_signals_daily_check/config.py` — new constants

- **IMPLEMENT**: Add `from datetime import date` to the imports, then append:
  ```python
  # Marker 2 -- off-balance-sheet lease commitments (SEC EDGAR 10-K/10-Q "Leases" note,
  # LLM-extracted dollar figure). See the Phase 2 handoff, Marker #2 resolution.
  SIGNALS_LEASE_COMMITMENT_GROWTH_FLAG_PCT = 50.0  # v1/tunable, unbacktestable -- no
      # historical time series for this disclosure exists; Shaun's own framing, 2026-08-18:
      # retune after a few quarters of real report output.
  SIGNALS_LEASE_NOTE_WINDOW_CHARS = 8000  # trailing window after the heading match --
      # mirrors sec_filings._find_def14a_heading_index's own window size.

  # Marker 4 -- capex outruns cash flow (negative free cash flow while capex is large).
  SIGNALS_CAPEX_MIN_FLAG_ABS = 10_000_000_000  # $10B sanity floor -- should never bind in
      # practice since watchlist.py already mega-cap-filters at $100B; insurance against a
      # data glitch, not a real threshold.

  # Marker 9 -- the Super Bowl signal (date-reminder + manual-check-flag; no structured
  # free data source exists for "% of ads that were AI-related" -- see the handoff).
  SIGNALS_NEXT_SUPER_BOWL_DATE = date(2027, 2, 14)  # Super Bowl LXI, SoFi Stadium --
      # human-maintained, bump forward by hand once Shaun records that year's ad-share
      # reading (see super_bowl.py's module docstring for the manual reset flow).

  # Marker 12 -- credit turns in the hot sector (bond yield vs Treasury proxy, per-issuer).
  SIGNALS_CREDIT_SPREAD_ISSUER_TREASURY_SERIES = "DGS10"  # v1 simplification: a fixed
      # 10Y Treasury comparator, not maturity-matched per-bond -- parsing each prospectus's
      # own maturity date was out of scope for this phase; a known follow-up, not a silent
      # shortcut (flagged explicitly in this plan's NOTES).
  SIGNALS_CREDIT_SPREAD_ISSUER_DIVERGENCE_FLAG_RATIO = 1.3  # v1/tunable -- current spread
      # >=1.3x the reading from 90 days ago.
  SIGNALS_ISSUER_SPREAD_LOOKBACK_DAYS = 90
  SIGNALS_ISSUER_SPREAD_LOOKBACK_TOLERANCE_DAYS = 10  # daily-granularity data, much
      # tighter than margin_debt's 20-day monthly-bucket tolerance.
  SIGNALS_BOND_CUSIP_REFRESH_DAYS = 30  # mirrors SEC_CIK_MAP_REFRESH_DAYS -- a company
      # could issue a new bond; don't cache a resolved CUSIP forever.
  SIGNALS_BOND_PROSPECTUS_FORM_TYPES = ("424B2", "424B5", "FWP")

  # Marker 14 enhancement -- "watch" tier below the flag threshold (added 2026-08-18;
  # confirmed with Shaun: keep verdict="ok" + data={"watch": True} rather than a new verdict
  # string, so nothing else that branches on verdict needs to change).
  SIGNALS_CREDIT_SPREAD_WATCH_PCT = 3.2  # within 0.3pp of the 3.5pp flag threshold.
  ```
- **PATTERN**: Every existing constant in this file has a trailing "why this number" comment
  — match that exactly, don't add bare constants.
- **VALIDATE**: `uv run --directory investments/fourteen-crash-signals-daily-check python -c
  "from fourteen_crash_signals_daily_check import config; print(config.SIGNALS_NEXT_SUPER_BOWL_DATE)"`

### Task 4: UPDATE `.../fourteen_crash_signals_daily_check/db.py` — 4 new tables + CRUD

- **IMPLEMENT**: Add to `init_signals_tables`'s `executescript` call:
  ```sql
  CREATE TABLE IF NOT EXISTS signals_lease_commitment_history (
      ticker              TEXT PRIMARY KEY,
      accession_number    TEXT NOT NULL,
      figure              REAL NOT NULL,
      filing_date         TEXT NOT NULL,
      checked_at          TEXT NOT NULL
  );
  CREATE TABLE IF NOT EXISTS signals_bond_cusip_cache (
      ticker              TEXT PRIMARY KEY,
      cusip               TEXT NOT NULL,
      accession_number    TEXT NOT NULL,
      resolved_at         TEXT NOT NULL
  );
  CREATE TABLE IF NOT EXISTS signals_issuer_spread_history (
      ticker              TEXT NOT NULL,
      spread_value        REAL NOT NULL,
      observed_at         TEXT NOT NULL,
      PRIMARY KEY (ticker, observed_at)
  );
  CREATE TABLE IF NOT EXISTS signals_manual_bond_yield (
      ticker              TEXT PRIMARY KEY,
      cusip               TEXT,
      yield_pct           REAL NOT NULL,
      entered_at          TEXT NOT NULL
  );
  ```
  Then add CRUD functions (below `upsert_signal_state`/`get_all_signal_states`):
  ```python
  def get_lease_commitment_history(conn: sqlite3.Connection, ticker: str) -> sqlite3.Row | None:
      return conn.execute(
          "SELECT * FROM signals_lease_commitment_history WHERE ticker = ?", (ticker,)
      ).fetchone()


  def upsert_lease_commitment_history(
      conn: sqlite3.Connection, *, ticker: str, accession_number: str, figure: float, filing_date: str
  ) -> None:
      with conn:
          conn.execute(
              """INSERT INTO signals_lease_commitment_history
                 (ticker, accession_number, figure, filing_date, checked_at)
                 VALUES (?, ?, ?, ?, ?)
                 ON CONFLICT(ticker) DO UPDATE SET accession_number=excluded.accession_number,
                 figure=excluded.figure, filing_date=excluded.filing_date, checked_at=excluded.checked_at""",
              (ticker, accession_number, figure, filing_date, _now()),
          )


  def get_bond_cusip(conn: sqlite3.Connection, ticker: str) -> sqlite3.Row | None:
      return conn.execute("SELECT * FROM signals_bond_cusip_cache WHERE ticker = ?", (ticker,)).fetchone()


  def upsert_bond_cusip(conn: sqlite3.Connection, *, ticker: str, cusip: str, accession_number: str) -> None:
      with conn:
          conn.execute(
              """INSERT INTO signals_bond_cusip_cache (ticker, cusip, accession_number, resolved_at)
                 VALUES (?, ?, ?, ?)
                 ON CONFLICT(ticker) DO UPDATE SET cusip=excluded.cusip,
                 accession_number=excluded.accession_number, resolved_at=excluded.resolved_at""",
              (ticker, cusip, accession_number, _now()),
          )


  def record_issuer_spread(conn: sqlite3.Connection, *, ticker: str, spread_value: float) -> None:
      today = _now()[:10]  # YYYY-MM-DD, one row per ticker per day
      with conn:
          conn.execute(
              """INSERT INTO signals_issuer_spread_history (ticker, spread_value, observed_at)
                 VALUES (?, ?, ?)
                 ON CONFLICT(ticker, observed_at) DO UPDATE SET spread_value=excluded.spread_value""",
              (ticker, spread_value, today),
          )


  def get_issuer_spread_near(
      conn: sqlite3.Connection, ticker: str, target_date, tolerance_days: int
  ) -> sqlite3.Row | None:
      """Closest row to target_date within tolerance_days -- same nearest-match-with-
      tolerance philosophy as mytrader margin_debt.py's _find_prior_year_row, adapted to
      query the DB directly instead of an in-memory series."""
      from datetime import date as _date

      rows = conn.execute(
          "SELECT * FROM signals_issuer_spread_history WHERE ticker = ? ORDER BY observed_at", (ticker,)
      ).fetchall()
      best, best_diff = None, None
      for row in rows:
          row_date = _date.fromisoformat(row["observed_at"])
          diff = abs((row_date - target_date).days)
          if best_diff is None or diff < best_diff:
              best, best_diff = row, diff
      if best is None or best_diff > tolerance_days:
          return None
      return best


  def get_manual_bond_yield(conn: sqlite3.Connection, ticker: str) -> sqlite3.Row | None:
      return conn.execute("SELECT * FROM signals_manual_bond_yield WHERE ticker = ?", (ticker,)).fetchone()


  def set_manual_bond_yield(conn: sqlite3.Connection, *, ticker: str, cusip: str | None, yield_pct: float) -> None:
      with conn:
          conn.execute(
              """INSERT INTO signals_manual_bond_yield (ticker, cusip, yield_pct, entered_at)
                 VALUES (?, ?, ?, ?)
                 ON CONFLICT(ticker) DO UPDATE SET cusip=excluded.cusip,
                 yield_pct=excluded.yield_pct, entered_at=excluded.entered_at""",
              (ticker, cusip, yield_pct, _now()),
          )
  ```
- **PATTERN**: `db.py:53-68` (`upsert_signal_state`) for the exact
  `INSERT ... ON CONFLICT DO UPDATE` upsert shape wrapped in `with conn:`.
- **GOTCHA**: `signals_lease_commitment_history` and `signals_bond_cusip_cache` are named
  with `PRIMARY KEY (ticker)` — despite "history" in the first table's name, this is a
  single-row-per-ticker cache (mirrors `sec_filing_cache`'s "invalidate on new
  accession_number" shape), not an append-only log. `signals_issuer_spread_history` **is**
  append-only (`PRIMARY KEY (ticker, observed_at)`) because Marker #12 genuinely needs
  multiple historical readings to find the one closest to 90 days ago.
- **VALIDATE**: `uv run --directory investments/fourteen-crash-signals-daily-check python -m
  pytest fourteen_crash_signals_daily_check/tests/test_db.py -v` (after Task 5).

### Task 5: UPDATE `.../fourteen_crash_signals_daily_check/tests/test_db.py` — new table tests

- **IMPLEMENT**: For each of the 4 new tables, mirror the existing
  `test_upsert_signal_state_*`-style tests already in this file: one test confirming insert,
  one confirming upsert-on-conflict overwrites the right fields, and for
  `get_issuer_spread_near` specifically, tests confirming (a) exact match, (b) closest match
  within tolerance, (c) `None` returned when nothing is within tolerance, (d) `None` returned
  when the table is empty for that ticker.
- **PATTERN**: Use the `db_conn` fixture from `conftest.py` — do not construct a raw
  `sqlite3.connect` in this test file.
- **VALIDATE**: `uv run --directory investments/fourteen-crash-signals-daily-check python -m
  pytest fourteen_crash_signals_daily_check/tests/test_db.py -v`

### Task 6: UPDATE `investments/my-trader/mytrader/market_data.py` — `fetch_cash_flow_statement`

- **IMPLEMENT**:
  ```python
  def fetch_cash_flow_statement(ticker: str) -> dict[str, float] | None:
      """Latest ANNUAL cash-flow statement (not quarterly/TTM -- Phase 2 handoff, Marker #4
      resolution: matches the fact-check's own cited Oracle numbers, which are FY26 annual,
      and avoids quarterly noise). Confirmed live 2026-08-18 against real ORCL data:
      yf.Ticker(ticker).cashflow already exposes a precomputed "Free Cash Flow" row --
      Free Cash Flow = Operating Cash Flow + Capital Expenditure (capex is stored as a
      negative outflow, so this is addition not subtraction). Mirrors
      fetch_balance_sheet_financials's exact try/except/return-None shape."""
      import yfinance as yf

      try:
          t = yf.Ticker(ticker)
          cf = t.cashflow
          if cf is None or cf.empty:
              return None
          latest_col = cf.columns[0]  # most recent annual period, leftmost column
          result: dict[str, float] = {}
          for row_label, key in (
              ("Free Cash Flow", "free_cash_flow"),
              ("Capital Expenditure", "capital_expenditure"),
              ("Operating Cash Flow", "operating_cash_flow"),
          ):
              if row_label in cf.index:
                  value = cf.loc[row_label, latest_col]
                  if value is not None:
                      result[key] = float(value)
          if "free_cash_flow" not in result:
              return None
          result["period_end"] = latest_col.date().isoformat() if hasattr(latest_col, "date") else str(latest_col)
          return result
      except Exception:
          return None
  ```
- **PATTERN**: `market_data.py:114-155` (`fetch_balance_sheet_financials`) for the exact
  try/except/return-`None` shape and docstring style.
- **GOTCHA — CONFIRM BEFORE TRUSTING**: yfinance's cash-flow field naming has drifted across
  library versions (older docs reference `capitalExpenditures`/
  `totalCashFromOperatingActivities` as `.info`-style camelCase dict keys; the row labels
  above were confirmed live 2026-08-18 against the version pinned in this workspace's
  `uv.lock` at that time). Re-confirm the exact installed version's row labels before relying
  on this: `uv run --directory investments/my-trader python -c "import yfinance;
  print(yfinance.Ticker('ORCL').cashflow.index.tolist())"` — if `"Free Cash Flow"`,
  `"Capital Expenditure"`, `"Operating Cash Flow"` are not all present verbatim, adjust the
  row-label strings above to match what's actually installed, don't trust this plan's
  strings blindly if the pinned version has since changed.
- **VALIDATE**: `uv run --directory investments/my-trader python -c "from mytrader import
  market_data; print(market_data.fetch_cash_flow_statement('ORCL'))"` (live network call —
  confirm it returns a dict with all 4 keys before moving on).

### Task 7: UPDATE `investments/my-trader/mytrader/tests/test_market_data.py` — cash-flow tests

- **IMPLEMENT**: Add a `_install_fake_yfinance`-style fixture extension (or new helper) that
  fakes `t.cashflow` as a `pandas.DataFrame` indexed by row label with one column (a
  `pd.Timestamp`). Tests to add: (a) happy path returns all 4 keys with correct values, (b)
  returns `None` when `cashflow` is empty, (c) returns `None` when `"Free Cash Flow"` row is
  missing (the one required key), (d) still returns a partial dict (missing
  `capital_expenditure`) when only that row is absent but `"Free Cash Flow"` is present.
- **PATTERN**: `test_market_data.py:141-180` (`fetch_balance_sheet_financials` tests) for the
  exact `_install_fake_yfinance(monkeypatch, balance_sheet=bs, financials=fin)` fixture-call
  shape — extend that same helper to also accept a `cashflow=` kwarg rather than writing a
  parallel fixture.
- **VALIDATE**: `uv run --directory investments/my-trader python -m pytest
  mytrader/tests/test_market_data.py -v -k cash_flow`

### Task 8: CREATE `.../fourteen_crash_signals_daily_check/capex_cashflow.py` (Marker #4)

- **IMPLEMENT**:
  ```python
  """Marker 4 -- capex outruns cash flow, via a negative free-cash-flow check (design (b)
  from the Phase 2 handoff, not a two-period capex/revenue growth-gap -- simpler,
  single-period, and doesn't need a second income-statement fetch). Confirmed live
  2026-08-18 against real ORCL data: FCF = Operating Cash Flow + Capital Expenditure
  (capex already negative)."""

  from __future__ import annotations

  from typing import Any

  from mytrader import market_data
  from mytrader.checks import CheckResult

  from . import config


  def _check_one_ticker(ticker: str) -> CheckResult | None:
      cf = market_data.fetch_cash_flow_statement(ticker)
      if cf is None:
          return None
      fcf = cf["free_cash_flow"]
      capex = abs(cf.get("capital_expenditure", 0.0))
      detail = (
          f"{ticker}: Free Cash Flow ${fcf / 1e9:+.1f}B, Capital Expenditure ${capex / 1e9:.1f}B "
          f"(period ending {cf.get('period_end', '?')})"
      )
      verdict = "flag" if fcf < 0 and capex >= config.SIGNALS_CAPEX_MIN_FLAG_ABS else "ok"
      return CheckResult(
          name="capex_cashflow", verdict=verdict, detail=detail,
          data={"ticker": ticker, "free_cash_flow": fcf, "capital_expenditure": capex, "period_end": cf.get("period_end")},
      )


  def check_capex_cashflow(hot_watchlist: list[Any]) -> list[CheckResult]:
      results = []
      for row in hot_watchlist:
          result = _check_one_ticker(row["ticker"])
          if result is not None:
              results.append(result)
      return results
  ```
- **PATTERN**: `market_cap_milestone.py` for the "consume `hot_watchlist` rows directly, no
  DB connection needed" shape; `insider_trend.py` for the "return `list[CheckResult]`, skip
  tickers with nothing to report" shape.
- **VALIDATE**: `uv run --directory investments/fourteen-crash-signals-daily-check python -m
  pytest fourteen_crash_signals_daily_check/tests/test_capex_cashflow.py -v` (after Task 9).

### Task 9: CREATE `.../fourteen_crash_signals_daily_check/tests/test_capex_cashflow.py`

- **IMPLEMENT**: Mirror `test_credit_spread.py`'s monkeypatch-at-module-level style.
  Monkeypatch `fourteen_crash_signals_daily_check.capex_cashflow.market_data.fetch_cash_flow_statement`.
  Tests: (a) flags when FCF negative and capex ≥ `SIGNALS_CAPEX_MIN_FLAG_ABS`, (b) stays ok
  when FCF negative but capex below the floor, (c) stays ok when FCF positive regardless of
  capex size, (d) ticker silently skipped (not present in results) when
  `fetch_cash_flow_statement` returns `None`, (e) `check_capex_cashflow` with an empty
  watchlist returns `[]`.
- **VALIDATE**: `uv run --directory investments/fourteen-crash-signals-daily-check python -m
  pytest fourteen_crash_signals_daily_check/tests/test_capex_cashflow.py -v`

### Task 10: CREATE `.../fourteen_crash_signals_daily_check/super_bowl.py` (Marker #9)

- **IMPLEMENT**:
  ```python
  """Marker 9 -- the Super Bowl signal. No structured free data source exists for "% of
  Super Bowl ads that were AI-related" (see the Phase 2 handoff) -- a scheduled daily job
  can't do the web-research pass a human/agent can. v1 scope, confirmed with Shaun
  2026-08-18: a date-proximity reminder, not content automation.

  Manual reset flow: once SIGNALS_NEXT_SUPER_BOWL_DATE passes, this check flags every day
  until Shaun manually checks that year's post-game trade coverage (Adweek etc.) and bumps
  SIGNALS_NEXT_SUPER_BOWL_DATE forward to next year's game in config.py -- the flag clears
  itself the moment the constant is bumped, no separate acknowledgment table needed."""

  from __future__ import annotations

  from datetime import date

  from mytrader.checks import CheckResult

  from . import config


  def check_super_bowl_signal() -> CheckResult:
      today = date.today()
      target = config.SIGNALS_NEXT_SUPER_BOWL_DATE
      if today < target:
          days_left = (target - today).days
          return CheckResult(
              name="super_bowl_signal", verdict="unknown",
              detail=f"Next Super Bowl is {target.isoformat()} ({days_left} day(s) away) -- "
                     f"ad-share content is not automatable, nothing to check yet",
              data={"next_date": target.isoformat(), "days_left": days_left},
          )
      return CheckResult(
          name="super_bowl_signal", verdict="flag",
          detail=f"Super Bowl ({target.isoformat()}) has passed -- manually check that year's "
                 f"post-game trade coverage (Adweek etc.) for AI-related ad share, then bump "
                 f"SIGNALS_NEXT_SUPER_BOWL_DATE forward in config.py to clear this flag",
          data={"next_date": target.isoformat()},
      )
  ```
- **PATTERN**: `credit_spread.py`'s module docstring style for explaining *why* this marker
  is shaped differently from the others.
- **GOTCHA**: `verdict="unknown"` is used here for the *normal, expected, most-of-the-year*
  state (waiting for the date) — a deliberate deviation from `"unknown"`'s usual meaning
  elsewhere in this package ("a data source failed"). This is intentional per the handoff
  ("never silently 'ok' when nothing was actually checked") — `report.py`/`main.py` must not
  treat this marker's `"unknown"` as something to alert on the way a genuine fetch failure
  might be treated elsewhere.
- **VALIDATE**: `uv run --directory investments/fourteen-crash-signals-daily-check python -m
  pytest fourteen_crash_signals_daily_check/tests/test_super_bowl.py -v` (after Task 11).

### Task 11: CREATE `.../fourteen_crash_signals_daily_check/tests/test_super_bowl.py`

- **IMPLEMENT**: Monkeypatch `config.SIGNALS_NEXT_SUPER_BOWL_DATE` to control "today vs.
  target" in tests (or monkeypatch `super_bowl.date` if freezing "today" is cleaner — check
  whether this codebase already has a date-freezing convention in `margin_debt.py`'s tests
  first and mirror it). Tests: (a) `verdict="unknown"` with correct `days_left` when target
  is in the future, (b) `verdict="flag"` when target is today, (c) `verdict="flag"` when
  target is in the past.
- **VALIDATE**: `uv run --directory investments/fourteen-crash-signals-daily-check python -m
  pytest fourteen_crash_signals_daily_check/tests/test_super_bowl.py -v`

### Task 12: CREATE `.../fourteen_crash_signals_daily_check/lease_commitment.py` (Marker #2)

- **IMPLEMENT**:
  ```python
  """Marker 2 -- off-balance-sheet lease commitments ("leases that have not yet
  commenced"), disclosed as narrative footnote text in the Leases note of the Financial
  Statements section of a 10-K/10-Q -- not a clean XBRL field (see the Phase 2 handoff's
  Marker #2 section for the full fact-check). Reuses sec_filings.py's CIK/filing-index/
  document-fetch plumbing directly (now public, see Task 1) plus a new heading-search + a
  new strictly-parseable LLM prompt, distinct from sec_filings._summarize_sections's
  free-prose one."""

  from __future__ import annotations

  import re
  import sqlite3
  from typing import Any

  from mytrader import sec_filings
  from mytrader.checks import CheckResult

  from . import config, db

  _LEASE_HEADING_CANDIDATES = (
      "leases that have not yet commenced",
      "leases not yet commenced",
      "leases signed but not yet commenced",
  )

  _LEASE_FIGURE_PROMPT = """\
  You are extracting a single financial figure from a SEC filing's Leases note for {ticker}.

  Return ONLY a single number in USD (no symbols, no commas, no words) for the total \
  dollar amount of leases that have not yet commenced (i.e. signed but not yet begun). \
  If this filing does not disclose such a figure, return exactly: NONE

  Text:
  ---
  {text}
  ---
  """


  def _find_lease_note_window(text: str) -> str | None:
      """Mirrors sec_filings._find_def14a_heading_index's heuristic: footnotes have no
      Item-style header, so search for the heading phrase itself, preferring the last
      ALL-CAPS occurrence (the real note header) over a prose cross-reference, falling back
      to plain last-occurrence if no ALL-CAPS hit exists."""
      lower = text.lower()
      idxs: list[int] = []
      for heading in _LEASE_HEADING_CANDIDATES:
          start = 0
          while True:
              idx = lower.find(heading, start)
              if idx == -1:
                  break
              idxs.append(idx)
              start = idx + 1
      if not idxs:
          return None
      caps_idxs = [i for i in idxs if text[i:i + 40].isupper()]
      idx = caps_idxs[-1] if caps_idxs else idxs[-1]
      return text[idx: idx + config.SIGNALS_LEASE_NOTE_WINDOW_CHARS]


  def _summarize_lease_figure(ticker: str, text: str) -> float | None:
      import asyncio
      import sys
      from pathlib import Path

      _scripts_dir = Path(__file__).resolve().parent.parent.parent.parent / ".claude" / "scripts"
      sys.path.insert(0, str(_scripts_dir))
      from sdk_compat import ClaudeAgentOptions, run_text

      prompt = _LEASE_FIGURE_PROMPT.format(ticker=ticker, text=text[:config.SIGNALS_LEASE_NOTE_WINDOW_CHARS])
      try:
          raw = asyncio.run(run_text(
              prompt=prompt,
              options=ClaudeAgentOptions(allowed_tools=[], model="sonnet"),
          )).strip()
      except Exception:
          return None
      if raw.upper() == "NONE":
          return None
      cleaned = re.sub(r"[^\d.]", "", raw)
      try:
          return float(cleaned) if cleaned else None
      except ValueError:
          return None


  def _latest_10k_or_10q(index: dict[str, Any]) -> tuple[str, dict[str, str]] | None:
      """Whichever of 10-K/10-Q was filed most recently -- an annual 10-K can update this
      figure too, not just quarterlies (Phase 2 handoff, Marker #2 resolution)."""
      candidates = []
      for filing_type in ("10-K", "10-Q"):
          entry = sec_filings.latest_filing_entry(index, filing_type)
          if entry is not None:
              candidates.append((filing_type, entry))
      if not candidates:
          return None
      candidates.sort(key=lambda c: c[1]["filing_date"], reverse=True)
      return candidates[0]


  def _check_one_ticker(conn: sqlite3.Connection, ticker: str) -> CheckResult | None:
      cik = sec_filings.get_cik(conn, ticker)
      if cik is None:
          return None
      index = sec_filings.fetch_filing_index(cik)
      if index is None:
          return None
      latest = _latest_10k_or_10q(index)
      if latest is None:
          return None
      filing_type, entry = latest

      prior = db.get_lease_commitment_history(conn, ticker)
      if prior is not None and prior["accession_number"] == entry["accession_number"]:
          figure = prior["figure"]  # unchanged since last check -- skip re-fetch/re-summarize
      else:
          html = sec_filings.fetch_filing_document(cik, entry["accession_number"], entry["primary_document"])
          if html is None:
              return None
          text = sec_filings.strip_html(html)
          window = _find_lease_note_window(text)
          if window is None:
              return None  # not disclosed this filing -- an honest gap, not a fetch failure
          figure = _summarize_lease_figure(ticker, window)
          if figure is None:
              return None
          db.upsert_lease_commitment_history(
              conn, ticker=ticker, accession_number=entry["accession_number"],
              figure=figure, filing_date=entry["filing_date"],
          )

      if prior is None:
          return CheckResult(
              name="lease_commitments", verdict="ok",
              detail=f"{ticker}: ${figure / 1e9:.1f}B uncommenced lease commitments "
                     f"(baseline, {filing_type} filed {entry['filing_date']}) -- no prior "
                     f"reading to compare growth against yet",
              data={"ticker": ticker, "figure": figure, "filing_date": entry["filing_date"]},
          )

      growth_pct = (figure - prior["figure"]) / prior["figure"] * 100 if prior["figure"] else 0.0
      detail = (
          f"{ticker}: ${figure / 1e9:.1f}B uncommenced lease commitments "
          f"({growth_pct:+.1f}% since last filing, {filing_type} filed {entry['filing_date']})"
      )
      verdict = "flag" if growth_pct >= config.SIGNALS_LEASE_COMMITMENT_GROWTH_FLAG_PCT else "ok"
      return CheckResult(
          name="lease_commitments", verdict=verdict, detail=detail,
          data={"ticker": ticker, "figure": figure, "growth_pct": growth_pct, "filing_date": entry["filing_date"]},
      )


  def check_lease_commitments(conn: sqlite3.Connection, hot_watchlist: list[Any]) -> list[CheckResult]:
      results = []
      for row in hot_watchlist:
          result = _check_one_ticker(conn, row["ticker"])
          if result is not None:
              results.append(result)
      return results
  ```
- **PATTERN**: `investments/briefs-finance/scripts/llm_extract.py` (whole file) for the
  "prompt an LLM for one structured value via `sdk_compat.run_text`, degrade to a sentinel on
  parse failure" shape — this is simpler (a bare number-or-`NONE`, not JSON) so no retry loop
  is needed, unlike `llm_extract.py`'s 3-retry JSON parse.
- **IMPORTS**: `sdk_compat` lives in `.claude/scripts`, not in this package or `mytrader` —
  the `sys.path.insert` dance inside `_summarize_lease_figure` mirrors
  `sec_filings.py:34-36`'s exact module-level pattern (done inside the function here rather
  than at module level, since this keeps the import lazy/optional the same way
  `alerts.py:26-31` already does for `notifications`).
  ```
- **GOTCHA**: The very first time a ticker is ever checked (`prior is None`), the result is
  always `verdict="ok"` regardless of the dollar figure's size — there's nothing to compare
  growth against yet. Do not attempt to flag on an absolute dollar threshold for the baseline
  case; only growth-rate flags after a second observation, per the handoff's explicit
  resolution.
- **GOTCHA**: If the same accession_number is seen again on a later run (no new filing yet),
  this function reuses the cached `figure` without re-fetching or re-summarizing — cheap, and
  correctly produces `growth_pct == 0.0` (not a flag) rather than re-running an unnecessary
  LLM call every single day between filings.
- **VALIDATE**: `uv run --directory investments/fourteen-crash-signals-daily-check python -m
  pytest fourteen_crash_signals_daily_check/tests/test_lease_commitment.py -v` (after
  Task 13).

### Task 13: CREATE `.../fourteen_crash_signals_daily_check/tests/test_lease_commitment.py`

- **IMPLEMENT**: Monkeypatch `sec_filings.get_cik`/`fetch_filing_index`/`fetch_filing_document`
  (imported via `lease_commitment.sec_filings`) and `lease_commitment._summarize_lease_figure`
  directly (don't actually call an LLM in tests — this is the one function in this whole
  plan that hits `sdk_compat`, and every other test file in this project stubs the LLM call
  rather than invoking it). Tests: (a) first-ever observation for a ticker returns
  `verdict="ok"` with no `growth_pct`-based flag regardless of figure size, (b) second
  observation with ≥50% growth flags, (c) second observation with <50% growth stays ok, (d)
  same accession_number on a second run reuses the cached figure and does not call the fetch
  functions again (assert via a `_raise`-style monkeypatch, mirroring
  `test_sec_filings.py:111-114`'s "should not fetch" pattern), (e) ticker with no CIK is
  silently skipped, (f) ticker whose filing has no matching heading (`_find_lease_note_window`
  returns `None`) is silently skipped, not treated as an error.
- **PATTERN**: `test_sec_filings.py:98-119`
  (`test_get_filing_summaries_uses_cache_when_accession_unchanged`) for the exact
  "assert the fetch function is never called" test shape via a `_raise` stub.
- **VALIDATE**: `uv run --directory investments/fourteen-crash-signals-daily-check python -m
  pytest fourteen_crash_signals_daily_check/tests/test_lease_commitment.py -v`

### Task 14: CREATE `.../fourteen_crash_signals_daily_check/credit_spread_issuer.py` (Marker #12)

- **IMPLEMENT**:
  ```python
  """Marker 12 -- credit turns in the hot sector while the broad market stays calm (bond
  yield vs. Treasury proxy, per-issuer). Two independent sub-problems (Phase 2 handoff,
  Marker #12 resolution):

  1. Ticker -> bond CUSIP: solved. Corporate bond prospectus filings (424B2/424B5/FWP)
     state "CUSIP No. XXXXXXXXX" on the cover page as a matter of regulatory practice --
     reuses sec_filings.py's CIK/filing-index/document-fetch plumbing (now public). Some
     issuers (private-credit-heavy names, Rule 144A private placements) have no public
     prospectus on EDGAR -- degrades to "no public bond found" for them, an honest gap, not
     a bug.

  2. CUSIP -> current yield: NOT solved as of the Phase 2 handoff. FINRA's own Fixed Income
     Data Center and the Morningstar Bond Center mirror are both JS-rendered, not scrapeable
     via plain requests.get(). Four third-party candidate sites were named but none confirmed
     working (Atlantis Data Solutions, Terrapin Finance, Empirasign, Cbonds). TASK: live-
     verify each against a real CUSIP discovered by part 1 above BEFORE trusting
     _fetch_bond_yield_live's implementation here -- see that function's docstring. If none
     pan out, this check falls back to db.get_manual_bond_yield (Shaun enters a reading by
     hand via main.py's `record-bond-yield` subcommand, Task 22)."""

  from __future__ import annotations

  import re
  import sqlite3
  from datetime import date, timedelta
  from typing import Any

  from mytrader import sec_filings
  from mytrader.checks import CheckResult
  from scripts.macro import fred_value_on

  from . import config, db

  _CUSIP_RE = re.compile(r"CUSIP\s*(?:No\.?|Number)?[:\s]*([A-Z0-9]{9})", re.IGNORECASE)


  def _resolve_cusip(conn: sqlite3.Connection, ticker: str) -> str | None:
      cached = db.get_bond_cusip(conn, ticker)
      if cached is not None:
          return cached["cusip"]  # SIGNALS_BOND_CUSIP_REFRESH_DAYS staleness check: v1
              # skips this (re-resolving only when nothing is cached yet) -- see NOTES.

      cik = sec_filings.get_cik(conn, ticker)
      if cik is None:
          return None
      index = sec_filings.fetch_filing_index(cik)
      if index is None:
          return None

      candidates = []
      for form_type in config.SIGNALS_BOND_PROSPECTUS_FORM_TYPES:
          entry = sec_filings.latest_filing_entry(index, form_type)
          if entry is not None:
              candidates.append(entry)
      if not candidates:
          return None  # no public prospectus on EDGAR -- e.g. Rule 144A private placement
      candidates.sort(key=lambda c: c["filing_date"], reverse=True)
      latest = candidates[0]

      html = sec_filings.fetch_filing_document(cik, latest["accession_number"], latest["primary_document"])
      if html is None:
          return None
      text = sec_filings.strip_html(html)[:5000]  # cover page is near the top of the document
      match = _CUSIP_RE.search(text)
      if match is None:
          return None
      cusip = match.group(1).upper()
      db.upsert_bond_cusip(conn, ticker=ticker, cusip=cusip, accession_number=latest["accession_number"])
      return cusip


  def _fetch_bond_yield_live(cusip: str) -> float | None:
      """SPIKE TASK, do this FIRST before trusting the rest of this function: test each of
      the 4 candidate sites (Atlantis Data Solutions, Terrapin Finance, Empirasign, Cbonds)
      against a real CUSIP from _resolve_cusip() above -- proper request headers, check for
      a JSON/AJAX endpoint behind the page, not just the top-level URL (same approach that
      found SEC EDGAR needs a User-Agent header, see sec_filings.py's module docstring).
      Document findings in this docstring once tested. If a working source is found,
      implement the fetch here. If none pan out (a real, accepted possible outcome per the
      handoff), leave this returning None permanently -- check_credit_spread_issuer already
      falls back to db.get_manual_bond_yield when this returns None, so the marker degrades
      to a semi-automated, manually-entered-yield shape rather than breaking."""
      return None  # unresolved as of the Phase 2 handoff -- see docstring


  def _get_yield(conn: sqlite3.Connection, ticker: str, cusip: str) -> float | None:
      live = _fetch_bond_yield_live(cusip)
      if live is not None:
          return live
      manual = db.get_manual_bond_yield(conn, ticker)
      return manual["yield_pct"] if manual is not None else None


  def _check_one_ticker(conn: sqlite3.Connection, ticker: str) -> CheckResult | None:
      cusip = _resolve_cusip(conn, ticker)
      if cusip is None:
          return None
      yield_pct = _get_yield(conn, ticker, cusip)
      if yield_pct is None:
          return CheckResult(
              name="credit_spread_issuer", verdict="unknown",
              detail=f"{ticker}: bond CUSIP {cusip} found, but no live or manually-entered "
                     f"yield reading available -- run `record-bond-yield {ticker} <yield_pct>`",
              data={"ticker": ticker, "cusip": cusip},
          )
      today = date.today()
      treasury_yield = fred_value_on(config.SIGNALS_CREDIT_SPREAD_ISSUER_TREASURY_SERIES, today)
      if treasury_yield is None:
          return CheckResult(
              name="credit_spread_issuer", verdict="unknown",
              detail=f"{ticker}: Treasury yield unavailable (FRED_API_KEY not set, or series unavailable)",
              data={"ticker": ticker, "cusip": cusip},
          )
      spread = yield_pct - treasury_yield
      db.record_issuer_spread(conn, ticker=ticker, spread_value=spread)

      prior = db.get_issuer_spread_near(
          conn, ticker, today - timedelta(days=config.SIGNALS_ISSUER_SPREAD_LOOKBACK_DAYS),
          config.SIGNALS_ISSUER_SPREAD_LOOKBACK_TOLERANCE_DAYS,
      )
      if prior is None:
          return CheckResult(
              name="credit_spread_issuer", verdict="ok",
              detail=f"{ticker}: spread {spread:.2f}pp (baseline, no 90-day-prior reading to "
                     f"compare divergence against yet)",
              data={"ticker": ticker, "cusip": cusip, "spread": spread},
          )
      prior_spread = prior["spread_value"]
      ratio = spread / prior_spread if prior_spread else None
      detail = (
          f"{ticker}: spread {spread:.2f}pp vs {prior_spread:.2f}pp 90 days ago ({ratio:.2f}x)"
          if ratio is not None else f"{ticker}: spread {spread:.2f}pp"
      )
      verdict = "flag" if ratio is not None and ratio >= config.SIGNALS_CREDIT_SPREAD_ISSUER_DIVERGENCE_FLAG_RATIO else "ok"
      return CheckResult(
          name="credit_spread_issuer", verdict=verdict, detail=detail,
          data={"ticker": ticker, "cusip": cusip, "spread": spread, "ratio": ratio},
      )


  def check_credit_spread_issuer(conn: sqlite3.Connection, hot_watchlist: list[Any]) -> list[CheckResult]:
      results = []
      for row in hot_watchlist:
          result = _check_one_ticker(conn, row["ticker"])
          if result is not None:
              results.append(result)
      return results
  ```
- **PATTERN**: `sec_filings.py`'s own CIK-resolution + filing-fetch pattern, reused directly
  via the public functions from Task 1. `margin_debt.py`'s
  `_find_prior_year_row`/tolerance-window approach for the general shape of
  `db.get_issuer_spread_near`.
- **IMPORTS**: `fred_value_on` from `scripts.macro` (`investments/briefs-finance/scripts/
  macro.py:102`) — same cross-package import shape as `credit_spread.py`'s existing
  `from scripts.macro import fred_series_range`.
- **GOTCHA — do this before writing anything else in this task**: `_fetch_bond_yield_live`
  is intentionally a stub returning `None`. Per the handoff, run the live-verification spike
  first: use `_resolve_cusip` against a real hot-watchlist ticker (run it standalone via a
  throwaway script or the Python REPL) to get one real CUSIP, then try each of the 4
  candidate sites against it with a real `User-Agent` header and check browser devtools
  Network tab for a JSON/AJAX endpoint the page's JS calls. If one works, implement the fetch
  in `_fetch_bond_yield_live` and update its docstring with what was found. If none work,
  leave the stub as-is — the manual-entry fallback path (`db.get_manual_bond_yield`,
  `main.py`'s `record-bond-yield` subcommand) is not a degraded placeholder, it's this
  marker's accepted v1 shape per the handoff's own framing ("a semi-automated marker, not a
  failure").
- **GOTCHA**: `_resolve_cusip` does not implement `SIGNALS_BOND_CUSIP_REFRESH_DAYS`
  staleness re-checking in this v1 (once a CUSIP is cached for a ticker, it's used
  indefinitely) — the constant is defined in `config.py` (Task 3) for a documented future
  follow-up, not wired in yet. Flag this explicitly in code review; it's a deliberate v1
  scope-trim to keep this already-large task bounded, not an oversight — a company issuing
  an entirely new benchmark bond is rare enough that a manual `DELETE FROM
  signals_bond_cusip_cache WHERE ticker = ?` is an acceptable manual escape hatch for now.
- **GOTCHA**: `SIGNALS_CREDIT_SPREAD_ISSUER_TREASURY_SERIES = "DGS10"` is a fixed comparator,
  not maturity-matched to each bond's actual remaining term (the handoff describes
  maturity-matching as the ideal, but no maturity-parsing mechanism was resolved in Round 2).
  This is a documented v1 simplification — do not silently try to add per-bond maturity
  matching as an unplanned enhancement; it would need its own maturity-date regex off the
  same prospectus cover page and its own design discussion.
- **VALIDATE**: `uv run --directory investments/fourteen-crash-signals-daily-check python -m
  pytest fourteen_crash_signals_daily_check/tests/test_credit_spread_issuer.py -v` (after
  Task 15). Also, once `_fetch_bond_yield_live`'s spike is done (whichever branch),
  live-validate `_resolve_cusip` against a real ticker with a known public bond (e.g. `ORCL`)
  before trusting the regex against real EDGAR HTML.

### Task 15: CREATE `.../fourteen_crash_signals_daily_check/tests/test_credit_spread_issuer.py`

- **IMPLEMENT**: Monkeypatch `sec_filings.get_cik`/`fetch_filing_index`/`fetch_filing_document`,
  `credit_spread_issuer._fetch_bond_yield_live`, and `credit_spread_issuer.fred_value_on`.
  Tests: (a) CUSIP resolved and cached from a fake 424B2 filing's cover-page HTML (regex
  match), (b) cached CUSIP reused without re-fetching on a second call (assert-not-called
  style), (c) no CUSIP found when none of the 3 form types are present in the filing index
  (ticker skipped, `None` returned), (d) `verdict="unknown"` with the `record-bond-yield`
  hint when CUSIP resolves but neither live nor manual yield is available, (e) manual yield
  used when `_fetch_bond_yield_live` returns `None` but `db.get_manual_bond_yield` has a row,
  (f) `verdict="ok"` baseline (no flag) on the first-ever spread observation for a ticker,
  (g) `verdict="flag"` when spread ≥1.3x the 90-day-prior reading, (h) `verdict="ok"` when
  ratio is below 1.3x, (i) `verdict="unknown"` when `fred_value_on` returns `None`.
- **PATTERN**: `test_sec_filings.py`'s monkeypatch-the-module-function style, applied to
  `credit_spread_issuer.sec_filings.<fn>` (the module-attribute path, since this file does
  `from mytrader import sec_filings` then calls `sec_filings.get_cik(...)`, not
  `from mytrader.sec_filings import get_cik`).
- **VALIDATE**: `uv run --directory investments/fourteen-crash-signals-daily-check python -m
  pytest fourteen_crash_signals_daily_check/tests/test_credit_spread_issuer.py -v`

### Task 16: UPDATE `.../fourteen_crash_signals_daily_check/credit_spread.py` — Marker #14 watch tier

- **IMPLEMENT**: Replace the final `return CheckResult(name="credit_spread_streak",
  verdict="ok", ...)` block (the non-flagging branch) with:
  ```python
  watch = latest_value >= config.SIGNALS_CREDIT_SPREAD_WATCH_PCT
  detail = (
      f"ICE BofA US HY OAS at {latest_value:.2f}pp (as of {latest_date.isoformat()}); "
      f"{streak_days} consecutive day(s) at/above {config.SIGNALS_CREDIT_SPREAD_STREAK_FLAG_PCT:.1f}pp "
      f"(needs {config.SIGNALS_CREDIT_SPREAD_STREAK_TRADING_DAYS} to flag)"
  )
  if watch:
      gap = config.SIGNALS_CREDIT_SPREAD_STREAK_FLAG_PCT - config.SIGNALS_CREDIT_SPREAD_WATCH_PCT
      detail += f" -- WATCH: within {gap:.1f}pp of the flag threshold"
  return CheckResult(
      name="credit_spread_streak", verdict="ok", detail=detail,
      data={"value": latest_value, "streak_days": streak_days, "as_of": latest_date.isoformat(), "watch": watch},
  )
  ```
  The `verdict="flag"` branch above it is unchanged.
- **PATTERN**: Confirmed with Shaun 2026-08-18 — `data={"watch": True}`, `verdict` stays
  `"ok"`, no 5th verdict string added to the `CheckResult` contract.
- **GOTCHA**: `watch` is computed purely from `latest_value >= SIGNALS_CREDIT_SPREAD_WATCH_PCT`
  — it does not consider `streak_days` proximity to the 21-day duration threshold (e.g. a
  spread at 3.6% for only 3 days is `verdict="flag"`... wait, re-check: 3.6% is already
  above the 3.5% flag *value*, so it's accumulating streak_days, not in "watch" territory at
  all — watch is specifically for the *value* gap (3.2%–3.49%), per the handoff's literal
  wording. A separate "streak-duration approaching 21 days" watch state was considered but is
  explicitly out of scope — don't add it silently.
- **VALIDATE**: `uv run --directory investments/fourteen-crash-signals-daily-check python -m
  pytest fourteen_crash_signals_daily_check/tests/test_credit_spread.py -v` (after Task 17).

### Task 17: UPDATE `.../fourteen_crash_signals_daily_check/tests/test_credit_spread.py` — watch tier tests

- **IMPLEMENT**: Add tests: (a) `data["watch"] is True` and detail contains `"WATCH"` when
  latest value is 3.2–3.49 and streak is short, (b) `data["watch"] is False` when latest
  value is below 3.2, (c) existing flag-path tests (lines 44-62) still pass unmodified —
  confirm `verdict="flag"` results don't also carry a `"watch"` key expectation (they don't
  need one; `watch` is only computed in the `"ok"` branch).
- **VALIDATE**: `uv run --directory investments/fourteen-crash-signals-daily-check python -m
  pytest fourteen_crash_signals_daily_check/tests/test_credit_spread.py -v`

### Task 18: UPDATE `.../fourteen_crash_signals_daily_check/alerts.py` — daily streak alert

- **IMPLEMENT**: Add a new function alongside `maybe_notify`:
  ```python
  def notify_credit_spread_streak_daily(result) -> None:
      """Deliberate exception to this module's transition-only alert rule above -- Shaun
      explicitly asked for a daily 'day N and counting' WhatsApp ping while Marker 14's
      streak continues, not just once on first firing (2026-08-18, Phase 2 handoff). Does
      not touch db.upsert_signal_state -- main.py still calls that separately for
      credit_spread_streak, for state-tracking/report consistency; this function's firing
      decision is independent of that transition gate."""
      if result.verdict != "flag":
          return
      streak_days = result.data.get("streak_days", "?")

      import sys
      from pathlib import Path

      _scripts_dir = Path(__file__).resolve().parent.parent.parent.parent / ".claude" / "scripts"
      sys.path.insert(0, str(_scripts_dir))
      from notifications import send_whatsapp_notification

      send_whatsapp_notification(
          f"14 Crash Signals: credit spread streak, day {streak_days} and counting -- {result.detail}"
      )
  ```
- **PATTERN**: `alerts.py:26-31`'s exact lazy-import-of-notifications shape (the same
  `sys.path.insert` dance `maybe_notify` already does).
- **GOTCHA**: This function takes a single `CheckResult`, not the `list[dict]` shape
  `maybe_notify` takes — different signature, deliberately, since it's called separately in
  `main.py` (Task 22) rather than folded into the generic `alert_inputs` list.
- **VALIDATE**: `uv run --directory investments/fourteen-crash-signals-daily-check python -m
  pytest fourteen_crash_signals_daily_check/tests/test_alerts.py -v` (after Task 19).

### Task 19: UPDATE `.../fourteen_crash_signals_daily_check/tests/test_alerts.py` — daily streak alert tests

- **IMPLEMENT**: Monkeypatch `notifications.send_whatsapp_notification` the same way the
  existing `maybe_notify` tests already do. Tests: (a) sends every call while `verdict="flag"`
  (call it twice in a row with the same result — confirm it sends both times, unlike
  `maybe_notify`'s transition-gating), (b) does not send when `verdict="ok"`, (c) message text
  contains the `streak_days` value.
- **VALIDATE**: `uv run --directory investments/fourteen-crash-signals-daily-check python -m
  pytest fourteen_crash_signals_daily_check/tests/test_alerts.py -v`

### Task 20: UPDATE `.../fourteen_crash_signals_daily_check/report.py` — wire real rows

- **IMPLEMENT**: Remove `2`, `4`, `9`, `12` from `_PLACEHOLDER_MARKERS`. Change
  `render_signals_report`'s signature to accept the 4 new result lists/objects
  (`lease_commitment_results: list[Any]`, `capex_cashflow_results: list[Any]`,
  `super_bowl_result: Any`, `credit_spread_issuer_results: list[Any]`), and extend
  `marker_rows` construction to render one row per ticker for markers 2, 4, 12 (mirroring the
  existing `insider_trend_results` loop at lines 63-67) and one row for marker 9 (a single
  `CheckResult`, mirroring markers 5/10/14 at lines 59-61). For marker 14's row, append
  `" (WATCH)"` to the detail when `credit_spread_result.data.get("watch")` is true and
  verdict is still `"ok"`.
- **PATTERN**: Lines 58-67 of the current file for both the single-`CheckResult` row shape
  and the `list[CheckResult]`-per-ticker row shape.
- **GOTCHA**: `write_signals_report`'s `*args, **kwargs` passthrough (line 79-80) means
  `main.py`'s call site (Task 22) must be updated in lockstep with this signature change —
  they're not independently validatable via this file's own tests alone.
- **VALIDATE**: `uv run --directory investments/fourteen-crash-signals-daily-check python -m
  pytest fourteen_crash_signals_daily_check/tests/test_report.py -v` (after Task 21).

### Task 21: UPDATE `.../fourteen_crash_signals_daily_check/tests/test_report.py`

- **IMPLEMENT**: Update every existing call to `render_signals_report`/`write_signals_report`
  to pass the 4 new arguments. Add assertions that markers 2/4/9/12 render real rows (not the
  `_NOT_YET_AUTOMATED` placeholder text) and that markers still-pending (1, 3, 6, 7, 11, 13)
  still render the placeholder. Add a test confirming the `(WATCH)` suffix appears on
  marker 14's row when `data={"watch": True}` is passed.
- **VALIDATE**: `uv run --directory investments/fourteen-crash-signals-daily-check python -m
  pytest fourteen_crash_signals_daily_check/tests/test_report.py -v`

### Task 22: UPDATE `.../fourteen_crash_signals_daily_check/main.py` — wire everything

- **IMPLEMENT**: In `cmd_daily_check`, after the existing 4 checks, add:
  ```python
  from . import capex_cashflow, credit_spread_issuer, lease_commitment, super_bowl

  lease_commitment_results = lease_commitment.check_lease_commitments(conn, hot_watchlist)
  capex_cashflow_results = capex_cashflow.check_capex_cashflow(hot_watchlist)
  super_bowl_result = super_bowl.check_super_bowl_signal()
  credit_spread_issuer_results = credit_spread_issuer.check_credit_spread_issuer(conn, hot_watchlist)
  ```
  Pass all 4 into `report.write_signals_report(...)` per Task 20's new signature. Extend
  `alert_inputs` with per-ticker entries for `lease_commitments:{ticker}`,
  `capex_cashflow:{ticker}`, `credit_spread_issuer:{ticker}` (mirroring the existing
  `insider_trend:{ticker}` entry), plus one entry for `super_bowl_signal` (marker_key
  `"super_bowl_signal"`, `is_firing=super_bowl_result.verdict == "flag"`). After the existing
  `maybe_notify(conn, alert_inputs)` call, add:
  ```python
  db.upsert_signal_state(
      conn, marker_key="credit_spread_streak",
      is_firing=credit_spread_result.verdict == "flag", detail=credit_spread_result.detail,
  )
  alerts.notify_credit_spread_streak_daily(credit_spread_result)
  ```
  (Note: `credit_spread_streak` is deliberately excluded from the generic `alert_inputs` list
  — it never went through `maybe_notify`'s transition gate before this task either, since
  Phase 1 already didn't include it there; confirm this against the current file before
  assuming, and if Phase 1's `alert_inputs` did include it, remove that entry as part of this
  task so it isn't double-alerted.)

  Also add a new CLI subcommand for the manual bond-yield fallback:
  ```python
  def cmd_record_bond_yield(args) -> None:
      conn = _open_conn()
      from . import db
      db.set_manual_bond_yield(conn, ticker=args.ticker.upper(), cusip=args.cusip, yield_pct=args.yield_pct)
      conn.close()
      print(f"Recorded manual bond yield for {args.ticker.upper()}: {args.yield_pct}%")
  ```
  wired into `main()`'s `subparsers` with `ticker`, `--cusip` (optional), `yield_pct`
  positional float arguments.
- **PATTERN**: `main.py`'s existing `cmd_daily_check` orchestration order and `alert_inputs`
  list-building loop (lines 46-50, the `insider_trend_results` loop) for the per-ticker
  alert-entry shape.
- **GOTCHA**: Check the current (Phase-1-shipped) `alert_inputs` list before editing — this
  plan was written assuming `credit_spread_streak` is NOT in it (Phase 1's `main.py` as read
  during planning only includes `margin_debt_growth`, `market_cap_milestone:...`, and
  `insider_trend:{ticker}` entries; `credit_spread_streak`'s state is not currently upserted
  by `main.py` at all — Task 22 adds that upsert call for the first time, for report/state
  consistency, deliberately routed around `maybe_notify`).
- **VALIDATE**: `uv run --directory investments/fourteen-crash-signals-daily-check python -m
  fourteen_crash_signals_daily_check.main daily-check` (live run — confirm
  `signals-report.md` renders all 4 new markers with real data, not tracebacks, and that the
  process exits 0).

### Task 23: UPDATE `investments/TOOLS.md`

- **IMPLEMENT**: Update line 20's Fourteen Crash Signals row description from "Tracks 4 of
  the 14 crash-warning markers..." to "Tracks 8 of the 14 crash-warning markers (credit
  spread streak + watch tier, margin debt YoY, insider selling trend, market-cap milestone,
  off-balance-sheet leases, capex-vs-cash-flow, Super Bowl ad-share reminder, credit spread
  divergence)..." — keep the rest of the row (deployment target, cadence) unchanged. Add a
  one-line mention that Marker #12's yield lookup may be semi-manual (`record-bond-yield`
  subcommand) depending on what Task 14's spike found.
- **VALIDATE**: Manual read-through — confirm the row accurately reflects what actually
  shipped (especially Marker #12's live-vs-manual yield status, which depends on Task 14's
  spike outcome).

---

## TESTING STRATEGY

### Unit Tests

Every new/modified function gets monkeypatch-isolated tests following this package's
existing convention (`test_credit_spread.py` is the canonical example) — no test hits a real
network endpoint or a real LLM call. `db_conn`/`_isolate_signals_report_path` fixtures from
`conftest.py` are reused unchanged; no new fixtures needed beyond a `cashflow=` extension to
`mytrader/tests/test_market_data.py`'s existing fake-yfinance helper.

### Integration Tests

None beyond the existing `test_report.py`/`test_alerts.py` wiring tests — this package has no
end-to-end integration test suite beyond unit tests plus the manual `daily-check` run
(Task 22's VALIDATE step and Level 4 below).

### Edge Cases

- Ticker with no CIK resolvable at all (delisted, foreign-only listing) — markers #2 and #12
  must silently skip it, not error.
- Ticker whose filing index has no matching form type at all — same silent skip.
- First-ever observation for any per-ticker growth/divergence check (#2, #12) — must never
  flag on a baseline reading with nothing to compare against.
- `FRED_API_KEY` unset — `credit_spread_issuer.py`'s Treasury lookup and `credit_spread.py`'s
  existing streak check both already degrade to `"unknown"`; confirm this still holds after
  Task 16's edit.
- Empty hot watchlist (no rising sectors this run) — all 4 new per-ticker check functions
  must return `[]`, not raise, mirroring `market_cap_milestone.py`'s existing
  `verdict="unknown"` handling for this case (note: the 3 new per-ticker functions return
  `[]` rather than a single `"unknown"` result for an empty watchlist, since they're
  list-returning like `insider_trend.py`, not single-result like `market_cap_milestone.py` —
  confirm `report.py`'s Task 20 rendering handles an empty list gracefully for each,
  mirroring the existing `insider_trend_results` empty-list branch at `report.py:66-67`).

---

## VALIDATION COMMANDS

### Level 1: Syntax & Style

```powershell
uv run --directory investments/fourteen-crash-signals-daily-check ruff check fourteen_crash_signals_daily_check
uv run --directory investments/my-trader ruff check mytrader/sec_filings.py mytrader/market_data.py
```

### Level 2: Unit Tests

```powershell
uv run --directory investments/fourteen-crash-signals-daily-check python -m pytest fourteen_crash_signals_daily_check/tests -v
uv run --directory investments/my-trader python -m pytest mytrader/tests/test_sec_filings.py mytrader/tests/test_market_data.py -v
```

### Level 3: Integration Tests

```powershell
uv run --directory investments/my-trader python -m pytest mytrader -v
uv run --directory investments/goat python -m pytest goat -v
```
(Full regression on both sibling packages this phase's renames could ripple into —
`sec_filings.py` is also imported by `mytrader/checks/principles_fit.py`.)

### Level 4: Manual Validation

```powershell
uv run --directory investments/fourteen-crash-signals-daily-check python -m fourteen_crash_signals_daily_check.main daily-check
```
Then read `investments/fourteen-crash-signals-daily-check/signals-report.md` — confirm
markers 2, 4, 9, 12 show real data (or an honest `"unknown"`/skip, never a traceback), and
that markers 1, 3, 6, 7, 11, 13 still show the placeholder text.

### Level 5: Additional Validation

```powershell
uv run --directory investments/my-trader python -c "import yfinance; print(yfinance.Ticker('ORCL').cashflow.index.tolist())"
```
Run this before trusting Task 6's row-label strings (per that task's own GOTCHA).

---

## ACCEPTANCE CRITERIA

- [ ] `sec_filings.py`'s 5 renamed functions (`get_cik`, `fetch_filing_index`,
      `fetch_filing_document`, `strip_html`, `latest_filing_entry`) are public, and every
      existing caller (`get_filing_summaries_for_ticker`, its test file) still passes.
- [ ] `_extract_10k_sections`/`_extract_10q_sections` now capture `financial_statements`.
- [ ] Markers #2, #4, #9, #12 each produce real `CheckResult`(s) in `signals-report.md`,
      replacing their `_NOT_YET_AUTOMATED` placeholder rows.
- [ ] Marker #2 never flags on a ticker's first-ever observation; flags only on ≥50% QoQ
      growth against a stored prior figure.
- [ ] Marker #4 flags only when Free Cash Flow is negative AND |Capital Expenditure| ≥ $10B.
- [ ] Marker #9 correctly counts down before the Super Bowl date and flips to a manual-check
      flag on/after it.
- [ ] Marker #12's CUSIP discovery works against at least one real ticker with a public
      EDGAR-registered bond (manually confirmed, not just unit-tested).
- [ ] Marker #12's yield lookup either has a working live scrape (if Task 14's spike found
      one) or correctly falls back to `db.get_manual_bond_yield` / the `record-bond-yield`
      CLI subcommand, and clearly says which mode it's in via the report detail text.
- [ ] Marker #14's report row shows a `(WATCH)` indicator when the spread is 3.2–3.49% and
      not yet flagging; the daily "day N and counting" WhatsApp alert fires on every run
      while the streak is active, not just once.
- [ ] All validation commands (Levels 1-4) pass with zero errors.
- [ ] `investments/TOOLS.md` accurately reflects the new marker count and Marker #12's actual
      (live vs. manual) yield-lookup mode.
- [ ] No regressions in `mytrader`'s or `goat`'s existing test suites.

---

## COMPLETION CHECKLIST

- [ ] All 23 tasks completed in order.
- [ ] Each task's own `VALIDATE` command passed immediately after that task.
- [ ] Full test suite passes across all 3 packages (`fourteen-crash-signals-daily-check`,
      `my-trader`, `goat`).
- [ ] No `ruff`/lint errors in any modified or new file.
- [ ] Manual `daily-check` run confirms the report renders correctly end-to-end.
- [ ] Acceptance criteria all met.
- [ ] `investments/TOOLS.md` updated.

---

## NOTES

- **Marker #12 is genuinely the riskiest task in this plan** — the CUSIP-discovery half
  (Task 14's `_resolve_cusip`) is fully deterministic and specified, but the yield-lookup
  half (`_fetch_bond_yield_live`) cannot be pre-specified with confidence; it depends on a
  live-verification spike against 4 unconfirmed third-party sites, per the handoff's own
  explicit framing. Budget real time for this spike, and treat "none of the 4 pan out,
  ship the manual-entry fallback" as a fully acceptable outcome, not a failure to route
  around.
- **`SIGNALS_BOND_CUSIP_REFRESH_DAYS` and per-bond Treasury-maturity-matching are both
  defined/discussed but deliberately not fully wired in this v1** — see Task 14's GOTCHAs.
  Both are reasonable Phase 3+ follow-ups, not omissions to silently fix now.
- **Marker #9's `verdict="unknown"` for most of the year is a deliberate semantic
  deviation** from this package's usual "unknown = fetch failed" meaning — see Task 10's
  GOTCHA. Don't let a later marker's alert-wiring assume "unknown never means anything
  actionable" without checking this one specifically.
- **Why 4 markers + 1 enhancement in one plan, not split further**: the source handoff
  itself frames all four markers as one coherent Phase 2 slice (all reuse the same
  hot-watchlist input or need none; all reuse `sec_filings.py` or `market_data.py`'s
  existing patterns) and is explicitly marked "ready for `/plan-feature`" as a whole. The
  task ordering above (simplest markers first) still allows shipping incrementally within
  this plan if time runs short — Tasks 1-11 (sec_filings renames, config/db, Markers #4 and
  #9) are fully self-contained and independently valuable even if Tasks 12-19 (Markers #2,
  #12, and the Marker #14 enhancement) slip to a follow-up session.
- **Markers #1, #3, #6, #7, #11, #13 remain out of scope** — Phase 1's own Phase 3 framing
  (source-hunting for markers with no confirmed free data source) still applies unchanged.
