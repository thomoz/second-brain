# Feature: ASX Market Announcement Reads for `principles_fit`

The following plan should be complete, but it's important to validate documentation and
codebase patterns and task sanity before implementing. Pay special attention to naming
of existing utils/types/models — import from the right files, mirror the sibling
SEC-filings build exactly where noted.

**Source handoff**: `.agent/plans/asx-market-announcements-handoff.md` — discovery/access-
mechanism research is already complete and confirmed live (2026-08-03). This plan turns
that handoff into an implementation-ready task breakdown. Read the handoff in full before
starting; this plan does not repeat its access-mechanism research, only the resulting
build shape.

## Feature Description

`principles_fit` (`investments/my-trader/mytrader/checks/principles_fit.py`) is Find's
opt-in check that builds a thesis from Find's own live data and grades it against 9
named-investor frameworks. As of 2026-08-03 it already folds in each **US-listed**
ticker's SEC EDGAR 10-K/10-Q/DEF 14A filings via `mytrader/sec_filings.py`. This feature
adds the ASX-listed equivalent: reading each **ASX-listed** ticker's (`.AX` suffix)
Annual Report / Half-Year Report from the ASX Market Announcements Platform (PDF
filings) and folding a summary into the same thesis, so ASX names get primary-source
disclosure context too, not just yfinance-derived ratios.

## User Story

As Shaun, using Find to assess an ASX-listed holding/watchlist ticker (e.g. `BXB.AX`,
`WES.AX`)
I want `principles_fit`'s thesis to include a summary of that company's own latest
Annual Report / Half-Year Report
So that the 9 investor-framework grades reflect what the company itself discloses, not
just derived stats — matching the SEC-filings treatment US tickers already get.

## Problem Statement

SEC EDGAR has no ASX coverage. `sec_filings.get_filing_summaries_for_ticker()` returns
`None` for any `.AX` ticker via a clean CIK-lookup miss (confirmed live) — so ASX-listed
holdings/watchlist rows (`BXB.AX`, `WES.AX` today; more may be added later) never get
the primary-source disclosure layer that US tickers get. They still get the full
yfinance-derived check suite; only the filing-read layer is missing.

## Solution Statement

Add a sibling module, `mytrader/asx_announcements.py`, that mirrors `sec_filings.py`'s
shape exactly (direct-fetch via `requests`, no third-party wrapper, graceful `None` on
any failure, cache-aware orchestrator, one `sdk_compat` LLM summarization call per
document) but swaps SEC EDGAR's HTML fetch for ASX's PDF fetch (via the confirmed
list → interstitial → hidden-field → direct-PDF-URL chain) and BeautifulSoup HTML
extraction for `pdfplumber`/PyMuPDF+OCR PDF extraction (reusing
`briefs-finance/scripts/extract.py`'s proven pattern directly). Wire the result into
`principles_fit._build_thesis()` as a third optional parameter, alongside
`macro_rows` and `filing_summaries`.

## Feature Metadata

**Feature Type**: Enhancement (extends an existing, just-shipped feature to a second
market)
**Estimated Complexity**: Medium — the access-mechanism and PDF-extraction pieces are
already de-risked (per the handoff); the two real unknowns are (1) real ASX report
section-heading conventions (untested against a live fetch) and (2) real announcement
title strings for filtering Annual Report / Half-Year Report out of the full
announcements feed (also untested against a live fetch). Both are flagged as
first-implementation-session tasks below, same as `sec_filings.py`'s DEF 14A heading
work was.
**Primary Systems Affected**: `investments/my-trader/mytrader/` (new module, `db.py`,
`config.py`, `checks/principles_fit.py`, `main.py`, `pyproject.toml`,
`.claude/skills/my-trader/SKILL.md`)
**Dependencies**: `pdfplumber`, `pymupdf`, `pytesseract`, `Pillow` — all already
resolved in the shared `investments/uv.lock` as `briefs-finance` dependencies; just need
adding to `my-trader`'s own `pyproject.toml` dependency list (workspace dependency
already exposes them transitively at runtime, but declare them directly per the
project's explicit-dependency convention — see `sec_filings.py`'s own `beautifulsoup4`
declaration in `my-trader`'s `pyproject.toml`).

---

## CONTEXT REFERENCES

### Relevant Codebase Files — READ THESE BEFORE IMPLEMENTING

- `investments/my-trader/mytrader/sec_filings.py` (full file, 319 lines) — **the exact
  structural pattern to mirror.** Module docstring (lines 1-17) explains the two-cache
  design philosophy — read it, the same reasoning applies here almost verbatim. Key
  functions to mirror 1:1 by shape (not literally, since ASX has no CIK-equivalent
  resolution step — see Task 2.1):
  - `_fetch_cik_map_bulk`/`_refresh_cik_map_if_stale`/`_get_cik` (lines 50-78) — **NOT
    needed for ASX**: the ASX code is just the ticker with `.AX` stripped, no bulk
    ticker→code map or resolution step required. This is a real simplification vs SEC,
    not a gap — flag explicitly in the new module's docstring so a future reader
    doesn't go looking for a missing CIK-equivalent step.
  - `_fetch_filing_index`/`_latest_filing_entry` (lines 83-106) — mirror shape for
    `_fetch_announcements_list`/`_select_target_announcements` (Task 2.2).
  - `_fetch_filing_document` (lines 109-120) — mirror shape for `_resolve_pdf_url` +
    `_fetch_pdf_bytes` (Task 2.3), same `status_code != 200` / size-guard / bare
    `except Exception: return None` pattern.
  - `_strip_html`/`_split_by_item`/`_split_by_part`/`_extract_10k_sections`/
    `_extract_10q_sections` (lines 125-190) — **NOT the pattern to mirror for
    extraction** (that's Item-header-specific to SEC). Instead mirror:
  - `_find_def14a_heading_index`/`_extract_def14a_sections` (lines 193-235) — **this
    IS the pattern to mirror** for ASX section extraction (Task 2.4): free-form
    heading search with TOC-vs-body duplication handling (prefer last ALL-CAPS
    occurrence, fall back to plain rfind), fixed trailing char window per section.
    Read the comment block at lines 193-203 and 218-227 carefully — the exact same
    "biggest technical-risk area, LLM summarization filters window noise, not this
    extraction step" caveat applies to ASX reports, which also have no reliable
    numbered-heading convention.
  - `_summarize_sections`/`_SUMMARY_PROMPT` (lines 250-277) — mirror near-verbatim for
    `_summarize_sections` in the new module (Task 2.5), same `sdk_compat` call shape,
    same truncation-per-section pattern.
  - `get_filing_summaries_for_ticker` (lines 282-318) — **the orchestrator shape to
    mirror exactly** for `get_announcement_summaries_for_ticker` (Task 2.6): per-type
    loop, cache lookup by identity key, stale-fallback-on-fetch-failure, courtesy
    delay between requests, `summaries or None` return.

- `investments/my-trader/mytrader/checks/principles_fit.py` — the integration point.
  - Module docstring lines 38-49 — the exact prose pattern to extend for an ASX
    paragraph (Task 3.1): explain what's added, why the cache policy differs from this
    check's own "never cache the thesis" policy, and how non-ASX/non-US tickers degrade.
  - `_build_thesis()` signature (lines 61-69) and the `filing_summaries` fold-in block
    (lines 113-115) — add a third optional param `asx_summaries: dict[str, str] | None
    = None` and mirror the same `if asx_summaries: for type_, summary in
    asx_summaries.items(): parts.append(...)` block immediately after.
  - `check()` (lines 120-171) — line 139
    (`filing_summaries = sec_filings.get_filing_summaries_for_ticker(ticker, conn) if
    conn is not None else None`) is the exact line to mirror for
    `asx_summaries = asx_announcements.get_announcement_summaries_for_ticker(ticker,
    conn) if conn is not None else None`. Line 169
    (`"filing_types_used": sorted(filing_summaries) if filing_summaries else []`) is
    the exact line to mirror for a new `"asx_announcement_types_used"` data key.
  - Import line 57 (`from .. import config, db, sec_filings`) — add `asx_announcements`
    to this import.

- `investments/my-trader/mytrader/db.py`
  - Lines 82-99 — `macro_snapshot_cache`/`sec_cik_map`/`sec_filing_cache` table
    definitions inside the same `CREATE TABLE IF NOT EXISTS` block (part of
    `init_db()` or equivalent — check the enclosing function name before editing).
    Add a new `asx_announcement_cache` table here (Task 1.2), same
    `(ticker, announcement_type)` composite-PK shape as `sec_filing_cache`'s
    `(ticker, filing_type)`, but with `announcement_id` instead of
    `accession_number` as the change-detection key (the ASX `idsId` is the closest
    analogue to SEC's accession number — a new `idsId` for the same
    ticker+announcement_type means a new report was lodged).
  - Lines 336-371 — `upsert_cik_map_bulk`/`get_cik_for_ticker`/
    `get_cached_filing_summary`/`upsert_filing_summary_cache` — mirror
    `get_cached_filing_summary`/`upsert_filing_summary_cache` exactly (shape only, swap
    `filing_type`→`announcement_type` and `accession_number`→`announcement_id`) for
    `get_cached_asx_summary`/`upsert_asx_summary_cache` (Task 1.3). **No bulk-map
    upsert function needed** — see the CIK-step note above.

- `investments/my-trader/mytrader/config.py`
  - Lines 178-213 — the full `SEC_*` constants block, added 2026-08-03. Mirror this
    block's shape and inline-comment density for a new `ASX_*` block (Task 1.1): every
    constant here has a "why this value" comment; match that density, don't just copy
    values.

- `investments/my-trader/mytrader/tickers.py` (14 lines, full file) —
  `asx_variant(ticker)` appends `.AX`; `normalize(ticker)` upper-cases + share-class
  maps. The new module does the reverse (strip `.AX`) — write a small helper, e.g.
  `_is_asx_ticker(ticker)`/`_bare_asx_code(ticker)`, local to `asx_announcements.py`
  (SEC's module has no equivalent need, so there's nothing to mirror here — just
  confirm `ticker.strip().upper().endswith(".AX")` matches how tickers actually arrive,
  see `market_data.py:66` `tickers.normalize(ticker)` for the upstream normalization
  already applied before checks run).

- `investments/briefs-finance/scripts/extract.py` (64 lines, full file) — **reuse
  `extract_text(pdf_path: Path) -> str` directly**, don't reimplement. It already does
  pdfplumber-first, PyMuPDF+pytesseract-OCR-fallback exactly per the handoff's
  confirmed plan. Import as `from scripts.extract import extract_text` — this exact
  import style (bare `scripts.*`, not `briefs_finance.scripts.*`) already works from
  `my-trader` because `briefs-finance`'s `pyproject.toml` (`[tool.hatch.build.targets.
  wheel] packages = ["scripts"]`) exposes `scripts` as a top-level importable package
  via the uv workspace — confirmed by `principles_fit.py`'s own existing
  `from scripts.config import PRINCIPLES_DIR` / `from scripts.score import
  score_thesis_against_principle` (lines 132-133). `extract_text` takes a `Path`, not
  bytes — write the fetched PDF to a `tempfile.NamedTemporaryFile(suffix=".pdf")`
  before calling it (no existing bytes-in-memory variant to reuse).

- `investments/my-trader/mytrader/main.py` lines 38-47 — the `find` CLI output
  renderer. Lines 45-47 (`filing_types_used` → `(includes SEC filing read: ...)`
  print) is the exact pattern to mirror for a new
  `(includes ASX announcement read: ...)` line (Task 3.2), reading the new
  `asx_announcement_types_used` data key.

- `investments/my-trader/mytrader/tests/test_sec_filings.py` — the exact test-shape to
  mirror for `test_asx_announcements.py` (Task 4.1): fixture-file-based section
  extraction tests (`_FIXTURES = pathlib.Path(__file__).parent / "fixtures"`, line 7),
  cache hit/miss/stale-fallback tests (mirror `test_get_filing_summaries_uses_cache_
  when_accession_unchanged` / `test_get_filing_summaries_refetches_on_new_accession` /
  `test_get_filing_summaries_falls_back_to_stale_cache_on_fetch_failure` — lines 98,
  121, 145), never a live network call in tests.

- `investments/my-trader/mytrader/tests/conftest.py` lines 80-86
  (`_no_real_sec_filing_fetch` autouse fixture, monkeypatches
  `"mytrader.checks.principles_fit.sec_filings.get_filing_summaries_for_ticker"` to
  `lambda ticker, conn: None`) — **add a sibling autouse fixture**
  `_no_real_asx_announcement_fetch` (Task 4.2) monkeypatching
  `"mytrader.checks.principles_fit.asx_announcements.get_announcement_summaries_
  for_ticker"` the same way. Without this, every existing test that exercises the real
  `principles_fit.check()` with a `.AX`-suffixed ticker would start making real network
  calls the moment `asx_announcements` is wired in — same reasoning as the existing
  fixture's docstring.

- `.claude/skills/my-trader/SKILL.md` lines 259-301 (`## SEC Filing Reads
  (principles_fit)` section) — the exact documentation shape/density to mirror for a
  new `## ASX Announcement Reads (principles_fit)` section (Task 3.3): what's added,
  caching behavior, degradation behavior, the CLI transparency-note format, and a
  "Known limitations" sub-list.

- `investments/my-trader/pyproject.toml` (full file, ~25 lines) — `dependencies` list
  (currently includes `beautifulsoup4>=4.12.0`, the SEC module's HTML-parsing dep) is
  where `pdfplumber>=0.11.0`, `pymupdf>=1.24.0`, `pytesseract>=0.3.10`, `Pillow>=10.0.0`
  get added (Task 1.4) — copy exact version pins from
  `investments/briefs-finance/pyproject.toml` lines 6, 12-14 so the shared
  `investments/uv.lock` resolution stays consistent (no new resolution work, per the
  handoff).

### New Files to Create

- `investments/my-trader/mytrader/asx_announcements.py` — the core module (Tasks
  2.1–2.6).
- `investments/my-trader/mytrader/tests/test_asx_announcements.py` — unit tests
  (Task 4.1).
- `investments/my-trader/mytrader/tests/fixtures/asx_announcements_list_BXB.html`,
  `asx_interstitial_BXB.html`, `asx_half_year_report_BXB.pdf` (or similarly named,
  ticker-specific fixture files — see Task 4.3) — real saved fixtures, same convention
  as the existing `tests/fixtures/` dir used by `test_sec_filings.py`.

### Relevant Documentation

- SEC filings sibling build's own plan/handoff pair —
  `.agent/plans/completed/sec-filings-principles-fit-handoff.md` and
  `.agent/plans/completed/sec-filings-principles-fit.md` — read these for the exact
  planning→implementation shape that succeeded last time on this same check, one
  market over. No external library docs are needed beyond what `extract.py` already
  demonstrates (`pdfplumber`/PyMuPDF/pytesseract usage is already proven working code
  in this repo, not something to research fresh).
- ASX Market Announcements Platform access mechanism — fully documented with confirmed
  live URLs and a real downloaded-PDF verification in
  `.agent/plans/asx-market-announcements-handoff.md` (the source handoff for this
  plan) — do not re-research, the mechanism is settled.

### Patterns to Follow

**Module docstring density**: every non-obvious design decision gets a comment
explaining *why*, not *what* — see `sec_filings.py` lines 1-17 and
`principles_fit.py` lines 38-49 as the bar to match.

**Error handling**: every network/parse function returns `None` (or `dict | None`) on
any failure — bare `except Exception: return None`, never raises. Nothing in this
check's call chain should ever throw; `principles_fit.check()` must keep working with
degraded (stats-only) data if any step fails.

**Caching invalidation**: identity-key-based (accession number / announcement id), not
time-based — "invalidate when the underlying document changes," not "invalidate after N
days." Stale-cache-as-fallback-on-fetch-failure is a deliberate feature, not a bug (see
`sec_filings.py` lines 313-314).

**Naming convention**: `ASX_*` prefix for all new `config.py` constants (mirrors
`SEC_*`); `asx_` prefix for new `db.py` table/function names (mirrors `sec_`/`cik`).

**LLM calls**: always through `sdk_compat` (`from sdk_compat import
ClaudeAgentOptions, run_text`, via the `sys.path.insert` shim at
`sec_filings.py` lines 34-36 — copy that exact sys.path-insert block, don't invent a
different import mechanism), never a direct provider SDK import — required by this
project's model-agnostic-runtime rule (see root `CLAUDE.md`).

**Courtesy delay**: `time.sleep(config.ASX_REQUEST_DELAY_SECONDS)` between sequential
requests to the same external host, mirroring `SEC_REQUEST_DELAY_SECONDS`'s reasoning —
the handoff's own caution about the interstitial's Incapsula/Imperva WAF makes this more
important here than for SEC, not less.

---

## IMPLEMENTATION PLAN

### Phase 1: Foundation

Config constants, DB schema/CRUD, and dependency declarations — everything the core
module needs to import, with nothing yet calling out to the network.

**Tasks:**
- Add `ASX_*` constants block to `config.py`
- Add `asx_announcement_cache` table + CRUD to `db.py`
- Add PDF-extraction dependencies to `my-trader`'s `pyproject.toml`

### Phase 2: Core Implementation

The `asx_announcements.py` module itself: list fetch → interstitial resolve → PDF fetch
→ text extract → section extract → summarize → cache-aware orchestrator.

**Tasks:**
- List-announcements fetch + type-filtering
- Interstitial fetch + hidden-field `pdfURL` extraction
- PDF fetch + text extraction (reusing `briefs-finance`'s `extract_text`)
- Section extraction (heading-search heuristic, DEF14A-style)
- LLM summarization (`sdk_compat`, mirrors `_summarize_sections`)
- Orchestrator (`get_announcement_summaries_for_ticker`, cache-aware)

### Phase 3: Integration

Wire the new module into `principles_fit`, the CLI output, and the skill doc.

**Tasks:**
- `principles_fit.py`: third thesis parameter + `check()` call site + `data` key
- `main.py`: CLI transparency-note line
- `SKILL.md`: new documentation section

### Phase 4: Testing & Validation

Fixture capture (one real network round-trip, saved to disk) + fixture-based unit
tests + the autouse test-isolation fixture.

**Tasks:**
- Capture real fixtures against `BXB`/`WES` (per the handoff's confirmed access
  mechanism)
- Unit tests mirroring `test_sec_filings.py`'s shape
- `conftest.py` autouse fixture to block live calls in the rest of the suite

---

## STEP-BY-STEP TASKS

Execute every task in order, top to bottom. Each task is atomic and independently
testable.

### Task 1.1 — ADD `ASX_*` config constants to `config.py`

- **IMPLEMENT**: Add a new block after the existing `SEC_*` block (after line 213),
  with the same "why this value" comment density:
  - `ASX_USER_AGENT` — per the handoff's caution (a real browser UA, not a descriptive
    contact-email UA like `SEC_USER_AGENT` — the WAF concern is different in kind from
    SEC's fair-access policy; comment should say why these two differ, don't reuse
    `SEC_USER_AGENT`)
  - `ASX_ANNOUNCEMENTS_LIST_URL_TEMPLATE = "https://www.asx.com.au/asx/v2/statistics/
    announcements.do?by=asxCode&asxCode={code}&timeframe=Y&year={year}"` (confirmed
    live in the handoff)
  - `ASX_ANNOUNCEMENT_TYPES` — mapping of a stable internal label to a title-substring
    match pattern, e.g. `{"Annual Report": ("annual report",), "Half-Year Report":
    ("half year report", "half-year report", "appendix 4d")}` — **mark this dict with
    a GOTCHA comment**: values are provisional, must be confirmed/corrected against a
    real fetched announcements list (Task 2.1/4.3) before trusting; do not treat these
    strings as verified.
  - `ASX_REQUEST_DELAY_SECONDS = 0.2` (mirror `SEC_REQUEST_DELAY_SECONDS`)
  - `ASX_ANNOUNCEMENT_SUMMARY_MODEL = "sonnet"` — reuse the already-locked-in tier from
    `SEC_FILING_SUMMARY_MODEL` per handoff open-question #4's recommended default;
    comment should note this is a reused default, not a fresh evaluation, and that
    Shaun can override after seeing real ASX-PDF-derived summary quality (PDF text is
    noisier than SEC's clean HTML — flag this uncertainty in the comment, mirroring
    `SEC_FILING_SUMMARY_MODEL`'s own comment density at lines 196-206).
  - `ASX_MAX_SECTION_CHARS = 6000` (mirror `SEC_MAX_SECTION_CHARS`)
  - `ASX_MAX_RAW_PDF_BYTES = 10_000_000` (mirror `SEC_MAX_RAW_DOCUMENT_BYTES`)
  - `ASX_HEADING_CANDIDATES` — tuple of lowercase heading strings to search for during
    section extraction, e.g. `("operating and financial review", "principal risks",
    "directors' report", "review of operations")` — **same GOTCHA as
    `ASX_ANNOUNCEMENT_TYPES`**: provisional, confirm against a real fetched PDF before
    trusting (mirrors `_DEF14A_HEADINGS`' own documented gap in `sec_filings.py` lines
    41-45).
- **PATTERN**: `config.py:178-213` (full `SEC_*` block)
- **GOTCHA**: `ASX_ANNOUNCEMENT_TYPES` and `ASX_HEADING_CANDIDATES` values are
  best-guess until Task 2.1/2.4 are validated against a real live fetch — do not ship
  without that validation step (see Task 4.3).
- **VALIDATE**: `python -c "from mytrader import config; print(config.ASX_ANNOUNCEMENT_TYPES, config.ASX_HEADING_CANDIDATES)"`
  (run from `investments/my-trader/`, or via `uv run --directory investments/my-trader python -c "..."`)

### Task 1.2 — ADD `asx_announcement_cache` table to `db.py`

- **IMPLEMENT**: Add inside the same `CREATE TABLE IF NOT EXISTS` multi-statement block
  as `sec_filing_cache` (after line 99):
  ```sql
  CREATE TABLE IF NOT EXISTS asx_announcement_cache (
      ticker              TEXT NOT NULL,
      announcement_type   TEXT NOT NULL,
      announcement_id     TEXT NOT NULL,
      summary             TEXT NOT NULL,
      fetched_at          TEXT NOT NULL,
      PRIMARY KEY (ticker, announcement_type)
  );
  ```
- **PATTERN**: `db.py:92-99` (`sec_filing_cache` definition, identical shape)
- **IMPORTS**: none new
- **VALIDATE**: run any existing test that calls `db.init_db`/equivalent setup (check
  the function name enclosing the `CREATE TABLE` block first — likely exercised by
  every existing test via `conftest.py`'s `db_conn` fixture) and confirm no SQL error:
  `uv run --directory investments/my-trader pytest mytrader/tests/test_db.py -q`
  (or whichever test file covers schema init — locate via
  `grep -rn "init_db\|CREATE TABLE" mytrader/tests/`)

### Task 1.3 — ADD `get_cached_asx_summary`/`upsert_asx_summary_cache` CRUD to `db.py`

- **IMPLEMENT**: Two functions immediately after `upsert_filing_summary_cache` (after
  line 371):
  ```python
  def get_cached_asx_summary(
      conn: sqlite3.Connection, ticker: str, announcement_type: str
  ) -> sqlite3.Row | None:
      return conn.execute(
          """SELECT * FROM asx_announcement_cache WHERE ticker = ? AND announcement_type = ?""",
          (ticker, announcement_type),
      ).fetchone()


  def upsert_asx_summary_cache(
      conn: sqlite3.Connection, *, ticker: str, announcement_type: str,
      announcement_id: str, summary: str,
  ) -> None:
      with conn:
          conn.execute(
              """INSERT OR REPLACE INTO asx_announcement_cache
                 (ticker, announcement_type, announcement_id, summary, fetched_at)
                 VALUES (?, ?, ?, ?, ?)""",
              (ticker, announcement_type, announcement_id, summary, _now()),
          )
  ```
- **PATTERN**: `db.py:352-371` (`get_cached_filing_summary`/`upsert_filing_summary_cache`,
  identical shape — swap `filing_type`→`announcement_type`,
  `accession_number`→`announcement_id`)
- **IMPORTS**: none new (`_now()` already defined in `db.py`, used throughout)
- **VALIDATE**: `uv run --directory investments/my-trader python -c "
  import sqlite3; from mytrader import db
  conn = sqlite3.connect(':memory:'); conn.row_factory = sqlite3.Row
  db.init_db(conn)  # confirm actual init function name from Task 1.2 first
  db.upsert_asx_summary_cache(conn, ticker='BXB.AX', announcement_type='Annual Report', announcement_id='123', summary='test')
  row = db.get_cached_asx_summary(conn, 'BXB.AX', 'Annual Report')
  assert row['summary'] == 'test'; print('OK')"`

### Task 1.4 — ADD PDF-extraction dependencies to `my-trader`'s `pyproject.toml`

- **IMPLEMENT**: Add to the `dependencies` list:
  `"pdfplumber>=0.11.0"`, `"pymupdf>=1.24.0"`, `"pytesseract>=0.3.10"`,
  `"Pillow>=10.0.0"` — exact same version pins as
  `investments/briefs-finance/pyproject.toml` lines 6, 12-14 (already lock-resolved in
  the shared `investments/uv.lock`, so this should NOT trigger a new resolution).
- **PATTERN**: `investments/my-trader/pyproject.toml` `dependencies` list (currently has
  `beautifulsoup4>=4.12.0` for the SEC module — same slot)
- **GOTCHA**: run `uv sync` (not `uv lock`) after this edit — the versions are already
  resolved in the shared workspace lock, adding a direct dependency on an
  already-locked package should not change the lock file. If `uv sync` unexpectedly
  wants to modify `uv.lock`, stop and investigate before proceeding (version pin
  mismatch vs briefs-finance's own pin, most likely cause).
- **VALIDATE**: `cd investments && uv sync && uv run --directory my-trader python -c "import pdfplumber, fitz, pytesseract, PIL; print('OK')"`

### Task 2.1 — CREATE `asx_announcements.py`: list fetch + type filtering

- **IMPLEMENT**: Module skeleton with docstring (mirror `sec_filings.py`'s docstring
  density — explain the no-CIK-step simplification explicitly, per the note in
  "Relevant Codebase Files" above). Then:
  - `_is_asx_ticker(ticker: str) -> bool` — `ticker.strip().upper().endswith(".AX")`
  - `_bare_asx_code(ticker: str) -> str` — strip the `.AX` suffix
  - `_fetch_announcements_list(code: str, year: int) -> list[dict[str, Any]] | None` —
    GET `config.ASX_ANNOUNCEMENTS_LIST_URL_TEMPLATE.format(code=code, year=year)` with
    `_HEADERS = {"User-Agent": config.ASX_USER_AGENT}`, parse the returned HTML table
    with BeautifulSoup (`from bs4 import BeautifulSoup`, already a `my-trader` dep via
    `sec_filings.py`'s `_strip_html`), extract per-row: title text, date, and the
    `idsId` value out of the `displayAnnouncement.do?display=pdf&idsId={id}` href.
    Return `None` on any non-200/parse failure (mirror `_fetch_filing_index`).
  - `_select_target_announcements(rows: list[dict], types: dict[str, tuple[str,
    ...]]) -> dict[str, dict]` — for each label in `config.ASX_ANNOUNCEMENT_TYPES`,
    find the most recent row whose title (lowercased) contains any of that label's
    match substrings; return `{label: row}` for labels with a match.
- **PATTERN**: `sec_filings.py:83-106` (`_fetch_filing_index`/`_latest_filing_entry`
  shape — list-then-select, same graceful-`None` style)
- **IMPORTS**: `requests`, `bs4.BeautifulSoup`, `from . import config`
- **GOTCHA**: real title strings and table structure are unconfirmed — this task's
  real completion requires the fixture captured in Task 4.3 (a real saved
  `announcements.do` HTML response for `BXB`/`WES`) to write the BeautifulSoup
  selector against actual markup, not guessed markup. Do Task 4.3's fixture capture
  FIRST if implementing this task for real (the plan lists it in Phase 4 for document
  organization, not execution order — see NOTES section).
- **VALIDATE**: `uv run --directory investments/my-trader python -c "
  from mytrader import asx_announcements as a
  rows = a._fetch_announcements_list('BXB', 2026); print(len(rows) if rows else rows)"`
  (real network call, run manually once — not part of the automated test suite)

### Task 2.2 — ADD interstitial fetch + `pdfURL` extraction

- **IMPLEMENT**: `_resolve_pdf_url(ids_id: str) -> str | None` — GET
  `https://www.asx.com.au/asx/v2/statistics/displayAnnouncement.do?display=pdf&idsId=
  {ids_id}` with the same `_HEADERS`, regex-extract the hidden `pdfURL` field value
  from the response HTML (per the handoff's confirmed markup: `<input name="pdfURL"
  value="..." type="hidden">`) — use a compiled regex, not full HTML parsing (mirrors
  `sec_filings.py`'s preference for the lightest tool that works; BeautifulSoup is
  already used for the list page so either is defensible, but regex against a known
  fixed-attribute-order hidden input is simpler here — use your judgment, note the
  choice in a comment either way).
- **PATTERN**: `sec_filings.py:109-120` (`_fetch_filing_document` — same
  status-code/exception-guard shape, different extraction step)
- **GOTCHA**: per the handoff's caution, the interstitial page loads an
  Incapsula/Imperva WAF script tag — a real browser `User-Agent` (already set via
  `ASX_USER_AGENT` in Task 1.1) is required; don't add extra headers beyond that
  without a documented reason, and don't increase request volume beyond one fetch per
  announcement.
- **VALIDATE**: covered by Task 4.1's fixture-based unit test (no live call in
  automated tests); manual live check during implementation:
  `uv run --directory investments/my-trader python -c "
  from mytrader import asx_announcements as a
  print(a._resolve_pdf_url('<real ids_id from Task 2.1's manual run>'))"`

### Task 2.3 — ADD PDF fetch + text extraction

- **IMPLEMENT**:
  - `_fetch_pdf_bytes(url: str) -> bytes | None` — GET the resolved `pdfURL` directly
    (sessionless per the handoff), same `status_code != 200` and
    `len(r.content) > config.ASX_MAX_RAW_PDF_BYTES` guards as
    `_fetch_filing_document`.
  - `_extract_pdf_text(pdf_bytes: bytes) -> str` — write `pdf_bytes` to a
    `tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)`, call
    `scripts.extract.extract_text(Path(tmp.name))`, then delete the temp file in a
    `finally` block (use `tempfile.TemporaryDirectory()` instead if that's cleaner —
    either is fine, just guarantee cleanup even on exception).
- **PATTERN**: `sec_filings.py:109-120` (fetch shape); `briefs-finance/scripts/
  extract.py:50-55` (`extract_text`, reused directly, not reimplemented)
- **IMPORTS**: `tempfile`, `pathlib.Path`, `from scripts.extract import extract_text`
  (see "Relevant Codebase Files" above for why this bare `scripts.*` import resolves)
- **GOTCHA**: `extract_text` takes a `Path`, not bytes/BytesIO — there is no
  in-memory variant in `extract.py` to reuse; don't try to avoid the temp-file step.
- **VALIDATE**: covered by Task 4.1; manual: fetch a real resolved `pdfURL` from Task
  2.2's output and confirm non-empty extracted text.

### Task 2.4 — ADD section extraction (heading-search heuristic)

- **IMPLEMENT**: `_extract_sections(text: str) -> dict[str, str]` — for each heading in
  `config.ASX_HEADING_CANDIDATES`, find the last occurrence (prefer an
  ALL-CAPS/Title-Case heading match over a plain-text mid-sentence mention if
  distinguishable — mirror the caps-preference logic), slice a fixed
  `config.ASX_MAX_SECTION_CHARS`-ish trailing window (mirror `_extract_def14a_
  sections`'s `text[idx: idx + 8000]` pattern, but reuse `ASX_MAX_SECTION_CHARS` for
  the window size rather than hardcoding a new number).
- **PATTERN**: `sec_filings.py:193-235` (`_find_def14a_heading_index`/
  `_extract_def14a_sections` — this is the direct structural mirror, not the
  10-K/10-Q Item-splitting functions)
- **GOTCHA**: **biggest open risk in this task** — `ASX_HEADING_CANDIDATES` (Task 1.1)
  is unvalidated. Before trusting this function, fetch a real BXB or WES Annual
  Report / Half-Year Report PDF (Task 4.3), extract its text (Task 2.3), and manually
  inspect real section headings before finalizing the candidate list — same lesson
  `sec_filings.py`'s own DEF 14A heuristic learned the hard way (see that module's
  comments at lines 193-203, 218-227). Do not skip this validation step even though
  it's not automatable.
- **VALIDATE**: manual inspection against Task 4.3's real fixture text, then
  `uv run --directory investments/my-trader pytest mytrader/tests/test_asx_
  announcements.py::test_extract_sections_against_real_fixture -q` once Task 4.1's
  test exists.

### Task 2.5 — ADD LLM summarization

- **IMPLEMENT**: `_summarize_sections(ticker: str, announcement_type: str, sections:
  dict[str, str]) -> str | None` — near-verbatim mirror of `_summarize_sections`,
  same truncation-per-section pattern, adapted prompt wording (swap "SEC filing" for
  "ASX announcement"/"annual report"), `model=config.ASX_ANNOUNCEMENT_SUMMARY_MODEL`.
- **PATTERN**: `sec_filings.py:250-277` (`_SUMMARY_PROMPT`/`_summarize_sections`,
  including the `sys.path.insert` shim at lines 34-36 for `sdk_compat` import — copy
  that exact block into the new module's imports section)
- **IMPORTS**: `asyncio`; `sdk_compat.ClaudeAgentOptions`, `sdk_compat.run_text` (via
  the sys.path shim, not a direct package import — required by the model-agnostic
  runtime rule)
- **VALIDATE**: `uv run --directory investments/my-trader python -c "
  from mytrader import asx_announcements as a
  print(a._summarize_sections('BXB.AX', 'Annual Report', {'operating_and_financial_review': 'test content ' * 100}))"`

### Task 2.6 — ADD orchestrator `get_announcement_summaries_for_ticker`

- **IMPLEMENT**: `get_announcement_summaries_for_ticker(ticker: str, conn:
  sqlite3.Connection) -> dict[str, str] | None`:
  1. `if not _is_asx_ticker(ticker): return None` (immediate, no network call — this
     is the degradation path for US/other tickers, mirrors SEC's CIK-miss degradation
     but even cheaper since it's a pure string check)
  2. `code = _bare_asx_code(ticker)`
  3. Fetch current-year announcements list (Task 2.1); **consider a previous-year
     fallback** if the current-year list is empty or missing the target types (e.g.
     early January before the new year's first filing) — flag this as a judgment call
     to make during implementation based on what Task 4.3's real fetch shows, not a
     hard requirement.
  4. `_select_target_announcements` → for each matched type: check
     `db.get_cached_asx_summary`; if cached `announcement_id` matches the row's
     `idsId`, reuse; else resolve PDF URL (2.2) → fetch PDF (2.3) → extract sections
     (2.4) → summarize (2.5) → `db.upsert_asx_summary_cache` → `time.sleep(config.
     ASX_REQUEST_DELAY_SECONDS)`.
  5. On any per-type failure, fall back to stale cache if present (mirror
     `sec_filings.py:313-314` exactly).
  6. Return `summaries or None`.
- **PATTERN**: `sec_filings.py:282-318` (`get_filing_summaries_for_ticker` — the
  direct orchestrator template, minus the CIK-resolution step)
- **VALIDATE**: covered by Task 4.1's orchestrator-level tests (cache hit/miss/
  stale-fallback, non-ASX-ticker-returns-None-with-no-network-call).

### Task 3.1 — UPDATE `principles_fit.py`: third thesis parameter

- **IMPLEMENT**:
  - Line 57: `from .. import config, db, sec_filings` → add `asx_announcements`
  - `_build_thesis()` signature (lines 61-69): add
    `asx_summaries: dict[str, str] | None = None` after `filing_summaries`
  - After the `filing_summaries` fold-in block (after line 115):
    ```python
    if asx_summaries:
        for announcement_type, summary in asx_summaries.items():
            parts.append(f"{announcement_type} highlights: {summary}")
    ```
  - `check()` (after line 139):
    ```python
    asx_summaries = asx_announcements.get_announcement_summaries_for_ticker(ticker, conn) if conn is not None else None
    ```
    and thread it into the `_build_thesis(...)` call (line 140-143).
  - `data={...}` dict (after line 169): add
    `"asx_announcement_types_used": sorted(asx_summaries) if asx_summaries else []`
  - Module docstring: add a paragraph after the existing SEC-filings paragraph (lines
    38-49) explaining the ASX addition, mirroring that paragraph's density —
    reference `mytrader/asx_announcements.py` and this plan file.
- **PATTERN**: `principles_fit.py:57, 61-69, 113-115, 120-171` (every line cited
  above is the exact SEC-filings equivalent to mirror)
- **VALIDATE**: `uv run --directory investments/my-trader pytest mytrader/tests/test_principles_fit.py -q`
  (locate exact test filename via `grep -rn "principles_fit" mytrader/tests/` if
  different)

### Task 3.2 — UPDATE `main.py`: CLI transparency note

- **IMPLEMENT**: After line 47 (`print(f"  (includes SEC filing read: ...)")`), add:
  ```python
  asx_types = principles.data.get("asx_announcement_types_used") or []
  if asx_types:
      print(f"  (includes ASX announcement read: {', '.join(asx_types)})")
  ```
- **PATTERN**: `main.py:45-47` (identical shape, new data key)
- **VALIDATE**: manual CLI run against `BXB.AX`:
  `uv run --directory investments/my-trader python -m mytrader.main find BXB.AX`
  (confirm exact CLI invocation shape via `main.py`'s argparse setup if this differs)

### Task 3.3 — UPDATE `SKILL.md`: new documentation section

- **IMPLEMENT**: Add `## ASX Announcement Reads (principles_fit)` section immediately
  after `## SEC Filing Reads (principles_fit)` (after line 301, before `## Briefs
  Finance Candidate Sync` at line 303) — same subsection shape: what's added, caching
  behavior (identity-key on `announcement_id`, stale-fallback), degradation behavior
  (non-`.AX` tickers skip immediately, no network call), CLI transparency-note format,
  "Known limitations" sub-list (heading-search heuristic is provisional/best-effort,
  announcement-type title-matching is provisional, no previous-year-fallback edge case
  if not implemented in Task 2.6).
- **PATTERN**: `.claude/skills/my-trader/SKILL.md:259-301` (full section, structure to
  mirror)
- **VALIDATE**: `python .claude/skills/llm-wiki/scripts/wiki_ops.py lint` is for
  `wiki/`, not skills — no automated validation for SKILL.md; manual read-through for
  consistency with the SEC section's tone/density is the check here.

### Task 4.1 — CREATE `test_asx_announcements.py`

- **IMPLEMENT**: Mirror `test_sec_filings.py`'s test list, adapted:
  - `test_is_asx_ticker_true_for_dot_ax_suffix` / `test_is_asx_ticker_false_for_us_ticker`
  - `test_get_announcement_summaries_returns_none_immediately_for_non_asx_ticker`
    (assert no `requests` call happens — monkeypatch `requests.get` to raise if
    called, confirm it's never hit)
  - `test_fetch_announcements_list_against_real_fixture` (loads the saved HTML fixture
    from Task 4.3, asserts expected rows/types parsed)
  - `test_resolve_pdf_url_against_real_fixture` (loads saved interstitial HTML,
    asserts correct `pdfURL` extracted)
  - `test_extract_sections_against_real_fixture` (loads saved PDF fixture, asserts
    expected headings found — this test is what actually validates Task 2.4's
    heuristic, not just documents it)
  - `test_summarize_sections_returns_none_on_empty_input`
  - `test_get_announcement_summaries_uses_cache_when_announcement_id_unchanged`
  - `test_get_announcement_summaries_refetches_on_new_announcement_id`
  - `test_get_announcement_summaries_falls_back_to_stale_cache_on_fetch_failure`
- **PATTERN**: `test_sec_filings.py` full file (13 existing test functions — mirror the
  fixture-loading convention at line 7, and the cache-behavior tests at lines 98, 121,
  145 especially closely, they're the highest-value tests to get right)
- **VALIDATE**: `uv run --directory investments/my-trader pytest mytrader/tests/test_asx_announcements.py -v`

### Task 4.2 — ADD `_no_real_asx_announcement_fetch` autouse fixture to `conftest.py`

- **IMPLEMENT**: Immediately after `_no_real_sec_filing_fetch` (after line 86):
  ```python
  @pytest.fixture(autouse=True)
  def _no_real_asx_announcement_fetch(monkeypatch):
      """principles_fit.check() calls asx_announcements.get_announcement_summaries_
      for_ticker(), which does real ASX HTTP + LLM calls when conn is not None --
      global/autouse for the same reason as _no_real_sec_filing_fetch above."""
      monkeypatch.setattr(
          "mytrader.checks.principles_fit.asx_announcements.get_announcement_summaries_for_ticker",
          lambda ticker, conn: None,
      )
  ```
- **PATTERN**: `conftest.py:80-86` (`_no_real_sec_filing_fetch`, identical shape)
- **GOTCHA**: this must land in the same PR/commit as Task 3.1 (the `principles_fit.py`
  wiring) — landing Task 3.1 without this fixture will make every existing test that
  exercises `principles_fit.check()` with a `.AX` ticker start making real network+LLM
  calls.
- **VALIDATE**: `uv run --directory investments/my-trader pytest mytrader/tests/ -q`
  (full suite — confirm no test hangs or makes a real network call; watch wall-clock
  time, a network call would visibly slow the suite)

### Task 4.3 — CAPTURE real fixtures against `BXB`/`WES`

- **IMPLEMENT**: One manual, deliberate live round-trip (not automated, not part of
  CI/tests) to populate `mytrader/tests/fixtures/`:
  1. Fetch `ASX_ANNOUNCEMENTS_LIST_URL_TEMPLATE` for `BXB`, current year → save raw
     HTML as `asx_announcements_list_BXB.html`.
  2. From that list, pick a real Annual Report or Half-Year Report row's `idsId`,
     fetch the interstitial → save raw HTML as `asx_interstitial_BXB.html`.
  3. Extract the `pdfURL`, fetch the PDF → save as
     `asx_half_year_report_BXB.pdf` (or matching real title).
  4. Repeat for `WES` if the BXB fixture alone doesn't exercise enough heading
     variety once Task 2.4 is written against it.
  - **This task's real output is validating/correcting Tasks 1.1's
    `ASX_ANNOUNCEMENT_TYPES`/`ASX_HEADING_CANDIDATES` guesses against real markup and
    real headings** — expect to revise those config values after this task, before
    Task 4.1's tests can meaningfully pass.
- **PATTERN**: the handoff's own "CONFIRMED live 2026-08-03" section already did steps
  1-3 manually with `curl`/browser tools during discovery — repeat the same chain,
  this time saving the artifacts as committed test fixtures.
- **GOTCHA**: per the handoff's WAF caution, do this manually and once, not in a
  loop/script that could be mistaken for scraping abuse. Respect
  `ASX_REQUEST_DELAY_SECONDS` even during manual fixture capture.
- **VALIDATE**: fixture files exist and are non-empty:
  `ls -la investments/my-trader/mytrader/tests/fixtures/asx_*`

---

## TESTING STRATEGY

### Unit Tests

Every network/LLM-touching function gets a fixture-based test (real saved HTML/PDF,
never a live call) — mirrors `test_sec_filings.py`'s existing discipline exactly. Cache
behavior (hit/miss/stale-fallback) gets explicit tests using an in-memory
`sqlite3.Connection` per the existing `db_conn` fixture pattern.

### Integration Tests

`principles_fit.check()` called end-to-end with `asx_announcements.get_announcement_
summaries_for_ticker` monkeypatched to a fixed return value (not `None`), asserting the
thesis text and `data["asx_announcement_types_used"]` reflect it — mirror however
`test_principles_fit.py` (or equivalent) currently tests the SEC filing-summaries
fold-in, if such a test exists; add one if it doesn't.

### Edge Cases

- Non-ASX ticker (e.g. `KO`, `BRK-B`) → `get_announcement_summaries_for_ticker` returns
  `None` immediately, zero network calls.
- ASX ticker with no matching Annual/Half-Year Report in the current year's list (e.g.
  early January) → graceful empty/partial result, not an exception.
- Cached `announcement_id` matches latest → no re-fetch, no LLM call.
- Cached `announcement_id` stale (new report lodged) → re-fetch + re-summarize.
- Live re-fetch fails but a stale cache exists → stale summary returned, not dropped.
- PDF is image-based/scanned (older ASX filing) → OCR fallback path in `extract_text`
  exercised, not just the `pdfplumber` primary path.
- No heading in `ASX_HEADING_CANDIDATES` found in extracted text → `_extract_sections`
  returns `{}`, `_summarize_sections` returns `None` for that type, orchestrator
  degrades to whatever other types succeeded (mirrors SEC's per-filing-type
  independence).

---

## VALIDATION COMMANDS

### Level 1: Syntax & Style

```
uv run --directory investments/my-trader ruff check mytrader/asx_announcements.py mytrader/checks/principles_fit.py mytrader/db.py mytrader/config.py mytrader/main.py
uv run --directory investments/my-trader mypy mytrader/asx_announcements.py
```

### Level 2: Unit Tests

```
uv run --directory investments/my-trader pytest mytrader/tests/test_asx_announcements.py -v
```

### Level 3: Integration Tests

```
uv run --directory investments/my-trader pytest mytrader/tests/ -q
```

(full suite — confirms the new autouse fixture (Task 4.2) prevents any regression in
existing tests, and that `principles_fit.py`'s wiring (Task 3.1) doesn't break its
existing test coverage)

### Level 4: Manual Validation

```
uv run --directory investments/my-trader python -m mytrader.main find BXB.AX
uv run --directory investments/my-trader python -m mytrader.main find WES.AX
```

Confirm the `Principles fit` section's output includes a
`(includes ASX announcement read: ...)` line for both, and that the thesis text
(inspect via `--verbose`/data dump if the CLI supports it, or a quick `python -c`
call into `find.lookup_ticker`) contains real Annual/Half-Year Report content, not a
generic fallback string. Also confirm a non-ASX ticker (`find KO`) is unaffected
(no ASX line, no behavior change from before this feature).

### Level 5: Additional Validation

None beyond the above — no external services/MCP servers involved.

---

## ACCEPTANCE CRITERIA

- [ ] `asx_announcements.py` mirrors `sec_filings.py`'s shape and error-handling
      discipline (every network/parse function returns `None` on failure, never raises)
- [ ] Non-ASX tickers degrade with zero network calls (verified by test, not just
      inspection)
- [ ] `principles_fit`'s thesis includes ASX announcement summaries for `.AX` tickers
      when available, unchanged behavior for all other tickers
- [ ] Cache correctly invalidates on new `announcement_id`, correctly reuses on
      unchanged `announcement_id`, correctly falls back to stale cache on fetch failure
- [ ] CLI (`find`) shows the new transparency note for ASX tickers
- [ ] `ASX_ANNOUNCEMENT_TYPES`/`ASX_HEADING_CANDIDATES` have been validated against at
      least one real fetched BXB or WES report, not left as untested guesses
- [ ] Full `my-trader` test suite passes with the new autouse fixture in place, no
      live network/LLM calls triggered by existing tests
- [ ] `SKILL.md` documents the new capability at the same density as the SEC section
- [ ] No regressions to the existing SEC-filings behavior (`filing_types_used`
      note/data key unchanged)

## COMPLETION CHECKLIST

- [ ] All tasks completed in order (Phase 1 → 2 → 3 → 4, with Task 4.3's fixture
      capture pulled forward before Tasks 2.1/2.4 are considered "real" per those
      tasks' own GOTCHA notes)
- [ ] Each task's validation command passed
- [ ] Full test suite passes
- [ ] `ruff`/`mypy` clean on all touched files
- [ ] Manual `find BXB.AX`/`find WES.AX` runs confirmed real filing content in output
- [ ] Acceptance criteria all met
- [ ] `SKILL.md` updated

---

## NOTES

- **Execution order caveat**: Phase 4's Task 4.3 (fixture capture) is listed last for
  document organization, but several earlier tasks (2.1, 2.2, 2.4) explicitly depend
  on it to validate provisional config values and write real selectors against real
  markup — the implementing agent/session should pull Task 4.3 forward and do it
  first, or interleave it with Tasks 2.1-2.4 rather than treating "Phase order" as
  strict execution order. This mirrors how `sec_filings.py` was actually built (per
  its own comments referencing "Task 3.1" real-filing validation work embedded
  throughout the module, not done as a separate final phase).
- **Open questions carried over from the handoff, still unresolved** (surface to Shaun
  before/during implementation if not already answered):
  1. Appendix 4E in scope for v1, or Annual Report + Half-Year Report only? This plan
     assumes the latter (matches the handoff's leaning); `ASX_ANNOUNCEMENT_TYPES` can
     be extended later without a structural change if Shaun wants Appendix 4E added.
  2. `ASX_ANNOUNCEMENT_SUMMARY_MODEL` — this plan defaults to reusing `"sonnet"` (same
     tier as SEC); revisit after seeing real summary quality against noisier
     PDF-extracted text, per Task 1.1's comment.
- **No CIK-equivalent step** is a genuine simplification vs the SEC build, not a
  missing piece — worth stating plainly in the new module's docstring so a future
  reader doesn't go looking for one.
- **Two markets, one check**: `principles_fit` now optionally folds in filing/
  announcement context from up to two independent primary-source pipelines
  (`sec_filings` for US, `asx_announcements` for ASX) — a ticker could theoretically
  be both if this pattern is ever extended to dual-listed names, though none exist in
  the current watchlist/holdings. Both calls in `check()` are independent and
  order-independent; no shared state between them beyond both writing into the same
  `parts` list in `_build_thesis`.
