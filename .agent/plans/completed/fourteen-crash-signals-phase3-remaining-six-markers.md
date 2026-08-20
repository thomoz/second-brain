# Feature: Fourteen Crash Signals Daily Check — Phase 3 (Markers #1, #3, #6, #7, #11, #13)

The following plan should be complete, but it's important to validate documentation and
codebase patterns and task sanity before implementing. Pay special attention to naming of
existing utils/types/models. Import from the right files.

**Source**: `investments/my-trader/14-signals-crash-warning-phase3-handoff.md` — marked
"ready for `/plan-feature`" (2026-08-18). **Prerequisite context**: the shipped Phase 1
(`.agent/plans/fourteen-crash-signals-phase1-core-signals.md`) and Phase 2
(`.agent/plans/fourteen-crash-signals-phase2-markers-2-4-9-12.md`) plans — this plan mirrors
their file layout, config/DB/test conventions exactly and does not re-explain them.

**Live-verification note**: every EDGAR/RSS/CBOE claim below was re-confirmed with real HTTP
requests during this planning session (2026-08-18), on top of the handoff's own research —
not taken on the handoff's word alone. Three findings materially improve on the handoff:

1. **Marker #7 (CBOE put/call ratio) is now fully buildable, not a spike/stub.** The handoff
   left this as "needs a live spike before committing" because the page looked HTML-table-only.
   It isn't — the page embeds a machine-readable JSON blob (`"ratios":[{"name":"EQUITY
   PUT/CALL RATIO","value":"0.65"}, ...]`) inside a Next.js `self.__next_f.push(...)` script
   tag, extractable with a single targeted regex (confirmed live, see Task 12). No fragile
   HTML-table scraping needed.
2. **A real, previously-undocumented footgun in EDGAR's full-text search API**: passing an
   empty `q` parameter (`q=""`) silently returns an inflated, wrong count (1661 vs the
   correct 181 for an identical query) — omitting `q` entirely is required. Also: the `ciks`
   parameter silently returns 0 hits (not an error) if the CIK isn't zero-padded to 10 digits.
   Both confirmed live this session (see Task 1's `edgar_fulltext_search_count` docstring).
3. **Markers #1 and #6 need zero new DB tables**, a deliberate simplification vs. the
   handoff's own cross-cutting notes (which proposed a filing-count-history table for each).
   EDGAR's full-text search API accepts arbitrary historical `startdt`/`enddt` ranges on
   every call (confirmed live), so both markers can compute "current window vs. baseline
   window" with two live queries per run instead of accumulating local history — the same
   zero-state philosophy `credit_spread.py` already uses for FRED-backed Marker #14. Only
   Markers #7 and #11 need new tables (see NOTES for the full per-marker rationale).

## Feature Description

Phases 1–2 shipped 8 of the 14 crash-warning markers with real data (2, 4, 5, 8, 9, 10, 12,
14) plus the shared hot-company watchlist layer; the remaining 6 render as
`"Not yet automated"` placeholder rows in `report.py`. This phase replaces all 6 remaining
placeholders with real `CheckResult`-shaped checks, which — once this phase ships — retires
`report.py`'s `_PLACEHOLDER_MARKERS` mechanism entirely: all 14 markers become real:

- **#1 Record debt issuance (hot sector)** — per-issuer, EDGAR full-text search count of
  424B2/424B5/FWP filings, trailing 180 days vs. the same issuer's own trailing-2-year
  average rate, flagged at ≥2x.
- **#3 Seller finances buyer (vendor/circular financing)** — no free structured source
  exists (confirmed, not just assumed — EDGAR phrase search is too noisy to isolate this
  deal shape). Ships as a permanent `verdict="unknown"` maintained flag naming the
  hot-watchlist tickers to news-scan manually, the same honest-gap shape as Marker #9's
  original scope before this phase (Marker #9 itself is unaffected — already shipped).
- **#6 Record IPO/equity issuance** — market-wide (no watchlist dependency), EDGAR
  full-text search count of S-1 (intent-to-register) and 424B4 (priced IPO, a cleaner
  sub-signal) filings, current 30-day window vs. the same calendar window one year prior
  (a direct YoY comparison, mirroring `mytrader/margin_debt.py`'s own YoY shape).
- **#7 Retail piles into leverage** — CBOE daily options market-statistics page, equity
  put/call ratio extracted from an embedded JSON blob (not the fund-flow data the source
  video described — a **different mechanism**, flagged for Shaun's explicit sign-off before
  landing in `main.py`'s daily run, see NOTES). Flags when today's ratio drops well below
  its own accumulating trailing average (z-score-based, needs a short bootstrap period).
- **#11 Regulators sound the alarm** — daily poll of 3 RSS feeds (SEC press releases, Fed
  press releases, Fed speeches), keyword-scan against a trigger-phrase list, one
  `CheckResult` per newly-seen matching item (title/description-only, a documented
  scoped-down v1 — see NOTES).
- **#13 Funding markets start choking** — FRED-backed, zero new DB state (mirrors
  `credit_spread.py`'s own pattern): primary signal is the 3-Month AA Nonfinancial
  Commercial Paper Rate minus the 3-Month Treasury Bill rate (`DCPN3M - DTB3`), a direct
  funding-stress spread, flagged on a z-score vs. its own trailing year; STLFSI4/NFCI (two
  independent broad financial-stress indices) as secondary corroborating flags.

## User Story

As Shaun (multi-business founder managing his own portfolio)
I want the remaining 6 of the 14 crash-warning markers automated with real, live-verified
data sources (or an honest "no source exists" flag where that's genuinely the case), wired
into the existing daily report/alert
So that the full 14-signal framework is either real signal or an honestly-labeled manual
flag — no marker pretends to be more automated than it is, and none silently gets skipped.

## Problem Statement

Phase 1's own scope decision deferred these 6 markers because none had a confirmed
free/structured data source at the time. The Phase 3 handoff did that research (live-tested
every candidate source, not just documentation) and resolved 5 of the 6 with a genuine
source; the 6th (#3) resolved to an honest "no automatable source exists" verdict, the same
shape Marker #9 already uses successfully in this codebase.

## Solution Statement

Six new marker-check modules. Two reuse a new shared EDGAR full-text-search helper added to
`mytrader/sec_filings.py` (Markers #1, #6). One reuses `scripts.macro.fred_series_range`
with zero new fetch code, same as `credit_spread.py` (Marker #13). One is a pure
requests+regex scrape against a newly-discovered JSON-in-script-tag source (Marker #7). One
is a pure stdlib `xml.etree.ElementTree` RSS poll, no new dependency (Marker #11). One is a
static "no source" flag with no fetch logic at all (Marker #3). Only Markers #7 and #11 need
new DB tables (both need to accumulate their own history/dedup state — CBOE and RSS feeds
don't expose queryable historical data the way EDGAR/FRED do). `report.py` drops
`_PLACEHOLDER_MARKERS` entirely and gains 6 new render branches. `main.py` orchestrates the
6 new checks and extends `alert_inputs` for the 5 markers capable of ever firing (not #3,
which is permanently `unknown`). No new systemd timer/service — extends the same
`daily-check` command the deployed `second-brain-fourteen-signals.timer` already runs.

## Feature Metadata

**Feature Type**: Enhancement (extends an already-shipped package; final phase of this
package's original 14-marker scope)
**Estimated Complexity**: High — 6 independent new marker modules, one new cross-package
shared helper, 2 new DB tables, and one component (#7) that landed with a **materially
better data source than the handoff itself found**, discovered during this planning
session — worth Shaun re-confirming the recommendation still holds before it ships live.
**Primary Systems Affected**: `investments/fourteen-crash-signals-daily-check/` (all
modules), `investments/my-trader/mytrader/sec_filings.py`, `investments/TOOLS.md`.
**Dependencies**: `requests` (already a direct dep), stdlib `xml.etree.ElementTree` and
`statistics` (no new dependency declarations needed for RSS parsing or z-score math).

---

## CONTEXT REFERENCES

### Relevant Codebase Files — READ THESE BEFORE IMPLEMENTING

- `investments/my-trader/14-signals-crash-warning-phase3-handoff.md` (whole file) — the
  authoritative source for every marker's fact-check and feasibility research. This plan's
  NOTES section documents where it improves on the handoff (esp. Marker #7); don't
  re-litigate a decision already made in the handoff without a documented reason.
- `.agent/plans/fourteen-crash-signals-phase2-markers-2-4-9-12.md` (whole file) — the
  immediately-prior phase's plan. Every pattern this plan uses (config constant style, DB
  upsert shape, `CheckResult` list-vs-single shape, cross-package import style, test
  monkeypatch style, alert-input wiring) is established there; this plan does not repeat
  the explanation, only the application.
- `investments/fourteen-crash-signals-daily-check/fourteen_crash_signals_daily_check/config.py`
  (whole file, 91 lines as of this plan) — append new constants at the end, same
  `SIGNALS_*`-prefixed, "why this number" trailing-comment style as every existing block.
- `.../db.py` (whole file, 181 lines) — `init_signals_tables`'s `executescript` block and
  the `upsert_signal_state`/`record_issuer_spread`/`get_issuer_spread_near` functions —
  mirror this exact `INSERT ... ON CONFLICT DO UPDATE` + `with conn:` shape for the 2 new
  tables this phase adds.
- `.../watchlist.py` (whole file) — `get_or_refresh_hot_watchlist(conn)`, the shared input
  Marker #1 reads from (Markers #3, #6, #7, #11, #13 do NOT use the watchlist — #3
  references it only for its report text, #6/#7/#11/#13 are market-wide/broad-market
  checks with no per-issuer shape at all).
- `.../credit_spread.py` (whole file, 60 lines) — the exact "recompute entirely from a live
  FRED history fetch every run, zero local DB state" pattern Marker #13 mirrors precisely.
  Also the best example in this package of a z-score-adjacent threshold-with-watch-tier
  shape (though Marker #13 doesn't need a watch tier itself).
- `.../credit_spread_issuer.py` (whole file, 194 lines) — Phase 2's own precedent for "one
  sub-problem confirmed live via a documented spike test, one left genuinely open with a
  manual fallback" (`_fetch_bond_yield_live`'s docstring). Marker #7 in this phase is what
  that spike *would* have looked like if it had succeeded — read this file to see the shape
  a resolved spike replaces.
- `.../insider_trend.py` (whole file) — best existing example of "return `list[CheckResult]`,
  skip entries with nothing to report, degrade to an explicit `[]`-is-valid empty state" —
  Marker #1 (per-ticker) and Marker #11 (per-matched-item) both follow this shape.
- `.../super_bowl.py` (whole file) — the closest existing precedent for Marker #3: a
  `CheckResult` with **no fetch logic at all**, a documented "this is deliberately
  `unknown`, not a fetch failure" GOTCHA, and a module docstring explaining why no automation
  is possible. Marker #3 follows this file's shape almost exactly, minus the date logic.
- `.../lease_commitment.py` (whole file) — per-issuer `list[CheckResult]` shape reading
  `sec_filings` functions directly (the shape Marker #1 also follows, one level simpler
  since #1 needs only a count, not a document fetch + LLM summarization).
- `.../margin_debt.py` (whole file) — the existing YoY-comparison-with-tolerance shape
  Marker #6 mirrors (`_find_prior_year_row`'s "same calendar window, one year earlier"
  logic) — Marker #6 needs the same comparison shape but against a live EDGAR query instead
  of a cached spreadsheet row.
- `.../alerts.py` (whole file, 62 lines) — `maybe_notify`'s generic
  `{"marker_key", "is_firing", "detail"}` input shape — reused as-is, no changes needed to
  this file in this phase (unlike Phase 2, which added a Marker-14-specific daily-repeat
  alert function here).
- `.../report.py` (whole file, 101 lines) — `_PLACEHOLDER_MARKERS` (currently markers 1, 3,
  6, 7, 11, 13 — all six removed by this phase) and `render_signals_report`'s row-assembly
  shape (single-`CheckResult` markers render one row directly; `list[CheckResult]` markers
  render one row per item with an explicit "no results this run" fallback row).
- `.../main.py` (whole file, 132 lines) — `cmd_daily_check`'s orchestration order,
  `alert_inputs` list-building shape, and `_open_conn`'s init-tables sequence.
- `.../tests/conftest.py` (whole file) — `db_conn` fixture (in-memory-per-test sqlite,
  `init_signals_tables` called) and the autouse `_isolate_signals_report_path` fixture.
- `.../tests/test_credit_spread_issuer.py` (whole file) — the closest existing test-style
  precedent for the multi-source-fallback markers in this phase (#7's bootstrap-then-flag
  shape, #11's dedup-then-flag shape): monkeypatch each fetch function independently,
  assert on `verdict`/`detail`/`data`.
- `investments/my-trader/mytrader/sec_filings.py` (whole file, 323 lines) — this plan adds
  ONE new public function (`edgar_fulltext_search_count`) to this file; read the existing
  `_HEADERS`/`fetch_filing_index`/`get_cik` functions immediately above it (lines 76-121)
  to match the exact try/except/return-None shape and `_HEADERS` reuse.
- `investments/my-trader/mytrader/tests/test_sec_filings.py` (whole file) — note this file
  has **no existing direct-`requests.get`-mocking test** (every existing test monkeypatches
  at a higher level, e.g. `_fetch_cik_map_bulk`, `fetch_filing_document`) — Task 2's new
  tests are the first in this file to mock `requests.get` itself; write a small local fake
  response object, there is nothing existing to mirror for this specific case.
- `investments/briefs-finance/scripts/macro.py` lines 68-105 (`fred_series_range`,
  `fred_value_on`) — `fred_series_range` is what Marker #13 uses (whole-history fetch, same
  as `credit_spread.py` already imports); confirms the exact `list[tuple[date, float]] | None`
  return shape this plan's z-score code consumes.
- `investments/my-trader/mytrader/config.py` lines 208-221 (`SEC_USER_AGENT`,
  `SEC_CIK_MAP_URL`, `SEC_SUBMISSIONS_URL_TEMPLATE`, `SEC_ARCHIVES_URL_TEMPLATE`,
  `SEC_CIK_MAP_REFRESH_DAYS`, `SEC_FILING_TYPES`, `SEC_REQUEST_DELAY_SECONDS`) — no changes
  needed here, referenced only so the new `edgar_fulltext_search_count` function's
  `_HEADERS` reuse (built from `SEC_USER_AGENT`) is traceable.
- `investments/fourteen-crash-signals-daily-check/pyproject.toml` (whole file) — confirms no
  new dependency declarations are needed this phase (RSS parsing uses stdlib
  `xml.etree.ElementTree`, z-score math uses stdlib `statistics`, CBOE scraping reuses
  `requests` which is already a direct dep).
- `investments/TOOLS.md` (the Fourteen Crash Signals rows, currently lines ~20/41-42) — no
  new CLI subcommand needed this phase (unlike Phase 2's `record-bond-yield`), but the
  "Fourteen Crash Signals" row's own description should be updated once all 14 markers are
  real (currently describes it as a partial build).

### New Files to Create

- `.../fourteen_crash_signals_daily_check/debt_issuance.py` — Marker #1 check.
- `.../fourteen_crash_signals_daily_check/seller_financing.py` — Marker #3 check.
- `.../fourteen_crash_signals_daily_check/ipo_issuance.py` — Marker #6 check.
- `.../fourteen_crash_signals_daily_check/retail_leverage.py` — Marker #7 check.
- `.../fourteen_crash_signals_daily_check/regulator_alarm.py` — Marker #11 check.
- `.../fourteen_crash_signals_daily_check/funding_stress.py` — Marker #13 check.
- `.../fourteen_crash_signals_daily_check/tests/test_debt_issuance.py`
- `.../fourteen_crash_signals_daily_check/tests/test_seller_financing.py`
- `.../fourteen_crash_signals_daily_check/tests/test_ipo_issuance.py`
- `.../fourteen_crash_signals_daily_check/tests/test_retail_leverage.py`
- `.../fourteen_crash_signals_daily_check/tests/test_regulator_alarm.py`
- `.../fourteen_crash_signals_daily_check/tests/test_funding_stress.py`

### Patterns to Follow

**Naming conventions**: `SIGNALS_*` prefix for every new config constant, each with a
trailing "why this number" comment. Module-level check functions named `check_<marker_name>`;
per-item helpers prefixed `_`.

**Error handling**: Never raise from a check function. Every external `requests` call wrapped
in `try/except Exception: return None`. A marker with nothing to report degrades to either
`verdict="unknown"` (source genuinely unreachable, or — Marker #3's deliberate case — nothing
is automatable at all) or a silently-skipped item within a `list[CheckResult]`.

**DB pattern**: `INSERT ... ON CONFLICT(...) DO UPDATE` upserts wrapped in `with conn:` for
both new tables (see `db.py`'s `record_issuer_spread`), never a separate
`SELECT`-then-`INSERT`-or-`UPDATE` branch.

**Cross-package imports**: `from mytrader import sec_filings` / `from mytrader.checks import
CheckResult` / `from scripts.macro import fred_series_range` — the exact shape every existing
module in this package already uses.

**Testing pattern**: `monkeypatch.setattr("fourteen_crash_signals_daily_check.<module>.<fn>",
...)` (module-path string form, or direct attribute form via the imported module object — see
`test_credit_spread_issuer.py` for the direct-object form this plan's tests should match) for
functions called via `from X import Y` inside the module under test; `db_conn` fixture from
`conftest.py` for any test touching the database.

---

## IMPLEMENTATION PLAN

### Phase 1: Foundation — shared EDGAR helper + config/schema

Add `edgar_fulltext_search_count` to `sec_filings.py` (needed by Markers #1 and #6), and add
every new config constant + the 2 new DB tables (Markers #7, #11 only) this phase's markers
need.

### Phase 2: Core Implementation — 6 markers, simplest/most-confirmed first

Build in this order, each validated live before moving to the next: `funding_stress.py`
(#13, zero new state, reuses `fred_series_range` verbatim) → `seller_financing.py` (#3, no
fetch logic at all) → `debt_issuance.py` (#1, one new helper, per-issuer) → `ipo_issuance.py`
(#6, same new helper, market-wide) → `retail_leverage.py` (#7, new scrape + new DB table) →
`regulator_alarm.py` (#11, new RSS parsing + new DB table, the most novel one).

### Phase 3: Integration — report/alert/CLI wiring

Wire all 6 new markers into `report.py` (retiring `_PLACEHOLDER_MARKERS` entirely — after
this phase, every one of the 14 markers renders real data or an honest permanent-`unknown`
flag) and `main.py` (calling the checks, feeding `alert_inputs` for the 5 markers capable of
firing). Update `investments/TOOLS.md`.

### Phase 4: Testing & Validation

Unit tests for every new function, full-suite regression run, and a manual `daily-check` run
against real external sources to confirm the report renders all 14 markers correctly
end-to-end.

---

## STEP-BY-STEP TASKS

IMPORTANT: Execute every task in order, top to bottom. Each task is atomic and independently
testable.

### Task 1: UPDATE `investments/my-trader/mytrader/sec_filings.py` — add `edgar_fulltext_search_count`

- **IMPLEMENT**: Add after `fetch_filing_document` (currently ends at line 120), before the
  `# --- Section extraction ---` comment:
  ```python
  # --- Full-text search (aggregate counting, not per-filing fetch) -----------


  def edgar_fulltext_search_count(
      forms: str, *, cik: str | None = None, startdt: date | None = None, enddt: date | None = None
  ) -> int | None:
      """Count of EDGAR full-text-search hits for the given form-type(s) (comma-separated,
      e.g. "424B2,424B5,FWP"), optionally scoped to one issuer CIK and/or a filing-date
      range. Confirmed live 2026-08-18 (Phase 3 planning session, real requests against
      efts.sec.gov/LATEST/search-index):

      - GOTCHA (silent wrong answer, not an error): omit the `q` (search-text) parameter
        entirely. Passing q="" returns an inflated, wrong total (1661 vs the correct 181
        for an identical S-1/30-day query) -- confirmed by testing both forms side by side.
        Do not add a `q` param to this function.
      - GOTCHA (also silent, also confirmed): `cik` must be the 10-digit zero-padded form
        (e.g. "0001341439"), not the raw digits sec_filings.get_cik() returns (e.g.
        "1341439") -- the unpadded form returns hits.total.value == 0 with a 200 status,
        not an error. This function pads internally so callers can pass get_cik()'s output
        straight through without remembering to pad it themselves.
      - Response shape confirmed live: {"hits": {"total": {"value": <int>, "relation":
        "eq"}, "hits": [...]}}. This function returns only hits.total.value -- callers
        needing individual filing entries should use fetch_filing_index/latest_filing_entry
        instead (this is for aggregate counting, e.g. Markers #1/#6 of the Fourteen Crash
        Signals daily check).
      """
      params: dict[str, str] = {"forms": forms}
      if cik is not None:
          params["ciks"] = f"{int(cik):010d}"
      if startdt is not None:
          params["startdt"] = startdt.isoformat()
      if enddt is not None:
          params["enddt"] = enddt.isoformat()
      try:
          r = requests.get(
              "https://efts.sec.gov/LATEST/search-index", params=params, headers=_HEADERS, timeout=20
          )
          if r.status_code != 200:
              return None
          return r.json()["hits"]["total"]["value"]
      except Exception:
          return None
  ```
  Add `from datetime import date, datetime, timezone` to the imports at the top of the file
  (currently only `datetime, timezone` are imported at line 26 — add `date` to that same
  import line).
- **PATTERN**: `fetch_filing_index` (lines 83-91) for the exact `_HEADERS`/try-except/
  status-code-check shape.
- **VALIDATE**: `uv run --directory investments/my-trader python -c "from datetime import
  date, timedelta; from mytrader import sec_filings; n =
  sec_filings.edgar_fulltext_search_count('424B2,424B5,FWP', cik='1341439',
  startdt=date.today()-timedelta(days=180), enddt=date.today()); print('count:', n); assert
  isinstance(n, int)"` (live network call against real ORCL data — confirm it returns an int,
  not None, before moving on).

### Task 2: CREATE tests for `edgar_fulltext_search_count` in `investments/my-trader/mytrader/tests/test_sec_filings.py`

- **IMPLEMENT**: This file has no existing direct-`requests.get`-mocking test to mirror —
  write a small local fake response class:
  ```python
  class _FakeSearchResponse:
      def __init__(self, status_code: int, payload: dict | None = None):
          self.status_code = status_code
          self._payload = payload or {}

      def json(self):
          return self._payload


  def test_edgar_fulltext_search_count_returns_total_value(monkeypatch):
      def _fake_get(url, params=None, headers=None, timeout=None):
          assert "q" not in params  # GOTCHA regression -- q must never be sent
          assert params["ciks"] == "0001341439"  # zero-padded from raw "1341439"
          return _FakeSearchResponse(200, {"hits": {"total": {"value": 42, "relation": "eq"}}})

      monkeypatch.setattr(sec_filings.requests, "get", _fake_get)
      count = sec_filings.edgar_fulltext_search_count("424B2,424B5,FWP", cik="1341439")
      assert count == 42


  def test_edgar_fulltext_search_count_none_on_non_200(monkeypatch):
      monkeypatch.setattr(sec_filings.requests, "get", lambda *a, **k: _FakeSearchResponse(500))
      assert sec_filings.edgar_fulltext_search_count("S-1") is None


  def test_edgar_fulltext_search_count_none_on_exception(monkeypatch):
      def _raise(*a, **k):
          raise ConnectionError("boom")

      monkeypatch.setattr(sec_filings.requests, "get", _raise)
      assert sec_filings.edgar_fulltext_search_count("S-1") is None


  def test_edgar_fulltext_search_count_no_cik_param_when_omitted(monkeypatch):
      def _fake_get(url, params=None, headers=None, timeout=None):
          assert "ciks" not in params  # market-wide query, Marker #6's shape
          return _FakeSearchResponse(200, {"hits": {"total": {"value": 85, "relation": "eq"}}})

      monkeypatch.setattr(sec_filings.requests, "get", _fake_get)
      assert sec_filings.edgar_fulltext_search_count("S-1") == 85
  ```
- **PATTERN**: pytest's standard `monkeypatch.setattr(module.dependency, "get", fake_fn)`
  form, matching this file's existing `monkeypatch.setattr(sec_filings, "_fetch_cik_map_bulk",
  ...)` style but one level deeper (patching `requests.get` itself since this is the first
  function in the module tested at that level).
- **VALIDATE**: `uv run --directory investments/my-trader python -m pytest
  mytrader/tests/test_sec_filings.py -v -k edgar_fulltext`

### Task 3: UPDATE `.../fourteen_crash_signals_daily_check/config.py` — new constants for all 6 markers

- **IMPLEMENT**: Append after the existing Marker 14 watch-tier block:
  ```python
  # Marker 1 -- record debt issuance in the hot sector (per-issuer, EDGAR full-text search
  # count of debt-prospectus filings, current vs. this issuer's own historical rate).
  SIGNALS_DEBT_ISSUANCE_LOOKBACK_DAYS = 180  # trailing window being evaluated.
  SIGNALS_DEBT_ISSUANCE_BASELINE_DAYS = 730  # 2 years -- own-history baseline window,
      # queried live from EDGAR rather than accumulated locally (see this plan's NOTES).
  SIGNALS_DEBT_ISSUANCE_FLAG_RATIO = 2.0  # v1/tunable -- trailing-180d count >=2x this
      # issuer's own per-180d average rate over the trailing 2 years.

  # Marker 3 -- seller finances buyer (vendor/circular financing). No automatable source
  # exists (confirmed by live-testing EDGAR phrase search, too noisy to isolate this deal
  # shape) -- this marker is a permanent verdict="unknown" maintained flag, same shape as
  # Marker #9 before it shipped real date-logic. No config constants needed -- nothing to
  # tune, see seller_financing.py.

  # Marker 6 -- record IPO/equity issuance (market-wide, EDGAR full-text search, YoY window
  # comparison -- mirrors mytrader.margin_debt's own YoY shape).
  SIGNALS_IPO_FILING_WINDOW_DAYS = 30  # trailing window compared against the same calendar
      # window one year prior -- confirmed live 2026-08-18: S-1 filings over an identical
      # 18-day August window differ meaningfully year over year (85 in 2026 vs 145 in 2025),
      # confirming this is a real, moving signal.
  SIGNALS_IPO_FILING_FLAG_RATIO = 1.5  # v1/tunable, distinct from Marker #1's 2.0x since
      # S-1/424B4 filing volume is naturally noisier / less issuer-specific.

  # Marker 7 -- retail piles into leverage (CBOE equity put/call ratio proxy -- NOTE: this
  # measures options positioning, a DIFFERENT mechanism than the source video's ETF/fund-flow
  # framing; see this plan's NOTES for the sign-off flag before this ships live).
  SIGNALS_PUTCALL_MIN_HISTORY_DAYS = 30  # bootstrap period -- this package accumulates its
      # own daily readings (CBOE exposes no historical series), so the first ~30 days can
      # only report "accumulating baseline", never flag.
  SIGNALS_PUTCALL_FLAG_ZSCORE = -2.0  # v1/tunable -- flag when today's equity put/call ratio
      # is >=2 standard deviations BELOW its own trailing mean (unusually low put/call =
      # more speculative call-buying, the retail-leverage proxy per the handoff).

  # Marker 11 -- regulators sound the alarm (SEC + Fed press releases + Fed speeches RSS,
  # keyword-scan against titles/descriptions -- v1 scope, does not fetch/scan full linked
  # documents, see this plan's NOTES).
  SIGNALS_REGULATOR_FEED_URLS = (
      "https://www.sec.gov/news/pressreleases.rss",
      "https://www.federalreserve.gov/feeds/press_all.xml",
      "https://www.federalreserve.gov/feeds/speeches.xml",
  )  # all 3 confirmed live 2026-08-18: real, current items, valid RSS 2.0, <guid> present
     # and stable on every item across all 3 feeds (used as the dedup key).
  SIGNALS_REGULATOR_TRIGGER_PHRASES = (
      "systemic risk", "financial stability", "leverage", "asset valuations", "bubble",
      "ai", "shadow bank", "private credit",
  )  # v1/tunable -- case-insensitive substring match against title+description.

  # Marker 13 -- funding markets start choking (FRED-backed, zero new DB state -- mirrors
  # credit_spread.py's own "recompute from FRED history every run" pattern exactly).
  SIGNALS_FUNDING_SPREAD_SERIES = ("DCPN3M", "DTB3")  # 3-Month AA Nonfinancial Commercial
      # Paper Rate minus 3-Month Treasury Bill rate -- a direct, daily-updating
      # funding-market-stress spread (widens when short-term lenders demand more premium to
      # fund non-bank borrowers).
  SIGNALS_FUNDING_STRESS_INDEX_SERIES = ("STLFSI4", "NFCI")  # St. Louis Fed Financial Stress
      # Index + Chicago Fed National Financial Conditions Index -- two independent broad
      # gauges, secondary corroboration only, not the primary signal.
  SIGNALS_FUNDING_SPREAD_LOOKBACK_DAYS = 365  # trailing year for the z-score baseline.
  SIGNALS_FUNDING_SPREAD_FLAG_ZSCORE = 2.0  # v1/tunable -- spread >=2 std devs above its
      # own trailing-year mean.
  SIGNALS_FUNDING_STRESS_FLAG_ZSCORE = 2.0  # same threshold shape applied to STLFSI4/NFCI.
  ```
- **PATTERN**: every existing constant in this file has a trailing "why this number" comment
  — match that exactly.
- **VALIDATE**: `uv run --directory investments/fourteen-crash-signals-daily-check python -c
  "from fourteen_crash_signals_daily_check import config; print(config.SIGNALS_REGULATOR_FEED_URLS,
  config.SIGNALS_FUNDING_SPREAD_SERIES)"`

### Task 4: UPDATE `.../fourteen_crash_signals_daily_check/db.py` — 2 new tables + CRUD

- **IMPLEMENT**: Add to `init_signals_tables`'s `executescript` call:
  ```sql
  CREATE TABLE IF NOT EXISTS signals_putcall_history (
      observed_at   TEXT PRIMARY KEY,
      ratio         REAL NOT NULL
  );
  CREATE TABLE IF NOT EXISTS signals_regulator_alert_seen (
      guid          TEXT PRIMARY KEY,
      source        TEXT NOT NULL,
      title         TEXT NOT NULL,
      seen_at       TEXT NOT NULL
  );
  ```
  Then add CRUD functions (below the existing Marker #12 functions):
  ```python
  def record_putcall_ratio(conn: sqlite3.Connection, *, ratio: float) -> None:
      today = _now()[:10]  # YYYY-MM-DD, one row per day
      with conn:
          conn.execute(
              """INSERT INTO signals_putcall_history (observed_at, ratio) VALUES (?, ?)
                 ON CONFLICT(observed_at) DO UPDATE SET ratio=excluded.ratio""",
              (today, ratio),
          )


  def get_putcall_history(conn: sqlite3.Connection, since_days: int) -> list[sqlite3.Row]:
      from datetime import date, timedelta

      cutoff = (date.today() - timedelta(days=since_days)).isoformat()
      return conn.execute(
          "SELECT * FROM signals_putcall_history WHERE observed_at >= ? ORDER BY observed_at",
          (cutoff,),
      ).fetchall()


  def has_seen_regulator_alert(conn: sqlite3.Connection, guid: str) -> bool:
      row = conn.execute(
          "SELECT 1 FROM signals_regulator_alert_seen WHERE guid = ?", (guid,)
      ).fetchone()
      return row is not None


  def mark_regulator_alert_seen(conn: sqlite3.Connection, *, guid: str, source: str, title: str) -> None:
      with conn:
          conn.execute(
              """INSERT INTO signals_regulator_alert_seen (guid, source, title, seen_at)
                 VALUES (?, ?, ?, ?)
                 ON CONFLICT(guid) DO NOTHING""",
              (guid, source, title, _now()),
          )
  ```
- **PATTERN**: `record_issuer_spread`/`get_issuer_spread_near` (Phase 2) for the exact
  "one row per day, upsert on conflict" shape `record_putcall_ratio`/`get_putcall_history`
  mirror. `mark_regulator_alert_seen` deliberately uses `DO NOTHING` (not `DO UPDATE`) since
  a seen-guid row never needs updating, only insert-once-then-ignore.
- **GOTCHA**: `get_putcall_history`'s `since_days` window should be called with a value
  meaningfully larger than `SIGNALS_PUTCALL_MIN_HISTORY_DAYS` in practice (e.g. 90) so the
  trailing mean/std has more than the bare-minimum bootstrap sample once past day 30 — pass
  this as an explicit argument from `retail_leverage.py`, don't hardcode a window inside
  `db.py` itself.
- **VALIDATE**: `uv run --directory investments/fourteen-crash-signals-daily-check python -m
  pytest fourteen_crash_signals_daily_check/tests/test_db.py -v` (after Task 5).

### Task 5: UPDATE `.../fourteen_crash_signals_daily_check/tests/test_db.py` — new table tests

- **IMPLEMENT**: Mirror the existing `test_upsert_signal_state_*`/`test_record_issuer_spread_*`
  style tests already in this file. Tests: (a) `record_putcall_ratio` insert then
  `get_putcall_history` returns it, (b) calling `record_putcall_ratio` twice same-day upserts
  (only one row for today), (c) `get_putcall_history` excludes rows older than `since_days`,
  (d) `has_seen_regulator_alert` returns `False` before, `True` after
  `mark_regulator_alert_seen`, (e) `mark_regulator_alert_seen` called twice with the same guid
  doesn't raise (the `DO NOTHING` path).
- **PATTERN**: Use the `db_conn` fixture from `conftest.py` — do not construct a raw
  `sqlite3.connect` in this test file.
- **VALIDATE**: `uv run --directory investments/fourteen-crash-signals-daily-check python -m
  pytest fourteen_crash_signals_daily_check/tests/test_db.py -v`

### Task 6: CREATE `.../fourteen_crash_signals_daily_check/funding_stress.py` (Marker #13)

- **IMPLEMENT**:
  ```python
  """Marker 13 -- funding markets start choking. Zero new DB state -- mirrors
  credit_spread.py's own "recompute entirely from a live FRED history fetch every run"
  pattern exactly, confirmed live 2026-08-18 (Phase 3 handoff): all series fetched via
  scripts.macro.fred_series_range, the exact function credit_spread.py already imports.

  Primary signal: DCPN3M - DTB3 (3-Month AA Nonfinancial Commercial Paper Rate minus
  3-Month Treasury Bill rate), a direct funding-market-stress spread -- widens when
  short-term lenders demand more premium to fund non-bank borrowers, the textbook
  mechanism the video describes (e.g. the 2007 Bear Stearns fund episode). Flagged on a
  z-score vs. its own trailing year, not a fixed absolute level, since "normal" for this
  spread shifts with the broader rate environment.

  Secondary corroboration: STLFSI4 (St. Louis Fed) and NFCI (Chicago Fed), two
  independent broad financial-stress indices -- flag if either also crosses its own
  z-score threshold, corroborating rather than replacing the primary spread signal.
  """

  from __future__ import annotations

  import statistics
  from datetime import date, timedelta

  from mytrader.checks import CheckResult
  from scripts.macro import fred_series_range

  from . import config


  def _zscore_of_latest(history: list[tuple[date, float]]) -> tuple[float, float] | None:
      """Returns (latest_value, zscore) using the full history's own mean/stdev, or None
      if there are fewer than 2 points (stdev undefined) or stdev is 0 (flat series)."""
      if len(history) < 2:
          return None
      values = [v for _, v in history]
      mean = statistics.mean(values)
      stdev = statistics.pstdev(values)
      if stdev == 0:
          return None
      latest = values[-1]
      return latest, (latest - mean) / stdev


  def _fetch_spread_zscore() -> tuple[float, float] | None:
      cp_series, tbill_series = config.SIGNALS_FUNDING_SPREAD_SERIES
      today = date.today()
      start = today - timedelta(days=config.SIGNALS_FUNDING_SPREAD_LOOKBACK_DAYS)
      cp_history = fred_series_range(cp_series, start, today)
      tbill_history = fred_series_range(tbill_series, start, today)
      if not cp_history or not tbill_history:
          return None
      tbill_by_date = dict(tbill_history)
      spread_history = [
          (d, v - tbill_by_date[d]) for d, v in cp_history if d in tbill_by_date
      ]
      return _zscore_of_latest(spread_history)


  def _fetch_index_zscore(series_id: str) -> tuple[float, float] | None:
      today = date.today()
      start = today - timedelta(days=config.SIGNALS_FUNDING_SPREAD_LOOKBACK_DAYS)
      history = fred_series_range(series_id, start, today)
      if not history:
          return None
      return _zscore_of_latest(history)


  def check_funding_stress() -> CheckResult:
      spread_result = _fetch_spread_zscore()
      if spread_result is None:
          return CheckResult(
              name="funding_stress", verdict="unknown",
              detail="FRED commercial-paper/Treasury spread data unavailable "
                     "(FRED_API_KEY not set, series unavailable, or insufficient history)",
          )
      spread_value, spread_z = spread_result
      spread_flag = spread_z >= config.SIGNALS_FUNDING_SPREAD_FLAG_ZSCORE

      index_flags = []
      for series_id in config.SIGNALS_FUNDING_STRESS_INDEX_SERIES:
          idx_result = _fetch_index_zscore(series_id)
          if idx_result is not None:
              idx_value, idx_z = idx_result
              if idx_z >= config.SIGNALS_FUNDING_STRESS_FLAG_ZSCORE:
                  index_flags.append(f"{series_id}={idx_value:.3f} (z={idx_z:.2f})")

      detail = (
          f"CP-Treasury spread (DCPN3M-DTB3) {spread_value:.2f}pp (z={spread_z:.2f} vs "
          f"trailing {config.SIGNALS_FUNDING_SPREAD_LOOKBACK_DAYS}d)"
      )
      if index_flags:
          detail += f"; corroborating stress index(es) elevated: {', '.join(index_flags)}"
      verdict = "flag" if spread_flag or index_flags else "ok"
      return CheckResult(
          name="funding_stress", verdict=verdict, detail=detail,
          data={"spread": spread_value, "spread_zscore": spread_z, "index_flags": index_flags},
      )
  ```
- **PATTERN**: `credit_spread.py` (whole file) for the "no DB connection parameter needed,
  recompute entirely from a live FRED fetch" shape.
- **GOTCHA**: `_zscore_of_latest` uses population stdev (`statistics.pstdev`), not sample
  stdev (`statistics.stdev`) — deliberate: the trailing-year history is being treated as the
  full population of interest for "how unusual is today", not a sample estimating some larger
  population, consistent with how a z-score-vs-own-history framing is used elsewhere in this
  plan (Marker #7's bootstrap z-score uses the same choice, see Task 12).
- **VALIDATE**: `uv run --directory investments/fourteen-crash-signals-daily-check python -m
  pytest fourteen_crash_signals_daily_check/tests/test_funding_stress.py -v` (after Task 7).

### Task 7: CREATE `.../fourteen_crash_signals_daily_check/tests/test_funding_stress.py`

- **IMPLEMENT**: Mirror `test_credit_spread.py`'s monkeypatch-at-module-level style,
  monkeypatching `fourteen_crash_signals_daily_check.funding_stress.fred_series_range`.
  Tests: (a) flags when the CP-Treasury spread's z-score is at/above the threshold, (b) stays
  ok when spread z-score is below threshold and no index is elevated, (c) flags when the
  spread itself is ok but STLFSI4 or NFCI crosses its own threshold (corroboration path),
  (d) `verdict="unknown"` when `fred_series_range` returns `None`/falsy for the spread series,
  (e) date misalignment: `cp_history` has a date `tbill_history` doesn't (or vice versa) — that
  date is dropped from the joint spread series, not a crash.
  ```python
  def _series(values: list[float], start: date) -> list[tuple[date, float]]:
      return [(start + timedelta(days=i), v) for i, v in enumerate(values)]
  ```
  Use a helper like this to build synthetic ascending histories with a controllable
  mean/stdev/last-value for each test case.
- **VALIDATE**: `uv run --directory investments/fourteen-crash-signals-daily-check python -m
  pytest fourteen_crash_signals_daily_check/tests/test_funding_stress.py -v`

### Task 8: CREATE `.../fourteen_crash_signals_daily_check/seller_financing.py` (Marker #3)

- **IMPLEMENT**:
  ```python
  """Marker 3 -- seller finances buyer (vendor/circular financing, e.g. Nvidia's $30B
  OpenAI stake, the Nvidia+Microsoft+Anthropic deal, Coreweave's unsold-capacity
  commitment). No free structured source exists for this -- confirmed by live-testing
  EDGAR full-text search for vendor-financing-shaped phrases during the Phase 3 handoff
  (e.g. "capacity purchase agreement" in 8-Ks returned 7 hits, dominated by an unrelated
  Alaska Air Group filing, not tech vendor-financing deals). There is no XBRL tag, form
  type, or SIC-scoped search that captures "Company A invests in Company B who then buys
  Company A's product" as a discrete, structured fact -- every real example was identified
  from trade-press coverage of a specific named deal, not a queryable dataset.

  Same shape as Marker #9 before it shipped real date-logic: a permanent
  verdict="unknown" maintained flag, not a placeholder for more research -- this is the
  honest, final answer for this marker, confirmed with Shaun 2026-08-18 (Phase 3 handoff).
  No polling cadence makes this into real automation; there is nothing to poll."""

  from __future__ import annotations

  from typing import Any

  from mytrader.checks import CheckResult


  def check_seller_financing(hot_watchlist: list[Any]) -> CheckResult:
      tickers = [row["ticker"] for row in hot_watchlist]
      if tickers:
          detail = (
              "No automatable source exists for vendor/circular-financing deals -- "
              f"periodically news-scan the current hot watchlist yourself: {', '.join(tickers)}"
          )
      else:
          detail = (
              "No automatable source exists for vendor/circular-financing deals, and no "
              "hot-watchlist companies are resolved this run to suggest news-scanning."
          )
      return CheckResult(
          name="seller_financing", verdict="unknown", detail=detail,
          data={"tickers": tickers},
      )
  ```
- **PATTERN**: `super_bowl.py`'s module docstring style and its `verdict="unknown"` as the
  *normal, permanent, expected* state (not a fetch-failure signal) — this file's GOTCHA is the
  same one documented there: `report.py`/`main.py` must not treat this marker's `"unknown"` as
  something to alert on.
- **GOTCHA**: This check takes `hot_watchlist` (already-computed rows) directly, not a `conn`
  — it never queries the DB itself, only reads the list already computed once per run by
  `watchlist.get_or_refresh_hot_watchlist`. Do not recompute the watchlist independently here.
- **VALIDATE**: `uv run --directory investments/fourteen-crash-signals-daily-check python -m
  pytest fourteen_crash_signals_daily_check/tests/test_seller_financing.py -v` (after Task 9).

### Task 9: CREATE `.../fourteen_crash_signals_daily_check/tests/test_seller_financing.py`

- **IMPLEMENT**: Tests: (a) `verdict="unknown"` always, regardless of input, (b) detail names
  every ticker in a non-empty `hot_watchlist`, (c) detail degrades gracefully (different
  message) when `hot_watchlist` is `[]`, (d) `data["tickers"]` matches the input tickers
  exactly.
- **VALIDATE**: `uv run --directory investments/fourteen-crash-signals-daily-check python -m
  pytest fourteen_crash_signals_daily_check/tests/test_seller_financing.py -v`

### Task 10: CREATE `.../fourteen_crash_signals_daily_check/debt_issuance.py` (Marker #1)

- **IMPLEMENT**:
  ```python
  """Marker 1 -- record debt issuance in the hot sector. Per-issuer, reads the hot
  watchlist (like Markers #2/#4/#12). Uses the same three form types
  (424B2/424B5/FWP) already declared as SIGNALS_BOND_PROSPECTUS_FORM_TYPES for
  Marker #12's CUSIP discovery -- the same filing types that disclose a CUSIP also
  *are* the debt-issuance events this marker wants to count, confirmed live 2026-08-18.

  Zero new DB state (a deliberate simplification vs. the Phase 3 handoff's own suggestion
  of a filing-count-history table): EDGAR's full-text search API accepts arbitrary
  startdt/enddt ranges on every call, so both the trailing window and the historical
  baseline are computed via two live queries per ticker per run, not accumulated locally.

  Honest limitation (state this in the report, same standard as Marker #12's bond-yield
  proxy): this counts filing EVENTS, not aggregate dollar principal -- it cannot reproduce
  a literal "$570B global AI-debt issuance" figure. It answers "is this issuer suddenly
  filing debt prospectuses faster than its own history," a real, directionally-correct
  proxy for "record debt issuance," not an exact dollar match."""

  from __future__ import annotations

  from datetime import date, timedelta
  from typing import Any

  from mytrader import sec_filings
  from mytrader.checks import CheckResult

  from . import config

  _FORM_TYPES = ",".join(config.__dict__.get("SIGNALS_BOND_PROSPECTUS_FORM_TYPES", ())) or None


  def _check_one_ticker(conn, ticker: str) -> CheckResult | None:
      cik = sec_filings.get_cik(conn, ticker)
      if cik is None:
          return None
      today = date.today()
      forms = ",".join(config.SIGNALS_BOND_PROSPECTUS_FORM_TYPES)

      trailing_count = sec_filings.edgar_fulltext_search_count(
          forms, cik=cik,
          startdt=today - timedelta(days=config.SIGNALS_DEBT_ISSUANCE_LOOKBACK_DAYS), enddt=today,
      )
      if trailing_count is None:
          return None
      baseline_count = sec_filings.edgar_fulltext_search_count(
          forms, cik=cik,
          startdt=today - timedelta(days=config.SIGNALS_DEBT_ISSUANCE_BASELINE_DAYS), enddt=today,
      )
      if baseline_count is None:
          return None

      periods = config.SIGNALS_DEBT_ISSUANCE_BASELINE_DAYS / config.SIGNALS_DEBT_ISSUANCE_LOOKBACK_DAYS
      baseline_rate = baseline_count / periods  # average filings per trailing-window-length period

      detail = (
          f"{ticker}: {trailing_count} debt-prospectus filing(s) in the trailing "
          f"{config.SIGNALS_DEBT_ISSUANCE_LOOKBACK_DAYS}d (own {config.SIGNALS_DEBT_ISSUANCE_BASELINE_DAYS}d "
          f"average: {baseline_rate:.1f}/period) -- counts filing events, not dollar principal"
      )
      verdict = "ok"
      if baseline_rate > 0 and trailing_count >= baseline_rate * config.SIGNALS_DEBT_ISSUANCE_FLAG_RATIO:
          verdict = "flag"
      return CheckResult(
          name="debt_issuance", verdict=verdict, detail=detail,
          data={"ticker": ticker, "trailing_count": trailing_count, "baseline_rate": baseline_rate},
      )


  def check_debt_issuance(conn, hot_watchlist: list[Any]) -> list[CheckResult]:
      results = []
      for row in hot_watchlist:
          result = _check_one_ticker(conn, row["ticker"])
          if result is not None:
              results.append(result)
      return results
  ```
  Drop the stray `_FORM_TYPES` module-level line above (leftover from drafting) — it is not
  used anywhere in the function bodies; the working code builds `forms` fresh inside
  `_check_one_ticker` via `",".join(config.SIGNALS_BOND_PROSPECTUS_FORM_TYPES)`. Do not
  include that dead line in the actual file.
- **PATTERN**: `lease_commitment.py`'s `_check_one_ticker`/`check_lease_commitments` shape
  (per-ticker, `list[CheckResult]`, `conn` + `hot_watchlist` params) — this marker is simpler
  since it needs no document fetch or LLM step, just two count queries.
  `config.SIGNALS_BOND_PROSPECTUS_FORM_TYPES` already exists (Phase 2, `config.py` line 85) —
  import it as-is, do not redeclare.
- **GOTCHA**: `baseline_rate > 0` guards against a divide-by-zero-shaped flag when a ticker
  has never filed one of these form types in 2 years (an issuer with literally zero
  historical filings shouldn't flag just because `trailing_count` is any positive number —
  that's "first ever debt issuance", arguably interesting but not what this marker's
  divergence-ratio framing is designed to catch; it renders `verdict="ok"` with the honest
  0.0/period baseline visible in the detail string).
- **VALIDATE**: `uv run --directory investments/fourteen-crash-signals-daily-check python -m
  pytest fourteen_crash_signals_daily_check/tests/test_debt_issuance.py -v` (after Task 11).

### Task 11: CREATE `.../fourteen_crash_signals_daily_check/tests/test_debt_issuance.py`

- **IMPLEMENT**: Mirror `test_credit_spread_issuer.py`'s monkeypatch-at-module-level style
  (`monkeypatch.setattr(debt_issuance.sec_filings, "get_cik", ...)` /
  `"edgar_fulltext_search_count"`). Tests: (a) flags when `trailing_count >=
  baseline_rate * SIGNALS_DEBT_ISSUANCE_FLAG_RATIO`, (b) stays ok when below the ratio,
  (c) stays ok (no divide-by-zero) when `baseline_count == 0`, (d) ticker silently skipped
  when `get_cik` returns `None`, (e) ticker silently skipped when either
  `edgar_fulltext_search_count` call returns `None`, (f) `check_debt_issuance` with an empty
  watchlist returns `[]`.
- **VALIDATE**: `uv run --directory investments/fourteen-crash-signals-daily-check python -m
  pytest fourteen_crash_signals_daily_check/tests/test_debt_issuance.py -v`

### Task 12: CREATE `.../fourteen_crash_signals_daily_check/ipo_issuance.py` (Marker #6)

- **IMPLEMENT**:
  ```python
  """Marker 6 -- record IPO/equity issuance. Market-wide, not per-issuer (hot-watchlist
  mega-caps aren't IPO candidates) -- no hot_watchlist parameter needed. Uses the same
  edgar_fulltext_search_count helper as Marker #1 (see debt_issuance.py / sec_filings.py),
  but compares a trailing window against the SAME CALENDAR WINDOW one year prior (a direct
  YoY comparison, mirroring mytrader.margin_debt's own YoY shape) rather than a rolling
  multi-period baseline -- confirmed live 2026-08-18 this is a real, moving signal: S-1
  filings over an identical 18-day August window differ meaningfully year over year (85 in
  2026 vs 145 in 2025) -- notably LOWER in 2026, a reminder this metric doesn't move
  monotonically upward and a naive "always flag on growth" implementation would need real
  data, not an assumption, to calibrate.

  Two sub-signals, both flagged independently then combined: S-1 (intent-to-register --
  used by a long tail of small-cap/shell registrants too, a pace/activity proxy not a
  "big-name IPO" proxy) and 424B4 (final IPO prospectus, i.e. actually priced -- a cleaner,
  stronger filter, confirmed live and queryable the same way)."""

  from __future__ import annotations

  from datetime import date, timedelta

  from mytrader import sec_filings
  from mytrader.checks import CheckResult

  from . import config


  def _windowed_count(forms: str, start: date, end: date) -> int | None:
      return sec_filings.edgar_fulltext_search_count(forms, startdt=start, enddt=end)


  def _sub_signal(forms: str, label: str) -> tuple[str, bool] | None:
      today = date.today()
      window_start = today - timedelta(days=config.SIGNALS_IPO_FILING_WINDOW_DAYS)
      current = _windowed_count(forms, window_start, today)
      if current is None:
          return None
      prior_end = today - timedelta(days=365)
      prior_start = prior_end - timedelta(days=config.SIGNALS_IPO_FILING_WINDOW_DAYS)
      prior = _windowed_count(forms, prior_start, prior_end)
      if prior is None:
          return f"{label}: {current} filing(s) (no prior-year comparison available)", False

      ratio = current / prior if prior else None
      flagged = ratio is not None and ratio >= config.SIGNALS_IPO_FILING_FLAG_RATIO
      detail = (
          f"{label}: {current} filing(s) in the trailing {config.SIGNALS_IPO_FILING_WINDOW_DAYS}d "
          f"vs {prior} in the same window a year ago"
          + (f" ({ratio:.2f}x)" if ratio is not None else "")
      )
      return detail, flagged


  def check_ipo_issuance() -> CheckResult:
      s1_result = _sub_signal("S-1", "S-1 (intent to register)")
      b4_result = _sub_signal("424B4", "424B4 (priced IPO)")
      if s1_result is None and b4_result is None:
          return CheckResult(
              name="ipo_issuance", verdict="unknown",
              detail="EDGAR full-text search unavailable for both S-1 and 424B4 sub-signals",
          )
      details = [r[0] for r in (s1_result, b4_result) if r is not None]
      flagged = any(r[1] for r in (s1_result, b4_result) if r is not None)
      return CheckResult(
          name="ipo_issuance", verdict="flag" if flagged else "ok",
          detail="; ".join(details),
          data={"s1": s1_result, "424b4": b4_result},
      )
  ```
- **PATTERN**: `margin_debt.py`'s YoY-comparison-with-graceful-degradation shape (compare
  against a matched-calendar-window-one-year-prior value, degrade to a no-comparison message
  when the prior value is unavailable rather than failing the whole check).
- **GOTCHA**: `prior_end = today - timedelta(days=365)` (exactly 365 days back, not adjusted
  for leap years) intentionally mirrors the handoff's own "identical calendar window" framing
  loosely, not to the day — this is a v1 approximation, not a bug; a true calendar-identical
  window (e.g. "Aug 1 - Aug 18" in both years) would need month/day arithmetic this plan
  doesn't add, since a 1-2 day drift doesn't materially change a 30-day-window filing count.
- **VALIDATE**: `uv run --directory investments/fourteen-crash-signals-daily-check python -m
  pytest fourteen_crash_signals_daily_check/tests/test_ipo_issuance.py -v` (after Task 13).

### Task 13: CREATE `.../fourteen_crash_signals_daily_check/tests/test_ipo_issuance.py`

- **IMPLEMENT**: Monkeypatch `ipo_issuance.sec_filings.edgar_fulltext_search_count` with a
  side-effect function keyed on the `forms`/`startdt` args (since both sub-signals and both
  windows call the same function). Tests: (a) flags when either sub-signal's ratio meets the
  threshold, (b) stays ok when neither does, (c) `verdict="unknown"` only when BOTH
  sub-signals return `None` for their current-window query, (d) one sub-signal degrades to
  "no prior-year comparison" text (not a crash) when only the prior-window query returns
  `None`, (e) divide-by-zero guard when `prior == 0`.
- **VALIDATE**: `uv run --directory investments/fourteen-crash-signals-daily-check python -m
  pytest fourteen_crash_signals_daily_check/tests/test_ipo_issuance.py -v`

### Task 14: CREATE `.../fourteen_crash_signals_daily_check/retail_leverage.py` (Marker #7)

- **IMPLEMENT**:
  ```python
  """Marker 7 -- retail piles into leverage. NOTE (read before enabling this in
  main.py's daily run -- flagged for Shaun's explicit sign-off, see this plan's NOTES):
  this measures CBOE equity options positioning (the put/call ratio), a DIFFERENT
  mechanism than the source video's framing (record ETF inflows / leveraged-fund flows).
  No free structured fund-flow feed was reachable (ICI's stats page 403'd; yfinance's
  shares-outstanding history returned None for leveraged ETF tickers) -- this is a
  related-but-not-identical proxy: a low put/call ratio (more speculative call-buying)
  is a reasonable signal of retail leverage-seeking behavior, not the same thing as fund
  inflows.

  Data source, confirmed live 2026-08-18 during Phase 3 planning (an upgrade over the
  Phase 3 handoff's own "needs a live spike" assessment): cboe.com's daily options
  market-statistics page is server-rendered by Next.js and embeds a JSON blob inside a
  `self.__next_f.push(...)` script tag containing `"ratios":[{"name":"EQUITY PUT/CALL
  RATIO","value":"0.65"}, ...]` -- NOT HTML-table-only as the handoff assumed. A single
  targeted regex against the escaped JSON text extracts the field directly (mirrors
  credit_spread_issuer.py's _CUSIP_RE -- regex out the one field needed, don't parse the
  whole document). CBOE exposes no historical series for this ratio (today's reading
  only) -- this package accumulates its own daily history via signals_putcall_history,
  the same "no source-side history, build our own" shape credit_spread_issuer.py uses for
  Marker #12's spread history."""

  from __future__ import annotations

  import re
  import sqlite3
  import statistics

  import requests
  from mytrader.checks import CheckResult

  from . import config, db

  _CBOE_URL = "https://www.cboe.com/us/options/market_statistics/daily/"
  _HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
  # EQUITY PUT/CALL RATIO's escaped-JSON field, confirmed live 2026-08-18 against the real
  # page: ...\"name\":\"EQUITY PUT/CALL RATIO\",\"value\":\"0.65\"... -- match the escaped
  # quotes literally (\\\") since the page embeds JSON-as-a-JS-string-literal, not raw JSON.
  _PUTCALL_RE = re.compile(
      r'EQUITY PUT/CALL RATIO\\+"\s*,\s*\\+"value\\+"\s*:\s*\\+"([0-9.]+)\\+"'
  )


  def _fetch_putcall_ratio_live() -> float | None:
      try:
          r = requests.get(_CBOE_URL, headers=_HEADERS, timeout=20)
          if r.status_code != 200:
              return None
          match = _PUTCALL_RE.search(r.text)
          if match is None:
              return None
          return float(match.group(1))
      except Exception:
          return None


  def check_retail_leverage(conn: sqlite3.Connection) -> CheckResult:
      ratio = _fetch_putcall_ratio_live()
      if ratio is None:
          return CheckResult(
              name="retail_leverage", verdict="unknown",
              detail="CBOE equity put/call ratio unavailable this run (fetch or parse failed)",
          )

      history_window = max(config.SIGNALS_PUTCALL_MIN_HISTORY_DAYS * 3, 90)
      prior_rows = db.get_putcall_history(conn, history_window)
      db.record_putcall_ratio(conn, ratio=ratio)

      if len(prior_rows) < config.SIGNALS_PUTCALL_MIN_HISTORY_DAYS:
          return CheckResult(
              name="retail_leverage", verdict="unknown",
              detail=f"Equity put/call ratio {ratio:.2f} -- accumulating baseline, "
                     f"day {len(prior_rows) + 1} of {config.SIGNALS_PUTCALL_MIN_HISTORY_DAYS} "
                     f"(different mechanism than ETF/fund-flow data -- see module docstring)",
              data={"ratio": ratio, "history_days": len(prior_rows)},
          )

      prior_values = [row["ratio"] for row in prior_rows]
      mean = statistics.mean(prior_values)
      stdev = statistics.pstdev(prior_values)
      zscore = (ratio - mean) / stdev if stdev else 0.0
      flagged = stdev > 0 and zscore <= config.SIGNALS_PUTCALL_FLAG_ZSCORE
      detail = (
          f"Equity put/call ratio {ratio:.2f} (z={zscore:.2f} vs trailing "
          f"{len(prior_values)}d mean {mean:.2f}) -- options positioning proxy, not the "
          f"video's ETF/fund-flow mechanism"
      )
      return CheckResult(
          name="retail_leverage", verdict="flag" if flagged else "ok", detail=detail,
          data={"ratio": ratio, "zscore": zscore, "mean": mean},
      )
  ```
- **PATTERN**: `credit_spread_issuer.py`'s `_CUSIP_RE` for the "regex a single field out of
  raw fetched text, don't fully parse the document" approach.
- **IMPORTS**: This is the first module in this package to call `requests` directly (every
  other module goes through `mytrader`/`goat`/`scripts.macro`'s existing wrappers) — `requests`
  is already a direct dependency of this package (`pyproject.toml` line 8), so no dependency
  change is needed, just a new top-level `import requests`.
- **GOTCHA**: `db.record_putcall_ratio(conn, ratio=ratio)` is called BEFORE computing the
  z-score against `prior_rows` (which was fetched before the write) — this is deliberate:
  today's own reading must never be included in its own baseline comparison, so the read
  (`get_putcall_history`) must happen strictly before the write (`record_putcall_ratio`) each
  run. Do not reorder these two calls.
- **GOTCHA**: The regex `\\+"` (one-or-more literal backslashes before a quote) — confirmed
  necessary because different Next.js payload-escaping depths were observed in casual testing
  (the page's own escaping can nest); use `\\+` not a fixed `\\\\` count so the regex tolerates
  either. Re-confirm against the real live page text at implementation time before trusting
  this pattern blindly (`r.text` from a real fetch, not a canned fixture) — if CBOE changes
  their page's rendering approach, this regex is the single point of fragility in this file,
  by design (same trade-off Marker #12's CUSIP regex already accepts).
- **VALIDATE**: `uv run --directory investments/fourteen-crash-signals-daily-check python -c
  "from fourteen_crash_signals_daily_check.retail_leverage import _fetch_putcall_ratio_live;
  r = _fetch_putcall_ratio_live(); print('ratio:', r); assert r is not None and 0 < r < 5"`
  (live network call — confirm it returns a real float before moving on; a value of `None`
  here means the regex needs adjusting against the actual current page text, not that this
  plan's approach is wrong).

### Task 15: CREATE `.../fourteen_crash_signals_daily_check/tests/test_retail_leverage.py`

- **IMPLEMENT**: Monkeypatch `retail_leverage._fetch_putcall_ratio_live` (not `requests.get`
  directly — the regex-extraction logic is exercised separately, see the next bullet).
  Tests: (a) `verdict="unknown"` when `_fetch_putcall_ratio_live` returns `None`,
  (b) `verdict="unknown"` with "accumulating baseline" detail and correct day-count when
  `db_conn` has fewer than `SIGNALS_PUTCALL_MIN_HISTORY_DAYS` prior rows, (c) flags when
  `stdev > 0` and today's z-score is at/below the flag threshold, (d) stays ok when z-score is
  above threshold, (e) never flags when `stdev == 0` (all prior readings identical) even if
  today's ratio differs, (f) confirms `db.record_putcall_ratio` was called (row exists in
  `db_conn` after) even on the accumulating-baseline path, not only after bootstrap completes.
  Add one separate test exercising `_PUTCALL_RE` directly against a realistic escaped-JSON
  fixture string (not a live fetch) to lock in the regex shape:
  ```python
  _FIXTURE_TEXT = r'...\"name\":\"EQUITY PUT/CALL RATIO\",\"value\":\"0.65\"...'

  def test_putcall_regex_extracts_from_escaped_json_fixture():
      match = retail_leverage._PUTCALL_RE.search(_FIXTURE_TEXT)
      assert match is not None
      assert match.group(1) == "0.65"
  ```
- **VALIDATE**: `uv run --directory investments/fourteen-crash-signals-daily-check python -m
  pytest fourteen_crash_signals_daily_check/tests/test_retail_leverage.py -v`

### Task 16: CREATE `.../fourteen_crash_signals_daily_check/regulator_alarm.py` (Marker #11)

- **IMPLEMENT**:
  ```python
  """Marker 11 -- regulators sound the alarm. Daily poll of 3 RSS feeds (SEC press
  releases, Fed press releases, Fed speeches), all confirmed live 2026-08-18: valid RSS
  2.0, parseable with stdlib xml.etree.ElementTree (no new dependency), current items,
  <guid> present and stable on every item across all 3 feeds -- used as the dedup key so
  the same item isn't re-flagged every day it stays in the feed (mirrors
  signals_bond_cusip_cache's own dedup-by-key shape from Marker #12).

  v1 scope, an honest scope-down from what a human reading the full documents would
  catch: this keyword-scans only the RSS item's title+description, not the linked full
  document. RSS titles/descriptions are often generic ("Federal Reserve Board announces
  approval of the application by [Bank]") -- many of the substantive systemic-risk
  statements this marker actually wants (BIS-style commentary, Financial Stability Report
  language) live in the body of a linked report, not the feed's own text. Fetching and
  scanning full linked-report text is a real, meaningfully bigger scope item, deliberately
  NOT part of this phase's baseline (see this plan's NOTES)."""

  from __future__ import annotations

  import sqlite3
  import xml.etree.ElementTree as ET

  import requests
  from mytrader.checks import CheckResult

  from . import config, db

  _HEADERS = {"User-Agent": "Shaun Thomson thomoz@outlook.com"}


  def _fetch_feed_items(url: str) -> list[dict[str, str]]:
      try:
          r = requests.get(url, headers=_HEADERS, timeout=20)
          if r.status_code != 200:
              return []
          root = ET.fromstring(r.content)
      except Exception:
          return []
      items = []
      for item in root.findall(".//item"):
          guid_el = item.find("guid")
          title_el = item.find("title")
          desc_el = item.find("description")
          link_el = item.find("link")
          guid = (guid_el.text or "").strip() if guid_el is not None else None
          if not guid:
              continue  # no stable dedup key -- skip rather than risk re-flagging forever
          items.append({
              "guid": guid,
              "title": (title_el.text or "").strip() if title_el is not None else "",
              "description": (desc_el.text or "").strip() if desc_el is not None else "",
              "link": (link_el.text or "").strip() if link_el is not None else "",
              "source": url,
          })
      return items


  def _matches_trigger_phrase(item: dict[str, str]) -> bool:
      haystack = f"{item['title']} {item['description']}".lower()
      return any(phrase in haystack for phrase in config.SIGNALS_REGULATOR_TRIGGER_PHRASES)


  def check_regulator_alarm(conn: sqlite3.Connection) -> list[CheckResult]:
      results = []
      for feed_url in config.SIGNALS_REGULATOR_FEED_URLS:
          for item in _fetch_feed_items(feed_url):
              if db.has_seen_regulator_alert(conn, item["guid"]):
                  continue
              db.mark_regulator_alert_seen(
                  conn, guid=item["guid"], source=feed_url, title=item["title"]
              )
              if not _matches_trigger_phrase(item):
                  continue  # seen and recorded, but not a keyword match -- not a CheckResult
              results.append(CheckResult(
                  name="regulator_alarm", verdict="flag",
                  detail=f"{item['title']} ({item['link']})",
                  data={"guid": item["guid"], "source": feed_url, "title": item["title"]},
              ))
      return results
  ```
- **PATTERN**: `insider_trend.py`'s `list[CheckResult]`, skip-if-nothing-to-report shape --
  most days this returns `[]` (no new matching items), which `report.py` renders with an
  explicit fallback row (see Task 18), not an error state.
  `db.mark_regulator_alert_seen`/`db.has_seen_regulator_alert` mirror
  `db.upsert_bond_cusip`/`db.get_bond_cusip`'s cache-check-before-fetch shape, adapted to a
  boolean-seen check instead of a cached value.
- **GOTCHA**: Every fetched item (whether or not it matches a trigger phrase) is marked seen
  — this is deliberate. If dedup only happened for matched items, a non-matching item seen
  today could still be re-evaluated (and potentially match, if `SIGNALS_REGULATOR_TRIGGER_PHRASES`
  is tuned later) on every subsequent run for as long as it stays in the 20-25-item feed
  window, which is a much noisier dedup story than "each item is considered exactly once,
  the day it's first seen."
  **GOTCHA**: This means changing `SIGNALS_REGULATOR_TRIGGER_PHRASES` will NOT retroactively
  flag already-seen items even if the new phrase list would have matched them — an accepted
  v1 trade-off given trigger-phrase tuning is expected to happen occasionally (per the
  handoff's "tunable, v1" framing), not a bug to fix in this phase.
- **VALIDATE**: `uv run --directory investments/fourteen-crash-signals-daily-check python -m
  pytest fourteen_crash_signals_daily_check/tests/test_regulator_alarm.py -v` (after Task 17).

### Task 17: CREATE `.../fourteen_crash_signals_daily_check/tests/test_regulator_alarm.py`

- **IMPLEMENT**: Monkeypatch `regulator_alarm._fetch_feed_items` (a list of dict-shaped fake
  items per feed URL, via a side-effect function keyed on the `url` arg) rather than
  `requests.get`/XML parsing directly — that XML-parsing logic gets its own separate test.
  Tests: (a) a new item whose title contains a trigger phrase produces one flagged
  `CheckResult` and is marked seen, (b) a new item that doesn't match any trigger phrase
  produces no `CheckResult` but IS marked seen (regression for the GOTCHA above — call
  `check_regulator_alarm` a second time with the same fake item still returned by
  `_fetch_feed_items` and confirm no duplicate/new result), (c) an already-seen item (pre-seed
  `db.mark_regulator_alert_seen` in the test) produces no `CheckResult` even if it matches a
  trigger phrase, (d) items across all 3 configured feed URLs are all processed (not just the
  first), (e) `check_regulator_alarm` with all feeds returning `[]` returns `[]`.
  Add one separate test exercising `_fetch_feed_items` against a real minimal RSS XML string
  fixture (monkeypatching `requests.get` this one time) to lock in the guid/title/description
  extraction:
  ```python
  _FIXTURE_RSS = """<?xml version="1.0"?><rss version="2.0"><channel>
  <item><title>Fed Board issues statement</title><link>https://example.com/x</link>
  <guid>https://example.com/x</guid><description>systemic risk language here</description>
  </item></channel></rss>"""
  ```
- **VALIDATE**: `uv run --directory investments/fourteen-crash-signals-daily-check python -m
  pytest fourteen_crash_signals_daily_check/tests/test_regulator_alarm.py -v`

### Task 18: UPDATE `.../fourteen_crash_signals_daily_check/report.py` — remove all 6 placeholders, wire real rows

- **IMPLEMENT**: Delete `_NOT_YET_AUTOMATED` and `_PLACEHOLDER_MARKERS` entirely (no marker
  needs a placeholder after this phase). Add 6 new parameters to `render_signals_report`
  (after the existing `credit_spread_issuer_results` param):
  `debt_issuance_results: list[Any]`, `seller_financing_result: Any`,
  `ipo_issuance_result: Any`, `retail_leverage_result: Any`,
  `regulator_alarm_results: list[Any]`, `funding_stress_result: Any`. Add render branches
  following the file's existing two shapes:
  ```python
  if debt_issuance_results:
      for r in debt_issuance_results:
          marker_rows.append((1, f"| 1 | Record debt issuance, hot sector ({r.data.get('ticker', '?')}) | {r.verdict} | {r.detail} |"))
  else:
      marker_rows.append((1, "| 1 | Record debt issuance, hot sector | ok | No hot-watchlist tickers with a resolvable CIK/filing count this run. |"))
  marker_rows.append((3, f"| 3 | Seller finances buyer | {seller_financing_result.verdict} | {seller_financing_result.detail} |"))
  marker_rows.append((6, f"| 6 | Record IPO/equity issuance | {ipo_issuance_result.verdict} | {ipo_issuance_result.detail} |"))
  marker_rows.append((7, f"| 7 | Retail piles into leverage | {retail_leverage_result.verdict} | {retail_leverage_result.detail} |"))
  if regulator_alarm_results:
      for r in regulator_alarm_results:
          marker_rows.append((11, f"| 11 | Regulators sound the alarm | {r.verdict} | {r.detail} |"))
  else:
      marker_rows.append((11, "| 11 | Regulators sound the alarm | ok | No new matching regulator statements this run. |"))
  marker_rows.append((13, f"| 13 | Funding markets start choking | {funding_stress_result.verdict} | {funding_stress_result.detail} |"))
  ```
  Remove the now-dead `for num, name in _PLACEHOLDER_MARKERS: ...` loop.
- **PATTERN**: `insider_trend_results`/`lease_commitment_results`'s existing
  if/else-with-fallback-row shape (for the two `list[CheckResult]` markers, #1 and #11);
  `credit_spread_result`/`market_cap_result`'s existing direct-row shape (for the four
  single-`CheckResult` markers, #3/#6/#7/#13).
- **GOTCHA**: After this task, `render_signals_report` takes 15 positional parameters total
  (9 existing + 6 new) — this is a real code smell the plan is deliberately not fixing (e.g.
  by switching to a single results dict/dataclass) since that's a larger refactor than this
  phase's scope; flagged in this plan's NOTES as a legitimate follow-up, not silently ignored.
- **VALIDATE**: `uv run --directory investments/fourteen-crash-signals-daily-check python -m
  pytest fourteen_crash_signals_daily_check/tests/test_report.py -v` (after Task 19).

### Task 19: UPDATE `.../fourteen_crash_signals_daily_check/tests/test_report.py`

- **IMPLEMENT**: Update every existing call to `render_signals_report` in this file to pass
  the 6 new required positional/keyword arguments (fake `CheckResult`/list-of-`CheckResult`
  values, mirroring how the existing 9 params are already faked in this file's current
  tests). Add new tests: (a) all 14 marker numbers (1-14) appear as row numbers in the
  rendered output, confirming `_PLACEHOLDER_MARKERS`/`_NOT_YET_AUTOMATED` are fully gone with
  no marker silently dropped, (b) marker 3's row renders `seller_financing_result`'s
  `verdict`/`detail` directly (not the old placeholder text), (c) marker 11 renders one row
  per item in a non-empty `regulator_alarm_results` list, (d) marker 11 renders the
  "No new matching regulator statements" fallback row when the list is empty.
- **VALIDATE**: `uv run --directory investments/fourteen-crash-signals-daily-check python -m
  pytest fourteen_crash_signals_daily_check/tests/test_report.py -v`

### Task 20: UPDATE `.../fourteen_crash_signals_daily_check/main.py` — orchestrate 6 new checks

- **IMPLEMENT**: In `cmd_daily_check`, add the 6 new module imports to the existing `from .
  import (...)` block (alphabetical, matching the existing style):
  `debt_issuance, funding_stress, ipo_issuance, regulator_alarm, retail_leverage,
  seller_financing`. After the existing `credit_spread_issuer_results = ...` line, add:
  ```python
  debt_issuance_results = debt_issuance.check_debt_issuance(conn, hot_watchlist)
  seller_financing_result = seller_financing.check_seller_financing(hot_watchlist)
  ipo_issuance_result = ipo_issuance.check_ipo_issuance()
  retail_leverage_result = retail_leverage.check_retail_leverage(conn)
  regulator_alarm_results = regulator_alarm.check_regulator_alarm(conn)
  funding_stress_result = funding_stress.check_funding_stress()
  ```
  Pass all 6 new values into `report.write_signals_report(...)`'s existing call, appended in
  the same order `render_signals_report`'s new parameters expect (Task 18). Extend
  `alert_inputs` with:
  ```python
  {"marker_key": "ipo_issuance", "is_firing": ipo_issuance_result.verdict == "flag", "detail": ipo_issuance_result.detail},
  {"marker_key": "retail_leverage", "is_firing": retail_leverage_result.verdict == "flag", "detail": retail_leverage_result.detail},
  {"marker_key": "funding_stress", "is_firing": funding_stress_result.verdict == "flag", "detail": funding_stress_result.detail},
  ```
  (single-result markers, alongside the existing `margin_debt_growth`/`market_cap_milestone`/
  `super_bowl_signal` entries), and per-item loops for the two `list[CheckResult]` markers:
  ```python
  for r in debt_issuance_results:
      alert_inputs.append({
          "marker_key": f"debt_issuance:{r.data.get('ticker')}",
          "is_firing": r.verdict == "flag", "detail": r.detail,
      })
  for r in regulator_alarm_results:
      alert_inputs.append({
          "marker_key": f"regulator_alarm:{r.data.get('guid')}",
          "is_firing": True, "detail": r.detail,
      })
  ```
  Do **not** add an entry for `seller_financing_result` — it is permanently `verdict="unknown"`
  and can never transition to firing; wiring it into `alert_inputs` would be dead code.
- **PATTERN**: The existing `insider_trend_results`/`lease_commitment_results`/
  `capex_cashflow_results`/`credit_spread_issuer_results` per-item `alert_inputs.append` loops
  immediately above where the new code is inserted.
- **GOTCHA**: `regulator_alarm_results` uses `"is_firing": True` unconditionally (every
  `CheckResult` this function returns already has `verdict="flag"` by construction — see
  Task 16, `check_regulator_alarm` only appends a result when `_matches_trigger_phrase` is
  `True`) — there is no "ok" state per-item for this marker the way there is for
  `debt_issuance_results`, so `r.verdict == "flag"` would be equivalent but `True` is more
  direct about what's actually possible here.
- **GOTCHA**: `db.upsert_signal_state`'s marker_key for `regulator_alarm` uses the item's
  `guid` (a URL or UUID) as the per-item key, not a ticker — this is intentional (each RSS
  item is its own one-time event, there's no ongoing "streak" or "still firing" state the way
  a ticker-scoped marker has; every new match is inherently a new transition since
  `check_regulator_alarm` itself already filters to never-seen-before items via
  `db.has_seen_regulator_alert`).
- **VALIDATE**: `uv run --directory investments/fourteen-crash-signals-daily-check python -c
  "import ast; ast.parse(open('fourteen_crash_signals_daily_check/main.py').read())"` (syntax
  check only — full behavioral validation happens in Task 21's manual run, since this
  function's real work is live external I/O across 14 markers, not something a fast unit test
  meaningfully covers beyond what each marker's own test file already does).

### Task 21: UPDATE `investments/TOOLS.md`

- **IMPLEMENT**: Update the "Fourteen Crash Signals" row's description (currently describes a
  partial build) to reflect that all 14 markers are now real (2, 4, 5, 8, 9, 10, 12, 14 from
  Phases 1-2; 1, 3, 6, 7, 11, 13 from this phase) — Marker 3 permanently manual-flag,
  Markers 1/6/7/11/13 fully automated, per the report's own per-row status.
- **VALIDATE**: Manual read-through — confirm the updated row accurately reflects
  `report.py`'s post-Task-18 behavior (no marker described as "not yet automated").

---

## TESTING STRATEGY

### Unit Tests

Every new function gets monkeypatch-isolated unit tests following this package's existing
`test_credit_spread_issuer.py`/`test_credit_spread.py` style — mock at the function-call
boundary (`sec_filings.edgar_fulltext_search_count`, `fred_series_range`,
`_fetch_putcall_ratio_live`, `_fetch_feed_items`), never mock `requests`/network calls inside
a test asserting business logic (those get their own narrow fixture-based test, see Tasks 2,
15, 17).

### Integration Tests

`test_report.py`'s updated tests (Task 19) are this package's integration-test layer —
confirming all 14 marker numbers render correctly from realistic fake `CheckResult` inputs
end-to-end through `render_signals_report`.

### Edge Cases

- Marker #1/#6: EDGAR full-text search returning `0` (a real, valid "no filings this
  period" answer) must not be treated as a fetch failure (`None`) — verify the
  `is None` vs `== 0` distinction is preserved throughout (a `0` count is falsy in Python,
  a classic bug magnet if any code uses `if not count:` instead of `if count is None:`).
- Marker #7: the very first-ever run (empty `signals_putcall_history` table) must not crash
  computing a z-score against zero prior rows — the `len(prior_rows) <
  SIGNALS_PUTCALL_MIN_HISTORY_DAYS` branch handles this, confirm a test exercises exactly
  `len(prior_rows) == 0`.
- Marker #11: a feed returning items with no `<guid>` element at all (malformed/nonstandard
  feed) must be skipped, not crash the whole check — confirmed handled by `_fetch_feed_items`'s
  `if not guid: continue`.
- Marker #13: `cp_history`/`tbill_history` covering different date ranges (FRED series can
  have gaps or different publication calendars) — confirm the dict-intersection join in
  `_fetch_spread_zscore` degrades gracefully rather than raising a `KeyError`.

---

## VALIDATION COMMANDS

### Level 1: Syntax & Style

```
uv run --directory investments/my-trader ruff check mytrader/sec_filings.py mytrader/tests/test_sec_filings.py
uv run --directory investments/fourteen-crash-signals-daily-check ruff check fourteen_crash_signals_daily_check/
```

### Level 2: Unit Tests

```
uv run --directory investments/my-trader python -m pytest mytrader/tests/test_sec_filings.py -v
uv run --directory investments/fourteen-crash-signals-daily-check python -m pytest fourteen_crash_signals_daily_check/tests/ -v
```

### Level 3: Integration Tests

```
uv run --directory investments/fourteen-crash-signals-daily-check python -m pytest fourteen_crash_signals_daily_check/tests/test_report.py fourteen_crash_signals_daily_check/tests/test_db.py -v
```

### Level 4: Manual Validation

```
uv run --directory investments/fourteen-crash-signals-daily-check python -m fourteen_crash_signals_daily_check.main daily-check
```

Then read `investments/fourteen-crash-signals-daily-check/signals-report.md` end to end and
confirm: all 14 marker rows present, numbered 1-14, no row says "Not yet automated", Marker 3
reads as a permanent manual-flag (not an error), Markers 1/6/7/11/13 show real detail
strings sourced from live data fetched during this run.

### Level 5: Additional Validation (Optional)

Run the full existing regression suite for both packages to confirm zero collateral damage
from the `sec_filings.py` addition (a shared module Marker #2/#12 from Phase 2 also depend
on):
```
uv run --directory investments/my-trader python -m pytest mytrader/tests/ -v
```

---

## ACCEPTANCE CRITERIA

- [ ] All 6 remaining markers (1, 3, 6, 7, 11, 13) render real `CheckResult`-derived rows in
      `signals-report.md` — `_PLACEHOLDER_MARKERS`/`_NOT_YET_AUTOMATED` are fully removed from
      `report.py`.
- [ ] `edgar_fulltext_search_count` is confirmed live-working (Task 1's validate command
      returns a real int) before any dependent marker (#1, #6) is trusted.
- [ ] Marker #7's CBOE regex extraction is confirmed live-working (Task 14's validate command
      returns a real float) — and Shaun has explicitly signed off on shipping the
      options-positioning proxy (a different mechanism than originally described) before
      `main.py` wires it into the daily automated run (see NOTES).
- [ ] Marker #3 never appears as a firing/alertable marker in `alert_inputs` (permanently
      `unknown`, by design).
- [ ] All new unit tests pass; full existing regression suite (`my-trader` +
      `fourteen-crash-signals-daily-check`) still passes with zero collateral failures.
- [ ] A real `daily-check` run completes end-to-end and produces a report with no marker
      showing stale/placeholder text.
- [ ] `investments/TOOLS.md` accurately describes the now-fully-automated tool.

---

## COMPLETION CHECKLIST

- [ ] All 21 tasks completed in order
- [ ] Each task's own VALIDATE command passed immediately after that task
- [ ] Full test suite passes (unit + integration, both packages)
- [ ] Ruff clean on all touched files
- [ ] Manual `daily-check` run confirms all 14 markers render correctly
- [ ] Shaun has reviewed and signed off on Marker #7's proxy substitution (see NOTES)
- [ ] `investments/TOOLS.md` updated

---

## NOTES

**Marker #7 needs Shaun's explicit sign-off before it goes live in the automated daily run.**
The handoff itself flagged this ("this is the one marker where the honest source is
meaningfully different in kind from what the original fact-check described, not just a
data-access workaround"). This plan's own research found a materially better data source
than the handoff expected (a clean JSON field, not fragile HTML-table scraping) — but that
only resolves the *technical feasibility* question, not the *is-this-still-the-right-proxy*
question. Recommend: build it per Tasks 14-15 and Task 20's wiring, but hold it out of (or
comment out) the `alert_inputs` entry specifically until Shaun has seen a few days of real
`retail_leverage_result` output in the report and confirms the proxy is worth alerting on —
the report row itself is harmless to ship immediately (advisor-mode, no action implied), only
the WhatsApp-alerting wiring is the part worth gating.

**Why Markers #1 and #6 need zero new DB tables, deviating from the handoff's own suggestion**:
the handoff's cross-cutting notes proposed a "small per-ticker filing-count-history table"
for #1 and a "market-wide filing-count-history table" for #6. This plan found (by testing
live during this session, not assuming) that EDGAR's full-text search API accepts arbitrary
historical `startdt`/`enddt` ranges on every single call — there is no need to accumulate a
local rolling series when the source itself can answer "how many filings were there in this
past window" for ANY past window, on demand, at any time. This mirrors why `credit_spread.py`
(Marker #14) never needed local state either — FRED, like EDGAR's full-text search, serves
full historical data on every call. This is a genuine simplification found during planning,
not a corner cut — flagged explicitly per this project's standing convention of stating
honest deviations rather than silently deviating.

**Markers #7 and #11 DO need new DB tables** because their sources are the opposite case:
CBOE's page shows only today's reading (no historical API), and RSS feeds only show the
current ~20-25 most recent items (no historical archive query) — both sources are
fundamentally "point-in-time snapshot" rather than "queryable history," so this package must
build its own accumulated history/dedup state to compute anything relative (a trailing
average, or "have I seen this before").

**Marker #11's title/description-only v1 scope** (not fetching/scanning full linked
documents) is the same honest scoped-down decision the Phase 3 handoff itself recommended —
carried forward unchanged into this plan, not re-litigated. A future phase could add full-text
fetching of the linked press-release/speech pages for a stronger keyword match, at real added
complexity (each RSS item is a link to fetch and parse, not just a title/description already
in hand) — a legitimate follow-up, not part of this phase.

**`render_signals_report`'s growing parameter list** (15 positional params after this phase,
up from 9) is a real code smell this plan does not fix. A natural follow-up (not in this
phase's scope) would be a single `results: dict[str, CheckResult | list[CheckResult]]`
parameter keyed by marker number or name, removing the need to update this function's
signature every time a new marker ships. Flagged here so it isn't silently repeated
indefinitely as a growing footgun.

**Marker #6's YoY window uses a fixed 365-day offset**, not a true calendar-identical window
(e.g. exact "Aug 1 - Aug 18" match in both years) — see Task 12's GOTCHA. Acceptable for a
30-day window (a 1-2 day drift is noise-level against a 30-day filing count), but would need
revisiting if `SIGNALS_IPO_FILING_WINDOW_DAYS` were ever shortened significantly.
