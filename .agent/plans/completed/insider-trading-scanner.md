# Feature: Insider Trading Scanner (OpenInsider)

The following plan should be complete, but it's important to validate documentation and
codebase patterns and task sanity before implementing. Pay special attention to naming of
existing utils/types/models. Import from the right files.

## Feature Description

A daily scan of OpenInsider.com's aggregated SEC Form 4 data (insiders — officers,
directors, 10%+ owners — trading their own company's stock), split into two halves:

1. **Holdings watch** — for every ticker Shaun currently holds, check for recent
   open-market insider buys or sells. A large sell (potentially millions of dollars) may
   read as a board member acting like the company is about to disappoint; a buy may be a
   signal worth adding to. Immediate WhatsApp alert on any hit.
2. **Discovery scan** — market-wide daily scan for $25k+ open-market insider *purchases*
   only, staged as new-candidate signals independent of sector rotation. Immediate
   WhatsApp alert when new candidates are staged.

Both are advisor-notes-only. No auto-buy/sell, no auto-watchlist-add. Discovery candidates
land in the existing `goat_pending_candidates` staging table for explicit
promote/dismiss — same precedent as every other Goat candidate source.

## User Story

As Shaun (multi-business founder managing his own portfolio)
I want to be alerted when a company insider makes a large, meaningful open-market trade —
either on something I already hold, or as a fresh market-wide buy signal
So that I can factor genuine insider conviction (not routine equity-comp noise) into my
own decisions, without having to manually check OpenInsider myself

## Problem Statement

Shaun has no visibility into insider trading activity today. A board member selling
millions of dollars of stock in a company he holds is exactly the kind of red flag his
existing Goat tooling (150DMA exit check, sector rotation, heartbeat scanner) doesn't
surface, because none of those are fundamentals/ownership-based signals.

## Solution Statement

Add a new `openinsider.py` scraper (mirrors `sp500_universe.py`'s direct-fetch style) and
`insider_scan.py` orchestrator (mirrors `heartbeat_scan.py`'s discovery-staging pattern
and `monitor.py`'s holdings-check pattern) to the existing `goat` package. A new
`goat_insider_filings_seen` table dedups filings by natural key (discrete one-time events,
unlike the 150DMA check's continuous on/off state, so `goat_alert_history`'s
open/acknowledge semantics don't fit — see Notes). Wired into a new `scan-insiders` CLI
command and a new daily systemd timer, following the exact deployment pattern already
used for `scan-heartbeat`.

## Feature Metadata

**Feature Type**: New Capability
**Estimated Complexity**: Medium
**Primary Systems Affected**: `investments/goat` package only (new files + additive
changes to `db.py`, `config.py`, `main.py`, `monitor.py`); read-only cross-package access
to `mytrader.db` (existing precedent, e.g. `heartbeat_scan.py:15,59-62`)
**Dependencies**: `requests` + `beautifulsoup4` — already transitively available via the
`my-trader` workspace dependency (`investments/my-trader/pyproject.toml:8,12`), same as
`sp500_universe.py` uses them without declaring them in `goat/pyproject.toml`. No new
dependency to add.

---

## Design Decisions (resolved with Shaun 2026-08-17)

1. **Trade-type filtering**: `P` (open-market purchase) and `S` (open-market sale) codes
   only. Excludes `A` (grant/award), `M` (option exercise), `G` (gift), `F`
   (tax-withholding sale) — none of these reflect genuine conviction.
2. **Dollar thresholds**: OpenInsider's own pre-built floors — $25k for purchases, $100k
   for sales. Both are *minimums*, not caps — a $2M sale is well within the $100k+ sales
   bucket. Shaun's actual interest is large sells (potentially millions), so alert detail
   must surface the dollar value prominently rather than treating every hit as equally
   weighted.
3. **Sector filter**: none. Insider activity is an independent signal, not filtered by
   `sector_rotation.rank_sectors` (unlike the heartbeat scanner).
4. **Notification shape**: both halves fire immediate WhatsApp alerts (no batching), same
   as every other Goat scan.
5. **Package placement**: Goat (not my-trader) — mirrors the 150DMA exit check's shape for
   holdings-watch and the heartbeat/sector scanners' shape for discovery.
6. **Staging table**: reuse `goat_pending_candidates` with `source="goat_insider_discovery"`.

---

## CONTEXT REFERENCES

### Relevant Codebase Files — READ THESE BEFORE IMPLEMENTING

- `investments/goat/goat/heartbeat_scan.py` (whole file, 117 lines) — Why: the exact
  discovery-scan orchestrator shape to mirror (fetch universe → filter → check → 3-way
  dedup against holdings/watchlist/pending → stage → report). `run_heartbeat_scan`
  (lines 21-82) is the closest analog to `run_discovery_scan`.
- `investments/goat/goat/monitor.py` (whole file, 247 lines) — Why: `run_monitor`
  (lines 46-68) is the holdings-check shape; `maybe_notify` (lines 109-143) is the
  notification function to extend (see Task 6 GOTCHA — its `parts` list at lines 126-131
  hardcodes `"below 150DMA exit threshold"`, not reusable as-is); `_stage_new_sector_candidates`
  (lines 146-170) is the 3-way dedup + banned-ticker skip pattern for discovery staging.
- `investments/goat/goat/db.py` (whole file, 141 lines) — Why: `init_goat_tables`
  (lines 15-42) is where the new table's `CREATE TABLE IF NOT EXISTS` goes;
  `insert_goat_pending_candidate` (lines 96-106) and `delete_goat_pending_candidate`
  (lines 109-114, note the `cur.rowcount` return pattern) are the CRUD idioms to follow
  for the new `goat_insider_filings_seen` table.
- `investments/goat/goat/sp500_universe.py` (whole file, 80 lines) — Why: exact
  `requests` + `BeautifulSoup` direct-fetch style to mirror in `openinsider.py` —
  headers dict (line 18), try/except-returns-None-on-any-failure (lines 21-57),
  local `import requests`/`from bs4 import BeautifulSoup` inside the function (not
  top-level, lines 25-26).
- `investments/goat/goat/main.py` (whole file, 192 lines) — Why: `_open_conn`
  (lines 8-19), `cmd_scan_heartbeat` (lines 83-97) is the closest CLI command shape to
  mirror for `cmd_scan_insiders`; `main()` (lines 145-191) is where the subparser +
  dispatch entry goes.
- `investments/goat/goat/config.py` (whole file, 198 lines) — Why: shows the established
  comment style (every tunable constant gets a "why this number, per which HANDOFF
  section, v1/tunable vs literature-final" comment — lines 12-41 and 124-159 are good
  examples) and where new constants get appended (end of file, following the
  `GOAT_GICS_TO_ETF_SECTOR_LABEL` block at lines 179-197).
- `investments/my-trader/mytrader/db.py:179-180` (`get_all_holdings`) — Why: the read-only
  cross-package call for the holdings-watch ticker list, same as `mytrader.db.get_all_holdings`
  used implicitly via `heartbeat_scan.py`'s and `monitor.py`'s `mt_db` import.
- `investments/my-trader/mytrader/checks/__init__.py:10-14` (`CheckResult`) — Why: NOT
  used by this feature (see Notes — insider filings are raw event data, not a
  threshold check), but read it so you understand why `insider_scan.py` deliberately
  does NOT wrap filings in `CheckResult`.
- `investments/my-trader/mytrader/tickers.py:8-10` (`normalize`) — Why: ticker
  normalization (e.g. `BRK.B` → `BRK-B`) must be applied to OpenInsider's raw ticker
  text, same as `sp500_universe.py:51` does for Wikipedia's table.
- `investments/goat/goat/tests/conftest.py` (whole file, 46 lines) — Why: `db_conn`
  fixture (lines 19-26), `_isolate_goat_report_path` (lines 29-35, **must be extended**
  to also monkeypatch `GOAT_INSIDER_SCAN_REPORT_PATH`), `_no_real_price_history_fetch`
  (lines 38-45, not directly relevant here but shows the "no real network call by
  default" precedent this feature must also honor for `requests.get`).
- `investments/goat/goat/tests/test_sp500_universe.py` (whole file, 110 lines) — Why:
  exact test pattern for a scraper — `_FakeResponse` class (lines 17-20),
  `monkeypatch.setattr("requests.get", ...)` (line 24), canned HTML fixture string
  (lines 7-14) — mirror this shape for `test_openinsider.py`.
- `investments/goat/goat/tests/test_heartbeat_scan.py` (whole file, 152 lines) — Why:
  exact test pattern for a discovery-scan orchestrator — `_patch_common` helper
  (lines 40-62) monkeypatches every collaborator function by its
  `goat.heartbeat_scan.<module>.<function>` import path; mirror this shape for
  `test_insider_scan.py`.
- `investments/goat/goat/tests/test_monitor.py:118-185` (`_fake_notifications_module`,
  `test_maybe_notify_*`) — Why: exact pattern for testing `maybe_notify` without a real
  WhatsApp/toast call — `monkeypatch.setitem(sys.modules, "notifications", ...)`.
- `investments/goat/goat/tests/test_db.py` (whole file, 86 lines) — Why: CRUD test
  pattern to mirror for the new `goat_insider_filings_seen` table tests.
- `scripts/systemd/second-brain-goat-heartbeat-scan.timer` and
  `second-brain-goat-heartbeat-scan.service` — Why: exact systemd unit shape to mirror
  for the new daily insider-scan timer/service (see Task 12).
- `scripts/systemd/second-brain-goat-monitor.timer:6` — Why: shows the daily cadence
  convention (`OnCalendar=*-*-* 21:35:00 UTC`) — the new insider-scan timer should run
  shortly after this (21:35 UTC ≈ 7:35am AEST/AEDT) so it doesn't collide.
- `investments/insider-trading-scanner-handoff.md` (whole file) — Why: the original
  design-discussion doc this plan formalizes; contains OpenInsider's confirmed URL
  structure (`/screener`, `/latest-insider-purchases-25k`, GET params `s`/`vl`/`td`/`tdr`)
  from a live fetch on 2026-08-17.

### New Files to Create

- `investments/goat/goat/openinsider.py` — OpenInsider.com scraper (screener + latest-purchases fetch, HTML table parsing, dedup-key builder)
- `investments/goat/goat/insider_scan.py` — orchestrator (`run_holdings_watch`, `run_discovery_scan`, report render/write)
- `investments/goat/goat/tests/test_openinsider.py` — scraper unit tests
- `investments/goat/goat/tests/test_insider_scan.py` — orchestrator unit tests
- `scripts/systemd/second-brain-goat-insider-scan.timer` — daily VPS timer
- `scripts/systemd/second-brain-goat-insider-scan.service` — VPS service unit

### New Files Auto-Generated At Runtime (not created by you, but referenced)

- `investments/goat/insider-scan-report.md` — mirrors `monitor-report.md` / `heartbeat-candidates-pending-review.md`, written by `insider_scan.write_insider_scan_report`

### Files to Modify

- `investments/goat/goat/db.py` — add `goat_insider_filings_seen` table to `init_goat_tables`; add `insert_goat_insider_filing_seen` + `get_recent_insider_filings_seen`
- `investments/goat/goat/config.py` — append insider-scan constants
- `investments/goat/goat/monitor.py` — `maybe_notify` gets a new `alert_label` param (backward-compatible default)
- `investments/goat/goat/main.py` — new `cmd_scan_insiders` + subparser + dispatch entry
- `investments/goat/goat/tests/conftest.py` — extend `_isolate_goat_report_path` to also isolate `GOAT_INSIDER_SCAN_REPORT_PATH`
- `investments/goat/goat/tests/test_monitor.py` — add `alert_label` regression test
- `investments/goat/goat/tests/test_db.py` — add CRUD tests for the new table

### Relevant Documentation

- OpenInsider.com itself has no formal API docs — the handoff doc's "Context" section
  (confirmed live 2026-08-17) is the source of truth for URL structure. No external doc
  link exists to cite; treat the handoff's confirmed structure as provisional and
  re-verify column headers live during Task 1 (see GOTCHA there).

### Patterns to Follow

**Scraper resilience (from `sp500_universe.py:21-57`):**
```python
try:
    r = requests.get(url, headers=_HEADERS, timeout=30)
    if r.status_code != 200:
        return None
    ...
    return rows or None
except Exception:
    return None
```
Every fetch function returns `None` on any failure — callers print a `[goat-insider-scan] ...`
message and skip gracefully (never raise, never silently return `[]` for a real failure vs
"nothing found").

**3-way dedup before staging (from `monitor.py:158-165` / `heartbeat_scan.py:59-64`):**
```python
if ticker in config.GOAT_BANNED_TICKERS:
    continue
if mt_db.get_holding_row(conn, ticker) is not None:
    continue
if mt_db.get_watchlist_row(conn, ticker) is not None:
    continue
if db.get_goat_pending_candidate(conn, ticker) is not None:
    continue
```

**INSERT OR IGNORE + rowcount for "was this new?" (from `db.py:109-114` style, adapted from DELETE to INSERT):**
```python
with conn:
    cur = conn.execute("INSERT OR IGNORE INTO ... VALUES (...)", (...))
    return cur.rowcount == 1
```

**Money formatting**: `f"${value:,.0f}"` — no existing precedent in this codebase for
dollar formatting (checked `monitor.py`, `exit_check.py` — neither renders raw dollar
values), so this is a new but standard Python idiom, not a deviation from an existing one.

**CLI command shape (from `main.py:83-97`, `cmd_scan_heartbeat`):**
```python
def cmd_scan_insiders(args) -> None:
    from .insider_scan import render_insider_scan_report, run_discovery_scan, run_holdings_watch, write_insider_scan_report
    from .monitor import maybe_notify

    conn = _open_conn()
    watch_result = run_holdings_watch(conn)
    discovery_result = run_discovery_scan(conn)
    conn.close()
    write_insider_scan_report(watch_result, discovery_result)
    maybe_notify(
        {"new_alerts": watch_result["new_alerts"]},
        new_candidates=discovery_result["new_candidates"],
        alert_label="insider P/S filing(s) on current holdings",
    )
    print(
        f"Insider scan complete: {len(watch_result['new_alerts'])} holdings-watch alert(s), "
        f"{len(discovery_result['new_candidates'])} new discovery candidate(s). "
        f"See investments/goat/insider-scan-report.md"
    )
```

---

## IMPLEMENTATION PLAN

### Phase 1: Foundation

- Add `goat_insider_filings_seen` table + CRUD to `db.py`
- Append insider-scan config constants to `config.py`

### Phase 2: Core Implementation

- Build `openinsider.py` scraper (table parsing, `fetch_screener_filings`, `fetch_discovery_purchases`, `build_dedup_key`)
- Build `insider_scan.py` orchestrator (`run_holdings_watch`, `run_discovery_scan`, report render/write)

### Phase 3: Integration

- Extend `monitor.maybe_notify` with `alert_label` param
- Wire `cmd_scan_insiders` into `main.py` (subparser + dispatch)
- Extend `conftest.py`'s report-path isolation fixture

### Phase 4: Testing & Validation

- Unit tests for scraper (canned HTML, monkeypatched `requests.get`)
- Unit tests for orchestrator (monkeypatched collaborators, mirrors `test_heartbeat_scan.py`)
- Unit tests for new DB CRUD
- Regression test for `maybe_notify`'s new `alert_label` param
- Deploy systemd timer/service to VPS

---

## STEP-BY-STEP TASKS

Execute in order, top to bottom. Each task is atomic and independently testable.

### Task 1: CREATE `investments/goat/goat/openinsider.py`

- **IMPLEMENT**: OpenInsider scraper module:
  - `_HEADERS = {"User-Agent": config.GOAT_OPENINSIDER_USER_AGENT}`
  - `_EXPECTED_COLUMNS: dict[str, str]` — maps OpenInsider's header text (`"Filing Date"`,
    `"Trade Date"`, `"Ticker"`, `"Company Name"`, `"Insider Name"`, `"Title"`,
    `"Trade Type"`, `"Price"`, `"Qty"`, `"Owned"`, `"ΔOwn"`, `"Value"`) to internal snake_case
    field names. Build the column index map by reading the table's actual `<th>` header
    row text, NOT by hardcoded position — OpenInsider's table has extra leading columns
    (e.g. a filing-link icon column) not confirmed in the handoff's column list.
  - `_parse_money(text: str) -> float | None` — strips `$`, `,`, `+`, returns `None` on
    unparsable/empty/`"N/A"` text.
  - `_parse_table(html: str) -> list[dict] | None` — `BeautifulSoup(html, "html.parser")`,
    find the results table, build header→index map, extract rows, skip any row missing a
    ticker, split `Trade Type` on `" - "` (or first token) into `trade_type_code`
    (`"P"`/`"S"`/etc.), normalize ticker via `mytrader.tickers.normalize`, parse `value`
    via `_parse_money` and drop the row if unparsable. Returns `None` if the table itself
    isn't found (mirrors `sp500_universe.py:36-37`).
  - `_fetch(url: str, params: dict | None = None) -> list[dict] | None` — `import requests`
    inside the function (not top-level, matches `sp500_universe.py:25`), try/except
    returning `None` on any exception or non-200 status, delegates parsing to `_parse_table`.
  - `fetch_screener_filings(tickers_list: list[str], trade_type: str, min_value: float) -> list[dict] | None`
    — hits `{GOAT_OPENINSIDER_BASE_URL}/screener` with `params={"s": ",".join(tickers_list), "vl": str(int(min_value))}`.
    Returns `[]` immediately if `tickers_list` is empty (no request). Filters the parsed
    rows to `row["trade_type_code"] == trade_type` after fetch (belt-and-suspenders — do
    not assume the `vl`/`s` params alone are sufficient filtering).
  - `fetch_discovery_purchases() -> list[dict] | None` — hits
    `{GOAT_OPENINSIDER_BASE_URL}/latest-insider-purchases-25k` with no params, filters to
    `trade_type_code == "P"`.
  - `build_dedup_key(row: dict) -> str` — `"|".join([row["ticker"], row.get("filing_date",""), row.get("trade_date",""), row.get("insider_name",""), row["trade_type_code"], f"{row['value']:.2f}"])`.
    This is a synthesized natural key (not a scraped SEC accession number — parsing the
    filing-link `<a href>` for a true stable ID was considered but adds parsing
    complexity for marginal benefit at this scale; the synthesized key is unique enough
    in practice since two insiders filing the identical ticker/date/name/type/value combo
    on the same day is not a realistic collision).
- **PATTERN**: `investments/goat/goat/sp500_universe.py` (whole file) — same
  requests+BeautifulSoup+headers+timeout+try/except shape.
- **IMPORTS**: `from __future__ import annotations`; `from mytrader import tickers`;
  `from . import config` (module-level); `import requests` / `from bs4 import BeautifulSoup`
  local to functions that need them.
- **GOTCHA**: The handoff doc's column list (`Filing Date, Trade Date, Ticker, Company
  Name, Insider Name, Title, Trade Type, Price, Qty, Owned, ΔOwn (%), Value`) was
  confirmed via a live fetch on 2026-08-17 but the exact HTML table `class`/`id` attribute
  was NOT recorded in the handoff. Before writing the final selector, do a live
  `requests.get("http://openinsider.com/latest-insider-purchases-25k", headers=_HEADERS)`
  and inspect the actual table markup (OpenInsider's tables commonly use
  `class="tinytable"` — verify this, don't assume it). If the table isn't found by the
  first selector tried, fall back to the first `<table>` on the page that has a `<th>`
  matching `"Ticker"`.
- **GOTCHA**: `ΔOwn` uses a Greek delta character — match on `"ΔOwn"` and also handle a
  plain-ASCII fallback (`"Own"` sub-match) in case the live header text differs slightly
  from the handoff's transcription. This field isn't used downstream anyway (not in
  `_EXPECTED_COLUMNS`'s consumed set beyond storage), so a missed match here is low-risk.
- **VALIDATE**: `uv run --directory investments/goat python -c "from goat import openinsider; print(openinsider.fetch_discovery_purchases())"` — must return a non-empty list of dicts against the live site (manual/exploratory check, not part of the automated test suite).

### Task 2: UPDATE `investments/goat/goat/config.py`

- **IMPLEMENT**: Append after the `GOAT_GICS_TO_ETF_SECTOR_LABEL` block (after line 197):
  ```python
  # Insider trading scanner (OpenInsider), per investments/insider-trading-scanner-handoff.md
  # and Shaun's 2026-08-17 clarification: he's after large open-market sells (potential
  # "board member expects bad news" signal, plausibly $1M+) and $25k+ open-market buys.
  # P/S trade-type codes only -- excludes grants (A), option exercises (M), gifts (G),
  # tax-withholding sales (F), none of which reflect the same conviction signal.
  GOAT_OPENINSIDER_BASE_URL = "http://openinsider.com"
  GOAT_OPENINSIDER_USER_AGENT = "Mozilla/5.0 (compatible; SecondBrainGoat/1.0)"
  GOAT_INSIDER_PURCHASE_MIN_VALUE = 25_000  # matches OpenInsider's own
                                                # /latest-insider-purchases-25k floor
  GOAT_INSIDER_SALE_MIN_VALUE = 100_000  # matches OpenInsider's own
                                             # /latest-insider-sales-100k floor -- a floor,
                                             # not a cap, so multi-million-dollar sales are
                                             # included.
  GOAT_INSIDER_HOLDINGS_WATCH_LOOKBACK_DAYS = 5  # Form 4 must be filed within 2 US
      # business days of the trade -- 5 calendar days of slack covers weekends/holidays
      # on top of this scan's own daily cadence, without re-surfacing anything genuinely
      # stale. v1/tunable.
  GOAT_INSIDER_DISCOVERY_LOOKBACK_DAYS = 5  # same reasoning as above -- a safety net on
      # top of OpenInsider's own latest-first page ordering.
  GOAT_INSIDER_SCAN_REPORT_PATH = GOAT_DIR / "insider-scan-report.md"
  ```
- **PATTERN**: `config.py:12-41` (comment density/style), `config.py:57-62` (`GOAT_BANNED_TICKERS`, for the "why + date + who decided" comment convention).
- **VALIDATE**: `uv run --directory investments/goat python -c "from goat import config; print(config.GOAT_INSIDER_SCAN_REPORT_PATH)"`

### Task 3: UPDATE `investments/goat/goat/db.py`

- **IMPLEMENT**:
  1. Add to `init_goat_tables`'s `executescript` (after the `goat_sp500_constituents` table, before the closing `"""`):
     ```sql
     CREATE TABLE IF NOT EXISTS goat_insider_filings_seen (
         id              INTEGER PRIMARY KEY AUTOINCREMENT,
         dedup_key       TEXT NOT NULL UNIQUE,
         ticker          TEXT NOT NULL,
         filing_date     TEXT NOT NULL,
         trade_date      TEXT NOT NULL,
         insider_name    TEXT NOT NULL,
         trade_type      TEXT NOT NULL,
         value           REAL NOT NULL,
         kind            TEXT NOT NULL,
         seen_at         TEXT NOT NULL
     );
     ```
  2. Add two new functions (place after `get_sp500_constituents` at the end of the file):
     ```python
     def insert_goat_insider_filing_seen(
         conn: sqlite3.Connection, *, dedup_key: str, ticker: str, filing_date: str,
         trade_date: str, insider_name: str, trade_type: str, value: float, kind: str,
     ) -> bool:
         """Returns True if this filing was newly seen (inserted), False if it's a
         duplicate of a filing already alerted/staged in a prior run."""
         with conn:
             cur = conn.execute(
                 """INSERT OR IGNORE INTO goat_insider_filings_seen
                    (dedup_key, ticker, filing_date, trade_date, insider_name, trade_type, value, kind, seen_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                 (dedup_key, ticker, filing_date, trade_date, insider_name, trade_type, value, kind, _now()),
             )
             return cur.rowcount == 1


     def get_recent_insider_filings_seen(
         conn: sqlite3.Connection, kind: str | None = None, limit: int = 50
     ) -> list[sqlite3.Row]:
         if kind is not None:
             return conn.execute(
                 "SELECT * FROM goat_insider_filings_seen WHERE kind = ? ORDER BY seen_at DESC LIMIT ?",
                 (kind, limit),
             ).fetchall()
         return conn.execute(
             "SELECT * FROM goat_insider_filings_seen ORDER BY seen_at DESC LIMIT ?", (limit,)
         ).fetchall()
     ```
- **PATTERN**: `db.py:96-114` (`insert_goat_pending_candidate` / `delete_goat_pending_candidate` — INSERT OR IGNORE and rowcount-return idioms).
- **VALIDATE**: `uv run --directory investments/goat python -m pytest goat/tests/test_db.py -q` (after Task 10 adds new tests here)

### Task 4: CREATE `investments/goat/goat/insider_scan.py`

- **IMPLEMENT**: Orchestrator module per the exact code sketch in "Patterns to Follow" and
  the design decisions above:
  - `_within_lookback(trade_date_str: str, lookback_days: int) -> bool` — parses
    `trade_date_str` as `"%Y-%m-%d"` (verify this is OpenInsider's actual date format
    during Task 1's live check — adjust the format string if different), compares to
    `date.today()`. Returns `True` (don't drop the filing) if the date string is
    unparsable — never silently discard a real filing due to a parsing edge case.
  - `run_holdings_watch(conn) -> dict[str, Any]`:
    - `held_tickers = sorted({row["ticker"] for row in mt_db.get_all_holdings(conn)})`
    - If `held_tickers` is empty, skip the fetch entirely and return zeroed results.
    - Fetch purchases (`GOAT_INSIDER_PURCHASE_MIN_VALUE`) and sales
      (`GOAT_INSIDER_SALE_MIN_VALUE`) via two separate `openinsider.fetch_screener_filings`
      calls (one per trade type — matches the "handful of requests, not per-ticker"
      etiquette).
    - If BOTH return `None` (total fetch failure), print a `[goat-insider-scan] ...`
      message and return zeroed results — do not raise, do not partially process.
    - For each row (from whichever of purchases/sales succeeded), skip if outside
      `GOAT_INSIDER_HOLDINGS_WATCH_LOOKBACK_DAYS`, build `dedup_key`, call
      `db.insert_goat_insider_filing_seen(..., kind="holdings_watch")` — skip if not
      newly inserted (already alerted in a prior run).
    - For each newly-seen filing, build a detail string: `f"{insider_name} ({title}) {bought|sold} ${value:,.0f} of {ticker} on {trade_date}"`
      and append `{"ticker": ticker, "message": detail}` to `new_alerts`.
    - Return `{"checked_holdings": len(held_tickers), "new_alerts": new_alerts, "recent_filings": [dict(r) for r in db.get_recent_insider_filings_seen(conn, kind="holdings_watch")]}`.
  - `run_discovery_scan(conn) -> dict[str, Any]`:
    - `rows = openinsider.fetch_discovery_purchases()`; if `None`, print a
      `[goat-insider-scan] ...` message and treat as `[]` (empty, not a crash).
    - For each row: skip if outside `GOAT_INSIDER_DISCOVERY_LOOKBACK_DAYS`; skip if
      `ticker in config.GOAT_BANNED_TICKERS`; run the standard 3-way dedup
      (`mt_db.get_holding_row`, `mt_db.get_watchlist_row`, `db.get_goat_pending_candidate`);
      call `db.insert_goat_insider_filing_seen(..., kind="discovery")`, skip if not newly
      inserted.
    - For each newly-staged filing, build `signal_detail` (same shape as holdings-watch's
      detail string, but always "bought" since discovery is purchases-only), call
      `db.insert_goat_pending_candidate(conn, ticker=ticker, sector_label="Insider Buy", signal_detail=signal_detail, source="goat_insider_discovery")`,
      append `{"ticker": ticker, "sector_label": "Insider Buy", "detail": signal_detail}`
      to `new_candidates`.
    - Return `{"new_candidates": new_candidates, "pending_candidates": [dict(r) for r in db.get_all_goat_pending_candidates(conn) if r["source"] == "goat_insider_discovery"]}`.
  - `render_insider_scan_report(watch_result, discovery_result) -> str` — combined
    markdown, two sections ("Holdings Watch" — list of `new_alerts` or "No new insider
    activity on current holdings."; "Discovery Candidates — Pending Review" — table of
    `pending_candidates`, same 3-column shape as `heartbeat_scan.render_heartbeat_candidates_report`
    minus the sector column, or keep it since `sector_label="Insider Buy"` is always the
    same value — your call, but stay consistent with the other two candidate-report tables'
    column shape for a familiar reading experience). Ends with `promote-candidate`/`dismiss-candidate`
    instructions, same wording convention as the other two reports.
  - `write_insider_scan_report(watch_result, discovery_result) -> None` — writes to
    `config.GOAT_INSIDER_SCAN_REPORT_PATH`.
- **PATTERN**: `investments/goat/goat/heartbeat_scan.py:21-117` (whole file) for the
  overall shape; `investments/goat/goat/monitor.py:46-68` (`run_monitor`) for the
  holdings-iteration shape.
- **IMPORTS**: `from __future__ import annotations`; `import sqlite3`;
  `from datetime import date, datetime`; `from typing import Any`;
  `from mytrader import db as mt_db`; `from . import config, db, openinsider`.
- **GOTCHA**: Do NOT wrap filings in `mytrader.checks.CheckResult` — that dataclass models
  a computed pass/fail check against a continuous signal (`verdict: "ok"|"flag"|"info"|"unknown"`),
  which doesn't fit a raw discrete event like "insider X sold $Y of ticker Z on date D".
  Work with plain dicts throughout, matching the shape `monitor.maybe_notify` already
  expects (`{"ticker": ..., "message": ...}` for alerts, `{"ticker": ..., "sector_label": ..., "detail": ...}` for candidates).
- **GOTCHA**: `goat_alert_history`'s open/acknowledge semantics (`get_open_goat_alert` /
  `acknowledge_goat_alert`) model a *continuous state* that can turn on and back off
  (e.g. "closed below 150DMA" → later "recovered above it", auto-acknowledged). An
  insider filing is a one-time discrete event with no "recovery" to auto-acknowledge —
  using that table's dedup would incorrectly suppress a second, later, genuinely-different
  insider sale on the same ticker while the first "alert" sits unacknowledged. This is
  why this feature uses the new `goat_insider_filings_seen` table (dedup by filing
  identity) instead of `goat_alert_history` (dedup by ticker+check_name, assuming a
  single ongoing condition).
- **VALIDATE**: `uv run --directory investments/goat python -m pytest goat/tests/test_insider_scan.py -q` (after Task 9)

### Task 5: UPDATE `investments/goat/goat/monitor.py`

- **IMPLEMENT**: Change `maybe_notify`'s signature (line 109) from:
  ```python
  def maybe_notify(result: dict[str, Any], new_candidates: list[dict[str, Any]] | None = None) -> None:
  ```
  to:
  ```python
  def maybe_notify(
      result: dict[str, Any], new_candidates: list[dict[str, Any]] | None = None,
      alert_label: str = "below 150DMA exit threshold",
  ) -> None:
  ```
  and change line 128 from:
  ```python
  parts.append(f"{n_alerts} holding(s) below 150DMA exit threshold")
  ```
  to:
  ```python
  parts.append(f"{n_alerts} holding(s) {alert_label}")
  ```
- **PATTERN**: The existing `new_candidates` param is already a precedent for extending
  this function's reuse across scan types without breaking existing callers.
- **GOTCHA**: This is a shared function called by `cmd_monitor` and `cmd_check_live` (both
  in `main.py`) with no `alert_label` arg — the default value MUST reproduce today's exact
  wording (`"below 150DMA exit threshold"`) so those two callers are unaffected. Do not
  change the default.
- **VALIDATE**: `uv run --directory investments/goat python -m pytest goat/tests/test_monitor.py -q` — all existing `maybe_notify` tests must still pass unmodified (they don't pass `alert_label`, so they exercise the default).

### Task 6: UPDATE `investments/goat/goat/main.py`

- **IMPLEMENT**:
  1. Add `cmd_scan_insiders` (place after `cmd_scan_heartbeat`, before `cmd_promote_candidate`):
     ```python
     def cmd_scan_insiders(args) -> None:
         from .insider_scan import run_discovery_scan, run_holdings_watch, write_insider_scan_report
         from .monitor import maybe_notify

         conn = _open_conn()
         watch_result = run_holdings_watch(conn)
         discovery_result = run_discovery_scan(conn)
         conn.close()
         write_insider_scan_report(watch_result, discovery_result)
         maybe_notify(
             {"new_alerts": watch_result["new_alerts"]},
             new_candidates=discovery_result["new_candidates"],
             alert_label="insider P/S filing(s) on current holdings",
         )
         print(
             f"Insider scan complete: {len(watch_result['new_alerts'])} holdings-watch alert(s), "
             f"{len(discovery_result['new_candidates'])} new discovery candidate(s). "
             f"See investments/goat/insider-scan-report.md"
         )
     ```
  2. Add subparser in `main()` (after the `scan-heartbeat` subparser, before `promote-candidate`):
     ```python
     subparsers.add_parser(
         "scan-insiders",
         help="Daily OpenInsider Form 4 scan -- holdings-watch (P/S on held tickers) + market-wide $25k+ purchase discovery",
     )
     ```
  3. Add to the `dispatch` dict: `"scan-insiders": cmd_scan_insiders,`
- **PATTERN**: `main.py:83-97` (`cmd_scan_heartbeat`), `main.py:157-160` (subparser registration for `scan-heartbeat`).
- **VALIDATE**: `uv run --directory investments/goat python -m goat.main scan-insiders` — must run end-to-end without error and print the summary line (live network call; acceptable for manual validation, not part of automated tests).

### Task 7: UPDATE `investments/goat/goat/tests/conftest.py`

- **IMPLEMENT**: Add one line to `_isolate_goat_report_path` (after line 34):
  ```python
  monkeypatch.setattr(
      goat_config, "GOAT_INSIDER_SCAN_REPORT_PATH", tmp_path / "insider-scan-report.md"
  )
  ```
- **PATTERN**: `conftest.py:29-35` (existing two-line pattern for `GOAT_MONITOR_REPORT_PATH` / `GOAT_HEARTBEAT_CANDIDATES_MD_PATH`).
- **GOTCHA**: Without this, any test that calls `write_insider_scan_report` would write into
  the real `investments/goat/insider-scan-report.md` during test runs — this fixture is
  `autouse=True`, so it's required, not optional.
- **VALIDATE**: N/A standalone — verified by Task 9's tests passing without touching the real report file.

### Task 8: CREATE `investments/goat/goat/tests/test_openinsider.py`

- **IMPLEMENT**: Test cases (mirror `test_sp500_universe.py`'s `_FakeResponse` + `monkeypatch.setattr("requests.get", ...)` pattern):
  - `test_fetch_discovery_purchases_parses_table_and_filters_purchase_code` — canned HTML
    with a header row (`Filing Date, Trade Date, Ticker, Company Name, Insider Name,
    Title, Trade Type, Price, Qty, Owned, ΔOwn, Value`) and 2+ data rows, at least one
    `"P - Purchase"` and one `"S - Sale"` row — assert only the `P` row is returned, and
    that `value` is parsed to a float (e.g. `"$1,234,567"` → `1234567.0`).
  - `test_fetch_discovery_purchases_returns_none_on_missing_table` — HTML with no matching table → `None`.
  - `test_fetch_discovery_purchases_returns_none_on_bad_status` — status 500 → `None`.
  - `test_fetch_discovery_purchases_returns_none_on_network_error` — `requests.get` raises → `None`.
  - `test_fetch_screener_filings_builds_correct_params` — monkeypatch `requests.get` to a
    function that records `params` and returns a `_FakeResponse` with canned HTML; assert
    `params["s"]` contains the joined ticker list and `params["vl"]` matches the passed
    `min_value`.
  - `test_fetch_screener_filings_returns_empty_list_without_request_when_no_tickers` —
    call with `tickers_list=[]`, assert result is `[]` and `requests.get` was never called
    (monkeypatch a call-tracking stub).
  - `test_fetch_screener_filings_filters_to_requested_trade_type` — canned HTML with both
    P and S rows, call with `trade_type="S"`, assert only S rows returned.
  - `test_parse_table_normalizes_dotted_tickers` — a row with `BRK.B` → asserts `BRK-B` in
    output (same normalization precedent as `test_sp500_universe.py:23-30`).
  - `test_build_dedup_key_is_stable_and_order_sensitive` — same row dict twice produces
    the same key; changing any one field (value, trade_date, etc.) produces a different key.
- **PATTERN**: `investments/goat/goat/tests/test_sp500_universe.py` (whole file).
- **VALIDATE**: `uv run --directory investments/goat python -m pytest goat/tests/test_openinsider.py -v`

### Task 9: CREATE `investments/goat/goat/tests/test_insider_scan.py`

- **IMPLEMENT**: Test cases (mirror `test_heartbeat_scan.py`'s `_patch_common` monkeypatch-every-collaborator style, and `test_monitor.py`'s `_seed_holding` helper):
  - `test_run_holdings_watch_alerts_on_new_sale_filing` — seed a holding (e.g. VRTX),
    monkeypatch `goat.insider_scan.openinsider.fetch_screener_filings` to return a
    canned S filing for VRTX on the purchase call empty / sale call populated; assert
    `len(result["new_alerts"]) == 1` and the message contains the ticker and dollar value.
  - `test_run_holdings_watch_stays_quiet_on_repeat_run` — same filing across two calls to
    `run_holdings_watch`; second run's `new_alerts == []` (dedup via `goat_insider_filings_seen`).
  - `test_run_holdings_watch_skips_fetch_when_no_holdings` — empty holdings table; assert
    `openinsider.fetch_screener_filings` is never called (call-tracking monkeypatch) and
    result is zeroed.
  - `test_run_holdings_watch_handles_total_fetch_failure_gracefully` — both
    purchases/sales fetches monkeypatched to return `None`; must not raise, `new_alerts == []`.
  - `test_run_holdings_watch_ignores_filing_outside_lookback_window` — a filing with
    `trade_date` older than `GOAT_INSIDER_HOLDINGS_WATCH_LOOKBACK_DAYS`; assert it's excluded.
  - `test_run_discovery_scan_stages_new_purchase_candidate` — monkeypatch
    `openinsider.fetch_discovery_purchases` to return one fresh-dated $30k purchase for a
    ticker not held/watchlisted/pending; assert `len(result["new_candidates"]) == 1` and
    `goat_db.get_goat_pending_candidate(conn, ticker)["source"] == "goat_insider_discovery"`.
  - `test_run_discovery_scan_skips_ticker_already_a_holding` — mirrors `test_run_heartbeat_scan_skips_ticker_already_a_holding`.
  - `test_run_discovery_scan_skips_ticker_already_in_watchlist` — mirrors the watchlist equivalent.
  - `test_run_discovery_scan_skips_banned_ticker` — a candidate ticker in `config.GOAT_BANNED_TICKERS` (monkeypatch the set to include a test ticker) is never staged.
  - `test_run_discovery_scan_stays_quiet_on_repeat_run` — same filing across two calls; second run's `new_candidates == []`, `pending_candidates` still has exactly one row.
  - `test_run_discovery_scan_handles_fetch_failure_gracefully` — `fetch_discovery_purchases` returns `None`; must not raise, `new_candidates == []`.
  - `test_render_insider_scan_report_lists_alerts_and_pending_candidates` — canned
    `watch_result`/`discovery_result` dicts; assert ticker, dollar detail, and "No new
    insider activity" (empty case) all render correctly.
- **PATTERN**: `investments/goat/goat/tests/test_heartbeat_scan.py` (whole file), `investments/goat/goat/tests/test_monitor.py:30-46` (`_seed_holding`).
- **VALIDATE**: `uv run --directory investments/goat python -m pytest goat/tests/test_insider_scan.py -v`

### Task 10: UPDATE `investments/goat/goat/tests/test_db.py`

- **IMPLEMENT**: Append tests for the new table (mirror the existing `goat_pending_candidates` test block at lines 45-86):
  - `test_insert_goat_insider_filing_seen_returns_true_on_first_insert`
  - `test_insert_goat_insider_filing_seen_returns_false_on_duplicate_dedup_key`
  - `test_get_recent_insider_filings_seen_filters_by_kind`
  - `test_get_recent_insider_filings_seen_orders_newest_first`
- **PATTERN**: `investments/goat/goat/tests/test_db.py:45-86`.
- **VALIDATE**: `uv run --directory investments/goat python -m pytest goat/tests/test_db.py -v`

### Task 11: UPDATE `investments/goat/goat/tests/test_monitor.py`

- **IMPLEMENT**: Add one regression test after the existing `maybe_notify` test block
  (after line 184):
  ```python
  def test_maybe_notify_uses_custom_alert_label(monkeypatch):
      toast_calls, whatsapp_calls = [], []
      monkeypatch.setitem(sys.modules, "notifications", _fake_notifications_module(toast_calls, whatsapp_calls))

      monitor.maybe_notify(
          {"new_alerts": [{"ticker": "VRTX", "message": "sold $2,000,000 of VRTX"}]},
          alert_label="insider P/S filing(s) on current holdings",
      )
      (message,), _kwargs = whatsapp_calls[0]
      assert "insider P/S filing(s) on current holdings" in message
      assert "below 150DMA exit threshold" not in message
  ```
- **PATTERN**: `test_monitor.py:176-184` (`test_maybe_notify_sends_whatsapp_with_ticker_detail`).
- **VALIDATE**: `uv run --directory investments/goat python -m pytest goat/tests/test_monitor.py -v`

### Task 12: CREATE `scripts/systemd/second-brain-goat-insider-scan.timer` and `.service`

- **IMPLEMENT**:
  `second-brain-goat-insider-scan.service`:
  ```ini
  [Unit]
  Description=Goat Insider Trading Scan
  After=network.target

  [Service]
  Type=oneshot
  User=secondbrain
  WorkingDirectory=/home/secondbrain/second-brain/investments/goat
  ExecStart=/home/secondbrain/second-brain/investments/.venv/bin/python -m goat.main scan-insiders
  StandardOutput=append:/home/secondbrain/second-brain/investments/goat/insider_scan_runs.log
  StandardError=append:/home/secondbrain/second-brain/investments/goat/insider_scan_runs.log
  ```
  `second-brain-goat-insider-scan.timer`:
  ```ini
  [Unit]
  Description=Goat Insider Trading Scan Timer
  Requires=second-brain-goat-insider-scan.service

  [Timer]
  OnCalendar=*-*-* 21:50:00 UTC
  Persistent=true

  [Install]
  WantedBy=timers.target
  ```
- **PATTERN**: `scripts/systemd/second-brain-goat-heartbeat-scan.service` and
  `second-brain-goat-monitor.timer:6` (cadence convention — 21:50 UTC runs 15 minutes
  after the existing 21:35 UTC goat-monitor timer, avoiding overlap).
- **GOTCHA**: This is a **manual deployment step** — creating these files does not deploy
  them. Per CLAUDE.md's deploy workflow, actually registering + enabling the timer on the
  VPS (`scp` the two files, `systemctl daemon-reload`, `systemctl enable --now second-brain-goat-insider-scan.timer`)
  is Shaun's call to run himself (SSH access required) or to explicitly ask for as a
  follow-up — do not attempt this from within the plan-execution session.
- **VALIDATE**: N/A (files only; VPS registration is a separate manual step per the GOTCHA above).

---

## TESTING STRATEGY

### Unit Tests

All new logic (scraper parsing, orchestrator dedup/staging, DB CRUD, `maybe_notify`
extension) gets unit tests following this project's existing `pytest` + `monkeypatch`
conventions — no live network calls in the automated suite (every `requests.get` call is
monkeypatched, matching `test_sp500_universe.py`'s and `test_heartbeat_scan.py`'s
precedent).

### Integration Tests

None planned beyond the orchestrator-level tests in Task 9, which already exercise the
full `run_holdings_watch`/`run_discovery_scan` flow against a real (test) SQLite
connection via the `db_conn` fixture — this matches the project's existing "integration"
depth for `heartbeat_scan.py` and `monitor.py` (no separate integration test tier exists
in this package).

### Edge Cases

- Empty holdings table (no tickers to check) — `run_holdings_watch` must skip the fetch entirely.
- Total scraper fetch failure (network down / site restructured) — both halves must
  degrade gracefully (log + continue), never raise, never wipe the previous report.
- Same filing appearing again on a subsequent day's lookback window (dedup via
  `goat_insider_filings_seen`) — must not re-alert or re-stage.
- A discovery candidate ticker that gets promoted or added as a holding between scans —
  the 3-way dedup naturally prevents re-staging, matching existing precedent.
- Unparsable trade date — must not crash `_within_lookback`, and must not silently drop a
  real filing (fail open, not closed).
- `BRK.B`-style dotted tickers from OpenInsider — must normalize via `mytrader.tickers.normalize`.

---

## VALIDATION COMMANDS

### Level 1: Syntax & Style
```powershell
uv run --directory investments/goat ruff check goat/
uv run --directory investments/goat mypy goat/openinsider.py goat/insider_scan.py
```

### Level 2: Unit Tests
```powershell
uv run --directory investments/goat python -m pytest -q
```

### Level 3: Integration Tests
Covered by Level 2 (see Testing Strategy — no separate tier in this package).

### Level 4: Manual Validation
```powershell
uv run --directory investments/goat python -m goat.main scan-insiders
```
Confirm `investments/goat/insider-scan-report.md` is created/updated, and (if any hits
fired) a WhatsApp message arrives with ticker + dollar detail. Re-run immediately and
confirm the second run reports zero new alerts/candidates for anything already seen
(dedup working).

### Level 5: Additional Validation
N/A — no MCP servers relevant to this feature.

---

## ACCEPTANCE CRITERIA

- [ ] `scan-insiders` CLI command runs end-to-end and writes `insider-scan-report.md`
- [ ] Holdings-watch alerts fire immediately via WhatsApp with ticker + dollar value in the message
- [ ] Discovery candidates stage into `goat_pending_candidates` with `source="goat_insider_discovery"` and are promotable/dismissible via the existing commands unchanged
- [ ] Same filing never re-alerts or re-stages on a subsequent run (dedup via `goat_insider_filings_seen`)
- [ ] `P`/`S` trade types only — grants/exercises/gifts/tax-withholding sales never surface
- [ ] Existing `maybe_notify` callers (`cmd_monitor`, `cmd_check_live`) produce byte-identical WhatsApp/toast wording to before this change
- [ ] All validation commands pass with zero errors
- [ ] No regressions in existing Goat test suite
- [ ] Code follows existing Goat package conventions (comment density in `config.py`, dict-based results, `[goat-insider-scan]`-prefixed log lines)

---

## COMPLETION CHECKLIST

- [ ] All 12 tasks completed in order
- [ ] Each task's validation command passed immediately after that task
- [ ] Full `investments/goat` test suite passes (`uv run --directory investments/goat python -m pytest -q`)
- [ ] `ruff check` and `mypy` clean on the two new modules
- [ ] Manual `scan-insiders` run confirmed against the live OpenInsider site
- [ ] Acceptance criteria all met
- [ ] Systemd timer/service files created (VPS registration left as an explicit follow-up for Shaun, per Task 12's GOTCHA)

---

## NOTES

- **Why not `CheckResult`/`goat_alert_history`**: this feature's core shape (discrete,
  one-time events vs. a continuous threshold condition) doesn't fit either of the two
  existing abstractions cleanly. Rather than force-fit and produce confusing semantics
  (see Task 4's GOTCHAs), this plan introduces one small new table
  (`goat_insider_filings_seen`) purpose-built for "have I already told Shaun about this
  specific filing" dedup. This is a deliberate deviation from "always mirror an existing
  pattern exactly" — flagged explicitly rather than silently invented.
- **Deferred (per the original handoff, still deferred here)**: same-day/intraday Form 4
  alerting (would need direct SEC EDGAR polling, not OpenInsider's own lag), any kind of
  insider-conviction scoring model, and a SEC EDGAR XML fallback path if OpenInsider ever
  becomes unreliable.
- **`sector_label="Insider Buy"`**: reusing `goat_pending_candidates`'s `NOT NULL
  sector_label` column for a non-sector signal is a minor cosmetic compromise (chosen
  over adding a nullable column or a dedicated table) — accepted because it keeps
  `promote-candidate`/`dismiss-candidate` working unchanged against every candidate
  source, and reads sensibly in both the report table and the WhatsApp alert line
  (`"AAPL (Insider Buy): ..."`).
