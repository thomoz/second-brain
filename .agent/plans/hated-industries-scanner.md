# Feature: Hated Industries Scanner

The following plan should be complete, but it's important to validate documentation and
codebase patterns and task sanity before implementing. Pay special attention to naming
of existing utils, types, and models — import from the right files.

## Feature Description

A daily VPS scan that finds industries the market is currently punishing hardest —
severe, still-live price underperformance at the industry level — and layers on two
extra reads that turn "what's down" into "what might be down for reasons that don't
hold up": an LLM web-search call that identifies the dominant negative narrative and
judges whether it plausibly applies industry-wide or is one or two loud names dragging
an index, and a fundamentals-divergence check against a handful of the industry's
largest constituents (did revenue/earnings actually deteriorate, or just the price?).
Purely advisory — no verdict, no ticker staging, no buy/sell language. It surfaces
industries for Shaun to review, and the natural next step for a flagged one is running
its constituent names through my-trader Find or checking the AI-Resistant Moat
Scanner's ranking.

## User Story

As Shaun (advisor-mode Second Brain user, contrarian value/GARP-leaning investor)
I want a daily check that surfaces industries currently out of favor with the market,
along with why and whether the underlying businesses actually got worse
So that I can catch the next SaaS-style overreaction (deep pessimism the market
later massively reversed) while the pessimism is still live, not after the fact

## Problem Statement

Goat's existing industry rotation ranking (`industry_rotation.py`) already ranks all
39 ETF-covered industries by 6-month return, so "what's at the bottom" is technically
visible today — but nothing distinguishes a genuinely-hated industry (severe,
narrative-driven, still-live underperformance) from an industry that's merely lagging
in a normal way, and nothing checks whether the underlying businesses' fundamentals
actually justify the price action. Shaun's own example: SaaS software was broadly sold
off a few months back on fear that AI would cheaply replace it — a narrative that
turned out not to apply evenly across the industry (some names are too deeply embedded
in customer operations for that ROI math to work), and the mispricing on several of
those names has since reversed massively. There is currently no tool that would have
flagged that episode while it was happening.

## Solution Statement

Add a new module `goat/hated_industries_scan.py` that reuses `industry_rotation.py`'s
existing 39-industry-ETF universe and price-history fetch, and layers three checks on
top, gated in sequence so the expensive step only runs on genuine candidates:

1. **Quant severity gate** — bottom-5 of the 39 by 6-month return, AND underperforming
   SPY by a minimum margin on both a 3-month and 6-month window, AND at least a minimum
   drawdown from its 52-week closing high, AND not already showing a sharp recent
   recovery (the "still currently hated, not already reversed" filter).
2. **Narrative classification** — one `sdk_compat.run_text` + WebSearch call per
   industry that clears gate 1 (same mechanism `mytrader/news_search.py` already uses
   for ticker-level news, industry-scoped instead), cached per industry per day. Asks
   for the dominant negative narrative, whether it reads as industry-wide or
   concentrated in one or two large constituents, and — in the same call — the
   industry ETF's 3-5 largest constituent holdings by weight (folding holdings
   resolution into the already-gated WebSearch call instead of maintaining a 39-entry
   static seed table that would need manual upkeep and can't be verified against live
   data the way a WebSearch call can — see NOTES for why this improves on the
   handoff's original "hardcoded seed table" recommendation).
3. **Fundamentals-divergence check** — for the constituent tickers the narrative call
   returned, pull `revenueGrowth`/`earningsGrowth` via the existing yfinance wrapper
   and classify whether the businesses are still growing despite the price collapse
   (divergence = the overreaction signature), still declining (hate may be earned), or
   mixed/insufficient data.

Output is one advisory Markdown report, no ticker staging into `goat_pending_candidates`
(confirmed with Shaun — this tool's job stays separate from the Moat Scanner's and
my-trader Find's ticker-level picks), and a WhatsApp+toast alert only when an industry
**newly** enters the hated set (a small `goat_hated_industries_seen` table tracks this
so a still-hated industry doesn't re-alert every day).

## Feature Metadata

**Feature Type**: New Capability (sibling extension of an existing pattern)
**Estimated Complexity**: Medium — the severity-gate math is a straightforward
extension of already-shipped, already-tested code (`industry_rotation.py`), but the
narrative-classification LLM call and the fundamentals-divergence check are genuinely
new mechanics with no exact prior template in this codebase (closest analogues:
`mytrader/news_search.py` for the WebSearch/cache shape, `ai_resistant_moat_scanner`
for a blended quant+qualitative read).
**Primary Systems Affected**: `investments/goat/` only (`goat/config.py`, new
`goat/hated_industries_scan.py`, `goat/db.py`, `goat/main.py`, tests, `TOOLS.md`).
**Dependencies**: None new — reuses `yfinance` (already a goat/mytrader dependency)
and `sdk_compat`'s WebSearch tool (already used by `mytrader/news_search.py`, no new
paid API).

---

## Decisions Confirmed With Shaun (2026-09-16, this session)

1. **No ticker-level candidate staging.** This tool flags industries only — it does
   **not** write into `goat_pending_candidates` and has no promote/dismiss flow.
   Confirmed explicitly: keeps this tool's job separate from the Moat Scanner's and
   my-trader Find's ticker-level picks. Representative constituent tickers are shown
   in the report as read-only pointers, never stageable.
2. **Top-holdings source: resolved via the same WebSearch call as the narrative
   classification**, not a static seed table (see Solution Statement point 2 and NOTES
   for the reasoning — this was a refinement made during this planning session, not a
   literal re-ask of the handoff's "hardcoded table" framing Shaun had provisionally
   accepted; flagged here so it's visible as an explicit deviation from the handoff
   doc, not a silent one).

---

## CONTEXT REFERENCES

### Relevant Codebase Files — READ THESE BEFORE IMPLEMENTING

- `investments/goat/goat/industry_rotation.py` (all 49 lines) — `fetch_all_industry_closes()`
  and `rank_industries()`, the exact universe/price-history foundation this feature
  extends. Reuse `fetch_all_industry_closes()` as-is; do not re-fetch or re-derive the
  39-ticker universe.
- `investments/goat/goat/config.py` lines 150-194 (`GOAT_INDUSTRY_ETFS`,
  `GOAT_FINVIZ_INDUSTRIES`, `GOAT_INDUSTRY_HISTORY_LOOKBACK_DAYS`,
  `GOAT_INDUSTRY_RANK_WINDOW_TRADING_DAYS`) — the universe and constants to import
  from, not redefine. Lines 43-91 (`GOAT_SECTOR_*` block) and lines 474-508
  (`GOAT_DMA_BREAKOUT_*` block) — the constant-naming/comment-density convention to
  match exactly for the new `GOAT_HATED_*` block (every tunable number gets an inline
  comment stating why that value, citing precedent or "v1/tunable" honestly).
- `investments/goat/goat/dma_breakout_scan.py` (all 276 lines) — **the closest and
  freshest full precedent in this codebase** for "extend goat with a new gated
  discovery scan": `fetch_universe_constituents()`'s ethical-filter-applied
  universe-build shape, `run_dma_breakout_scan()`'s try/except-per-item loop with a
  `market_data.cached_session()` wrapper, and `render_.../write_...` report functions.
  Mirror this file's overall shape for `hated_industries_scan.py`, adapted from
  per-ticker to per-industry.
- `investments/goat/goat/sector_rotation.py` lines 53-113 (`check_sector_breakout`) —
  the sign-flip/cross-detection idiom; not directly reused here (this feature's gate is
  threshold-based, not a cross), but read for the "informational vs. gating" slope
  distinction `dma_breakout_scan.py`'s docstring discusses, since this feature makes a
  similar "informational, not gating" choice for its reversal check (see Task 2).
- `investments/goat/goat/monitor.py` lines 236-256 (`run_sector_scan`) and lines
  314-391 (`run_industry_scan`, `render_industry_ranking_report`,
  `write_industry_ranking_report`) — `render_industry_ranking_report`'s Top-5/Bottom-5/
  full-table/gap-list section shape is the direct template for this feature's own
  report sections (severity table + narrative + fundamentals-divergence per flagged
  industry). Note `run_industry_scan()` takes no `conn` (pure compute) — this
  feature's `run_hated_industries_scan()` DOES need `conn` (the seen-table dedup and
  narrative cache both require DB access), so don't copy the no-conn signature
  reflexively.
- `investments/my-trader/mytrader/news_search.py` (all ~90 lines) — the exact
  WebSearch-call-with-TTL-cache mechanism to copy: `sdk_compat.run_text` with
  `ClaudeAgentOptions(allowed_tools=["WebSearch"], model=...)`, `_parse_json` fence
  stripping, `get_news_events_for_ticker`'s cache-check → call → cache-write →
  stale-fallback-on-failure flow. This feature's `classify_industry_narrative()`
  follows the identical flow, industry-scoped instead of ticker-scoped, with a richer
  JSON schema (narrative + systemic-call + top holdings, not just material/detail).
- `investments/my-trader/mytrader/checks/news_events.py` (module docstring, all 46
  lines) — read in full before writing the narrative prompt. Explains *why* yfinance's
  own `.news` feed was rejected as a data source for this kind of check (generic
  market-recap noise, missed the real story) — the same reasoning applies here; do not
  reach for `Ticker(x).news` as a shortcut instead of the WebSearch pattern. Also
  documents a known limitation (Codex's `web_search` tool sometimes has a
  less-fresh/different index than Claude Code's own `WebSearch` — worth restating in
  this feature's own module docstring as an inherited caveat, not re-litigating it).
- `investments/my-trader/mytrader/config.py` lines ~345-352
  (`NEWS_EVENTS_SUMMARY_MODEL`, `NEWS_EVENTS_CACHE_HOURS`) — the constant-naming
  precedent for this feature's `GOAT_HATED_NARRATIVE_SUMMARY_MODEL` /
  `GOAT_HATED_NARRATIVE_CACHE_HOURS`.
- `investments/my-trader/mytrader/db.py` lines ~127 (`news_events_cache` table), ~541
  (`get_cached_news_events`), ~547 (`upsert_news_events_cache`) — the cache-table CRUD
  shape to mirror for this feature's `goat_hated_industries_narrative_cache` table
  (new, in `goat/db.py` — goat has its own DB module, don't add to `mytrader/db.py`).
- `investments/goat/goat/db.py` lines 15-60 (`init_goat_tables`, existing table
  definitions) — where the two new tables (`goat_hated_industries_seen`,
  `goat_hated_industries_narrative_cache`) get added, inside the same
  `conn.executescript(...)` block. Lines 157-196 (`get_goat_pending_candidate`,
  `insert_goat_pending_candidate`, `delete_goat_pending_candidate`) — CRUD shape to
  mirror (parametrized SQL, `with conn:` for writes, `_now()` helper already defined
  at the top of the file). Lines 224-254 (`insert_goat_insider_filing_seen`,
  `get_recent_insider_filings_seen`) — the closest existing "seen" dedup-table
  precedent (`INSERT OR IGNORE`, returns whether the insert was new) — this feature's
  `goat_hated_industries_seen` needs an upsert (not insert-or-ignore) since
  `last_flagged_at` must update on every re-qualifying day even though `first_flagged_at`
  should not.
- `investments/goat/goat/main.py` lines 120-137 (`cmd_scan_dma_breakout`) — the exact
  command-function shape to mirror: open conn → run scan → close conn → write report →
  `maybe_notify(...)` → print summary. Lines 155-195 (`monitor.py`'s `maybe_notify`) —
  read the full function (not just the excerpt) before calling it; note the
  `candidate_label` parameter must describe *this* feature's candidates (e.g. "newly
  hated industrie(s) flagged"), not a copy-pasted sector/DMA label (see the 2026-08-18
  fix documented in that function's own docstring for why this matters).
- `investments/goat/goat/main.py` — subparser registration + `dispatch` dict pattern
  (search for `"scan-dma-breakout"` — two occurrences, the `add_parser` call and the
  dispatch entry) — mirror both for `"scan-hated-industries"`.
- `investments/goat/goat/market_data.py` — wait, this lives in `mytrader`, not `goat`
  (`investments/my-trader/mytrader/market_data.py`) — `TickerData` dataclass (`.info`
  is the raw yfinance `.info` dict — `revenueGrowth`/`earningsGrowth` are standard
  keys on it, no new fetch code needed), `fetch_ticker_data(ticker)`, and
  `cached_session()` (wrap the fundamentals-divergence loop in this, same reason
  `dma_breakout_scan.py` does — avoids redundant yfinance calls within one run).
- `investments/briefs-finance/scripts/ethical_filter.py` lines 8-19 (`check_ticker`) —
  apply this to the narrative call's returned top-holdings tickers before running the
  fundamentals-divergence check on them (same convention as every other broad-universe
  Goat scan) — return `(excluded, review_reason)`; drop excluded, note review_reason
  in the report the same way `dma_breakout_scan.py` does (see its
  `signal_detail += f"; {c['review_reason']}"` line, adapt the idiom).
- `investments/goat/goat/price_history.py` (all 35 lines) — `fetch_close_history(ticker,
  lookback_days)`, reused as-is both for the 39 industry ETFs (via
  `industry_rotation.fetch_all_industry_closes()`) and for a new direct call to fetch
  `SPY`'s own close history for the relative-underperformance comparison.
- `investments/ai-resistant-moat-scanner/ai_resistant_moat_scanner/qualitative.py` —
  read for the "nullable field, not disclosed → null, never guessed" discipline this
  feature's narrative-classification JSON schema should follow (e.g. `systemic` should
  be `true`/`false`/`null`, not forced to a confident guess when the evidence is thin).
- `investments/goat/goat/tests/conftest.py` lines 29-49 (`_isolate_goat_report_path`) —
  **must add** a `monkeypatch.setattr(goat_config, "GOAT_HATED_REPORT_PATH", tmp_path /
  "hated-industries-report.md")` line here, same as every other Goat report path, or
  any test exercising the new report-writer pollutes the real repo path.
- `investments/goat/goat/tests/test_dma_breakout_scan.py` (all ~270+ lines) — the
  freshest test-fixture-construction pattern in this codebase (`_dates`,
  `_series_with_cross`-style helpers, `_healthy_ticker_data` for a fabricated
  `TickerData`). Mirror this file's structure for `test_hated_industries_scan.py`.
- `investments/goat/goat/tests/test_industry_rotation.py` — the ranking-test pattern
  (`rank_industries` ordering/missing-data-sorts-last) this feature's severity-gate
  tests build on top of.
- `investments/TOOLS.md` lines ~39-83 (Automated + Manual tables) — add rows here as
  part of this feature (hand-maintained file, per its own header).

### New Files to Create

- `investments/goat/goat/hated_industries_scan.py` — severity gate, narrative
  classification, fundamentals-divergence check, orchestrator, report render/write.
- `investments/goat/goat/tests/test_hated_industries_scan.py` — unit tests covering
  the severity gate, seen-table dedup/re-alert logic, and fundamentals-divergence
  classification (narrative-classification's actual WebSearch call is
  monkeypatched/stubbed in tests, same as `news_search.py`'s own test suite stubs
  `_search_news_events` — check `mytrader/tests/test_news_search.py` for the exact
  stubbing pattern before writing this file's narrative tests).
- `investments/goat/hated-industries-report.md` — the generated report itself
  (created by running the new command at least once during Level 4 validation; do not
  hand-author this file's content).

### Relevant Documentation

No external library documentation needed — this feature is built entirely from
patterns already live in this codebase (yfinance via existing wrappers, `sdk_compat`'s
WebSearch tool via existing `mytrader/news_search.py`). No new dependency, no new API
integration.

### Patterns to Follow

**Naming Conventions:** `GOAT_HATED_*` prefix for new config constants (matches
`GOAT_SECTOR_*`/`GOAT_INDUSTRY_*`/`GOAT_DMA_BREAKOUT_*`/`GOAT_HEARTBEAT_*` precedent —
one prefix per feature, not a shared generic one). Every tunable constant gets an
inline `#` comment stating *why* that value was chosen, citing precedent numbers where
one exists and honestly saying "v1/tunable" where none does — this is a hard, visibly
enforced convention throughout `goat/config.py` (see every block cited above).

**Error Handling:** per-item `try/except` inside every scan loop (see
`fetch_all_industry_closes()`'s per-ticker try/except and
`run_dma_breakout_scan()`'s per-constituent try/except), printing a
`[goat-hated-industries-scan] ...` prefixed message and continuing — one bad
industry/ticker must never abort the whole run. The WebSearch call specifically
should return `None` on any failure (network, LLM error, malformed JSON) exactly like
`news_search._search_news_events` does, with a stale-cache fallback preferred over a
hard failure (mirror `get_news_events_for_ticker`'s fallback order).

**Logging Pattern:** `print(f"[goat-hated-industries-scan] ...")` prefixed messages,
matching every other Goat scan module's console-log convention (`[goat-sector-scan]`,
`[goat-industry-scan]`, `[goat-dma-breakout-scan]`).

**Report tone:** "Advisor notes only; no trade action is ever suggested here (see
SOUL.md)" disclaimer line, present on every existing Goat report — required here too.
Additionally, this report must never phrase a divergence finding as a recommendation
("fundamentals still growing — look attractive here" is out of bounds; "fundamentals
still growing despite the price decline" is fine — state the fact, not the
implication).

**Candidate/seen dedup pattern:** `goat_hated_industries_seen` keyed on
`industry_label` (not `ticker` — an industry, unlike a stock, is the identity here).
On each run: an industry that qualifies and has no row → insert (first appearance,
alert-worthy). An industry that qualifies and already has a row → update
`last_flagged_at` only, no alert (still hated, already told Shaun). An industry that
previously had a row but no longer qualifies this run → delete the row (so if it drops
out and later re-qualifies, that's treated as a fresh alert — matches Shaun's framing
that a second wave of the same story is worth knowing about again).

---

## IMPLEMENTATION PLAN

### Phase 1: Config + DB Schema

**Tasks:**
- Add the `GOAT_HATED_*` constant block to `goat/config.py` (see exact list and
  reasoning in Task 1 below).
- Add `goat_hated_industries_seen` and `goat_hated_industries_narrative_cache` tables
  to `goat/db.py`'s `init_goat_tables`, plus their CRUD functions.

### Phase 2: Core Implementation — Severity Gate

**Tasks:**
- `hated_industries_scan.py`: `fetch_spy_close()`, `compute_industry_severity(closes,
  spy_close)` — per-industry 3mo/6mo return, vs-SPY deltas, drawdown-from-52wk-high,
  recent-N-day return, and a `qualifies: bool` per the thresholds.
- Unit tests for the severity gate's threshold logic (qualifying case,
  bottom-5-but-not-severe-enough case, severe-but-already-reversing case,
  insufficient-history case).

### Phase 3: Core Implementation — Narrative + Fundamentals

**Tasks:**
- `hated_industries_scan.py`: `classify_industry_narrative(industry_label, ticker,
  conn)` — WebSearch call with TTL cache, mirroring `news_search.py`'s flow exactly.
- `hated_industries_scan.py`: `check_fundamentals_divergence(top_holdings)` —
  ethical-filter the holdings, pull yfinance `revenueGrowth`/`earningsGrowth` per
  ticker via `cached_session()`, classify the aggregate read.
- Unit tests for both (narrative call mocked/stubbed; fundamentals-divergence tested
  against fabricated `TickerData` fixtures covering growing/declining/mixed/
  insufficient-data cases).

### Phase 4: Integration — Orchestrator, Report, CLI, Notify

**Tasks:**
- `hated_industries_scan.py`: `run_hated_industries_scan(conn)` — ties gate → seen-
  table dedup → narrative → fundamentals together; `render_hated_industries_report(result)`;
  `write_hated_industries_report(result)`.
- `goat/main.py`: `cmd_scan_hated_industries(args)` + subparser + dispatch entry.
- `goat/tests/conftest.py`: add the report-path isolation line.
- `investments/TOOLS.md`: add rows to Automated + Manual tables.
- New systemd unit pair + `scripts/deploy.ps1` timer-list addition.

### Phase 5: Testing & Validation

**Tasks:**
- Full `goat` test suite green.
- Manual VPS run via `invoke_investments.ps1`.
- The IGV/Software - Application real-history backtest sanity check (see Task 11).

---

## STEP-BY-STEP TASKS

### UPDATE `investments/goat/goat/config.py`

- **IMPLEMENT**: Add this block immediately after the `GOAT_DMA_BREAKOUT_*` block
  (end of file, keeping the file's chronological-by-feature ordering convention):

```python
# Hated Industries Scanner, per investments/hated-industries-scanner-handoff.md and
# .agent/plans/hated-industries-scanner.md -- contrarian counterpart to
# industry_rotation.py: finds industries suffering severe, still-live
# underperformance that may be a narrative-driven overreaction rather than a
# fundamentals-justified decline (Shaun's SaaS/AI-fear precedent, drafted 2026-09-16).
GOAT_HATED_RANK_WINDOW_SHORT_TRADING_DAYS = 63  # ~3 calendar months -- same value as
    # GOAT_SECTOR_RANK_WINDOW_TRADING_DAYS, reused here as the "short" severity
    # window; GOAT_INDUSTRY_RANK_WINDOW_TRADING_DAYS (126/6mo, already defined above)
    # doubles as the "long" window. A fear-driven selloff can be a 3-month event, not
    # always a slow 6-month bleed -- both windows are checked, not just one.
GOAT_HATED_BOTTOM_N = 5  # only the worst 5 of the 39 covered industries (by 6-month
    # return) are even considered for the narrative/fundamentals checks below --
    # matches industry-ranking.md's existing "Bottom 5 Falling" framing. v1/tunable.
GOAT_HATED_MIN_UNDERPERFORMANCE_VS_SPY_PCT_3MO = 15.0  # percentage points --
    # industry's 3-month return must trail SPY's own 3-month return by at least this
    # much. v1/tunable, start conservative per this codebase's usual precedent
    # (Cash-Value Scan's 0.80->0.50, Moat Scan's 80 stage threshold).
GOAT_HATED_MIN_UNDERPERFORMANCE_VS_SPY_PCT_6MO = 20.0  # same idea, 6-month window.
    # "Bottom 5 of 39" alone always exists even in a genuinely rising market where
    # nothing is truly hated -- this vs-SPY margin is what makes the gate mean
    # something. Both the 3mo AND 6mo margins must clear for a qualifying industry.
GOAT_HATED_MIN_DRAWDOWN_FROM_HIGH_PCT = 25.0  # % below the trailing 52-week closing
    # high -- a distinct severity dimension from windowed return (catches a sharp
    # multi-week crash a windowed return can dilute against an older high). v1/tunable.
GOAT_HATED_REVERSAL_LOOKBACK_DAYS = 10  # trading days -- same order of magnitude as
    # GOAT_SECTOR_CROSS_RECENCY_DAYS / GOAT_DMA_BREAKOUT_CROSS_RECENCY_DAYS (both 10).
GOAT_HATED_REVERSAL_MAX_RECENT_RETURN_PCT = 8.0  # if the industry has already gained
    # more than this over the last GOAT_HATED_REVERSAL_LOOKBACK_DAYS trading days, it's
    # treated as "already reversing" and excluded from this run's qualifying set --
    # Shaun's own framing (2026-09-16) is to catch live pessimism before the reversal,
    # not to flag it after the fact. v1/tunable.
GOAT_HATED_HISTORY_LOOKBACK_DAYS = 500  # calendar days -- same margin philosophy as
    # GOAT_DMA_BREAKOUT_HISTORY_LOOKBACK_DAYS / GOAT_HEARTBEAT_HISTORY_LOOKBACK_DAYS,
    # comfortably covers a 252-trading-day (52-week) high lookup plus the 126-day rank
    # window plus margin.
GOAT_HATED_NARRATIVE_SUMMARY_MODEL = "sonnet"  # same alias as mytrader/config.py's
    # NEWS_EVENTS_SUMMARY_MODEL -- this call is the same shape (sdk_compat.run_text +
    # WebSearch), just industry-scoped instead of ticker-scoped.
GOAT_HATED_NARRATIVE_CACHE_HOURS = 20.0  # matches NEWS_EVENTS_CACHE_HOURS exactly --
    # same daily-scan cadence, same reasoning (a day-old narrative read is still
    # useful; avoids a repeat WebSearch call if the scan is re-run same-day).
GOAT_HATED_MIN_CONSTITUENT_FUNDAMENTALS_SAMPLE = 2  # at least this many of the
    # narrative call's returned top-holdings tickers must resolve to usable yfinance
    # revenue/earnings growth data for the divergence read to be stated with
    # confidence -- below this, the report says "insufficient constituent data" rather
    # than asserting a divergence read from 0-1 data points.
GOAT_HATED_REPORT_PATH = GOAT_DIR / "hated-industries-report.md"
```

- **PATTERN**: `goat/config.py` lines 474-508 (`GOAT_DMA_BREAKOUT_*` block) for
  comment density/style; lines 150-194 (`GOAT_INDUSTRY_*` block) for the constants
  this new block imports/reuses rather than redefines
  (`GOAT_INDUSTRY_RANK_WINDOW_TRADING_DAYS`, `GOAT_INDUSTRY_ETFS`).
- **GOTCHA**: Do NOT redefine a 6-month window constant — reuse
  `GOAT_INDUSTRY_RANK_WINDOW_TRADING_DAYS` (126) directly, add only the new 3-month
  (`GOAT_HATED_RANK_WINDOW_SHORT_TRADING_DAYS`) constant.
- **VALIDATE**: `uv run --directory investments/goat python -c "from goat import config; print(config.GOAT_HATED_BOTTOM_N, config.GOAT_HATED_REPORT_PATH)"`

### UPDATE `investments/goat/goat/db.py`

- **IMPLEMENT**: Add two tables to `init_goat_tables`'s `executescript` block:

```sql
CREATE TABLE IF NOT EXISTS goat_hated_industries_seen (
    industry_label   TEXT PRIMARY KEY,
    ticker           TEXT NOT NULL,
    first_flagged_at TEXT NOT NULL,
    last_flagged_at  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS goat_hated_industries_narrative_cache (
    industry_label    TEXT PRIMARY KEY,
    ticker            TEXT NOT NULL,
    narrative_thesis  TEXT NOT NULL,
    systemic          INTEGER,
    reasoning         TEXT NOT NULL,
    top_holdings_json TEXT NOT NULL,
    fetched_at        TEXT NOT NULL
);
```

  Plus CRUD functions:
  - `get_hated_industry_seen(conn, industry_label) -> sqlite3.Row | None`
  - `upsert_hated_industry_seen(conn, *, industry_label, ticker) -> bool` — returns
    `True` if this is a brand-new row (first appearance this "wave" — alert-worthy),
    `False` if it already existed (update `last_flagged_at` only, `first_flagged_at`
    untouched). Use `INSERT ... ON CONFLICT(industry_label) DO UPDATE SET
    last_flagged_at = excluded.last_flagged_at` and check `cur.rowcount`/a preceding
    `SELECT` to determine new-vs-existing (SQLite's `ON CONFLICT DO UPDATE` doesn't
    itself tell you which branch fired — do a `get_hated_industry_seen` read first,
    same as `dma_breakout_scan.py`'s existing "check before insert" idiom at
    `monitor.py` lines 223-228).
  - `delete_hated_industry_seen(conn, industry_label) -> int` — mirrors
    `delete_goat_pending_candidate`'s shape.
  - `get_all_hated_industries_seen(conn) -> list[sqlite3.Row]`
  - `get_cached_hated_narrative(conn, industry_label) -> sqlite3.Row | None`
  - `upsert_hated_narrative_cache(conn, *, industry_label, ticker, narrative_thesis,
    systemic, reasoning, top_holdings_json) -> None` — `INSERT OR REPLACE`, mirrors
    `mytrader/db.py`'s `upsert_news_events_cache`.
- **PATTERN**: `goat/db.py` lines 15-60 (`init_goat_tables` structure), lines 157-196
  (`get_goat_pending_candidate`/`insert_goat_pending_candidate`/
  `delete_goat_pending_candidate` CRUD shape), lines 224-254
  (`insert_goat_insider_filing_seen` — closest existing "seen" table, though that one
  is insert-or-ignore not upsert, since a filing dedup key never needs its own
  timestamp bumped the way `last_flagged_at` does here).
  `investments/my-trader/mytrader/db.py` lines ~541-556 (`get_cached_news_events`/
  `upsert_news_events_cache`) for the narrative-cache CRUD shape specifically.
- **IMPORTS**: `systemic` stored as `INTEGER` (SQLite has no bool type) — `1`/`0`/`NULL`
  for `True`/`False`/`None`; convert at the Python boundary (`int(x) if x is not None
  else None` on write, `bool(row["systemic"]) if row["systemic"] is not None else None`
  on read).
- **GOTCHA**: `top_holdings_json` stores a JSON-serialized list (`json.dumps([...])`)
  — `goat/db.py` doesn't currently import `json` at module level; add the import.
- **VALIDATE**: `uv run --directory investments/goat python -m pytest goat/tests/test_db.py -q`

### CREATE `investments/goat/goat/hated_industries_scan.py`

- **IMPLEMENT** (Phase 2 — severity gate):
  - `fetch_spy_close() -> pd.Series | None` — `price_history.fetch_close_history("SPY",
    config.GOAT_HATED_HISTORY_LOOKBACK_DAYS)`.
  - `compute_industry_severity(closes: dict[str, pd.Series | None], spy_close:
    pd.Series | None) -> list[dict[str, Any]]` — for each `(ticker, industry_label)`
    in `config.GOAT_INDUSTRY_ETFS`: compute 3mo return
    (`GOAT_HATED_RANK_WINDOW_SHORT_TRADING_DAYS`), 6mo return
    (`GOAT_INDUSTRY_RANK_WINDOW_TRADING_DAYS`, reuse `industry_rotation.rank_industries`'s
    own pct-return formula: `(close.iloc[-1] / close.iloc[-(window+1)] - 1) * 100`),
    the same two windows for `spy_close`, `underperformance_3mo = industry_3mo -
    spy_3mo` (negative = underperforming) and `underperformance_6mo` likewise,
    `drawdown_from_high_pct = (close.iloc[-1] / close.iloc[-252:].max() - 1) * 100`
    (use `close.iloc[-min(252, len(close)):]` for a shorter series — don't crash on
    less than a year of history), `recent_return_pct` over
    `GOAT_HATED_REVERSAL_LOOKBACK_DAYS`. Return `None` for any figure whose window
    exceeds available history (same missing-data-safe pattern as
    `rank_industries`), never raise. Set `qualifies: bool` = all of: ranked in the
    worst `GOAT_HATED_BOTTOM_N` by 6mo return among industries with data, `underperformance_3mo
    <= -GOAT_HATED_MIN_UNDERPERFORMANCE_VS_SPY_PCT_3MO`, `underperformance_6mo <=
    -GOAT_HATED_MIN_UNDERPERFORMANCE_VS_SPY_PCT_6MO`, `drawdown_from_high_pct <=
    -GOAT_HATED_MIN_DRAWDOWN_FROM_HIGH_PCT`, `recent_return_pct <=
    GOAT_HATED_REVERSAL_MAX_RECENT_RETURN_PCT` (or `None` treated as not-disqualifying
    if insufficient history for the recency window specifically — don't let a data gap
    silently suppress an otherwise-qualifying industry).
- **IMPLEMENT** (Phase 3 — narrative + fundamentals):
  - `_NARRATIVE_SEARCH_PROMPT` module constant — ask for: (1) the dominant negative
    narrative driving `{industry_label}`'s underperformance right now, (2) whether
    that reasoning plausibly applies industry-wide or is concentrated in one/two large
    constituents' company-specific issues, (3) the industry ETF `{ticker}`'s 3-5
    largest constituent holdings by weight (ticker + name). JSON response schema:
    `{"narrative_thesis": str, "systemic": true|false|null, "reasoning": str,
    "top_holdings": [{"ticker": str, "name": str}, ...]}`. Follow
    `mytrader/news_search.py`'s `_SEARCH_PROMPT` structure and its "respond with ONLY
    a JSON object" instruction verbatim in style.
  - `_search_industry_narrative(industry_label, ticker) -> dict | None` — mirrors
    `news_search._search_news_events` exactly: `asyncio.run(run_text(prompt=...,
    options=ClaudeAgentOptions(allowed_tools=["WebSearch"],
    model=config.GOAT_HATED_NARRATIVE_SUMMARY_MODEL)))`, parsed via the same
    `_parse_json`-style fence-stripping helper (either import/reuse
    `mytrader.news_search`'s parser if it's exposed as a public function, or copy the
    small helper — check whether `_parse_json` is name-mangled private before deciding
    to import vs. copy).
  - `classify_industry_narrative(industry_label, ticker, conn) -> dict | None` —
    cache-check via `db.get_cached_hated_narrative` against
    `GOAT_HATED_NARRATIVE_CACHE_HOURS`, call `_search_industry_narrative` on a miss,
    write through `db.upsert_hated_narrative_cache`, stale-cache fallback on search
    failure (same three-branch flow as `news_search.get_news_events_for_ticker`).
  - `check_fundamentals_divergence(top_holdings: list[dict]) -> dict` — ethical-filter
    each holding ticker via `scripts.ethical_filter.check_ticker` (drop excluded,
    collect review_reason); for the rest, `market_data.fetch_ticker_data(ticker)`
    inside a `cached_session()`, read `data.info.get("revenueGrowth")` and
    `data.info.get("earningsGrowth")`; classify each resolvable ticker as
    "growing" (either metric > 0), "declining" (both <= 0 and at least one not None),
    or skip (both None/missing). Aggregate: if resolvable count <
    `GOAT_HATED_MIN_CONSTITUENT_FUNDAMENTALS_SAMPLE`, `verdict = "insufficient_data"`;
    else majority-growing → `"fundamentals_still_growing"` (the overreaction
    signature), majority-declining → `"fundamentals_also_declining"`, tie/mixed →
    `"mixed"`. Return `{"verdict": ..., "per_ticker": [...], "resolved_count": n,
    "excluded": [...]}`.
- **IMPLEMENT** (Phase 4 — orchestrator/report):
  - `run_hated_industries_scan(conn: sqlite3.Connection) -> dict[str, Any]` — fetch
    `industry_rotation.fetch_all_industry_closes()` + `fetch_spy_close()`, compute
    severity, take the qualifying set (already bounded to `GOAT_HATED_BOTTOM_N` by
    the `qualifies` logic above), for each qualifying industry call
    `classify_industry_narrative` then `check_fundamentals_divergence` on its
    `top_holdings`, then dedup via `db.upsert_hated_industry_seen` — collect
    `new_candidates` (the "was this brand-new" `True` cases) for the WhatsApp alert.
    Separately: for every row in `db.get_all_hated_industries_seen(conn)` whose
    `industry_label` is NOT in this run's qualifying set, call
    `db.delete_hated_industry_seen` (drop-out cleanup, per the "Candidate/seen dedup
    pattern" section above). Return `{"severity": [...all 39 rows...], "flagged": [...
    enriched qualifying rows...], "new_candidates": [...], "asx_note": None}` (no ASX
    note actually needed — this feature is US-ETF-only via `GOAT_INDUSTRY_ETFS`, unlike
    `dma_breakout_scan.py`'s combined-universe scans; omit any ASX-availability
    handling, it doesn't apply here).
  - `render_hated_industries_report(result) -> str` — sections: intro/disclaimer
    (mirror `render_industry_ranking_report`'s tone), then one sub-section per flagged
    industry with a small table (3mo/6mo return, vs-SPY deltas, drawdown-from-high,
    "hated since" = `first_flagged_at` date) followed by narrative thesis + systemic
    call + fundamentals-divergence verdict + representative constituent tickers
    (explicitly labeled "read-only — not staged as candidates"), then a closing note
    if `result["flagged"]` is empty ("No industry cleared the severity gate today").
  - `write_hated_industries_report(result) -> None`.
- **PATTERN**: `dma_breakout_scan.py` end to end for orchestrator shape;
  `monitor.py`'s `render_industry_ranking_report` (lines 326-385) for report-section
  shape; `news_search.py` end to end for the WebSearch/cache flow.
- **IMPORTS**: `from . import config, db, industry_rotation, price_history`;
  `from mytrader import market_data`; `from scripts.ethical_filter import check_ticker
  as ethical_check`; `from mytrader.news_search import ...` only if reusing its
  `_parse_json` helper directly (confirm it's importable, not name-mangled — if
  private, copy the ~8-line helper instead of reaching into another module's
  underscore-prefixed internals).
- **GOTCHA**: `top_holdings` tickers returned by the WebSearch call are LLM-sourced
  free text, not a guaranteed-clean ticker list — normalize via `mytrader.tickers.normalize`
  before any yfinance lookup, and treat a `fetch_ticker_data` failure for any one of
  them as "not resolvable" (skip, don't crash), same defensive posture as every other
  yfinance call in this codebase.
- **GOTCHA**: This feature's `qualifies` bottom-N logic must rank only among industries
  that HAVE return data (`return_pct is not None`) — mirror `rank_industries`'s
  missing-data-sorts-last convention so a data-gap industry can't spuriously occupy a
  "worst 5" slot ahead of a real one.
- **VALIDATE**: `uv run --directory investments/goat python -m pytest goat/tests/test_hated_industries_scan.py -q`

### UPDATE `investments/goat/goat/main.py`

- **IMPLEMENT**: `cmd_scan_hated_industries(args)`:

```python
def cmd_scan_hated_industries(args) -> None:
    from .hated_industries_scan import run_hated_industries_scan, write_hated_industries_report
    from .monitor import maybe_notify

    conn = _open_conn()
    result = run_hated_industries_scan(conn)
    conn.close()
    write_hated_industries_report(result)
    maybe_notify(
        {"new_alerts": []}, new_candidates=result["new_candidates"],
        candidate_label="newly hated industrie(s) flagged",
    )
    print(
        f"Hated industries scan complete: {len(result['flagged'])} industry(ies) "
        f"cleared the severity gate, {len(result['new_candidates'])} newly flagged. "
        f"See investments/goat/hated-industries-report.md"
    )
```

  Plus `subparsers.add_parser("scan-hated-industries", help="On-demand hated "
  "industries scan (also runs daily as part of monitor, or standalone)")` and a
  `dispatch["scan-hated-industries"] = cmd_scan_hated_industries` entry.
- **PATTERN**: `main.py` lines 120-137 (`cmd_scan_dma_breakout`) — same shape, adapted.
- **GOTCHA**: `maybe_notify`'s `candidate_label` must be feature-specific (see the
  2026-08-18 fix in `monitor.py`'s `maybe_notify` docstring) — do not leave it at the
  default `"new sector breakout candidate(s)"`.
- **DECISION**: Not wired into `cmd_monitor()`'s daily call chain the way
  `run_industry_scan` is — this feature gets its own systemd timer (see Task 9), same
  as Heartbeat Scan / Insider Scan / DMA Breakout, all of which run standalone rather
  than piggybacking on the base Monitor cadence. Confirm this placement during
  implementation if it turns out `cmd_monitor()` already bundles every daily Goat
  check by convention — the codebase currently mixes both patterns (sector + industry
  ranking ride along in `monitor`; heartbeat/insider/dma-breakout are standalone), so
  either is locally consistent; standalone is recommended because this feature's own
  LLM/WebSearch cost shouldn't silently ride along on every `monitor` invocation
  (including any future on-demand `monitor` runs Shaun triggers manually).
- **VALIDATE**: `uv run --directory investments/goat python -m goat.main scan-hated-industries --help`
  (argparse smoke test only — do NOT run this against the real DB locally, see Level 4).

### UPDATE `investments/goat/goat/tests/conftest.py`

- **IMPLEMENT**: add `monkeypatch.setattr(goat_config, "GOAT_HATED_REPORT_PATH",
  tmp_path / "hated-industries-report.md")` inside `_isolate_goat_report_path`.
- **PATTERN**: lines 29-49, same fixture, same pattern as the other 5 report-path
  monkeypatches already there.
- **GOTCHA**: skipping this means any test calling `write_hated_industries_report`
  writes into the real `investments/goat/hated-industries-report.md` during `pytest`.
- **VALIDATE**: run the full goat test suite (Level 2 below), confirm `git status`
  shows no unexpected modification to `investments/goat/hated-industries-report.md`.

### CREATE `investments/goat/goat/tests/test_hated_industries_scan.py`

- **IMPLEMENT**: 
  - Severity-gate tests: a fabricated close series that clears all four thresholds
    (qualifies=True), one that's bottom-5 but doesn't clear the vs-SPY margin
    (qualifies=False), one that's severe but shows a sharp recent recovery
    (qualifies=False, reversal exclusion), one with insufficient history for the
    52-week drawdown lookup (degrades gracefully, doesn't crash — treat as
    non-qualifying, not an error).
  - `classify_industry_narrative` tests: stub/monkeypatch
    `_search_industry_narrative` (or whatever the WebSearch wrapper function is named)
    to return a fixed dict; assert cache-hit-within-TTL skips the call; assert
    cache-miss-or-stale calls it and writes through; assert a `None` return (search
    failure) falls back to a stale cache row if one exists, else returns `None`. Check
    `mytrader/tests/test_news_search.py` first for the exact stub-injection pattern
    (monkeypatching module-level function vs. dependency injection) and mirror it.
  - `check_fundamentals_divergence` tests: fabricated `TickerData` fixtures (mirror
    `test_dma_breakout_scan.py`'s `_healthy_ticker_data` helper) covering: all
    holdings growing → `"fundamentals_still_growing"`; all declining →
    `"fundamentals_also_declining"`; mixed → `"mixed"`; fewer than
    `GOAT_HATED_MIN_CONSTITUENT_FUNDAMENTALS_SAMPLE` resolvable →
    `"insufficient_data"`; an ethically-excluded holding is dropped before scoring
    (assert it appears in `excluded`, not `per_ticker`).
  - Seen-table/dedup integration test: run `run_hated_industries_scan` twice in a row
    against the same monkeypatched qualifying industry — first run produces one
    `new_candidates` entry, second run produces zero (already seen); a third run with
    that industry monkeypatched OUT of the qualifying set, followed by a fourth run
    with it back IN, produces a `new_candidates` entry again (drop-out-then-requalify
    re-alerts).
- **PATTERN**: `test_dma_breakout_scan.py` (fixture-construction style),
  `test_industry_rotation.py` (`_dates`/ranking-test style).
- **VALIDATE**: `uv run --directory investments/goat python -m pytest goat/tests/test_hated_industries_scan.py -q`

### UPDATE `investments/TOOLS.md`

- **IMPLEMENT**: Add a "Goat Hated Industries Scan" row to the "Automated (scheduled)"
  table (mirror the DMA Breakout Scan row's format exactly — `<a
  id="goat-hated-industries-scan">`, Daily Read link, schedule, output path), a
  corresponding entry in the "Daily Read" table linking
  `investments/goat/hated-industries-report.md`, and a "Goat hated-industries scan
  (on-demand)" row in "Manual / on-demand only"
  (`-Package goat -Command "scan-hated-industries"`).
- **PATTERN**: `TOOLS.md` line 26 (Daily Read entry) and line 44 (DMA Breakout
  Automated row) for exact format.
- **VALIDATE**: manual read-through — no automated check for a docs file.

### CREATE `scripts/systemd/second-brain-goat-hated-industries-scan.service` + `.timer`

- **IMPLEMENT**: copy `second-brain-goat-dma-breakout-scan.{service,timer}` (or
  `second-brain-goat-heartbeat-scan.{service,timer}`) near-verbatim:
  `ExecStart=.../investments/.venv/bin/python -m goat.main scan-hated-industries`,
  `WorkingDirectory=.../investments/goat`, stdout+stderr
  `append:.../investments/goat/hated_industries_scan_runs.log`.
  `OnCalendar=*-*-* 23:50:00 UTC` — checked against every existing timer's
  `OnCalendar` value this session (21:35, 21:50, 22:05, 22:30, 22:45, 22:55, 23:30 are
  all taken; 23:50 is clear).
- **PATTERN**: `scripts/systemd/second-brain-goat-dma-breakout-scan.{service,timer}`.
- **VALIDATE**: `systemd-analyze verify` on the VPS (or a plain read-through if that's
  not available locally) — confirm no syntax error, confirm the `OnCalendar` line
  matches the chosen slot exactly.

### UPDATE `scripts/deploy.ps1`

- **IMPLEMENT**: add `second-brain-goat-hated-industries-scan.timer` to the `$TIMERS`
  stop/start list.
- **PATTERN**: every other Goat timer name already in that list.
- **VALIDATE**: manual read-through.

---

## TESTING STRATEGY

### Unit Tests

Severity-gate threshold logic (all four gate conditions independently, plus the
combined AND), fundamentals-divergence classification, narrative-cache TTL behavior
(mocked WebSearch call) — all covered in `test_hated_industries_scan.py` per the task
above.

### Integration Tests

`run_hated_industries_scan()` → `render_hated_industries_report()` →
`write_hated_industries_report()` round-trip against the monkeypatched report path;
the seen-table dedup/re-alert multi-run sequence described in the test task above.

### Edge Cases

- Zero industries qualify on a given day (report renders a clean "nothing flagged"
  section, no crash, `maybe_notify` stays silent).
- All 39 industries return `None` closes (simulated yfinance outage) — severity gate
  produces an all-`None` list, nothing qualifies, no crash.
- WebSearch call fails for a qualifying industry with no prior cache row — the
  industry still appears in `flagged` with narrative fields explicitly `None`/"unknown"
  rather than the whole run aborting (mirror `news_events.py`'s `verdict="unknown"`
  posture for a total search failure).
- Narrative call returns a `top_holdings` ticker that doesn't resolve via yfinance at
  all (delisted/malformed) — `check_fundamentals_divergence` skips it, doesn't crash,
  and the `resolved_count` still reflects only genuinely-resolved tickers.
- An industry qualifies, gets flagged, and its narrative call returns
  `"systemic": null` (LLM genuinely uncertain) — report renders this as "unclear
  whether industry-wide or concentrated," never silently defaults to `true` or
  `false`.

---

## VALIDATION COMMANDS

### Level 1: Syntax & Style
```powershell
uv run --directory investments/goat ruff check goat/
uv run --directory investments/goat mypy goat/
```

### Level 2: Unit Tests
```powershell
uv run --directory investments/goat python -m pytest -q
```

### Level 3: Integration Tests
Covered by Level 2 — this codebase does not separate unit/integration test files for
Goat (single `testpaths = ["goat/tests"]` in `pyproject.toml`, same as every other
Goat feature's plan notes).

### Level 4: Manual Validation (VPS only — never run locally against the real DB)
```powershell
.\scripts\invoke_investments.ps1 -Package goat -Command "scan-hated-industries"
```
Then read `investments/goat/hated-industries-report.md` (pulled to this machine via
vault sync) and manually sanity-check:
- Severity table shows plausible 3mo/6mo returns and drawdown figures for all 39
  industries (spot-check 2-3 against a live chart).
- Any flagged industry's narrative thesis reads as a real, coherent summary (not
  garbled JSON leakage) and its systemic call is one of true/false/null, never a
  hallucinated confident guess with no reasoning.
- Fundamentals-divergence verdict is present and its `per_ticker` detail matches
  what a quick manual yfinance/Google check of those same tickers' recent
  revenue/earnings trend shows.
- Run twice in the same day — second run produces zero `new_candidates` (dedup
  working) even if the same industries still qualify.
- No ticker rows appear in `goat_pending_candidates` as a side effect (confirms the
  "no ticker staging" decision held in the actual implementation).

### Level 5: Additional Validation — the SaaS-episode backtest

Before considering this feature validated, manually check the severity gate's logic
against **`IGV` (Software - Application)**, using real historical yfinance data, over
the actual AI-fear window Shaun is describing (a few months prior to 2026-09-16 per
his framing — confirm the exact window via a quick web/news search on when SaaS
sentiment specifically bottomed, then pull `IGV` and `SPY` close history spanning
that period). Confirm the severity gate's thresholds (as currently set) would have
flagged `Software - Application` as hated during that window, and roughly how many
weeks before the subsequent recovery the flag would have fired. This is a one-off
manual check (a Python one-liner against `price_history.fetch_close_history`, not a
permanent automated test) — if the current threshold values would have missed the
episode, tune them (loosen the vs-SPY margins or the drawdown floor) before shipping,
same "tune from a real reference case" precedent as every other threshold in this
codebase.

---

## ACCEPTANCE CRITERIA

- [ ] Severity gate correctly identifies the worst-5-of-39 industries by 6-month
      return, filtered further by vs-SPY underperformance (3mo AND 6mo), drawdown
      floor, and not-already-reversing.
- [ ] Narrative classification returns a structured, cached, industry-scoped read
      (thesis + systemic call + top holdings) via the existing WebSearch mechanism,
      with graceful degradation on failure.
- [ ] Fundamentals-divergence check correctly classifies growing/declining/mixed/
      insufficient-data against the narrative call's returned constituents.
- [ ] No writes to `goat_pending_candidates` anywhere in this feature — confirmed by
      code review (per Shaun's 2026-09-16 decision).
- [ ] `goat_hated_industries_seen` correctly gates WhatsApp/toast alerts to
      newly-flagged industries only; re-qualifying the next day does not re-alert;
      dropping out and re-qualifying later does re-alert.
- [ ] `scan-hated-industries` CLI command works standalone with its own systemd timer
      (23:50 UTC, no collision with existing timers).
- [ ] All validation commands (Levels 1-5) pass, including the IGV backtest sanity
      check.
- [ ] `investments/TOOLS.md` updated (Automated + Daily Read + Manual tables).
- [ ] No trade-action language anywhere in the new report (SOUL.md compliance, same
      as every other Goat report).

## COMPLETION CHECKLIST

- [ ] All tasks completed in order
- [ ] Each task's validation command passed immediately after that task
- [ ] Full goat test suite passes (`uv run --directory investments/goat python -m pytest -q`)
- [ ] ruff + mypy clean
- [ ] Level 4 manual VPS validation run, report inspected by eye
- [ ] Level 5 IGV backtest run, thresholds tuned if it would have missed the episode
- [ ] Acceptance criteria all met
- [ ] `TOOLS.md` updated, systemd timer + `deploy.ps1` updated

---

## NOTES

- **Why the top-holdings source changed from the handoff's "hardcoded seed table"
  recommendation.** The handoff (`investments/hated-industries-scanner-handoff.md`)
  proposed a static `GOAT_INDUSTRY_TOP_HOLDINGS` config dict, reasoning it would avoid
  scraper-maintenance surface area (same logic as the DMA Breakout Scanner's ASX
  `sector_label` gap-note precedent). During this planning session, folding
  holdings-resolution into the *same* WebSearch call already gated by the severity
  check (part of narrative classification) came out ahead on every axis that mattered:
  zero new maintenance burden (no 39-entry table to research now or refresh later as
  index compositions drift), zero risk of the LLM inventing/guessing holdings data
  from stale training knowledge (a live WebSearch call fetches current data, same
  "not disclosed → null, never guessed" discipline the Moat Scanner's `qualitative.py`
  already follows), and it costs nothing extra since the call only fires for the
  already-small set of industries that cleared the severity gate — the same cost
  bound the seed-table idea was trying to achieve, just without the static-data
  staleness risk. Flagged explicitly in "Decisions Confirmed With Shaun" above since
  this is a deviation from what the handoff proposed and Shaun had provisionally
  waved through, not something to slide past silently.
- **Why no ticker staging (Decision 1).** Confirmed directly with Shaun 2026-09-16:
  keeping this tool's job separate from the Moat Scanner's and my-trader Find's
  ticker-level picks. This does mean the "next step" for a flagged industry is
  manual — Shaun reads the representative constituents in the report and decides
  himself whether to run any of them through Find or check the Moat ranking. That's
  intentional, not a gap.
- **The two-window (3mo + 6mo) severity design is genuinely new for this feature** —
  every other Goat rotation/breakout check in this codebase uses exactly one window.
  Worth double-checking during implementation that requiring both (rather than
  either) doesn't make the gate so strict it rarely fires; if the first live run (or
  the Level 5 IGV backtest) shows this, relaxing to "either window's margin clears"
  is a one-line change, not a re-plan.
- **This feature deliberately has no promote/dismiss CLI commands** (unlike
  Heartbeat/DMA Breakout/Sector scans) — there is nothing to promote, since nothing
  is staged as a ticker candidate. Don't add `cmd_promote_candidate`-style scaffolding
  for this feature by reflexive copy-paste.

## Confidence Score

**7/10** for one-pass implementation success. The severity-gate math and the overall
scan/report/CLI/systemd plumbing are near-exact mirrors of already-shipped, tested
code (`industry_rotation.py`, `dma_breakout_scan.py`) — high confidence there. Points
held back for: (1) the narrative-classification JSON schema and prompt are new,
untested against real WebSearch output — the execution agent should expect at least
one iteration on prompt wording/JSON-parsing robustness once real results come back,
same as `news_search.py`'s own documented history of prompt refinement; (2) the
fundamentals-divergence check's reliance on `revenueGrowth`/`earningsGrowth` being
populated in yfinance `.info` for the LLM-returned constituent tickers is unverified
at plan time — some tickers may lack these fields, which is why
`GOAT_HATED_MIN_CONSTITUENT_FUNDAMENTALS_SAMPLE` and the "insufficient_data" verdict
exist as a safety net, not a guarantee the check is always informative; (3) the Level
5 IGV backtest is a real, not-yet-performed validation against Shaun's actual
motivating episode — there's a real chance the initial threshold values need tuning
after that check, which is expected (flagged throughout as v1/tunable) but does mean
"done" isn't "done" until that backtest is actually run.
