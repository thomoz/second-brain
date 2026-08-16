# Feature: Goat — Intraday 150DMA Alerting

The following plan should be complete, but it's important that you validate documentation and codebase patterns and task sanity before you start implementing.

Pay special attention to naming of existing utils, types, and models. Import from the right files etc.

This plan covers the **"Intraday 150DMA Alerting" cross-cutting item** from `investments/goat/HANDOFF.md` (lines 184-227) — explicitly *not* a new numbered phase, but a timing change layered on top of the already-shipped, already-live Phase 1 daily exit check (`goat/exit_check.py` + `goat/monitor.py`, systemd timer active on the VPS since 2026-08-16). Phase 2 (sector rotation) also shipped and is out of scope here. Phase 3 (heartbeat scanner) is unplanned and out of scope here.

## Feature Description

Goat's Phase 1 exit check already tells Shaun when a holding has closed below its 150-day moving average — but only once daily, at 21:35 UTC (07:35 AEST), after both the ASX and (that trading day's) US session have fully closed. Shaun explicitly wants to know **the moment** a holding's live price crosses below its 150DMA while the relevant market is still open, not the next morning. This feature adds a second, high-frequency check (`check-live`) that runs every few minutes during market hours, fetches each open-market holding's *live* quote (not a completed daily close), and compares it against the same 150-day MA the daily check already computes — reusing the exact same alert/dedup machinery so the two checks never double-alert for the same event.

## User Story

As Shaun, holding both ASX-listed and US-listed positions and following Goat's own "the exit matters most" rule
I want a WhatsApp alert within minutes of a holding's live price crossing below its 150-day MA, whichever market that holding trades on and whatever time of day that happens
So that I can act on the exit rule the same day it fires, instead of finding out at next morning's batch summary

## Problem Statement

The daily monitor (`goat/monitor.py:run_monitor`) is correct but too slow for Shaun's stated need — it evaluates the 150DMA exit rule exactly once per day, after markets close, against that day's final close price. Between "the price actually crosses" and "Shaun finds out," there can be up to a full trading day (or more, across a weekend) of delay on a rule Shaun has explicitly prioritized as the most important one in the whole framework ("the exit matters most").

## Solution Statement

Add a new `goat/market_hours.py` module that answers "is the ASX open right now?" / "is the US market open right now?" using `zoneinfo`-based local-time windows (no market-holiday calendar — deliberately out of scope, see NOTES). Add `exit_check.check_150dma_exit_live()`, a live-quote variant of the existing daily check that keeps the 150-day MA computed from **completed** daily closes only (never from the live price itself — this preserves HANDOFF's explicit design decision that the MA is not live-updating) while comparing that MA against a live price. Add `goat/live_monitor.py::run_live_monitor()`, an orchestrator that: filters my-trader's holdings down to whichever ones' market is currently open (classified from the ticker's own `.AX`-suffix convention, already used consistently in real holdings data — no new DB column needed), fetches each one's live quote via my-trader's existing `market_data.fetch_current_price()`, runs the live check, and reconciles alerts through the **same** `goat_alert_history` dedup table and `check_name` (`"below_150dma"`) the daily check already uses — so whichever check (live or EOD) sees the crossing first creates the one alert, and the other one runs into the existing open-alert dedup and stays quiet. A new `check-live` CLI subcommand + systemd service/timer (firing every `GOAT_LIVE_POLL_INTERVAL_MINUTES` minutes, 24/7, with the actual market-hours gating done in Python rather than brittle DST-aware systemd calendar syntax) wires it into the same deploy/timer-management flow the daily monitor already uses.

## Feature Metadata

**Feature Type**: Enhancement (extends the already-shipped Phase 1 exit check with a second, higher-frequency check path — no new workspace member, no new sibling package)
**Estimated Complexity**: Medium — the live-check math is a careful but mechanical variant of existing logic; the two things that need real care are (a) not letting the live price contaminate the 150-day MA itself, and (b) making sure the shared dedup logic between the daily and live checks is reused, not re-implemented, so they can never double-alert.
**Primary Systems Affected**: `investments/goat/goat/` (new `market_hours.py`, `live_monitor.py`; extended `exit_check.py`, `main.py`); `scripts/systemd/` (two new unit files); `scripts/deploy.ps1` (new timer added to the managed list). No changes to `my-trader/`, no new DB tables (reuses `goat_alert_history` as-is), no changes to Phase 2/3 scope.
**Dependencies**: None beyond what Phase 1 already added (`yfinance`, `pandas`, `mytrader` workspace dependency, Python 3.12 stdlib `zoneinfo`).

---

## OPEN QUESTIONS RESOLVED DURING THIS PLANNING SESSION (2026-08-16) — BINDING

HANDOFF.md's "Open design questions" section (numbered 1-6) is answered here; do not re-litigate during implementation:

1. **Live price source** → reuse `mytrader.market_data.fetch_current_price(ticker) -> float | None` **as-is, unmodified**. It already exists, is already used live in `mytrader/monitor.py` and `mytrader/snapshot.py` for every holding's P&L column, and already does the `.info.get("regularMarketPrice") or .info.get("currentPrice")` lookup plus the ASX `.AX` fallback internally (via `market_data.fetch_ticker_data`). No new yfinance research needed — this is a proven, already-live pattern, not a new integration.
2. **Polling cadence** → `GOAT_LIVE_POLL_INTERVAL_MINUTES = 10` as the v1 default (new `goat/config.py` constant, tunable). Rationale: the existing 30-minute heartbeat timer (`scripts/systemd/second-brain-heartbeat.timer`, `OnCalendar=*:0/30`) is this repo's only precedent for a recurring sub-daily timer; 10 minutes is deliberately tighter than that precedent to honor Shaun's explicit "AS SOON AS IT DROPS" urgency, while each individual run is cheap (only the tickers whose market is *currently open* get fetched — typically a handful, not all holdings) so the tighter cadence doesn't multiply cost the way it would if every run checked every holding. Flagged as v1/tunable, not literature-final, same discipline as every other threshold in this codebase (see `config.py`'s existing comment style).
3. **Two separate market-hours windows** → resolved by ticker-suffix classification, not a new DB column. Real holdings data (`investments/my-trader/holdings.md`, confirmed by inspection 2026-08-16) already stores ASX-listed tickers with an explicit `.AX` suffix (e.g. `GGOV.AX`) and US-listed tickers bare (e.g. `AG`, `LULU`, `V`) — this is the exact same convention `mytrader.tickers.asx_variant()`/`price_history.fetch_close_history`'s fallback logic already assumes. `market_hours.classify_market(ticker)` just checks `ticker.strip().upper().endswith(".AX")`. `run_live_monitor()` only fetches/checks ASX-suffixed holdings when `is_asx_open()` is true, and only non-`.AX` holdings when `is_us_market_open()` is true — both can be true or false independently (they never overlap in AEST/AEDT: ASX 10:00-16:00 Sydney local vs. US 9:30am-4:00pm ET, which is Sydney nighttime).
4. **What "crosses" means against a live price** → the 150-day MA is **always** computed from completed daily closes only, never from the live price — matches HANDOFF's design decision #4 exactly. See `check_150dma_exit_live()` in Task section below for the precise mechanism (and the GOTCHA about why simply appending the live price to the existing series and calling `check_150dma_exit()` unmodified would be *wrong*).
5. **Dedup/re-alert behavior at higher cadence** → confirmed to hold **by construction**, not by new logic: the live check reuses the exact same `(ticker, source_table="holdings", check_name="below_150dma")` dedup key as the daily check (see `monitor.py`'s `_reconcile_alerts`, renamed `reconcile_alerts` — see Task 1 below — and imported directly into `live_monitor.py`). Whichever check observes the crossing first creates the one open alert; every later check (live or daily, same day or later) sees `get_open_goat_alert(...) is not None` and stays quiet, exactly like two daily runs in a row already do today (`test_run_monitor_stays_quiet_on_repeat_flag`).
6. **Cost/reliability under frequent polling** → no new backoff/retry infrastructure. Reuse the exact per-ticker `try/except: print(...); continue` resilience idiom already in `monitor.py::run_monitor` (lines 49-58) — a single ticker's yfinance failure never aborts the run. If real rate-limiting is observed post-deploy, that's a follow-up, not something to build speculatively now (matches this repo's "don't build for hypothetical future requirements" convention).

**Not scoped here** (per HANDOFF.md's own line, restated): no change to Phase 2 (sector rotation) or Phase 3 (heartbeat scanner) cadence. `run_live_monitor()` does not touch `sector-ranking.md`, `sector-candidates-pending-review.md`, or `monitor-report.md` — those stay exclusively the daily `monitor` command's responsibility.

---

## CONTEXT REFERENCES

### Relevant Codebase Files — READ THESE BEFORE IMPLEMENTING

- `investments/goat/HANDOFF.md` (full file, esp. lines 184-227) — Why: the source design doc this plan implements; also read lines 79-93 ("Reuse vs. standalone") for the DB-co-location and Goat-never-writes-into-my-trader's-tables rules this feature must keep respecting (it doesn't touch `holdings`/`watchlist` at all, only reads `holdings` and writes `goat_alert_history`, both already-established patterns).
- `investments/goat/goat/exit_check.py` (full file, 64 lines) — Why: `check_150dma_exit(ticker, close: pd.Series) -> CheckResult` is the function this plan adds a live-quote sibling to. Read the whole file, especially the `data={"pct_below", "ma", "price"}` shape (the live variant's `CheckResult.data` must match this shape so any future code treating the two interchangeably doesn't break) and the "Deliberately separates the magnitude... from the duration..." comment (lines 40-47) explaining why `pct_below` and the consecutive-day count are computed as two separate things — the live variant must preserve that same separation.
- `investments/goat/goat/config.py` (full file, 85 lines) — Why: append new constants here (Task 2 below), following the exact citation/rationale comment style already established for `GOAT_150DMA_FLAG_PCT` etc. (lines 12-41) — every threshold in this file has a "why this number" comment; the new `GOAT_LIVE_POLL_INTERVAL_MINUTES` and market-hours-window constants must too.
- `investments/goat/goat/monitor.py` (full file, 233 lines) — Why: (a) `_reconcile_alerts` (lines 21-39) is the dedup logic this plan's `live_monitor.py` must reuse, not duplicate — see Task 1 below for the rename-to-public decision and why. (b) `run_monitor` (lines 42-64)'s per-ticker `try/except: print(...); continue` shape (lines 49-58) is the exact resilience idiom `run_live_monitor` must copy. (c) `maybe_notify` (lines 105-131) is reused **as-is, unmodified** — it only needs a dict with a `"new_alerts"` key shaped like `_reconcile_alerts`'s return, which `run_live_monitor`'s result dict will provide.
- `investments/goat/goat/db.py` (full file, 109 lines) — Why: `get_open_goat_alert`, `insert_goat_alert`, `acknowledge_goat_alert`, `get_open_goat_alerts` (lines 39-75) are reused **as-is, unmodified** via `reconcile_alerts` — no schema change, no new table, no new CRUD function needed for this feature.
- `investments/goat/goat/price_history.py` (full file, 33 lines) — Why: `fetch_close_history(ticker, lookback_days) -> pd.Series | None` is reused as-is for the historical-MA leg of the live check. Note its tz-handling (`close.index = close.index.tz_localize(None)` at line 30) — the new `_completed_closes_only` helper (Task 3) must account for this: `close.index` is tz-naive after this function returns, so "is the last row's date == today" must be computed by comparing `.date()` against a tz-aware `datetime.now(ZoneInfo(...))` `.date()`, not by comparing tz-aware objects directly.
- `investments/my-trader/mytrader/market_data.py` (full file, 158 lines, esp. `fetch_current_price` lines 86-95 and `fetch_ticker_data`/`_fetch_one` lines 52-84) — Why: `fetch_current_price(ticker) -> float | None` is reused directly (`from mytrader import market_data`) — confirms it already handles the `.AX` fallback internally via `tickers.asx_variant`, so `live_monitor.py` never needs to guess/retry ticker variants itself, it just passes the holdings-table ticker straight through (which for ASX rows already carries the `.AX` suffix — see resolved question 3 above).
- `investments/my-trader/mytrader/tickers.py` (full file, 15 lines) — Why: `normalize()`/`asx_variant()` — confirms `normalize()` only maps `BRK.B`/`BRK.A` share-class quirks and does **not** strip an existing `.AX` suffix, so `market_hours.classify_market()`'s plain `.endswith(".AX")` check on the raw holdings-table ticker is safe and matches how `market_data`/`price_history` already treat these tickers.
- `investments/my-trader/mytrader/db.py` (lines 30-44, `holdings` schema; lines 179-184ish, `get_all_holdings`) — Why: confirms the `holdings` table has no exchange/market column — `classify_market()`'s ticker-suffix approach is the only signal available and is the correct one (matches real production data, not a guess).
- `investments/my-trader/holdings.md` (full file, 16 lines, current real data 2026-08-16) — Why: ground truth confirming the `.AX`-suffix convention (`GGOV.AX` vs. bare `AG`/`LULU`/`V`/`LLY`/`LYV`/`ETPMAG`/`OOO`) — read this before writing `classify_market()` so its test fixtures use realistic tickers.
- `investments/goat/goat/main.py` (full file, 140 lines) — Why: `_open_conn()` (lines 8-19) and the argparse subparser dispatch-dict shape (lines 103-136) — add `check-live` here following the exact shape `monitor`/`scan-sectors` already use (no arguments needed, same as `monitor`).
- `.claude/scripts/notifications.py` (full file, 46 lines) — Why: `send_whatsapp_notification(message: str) -> bool` — confirms the exact signature `maybe_notify` (reused unmodified) already calls; no change needed here, just context for why `maybe_notify` works unmodified for the live path too.
- `investments/goat/goat/tests/conftest.py` (full file, 42 lines) — Why: the `db_conn` fixture and the autouse `_no_real_price_history_fetch` fixture (lines 35-42) that globally stubs `goat.price_history.fetch_close_history` to return `None` by default — new live-check tests inherit this for free and must override both `goat.price_history.fetch_close_history` **and** a new stub for `mytrader.market_data.fetch_current_price` per-test via `monkeypatch`, mirroring `test_monitor.py`'s per-ticker-branching `_fake_fetch` idiom (see next reference).
- `investments/goat/goat/tests/test_exit_check.py` (full file, 81 lines) — Why: `_flat_then()`/`_dates()` helpers and the boundary-condition test style (`test_flags_at_the_threshold_boundary_using_gte_not_gt`) — the new `check_150dma_exit_live` tests go in this same file, reusing `_flat_then()` unmodified (it builds a pure historical series, which is exactly what the live check's `close` parameter needs — the live price is a separate, explicit argument, not part of the series).
- `investments/goat/goat/tests/test_monitor.py` (full file, 295 lines) — Why: `_seed_holding()` (lines 30-34) and `_flagging_series()`/`_non_flagging_series()` (lines 16-27) are directly reusable for `test_live_monitor.py`; also confirms the `db_conn`/`monkeypatch` fixture-injection pattern this project always uses instead of mocking frameworks.
- `scripts/systemd/second-brain-goat-monitor.service` and `.timer` (both full files) — Why: the exact oneshot-service + calendar-timer shape to mirror for the two new unit files (Task 6 below) — same `WorkingDirectory`, same venv path, same log-append pattern, different `ExecStart` subcommand and a very different `[Timer]` block (frequent interval instead of once daily).
- `scripts/systemd/second-brain-heartbeat.timer` (full file, 11 lines) — Why: `OnCalendar=*:0/30` is this repo's only existing precedent for a "every N minutes" systemd timer — the new live-check timer's `OnCalendar=*:0/10` follows this exact syntax, just with a different step.
- `scripts/deploy.ps1` (full file, 98 lines, esp. `$TIMERS` array lines 17-22) — Why: **must be updated** (Task 7) to add the new timer to the managed stop/start list, with a comment matching the existing style (lines 10-16 already explain why `second-brain-mytrader-monitor.timer` is deliberately excluded — the new timer's addition needs a one-line justification in the same spot, not a silent addition).

### New Files to Create

- `investments/goat/goat/market_hours.py` — `is_asx_open(now: datetime | None = None) -> bool`, `is_us_market_open(now: datetime | None = None) -> bool`, `classify_market(ticker: str) -> str` (returns `"ASX"` or `"US"`).
- `investments/goat/goat/live_monitor.py` — `run_live_monitor(conn: sqlite3.Connection) -> dict[str, Any]`, orchestrating the live check across whichever holdings' market is currently open.
- `investments/goat/goat/tests/test_market_hours.py` — unit tests for the three functions above against fixed, explicit datetimes (weekday/weekend, in-hours/out-of-hours, both markets).
- `investments/goat/goat/tests/test_live_monitor.py` — unit tests mirroring `test_monitor.py`'s shape for `run_live_monitor`.
- `scripts/systemd/second-brain-goat-live-check.service` — oneshot service, `ExecStart=... -m goat.main check-live`.
- `scripts/systemd/second-brain-goat-live-check.timer` — `OnCalendar=*:0/10`, always-on (Python-side market-hours gating decides whether any real work happens).

### Files to Update

- `investments/goat/goat/exit_check.py` — add `check_150dma_exit_live(ticker: str, close: pd.Series, live_price: float) -> CheckResult`.
- `investments/goat/goat/config.py` — append `GOAT_LIVE_POLL_INTERVAL_MINUTES`, `GOAT_ASX_MARKET_OPEN`/`GOAT_ASX_MARKET_CLOSE`, `GOAT_US_MARKET_OPEN`/`GOAT_US_MARKET_CLOSE`, `GOAT_ASX_TZ`/`GOAT_US_TZ` constants.
- `investments/goat/goat/monitor.py` — rename `_reconcile_alerts` to `reconcile_alerts` (drop the leading underscore; update its one internal call site at line 55 and its docstring if any); no behavior change.
- `investments/goat/goat/main.py` — add `check-live` subcommand (`cmd_check_live`) wired the same way `cmd_monitor` is, minus the sector-scan/report-writing parts.
- `scripts/deploy.ps1` — add `"second-brain-goat-live-check.timer"` to the `$TIMERS` array with a one-line comment.
- `investments/goat/HANDOFF.md` — after implementation, update the "Intraday 150DMA Alerting" section's header to note it's built + live, matching how the Phase 1/Phase 2 status lines at the top of the file were updated when those shipped (see line 3's existing style) — this is a documentation task, not a code task, but keep HANDOFF.md's running status-line convention intact.

### Relevant Documentation

- Python `zoneinfo` stdlib docs (https://docs.python.org/3/library/zoneinfo.html) — `ZoneInfo("Australia/Sydney")` and `ZoneInfo("America/New_York")` correctly handle AEST/AEDT and EST/EDT daylight-saving transitions automatically (both hemispheres, opposite DST calendars) — this is *why* the plan uses local-time zone-aware comparisons in Python rather than trying to encode both DST schedules as static UTC windows in the systemd timer's `OnCalendar=` syntax (which would silently drift wrong twice a year for each region).
  - Why: this is the one piece of the design that would be actively wrong if simplified to "just pick a UTC window" — worth reading if unfamiliar with `zoneinfo`'s DST-aware comparison behavior before implementing `market_hours.py`.

### Patterns to Follow

**Threshold/config sourcing discipline:** every tunable number in `goat/config.py` has a comment explaining where it came from and whether it's literature-sourced or a v1 guess (see `GOAT_150DMA_FLAG_PCT`, `GOAT_SECTOR_RANK_WINDOW_TRADING_DAYS`). The new `GOAT_LIVE_POLL_INTERVAL_MINUTES` must follow this exactly — it's explicitly a v1 guess (see resolved question 2 above), not a researched number, and the comment must say so.

**CheckResult verdict semantics:** `"flag"` = risk/exit warning (this feature, matches Phase 1's exit check), `"ok"` = no issue, `"unknown"` = insufficient data, `"interesting"` = a positive opportunity signal (Phase 2's breakout detector — not relevant here, but don't accidentally reuse `"interesting"` for this check).

**Cross-package reuse, read-only:** `live_monitor.py` reads `mytrader.db.get_all_holdings(conn)` and calls `mytrader.market_data.fetch_current_price(ticker)` directly — both already-established cross-package read patterns (`monitor.py` already does the former; nothing in Goat has called `market_data` before, but `market_data` is a plain read-only function with no side effects, consistent with the "Goat never *writes* into my-trader's tables" rule, which only ever applied to writes).

**Dedup via shared function, not duplicated logic:** this is the one deliberate deviation from `price_history.py`'s own stated convention ("Ported rather than imported since that function is module-private... worth reusing/porting rather than reinventing" — but that comment is about a *pure computation* being cheap to duplicate). Alert-dedup logic is different: it directly mutates shared state (`goat_alert_history`), so two independent implementations risk silently drifting apart over time (e.g. one gets a bugfix, the other doesn't) in a way a pure computation duplicate wouldn't. `reconcile_alerts` is promoted from private to public and imported properly instead. State this rationale as a one-line comment above `reconcile_alerts`'s new public definition in `monitor.py`, so a future reader doesn't assume the module-private convention was simply forgotten.

---

## IMPLEMENTATION PLAN

### Phase 1: Foundation — market-hours + config

**Tasks:**
- Add market-hours constants to `config.py`
- Implement `market_hours.py` (pure functions, no I/O, fully unit-testable against fixed datetimes)

### Phase 2: Core Implementation — live check + orchestration

**Tasks:**
- Add `check_150dma_exit_live()` to `exit_check.py`
- Promote `_reconcile_alerts` → `reconcile_alerts` in `monitor.py`
- Implement `live_monitor.py::run_live_monitor()`

### Phase 3: Integration — CLI + deployment

**Tasks:**
- Add `check-live` CLI subcommand
- Add systemd service + timer
- Update `deploy.ps1`'s managed timer list

### Phase 4: Testing & Validation

**Tasks:**
- Unit tests for `market_hours.py` (fixed-datetime table)
- Unit tests for `check_150dma_exit_live()` (mirrors existing `check_150dma_exit` boundary tests)
- Unit tests for `run_live_monitor()` (dedup-sharing with daily monitor is the critical case)
- Manual validation against the real DB during a real open-market window

---

## STEP-BY-STEP TASKS

IMPORTANT: Execute every task in order, top to bottom. Each task is atomic and independently testable.

### 1. UPDATE `investments/goat/goat/config.py`

- **IMPLEMENT**: Append, following the existing block-comment style exactly:
  ```python
  # Intraday 150DMA live-check polling, per investments/goat/HANDOFF.md's
  # "Intraday 150DMA Alerting" section (raised 2026-08-16) -- Shaun wants a
  # WhatsApp alert as soon as a holding's LIVE price crosses below its 150DMA
  # while the relevant market is still open, not at next morning's daily batch.
  # This is genuinely a new, unresearched cadence choice -- v1/tunable, not
  # literature-final, same as GOAT_SECTOR_RANK_WINDOW_TRADING_DAYS.
  GOAT_LIVE_POLL_INTERVAL_MINUTES = 10  # tighter than the only existing
                                           # recurring-timer precedent in this repo
                                           # (second-brain-heartbeat.timer, every 30
                                           # min) to honor "as soon as it drops" --
                                           # each run is cheap because only
                                           # currently-open-market holdings get
                                           # fetched, not the whole holdings table.

  # ASX/US regular-session local hours -- deliberately regular-session only, no
  # pre/post-market, and deliberately no market-holiday calendar (a holiday just
  # means fetch_current_price/fetch_close_history return stale/None data, which
  # the existing per-ticker try/except already handles gracefully -- see
  # HANDOFF.md's explicitly-deferred scope; a real holiday calendar is a separate
  # follow-up, not built speculatively here).
  GOAT_ASX_TZ = "Australia/Sydney"
  GOAT_ASX_MARKET_OPEN = (10, 0)   # 10:00am Sydney local
  GOAT_ASX_MARKET_CLOSE = (16, 0)  # 4:00pm Sydney local
  GOAT_US_TZ = "America/New_York"
  GOAT_US_MARKET_OPEN = (9, 30)    # 9:30am US Eastern
  GOAT_US_MARKET_CLOSE = (16, 0)   # 4:00pm US Eastern
  ```
- **PATTERN**: `GOAT_150DMA_FLAG_PCT` block (config.py lines 12-41) for the citation-comment style.
- **VALIDATE**: `uv run --directory investments/goat python -c "from goat import config; print(config.GOAT_LIVE_POLL_INTERVAL_MINUTES, config.GOAT_ASX_TZ, config.GOAT_US_MARKET_OPEN)"`

### 2. CREATE `investments/goat/goat/market_hours.py`

- **IMPLEMENT**:
  ```python
  """Market-hours gating for Goat's intraday live check -- decides which holdings'
  market is currently open, so the live-check poller only fetches/checks tickers
  whose market is genuinely trading right now. See HANDOFF.md's "Intraday 150DMA
  Alerting" section, resolved design questions 2-3."""

  from __future__ import annotations

  from datetime import datetime
  from zoneinfo import ZoneInfo

  from . import config


  def _is_open(now: datetime | None, tz_name: str, open_hm: tuple[int, int], close_hm: tuple[int, int]) -> bool:
      tz = ZoneInfo(tz_name)
      local = (now or datetime.now(tz)).astimezone(tz)
      if local.weekday() >= 5:  # Saturday=5, Sunday=6
          return False
      open_t = local.replace(hour=open_hm[0], minute=open_hm[1], second=0, microsecond=0)
      close_t = local.replace(hour=close_hm[0], minute=close_hm[1], second=0, microsecond=0)
      return open_t <= local <= close_t


  def is_asx_open(now: datetime | None = None) -> bool:
      return _is_open(now, config.GOAT_ASX_TZ, config.GOAT_ASX_MARKET_OPEN, config.GOAT_ASX_MARKET_CLOSE)


  def is_us_market_open(now: datetime | None = None) -> bool:
      return _is_open(now, config.GOAT_US_TZ, config.GOAT_US_MARKET_OPEN, config.GOAT_US_MARKET_CLOSE)


  def classify_market(ticker: str) -> str:
      """'ASX' or 'US', from the ticker's own .AX suffix -- matches the real
      holdings-table convention (see investments/my-trader/holdings.md: GGOV.AX
      vs. bare AG/LULU/V) and mytrader.tickers.asx_variant's own assumption."""
      return "ASX" if ticker.strip().upper().endswith(".AX") else "US"
  ```
- **GOTCHA**: `now` must accept a tz-aware `datetime` (e.g. constructed with `datetime(..., tzinfo=ZoneInfo("UTC"))`) for `.astimezone(tz)` to behave correctly in tests — a naive `datetime` passed as `now` will raise or silently misbehave; tests must always pass tz-aware fixtures. Document this in the function's use, and in tests always build fixtures via `datetime(..., tzinfo=ZoneInfo("UTC"))`.
- **IMPORTS**: stdlib only (`datetime`, `zoneinfo.ZoneInfo`) plus local `config`.
- **VALIDATE**: `uv run --directory investments/goat python -c "from goat.market_hours import classify_market; assert classify_market('GGOV.AX') == 'ASX'; assert classify_market('LULU') == 'US'; print('ok')"`

### 3. UPDATE `investments/goat/goat/exit_check.py`

- **IMPLEMENT**: Add below `check_150dma_exit`:
  ```python
  def check_150dma_exit_live(ticker: str, close: pd.Series, live_price: float) -> CheckResult:
      """Live/intraday sibling of check_150dma_exit. `close` must be historical
      daily closes for COMPLETED trading days only -- callers must strip any
      trailing same-day partial bar before calling this (see live_monitor.py's
      _completed_closes_only). `live_price` stands in for "today's close" as it
      would look at end of day, but the 150-day MA itself is computed only from
      `close` (completed days) -- it is never live-updating, matching HANDOFF's
      explicit design decision that the MA is not recomputed from partial-day
      data. Persistence (GOAT_150DMA_MIN_CONSECUTIVE_DAYS) is checked across the
      most recent (N-1) COMPLETED days plus today's live day, so this stays
      correct even if that config value is ever raised above 1."""
      n_prior_needed = config.GOAT_150DMA_MIN_CONSECUTIVE_DAYS - 1
      min_len = config.GOAT_MA_LONG_DAYS + n_prior_needed
      if len(close) < min_len:
          return CheckResult(
              name="below_150dma", verdict="unknown",
              detail=f"{ticker}: insufficient price history for a "
                     f"{config.GOAT_MA_LONG_DAYS}-day MA",
          )

      ma_today = float(close.tail(config.GOAT_MA_LONG_DAYS).mean())
      pct_below_today = (ma_today - live_price) / ma_today * 100
      today_qualifies = pct_below_today >= config.GOAT_150DMA_FLAG_PCT

      prior_qualifies = True
      if n_prior_needed > 0:
          ma = close.rolling(config.GOAT_MA_LONG_DAYS).mean()
          pct_below_hist = ((ma - close) / ma * 100).dropna()
          prior_qualifies = bool(
              (pct_below_hist.tail(n_prior_needed) >= config.GOAT_150DMA_FLAG_PCT).all()
          )

      flagged = bool(today_qualifies and prior_qualifies)
      data = {"pct_below": float(pct_below_today), "ma": ma_today, "price": float(live_price)}

      if flagged:
          return CheckResult(
              name="below_150dma", verdict="flag",
              detail=f"{ticker}: LIVE price now {pct_below_today:.1f}% below its "
                     f"{config.GOAT_MA_LONG_DAYS}-day MA (intraday -- not yet a "
                     f"confirmed close); has stayed >={config.GOAT_150DMA_FLAG_PCT:.0f}% "
                     f"below for {config.GOAT_150DMA_MIN_CONSECUTIVE_DAYS}+ trading "
                     f"day(s) including today -- 150DMA exit-rule threshold triggered",
              data=data,
          )
      return CheckResult(
          name="below_150dma", verdict="ok",
          detail=f"{ticker}: LIVE price {abs(pct_below_today):.1f}% "
                 f"{'below' if pct_below_today > 0 else 'above'} its "
                 f"{config.GOAT_MA_LONG_DAYS}-day MA (intraday)",
          data=data,
      )
  ```
- **PATTERN**: `check_150dma_exit` (exit_check.py lines 12-63) — same `CheckResult` shape (`name="below_150dma"` unchanged — this is what makes the shared dedup key in resolved question 5 work), same `data` dict keys.
- **GOTCHA (critical, must document if deviated from)**: do **not** implement this by concatenating `live_price` onto the end of `close` and calling the existing `check_150dma_exit()` unmodified. That would make `live_price` part of the `rolling(150)` window used to compute the MA itself, silently violating HANDOFF's design decision #4 ("does the current live price sit below the most recently completed 150DMA, not a live-updating MA") — the MA would shift based on the live price it's supposed to be independent of. `ma_today` above is computed from `close.tail(150)` alone, before `live_price` enters the comparison at all.
- **IMPORTS**: no new imports — same `pandas as pd`, `from mytrader.checks import CheckResult`, `from . import config` already at the top of the file.
- **VALIDATE**: `uv run --directory investments/goat python -m pytest goat/tests/test_exit_check.py -q` (after Task 8 adds new tests here).

### 4. UPDATE `investments/goat/goat/monitor.py`

- **IMPLEMENT**: Rename `_reconcile_alerts` (line 21) to `reconcile_alerts` (drop leading underscore). Update its one call site at line 55 (`new_alerts.extend(_reconcile_alerts(...))` → `reconcile_alerts(...)`). Add a one-line comment above the new public definition:
  ```python
  # Public (not module-private) because goat/live_monitor.py also calls this
  # directly -- shared dedup state (goat_alert_history) is riskier to duplicate
  # than a pure computation would be, so this is imported properly rather than
  # ported/copied the way price_history.py's crash_windows-derived logic was.
  def reconcile_alerts(
      ticker: str, checks: list[CheckResult], conn: sqlite3.Connection
  ) -> list[dict[str, Any]]:
  ```
- **PATTERN**: see "Dedup via shared function, not duplicated logic" in Patterns to Follow above for the full rationale.
- **GOTCHA**: this is a pure rename — no signature or behavior change. Grep the whole `investments/goat/` tree for `_reconcile_alerts` after the rename to make sure no other call site (including tests) was missed.
- **VALIDATE**: `uv run --directory investments/goat python -m pytest goat/tests/test_monitor.py -q` (must still pass unmodified — confirms the rename didn't break the existing daily-check tests).

### 5. CREATE `investments/goat/goat/live_monitor.py`

- **IMPLEMENT**:
  ```python
  """Goat's intraday 150DMA live check -- runs frequently during market hours
  (see market_hours.py) and reuses the exact same goat_alert_history dedup as
  the daily monitor (monitor.reconcile_alerts) so the two checks can never
  double-alert for the same crossing. See investments/goat/HANDOFF.md's
  "Intraday 150DMA Alerting" section."""

  from __future__ import annotations

  import sqlite3
  from datetime import datetime
  from typing import Any
  from zoneinfo import ZoneInfo

  import pandas as pd
  from mytrader import db as mt_db, market_data

  from . import config, exit_check, market_hours, price_history
  from .monitor import SOURCE_TABLE, reconcile_alerts


  def _completed_closes_only(close: pd.Series, tz_name: str) -> pd.Series:
      """Defensive guard: yfinance daily history can include a partial,
      still-updating bar for the current trading day when fetched mid-session.
      The 150-day MA must only ever be built from completed days (see
      exit_check.check_150dma_exit_live's docstring), so drop the trailing row
      if its date matches "today" in the ticker's own exchange-local calendar
      day. close.index is tz-naive by the time price_history.fetch_close_history
      returns it (see that function's tz_localize(None) call), so compare
      against a tz-aware "today" computed in the exchange's own timezone, not
      the machine's local/UTC date."""
      if close.empty:
          return close
      today_local = datetime.now(ZoneInfo(tz_name)).date()
      if close.index[-1].date() == today_local:
          return close.iloc[:-1]
      return close


  def run_live_monitor(conn: sqlite3.Connection) -> dict[str, Any]:
      asx_open = market_hours.is_asx_open()
      us_open = market_hours.is_us_market_open()

      new_alerts: list[dict[str, Any]] = []
      checked = 0

      if asx_open or us_open:
          holdings = mt_db.get_all_holdings(conn)
          for row in holdings:
              ticker = row["ticker"]
              market = market_hours.classify_market(ticker)
              if (market == "ASX" and not asx_open) or (market == "US" and not us_open):
                  continue
              tz_name = config.GOAT_ASX_TZ if market == "ASX" else config.GOAT_US_TZ
              try:
                  live_price = market_data.fetch_current_price(ticker)
                  if live_price is None:
                      print(f"[goat-live-monitor] no live price for {ticker}, skipping")
                      continue
                  close = price_history.fetch_close_history(ticker, config.GOAT_MA_HISTORY_LOOKBACK_DAYS)
                  if close is None:
                      print(f"[goat-live-monitor] no price history for {ticker}, skipping")
                      continue
                  close = _completed_closes_only(close, tz_name)
                  check = exit_check.check_150dma_exit_live(ticker, close, live_price)
                  new_alerts.extend(reconcile_alerts(ticker, [check], conn))
                  checked += 1
              except Exception as e:
                  print(f"[goat-live-monitor] error checking {ticker}: {e}")

      return {
          "checked_holdings": checked,
          "new_alerts": new_alerts,
          "open_alerts": [dict(a) for a in __import__("goat.db", fromlist=["get_open_goat_alerts"]).get_open_goat_alerts(conn)],
      }
  ```
  (Note: replace the `__import__(...)` line with a normal `from . import db` at the top and `db.get_open_goat_alerts(conn)` — written inline above only to keep the import list visible next to its one use in this plan; **do not actually ship the `__import__` form**, use a clean top-level `from . import db` alongside the other `from . import config, exit_check, market_hours, price_history` and call `db.get_open_goat_alerts(conn)` directly.)
- **PATTERN**: `monitor.run_monitor` (monitor.py lines 42-64) for the overall shape and the per-ticker `try/except` resilience idiom (lines 49-58, copied verbatim in spirit).
- **IMPORTS**: `from mytrader import db as mt_db, market_data`; `from . import config, db, exit_check, market_hours, price_history`; `from .monitor import SOURCE_TABLE, reconcile_alerts` (note: `SOURCE_TABLE` is imported for symmetry/possible future use in messages, but `reconcile_alerts` itself already hardcodes `SOURCE_TABLE` internally in `monitor.py`, so `live_monitor.py` does not need to pass it explicitly — confirm this against `monitor.py`'s actual `reconcile_alerts` signature before wiring the call, since the plan's read of `monitor.py` above (lines 21-39) shows `SOURCE_TABLE` is a module-level closure-captured constant inside `_reconcile_alerts`/`reconcile_alerts`, not a parameter).
- **GOTCHA**: the cheap early-exit (`if asx_open or us_open:`) means zero yfinance calls and zero DB reads of `holdings` happen when both markets are closed — only `get_open_goat_alerts` runs (cheap, always, for a consistent return shape). This matters for the "runs 24/7 via a 10-minute timer" design (Task 6) — most invocations outside trading hours must be near-instant no-ops.
- **VALIDATE**: `uv run --directory investments/goat python -m pytest goat/tests/test_live_monitor.py -q` (after Task 9).

### 6. UPDATE `investments/goat/goat/main.py`

- **IMPLEMENT**: Add alongside `cmd_monitor`:
  ```python
  def cmd_check_live(args) -> None:
      from .live_monitor import run_live_monitor
      from .monitor import maybe_notify

      conn = _open_conn()
      result = run_live_monitor(conn)
      conn.close()
      maybe_notify(result)
      print(
          f"Goat live check complete: checked {result['checked_holdings']} open-market "
          f"holding(s), {len(result['new_alerts'])} new alert(s)."
      )
  ```
  And register it: `subparsers.add_parser("check-live", help="Intraday 150DMA live-price check against currently-open-market holdings")`, plus add `"check-live": cmd_check_live` to the `dispatch` dict.
- **PATTERN**: `cmd_monitor` (main.py lines 22-45) and `cmd_scan_sectors` (lines 48-60) for the exact `_open_conn()` / do work / `conn.close()` / print-summary shape.
- **GOTCHA**: deliberately does **not** call `write_report`/`run_sector_scan` — this command's job is only the live check + WhatsApp alert, not the daily summary file (matches "Not scoped here" in the resolved-questions section).
- **VALIDATE**: `uv run --directory investments/goat python -m goat.main check-live` (manual — will do nothing if run outside both markets' hours; see Level 4 validation below for how to confirm it actually works when a market is open).

### 7. CREATE `scripts/systemd/second-brain-goat-live-check.service`

- **IMPLEMENT**:
  ```ini
  [Unit]
  Description=Goat Intraday 150DMA Live Check
  After=network.target

  [Service]
  Type=oneshot
  User=secondbrain
  WorkingDirectory=/home/secondbrain/second-brain/investments/goat
  ExecStart=/home/secondbrain/second-brain/investments/.venv/bin/python -m goat.main check-live
  StandardOutput=append:/home/secondbrain/second-brain/investments/goat/live_check_runs.log
  StandardError=append:/home/secondbrain/second-brain/investments/goat/live_check_runs.log
  ```
- **PATTERN**: `scripts/systemd/second-brain-goat-monitor.service` (mirror exactly except `ExecStart` and the log filename).
- **VALIDATE**: `systemd-analyze verify scripts/systemd/second-brain-goat-live-check.service` (run on the VPS after deploy; can't validate systemd unit syntax on Windows dev machine).

### 8. CREATE `scripts/systemd/second-brain-goat-live-check.timer`

- **IMPLEMENT**:
  ```ini
  [Unit]
  Description=Goat Intraday 150DMA Live Check Timer
  Requires=second-brain-goat-live-check.service

  [Timer]
  OnCalendar=*:0/10
  Persistent=true

  [Install]
  WantedBy=timers.target
  ```
- **PATTERN**: `scripts/systemd/second-brain-heartbeat.timer` for the `OnCalendar=*:0/N` syntax; `second-brain-goat-monitor.timer` for the rest of the shape. The step (`10`) must match `GOAT_LIVE_POLL_INTERVAL_MINUTES` in `config.py` (Task 1) — if that constant is tuned later, update this file too (they are not programmatically linked; note this coupling in a comment in `config.py`'s `GOAT_LIVE_POLL_INTERVAL_MINUTES` block if not already implied).
- **GOTCHA**: deliberately `*:0/10` (all day, every day) rather than trying to encode ASX/US hours directly in `OnCalendar=` — see "Relevant Documentation" above for why a static UTC window would drift wrong across DST transitions in either hemisphere. The real gating is `market_hours.py`'s Python-side check inside `run_live_monitor`, which is correct across DST by construction (`zoneinfo`-based).
- **VALIDATE**: `systemd-analyze calendar "*:0/10"` (on the VPS, or any Linux box with systemd) — confirms the calendar expression parses and previews the next several fire times.

### 9. UPDATE `scripts/deploy.ps1`

- **IMPLEMENT**: Add to the `$TIMERS` array (lines 17-22):
  ```powershell
  $TIMERS = @(
      "second-brain-heartbeat.timer",
      "second-brain-vaultsync.timer",
      "second-brain-reflect.timer",
      "second-brain-goat-monitor.timer",
      "second-brain-goat-live-check.timer"
  )
  ```
- **PATTERN**: existing array shape; the comment block above it (lines 10-16) already explains the general "every timer that touches the repo must be stopped during deploy" rule — no new comment needed unless this timer has some special exception (it doesn't; it's a plain oneshot like `second-brain-goat-monitor.timer` already in the list).
- **GOTCHA**: the new `.service`/`.timer` unit files themselves are not automatically installed/enabled on the VPS by `deploy.ps1` — that's a one-time manual `systemctl enable --now` step on the VPS after the files are pulled via git (same as how `second-brain-goat-monitor.timer` was originally brought up per HANDOFF.md's Phase 1 status line: "systemd units exist but are NOT enabled on the VPS — needs Shaun's explicit go-ahead"). Do not enable this new timer automatically as part of implementation; leave it for Shaun's explicit go-ahead, exactly like Phase 1's units were.
- **VALIDATE**: manual review — `deploy.ps1` has no automated test; confirm by reading the diff that the array change is the only change and no other logic was touched.

### 10. UPDATE `investments/goat/goat/tests/test_exit_check.py`

- **IMPLEMENT**: Append tests for `check_150dma_exit_live`, mirroring the existing tests' structure exactly:
  - `test_live_price_above_ma_is_ok` — live price above the historical MA → `"ok"`.
  - `test_live_price_at_or_below_ma_flags_immediately` — with `GOAT_150DMA_MIN_CONSECUTIVE_DAYS == 1` (current live config value), a single live price at/below the MA flags immediately, same semantics as the daily check's `test_flags_immediately_on_single_qualifying_day`.
  - `test_live_check_does_not_let_live_price_affect_the_ma` — construct a historical `close` series where the MA is a known value (e.g. flat 100.0 for 150 days), pass a wildly different `live_price` (e.g. 1.0), and assert `result.data["ma"] == 100.0` (not shifted toward 1.0) — this is the regression test for the GOTCHA in Task 3; it must fail if someone "fixes" the implementation by concatenating `live_price` onto `close`.
  - `test_live_check_insufficient_history_is_unknown` — mirrors `test_insufficient_history_is_unknown`.
  - `test_live_check_persistence_across_prior_completed_days_and_today` — set `GOAT_150DMA_MIN_CONSECUTIVE_DAYS` to `2` via monkeypatch for this one test (even though the live default is `1`), construct `close` where the second-to-last completed day already qualified, and confirm today's live price also qualifying is required to flag (and that today alone, with the prior day recovered, does not flag) — proves the `n_prior_needed` generalization in Task 3 is correct, not just correct for `N=1`.
- **PATTERN**: `_flat_then()`/`_dates()` helpers already in this file (lines 8-18) — reuse unmodified.
- **VALIDATE**: `uv run --directory investments/goat python -m pytest goat/tests/test_exit_check.py -q`

### 11. CREATE `investments/goat/goat/tests/test_market_hours.py`

- **IMPLEMENT**: Fixed-datetime table tests, e.g.:
  ```python
  from datetime import datetime
  from zoneinfo import ZoneInfo

  from goat import market_hours


  def _utc(y, mo, d, h, mi):
      return datetime(y, mo, d, h, mi, tzinfo=ZoneInfo("UTC"))


  def test_classify_market_asx_suffix():
      assert market_hours.classify_market("GGOV.AX") == "ASX"
      assert market_hours.classify_market("ggov.ax") == "ASX"  # case-insensitive


  def test_classify_market_bare_ticker_is_us():
      assert market_hours.classify_market("LULU") == "US"


  def test_asx_open_during_sydney_trading_hours():
      # 2026-08-17 is a Monday; 02:00 UTC = 12:00 AEST (Sydney, +10 in Aug, no DST)
      assert market_hours.is_asx_open(_utc(2026, 8, 17, 2, 0)) is True


  def test_asx_closed_outside_trading_hours():
      # 23:00 UTC = 09:00 AEST next day -- before 10am open
      assert market_hours.is_asx_open(_utc(2026, 8, 16, 23, 0)) is False


  def test_asx_closed_on_weekend():
      # 2026-08-15 is a Saturday
      assert market_hours.is_asx_open(_utc(2026, 8, 15, 2, 0)) is False


  def test_us_market_open_during_ny_trading_hours():
      # 2026-08-17 Monday, 15:00 UTC = 11:00 EDT (US, -4 in Aug)
      assert market_hours.is_us_market_open(_utc(2026, 8, 17, 15, 0)) is True


  def test_us_market_closed_outside_trading_hours():
      assert market_hours.is_us_market_open(_utc(2026, 8, 17, 3, 0)) is False


  def test_asx_and_us_hours_never_overlap():
      # spot-check across a full day in 5-min increments that both are never
      # simultaneously True (Sydney daytime is US nighttime and vice versa)
      from datetime import timedelta
      start = _utc(2026, 8, 17, 0, 0)
      for i in range(288):  # 24h in 5-min steps
          t = start + timedelta(minutes=5 * i)
          assert not (market_hours.is_asx_open(t) and market_hours.is_us_market_open(t))
  ```
- **GOTCHA**: verify the exact UTC offsets used above against the actual dates chosen at implementation time — Australia's DST (AEDT, +11) runs roughly Oct-Apr, and US DST (EDT, -4) runs roughly Mar-Nov, so a date in August has ASX at standard AEST (+10) and US at EDT (-4); pick implementation-time-current or clearly-past-tense fixed dates and double check the offsets with `python -c "from zoneinfo import ZoneInfo; from datetime import datetime; print(datetime(2026,8,17,tzinfo=ZoneInfo('Australia/Sydney')).utcoffset())"` rather than trusting the offsets written in this plan verbatim.
- **VALIDATE**: `uv run --directory investments/goat python -m pytest goat/tests/test_market_hours.py -q`

### 12. CREATE `investments/goat/goat/tests/test_live_monitor.py`

- **IMPLEMENT**: Mirror `test_monitor.py`'s fixture/monkeypatch style:
  - `test_run_live_monitor_noop_when_both_markets_closed` — monkeypatch `goat.live_monitor.market_hours.is_asx_open`/`is_us_market_open` to both return `False`; seed a holding; assert `checked_holdings == 0` and that `mytrader.market_data.fetch_current_price` was never called (monkeypatch it to raise if called, to prove the early-exit works).
  - `test_run_live_monitor_only_checks_matching_market` — one ASX holding (`"GGOV.AX"`), one US holding (`"LULU"`); `is_asx_open` → `True`, `is_us_market_open` → `False`; assert only the ASX ticker was fetched/checked (`checked_holdings == 1`).
  - `test_run_live_monitor_creates_new_alert_on_flag` — mirrors `test_run_monitor_creates_new_alert_for_first_flag`; stub `market_data.fetch_current_price` and `price_history.fetch_close_history` to produce a flagging live price against a flat historical MA; assert one new alert, one row in `goat_alert_history`.
  - `test_live_and_daily_monitor_share_dedup_no_double_alert` — **the critical dedup test for resolved question 5**: seed a holding, run `live_monitor.run_live_monitor` first (with a flagging live price) to create the alert, then run `monitor.run_monitor` (with a flagging daily close for the same ticker) and assert `run_monitor`'s result has zero `new_alerts` (because `get_open_goat_alert` already finds the live-created row) — proves the two checks share one dedup row via the same `check_name`.
  - `test_run_live_monitor_skips_ticker_with_no_live_price` — mirrors `test_run_monitor_skips_ticker_with_no_price_history`, but stubs `market_data.fetch_current_price` to return `None`.
  - `_completed_closes_only` unit tests (can live in this file or a small dedicated block): a series whose last index date is "today" (relative to a monkeypatched `datetime.now`) gets its last row dropped; a series whose last date is not today is returned unchanged; an empty series is returned unchanged without error.
- **PATTERN**: `test_monitor.py`'s `_seed_holding`, `_flagging_series`/`_non_flagging_series`, and `_fake_notifications_module` (for confirming `maybe_notify` still gets called correctly from `cmd_check_live` — though that itself is argparse-wired and per this project's convention, per `test_monitor.py` line 267's comment, argparse-wired `cmd_*` functions are not directly unit tested; test `run_live_monitor` + `maybe_notify` at the function level instead, same as the existing suite does for `cmd_monitor`).
- **VALIDATE**: `uv run --directory investments/goat python -m pytest goat/tests/test_live_monitor.py -q`

### 13. Full suite + lint validation

- **VALIDATE**:
  ```powershell
  uv sync --directory investments/goat --extra dev
  uv run --directory investments/goat python -m pytest -q
  uv run --directory investments/goat ruff check goat/
  ```
  All existing + new tests must pass; zero ruff findings on touched files.

---

## TESTING STRATEGY

### Unit Tests

Every new pure function (`market_hours.*`, `exit_check.check_150dma_exit_live`) gets fixture-driven unit tests with no I/O, following this project's existing style exactly (synthetic `pd.Series`/fixed `datetime` inputs, no real yfinance/network calls — enforced globally by `conftest.py`'s autouse `_no_real_price_history_fetch` fixture, which must be joined by an equivalent per-test stub for `market_data.fetch_current_price` in any test that would otherwise hit real yfinance).

### Integration Tests

`test_live_monitor.py`'s dedup-sharing test (`test_live_and_daily_monitor_share_dedup_no_double_alert`) is the one genuine integration test in this plan — it exercises `live_monitor.run_live_monitor` and `monitor.run_monitor` together against the same `db_conn` fixture and the real `goat_alert_history` table (in-memory/tmp-path SQLite via the existing `db_conn` fixture, not mocked), confirming the cross-module dedup contract actually holds end-to-end, not just in isolation.

### Edge Cases

- Both markets closed simultaneously (most of the day, given AEST) → zero yfinance calls, `checked_holdings == 0`.
- A ticker whose live price fetch succeeds but whose historical close fetch fails (or vice versa) → skipped gracefully, doesn't abort the run (mirrors `test_run_monitor_skips_ticker_with_no_price_history`).
- `_completed_closes_only` when yfinance did *not* return a partial today-bar (i.e. the guard is a no-op) — must not incorrectly drop a legitimate completed day.
- `GOAT_150DMA_MIN_CONSECUTIVE_DAYS` temporarily monkeypatched to `2`+ in a live-check test, to prove the generalized persistence logic (Task 3) isn't silently hardcoded to `N=1` even though that's the current live default.
- A holding ticker that's neither clearly ASX nor recognizably US-suffixed (shouldn't occur given the real data convention, but `classify_market` must still return a deterministic value, not raise) — covered implicitly since `classify_market` has no failure path, just document this in a code comment if not obvious.

---

## VALIDATION COMMANDS

### Level 1: Syntax & Style

```powershell
uv run --directory investments/goat ruff check goat/
uv run --directory investments/goat mypy goat/ --ignore-missing-imports
```

### Level 2: Unit Tests

```powershell
uv run --directory investments/goat python -m pytest goat/tests/test_market_hours.py goat/tests/test_exit_check.py goat/tests/test_live_monitor.py -q
```

### Level 3: Integration Tests

```powershell
uv run --directory investments/goat python -m pytest -q
```
(Full suite — confirms the `monitor.py` rename in Task 4 didn't break any existing test, and the new dedup-sharing test passes.)

### Level 4: Manual Validation

- Run `uv run --directory investments/goat python -m goat.main check-live` **during a window when at least one market is genuinely open** (e.g. weekday ~11am AEST for ASX, or weekday ~midnight-6am AEST for US) against the real DB. Confirm:
  1. Console output shows a non-zero `checked_holdings` count for the open market's tickers only.
  2. No exception; any per-ticker fetch failure is logged and skipped, not fatal.
  3. If a real holding happens to be below its 150DMA at that moment, confirm exactly one WhatsApp message arrives (not one from this run and a duplicate later from the next daily `monitor` run the same day) — this is the real-world confirmation of the dedup-sharing design, not just the unit test.
- Separately, run it **outside both markets' hours** (e.g. weekday ~8pm AEST) and confirm it exits near-instantly with `checked_holdings == 0` and no yfinance calls (can verify via `time` on the command, or temporarily add a print inside the `if asx_open or us_open:` block during manual testing only, then remove it).
- `systemd-analyze verify` and `systemd-analyze calendar "*:0/10"` on the VPS (Task 7/8's validate commands) before enabling the timer.
- Do **not** run `systemctl enable --now second-brain-goat-live-check.timer` as part of this implementation — that step is explicitly Shaun's call (see Task 9's GOTCHA), same as Phase 1's original rollout.

### Level 5: Additional Validation (Optional)

None beyond the above — this feature has no UI, no external API beyond yfinance (already covered by existing patterns), and no MCP server involvement.

---

## ACCEPTANCE CRITERIA

- [ ] `market_hours.is_asx_open`/`is_us_market_open`/`classify_market` correctly classify real holdings-table tickers and correctly gate on Sydney/NY local trading hours across DST (verified via `zoneinfo`, not hardcoded UTC offsets)
- [ ] `check_150dma_exit_live` never lets `live_price` influence the 150-day MA value itself (covered by `test_live_check_does_not_let_live_price_affect_the_ma`)
- [ ] `check-live` and the existing daily `monitor` command share one `goat_alert_history` dedup row per (ticker, check_name) — verified by `test_live_and_daily_monitor_share_dedup_no_double_alert`, and confirmed live during Level 4 manual validation
- [ ] `check-live` performs zero yfinance calls and returns near-instantly when both markets are closed
- [ ] New systemd unit files mirror the existing `second-brain-goat-monitor.service`/`.timer` shape exactly except for the intentional differences (subcommand, cadence)
- [ ] `deploy.ps1`'s `$TIMERS` array includes the new timer
- [ ] The new timer is **not** auto-enabled on the VPS as part of this implementation — left for Shaun's explicit go-ahead
- [ ] Full existing test suite (Phase 1 + Phase 2 tests) still passes unmodified after the `_reconcile_alerts` → `reconcile_alerts` rename
- [ ] `ruff check` and `mypy` clean on all touched/new files
- [ ] HANDOFF.md's "Intraday 150DMA Alerting" section updated to reflect built status, matching the file's existing running-status-line convention

---

## COMPLETION CHECKLIST

- [ ] All 13 tasks completed in order
- [ ] Each task's inline `VALIDATE` command passed immediately after that task
- [ ] Full test suite (`pytest -q` at the `investments/goat` root) passes
- [ ] `ruff check` and `mypy` clean
- [ ] Manual validation performed during at least one real open-market window (Level 4)
- [ ] Manual validation performed during a closed-market window confirming the cheap no-op path
- [ ] Acceptance criteria all met
- [ ] `deploy.ps1` diff reviewed — only the `$TIMERS` array line added, nothing else touched
- [ ] HANDOFF.md status line updated

---

## NOTES

**Deliberately deferred / out of scope for this plan** (do not build speculatively):
- Market-holiday calendars for either exchange — a stale/None fetch on a holiday just gets skipped gracefully by the existing per-ticker error handling; a real holiday calendar is a distinct follow-up if ever needed.
- Any change to Phase 2 (sector rotation) or Phase 3 (heartbeat scanner) cadence — explicitly out of scope per HANDOFF.md's own line.
- yfinance rate-limit backoff/retry infrastructure — not built speculatively; only add if real rate-limiting is observed post-deploy at the new cadence.
- Pre-market/after-hours session coverage for either exchange — regular session only, matching Shaun's stated need ("while the market is still open," i.e. regular trading hours).
- Auto-enabling the new systemd timer on the VPS — requires Shaun's explicit go-ahead, same precedent as Phase 1's original rollout (HANDOFF.md status line: "systemd units exist but are NOT enabled on the VPS").

**Design decision worth flagging explicitly to Shaun after implementation**: because the live check and the daily EOD check now share one dedup key, if a holding dips below its 150DMA intraday, gets alerted live, recovers by end of day (auto-acknowledged by the next `run_monitor`/`run_live_monitor` that sees it back above threshold), and then dips again the *same or a later* day, that's correctly treated as a fresh event and re-alerts — this matches the already-existing (pre-this-feature) recovery/re-alert behavior of the daily check, just now able to fire and recover faster. Worth a one-line mention when reporting this feature complete, not a design question to resolve now — it's the natural, already-tested consequence of Phase 1's existing dedup semantics (`test_run_monitor_auto_acknowledges_on_recovery`) extended to a faster cadence.

**Confidence score: 8/10** for one-pass implementation success. The two points of highest risk are (a) the exact systemd `OnCalendar=*:0/10` syntax and DST behavior should be double-checked with `systemd-analyze calendar` on the actual VPS rather than trusted blindly from this plan, and (b) whether yfinance's `.history()` call inside `fetch_close_history` actually does include a partial today-bar during market hours in practice is asserted here from general yfinance behavior/caution, not confirmed against this specific codebase's usage — Task 5's `_completed_closes_only` guard is written to be safe either way (a no-op if there's no partial bar), but the manual Level 4 validation step should explicitly print the last 2 rows of a live-fetched `close` series during a real market-hours run to confirm this empirically once, rather than assuming.
