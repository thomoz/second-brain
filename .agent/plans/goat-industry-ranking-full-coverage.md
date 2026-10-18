# Feature: Full-Coverage Industry Rotation Ranking (144/144 industries, Finviz Groups)

The following plan should be complete, but it's important to validate documentation and
codebase patterns and task sanity before implementing. Pay special attention to naming
of existing utils/types/models — import from the right files.

## Feature Description

A new, additive industry-rotation ranking report covering **every** Finviz industry
(144, not just the 39 that happen to have a dedicated ETF), built by scraping Finviz's
own "Groups" performance view — a single free page that already aggregates return data
by industry, the same way commercial tools like Felix Prehn's Winston app ("Stock
Radar") present industry-level money-flow screens.

## User Story

As Shaun, running several businesses and investing on the side,
I want an industry rotation ranking that covers all ~144 Finviz industries, not just
the 39 with a dedicated ETF,
So that I can see rotation across the full market the way a Winston-style "money
flowing in/out by industry" screen does, without having to build or pay for a
constituent-stock aggregation pipeline.

## Problem Statement

`investments/goat/goat/industry_rotation.py` ranks industries by the price return of
one representative ETF per industry (`GOAT_INDUSTRY_ETFS`), which only covers 39 of
Finviz's 144 industries — the other 105 simply have no dedicated, currently-trading
ETF and are listed as "Not Covered" in `industry-ranking.md`. Shaun asked how tools
like Winston cover the full ~150-industry taxonomy and whether reaching that requires
a paid API. Initial framing in conversation assumed the answer was constituent-stock
aggregation (classify thousands of individual stocks into industries via yfinance,
then average their returns) — doable, but meaningfully more engineering (universe
breadth, many more yfinance calls, rate-limit pacing, an aggregation-method choice).

## Solution Statement

**Live research during this planning pass found a much simpler path that supersedes
that initial framing.** Finviz's own "Groups" view
(`finviz.com/groups.ashx?g=industry&v=140`) already aggregates performance by
industry server-side and returns **all 144 industries in a single free HTTP request**
with six ready-made return windows (Perf Week/Month/Quarter/Half/Year/YTD) — this is
almost certainly how Winston-style industry screens work under the hood: constituent
aggregation done by *someone else's* servers, surfaced through Finviz's UI, scraped
for free. No yfinance calls, no per-stock classification, no new rate-limit exposure,
no paid API of any kind.

This plan adds a brand-new, fully additive sibling report (`industry-ranking-full.md`)
built from that one page. It does **not** touch, replace, or extend the existing
39-industry ETF-based ranking (`industry_rotation.py`), its breakout-signal/candidate
-staging pipeline (`monitor.run_industry_scan`), the industry-heartbeat gate
(`industry_heartbeat_scan.py`), or the hated-industries severity gate
(`hated_industries_scan.py`) — all of those mechanically require a daily price
*series* (for 50DMA-cross detection / drawdown-from-52-week-high), which Finviz's
Groups page does not provide (it only gives period-return percentages, not daily
closes). Those tools keep working exactly as they do today, unchanged.

## Feature Metadata

**Feature Type**: New Capability (additive sibling report inside the existing `goat`
package — not a new workspace package, not a modification of any existing one)
**Estimated Complexity**: Low (one new free single-page scrape, no DB, no yfinance,
no pagination, no ticker-watermark handling — genuinely simpler than every other
Finviz-scraping module already in this codebase)
**Primary Systems Affected**: `investments/goat/` only (new modules + config + one new
CLI subcommand + one new systemd timer). Zero changes to `investments/my-trader/`,
`investments/briefs-finance/`, or any other sibling package.
**Dependencies**: `requests`, `beautifulsoup4` (both already `goat`/`my-trader`
dependencies — no new dependency needed)

---

## DECISIONS RESOLVED (read first — these answer the plan-feature prompt's open questions)

**1. Data source: Finviz Groups page, not constituent-stock aggregation via yfinance.**
LIVE-VERIFIED 2026-10-18 during this planning pass:
`https://finviz.com/groups.ashx?g=industry&v=140` (using the same
`mytrader.config.FINVIZ_USER_AGENT` header `finviz_screener.py` already uses) returns
HTTP 200 and one HTML `<table>` with headers
`['No.', 'Name', 'Perf Week', 'Perf Month', 'Perf Quart', 'Perf Half', 'Perf Year',
'Perf YTD', 'Avg Volume', 'Rel Volume', 'Change %', 'Volume']` and **145 `<tr>` rows
(144 data rows + 1 header row)** — e.g. row 1 `['1', 'Advertising Agencies', '-1.24%',
'-11.71%', '-27.69%', '-32.96%', '-47.16%', '-50.25%', '50.47M', '0.76', '-3.50%',
'38.22M']`, row 144 `['144', 'Waste Management', '7.09%', '5.30%', '-0.42%', '4.43%',
'2.99%', '3.19%', '24.01M', '1.24', '1.02%', '29.82M']`. This is the **same page**
`GOAT_FINVIZ_INDUSTRIES`'s 143/144-label canonical list was originally sourced from
(`investments/goat/goat/config.py:96`, "Full taxonomy sourced from
finviz.com/groups?g=industry, fetched 2026-08-23") — nobody previously noticed that
page also carries live per-industry performance data in its `v=140` ("Performance")
view, not just the static label list captured on 2026-08-23. (Note the real path is
`groups.ashx`, not the bare `groups` the 2026-08-23 comment used — a corrected detail,
not a design change.) No ticker column exists on this page (rows are industry names,
not stock tickers), so Finviz's unauthenticated-scraper ticker-watermarking
(`finviz_screener._descramble_ticker`'s whole reason to exist) **does not apply
here** — this scrape is structurally simpler than `finviz_screener.py`'s.

**2. Purely additive — zero changes to any existing file's *behavior*.** The four
existing consumers of the 39-industry ETF map
(`industry_rotation.py`/`monitor.run_industry_scan`, `industry_heartbeat_scan.py`,
`hated_industries_scan.py`, `rotation_flow.py`'s snapshot diffing) all need a daily
price *series* to do what they do (MA-cross detection, 52-week-high drawdown, day-over
-day snapshot diffing) — Finviz Groups gives only point-in-time period-return
percentages, not a price series, so it structurally cannot replace or feed any of
them. This plan adds a new, independent module pair and a new, independent report
file; `GOAT_INDUSTRY_ETFS`, `GOAT_FINVIZ_INDUSTRY_SLUGS`, and every existing Goat
module are untouched.

**3. New report file, not a new section in the existing `industry-ranking.md`.**
`render_industry_ranking_report` (`monitor.py:430`) fully overwrites
`industry-ranking.md` via `.write_text(...)` on every Goat Monitor run
(`GOAT_INDUSTRY_RANKING_MD_PATH`, `config.py:156`) and on every on-demand
`scan-industries` run (`main.py:117`). Writing a second, independent section into
that same path from a different command would mean whichever of the two writers ran
most recently wins, silently erasing the other's content. A dedicated new path
(`GOAT_INDUSTRY_FULL_RANKING_MD_PATH` → `industry-ranking-full.md`) avoids that
collision entirely — same "give every independent writer its own file" discipline
`ai_resistant_moat_scanner` and `dma_breakout_scan` already follow for their own
report pairs.

**4. Ranking window + report shape.** Finviz gives six ready-made windows for free
(Week/Month/Quarter/Half/Year/YTD) — richer than anything built in this codebase so
far. Primary sort/rank column is **Perf Half** (the closest existing-convention match
to `GOAT_INDUSTRY_RANK_WINDOW_TRADING_DAYS`'s ~6-month long window); **Perf Week**
doubles as the existing short-window concept
(`GOAT_ROTATION_SHORT_WINDOW_TRADING_DAYS`, 1 trading week) with zero extra fetch,
since it's already a column on the same scraped row. Report shape mirrors
`render_industry_ranking_report`'s existing Top 5 Rising / Bottom 5 Falling / Full
Ranking structure (`monitor.py:430-460`) — but with **no "Not Covered" section**
(nothing is uncovered here) and **all six Perf columns shown** in the full table
(free, already on the row, no reason to drop the other five).

**5. No DB table, no candidate staging, no WhatsApp alert, no chart — deliberately
v1-minimal.** This is a pure informational ranking, same explicit scope boundary the
original `industry-rotation-handoff.md` set ("ranking + chart only... not a new
Goat signal/candidate type") — there is no "opportunity" or "breakout" concept to
stage here, so no `goat_pending_candidates` row, no `promote-candidate`/
`dismiss-candidate`, no notify.py. **Charting is explicitly NOT extended to this data
source** — Finviz Groups has no daily price series to rebase-to-100 and plot; that
capability (if ever built per the original handoff's deferred Phase 3) stays
exclusive to the 39 ETF-backed industries that have real yfinance price history via
`price_history.py`. **Rotation-snapshot/day-over-day flow tracking is also deferred**
— `goat_rotation_snapshots`' schema (`db.py:92-103`) already has a generic
`scope TEXT NOT NULL` column and a `UNIQUE(scope, snapshot_date, ticker)` constraint
that could hold a new `scope="industry_full"` with zero migration (using the
industry *name* as the `ticker` field, a deliberate repurposing — `rank`/
`return_pct`/`return_pct_1w` already fit this report's own Perf Half/Perf Week
numbers) — flagged as a natural, low-effort v2 if Shaun later wants trend-tracking
here too, **not built in this plan**.

**6. Sanity cross-check against the existing canonical list.** Both
`GOAT_FINVIZ_INDUSTRIES` (`config.py:98-146`) and this new scrape are sourced from the
same Finviz page, so the 144 scraped `Name` values should match that embedded list
exactly. A test asserting this (`set(scraped names) == set(config.GOAT_FINVIZ_INDUSTRIES)`
against a live-shaped fixture) is cheap insurance against future taxonomy drift — not
a runtime gate (a real scrape mismatch should widen the report, not crash it, same
fail-safe posture as every other Finviz scrape in this codebase).

---

## CONTEXT REFERENCES

### Relevant Codebase Files — READ THESE BEFORE IMPLEMENTING

- `investments/my-trader/mytrader/finviz_screener.py` (whole file, 187 lines) — the
  scraping pattern to mirror for **structure** (headers dict from
  `config.FINVIZ_USER_AGENT`, `requests.get(..., timeout=30)`, BeautifulSoup table
  parse, "valid page vs. no data vs. not a real page" tri-state return) but this new
  scrape is **simpler**: one page, no pagination loop, no ticker-watermark
  descrambling (no ticker column at all on the Groups page).
- `investments/goat/goat/industry_rotation.py` (whole file, 123 lines) — the sibling
  module this new one sits next to. `rank_industries` (lines 29-58) is the closest
  shape to mirror for `rank_all_industries`, but simpler (no `closes: dict[str,
  pd.Series]` fetch step — Finviz already returns the return percentages directly,
  no price series to compute a return from).
- `investments/goat/goat/monitor.py` lines 430-500 (`render_industry_ranking_report`)
  — the exact report-shape precedent (Top 5 Rising / Bottom 5 Falling / Full Ranking
  tables, `_today_sydney()` date stamping) to mirror for the new report, minus the
  "Not Covered" / rotation-flow / heartbeat-gate sections (none apply here — see
  Decision #5).
- `investments/goat/goat/config.py` lines 93-244 — read this whole section for full
  context: `GOAT_FINVIZ_INDUSTRIES` (144-label canonical list, line 98), its own
  sourcing comment pointing at the exact page this plan scrapes (line 96),
  `GOAT_INDUSTRY_RANKING_MD_PATH` (line 156), `GOAT_ROTATION_SHORT_WINDOW_TRADING_DAYS`
  (line 171), `GOAT_FINVIZ_INDUSTRY_SLUGS` (line 199) — none of these are modified by
  this plan, but the execution agent needs to see them to understand why they're
  untouched (Decision #2) and to place the new constants next to the right section
  rather than scattering them.
- `investments/goat/goat/db.py` lines 92-103 (`goat_rotation_snapshots` schema) — read
  for context on Decision #5's "deferred, zero-migration v2" note; **do not** add any
  new table or write to this one in this plan's own execution.
- `investments/my-trader/mytrader/tests/test_finviz_screener.py` (whole file) — the
  exact test-mocking idiom to mirror: a `_FakeResponse`/fake-HTML-string approach for
  `requests.get`, and direct unit tests of the parse function against a hand-built
  HTML fixture string shaped like a real (but trimmed) live page.
- `investments/goat/goat/tests/test_industry_rotation.py` (whole file, 44 lines) — the
  exact pure-function test shape for a ranking function: construct synthetic rows,
  monkeypatch config where needed, assert ordering + missing-data-sorts-last +
  `rank` assignment. `rank_all_industries` in this plan has no "missing data" case in
  practice (Finviz either returns all 144 rows or the whole fetch fails), but the
  test-authoring shape (imports, assertion style) is the one to copy.
- `scripts/systemd/second-brain-goat-dma-breakout-scan.service` +
  `.timer` — the exact systemd unit shape to copy: oneshot service,
  `WorkingDirectory=/home/secondbrain/second-brain/investments/goat`, `ExecStart`
  pointed at `goat.main` with the new subcommand, its own `*_runs.log`.
- `investments/goat/goat/main.py` lines 109-125 (`cmd_scan_industries` /
  `scan-industries` wiring) — the CLI-command shape to mirror for the new
  `scan-industries-full` subcommand: this one is even simpler (no `conn`/DB needed at
  all — see Decision #5, zero staging/notify).
- `investments/TOOLS.md` — not part of this plan's implementation tasks (per that
  file's own "update whenever a tool's schedule/command/output changes" instruction,
  same follow-up posture every recent tool in this codebase has shipped with) — add
  a row once the new report is confirmed live.

### New Files to Create

```
investments/goat/goat/finviz_groups.py           # fetch_industry_groups() -> list[dict] | None
investments/goat/goat/industry_rotation_full.py  # rank_all_industries(rows) -> list[dict]
                                                  # render_full_industry_ranking_report(result) -> str
                                                  # write_full_industry_ranking_report(result) -> None
investments/goat/goat/tests/test_finviz_groups.py
investments/goat/goat/tests/test_industry_rotation_full.py

scripts/systemd/second-brain-goat-industry-full-scan.service
scripts/systemd/second-brain-goat-industry-full-scan.timer
```

### Files to Update

- `investments/goat/goat/config.py` — add `GOAT_FINVIZ_GROUPS_URL`,
  `GOAT_INDUSTRY_FULL_RANKING_MD_PATH`, `GOAT_INDUSTRY_FULL_PRIMARY_WINDOW` (see Phase
  1 below). Add immediately after the existing industry-rotation section (after line
  244's `GOAT_FINVIZ_INDUSTRY_SLUGS` closing brace), not interleaved with it.
- `investments/goat/goat/main.py` — add `cmd_scan_industries_full` + the
  `scan-industries-full` subparser + dispatch entry, modeled on
  `cmd_scan_industries` (lines 109-125) but without `_open_conn()`/DB (Decision #5).
- `scripts/deploy.ps1` — add `"second-brain-goat-industry-full-scan.timer"` to
  `$TIMERS`.

### Patterns to Follow

**Naming**: module names `finviz_groups.py` / `industry_rotation_full.py` (snake_case,
matching every other `goat` module). Constants prefixed `GOAT_INDUSTRY_FULL_` /
`GOAT_FINVIZ_GROUPS_` (this codebase's short all-caps-prefix convention — `GOAT_`,
`MOAT_`, `CASH_VALUE_`, `VE_`).

**Error handling**: `fetch_industry_groups()` returns `None` on total failure (bad
status code, network exception, or the expected 144-row table not found at all) —
mirrors `finviz_screener.fetch_screener_universe`'s and
`ai_resistant_moat_scanner.universe.fetch_screened_universe`'s "`None` = total
failure, caller decides what to do" posture. Unlike those, there is **no partial
-failure case to handle** — this is one page, one table, not paginated multi-request
fetch, so the function's shape is simpler (no "first page vs later page" distinction
needed).

**Logging**: bracketed-module-name prefix on every print, e.g.
`[goat-industry-full-scan] ...` (see every scan module in this codebase).

**"Unknown" vs "flag" vs "interesting" verdicts**: **not applicable here** — there is
no `CheckResult`/verdict concept in this feature at all (Decision #5, no signal, no
candidate). `rank_all_industries` returns plain dicts (ticker-rotation-report-row
shape), same as `rank_industries`/`rank_sectors` already do.

---

## IMPLEMENTATION PLAN

### Phase 0: Live Research — ALREADY DONE during this planning pass

Documented in full under "DECISIONS RESOLVED" #1 above. No further live verification
needed before implementation — the exact URL, exact view parameter (`v=140`), exact
column headers, and exact row count (144 data rows) are all confirmed. The execution
agent should still re-run the one-line sanity check below before writing any parsing
code, in case Finviz's page shape has changed since 2026-10-18:

```python
import requests
from bs4 import BeautifulSoup
from mytrader import config
r = requests.get("https://finviz.com/groups.ashx", headers={"User-Agent": config.FINVIZ_USER_AGENT}, params={"g": "industry", "v": "140"}, timeout=30)
soup = BeautifulSoup(r.text, "html.parser")
for t in soup.find_all("table"):
    ths = [th.get_text(strip=True) for th in t.find_all("th")]
    if len(ths) > 5:
        print(ths, len(t.find_all("tr")))
```
Expect: `['No.', 'Name', 'Perf Week', 'Perf Month', 'Perf Quart', 'Perf Half', 'Perf Year', 'Perf YTD', 'Avg Volume', 'Rel Volume', 'Change %', 'Volume']` and 145 `<tr>` (144 data + 1 header). If this has drifted, stop and reconcile this plan's Phase 1 column-index assumptions before continuing — don't silently adapt around a changed shape.

### Phase 1: Config + Fetch/Parse Module

**Tasks:**
- UPDATE `investments/goat/goat/config.py` — immediately after the existing
  `GOAT_FINVIZ_INDUSTRY_SLUGS` block (after line 244), add:
  ```python
  # Full-coverage industry ranking (all 144 Finviz industries, not just the 39 with
  # a dedicated ETF), per .agent/plans/goat-industry-ranking-full-coverage.md.
  # LIVE-VERIFIED 2026-10-18: Finviz's own Groups "Performance" view
  # (groups.ashx?g=industry&v=140) already aggregates return data by industry
  # server-side -- no yfinance, no constituent-stock classification needed.
  # Deliberately separate from GOAT_INDUSTRY_ETFS/GOAT_FINVIZ_INDUSTRY_SLUGS above
  # -- this feature cannot feed or replace the 39-industry breakout/candidate
  # pipeline (no daily price series in this data source), see plan Decision #2.
  GOAT_FINVIZ_GROUPS_URL = "https://finviz.com/groups.ashx"
  GOAT_INDUSTRY_FULL_RANKING_MD_PATH = GOAT_DIR / "industry-ranking-full.md"
  GOAT_INDUSTRY_FULL_PRIMARY_WINDOW = "perf_half"  # closest match to the existing
      # ~6-month GOAT_INDUSTRY_RANK_WINDOW_TRADING_DAYS convention; v1/tunable --
      # "perf_quarter" or "perf_month" are equally valid choices, change freely.
  ```
- CREATE `investments/goat/goat/finviz_groups.py`:
  ```python
  """Finviz Groups scraper -- LIVE-VERIFIED 2026-10-18, see
  .agent/plans/goat-industry-ranking-full-coverage.md Decision #1. A single free
  page (groups.ashx?g=industry&v=140) already aggregates return performance by
  industry server-side, covering all 144 Finviz industries in one request -- no
  yfinance, no per-stock classification, no pagination, no ticker-watermark
  handling (there is no ticker column on this page, only industry names).
  """
  from __future__ import annotations
  from typing import Any
  from . import config

  _HEADERS = {"User-Agent": ...}  # import from mytrader.config.FINVIZ_USER_AGENT, same as finviz_screener.py

  _PCT_COLUMNS = {
      "Perf Week": "perf_week", "Perf Month": "perf_month", "Perf Quart": "perf_quarter",
      "Perf Half": "perf_half", "Perf Year": "perf_year", "Perf YTD": "perf_ytd",
      "Change %": "change_pct",
  }

  def _parse_pct(text: str) -> float | None:
      # strip "%", handle a literal "-" (Finviz's own "no data" placeholder, same
      # convention _parse page style checks already assume elsewhere in this repo)
      ...

  def fetch_industry_groups() -> list[dict[str, Any]] | None:
      # GET config.GOAT_FINVIZ_GROUPS_URL with params {"g": "industry", "v": "140"},
      # timeout=30. Return None on non-200 status or request exception (mirrors
      # finviz_screener._fetch_page's try/except-returns-None).
      # Parse the one <table> whose <th> list matches the expected 12-column header
      # exactly (mirrors finviz_screener._parse_page's "pick the candidate table"
      # idiom, but there's no wrapper-table/mega-row problem on this page -- a
      # direct header-list equality check is enough, no row-count-max-wins logic
      # needed).
      # Each row -> {"name": <Name column text>, **{parsed pct columns},
      #              "avg_volume": <raw text>, "rel_volume": <float>,
      #              "volume": <raw text>}
      # Return None if the table isn't found at all (total failure) -- never [].
      ...
  ```
  - **GOTCHA**: `Rel Volume` (e.g. `"0.76"`) is a plain decimal ratio, not a
    percentage — parse with `float(text)`, not `_parse_pct`. `Avg Volume`/`Volume`
    carry `M`/`B`/`K` suffixes (e.g. `"50.47M"`) — **leave these as raw text**, no
    new money-text parser needed; they're shown for context only, never used in
    ranking logic (Decision #4 ranks purely on the Perf columns).
  - **VALIDATE**: `uv run --directory investments/goat pytest goat/tests/test_finviz_groups.py -v`

### Phase 2: Ranking + Report

**Tasks:**
- CREATE `investments/goat/goat/industry_rotation_full.py`:
  ```python
  """Full-coverage (144/144) industry ranking, built directly from
  finviz_groups.fetch_industry_groups() -- no price-series fetch needed, Finviz
  already computed the return percentages server-side. See
  .agent/plans/goat-industry-ranking-full-coverage.md."""
  from __future__ import annotations
  from typing import Any
  from . import config

  def rank_all_industries(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
      # Sort by config.GOAT_INDUSTRY_FULL_PRIMARY_WINDOW descending (None-safe,
      # though in practice every row should have every Perf column populated --
      # mirror rank_industries'/rank_sectors' "missing sorts last" idiom anyway,
      # same defensive posture, in case Finviz ever leaves one industry's Perf
      # cell blank).
      # Assign row["rank"] = i (1-indexed), same as rank_industries/rank_sectors.
      ...

  def render_full_industry_ranking_report(result: dict[str, Any]) -> str:
      # Mirrors monitor.render_industry_ranking_report's Top 5 Rising / Bottom 5
      # Falling / Full Ranking shape (monitor.py:430-473) -- primary window
      # (config.GOAT_INDUSTRY_FULL_PRIMARY_WINDOW) drives rank/headline selection;
      # Full Ranking table shows ALL SIX Perf columns per row (Week/Month/Quarter/
      # Half/Year/YTD), not just the primary one -- free, already on the row.
      # NO "Not Covered" section (nothing is uncovered). Explanatory header note:
      # "advisor notes only... sourced from Finviz's own Groups performance view,
      # covering all 144 industries -- this is a pure informational ranking, no
      # breakout signal or candidate staging (see the 39-industry
      # industry-ranking.md for that)."
      ...

  def write_full_industry_ranking_report(result: dict[str, Any]) -> None:
      config.GOAT_INDUSTRY_FULL_RANKING_MD_PATH.write_text(
          render_full_industry_ranking_report(result), encoding="utf-8"
      )
  ```
  - **VALIDATE**: `uv run --directory investments/goat pytest goat/tests/test_industry_rotation_full.py -v`

### Phase 3: CLI Wiring

**Tasks:**
- UPDATE `investments/goat/goat/main.py` — add, modeled on `cmd_scan_industries`
  (lines 109-125) but **no `_open_conn()`/DB at all** (Decision #5 — this feature
  never touches `investments.db`):
  ```python
  def cmd_scan_industries_full(args) -> None:
      from . import finviz_groups, industry_rotation_full

      rows = finviz_groups.fetch_industry_groups()
      if rows is None:
          print("[goat-industry-full-scan] Finviz Groups fetch failed -- no report written this run")
          return
      ranking = industry_rotation_full.rank_all_industries(rows)
      industry_rotation_full.write_full_industry_ranking_report({"ranking": ranking})
      print(
          f"Full industry ranking complete: ranked {len(ranking)}/144 industries. "
          f"See investments/goat/industry-ranking-full.md"
      )
  ```
  - Add `subparsers.add_parser("scan-industries-full", help="On-demand full-coverage (144 industries) rotation ranking via Finviz Groups")`
    and a `"scan-industries-full": cmd_scan_industries_full` dispatch entry, both
    placed next to the existing `scan-industries` entries (lines ~391-393, ~460).
  - **GOTCHA**: on a total fetch failure, this prints and returns **without**
    writing a stale-banner (unlike `cash_value_scan`/`ai_resistant_moat_scanner`'s
    `_write_banner` pattern) — v1/simplest: the previous day's report file is left
    untouched (same effective "keep showing the last good run" outcome, just without
    an explicit banner prepended). If this proves confusing in practice, add a
    `_write_banner`-style note later; not required for v1.
  - **VALIDATE**:
    `uv run --directory investments/goat python -m goat.main scan-industries-full`
    (no DB involved — this one is safe to run locally too, unlike every other `goat`
    command; still prefer `scripts/invoke_investments.ps1 -Package goat -Command
    "scan-industries-full"` for the real/first run so the report lands in the VPS
    working tree).

### Phase 4: Tests

**Tasks:**
- CREATE `investments/goat/goat/tests/test_finviz_groups.py` — mirror
  `test_finviz_screener.py`'s fixture-HTML-string + monkeypatched `requests.get`
  idiom:
  - A ~5-row trimmed fixture HTML table shaped exactly like the live v=140 page
    (same 12 headers, a few real rows e.g. "Advertising Agencies"/"Waste
    Management" from the live sample above).
  - `test_fetch_industry_groups_parses_all_rows` — asserts row count and spot-checks
    one row's `name`/`perf_half`/`change_pct` parse to the expected values.
  - `test_fetch_industry_groups_returns_none_on_bad_status` /
    `..._on_network_error` / `..._when_table_not_found` — mirror
    `test_fetch_page_returns_none_on_bad_status`/`_on_network_error` and
    `test_parse_page_returns_none_when_not_a_screener_page`.
  - `test_parse_pct_handles_percent_strings_and_dash_placeholder` — direct unit test
    of the `_parse_pct` helper, including Finviz's own `"-"` no-data placeholder
    (confirm live whether this page ever emits one; if it never does in practice,
    keep the guard anyway — same defensive-but-untriggered posture as other
    None-safe parsers in this codebase).
  - `test_canonical_industry_list_matches_scraped_names` — build a 144-row fixture
    using the **exact** `config.GOAT_FINVIZ_INDUSTRIES` list as the `Name` values,
    assert `{r["name"] for r in fetch_industry_groups()} ==
    set(config.GOAT_FINVIZ_INDUSTRIES)` (Decision #6's drift-insurance check).
- CREATE `investments/goat/goat/tests/test_industry_rotation_full.py` — mirror
  `test_industry_rotation.py`'s pure-function shape:
  - `test_rank_all_industries_orders_by_primary_window_descending`
  - `test_rank_all_industries_assigns_rank_starting_at_one`
  - `test_render_full_industry_ranking_report_shows_all_six_perf_columns_and_no_not_covered_section`
    — asserts `"Not Covered"` is absent from the rendered text (a direct regression
    guard for Decision #4's explicit scope difference from the existing report).
  - **VALIDATE**: `uv run --directory investments/goat pytest -v` (full suite)

### Phase 5: Deployment Wiring

**Tasks:**
- CREATE `scripts/systemd/second-brain-goat-industry-full-scan.service` — mirrors
  `second-brain-goat-dma-breakout-scan.service`: `WorkingDirectory=
  /home/secondbrain/second-brain/investments/goat`, `ExecStart=
  .../goat.main scan-industries-full`, log file
  `investments/goat/industry_full_scan_runs.log`.
- CREATE `scripts/systemd/second-brain-goat-industry-full-scan.timer` —
  `OnCalendar=*-*-* 21:40:00 UTC` (5 minutes after Goat Monitor's existing 21:35 UTC
  slot, thematically adjacent, free per `investments/TOOLS.md`'s schedule table as
  of this plan's writing — **cross-check that table before finalizing the exact
  minute**, in case a later edit has filled it), `Persistent=true` (matches every
  other daily-cadence Goat timer).
- UPDATE `scripts/deploy.ps1` — add `"second-brain-goat-industry-full-scan.timer"`
  to `$TIMERS`.
- No `invoke_investments.ps1` change needed — `-Package goat` already exists; the
  new `scan-industries-full` command works through the existing wrapper entry
  unchanged.
- Manual VPS deploy (same posture as every recent tool — explicit follow-up, not
  part of this plan's own execution):
  ```
  ssh secondbrain@137.184.102.104
  cd /home/secondbrain/second-brain && git pull && \
    sudo cp scripts/systemd/second-brain-goat-industry-full-scan.service scripts/systemd/second-brain-goat-industry-full-scan.timer /etc/systemd/system/ && \
    sudo systemctl daemon-reload && \
    sudo systemctl enable --now second-brain-goat-industry-full-scan.timer && \
    cd investments/goat && \
    ../.venv/bin/python -m goat.main scan-industries-full
  ```

---

## TESTING STRATEGY

### Unit Tests
Every pure function (`finviz_groups._parse_pct`, `finviz_groups.fetch_industry_groups`,
`industry_rotation_full.rank_all_industries`,
`industry_rotation_full.render_full_industry_ranking_report`) gets direct unit tests
with constructed HTML-string / dict fixtures — no real network, mirroring
`test_finviz_screener.py`'s idiom exactly.

### Integration Tests
`cmd_scan_industries_full`'s own wiring (fetch → rank → write report → print summary)
is thin enough that the unit tests above plus one direct call in Phase 3's VALIDATE
step cover it — no dedicated integration test file needed (consistent with this
being the only Goat command with zero DB involvement; there's nothing to integration
-test in the DB sense).

### Edge Cases
- Finviz returns fewer than 144 rows (a de-listed/merged industry) — ranking still
  works over however many rows came back; report header should say "ranked N/144",
  not hardcode 144.
- `fetch_industry_groups()` returns `None` (total failure) — `cmd_scan_industries_full`
  prints and returns without writing anything, leaving the previous report in place
  (Phase 3 GOTCHA).
- A single industry's Perf cell is Finviz's `"-"` no-data placeholder —
  `_parse_pct` returns `None` for that one field without raising; `rank_all_industries`
  sorts that row last (same "missing data sorts last, never first/interspersed"
  idiom as `rank_industries`/`rank_sectors`).
- The scraped `Name` list drifts from `config.GOAT_FINVIZ_INDUSTRIES` (Finviz renames
  or re-buckets an industry) — caught by
  `test_canonical_industry_list_matches_scraped_names` at test time, not a runtime
  crash (Decision #6); a real live drift just means that one test needs updating
  alongside a manual `GOAT_FINVIZ_INDUSTRIES` refresh, not a blocker for the feature
  itself.

---

## VALIDATION COMMANDS

### Level 1: Syntax & Style
```
uv run --directory investments/goat ruff check goat/finviz_groups.py goat/industry_rotation_full.py
uv run --directory investments/goat mypy goat/finviz_groups.py goat/industry_rotation_full.py
```

### Level 2: Unit Tests
```
uv run --directory investments/goat pytest -v
```

### Level 3: Integration Tests
Covered by Level 2 plus the Phase 3 manual CLI run below — no separate integration
test command (see Testing Strategy).

### Level 4: Manual Validation
```
# Safe to run locally too (no DB involved, unlike every other goat command) --
# but prefer invoke_investments.ps1 for the real first run so the report lands on
# the VPS working tree:
uv run --directory investments/goat python -m goat.main scan-industries-full

# Real run, once ready:
.\scripts\invoke_investments.ps1 -Package goat -Command "scan-industries-full"
```
Confirm: no exceptions, `investments/goat/industry-ranking-full.md` is written with
~144 ranked rows across six Perf-window columns, console prints "ranked N/144
industries".

### Level 5: Additional Validation
None beyond the standard workspace tooling already listed above.

---

## ACCEPTANCE CRITERIA

- [ ] `industry-ranking-full.md` is produced covering ~144 Finviz industries (not
      just the existing 39 ETF-backed ones), ranked by `GOAT_INDUSTRY_FULL_PRIMARY_WINDOW`.
- [ ] Zero behavioral changes to `industry_rotation.py`, `monitor.run_industry_scan`,
      `industry_heartbeat_scan.py`, `hated_industries_scan.py`, or
      `GOAT_INDUSTRY_ETFS`/`GOAT_FINVIZ_INDUSTRY_SLUGS` — confirmed by the existing
      Goat test suite passing unchanged.
- [ ] No new DB table, no candidate staging, no WhatsApp alert, no new yfinance call
      anywhere in this feature.
- [ ] A total Finviz fetch failure degrades gracefully (prints, writes nothing, does
      not crash) rather than throwing.
- [ ] `ruff`/`mypy`/`pytest` all pass with zero errors.
- [ ] Deployment wiring (`deploy.ps1`, systemd units) is in place, though the actual
      VPS deploy itself is a manual follow-up for Shaun, not part of this plan's own
      execution.
- [ ] `investments/TOOLS.md` gets a new row once the tool is confirmed live (flagged
      as a follow-up task, per that file's own update convention).

## COMPLETION CHECKLIST

- [ ] Phase 0's live-shape re-check passed before writing any parsing code
- [ ] All tasks completed in order (Phases 1-5)
- [ ] Each phase's validation command passed before moving to the next
- [ ] Full test suite passes, including the two new test files
- [ ] No linting or type errors
- [ ] Manual `scan-industries-full` run confirmed working (locally is fine here —
      see Phase 3 VALIDATE note on why this command is DB-free)
- [ ] Acceptance criteria all met
- [ ] Shaun has reviewed the new report's shape/content before the VPS deploy

---

## NOTES

- This plan deliberately supersedes the "constituent-stock aggregation via yfinance"
  framing floated earlier in conversation — that approach remains *possible* but is
  strictly more expensive (more engineering, more yfinance load, more rate-limit
  risk) for the same end result Finviz's own Groups page already gives away for
  free. If Shaun specifically wants true per-stock constituent aggregation later
  (e.g. to compute a cap-weighted rather than Finviz's own return methodology, which
  is not publicly documented), that remains a separate, larger follow-on plan — not
  a revision of this one.
- Deliberately does **not** attempt the actual VPS deploy, nor touch
  `investments/TOOLS.md` — both are explicit follow-ups once Shaun has reviewed the
  built tool, consistent with how every other recent tool in this codebase
  (`volume-earnings-scanner`, `ai-resistant-moat-scanner`) shipped: build + test
  locally first, confirm with Shaun, deploy second.
- `GOAT_INDUSTRY_FULL_PRIMARY_WINDOW = "perf_half"` is explicitly v1/tunable, same
  posture as every other threshold in this codebase shipped as "start with a
  reasonable default, tune after the first few days of real output."
