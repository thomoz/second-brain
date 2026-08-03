# Feature: Read SEC Filings Into Find's Principles-Fit Check

The following plan should be complete, but it's important to validate documentation and
codebase patterns and task sanity before implementing. Pay special attention to naming
of existing utils, types, and models. Import from the right files.

This plan implements the full scope discovered in
`.agent/plans/sec-filings-principles-fit-handoff.md` (a discovery conversation, not a
plan — this document supersedes it) with three open questions from that handoff now
resolved by Shaun (2026-08-03):

1. **DEF 14A proxy statements are in scope for v1**, alongside 10-K/10-Q (not deferred).
2. **Summarizer model tier**: test `"sonnet"` vs `"haiku"` on a real filing during build
   validation before locking the default (handoff's own recommendation — see Task 4.3).
   **Clarified 2026-08-03**: these are Claude-shaped tier *aliases*, not literal Claude
   model calls — `SB_AGENT_BACKEND=codex` is this repo's active backend (see
   `CLAUDE.md`'s model-agnostic architecture rule and `[[project_codex_backend]]`), so
   `codex_sdk_compat.py`'s `_MODEL_ALIASES` remaps them before any call goes out.
   Live-checked at planning time: `"haiku"` → `gpt-5.4-mini`, `"sonnet"`/`"opus"` →
   `gpt-5.4` (no separate strong tier currently configured, both aliases collapse to
   the same model). So Task 4.3's comparison is actually **gpt-5.4 (full) vs
   gpt-5.4-mini**, not Anthropic Sonnet vs Haiku — same "bigger/pricier vs
   smaller/cheaper" shape, just resolved through a different provider than the alias
   names suggest. This mapping can change without this plan's knowledge (env vars
   `CODEX_MODEL_CHEAP`/`CODEX_MODEL_MID`/`CODEX_MODEL_STRONG`, or a future backend
   switch back to `SB_AGENT_BACKEND=claude`/`pi`) — re-check the live mapping at Task
   4.3's execution time rather than trusting this note if much time has passed.
3. **Integration model**: **Option A** — augment `principles_fit.py`'s existing
   `_build_thesis()` with filing summaries, folding them into the one combined thesis
   all 9 principle files grade against, rather than adding a new standalone check.

## Feature Description

`my-trader`'s Find tool currently assesses a ticker using only `yfinance`'s pre-computed
summary stats. This feature adds a new data source: the company's own primary-source SEC
filings (10-K, 10-Q, DEF 14A), fetched directly from SEC EDGAR (free, no API key, just a
descriptive `User-Agent`), tag-stripped, section-extracted (Business, Risk Factors, MD&A
for 10-K/10-Q; Executive Compensation and Security Ownership for DEF 14A), summarized via
one LLM call per filing (through `sdk_compat`, per `CLAUDE.md`'s model-agnostic rule),
and folded into `principles_fit.py`'s existing thesis-building step — so the same 9
investor-framework grades (Buffett, Graham, Lynch, Munger, Dalio, Marks, Fisher, Smith,
Neilson) are now informed by what the company itself discloses, not just Yahoo's derived
ratios. This is the tool's move toward Shaun's stated goal: **"a tool that approximates
an expert investor."**

## User Story

As Shaun (a personal investor using Find's `principles_fit` check to grade tickers
against 9 named-investor frameworks)
I want the framework grading to also draw on the company's actual 10-K/10-Q/DEF 14A
disclosures, not just Yahoo Finance's derived ratios
So that the grades reflect what an expert investor would actually read before investing,
and Find can meaningfully assess US-listed tickers Briefs Finance never covered.
Shaun is a rookie trader, so needs interpretations that this tool makes presented to him 
in a simple manner, so that he can easily decide whether to invest in a particular company 
or commodity etc.

## Problem Statement

`principles_fit.py` (built 2026-08-02) grades a thesis built entirely from live
`yfinance` stats (PE, debt/equity, ROE, dividend history) plus a cached macro-regime
snapshot. For the six bottom-up frameworks (Buffett/Graham/Lynch/Munger/Fisher/Smith),
an expert investor would actually read the company's primary filing documents —
Business description, Risk Factors, MD&A, and (for Buffett/Munger's
incentive-alignment criteria specifically) executive compensation and insider ownership
— not derived ratios. None of that primary-source material currently reaches the thesis
or the 9 grading calls.

## Solution Statement

Add `mytrader/sec_filings.py`, modeled on `mytrader/abs_cpi.py`'s style (direct
government-source fetch via `requests`, no third-party SEC wrapper library, explicit
`User-Agent`, graceful `None`/skip on any failure — never raises). It resolves a ticker
to its SEC CIK (cached in a new `sec_cik_map` DB table, bulk-refreshed periodically),
finds the most recent 10-K / 10-Q / DEF 14A via SEC's submissions API, fetches the filing
HTML, extracts the relevant sections (Item-header-based for 10-K/10-Q, heading-search-
based for DEF 14A — see GOTCHAs, this is a real technical-risk area), summarizes each
filing's extracted sections with one LLM call (via `sdk_compat`, mirroring
`briefs-finance/scripts/score.py`'s own sys.path-insert pattern for reaching it), and
caches the summary in a new `sec_filing_cache` DB table keyed on `(ticker, filing_type)`
with the filing's accession number as the staleness check (only re-fetch/re-summarize
when a newer filing has actually been published — filing text doesn't change between
filings, unlike `principles_fit`'s live-stats thesis, which is why this cache uses a
completely different invalidation rule than that check's own "never cache" policy).

`checks/principles_fit.py`'s `_build_thesis()` gains a new optional
`filing_summaries: dict[str, str] | None` parameter (same pattern as the existing
`macro_rows` parameter — appended at the end, default `None`, so existing test call
sites keep working unchanged) and folds each filing's summary into the thesis text when
present. `check()` calls `sec_filings.get_filing_summaries_for_ticker(ticker, conn)`
(only when `conn is not None`, same gate the macro-snapshot lookup already uses) and
passes the result through. Non-US tickers (BXB.AX, WES.AX, VOLV-B.ST, etc. — SEC EDGAR
has no coverage) degrade gracefully to today's stats-only behavior via a plain CIK-lookup
miss, exactly like `concentration.py`/`etf_mechanics.py` already handle missing data.

## Feature Metadata

**Feature Type**: Enhancement (extends existing `principles_fit` check; no changes to
`engine.py`'s call site or `principles_fit.check()`'s external signature)
**Estimated Complexity**: High (two genuinely fuzzy HTML-section-extraction heuristics —
10-K/10-Q's Part-aware Item-header splitting, and DEF 14A's heading-search — a new bulk
CIK-map cache, a new filing-summary cache, a new direct LLM call, and real external-API
risk that can only be validated against live filings, not fully verified during planning)
**Primary Systems Affected**: `investments/my-trader/mytrader/` (new `sec_filings.py`,
extended `checks/principles_fit.py`, `db.py`, `config.py`, `main.py`),
`investments/my-trader/pyproject.toml`, `.claude/skills/my-trader/SKILL.md`
**Dependencies**: `beautifulsoup4` (new explicit dependency — already present
transitively in `investments/uv.lock` per a workspace-mate's pull, e.g. pandas'
`read_html` extra, confirmed importable in the current venv as `bs4` 4.15.0, but not
declared in any `pyproject.toml` — must be added explicitly rather than relied on as an
undeclared transitive dependency, since a future lockfile change could silently drop it).
No other new dependencies — `requests` and `sdk_compat`'s LLM access are already
available via existing imports.

---

## CONTEXT REFERENCES

### Relevant Codebase Files — READ THESE BEFORE IMPLEMENTING

- `.agent/plans/sec-filings-principles-fit-handoff.md` (full file) — the original
  discovery conversation this plan formalizes. Contains the exact SEC EDGAR endpoints,
  the confirmed `User-Agent` string, and the scope boundaries (10-K/10-Q/DEF 14A only,
  no earnings-call transcripts, most-recent filing only — not historical). Don't
  re-litigate anything marked "confirmed" there.
- `investments/my-trader/mytrader/checks/principles_fit.py` (full file, 151 lines) — the
  check this plan extends. `_build_thesis()` (lines 48-99) is the function gaining the
  new `filing_summaries` parameter — follow its exact existing pattern for the
  `macro_rows` parameter (added at the end, default `None`, conditionally appended to
  `parts` only when truthy, lines 94-97) for the new parameter. `check()` (lines
  102-150) is where `sec_filings.get_filing_summaries_for_ticker()` gets called,
  mirroring the existing `db.get_macro_snapshot(conn) if conn is not None else []`
  pattern at line 120. The module docstring (lines 1-37) documents why this check is
  deliberately NOT cached at the thesis level — the new filing-summary cache is a
  narrower, different-invalidation-rule cache one layer down (inside `sec_filings.py`,
  not `principles_fit.py` itself), not a contradiction of that policy; say so explicitly
  in this file's docstring update (Task 2.2) so a future reader doesn't "fix" the
  apparent inconsistency.
- `investments/my-trader/mytrader/abs_cpi.py` (full file, 75 lines) — the exact style
  `sec_filings.py` should mirror: direct-from-government-source fetch, no third-party
  wrapper library, `requests` + explicit header, module-level constants for
  URL-template/tunable parameters, graceful `None` return on any failure (`except
  Exception: return None`, e.g. lines 46-47, 73-74), a `_fetch_*_bytes()`-style private
  helper separated from the public `fetch_*()` entry point.
- `investments/briefs-finance/scripts/score.py` (full file, 300 lines) —
  `score_thesis_against_principle()` (lines 43-60) is the exact pattern for
  `sec_filings.py`'s new LLM summarization call: the `sys.path.insert` reach into
  `.claude/scripts` (lines 14-16) to import `sdk_compat`'s `ClaudeAgentOptions`/
  `run_text`, `asyncio.run(run_text(...))`, `try/except Exception: return <fallback>`
  (never raises). Mirror this exactly rather than reinventing an LLM-call pattern —
  `sec_filings.py` is a new direct caller of `sdk_compat`, same tier as `score.py`, not
  a caller-of-a-caller like `principles_fit.py` (which never imports `sdk_compat`
  itself, only `scripts.score`).
- `investments/my-trader/mytrader/db.py` (full file, 345 lines) — `sync_state` table
  (lines 70-73) and `get_sync_watermark`/`set_sync_watermark` (lines 289-299) are reused
  unmodified for the CIK-map refresh watermark (key
  `"sec_cik_map_refreshed_at"`) — no new watermark-table code needed, this is exactly
  what `sync_state`'s "generic enough for future watermarks" design comment
  (`db.py:70-73`'s originating plan) anticipated. `macro_snapshot_cache` (lines 82-87)
  and `upsert_macro_snapshot`/`get_macro_snapshot` (lines 302-321) are the closest
  existing pattern for a cache table — but note it's a full-overwrite cache (no
  staleness key), whereas the new `sec_filing_cache` needs an accession-number
  staleness check, so it's a new pattern, not a direct reuse. `_ensure_watchlist_return_columns`
  (lines 13-24) is the reference for `init_mytrader_tables`'s additive-migration
  style — the two new tables go in the same `executescript` call
  (lines 27-88) as `CREATE TABLE IF NOT EXISTS`, no `ALTER TABLE` needed since these are
  brand-new tables, not new columns on an existing one.
- `investments/my-trader/mytrader/engine.py` (full file, 137 lines) — `run_assessment()`
  (lines 91-136) calls `principles_fit.check()` at lines 123-127 with the exact
  positional args this plan's `_build_thesis()`/`check()` changes must remain
  compatible with — **this call site does NOT change** (Option A confirmed: the new
  filing-summary lookup happens entirely inside `principles_fit.check()`, gated on the
  `conn` it already receives, not a new parameter threaded through `engine.py`).
- `investments/my-trader/mytrader/config.py` (full file, 177 lines) — existing threshold/
  constant grouping style (e.g. lines 79-176's Phase C macro constants, each with a
  comment explaining its source/confidence) is the pattern for the new `SEC_*` constants
  (Task 1.1). Note the file's `Added <date> --` comment convention for constants added
  after the file's original creation — use it for these too.
- `investments/my-trader/mytrader/main.py` (full file, 325 lines) — `_print_assessment()`
  (lines 20-44) is where a one-line addition surfaces whether a Find result was informed
  by real filing reads (Task 3.3) — mirrors the existing `macro_note` conditional
  construction at line 41.
- `investments/my-trader/mytrader/tickers.py` (full file, 15 lines) — `normalize()`
  (lines 8-10) is reused for CIK-map lookups (uppercases, applies the `BRK.B`→`BRK-B`
  share-class map) — SEC's `company_tickers.json` uses plain uppercase tickers, matching
  `normalize()`'s output for ordinary tickers; note `BRK.B`/`BRK-A` specifically will
  **not** match SEC's ticker convention (SEC lists `BRK-B` under CIK 1067983 the same
  way, so `normalize()`'s existing dash-form output is actually already correct here —
  confirm this against the real bulk file at Task 2.1's validation step, don't assume).
- `investments/my-trader/mytrader/market_data.py` (lines 1-19) — `TickerData` dataclass,
  reused unmodified as the existing `data` parameter type in `principles_fit.check()`;
  no changes needed here, referenced only so the execution agent doesn't confuse this
  with the new filing-summary flow (filing summaries are ticker-string-keyed, not
  `TickerData`-keyed).
- `investments/my-trader/mytrader/tests/test_checks_principles_fit.py` (full file, 139
  lines) — the exact test-extension pattern to mirror (Task 4.2): compare
  `test_thesis_omits_macro_section_when_no_snapshot`/
  `test_thesis_includes_macro_snapshot_when_provided` (lines 84-101) and
  `test_check_reads_macro_snapshot_from_db_conn`/
  `test_check_macro_snapshot_as_of_none_without_conn` (lines 104-139) — the new
  `filing_summaries` parameter needs the identical four-test shape (thesis omits when
  `None`, thesis includes when provided, `check()` calls the new lookup when `conn` is
  given, `check()` skips it when `conn` is `None`).
- `investments/my-trader/mytrader/tests/conftest.py` (full file, 78 lines) — `db_conn`
  fixture (lines 19-26) is reused unmodified for `sec_filings.py`'s tests (needs
  `init_mytrader_tables` to have created the two new tables). Note the three existing
  `autouse=True` fixtures (lines 29-77) that globally stub real network calls
  (backtest refresh, recent-return fetch, crash-drawdown fetch) — **a fourth is needed**
  for this feature (Task 4.1's fixture addition) stubbing
  `mytrader.checks.principles_fit.sec_filings.get_filing_summaries_for_ticker` to
  return `None` by default, for the exact reason documented in this fixture file's own
  comments: without it, every test in the suite that exercises the real
  `principles_fit.check()` (not just this feature's own tests) would silently attempt a
  real SEC EDGAR + LLM call. Add it here, in `conftest.py`, not in
  `test_checks_principles_fit.py` alone, matching the existing three fixtures' global
  scope and stated rationale (`conftest.py:29-44`'s comment explicitly warns about this
  exact class of bug reappearing).
- `investments/my-trader/pyproject.toml` (full file, 30 lines) — `dependencies` list
  (lines 5-12) is where `beautifulsoup4` gets added (Task 1.3); mirrors how
  `openpyxl>=3.1.0` was added for `abs_cpi.py`'s xlsx parsing (line 11) — same
  "new stdlib-adjacent parsing dependency for a new direct-fetch module" shape.
- `investments/my-trader/mytrader/tests/test_macro_indicators.py` — the closest existing
  example (from Phase C) of a test file that monkeypatches an external-fetch helper
  function (`fred_value_on`/`_yfinance_latest_close`) rather than the raw `requests`
  call itself — mirror this shape for `test_sec_filings.py` (monkeypatch
  `mytrader.sec_filings._fetch_filing_index`/`_fetch_filing_document`/`_fetch_cik_map_bulk`,
  never let `requests.get` actually execute in a test).

### New Files to Create

- `investments/my-trader/mytrader/sec_filings.py` — CIK-map cache/lookup, filing-index
  fetch, section extraction (10-K/10-Q Item-header + Part-aware; DEF 14A heading-search),
  LLM summarization, filing-summary cache, and the top-level orchestrator
  `get_filing_summaries_for_ticker(ticker, conn) -> dict[str, str] | None`.
- `investments/my-trader/mytrader/tests/test_sec_filings.py`
- `investments/my-trader/mytrader/tests/fixtures/sec_10k_sample.html` — a real, trimmed
  10-K HTML snippet (Task 3.1) used by the section-extraction tests instead of a live
  fetch. Sourced from one of AMZN/KO/UBER/CPRT's actual filed 10-K during Task 3.1's
  manual step — trim to just enough surrounding Item-header context to exercise the
  extraction logic (a few hundred KB at most, not the full multi-MB original document).
- `investments/my-trader/mytrader/tests/fixtures/sec_10q_sample.html` — same, for the
  Part-aware 10-Q extraction path (needs both Part I and Part II Item headers present to
  exercise the Part-disambiguation logic — pick a fixture where this is verifiably
  correct by hand before trusting the test).
- `investments/my-trader/mytrader/tests/fixtures/sec_def14a_sample.html` — same, for the
  DEF 14A heading-search path.

### Files to Modify

- `investments/my-trader/mytrader/db.py` — add `sec_cik_map` + `sec_filing_cache` tables
  to `init_mytrader_tables`; add `get_cik_for_ticker`, `upsert_cik_map_bulk`,
  `get_cached_filing_summary`, `upsert_filing_summary_cache`.
- `investments/my-trader/mytrader/config.py` — add `SEC_*` constants (Task 1.1).
- `investments/my-trader/mytrader/checks/principles_fit.py` — `_build_thesis()` gains
  `filing_summaries` param; `check()` calls the new lookup; module docstring updated.
- `investments/my-trader/mytrader/main.py` — `_print_assessment()` gains a one-line
  "informed by N SEC filing(s)" note when present.
- `investments/my-trader/pyproject.toml` — add `beautifulsoup4` dependency.
- `investments/my-trader/mytrader/tests/conftest.py` — add the 4th autouse network-stub
  fixture.
- `investments/my-trader/mytrader/tests/test_checks_principles_fit.py` — extend for the
  new parameter/call (Task 4.2).
- `.claude/skills/my-trader/SKILL.md` — document the SEC filing augmentation.

### Relevant Documentation

No new external library documentation needed beyond what the handoff already recorded —
`beautifulsoup4` is a well-known stdlib-adjacent HTML parser already transitively present
in the workspace lockfile (see Feature Metadata), and the three SEC EDGAR endpoints
(ticker→CIK bulk file, per-company submissions JSON, filing document Archive path) are
fully specified with exact URL shapes in
`.agent/plans/sec-filings-principles-fit-handoff.md`'s "Remaining Steps §1" section —
reproduced in the STEP-BY-STEP TASKS below rather than re-fetched, since this plan's
author did not browse live during planning (same caveat the handoff itself states).
**Spot-check the exact URL shapes and JSON structure against a real response at Task
2.1's first validation step** before writing extraction code against assumed structure.

### Patterns to Follow

**Naming Conventions:**
- `snake_case` throughout, matching every existing `mytrader/` module.
- Private fetch helpers prefixed `_fetch_*` (mirrors `abs_cpi.py`'s
  `_fetch_workbook_bytes`, `macro_indicators.py`'s `_yfinance_latest_close`).
- The public orchestrator is a single verb-first function,
  `get_filing_summaries_for_ticker`, matching `candidate_sync.py`'s
  `sync_new_candidates(conn)` shape (one clear entry point, everything else private).

**Error Handling:**
- Every network/parse step degrades to `None`/empty on failure, never raises — matches
  `abs_cpi.py`'s `except Exception: return None` at every layer and
  `macro_indicators.py`'s per-check `"unknown"` verdict convention. A single filing's
  fetch/extract/summarize failure must not prevent the other filing types from still
  being returned — each filing type in `get_filing_summaries_for_ticker`'s loop is
  independently wrapped (see the handoff's own note that this pattern already exists in
  `run_monitor`'s per-row `try/except`, `monitor.py:70-77` — same defensive shape here).
- On a transient fetch/summarize failure where a *stale* cached summary already exists,
  return the stale summary rather than dropping that filing type entirely — a stale
  filing read is still more informative than no filing read, and filing text changes
  infrequently enough that "stale" here likely means "still the same actual filing,"
  not meaningfully wrong.

**DB Pattern:**
- `sec_cik_map (ticker TEXT PRIMARY KEY, cik TEXT NOT NULL)` — a full-resync bulk cache
  (`DELETE FROM sec_cik_map` then re-insert all rows in one transaction on refresh, not
  an incremental upsert — company tickers get delisted/renamed, so a partial upsert
  would accumulate stale rows forever). Refresh gating uses the existing `sync_state`
  table (key `"sec_cik_map_refreshed_at"`), not a new column — matches `sync_state`'s
  documented "generic enough for future watermarks" purpose exactly.
- `sec_filing_cache (ticker TEXT, filing_type TEXT, accession_number TEXT NOT NULL,
  summary TEXT NOT NULL, fetched_at TEXT NOT NULL, PRIMARY KEY (ticker, filing_type))` —
  `INSERT OR REPLACE`, matching `upsert_macro_snapshot`'s idiom (`db.py:302-317`).
  Staleness check is the caller's job (compare `accession_number` to the filing index's
  latest), not baked into the getter — mirrors `candidate_sync.py`'s watermark-comparison
  being done by the caller (`db.get_sync_watermark` returns a raw value, the caller
  decides what to do with it), not the DB layer.

**CIK Formatting Gotcha (real, easy to get backwards):**
- The submissions JSON URL needs a **10-digit zero-padded** CIK:
  `f"{int(cik):010d}"`.
- The Archives document URL needs the **unpadded** CIK (no leading zeros).
- Store the raw CIK value from `company_tickers.json`'s `cik_str` field (already a plain
  int, no padding) in `sec_cik_map`, and apply padding only at the one call site that
  needs it (`_fetch_filing_index`). Getting this backwards produces a 404 that looks like
  "ticker not covered" rather than a formatting bug — worth a defensive comment at both
  call sites pointing at each other.

**Testing Pattern:**
- `tmp_path`-backed SQLite via the existing `db_conn` fixture — never the real shared DB.
- `test_sec_filings.py` monkeypatches the module's own `_fetch_cik_map_bulk`,
  `_fetch_filing_index`, `_fetch_filing_document` functions (never lets real `requests`
  calls execute) and the summarization LLM call (monkeypatch the local
  `_summarize_sections` function, same as `score.py`'s
  `score_thesis_against_principle` gets monkeypatched in
  `test_checks_principles_fit.py:32`) — plus the three saved HTML fixtures for the
  extraction-logic tests specifically (extraction is pure-function text processing, no
  network needed once given fixture HTML).
- `test_checks_principles_fit.py`'s extension monkeypatches
  `mytrader.checks.principles_fit.sec_filings.get_filing_summaries_for_ticker` at the
  `principles_fit` module's own reference to it (confirm the import style —
  `from . import sec_filings` in `checks/__init__.py`'s sibling-module style like
  `from .. import config, db` at `principles_fit.py:44`, or `from ..
  import sec_filings` directly — whichever makes
  `mytrader.checks.principles_fit.sec_filings.<fn>` the correct monkeypatch target;
  verify against the actual import line written in Task 2.2, matching the exact same
  "patch at the importing module's own reference, not the source module" gotcha the
  Phase C plan called out for `monitor.py`'s `macro_indicators`/`candidate_sync`
  imports).

---

## IMPLEMENTATION PLAN

### Phase 1: Foundation (config constants + DB schema)

**Tasks:**
- Add `SEC_*` constants to `config.py`
- Add `sec_cik_map` + `sec_filing_cache` tables and their CRUD functions to `db.py`
- Add `beautifulsoup4` to `pyproject.toml`

### Phase 2: Core Implementation (`sec_filings.py` + `principles_fit.py` wiring)

**Tasks:**
- `sec_filings.py`: CIK resolution, filing-index lookup, document fetch, section
  extraction (10-K/10-Q + DEF 14A), summarization, cache-aware orchestrator
- `checks/principles_fit.py`: `_build_thesis()` + `check()` updated
- `main.py`: one-line transparency note in `_print_assessment()`

### Phase 3: Fixtures + Documentation

**Tasks:**
- Fetch and save 3 real HTML fixtures (10-K, 10-Q, DEF 14A) for extraction tests
- Update `.claude/skills/my-trader/SKILL.md`

### Phase 4: Testing & Validation

**Tasks:**
- Unit tests for `sec_filings.py` (CIK lookup, extraction, cache, orchestration)
- Extended tests for `principles_fit.py`
- New `conftest.py` autouse fixture
- Live validation: real `find` run, sonnet-vs-haiku summarizer comparison, non-US
  ticker degradation check

---

## STEP-BY-STEP TASKS

Execute in order. Each task is atomic and independently testable.

### Task 1.1: UPDATE `investments/my-trader/mytrader/config.py`

- **IMPLEMENT**: Add below the existing constants (after the UK CPI band, end of file):
  ```python
  # Added 2026-08-0X -- SEC EDGAR filing reads for principles_fit's thesis (see
  # .agent/plans/sec-filings-principles-fit.md). SEC_USER_AGENT is a legally-required
  # descriptive header per SEC's fair-access policy -- confirmed with Shaun, do not
  # change without asking (a generic/missing User-Agent can get the IP rate-limited).
  SEC_USER_AGENT = "Shaun Thomson thomoz@outlook.com"
  SEC_CIK_MAP_URL = "https://www.sec.gov/files/company_tickers.json"
  SEC_SUBMISSIONS_URL_TEMPLATE = "https://data.sec.gov/submissions/CIK{cik_padded}.json"
  SEC_ARCHIVES_URL_TEMPLATE = (
      "https://www.sec.gov/Archives/edgar/data/{cik}/{accession_no_dashes}/{document}"
  )
  SEC_CIK_MAP_REFRESH_DAYS = 30  # bulk ticker->CIK file changes rarely; a brand-new
                                   # IPO not yet in a <30-day-old cache is a known,
                                   # accepted gap -- not solved in v1, see NOTES.
  SEC_FILING_TYPES = ("10-K", "10-Q", "DEF 14A")
  SEC_REQUEST_DELAY_SECONDS = 0.2  # small courtesy delay between the handful of
                                     # sequential SEC requests one Find call can make
                                     # (index + up to 3 documents) -- well under SEC's
                                     # stated ~10 req/sec limit, defensive only.
  SEC_FILING_SUMMARY_MODEL = "sonnet"  # best-guess starting default -- compare against
                                         # "haiku" on a real filing at Task 4.3's manual
                                         # validation before treating this as final; see
                                         # NOTES for why "sonnet" was chosen as the
                                         # interim default over "haiku".
  SEC_MAX_SECTION_CHARS = 6000  # per-section cap fed into the summarization prompt --
                                  # mirrors scripts/score.py's own
                                  # file_content[:3000] truncation pattern for the same
                                  # "don't blow the prompt budget" reason.
  SEC_MAX_RAW_DOCUMENT_BYTES = 10_000_000  # guard against a mislinked huge document;
                                              # a 10-K/10-Q/DEF14A primary document is
                                              # never legitimately this large.
  ```
- **PATTERN**: `config.py`'s existing `Added <date> --` constant-block convention (e.g.
  lines 116-131, 133-142).
- **GOTCHA**: Do not reuse briefs-finance's `scripts/config.py` `FRED_SERIES`-style
  dict-of-strings shape for `SEC_FILING_TYPES` — a plain tuple is correct here since
  these are iterated in a fixed, always-all-three order, not looked up by key.
- **VALIDATE**: `uv run --directory investments/my-trader python -c "from mytrader import config; print(config.SEC_USER_AGENT, config.SEC_FILING_TYPES)"`

### Task 1.2: UPDATE `investments/my-trader/mytrader/db.py`

- **IMPLEMENT**: Add to `init_mytrader_tables`'s `executescript` call (after the
  `macro_snapshot_cache` table definition, `db.py:82-87`):
  ```sql
  CREATE TABLE IF NOT EXISTS sec_cik_map (
      ticker          TEXT PRIMARY KEY,
      cik             TEXT NOT NULL
  );
  CREATE TABLE IF NOT EXISTS sec_filing_cache (
      ticker              TEXT NOT NULL,
      filing_type         TEXT NOT NULL,
      accession_number    TEXT NOT NULL,
      summary             TEXT NOT NULL,
      fetched_at          TEXT NOT NULL,
      PRIMARY KEY (ticker, filing_type)
  );
  ```
  Add after `get_macro_snapshot` (after line 321):
  ```python
  def upsert_cik_map_bulk(conn: sqlite3.Connection, ticker_to_cik: dict[str, str]) -> None:
      """Full resync, not incremental -- company tickers get delisted/renamed, so a
      stale row must be able to disappear on refresh, not just accumulate."""
      with conn:
          conn.execute("DELETE FROM sec_cik_map")
          conn.executemany(
              "INSERT INTO sec_cik_map (ticker, cik) VALUES (?, ?)",
              list(ticker_to_cik.items()),
          )


  def get_cik_for_ticker(conn: sqlite3.Connection, ticker: str) -> str | None:
      row = conn.execute("SELECT cik FROM sec_cik_map WHERE ticker = ?", (ticker,)).fetchone()
      return row["cik"] if row else None


  def get_cached_filing_summary(
      conn: sqlite3.Connection, ticker: str, filing_type: str
  ) -> sqlite3.Row | None:
      return conn.execute(
          """SELECT * FROM sec_filing_cache WHERE ticker = ? AND filing_type = ?""",
          (ticker, filing_type),
      ).fetchone()


  def upsert_filing_summary_cache(
      conn: sqlite3.Connection, *, ticker: str, filing_type: str,
      accession_number: str, summary: str,
  ) -> None:
      with conn:
          conn.execute(
              """INSERT OR REPLACE INTO sec_filing_cache
                 (ticker, filing_type, accession_number, summary, fetched_at)
                 VALUES (?, ?, ?, ?, ?)""",
              (ticker, filing_type, accession_number, summary, _now()),
          )
  ```
- **PATTERN**: `upsert_macro_snapshot`/`get_macro_snapshot` (`db.py:302-321`) for the
  cache read/write shape; `get_sync_watermark`/`set_sync_watermark` (`db.py:289-299`,
  unmodified, reused directly) for the CIK-map refresh watermark — no new watermark code
  needed in this file.
- **GOTCHA**: `upsert_cik_map_bulk` takes a plain `dict[str, str]`, not a list of rows —
  the caller (`sec_filings._refresh_cik_map_if_stale`) is responsible for building this
  dict from the parsed JSON; `db.py` stays free of SEC-specific JSON-shape knowledge,
  matching this file's existing "schema + CRUD only" scope (it never parses external
  API responses anywhere else either).
- **VALIDATE**: `uv run --directory investments/my-trader python -m pytest mytrader/tests/test_db.py -v` (extend with new test functions per Task 4.1's DB-layer coverage — mirror `test_db.py`'s existing watermark test shape for the two new getters/setters).

### Task 1.3: UPDATE `investments/my-trader/pyproject.toml`

- **IMPLEMENT**: Add `"beautifulsoup4>=4.12.0",` to the `dependencies` list (after
  `"openpyxl>=3.1.0",`, line 11).
- **PATTERN**: `pyproject.toml:5-12`'s existing dependency-list style.
- **VALIDATE**: `uv sync --directory investments/my-trader --extra dev` then
  `uv run --directory investments/my-trader python -c "import bs4; print(bs4.__version__)"`.

### Task 2.1: CREATE `investments/my-trader/mytrader/sec_filings.py`

- **IMPLEMENT**: Full module (structure below — fill in per the CONTEXT REFERENCES
  patterns above; this is deliberately less line-for-line prescriptive than Phase C's
  plan was, because the exact JSON/HTML shapes must be spot-checked against a real live
  response first, which this planning pass could not do):

  ```python
  """SEC EDGAR filing fetch + extraction + summarization for principles_fit's thesis
  (see .agent/plans/sec-filings-principles-fit.md). Modeled on abs_cpi.py's style:
  direct government-source fetch via requests, no third-party SEC wrapper library,
  explicit User-Agent, graceful None/skip on any failure -- never raises.

  Two independent caches, deliberately different from principles_fit.py's own "never
  cache the thesis" policy documented in that file's module docstring: sec_cik_map
  (bulk ticker->CIK map, refreshed on a >SEC_CIK_MAP_REFRESH_DAYS-stale schedule via the
  existing sync_state watermark table) and sec_filing_cache (per-ticker/filing_type
  summary, invalidated only when a newer accession_number appears -- filing text is
  static between filings, unlike the live stats principles_fit's own thesis is built
  from, so this is a fundamentally different invalidation rule, not an inconsistency).

  Non-US tickers (SEC EDGAR has no ASX/LSE/etc coverage) degrade gracefully via a plain
  CIK-lookup miss -- get_filing_summaries_for_ticker returns None, exactly like
  concentration.py/etf_mechanics.py already handle other missing-data cases.
  """

  from __future__ import annotations

  import asyncio
  import re
  import sqlite3
  import sys
  import time
  from datetime import datetime, timezone
  from pathlib import Path
  from typing import Any

  import requests

  from . import config, db

  _SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent.parent / ".claude" / "scripts"
  sys.path.insert(0, str(_SCRIPTS_DIR))
  from sdk_compat import ClaudeAgentOptions, run_text  # noqa: E402

  _HEADERS = {"User-Agent": config.SEC_USER_AGENT}
  _ITEM_HEADER_RE = re.compile(r"(?:^|\n)\s*item\s+(\d+[a-z]?)\.?\s", re.IGNORECASE)
  _PART_HEADER_RE = re.compile(r"(?:^|\n)\s*part\s+(i{1,3}|iv)\b", re.IGNORECASE)
  _DEF14A_HEADINGS = (
      "compensation discussion and analysis",
      "executive compensation",
      "security ownership of certain beneficial owners",
  )

  # --- CIK resolution -------------------------------------------------------

  def _fetch_cik_map_bulk() -> dict[str, str] | None:
      """GOTCHA: verify at first real run that company_tickers.json's shape is still
      {"0": {"cik_str": <int>, "ticker": <str>, "title": <str>}, "1": {...}, ...} --
      this plan's author could not browse live during planning."""
      try:
          r = requests.get(config.SEC_CIK_MAP_URL, headers=_HEADERS, timeout=30)
          if r.status_code != 200:
              return None
          raw = r.json()
          return {row["ticker"].upper(): str(row["cik_str"]) for row in raw.values()}
      except Exception:
          return None


  def _refresh_cik_map_if_stale(conn: sqlite3.Connection) -> None:
      last = db.get_sync_watermark(conn, "sec_cik_map_refreshed_at")
      if last is not None:
          age_days = (datetime.now(timezone.utc) - datetime.fromisoformat(last)).days
          if age_days < config.SEC_CIK_MAP_REFRESH_DAYS:
              return
      bulk = _fetch_cik_map_bulk()
      if bulk is None:
          return  # keep using whatever's cached (possibly nothing) rather than block
      db.upsert_cik_map_bulk(conn, bulk)
      db.set_sync_watermark(conn, "sec_cik_map_refreshed_at", datetime.now(timezone.utc).isoformat())


  def _get_cik(conn: sqlite3.Connection, ticker: str) -> str | None:
      _refresh_cik_map_if_stale(conn)
      return db.get_cik_for_ticker(conn, ticker)

  # --- Filing index + document fetch ----------------------------------------

  def _fetch_filing_index(cik: str) -> dict[str, Any] | None:
      url = config.SEC_SUBMISSIONS_URL_TEMPLATE.format(cik_padded=f"{int(cik):010d}")
      try:
          r = requests.get(url, headers=_HEADERS, timeout=15)
          if r.status_code != 200:
              return None
          return r.json()
      except Exception:
          return None


  def _latest_filing_entry(index: dict[str, Any], form_type: str) -> dict[str, str] | None:
      recent = index.get("filings", {}).get("recent", {})
      forms = recent.get("form", [])
      for i, form in enumerate(forms):
          if form == form_type:
              return {
                  "accession_number": recent["accessionNumber"][i],
                  "primary_document": recent["primaryDocument"][i],
                  "filing_date": recent["filingDate"][i],
              }
      return None  # GOTCHA: also check index["filings"]["files"] (older filings
                   # paginated out of "recent") if this misses too often in practice --
                   # not implemented in v1, "most recent filing" almost always lands in
                   # the "recent" array; note as a known gap if Task 4.3 finds otherwise.


  def _fetch_filing_document(cik: str, accession_number: str, document: str) -> str | None:
      url = config.SEC_ARCHIVES_URL_TEMPLATE.format(
          cik=str(int(cik)), accession_no_dashes=accession_number.replace("-", ""),
          document=document,
      )
      try:
          r = requests.get(url, headers=_HEADERS, timeout=30)
          if r.status_code != 200 or len(r.content) > config.SEC_MAX_RAW_DOCUMENT_BYTES:
              return None
          return r.text
      except Exception:
          return None

  # --- Section extraction -----------------------------------------------------

  def _strip_html(html: str) -> str:
      from bs4 import BeautifulSoup

      soup = BeautifulSoup(html, "html.parser")
      return soup.get_text(separator="\n")


  def _split_by_item(text: str) -> dict[str, str]:
      matches = list(_ITEM_HEADER_RE.finditer(text))
      items: dict[str, str] = {}
      for i, m in enumerate(matches):
          label = m.group(1).upper()
          if label in items:
              continue  # keep first occurrence only
          end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
          items[label] = text[m.start():end]
      return items


  def _split_by_part(text: str) -> dict[str, str]:
      matches = list(_PART_HEADER_RE.finditer(text))
      if not matches:
          return {"": text}
      parts: dict[str, str] = {}
      for i, m in enumerate(matches):
          label = m.group(1).upper()
          end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
          parts.setdefault(label, text[m.start():end])
      return parts


  def _extract_10k_sections(text: str) -> dict[str, str]:
      items = _split_by_item(text)
      sections = {}
      if "1" in items:
          sections["business"] = items["1"]
      if "1A" in items:
          sections["risk_factors"] = items["1A"]
      if "7" in items:
          sections["mda"] = items["7"]
      return sections


  def _extract_10q_sections(text: str) -> dict[str, str]:
      # GOTCHA (real, specific): 10-Q Item numbers repeat across Part I and Part II with
      # DIFFERENT meanings (Part I Item 2 = MD&A; Part II Item 1A = Risk Factors). Must
      # split by Part FIRST, then find Items within each Part's own substring --
      # splitting by Item across the whole document conflates them.
      parts = _split_by_part(text)
      part1_items = _split_by_item(parts.get("I", ""))
      part2_items = _split_by_item(parts.get("II", ""))
      sections = {}
      if "2" in part1_items:
          sections["mda"] = part1_items["2"]
      if "1A" in part2_items:
          sections["risk_factors"] = part2_items["1A"]
      return sections


  def _extract_def14a_sections(text: str) -> dict[str, str]:
      # No reliable Item-header convention in practice (unlike 10-K/10-Q) -- real proxy
      # statements use free-form section titles. Heading-substring search + a fixed
      # trailing window is a deliberately blunter heuristic than the Item-splitting
      # above; the LLM summarization step is expected to filter noise within the window,
      # not this extraction step. Flag explicitly in NOTES as the plan's biggest
      # remaining technical-risk area -- test against real filings at Task 4.3.
      lower = text.lower()
      sections = {}
      for heading in _DEF14A_HEADINGS:
          idx = lower.find(heading)
          if idx == -1:
              continue
          sections[heading.replace(" ", "_")] = text[idx: idx + 8000]
      return sections


  def _extract_sections(html: str, filing_type: str) -> dict[str, str]:
      text = _strip_html(html)
      if filing_type == "10-K":
          return _extract_10k_sections(text)
      if filing_type == "10-Q":
          return _extract_10q_sections(text)
      if filing_type == "DEF 14A":
          return _extract_def14a_sections(text)
      return {}

  # --- Summarization -----------------------------------------------------------

  _SUMMARY_PROMPT = """\
  You are summarizing part of {ticker}'s {filing_type} SEC filing for an investment \
  analyst. Condense the following into a focused, investment-relevant summary \
  (200-400 words) -- keep material risks, competitive position, and financial \
  trajectory; drop boilerplate legal hedging and repetitive disclaimers.

  {sections_text}

  Return plain text only, no markdown headers.
  """


  def _summarize_sections(ticker: str, filing_type: str, sections: dict[str, str]) -> str | None:
      sections_text = "\n\n".join(
          f"[{name.upper()}]\n{text[:config.SEC_MAX_SECTION_CHARS]}"
          for name, text in sections.items() if text.strip()
      )
      if not sections_text.strip():
          return None
      prompt = _SUMMARY_PROMPT.format(ticker=ticker, filing_type=filing_type, sections_text=sections_text)
      try:
          raw = asyncio.run(run_text(
              prompt=prompt,
              options=ClaudeAgentOptions(allowed_tools=[], model=config.SEC_FILING_SUMMARY_MODEL),
          ))
          return raw.strip() or None
      except Exception:
          return None

  # --- Orchestrator -------------------------------------------------------------

  def get_filing_summaries_for_ticker(ticker: str, conn: sqlite3.Connection) -> dict[str, str] | None:
      cik = _get_cik(conn, ticker.upper())
      if cik is None:
          return None
      index = _fetch_filing_index(cik)
      if index is None:
          return None

      summaries: dict[str, str] = {}
      for filing_type in config.SEC_FILING_TYPES:
          latest = _latest_filing_entry(index, filing_type)
          if latest is None:
              continue
          cached = db.get_cached_filing_summary(conn, ticker, filing_type)
          if cached is not None and cached["accession_number"] == latest["accession_number"]:
              summaries[filing_type] = cached["summary"]
              continue

          html = _fetch_filing_document(cik, latest["accession_number"], latest["primary_document"])
          summary = None
          if html is not None:
              sections = _extract_sections(html, filing_type)
              if sections:
                  summary = _summarize_sections(ticker, filing_type, sections)

          if summary is not None:
              db.upsert_filing_summary_cache(
                  conn, ticker=ticker, filing_type=filing_type,
                  accession_number=latest["accession_number"], summary=summary,
              )
              summaries[filing_type] = summary
          elif cached is not None:
              summaries[filing_type] = cached["summary"]  # stale-but-usable fallback

          time.sleep(config.SEC_REQUEST_DELAY_SECONDS)

      return summaries or None
  ```
- **IMPORTS**: `from sdk_compat import ClaudeAgentOptions, run_text` via the
  `sys.path.insert` reach into `.claude/scripts`, exact same mechanism as
  `briefs-finance/scripts/score.py:14-16` — confirm the relative-path arithmetic
  (`Path(__file__).resolve().parent.parent.parent.parent`) actually lands on
  `.claude/scripts` from `mytrader/sec_filings.py`'s location (4 levels up:
  `sec_filings.py` → `mytrader/` → `my-trader/` → `investments/` → repo root, then
  `/.claude/scripts` — count this carefully, it's one level different from
  `score.py`'s own path since that file lives one directory deeper at
  `briefs-finance/scripts/score.py`).
- **PATTERN**: `abs_cpi.py`'s overall shape (see file header docstring above) and
  `score.py:43-60`'s LLM-call try/except shape.
- **GOTCHA**: See the three inline GOTCHA comments in the code above (10-Q Part/Item
  disambiguation, `_latest_filing_entry`'s `"recent"`-array-only limitation, DEF 14A's
  blunter heuristic) — these are real, not filler; a reviewer should specifically check
  these three areas against Task 3.1's real fixtures.
- **GOTCHA**: `ticker.upper()` is used directly in `get_filing_summaries_for_ticker`
  rather than `tickers.normalize()` — confirm during Task 2.1's validation whether
  SEC's bulk file actually uses `BRK-B`/`BRK.B`/`BRKB` for dual-class tickers (three
  real possibilities) and adjust to call `tickers.normalize()` instead if the dash form
  doesn't match; don't assume without checking a real response.
- **VALIDATE**:
  ```powershell
  uv run --directory investments/my-trader python -c "from mytrader.sec_filings import _fetch_cik_map_bulk; m = _fetch_cik_map_bulk(); print(len(m) if m else 'FAILED', m.get('AAPL') if m else None)"
  uv run --directory investments/my-trader python -c "from mytrader.sec_filings import _fetch_filing_index; print(_fetch_filing_index('320193') is not None)"
  ```

### Task 2.2: UPDATE `investments/my-trader/mytrader/checks/principles_fit.py`

- **IMPLEMENT**: Add `from .. import sec_filings` to imports (line 44 area, alongside
  `from .. import config, db`). Update `_build_thesis()` signature to add
  `filing_summaries: dict[str, str] | None = None` as the last parameter, and append
  before the `return " ".join(parts)` line (after the existing `macro_rows` block,
  around line 97):
  ```python
      if filing_summaries:
          for filing_type, summary in filing_summaries.items():
              parts.append(f"{filing_type} filing highlights: {summary}")
  ```
  Update `check()`: after the existing `macro_rows = db.get_macro_snapshot(conn) if conn is not None else []` line (120), add:
  ```python
      filing_summaries = sec_filings.get_filing_summaries_for_ticker(ticker, conn) if conn is not None else None
  ```
  and pass it into `_build_thesis(...)`'s call (line 121-123) as the new final argument.
  In the `CheckResult` `data=` dict (lines 146-149), add:
  ```python
      "filing_types_used": sorted(filing_summaries) if filing_summaries else [],
  ```
  Update the module docstring (lines 1-37) to add a short paragraph after the existing
  macro-regime paragraph (after line 36) explaining the filing-summary addition and
  explicitly cross-referencing why it uses a *different* cache-invalidation rule than
  this check's own "never cache the thesis" policy (see Solution Statement above for the
  exact wording to adapt).
- **PATTERN**: The existing `macro_rows` parameter's exact addition shape (added last,
  default `None`, conditionally appended) — this task's whole job is to repeat that
  pattern for `filing_summaries`, not invent a new one.
- **GOTCHA**: `get_filing_summaries_for_ticker` makes real network + LLM calls when
  `conn is not None` and the cache misses — every existing test that calls
  `principles_fit.check()` with a real `db_conn` fixture (not just this feature's own
  new tests) will break/hang/hit real APIs unless the new `conftest.py` autouse fixture
  (Task 4.1) is added in the same commit as this change, not after. Sequence Task 4.1
  immediately after this task when executing, don't leave the test suite red in between.
- **VALIDATE**: `uv run --directory investments/my-trader python -m pytest mytrader/tests/test_checks_principles_fit.py -v` (will fail until Task 4.1/4.2 land — expected at this point, don't treat as a regression signal yet).

### Task 3.1: CREATE real filing fixtures (manual/dev step, not automated)

- **IMPLEMENT**: Using the now-working `sec_filings.py` functions directly (e.g. via a
  throwaway `python -c` invocation or scratch script, not committed), fetch one real
  10-K, one real 10-Q, and one real DEF 14A from among AMZN/KO/UBER/CPRT (already
  watchlist/holdings tickers, per the handoff). Save each raw HTML response, then trim
  it down to a fixture-sized file (keep enough surrounding context around the actual
  Item/heading boundaries to exercise the extraction logic meaningfully — a few hundred
  KB, not the multi-MB original) at:
  - `investments/my-trader/mytrader/tests/fixtures/sec_10k_sample.html`
  - `investments/my-trader/mytrader/tests/fixtures/sec_10q_sample.html`
  - `investments/my-trader/mytrader/tests/fixtures/sec_def14a_sample.html`
- **GOTCHA**: Manually verify by eye that `_extract_10k_sections`/`_extract_10q_sections`/
  `_extract_def14a_sections` produce sensible output against these real fixtures before
  writing tests that assert specific extracted content — if the Item-header regex
  doesn't match this filer's actual formatting (real risk flagged in the handoff), fix
  the regex now, against real data, rather than writing a test that just encodes
  whatever the (possibly broken) extraction currently happens to produce.
- **VALIDATE**: Manual read-through of extracted section text for all three fixtures —
  confirm Business/Risk Factors/MD&A (10-K), MD&A/Risk Factors (10-Q, confirm they came
  from the correct Part), and at least one proxy heading (DEF 14A) were located.

### Task 3.2: UPDATE `investments/my-trader/mytrader/main.py`

- **IMPLEMENT**: In `_print_assessment()` (lines 38-44), after the existing
  `macro_note` line, add:
  ```python
      filing_types = principles.data.get("filing_types_used") or []
      if filing_types:
          print(f"  (includes SEC filing read: {', '.join(filing_types)})")
  ```
- **PATTERN**: `main.py:41`'s existing `macro_note` conditional-string construction.
- **VALIDATE**: `uv run --directory investments/my-trader python -m mytrader.main find --ticker KO` — confirm the new line appears when a filing was actually used.

### Task 3.3: UPDATE `.claude/skills/my-trader/SKILL.md`

- **IMPLEMENT**: Add a short "## SEC Filing Reads (principles_fit)" section (after
  wherever `principles_fit`/macro-regime caching is currently documented — grep the file
  for "principles_fit" first to find the right insertion point) summarizing: 10-K/10-Q/
  DEF 14A pulled from SEC EDGAR for US-listed tickers only, folded into the same thesis
  all 9 principle files grade, cached per-filing (only re-fetched on a new accession
  number, not every Find call), non-US tickers degrade silently to stats-only behavior,
  and the summarizer model tier default (note it's `config.SEC_FILING_SUMMARY_MODEL`,
  tunable).
- **PATTERN**: `SKILL.md`'s existing section structure (same file Phase C's plan already
  extended — match that section's density/format).
- **VALIDATE**: Manual read-through — no command executes here.

### Task 4.1: UPDATE `investments/my-trader/mytrader/tests/conftest.py`

- **IMPLEMENT**: Add a fourth `autouse=True` fixture, matching the style/rationale of
  the three that precede it (lines 50-77):
  ```python
  @pytest.fixture(autouse=True)
  def _no_real_sec_filing_fetch(monkeypatch):
      """principles_fit.check() calls sec_filings.get_filing_summaries_for_ticker(),
      which does real SEC EDGAR HTTP + LLM calls when conn is not None -- global/autouse
      for the same reason as the three fixtures above: don't let a real network/LLM
      call hit every test in the suite that exercises the real check by default."""
      monkeypatch.setattr(
          "mytrader.checks.principles_fit.sec_filings.get_filing_summaries_for_ticker",
          lambda ticker, conn: None,
      )
  ```
- **PATTERN**: `conftest.py:63-69` (`_no_real_recent_return_fetch`) — closest existing
  shape (single monkeypatched function, one-line lambda replacement).
- **VALIDATE**: `uv run --directory investments/my-trader python -m pytest mytrader/tests -q` — confirm the full suite (not just this feature's new tests) passes with no real network calls.

### Task 4.2: EXTEND `investments/my-trader/mytrader/tests/test_checks_principles_fit.py`

- **IMPLEMENT**: Add, mirroring the existing macro-snapshot test block (lines 84-139)
  exactly:
  - `test_thesis_omits_filing_section_when_none` — `_build_thesis(..., filing_summaries=None)`, assert `"filing highlights" not in thesis`.
  - `test_thesis_includes_filing_summaries_when_provided` — pass
    `filing_summaries={"10-K": "Strong moat, rising margins."}`, assert both the filing
    type and summary text appear in the thesis.
  - `test_check_calls_filing_lookup_when_conn_given` — monkeypatch
    `mytrader.checks.principles_fit.sec_filings.get_filing_summaries_for_ticker` to a
    function that records it was called and returns a fixed dict; assert the returned
    `CheckResult.data["filing_types_used"]` reflects it.
  - `test_check_skips_filing_lookup_without_conn` — call `check()` with `conn=None`
    (existing pattern, e.g. `test_check_macro_snapshot_as_of_none_without_conn`), assert
    `filing_types_used == []` and that the monkeypatched lookup function (set to raise
    if called) was never invoked.
- **PATTERN**: `test_checks_principles_fit.py:84-139`'s four-test macro-snapshot block —
  this task is structurally the same block, repeated for the new parameter.
- **VALIDATE**: `uv run --directory investments/my-trader python -m pytest mytrader/tests/test_checks_principles_fit.py -v`

### Task 4.3: CREATE `investments/my-trader/mytrader/tests/test_sec_filings.py`

- **IMPLEMENT**:
  - `test_get_cik_returns_none_when_ticker_not_in_map` — seed `db_conn`'s
    `sec_cik_map` with unrelated tickers only (or leave empty + stub
    `_fetch_cik_map_bulk` to return a small fixed dict), assert lookup for e.g. `"BXB"`
    returns `None`.
  - `test_refresh_cik_map_skips_when_fresh` — seed `sync_state`'s watermark to "now",
    monkeypatch `_fetch_cik_map_bulk` to raise if called, assert no exception (i.e. it
    wasn't called).
  - `test_refresh_cik_map_fetches_when_stale_or_missing` — no watermark set, stub
    `_fetch_cik_map_bulk` to return `{"KO": "21344"}`, call `_get_cik`, assert the DB
    now has that row and the watermark was set.
  - `test_split_by_item_10k` — feed `_split_by_item` a small synthetic string with
    `"Item 1. Business... Item 1A. Risk Factors... Item 7. MD&A..."`, assert the three
    keys/text slices come back correctly bounded.
  - `test_split_by_part_and_item_10q_disambiguates_part_i_and_ii` — synthetic string
    with `"PART I ... Item 2. MD&A text ... PART II ... Item 1A. Risk Factors text"`,
    assert `_extract_10q_sections` returns `mda` from the Part I text and
    `risk_factors` from the Part II text specifically (this is the test that would
    catch a regression of the Part-disambiguation gotcha).
  - `test_extract_10k_sections_against_real_fixture` — load
    `fixtures/sec_10k_sample.html`, assert `business`/`risk_factors`/`mda` keys are
    present and non-empty.
  - `test_extract_10q_sections_against_real_fixture` — same, for the 10-Q fixture.
  - `test_extract_def14a_sections_against_real_fixture` — same, for the DEF 14A
    fixture, assert at least one of the three heading keys is present.
  - `test_summarize_sections_returns_none_on_empty_input` — empty `sections` dict,
    assert `None` without calling the LLM.
  - `test_get_filing_summaries_returns_none_for_unmapped_ticker` — stub `_get_cik` (or
    the underlying map) so lookup misses, assert
    `get_filing_summaries_for_ticker` returns `None`.
  - `test_get_filing_summaries_uses_cache_when_accession_unchanged` — seed
    `sec_filing_cache` with a summary + accession number, stub `_fetch_filing_index`/
    `_latest_filing_entry` (via `_fetch_filing_index`'s return shape) so the "latest"
    accession number matches the cached one, monkeypatch `_fetch_filing_document` to
    raise if called, assert the cached summary is returned without a new fetch.
  - `test_get_filing_summaries_refetches_on_new_accession` — cached row has an older
    accession number than what the stubbed index reports as latest; stub
    `_fetch_filing_document`/`_extract_sections`/`_summarize_sections` to return a new
    summary; assert the cache row gets updated and the new summary is returned.
  - `test_get_filing_summaries_falls_back_to_stale_cache_on_fetch_failure` — cached row
    exists, stub `_fetch_filing_document` to return `None` (simulated network failure),
    assert the stale cached summary is still returned rather than that filing type being
    dropped.
- **PATTERN**: `mytrader/tests/test_macro_indicators.py`'s monkeypatch-the-fetch-helper
  shape (never a real `requests` call in any test); `conftest.py`'s `db_conn` fixture
  for every test needing the two new tables.
- **VALIDATE**: `uv run --directory investments/my-trader python -m pytest mytrader/tests/test_sec_filings.py -v`

### Task 4.4: Manual live validation (Shaun-facing checkpoint, not automatable)

- **IMPLEMENT**:
  1. Run the full suite: `uv run --directory investments/my-trader python -m pytest mytrader/tests -q` — must be fully green, including the pre-existing suite (confirm no regression from the new autouse fixture or the `_build_thesis` signature change).
  2. `ruff check` + `mypy` (Level 1, see VALIDATION COMMANDS).
  3. **Sonnet-vs-haiku comparison** (in practice: `gpt-5.4` vs `gpt-5.4-mini` — see the
     "Clarified 2026-08-03" note near the top of this plan; re-verify the live alias
     mapping first with
     `uv run --directory .claude/scripts python -c "import sys; sys.path.insert(0,'.'); from codex_sdk_compat import _MODEL_ALIASES; print(_MODEL_ALIASES)"`
     in case it's drifted since planning): temporarily run
     `get_filing_summaries_for_ticker` for a real ticker (KO recommended — already a
     holding, real 10-K available) once with `config.SEC_FILING_SUMMARY_MODEL` set to
     `"sonnet"` and once to `"haiku"` (bypass the cache between runs, e.g. delete the
     `sec_filing_cache` row between calls, or call `_summarize_sections` directly
     against the same extracted sections for a clean A/B). Print/save both summaries
     side by side and share with Shaun for a real quality judgment — specifically
     whether the cheap tier drops material caveats the mid/strong tier keeps. **Lock in
     `config.SEC_FILING_SUMMARY_MODEL` based on this real comparison** (don't leave the
     plan's `"sonnet"` placeholder default unexamined) and note the outcome + reasoning
     (including which literal model each alias actually resolved to at test time) in
     `handoff.md` or a commit message.
  4. `uv run --directory investments/my-trader python -m mytrader.main find --ticker KO`
     — confirm the "(includes SEC filing read: ...)" line appears, and eyeball the
     resulting principle scores/reasoning for any obvious signal that filing content is
     actually influencing the grading (not just decorative).
  5. Run `find` against a real **non-US** watchlist ticker (e.g. BXB.AX) — confirm no
     crash/exception and that the run completes with `filing_types_used == []`,
     confirming the graceful-degradation path.
  6. Spot-check DEF 14A extraction quality specifically (the plan's biggest flagged
     risk) — read the actual DEF 14A summary produced for at least one real ticker and
     judge whether the heading-search heuristic located genuinely relevant content or
     noise. If it's consistently noise, note this as a known limitation in
     `.claude/skills/my-trader/SKILL.md`'s "Known Limitations" section rather than
     blocking the rest of the feature on perfecting it.
- **VALIDATE**: All of the above are themselves the validation — this task has no
  further downstream check.

---

## TESTING STRATEGY

### Unit Tests
`sec_filings.py`'s pure-function pieces (CIK caching, Item/Part splitting, extraction,
cache orchestration) get full coverage via `pytest` + `monkeypatch`, never hitting real
network/LLM calls (Task 4.3). `principles_fit.py`'s extension gets the same four-test
shape its existing `macro_rows` parameter already has (Task 4.2).

### Integration Tests
None beyond the existing `engine.run_assessment()` → `principles_fit.check()` call path,
which is exercised indirectly by the full `mytrader/tests` suite once the new
`conftest.py` fixture (Task 4.1) is in place — no new integration-test file needed since
`engine.py`'s call site doesn't change.

### Edge Cases
- Non-US ticker (no CIK match) — graceful `None`, no crash.
- CIK map fetch fails entirely (SEC outage) — falls back to whatever's cached, or `None`
  if nothing cached yet; never blocks Find.
- Filing index fetch succeeds but a given filing type (e.g. DEF 14A) has never been
  filed for this CIK, or isn't in the `"recent"` array — that filing type is just
  skipped, others still returned.
- Filing document fetch/parse succeeds but section extraction finds nothing (formatting
  doesn't match the Item-header heuristic) — that filing type skipped, no crash.
- Summarization LLM call fails/times out — falls back to stale cache if present,
  otherwise skipped.
- Cache hit vs. cache miss vs. stale-fallback — all three paths explicitly tested
  (Task 4.3's last three tests).
- 10-Q's Part I/Part II Item-number collision — explicitly tested
  (`test_split_by_part_and_item_10q_disambiguates_part_i_and_ii`).

---

## VALIDATION COMMANDS

### Level 1: Syntax & Style
```powershell
uv run --directory investments/my-trader ruff check mytrader/
uv run --directory investments/my-trader mypy mytrader/sec_filings.py mytrader/checks/principles_fit.py
```

### Level 2: Unit Tests
```powershell
uv run --directory investments/my-trader python -m pytest mytrader/tests -q
```

### Level 3: Integration Tests
Covered by Level 2 (no separate integration suite — see TESTING STRATEGY).

### Level 4: Manual Validation
See Task 4.4 in full — sonnet-vs-haiku comparison, real `find --ticker KO` run, real
non-US ticker degradation check, DEF 14A quality spot-check.

### Level 5: Additional Validation (Optional)
None.

---

## ACCEPTANCE CRITERIA

- [ ] `sec_filings.py` resolves a US ticker to a CIK, fetches its latest 10-K/10-Q/DEF
      14A, extracts relevant sections, and summarizes each via `sdk_compat`
- [ ] Filing summaries are cached per `(ticker, filing_type)`, invalidated only on a new
      accession number — not re-fetched/re-summarized on every Find call
- [ ] `principles_fit.py`'s thesis includes filing highlights when available, and omits
      them cleanly (no crash, no empty section) when not
- [ ] Non-US tickers degrade to today's stats-only behavior with no exception
- [ ] `config.SEC_FILING_SUMMARY_MODEL`'s default has been set based on a real
      sonnet-vs-haiku comparison (Task 4.3), not left as an unexamined placeholder
- [ ] Full `mytrader/tests` suite passes, including the pre-existing suite (no
      regression from the new autouse `conftest.py` fixture)
- [ ] `ruff check` / `mypy` clean on the new/modified files
- [ ] `.claude/skills/my-trader/SKILL.md` documents the new behavior and its known
      limitations (DEF 14A heuristic quality, 30-day CIK-map staleness window)
- [ ] `main.py`'s `find` output visibly indicates when a result was informed by real
      SEC filing reads

---

## COMPLETION CHECKLIST

- [ ] All tasks completed in order (1.1 → 4.4)
- [ ] Each task's own validation command passed before moving to the next
- [ ] Full test suite green, `ruff`/`mypy` clean
- [ ] Task 3.1's three real fixtures committed and manually verified to extract
      sensible content
- [ ] Task 4.4's live validation actually run against real tickers (KO + a real non-US
      watchlist ticker), not skipped
- [ ] `SKILL.md` updated
- [ ] Sonnet-vs-haiku decision made and recorded (not left as the planning-time
      placeholder default)

---

## NOTES

- **Why `"sonnet"` as the interim default over `"haiku"`**: the 9 existing
  principle-grading calls (`score.py`) work fine on `"haiku"` because they're short,
  structured, single-file-vs-thesis comparisons with a fixed JSON output shape.
  Summarizing a real 10-K's Risk Factors section without dropping a materially important
  caveat is a qualitatively harder compression task with no structured-output safety
  net — erring toward the higher-quality tier as the *starting* default (to be
  confirmed or overridden by Task 4.3's real comparison) is the more conservative
  choice given the summary directly feeds 9 downstream grading calls that assume it's
  trustworthy.
- **These tier names are Claude-shaped aliases, not literal model calls.** This repo's
  active agent backend is Codex (`SB_AGENT_BACKEND=codex`, a ChatGPT flat-rate
  subscription — see `CLAUDE.md`'s model-agnostic architecture rule and
  `[[project_codex_backend]]`), so every `"haiku"`/`"sonnet"`/`"opus"` string passed to
  `ClaudeAgentOptions(model=...)` anywhere in this codebase — including
  `scripts/score.py`'s existing 9 principle-grading calls and this plan's new
  `SEC_FILING_SUMMARY_MODEL` — gets remapped by `codex_sdk_compat.py`'s
  `_MODEL_ALIASES` before the call actually goes out. Live-checked at planning time
  (2026-08-03): `"haiku"` → `gpt-5.4-mini`, `"sonnet"` → `gpt-5.4`, `"opus"` → `gpt-5.4`
  (opus and sonnet currently collapse to the same model — no separate strong tier
  configured). So "test sonnet vs haiku" in Task 4.3 really means "test gpt-5.4 vs
  gpt-5.4-mini." This is a naming carryover from when this codebase ran on the native
  Claude Agent SDK — the whole point of `sdk_compat`'s abstraction is that call sites
  never had to change when the backend switched to Codex, so the alias names stayed.
  This mapping is configurable (`CODEX_MODEL_CHEAP`/`CODEX_MODEL_MID`/
  `CODEX_MODEL_STRONG` env vars) and would change entirely if `SB_AGENT_BACKEND` ever
  switches back to `claude` or to `pi` — don't assume this note is still accurate by
  the time Task 4.3 actually runs; re-check the live mapping first (command given in
  Task 4.3 above).
- **DEF 14A extraction is the single biggest technical-risk area in this plan** — unlike
  10-K/10-Q's fairly standardized "Item 1A." convention, real proxy statements use
  free-form section titles with no numbering guarantee. The heading-substring-plus-fixed-
  window heuristic here is deliberately blunt; if Task 4.4's real-filing spot-check shows
  it's consistently pulling noise rather than the compensation/ownership content it's
  meant to, document that as a known limitation rather than trying to perfect it in this
  pass — a degraded-but-present DEF 14A signal alongside solid 10-K/10-Q coverage is
  still net-positive over today's stats-only baseline.
- **CIK-map staleness (30-day refresh window)** means a ticker that IPO'd in the last
  month may not resolve to a CIK yet even though SEC has since added it — accepted gap,
  not solved in v1 (see `config.py`'s `SEC_CIK_MAP_REFRESH_DAYS` comment).
- **`_latest_filing_entry` only checks the `"recent"` array** in the submissions JSON,
  not the paginated `"files"` array SEC uses for companies with a very long filing
  history — in practice "most recent 10-K/10-Q/DEF 14A" should always land in
  `"recent"` (SEC's own docs describe it as covering roughly the last ~1000 filings /
  most recent few years), but this hasn't been verified against a real high-filing-volume
  company during planning. Flag if Task 4.3/4.4 finds a ticker where this misses.
- **Cost/latency**: worst case (all three filing types are cache-misses) is 1 CIK-map
  lookup (usually cached) + 3 filing-index/document fetch pairs + up to 3 LLM
  summarization calls, on top of the 9 existing principle-grading LLM calls
  `principles_fit.check()` already makes. This only happens on a genuinely new filing
  (rare — a few times a year per ticker at most), so the steady-state cost per Find call
  is unchanged (cache hits are just 3 fast DB reads). First-ever Find call for a given
  ticker is the slow path; acceptable since Find is explicitly an on-demand, not
  high-frequency, action.
