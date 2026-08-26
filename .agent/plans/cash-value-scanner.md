# Feature: Cash-Value Scanner ("Cash 80% Trading Value")

The following plan should be complete, but its important that you validate documentation
and codebase patterns and task sanity before you start implementing.

Pay special attention to naming of existing utils, types, and models. Import from the
right files. In particular: `mytrader.market_data.fetch_ticker_data` /
`fetch_cash_flow_statement`, `mytrader.tickers.normalize` / `asx_variant`,
`scripts.ethical_filter.check_ticker`, `mytrader.db.get_holding_row` /
`get_watchlist_row`, and the `mytrader.config` constant style.

---

## Feature Description

A scheduled screener that finds companies **trading at roughly cash value** — where
**net cash** (cash + short-term investments − total debt) is at least **80% of the
company's market capitalisation** — and that also **generate positive cash flow** (so
the list isn't just dying companies burning down their reserves). Classic Graham /
deep-value "you're buying the operating business for ~20c on the dollar after backing
out the bank balance" setup, with a going-concern quality gate.

Output is a single ranked Markdown report (`investments/my-trader/cash-value-report.md`),
same shape as `goat-report.md` / `my-trader-report.md`: **advisor notes only** — no
candidate staging, no auto-watchlist-add, no WhatsApp alert. Shaun runs his own deep
dive (`my-trader find`, `briefs-finance assess`) on anything he likes the look of.

Two universes:
- **US** — Finviz screener (`finviz.com/screener.ashx`), coarse-prefiltered on
  Price/Cash, then precisely re-tested via yfinance.
- **ASX** — S&P/ASX 200 constituents scraped from Wikipedia (mirrors the existing
  `goat/goat/sp500_universe.py` Wikipedia-table scrape), every constituent re-tested
  via yfinance (`.AX` tickers).

The net-cash-to-market-cap ratio is **currency-consistent per company** (both figures
come from the same yfinance `.info` in the listing currency), so no FX handling is
needed for the ratio itself. Absolute-dollar columns are labelled with each row's
currency.

## User Story

As Shaun (advisor-mode Second Brain user, self-described investing rookie)
I want a daily-refreshed ranked list of US and ASX companies whose net cash is ≥ 80%
of their market cap AND that are cash-flow positive
So that I have a curated shortlist of deep-value "buying the business for the stub"
candidates to run my own deeper `find` / `assess` passes on, without manually
screening thousands of tickers.

## Problem Statement

There is no tool in `investments/` that screens the whole market for balance-sheet
deep-value (net cash vs. market cap). `my-trader find` assesses **one ticker at a
time** and only surfaces this kind of signal incidentally (it has no net-cash check at
all). `goat` is explicitly momentum / sector-rotation — the opposite philosophy
(`investments/goat/HANDOFF.md`). `briefs-finance` only scores tickers that already
appear in a Briefs Finance PDF. So a cash-rich micro/small-cap trading below its own
bank balance is invisible to the current toolset unless Shaun already knows the ticker.

## Solution Statement

A new `cash-value-scan` subcommand on **my-trader** (it already owns the
screener-scrape pattern, the yfinance fundamentals wrappers, `tickers.normalize`, and
the ethical-filter import). Two new universe-provider modules
(`mytrader/finviz_screener.py`, `mytrader/asx200_universe.py`) each return a coarse
ticker list. One orchestration module (`mytrader/cash_value_scan.py`) enriches every
candidate through `market_data.fetch_ticker_data`, applies the precise net-cash +
cash-flow test + ethical filter + sector exclusions, ranks by cash ratio, and writes
the report. A read-only DB connection tags rows Shaun already holds / watchlists.
A new VPS systemd timer runs it daily.

## Feature Metadata

**Feature Type**: New Capability (sibling extension of the `openinsider.py` /
`sp500_universe.py` screener-scrape pattern; new subcommand on an existing tool).
**Estimated Complexity**: Medium — two HTML scrapers (one new site: Finviz, with
pagination), one compute/render module, CLI wiring, one systemd pair, tests. No new
external dependencies (`requests` + `beautifulsoup4` + `yfinance` all already declared
in `investments/my-trader/pyproject.toml`).
**Primary Systems Affected**: `investments/my-trader/` only (`mytrader/config.py`,
new `mytrader/finviz_screener.py`, new `mytrader/asx200_universe.py`, new
`mytrader/cash_value_scan.py`, `mytrader/main.py`, `mytrader/tests/`), plus
`scripts/systemd/` (new pair), `investments/TOOLS.md`, and the handoff doc's status line.
**Dependencies**: None new. Reuses `scripts.ethical_filter` (workspace sibling,
already imported by `mytrader/engine.py`).

---

## Decisions Confirmed With Shaun (2026-08-26, planning session — treat as settled)

> **AMENDED post-first-live-run (2026-08-26):** the first VPS run of the built
> scanner returned **zero** names across 492 US + 200 ASX. Shaun loosened two knobs:
> (1) cash-flow gate is now **positive operating cash flow only** — FCF is still
> computed, shown, and given a `negative FCF` tag, but does not filter (positive OCF
> with negative FCF is usually growth capex, not burn); (2) cash-ratio threshold is
> now **0.50** (`CASH_VALUE_RATIO_THRESHOLD` in `config.py`), 0.80 being effectively
> net-net territory that doesn't exist in developed markets. Report `#` title
> changed to threshold-agnostic "Cash-Value Scan". Decisions 1 and 2 below are the
> original planning-session calls, kept for the record.

1. **Cash-flow gate**: positive trailing **operating cash flow AND positive free cash
   flow**. Read from yfinance `.info` (`operatingCashflow`, `freeCashflow`); when
   either is missing, fall back to the latest **annual** figures via
   `market_data.fetch_cash_flow_statement`. No minimum-margin or FCF-yield floor in v1.
   (Shaun: "no idea" → planner's call, per the handoff's own recommendation.)
2. **Cash ratio threshold**: plain **hard cutoff at 0.80**. One list. **No** "75–80%
   near-miss" section. (Shaun: "Plain old hard cutoff.")
3. **Sector exclusions**: exclude **Financials and Real Estate** — net cash is not a
   meaningful concept for a bank / REIT. (Shaun: "exclude.")
4. **Size floor**: **no hard drop.** Finviz's coarse filter already imposes avg
   volume > 100K and price > $1, which removes the untradeable shells. Just **tag**
   `⚠ micro` below **US$50M** market cap (or A$75M for ASX rows). Everything stays on
   the list so Shaun can eyeball anything. (Shaun: "No idea — why does this matter?"
   → explained: cash-value micro-caps are often distressed / illiquid; tag, don't hide.)
5. **Scope**: **US (Finviz) + ASX (S&P/ASX 200 via Wikipedia)** for v1. The ratio is
   currency-consistent per company so no FX math is needed. Broader ASX (All
   Ordinaries / small-caps) is **deferred** — too many yfinance lookups for a nightly
   job, and ASX 200 large-caps rarely trade at cash value so the ASX side will be thin
   at first. (Shaun: "Can we include asx too?" → yes, ASX 200.)
6. **Scrape-failure behaviour** (no DB, so no snapshot): if the **US (Finviz) fetch
   fails**, keep and re-serve the previous `cash-value-report.md` with a
   `> ⚠ STALE — Finviz fetch failed <date>, showing last good run` banner prepended.
   If only the **ASX fetch** fails, still write a fresh report but with an inline
   "ASX universe unavailable this run" note in the ASX section. (Shaun: "sure.")
7. **Names**: CLI subcommand `cash-value-scan`; report file
   `investments/my-trader/cash-value-report.md`. Shaun's working name
   **"Cash 80% Trading Value"** is the report's `#` title / heading. (Shaun: "sure.")
8. **Schedule**: new VPS systemd pair
   `second-brain-mytrader-cashvalue-scan.{service,timer}`, daily at **22:30 UTC**
   (after the 21:35 / 21:50 / 22:05 Goat + crash-signal stack). This is a brand-new
   command with no Windows twin, so — unlike my-trader *Monitor* — it runs on the VPS
   like every other scheduled scan. (Shaun: "yes.")
9. **Hold / watchlist tag**: open a **read-only** shared-DB connection and tag rows
   Shaun already holds (`● held`) or watchlists (`○ watchlist`), so he doesn't
   re-research something he already tracks. Tag only — never a filter, never a write.
   (Shaun: confirmed after plain-language explanation.)

---

## CONTEXT REFERENCES

### Relevant Codebase Files — YOU MUST READ THESE BEFORE IMPLEMENTING

- `investments/my-trader/mytrader/openinsider.py` (whole file, 219 lines) — **the
  screener-scrape pattern to mirror**. Note specifically: `_HEADERS` dict built from a
  `config.*_USER_AGENT` constant (line 18); `_fetch(url, params)` (lines 167–177) —
  `requests.get` with `headers`/`params`/`timeout=30`, `status_code != 200 → None`,
  bare `except Exception: return None`; `_parse_table` (lines 113–164) — BeautifulSoup
  `html.parser`, iterate `soup.find_all("table")` and pick the one whose `<th>` set
  contains a known column, build a `col_index` map, normalise non-breaking spaces with
  `" ".join(text.split())`; the `_ZERO_RESULTS_MARKER` idiom (lines 101–110, 124–126)
  — a static footer string that distinguishes "site answered with zero rows" (`[]`)
  from "response isn't a real results page" (`None`); `tickers.normalize(ticker_text)`
  on every parsed ticker (line 146).
- `investments/goat/goat/sp500_universe.py` (whole file, 80 lines) — **the
  Wikipedia-constituent-table scrape to mirror for `asx200_universe.py`**.
  `fetch_sp500_constituents()` (lines 21–57): `requests.get(WIKI_URL, headers=_HEADERS,
  timeout=30)`, `soup.find("table", {"id": "constituents"})` with a
  `{"class": "wikitable"}` fallback, skip the header row (`trs[1:]`), `len(cells) < 3`
  guard, `tickers.normalize(symbol)`, `return rows or None`. Note it caches in a DB
  table — **our version has no DB, so drop `get_or_refresh_*` and just call the fetch
  each run**.
- `investments/goat/goat/fundamentals_context.py` (whole file, 100 lines) — **the
  `.info` field-access + None-safety pattern for balance-sheet numbers**. Lines 41–53
  show exactly how to read `info.get("totalCash")`, `info.get("freeCashflow")`,
  `info.get("operatingCashflow")`, `info.get("debtToEquity")` with `fetch_balance_sheet_financials`
  fallback, and the `(info.get("operatingCashflow") or 0) > 0` cash-generating test.
  Mirror this exact defensiveness (every field can be `None`).
- `investments/my-trader/mytrader/market_data.py` (whole file, 192 lines):
  - `fetch_ticker_data(ticker)` (lines 71–83) — normalises, tries `.AX` fallback,
    returns `TickerData | None`. `TickerData.info` is the yfinance `.info` dict.
  - `cached_session()` (lines 24–37) — per-run in-memory cache context; **wrap the
    enrichment loop in `with market_data.cached_session():`** the same way
    `monitor.run_monitor` does (monitor.py:117).
  - `fetch_cash_flow_statement(ticker)` (lines 160–191) — latest **annual** cash-flow
    statement, returns `{"free_cash_flow", "operating_cash_flow", "capital_expenditure",
    "period_end"}` or `None` (returns `None` if `free_cash_flow` row is absent). This
    is the **fallback** when `.info` lacks `operatingCashflow` / `freeCashflow`.
  - `_looks_valid` / `_fetch_one` (lines 39–68) — why a bad ticker returns `None`.
- `investments/my-trader/mytrader/checks/balance_sheet.py` (docstring, lines 1–37) —
  **why `net_cash` uses raw `totalDebt` and does NOT strip out IFRS 16 capitalised
  leases**: leases behave economically like real debt, rating agencies include them,
  Yahoo's raw number is "the more conservative, defensible number; a lease-excluded
  variant would understate real risk." Do not try to net out leases.
- `investments/my-trader/mytrader/tickers.py` (whole file, 14 lines) —
  `normalize(ticker)` (upper + `BRK.B→BRK-B` map), `asx_variant(ticker)` (`+ ".AX"`).
- `scripts/ethical_filter.py` (whole file — it's `investments/briefs-finance/scripts/ethical_filter.py`,
  imported as `scripts.ethical_filter` from the workspace) — `check_ticker(ticker)`
  returns `(excluded: bool, reason: str | None)`: `(True, reason)` = auto-exclude,
  `(False, "REVIEW: ...")` = borderline, `(False, None)` = allowed.
- `investments/my-trader/mytrader/engine.py` lines 8, 137 — the exact import
  (`from scripts.ethical_filter import check_ticker as ethical_check`) and 3-way
  handling: `excluded` drops it, a non-None `exclusion_reason` with `excluded=False`
  is shown as `REVIEW:`.
- `investments/briefs-finance/scripts/config.py` lines 22–26 — `DEFENSE_TICKERS`
  (18 tickers) + `DEFENSE_REVIEW_TICKERS` (`BA`, `PLTR`). These back `check_ticker`.
- `investments/my-trader/mytrader/monitor.py` lines 238–358 (`render_report`,
  `write_report`) — **the report-rendering convention**: build `lines: list[str]`,
  end with `"\n".join(lines) + "\n"`, `config.<PATH>.write_text(..., encoding="utf-8")`.
  Note the top-of-report boilerplate: a "What this is" line and an
  "Advisor notes only; no trade action is ever suggested here (see SOUL.md)." line,
  and `_today_sydney()` (monitor.py:41–43, `datetime.now(ZoneInfo("Australia/Sydney")).date().isoformat()`)
  for the run-date label. **Reuse `_today_sydney` — copy the same 3-line helper into
  `cash_value_scan.py`** (monitor.py keeps its own copy; there is no shared util).
- `investments/goat/goat/heartbeat_scan.py` lines 85–116 (`render_heartbeat_candidates_report`,
  `write_heartbeat_candidates_report`) — a **closer structural match** than
  monitor.py: a scan that produces one ranked table + a "scanned N tickers" line +
  `Last auto-generated: {date}` footer, written straight to a `config.*_MD_PATH`.
  Mirror this shape.
- `investments/my-trader/mytrader/main.py` (whole file, 431 lines) — the CLI
  convention: `_open_conn()` (lines 8–17), one `cmd_<name>(args)` function per
  subcommand that opens a conn / does work / `conn.close()` / `print(...)` a
  one-line summary, `subparsers.add_parser(...)` in `main()`, and the `dispatch`
  dict (lines 403–421). `cmd_find` (lines 56–62) is the simplest read-only example.
- `investments/my-trader/mytrader/config.py` (whole file, 555 lines) — **constant
  style**: every threshold has a trailing `#` comment citing a source
  ("Shaun's number, date" / "widely-cited rule of thumb" / "textbook default" /
  a plan-doc path) AND a plain-English "which direction is good" note (per the
  `feedback_check_interpretation_convention` memory). See `ETF_AUM_FLAG_USD`
  (lines 307–313), `INSIDER_SELLING_*` (lines 544–554), `SEC_USER_AGENT`
  (line 211 — "confirmed with Shaun, do not change without asking"), `ASX_USER_AGENT`
  (lines 252–255 — a real browser UA "to avoid tripping bot detection"). The
  `OPENINSIDER_*` block (lines 531–538) is the pattern for a new scraper-config block.
- `investments/my-trader/mytrader/tests/conftest.py` (whole file, 167 lines) — the
  **autouse network-stub convention**: every real network/LLM call site an engine
  path can reach has a `@pytest.fixture(autouse=True)` that `monkeypatch.setattr`s it
  to a `None`-returning stub, "global/autouse so a future test file doesn't
  reintroduce this by forgetting to stub it." Also the `db_conn` fixture (lines
  19–27, real tmp-path SQLite, `init_mytrader_tables`) and the
  `_isolate_snapshot_paths` autouse fixture (lines 29–48) — **add `CASH_VALUE_REPORT_PATH`
  isolation there** so tests never touch the real report file.
- `investments/my-trader/mytrader/tests/test_openinsider.py` (whole file, 182 lines)
  — **the scraper-test pattern to mirror**: a `_FAKE_HTML` module constant with a
  representative results table, a `_FakeResponse` class (`text` + `status_code`),
  `monkeypatch.setattr("requests.get", lambda *a, **k: _FakeResponse(...))`, and
  separate tests for: parses-table, filters-correctly, returns-`[]`-on-zero-results,
  returns-`None`-on-missing-table, returns-`None`-on-bad-status,
  returns-`None`-on-network-error, builds-correct-params.
- `investments/my-trader/mytrader/tests/test_market_data.py` lines 1–24 — the
  "save the real function ref at import time before conftest patches it" idiom, for
  any test that needs the real `fetch_ticker_data` / `fetch_cash_flow_statement`
  (we won't — we hand-build `TickerData` — but know the idiom exists).
- `investments/my-trader/mytrader/db.py` lines 159–184 — `get_holding_row(conn,
  ticker, bucket=None)`, `get_watchlist_row(conn, ticker, bucket=None)`,
  `get_all_holdings(conn)`, `get_all_watchlist(conn)` — all return `sqlite3.Row`
  (dict-like via `row["ticker"]`, **no `.get()`**). Use `get_all_holdings` /
  `get_all_watchlist` once and build `set`s of tickers for the tag lookup (cheaper
  than a per-ticker query in the loop).
- `scripts/systemd/second-brain-goat-insider-scan.service` + `.timer` (both whole,
  ~11 lines each) — **the systemd pair to mirror**. `.service`: `Type=oneshot`,
  `User=secondbrain`, `WorkingDirectory=/home/secondbrain/second-brain/investments/my-trader`,
  `ExecStart=/home/secondbrain/second-brain/investments/.venv/bin/python -m mytrader.main cash-value-scan`,
  `StandardOutput`/`StandardError=append:/home/secondbrain/second-brain/investments/my-trader/cashvalue_scan_runs.log`.
  `.timer`: `Requires=<service>`, `OnCalendar=*-*-* 22:30:00 UTC`, `Persistent=true`,
  `[Install] WantedBy=timers.target`.
- `scripts/deploy.ps1` lines 10–26 — the `$TIMERS` array of timers stopped during a
  deploy. **Do NOT add the new timer here** (the comment at lines 12–16 is explicit:
  my-trader's own scheduled work stays off this list; the deploy only stops timers
  that `git commit`/write inside the repo — but this new scan only *writes a report
  file* which is fine to have happen mid-deploy, same as goat-monitor which writes
  reports and *is* listed only because it also imports and could race). Actually:
  add it — it writes `cash-value-report.md` inside the repo working tree and
  `deploy.ps1` does a `git stash` / `stash pop` that a mid-deploy report write
  could conflict with. Match `second-brain-goat-heartbeat-scan.timer`'s treatment
  (it's in the list). **Confirm this call during implementation by re-reading the
  deploy.ps1 comment.**
- `scripts/setup_vps.sh` lines 46–58 — `*.service`/`*.timer` are all `scp`'d and
  `daemon-reload`ed, but only a hardcoded subset is `enable --now`'d. **A new timer
  must be enabled manually on the VPS** — the plan's Level 4 validation gives Shaun
  the command.
- `.claude/scripts/run_vault_sync.sh` line 21 —
  `SYNC_PATHS=(Memory/ investments/goat/*.md investments/my-trader/*.md)`. The new
  `investments/my-trader/cash-value-report.md` is **already covered** by
  `investments/my-trader/*.md` — a VPS-written report reaches the local repo on the
  next 2-minute vault sync with zero extra wiring.
- `scripts/invoke_investments.ps1` lines 21–41 — `-Package my-trader` maps to
  `Dir="my-trader"`, `Module="mytrader.main"`. `.\scripts\invoke_investments.ps1
  -Package my-trader -Command "cash-value-scan"` is the on-demand invocation. Avoid
  `$`, backticks, backslashes in any `-Command` value (line 18–19 caveat).

### New Files to Create

- `investments/my-trader/mytrader/finviz_screener.py` — paginated Finviz screener
  HTML-table scraper. Returns `list[dict]` (`{ticker, company, sector, industry,
  country, market_cap_text, price_text}`) or `None` on fetch failure. Paginates
  internally via `&r=1,21,41,...` until a page returns 0 data rows or `FINVIZ_MAX_PAGES`.
- `investments/my-trader/mytrader/asx200_universe.py` — Wikipedia S&P/ASX 200
  constituent-table scraper (mirrors `sp500_universe.fetch_sp500_constituents`, minus
  the DB cache). Returns `list[dict]` (`{ticker, company, sector}`) or `None`.
- `investments/my-trader/mytrader/cash_value_scan.py` — orchestration: universe fetch
  (both) → per-ticker yfinance enrichment → net-cash + cash-flow test → ethical
  filter + sector exclusion → rank → render → write. Includes a local `_today_sydney`
  helper (copy from monitor.py:41–43) and stale-report fallback logic.
- `investments/my-trader/mytrader/tests/test_finviz_screener.py` — scraper unit tests
  (mirror `test_openinsider.py`).
- `investments/my-trader/mytrader/tests/test_asx200_universe.py` — scraper unit tests.
- `investments/my-trader/mytrader/tests/test_cash_value_scan.py` — metric-math +
  filtering + ranking + render + stale-fallback tests.
- `scripts/systemd/second-brain-mytrader-cashvalue-scan.service`
- `scripts/systemd/second-brain-mytrader-cashvalue-scan.timer`

### Files to Modify

- `investments/my-trader/mytrader/config.py` — new `CASH_VALUE_*`, `FINVIZ_*`,
  `ASX200_*` constant block + `CASH_VALUE_REPORT_PATH`.
- `investments/my-trader/mytrader/main.py` — `cmd_cash_value_scan`, subparser,
  dispatch entry.
- `investments/my-trader/mytrader/tests/conftest.py` — add `CASH_VALUE_REPORT_PATH`
  to `_isolate_snapshot_paths`; add autouse stubs for the two new scrapers +
  `fetch_ticker_data` + `fetch_cash_flow_statement`.
- `investments/TOOLS.md` — new rows in "Automated (scheduled)" and "Manual /
  on-demand only", and a "Daily Read" entry.
- `investments/cash-value-scanner-handoff.md` — change the `## Status:` line to
  `PLANNED — see .agent/plans/cash-value-scanner.md (created 2026-08-26)`. Leave the
  rest as the historical background record (matches how `goat` handoffs were left in
  place after their plans superseded them).

### Relevant Documentation

- **Finviz screener** — no official API for the free tier. Live-verified 2026-08-26
  (this planning session):
  - URL: `https://finviz.com/screener.ashx?v=111&f=<filters>&o=pricecash`
  - `v=111` = "Overview" view. Columns rendered: `No.`, `Ticker`, `Company`,
    `Sector`, `Industry`, `Country`, `Market Cap`, `P/E`, `Price`, `Change`, `Volume`.
  - Coarse filter set: `fa_pc_u3` (Price/Cash under 3), `geo_usa` (US-listed),
    `sh_avgvol_o100` (avg volume over 100K), `sh_price_o1` (price over $1).
  - `&o=pricecash` sorts ascending by Price/Cash.
  - Pagination: `&r=1`, `&r=21`, `&r=41`, … (1-indexed row offset, 20 rows/page in
    the free tier).
  - Result count today: **492 matches across 25 pages**. Publicly viewable, no login.
  - CSV export (`/export`, `/api/v1/screener-export-csv`) is Elite-only AND
    `Disallow`ed in `robots.txt` — **do not use it**; scrape the HTML table.
  - `robots.txt`: `Disallow: /screener?*` with `Allow` exceptions for specific
    `v=...&s=...` technical screens. The legacy `.ashx` path (`/screener.ashx`) is
    **not** matched by the `/screener?` disallow rule. `/export`, `/chart`, `/image`,
    `/api/*` are disallowed. Treat as: same acceptable-scrape class as the existing
    `openinsider.com` and `en.wikipedia.org` scrapes in this repo — a real browser
    User-Agent, ~25 sequential GETs once/day, a courtesy delay between pages.
  - Finviz **does** block obviously-bot User-Agents on some paths → use a real
    browser UA (same reasoning as `config.ASX_USER_AGENT`).
- **S&P/ASX 200 constituents** — `https://en.wikipedia.org/wiki/S%26P/ASX_200`.
  Live-verified 2026-08-26: a "Constituent companies" table, ~200 rows, columns
  `Code`, `Company`, `Sector`, `Market Capitalisation`, `Headquarters`. Same scrape
  shape as the existing S&P 500 Wikipedia scrape. yfinance ticker form is
  `<CODE>.AX`.
- **yfinance `.info` fields** used (all can be absent → treat as missing, skip the
  ticker for the ratio test):
  - `marketCap` — market capitalisation, listing currency.
  - `totalCash` — cash + equivalents + short-term investments, listing currency.
  - `totalDebt` — short + long-term debt, **includes IFRS 16 capitalised leases**
    (per `checks/balance_sheet.py` docstring — this is the conservative number, keep it).
  - `operatingCashflow`, `freeCashflow` — trailing, listing currency.
  - `sector` — yfinance sector string (e.g. `"Financial Services"`, `"Real Estate"`).
    Finviz uses `"Financial"` / `"Real Estate"` — exclude on **both** vocabularies.
  - `financialCurrency` / `currency` — for the per-row currency label.

### Patterns to Follow

**Scraper module shape** (from `openinsider.py` / `sp500_universe.py`):
```python
"""<one-line what> — mirrors openinsider.py's direct-fetch style (requests +
BeautifulSoup, headers dict, timeout, try/except-returns-None-on-any-failure)."""

from __future__ import annotations

from . import config, tickers

_HEADERS = {"User-Agent": config.FINVIZ_USER_AGENT}


def _fetch(url: str, params: dict | None = None) -> str | None:
    import requests
    try:
        r = requests.get(url, headers=_HEADERS, params=params, timeout=30)
        if r.status_code != 200:
            return None
        return r.text
    except Exception:
        return None
```
Import `requests` / `bs4` **inside the function** (both modules do this — keeps import
time cheap and matches the pattern the test suite's monkeypatching relies on:
`monkeypatch.setattr("requests.get", ...)`).

**Config constant block** (from `config.py`'s `OPENINSIDER_*` block, lines 531–538):
```python
# Finviz screener scraper (mytrader/finviz_screener.py) — the US universe source for
# the cash-value scan (mytrader/cash_value_scan.py), per
# .agent/plans/cash-value-scanner.md. Coarse Price/Cash prefilter only; the precise
# net-cash test runs in the yfinance enrichment pass. Live-verified 2026-08-26:
# 492 matches / 25 pages, public, no login.
FINVIZ_SCREENER_URL = "https://finviz.com/screener.ashx"
FINVIZ_USER_AGENT = (  # a real browser UA — Finviz blocks obviously-bot UAs on some
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "  # paths, same
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"              # reason as
)                                                                     # ASX_USER_AGENT
FINVIZ_SCREENER_FILTERS = "fa_pc_u3,geo_usa,sh_avgvol_o100,sh_price_o1"  # Price/Cash
    # under 3 + US-listed + avg vol > 100K + price > $1. P/C uses GROSS cash and
    # net cash <= gross cash, so net cash >= 80% of mcap implies P/C <= 1.25 — a
    # P/C < 3 net safely contains every true positive. Lower P/C = more cash-like.
FINVIZ_SCREENER_ROWS_PER_PAGE = 20  # free tier; pagination is &r=1,21,41,...
FINVIZ_MAX_PAGES = 40  # safety cap (~25 pages today) — stop paginating past this
FINVIZ_REQUEST_DELAY_SECONDS = 0.5  # courtesy delay between sequential page GETs —
                                       # same class as SEC_REQUEST_DELAY_SECONDS (0.2)
```

**`.info` numeric extraction, None-safe** (from `fundamentals_context.py:41–53`):
```python
info = data.info
total_cash = info.get("totalCash")
total_debt = info.get("totalDebt")
market_cap = info.get("marketCap")
if total_cash is None or total_debt is None or not market_cap:  # 0 mcap = unusable
    return None  # not enough data to test this ticker
net_cash = total_cash - total_debt
cash_ratio = net_cash / market_cap
```

**Cash-flow gate with annual fallback**:
```python
ocf = info.get("operatingCashflow")
fcf = info.get("freeCashflow")
if ocf is None or fcf is None:
    annual = market_data.fetch_cash_flow_statement(data.ticker)  # latest ANNUAL, or None
    if annual is not None:
        ocf = ocf if ocf is not None else annual.get("operating_cash_flow")
        fcf = fcf if fcf is not None else annual.get("free_cash_flow")
cash_flow_ok = ocf is not None and fcf is not None and ocf > 0 and fcf > 0
```

**Ethical filter 3-way** (from `engine.py:137`):
```python
from scripts.ethical_filter import check_ticker as ethical_check
excluded, reason = ethical_check(ticker)
if excluded:
    continue  # defense contractor — dropped entirely, not shown
# else: reason may be "REVIEW: ..." — keep the row, prefix its plain-English read
```

**Report render** (from `heartbeat_scan.py:85–116` + `monitor.py:238–248`):
```python
def render_report(result: dict) -> str:
    lines = [
        "# Cash 80% Trading Value",
        "",
        "What this is: companies whose net cash (cash minus debt) is at least 80% of "
        "their market cap AND that are cash-flow positive — you're paying roughly the "
        "cash balance and getting the operating business for the stub.",
        "",
        "Auto-generated daily — overwritten every run. Advisor notes only; no trade "
        "action is ever suggested here (see SOUL.md). Run your own `find` / `assess` "
        "on anything you like the look of.",
        "",
        f"## Run: {_today_sydney()}",
        ...
    ]
    ...
    return "\n".join(lines) + "\n"
```

**CLI cmd** (from `main.py` `cmd_find`:56–62 + `cmd_gold_backtest`:285–293):
```python
def cmd_cash_value_scan(args) -> None:
    from .cash_value_scan import run_scan, write_report

    conn = _open_conn()          # read-only use — tag held/watchlist rows only
    result = run_scan(conn)
    conn.close()
    write_report(result)
    print(
        f"Cash-value scan complete: {result['qualifying_count']} name(s) at >=80% "
        f"net cash / market cap. See investments/my-trader/cash-value-report.md"
    )
```

**Systemd pair** (from `second-brain-goat-insider-scan.{service,timer}`) — exact
field set, only Description / WorkingDirectory / ExecStart / log path / OnCalendar
change.

---

## IMPLEMENTATION PLAN

### Phase 1: Foundation — Config + Universe Scrapers

Add every constant the feature needs to `config.py` first (so the scrapers and
orchestrator can import real names, not placeholders). Then build the two
universe-provider scrapers as standalone, independently-testable modules with no
dependency on the orchestrator.

**Tasks:** config block; `finviz_screener.py` + tests; `asx200_universe.py` + tests.

### Phase 2: Core Implementation — Metric Math + Orchestration

Build `cash_value_scan.py`: the pure per-ticker metric functions (net cash, cash
ratio, EV%, FCF yield on EV, cash-flow gate), then the enrichment loop, then the
filter/rank/render/write pipeline, then the stale-report fallback.

**Tasks:** `cash_value_scan.py` (compute helpers → `run_scan` → `render_report` →
`write_report`); tests.

### Phase 3: Integration — CLI + Test Isolation

Wire `cash-value-scan` into `main.py`. Extend `conftest.py` so the new network call
sites are stubbed suite-wide and the report path is isolated.

**Tasks:** `main.py` subparser/cmd/dispatch; `conftest.py` fixtures.

### Phase 4: Deployment + Docs

Systemd pair, `TOOLS.md`, handoff status line. (Enabling the timer on the VPS is a
manual step handed to Shaun — see Level 4 validation.)

**Tasks:** two systemd unit files; `TOOLS.md` edits; handoff status line;
`deploy.ps1` `$TIMERS` entry (confirm during implementation).

---

## STEP-BY-STEP TASKS

Execute in order, top to bottom. Each task is independently testable.

### Task 1: ADD config block to `investments/my-trader/mytrader/config.py`

- **IMPLEMENT**: Append a new block at end of file (after `INSIDER_SELLING_*`), with
  the `feedback_check_interpretation_convention` comment style (full metric name +
  "which direction is good" + a source citation on every threshold):
  ```python
  # ---------------------------------------------------------------------------
  # Cash-Value Scanner ("Cash 80% Trading Value") — mytrader/cash_value_scan.py,
  # per .agent/plans/cash-value-scanner.md. Scheduled daily on the VPS. Screens for
  # companies trading at ~cash value: net cash (cash + short-term investments minus
  # total debt) >= 80% of market cap, AND positive operating + free cash flow.
  # Advisor-notes report only; no staging, no alerts. Shaun's idea 2026-08-26.
  # ---------------------------------------------------------------------------
  CASH_VALUE_REPORT_PATH = MY_TRADER_DIR / "cash-value-report.md"

  CASH_VALUE_RATIO_THRESHOLD = 0.80  # qualifies when net cash / market cap >= this.
      # Higher = more of the share price is just the bank balance. 0.80 = "paying
      # ~20c on the dollar for everything the business does except its cash." Plain
      # hard cutoff, no near-miss band — Shaun's call, 2026-08-26.
  CASH_VALUE_MICRO_CAP_TAG_USD = 50_000_000.0  # tag (NOT drop) rows below this market
      # cap with "micro" — cash-value micro-caps are disproportionately distressed /
      # illiquid, but Finviz's coarse filter (avg vol > 100K, price > $1) already
      # removes the untradeable shells, and Shaun wants to eyeball everything.
      # Smaller = less liquid / higher risk. Shaun's call, 2026-08-26.
  CASH_VALUE_MICRO_CAP_TAG_AUD = 75_000_000.0  # ~same threshold for AUD-denominated
      # ASX rows (rough USD->AUD, not a live FX rate — this is a display tag only).
  CASH_VALUE_EXCLUDED_SECTORS = frozenset({
      "Financial", "Financial Services", "Real Estate",  # net cash is not a
  })  # meaningful concept for a bank / REIT — Shaun's call, 2026-08-26. Matches both
      # Finviz sector strings ("Financial", "Real Estate") and yfinance's
      # ("Financial Services", "Real Estate").
  CASH_VALUE_REPORT_MAX_ROWS = 60  # if more than this qualify, show the top N by cash
      # ratio and note the overflow count. Ratio sort + the cash-flow gate should
      # keep it well under this in practice. v1 best-guess cap.

  # Finviz screener scraper (mytrader/finviz_screener.py) — US universe source.
  FINVIZ_SCREENER_URL = "https://finviz.com/screener.ashx"
  FINVIZ_USER_AGENT = (  # real browser UA — Finviz blocks obviously-bot UAs on some
      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
  )  # paths; same reasoning as ASX_USER_AGENT above.
  FINVIZ_SCREENER_FILTERS = "fa_pc_u3,geo_usa,sh_avgvol_o100,sh_price_o1"  # Price/Cash
      # < 3 (net cash <= gross cash, so net cash >= 80% mcap implies P/C <= 1.25 —
      # P/C < 3 safely contains every true positive), US-listed, avg vol > 100K,
      # price > $1. Live-verified 2026-08-26: 492 matches / 25 pages.
  FINVIZ_SCREENER_ROWS_PER_PAGE = 20  # free tier; pagination is &r=1,21,41,...
  FINVIZ_MAX_PAGES = 40  # safety cap (~25 pages of real data today).
  FINVIZ_REQUEST_DELAY_SECONDS = 0.5  # courtesy delay between sequential page GETs —
                                         # same class as SEC_REQUEST_DELAY_SECONDS.

  # S&P/ASX 200 constituent scrape (mytrader/asx200_universe.py) — ASX universe source.
  ASX200_WIKI_URL = "https://en.wikipedia.org/wiki/S%26P/ASX_200"
  ASX200_USER_AGENT = "Mozilla/5.0 (compatible; SecondBrainMyTrader/1.0)"  # Wikipedia
      # is scrape-friendly; a descriptive UA is enough (same as GOAT_SP500_USER_AGENT).
  ```
- **PATTERN**: `config.py` lines 307–330 (`ETF_*` — rule-of-thumb citation style),
  lines 531–554 (`OPENINSIDER_*` / `INSIDER_SELLING_*` — new-scraper-config block).
  `MY_TRADER_DIR` is already defined at line 10.
- **IMPORTS**: none new — `frozenset`, `Path` (via `MY_TRADER_DIR`) already available.
- **GOTCHA**: keep `CASH_VALUE_EXCLUDED_SECTORS` matching **both** vocabularies —
  Finviz says `"Financial"`, yfinance says `"Financial Services"`.
- **VALIDATE**: `uv run --directory investments/my-trader python -c "from mytrader import config; print(config.CASH_VALUE_RATIO_THRESHOLD, config.FINVIZ_SCREENER_FILTERS, config.CASH_VALUE_REPORT_PATH.name)"`

### Task 2: CREATE `investments/my-trader/mytrader/finviz_screener.py`

- **IMPLEMENT**: A paginated Finviz Overview-view screener-table scraper.
  ```python
  """Finviz screener HTML-table scraper -- the US universe for the cash-value scan
  (mytrader/cash_value_scan.py, see .agent/plans/cash-value-scanner.md). Mirrors
  openinsider.py's direct-fetch style (requests + BeautifulSoup, headers dict,
  timeout, try/except-returns-None-on-any-failure). Coarse Price/Cash prefilter
  only -- the precise net-cash test runs later in the yfinance enrichment pass."""

  from __future__ import annotations

  import time

  from . import config, tickers

  _HEADERS = {"User-Agent": config.FINVIZ_USER_AGENT}

  # v=111 "Overview" columns, live-confirmed 2026-08-26.
  _EXPECTED_COLUMNS = {
      "Ticker": "ticker",
      "Company": "company",
      "Sector": "sector",
      "Industry": "industry",
      "Country": "country",
      "Market Cap": "market_cap_text",
      "Price": "price_text",
  }


  def _fetch_page(row_offset: int) -> str | None:
      import requests
      params = {
          "v": "111",
          "f": config.FINVIZ_SCREENER_FILTERS,
          "o": "pricecash",
          "r": str(row_offset),
      }
      try:
          r = requests.get(config.FINVIZ_SCREENER_URL, headers=_HEADERS, params=params, timeout=30)
          if r.status_code != 200:
              return None
          return r.text
      except Exception:
          return None


  def _parse_page(html: str) -> list[dict] | None:
      """Returns the page's data rows, [] if the page is a valid screener page with
      no rows (end of pagination), None if it doesn't look like a screener results
      page at all."""
      from bs4 import BeautifulSoup

      soup = BeautifulSoup(html, "html.parser")
      table = None
      for candidate in soup.find_all("table"):
          headers = [" ".join(th.get_text(strip=True).split()) for th in candidate.find_all("th")]
          if "Ticker" in headers and "Market Cap" in headers:
              table = candidate
              break
      if table is None:
          # A real Finviz page always renders the filter chrome even with 0 results;
          # "Total" appears in the results-count text. Its absence => not a real
          # screener page (blocked, captcha, layout change) => unknown/failure.
          return [] if "Total" in html else None

      header_cells = [" ".join(th.get_text(strip=True).split()) for th in table.find_all("th")]
      col_index = {
          _EXPECTED_COLUMNS[h]: i for i, h in enumerate(header_cells) if h in _EXPECTED_COLUMNS
      }
      if "ticker" not in col_index:
          return None

      rows: list[dict] = []
      for tr in table.find_all("tr"):
          cells = tr.find_all("td")
          if not cells or col_index["ticker"] >= len(cells):
              continue
          ticker_text = cells[col_index["ticker"]].get_text(strip=True)
          if not ticker_text or ticker_text.lower() in {"ticker", "no."}:
              continue
          row = {"ticker": tickers.normalize(ticker_text)}
          for field, idx in col_index.items():
              if field == "ticker" or idx >= len(cells):
                  continue
              row[field] = cells[idx].get_text(strip=True)
          rows.append(row)
      return rows


  def fetch_screener_universe() -> list[dict] | None:
      """Paginates the coarse Finviz screen. Returns the deduped list of rows, or
      None if the FIRST page fails (total failure -- caller serves a stale report).
      A later-page failure stops pagination early and returns what was gathered so
      far (partial is better than nothing for a coarse prefilter)."""
      all_rows: list[dict] = []
      seen: set[str] = set()
      for page in range(config.FINVIZ_MAX_PAGES):
          offset = 1 + page * config.FINVIZ_SCREENER_ROWS_PER_PAGE
          html = _fetch_page(offset)
          if html is None:
              if page == 0:
                  return None
              break
          parsed = _parse_page(html)
          if parsed is None:
              if page == 0:
                  return None
              break
          if not parsed:
              break
          new = [r for r in parsed if r["ticker"] not in seen]
          for r in new:
              seen.add(r["ticker"])
          all_rows.extend(new)
          if len(parsed) < config.FINVIZ_SCREENER_ROWS_PER_PAGE:
              break
          if page < config.FINVIZ_MAX_PAGES - 1:
              time.sleep(config.FINVIZ_REQUEST_DELAY_SECONDS)
      return all_rows
  ```
- **PATTERN**: `openinsider.py` `_fetch` (167–177), `_parse_table` (113–164),
  `_ZERO_RESULTS_MARKER` idiom (101–126). `import requests` / `from bs4 import
  BeautifulSoup` **inside** the functions (matches openinsider.py + how the tests
  monkeypatch `requests.get`).
- **IMPORTS**: `time` (stdlib, top-level ok — openinsider.py keeps `requests`/`bs4`
  function-local but `time` is fine at module level; check no lint objection).
- **GOTCHA**: (1) Finviz's first "row" is `&r=1` not `&r=0`. (2) The header row and
  a "No." index column exist — skip any `<tr>` whose ticker cell is empty or literally
  `"Ticker"` / `"No."`. (3) Finviz renders **multiple** `<table>` elements (nav,
  filters, results) — pick the one whose `<th>` set has both `"Ticker"` and
  `"Market Cap"`. (4) The real pagination-end signal is a short page (< 20 rows) or a
  page with 0 data rows — both handled. (5) `time.sleep` in the loop will make the
  full-run test slow — tests must patch `_fetch_page` (not `requests.get`) OR patch
  `time.sleep`; see Task 3.
- **VALIDATE**: `uv run --directory investments/my-trader python -c "import mytrader.finviz_screener"`
  then Task 3's tests. (A real network smoke test belongs in Level 4, on the VPS.)

### Task 3: CREATE `investments/my-trader/mytrader/tests/test_finviz_screener.py`

- **IMPLEMENT**: Mirror `test_openinsider.py`. A `_FAKE_PAGE_HTML` constant with a
  representative Finviz Overview table (nav table + filter table + results table with
  ~3 rows incl. the header row and a "No." column), a `_FakeResponse` class, and:
  - `test_parse_page_extracts_ticker_sector_marketcap`
  - `test_parse_page_normalizes_dotted_tickers` (`BRK.B` → `BRK-B`)
  - `test_parse_page_returns_empty_list_when_no_data_rows_but_total_present`
  - `test_parse_page_returns_none_when_not_a_screener_page` (`"<html>nope</html>"`)
  - `test_fetch_screener_universe_paginates_until_short_page` — monkeypatch
    `finviz_screener._fetch_page` to return full pages for offsets 1, 21 then a
    short page for 41; assert the combined deduped row count and that offset 61 is
    never requested.
  - `test_fetch_screener_universe_returns_none_when_first_page_fails` —
    `_fetch_page` returns `None` for offset 1.
  - `test_fetch_screener_universe_stops_early_and_returns_partial_on_later_page_failure`
  - `test_fetch_screener_universe_dedupes_across_pages`
  - `test_fetch_screener_universe_sleeps_between_pages` — monkeypatch `time.sleep`
    with a call counter, assert it's called (pages - 1) times, not after the last.
- **PATTERN**: `test_openinsider.py` in full — `_FakeResponse`, the
  `monkeypatch.setattr("requests.get", ...)` for parse tests, direct
  `monkeypatch.setattr("mytrader.finviz_screener._fetch_page", ...)` for pagination
  tests (so no real sleep, no real HTTP).
- **GOTCHA**: patch `mytrader.finviz_screener.time.sleep` (or
  `monkeypatch.setattr("time.sleep", ...)`) in the pagination tests or they take
  `0.5s * pages`.
- **VALIDATE**: `uv run --directory investments/my-trader python -m pytest -q mytrader/tests/test_finviz_screener.py`

### Task 4: CREATE `investments/my-trader/mytrader/asx200_universe.py`

- **IMPLEMENT**: Wikipedia S&P/ASX 200 constituent-table scraper, mirroring
  `goat/goat/sp500_universe.py:fetch_sp500_constituents` minus the DB cache.
  ```python
  """S&P/ASX 200 constituent universe for the cash-value scan (mytrader/
  cash_value_scan.py, see .agent/plans/cash-value-scanner.md). Scrapes Wikipedia's
  constituent table -- mirrors goat/goat/sp500_universe.py's fetch style (requests +
  BeautifulSoup, headers dict, timeout, try/except-returns-None-on-any-failure).
  No DB cache: unlike goat's S&P 500 scan this tool is DB-write-free, so it re-scrapes
  each run; a scrape failure just means "no ASX rows this run" (cash_value_scan.py
  notes that inline and still writes the US report)."""

  from __future__ import annotations

  from . import config, tickers

  _HEADERS = {"User-Agent": config.ASX200_USER_AGENT}


  def fetch_asx200_constituents() -> list[dict[str, str]] | None:
      import requests
      from bs4 import BeautifulSoup

      try:
          r = requests.get(config.ASX200_WIKI_URL, headers=_HEADERS, timeout=30)
          if r.status_code != 200:
              return None
          soup = BeautifulSoup(r.text, "html.parser")
          table = None
          for candidate in soup.find_all("table", {"class": "wikitable"}):
              headers = [th.get_text(strip=True).lower() for th in candidate.find_all("th")]
              if any(h in ("code", "asx code", "symbol", "ticker") for h in headers):
                  table = candidate
                  break
          if table is None:
              return None

          header_cells = [th.get_text(strip=True).lower() for th in table.find_all("th")]
          def _col(*names: str) -> int | None:
              for i, h in enumerate(header_cells):
                  if h in names:
                      return i
              return None
          code_i = _col("code", "asx code", "symbol", "ticker")
          company_i = _col("company", "company name", "name")
          sector_i = _col("sector", "gics sector")
          if code_i is None:
              return None

          rows: list[dict[str, str]] = []
          for tr in table.find_all("tr")[1:]:
              cells = tr.find_all("td")
              if not cells or code_i >= len(cells):
                  continue
              code = cells[code_i].get_text(strip=True)
              if not code:
                  continue
              rows.append({
                  "ticker": tickers.normalize(code),  # bare code; .AX added by caller
                  "company": cells[company_i].get_text(strip=True) if company_i is not None and company_i < len(cells) else "",
                  "sector": cells[sector_i].get_text(strip=True) if sector_i is not None and sector_i < len(cells) else "",
              })
          return rows or None
      except Exception:
          return None
  ```
- **PATTERN**: `sp500_universe.fetch_sp500_constituents` (lines 21–57) — the
  `try` / `status_code` / `soup.find("table", ...)` / skip-header / `len(cells)` guard
  / `tickers.normalize` / `return rows or None` shape, and the bare
  `except Exception: return None`.
- **IMPORTS**: `from . import config, tickers`. `requests` / `bs4` function-local.
- **GOTCHA**: (1) The Wikipedia table's exact header label may be `"Code"`,
  `"ASX code"`, or `"Symbol"` depending on the revision — the `_col` helper tries
  several. If it changes again, the function returns `None` (graceful). (2) The
  ticker is stored **bare** (`WES`, not `WES.AX`); `cash_value_scan.py` builds the
  `.AX` form via `tickers.asx_variant`. (3) Some constituent rows contain a `<sup>`
  reference marker inside the code cell — `get_text(strip=True)` includes it;
  `tickers.normalize` uppercases but won't strip a stray digit. Add a guard:
  `code = "".join(c for c in code if c.isalpha())` before `normalize` — ASX codes
  are 3 letters (a few are 3+, all alpha). **Verify against the live page during
  implementation.**
- **VALIDATE**: `uv run --directory investments/my-trader python -c "import mytrader.asx200_universe"`
  then Task 5's tests.

### Task 5: CREATE `investments/my-trader/mytrader/tests/test_asx200_universe.py`

- **IMPLEMENT**: `_FAKE_WIKI_HTML` with a `wikitable` containing a `Code`/`Company`/
  `Sector`/`Market cap` header and ~2 constituent rows, plus:
  - `test_fetch_parses_code_company_sector`
  - `test_fetch_strips_reference_markers_from_code` (`WES[1]` → `WES`)
  - `test_fetch_returns_none_on_missing_table`
  - `test_fetch_returns_none_on_bad_status`
  - `test_fetch_returns_none_on_network_error`
  - `test_fetch_handles_alternate_header_label` (`"Symbol"` instead of `"Code"`)
- **PATTERN**: `test_openinsider.py` `_FakeResponse` + `monkeypatch.setattr("requests.get", ...)`.
  (`goat/goat/tests/test_sp500_universe.py` is the closer analogue — read it for the
  Wikipedia-fixture shape.)
- **VALIDATE**: `uv run --directory investments/my-trader python -m pytest -q mytrader/tests/test_asx200_universe.py`

### Task 6: CREATE `investments/my-trader/mytrader/cash_value_scan.py`

- **IMPLEMENT**: The orchestrator. Sections:

  1. **Module docstring** referencing the plan doc.
  2. **`_today_sydney()`** — copy verbatim from `monitor.py:38–43` (the
     `SYDNEY_TZ = ZoneInfo("Australia/Sydney")` module constant + the function).
  3. **`compute_cash_value_metrics(data) -> dict | None`** — pure function.
     `data` is a `TickerData`. Returns `None` when `marketCap`/`totalCash`/`totalDebt`
     are not all present (can't test). Otherwise returns:
     ```python
     {
         "net_cash": net_cash,                    # total_cash - total_debt
         "cash_ratio": net_cash / market_cap,     # the headline
         "ev": market_cap - net_cash,             # enterprise value proxy (the "stub")
         "ev_pct_of_mcap": (market_cap - net_cash) / market_cap,  # = 1 - cash_ratio
         "market_cap": market_cap,
         "operating_cash_flow": ocf,              # after annual fallback; may be None
         "free_cash_flow": fcf,                   # after annual fallback; may be None
         "fcf_yield_on_ev": (fcf / ev) if (fcf is not None and ev and ev > 0) else None,
         "revenue_growth": data.info.get("revenueGrowth"),
         "sector": data.info.get("sector"),
         "currency": data.info.get("financialCurrency") or data.info.get("currency"),
         "cash_flow_ok": ocf is not None and fcf is not None and ocf > 0 and fcf > 0,
         "cash_flow_source": "info" | "annual" | "partial-annual",  # for the report note
     }
     ```
     Use the "Cash-flow gate with annual fallback" snippet from **Patterns to Follow**.
     `fetch_cash_flow_statement` is `market_data.fetch_cash_flow_statement`.
  4. **`_passes(metrics) -> bool`** — `metrics is not None and
     metrics["cash_ratio"] >= config.CASH_VALUE_RATIO_THRESHOLD and
     metrics["cash_flow_ok"] and metrics["sector"] not in
     config.CASH_VALUE_EXCLUDED_SECTORS`.
  5. **`_enrich_universe(coarse_rows, *, market, held, watched) -> list[dict]`** —
     for each coarse row: skip if `row["sector"]` (the Finviz/Wiki sector) is in
     `CASH_VALUE_EXCLUDED_SECTORS` (cheap pre-skip, saves a yfinance call); run
     `ethical_check` and `continue` if `excluded`; build the yfinance ticker
     (`row["ticker"]` for US, `tickers.asx_variant(row["ticker"])` for ASX);
     `data = market_data.fetch_ticker_data(yf_ticker)`; `if data is None: continue`;
     `metrics = compute_cash_value_metrics(data)`; `if not _passes(metrics): continue`;
     assemble the result row (ticker, company, market label, all metrics, the
     `REVIEW:` reason if any, `held`/`watched` tags, `micro` tag if
     `market_cap < CASH_VALUE_MICRO_CAP_TAG_{USD,AUD}`, a `revenue_growth` warning
     tag if `revenue_growth is not None and revenue_growth < 0`, and a one-line
     plain-English read). Wrap the per-ticker body in `try/except Exception` with a
     `print(f"[cash-value-scan] error on {yf_ticker}: {e}")` (matches
     `heartbeat_scan.py:72–73` / `monitor.py:143–144`).
  6. **`run_scan(conn) -> dict`**:
     - `held = {r["ticker"] for r in mt_db.get_all_holdings(conn)}`,
       `watched = {r["ticker"] for r in mt_db.get_all_watchlist(conn)}`
       (import `from . import db as ...` — the module is `mytrader.db`; `main._open_conn`
       already inits the tables).
     - `us_coarse = finviz_screener.fetch_screener_universe()`
     - `asx_coarse = asx200_universe.fetch_asx200_constituents()`
     - If `us_coarse is None` → return `{"stale": True, ...}` (caller re-serves the
       old report with a banner).
     - `with market_data.cached_session():` run `_enrich_universe` for US then ASX
       (ASX only if `asx_coarse` is not `None`).
     - Combine, sort by `cash_ratio` desc, split into shown / overflow at
       `CASH_VALUE_REPORT_MAX_ROWS`.
     - Return `{"stale": False, "us_rows": [...], "asx_rows": [...],
       "asx_unavailable": asx_coarse is None, "qualifying_count": N,
       "us_scanned": len(us_coarse), "asx_scanned": len(asx_coarse or []),
       "overflow": M}`.
  7. **`render_report(result) -> str`** — the `lines: list[str]` + `"\n".join + "\n"`
     shape. Header per the **Patterns to Follow** snippet. One combined ranked table
     (US + ASX merged, sorted by ratio), columns per the handoff's "Ranking design":
     `| Ticker | Company | Mkt | Cash ratio | EV % of mcap | Market cap | OCF (TTM) |
     FCF | FCF yld on EV | Net cash | Rev growth YoY | Sector | Tags | Read |`.
     "Tags" column carries `● held` / `○ watchlist` / `⚠ micro` /
     `⚠ shrinking revenue` / `REVIEW: defense`. "Read" is the one-line plain-English
     synthesis. Prefix with `## Run: {_today_sydney()}` and a
     `Scanned N US + M ASX names; K qualify at >= 80% net cash / market cap.` line.
     If `result["asx_unavailable"]`: add `> ASX universe unavailable this run
     (Wikipedia scrape failed) — US results only.` If `result["overflow"]`: footer
     `... and {overflow} more below the top {MAX_ROWS} (by cash ratio).`
     End with `Last auto-generated: {_today_sydney()}.`
  8. **`write_report(result) -> None`**:
     ```python
     def write_report(result: dict) -> None:
         if result.get("stale"):
             _write_stale_banner()
             return
         config.CASH_VALUE_REPORT_PATH.write_text(render_report(result), encoding="utf-8")

     def _write_stale_banner() -> None:
         """US (Finviz) fetch failed -> keep yesterday's report, prepend a banner.
         If there is no prior report at all, write a minimal 'scan failed' file."""
         path = config.CASH_VALUE_REPORT_PATH
         banner = (
             f"> ⚠ STALE - Finviz fetch failed {_today_sydney()}, showing the "
             f"last good run below.\n\n"
         )
         if path.exists():
             existing = path.read_text(encoding="utf-8")
             # strip any prior stale banner so they don't stack
             existing = existing.split("\n\n", 1)[1] if existing.startswith("> ⚠ STALE") else existing
             path.write_text(banner + existing, encoding="utf-8")
         else:
             path.write_text(
                 f"# Cash 80% Trading Value\n\n{banner}No prior report to show.\n",
                 encoding="utf-8",
             )
     ```
- **PATTERN**: `heartbeat_scan.py` (whole file) for the run/render/write triad;
  `monitor.py:117` for `with market_data.cached_session():`; `engine.py:8,137` for
  the ethical filter; `fundamentals_context.py:41–53` for `.info` None-safety;
  `monitor.py:41–43` for `_today_sydney`.
- **IMPORTS**:
  ```python
  from __future__ import annotations
  import sqlite3
  from datetime import datetime
  from zoneinfo import ZoneInfo
  from scripts.ethical_filter import check_ticker as ethical_check
  from . import asx200_universe, config, db as mt_db, finviz_screener, market_data, tickers
  ```
- **GOTCHA**: (1) `net_cash` can exceed `market_cap` (`cash_ratio > 1`) — a company
  trading **below** net cash. `ev` goes negative; `ev_pct_of_mcap` goes negative;
  `fcf_yield_on_ev` is undefined (guard `ev > 0`). Render these as
  `EV % of mcap: -12% (below net cash)` and `FCF yld on EV: n/a`. This is the
  best-case find, not an error. (2) `revenueGrowth` is a fraction (`0.05` = +5%),
  display `* 100`. (3) yfinance `.info["sector"]` for ETFs/funds is often absent —
  a fund slipping through the Finviz screen will just fail `compute_cash_value_metrics`
  (no `totalDebt`) and be skipped; no special handling needed. (4) The ASX
  `_enrich_universe` call must build `tickers.asx_variant(row["ticker"])`
  (`WES` → `WES.AX`) — do NOT rely on `fetch_ticker_data`'s bare-then-`.AX` fallback
  (it works, but an explicit `.AX` avoids a wasted first lookup for all 200 names).
  (5) `get_all_holdings` / `get_all_watchlist` rows are `sqlite3.Row` — access
  `r["ticker"]`, never `r.get(...)`. (6) Do not write to the DB anywhere in this
  module — `conn` is read-only by convention here.
- **VALIDATE**: `uv run --directory investments/my-trader python -c "import mytrader.cash_value_scan"`
  then Task 7.

### Task 7: CREATE `investments/my-trader/mytrader/tests/test_cash_value_scan.py`

- **IMPLEMENT**:
  - **`compute_cash_value_metrics`**:
    - `test_computes_ratio_and_ev_for_cash_rich_name` — `TickerData(info={"marketCap":
      100e6, "totalCash": 120e6, "totalDebt": 20e6, "operatingCashflow": 5e6,
      "freeCashflow": 4e6, "sector": "Technology"})` → `cash_ratio == 1.0`,
      `ev == 0`, `cash_flow_ok is True`.
    - `test_returns_none_when_market_cap_missing`
    - `test_returns_none_when_total_debt_missing`
    - `test_cash_ratio_above_one_when_trading_below_net_cash` — `net_cash > mcap`;
      assert `ev < 0`, `fcf_yield_on_ev is None`.
    - `test_cash_flow_falls_back_to_annual_when_info_missing` — monkeypatch
      `mytrader.market_data.fetch_cash_flow_statement` to return
      `{"operating_cash_flow": 3e6, "free_cash_flow": 2e6, "free_cash_flow": ...}`;
      `.info` has no `operatingCashflow`/`freeCashflow`; assert `cash_flow_ok`,
      `cash_flow_source == "annual"`.
    - `test_cash_flow_not_ok_when_fcf_negative`
  - **`_passes`**:
    - `test_passes_requires_ratio_and_cashflow_and_sector`
    - `test_rejects_financial_services_sector`
    - `test_rejects_below_threshold_ratio` (0.79 fails, 0.80 passes)
  - **`run_scan`** (with `db_conn` fixture + monkeypatched universe fetchers +
    monkeypatched `market_data.fetch_ticker_data`):
    - Seed `db_conn` with one holding (`upsert_holding`) and one watchlist row
      (`upsert_watchlist_row`), patch `finviz_screener.fetch_screener_universe` to
      return 3 coarse rows (one qualifying, one failing the ratio, one a defense
      ticker like `"LMT"`), patch `asx200_universe.fetch_asx200_constituents` to
      return 1 row, patch `market_data.fetch_ticker_data` to return crafted
      `TickerData` per ticker. Assert: only the qualifying names in `us_rows`/
      `asx_rows`, the defense ticker excluded, the held ticker tagged `held`,
      `qualifying_count` correct, `stale is False`.
    - `test_run_scan_returns_stale_when_finviz_fails` — `fetch_screener_universe`
      returns `None` → `result["stale"] is True`.
    - `test_run_scan_notes_asx_unavailable_when_wiki_fails` —
      `fetch_asx200_constituents` returns `None` → `result["asx_unavailable"] is True`,
      US rows still present.
    - `test_run_scan_sorts_by_cash_ratio_desc`
    - `test_run_scan_caps_at_max_rows_and_reports_overflow` — patch
      `config.CASH_VALUE_REPORT_MAX_ROWS` low.
  - **`render_report` / `write_report`**:
    - `test_render_includes_run_date_and_advisor_disclaimer`
    - `test_render_lists_qualifying_names_with_tags`
    - `test_render_shows_asx_unavailable_note`
    - `test_write_stale_banner_prepends_to_existing_report` — write a fake prior
      report to the isolated `CASH_VALUE_REPORT_PATH`, call `write_report({"stale":
      True})`, assert the banner is prepended and the old body preserved.
    - `test_write_stale_banner_does_not_stack` — call it twice, assert one banner.
- **PATTERN**: `test_openinsider.py` (fixture-HTML + monkeypatch style),
  `test_monitor.py` (hand-built result dicts fed to `render_*`), `conftest.py`
  `db_conn` fixture. `mytrader.db.upsert_holding` / `upsert_watchlist_row`
  signatures are in `db.py` (keyword-only args — check the exact names).
- **GOTCHA**: the autouse fixtures from Task 8 stub the universe fetchers to `None`
  by default — every `run_scan` test must **explicitly** `monkeypatch.setattr` them
  back to a data-returning stub (same "save/restore the real ref" discipline as
  `test_market_data.py:16`, except here you just set your own stub).
- **VALIDATE**: `uv run --directory investments/my-trader python -m pytest -q mytrader/tests/test_cash_value_scan.py`

### Task 8: UPDATE `investments/my-trader/mytrader/tests/conftest.py`

- **IMPLEMENT**:
  1. In `_isolate_snapshot_paths` (lines 29–48), add one line:
     ```python
     monkeypatch.setattr(mt_config, "CASH_VALUE_REPORT_PATH", tmp_path / "cash-value-report.md")
     ```
  2. Add three new autouse fixtures at the end of the file, matching the existing
     `_no_real_*` style + docstring convention:
     ```python
     @pytest.fixture(autouse=True)
     def _no_real_finviz_fetch(monkeypatch):
         """cash_value_scan.run_scan() calls finviz_screener.fetch_screener_universe()
         -- a real paginated HTTP scrape -- global/autouse for the same reason as the
         fixtures above: no real network call by default. Tests exercising run_scan
         re-patch this with fixture data."""
         monkeypatch.setattr(
             "mytrader.finviz_screener.fetch_screener_universe", lambda: None
         )

     @pytest.fixture(autouse=True)
     def _no_real_asx200_fetch(monkeypatch):
         """cash_value_scan.run_scan() calls asx200_universe.fetch_asx200_constituents()
         -- a real Wikipedia scrape -- global/autouse, same reason."""
         monkeypatch.setattr(
             "mytrader.asx200_universe.fetch_asx200_constituents", lambda: None
         )

     @pytest.fixture(autouse=True)
     def _no_real_cash_flow_statement_fetch(monkeypatch):
         """cash_value_scan.compute_cash_value_metrics() falls back to
         market_data.fetch_cash_flow_statement() when .info lacks the cash-flow
         fields -- a real yfinance network call -- global/autouse, same reason.
         (test_cash_value_scan.py's annual-fallback test re-patches this.)"""
         monkeypatch.setattr(
             "mytrader.market_data.fetch_cash_flow_statement", lambda ticker: None
         )
     ```
- **GOTCHA**: There is currently **no** autouse stub for `market_data.fetch_ticker_data`
  itself (engine tests mock `run_assessment` a level up). `test_cash_value_scan.py`
  must patch `fetch_ticker_data` per-test. Do **not** add a global autouse stub for
  `fetch_ticker_data` — it would break `test_market_data.py`'s own direct tests.
- **VALIDATE**: `uv run --directory investments/my-trader python -m pytest -q` (full
  suite still green — no pre-existing test regressed by the new autouse fixtures).

### Task 9: UPDATE `investments/my-trader/mytrader/main.py`

- **IMPLEMENT**:
  1. Add `cmd_cash_value_scan` (place near `cmd_gold_backtest`, ~line 285):
     ```python
     def cmd_cash_value_scan(args) -> None:
         from .cash_value_scan import run_scan, write_report

         conn = _open_conn()
         result = run_scan(conn)
         conn.close()
         write_report(result)
         if result.get("stale"):
             print(
                 "Cash-value scan: Finviz fetch FAILED — kept the previous "
                 "cash-value-report.md with a STALE banner."
             )
             return
         asx_note = " (ASX universe unavailable)" if result.get("asx_unavailable") else ""
         print(
             f"Cash-value scan complete: {result['qualifying_count']} name(s) at "
             f">=80% net cash / market cap{asx_note}. "
             f"See investments/my-trader/cash-value-report.md"
         )
     ```
  2. In `main()` add the subparser (near `gold-backtest`, ~line 360):
     ```python
     subparsers.add_parser(
         "cash-value-scan",
         help="Screen US + ASX for companies with net cash >= 80% of market cap and "
              "positive cash flow (writes cash-value-report.md)",
     )
     ```
  3. Add to the `dispatch` dict: `"cash-value-scan": cmd_cash_value_scan,`.
- **PATTERN**: `cmd_gold_backtest` (285–293) — no-arg subcommand, opens conn, does
  work, prints one line. `subparsers.add_parser("snapshot", ...)` (353) — no-arg
  parser. `dispatch` dict (403–421).
- **GOTCHA**: this subcommand has **no arguments** — use the bare
  `subparsers.add_parser("cash-value-scan", help=...)` form (like `snapshot` /
  `monitor` / `gold-backtest`), not one with `.add_argument`.
- **VALIDATE**:
  `uv run --directory investments/my-trader python -m mytrader.main cash-value-scan --help`
  (should print the help, not error). Full run is Level 4 (VPS only — it hits the
  live DB + network).

### Task 10: CREATE the systemd pair in `scripts/systemd/`

- **IMPLEMENT**:
  `scripts/systemd/second-brain-mytrader-cashvalue-scan.service`:
  ```ini
  [Unit]
  Description=my-trader Cash-Value Scan
  After=network.target

  [Service]
  Type=oneshot
  User=secondbrain
  WorkingDirectory=/home/secondbrain/second-brain/investments/my-trader
  ExecStart=/home/secondbrain/second-brain/investments/.venv/bin/python -m mytrader.main cash-value-scan
  StandardOutput=append:/home/secondbrain/second-brain/investments/my-trader/cashvalue_scan_runs.log
  StandardError=append:/home/secondbrain/second-brain/investments/my-trader/cashvalue_scan_runs.log
  ```
  `scripts/systemd/second-brain-mytrader-cashvalue-scan.timer`:
  ```ini
  [Unit]
  Description=my-trader Cash-Value Scan Timer
  Requires=second-brain-mytrader-cashvalue-scan.service

  [Timer]
  OnCalendar=*-*-* 22:30:00 UTC
  Persistent=true

  [Install]
  WantedBy=timers.target
  ```
- **PATTERN**: `second-brain-goat-insider-scan.{service,timer}` — byte-for-byte
  except Description / WorkingDirectory / ExecStart module+cmd / log path / OnCalendar.
- **GOTCHA**: `WorkingDirectory` is `investments/my-trader` and the module is
  `mytrader.main` (per `invoke_investments.ps1`'s `$PACKAGES` map) — NOT
  `investments/goat` / `goat.main`. The venv is the shared
  `investments/.venv` (goat units use it; my-trader on the VPS resolves
  `scripts.*` and `briefs-finance` through that same workspace venv).
- **VALIDATE**: `python -c "import configparser; c=configparser.ConfigParser(); c.optionxform=str; c.read('scripts/systemd/second-brain-mytrader-cashvalue-scan.timer'); print(dict(c['Timer']))"`
  (parses cleanly). Real `systemctl` enable is Level 4.

### Task 11: UPDATE `investments/TOOLS.md`

- **IMPLEMENT**:
  1. **Daily Read** table (lines ~14–22): add a row
     `| [investments/my-trader/cash-value-report.md](my-trader/cash-value-report.md) | Cash-Value Scan (daily, ~22:30 UTC) | [→](#cashvalue-scan) |`
  2. **Automated (scheduled)** table (lines ~31–38): add a row after the my-trader
     Monitor row:
     `| <a id="cashvalue-scan"></a>[↑](#daily-read) **Cash-Value Scan** ("Cash 80% Trading Value") | Screens US (Finviz) + ASX 200 (Wikipedia) for net cash >= 80% of market cap + positive operating & free cash flow; ranked advisor-notes list, no staging/alerts | VPS systemd (second-brain-mytrader-cashvalue-scan.timer) | Daily, 22:30 UTC | investments/my-trader/cash-value-report.md |`
  3. **Manual / on-demand only** table (lines ~47–68): add a row
     `| **Cash-Value Scan (on-demand)** | Same US+ASX net-cash screen, right now | -Package my-trader -Command "cash-value-scan" | investments/my-trader/cash-value-report.md |`
  4. Update the "Four packages" / "Last updated" line at the top (lines 1–8) — bump
     the date to 2026-08-26 and confirm the package count phrasing still reads right
     (still four packages; this is a new *command*, not a new package).
- **PATTERN**: existing rows in each of the three tables — match column count,
  `<a id>`/`[↑]`/`[→]` anchor convention, and the terse description style.
- **VALIDATE**: manual read-through; `grep -n "cashvalue-scan" investments/TOOLS.md`
  shows the anchor + both `[→]`/`[↑]` links resolve.

### Task 12: UPDATE `investments/cash-value-scanner-handoff.md`

- **IMPLEMENT**: Change line 3 from
  `## Status: NOT STARTED — handoff drafted 2026-08-26 (this session). Awaiting /plan-feature.`
  to
  `## Status: PLANNED — see .agent/plans/cash-value-scanner.md (created 2026-08-26). Awaiting /execute.`
  Leave the rest of the file untouched (historical background record).
- **VALIDATE**: manual read-through.

---

## TESTING STRATEGY

Framework: `pytest` (declared in `investments/my-trader/pyproject.toml`
`[project.optional-dependencies] dev`; `testpaths = ["mytrader/tests"]`,
`pythonpath = ["."]`). All tests run **locally** against fixtures / a tmp-path
SQLite DB — never the VPS `investments.db`, never the live network.

### Unit Tests

- **`finviz_screener.py`** — fixture-HTML parse tests + pagination-logic tests
  (patch `_fetch_page`, not `requests.get`, for the multi-page cases; patch
  `time.sleep`). Zero-result vs. not-a-screener-page distinction. First-page-fail →
  `None`; later-page-fail → partial. Dedup across pages. (Mirror `test_openinsider.py`.)
- **`asx200_universe.py`** — fixture-`wikitable` parse test, reference-marker
  stripping, alternate header label, all failure modes → `None`. (Mirror
  `test_openinsider.py` / `goat`'s `test_sp500_universe.py`.)
- **`cash_value_scan.compute_cash_value_metrics` / `_passes`** — pure functions,
  hand-built `TickerData`, no fixtures beyond `monkeypatch` for the annual fallback.
  Cover: normal cash-rich name, `cash_ratio > 1` (below net cash), missing
  `marketCap`/`totalCash`/`totalDebt` → `None`, annual cash-flow fallback,
  negative-FCF rejection, excluded-sector rejection, sub-threshold ratio rejection.

### Integration Tests

- **`cash_value_scan.run_scan(db_conn)`** — real tmp SQLite (`db_conn` fixture),
  monkeypatched universe fetchers + `market_data.fetch_ticker_data`, seeded holdings
  + watchlist rows. Assert: filtering (ratio / cash-flow / sector / ethical),
  held/watchlist tagging, ranking order, `stale` on Finviz failure,
  `asx_unavailable` on Wikipedia failure, overflow cap.
- **`render_report` / `write_report`** — hand-built `result` dicts (like
  `test_monitor.py` does for `render_report`); assert run-date header, advisor
  disclaimer line, tag rendering, ASX-unavailable note, and the stale-banner
  prepend/no-stack behaviour against the isolated `CASH_VALUE_REPORT_PATH`.

### Edge Cases

- `net_cash > market_cap` (`cash_ratio > 1`) — company trading below its own net
  cash. Must render `ev < 0` / `EV % of mcap` negative / `FCF yld on EV: n/a`
  without a `ZeroDivisionError` or crash. This is the best-case find.
- `marketCap == 0` in `.info` — `not market_cap` guard → `None`, ticker skipped.
- yfinance returns `None` for a ticker entirely (`fetch_ticker_data` → `None`) —
  `continue`, no crash, logged.
- A fund/ETF slips through the Finviz coarse screen — no `totalDebt` in `.info` →
  `compute_cash_value_metrics` → `None` → skipped. No special handling needed.
- Finviz layout change (results `<table>` no longer has a `"Market Cap"` `<th>`) —
  `_parse_page` → `None` on page 0 → `run_scan` returns `stale` → previous report
  kept with a banner (does not silently produce an empty report).
- Wikipedia ASX table header renamed — `fetch_asx200_constituents` → `None` →
  report still written, "ASX universe unavailable" note shown.
- Same ticker on both the US Finviz list and (as an ADR) somewhere — dedup by
  `ticker` within Finviz pagination; US vs ASX lists are disjoint namespaces
  (bare vs `.AX`), no cross-dedup needed.
- Defense ticker (`LMT` etc.) in the coarse list — `ethical_check` → `excluded` →
  dropped, never rendered. `BA` / `PLTR` → `REVIEW:` tag, kept.
- More than `CASH_VALUE_REPORT_MAX_ROWS` qualify — top N by ratio shown, overflow
  count in the footer.
- `time.sleep` between Finviz pages — must not run in tests (patch it).

---

## VALIDATION COMMANDS

Run every command. All Level 1–3 commands run locally; Level 4 runs on the VPS only.

### Level 1: Syntax & Import

```powershell
uv run --directory investments/my-trader python -c "import mytrader.finviz_screener, mytrader.asx200_universe, mytrader.cash_value_scan, mytrader.main, mytrader.config"
uv run --directory investments/my-trader python -m mytrader.main cash-value-scan --help
```
(No dedicated linter is wired for this package beyond what pytest collection surfaces;
`ruff` is available as a dev extra — `uv run --directory investments/my-trader ruff check mytrader/finviz_screener.py mytrader/asx200_universe.py mytrader/cash_value_scan.py` — run it, fix anything, but a clean pytest collection is the hard gate.)

### Level 2: Unit Tests

```powershell
uv run --directory investments/my-trader python -m pytest -q mytrader/tests/test_finviz_screener.py mytrader/tests/test_asx200_universe.py mytrader/tests/test_cash_value_scan.py
```

### Level 3: Full Suite (No Regressions)

```powershell
uv run --directory investments/my-trader python -m pytest -q
```
Must be all-green — the new autouse `conftest.py` fixtures must not break any
existing test.

### Level 4: Manual Validation (VPS only — never local)

`investments.db` lives only on the VPS. Run the scan through the SSH wrapper:
```powershell
.\scripts\invoke_investments.ps1 -Package my-trader -Command "cash-value-scan"
```
Then confirm `investments/my-trader/cash-value-report.md` appears (after the next
vault sync, or check on the VPS directly) with: a `# Cash 80% Trading Value` title,
a `## Run: <date>` line, the advisor-notes disclaimer, a ranked table sorted by cash
ratio, and (if any) `● held` / `○ watchlist` tags matching real holdings. Spot-check
2–3 names by hand against their latest 10-Q / half-year balance sheet
(cash − debt ≈ 80%+ of market cap, OCF and FCF both positive).

Then install + enable the timer on the VPS (hand this to Shaun as one block):
```
ssh secondbrain@137.184.102.104 "sudo cp /home/secondbrain/second-brain/scripts/systemd/second-brain-mytrader-cashvalue-scan.service /etc/systemd/system/ && sudo cp /home/secondbrain/second-brain/scripts/systemd/second-brain-mytrader-cashvalue-scan.timer /etc/systemd/system/ && sudo systemctl daemon-reload && sudo systemctl enable --now second-brain-mytrader-cashvalue-scan.timer && systemctl status second-brain-mytrader-cashvalue-scan.timer --no-pager"
```
(The units also land on the VPS automatically on the next `git pull` there, but
`setup_vps.sh` only auto-*enables* a hardcoded subset — a new timer must be enabled
once by hand, as above.)

### Level 5: Additional Validation (Optional)

```powershell
# Real Finviz reachability smoke test (network — run sparingly, not in CI)
uv run --directory investments/my-trader python -c "from mytrader import finviz_screener; rows = finviz_screener.fetch_screener_universe(); print(None if rows is None else f'{len(rows)} coarse rows, first: {rows[0]}')"
uv run --directory investments/my-trader python -c "from mytrader import asx200_universe; rows = asx200_universe.fetch_asx200_constituents(); print(None if rows is None else f'{len(rows)} ASX 200 rows, first: {rows[0]}')"
```
Expect ~400–500 US coarse rows and ~200 ASX rows. If Finviz returns `None`, check
whether the UA is being blocked (try from a browser) before assuming a code bug.

---

## ACCEPTANCE CRITERIA

- [ ] `mytrader.main cash-value-scan` runs on the VPS and writes
      `investments/my-trader/cash-value-report.md`.
- [ ] The report lists only companies with **net cash ≥ 80% of market cap** AND
      **positive trailing operating cash flow AND positive free cash flow** (with
      annual fallback when `.info` lacks the fields).
- [ ] Financials and Real Estate are excluded; defense contractors are excluded;
      `BA`/`PLTR` appear with a `REVIEW:` tag.
- [ ] Rows are ranked by cash ratio descending; `⚠ micro` tags rows under
      US$50M / A$75M market cap without dropping them.
- [ ] Rows Shaun holds show `● held`; rows on his watchlist show `○ watchlist`.
- [ ] Both US (Finviz, paginated) and ASX 200 (Wikipedia) universes are scanned; an
      ASX scrape failure still produces a US-only report with a visible note.
- [ ] A Finviz (US) scrape failure keeps the previous report and prepends a single
      `STALE` banner (banners do not stack across consecutive failures).
- [ ] `cash_ratio > 1` (trading below net cash) renders cleanly, no crash.
- [ ] New VPS systemd pair exists, mirrors the goat-insider-scan unit shape,
      `OnCalendar=*-*-* 22:30:00 UTC`.
- [ ] `investments/TOOLS.md` documents the tool in all three tables; the handoff
      doc's status line points at this plan.
- [ ] `uv run --directory investments/my-trader python -m pytest -q` is all-green
      (new tests pass, zero existing-test regressions).
- [ ] No writes to `investments.db` anywhere in the new code path (read-only conn
      for hold/watchlist tags only).
- [ ] No changes outside `investments/my-trader/`, `scripts/systemd/`,
      `investments/TOOLS.md`, `investments/cash-value-scanner-handoff.md`, and
      (if confirmed) `scripts/deploy.ps1`'s `$TIMERS` array.

---

## COMPLETION CHECKLIST

- [ ] Tasks 1–12 completed in order.
- [ ] Each task's own VALIDATE command run and passed.
- [ ] Level 1–3 validation commands all pass locally.
- [ ] Level 4 manual run done on the VPS via `invoke_investments.ps1`; report file
      inspected; 2–3 names hand-verified against real filings.
- [ ] Timer enabled on the VPS and `systemctl status` shows it active/waiting.
- [ ] `TOOLS.md` + handoff status line updated.
- [ ] `deploy.ps1` `$TIMERS` decision made and applied (or explicitly left out with
      a one-line reason in the PR/commit message).
- [ ] Auto-memory `project_cash_value_scanner.md` updated to "BUILT / live on VPS"
      after Level 4 passes (separate from this plan — a post-execution step).

---

## NOTES

- **Why my-trader, not Goat**: this is a fundamentals/value screen. Goat is
  momentum/sector-rotation — explicitly a different philosophy
  (`investments/goat/HANDOFF.md`). my-trader already owns the screener-scrape pattern
  (`openinsider.py`), the yfinance wrappers (`market_data.py`), `tickers.normalize`,
  and the ethical-filter import (`engine.py:8`).
- **Why no DB**: Shaun said "just list them" — no staging, no "new since last run"
  diffing, no WhatsApp. Adding those later would need a snapshot table (same shape as
  the deferred goat `goat_rotation_snapshots` work). The read-only conn is only for
  hold/watchlist tags.
- **Finviz scrape acceptability**: `robots.txt` disallows `/screener?*` and `/export`
  / `/api/*`, but not the legacy `/screener.ashx` path this uses, and we never touch
  the export endpoints. ~25 sequential GETs once/day with a real browser UA and a
  0.5s inter-page delay — the same acceptable-scrape class as the existing
  `openinsider.com` and `en.wikipedia.org` scrapes already in this repo. If Finviz
  ever hard-blocks the scrape, the fallback is the SEC XBRL `frames` API (documented
  as the v2 universe source in the handoff) — out of scope here.
- **`net_cash` includes IFRS 16 leases in `totalDebt`** — deliberately, per
  `checks/balance_sheet.py`'s documented reasoning. This makes the 80% bar
  *harder* to clear (more debt subtracted), which is the conservative direction for
  a "safe deep value" screen.
- **ASX side will be thin initially** — ASX 200 constituents are large caps and
  rarely trade at cash value (that's a small/micro-cap phenomenon). A follow-up
  could widen the ASX universe to the All Ordinaries (~500) or a full ASX board
  scrape, at the cost of a longer nightly run. Flagged, not built.
- **Report row cap** (`CASH_VALUE_REPORT_MAX_ROWS = 60`) is a v1 guess. The ratio
  sort + cash-flow gate should keep the real count well under it; tune after seeing
  live output.
- **`.claude/skills/my-trader/SKILL.md`** is conversational-Find-focused and does not
  need to document this scheduled scan (TOOLS.md is the right home). Optionally add a
  one-line "see also: cash-value-scan in TOOLS.md" pointer — not required.
- **Confidence for one-pass execution: 7/10.** The scraper + compute + render +
  CLI + systemd + tests are all close mirrors of existing, well-established patterns
  in this exact package, and the metric math is simple. The two soft spots: (1) the
  live Finviz HTML structure (multiple tables, the "No." column, exact `<th>`
  labels, the `&r=` pagination end-signal) is described from a single live check and
  a browser-rendered view — the execution agent should fetch one real page early and
  adjust `_parse_page` / `_EXPECTED_COLUMNS` against it before writing the tests;
  (2) the S&P/ASX 200 Wikipedia table's exact header label + reference-marker
  handling needs one live look. Both are contained (graceful `None` on mismatch, and
  the stale-report fallback covers a US parse break), so a miss degrades safely
  rather than shipping wrong data.
