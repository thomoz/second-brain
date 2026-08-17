# Feature: Goat Phase 3 — S&P 500 Heartbeat Scanner

The following plan should be complete, but it's important that you validate documentation and codebase patterns and task sanity before you start implementing.

Pay special attention to naming of existing utils, types, and models. Import from the right files etc.

This plan covers **Phase 3 only** of `investments/goat/HANDOFF.md`'s 3-phase Goat scope — the stock/index "heartbeat" scanner within rising sectors. Phase 1 (150-day-MA holdings exit check, plus its 2026-08-16 intraday live-check extension) and Phase 2 (11 SPDR sector ETF ranking + breakout signal) are both already shipped and live. Phase 3 was explicitly called out in HANDOFF.md as "the hardest, most open questions" and "the single most underspecified part of the whole framework" — the two genuinely unresearched design questions (the heartbeat consolidation metric, and the fundamentals risk-filter shape) were resolved in a real research/discussion pass during this planning session (2026-08-17), captured below — do not re-litigate them during implementation.

## Feature Description

Extend Goat with a weekly scan (plus on-demand trigger) that screens S&P 500 constituents inside currently-"rising" sectors (per Phase 2's own ranking) for the webinar's "heartbeat" entry pattern: a sustained, low-volatility sideways consolidation followed by a breakout above the 50-day moving average with that MA now sloping up. A fresh hit gets staged as a real, actionable candidate (reusing Phase 2's existing `goat_pending_candidates` table) with fundamentals survival-context attached, for Shaun to `promote-candidate` into my-trader's watchlist or `dismiss-candidate`.

## User Story

As Shaun, wanting to find individual stocks worth a look within sectors that are already rising (per Phase 2), rather than eyeballing charts across the S&P 500 myself
I want a weekly scan that flags stocks showing a genuine "heartbeat" consolidation-then-breakout pattern, with debt/cash-runway/margin/growth context attached so I can judge survival risk myself
So that I get real, sourced stock candidates from the webinar's own Step 1 framework, not just the sector-level signal Phase 2 already gives me

## Problem Statement

Phase 2 answers "which sectors are rising" but stops there — it doesn't look inside a rising sector for genuinely fresh, technically-confirmed individual stock entries. HANDOFF.md's own Q2 ("can it scan for stocks with the heartbeat pattern that just crossed the 50DMA?") was answered "yes, technically, but this is the harder half" specifically because the "heartbeat" (low-volatility consolidation for 1-3+ months) has no existing, sourced quantitative definition anywhere in this codebase or the source webinar notes — HANDOFF.md explicitly warns against "just guess a number and ship it," the same discipline `opportunity.py`'s thresholds went through after Shaun called out invented numbers the first time.

## Solution Statement

Add three new modules to `investments/goat/goat/`:

1. **`sp500_universe.py`** — scrapes the S&P 500 constituent list + GICS sector from Wikipedia (`requests` + `BeautifulSoup`, matching the existing `asx_announcements.py`/`sec_filings.py` direct-fetch style — no `pandas.read_html`, since neither `lxml` nor `html5lib` is a declared dependency anywhere in the workspace), cached in a new `goat_sp500_constituents` table refreshed weekly rather than scraped every run.
2. **`heartbeat.py`** — the actual pattern detector. The consolidation ("heartbeat") leg is a **Bollinger Band Width (BBW) percentile squeeze**: reusing the exact `width_pct` formula already proven in `mytrader/gold_technicals.py::compute_bollinger()` (textbook 20-day/2.0-std-dev Bollinger, ported to a full `*_series()` the same way that module's own docstring prescribes — one formula, no second independently-drifting copy), flagged when BBW has sat at/below its own trailing 1-year Nth-percentile threshold for most of the last ~3 months (self-relative to each ticker's own volatility regime — chosen specifically because a fixed universal percentage would misfire wildly comparing a mega-cap to a small-cap biotech across 500 different tickers). The breakout leg reuses the same 50DMA-cross-plus-slope-turning-up idiom `sector_rotation.check_sector_breakout()` (Phase 2) already implements — ported into `heartbeat.py` as its own copy (see NOTES for why this is a deliberate non-refactor, matching the codebase's own already-accepted duplication between `macro_indicators.check_gold_trend()` and `sector_rotation.check_sector_breakout()`).
3. **`fundamentals_context.py`** — computes the webinar's own priority-ordered survival checklist (debt → cash runway → margins → revenue growth → cash generation) as **informational context attached to every candidate**, not a hard pass/fail gate (confirmed with Shaun 2026-08-17: gating on all 5 independently would filter out nearly the entire S&P 500, since almost no company is debt-free). The only thing that actually **suppresses** a candidate from being staged is a genuine near-term-insolvency combination (debt/equity at/above the existing `DEBT_TO_EQUITY_FLAG` threshold **and** cash-burning with under a year of runway) — everything else surfaces as plain-English context in the candidate's note for Shaun to judge himself, matching this tool's advisor-only philosophy everywhere else.

A new orchestrator, `heartbeat_scan.py::run_heartbeat_scan()`, ties these together: get Phase 2's current rising-sector list, filter the (cached) S&P 500 universe down to just those sectors' constituents, run the heartbeat+breakout check per ticker, compute fundamentals context on any hit, and stage genuinely fresh candidates into the existing `goat_pending_candidates` table (`source="goat_heartbeat_scan"`) via the same three-way holding/watchlist/already-pending dedup `monitor.py::_stage_new_sector_candidates` already established for Phase 2. New `scan-heartbeat` CLI subcommand (on-demand) plus a new weekly systemd timer (not enabled without Shaun's explicit go-ahead, same precedent as every other Goat rollout).

## Feature Metadata

**Feature Type**: Enhancement (extends the already-shipped `investments/goat/` package — no new workspace member, no new sibling package)
**Estimated Complexity**: High — not because any single piece is algorithmically hard, but because this phase combines a genuinely novel, self-sourced technical definition (no existing codebase precedent for a percentile-relative volatility screen), a new external data source (Wikipedia scrape) with real markup-drift risk, a materially larger fetch volume (potentially 100-300 individual stock fetches per weekly run vs. Phase 1/2's ~10-20), and new fundamentals-field usage (`totalCash`/`freeCashflow`/margins/`revenueGrowth`) that no existing Goat code has touched yet.
**Primary Systems Affected**: `investments/goat/goat/` (new `sp500_universe.py`, `heartbeat.py`, `fundamentals_context.py`, `heartbeat_scan.py`; extended `config.py`, `db.py`, `main.py`, `monitor.py`); `investments/briefs-finance/data/investments.db` (new `goat_sp500_constituents` table; new *rows* of an existing type in `goat_pending_candidates`, no schema change there); `scripts/systemd/` (two new unit files); `scripts/deploy.ps1` (new timer added to the managed list). No changes to any `my-trader/` `.py` file — read-only reuse of `mytrader.market_data`/`mytrader.config`/`mytrader.tickers`, same boundary Phase 1/2 already established.
**Dependencies**: None beyond what Phase 1/2 already added (`yfinance`, `pandas`, `mytrader` workspace dependency — `requests`+`beautifulsoup4` are already transitive via the `my-trader` workspace dependency, confirmed in `investments/my-trader/pyproject.toml`, so no new `goat/pyproject.toml` dependency line is needed).

---

## RESEARCH RESOLVED DURING THIS PLANNING SESSION (2026-08-17) — BINDING

HANDOFF.md's "Still open — needs real research/backtesting" section (#1, the heartbeat threshold) and the fundamentals-filter shape (not explicitly listed as an open question in HANDOFF.md, but implied by "Fundamentals risk filter... needs its own design") are resolved here. Confirmed directly with Shaun 2026-08-17 — do not re-litigate:

1. **Heartbeat consolidation metric → Bollinger Band Width (BBW) percentile squeeze**, not Minervini's VCP. Researched both (see Sources below): VCP (progressively-tightening pullbacks, commonly cited as something like 25%→15%→8%→4% or 18%→12%→6% depending on source — sources don't even agree on the exact percentages) needs pivot/swing-high-low detection, a materially harder and more fragile v1 build with no single canonical number to cite. BBW-squeeze (bands contracting around price; BandWidth = `(upper - lower) / middle * 100`) is the standard, widely-documented volatility-contraction measure, and — critically — this codebase already has the exact formula proven and tested in `mytrader/gold_technicals.py::compute_bollinger()` (lines 117-125). Reusing it is real code reuse, not a new invention.
2. **Squeeze threshold is self-relative (percentile), not a fixed absolute %.** A universal fixed BBW cutoff would behave completely differently for (say) a stable mega-cap utility vs. a volatile small-cap biotech, both of which can appear anywhere in a 500-name scan. Flag when a ticker's current BBW sits at/below its own trailing-year Nth-percentile — see `GOAT_HEARTBEAT_BBW_PERCENTILE` below for the specific v1 number, documented as tunable/v1 (not literature-final), same treatment `GOAT_SECTOR_CROSS_RECENCY_DAYS` already got in Phase 2.
3. **Fundamentals risk filter is informational-not-gating.** The webinar frames debt/cash-runway/margins/revenue-growth/cash-generation as a priority-ordered human checklist ("how unlikely is bankruptcy"), not a strict AND-of-5 pass/fail battery — gating on all 5 independently would disqualify almost every real company (very few S&P 500 constituents carry zero debt). All 5 are computed and surfaced as plain-English context on every staged candidate (same "advisor notes only, judge for yourself" philosophy as `price_action.py`/`macro_indicators.check_gold_trend()`). The only thing that actually suppresses staging is a genuine near-term-insolvency combination — see `fundamentals_context.py`'s task below for the exact condition, built entirely from thresholds this codebase already has (`mytrader.config.DEBT_TO_EQUITY_FLAG`), not new invented numbers.

### Sources consulted (heartbeat pattern research, 2026-08-17)
- [VCP Pattern Explained — TrendSpider](https://trendspider.com/learning-center/volatility-contraction-pattern-vcp/) — VCP contraction-depth percentages and 2-5-contraction base structure (why VCP was not chosen for v1: no single agreed-upon percentage set, needs pivot detection).
- [Mastering the Volatility Contraction Pattern — Deepvue](https://deepvue.com/screener/volatility-contraction-pattern/) — same VCP caveat, cross-referenced.
- [Custom Bollinger Band Squeeze Screener — TradingView/Pineify](https://www.tradingview.com/script/LvV9KymH-Custom-Bollinger-Band-Squeeze-Screener-Pineify/) and [Bollinger Bands Strategy: Squeeze then Surge — LuxAlgo](https://www.luxalgo.com/blog/bollinger-bands-strategy-squeeze-then-surge/) — confirms BandWidth (`(upper-lower)/middle`) as the standard, widely-used quantitative squeeze measure, the basis for the metric chosen here.
- [Bollinger Band Squeeze US Stocks — ChartMill](https://www.chartmill.com/stock/markets/usa/screener/bollinger-band-squeeze-stocks) — confirms this is a real, commonly-screened-for pattern, not a niche/unproven one.

---

## CONTEXT REFERENCES

### Relevant Codebase Files — READ THESE BEFORE IMPLEMENTING

- `investments/goat/HANDOFF.md` (whole file, esp. lines 138-183 "Phase 3" and lines 272-283 "Still open") — the authoritative scope/history document; Phase 3's exact requirements and everything already resolved live here.
- `investments/goat/goat/config.py` — every existing Goat threshold, and *why* each one is what it is (2026-08-16 overrides, Weinstein/webinar sourcing notes). Mirror this documentation density for every new constant.
- `investments/goat/goat/sector_rotation.py` (lines 53-113) — `check_sector_breakout()` is the exact cross+slope idiom to port into `heartbeat.py`; read this fully, don't paraphrase from memory.
- `investments/goat/goat/monitor.py` (lines 138-182) — `_stage_new_sector_candidates()` and `run_sector_scan()` are the staging/orchestration pattern `heartbeat_scan.py` must mirror; `maybe_notify()` (lines 109-135) needs a small generalization (see Task list).
- `investments/goat/goat/db.py` (whole file) — `goat_pending_candidates` schema (lines 28-35) is already generic enough to reuse as-is; `insert_goat_pending_candidate`/`get_goat_pending_candidate` (lines 78-100) reused directly, no schema change.
- `investments/goat/goat/price_history.py` — `fetch_close_history()` is the exact fetch function to reuse for every per-ticker close-history fetch in this phase; already handles the `.AX` fallback (irrelevant for S&P 500 names, but harmless).
- `investments/goat/goat/main.py` — CLI dispatch pattern (`cmd_*` functions + `dispatch` dict + `_open_conn()`); `cmd_promote_candidate`/`cmd_dismiss_candidate` (lines 77-114) already work generically for any `goat_pending_candidates` row regardless of source — confirm during Level 4 validation they work unchanged for a `source="goat_heartbeat_scan"` row too.
- `investments/my-trader/mytrader/gold_technicals.py` (lines 1-11 docstring, lines 117-125 `compute_bollinger`) — the BBW formula to port, and the module's own documented "`*_series()` full history + `compute_*()` latest-value wrapper" convention to follow for `heartbeat.py`'s own functions.
- `investments/my-trader/mytrader/macro_indicators.py` (lines 502-573, `check_gold_trend`) — the sign-flip cross-detection idiom (`diff.gt(0).astype(int) - diff.lt(0).astype(int)`, `sign.diff().fillna(0) != 0`) already used twice in this codebase; `heartbeat.py`'s breakout leg is a third, deliberate copy (see NOTES).
- `investments/my-trader/mytrader/checks/balance_sheet.py` (whole file) — the ROE-fallback-when-`.info`-is-empty pattern (`market_data.fetch_balance_sheet_financials`) — `fundamentals_context.py` should degrade the same way when a field is missing, not just report "unknown" for the whole ticker.
- `investments/my-trader/mytrader/market_data.py` (whole file) — `fetch_ticker_data()` / `TickerData.info` is the fundamentals data source; `fetch_balance_sheet_financials()` (lines 114-157) is the deeper-statement fallback to reuse if `.info`'s `totalCash`/`freeCashflow`/etc. come back empty for a given ticker.
- `investments/my-trader/mytrader/config.py` (lines 62-76) — `DEBT_TO_EQUITY_IDEAL`/`DEBT_TO_EQUITY_FLAG`/`ROE_FLAG_THRESHOLD_PCT` — reused directly by `fundamentals_context.py`, not re-derived.
- `investments/my-trader/mytrader/candidate_sync.py` (whole file) — the "separate staging area, explicit promote/dismiss action, never direct into watchlist" philosophy this whole phase must keep following (already established, do not deviate).
- `investments/my-trader/mytrader/asx_announcements.py` (lines 1-100) — the `requests` + `BeautifulSoup` direct-fetch style to mirror in `sp500_universe.py` (headers dict, timeout, try/except-returns-None-on-any-failure, no third-party wrapper library).
- `investments/my-trader/mytrader/tickers.py` — `normalize()` handles `BRK.B`→`BRK-B`-style share-class dots; Wikipedia's raw `Symbol` column uses dots for these same tickers (e.g. `BRK.B`), so every scraped ticker must be passed through `tickers.normalize()` before use.
- `investments/goat/goat/tests/conftest.py` (whole file) — fixture pattern (`db_conn`, `_isolate_goat_report_path`, `_no_real_price_history_fetch`) every new test file must follow; extend `_isolate_goat_report_path` for the new report file path.
- `investments/goat/goat/tests/test_sector_rotation.py` (lines 1-60) — the price-series test-builder-helper style (`_dates`, `_flat_then_move`, `_series_with_cross`) to mirror for `heartbeat.py`'s tests.
- `scripts/systemd/second-brain-goat-monitor.service` / `.timer` and `second-brain-goat-live-check.service` / `.timer` — the exact unit-file shape to copy for the new weekly timer.
- `scripts/deploy.ps1` (the `$TIMERS` array, ~lines 17-22) — add the new timer name here.

### New Files to Create

- `investments/goat/goat/sp500_universe.py` — Wikipedia S&P 500 constituent scrape + weekly-cached lookup.
- `investments/goat/goat/heartbeat.py` — BBW-squeeze + 50DMA-cross-and-slope combined signal.
- `investments/goat/goat/fundamentals_context.py` — debt/runway/margin/growth/cash-generation informational context + insolvency-risk suppression check.
- `investments/goat/goat/heartbeat_scan.py` — orchestrator (`run_heartbeat_scan`, report render/write functions).
- `scripts/systemd/second-brain-goat-heartbeat-scan.service` — weekly scan unit.
- `scripts/systemd/second-brain-goat-heartbeat-scan.timer` — weekly schedule.
- `investments/goat/goat/tests/test_sp500_universe.py`
- `investments/goat/goat/tests/test_heartbeat.py`
- `investments/goat/goat/tests/test_fundamentals_context.py`
- `investments/goat/goat/tests/test_heartbeat_scan.py`

### Patterns to Follow

**Config constant documentation density**: every new threshold in `config.py` needs a comment block matching the existing style — what it is, where it came from (sourced vs. v1/tunable), and an explicit "v1/tunable, not literature-final" flag for anything not directly citable (see `GOAT_SECTOR_CROSS_RECENCY_DAYS`'s comment as the template).

**Graceful per-ticker degradation**: every existing Goat/my-trader fetch loop wraps each ticker in its own `try/except`, logs `print(f"[goat-...] error ...: {e}")`, and continues — never lets one bad ticker abort the whole run (`monitor.py::run_monitor`, `sector_rotation.fetch_all_sector_closes`, `live_monitor.run_live_monitor` all do this identically). `heartbeat_scan.py`'s per-ticker loop must do the same — at 100-300 tickers/run, at least a few failures are certain.

**CheckResult verdict convention**: `"flag"` = a genuine risk/action-required signal (Phase 1's exit check); `"interesting"` = an opportunity signal, never `"flag"` (Phase 2's `check_sector_breakout`, `opportunity.py`); `"info"`/`"unknown"` = neutral or missing-data. The heartbeat breakout check is an opportunity signal — use `"interesting"`, matching Phase 2 exactly, not `"flag"`.

**Plain-English interpretation clause**: per the "Check interpretation convention" project memory, every check's `detail` text must include what the number *means*, not just the number+threshold (see `macro_indicators.py`'s 2026-08-10 retrofit for the model — e.g. "wider spreads mean credit markets are pricing higher default/recession risk").

---

## IMPLEMENTATION PLAN

### Phase 1: Foundation — config, DB schema, S&P 500 universe

**Tasks:**
- Add every new `GOAT_HEARTBEAT_*`/`GOAT_SP500_*`/`GOAT_CASH_RUNWAY_*` constant to `goat/config.py`, fully documented per the pattern above.
- Add `goat_sp500_constituents` table + CRUD to `goat/db.py`.
- Build `sp500_universe.py`'s scrape + cache-refresh logic.

### Phase 2: Core Implementation — heartbeat detection + fundamentals context

**Tasks:**
- `heartbeat.py`: BBW series, percentile-squeeze detection, ported cross+slope leg, combined `check_heartbeat_breakout()`.
- `fundamentals_context.py`: the 5-factor informational computation + insolvency-risk suppression check.

### Phase 3: Integration — orchestrator, CLI, notifications, deploy

**Tasks:**
- `heartbeat_scan.py`: `run_heartbeat_scan()`, report render/write.
- `main.py`: `scan-heartbeat` subcommand.
- Generalize `monitor.py::maybe_notify()`'s candidate-count parameter.
- New systemd unit + timer; add to `deploy.ps1`'s `$TIMERS`.
- Update `HANDOFF.md`'s status header (same as every prior phase's completion convention).

### Phase 4: Testing & Validation

**Tasks:**
- Unit tests for every new module, mirroring existing Goat test style.
- Live manual validation run against the real DB (Level 4 below).

---

## STEP-BY-STEP TASKS

Execute in order, top to bottom.

### 1. UPDATE `investments/goat/goat/config.py`

- **IMPLEMENT**: Add, in this order, with full doc-comments matching the file's existing density:
  ```python
  # S&P 500 heartbeat scanner, per investments/goat/HANDOFF.md Phase 3. See
  # .agent/plans/goat-phase3-heartbeat-scanner.md's "RESEARCH RESOLVED" section
  # for why BBW-percentile-squeeze was chosen over Minervini's VCP.
  GOAT_HEARTBEAT_HISTORY_LOOKBACK_DAYS = 500  # calendar days -- same margin
                                                 # philosophy as GOLD_MA_HISTORY_LOOKBACK_DAYS
                                                 # (500 calendar days for a 200-day MA in
                                                 # mytrader/config.py); here it must
                                                 # comfortably cover the 252-trading-day BBW
                                                 # percentile lookback below plus the 20-day
                                                 # Bollinger period plus weekday/holiday margin.
  GOAT_HEARTBEAT_BBW_PERIOD_DAYS = 20  # textbook Bollinger default -- same value as
                                          # mytrader.config.GOLD_TA_BOLLINGER_PERIOD_DAYS,
                                          # reused for consistency, not re-derived.
  GOAT_HEARTBEAT_BBW_STD_MULTIPLIER = 2.0  # textbook default -- same value as
                                              # mytrader.config.GOLD_TA_BOLLINGER_STD_MULTIPLIER.
  GOAT_HEARTBEAT_BBW_PERCENTILE_LOOKBACK_DAYS = 252  # ~1 trading year -- the window BBW's
                                                         # own rolling percentile is measured
                                                         # against (self-relative to each
                                                         # ticker's own volatility regime, not
                                                         # a universal fixed %). v1/tunable.
  GOAT_HEARTBEAT_BBW_PERCENTILE = 10  # flag when BBW sits at/below its own trailing
                                         # GOAT_HEARTBEAT_BBW_PERCENTILE_LOOKBACK_DAYS-day
                                         # 10th percentile -- "near a 1-year volatility low".
                                         # v1/tunable, not literature-final, same status as
                                         # GOAT_SECTOR_CROSS_RECENCY_DAYS.
  GOAT_HEARTBEAT_MIN_DURATION_DAYS = 63  # ~3 calendar months of trading days -- matches the
                                            # webinar's own "3 months minimum" and this
                                            # codebase's existing GOAT_SECTOR_RANK_WINDOW_TRADING_DAYS
                                            # precedent for that exact figure.
  GOAT_HEARTBEAT_SQUEEZE_MIN_FRACTION = 0.8  # at least 80% of the trailing
                                                # GOAT_HEARTBEAT_MIN_DURATION_DAYS days must be
                                                # in-squeeze -- the webinar describes "smooth
                                                # up-down-up-down", not a perfectly unbroken
                                                # flat line, so a strict 100%-of-days
                                                # requirement would misfire on ordinary
                                                # single-day noise. v1/tunable.

  # Fundamentals survival context, per HANDOFF.md's debt -> cash runway -> margins ->
  # revenue growth -> cash generation priority order. Informational on every candidate,
  # NOT a pass/fail gate -- confirmed with Shaun 2026-08-17 (gating on all 5 would
  # disqualify almost the entire S&P 500). debt/equity reuses mytrader.config's existing
  # DEBT_TO_EQUITY_FLAG threshold directly, not a new number.
  GOAT_CASH_RUNWAY_FLAG_YEARS = 1.0  # cash-burning companies with less than this many
                                        # years of runway (totalCash / abs(freeCashflow))
                                        # combined with high debt/equity trip the
                                        # insolvency-risk suppression check below --
                                        # 1 year is a conservative, common
                                        # cash-runway-concern floor. v1/tunable.

  GOAT_SP500_WIKI_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
  GOAT_SP500_CACHE_TTL_DAYS = 7  # matches the weekly scan cadence -- no point
                                    # re-scraping Wikipedia more often than the scan itself
                                    # runs.
  GOAT_SP500_USER_AGENT = "Mozilla/5.0 (compatible; SecondBrainGoat/1.0)"

  # GICS Sector (Wikipedia's own column values) -> GOAT_SECTOR_ETFS label mapping.
  # Only "Information Technology" actually differs from GOAT_SECTOR_ETFS's "Technology"
  # -- the rest are written out explicitly anyway so a future Wikipedia label change
  # fails loudly (KeyError on an unmapped sector) rather than silently dropping tickers.
  GOAT_GICS_TO_ETF_SECTOR_LABEL: dict[str, str] = {
      "Information Technology": "Technology",
      "Financials": "Financials",
      "Energy": "Energy",
      "Health Care": "Health Care",
      "Consumer Discretionary": "Consumer Discretionary",
      "Consumer Staples": "Consumer Staples",
      "Industrials": "Industrials",
      "Materials": "Materials",
      "Utilities": "Utilities",
      "Real Estate": "Real Estate",
      "Communication Services": "Communication Services",
  }

  GOAT_HEARTBEAT_CANDIDATES_MD_PATH = GOAT_DIR / "heartbeat-candidates-pending-review.md"
  ```
- **GOTCHA**: `GOAT_HEARTBEAT_BBW_PERCENTILE_LOOKBACK_DAYS` (252 trading days) requires roughly 252/0.69 ≈ 365+ calendar days of raw history just for the percentile window itself, before the 20-day Bollinger warm-up on top — 500 calendar days is comfortable margin, don't shrink it.
- **VALIDATE**: `uv run --directory investments/goat python -c "from goat import config; print(config.GOAT_HEARTBEAT_BBW_PERCENTILE, config.GOAT_GICS_TO_ETF_SECTOR_LABEL['Information Technology'])"`

### 2. UPDATE `investments/goat/goat/db.py`

- **IMPLEMENT**: Add a `goat_sp500_constituents` table to `init_goat_tables()`'s `executescript`:
  ```sql
  CREATE TABLE IF NOT EXISTS goat_sp500_constituents (
      ticker      TEXT PRIMARY KEY,
      security    TEXT NOT NULL,
      gics_sector TEXT NOT NULL,
      fetched_at  TEXT NOT NULL
  );
  ```
  Add matching CRUD: `get_sp500_constituents_fetched_at(conn) -> str | None` (MIN or MAX of `fetched_at`, since the whole table is refreshed atomically — use MAX), `replace_sp500_constituents(conn, rows: list[dict]) -> None` (delete-all-then-insert-all inside one `with conn:` transaction, since this is a full-table cache refresh not an incremental sync), `get_sp500_constituents(conn) -> list[sqlite3.Row]`.
- **PATTERN**: Mirror `init_goat_tables`'s existing `executescript` style (`goat/db.py:15-36`) exactly — same `IF NOT EXISTS`, same trailing semicolons.
- **GOTCHA**: Use a delete-all-then-insert-all replace, not per-row upsert — the constituent list changes membership (additions/removals) between refreshes, and a stale row for a ticker that's dropped out of the index must not linger.
- **VALIDATE**: `uv run --directory investments/goat python -m pytest goat/tests/test_db.py -q`

### 3. CREATE `investments/goat/goat/sp500_universe.py`

- **IMPLEMENT**: `fetch_sp500_constituents() -> list[dict[str, str]] | None` — `requests.get(config.GOAT_SP500_WIKI_URL, headers={"User-Agent": config.GOAT_SP500_USER_AGENT}, timeout=30)`, parse with `BeautifulSoup(html, "html.parser")`, locate the table via `soup.find("table", {"id": "constituents"})` (the well-known id on this specific Wikipedia page), with a fallback to `soup.find("table", {"class": "wikitable"})` if the id lookup ever comes back `None` (defends against the id being renamed without a full outage). For each `<tr>` after the header row, pull `Symbol` / `Security` / `GICS Sector` from the first three `<td>`s' `get_text(strip=True)`. Returns `None` on any fetch/parse failure (network error, empty table, wrong column count), same graceful-degradation contract as `price_history.fetch_close_history`.
  Then `get_or_refresh_sp500_constituents(conn) -> list[sqlite3.Row]` — checks `db.get_sp500_constituents_fetched_at(conn)`; if `None` or older than `config.GOAT_SP500_CACHE_TTL_DAYS` days, calls `fetch_sp500_constituents()` and `db.replace_sp500_constituents(conn, rows)` (each ticker passed through `mytrader.tickers.normalize()` before storing — Wikipedia's raw `Symbol` column uses dots, e.g. `BRK.B`); on scrape failure, falls back to whatever's already cached (even if stale) rather than returning nothing, logging a warning. Then returns `db.get_sp500_constituents(conn)`.
- **PATTERN**: `mytrader/asx_announcements.py:73-100` for the requests+BeautifulSoup direct-fetch style (headers dict, `timeout=30`, try/except returning `None`).
- **IMPORTS**: `requests`, `bs4.BeautifulSoup` (import inside the function body, matching every other yfinance/bs4 import-inside-function convention already used throughout this codebase — e.g. `price_history.py:18`, `asx_announcements.py:93`), `mytrader.tickers`.
- **GOTCHA**: Wikipedia's table markup can and does drift over time — this is real scrape risk with no SLA, unlike yfinance. The stale-cache fallback above is the mitigation; do not let a scrape failure ever leave the heartbeat scan with zero candidates to check when a perfectly good week-old cache exists.
- **VALIDATE**: `uv run --directory investments/goat python -m pytest goat/tests/test_sp500_universe.py -q` (mock `requests.get`/`fetch_sp500_constituents` — no real network call in the test suite, matching `_no_real_price_history_fetch`'s existing "no real yfinance call in tests" philosophy).

### 4. CREATE `investments/goat/goat/heartbeat.py`

- **IMPLEMENT**:
  ```python
  def bollinger_width_series(close: pd.Series) -> pd.Series:
      """Full-history Bollinger Band Width (%) series -- ports gold_technicals.compute_bollinger's
      width_pct formula to a *_series() form (that module's own documented convention),
      needed here because heartbeat detection must look back over the whole trailing window,
      not just today's value."""
      period = config.GOAT_HEARTBEAT_BBW_PERIOD_DAYS
      mid = close.rolling(period).mean()
      std = close.rolling(period).std()
      upper = mid + config.GOAT_HEARTBEAT_BBW_STD_MULTIPLIER * std
      lower = mid - config.GOAT_HEARTBEAT_BBW_STD_MULTIPLIER * std
      return (upper - lower) / mid * 100

  def _is_in_squeeze(bbw: pd.Series) -> pd.Series:
      threshold = bbw.rolling(config.GOAT_HEARTBEAT_BBW_PERCENTILE_LOOKBACK_DAYS).quantile(
          config.GOAT_HEARTBEAT_BBW_PERCENTILE / 100
      )
      return (bbw <= threshold).fillna(False)

  def check_heartbeat_breakout(ticker: str, sector_label: str, close: pd.Series) -> CheckResult:
      ...
  ```
  `check_heartbeat_breakout` combines: (a) squeeze-sustained — over the trailing `GOAT_HEARTBEAT_MIN_DURATION_DAYS` window immediately *before* the most recent breakout crossing (not including today), at least `GOAT_HEARTBEAT_SQUEEZE_MIN_FRACTION` of days were `True` in `_is_in_squeeze`'s output; (b) the same cross+slope leg as `sector_rotation.check_sector_breakout` (port the sign-flip cross-detection block verbatim, using `config.GOAT_SECTOR_MA_SHORT_DAYS`/`GOAT_SECTOR_SLOPE_LOOKBACK_DAYS`/`GOAT_SECTOR_CROSS_RECENCY_DAYS` — these are already generic "50DMA cross+slope, webinar Step 1" constants, not sector-ETF-specific, so reuse them as-is rather than adding stock-specific duplicates). Return `verdict="interesting"` only when both legs pass; `"unknown"` on insufficient history (`len(close) < GOAT_HEARTBEAT_BBW_PERCENTILE_LOOKBACK_DAYS + GOAT_HEARTBEAT_MIN_DURATION_DAYS`, roughly — most S&P 500 constituents will clear this easily, unlike newly-listed names); `"ok"` otherwise. `data` dict includes `bbw_pct` (today's), `squeeze_fraction`, `trading_days_since_cross`, `slope_up` — mirrors `sector_rotation.check_sector_breakout`'s `data` shape.
- **PATTERN**: `sector_rotation.py:53-113` (`check_sector_breakout`) for the cross+slope leg, and `sector_rotation.py:53-56`'s docstring convention ("Flags 'interesting'... matching mytrader/checks/opportunity.py's verdict convention") for this function's own docstring.
- **IMPORTS**: `pandas as pd`, `mytrader.checks.CheckResult`, `from . import config`.
- **GOTCHA**: `.rolling(...).quantile(...)` on a series shorter than the rolling window returns `NaN`, not an error — `_is_in_squeeze`'s `.fillna(False)` handles this so early-history NaN rows never count as "in squeeze" by accident (would otherwise silently inflate the squeeze fraction for tickers near the edge of their available history).
- **GOTCHA**: Don't duplicate `sector_rotation.check_sector_breakout`'s cross-detection logic by *importing* it and reusing internals — Phase 2's function is tailored to its own ETF-specific detail-text wording and is already shipped/tested; port a second, independent copy into `heartbeat.py` instead. This mirrors the codebase's own already-accepted precedent (`macro_indicators.check_gold_trend()` and `sector_rotation.check_sector_breakout()` independently implement the identical sign-flip idiom — see `macro_indicators.py`'s own docstring, lines 8-11, explicitly calling this an accepted tradeoff, not a bug to fix). Do NOT refactor `sector_rotation.py` as part of this phase.
- **VALIDATE**: `uv run --directory investments/goat python -m pytest goat/tests/test_heartbeat.py -q`

### 5. CREATE `investments/goat/goat/fundamentals_context.py`

- **IMPLEMENT**: `compute_survival_context(ticker: str, data) -> dict` where `data` is a `mytrader.market_data.TickerData` (or `None`). Pulls, in the webinar's own priority order:
  - `debt_to_equity = data.info.get("debtToEquity")` — falls back to `mytrader.market_data.fetch_balance_sheet_financials(ticker)` when `None`, same pattern `checks/balance_sheet.py:56-59` already uses.
  - `total_cash = data.info.get("totalCash")`, `free_cashflow = data.info.get("freeCashflow")`; `cash_runway_years = total_cash / abs(free_cashflow)` only when both are present and `free_cashflow < 0` (cash-burning) — otherwise `None`, annotated in the summary text as `"N/A — cash generative"` rather than a missing-data gap, per the webinar's own framing that runway "mainly" matters for cash-burning companies.
  - `gross_margin = data.info.get("grossMargins")`, `operating_margin = data.info.get("operatingMargins")` — reported as a plain percentage in the summary, no threshold judgement (webinar just says "is it ok?" with no number).
  - `revenue_growth = data.info.get("revenueGrowth")` — reported as positive/negative, no magnitude threshold (webinar gives none).
  - `cash_generating = (data.info.get("operatingCashflow") or 0) > 0`.
  - `insolvency_risk = bool(debt_to_equity is not None and debt_to_equity >= mytrader_config.DEBT_TO_EQUITY_FLAG and cash_runway_years is not None and cash_runway_years < config.GOAT_CASH_RUNWAY_FLAG_YEARS)`.
  - `summary: str` — one plain-English sentence combining all of the above (e.g. `"debt/equity 45.2 (below flag threshold), cash-generative (no runway concern), gross margin 42.1%, revenue growth +8.1% YoY"`), following the "Check interpretation convention" project memory.
  Returns `{"debt_to_equity": ..., "cash_runway_years": ..., "gross_margin": ..., "operating_margin": ..., "revenue_growth": ..., "cash_generating": ..., "insolvency_risk": ..., "summary": ...}`. Every field is `None`-safe — a ticker with a totally empty `.info` still returns a dict with `insolvency_risk=False` (fields all `None`/unknown does not, by itself, indicate insolvency risk — that would be a false-positive-suppression bug, not a safe default) and a summary noting what's unavailable.
- **PATTERN**: `checks/balance_sheet.py:46-86` for the `.info`-then-statement-fallback shape and the "derived from balance sheet/income statement" caveat-note convention (line 68-72) — reuse the same caveat phrasing whenever `fetch_balance_sheet_financials` supplied a derived number.
- **IMPORTS**: `from mytrader import config as mytrader_config, market_data`, `from . import config`.
- **GOTCHA**: `mytrader.config.DEBT_TO_EQUITY_FLAG` is `150.0` in the same *percent-of-equity* units yfinance's raw `debtToEquity` field uses (already confirmed by `checks/balance_sheet.py`'s existing usage) — do not accidentally compare against a 0-1 fraction.
- **VALIDATE**: `uv run --directory investments/goat python -m pytest goat/tests/test_fundamentals_context.py -q`

### 6. CREATE `investments/goat/goat/heartbeat_scan.py`

- **IMPLEMENT**: `run_heartbeat_scan(conn: sqlite3.Connection) -> dict[str, Any]`:
  1. `sector_closes = sector_rotation.fetch_all_sector_closes()`; `ranking = sector_rotation.rank_sectors(sector_closes)` — recomputed fresh (cheap, 11 tickers), not read from a stale `sector-ranking.md`.
  2. `rising_etf_labels = {row["sector_label"] for row in ranking if row["rising"]}`.
  3. `constituents = sp500_universe.get_or_refresh_sp500_constituents(conn)`.
  4. Filter to `[c for c in constituents if config.GOAT_GICS_TO_ETF_SECTOR_LABEL.get(c["gics_sector"]) in rising_etf_labels]` — log (don't crash on) any `gics_sector` value missing from the map, since an unmapped sector should surface loudly rather than silently drop tickers (per the config comment above).
  5. For each filtered ticker (own `try/except`, matching the graceful-degradation pattern everywhere else): `close = price_history.fetch_close_history(ticker, config.GOAT_HEARTBEAT_HISTORY_LOOKBACK_DAYS)`; skip on `None`. `check = heartbeat.check_heartbeat_breakout(ticker, sector_label, close)`; skip unless `check.verdict == "interesting"`. Then `data = market_data.fetch_ticker_data(ticker)`; `context = fundamentals_context.compute_survival_context(ticker, data)`; skip staging (but still count as "scanned") if `context["insolvency_risk"]` is `True`.
  6. Three-way dedup + stage, mirroring `monitor.py::_stage_new_sector_candidates` exactly (not-a-holding, not-a-watchlist-row, not-already-pending) — `db.insert_goat_pending_candidate(conn, ticker=ticker, sector_label=sector_label, signal_detail=f"{check.detail}; survival context: {context['summary']}", source="goat_heartbeat_scan")`.
  7. Returns `{"scanned": n, "rising_sectors": sorted(rising_etf_labels), "new_candidates": [...], "pending_candidates": [dict(r) for r in db.get_all_goat_pending_candidates(conn) if r["source"] == "goat_heartbeat_scan"]}`.
  Plus `render_heartbeat_candidates_report(result) -> str` / `write_heartbeat_candidates_report(result) -> None`, styled after `monitor.render_sector_candidates_report`/`write_sector_candidates_report` (`monitor.py:211-236`), writing to `config.GOAT_HEARTBEAT_CANDIDATES_MD_PATH`, with a header line stating how many tickers were scanned across which rising sectors (matches the "decision-support report standard" project memory — every report needs enough context to act, not just a bare table).
- **PATTERN**: `monitor.py:138-182` (`_stage_new_sector_candidates`, `run_sector_scan`) is the direct template for steps 6-7; `monitor.py:211-236` for the report render/write pair.
- **IMPORTS**: `sqlite3`, `from typing import Any`, `from mytrader import db as mt_db, market_data`, `from . import config, db, fundamentals_context, heartbeat, price_history, sector_rotation, sp500_universe`.
- **GOTCHA**: This loop can run 100-300 individual yfinance fetches (close history + `.info`) in a single weekly run — materially more than any existing Goat/my-trader loop. Do not add `market_data.cached_session()` here (it caches by ticker for the duration of one run, but every ticker here is fetched exactly once anyway, so it buys nothing) — just make sure the per-ticker `try/except` genuinely isolates failures, since a rate-limit or transient block partway through must not lose already-found candidates from earlier in the loop.
- **VALIDATE**: `uv run --directory investments/goat python -m pytest goat/tests/test_heartbeat_scan.py -q`

### 7. UPDATE `investments/goat/goat/monitor.py`

- **IMPLEMENT**: Generalize `maybe_notify`'s second parameter from `new_sector_candidates: int = 0` to `new_candidates: int = 0` (rename only — the body already just adds it into the same `parts`/`summary` construction, no behavior change). Update `main.py::cmd_monitor`'s existing call site (`maybe_notify(result, new_sector_candidates=len(sector_result["new_candidates"]))` → `maybe_notify(result, new_candidates=len(sector_result["new_candidates"]))`).
- **PATTERN**: `monitor.py:109-135`.
- **GOTCHA**: This is a rename-only change to an already-shipped, tested function — do not change its `n_alerts`/`parts`/WhatsApp-message construction logic at all, just the parameter name and its one internal reference.
- **VALIDATE**: `uv run --directory investments/goat python -m pytest goat/tests/test_monitor.py -q`

### 8. UPDATE `investments/goat/goat/main.py`

- **IMPLEMENT**: Add `cmd_scan_heartbeat(args)`:
  ```python
  def cmd_scan_heartbeat(args) -> None:
      from .heartbeat_scan import run_heartbeat_scan, write_heartbeat_candidates_report
      from .monitor import maybe_notify

      conn = _open_conn()
      result = run_heartbeat_scan(conn)
      conn.close()
      write_heartbeat_candidates_report(result)
      maybe_notify({"new_alerts": []}, new_candidates=len(result["new_candidates"]))
      print(
          f"Heartbeat scan complete: scanned {result['scanned']} ticker(s) across "
          f"{len(result['rising_sectors'])} rising sector(s), "
          f"{len(result['new_candidates'])} new candidate(s). "
          f"See investments/goat/heartbeat-candidates-pending-review.md"
      )
  ```
  Register `subparsers.add_parser("scan-heartbeat", help="On-demand S&P 500 heartbeat-pattern scan within currently-rising sectors")` and add `"scan-heartbeat": cmd_scan_heartbeat` to the `dispatch` dict. Do **not** wire this into `cmd_monitor` — HANDOFF.md's resolved cadence is weekly-plus-on-demand, distinct from the daily `monitor` command, same Monitor/Find-style split already used for `scan-sectors`.
- **PATTERN**: `main.py:62-74` (`cmd_scan_sectors`) is the closest existing template.
- **VALIDATE**: `uv run --directory investments/goat python -m goat.main scan-heartbeat` (real run against the live DB — expect this to take a while and make ~100-300 real yfinance calls; this doubles as Level 4 manual validation, see below).

### 9. CREATE `scripts/systemd/second-brain-goat-heartbeat-scan.service`

- **IMPLEMENT**:
  ```ini
  [Unit]
  Description=Goat Heartbeat Scan
  After=network.target

  [Service]
  Type=oneshot
  User=secondbrain
  WorkingDirectory=/home/secondbrain/second-brain/investments/goat
  ExecStart=/home/secondbrain/second-brain/investments/.venv/bin/python -m goat.main scan-heartbeat
  StandardOutput=append:/home/secondbrain/second-brain/investments/goat/heartbeat_scan_runs.log
  StandardError=append:/home/secondbrain/second-brain/investments/goat/heartbeat_scan_runs.log
  ```
- **PATTERN**: `scripts/systemd/second-brain-goat-monitor.service` verbatim structure.
- **VALIDATE**: N/A until deployed (see Level 4).

### 10. CREATE `scripts/systemd/second-brain-goat-heartbeat-scan.timer`

- **IMPLEMENT**:
  ```ini
  [Unit]
  Description=Goat Heartbeat Scan Timer
  Requires=second-brain-goat-heartbeat-scan.service

  [Timer]
  OnCalendar=Sun *-*-* 22:00:00 UTC
  Persistent=true

  [Install]
  WantedBy=timers.target
  ```
- **PATTERN**: `scripts/systemd/second-brain-goat-monitor.timer`. Sunday 22:00 UTC (08:00 AEST Monday) chosen to run after the weekend, ahead of Monday's market open and clear of the daily 21:35 UTC monitor/live-check timers.
- **GOTCHA**: Same as every prior Goat rollout — **do not enable this timer** as part of implementation. It ships disabled; enabling on the VPS needs Shaun's explicit go-ahead, same as Phase 1's original rollout and the intraday live-check timer.

### 11. UPDATE `scripts/deploy.ps1`

- **IMPLEMENT**: Add `"second-brain-goat-heartbeat-scan.timer"` to the `$TIMERS` array (~line 17-22), alongside the existing three entries.
- **VALIDATE**: Manual review only — this script isn't run as part of implementation (deploy is a separate, explicit step).

### 12. UPDATE `investments/goat/HANDOFF.md`

- **IMPLEMENT**: Update the status header (line 3) to record Phase 3 complete, matching the exact style of the existing Phase 1/Phase 2/intraday-alerting completion notes (test count, what was validated live, systemd-not-enabled caveat).
- **VALIDATE**: N/A (documentation only).

### 13. CREATE test files

- `test_sp500_universe.py` — mock `requests.get` returning a small fixed HTML snippet with a `<table id="constituents">` containing 3-4 known rows (including one with a dot ticker like `BRK.B`, to verify `tickers.normalize()` gets applied); test the TTL-refresh logic with a monkeypatched `db.get_sp500_constituents_fetched_at` returning both a fresh and a stale timestamp; test the stale-cache fallback when `fetch_sp500_constituents()` returns `None`.
- `test_heartbeat.py` — mirror `test_sector_rotation.py`'s `_dates`/`_flat_then_move`/`_series_with_cross`-style builders. Cases: (a) a genuinely flat-then-tight-then-breakout series flags `"interesting"`; (b) a series with normal (non-squeezed) volatility before a 50DMA cross does NOT flag, even though the cross+slope leg alone would have passed under Phase 2's logic — this is the key regression test proving the heartbeat leg is actually gating, not a no-op; (c) insufficient history returns `"unknown"`; (d) a squeeze that's real but stale (cross happened long before `GOAT_SECTOR_CROSS_RECENCY_DAYS` ago) stays `"ok"`.
- `test_fundamentals_context.py` — mirror `checks/test_checks_balance_sheet.py`'s style for the `.info`-fallback-to-statements case. Cases: (a) normal profitable company → `insolvency_risk=False`, correct summary text; (b) cash-burning company with short runway AND high debt/equity → `insolvency_risk=True`; (c) cash-burning but low debt/equity → `insolvency_risk=False` (only the AND-combination suppresses); (d) cash-generative company → `cash_runway_years is None`, summary says "cash generative" not "unavailable"; (e) totally empty `.info` → all fields `None`/safe defaults, `insolvency_risk=False` (never defaults to a false positive).
- `test_heartbeat_scan.py` — mirror `test_monitor.py`'s style for `run_sector_scan`/`_stage_new_sector_candidates`. Cases: (a) end-to-end with monkeypatched `sector_rotation.rank_sectors`, `sp500_universe.get_or_refresh_sp500_constituents`, `price_history.fetch_close_history`, `market_data.fetch_ticker_data` — confirms a ticker in a rising sector with a real heartbeat signal gets staged with source `"goat_heartbeat_scan"`; (b) a ticker in a non-rising sector is filtered out before any fetch happens (assert the mocked fetch was never called for it — proves the sector filter, not just the dedup, is doing real work); (c) three-way dedup (already holding/watchlist/pending) skips staging, same assertions as the existing `_stage_new_sector_candidates` tests; (d) `insolvency_risk=True` suppresses staging even though the technical signal fired.
- **VALIDATE**: `uv run --directory investments/goat python -m pytest goat/tests -q` (full suite, expect 61 existing + new tests all passing).

---

## TESTING STRATEGY

### Unit Tests

Every new pure-computation function (`bollinger_width_series`, `_is_in_squeeze`, `check_heartbeat_breakout`, `compute_survival_context`) gets deterministic `pandas.Series`/dict-input tests with zero network calls, same discipline as every existing Goat test. `sp500_universe`/`heartbeat_scan`'s I/O-touching functions get fully mocked network/DB boundaries — no test in this suite makes a real HTTP or yfinance call, matching `conftest.py`'s existing `_no_real_price_history_fetch` philosophy (extend `conftest.py` with an equivalent autouse stub for `sp500_universe.fetch_sp500_constituents` if useful, or stub per-test — reviewer's call during implementation).

### Integration Tests

`test_heartbeat_scan.py`'s end-to-end cases are the integration layer here — full `run_heartbeat_scan()` against a real (test) SQLite connection with every external boundary (yfinance, Wikipedia, sector ranking) mocked, but real DB reads/writes through `goat.db`/`mytrader.db`.

### Edge Cases

- A ticker whose `gics_sector` value from Wikipedia doesn't match any key in `GOAT_GICS_TO_ETF_SECTOR_LABEL` (label drift) — must log and skip, not crash the whole scan.
- A newly-IPO'd S&P 500 constituent with under a year of price history — `check_heartbeat_breakout` returns `"unknown"`, never a false "interesting".
- Zero rising sectors this run (Phase 2 ranking finds nothing rising) — `run_heartbeat_scan` scans zero tickers and returns cleanly, doesn't error.
- Wikipedia scrape fails on a week where the cache is also empty (first-ever run before any successful scrape) — `sp500_universe` must degrade to an empty list, not `None`/crash, so `run_heartbeat_scan` still completes (scanning zero tickers) rather than blowing up the whole weekly job.

---

## VALIDATION COMMANDS

### Level 1: Syntax & Style
```powershell
uv run --directory investments/goat ruff check goat
uv run --directory investments/goat mypy goat
```

### Level 2: Unit Tests
```powershell
uv run --directory investments/goat python -m pytest goat/tests -q
```

### Level 3: Integration Tests
Covered by Level 2 (`test_heartbeat_scan.py`'s end-to-end cases) — no separate integration suite exists in this workspace.

### Level 4: Manual Validation
```powershell
# Real run against the live shared DB -- expect ~100-300 real yfinance calls,
# will take several minutes. Confirms: Wikipedia scrape succeeds against real
# markup, sector filter narrows to a sane ticker count, at least review whatever
# candidates (if any) get staged for plausibility against a real chart.
uv run --directory investments/goat python -m goat.main scan-heartbeat

# Confirm promote/dismiss work unchanged for a source="goat_heartbeat_scan" row
# (they're already source-agnostic, but this phase never explicitly validated it):
uv run --directory investments/goat python -m goat.main promote-candidate --ticker <TICKER> --asset-type stock
uv run --directory investments/goat python -m goat.main dismiss-candidate --ticker <TICKER>
```
Also visually sanity-check any real candidate that fires against a live chart (same spirit as HANDOFF.md's own reference-chart validation for the original heartbeat-pattern definition) — does the flagged consolidation genuinely look like a heartbeat, not just numerically satisfy the formula.

### Level 5: Additional Validation
N/A.

---

## ACCEPTANCE CRITERIA

- [ ] `scan-heartbeat` runs end-to-end against the real DB, scrapes real S&P 500 data, filters to genuinely rising sectors, and completes without crashing on individual ticker failures
- [ ] Heartbeat detection combines both legs (BBW squeeze + fresh cross/slope) — a series with only one leg passing does not flag `"interesting"` (proven by `test_heartbeat.py`'s regression case)
- [ ] Fundamentals context is informational on every candidate; only the debt+runway insolvency-risk combination suppresses staging
- [ ] `goat_pending_candidates` reused as-is (no schema change), `source="goat_heartbeat_scan"` distinguishes Phase 3 rows from Phase 2's
- [ ] `promote-candidate`/`dismiss-candidate` confirmed working unchanged for heartbeat-sourced candidates
- [ ] All new/updated code ruff + mypy clean
- [ ] Full test suite passes (existing 61 + new tests)
- [ ] No changes to any `my-trader/` `.py` file
- [ ] systemd units created but NOT enabled on the VPS
- [ ] `HANDOFF.md` status header updated

---

## COMPLETION CHECKLIST

- [ ] All 13 tasks completed in order
- [ ] Each task's validation command passed immediately after that task
- [ ] Full `investments/goat` test suite passes
- [ ] ruff + mypy clean
- [ ] Level 4 manual run completed against the real DB and reviewed for plausibility
- [ ] `deploy.ps1` updated (not run)
- [ ] `HANDOFF.md` updated

---

## NOTES

**Why BBW-percentile over VCP** — see "RESEARCH RESOLVED" section above; this was a real, sourced research pass, not a coin-flip, and should not be revisited without equally real justification (e.g. a manual validation run showing BBW-squeeze is producing obviously wrong candidates against real charts).

**Why fundamentals are informational, not gating** — confirmed directly with Shaun 2026-08-17. If this is ever revisited, the natural next step is *not* "add 5 hard gates" but something more like opportunity.py's confluence framing (N-of-5 factors favorable = stronger candidate), which preserves the "surface, don't auto-disqualify" philosophy while still differentiating candidates.

**Why `heartbeat.py` ports rather than imports `sector_rotation.check_sector_breakout`'s internals** — deliberate, matches this codebase's own already-accepted duplication precedent (see Task 4's second GOTCHA). If a third near-identical copy of the sign-flip cross-detection idiom ever appears in a future phase, that's the point to reconsider extracting a shared helper — not now, and not as a side effect of this phase.

**Performance/cost consideration** — this phase's weekly fetch volume (100-300 tickers) is an order of magnitude larger than anything else in Goat or my-trader's existing scheduled jobs. If this turns out to be slow or yfinance starts rate-limiting under the load, the mitigation is narrowing `GOAT_GICS_TO_ETF_SECTOR_LABEL`'s effective scope (fewer rising sectors happens naturally already) before reaching for anything more complex (batched/threaded fetching, etc.) — not scoped here, flag to Shaun if Level 4 validation shows this is a real problem.

**Explicitly deferred (do not build as part of this phase)** — VCP-style pivot/swing-detection as an alternative or additional pattern leg; any change to Phase 1/2's cadence or thresholds; a shared `ma_cross.py` refactor; batched/parallel yfinance fetching; a market-holiday calendar (same deferral as the rest of Goat).
