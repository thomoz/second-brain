# Feature: Earnings Deterioration Watch

The following plan should be complete, but it's important to validate documentation and
codebase patterns and task sanity before implementing. Pay special attention to naming
of existing utils/types/functions and import direction — in particular the **circular
import fix** in Phase 0 must land before anything else, and `earnings_watch.py`'s
functions must be reused by BOTH `checks/earnings_deterioration.py` (Find/Monitor,
opt-in) and the new standalone `scan-earnings-watch` CLI command — don't fork the logic
into two copies.

Source handoff: `investments/earnings-deterioration-watch-handoff.md` (read it first —
this plan resolves its 7 open questions and supersedes its "Recommended shape" section
where they differ, per the confirmations below).

---

## Feature Description

A daily advisor-notes check on Shaun's **holdings only** (never watchlist) that looks
for early evidence of **deteriorating earnings** — before the next quarterly
10-Q/10-K confirms it. Shaun's framing: official earnings are periodic, but the
*expectation* of earnings moves every day (analyst estimate revisions, 8-K disclosures,
guidance commentary). Three signals, each shown separately so Shaun can see which one
is actually firing:

1. **Analyst estimate-revision trend** — day-over-day consensus EPS/revenue estimate
   drift, sourced from `yfinance`'s `eps_trend`/`earnings_estimate`/`revenue_estimate`/
   `eps_revisions` (confirmed live 2026-09-17 against real AAPL data, `yfinance` 1.5.1
   — see Phase 1). This is the backbone signal; it's the only one that's genuinely
   "moves every day."
2. **Earnings-relevant 8-K filings** — SEC EDGAR's per-filing `items` field (e.g.
   `"2.02,9.01"`) is already present in the submissions JSON's `recent` block
   (confirmed live 2026-09-17 against real AAPL data — no filing-body parsing needed to
   know which Items triggered a given 8-K, closing a real gap the source handoff left
   as an open question).
3. **Guidance / management-commentary web search** — reuses `news_search.py`'s exact
   WebSearch+LLM mechanism with an earnings-focused prompt.

Callable two ways, both reusing the same underlying `mytrader/earnings_watch.py`
functions (confirmed with Shaun 2026-09-17 — this was originally scoped as
report-only, now explicitly both):

- **On-demand**: a new opt-in check, `checks/earnings_deterioration.py`, wired into
  `engine.run_assessment` the same way `news_events`/`insider_selling` are — always on
  via `find.lookup_ticker` (`find --ticker X`).
- **Scheduled**: a new standalone daily VPS timer (own report, own WhatsApp+toast
  alerting, own dedup state) — modeled on Goat Insider Scan, **holdings only**, never
  wired into `my-trader`'s own Monitor loop (cost reasoning in `checks/news_events.py`'s
  module docstring — Monitor's loop re-checks 50+ rows/day, this needs an LLM+WebSearch
  call per holding, so it stays a separate, cheaper-scoped job like Cash-Value Scan /
  Goat Insider Scan / AI-Resistant Moat Scan already are).

Advisor notes only — surfaces evidence, never a sell verdict (SOUL.md).

## User Story

As Shaun (advisor-mode Second Brain user)
I want a daily early-warning check on my actual holdings for signs that a company's
earnings are starting to deteriorate — analyst estimates trending down, an
earnings-relevant SEC 8-K, or guidance/KPI commentary suggesting a slowdown
So that I have a reason to look closer *before* the next quarterly report confirms a
miss, not just after.

## Problem Statement

No existing check reads forward-looking earnings expectations. `checks/balance_sheet.py`/
`dividend.py`/`valuation.py` are point-in-time fundamentals; `news_events.py` catches
live catalysts (M&A, lawsuits, credit downgrades) but not a slow, un-catalyzed drift in
what analysts expect a company to earn. `TickerData.calendar` already fetches
next-earnings-date + estimate avg/low/high into every assessment but nothing reads it;
`yfinance`'s richer `eps_trend`/`eps_revisions` accessors aren't used anywhere in this
codebase at all.

## Solution Statement

Add `mytrader/earnings_watch.py` with three signal-fetch functions (estimate trend,
8-K filings, guidance search), each with its own new DB table for
history/cache/dedup. Wire them into engine.py as one new opt-in check
(`checks/earnings_deterioration.py`, mirrors the `news_events`/`insider_selling`
one-CheckResult-with-itemized-`.data`-signals shape `opportunity.py` already
established) for Find, and into a new standalone `earnings_watch.run_earnings_watch()`
orchestrator + `scan-earnings-watch` CLI subcommand + systemd timer for the daily
scheduled job (own report, own alerting — not routed through Monitor's
`alert_history` reconcile except for the two state-like signals that fit it).

## Feature Metadata

**Feature Type**: New Capability
**Estimated Complexity**: High (new module, new check, 3 new DB table groups, a
same-package circular-import fix, new CLI command, new systemd timer, docs updates)
**Primary Systems Affected**: `investments/my-trader/mytrader/` (new + `engine.py`,
`db.py`, `config.py`, `main.py`, `sec_filings.py`, `news_search.py` extended),
`investments/goat/goat/config.py` (re-export only, see Phase 0), `investments/TOOLS.md`,
`scripts/deploy.ps1`, `scripts/systemd/`
**Dependencies**: none new — reuses `yfinance` (already pinned `>=0.2.40`, confirmed
live at 1.5.1), `sdk_compat` (already wired), SEC EDGAR (already integrated via
`sec_filings.py`)

---

## Decisions confirmed with Shaun (2026-09-17) — do not re-litigate these

1. **Callable both ways**: opt-in Find check AND a standalone scheduled daily job
   (see Feature Description above) — the handoff's "TBD" open question #3 is resolved.
2. **Holdings only, never watchlist** — Shaun explicitly reconfirmed this scope; the
   standalone daily job's `run_earnings_watch()` must only iterate
   `db.get_all_holdings(conn)`.
3. **Per-signal visibility, one CheckResult** — not 3 separate entries in
   `engine.run_assessment`'s check list. Mirrors `checks/opportunity.py`'s own
   established pattern exactly: one `CheckResult` whose `.verdict` is the aggregate
   (flag if any sub-signal flags) and whose `.detail`/`.data["signals"]` itemizes each
   sub-signal by name — see `opportunity.py`'s `reasons` list +
   `(N independent signals)` suffix for the exact style to mirror. This resolves the
   handoff's open question #3 in spirit (Shaun can see which signal fired) without
   adding 3 new top-level check names to every `run_assessment` call site and test.
4. **Re-alert cadence**: reuse the existing `alert_history` flag→ok→flag reconcile
   (via `monitor.reconcile_flag_alerts`, promoted to a shared function — Phase 2) for
   the two *state-like* signals (estimate trend, guidance search). The 8-K signal is a
   discrete per-filing event, not a continuous state, so it gets its own
   `earnings_watch_8k_seen` dedup table instead — a new accession number is always a
   new alert, matching Goat Insider Scan / Superinvestor Filings' own `_seen`-table
   precedent, not Monitor's reconcile pattern. This simplifies the handoff's open
   question #4 (no new "second bigger threshold" mechanism needed).
5. **ASX 8-K-equivalent (`asx_announcements.py`) leg — deferred.** Checked
   `investments/my-trader/holdings.md` live: every ASX-listed row (`ETPMAG.AX`,
   `GOLD.AX`, `GXLD.AX`, `PMGOLD.AX`, `URNM.AX`, `OOO.AX`) is a commodity ETF/trust with
   no earnings — zero current holdings would benefit. Not built in this plan; flagged
   in NOTES as a future add via the same module this codebase already has.
6. **Industry-context signal (handoff's signal #3) — included, but read-only/context
   only, never a gate by itself.** Requires a real fix first: `GOAT_INDUSTRY_ETFS`
   currently lives in `investments/goat/goat/config.py`, and `goat` already depends on
   `my-trader` (one-way workspace dependency, confirmed live — `goat/pyproject.toml`
   declares `my-trader = { workspace = true }`; `my-trader` declares no dependency on
   `goat`). `earnings_watch.py` importing anything from `goat` would create a circular
   workspace dependency. **Phase 0 below moves just the config dict (not the ranking
   functions) into `mytrader/config.py`**, mirroring the exact precedent already
   documented in `mytrader/config.py` for `OPENINSIDER_BASE_URL`/`OPENINSIDER_USER_AGENT`
   ("moved here from goat/goat/config.py 2026-08-19 ... this was the correct import
   direction"). This is a **smaller, safer migration than moving the whole
   `industry_rotation.py` ranking module** — see Phase 0's Gotcha for why.
7. **Cost sanity-checked** — live `holdings.md` has 16 rows; 7 are ETFs/commodity
   trusts (no earnings, degrade to "unknown" gracefully — see Phase 3's Gotcha) leaving
   **9 real operating-company holdings** (AG, LLY, LULU, LYV, NVDA, PDD, SOFI, UBER, V).
   Daily job cost: 9 WebSearch+LLM guidance calls + 9 cheap `yfinance` estimate fetches
   + 8-K summarization only for *newly filed* relevant 8-Ks (intermittent, not
   per-holding-per-day) — comfortably inside the cost envelope every other opt-in
   LLM+WebSearch check in this codebase already accepts.
8. **Schedule slot: 23:55 UTC** (after Hated Industries' 23:50, before the next day's
   02:35 Superinvestor EDGAR leg) — own timer, `second-brain-mytrader-earnings-watch.timer`.
9. **Thresholds ship with best-guess defaults, tune after real data accumulates** —
   same "ship then tune" precedent as Cash-Value Scan's `CASH_VALUE_RATIO_THRESHOLD`
   (0.80→0.50) and every macro threshold in `config.py`. The estimate-revision trend
   specifically has **no history to backtest against on day one** (this tool is the
   first thing to start recording it) — this is expected, not a gap to close now.

---

## CONTEXT REFERENCES

### Relevant Codebase Files — READ THESE BEFORE IMPLEMENTING

- `investments/my-trader/mytrader/sec_filings.py` (whole file, esp. lines 251-289
  `recent_filings_of_types`, lines 411-426 `extract_sections`/`_extract_sections`
  dispatch, lines 442-457 `_summarize_sections`) — the exact fetch/cache/summarize
  shape to mirror for the 8-K signal. `recent_filings_of_types` needs one **additive**
  field added to its returned dict (`items`) — do not change its existing keys, it's
  shared with `investments/superinvestor-filings/superinvestor_filings/edgar_monitor.py`.
- `investments/my-trader/mytrader/news_search.py` (whole file) — the exact
  WebSearch+LLM+TTL-cache shape to mirror for the guidance-search signal. Add a
  sibling function here (`get_earnings_guidance_for_ticker`), don't create a new module
  — this file's whole purpose is "live search for checks", the guidance search is the
  same job with a different prompt.
- `investments/my-trader/mytrader/checks/news_events.py` (whole file) — the
  Find-only opt-in check shape (`CheckResult` return, `conn is None` guard) AND its
  module docstring's cost reasoning (why an LLM+WebSearch-per-ticker check must never
  be unconditional in Monitor's loop) — cite this same reasoning for why the daily
  Earnings Watch job is its own separate scheduled job, not folded into `monitor.py`.
- `investments/my-trader/mytrader/checks/opportunity.py` (whole file) — the exact
  "one CheckResult, itemized `.data`/`.detail` with multiple named sub-signals, `(N
  independent signals)` suffix" pattern `checks/earnings_deterioration.py` must mirror
  (see Decision #3 above). Lines 126-165 are the concrete shape to copy.
- `investments/my-trader/mytrader/engine.py` (whole file) — `run_assessment`'s
  `include_news_events`/`include_insider_selling` opt-in param shape (lines 95-165) is
  the exact template for the new `include_earnings_watch` param; note `other_checks`
  (not appended after, like `principles_fit`) is where the new check must go so it
  participates in `opportunity.py`'s risk-flag gate — see line 151-158.
- `investments/my-trader/mytrader/find.py` (whole file) — `lookup_ticker`'s
  always-on opt-in wiring (lines 10-18) — the new check goes here the same way.
- `investments/my-trader/mytrader/monitor.py` (lines 55-73 `_reconcile_alerts`) —
  promote this to a public, reusable function (Phase 2) so the daily Earnings Watch
  job can alert-dedup the estimate-trend and guidance signals the same way Monitor
  does for its own checks.
- `investments/my-trader/mytrader/db.py` (whole file, esp. lines 35-153
  `init_mytrader_tables`, lines 353-390 `alert_history` CRUD, lines 456-497
  `sec_filing_cache`/`asx_announcement_cache` CRUD as the pattern to mirror for the new
  tables) — add new tables here, follow the exact `INSERT OR REPLACE` /
  cached-row-shape conventions already used.
- `investments/my-trader/mytrader/config.py` (whole file — it's long, that's normal
  for this module; read it fully once for the constant-naming/comment style, don't
  skim) — every new constant needs a comment in this file's exact style (what it does +
  why this starting value, citing a source or "best-guess default, ship then tune").
- `investments/my-trader/mytrader/main.py` (whole file) — CLI subcommand +
  `dispatch` dict wiring pattern; mirror `cmd_cash_value_scan`/`cmd_monitor`'s exact
  shape (open conn, run, write report, print one-line summary) for `cmd_scan_earnings_watch`.
- `investments/goat/goat/config.py` (lines 150-186, the `GOAT_INDUSTRY_ETFS` dict +
  `GOAT_INDUSTRY_HISTORY_LOOKBACK_DAYS`/`GOAT_INDUSTRY_RANK_WINDOW_TRADING_DAYS`) and
  `investments/goat/goat/industry_rotation.py` (whole file, only 49 lines) — the exact
  block to migrate in Phase 0, and the function that must be **left in place, untouched**
  (see Phase 0 Gotcha).
- `investments/goat/goat/price_history.py` (whole file, 35 lines) —
  `fetch_close_history`'s exact tries-`.AX`-fallback shape; the industry-context
  signal needs a tiny private copy of this logic inside `mytrader/`, not an import
  from `goat` (see Decision #6/Phase 0).
- `investments/my-trader/mytrader/market_data.py` (lines 39-49 `_looks_valid`, lines
  71-83 `fetch_ticker_data`) — reuse `fetch_ticker_data(ticker).info.get("quoteType")`
  for the natural ETF-degradation path (Decision/Gotcha in Phase 3 — do NOT add a
  special-case ETF branch, let empty `yfinance` estimate DataFrames degrade naturally,
  matching how `valuation.py`/`dividend.py` already handle ETFs with no PE/dividend).
- `investments/my-trader/mytrader/tests/conftest.py` (whole file) — the
  autouse-fixture pattern that stubs every real network/LLM call globally so the full
  test suite never hits the network by default. **New autouse fixtures are required**
  for this feature's 3 new real-I/O boundaries (Phase 5) — skipping this will make
  `pytest` slow/flaky/network-dependent for every future contributor, exactly the bug
  class this file's own docstrings describe having already been bitten by twice.
- `investments/my-trader/mytrader/tests/test_engine.py` (whole file, esp. lines
  8-22 `test_run_assessment_includes_all_ten_checks` and lines 225-250 the
  `include_news_events`/`include_insider_selling` opt-in tests) — the new
  `include_earnings_watch` opt-in must NOT change the default (no-opt-in) check count
  of 12; mirror lines 225-236's exact test shape for the new opt-in test.
- `investments/my-trader/mytrader/tests/test_find.py` (lines 21-36) —
  `test_lookup_ticker_opts_in_to_principles_fit_and_news_events` asserts the exact
  kwargs `find.lookup_ticker` passes to `engine.run_assessment`; this test's fake
  `_fake_run_assessment` signature **must be updated** to also accept/capture
  `include_earnings_watch` or it will raise `TypeError` once `find.py` passes that
  kwarg — a mechanical one-line fixture-signature update, not a design question.
- `investments/my-trader/mytrader/tests/test_sec_filings.py` (whole file) — the
  exact `monkeypatch`-based test style (fake SEC JSON dicts, `_FakeSearchResponse`) to
  mirror for the new 8-K tests.
- `investments/my-trader/mytrader/tests/test_checks_news_events.py` and
  `tests/test_checks_insider_selling.py` (both whole files, short) — the exact
  `checks/*.py` unit-test shape (verdict assertions via `monkeypatch` of the
  underlying fetch function) to mirror for `test_checks_earnings_deterioration.py`.
- `investments/my-trader/mytrader/holdings.md` — the real current holdings this
  feature will run against; re-read at manual-validation time since it changes.
- `investments/TOOLS.md` — update its "Daily Read" table, "Automated (scheduled)"
  table, and "Manual / on-demand only" table (see Phase 7).
- `scripts/systemd/second-brain-goat-insider-scan.service` /
  `.timer` — the exact systemd unit shape to copy (Phase 7).
- `scripts/deploy.ps1` (lines 17-31 `$TIMERS`) — add the new timer name here so
  deploys stop/start it correctly (Phase 7).

### New Files to Create

- `investments/my-trader/mytrader/earnings_watch.py` — the 3 signal-fetch functions +
  `run_earnings_watch()` orchestrator + `render_earnings_watch_report()`.
- `investments/my-trader/mytrader/checks/earnings_deterioration.py` — the Find/Monitor
  opt-in `CheckResult` wrapper.
- `investments/my-trader/mytrader/tests/test_earnings_watch.py` — unit tests for the
  module's fetch/trend/orchestrator functions.
- `investments/my-trader/mytrader/tests/test_checks_earnings_deterioration.py` — unit
  tests for the check wrapper.
- `scripts/systemd/second-brain-mytrader-earnings-watch.service` +
  `second-brain-mytrader-earnings-watch.timer`.

### Patterns to Follow

**Graceful degradation, never raise** — every fetch function in this codebase
(`sec_filings.py`, `asx_announcements.py`, `news_search.py`, `market_data.py`) wraps
its real I/O in `try/except Exception: return None`, and every orchestrator treats
`None` as "unavailable this run", never crashes. Mirror this exactly for all 3 new
signal-fetch functions.

**`CheckResult` verdicts**: `"ok" | "flag" | "info" | "unknown"` (`checks/__init__.py`).
`"unknown"` = data unavailable this run (network/LLM failure, or genuinely
not-applicable like an ETF with no earnings) — never conflate with `"ok"` (a real
"nothing wrong" read).

**Config constant comment style** — every threshold in `config.py` states what it
does, what value it's set to, and *why* (a cited source, a live-confirmed reading, or
explicitly "best-guess default, ship then tune" if no source exists). Copy this
exactly, don't add a bare number.

**Stale-but-usable cache fallback** — `sec_filings.get_filing_summaries_for_ticker`
and `news_search.get_news_events_for_ticker` both fall back to a stale cached row if a
live fetch fails, rather than returning nothing. Mirror this for the guidance-search
cache.

**Cost-boundary comment** — every LLM+WebSearch check's docstring explicitly states
its cost class and why it's opt-in/Find-only or its own separate scheduled job (see
`checks/news_events.py`'s module docstring). The new check + the new standalone module
both need this same explicit cost-reasoning docstring.

---

## IMPLEMENTATION PLAN

### Phase 0: Circular-import fix (must land first)

`goat` depends on `my-trader` (one-way workspace dependency, confirmed live via
`goat/pyproject.toml`'s `my-trader = { workspace = true }`). The industry-context
signal needs `GOAT_INDUSTRY_ETFS` (currently in `goat/goat/config.py`), and
`mytrader/earnings_watch.py` importing anything from `goat` would create a cycle.

**Tasks:**
- Move `GOAT_INDUSTRY_ETFS`, `GOAT_INDUSTRY_HISTORY_LOOKBACK_DAYS`,
  `GOAT_INDUSTRY_RANK_WINDOW_TRADING_DAYS` (currently
  `investments/goat/goat/config.py` lines ~150-186) into
  `investments/my-trader/mytrader/config.py`, **unrenamed** — mirror the exact
  `OPENINSIDER_BASE_URL`/`OPENINSIDER_USER_AGENT` 2026-08-19 precedent already
  documented in `mytrader/config.py` (moved for the identical "wrong import direction"
  reason, kept the same names).
- In `investments/goat/goat/config.py`, replace the moved block with:
  `from mytrader.config import GOAT_INDUSTRY_ETFS, GOAT_INDUSTRY_HISTORY_LOOKBACK_DAYS, GOAT_INDUSTRY_RANK_WINDOW_TRADING_DAYS  # noqa: F401  (re-exported for goat callers, moved to mytrader 2026-09 to avoid a circular import from earnings_watch.py)`
  — this preserves `goat.config.GOAT_INDUSTRY_ETFS` as a valid attribute so
  `industry_rotation.py`'s own `from . import config` + `config.GOAT_INDUSTRY_ETFS`
  usage is completely unaffected.
- **Do NOT move `industry_rotation.py`'s `fetch_all_industry_closes`/`rank_industries`
  functions themselves.** They stay in `goat/goat/industry_rotation.py`, untouched.

**GOTCHA**: `investments/goat/goat/tests/test_industry_rotation.py` monkeypatches
`goat_config.GOAT_INDUSTRY_ETFS = fake_etfs` directly (rebinding the module attribute)
and expects `industry_rotation.rank_industries` to see the new value via its own
`from . import config` + `config.GOAT_INDUSTRY_ETFS` lookup — this **only works if
`rank_industries` stays in `goat/industry_rotation.py`** reading `goat.config`'s own
namespace. If a future refactor moves `rank_industries` itself into `mytrader` (not
part of this plan), that test's monkeypatch target must move too — flagging this so
nobody "helpfully" does that half-migration later and silently breaks the test.

**VALIDATE**:
```
uv run --directory investments/goat pytest goat/tests/test_industry_rotation.py -v
uv run --directory investments/goat python -c "from goat import config; print(config.GOAT_INDUSTRY_ETFS['SMH'])"
```

### Phase 1: DB schema + config constants

**Tasks:**
- `mytrader/db.py`'s `init_mytrader_tables`: add 2 new tables (mirror the exact
  `CREATE TABLE IF NOT EXISTS` style already there):
  - `earnings_estimate_history` — `id INTEGER PRIMARY KEY AUTOINCREMENT, ticker TEXT
    NOT NULL, date TEXT NOT NULL, eps_estimate_avg REAL, revenue_estimate_avg REAL,
    revisions_up_30d INTEGER, revisions_down_30d INTEGER, recorded_at TEXT NOT NULL,
    UNIQUE(ticker, date)` — one row per ticker per day, `INSERT OR REPLACE` on rerun
    (mirror `record_price_snapshot`'s exact idiom, `db.py` lines 541-554).
  - `earnings_watch_8k_seen` — `ticker TEXT NOT NULL, accession_number TEXT NOT NULL,
    items TEXT NOT NULL, filing_date TEXT NOT NULL, summary TEXT, first_seen_at TEXT
    NOT NULL, PRIMARY KEY (ticker, accession_number)`.
  - `earnings_guidance_cache` — same shape as `news_events_cache` exactly (`ticker
    TEXT PRIMARY KEY, verdict TEXT NOT NULL, detail TEXT NOT NULL, fetched_at TEXT NOT
    NULL`).
- Add matching CRUD functions to `db.py`, mirroring the exact
  `get_cached_news_events`/`upsert_news_events_cache` pair (lines 500-514) and
  `get_cached_filing_summary`/`upsert_filing_summary_cache` pair (lines 456-475):
  `record_estimate_snapshot`, `get_estimate_history` (ordered by date, optionally
  windowed), `get_cached_earnings_8k`, `upsert_earnings_8k_seen`,
  `get_cached_earnings_guidance`, `upsert_earnings_guidance_cache`.
- `mytrader/config.py`: add (with full comment-style justification per the Patterns
  section above):
  - `EARNINGS_WATCH_REPORT_PATH = MY_TRADER_DIR / "earnings-watch-report.md"`
  - `EARNINGS_WATCH_8K_LOOKBACK_DAYS = 90` — Find's one-shot lookback window (no
    persisted state at Find time, same reasoning as `INSIDER_SELLING_LOOKBACK_DAYS`
    being wider than Goat's own incremental-poll window).
  - `EARNINGS_WATCH_8K_ITEM_ALLOWLIST = frozenset({"2.02", "2.05", "2.06", "1.01", "1.02", "7.01"})`
    — cite the handoff's own Item-code research (Results of Operations,
    restructuring/impairment, material agreement entered/terminated, Reg FD).
  - `EARNINGS_WATCH_TREND_WINDOW_DAYS = 30` — rolling window for the estimate-trend
    read.
  - `EARNINGS_WATCH_TREND_MIN_DATAPOINTS = 5` — minimum recorded daily snapshots
    before the trend check will flag anything (this tool starts with zero history on
    day one — must degrade to "insufficient history" for the first ~5 days, not
    silently flag on noise from 1-2 data points).
  - `EARNINGS_WATCH_TREND_FLAG_PCT = 3.0` — best-guess default (no history exists yet
    to derive this from, per Decision #9 — ship, then tune against real accumulated
    history the same way `CASH_VALUE_RATIO_THRESHOLD` was tuned after its first run).
  - `EARNINGS_WATCH_GUIDANCE_CACHE_HOURS = 20.0` — mirror `NEWS_EVENTS_CACHE_HOURS`
    exactly (same reasoning: no version identifier to key off, time-based TTL).
  - `EARNINGS_WATCH_SUMMARY_MODEL = "sonnet"` — mirror
    `SEC_FILING_SUMMARY_MODEL`/`NEWS_EVENTS_SUMMARY_MODEL`'s already-locked-in tier.

**VALIDATE**:
```
uv run --directory investments/my-trader python -c "from mytrader.db import init_mytrader_tables; from scripts.db import get_connection, init_db; init_db('/tmp/t.db'); c=get_connection('/tmp/t.db'); init_mytrader_tables(c); print([r['name'] for r in c.execute('SELECT name FROM sqlite_master WHERE type=\"table\"')])"
```
(confirm the 3 new tables appear; delete the scratch `/tmp/t.db` after)

### Phase 2: `sec_filings.py` extension (8-K support) + `monitor.py` alert-reconcile promotion

**Tasks:**
- `sec_filings.py`'s `recent_filings_of_types` (lines 251-289): add one **additive**
  key to each returned dict — `"items": recent.get("items", [])[i] if i < len(recent.get("items", [])) else ""`
  — confirmed live 2026-09-17 that SEC's submissions JSON already carries this field
  for 8-Ks (comma-separated Item codes, e.g. `"2.02,9.01"`) directly in the columnar
  `recent` block, no filing-body parsing needed. Do not change any existing key —
  `investments/superinvestor-filings/superinvestor_filings/edgar_monitor.py` also
  calls this function and must be unaffected.
- `monitor.py`: rename `_reconcile_alerts` (lines 55-73) to a public
  `reconcile_flag_alerts` (keep its exact signature and body), update its own two call
  sites (`_process_row`, `run_monitor`'s macro-checks call) to the new name. This is a
  pure rename + one new caller (`earnings_watch.py`, Phase 3) — no behavior change.

**GOTCHA**: `sec_filings.SEC_FILING_TYPES` (`config.py`) is `("10-K", "10-Q", "DEF
14A")` and is used by `get_filing_summaries_for_ticker`'s "latest of each type" logic —
**do not add `"8-K"` to that tuple**. 8-Ks need "every NEW one since last seen", not
"latest one", which is a structurally different query (`recent_filings_of_types`, not
`latest_filing_entry`) — this is why the 8-K fetch is a new function in
`earnings_watch.py`, not a change to `get_filing_summaries_for_ticker`.

**VALIDATE**:
```
uv run --directory investments/my-trader pytest mytrader/tests/test_sec_filings.py -v
uv run --directory investments/my-trader pytest mytrader/tests/test_monitor.py -v
```

### Phase 3: `mytrader/earnings_watch.py` — the 3 signal functions + orchestrator

**Tasks:**
- `fetch_estimate_snapshot(ticker: str) -> dict | None` — `yfinance.Ticker(ticker)`'s
  `.eps_trend`, `.earnings_estimate`, `.revenue_estimate`, `.eps_revisions`, all
  indexed by `period` (`"0q"`, `"+1q"`, `"0y"`, `"+1y"`) — use `"0y"` (current fiscal
  year) as the tracked period, not `"0q"` (too noisy quarter-to-quarter for a "genuine
  drift" read — document this choice in the module docstring as a v1 simplification,
  `"0q"` tracking is a clean future extension if `"0y"` proves too slow-moving).
  **GOTCHA (real, confirmed live)**: `eps_revisions`' columns are
  `upLast7days`/`upLast30days`/`downLast30days`/`downLast7Days` — note the
  **inconsistent capital-D in `downLast7Days`** vs. lowercase everywhere else; hardcode
  the exact strings, don't derive them programmatically. Return `None` if `.eps_trend`
  is empty or lacks a `"0y"` row (mirrors `market_data.py`'s empty-DataFrame
  degradation).
- `record_estimate_snapshot(conn, ticker, snapshot, date_str)` — `INSERT OR REPLACE`
  into `earnings_estimate_history`, mirroring `db.record_price_snapshot`'s exact
  idiom.
- `compute_estimate_trend(conn, ticker) -> dict` — reads
  `db.get_estimate_history(conn, ticker)` filtered to the last
  `EARNINGS_WATCH_TREND_WINDOW_DAYS` days. Returns
  `{"verdict": "unknown", "detail": "..."}`  if fewer than
  `EARNINGS_WATCH_TREND_MIN_DATAPOINTS` rows exist yet (expected for the first ~week
  after this ships — not a bug). Otherwise compares earliest-in-window vs.
  latest-in-window `eps_estimate_avg`; flags if the cumulative decline meets/exceeds
  `EARNINGS_WATCH_TREND_FLAG_PCT`. Note `revisions_down_30d > revisions_up_30d` as
  corroborating context in the detail text (not a separate gate).
- `fetch_new_earnings_8ks(ticker, conn, *, since: date) -> list[dict] | None` —
  `sec_filings.get_cik` → `sec_filings.fetch_filing_index` →
  `sec_filings.recent_filings_of_types(index, {"8-K"}, since)` (now carrying `items`,
  Phase 2) → filter to filings whose comma-split `items` intersect
  `config.EARNINGS_WATCH_8K_ITEM_ALLOWLIST`. For each match not already in
  `earnings_watch_8k_seen` (by accession number): fetch the document
  (`sec_filings.fetch_filing_document`), `sec_filings.strip_html` it (reuse directly —
  **do not** route through `sec_filings.extract_sections`, which has no `"8-K"`
  branch and doesn't need one: an 8-K's whole body IS the disclosure, there's no need
  to hunt an "Item N" section within it the way a 10-K needs), truncate to
  `config.SEC_MAX_SECTION_CHARS`, and summarize via a new prompt (mirror
  `sec_filings._summarize_sections`'s exact `sdk_compat.run_text` call shape, new
  model constant `EARNINGS_WATCH_SUMMARY_MODEL`). Persist via
  `db.upsert_earnings_8k_seen`. Returns the full list of matches in the window (both
  already-seen and newly-seen — Find has no "new" concept, mirrors
  `insider_selling.py`'s "every qualifying sale in the window is reported regardless"
  precedent) with a `"new_this_run"` bool per row for the daily job's alerting to key
  off.
- `news_search.py` addition (not a new module): `get_earnings_guidance_for_ticker(ticker,
  conn) -> dict | None` — copy `get_news_events_for_ticker`'s exact TTL-cache shape
  (lines 100-123) against the new `earnings_guidance_cache` table
  (`config.EARNINGS_WATCH_GUIDANCE_CACHE_HOURS`), with a new `_EARNINGS_GUIDANCE_PROMPT`
  asking about: lowered guidance, cut outlook, missed estimates, investor-day/
  conference commentary about demand/margin/growth deterioration, and any published
  monthly/weekly operating metrics showing a slowdown (same-store sales, subscriber
  counts, GMV, traffic) — folding the handoff's signal #5 into this same single
  WebSearch call rather than a second one (handoff's own recommendation, keeps this to
  one LLM/search call per holding/day). Same JSON response shape
  (`{"material": bool, "detail": str, "findings": [...]}`) and `_parse_json` reuse.
- `fetch_industry_context(ticker, data) -> dict | None` — read-only, context-only
  (never gates alone, per Decision #6). Maps `data.info.get("industry")` (yfinance's
  industry string) against `config.GOAT_INDUSTRY_ETFS`'s values (reverse lookup: build
  `{label: etf_ticker for etf_ticker, label in config.GOAT_INDUSTRY_ETFS.items()}`
  once). If no match, return `None` (many industries have no dedicated ETF in that
  39-name map — expected, not an error). If matched, fetch that single ETF's own
  recent return over `config.GOAT_INDUSTRY_RANK_WINDOW_TRADING_DAYS` trading days via
  a small private `_fetch_close_history` copied from
  `goat/goat/price_history.py:fetch_close_history` (11 lines — a private copy, not an
  import, per Phase 0's Decision #6 reasoning: don't import `goat` from `my-trader`).
  Returns `{"industry_label": ..., "etf_ticker": ..., "return_pct": ..., "rising": bool}`.
- `run_earnings_watch(conn) -> dict` — orchestrator, **holdings only**
  (`db.get_all_holdings(conn)`, per Decision #2). Skip MLPs
  (`mlp_filter.detect(data.info)`, mirror `engine.run_assessment`'s exact MLP-skip
  shape). For each remaining holding: fetch+record estimate snapshot, compute trend,
  fetch 8-Ks since `EARNINGS_WATCH_8K_LOOKBACK_DAYS` ago, fetch guidance search, fetch
  industry context. Alert-dedup: estimate-trend and guidance signals go through
  `monitor.reconcile_flag_alerts(ticker, "holdings", [trend_check_result,
  guidance_check_result], conn)` (Phase 2's promoted function — this also means these
  alerts show up in `my-trader`'s own Monitor "Open Alerts" section automatically,
  since both write to the same `alert_history` table keyed on `source_table="holdings"`
  — call this out as an intentional bonus, not a bug, when validating). 8-K signal
  alerts directly off `"new_this_run"` rows, no `alert_history` involvement (Decision
  #4). Returns a dict shaped for the renderer: per-holding results + a flat
  `new_alerts` list (mirrors `monitor.run_monitor`'s own return shape) for
  `maybe_notify`.
- `render_earnings_watch_report(result) -> str` — mirror `monitor.render_report`'s
  markdown structure (header, per-holding sections, "New Alerts This Run" section).
  Per holding: if ALL signals returned `"unknown"`/no data (the natural ETF/commodity-
  trust degradation path, e.g. `GOLD.AX`/`PMGOLD.AX`/`SILJ`), collapse to a single
  one-line "No earnings data available (fund/commodity instrument)" row instead of 3
  verbose "unknown" lines — mirror `monitor.py`'s own `_NOISE_CHECKS`/`_is_noise_check`
  boilerplate-suppression philosophy (lines 213-223), don't invent a new pattern for
  this. Explicitly note "Not covered: alternative data (app downloads, web traffic,
  credit-card spend) — no free source in this toolset" once at the top of the report,
  not per-holding.
- `write_report(result)` / `maybe_notify(result)` — mirror `monitor.py`'s exact
  pair (lines 357-376): write to `config.EARNINGS_WATCH_REPORT_PATH`, toast+WhatsApp
  only when `new_alerts` is non-empty.

**GOTCHA**: `market_data.cached_session()` (`market_data.py` lines 24-36) should wrap
`run_earnings_watch`'s per-holding loop the same way `monitor.run_monitor` does (`with
market_data.cached_session():`) — holdings iteration re-fetches `TickerData` for the
industry-context signal's `.info.get("industry")` lookup, and Monitor's own
O(n²)-avoidance reasoning applies identically here.

**VALIDATE** (manual, against real data — these hit real network/LLM, run once by
hand, not in the automated test suite):
```
uv run --directory investments/my-trader python -c "from mytrader.earnings_watch import fetch_estimate_snapshot; print(fetch_estimate_snapshot('AAPL'))"
uv run --directory investments/my-trader python -c "from mytrader.earnings_watch import fetch_new_earnings_8ks; from datetime import date, timedelta; import sqlite3; from mytrader.db import init_mytrader_tables; from scripts.db import get_connection, init_db; init_db('/tmp/t2.db'); c=get_connection('/tmp/t2.db'); init_mytrader_tables(c); print(fetch_new_earnings_8ks('AAPL', c, since=date.today()-timedelta(days=365)))"
```

### Phase 4: `checks/earnings_deterioration.py` + `engine.py`/`find.py` wiring

**Tasks:**
- `checks/earnings_deterioration.py`: `check(ticker, data, conn) -> CheckResult`.
  Calls all 3 signal functions (estimate trend via
  `earnings_watch.compute_estimate_trend` — note Find has no daily snapshot history to
  read either on a ticker it doesn't hold/track yet, so this will usually read
  "insufficient history" for a fresh Find lookup on a ticker with no
  `earnings_estimate_history` rows; that's correct, not a bug — the trend signal is
  inherently a Monitor/daily-job signal more than a Find one, but stays wired into
  Find for consistency and because a *held* ticker Shaun's already been running the
  daily job against WILL have history), `earnings_watch.fetch_new_earnings_8ks` (with
  `since=today - EARNINGS_WATCH_8K_LOOKBACK_DAYS`), `news_search.get_earnings_guidance_for_ticker`.
  Aggregate verdict: `"flag"` if any sub-signal flagged, `"unknown"` if ALL sub-signals
  are unknown/no-data (mirrors the natural ETF-degradation path — no special-case ETF
  branch, see Patterns section), else `"ok"`. `.detail` joins itemized findings
  semicolon-separated with a `(N independent signals)` suffix when >1 fires — copy
  `opportunity.py`'s exact style (lines 160-165). `.data["signals"]` carries the full
  structured per-signal dict for the daily report renderer's reuse.
- `engine.py`: add `include_earnings_watch: bool = False` param to `run_assessment`
  (mirror `include_news_events`'s exact placement/docstring style, lines 106-109). Add
  `if include_earnings_watch: other_checks.append(earnings_deterioration.check(normalized, data, conn))`
  inside the `other_checks` list construction (before `opportunity.check` is called,
  same placement as `news_events`/`insider_selling` — line ~156-158) so a flag here
  participates in `opportunity.py`'s existing risk-flag gate.
- `find.py`: `lookup_ticker` — add `include_earnings_watch=True` to its
  `engine.run_assessment` call (mirrors the other 3 always-on Find opt-ins exactly,
  line 15-18).

**VALIDATE**:
```
uv run --directory investments/my-trader python -c "from mytrader.checks import earnings_deterioration; print(earnings_deterioration.check.__module__)"
```

### Phase 5: Tests

**Tasks:**
- `tests/conftest.py`: 3 new autouse fixtures, mirroring the exact existing pattern
  (`_no_real_news_events_search` etc., lines 112-120):
  - `_no_real_earnings_estimate_fetch` — stub
    `mytrader.earnings_watch.fetch_estimate_snapshot` to return `None`.
  - `_no_real_earnings_8k_fetch` — stub `mytrader.earnings_watch.fetch_new_earnings_8ks`
    to return `None`.
  - `_no_real_earnings_guidance_search` — stub
    `mytrader.news_search.get_earnings_guidance_for_ticker` to return `None`.
- `tests/test_earnings_watch.py`: unit tests for
  `fetch_estimate_snapshot`/`record_estimate_snapshot`/`compute_estimate_trend`
  (insufficient-history case, declining-trend case, stable case),
  `fetch_new_earnings_8ks` (allowlisted item flags, non-allowlisted item ignored,
  already-seen accession not re-summarized — mirror
  `test_sec_filings.py`'s `test_get_filing_summaries_uses_cache_when_accession_unchanged`
  shape exactly), `fetch_industry_context` (matched industry, unmatched industry
  returns `None`), `render_earnings_watch_report` (ETF/no-data collapse-to-one-line
  case).
- `tests/test_checks_earnings_deterioration.py`: mirror
  `test_checks_news_events.py`'s exact shape — `conn is None`→`unknown`, all-signals-
  unknown→`unknown`, one signal flags→`flag`+itemized detail, no signals fire→`ok`.
- `tests/test_engine.py`: add `test_run_assessment_includes_earnings_watch_when_opted_in`
  mirroring lines 225-236's exact shape (stub
  `mytrader.engine.earnings_deterioration.check`, assert count is 13 — the default 12
  plus one).
- `tests/test_find.py`: **update**
  `test_lookup_ticker_opts_in_to_principles_fit_and_news_events` — `_fake_run_assessment`'s
  signature must add `include_earnings_watch=False` and the test must assert
  `captured["include_earnings_watch"] is True`, or this test will `TypeError` the
  moment `find.py` starts passing that kwarg (mechanical fix, not optional).
- `investments/goat/goat/tests/test_industry_rotation.py`: re-run as-is after Phase
  0 — should pass unchanged (Phase 0's Gotcha explains why). If it fails, Phase 0 was
  done wrong (functions were moved, not just the config dict) — fix by reverting to
  "config dict only" migration, don't patch the test to chase a bad migration.

**VALIDATE**:
```
uv run --directory investments/my-trader pytest mytrader/tests/ -v
uv run --directory investments/goat pytest goat/tests/test_industry_rotation.py -v
```

### Phase 6: CLI subcommand

**Tasks:**
- `main.py`: `cmd_scan_earnings_watch(args)` — mirror `cmd_cash_value_scan`/`cmd_monitor`'s
  exact shape (open conn, `run_earnings_watch`, `write_report`, `maybe_notify`,
  one-line print summary, close conn). Register `scan-earnings-watch` subparser +
  `dispatch` entry.

**VALIDATE**:
```
uv run --directory investments/my-trader python -m mytrader.main scan-earnings-watch
```
(this is the first REAL run against the live shared DB — expect it to actually write
`investments/my-trader/earnings-watch-report.md` and record the first day's estimate
snapshots; run this from the VPS per `investments.db`'s VPS-only rule — see "Manual
Validation" below, do not run this against a local throwaway DB and call it done)

### Phase 7: Deployment + docs

**Tasks:**
- `scripts/systemd/second-brain-mytrader-earnings-watch.service` — copy
  `second-brain-goat-insider-scan.service`'s exact shape, `WorkingDirectory=
  /home/secondbrain/second-brain/investments/my-trader`, `ExecStart=.../python -m
  mytrader.main scan-earnings-watch`, log path `earnings_watch_runs.log`.
- `scripts/systemd/second-brain-mytrader-earnings-watch.timer` — `OnCalendar=*-*-*
  23:55:00 UTC` (Decision #8), `Persistent=true`.
- `scripts/deploy.ps1`: add `"second-brain-mytrader-earnings-watch.timer"` to
  `$TIMERS` (line ~30).
- `investments/TOOLS.md`: add a row to "Daily Read", a row to "Automated
  (scheduled)" (mirror the Goat Insider Scan row's exact column shape), and a row to
  "Manual / on-demand only" (`-Package my-trader -Command "scan-earnings-watch"`).

**VALIDATE** (on the VPS, after `scp`/deploy):
```
sudo systemctl status second-brain-mytrader-earnings-watch.timer
sudo systemctl start second-brain-mytrader-earnings-watch.service && journalctl -u second-brain-mytrader-earnings-watch.service -n 50
```

---

## TESTING STRATEGY

### Unit Tests

Every new fetch/compute function gets a `monkeypatch`-based unit test with fixture
data, no real network/LLM calls (see Phase 5's autouse fixtures). Follow this
codebase's existing convention: test the graceful-degradation path (fetch fails →
`None`/`"unknown"`) as rigorously as the happy path — every existing `checks/*.py` test
file does this and it's caught real bugs before (e.g. `_looks_valid`'s `quoteType`
gotcha in `market_data.py`).

### Integration Tests

`test_engine.py`'s opt-in test (Phase 5) is the integration point that matters most —
confirms the new check participates correctly in `opportunity.py`'s risk-flag gate
through the real `run_assessment` wiring, not just in isolation (mirror
`test_news_events_flag_suppresses_opportunity`'s exact end-to-end shape).

### Edge Cases

- First-ever run: zero rows in `earnings_estimate_history` for every ticker — trend
  signal must degrade to "insufficient history", never flag on 1 data point.
- ETF/commodity-trust holding (`GOLD.AX`, `PMGOLD.AX`, `SILJ`, `OOO.AX`, `URNM.AX`,
  `ETPMAG.AX`, `GXLD.AX`): all 3 signals degrade to no-data naturally (empty
  `yfinance` estimate DataFrames, no CIK match or a CIK match with zero relevant
  filings, guidance search returns nothing material) — report collapses these to one
  line, never 3 verbose "unknown" blocks per fund holding.
- A holding with a genuinely new earnings-relevant 8-K vs. one with only a routine
  8-K (e.g. Item 5.02 officer change) filed in the same window — only the allowlisted
  one should fetch+summarize+alert; the routine one should be silently ignored (not
  even fetched — the `items` filter happens before the document fetch).
- A ticker with no SEC CIK match at all (foreign private issuer, non-US ASX holding) —
  `fetch_new_earnings_8ks` returns `None` (mirrors `sec_filings.get_filing_summaries_for_ticker`'s
  own CIK-miss degradation), not an empty list (distinguish "checked, found nothing"
  from "couldn't check at all").
- Repeat-day run with an unchanged declining trend — must NOT re-alert (via
  `reconcile_flag_alerts`'s existing flag→flag-stays-quiet dedup). A genuinely NEW 8-K
  arriving on day 2 while yesterday's 8-K is still in the lookback window — MUST alert
  (the 8-K signal's own `earnings_watch_8k_seen` dedup, independent of the
  `alert_history` state machine, is exactly why this needed its own table).
- `LLY`'s real holdings.md row (qty `0.0001`, a dust position) — must not error;
  every signal function operates on the ticker/data, not the quantity, so this should
  just work, but worth confirming explicitly since it's a real edge-case row in
  production data.

---

## VALIDATION COMMANDS

### Level 1: Syntax & Style
```
uv run --directory investments/my-trader ruff check mytrader/earnings_watch.py mytrader/checks/earnings_deterioration.py mytrader/sec_filings.py mytrader/news_search.py mytrader/engine.py mytrader/find.py mytrader/db.py mytrader/config.py mytrader/main.py
uv run --directory investments/my-trader mypy mytrader/earnings_watch.py mytrader/checks/earnings_deterioration.py
```

### Level 2: Unit Tests
```
uv run --directory investments/my-trader pytest mytrader/tests/ -v
uv run --directory investments/goat pytest goat/tests/test_industry_rotation.py -v
```

### Level 3: Integration Tests
```
uv run --directory investments/my-trader pytest mytrader/tests/test_engine.py mytrader/tests/test_find.py -v
```

### Level 4: Manual Validation
Run these **on the VPS** (per `investments.db`'s VPS-only rule — see root
`CLAUDE.md`'s Key Paths, "Interactive my-trader/briefs-finance commands run on the
VPS"), via `scripts/invoke_investments.ps1`:
```
.\scripts\invoke_investments.ps1 -Package my-trader -Command "scan-earnings-watch"
.\scripts\invoke_investments.ps1 -Package my-trader -Command "find --ticker NVDA"
```
Confirm: `investments/my-trader/earnings-watch-report.md` is written and readable;
`find --ticker NVDA`'s output includes an `earnings_deterioration` check line; a
second `scan-earnings-watch` run the same day produces zero new alerts (dedup
working); `investments/my-trader/holdings.md`'s ETF rows (`GOLD.AX` etc.) collapse to
one line each in the new report, not 3 verbose "unknown" blocks.

### Level 5: Additional Validation
```
sudo systemctl status second-brain-mytrader-earnings-watch.timer
```

---

## ACCEPTANCE CRITERIA

- [ ] `checks/earnings_deterioration.py` is wired into `find --ticker X` (always on)
- [ ] The daily `scan-earnings-watch` job runs against **holdings only**, never watchlist
- [ ] Estimate-trend signal correctly reports "insufficient history" for the first
      `EARNINGS_WATCH_TREND_MIN_DATAPOINTS` days, never flags on noise
- [ ] 8-K signal only fetches/summarizes filings whose Item codes intersect the
      allowlist; routine 8-Ks are filtered out before any document fetch
- [ ] 8-K alerting never re-alerts an already-seen accession number; a new accession
      always alerts once
- [ ] Guidance-search signal reuses `alert_history` reconcile (flag→ok→flag) via the
      promoted `reconcile_flag_alerts`
- [ ] ETF/commodity-trust holdings degrade gracefully with no special-case branch,
      collapsed to one line in the report
- [ ] `goat/tests/test_industry_rotation.py` passes unchanged after Phase 0
- [ ] No new circular import between `my-trader` and `goat`
- [ ] `pytest mytrader/tests/` passes with zero real network calls (confirm by running
      offline/airplane-mode once, or by checking no test takes >1s)
- [ ] New systemd timer deployed at 23:55 UTC, added to `scripts/deploy.ps1`'s `$TIMERS`
- [ ] `investments/TOOLS.md` updated (3 table rows)

## COMPLETION CHECKLIST

- [ ] All 7 phases completed in order (Phase 0 must land first)
- [ ] Each phase's validation command passed before moving to the next
- [ ] Full `pytest mytrader/tests/` + `goat/tests/test_industry_rotation.py` pass
- [ ] `ruff`/`mypy` clean on all touched/new files
- [ ] Manual VPS validation (Level 4) confirms a real report + real Find output
- [ ] Acceptance criteria all met
- [ ] `investments/TOOLS.md` and `scripts/deploy.ps1` updated

---

## NOTES

- **ASX 8-K-equivalent (`asx_announcements.py` leg) — explicitly deferred**, per
  Decision #5. Easy future add: `asx_announcements.py` already exists and handles the
  PDF-fetch/extract/summarize side; the only new work would be an ASX-side "what
  counts as earnings-relevant" filter analogous to the SEC Item-code allowlist (ASX
  doesn't have Item codes — would need title/keyword matching against announcement
  titles, similar to `ASX_ANNOUNCEMENT_TYPES`'s existing substring-matching approach).
  Revisit if/when Shaun holds an actual ASX-listed operating company (not just
  ETFs/commodity trusts).
- **Estimate-revision trend threshold has zero history to validate against on day
  one** — this is the first thing in the codebase to record this data. Expect to
  revisit `EARNINGS_WATCH_TREND_FLAG_PCT` after 2-4 weeks of real
  `earnings_estimate_history` accumulates, same "ship then tune" arc as
  `CASH_VALUE_RATIO_THRESHOLD`.
- **`"0y"` (current fiscal year) vs `"0q"` (current quarter) estimate tracking** — v1
  tracks only `"0y"` for simplicity (less noisy). If it proves too slow to catch a
  real deterioration early, `"0q"` tracking is a clean, additive follow-up (same table,
  one more column, no schema redesign).
- **Industry-context signal is informational only** — it never gates the aggregate
  verdict by itself (Decision #6). If a holding's industry has no dedicated ETF in the
  39-name `GOAT_INDUSTRY_ETFS` map, this signal is silently `None` — expected for the
  majority of individual holdings, not a gap.
