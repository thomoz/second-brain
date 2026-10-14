# Feature: Volume-Spike + Record-Earnings Scanner (US Small/Micro-Cap)

The following plan should be complete, but it's important to validate documentation and
codebase patterns and task sanity before implementing. Pay special attention to naming
of existing utils/types/models — import from the right files.

## Feature Description

A new daily-scheduled investments scanner that screens US small/micro-cap stocks for
two independent "Wall St is about to notice this" signals:

1. **Volume spike** — today's trading volume is far above its recent average, a proxy
   for institutional money quietly starting to flow into a name.
2. **Record earnings** — the most recently reported quarter represents a record (by the
   two definitions below) for that company's earnings, a sign the underlying business
   just had a breakout quarter before the market has caught up.

Either signal alone stages a candidate and fires a WhatsApp alert; a ticker that fires
both in the same run is called out specially as the strongest case. This mirrors (and
deliberately does not replace) Goat's existing large/mid-cap discovery scans — this one
is scoped specifically to the small/micro-cap names those scans structurally exclude.

## User Story

As Shaun, running several businesses and investing on the side,
I want a daily automated scan of small/micro-cap US stocks for unusual volume activity
or a record earnings quarter,
So that I get an early WhatsApp nudge on names that may be about to get discovered by
Wall St, without having to manually screen for them myself.

## Problem Statement

Shaun saw a TradingView-style per-ticker volume-spike alert and a "Winston Stock Radar"
screen for record-earnings-quarter small/micro-caps and wants both ideas built as one
automated tool, scoped to small/micro-caps specifically (confirmed 2026-10-11 — he
thinks this signal class is better suited to that cap range than large/mid-cap, which
Goat's existing scanners already cover).

## Solution Statement

A new sibling investments workspace package, `volume-earnings-scanner`, built to the
same shape as the most recent precedent in this codebase — `ai-resistant-moat-scanner`
(built 2026-09, same universe-caching + daily-slice + staging + promote/dismiss +
WhatsApp-alert shape). US-only Finviz-screened small/micro-cap universe; two
independent per-ticker signal checks; staging into its own pending-candidates table;
daily systemd timer; WhatsApp alert on new candidates; zero-candidate days silent.

## Feature Metadata

**Feature Type**: New Capability (new investments package)
**Estimated Complexity**: Medium-High (new package scaffold + two genuinely new signal
types neither of which has a working precedent anywhere in this codebase yet — see
Gotchas)
**Primary Systems Affected**: `investments/` workspace (new package), shared
`investments.db` (VPS-only), `scripts/deploy.ps1`, `scripts/invoke_investments.ps1`,
`scripts/systemd/`, `investments/TOOLS.md`
**Dependencies**: `my-trader` (workspace dependency — ethical filter, finviz_screener,
market_data, holdings/watchlist dedup, snapshot), `yfinance`, `requests`,
`beautifulsoup4`, `pandas`

---

## DECISIONS RESOLVED (read first — these answer the plan-feature prompt's open questions)

**1. New sibling package, not a Goat scan.** Goat's own universes are index-membership
lists (S&P 500 / FTSE 100 / ASX 200) — structurally large/mid-cap by construction, and
`goat_pending_candidates` has no columns for `volume_ratio` or EPS data. Shoehorning a
Finviz-screened small/micro-cap universe with different staged-row fields into Goat
would mean either polluting `goat_pending_candidates`'s shared schema or bolting on a
second table inside a package whose whole identity is index-based discovery. The
`ai-resistant-moat-scanner` precedent (built exactly for this reason — a Finviz-screened
universe with its own scoring, own table, own report) is the closer analogue; mirror it
file-for-file.

**2. Volume spike and record earnings are independent (OR) triggers, not an AND gate.**
Shaun described record earnings as "**another** sign" alongside volume, not a
requirement that both align — same framing this codebase already uses for every other
multi-signal check (DMA Breakout's 150-day/200-day crosses are independent; Earnings
Watch's three signals are independent, not combined into one verdict). Default: either
signal alone stages + alerts. When both fire on the same ticker in the same run, the
candidate's `signal_type` is `"both"` and the report/WhatsApp line is prefixed
`BOTH SIGNALS —` so Shaun can see the strongest case at a glance. Flag this as
**v1/tunable** — if it proves too noisy, the fix is changing one `if` in `scan.py`, not
a redesign.

**3. "Record" earnings, precisely (this needs live verification — see Gotcha #1).**
Free yfinance quarterly data only goes back ~4-5 quarters in practice (confirmed
nowhere else in this codebase — this is genuinely new ground, same "verify live, don't
assume" posture as `GOAT_FINVIZ_INDUSTRY_SLUGS`/the Finviz ticker-watermark discovery).
Given that shallow history, "record" is defined two ways, either of which qualifies —
**honestly documented as "record within the available free-data window," not a true
all-time record**:
   - **Record EPS**: the latest reported quarter's diluted EPS is the highest of every
     quarter in the fetched history (works even with only 4 quarters, no YoY math
     needed).
   - **Accelerating YoY growth**: the latest quarter's YoY EPS growth (vs. the same
     quarter a year ago) is the fastest YoY growth of every YoY-comparable quarter pair
     in the fetched history (the Winston app's "EPS growing faster each quarter"
     framing) — requires at least 5 quarters of history to compute even one prior
     comparison point; degrades to `"insufficient history"` below that (same posture as
     `earnings_watch.compute_estimate_trend`'s `EARNINGS_WATCH_TREND_MIN_DATAPOINTS`
     gate).

**4. Universe.** US-only (confirmed — no good free ASX micro-cap constituent source).
Two Finviz screens, unioned and deduped — mirrors
`ai_resistant_moat_scanner/universe.py`'s own multi-screen-then-merge pattern exactly
(that file merges per-sector screens; this merges per-cap-bucket screens instead):
   - micro+nano: `cap_microunder,geo_usa,sh_avgvol_o100,sh_price_o1`
   - small: `cap_small,geo_usa,sh_avgvol_o100,sh_price_o1`

   Together these approximate $0–$2B market cap, liquidity-floored at 100K avg daily
   volume and $1 price (same floor values as `FINVIZ_SCREENER_FILTERS`/
   `GOAT_DMA_BREAKOUT_MIN_AVG_VOLUME`). **The exact Finviz cap-bucket token names must
   be live-verified against finviz.com/screener.ashx before shipping** — Finviz's
   compound cap filters (`cap_microunder` = nano+micro i.e. "micro and under",
   `cap_small` = exact small-cap bucket only) are a best-guess from the filter-naming
   convention already reverse-engineered for `GOAT_FINVIZ_INDUSTRY_SLUGS`, not
   confirmed live during this planning pass.

---

## CONTEXT REFERENCES

### Relevant Codebase Files — READ THESE BEFORE IMPLEMENTING

- `investments/ai-resistant-moat-scanner/ai_resistant_moat_scanner/` (whole package) —
  **the primary template.** Copy its shape almost exactly:
  - `pyproject.toml` — workspace package definition, `my-trader` as a `tool.uv.sources`
    workspace dependency, `dev` extras, pytest/ruff/mypy config, hatchling build target.
  - `main.py` (131 lines) — CLI shape: `_open_conn()` (init_db + get_connection +
    init_mytrader_tables + this package's own `init_*_tables`), `cmd_scan`,
    `cmd_promote_candidate` (writes into my-trader's watchlist via
    `mytrader.db.upsert_watchlist_row` + `mytrader.snapshot.regenerate_all`, the one
    deliberate cross-package write, same comment convention — "Deliberate, explicit
    exception to 'this package never writes into my-trader's tables'"),
    `cmd_dismiss_candidate`, `argparse` subparser wiring.
  - `db.py` (170 lines) — `init_*_tables(conn)` with `CREATE TABLE IF NOT EXISTS` +
    idempotent `_MIGRATIONS` tuple hook (empty, kept ready); `*_pending_candidates`
    table with `ticker TEXT NOT NULL UNIQUE`; `insert_*_pending_candidate` returns
    `bool` (`cur.rowcount == 1`) for "was this newly staged"; `get_*_pending_candidate`
    / `get_all_*_pending_candidates` / `delete_*_pending_candidate`.
  - `universe.py` (103 lines) — multi-screen Finviz fetch-merge-dedup pattern
    (`fetch_screened_universe`), TTL-cached via a `*_universe_cache` table
    (`get_or_refresh_screened_universe`, stale-fallback posture: "a scrape failure must
    never leave the scan with zero names when a good week-old cache exists"), daily
    rotating slice (`date.today().toordinal() % n_slices`).
  - `scan.py` (143 lines) — orchestrator shape: `market_data.cached_session()`
    wrapping the per-ticker loop, per-ticker `try/except` so one bad ticker can't sink
    the run, ethical-filter check first (`scripts.ethical_filter.check_ticker`), held/
    watchlist/staged tagging (scored+shown but never re-staged), `time.sleep` between
    yfinance calls.
  - `notify.py` (42 lines) — **copy this almost verbatim**, just change the title
    string and the per-candidate line format.
  - `tests/conftest.py` (75 lines) — `db_conn`/`db_path` fixtures, `_isolate_report_paths`
    (monkeypatches report path constants to `tmp_path`), `_no_real_network` (stubs every
    network/LLM entrypoint — **mirror this list, adding stubs for whatever new
    `yfinance` calls this package introduces**), the `_raising_run_text` "un-stubbed LLM
    call fails loudly" pattern (not needed here — this package makes no LLM calls, but
    keep the no-network discipline).
  - `tests/test_scan.py` (lines 1-90 read) — shows exactly how `scan.run_scan` gets unit
    tested: monkeypatch `universe.get_scan_universe`, `mytrader.market_data.fetch_ticker_data`,
    and the scoring functions; assert on `db.get_all_*_pending_candidates` + the
    returned `result["new_candidates"]`.

- `investments/goat/goat/dma_breakout_scan.py` (365 lines) — the liquidity-floor
  (`passes_liquidity_floor`, lines 184-212) and staging-dedup-against-holdings/watchlist
  (lines 250-259: banned-ticker check, `mt_db.get_holding_row`,
  `mt_db.get_watchlist_row`, already-staged check, in that order) idioms to mirror.
  Also the module-docstring convention of explaining *why* this tool is simpler/
  different from its siblings.

- `investments/goat/goat/price_history.py` (67 lines) — `fetch_close_volume_history`
  (lines 37-66): the exact close+volume fetch shape to **port, not import** (goat
  depends on my-trader, not the reverse, and this new package is a my-trader-dependent
  sibling of goat, not a goat dependant — see `GOAT_INDUSTRY_ETFS`'s own migration
  comment in `goat/config.py` lines 150-154 for why a cross-package import here would be
  a circular/wrong-direction dependency). `earnings_watch.py`'s own
  `_fetch_close_history` (lines 283-304) is the established precedent for this exact
  "private copy, not a shared import" decision — same docstring convention to reuse.

- `investments/my-trader/mytrader/cash_value_scan.py` (393 lines) — the two-pass
  coarse-Finviz-then-precise-yfinance idiom (`_enrich_universe`, lines 147-212):
  Finviz's `market_cap_text`/`price_text` are **strings**, not parsed numbers — real
  `marketCap`/`regularMarketPrice` come from the yfinance `.info` dict at the precise
  stage, never parsed out of Finviz's text column. Also the rate-limit-tripwire
  `DEGRADED` banner pattern (`_write_banner`, lines 362-379) if this package's own
  report needs the same staleness protection (optional — this package stages/alerts
  rather than overwriting a single always-current report table, so may not need it; the
  execution agent should judge based on how `report.py` ends up shaped).

- `investments/my-trader/mytrader/finviz_screener.py` (187 lines) — `fetch_screener_universe(filters=None, sort="pricecash")`,
  already supports custom `filters`/`sort` (see its own docstring, lines 149-159:
  "other callers (e.g. the AI-resistant-moat scanner) pass their own"). Returns
  `list[dict] | None`; each row has `ticker`/`company`/`sector`/`industry`/`country`/
  `market_cap_text`/`price_text` keys. Ticker watermark-descrambling already handled
  internally — no new handling needed.

- `investments/my-trader/mytrader/market_data.py` (lines 1-120 read) — `TickerData`
  dataclass (`ticker`, `info`, `dividends`, `news`, `calendar` — **no EPS/earnings
  field**, see Gotcha #1), `fetch_ticker_data(ticker) -> TickerData | None` (tries `.AX`
  fallback — irrelevant here since this scan is US-only, but harmless), `cached_session()`
  context manager (prevents O(n²) re-fetch storms across a scan loop).

- `investments/my-trader/mytrader/earnings_watch.py` (522 lines) — the closest existing
  precedent for "pull something earnings-shaped out of yfinance that's never been used
  in this codebase before": `fetch_estimate_snapshot` (lines 81-129) shows the
  `yf_retry.call(lambda: t.<attribute>)` + empty/missing-index degradation shape to
  copy for whatever quarterly-EPS accessor Phase 0 settles on.
  `compute_estimate_trend` (lines 144-188) shows the "insufficient history yet" /
  `"unknown"` verdict shape for a signal that needs N data points. **Does NOT use actual
  reported quarterly EPS anywhere** (only forward estimates via `.eps_trend`/
  `.earnings_estimate`) — confirmed via repo-wide grep, this plan is the first thing in
  the codebase to touch reported quarterly EPS history. Treat Phase 0 as genuinely
  unresearched, same posture as `GOAT_HEARTBEAT_HISTORY_LOOKBACK_DAYS`'s own "first
  attempt structurally couldn't pass, had to be redesigned against real data" history.

- `investments/goat/goat/main.py` (481 lines) — `_PROMOTE_LABELS` dict keyed by
  `source` (lines 308-315) if this package's candidates ever need distinguishable
  promote labels per signal type (`"volume_spike"` vs `"record_earnings"` vs `"both"`)
  — optional refinement, not required for v1 (a single promote label is fine, same as
  `ai_resistant_moat_scanner.main.cmd_promote_candidate`'s single fixed
  `"AI-moat-approved — {thesis}"` label).

- `investments/TOOLS.md` — the "Daily Read" / "Automated (scheduled)" tables (lines
  12-57) this package's row gets added to once built (not part of this plan's
  implementation tasks — flagged as a follow-up, matching the file's own "update this
  file whenever a tool's schedule, command, or output path changes; it isn't
  regenerated automatically" instruction at the top).

- `scripts/systemd/second-brain-ai-moat-scan.service` + `.timer` — the exact systemd
  unit shape to copy (oneshot service, `WorkingDirectory`/`ExecStart` pointed at the new
  package, `StandardOutput`/`StandardError` appended to a `*_runs.log` in the package
  dir; timer `OnCalendar=*-*-* HH:MM:00 UTC` + `Persistent=true`).

- `scripts/deploy.ps1` (lines 17-34, `$TIMERS` array) — **GOTCHA**: the real existing
  `second-brain-ai-moat-scan.timer` is NOT in this list today (confirmed via grep while
  researching this plan — an actual gap in the codebase, not a misreading). Add the new
  timer here. Do not repeat the same omission for this tool.

- `scripts/invoke_investments.ps1` — `$PACKAGES` hashtable (lines 34-41) and the
  `ValidateSet` (line 24) both need a new entry for the new package
  (`"volume-earnings-scanner" = @{ Dir = "volume-earnings-scanner"; Module =
  "volume_earnings_scanner.main" }`), or `-Package volume-earnings-scanner` will fail
  PowerShell parameter validation before ever reaching SSH.

- `investments/pyproject.toml` (3 lines) — `tool.uv.workspace.members` list; add
  `"volume-earnings-scanner"`.

### New Files to Create

```
investments/volume-earnings-scanner/
  pyproject.toml
  README.md                                  (optional, short — mirrors moat-scanner's)
  DEPLOY.md                                  (VPS deploy steps, mirrors moat-scanner's)
  volume_earnings_scanner/
    __init__.py
    config.py           # path constants, Finviz filter strings, thresholds (all the
                         # "DECISIONS RESOLVED" numbers above, written as named
                         # constants with the same dated/rationale comment convention
                         # as goat/config.py and mytrader/config.py)
    db.py                # init_ve_tables: volume_earnings_pending_candidates +
                          # volume_earnings_universe_cache (mirrors moat_pending_
                          # candidates / moat_universe_cache schemas)
    universe.py           # two-screen Finviz fetch-merge-dedup + TTL cache + daily
                           # slice (mirrors ai_resistant_moat_scanner/universe.py)
    price_history.py      # ported fetch_close_volume_history (see Context Refs)
    volume_signal.py       # check_volume_spike(ticker, close, volume) -> CheckResult-
                            # shaped dict (ratio calc + threshold compare)
    earnings_signal.py     # fetch_quarterly_eps_history(ticker) [Phase 0 output lives
                            # here] + check_record_earnings(ticker, eps_history) ->
                            # CheckResult-shaped dict (record-EPS + accelerating-YoY
                            # logic from Decision #3)
    scan.py                # run_scan(conn) orchestrator (mirrors ai_resistant_moat_
                            # scanner/scan.py's run_scan shape)
    report.py               # render + write candidates-pending-review.md (mirrors
                             # goat's render_dma_breakout_candidates_report shape)
    notify.py                # mirrors ai_resistant_moat_scanner/notify.py near-verbatim
    main.py                   # CLI: scan / promote-candidate / dismiss-candidate
    tests/
      __init__.py
      conftest.py            # mirrors ai_resistant_moat_scanner/tests/conftest.py
      test_config.py
      test_db.py
      test_universe.py
      test_price_history.py
      test_volume_signal.py
      test_earnings_signal.py
      test_scan.py
      test_notify.py
      test_report.py

scripts/systemd/second-brain-volume-earnings-scan.service
scripts/systemd/second-brain-volume-earnings-scan.timer
```

### Files to Update

- `investments/pyproject.toml` — add workspace member.
- `scripts/deploy.ps1` — add `"second-brain-volume-earnings-scan.timer"` to `$TIMERS`.
- `scripts/invoke_investments.ps1` — add `ValidateSet` entry + `$PACKAGES` row.

### Patterns to Follow

**Naming**: package dir `volume-earnings-scanner` (kebab), module
`volume_earnings_scanner` (snake), matching `ai-resistant-moat-scanner` /
`ai_resistant_moat_scanner` exactly. Constants prefixed `VE_` (short, this codebase's
convention is a short all-caps package prefix — `GOAT_`, `CASH_VALUE_`, `MOAT_`,
`EARNINGS_WATCH_`).

**Error handling**: every per-ticker iteration wrapped in `try/except Exception as e:
print(f"[volume-earnings-scan] error on {ticker}: {e}")` — one bad ticker never sinks
the run. Every fetch function returns `None` on failure/missing-data rather than
raising, mirroring `market_data.fetch_ticker_data`'s and `price_history.fetch_close_history`'s
posture throughout this codebase.

**Logging**: bracketed-module-name prefix on every print, e.g.
`[volume-earnings-scan] ...` (see every scan module in this codebase).

**"Unknown" vs "flag" vs "interesting" verdicts**: use the same three-state vocabulary
`CheckResult` already establishes (`mytrader/checks/__init__.py`'s `CheckResult`) for
consistency, even though this package's own signal functions can return plain dicts
rather than a full `CheckResult` if that's simpler for a scan-shaped (not Find-shaped)
tool — `dma_breakout_scan.check_ma_cross` is the precedent for a scan module using
`CheckResult` directly; decide during Task 3/4 which is less friction.

---

## IMPLEMENTATION PLAN

### Phase 0: Live Research (do this BEFORE writing any signal logic)

This phase exists because both signals touch yfinance surface area nothing else in this
codebase has used (reported quarterly EPS history; Finviz market-cap-bucket filter
tokens). Skipping straight to implementation risks silently building against a
made-up field name — same failure mode the Finviz ticker-watermark bug and the
`GOAT_FINVIZ_INDUSTRY_SLUGS` live-verification note both already caught elsewhere in
this codebase.

**Tasks:**
- In a scratch Python shell (`uv run --directory investments/my-trader python`, since
  `yfinance` is already a my-trader dependency), run `yfinance.Ticker("NVDA")` (a name
  guaranteed to have rich history) and inspect, in order of preference:
  1. `t.quarterly_income_stmt` — confirm it exists on the installed yfinance version
     (`grep yfinance investments/my-trader/pyproject.toml` for the pinned version
     first), confirm the exact row label for diluted EPS (expect `"Diluted EPS"` or
     `"Basic EPS"` — row labels are a `pandas.Index`, print `.index.tolist()`), and
     count how many quarterly columns come back (expect 4-5).
  2. `t.earnings_history` — if present, this may be a cleaner source (already
     epsActual/epsEstimate/surprisePercent per the last 4 reported quarters, no row-
     label parsing needed). Compare row count against (1).
  3. Confirm `t.quarterly_earnings` is in fact removed/deprecated on the pinned
     yfinance version (it was a simpler `Revenue`/`Earnings` quarterly frame in older
     yfinance) — if it still exists and is simpler, prefer it instead.
  - Repeat against one genuinely small/micro-cap ticker (not a mega-cap like NVDA) to
    confirm the same fields are populated for thinner-coverage names — small/micro-caps
    are exactly where yfinance data gaps are most likely (same caveat
    `cash_value_scan`'s own `CASH_VALUE_DEGRADED_ASX_MIN_FRACTION` tripwire exists for).
  - **VALIDATE**: document the chosen accessor + exact row/column labels + observed
    history depth as a code comment at the top of `earnings_signal.py`, same
    "LIVE-VERIFIED <date>" comment convention as `GOAT_FINVIZ_INDUSTRY_SLUGS`.
- Separately, live-check the two Finviz cap-bucket filter tokens from Decision #4
  (`cap_microunder`, `cap_small`) against `https://finviz.com/screener.ashx?f=<token>,geo_usa`
  — confirm each returns a plausible result count and that the returned names'
  `market_cap_text` column actually falls in the expected range (not an empty/wrong
  screen, same verification class as `finviz_screener.py`'s own ticker-watermark
  discovery). **VALIDATE**: note the live-verified token strings (or corrected ones) in
  `config.py` next to `VE_FINVIZ_SCREENS`, same "live-verified" comment convention.

### Phase 1: Package Scaffold

**Tasks:**
- CREATE `investments/volume-earnings-scanner/pyproject.toml` — mirror
  `ai-resistant-moat-scanner/pyproject.toml` exactly (same `dependencies`,
  `tool.uv.sources`, `dev` extras, `pytest`/`ruff`/`mypy` config, hatchling build
  target), `name = "volume-earnings-scanner"`.
- UPDATE `investments/pyproject.toml` — add `"volume-earnings-scanner"` to
  `tool.uv.workspace.members`.
- CREATE `volume_earnings_scanner/__init__.py` (empty, matches every sibling package).
- CREATE `volume_earnings_scanner/config.py` — `VE_DIR`, report path constants
  (`VE_SCAN_REPORT_PATH`, `VE_CANDIDATES_MD_PATH`), the two Finviz screen strings
  (Phase 0 output), `VE_UNIVERSE_SLICES` (start at the same `5` as
  `MOAT_UNIVERSE_SLICES` — a daily-rotating small/micro-cap universe is likely larger
  than the moat scanner's sector screens, tune after Phase 0 confirms actual result
  counts), `VE_VOLUME_SPIKE_RATIO_THRESHOLD = 3.0` (the "300%" figure from the
  TradingView inspiration image), `VE_VOLUME_AVG_WINDOW_DAYS = 20`,
  `VE_VOLUME_MIN_AVG_VOLUME = 100_000` (matches `GOAT_DMA_BREAKOUT_MIN_AVG_VOLUME`),
  `VE_MIN_MARKET_CAP_USD = 50_000_000.0` / `VE_MAX_MARKET_CAP_USD = 2_000_000_000.0`,
  `VE_MIN_PRICE_USD = 1.0`, `VE_EARNINGS_MIN_QUARTERS_FOR_RECORD = 4`,
  `VE_EARNINGS_MIN_QUARTERS_FOR_YOY_ACCEL = 5`, `VE_FETCH_DELAY_SECONDS = 0.2`
  (matches `CASH_VALUE_FETCH_DELAY_SECONDS`). Every threshold gets the same
  "v1/tunable, start conservative" comment convention as `cash_value_scan`/
  `moat_scanner`'s own config constants.
  - **GOTCHA**: `DB_PATH` comes from `scripts.config` (re-exported, same as
    `goat/config.py` line 7 — `from scripts.config import DB_PATH`), not redefined.

### Phase 2: Universe + DB

**Tasks:**
- CREATE `volume_earnings_scanner/db.py` — `init_ve_tables(conn)`:
  `volume_earnings_pending_candidates` (`id`, `ticker TEXT UNIQUE`, `signal_type TEXT`
  — `'volume'|'earnings'|'both'`, `signal_detail TEXT`, `company_name TEXT`,
  `source TEXT DEFAULT 'volume_earnings_scan'`, `flagged_at TEXT`) +
  `volume_earnings_universe_cache` (mirrors `moat_universe_cache` exactly: `ticker PK`,
  `company`, `market_cap_text`, `fetched_at`). Idempotent `_MIGRATIONS` hook, empty,
  kept ready (mirrors `db.py` lines 51-60 in the moat scanner exactly).
  - `insert_ve_pending_candidate(...) -> bool`, `get_ve_pending_candidate`,
    `get_all_ve_pending_candidates`, `delete_ve_pending_candidate`,
    `get_universe_cache_fetched_at`, `replace_universe_cache`, `get_universe_cache`.
  - **VALIDATE**: `uv run --directory investments/volume-earnings-scanner pytest volume_earnings_scanner/tests/test_db.py -v`
- CREATE `volume_earnings_scanner/universe.py` — `fetch_screened_universe()` (run both
  Finviz screens, merge+dedupe by ticker — mirrors `ai_resistant_moat_scanner/universe.py`
  lines 26-56 almost exactly, just two cap-bucket screens instead of N sector screens),
  `get_or_refresh_screened_universe(conn)` (TTL cache + stale-fallback, mirrors lines
  59-79), `get_scan_universe(conn)` (daily slice, mirrors lines 82-103).
  - **VALIDATE**: `uv run --directory investments/volume-earnings-scanner pytest volume_earnings_scanner/tests/test_universe.py -v`

### Phase 3: Signal 1 — Volume Spike

**Tasks:**
- CREATE `volume_earnings_scanner/price_history.py` — port
  `goat/price_history.py`'s `fetch_close_volume_history` verbatim (same `.AX`-fallback
  shape is harmless even though this scan is US-only — keeps the ported function a
  faithful copy rather than a divergent rewrite, same "ported rather than imported"
  posture its docstring already states for its own origin).
- CREATE `volume_earnings_scanner/volume_signal.py` —
  `check_volume_spike(ticker, close, volume) -> dict`: compute trailing
  `VE_VOLUME_AVG_WINDOW_DAYS`-day average volume **excluding today**
  (`volume.iloc[-(window+1):-1].mean()`), compute `ratio = volume.iloc[-1] / trailing_avg`,
  return `{"verdict": "interesting", ...}` when
  `ratio >= VE_VOLUME_SPIKE_RATIO_THRESHOLD`, else `{"verdict": "ok", ...}`; `"unknown"`
  if fewer than `window + 1` volume days are available (same insufficient-history
  posture as `check_ma_cross`). Guard against a trailing average of `0`/`NaN` (illiquid
  or missing data) — return `"unknown"`, never divide by zero.
  - **GOTCHA**: `GOAT_DMA_BREAKOUT_MIN_AVG_VOLUME`'s liquidity floor is checked via
    yfinance's `averageVolume` `.info` field (a ~3-month rolling average Yahoo
    computes) — this signal's own 20-day trailing average is a **different, shorter**
    window computed from the fetched price/volume history, by design (today's spike
    needs to be measured against *recent* normal, not a 3-month baseline that a whole
    quarter of rising volume would already have dragged upward). Don't conflate the
    two numbers.
  - **VALIDATE**: `uv run --directory investments/volume-earnings-scanner pytest volume_earnings_scanner/tests/test_volume_signal.py -v`

### Phase 4: Signal 2 — Record Earnings

**Tasks:**
- CREATE `volume_earnings_scanner/earnings_signal.py` — `fetch_quarterly_eps_history(ticker) -> list[float] | None`
  using whatever accessor Phase 0 confirmed (newest-first list of diluted EPS values,
  `None` if the ticker has no usable quarterly earnings data — small/micro-caps with
  thin coverage are expected to degrade here, not crash). Same `yf_retry.call(lambda: ...)`
  wrapping as `earnings_watch.fetch_estimate_snapshot`.
  `check_record_earnings(ticker, eps_history) -> dict`: implements Decision #3 (record
  EPS, min `VE_EARNINGS_MIN_QUARTERS_FOR_RECORD` quarters; accelerating YoY growth, min
  `VE_EARNINGS_MIN_QUARTERS_FOR_YOY_ACCEL` quarters) — returns `"interesting"` if either
  sub-check fires, `"unknown"` below the minimum quarter count, `"ok"` otherwise. Detail
  text states plainly which of the two (or both) fired, and is explicit that "record"
  means "record within the available reporting history," per Decision #3's honesty
  requirement.
  - **VALIDATE**: `uv run --directory investments/volume-earnings-scanner pytest volume_earnings_scanner/tests/test_earnings_signal.py -v`

### Phase 5: Orchestration, Staging, Report, Notify

**Tasks:**
- CREATE `volume_earnings_scanner/scan.py` — `run_scan(conn) -> dict`: mirrors
  `ai_resistant_moat_scanner/scan.py`'s `run_scan` shape (universe → ethical filter →
  held/watchlist/staged tagging → `market_data.cached_session()` loop → per-ticker
  try/except). Per ticker: fetch close+volume history (Phase 3's fetcher) → run
  `check_volume_spike` → fetch EPS history (Phase 4's fetcher) → run
  `check_record_earnings` → if either `"interesting"`, apply the liquidity/market-cap/
  price precise-test floor (same two-pass idiom as `cash_value_scan`) → skip if already
  held/watchlisted/staged (mirrors `dma_breakout_scan.py` lines 250-259's ordering) →
  stage via `insert_ve_pending_candidate` with `signal_type` set to `"volume"`,
  `"earnings"`, or `"both"` as appropriate.
- CREATE `volume_earnings_scanner/report.py` — `render_candidates_report` /
  `write_candidates_report` (mirrors `dma_breakout_scan.render_dma_breakout_candidates_report`
  shape: table of ticker/company/signal_type/detail/flagged date, sorted newest-first).
  A `"BOTH SIGNALS — "` detail prefix for `signal_type == "both"` rows per Decision #2.
- CREATE `volume_earnings_scanner/notify.py` — copy
  `ai_resistant_moat_scanner/notify.py` near-verbatim: title `"Volume/Earnings Scanner Alert"`,
  per-candidate WhatsApp line format `"{ticker} — {company} ({signal_type}): {detail}"`.
- CREATE `volume_earnings_scanner/main.py` — mirrors
  `ai_resistant_moat_scanner/main.py`: `_open_conn`, `cmd_scan`, `cmd_promote_candidate`
  (writes into my-trader's watchlist, same deliberate-exception comment),
  `cmd_dismiss_candidate`, `argparse` wiring with subcommands `scan` /
  `promote-candidate --ticker X` / `dismiss-candidate --ticker X`.
  - **VALIDATE**: `uv run --directory investments/volume-earnings-scanner python -m volume_earnings_scanner.main scan` against a disposable local SQLite DB (never the real VPS `investments.db` — see the package's own module docstring warning, copied from `ai_resistant_moat_scanner/main.py` lines 8-10) to confirm the CLI wires together end-to-end before writing tests.

### Phase 6: Tests

**Tasks:**
- CREATE `tests/conftest.py` — mirrors `ai_resistant_moat_scanner/tests/conftest.py`:
  `db_path`/`db_conn` fixtures, `_isolate_report_paths` (monkeypatch this package's own
  report-path constants), `_no_real_network` (stub `mytrader.finviz_screener.fetch_screener_universe`,
  `mytrader.market_data.fetch_ticker_data`, and this package's own
  `price_history.fetch_close_volume_history` + `earnings_signal.fetch_quarterly_eps_history`
  — no LLM calls in this package, so no `run_text` stub needed, unlike the moat
  scanner).
- CREATE one test file per new module (`test_config.py` just sanity-checks path
  constants resolve; the rest exercise the real logic) — follow `test_scan.py`'s
  `_wire(monkeypatch, db_conn)` helper-function pattern (lines 43-62) for `scan.py`'s
  own tests: a fixture ticker with a known volume history that should/shouldn't trip
  the spike threshold, a fixture EPS history that should/shouldn't trip record/
  accelerating-YoY, one test asserting a `"both"`-signal_type stage + WhatsApp-detail
  prefix, one test asserting a held/watchlisted ticker is never (re)staged even when a
  signal fires.
  - **VALIDATE**: `uv run --directory investments/volume-earnings-scanner pytest -v`
    (full suite)

### Phase 7: Deployment Wiring

**Tasks:**
- CREATE `scripts/systemd/second-brain-volume-earnings-scan.service` — mirrors
  `second-brain-ai-moat-scan.service`, `WorkingDirectory`/`ExecStart` pointed at
  `investments/volume-earnings-scanner`, module
  `volume_earnings_scanner.main scan`, log file
  `investments/volume-earnings-scanner/volume_earnings_scan_runs.log`.
- CREATE `scripts/systemd/second-brain-volume-earnings-scan.timer` — pick a free daily
  UTC slot; `23:58 UTC` sits right after Earnings Deterioration Watch (`23:55`) and
  before nothing else currently scheduled (cross-check `investments/TOOLS.md`'s
  "Automated (scheduled)" table before finalizing the exact minute, in case a later
  edit to this plan or the codebase has filled that slot). `Persistent=true` per every
  other daily-cadence timer in this codebase (a missed day catches up, rather than
  silently skipping — the one explicit exception, `GOAT_DMA_BREAKOUT_PENDING_MAX_AGE_DAYS`'s
  explanation, is about auto-expiring stale candidates, not about `Persistent=`).
- UPDATE `scripts/deploy.ps1` — add `"second-brain-volume-earnings-scan.timer"` to
  `$TIMERS` (line ~17-34). **Do not also add `second-brain-ai-moat-scan.timer` here as
  a "fix" without confirming with Shaun first** — that's a pre-existing gap outside this
  plan's scope; flag it to Shaun separately rather than silently bundling an unrelated
  fix into this PR.
- UPDATE `scripts/invoke_investments.ps1` — add `"volume-earnings-scanner"` to the
  `ValidateSet` (line 24) and a matching entry to `$PACKAGES` (line ~34-41):
  `"volume-earnings-scanner" = @{ Dir = "volume-earnings-scanner"; Module = "volume_earnings_scanner.main" }`.
- CREATE `investments/volume-earnings-scanner/DEPLOY.md` — mirrors
  `ai-resistant-moat-scanner/DEPLOY.md`'s structure (uv sync on VPS, `scp` the systemd
  units up, `sudo systemctl daemon-reload && sudo systemctl enable --now
  second-brain-volume-earnings-scan.timer`, confirm via `sudo systemctl status`).
  Actually running these steps on the VPS is a manual action for Shaun (same posture as
  every other package's `DEPLOY.md`) — do not attempt SSH/VPS changes as part of this
  plan's own execution.

---

## TESTING STRATEGY

### Unit Tests
Every pure function (`check_volume_spike`, `check_record_earnings`,
`fetch_quarterly_eps_history`'s parsing logic) gets direct unit tests with constructed
`pandas.Series`/`list[float]` fixtures — no network. `scan.run_scan` gets tested with
every network/DB boundary monkeypatched, following `test_scan.py`'s `_wire()` helper
pattern exactly.

### Integration Tests
`main.py`'s `cmd_scan`/`cmd_promote_candidate`/`cmd_dismiss_candidate` against a
`tmp_path`-backed real SQLite DB (via the `db_conn` fixture) with network calls
monkeypatched — confirms the CLI → scan → db → report → notify chain wires together,
same level `ai_resistant_moat_scanner`'s own test suite operates at (no package in this
codebase appears to run genuinely live-network integration tests in CI; all rely on
monkeypatched fixtures).

### Edge Cases
- Ticker with <20 days of volume history (new listing) → `"unknown"`, never a
  false-positive spike from a near-empty trailing average.
- Ticker with exactly 4 quarters of EPS history → record-EPS check runs,
  accelerating-YoY check reports `"unknown"` (needs 5).
- Ticker with 0 or negative EPS in some quarters → YoY growth % math must not divide by
  zero or produce a nonsensical sign flip (mirror `earnings_watch.compute_estimate_trend`'s
  own `if earliest_avg == 0: return {"verdict": "unknown", ...}` guard).
- Ticker already held or watchlisted that trips both signals → scored/shown (if
  `report.py` chooses to show scored-but-not-staged rows, matching the moat scanner's
  own "held tickers are scored and shown, tagged, but never re-staged" posture) but
  never written to `volume_earnings_pending_candidates`.
- Finviz total failure on both screens in the same run → `universe.get_or_refresh_screened_universe`
  falls back to the existing cache (even if stale) rather than returning an empty
  universe, same as the moat scanner.
- A ticker already staged from a prior run that now ALSO trips the signal it hadn't
  before (was `"volume"`, now also trips `"earnings"`) — decide during Phase 5 whether
  `signal_type` upgrades to `"both"` on a re-run or stays at its originally-staged value
  (the `moat_pending_candidates` precedent is append-only / `INSERT OR IGNORE`, i.e.
  never updates an existing staged row — default to that same behavior unless Shaun
  asks for live upgrading).

---

## VALIDATION COMMANDS

### Level 1: Syntax & Style
```
uv run --directory investments/volume-earnings-scanner ruff check volume_earnings_scanner/
uv run --directory investments/volume-earnings-scanner mypy volume_earnings_scanner/
```

### Level 2: Unit Tests
```
uv run --directory investments/volume-earnings-scanner pytest -v
```

### Level 3: Integration Tests
Covered by the same `pytest -v` run above (`test_scan.py`/`test_main`-level tests use
the real `db_conn` fixture against a `tmp_path` SQLite file — no separate integration
test command exists elsewhere in this codebase either).

### Level 4: Manual Validation
```
# From the repo root, against a disposable local DB only -- NEVER the real VPS
# investments.db (see main.py's own module-docstring warning).
uv run --directory investments/volume-earnings-scanner python -m volume_earnings_scanner.main scan
```
Confirm: no exceptions, a `moat-candidates-pending-review.md`-shaped report file is
written, console summary line prints scanned/staged counts. Once genuinely ready for
production data, the real run is via
`scripts/invoke_investments.ps1 -Package volume-earnings-scanner -Command "scan"`
against the VPS — never a local `uv run` against the real workflow (same warning every
other package's CLI module docstring carries).

### Level 5: Additional Validation
None beyond the standard workspace tooling already listed above.

---

## ACCEPTANCE CRITERIA

- [ ] New `volume-earnings-scanner` package scans a live US small/micro-cap Finviz
      universe and stages genuinely new candidates on either a volume spike or a record
      earnings quarter (or both).
- [ ] Phase 0's live verification is documented in `earnings_signal.py` and `config.py`
      with the actual confirmed yfinance accessor + Finviz filter tokens, not
      assumptions.
- [ ] A ticker already held or watchlisted is scored but never staged/alerted.
- [ ] Zero-candidate runs are silent (no WhatsApp message).
- [ ] A ticker tripping both signals in one run is clearly marked `"both"` in the DB,
      report, and WhatsApp message.
- [ ] `ruff`/`mypy`/`pytest` all pass with zero errors.
- [ ] `promote-candidate`/`dismiss-candidate` work against a real (test) DB.
- [ ] Deployment wiring (`deploy.ps1`, `invoke_investments.ps1`, systemd units) is in
      place, though the actual VPS deploy itself is a manual follow-up for Shaun, not
      part of this plan's own execution.
- [ ] `investments/TOOLS.md` gets a new row once the tool is confirmed live (flagged as
      a follow-up task after this plan's execution, per the file's own update
      convention).

## COMPLETION CHECKLIST

- [ ] Phase 0 live research complete and documented before any signal logic is written
- [ ] All tasks completed in order (Phases 1-7)
- [ ] Each phase's validation command passed before moving to the next
- [ ] Full test suite passes
- [ ] No linting or type errors
- [ ] Manual `scan` run against a disposable local DB confirmed working
- [ ] Acceptance criteria all met
- [ ] Shaun has reviewed the Phase 0 findings (exact Finviz tokens, exact yfinance
      accessor) before the VPS deploy, since both are best-guesses in this plan that
      need live confirmation

---

## NOTES

- This plan deliberately does **not** attempt the actual VPS deploy, nor does it touch
  `investments/TOOLS.md` — both are explicit follow-ups once Shaun has reviewed the
  built tool, consistent with how every other recent tool in this codebase
  (`ai-resistant-moat-scanner`, `earnings-deterioration-watch`) shipped: build + test
  locally first, confirm with Shaun, deploy second.
- The `cap_microunder`/`cap_small` Finviz tokens and the `quarterly_income_stmt`
  (or equivalent) yfinance accessor are the two biggest unknowns in this plan — Phase 0
  exists specifically to de-risk them before any other code is written. If Phase 0
  turns up a materially different picture (e.g. Finviz's compound cap filters don't
  behave as named-convention suggests, or free yfinance quarterly data is even thinner
  than 4-5 quarters), stop and reconcile this plan's Decision #3/#4 sections before
  continuing — don't silently improvise past a wrong assumption.
- `VE_VOLUME_SPIKE_RATIO_THRESHOLD = 3.0` and the earnings "record" definitions are all
  explicitly v1/tunable, following this codebase's established precedent (Cash-Value
  Scan's 0.80→0.50, AI-Moat Scan's anti-signal penalty halving) of shipping a
  conservative first guess and tuning against the first few days of real output rather
  than hand-wringing over the exact number up front.
