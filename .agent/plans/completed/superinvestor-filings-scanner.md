# Feature: Superinvestor Fast-Disclosure Filings Scanner

The following plan should be complete, but it is important that you validate documentation and
codebase patterns and task sanity before you start implementing.

Pay special attention to the naming of existing utils, types, and models. Import from the right
files. In particular: `mytrader.sec_filings`, `mytrader.db`, `scripts.db` (this is
briefs-finance's `scripts/` package, re-exported as the shared DB layer), and
`.claude/scripts/notifications.py` (reached via a `sys.path` insert, mirroring
`goat/goat/insider_scan.py:456-460`).

Source handoff: `investments/superinvestor-filings-scanner-handoff.md` (read it in full first —
it carries the regulatory-deadline table and the "why each filing type beats 13F" reasoning that
must be reflected in the report copy).

---

## Feature Description

A daily scanner, keyed on a configurable list of tracked concentrated-value investors (Mohnish
Pabrai / Dalal Street first), that catches their **fast-disclosure** securities filings the day
they appear and fires one grouped WhatsApp alert — instead of waiting up to ~135 days for the
next quarterly 13F.

**v1 (Phases 1-4): US / SEC EDGAR leg only.** Polls each tracked filer's EDGAR submissions feed
for `SC 13D`, `SC 13D/A`, `SC 13G`, `SC 13G/A`, `3`, `4`, `4/A`, `5`, parses the structured
document (Form 3/4/5 XML; Schedule 13D/G structured XML with a cover-page-text fallback),
records each filing in an append-only seen-log, and alerts only on genuinely new filings.

**Phase 5: India / SEBI SAST leg.** Polls the NSE + BSE "System Driven Disclosures (SAST)"
Regulation 29 feeds, name-pattern-matches the acquirer against the tracked investor's alias
list, same seen-log + alert path with `source = 'sast'`. **Phase 5 tasks explicitly require
live verification of the NSE/BSE endpoint URLs and response formats at execution time** — the
research below is a starting point, not confirmed-working infrastructure.

Advisor-notes only. The scanner surfaces a filing; it never trades, never touches the watchlist
or holdings. Same posture as every other tool here (`Memory/SOUL.md`).

## User Story

As Shaun, who tracks a handful of concentrated value investors,
I want a WhatsApp alert the day one of them files a fast-disclosure form (13D/G, Form 3/4/5, or
an Indian SAST Reg 29 disclosure),
So that I learn about their threshold crossings and >10%-owner trades in days, not the ~1-4
months it takes for the information to surface in a 13F.

## Problem Statement

13F filings are due 45 days after quarter-end and are only a point-in-time snapshot, so a trade
made early in a quarter can stay invisible for ~135 days. Certain filings are legally required
far faster (13D: 5 business days after crossing 5%; Form 4: 2 business days for any >10%-owner
trade; SEBI SAST Reg 29: 2 working days for a 5% crossing or any ≥2% change past 5%). Nothing in
the workspace watches a *filer* (as opposed to an *issuer*) for these. `mytrader.sec_filings`
fetches issuer-keyed filings for the `principles_fit` thesis; there is no filer-keyed poll and
no seen-log for one-time disclosure events by a tracked person.

## Solution Statement

A new small package `investments/superinvestor-filings/` (sibling to
`fourteen-crash-signals-daily-check/`), depending on `my-trader` for the EDGAR fetch helpers and
the shared `scripts.db` connection, exactly as `goat` depends on `mytrader.openinsider`.

- **EDGAR leg** — for each tracked investor, for each of their CIKs, fetch
  `data.sec.gov/submissions/CIK{cik}.json` and walk `filings.recent` for the fast-disclosure
  form set within `SUPERINVESTOR_LOOKBACK_DAYS`. For each filing not already in
  `superinvestor_filings_seen`: fetch and parse the primary document, resolve the issuer ticker
  from the issuer CIK via the existing `sec_cik_map` table, insert into the seen-log, build an
  alert line.
- **Dedup / "new"** — `dedup_key = source | filer_key | form_type | issuer | accession`.
  Append-only, `INSERT OR IGNORE`; a filing alerts only on first insert. Mirrors
  `goat.db.insert_goat_insider_filing_seen` exactly.
- **First run** — silent-seed the trailing `SUPERINVESTOR_LOOKBACK_DAYS` (30) into the seen-log
  with no alert (a `sync_state` watermark marks that the first seed has happened), then alert
  only on genuinely new filings after that.
- **Alert** — one grouped WhatsApp digest per run via `.claude/scripts/notifications.py`
  (`send_whatsapp_notification` + `send_toast_notification`), the same pattern as
  `goat.insider_scan.maybe_notify_price_flags`. Plus an overwritten markdown report at
  `investments/superinvestor-filings/superinvestor-filings-report.md`.
- **India leg (Phase 5)** — `sast_monitor.py`, structurally parallel to `edgar_monitor.py`,
  `source = 'sast'`, name-pattern match instead of CIK match.
- **Schedule** — one daily systemd timer at 02:35 UTC (~12:35 AEST) for the EDGAR leg (after
  SEC's 22:00 ET filing cutoff, catching the full prior US day). Phase 5 adds a second timer at
  ~12:30 UTC (~22:30 AEST) for the India leg.

## Feature Metadata

**Feature Type**: New Capability
**Estimated Complexity**: High (Phases 1-4 Medium; Phase 5 High — unverified external feeds)
**Primary Systems Affected**:
- New package `investments/superinvestor-filings/`
- `investments/my-trader/mytrader/sec_filings.py` (2 new pure functions, additive)
- `investments/my-trader/mytrader/db.py` (1 new reverse-lookup helper, additive)
- `investments/my-trader/mytrader/config.py` (SEC archive/index URL constants if not already present)
- `investments/pyproject.toml` (workspace member)
- `scripts/invoke_investments.ps1` (`$PACKAGES` map + `ValidateSet`)
- `scripts/deploy.ps1` (`$TIMERS` list)
- `scripts/systemd/` (new `.service` + `.timer` files)
**Dependencies**: `requests` (already used), `python` stdlib `xml.etree.ElementTree` (Form 3/4/5
+ structured 13D/G parsing), `beautifulsoup4` (already a transitive dep via `mytrader`, used for
the 13D/G cover-page-text fallback). No new third-party packages. **No LLM / `sdk_compat`
dependency** — all parsing is structured, unlike `sec_filings.get_filing_summaries_for_ticker`.

---

## CONTEXT REFERENCES

### Relevant Codebase Files — YOU MUST READ THESE BEFORE IMPLEMENTING

- `investments/superinvestor-filings-scanner-handoff.md` (whole file) — Why: regulatory-deadline
  table, "which events actually beat 13F", explicitly-NOT-scoped list, the 12 open questions and
  their now-resolved answers (see NOTES at the bottom of this plan).
- `investments/my-trader/mytrader/sec_filings.py` (whole file) — Why: the EDGAR fetch layer to
  reuse and extend.
  - `_HEADERS` / `config.SEC_USER_AGENT` (line 38) — compliant User-Agent, already set.
  - `fetch_filing_index(cik)` (lines 83-91) — `GET data.sec.gov/submissions/CIK{cik:010d}.json`,
    returns the filer's recent-filings JSON. **This is the core poll.** Reuse as-is.
  - `latest_filing_entry(index, form_type)` (lines 94-106) — returns only the *first* match of
    one form type. NOT sufficient here (need all recent filings of a *set* of forms). Write a
    sibling `recent_filings_of_types()` — see Task 2.1.
  - `fetch_filing_document(cik, accession_number, document)` (lines 109-120) — pulls one filing
    doc from `www.sec.gov/Archives/...`, guarded by `config.SEC_MAX_RAW_DOCUMENT_BYTES`. Reuse.
  - `edgar_fulltext_search_count(forms, cik=, startdt=, enddt=)` (lines 125-163) — hits
    `efts.sec.gov/LATEST/search-index`, returns only `hits.total.value`. GOTCHA in its docstring:
    `ciks` must be 10-digit zero-padded; never pass a `q=""`. For `resolve-ciks` you need the hit
    *rows*, not the count — write a sibling `edgar_fulltext_search_hits()` (Task 2.2).
  - `get_cik(conn, ticker)` / `_refresh_cik_map_if_stale` (lines 63-79) — bulk `company_tickers.json`
    ticker→CIK map, cached in `sec_cik_map`, refreshed on a `SEC_CIK_MAP_REFRESH_DAYS`-stale
    schedule via the `sync_state` watermark. Call `get_cik` once at the start of a scan to force
    a refresh so the reverse lookup (Task 2.3) sees a populated table.
- `investments/goat/goat/insider_scan.py` (whole file) — Why: the scan-orchestration pattern to
  mirror.
  - `run_holdings_watch` (lines 100-168) — fetch → per-row `build_dedup_key` → `insert_*_seen`
    returns `newly_seen: bool` → if not newly seen `continue` → else build an alert dict. Mirror
    this control flow in `edgar_monitor.scan_edgar()`.
  - `maybe_notify_price_flags` (lines 447-468) — the `sys.path.insert` to reach
    `.claude/scripts/notifications.py`, then `send_toast_notification` + `send_whatsapp_notification`.
    Mirror exactly for `superinvestor_filings.notify.send_digest()`.
  - `_now_sydney_str` (lines 23-29) — report-footer timestamp idiom (`ZoneInfo`).
  - `render_insider_scan_report` / `write_insider_scan_report` (lines 510-678) — report copy
    style: "What this is:" opener, "Advisor notes only ... (see SOUL.md)", "overwritten every
    run", `## Run: {date}` heading, `Last auto-generated: {sydney_str}` footer.
- `investments/goat/goat/db.py` (whole file) — Why: the append-only deduped seen-log to copy.
  - `goat_insider_filings_seen` table DDL (lines 42-53) + the idempotent `ALTER TABLE ... ADD
    COLUMN` / `except sqlite3.OperationalError: pass` migration idiom (lines 71-115).
  - `insert_goat_insider_filing_seen` (lines 224-241) — `INSERT OR IGNORE ... RETURNING
    cur.rowcount == 1`. Copy this signature shape for `insert_superinvestor_filing_seen`.
  - `get_recent_insider_filings_seen` (lines 244-254), `get_macro_state` / `set_macro_state`
    (lines 282-297) — generic key/value state store idiom (use `sync_state` instead here, since
    `mytrader.db` already exposes `get_sync_watermark` / `set_sync_watermark`).
- `investments/goat/goat/main.py` (whole file) — Why: the `_open_conn()` layering pattern
  (lines 8-19: `init_db(DB_PATH)` → `get_connection` → `init_mytrader_tables` →
  `init_goat_tables`) and the `argparse` subcommand + `dispatch` dict structure (lines 235-296).
- `investments/fourteen-crash-signals-daily-check/main.py` (whole file) — Why: the closest
  structural sibling — same `_open_conn` layering (lines 8-22), same `argparse` shape, its
  `pyproject.toml` (`my-trader` + `goat` workspace deps, `hatchling`, `testpaths`) is the exact
  template for the new package's `pyproject.toml`.
- `investments/fourteen-crash-signals-daily-check/pyproject.toml` — Why: copy verbatim, change
  `name`, drop the `goat` dep (not needed), keep `my-trader`.
- `investments/goat/goat/tests/conftest.py` (whole file) — Why: the `db_path` / `db_conn`
  fixtures (`init_db` → `get_connection` → `init_mytrader_tables` → package tables) and the
  autouse network-stub fixture pattern. Copy into
  `investments/superinvestor-filings/superinvestor_filings/tests/conftest.py`.
- `investments/goat/goat/tests/test_insider_scan.py` (lines 1-60) — Why: test style —
  `monkeypatch.setattr("<module path>.<fetch fn>", lambda ...: [row])`, row-dict builders,
  assert on `result["new_alerts"]`.
- `investments/my-trader/mytrader/tests/test_sec_filings.py` (lines 1-70) — Why: how EDGAR fetch
  functions are unit-tested (monkeypatch `_fetch_cik_map_bulk`, fixture HTML files under
  `tests/fixtures/`, `_split_by_*` pure-function tests).
- `investments/my-trader/mytrader/openinsider.py` `build_dedup_key` (lines 210-218) — Why: the
  `"|".join([...])` dedup-key construction idiom.
- `scripts/systemd/second-brain-goat-insider-scan.service` + `.timer` — Why: exact templates.
  `Type=oneshot`, `User=secondbrain`, `WorkingDirectory=.../investments/goat`,
  `ExecStart=.../investments/.venv/bin/python -m goat.main scan-insiders`,
  `StandardOutput=append:.../<pkg>/<name>_runs.log`. Timer: `OnCalendar=*-*-* HH:MM:SS UTC`,
  `Persistent=true`, `WantedBy=timers.target`.
- `scripts/invoke_investments.ps1` (whole file) — Why: the `$PACKAGES` hashtable
  (`Dir` + `Module`), the `ValidateSet` on `-Package`, and the VPS-only-DB warning. Add a
  `superinvestor-filings` entry.
- `scripts/deploy.ps1` (lines 17-27) — Why: the `$TIMERS` array that gets stopped/started around
  a deploy. Add the new timer(s).
- `scripts/setup_vps.sh` (lines 45-58) — Why: shows systemd units are installed by
  `sudo cp scripts/systemd/*.{service,timer} /etc/systemd/system/ && sudo systemctl daemon-reload`
  then `enable --now`. `deploy.ps1` does NOT do this — it is a manual step (documented in
  MEMORY.md: "systemd unit deploys often need manual sudo cp"). Capture it as a handoff task.
- `Memory/SOUL.md` — Why: "Never modify financial account state", advisor-only, the exact
  wording the report disclaimer echoes.

### New Files to Create

```
investments/superinvestor-filings/
├── pyproject.toml
└── superinvestor_filings/
    ├── __init__.py
    ├── config.py                 — SUPERINVESTOR_TRACKED, form set, lookback, paths
    ├── db.py                     — superinvestor_filings_seen table + CRUD
    ├── edgar_monitor.py          — the US leg: poll submissions, dedup, build alerts
    ├── edgar_parse.py            — Form 3/4/5 XML + Schedule 13D/G structured-XML/text parsers
    ├── issuer_lookup.py          — issuer CIK → ticker (thin wrapper over mytrader.db)
    ├── report.py                 — render + write the markdown report
    ├── notify.py                 — grouped WhatsApp/toast digest
    ├── sast_monitor.py           — Phase 5: the India SEBI SAST leg
    ├── main.py                   — argparse CLI: scan | scan --edgar-only | scan --india-only | resolve-ciks
    └── tests/
        ├── __init__.py
        ├── conftest.py
        ├── fixtures/
        │   ├── submissions_dalal_street.json
        │   ├── form4_sample.xml
        │   ├── sc13g_structured_sample.xml
        │   ├── sc13g_text_sample.htm
        │   └── nse_sast_sample.csv          (Phase 5)
        ├── test_config.py
        ├── test_db.py
        ├── test_edgar_parse.py
        ├── test_edgar_monitor.py
        ├── test_issuer_lookup.py
        ├── test_report.py
        ├── test_notify.py
        └── test_sast_monitor.py             (Phase 5)

scripts/systemd/second-brain-superinvestor-edgar.service
scripts/systemd/second-brain-superinvestor-edgar.timer
scripts/systemd/second-brain-superinvestor-sast.service      (Phase 5)
scripts/systemd/second-brain-superinvestor-sast.timer        (Phase 5)
```

### Files to Modify

- `investments/my-trader/mytrader/sec_filings.py` — ADD `recent_filings_of_types()`,
  `edgar_fulltext_search_hits()`, `fetch_filing_directory_index()` (all pure, additive, no
  change to existing functions).
- `investments/my-trader/mytrader/db.py` — ADD `get_ticker_for_cik(conn, cik)` next to
  `get_cik_for_ticker` (line 461).
- `investments/my-trader/mytrader/config.py` — verify `SEC_ARCHIVES_URL_TEMPLATE` exists (it is
  referenced at `sec_filings.py:110`); ADD `SEC_SUBMISSIONS_URL_TEMPLATE` check (referenced at
  `sec_filings.py:84`). If either is missing, add it. ADD `SEC_ARCHIVES_DIR_URL_TEMPLATE` for
  the filing-directory `index.json` (Task 2.4).
- `investments/pyproject.toml` — add `"superinvestor-filings"` to `[tool.uv.workspace] members`.
- `scripts/invoke_investments.ps1` — add to `ValidateSet` and `$PACKAGES`.
- `scripts/deploy.ps1` — add timer name(s) to `$TIMERS`.

### Relevant Documentation — READ THESE BEFORE IMPLEMENTING

- SEC EDGAR submissions API — https://www.sec.gov/search-filings/edgar-application-programming-interfaces
  - Section: "data.sec.gov/submissions/" — `GET https://data.sec.gov/submissions/CIK##########.json`,
    CIK zero-padded to 10 digits, `filings.recent` is **columnar** (each field is a parallel
    array: `form[]`, `accessionNumber[]`, `filingDate[]`, `primaryDocument[]`,
    `primaryDocDescription[]`, `acceptanceDateTime[]`, `reportDate[]`). `filings.recent` holds
    ≥1 year or ≥1000 filings; older pages are in `filings.files[]` (NOT needed for a daily poll).
  - Why: this is the core per-filer poll. `fetch_filing_index` already implements the GET; you
    just need to walk the columnar arrays.
- SEC EDGAR full-text search (`efts.sec.gov/LATEST/search-index`) —
  https://tldrfiling.com/blog/sec-edgar-full-text-search-api and the existing docstring at
  `sec_filings.py:125-147`.
  - Params: `forms` (comma-sep), `startdt`/`enddt` (`YYYY-MM-DD`), `from`/`size` (pagination,
    `size` max 100), `q` (omit entirely — a `q=""` returns wrong totals). The existing code also
    passes `ciks` (10-digit zero-padded) and it works live. `entityName` is also accepted.
  - Response: `hits.total.value` (int), `hits.hits[]` each with `_id`
    (`"0001234567-24-001234:doc.htm"` — accession + filename) and `_source` keys:
    `file_date`, `form_type`, `display_names` (list like `["Dalal Street, LLC (CIK 0001549575)"]`),
    `file_num`, `film_num`, `ciks` (list). **VALIDATE the exact `_source` key names live** — the
    blog and the SEC's own UI disagree on `entity_name` vs `display_names`.
  - Rate limit: 10 req/s across all EDGAR hosts; UA header required
    (`config.SEC_USER_AGENT` = `"Shaun Thomson thomoz@outlook.com"` already conforms).
  - Why: `resolve-ciks` uses this to surface fund-entity CIKs by name for manual review.
- SEC Forms 3/4/5 XML (ownership) — the primary document for a `4` filing is an
  `ownershipDocument` XML. Key paths: `issuer/issuerCik`, `issuer/issuerName`,
  `issuer/issuerTradingSymbol` (**gives the ticker directly — no lookup needed for Form 4**),
  `reportingOwner/reportingOwnerId/rptOwnerName` + `.../rptOwnerCik`,
  `reportingOwner/reportingOwnerRelationship/isTenPercentOwner`,
  `nonDerivativeTable/nonDerivativeTransaction/` → `transactionDate/value`,
  `transactionCoding/transactionCode` (`P`=buy, `S`=sell, `A`=grant, `M`=exercise, `G`=gift,
  `F`=tax), `transactionAmounts/transactionShares/value`,
  `transactionAmounts/transactionPricePerShare/value`,
  `postTransactionAmounts/sharesOwnedFollowingTransaction/value`.
  - Why: full transaction-by-transaction parse (Shaun's confirmed choice — the XML is clean and
    the detail is the point).
- SEC Schedule 13D/13G structured XML — the SEC moved 13D/G to a structured (XML) submission
  format effective **December 18, 2024** (older filings are cover-page HTML/txt only). The
  structured filing exposes the subject-company CIK/name, CUSIP, and the "Aggregate Amount
  Beneficially Owned" / "Percent of Class" boxes as tagged fields.
  - Why: parse the structured XML when present (`filingDate >= 2024-12-18` heuristic — but
    detect by document type, not date); fall back to a targeted regex on the stripped cover-page
    text (`strip_html` already exists at `sec_filings.py:168`) for older `/A` filings that amend
    a pre-2024 13D/G.
  - **VALIDATE the exact structured-13D/G XML schema live** against a real recent Dalal Street
    `SC 13G` (CIK `0001549575` has them) — the SEC's EDGAR technical spec for this is the
    authority, not a blog.
- SEBI SAST Regulation 29 (Phase 5) — https://www.sebi.gov.in (SAST Regulations 2011, Reg 29(1)
  = 5% crossing within 2 working days; Reg 29(2) = every ≥2% change past 5% within 2 working
  days). Feed candidates to verify live:
  - NSE: `https://www.nseindia.com/companies-listing/corporate-filings-insider-trading`
    ("System Driven Disclosures (SAST)" — has a CSV download; NSE requires priming the session
    with a `GET https://www.nseindia.com` first to obtain cookies, then reusing that
    `requests.Session`).
  - BSE: `https://www.bseindia.com/corporates/Regulation_29.aspx` and
    `https://www.bseindia.com/corporates/Sast.html`.
  - Why: Pabrai's largest positions have historically been Indian (via the FPI route) and never
    touch EDGAR. **Phase 5 Task 5.1 is a spike: confirm a working, no-login, machine-readable
    endpoint before writing the parser.**

### Patterns to Follow

**Package layout / dependency direction** — new package depends on `my-trader` (workspace dep),
never the reverse. Mirror `fourteen-crash-signals-daily-check/pyproject.toml`:

```toml
[project]
name = "superinvestor-filings"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = ["my-trader", "requests>=2.31.0"]

[tool.uv.sources]
my-trader = { workspace = true }

[project.optional-dependencies]
dev = ["pytest>=8.0.0", "pytest-mock>=3.12.0", "ruff>=0.2.0", "mypy>=1.8.0"]

[tool.pytest.ini_options]
testpaths = ["superinvestor_filings/tests"]
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
packages = ["superinvestor_filings"]
```

**DB connection layering** (`main._open_conn`, mirror `goat/main.py:8-19`):

```python
def _open_conn():
    from scripts.db import get_connection, init_db
    from mytrader.db import init_mytrader_tables
    from .config import DB_PATH
    from .db import init_superinvestor_tables

    init_db(DB_PATH)
    conn = get_connection(DB_PATH)
    init_mytrader_tables(conn)          # sec_cik_map + sync_state
    init_superinvestor_tables(conn)
    return conn
```

**Config path constants** (mirror `goat/config.py:1-10`):

```python
from pathlib import Path
from scripts.config import DB_PATH  # noqa: F401  re-exported for callers

PKG_DIR = Path(__file__).resolve().parent.parent   # -> investments/superinvestor-filings
SUPERINVESTOR_REPORT_PATH = PKG_DIR / "superinvestor-filings-report.md"
```

**Seen-log table** (mirror `goat/db.py:42-53` + the `ALTER TABLE ... except OperationalError`
migration idiom for any future column):

```python
CREATE TABLE IF NOT EXISTS superinvestor_filings_seen (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    dedup_key         TEXT NOT NULL UNIQUE,
    source            TEXT NOT NULL,          -- 'edgar' | 'sast'
    filer_key         TEXT NOT NULL,          -- e.g. 'pabrai'
    filer_display     TEXT NOT NULL,
    form_type         TEXT NOT NULL,          -- 'SC 13G', '4', 'SAST Reg 29(2)', ...
    issuer            TEXT NOT NULL,
    issuer_ticker     TEXT,
    accession         TEXT,                   -- EDGAR accession / exchange ref
    event_date        TEXT,                   -- transaction / acquisition date
    filed_date        TEXT,
    shares            REAL,
    pct_owned         REAL,
    pct_owned_change  REAL,
    material_crossing TEXT,                   -- '5% cross' | '10% cross' | 'below 5%' | NULL
    transaction_code  TEXT,                   -- P/S/A/M/G/F for Form 4; NULL otherwise
    raw_url           TEXT,
    first_seen_at     TEXT NOT NULL
);
```

`insert_superinvestor_filing_seen(...) -> bool` — `INSERT OR IGNORE`, `return cur.rowcount == 1`
(mirror `goat/db.py:224-241`).

**Dedup key** (mirror `openinsider.build_dedup_key`):
```python
def build_dedup_key(source, filer_key, form_type, issuer, accession) -> str:
    return "|".join([source, filer_key, form_type, issuer or "", accession or ""])
```

**Notification** (mirror `goat/insider_scan.py:447-468`):
```python
import sys
from pathlib import Path
_scripts_dir = Path(__file__).resolve().parent.parent.parent.parent / ".claude" / "scripts"
sys.path.insert(0, str(_scripts_dir))
from notifications import send_toast_notification, send_whatsapp_notification
```
(`.parent` × 4 from `investments/superinvestor-filings/superinvestor_filings/notify.py` →
repo root. Verify the depth: `notify.py`→`superinvestor_filings`→`superinvestor-filings`→
`investments`→repo root. That is `.parent` × 4. Same as goat.)

**Error handling** — every network fetch: `try/except Exception: return None`, never raise
(mirror `sec_filings.py` module docstring + every function in it). A `None` from a fetch means
"unknown, skip this filer this run", logged with a `print("[superinvestor-scan] ...")` line
(mirror `goat/insider_scan.py:112`), never an alert.

**Report copy** — mirror `goat/insider_scan.render_insider_scan_report`: "What this is:"
opener, "Auto-generated ... overwritten every run. Advisor notes only; no trade action is ever
suggested here (see SOUL.md).", `## Run: {date}`, `Last auto-generated: {sydney_str}.` footer.

**Timezone** — `ZoneInfo("Australia/Sydney")` for the report footer (mirror
`goat/insider_scan.py:23-29`). Filing dates from EDGAR are US Eastern calendar dates — store
them verbatim as `YYYY-MM-DD` strings, do not convert.

**Anti-patterns to avoid**:
- Do NOT run this via `uv run --directory investments/superinvestor-filings ...` locally — that
  creates a fresh empty local `investments.db` (see `invoke_investments.ps1` header comment).
  All real runs go through `invoke_investments.ps1` against the VPS.
- Do NOT reuse `goat_alert_history` / `alert_history` — a one-time disclosure event does not fit
  that table's open/acknowledge semantics (same reasoning as
  `goat/insider_scan.py:1-7` NOTES). Dedup is the seen-log only.
- Do NOT add an LLM summarization step. Structured parse only.
- Do NOT auto-add issuers to any watchlist/holdings table. Report + alert only.
- Do NOT convert `latest_filing_entry` — leave it; add a sibling.
- Do NOT hardcode `2024-12-18` as the 13D/G-structured cutoff in a comparison — detect the
  document format (is there an XML primary doc / a `<edgarSubmission>` root?), fall back to text.

---

## IMPLEMENTATION PLAN

### Phase 1: Foundation — package scaffold, config, DB

Create the package skeleton, the tracked-investor config with the six resolved Pabrai/Dalal
Street CIKs, and the `superinvestor_filings_seen` table + CRUD. No network code yet.

**Tasks:**
- `pyproject.toml` from the template above; add to workspace members; `uv sync`.
- `config.py` — `SUPERINVESTOR_TRACKED`, `SUPERINVESTOR_EDGAR_FORMS`,
  `SUPERINVESTOR_LOOKBACK_DAYS = 30`, report path, `SUPERINVESTOR_FIRST_SEED_WATERMARK` key name.
- `db.py` — `init_superinvestor_tables`, `insert_superinvestor_filing_seen`,
  `get_recent_superinvestor_filings_seen`, `count_seen`.
- `tests/conftest.py` + `test_config.py` + `test_db.py`.

### Phase 2: EDGAR fetch layer (in `mytrader.sec_filings`, additive)

Add the pure fetch/parse-free functions to `mytrader.sec_filings` so they sit next to
`fetch_filing_index` and are unit-tested by that module's existing suite too.

**Tasks:**
- `recent_filings_of_types(index, forms: set[str], since: date) -> list[dict]` — walk the
  columnar `filings.recent`, return `[{form, accession_number, primary_document,
  primary_doc_description, filing_date, acceptance_datetime}]` for every entry whose `form` is in
  `forms` and whose `filingDate >= since`.
- `edgar_fulltext_search_hits(forms, *, entity_name=None, cik=None, startdt=None, enddt=None,
  size=100) -> list[dict] | None` — sibling of `edgar_fulltext_search_count`; return
  `hits.hits[]` mapped to `{accession, form_type, file_date, display_names, ciks, raw_url}`.
- `fetch_filing_directory_index(cik, accession_number) -> dict | None` — `GET
  www.sec.gov/Archives/edgar/data/{cik}/{accession_nodash}/index.json`, returns the
  `directory.item[]` list so a parser can find the real `.xml` when `primaryDocument` is the
  rendered `xslF345X03/...htm` wrapper rather than the raw XML.
- `mytrader/db.py`: `get_ticker_for_cik(conn, cik) -> str | None` —
  `SELECT ticker FROM sec_cik_map WHERE cik = ? LIMIT 1` (dual-class → first row is fine).
- `mytrader/config.py`: verify/add `SEC_SUBMISSIONS_URL_TEMPLATE`, `SEC_ARCHIVES_URL_TEMPLATE`,
  add `SEC_ARCHIVES_DIR_URL_TEMPLATE`.

### Phase 3: Parsers (`edgar_parse.py`, `issuer_lookup.py`)

**Tasks:**
- `parse_ownership_form(xml_text: str) -> dict | None` — Forms 3/4/5. Return
  `{issuer_name, issuer_cik, issuer_ticker, owner_name, owner_cik, is_ten_pct_owner,
  transactions: [{code, date, shares, price, shares_owned_after}]}`. Skip codes not in
  `{P, S}` for the *alert headline* but still record the filing.
- `parse_schedule_13dg(doc_text: str) -> dict | None` — try structured XML first
  (`xml.etree.ElementTree`, detect `<edgarSubmission>` / ownership-schedule root), else regex
  fallback on `sec_filings.strip_html(doc_text)` for: subject company name, CUSIP, "Aggregate
  Amount Beneficially Owned", "Percent of Class Represented". Return
  `{issuer_name, issuer_cik, cusip, shares, pct_owned}` (any field `None` if unparsable — never
  raise).
- `classify_material_crossing(form_type, pct_owned, prior_pct_owned) -> str | None` —
  `'5% cross'` / `'10% cross'` / `'below 5%'` / `None`. `prior_pct_owned` comes from the most
  recent prior seen-log row for the same `filer_key + issuer` (a `db.get_last_pct_owned(...)`
  helper).
- `issuer_lookup.resolve_ticker(conn, issuer_cik, issuer_ticker_hint) -> str | None` — prefer
  the hint (Form 4 gives it directly), else `mytrader.db.get_ticker_for_cik`, else `None`.
- Tests with real fixture files: a real Dalal Street `SC 13G` XML, a real Form 4 XML (use any
  recent `>10%` owner's — e.g. from `PABRAI MOHNISH` CIK `0001173334` if one exists, else any
  clean sample), an old cover-page `13G/A` HTML.

### Phase 4: Scan orchestration + CLI + report + alert + deploy wiring

**Tasks:**
- `edgar_monitor.scan_edgar(conn) -> dict` — for each tracked investor, call
  `mytrader.sec_filings.get_cik(conn, "AAPL")` once first (forces the `sec_cik_map` refresh —
  ticker value irrelevant), then for each CIK: `fetch_filing_index` →
  `recent_filings_of_types(index, SUPERINVESTOR_EDGAR_FORMS, today - LOOKBACK_DAYS)` → per
  filing: `build_dedup_key` → `insert_superinvestor_filing_seen`; if `not newly_seen: continue`;
  else fetch + parse the doc, classify crossing, build an alert dict. Return
  `{new_filings: [...], recent_filings: [...], first_seed: bool}`.
- **First-run seeding**: if `get_sync_watermark(conn, SUPERINVESTOR_FIRST_SEED_WATERMARK)` is
  `None`, insert every in-window filing into the seen-log but return `new_filings = []` and set
  the watermark. Every subsequent run alerts normally.
- `report.render_report(result) / write_report(result)` — overwrite
  `superinvestor-filings-report.md`. Sections: "New Since Last Run" (grouped by investor),
  "All Recent Filings (last N days)" table, a "How to read this" block that reproduces the
  handoff's "for a passive concentrated filer the high-value events are threshold crossings and
  Form 4s on names where they're already >10%" caveat so the alert is not oversold.
- `notify.send_digest(new_filings)` — one grouped WhatsApp message:
  `"Pabrai / Dalal Street — 2 new fast disclosures:\n- SC 13G on RAIN (5.2% stake, filed
  2026-09-05) [5% cross]\n- Form 4 on AMR (sold 40,000 sh @ $XX, txn 2026-09-02)"`. Toast too.
  No-op on empty list.
- `main.py` — `argparse`: `scan` (default: edgar; Phase 5 adds india), `scan --edgar-only`,
  `scan --india-only`, `resolve-ciks`. `resolve-ciks` calls
  `edgar_fulltext_search_hits(SUPERINVESTOR_EDGAR_FORMS + ["13F-HR"], entity_name="pabrai")`
  and prints the distinct `(display_name, cik)` pairs for manual config editing — it does NOT
  write config.
- `scripts/systemd/second-brain-superinvestor-edgar.service` + `.timer`
  (`OnCalendar=*-*-* 02:35:00 UTC`, `Persistent=true`).
- `scripts/invoke_investments.ps1`: `ValidateSet(... "superinvestor-filings")` +
  `$PACKAGES["superinvestor-filings"] = @{ Dir = "superinvestor-filings"; Module = "superinvestor_filings.main" }`.
- `scripts/deploy.ps1`: add `"second-brain-superinvestor-edgar.timer"` to `$TIMERS`.
- Update `investments/TOOLS.md` and add a `## Completed Phases` note to `CLAUDE.md` (mirror the
  existing investment-tool entries).
- Write a short deploy handoff (systemd `sudo cp` + `daemon-reload` + `enable --now`) — do NOT
  run it; VPS steps are Shaun's to run (chain into one pasteable `&&` block per MEMORY.md).

### Phase 5: India / SEBI SAST leg

**Tasks:**
- **5.1 Spike (do this first, timebox it):** live-check NSE + BSE for a no-login,
  machine-readable SAST Reg 29 daily feed. Document the working endpoint, request headers /
  cookie-priming needed, and the response schema in a comment block at the top of
  `sast_monitor.py`. If NEITHER exchange exposes one without a browser session, STOP and write a
  findings note for Shaun — do not build a brittle scraper without his sign-off.
- **5.2** `config.py`: add `india_aliases` to each `SUPERINVESTOR_TRACKED` entry (seed with the
  fund names from the handoff — `"pabrai investment fund"`, `"dalal street"`, `"dhandho"` — and
  a `# VERIFY current BSE/NSE entity names` comment).
- **5.3** `sast_monitor.fetch_sast_disclosures(session_date) -> list[dict] | None` and
  `scan_india(conn) -> dict` — structurally identical to `scan_edgar`: fetch daily list →
  name-pattern match `acquirer` against `india_aliases` (case-insensitive substring, any match)
  → `build_dedup_key("sast", filer_key, "SAST Reg 29(x)", issuer, exchange_ref)` →
  `insert_superinvestor_filing_seen` → alert dict. Reg 29(2) rows carry a `pct_change`; surface
  it (better granularity than US 13G).
- **5.4** `main.py`: wire `scan` to run both legs, `--india-only` to run just this.
- **5.5** second systemd timer `second-brain-superinvestor-sast.{service,timer}`
  (`OnCalendar=*-*-* 12:30:00 UTC` ≈ 22:30 AEST), add to `deploy.ps1 $TIMERS`.
- **5.6** tests with a saved fixture of the real feed response from 5.1.

---

## STEP-BY-STEP TASKS

Execute in order, top to bottom. Each task is independently testable.

### CREATE `investments/superinvestor-filings/pyproject.toml`
- **IMPLEMENT**: The template from "Patterns to Follow" above.
- **PATTERN**: `investments/fourteen-crash-signals-daily-check/pyproject.toml` (drop the `goat` dep).
- **GOTCHA**: `name` uses a hyphen (`superinvestor-filings`); the wheel package + import dir use
  an underscore (`superinvestor_filings`). Matches the `fourteen-crash-signals-daily-check` /
  `fourteen_crash_signals_daily_check` precedent.
- **VALIDATE**: `cd investments && uv sync` exits 0 and creates
  `investments/.venv/.../superinvestor_filings` link (editable install).

### UPDATE `investments/pyproject.toml`
- **IMPLEMENT**: add `"superinvestor-filings"` to `[tool.uv.workspace] members`.
- **VALIDATE**: `cd investments && uv sync` — no "member not found" error.

### CREATE `investments/superinvestor-filings/superinvestor_filings/__init__.py`
- **IMPLEMENT**: empty file.
- **VALIDATE**: `test -f investments/superinvestor-filings/superinvestor_filings/__init__.py`

### CREATE `investments/superinvestor-filings/superinvestor_filings/config.py`
- **IMPLEMENT**:
  ```python
  from __future__ import annotations
  from pathlib import Path
  from scripts.config import DB_PATH  # noqa: F401

  PKG_DIR = Path(__file__).resolve().parent.parent
  SUPERINVESTOR_REPORT_PATH = PKG_DIR / "superinvestor-filings-report.md"

  SUPERINVESTOR_EDGAR_FORMS: set[str] = {
      "SC 13D", "SC 13D/A", "SC 13G", "SC 13G/A", "3", "4", "4/A", "5",
  }
  SUPERINVESTOR_LOOKBACK_DAYS = 30
  SUPERINVESTOR_FIRST_SEED_WATERMARK = "superinvestor_first_seed_done"

  SUPERINVESTOR_TRACKED: dict[str, dict] = {
      "pabrai": {
          "display": "Mohnish Pabrai / Dalal Street",
          "edgar_ciks": [
              "1549575",   # Dalal Street, LLC (13F + SC 13G filer)
              "1173334",   # PABRAI MOHNISH (individual — Section 16 / group filings)
              "1571785",   # Pabrai Investment Fund 2, L.P.
              "1571780",   # Pabrai Investment Fund 3, Ltd.
              "1415742",   # Pabrai Investment Fund IV LP
              "1571786",   # Pabrai Investment Fund IV, L.P.
          ],
          "india_aliases": [  # Phase 5 — VERIFY current BSE/NSE entity names before relying on
              "pabrai investment fund", "dalal street", "dhandho",
          ],
      },
      # Add more investors here — data only, no code change.
  }
  ```
- **PATTERN**: `goat/config.py:1-10` (path constants), handoff "Config" section.
- **GOTCHA**: store CIKs as plain unpadded digit strings — `fetch_filing_index` and
  `edgar_fulltext_search_count` both zero-pad internally (`f"{int(cik):010d}"`).
- **GOTCHA**: the CIKs above were resolved 2026-09-07 via EDGAR company search. Re-confirm each
  still resolves with `fetch_filing_index` returning a non-`None` JSON before trusting the list
  (a bad CIK just yields `None` and is skipped — verify none are silently dead).
- **VALIDATE**: `uv run --directory investments/superinvestor-filings python -c "from superinvestor_filings import config; assert len(config.SUPERINVESTOR_TRACKED['pabrai']['edgar_ciks']) == 6"`
  (this import is safe locally — no DB is opened by config.py).

### CREATE `investments/superinvestor-filings/superinvestor_filings/db.py`
- **IMPLEMENT**: `init_superinvestor_tables(conn)` with the DDL from "Patterns to Follow";
  `insert_superinvestor_filing_seen(conn, *, dedup_key, source, filer_key, filer_display,
  form_type, issuer, issuer_ticker=None, accession=None, event_date=None, filed_date=None,
  shares=None, pct_owned=None, pct_owned_change=None, material_crossing=None,
  transaction_code=None, raw_url=None) -> bool`;
  `get_recent_superinvestor_filings_seen(conn, source=None, limit=100) -> list[Row]`;
  `get_last_pct_owned(conn, filer_key, issuer) -> float | None`;
  `count_seen(conn) -> int`.
- **PATTERN**: `goat/db.py:15-70` (DDL + `executescript` in `with conn:`),
  `goat/db.py:224-254` (`INSERT OR IGNORE` + `rowcount == 1`, `get_recent_*`).
- **IMPORTS**: `import sqlite3`, `from datetime import datetime, timezone`.
- **GOTCHA**: use the idempotent `try: conn.execute("ALTER TABLE ... ADD COLUMN ...") except
  sqlite3.OperationalError: pass` idiom for any column added later — SQLite has no
  `ADD COLUMN IF NOT EXISTS` (`goat/db.py:71-115`).
- **VALIDATE**: `uv run --directory investments/superinvestor-filings python -m pytest -q superinvestor_filings/tests/test_db.py`

### CREATE `investments/superinvestor-filings/superinvestor_filings/tests/conftest.py`
- **IMPLEMENT**: `db_path` (tmp) + `db_conn` fixtures (`init_db` → `get_connection` →
  `init_mytrader_tables` → `init_superinvestor_tables`); an autouse fixture that monkeypatches
  `superinvestor_filings.config.SUPERINVESTOR_REPORT_PATH` to `tmp_path`; an autouse fixture
  stubbing every network entrypoint (`mytrader.sec_filings.fetch_filing_index`,
  `.recent_filings_of_types` left real, `.fetch_filing_document`,
  `.edgar_fulltext_search_hits`) to return `None` by default.
- **PATTERN**: `goat/goat/tests/conftest.py` (whole file).
- **VALIDATE**: `uv run --directory investments/superinvestor-filings python -m pytest -q` collects with 0 errors.

### UPDATE `investments/my-trader/mytrader/config.py`
- **IMPLEMENT**: confirm `SEC_SUBMISSIONS_URL_TEMPLATE` and `SEC_ARCHIVES_URL_TEMPLATE` exist
  (referenced at `sec_filings.py:84,110`). Add
  `SEC_ARCHIVES_DIR_URL_TEMPLATE = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession_no_dashes}/index.json"`.
- **PATTERN**: the `SEC_*` block near `config.py:207-240`.
- **VALIDATE**: `uv run --directory investments/my-trader python -c "from mytrader import config; config.SEC_SUBMISSIONS_URL_TEMPLATE; config.SEC_ARCHIVES_URL_TEMPLATE; config.SEC_ARCHIVES_DIR_URL_TEMPLATE"`

### ADD to `investments/my-trader/mytrader/db.py`
- **IMPLEMENT**: `get_ticker_for_cik(conn, cik) -> str | None`:
  `row = conn.execute("SELECT ticker FROM sec_cik_map WHERE cik = ? LIMIT 1", (str(int(cik)),)).fetchone(); return row["ticker"] if row else None`.
- **PATTERN**: `get_cik_for_ticker` at `mytrader/db.py:461-463` (sits right after it).
- **GOTCHA**: `sec_cik_map.cik` is stored as the plain int-string from `company_tickers.json`
  (`str(row["cik_str"])`) — normalize the arg with `str(int(cik))` so a zero-padded input still
  matches.
- **VALIDATE**: `uv run --directory investments/my-trader python -m pytest -q mytrader/tests/test_sec_filings.py`

### ADD to `investments/my-trader/mytrader/sec_filings.py`
- **IMPLEMENT** `recent_filings_of_types(index, forms, since)`,
  `edgar_fulltext_search_hits(...)`, `fetch_filing_directory_index(cik, accession_number)` — see
  Phase 2 tasks for signatures.
- **PATTERN**: `latest_filing_entry` (lines 94-106) for the columnar-array walk;
  `edgar_fulltext_search_count` (lines 125-163) for the `efts` request + `try/except → None`;
  `fetch_filing_document` (lines 109-120) for the archives GET + byte guard.
- **IMPORTS**: already in the module (`requests`, `date`, `datetime`).
- **GOTCHA**: `filings.recent` may be missing keys on a filer with zero filings — use
  `.get(..., [])` and guard `len` mismatch across the parallel arrays (zip to the shortest).
- **GOTCHA**: `edgar_fulltext_search_hits` — `_source` key names are unverified; write it to
  tolerate both `entity_name` and `display_names`, and log a `print` if neither is present.
- **VALIDATE**: `uv run --directory investments/my-trader python -m pytest -q mytrader/tests/test_sec_filings.py`
  (add unit tests: feed a hand-built columnar `index` dict, assert the filtered list).

### CREATE `investments/superinvestor-filings/superinvestor_filings/edgar_parse.py`
- **IMPLEMENT**: `parse_ownership_form`, `parse_schedule_13dg`, `classify_material_crossing` —
  see Phase 3.
- **IMPORTS**: `import re`, `import xml.etree.ElementTree as ET`; for the fallback
  `from mytrader.sec_filings import strip_html`.
- **GOTCHA**: ownership XML has NO namespace on the root (`<ownershipDocument>`) — plain
  `ET.fromstring` + `.find("issuer/issuerTradingSymbol")` works. Schedule 13D/G structured XML
  MAY have a namespace — strip it or use `{*}` wildcard matching.
- **GOTCHA**: `transactionPricePerShare/value` can be absent (a gift/other) — default `None`.
- **GOTCHA**: `strip_html` needs `beautifulsoup4` — confirm it imports under the new package's
  venv (`mytrader` pulls it in). If not, add `beautifulsoup4>=4.12` to the new `pyproject.toml`.
- **VALIDATE**: `uv run --directory investments/superinvestor-filings python -m pytest -q superinvestor_filings/tests/test_edgar_parse.py`

### CREATE `investments/superinvestor-filings/superinvestor_filings/issuer_lookup.py`
- **IMPLEMENT**: `resolve_ticker(conn, issuer_cik, issuer_ticker_hint) -> str | None`.
- **PATTERN**: thin wrapper — `from mytrader.db import get_ticker_for_cik`.
- **VALIDATE**: `uv run --directory investments/superinvestor-filings python -m pytest -q superinvestor_filings/tests/test_issuer_lookup.py`

### CREATE `investments/superinvestor-filings/superinvestor_filings/edgar_monitor.py`
- **IMPLEMENT**: `scan_edgar(conn) -> dict` + first-run seeding — see Phase 4.
- **PATTERN**: `goat/insider_scan.py:100-168` (`run_holdings_watch` control flow).
- **IMPORTS**: `from datetime import date, timedelta`;
  `from mytrader import sec_filings`; `from mytrader.db import get_sync_watermark, set_sync_watermark`;
  `from . import config, db, edgar_parse, issuer_lookup`.
- **GOTCHA**: call `sec_filings.get_cik(conn, "AAPL")` once at the top to force the
  `sec_cik_map` refresh before any `resolve_ticker` call — otherwise a fresh DB has an empty map
  and every ticker resolves to `None`.
- **GOTCHA**: `SEC_REQUEST_DELAY_SECONDS` (`config.SEC_REQUEST_DELAY_SECONDS`, 0.2) —
  `time.sleep` it between every document fetch to stay under 10 req/s across ~6 CIKs × N filings.
- **GOTCHA**: the first-seed watermark must be set even if this run found zero in-window filings
  (otherwise the next run treats a brand-new filing as historical-and-skip it... no — it would
  re-enter seed mode and still not alert; set the watermark unconditionally once the seed pass
  completes without error).
- **VALIDATE**: `uv run --directory investments/superinvestor-filings python -m pytest -q superinvestor_filings/tests/test_edgar_monitor.py`

### CREATE `investments/superinvestor-filings/superinvestor_filings/report.py`
- **IMPLEMENT**: `render_report(result) -> str`, `write_report(result) -> None`.
- **PATTERN**: `goat/insider_scan.py:510-678` (copy style, `## Run:` heading,
  `_now_sydney_str` footer — reimplement that 4-line helper here).
- **GOTCHA**: reproduce the handoff's "high-value events are threshold crossings and Form 4s on
  >10% names; ordinary 5-10% sizing still waits for the quarterly cycle" caveat verbatim in a
  "How to read this" block so the tool is not oversold.
- **VALIDATE**: `uv run --directory investments/superinvestor-filings python -m pytest -q superinvestor_filings/tests/test_report.py`

### CREATE `investments/superinvestor-filings/superinvestor_filings/notify.py`
- **IMPLEMENT**: `send_digest(new_filings: list[dict]) -> None` — no-op on empty; one grouped
  WhatsApp message + one toast.
- **PATTERN**: `goat/insider_scan.py:447-468` exactly (the `sys.path.insert` block).
- **GOTCHA**: `.parent` × 4 from `notify.py` to repo root — verify by asserting the path ends in
  `.claude/scripts` and `notifications.py` exists there.
- **VALIDATE**: `uv run --directory investments/superinvestor-filings python -m pytest -q superinvestor_filings/tests/test_notify.py`
  (monkeypatch `send_whatsapp_notification` / `send_toast_notification`, assert called once with
  the grouped body / not called on empty).

### CREATE `investments/superinvestor-filings/superinvestor_filings/main.py`
- **IMPLEMENT**: `_open_conn()` (Patterns section) + `argparse` with `scan`
  (`--edgar-only` / `--india-only` flags) and `resolve-ciks`. `dispatch` dict like
  `goat/main.py:278-290`.
- **PATTERN**: `fourteen_crash_signals_daily_check/main.py` (whole file).
- **GOTCHA**: Phase 4 wires `scan` to EDGAR only. Phase 5 flips the default to run both legs —
  leave a `# Phase 5: also run scan_india()` marker.
- **VALIDATE**:
  `uv run --directory investments/superinvestor-filings python -m superinvestor_filings.main --help`
  lists `scan` and `resolve-ciks`.

### CREATE `scripts/systemd/second-brain-superinvestor-edgar.service` + `.timer`
- **IMPLEMENT**: service — `Type=oneshot`, `User=secondbrain`,
  `WorkingDirectory=/home/secondbrain/second-brain/investments/superinvestor-filings`,
  `ExecStart=/home/secondbrain/second-brain/investments/.venv/bin/python -m superinvestor_filings.main scan`,
  `StandardOutput`/`StandardError=append:/home/secondbrain/second-brain/investments/superinvestor-filings/superinvestor_edgar_runs.log`.
  Timer — `OnCalendar=*-*-* 02:35:00 UTC`, `Persistent=true`, `WantedBy=timers.target`,
  `Requires=second-brain-superinvestor-edgar.service`.
- **PATTERN**: `scripts/systemd/second-brain-goat-insider-scan.{service,timer}` verbatim.
- **VALIDATE**: `python -c "import configparser,sys; c=configparser.ConfigParser(); c.optionxform=str; c.read('scripts/systemd/second-brain-superinvestor-edgar.service'); print(c['Service']['ExecStart'])"`
  (or `systemd-analyze verify` on the VPS).

### UPDATE `scripts/invoke_investments.ps1`
- **IMPLEMENT**: add `"superinvestor-filings"` to the `[ValidateSet(...)]` on `-Package`; add
  `"superinvestor-filings" = @{ Dir = "superinvestor-filings"; Module = "superinvestor_filings.main" }`
  to `$PACKAGES`.
- **PATTERN**: the existing four entries (lines 23, 33-38).
- **VALIDATE**: `powershell -NoProfile -Command "& { . ./scripts/invoke_investments.ps1 }"` —
  errs on missing mandatory params (expected), no syntax error.

### UPDATE `scripts/deploy.ps1`
- **IMPLEMENT**: add `"second-brain-superinvestor-edgar.timer"` to `$TIMERS`.
- **PATTERN**: lines 17-27.
- **VALIDATE**: `powershell -NoProfile -File scripts/deploy.ps1 -WhatIf` is not supported;
  just `Select-String "superinvestor" scripts/deploy.ps1` returns the line.

### UPDATE `investments/TOOLS.md` + `CLAUDE.md`
- **IMPLEMENT**: one-paragraph entry in `TOOLS.md` (mirror the goat / fourteen-signals entries);
  a `### Superinvestor Filings Scanner` note under `CLAUDE.md`'s investment-tool section +
  a build-command line for `invoke_investments.ps1 -Package superinvestor-filings`.
- **VALIDATE**: `Select-String "superinvestor" investments/TOOLS.md CLAUDE.md`

### CREATE deploy handoff (do NOT execute)
- **IMPLEMENT**: `investments/superinvestor-filings/DEPLOY.md` with the one pasteable block:
  ```
  ssh secondbrain@137.184.102.104
  cd /home/secondbrain/second-brain && git pull && \
    sudo cp scripts/systemd/second-brain-superinvestor-edgar.{service,timer} /etc/systemd/system/ && \
    sudo systemctl daemon-reload && \
    sudo systemctl enable --now second-brain-superinvestor-edgar.timer && \
    cd investments && /home/secondbrain/second-brain/investments/.venv/bin/python -m uv sync && \
    cd superinvestor-filings && \
    /home/secondbrain/second-brain/investments/.venv/bin/python -m superinvestor_filings.main scan
  ```
  (first `scan` seeds the log silently — expect "0 new".)
- **PATTERN**: MEMORY.md "Manual command chaining" — one `&&` block.
- **VALIDATE**: n/a (doc).

### --- PHASE 5 (India) tasks begin here ---

### SPIKE: verify NSE/BSE SAST feed (Task 5.1)
- **IMPLEMENT**: a throwaway script hitting the NSE + BSE endpoints listed in "Relevant
  Documentation". Confirm: no login, machine-readable (CSV/JSON), includes acquirer name +
  issuer + shares/% + date, and the request-priming needed. Write findings into
  `sast_monitor.py`'s module docstring.
- **GOTCHA**: NSE blocks non-browser UAs and needs a cookie from `GET nseindia.com` first,
  reused via a `requests.Session`. Set a realistic `User-Agent`
  (`config.SEC_USER_AGENT` is NOT appropriate here — use a browser-like UA, mirror
  `GOAT_SP500_USER_AGENT = "Mozilla/5.0 (compatible; SecondBrainGoat/1.0)"` idiom).
- **STOP CONDITION**: if neither exchange has a no-login feed, write a findings note for Shaun
  and do not build a browser-session scraper without sign-off.
- **VALIDATE**: findings documented; a saved sample response committed as a test fixture.

### CREATE `sast_monitor.py` + wire into `main.py` + second timer (Tasks 5.2-5.6)
- **IMPLEMENT**: per Phase 5 tasks.
- **PATTERN**: `edgar_monitor.scan_edgar` structure; `goat/config.py` browser-UA idiom.
- **VALIDATE**:
  `uv run --directory investments/superinvestor-filings python -m pytest -q superinvestor_filings/tests/test_sast_monitor.py`
  and `.\scripts\invoke_investments.ps1 -Package superinvestor-filings -Command "scan --india-only"`.

---

## TESTING STRATEGY

Framework: `pytest` + `pytest-mock` (`monkeypatch`), matching every other `investments/`
package. Tests live in `superinvestor_filings/tests/`, `pythonpath = ["."]`.

### Unit Tests

- **`test_config.py`** — `SUPERINVESTOR_TRACKED` shape; 6 CIKs; forms set contents; lookback = 30.
- **`test_db.py`** — `init_superinvestor_tables` idempotent (call twice); `insert_*` returns
  `True` first time / `False` on duplicate `dedup_key`; `get_last_pct_owned` returns the most
  recent row's value; `count_seen`.
- **`test_edgar_parse.py`** — against committed fixture files:
  - Form 4 XML → transactions list with correct codes/dates/shares; `issuer_ticker` from
    `issuerTradingSymbol`; `is_ten_pct_owner` bool.
  - Structured 13G XML → `pct_owned`, `shares`, `issuer_cik`, `cusip`.
  - Old cover-page `13G/A` HTML → regex fallback pulls `pct_owned` (or `None` gracefully).
  - `classify_material_crossing`: 4.9→5.2 = `'5% cross'`; 9.5→10.4 = `'10% cross'`;
    6.0→4.2 = `'below 5%'`; 6.0→7.0 = `None`.
- **`test_issuer_lookup.py`** — hint wins; falls back to `sec_cik_map`; `None` when absent.
- **`test_edgar_monitor.py`** — monkeypatch `sec_filings.fetch_filing_index` to return a
  hand-built columnar index + `fetch_filing_document` to return a fixture:
  - new filing → appears in `result["new_filings"]` and in the seen-log.
  - same filing next run → `new_filings == []`.
  - **first-run seeding**: no watermark → in-window filings inserted, `new_filings == []`,
    watermark set; second run with one genuinely new filing → it alerts.
  - a fetch returning `None` → filer skipped, no crash, no alert.
- **`test_report.py`** — `render_report` includes the "How to read this" caveat, groups by
  investor, lists recent filings; empty result → "No new filings since last run".
- **`test_notify.py`** — empty list → neither sender called; non-empty → one grouped WhatsApp
  body containing every filing line.
- **`test_sast_monitor.py`** (Phase 5) — fixture CSV → alias match picks Pabrai rows only;
  Reg 29(2) `pct_change` surfaced; dedup on re-run.

### Integration Tests

- `main.py --help` lists subcommands (smoke).
- Full `scan_edgar(conn)` against fixtures end-to-end (in-memory tmp DB via `db_conn`): seed →
  new filing → report written to `tmp_path` → digest body asserted.

### Edge Cases

- Filer CIK with zero filings (`filings.recent` empty / missing keys).
- Columnar arrays of unequal length (zip-to-shortest guard).
- Form 4 with only non-P/S codes (grant/exercise) → recorded, not headlined in the alert.
- 13G/A amending a pre-2024 13D/G → no structured XML → text fallback → `None` pct is OK.
- Issuer CIK not in `sec_cik_map` (foreign / OTC issuer) → `issuer_ticker = None`, alert still
  fires with the issuer name.
- Two tracked CIKs both named on one group 13G → dedup_key differs by `filer_key`? No — same
  `filer_key`, same `form_type`, same `issuer`, same `accession` → one row (correct; a group
  filing is one event).
- Second run same day (timer double-fire / manual re-run) → all `INSERT OR IGNORE` no-ops,
  `new_filings == []`, digest not sent.
- Network down for the whole run → every fetch `None` → report notes "data unavailable", no
  alert, exit 0.

---

## VALIDATION COMMANDS

### Level 1: Syntax & Style
```
cd investments && uv run ruff check superinvestor-filings/
cd investments && uv run ruff check my-trader/mytrader/sec_filings.py my-trader/mytrader/db.py
cd investments && uv run mypy superinvestor-filings/superinvestor_filings
```

### Level 2: Unit Tests
```
uv run --directory investments/superinvestor-filings python -m pytest -q
uv run --directory investments/my-trader python -m pytest -q mytrader/tests/test_sec_filings.py
```

### Level 3: Full investments regression (no cross-package breakage)
```
cd investments && uv run python -m pytest -q my-trader goat fourteen-crash-signals-daily-check briefs-finance
```

### Level 4: Manual Validation (VPS only — never local; local would create an empty investments.db)
```
.\scripts\invoke_investments.ps1 -Package superinvestor-filings -Command "resolve-ciks"
.\scripts\invoke_investments.ps1 -Package superinvestor-filings -Command "scan --edgar-only"
# ^ first run: "0 new filings (first-run seed complete)". Re-run:
.\scripts\invoke_investments.ps1 -Package superinvestor-filings -Command "scan --edgar-only"
# ^ "0 new" again unless a genuine new filing landed. Check the report:
ssh secondbrain@137.184.102.104 "cat /home/secondbrain/second-brain/investments/superinvestor-filings/superinvestor-filings-report.md"
```

### Level 5: systemd (VPS, after the deploy handoff is run)
```
ssh secondbrain@137.184.102.104 "systemctl status second-brain-superinvestor-edgar.timer"
ssh secondbrain@137.184.102.104 "sudo systemctl start second-brain-superinvestor-edgar.service && tail -n 40 /home/secondbrain/second-brain/investments/superinvestor-filings/superinvestor_edgar_runs.log"
```

---

## ACCEPTANCE CRITERIA

- [ ] `investments/superinvestor-filings/` package exists, is a workspace member, `uv sync` clean.
- [ ] `scan --edgar-only` on a fresh DB seeds the seen-log silently (no WhatsApp), sets the
      first-seed watermark, prints "0 new".
- [ ] A subsequent run with a genuinely new tracked-filer filing in-window: inserts it, writes
      the report, sends exactly one grouped WhatsApp digest naming the issuer + form + key numbers.
- [ ] A re-run with no new filings: no digest, report still overwritten with a fresh timestamp.
- [ ] Form 4 XML parsed transaction-by-transaction (code/date/shares/price/post-holding);
      issuer ticker taken from `issuerTradingSymbol`.
- [ ] Schedule 13D/G: structured XML parsed when present, cover-page text fallback otherwise,
      `material_crossing` classified (`5% cross` / `10% cross` / `below 5%` / none).
- [ ] Every network failure path returns `None` and is skipped — the scan never raises, always
      exits 0, always writes a report.
- [ ] No write to `holdings`, `watchlist`, `goat_*`, `pending_candidates`, or any account state.
- [ ] `resolve-ciks` prints `(display_name, CIK)` pairs for "pabrai" and does not edit config.
- [ ] `scripts/invoke_investments.ps1` accepts `-Package superinvestor-filings`;
      `scripts/deploy.ps1 $TIMERS` includes the new timer; systemd unit files added.
- [ ] Full `investments/` pytest suite passes (no regression in `my-trader` from the
      `sec_filings.py` / `db.py` additions).
- [ ] `ruff` + `mypy` clean on the new package and the two modified `mytrader` files.
- [ ] `TOOLS.md` + `CLAUDE.md` updated; `DEPLOY.md` handoff written (not executed).
- [ ] Phase 5: SAST feed spike documented; if a feed exists, `scan --india-only` alias-matches
      Pabrai rows and dedups; if not, a findings note is written for Shaun and Phase 5 stops.

---

## COMPLETION CHECKLIST

- [ ] All Phase 1-4 tasks completed in order; each task's `VALIDATE` command passed immediately.
- [ ] Phase 5 spike run; Phase 5 build only if the spike found a usable feed.
- [ ] Level 1-3 validation commands all green.
- [ ] Level 4 manual run done on the VPS via `invoke_investments.ps1` (seed + re-run).
- [ ] `DEPLOY.md` handed to Shaun as one pasteable block; systemd install NOT run by the agent.
- [ ] Acceptance criteria all checked.
- [ ] `investments/superinvestor-filings-scanner-handoff.md` status line updated to "BUILT
      (EDGAR leg) — Phase 5 India: <state>".
- [ ] MEMORY.md pointer `project_superinvestor_filings_scanner.md` updated from "awaiting
      /plan-feature" to "BUILT, EDGAR leg live on VPS timer / Phase 5 pending".

---

## NOTES

**Resolved open questions (from the handoff's list of 12), per Shaun 2026-09-07:**
1. Package placement → **new package** `investments/superinvestor-filings/`.
2. First-run behaviour → **silent-seed trailing 30 days**, `SUPERINVESTOR_LOOKBACK_DAYS = 30`,
   watermark in `sync_state`.
3. Filer→CIK → **hardcode the 6 resolved CIKs in config** + a `resolve-ciks` discovery command
   (prints, does not write). No dynamic name-index parsing in v1.
4. 13G/A noise → **alert on all**, tag `material_crossing` for 5%/10%/below-5%. Tighten later.
5. Form 4 depth → **full XML transaction parse**.
6. India feed mechanics → **Phase 5, spike first** (Task 5.1); verify live, stop if no no-login feed.
7. India entity aliases → seeded from the handoff, `# VERIFY` comment, confirmed during 5.1.
8. Bulk/block-deal leg → **deferred** (not in this plan; a fast-follow if Phase 5 lands).
9. Alert cadence → **one grouped digest per run**.
10. Timer → **one daily EDGAR run 02:35 UTC (~12:35 AEST)**; Phase 5 adds an India run
    ~12:30 UTC (~22:30 AEST). ~24h max latency accepted.
11. Backfill → **start log empty** (the silent seed IS the only "history"; no historical import).
12. `goat_insider_filings_seen` overlap → **keep separate**. If Dalal Street files a US Form 4
    while a >10% owner, both this scanner and the goat insider discovery scan could surface it
    from different sources — accepted; different tables, different purpose. Note it in the report
    footer, do not attempt cross-suppression in v1.

**Design trade-offs:**
- The submissions API (`data.sec.gov/submissions/CIK*.json`) is the poll, NOT full-text search —
  it is filer-scoped by construction, has no rate-limit surprises, and `fetch_filing_index`
  already implements it. `efts` full-text search is used only by `resolve-ciks`.
- No LLM. Every prior `sec_filings` consumer summarizes prose; this one reads structured fields,
  so it stays a pure-Python parser and has no `sdk_compat` / backend dependency — cheaper,
  faster, deterministically testable.
- `material_crossing` needs a *prior* percent to compare against. On the very first observation
  of a `filer_key + issuer` pair there is no prior → `material_crossing` is set from the
  form-type heuristic alone (an initial `SC 13G` is by definition a 5% cross; an initial
  `SC 13D` likewise) and left `None` for `/A` amendments with no prior row.

**Confidence: 7.5/10** for one-pass success on Phases 1-4. The EDGAR submissions poll, the
seen-log, the notify path, and the systemd/deploy wiring are all near-exact copies of proven
code. The two genuine unknowns that need live validation during execution: (a) the exact
structured Schedule 13D/G XML schema (post-2024-12-18 format — spec-check against a real Dalal
Street `SC 13G`), and (b) the `efts` `_source` key names for `resolve-ciks`. Both have graceful
fallbacks specified. **Phase 5 is 3/10 confidence** and gated behind a spike — the NSE/BSE feeds
are unverified and NSE is actively hostile to non-browser clients.
