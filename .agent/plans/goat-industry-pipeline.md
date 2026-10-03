# Feature: Goat Industry-Granularity Pipeline + Rotation Trend Tracking (+ ASX/ETF Candidate Extension)

The following plan should be complete, but it's important that you validate documentation and
codebase patterns and task sanity before you start implementing. Pay special attention to naming of
existing constants/utils/types — import from the right files, reuse constants that already exist
(`GOAT_SECTOR_MA_SHORT_DAYS`, `GOAT_SECTOR_SLOPE_LOOKBACK_DAYS`, `GOAT_SECTOR_CROSS_RECENCY_DAYS`,
`GOAT_BANNED_TICKERS`, `ETF_AUM_FLAG_USD`) rather than adding duplicates. This plan folds together
three previously separate handoffs that all touch the same files — read them in this order before
starting:

1. `investments/goat/industry-pipeline-handoff.md` (whole file) — the combined handoff this plan
   implements. Supersedes `investments/goat/rotation-trend-tracking-handoff.md` and
   `investments/goat/industry-heartbeat-pipeline-handoff.md` (both carry a superseded-by note).
2. `.agent/plans/goat-rotation-trend-tracking.md` — an earlier full plan for Part A alone; good
   reference for schema/compute-shape detail, superseded in scope by this combined plan.

## Feature Description

Goat's **industry** layer (`industry_rotation.py` → `industry-ranking.md`, shipped
`.agent/plans/completed/goat-industry-rotation-ranking.md`) is today a pure ranking report: 39 of
Finviz's 143 industries that have a dedicated ETF, ranked by 126-trading-day return, re-fetched and
fully overwritten on every run. It has **no breakout signal, no candidate staging, no stock-level
scan** — the sector level (`sector_rotation.py` + `monitor.run_sector_scan` + `heartbeat_scan.py`)
has all three. Neither `sector-ranking.md` nor `industry-ranking.md` carries any memory of a prior
run, so there is no way to answer "which way is this industry heading" without `git log -p`
archaeology. And neither the sector- nor industry-level stock scan can ever surface an ASX stock or
an ETF as a *candidate* (ASX/ETF stay gate-only inputs today).

This feature closes all three gaps in one coordinated change (they share `run_industry_scan`,
`cmd_monitor`'s connection lifecycle, and `goat_pending_candidates`' staging/report/promote
conventions, hence being planned together):

- **Part A — Rotation Trend Tracking.** A daily snapshot table + a "Rotation Flow" section on both
  `sector-ranking.md` and `industry-ranking.md` showing which tickers flipped Rising/Falling since
  the last snapshot (both the existing long-window sign and a new short-window "this week" sign),
  plus a read-only CLI query path and an on-demand chart (built fresh per request as a Claude Code
  Artifact — no new always-on infra).
- **Part B — Industry-Granularity Heartbeat Pipeline.** Industry ETF breakout detection + candidate
  staging (parity with the sector level), a cached US+ASX industry-constituent universe, and a
  stock-level heartbeat scan gated on which industries are *currently in a breakout*, not just
  rising.
- **Part C — ASX + ETF Candidate Extension.** Mirrors `dma_breakout_scan.py`'s already-validated
  approach: an ASX leg (sector- and industry-level) and an ETF-universe leg so an ASX stock or an
  ETF can, for the first time, be staged as a Goat candidate — not just serve as a gate signal.

## User Story

As Shaun, running Goat's daily pipeline to find and vet new positions
I want to (1) see which sectors/industries are rising **and which way they're trending**, (2) have
the industry layer gate a stock-level heartbeat scan the same way the sector layer already does, and
(3) have that same pipeline work for ASX stocks and ETFs, not just US stocks
So that I can run the full chain — rising industry → industry ETF heartbeat → constituent heartbeat →
fundamentals — end to end, across every market/vehicle Goat already tracks, with fresh candidates
landing in the same promote/dismiss review workflow I already use.

## Problem Statement

See `investments/goat/industry-pipeline-handoff.md`'s "Current State" table (lines 45–58) for the
full gap matrix. In one line: the industry layer is viewing-only, both rotation reports are
memoryless, and ASX/ETFs can only ever be a gate, never a staged candidate.

## Solution Statement

Eight phases, in dependency order (each phase's tests pass before starting the next):

1. Rotation snapshot schema + flow compute (long-window, unchanged from Decision 1–7 below, **plus**
   a new short-window diff — folded into this same phase per Shaun's 2026-10-03 confirmation, not a
   fast-follow, since it reuses closes already fetched for the ranking — no new data, no new fetch).
2. Wire it into `cmd_monitor` (connection-lifecycle fix, splice Rotation Flow into both ranking
   reports) + the read-only `query-rotation-history` CLI (Part A's addendum deliverable, so a Claude
   Code session can pull snapshot history straight into the `dataviz`/Artifact pipeline on request).
3. `check_industry_breakout` + candidate staging in `run_industry_scan` — brings the industry level
   to full parity with `run_sector_scan` (ranking + breakout + staging), including a new
   `industry-candidates-pending-review.md`.
4. Industry constituent universe: a cached `goat_industry_constituents` table fed by (a) Finviz's
   screener, parameterized per industry, for US tickers, and (b) a **new hand-curated**
   `GOAT_ASX_INDUSTRY_CONSTITUENTS` dict for ASX tickers (per Shaun's 2026-10-03 call — build this
   now, do not defer).
5. `industry_heartbeat_scan.py` — the stock-level scan: gated on industries whose ETF is *currently
   in a breakout* (Open Question 1(a), confirmed default), scans that industry's US+ASX constituents
   for `heartbeat.check_heartbeat_breakout`, attaches fundamentals survival context, stages into
   `goat_pending_candidates`.
6. ASX sector-level extension to the **existing** `heartbeat_scan.py` (adds a third constituent leg
   alongside the already-shipped US/LSE legs — `asx200_universe` + a new
   `GOAT_ASX_GICS_TO_ETF_SECTOR_LABEL` map).
7. ETF-as-candidate heartbeat leg — a new, separate `etf_heartbeat_scan.py` scanning
   `config.GOAT_DMA_BREAKOUT_ETF_UNIVERSE` (57 tickers: 11 sector + 39 industry + 7 broad/commodity)
   unconditionally for the same heartbeat pattern, independent of any sector/industry filter (mirrors
   how `dma_breakout_scan.py` already treats this same universe — no rising-filter concept applies to
   an ETF the way it does to a GICS-sector-mapped stock).
8. Tests, `TOOLS.md`, `conftest.py` path isolation, VPS timer wiring, full validation pass.

---

## Feature Metadata

**Feature Type**: New Capability (industry-level parity + ASX/ETF candidate support) + Enhancement
(rotation memory on two existing reports).
**Estimated Complexity**: High — 4 new orchestrator/support modules, 2 new DB tables, ~6 new CLI
subcommands, 1 breaking signature change (`run_industry_scan` gains a required `conn`), one
hand-curated data table (`GOAT_ASX_INDUSTRY_CONSTITUENTS`) requiring real research effort, 2 new VPS
timer units. No change to any existing threshold/check's math (`heartbeat.check_heartbeat_breakout`,
`exit_check.py`, `fundamentals_context.py` are all reused unchanged).
**Primary Systems Affected**: `investments/goat/goat/{config,db,main,monitor,industry_rotation,
sector_rotation,heartbeat_scan}.py` (modified); new `rotation_flow.py`, `industry_constituents.py`,
`industry_heartbeat_scan.py`, `etf_heartbeat_scan.py`; `investments/goat/goat/tests/` (new + updated
test files); `investments/TOOLS.md`; `scripts/deploy.ps1`'s `$TIMERS_TO_MANAGE` list; VPS systemd
units (created by hand on the VPS — no unit files live in this repo, see Phase 8).
**Dependencies**: None new. `finviz_screener.py`, `asx200_universe.py`, `sp500_universe.py`-style
caching, `fundamentals_context.py`, `heartbeat.py`'s `check_heartbeat_breakout`, `mytrader.checks`,
`mytrader.tickers` are all reused unchanged.

---

## DECISIONS CONFIRMED (handoff 2026-08-23/2026-09-02/2026-10-03, this planning session 2026-10-03)

### Part A (unchanged from the handoff, confirmed 2026-08-23)
1. **State model: 2-state Rising/Falling**, reusing the existing `rising: bool` (`return_pct > 0`).
   No 3-state DOWNHILL/BASE/CLIMBING model — explicitly deferred, do not build it.
2. **Comparison granularity: day-over-day** (both scans run daily via `monitor`).
3. **Schema: one shared snapshot table** (`scope`, `snapshot_date`, `ticker`, `label`, `return_pct`,
   `rank`, `rising`), not two scope-specific tables.
4. **Retention: cap at 90 days.**
5. **Write cadence: only the once-daily `monitor` run writes a snapshot.** On-demand `scan-sectors` /
   `scan-industries` compute and render as before but do NOT insert a snapshot row or show a Rotation
   Flow section (avoids same-day double-counting).
6. **Report layout: additive** — new section alongside existing tables, not a replacement.
7. **Filter chips** (per-industry drill-down): out of scope.

### Part A — this planning session (2026-10-03)
8. **Short-window flow ships in this same phase**, not a fast-follow — it's a pure diff over closes
   already fetched for the long-window ranking (no new fetch). Window: **1 trading week (5 trading
   days)** only — not also 1-month, to keep the new report section to one extra table rather than
   two; 1-month is a flagged, easy fast-follow if 1-week alone proves too noisy (see Notes).
9. **Chart**: on-demand only, built as a Claude Code Artifact per request, no new always-on
   infrastructure, no schedule. Default scope: Top-5/Bottom-5 for industry, all 11 for sector.
   Default plotted series: `return_pct` (long-window), with `return_pct_1w` available as a second
   series/toggle once short-window flow ships (it does, per Decision 8).
10. **`query-rotation-history` CLI ships in this same phase** (cheap, mechanical) — actually *using*
    it to build a chart is naturally gated on enough snapshot history existing (starts empty at ship
    time), that gating needs no code.

### Part B (confirmed 2026-08-23/2026-09-02, this session)
11. **Gate = (a) ETF-breakout-only**, plus **(c) a manual `--industries` override** on top. Not
    "any rising" (b) or top-N regardless of breakout (d) — keeps constituent-fetch counts bounded.
12. **Constituent source = Finviz screener** (reuse `finviz_screener.py`) for US; **hand-curated
    dict** for ASX (Decision 16 below) — not an ETF-holdings scrape, not yfinance `.info["industry"]`.
13. **Liquidity floor for the per-industry Finviz screen**: reuse the cash-value scan's existing
    `sh_avgvol_o100,sh_price_o1` filter string verbatim — no new, industry-specific number.
14. **104 non-ETF industries: skip for v1.** No synthetic equal-weight index. Flagged follow-up only.
15. **Supplement, not replace**, the existing `scan-heartbeat` (sector-level S&P500+FTSE100 scan
    stays exactly as-is; this adds a parallel industry-level scan + candidate source).
16. **History guard**: unchanged behavior — a ticker with insufficient history is silently skipped
    (same as every other Goat scan's per-ticker `try/except` + `continue`), no new surfaced count.
17. **Notification**: yes — WhatsApp ping on new industry-heartbeat candidates via the existing
    `monitor.maybe_notify`, same pattern as every other Goat scan.
18. **`cmd_promote_candidate`'s hardcoded "Goat-approved sector rotation candidate" label and
    `source="goat_sector_rotation"`** become source-aware (read the pending row's own `source` and
    label accordingly) — needed now because this plan adds 4 more distinct `source` values
    (`goat_industry_rotation`, `goat_industry_heartbeat_scan`, `goat_etf_heartbeat_scan`, plus the
    ASX leg riding on the existing `goat_heartbeat_scan` source).
19. **Industry ETF breakout gets full parity with sector ETF breakout**: `run_industry_scan` also
    stages a fresh industry-ETF breakout into `goat_pending_candidates` (source
    `goat_industry_rotation`), mirroring `monitor._stage_new_sector_candidates` exactly — this is why
    `run_industry_scan` needs a `conn` (the handoff's own note), not merely for Part A's snapshot
    capture (which is called from `cmd_monitor` directly, not from inside `run_industry_scan`).

### Part C — ASX/ETF extension (confirmed 2026-09-20, this session)
20. **ASX industry-level constituents: build a hand-curated mapping now** (Shaun, 2026-10-03) — do
    **not** defer this piece. `GOAT_ASX_INDUSTRY_CONSTITUENTS: dict[str, str]` (ticker → one of the
    143 `GOAT_FINVIZ_INDUSTRIES` labels), built during Phase 4 via real per-company research
    (cross-referencing ASX's own listing/GICS classification against Finviz's finer taxonomy — the
    same research discipline already used to build `GOAT_INDUSTRY_ETFS`, `GOAT_ICB_TO_ETF_SECTOR_LABEL`,
    and `MOAT_TARGET_INDUSTRIES`). Coverage does not need to be all 200 ASX 200 constituents on day
    one — an uncovered ASX ticker simply never appears as an industry constituent, the same "never
    silently substitute, list what's missing" posture `industry-ranking.md`'s own "Not Covered"
    section already uses. Extend coverage incrementally after shipping, same as `GOAT_INDUSTRY_ETFS`'s
    own "39 of 143, extend later" framing.
21. **ETF heartbeat thresholds reused unmodified for v1.** Same "ship, then tune on real data"
    posture as every other `v1/tunable` constant in `config.py` (`GOAT_SECTOR_CROSS_RECENCY_DAYS`,
    `GOAT_HEARTBEAT_BASE_RANGE_MAX_PCT`, etc.) — do not invent a separate looser ETF threshold set
    speculatively.
22. **ETF candidates scanned unconditionally every run** — no rising-sector/industry prefilter.
    Mirrors `dma_breakout_scan.fetch_universe_constituents`'s own ETF leg (lines 107–114), which
    applies no rising filter either; an ETF has no GICS-sector membership of its own to gate on the
    way a stock does.

### Explicitly NOT in scope (unchanged from the handoff — do not build)
- No automatic buy/sell action — advisor-notes-only (`SOUL.md`).
- No 3-state DOWNHILL/BASE/CLIMBING rotation model.
- No synthetic index for the 104 non-ETF industries.
- No new alerting on trend *drift* (Part A is visibility, not automation).
- No change to `rank_sectors` / `rank_industries`'s ranking maths (only additive new fields).
- No change to the sector-level pipeline's existing behaviour beyond the two additive legs above.
- No auto-rendered chart on a schedule, no always-on web dashboard/server.
- No change to `heartbeat.check_heartbeat_breakout`'s math (reused byte-for-byte everywhere).

---

## CONTEXT REFERENCES

### Relevant Codebase Files — YOU MUST READ THESE BEFORE IMPLEMENTING

- `investments/goat/industry-pipeline-handoff.md` (whole file) — primary spec, read first.
- `investments/goat/goat/industry_rotation.py` (49 lines, whole file) — `fetch_all_industry_closes`
  (lines 15–25), `rank_industries` (28–48, extend with `return_pct_1w`/`rising_1w`; add
  `check_industry_breakout` as a new function mirroring `sector_rotation.check_sector_breakout`).
- `investments/goat/goat/sector_rotation.py` (113 lines, whole file) — `rank_sectors` (30–50, same
  short-window extension); `check_sector_breakout` (53–113) is the exact template for
  `check_industry_breakout` — copy its sign-flip cross-detection + slope-gate shape verbatim, reusing
  `GOAT_SECTOR_MA_SHORT_DAYS`/`GOAT_SECTOR_SLOPE_LOOKBACK_DAYS`/`GOAT_SECTOR_CROSS_RECENCY_DAYS`
  as-is (do not clone into `GOAT_INDUSTRY_*` duplicates — the signal definition isn't
  granularity-specific, only the universe it's applied to changes). Per `heartbeat.py`'s module
  docstring convention (deliberate duplication over a shared helper), write `check_industry_breakout`
  as its own copy, not a refactor of `check_sector_breakout`.
- `investments/goat/goat/monitor.py` (410 lines, whole file) — `_stage_new_sector_candidates`
  (227–251) is the exact template for a new `_stage_new_industry_candidates`; `run_sector_scan`
  (254–273) is the exact template for the rewritten `run_industry_scan` (today at 332–341, no-conn,
  no breakout, no staging); `render_sector_candidates_report`/`write_sector_candidates_report`
  (304–329) is the exact template for new `render_industry_candidates_report`/
  `write_industry_candidates_report`; `render_industry_ranking_report` (344–403) is what gets the
  Rotation Flow splice (Phase 2) and a new "Currently Gated (Fresh Breakout)" note (Phase 3, mirrors
  how `render_sector_ranking_report`'s sibling candidates file works); `maybe_notify` (162–224) is
  reused unchanged by every new scan, just with a new `candidate_label` string per caller.
- `investments/goat/goat/heartbeat_scan.py` (176 lines, whole file) — `run_heartbeat_scan` (37–137)
  is the exact orchestration template for `industry_heartbeat_scan.py`: rising-filter → constituent
  loop → `fetch_close_volume_history` → `check_heartbeat_breakout` → `fundamentals_context` →
  insolvency suppression → three-way dedup → stage → `notify_detail` short-form. Its US+LSE
  constituent-filtering block (lines 46–65) is also the exact template for Phase 6's new ASX leg
  (add a third `for c in asx_constituents:` block following the same `etf_label = ...map.get(...)`
  pattern, `market="ASX"`, `tickers.asx_variant`).
- `investments/goat/goat/dma_breakout_scan.py` (365 lines, whole file) — `fetch_universe_constituents`
  (75–116) is the reference for how an ETF-only leg is appended without a rising-filter
  (`config.GOAT_DMA_BREAKOUT_ETF_UNIVERSE.items()`, lines 107–114) — mirror this shape exactly for
  Phase 7's `etf_heartbeat_scan.py`. `passes_liquidity_floor` (184–212) is reused as-is for the ETF
  AUM gate (`market == "ETF"` branch, lines 202–204, using `mytrader_config.ETF_AUM_FLAG_USD`).
  `run_dma_breakout_scan` (215–297)'s per-ticker try/except + dedup + staging block (232–284) is the
  closest template for `etf_heartbeat_scan.run_etf_heartbeat_scan`.
- `investments/goat/goat/fundamentals_context.py` (whole file, 110 lines) — `compute_survival_context`
  already short-circuits cleanly for `info.get("quoteType") == "ETF"` (lines 35–42) — reuse unchanged,
  no new ETF-specific branch needed anywhere in this plan.
- `investments/goat/goat/sp500_universe.py` (whole file, 81 lines) and
  `investments/goat/goat/ftse100_universe.py` (whole file, 76 lines) — the exact
  `fetch_X` / `get_or_refresh_X` two-function, TTL-cached-in-DB shape to mirror for
  `industry_constituents.py`'s US (Finviz-backed, not Wikipedia-backed, but same caching shape) and
  for the overall `get_or_refresh_industry_constituents` entry point.
- `investments/my-trader/mytrader/finviz_screener.py` (whole file, 187 lines) —
  `fetch_screener_universe(filters=None, sort="pricecash")` (149–186) already accepts an arbitrary
  `filters` string (the `f=` query param) — no change needed to this file. `_EXPECTED_COLUMNS`
  (35–43) already extracts `industry`/`sector`/`company`/`market_cap_text`/`price_text`.
- `investments/ai-resistant-moat-scanner/ai_resistant_moat_scanner/config.py` (lines 35–48) —
  **critical gotcha**: its own comment states "Finviz's industry filter is single-select (you cannot
  OR industries in `f=`)" — confirms `f=ind_<slug>` is the right single-industry screener call for
  this plan's one-screen-per-gated-industry design (no OR needed here, unlike the moat scanner's
  multi-industry case). No slug mapping exists yet anywhere in this codebase — must be built fresh,
  see Phase 4's `GOTCHA`.
- `investments/my-trader/mytrader/asx200_universe.py` (whole file) — `fetch_asx200_constituents()`
  already returns a `sector` field (GICS-style, confirmed by its own `_SECTOR_HEADERS = ("sector",
  "gics sector")`, line 28) — this is what Phase 6's new `GOAT_ASX_GICS_TO_ETF_SECTOR_LABEL` maps
  from, mirroring `GOAT_GICS_TO_ETF_SECTOR_LABEL` (config.py lines 327–339) exactly. No `industry`
  field exists here — that's why Phase 4's ASX industry mapping must be hand-curated by ticker, not
  derived from this scrape.
- `investments/goat/goat/dma_breakout_scan.py` module docstring (lines 31–42) — the ASX
  `.AX`-suffix-at-universe-fetch-time ticker-qualification GOTCHA applies identically to every new
  ASX leg in this plan (Phases 4, 6).
- `investments/goat/goat/config.py` (680 lines, whole file) — `GOAT_SECTOR_ETFS` (48–55),
  `GOAT_BANNED_TICKERS` (57–62), `GOAT_FINVIZ_INDUSTRIES` (98–148, the 143-label taxonomy — slice
  needed for Phase 4's slug map is the 39 keys of `GOAT_INDUSTRY_ETFS`, not all 143),
  `GOAT_GICS_TO_ETF_SECTOR_LABEL` (327–339) and `GOAT_ICB_TO_ETF_SECTOR_LABEL` (352–401) are the
  exact dict-literal style + "written out explicitly, no cleverness, unmapped = skip + print" comment
  convention to mirror for `GOAT_ASX_GICS_TO_ETF_SECTOR_LABEL` and `GOAT_ASX_INDUSTRY_CONSTITUENTS`.
  `GOAT_DMA_BREAKOUT_ETF_UNIVERSE` (628–631) is the 57-ticker universe Phase 7 scans. Every threshold
  block's trailing `#` comment density (sourced-vs-Shaun's-number-vs-v1/tunable) is the documentation
  standard every new constant in this plan must match.
- `investments/my-trader/mytrader/config.py` lines 695–728 — `GOAT_INDUSTRY_ETFS` (706–724, 39
  tickers), `GOAT_INDUSTRY_HISTORY_LOOKBACK_DAYS`/`GOAT_INDUSTRY_RANK_WINDOW_TRADING_DAYS` (726–728)
  live here, not in `goat/config.py` (re-exported, see that file's own comment at lines 150–154 for
  why — a one-way workspace dependency). `DEBT_TO_EQUITY_FLAG` (line 80), `ETF_AUM_FLAG_USD`
  (line 328) are reused unchanged.
- `investments/goat/goat/db.py` (whole file, 493 lines) — `init_goat_tables` (16–166) is where the two
  new tables (`goat_rotation_snapshots`, `goat_industry_constituents`) get added, following the exact
  `CREATE TABLE IF NOT EXISTS` + (if needed) `ALTER TABLE ... try/except OperationalError` migration
  idiom already used 6 times in this file (93–166) for every schema addition since launch.
  `insert_goat_pending_candidate`/`get_goat_pending_candidate`/`delete_goat_pending_candidate`
  (220–247) are reused unchanged by every new staging path in this plan — only new `source` string
  values are added, no schema change to `goat_pending_candidates` itself.
- `investments/goat/goat/main.py` (whole file, 354 lines) — `_open_conn` (8–19), `cmd_monitor`
  (22–55, the connection-lifecycle fix target), `cmd_scan_industries` (93–104, also needs a `conn` now
  since `run_industry_scan` gains one), `cmd_scan_heartbeat`/`cmd_scan_dma_breakout` (106–143) are the
  exact dispatch-function templates for the 4 new CLI subcommands this plan adds
  (`scan-industry-heartbeat`, `scan-etf-heartbeat`, `query-rotation-history`, no change needed to
  `scan-sectors`/`scan-industries`'s actual signal, just their conn handling).
  `cmd_promote_candidate` (235–267, hardcoded label at line 261, hardcoded `source="goat_sector_rotation"`
  at line 263) is the function Decision 18 makes source-aware. The `dispatch` dict (333–345) and
  `subparsers.add_parser(...)` block (283–318) are where new subcommands register.
- `mytrader/checks/__init__.py` (whole file, 15 lines) — `CheckResult`:
  `name`/`verdict` (`"ok"`|`"flag"`|`"info"`|`"unknown"`, plus `"interesting"` by this codebase's own
  convention for opportunity signals — never use `"flag"` for a new breakout/heartbeat check)/
  `detail`/`data: dict`.
- Test files (read before writing new tests — exact fixture/monkeypatch idioms to mirror):
  `investments/goat/goat/tests/conftest.py` (whole file) — `db_conn` fixture (19–26),
  `_isolate_goat_report_path` (29–53, **must add every new `*_MD_PATH` constant here**),
  `_no_real_price_history_fetch` (56–68, autouse — every new scan test stays network-free by
  default, override per-test with `monkeypatch`).
  `investments/goat/goat/tests/test_industry_rotation.py` (whole file, 44 lines) — the
  `GOAT_INDUSTRY_ETFS`-monkeypatch-and-restore idiom (26–36) for isolating ranking tests from the
  real 39-entry dict.
  `investments/goat/goat/tests/test_sector_rotation.py` — `_series_with_cross`/
  `_declining_then_spike_series` builders (closest existing template for `check_industry_breakout`'s
  tests, mirrors `test_dma_breakout_scan.py`'s own generalized copies at lines 14–42).
  `investments/goat/goat/tests/test_heartbeat_scan.py` (whole file) — `_patch_common` (51–80) is the
  exact monkeypatch-everything-at-the-boundary idiom for `industry_heartbeat_scan.py`'s and
  `etf_heartbeat_scan.py`'s own test files.
  `investments/goat/goat/tests/test_dma_breakout_scan.py` (whole file) — `_healthy_ticker_data`/
  `_insolvent_ticker_data` `TickerData` builders (45–65) for fundamentals-context test fixtures.
  `investments/goat/goat/tests/test_monitor.py` (whole file) — `_seed_holding`/`_seed_watchlist`
  (30–41) dedup-fixture idiom, reused for `run_industry_scan`'s new staging tests.
- `investments/TOOLS.md` lines 18–55, 75–83 — the exact row format (file → trigger → cadence →
  outputs) every new report/command must get a row for; `scripts/deploy.ps1` lines 10–32
  (`$TIMERS_TO_MANAGE` array) is where new timer *names* get added (the unit files themselves are
  hand-created on the VPS, not stored in this repo — same precedent as every other Goat timer, see
  project memory `project_goat_heartbeat_quiet_redesign.md`'s note about a pending `sudo cp`).

### New Files to Create

- `investments/goat/goat/rotation_flow.py` — `compute_flow()`, `render_flow_section()` (Phase 1).
- `investments/goat/goat/industry_constituents.py` — `get_or_refresh_industry_constituents()` +
  its US (Finviz) / ASX (curated) helper functions (Phase 4).
- `investments/goat/goat/industry_heartbeat_scan.py` — `run_industry_heartbeat_scan()` +
  render/write report functions (Phase 5).
- `investments/goat/goat/etf_heartbeat_scan.py` — `run_etf_heartbeat_scan()` + render/write report
  functions (Phase 7).
- `investments/goat/goat/tests/test_rotation_flow.py` (Phase 1).
- `investments/goat/goat/tests/test_industry_constituents.py` (Phase 4).
- `investments/goat/goat/tests/test_industry_heartbeat_scan.py` (Phase 5).
- `investments/goat/goat/tests/test_etf_heartbeat_scan.py` (Phase 7).
- `investments/goat/industry-candidates-pending-review.md` (generated by Phase 3's first run — do
  not hand-write; mirrors `sector-candidates-pending-review.md`).
- `investments/goat/industry-heartbeat-candidates-pending-review.md` (generated, Phase 5).
- `investments/goat/etf-heartbeat-candidates-pending-review.md` (generated, Phase 7).

### Relevant Documentation

None to fetch for most of this plan — pure `pandas` + this codebase's own conventions, same as every
prior Goat feature. One exception: **Phase 4 needs a one-time live lookup of Finviz's real
industry-filter `f=ind_<slug>` values** (see that phase's `GOTCHA` — there is no API doc page for
this, it's scraped from the screener's own filter UI, same discipline
`MOAT_FINVIZ_SECTOR_SCREENS`'s "EVERY TOKEN HERE IS A BEST GUESS -- verified live during the build"
comment already documents for sector-level Finviz tokens).

### Patterns to Follow

**CheckResult verdict convention** (`mytrader/checks/__init__.py`; `sector_rotation.py` 53–56):
`"interesting"` for every new breakout/heartbeat check in this plan (opportunity signal) — never
`"flag"` (reserved for genuine risk/exit signals, e.g. `exit_check.py`). `"unknown"` for insufficient
history, `"ok"` for checked-but-not-present.

**Check-interpretation convention** (project memory `feedback_check_interpretation_convention.md`,
already followed by every `detail` string in `sector_rotation.py`/`heartbeat.py`/`dma_breakout_scan.py`):
spell out full metric names and state which direction is good, not just a number vs. a threshold.

**Config constant documentation density** (`config.py` throughout): every new threshold/constant
gets a trailing `#` comment stating what it is, where the number came from (sourced-with-citation /
"Shaun's number, date" / "v1/tunable, not literature-final"), and its relation to neighbors.

**Deliberate duplication over shared helpers** (`heartbeat.py` module docstring; `dma_breakout_scan.py`
lines 25–29): `check_sector_breakout`, `check_industry_breakout` (new), and `check_ma_cross` all stay
independent copies of the same sign-flip cross-detection idiom — do not refactor any of them to share
internals. Same posture for `heartbeat_scan.py`, `industry_heartbeat_scan.py`, `etf_heartbeat_scan.py`,
`dma_breakout_scan.py` as four independent orchestrators — each recomputes its own closes/ranking
rather than threading results from another module's run (confirmed precedent:
`heartbeat_scan.run_heartbeat_scan` calls `sector_rotation.fetch_all_sector_closes()` itself at line
38 rather than depending on `monitor.run_sector_scan`'s prior output, even though both run in the same
daily batch via separate timers).

**Three-way dedup before staging** (`heartbeat_scan.py` lines 92–97; `dma_breakout_scan.py` lines
253–259; `monitor._stage_new_sector_candidates` lines 241–246): check holding → watchlist →
already-pending, in that order, before every `db.insert_goat_pending_candidate` call. Every new
staging path in this plan (industry ETF, industry stock, ETF candidate) must do the same.

**Report file conventions**: every `render_*_report` function returns a markdown string via
`"\n".join(lines) + "\n"`, ends with `f"Last auto-generated: {_today_sydney()}."`, and every
`write_*_report` is a one-line `config.PATH.write_text(render(...), encoding="utf-8")`. Every
candidate-review report states the promote/dismiss CLI incantations in its header, per
`render_heartbeat_candidates_report` (lines 140–153) / `render_dma_breakout_candidates_report`
(315–329).

**`_today_sydney()` module-private copy, not cross-imported** — every orchestrator module
(`monitor.py`, `heartbeat_scan.py`, `dma_breakout_scan.py`) keeps its own copy per their shared
docstring rationale (real bug caught 2026-09-29, naive `date.today()` prints yesterday's date for
VPS UTC-clock runs after ~10am Sydney). `industry_heartbeat_scan.py` and `etf_heartbeat_scan.py`
need their own copies too.

**Ticker qualification for ASX** (`dma_breakout_scan.py` module docstring lines 31–42): qualify every
ASX ticker (`tickers.asx_variant`) once, at universe-fetch time, and use that qualified string
consistently through price history, fundamentals, dedup, and staging — never the bare code.

---

## IMPLEMENTATION PLAN

### Phase 1: Rotation Snapshot Schema + Flow Compute (Part A core + short-window)

**Tasks:**
- `config.py`: add `GOAT_ROTATION_SNAPSHOT_RETENTION_DAYS = 90`,
  `GOAT_ROTATION_SHORT_WINDOW_TRADING_DAYS = 5` (1 trading week).
- `db.py`: add `goat_rotation_snapshots` table to `init_goat_tables`; add
  `insert_rotation_snapshots`, `get_rotation_snapshots_for_date`, `get_latest_snapshot_date_before`,
  `prune_rotation_snapshots`, `get_rotation_history` (the last one serves Phase 2's CLI).
- `sector_rotation.rank_sectors` / `industry_rotation.rank_industries`: add `return_pct_1w` and
  `rising_1w` keys to every row (same None-safe missing-data handling as the existing long-window
  fields), computed against `config.GOAT_ROTATION_SHORT_WINDOW_TRADING_DAYS`.
- New `rotation_flow.py`: `compute_flow(previous_rows, current_ranking, *, label_key, field="rising")`
  and `render_flow_section(flow, *, title)`.

### Phase 2: Monitor Wiring + Report Splicing + Query CLI (Part A integration + addendum)

**Tasks:**
- `monitor.py`: add `capture_rotation_snapshot(conn, *, scope, ranking, label_key)` — looks up prior
  snapshot date, computes both the long-window and short-window `compute_flow` results, inserts
  today's snapshot rows (`INSERT OR IGNORE`, safe no-op on a same-day re-run), prunes past retention.
- `main.py::cmd_monitor`: move `conn.close()` to after both scans **and** both
  `capture_rotation_snapshot` calls (today it fires right after `run_sector_scan`, before
  `run_industry_scan` — see `cmd_monitor` lines 35–39).
- `monitor.render_sector_ranking_report` / `render_industry_ranking_report`: splice in the long- and
  short-window Rotation Flow sections only when present in `result` (absent on the `scan-sectors`/
  `scan-industries` on-demand path — the regression guard proving those reports stay unaffected).
- `db.py` + `main.py`: new read-only `query-rotation-history --scope sector|industry [--ticker X]
  [--days N]` CLI subcommand, prints JSON to stdout, no DB writes, no notify.

### Phase 3: Industry Breakout Check + Candidate Staging + Report (Part B-1)

**Tasks:**
- `industry_rotation.py`: add `check_industry_breakout(ticker, industry_label, close)`, a verbatim
  structural copy of `check_sector_breakout` reusing the same `GOAT_SECTOR_*` constants.
- `monitor.py`: rewrite `run_industry_scan()` → `run_industry_scan(conn)` — adds the breakout leg
  over `config.GOAT_INDUSTRY_ETFS`, a new `_stage_new_industry_candidates` (mirrors
  `_stage_new_sector_candidates`, `source="goat_industry_rotation"`), and a gate list in the result.
- `config.py`: add `GOAT_INDUSTRY_CANDIDATES_MD_PATH`.
- `monitor.py`: add `render_industry_candidates_report`/`write_industry_candidates_report` (mirrors
  `render_sector_candidates_report` exactly); `render_industry_ranking_report` gets a short "Fresh
  Breakout" note referencing the new candidates file.
- `main.py`: `cmd_monitor` and `cmd_scan_industries` both pass `conn` into `run_industry_scan` now
  (today `cmd_scan_industries` opens no connection at all — it needs one now); write the new report;
  call `maybe_notify` with `candidate_label="new industry rotation candidate(s)"`.
- `main.py::cmd_promote_candidate`: make the label/`source` write source-aware (read
  `pending["source"]`, map to a per-source label string) instead of the hardcoded
  `"Goat-approved sector rotation candidate"` / `source="goat_sector_rotation"`.

### Phase 4: Industry Constituent Universe — US Finviz + Hand-Curated ASX (Part B-2 + ASX ext.)

**Tasks:**
- `config.py`: add `GOAT_INDUSTRY_CONSTITUENTS_CACHE_TTL_DAYS` (mirror `GOAT_SP500_CACHE_TTL_DAYS`'s
  7-day value/reasoning), `GOAT_FINVIZ_INDUSTRY_SLUGS: dict[str, str]` (39 entries — the
  `GOAT_INDUSTRY_ETFS` labels only, not all 143 — mapping each to its real Finviz `ind_<slug>`
  screener code), `GOAT_ASX_INDUSTRY_CONSTITUENTS: dict[str, str]` (hand-curated ASX ticker →
  `GOAT_FINVIZ_INDUSTRIES` label).
- `db.py`: add `goat_industry_constituents` table (`ticker`, `industry_label`, `market`, `company`,
  `fetched_at`) + `get_industry_constituents_fetched_at`, `replace_industry_constituents`,
  `get_industry_constituents`.
- New `industry_constituents.py`: `fetch_industry_constituents_us(industry_label)` (calls
  `finviz_screener.fetch_screener_universe(filters=f"{slug},sh_avgvol_o100,sh_price_o1")`),
  `get_asx_industry_constituents(industry_label)` (reads `GOAT_ASX_INDUSTRY_CONSTITUENTS`, no
  network call), `get_or_refresh_industry_constituents(conn, industry_label)` combining both,
  TTL-cached per `industry_label`.

### Phase 5: Industry Heartbeat Scan + Staging + Reports + CLI (Part B-3)

**Tasks:**
- New `industry_heartbeat_scan.py`: `run_industry_heartbeat_scan(conn, industries=None)` — if
  `industries` is None, computes the gate itself (own `fetch_all_industry_closes` +
  `check_industry_breakout` call, independent of `run_industry_scan`'s own gate, per the
  orchestrator-independence pattern); else uses the given list verbatim (the `--industries` manual
  override). For each gated industry: `get_or_refresh_industry_constituents`, per-ticker
  `check_heartbeat_breakout` + `fundamentals_context` + three-way dedup, stage with
  `source="goat_industry_heartbeat_scan"`.
- `config.py`: add `GOAT_INDUSTRY_HEARTBEAT_CANDIDATES_MD_PATH`.
- `industry_heartbeat_scan.py`: `render_industry_heartbeat_candidates_report`/`write_...` (mirrors
  `heartbeat_scan.py`'s renderer).
- `main.py`: new `scan-industry-heartbeat` subcommand with `--industries "A,B"` override flag.

### Phase 6: ASX Sector-Level Extension to Existing Heartbeat Scan (Part C, sector leg)

**Tasks:**
- `config.py`: add `GOAT_ASX_GICS_TO_ETF_SECTOR_LABEL` (mirrors `GOAT_GICS_TO_ETF_SECTOR_LABEL`
  exactly, built from `asx200_universe`'s own `sector` field values).
- `heartbeat_scan.py::run_heartbeat_scan`: add a third constituent-filtering block
  (`asx200_universe.fetch_asx200_constituents()` → map sector → `tickers.asx_variant` →
  `market="ASX"`), appended to the existing US+LSE `filtered` list.

### Phase 7: ETF-as-Candidate Heartbeat Leg (Part C, ETF leg)

**Tasks:**
- New `etf_heartbeat_scan.py`: `run_etf_heartbeat_scan(conn)` — iterates
  `config.GOAT_DMA_BREAKOUT_ETF_UNIVERSE` unconditionally (no sector/industry gate), per-ticker
  `check_heartbeat_breakout` + `dma_breakout_scan.passes_liquidity_floor` (AUM-gated for ETFs) +
  `fundamentals_context` (already ETF-safe) + three-way dedup, stage with
  `source="goat_etf_heartbeat_scan"`.
- `config.py`: add `GOAT_ETF_HEARTBEAT_CANDIDATES_MD_PATH`.
- `etf_heartbeat_scan.py`: render/write report (mirrors `dma_breakout_scan.py`'s renderer shape).
- `main.py`: new `scan-etf-heartbeat` subcommand.

### Phase 8: Tests, Docs, VPS Wiring, Validation

**Tasks:**
- `conftest.py::_isolate_goat_report_path`: add every new `*_MD_PATH` constant from Phases 3/5/7.
- `investments/TOOLS.md`: new rows for `scan-industry-heartbeat`, `scan-etf-heartbeat`,
  `query-rotation-history` (on-demand only, no timer), `industry-candidates-pending-review.md`,
  `industry-heartbeat-candidates-pending-review.md`, `etf-heartbeat-candidates-pending-review.md`;
  update the existing Goat Monitor / Goat Heartbeat Scan rows to mention the new Rotation Flow
  section and ASX leg respectively.
- `scripts/deploy.ps1`: add `second-brain-goat-industry-heartbeat-scan.timer` and
  `second-brain-goat-etf-heartbeat-scan.timer` to `$TIMERS_TO_MANAGE`.
- VPS (manual, flag for Shaun — same as every prior Goat timer addition): hand-create the two new
  systemd `.timer`/`.service` unit files on the VPS (mirror `second-brain-goat-heartbeat-scan.timer`'s
  existing unit verbatim, new `OnCalendar=` slot — suggest ~22:50 UTC and ~23:00 UTC, between the
  existing 22:45 Heartbeat Scan and 22:55 DMA Breakout Scan), `sudo systemctl daemon-reload`,
  `enable --now` both.
- Full test suite + VPS command validation (see Validation Commands below).

---

## STEP-BY-STEP TASKS

### Phase 1

1. **ADD** `GOAT_ROTATION_SNAPSHOT_RETENTION_DAYS = 90`, `GOAT_ROTATION_SHORT_WINDOW_TRADING_DAYS = 5`
   to `investments/goat/goat/config.py` (near the `GOAT_SECTOR_*`/`GOAT_INDUSTRY_*` blocks).
   - **GOTCHA**: match the existing comment density — cite the 90-day number's precedent (two
     existing 90-day lookback constants already in this file: `GOAT_INSIDER_SALE_LOOKBACK_DAYS`,
     `GOAT_INSIDER_PRICE_STALE_DAYS`).
2. **ADD** `goat_rotation_snapshots` table to `db.py::init_goat_tables`'s `executescript` block:
   `id PK, scope TEXT, snapshot_date TEXT, ticker TEXT, label TEXT, return_pct REAL,
   return_pct_1w REAL, rank INTEGER, rising INTEGER, UNIQUE(scope, snapshot_date, ticker)`.
   - **PATTERN**: `db.py` lines 16–92 (the `executescript` block) — append, don't touch existing
     tables.
3. **CREATE** `db.insert_rotation_snapshots(conn, *, scope, snapshot_date, rows, label_key)` —
   `executemany` with `INSERT OR IGNORE`, pulling `ticker`/`return_pct`/`return_pct_1w`/`rank`/
   `rising` off each row dict and `label_key` for the label field.
   - **GOTCHA**: `INSERT OR IGNORE` on the `UNIQUE(scope, snapshot_date, ticker)` constraint is what
     makes a same-day re-run of `monitor` a safe no-op (Decision 5) — do not use `INSERT OR REPLACE`.
4. **CREATE** `db.get_rotation_snapshots_for_date(conn, scope, snapshot_date) -> list[sqlite3.Row]`.
5. **CREATE** `db.get_latest_snapshot_date_before(conn, scope, before_date) -> str | None` — `SELECT
   DISTINCT snapshot_date ... WHERE scope = ? AND snapshot_date < ? ORDER BY snapshot_date DESC LIMIT 1`.
6. **CREATE** `db.prune_rotation_snapshots(conn, retention_days) -> int` — delete rows with
   `snapshot_date` older than `today - retention_days`, across all scopes. Mirrors
   `delete_stale_pending_candidates`'s shape (lines 250–264) but keyed on date, not source.
7. **CREATE** `db.get_rotation_history(conn, *, scope, ticker=None, since_date=None) ->
   list[sqlite3.Row]` — ordered by `snapshot_date`; used by Phase 2's CLI.
   - **VALIDATE**: `uv run --directory investments/goat python -m pytest goat/tests/test_db.py -q`
8. **UPDATE** `industry_rotation.rank_industries` and `sector_rotation.rank_sectors`: add
   `return_pct_1w` (None if `len(close) < GOAT_ROTATION_SHORT_WINDOW_TRADING_DAYS + 1`) and
   `rising_1w` (`return_pct_1w > 0` or `None`) per row, computed the same way as the existing
   long-window fields (same `close.iloc[-1] / close.iloc[-(window+1)] - 1` idiom).
   - **GOTCHA**: this changes both functions' *output shape* (extra dict keys) — every existing
     caller (`monitor.run_sector_scan`, `monitor.run_industry_scan`, `heartbeat_scan.run_heartbeat_scan`
     via `rank_sectors`) must keep working unmodified since dict access is by key, not shape — confirm
     no caller does `list(row.values())`-style positional unpacking (grep confirms none do).
   - **VALIDATE**: `uv run --directory investments/goat python -m pytest goat/tests/test_industry_rotation.py goat/tests/test_sector_rotation.py -q`
9. **CREATE** `investments/goat/goat/rotation_flow.py`:
   - `compute_flow(previous_rows, current_ranking, *, label_key, field="rising") -> dict` — builds a
     `ticker -> field value` lookup from both sides; for each ticker present on both sides with a
     non-`None` field value on both, records a transition (`from`/`to` bool); tickers missing from
     one side, or `None` on either side, are excluded (an unknown state can't transition). Returns
     `{"transitions": [...], "summary": {"rising_to_falling": n, "falling_to_rising": n,
     "unchanged_rising": n, "unchanged_falling": n}, "no_prior_count": n}`.
   - `render_flow_section(flow, *, title) -> list[str]` — markdown fragment: a summary line + a table
     of transitions (ticker, label, from → to), or "No prior snapshot yet" if `flow is None`.
   - **PATTERN**: `heartbeat.py`'s module docstring documents *why* each gate exists before the code
     — do the same here for the exclusion-of-`None`-on-either-side rule.
10. **CREATE** `investments/goat/goat/tests/test_rotation_flow.py` — cover: no-prior-snapshot case,
    rising→falling transition, falling→rising transition, unchanged cases, a ticker with `None`
    `rising` on one side is excluded, `field="rising_1w"` works identically to `field="rising"`.

### Phase 2

11. **CREATE** `monitor.capture_rotation_snapshot(conn, *, scope, ranking, label_key) -> dict`:
    - `today = _today_sydney()`; `previous_date = db.get_latest_snapshot_date_before(conn, scope, today)`.
    - `previous_rows = db.get_rotation_snapshots_for_date(conn, scope, previous_date) if previous_date else []`.
    - `long_flow = rotation_flow.compute_flow(previous_rows, ranking, label_key=label_key) if previous_rows else None`.
    - `short_flow = rotation_flow.compute_flow(previous_rows, ranking, label_key=label_key, field="rising_1w") if previous_rows else None`.
    - `db.insert_rotation_snapshots(conn, scope=scope, snapshot_date=today, rows=ranking, label_key=label_key)`.
    - `db.prune_rotation_snapshots(conn, config.GOAT_ROTATION_SNAPSHOT_RETENTION_DAYS)`.
    - Returns `{"rotation_flow": long_flow, "short_window_flow": short_flow}`.
12. **UPDATE** `main.py::cmd_monitor` (lines 22–55):
    - Call `sector_result = run_sector_scan(conn)`, then
      `sector_result.update(monitor.capture_rotation_snapshot(conn, scope="sector", ranking=sector_result["ranking"], label_key="sector_label"))`
      **before** `conn.close()`.
    - Call `industry_result = run_industry_scan(conn)` (now takes `conn` — see Phase 3), then the
      same `capture_rotation_snapshot` call with `scope="industry"`, `label_key="industry_label"`,
      **before** `conn.close()`.
    - Move `conn.close()` to after both scans and both snapshot captures.
    - **GOTCHA** (handoff's own note, lines 114–116): today `conn.close()` fires between
      `run_sector_scan` and `run_industry_scan` — this is the exact bug both Part A and Part B-1
      independently require fixing; do it once, here.
13. **UPDATE** `monitor.render_sector_ranking_report` / `render_industry_ranking_report`: splice
    `rotation_flow.render_flow_section(result["rotation_flow"], title="Rotation Flow")` and
    `render_flow_section(result["short_window_flow"], title="Short-Window Flow (1-Week)")` after the
    existing tables, only `if result.get("rotation_flow") is not None` (the `scan-sectors`/
    `scan-industries` on-demand paths never set this key — verify via `result.get(...)`, not
    `result[...]`, so a `KeyError` never fires on the on-demand path).
    - **VALIDATE**: `uv run --directory investments/goat python -m pytest goat/tests/test_monitor.py -q`
      — add a case proving `scan-sectors`'s `run_sector_scan` output renders with NO Rotation Flow
      section (the regression guard Decision 5 calls for).
14. **CREATE** `db.get_rotation_history` (done in Phase 1, task 7) wiring into `main.py`: new
    `cmd_query_rotation_history(args)` — opens conn, calls `db.get_rotation_history(conn, scope=args.scope,
    ticker=args.ticker, since_date=...)` (computed from `args.days` if given), `conn.close()`, prints
    `json.dumps([dict(r) for r in rows], indent=2, default=str)` to stdout. Register
    `query-rotation-history` subparser with `--scope` (required, choices `sector`/`industry`),
    `--ticker` (optional), `--days` (optional, default `GOAT_ROTATION_SNAPSHOT_RETENTION_DAYS`).
    - **GOTCHA**: this is a **read-only** CLI path — no `maybe_notify`, no report write, no staging.
      Mirrors `cmd_dismiss_candidate`'s minimalism (lines 270–277), not `cmd_scan_*`'s full pipeline.
    - **VALIDATE**: manual — `uv run --directory investments/goat python -m goat.main
      query-rotation-history --scope sector --days 7` against a local throwaway DB with seeded rows.

### Phase 3

15. **CREATE** `industry_rotation.check_industry_breakout(ticker, industry_label, close) -> CheckResult`
    — exact structural copy of `sector_rotation.check_sector_breakout` (lines 53–113), s/sector/industry/
    in names and detail strings only, same `GOAT_SECTOR_MA_SHORT_DAYS`/`_SLOPE_LOOKBACK_DAYS`/
    `_CROSS_RECENCY_DAYS` constants.
    - **VALIDATE**: `uv run --directory investments/goat python -m pytest goat/tests/test_industry_rotation.py -q`
      (new `test_check_industry_breakout_*` cases mirroring `test_sector_rotation.py`'s own).
16. **CREATE** `monitor._stage_new_industry_candidates(checks, conn) -> list[dict]` — exact copy of
    `_stage_new_sector_candidates` (lines 227–251), `source="goat_industry_rotation"`.
17. **REWRITE** `monitor.run_industry_scan()` → `run_industry_scan(conn)` (lines 332–341):
    - Keep the existing ranking compute + `not_covered` list unchanged.
    - Add a breakout-checks loop over `config.GOAT_INDUSTRY_ETFS.items()` (mirrors `run_sector_scan`
      lines 258–265), feeding `_stage_new_industry_candidates`.
    - Add `"heartbeat_gate": [etf for etf, check in breakout_checks if check.verdict == "interesting"]`
      to the result dict (informational; `industry_heartbeat_scan.py` recomputes its own gate
      independently per the orchestrator-independence pattern — this field is for the report only).
    - Add `"new_candidates"` and `"pending_candidates"` (filtered to `source == "goat_industry_rotation"`,
      mirrors `heartbeat_scan`'s own `pending_candidates` filter at line 135) to the result dict.
18. **ADD** `GOAT_INDUSTRY_CANDIDATES_MD_PATH = GOAT_DIR / "industry-candidates-pending-review.md"`
    to `config.py`.
19. **CREATE** `monitor.render_industry_candidates_report` / `write_industry_candidates_report` —
    exact copy of `render_sector_candidates_report`/`write_sector_candidates_report` (304–329).
20. **UPDATE** `monitor.render_industry_ranking_report`: add a one-line note after the "Not Covered"
    section — `"N industries currently in a fresh breakout -- see industry-candidates-pending-review.md"`
    using the new `heartbeat_gate` field.
21. **UPDATE** `main.py::cmd_monitor`: thread `conn` into `run_industry_scan(conn)`; write the new
    industry candidates report; fold `industry_result["new_candidates"]` into the existing
    `maybe_notify` call (either a second `maybe_notify` call with its own `candidate_label`, or extend
    the existing call's `candidates` list — prefer a second call, mirroring how `cmd_scan_insiders`
    already makes multiple `maybe_notify`-adjacent calls for distinct signal types).
22. **UPDATE** `main.py::cmd_scan_industries`: now opens a connection (`_open_conn()`), passes it to
    `run_industry_scan(conn)`, writes both the ranking report and the new candidates report, calls
    `maybe_notify`, closes the connection. (Today this command is connection-free — it becomes
    connection-using, matching `cmd_scan_sectors`'s existing shape exactly.)
23. **UPDATE** `main.py::cmd_promote_candidate` (lines 235–267): replace the hardcoded label/`source`
    with a lookup dict keyed by `pending["source"]`:
    ```python
    _PROMOTE_LABELS = {
        "goat_sector_rotation": "Goat-approved sector rotation candidate",
        "goat_industry_rotation": "Goat-approved industry rotation candidate",
        "goat_heartbeat_scan": "Goat-approved heartbeat candidate",
        "goat_dma_breakout_scan": "Goat-approved DMA breakout candidate",
        "goat_industry_heartbeat_scan": "Goat-approved industry heartbeat candidate",
        "goat_etf_heartbeat_scan": "Goat-approved ETF heartbeat candidate",
    }
    label = _PROMOTE_LABELS.get(pending["source"], "Goat-approved candidate")
    ```
    then `notes=f"{label} — {pending['signal_detail']}"`, `source=pending["source"]` (not a literal).
    - **GOTCHA**: `GOAT_BANNED_TICKERS` enforcement (line 244) stays unchanged — ticker-level, not
      source-level.
    - **VALIDATE**: `uv run --directory investments/goat python -m pytest goat/tests/test_monitor.py -q`
      (new staging/report tests) + a manual `promote-candidate` smoke test per source.

### Phase 4

24. **RESEARCH** (do this before writing `GOAT_FINVIZ_INDUSTRY_SLUGS`): fetch Finviz's screener page
    once (e.g. `https://finviz.com/screener.ashx?v=111&f=sec_technology`) and inspect the Industry
    filter `<select>`'s `<option value="ind_...">` entries to build the real `label -> ind_<slug>`
    mapping for the 39 `GOAT_INDUSTRY_ETFS` labels (not all 143 — the gate only ever selects from
    these 39, since gating requires an ETF to exist). Document each slug's source inline, same
    "verified live during the build" posture as `MOAT_FINVIZ_SECTOR_SCREENS`'s own comment.
    - **GOTCHA**: a wrong/stale slug just yields an empty screen for that industry (same
      fail-safe-empty posture as every other Finviz-backed scan in this codebase) — not a crash. The
      `--industries` manual override (Phase 5) is the practical workaround for any slug that drifts.
25. **ADD** to `config.py`: `GOAT_INDUSTRY_CONSTITUENTS_CACHE_TTL_DAYS = 7` (mirrors
    `GOAT_SP500_CACHE_TTL_DAYS`), `GOAT_FINVIZ_INDUSTRY_SLUGS: dict[str, str]` (from task 24),
    `GOAT_ASX_INDUSTRY_CONSTITUENTS: dict[str, str]` (hand-curated, see task 26).
26. **RESEARCH + ADD** `GOAT_ASX_INDUSTRY_CONSTITUENTS: dict[str, str]` — ticker → one of the 143
    `GOAT_FINVIZ_INDUSTRIES` labels, for a reasonable initial slice of ASX-listed companies
    (prioritize large/liquid names likely to appear in a heartbeat-worthy industry — cross-reference
    `asx200_universe`'s own constituent list + sector field against Finviz's finer taxonomy; this is a
    genuine per-company research task, same discipline as `GOAT_INDUSTRY_ETFS`'s own 2026-08-23
    build). Document the research date and coverage caveat in the comment above the dict, mirroring
    `GOAT_INDUSTRY_ETFS`'s own "39 of 143 ... researched 2026-08-23" comment (config.py line 724).
    - **GOTCHA**: do not block this plan's ship on exhaustive ASX-200 coverage — an uncovered ticker
      simply never surfaces as an industry constituent (same "Not Covered" posture as
      `industry-ranking.md`'s own gap list), not a silent substitution. Extend later.
27. **CREATE** `db.goat_industry_constituents` table in `init_goat_tables`: `ticker TEXT, industry_label
    TEXT, market TEXT, company TEXT, fetched_at TEXT, PRIMARY KEY (ticker, industry_label)` (a ticker
    can legitimately belong to the cache for only one industry at a time per source, but keying on
    the pair avoids any cross-industry collision if a research update ever reclassifies one).
    Add `get_industry_constituents_fetched_at(conn, industry_label)`,
    `replace_industry_constituents(conn, industry_label, rows)` (delete-then-insert for that one
    industry_label, mirrors `replace_sp500_constituents`'s shape but scoped per-industry, not global),
    `get_industry_constituents(conn, industry_label)`.
28. **CREATE** `investments/goat/goat/industry_constituents.py`:
    - `fetch_industry_constituents_us(industry_label) -> list[dict] | None` — looks up
      `config.GOAT_FINVIZ_INDUSTRY_SLUGS.get(industry_label)`; if missing, returns `None` (logged,
      not a crash); else calls `finviz_screener.fetch_screener_universe(filters=f"{slug},sh_avgvol_o100,sh_price_o1")`.
    - `get_asx_industry_constituents(industry_label) -> list[dict]` — pure dict lookup over
      `config.GOAT_ASX_INDUSTRY_CONSTITUENTS`, no network, no caching needed (already a static config
      value — no TTL applies to this leg).
    - `get_or_refresh_industry_constituents(conn, industry_label) -> list[dict]` — TTL-checks the US
      Finviz leg only (the ASX leg is static); combines both into one list of
      `{"ticker", "company", "industry_label", "market"}` dicts, `tickers.asx_variant`-qualified for
      the ASX rows (per the module GOTCHA above), `tickers.normalize`-qualified for US rows.
    - **PATTERN**: `sp500_universe.get_or_refresh_sp500_constituents` (61–80) is the exact
      stale-check-then-refresh-then-fallback-to-cache shape, applied per-`industry_label` instead of
      globally.
29. **CREATE** `investments/goat/goat/tests/test_industry_constituents.py` — cover: US leg cache hit/
    miss/refresh/stale-fallback (mirrors `test_sp500_universe.py`'s own cases), ASX leg returns the
    curated entries for a known industry and `[]` for an uncurated one, combined output tags `market`
    correctly per row, a missing Finviz slug returns the ASX-only rows rather than crashing.
    - **VALIDATE**: `uv run --directory investments/goat python -m pytest goat/tests/test_industry_constituents.py -q`

### Phase 5

30. **CREATE** `investments/goat/goat/industry_heartbeat_scan.py::run_industry_heartbeat_scan(conn,
    industries=None) -> dict`:
    - Gate: if `industries` is `None`, compute it (`industry_rotation.fetch_all_industry_closes()` +
      `check_industry_breakout` per ETF, `verdict == "interesting"` → gated industry labels); else use
      the given list verbatim.
    - For each gated industry label: `industry_constituents.get_or_refresh_industry_constituents(conn,
      label)`; per constituent, `price_history.fetch_close_volume_history` →
      `heartbeat.check_heartbeat_breakout` → (if `"interesting"`) `market_data.fetch_ticker_data` →
      `fundamentals_context.compute_survival_context` → insolvency suppression → three-way dedup →
      `db.insert_goat_pending_candidate(..., source="goat_industry_heartbeat_scan")`.
    - Mirrors `heartbeat_scan.run_heartbeat_scan`'s exact loop body (lines 69–126), including the
      short `notify_detail` convention (lines 118–122) and the `scanned`/`pending_candidates`
      result-dict shape.
    - **GOTCHA**: no ethical-filter call here, matching `heartbeat_scan.py`'s own existing precedent
      (it doesn't call `ethical_check` either, unlike `dma_breakout_scan.py`) — this is a pre-existing
      asymmetry in the codebase, out of scope to fix here; do not introduce a new inconsistency by
      adding it only to this new module.
31. **ADD** `GOAT_INDUSTRY_HEARTBEAT_CANDIDATES_MD_PATH` to `config.py`.
32. **CREATE** `render_industry_heartbeat_candidates_report`/`write_...` in
    `industry_heartbeat_scan.py` — mirrors `render_heartbeat_candidates_report` (140–169).
33. **UPDATE** `main.py`: add `cmd_scan_industry_heartbeat(args)` + subparser with `--industries
    "Semiconductors,Oil & Gas Equipment & Services"` (comma-split, `.strip()` each) optional override;
    register in `dispatch`.
34. **CREATE** `investments/goat/goat/tests/test_industry_heartbeat_scan.py` — mirrors
    `test_heartbeat_scan.py`'s `_patch_common` monkeypatch-the-boundary style; cover: gate computed
    from breakout when `industries=None`, `--industries` override bypasses gate computation entirely,
    dedup against holdings/watchlist/already-pending, insolvency suppression, `source` value on
    staged rows.
    - **VALIDATE**: `uv run --directory investments/goat python -m pytest goat/tests/test_industry_heartbeat_scan.py -q`

### Phase 6

35. **ADD** `GOAT_ASX_GICS_TO_ETF_SECTOR_LABEL: dict[str, str]` to `config.py` — mirrors
    `GOAT_GICS_TO_ETF_SECTOR_LABEL` (327–339), values sourced from `asx200_universe`'s own `sector`
    column (live-check the actual distinct values returned, same "written out explicitly" posture —
    do not assume they match the US Wikipedia GICS labels verbatim without checking).
36. **UPDATE** `heartbeat_scan.run_heartbeat_scan` (37–137): add a third constituent block after the
    existing LSE one (56–65):
    ```python
    asx_constituents = asx200_universe.fetch_asx200_constituents() or []
    for c in asx_constituents:
        etf_label = config.GOAT_ASX_GICS_TO_ETF_SECTOR_LABEL.get(c["sector"])
        if etf_label is None:
            print(f"[goat-heartbeat-scan] unmapped ASX sector {c['sector']!r} for {c['ticker']}, skipping")
            continue
        if etf_label in rising_etf_labels:
            filtered.append({
                "ticker": tickers.asx_variant(c["ticker"]), "company": c["company"],
                "sector_label": etf_label, "market": "ASX",
            })
    ```
    - **GOTCHA**: `asx200_universe.fetch_asx200_constituents()` has **no DB cache** (unlike
      `sp500_universe`/`ftse100_universe`) and returns `None` on scrape failure — guard with
      `or []`, matching `dma_breakout_scan.fetch_universe_constituents`'s own handling (line 96).
    - **IMPORTS**: add `from mytrader import asx200_universe` to `heartbeat_scan.py`'s import block.
37. **UPDATE** `investments/goat/goat/tests/test_heartbeat_scan.py`: extend `_patch_common` with an
    `asx_constituents` param + monkeypatch for `asx200_universe.fetch_asx200_constituents`; add a test
    proving an ASX constituent in a rising sector gets scanned and staged with `market="ASX"`, and one
    proving an unmapped ASX sector is skipped with a print, not a crash.
    - **VALIDATE**: `uv run --directory investments/goat python -m pytest goat/tests/test_heartbeat_scan.py -q`

### Phase 7

38. **CREATE** `investments/goat/goat/etf_heartbeat_scan.py::run_etf_heartbeat_scan(conn) -> dict`:
    - Iterate `config.GOAT_DMA_BREAKOUT_ETF_UNIVERSE.items()` unconditionally (skip
      `GOAT_BANNED_TICKERS`, mirrors `dma_breakout_scan.fetch_universe_constituents` lines 107–114).
    - Per ETF: `price_history.fetch_close_volume_history` → `heartbeat.check_heartbeat_breakout` →
      (if `"interesting"`) `market_data.fetch_ticker_data` →
      `dma_breakout_scan.passes_liquidity_floor("ETF", data)` (AUM gate) →
      `fundamentals_context.compute_survival_context` (already ETF-safe, trivially passes) →
      three-way dedup → stage `source="goat_etf_heartbeat_scan"`.
    - **GOTCHA**: reuse `dma_breakout_scan.passes_liquidity_floor` by importing it directly
      (`from . import dma_breakout_scan`) rather than copying it — it's generic over `market` already
      and takes no Goat-DMA-specific state; this is a reuse, not the "deliberate duplication"
      convention (that convention applies to the *check* functions, e.g. `check_ma_cross` vs.
      `check_heartbeat_breakout`, not to a liquidity-floor predicate with zero check-specific logic).
39. **ADD** `GOAT_ETF_HEARTBEAT_CANDIDATES_MD_PATH` to `config.py`.
40. **CREATE** `render_etf_heartbeat_candidates_report`/`write_...` in `etf_heartbeat_scan.py` —
    mirrors `render_dma_breakout_candidates_report`'s table shape (no "freshest cross" sort needed
    here, plain ticker order is fine since heartbeat candidates don't carry a cross-recency number).
41. **UPDATE** `main.py`: add `cmd_scan_etf_heartbeat(args)` + subparser, register in `dispatch`.
42. **CREATE** `investments/goat/goat/tests/test_etf_heartbeat_scan.py` — mirrors
    `test_dma_breakout_scan.py`'s fixture style (`_healthy_ticker_data`/`_insolvent_ticker_data`);
    cover: unconditional scan (no sector/industry filter applied), `GOAT_BANNED_TICKERS` skip, AUM
    liquidity floor gate, three-way dedup, `source` value.
    - **VALIDATE**: `uv run --directory investments/goat python -m pytest goat/tests/test_etf_heartbeat_scan.py -q`

### Phase 8

43. **UPDATE** `conftest.py::_isolate_goat_report_path`: add
    `GOAT_INDUSTRY_CANDIDATES_MD_PATH`, `GOAT_INDUSTRY_HEARTBEAT_CANDIDATES_MD_PATH`,
    `GOAT_ETF_HEARTBEAT_CANDIDATES_MD_PATH` (and `GOAT_SECTOR_RANKING_MD_PATH`/
    `GOAT_SECTOR_CANDIDATES_MD_PATH` if a full-suite run reveals they were never isolated and a new
    test writes through them — check first, don't assume).
44. **UPDATE** `investments/TOOLS.md`: new rows for every new report + command, per the existing table
    format (lines 18–55 for the daily-read table, 75–83 for the on-demand command table).
45. **UPDATE** `scripts/deploy.ps1`: add the two new timer names to `$TIMERS_TO_MANAGE` (lines 18–32).
46. **MANUAL (flag for Shaun, do not attempt over this tool's SSH restrictions)**: hand-create
    `second-brain-goat-industry-heartbeat-scan.timer`/`.service` and
    `second-brain-goat-etf-heartbeat-scan.timer`/`.service` on the VPS (`/etc/systemd/system/`),
    mirroring `second-brain-goat-heartbeat-scan.timer`'s existing unit content with a new
    `OnCalendar=` (suggest 22:50 and 23:00 UTC respectively — see TOOLS.md's existing stagger),
    `sudo systemctl daemon-reload`, `sudo systemctl enable --now` both.
47. **RUN** the full test suite + every manual VPS validation command (see below).

---

## TESTING STRATEGY

### Unit Tests
Every new pure-compute function (`check_industry_breakout`, `rotation_flow.compute_flow`) gets a
dedicated test module using this codebase's `_dates`/`_flat_then_move`/`_series_with_cross`
synthetic-series-builder idiom (no real yfinance calls — `conftest.py`'s autouse
`_no_real_price_history_fetch` already guards against that by default).

### Integration Tests
Every new orchestrator (`run_industry_scan`, `industry_heartbeat_scan.run_industry_heartbeat_scan`,
`etf_heartbeat_scan.run_etf_heartbeat_scan`, `heartbeat_scan.run_heartbeat_scan`'s new ASX leg) gets
tests using the `db_conn` fixture + `monkeypatch.setattr` at the module boundary (`_patch_common`-style),
proving: staging happens on an "interesting" verdict, three-way dedup prevents re-staging, insolvency
suppression blocks staging, and the report/result-dict shape is correct.

### Edge Cases
- A same-day double-run of `cmd_monitor` must not double-insert a rotation snapshot row
  (`INSERT OR IGNORE` + `UNIQUE(scope, snapshot_date, ticker)`).
- First-ever `monitor` run after deploy: no prior snapshot exists → `rotation_flow`/
  `short_window_flow` are both `None` → report shows "No prior snapshot yet", not a crash.
- A ticker with `rising=None` (insufficient price history) on either side of a flow diff is excluded,
  not treated as a transition.
- `scan-sectors`/`scan-industries` (on-demand) never write a snapshot row or render a Rotation Flow
  section, even when prior snapshot rows exist from `monitor`.
- An unmapped ASX sector/GICS value is skipped with a `print`, never a `KeyError` crash.
- A missing `GOAT_FINVIZ_INDUSTRY_SLUGS` entry for a gated industry falls back to ASX-only
  constituents (or an empty list), not a crash.
- `GOAT_BANNED_TICKERS` (`XLI`) is excluded from the new ETF heartbeat leg, same as every other ETF
  universe iteration in this codebase.
- `cmd_promote_candidate` on a pending row whose `source` isn't in `_PROMOTE_LABELS` falls back to a
  generic label, never a `KeyError`.

---

## VALIDATION COMMANDS

### Level 1: Syntax & Style
```powershell
uv run --directory investments/goat ruff check goat/
```

### Level 2: Unit + Integration Tests
```powershell
uv run --directory investments/goat python -m pytest -q
```

### Level 3: Manual Validation — on the VPS via `invoke_investments.ps1` (never run locally against
the real DB; `investments.db` is VPS-only, see project memory `project_investments_db_git_conflict.md`)
```powershell
.\scripts\invoke_investments.ps1 -Package goat -Command "monitor"
.\scripts\invoke_investments.ps1 -Package goat -Command "scan-sectors"
.\scripts\invoke_investments.ps1 -Package goat -Command "scan-industries"
.\scripts\invoke_investments.ps1 -Package goat -Command "scan-industry-heartbeat"
.\scripts\invoke_investments.ps1 -Package goat -Command "scan-industry-heartbeat --industries ""Semiconductors,Oil & Gas Equipment & Services"""
.\scripts\invoke_investments.ps1 -Package goat -Command "scan-etf-heartbeat"
.\scripts\invoke_investments.ps1 -Package goat -Command "scan-heartbeat"
.\scripts\invoke_investments.ps1 -Package goat -Command "query-rotation-history --scope sector --days 7"
```
First `monitor` run after deploy shows "No prior snapshot yet" for both scopes (expected — no history
before this ships). Re-run `monitor` a second time same-day and confirm the Rotation Flow section
still says "No prior snapshot yet" (same-day snapshot shouldn't count as "prior"), then run on two
different calendar days (or manually insert a fake prior-day snapshot row in a throwaway local DB) to
confirm a real transition renders correctly.

### Level 4: Content Validation
Spot-check `GOAT_FINVIZ_INDUSTRY_SLUGS` entries by hand against `finviz.com/screener.ashx?f=ind_<slug>`
for 3–4 industries before trusting the full 39-entry map. Spot-check a handful of
`GOAT_ASX_INDUSTRY_CONSTITUENTS` entries against each company's actual ASX listing/business
description.

---

## ACCEPTANCE CRITERIA

- [ ] `sector-ranking.md` and `industry-ranking.md` both show a Rotation Flow + Short-Window Flow
      section on every `monitor` run, and show neither on a `scan-sectors`/`scan-industries` run.
- [ ] A same-day double-run of `monitor` does not duplicate or corrupt snapshot rows.
- [ ] `industry-ranking.md` reports which industries are currently in a fresh breakout, and those
      ETFs get staged into `goat_pending_candidates` (`source="goat_industry_rotation"`).
- [ ] `scan-industry-heartbeat` (with and without `--industries`) stages genuinely new US+ASX stock
      candidates with fundamentals context attached, respecting three-way dedup and insolvency
      suppression.
- [ ] `scan-heartbeat` (sector-level) now also scans ASX constituents of currently-rising sectors.
- [ ] `scan-etf-heartbeat` stages ETF candidates from the full 57-ticker universe unconditionally,
      respecting the AUM liquidity floor and `GOAT_BANNED_TICKERS`.
- [ ] `promote-candidate` labels and tags every candidate correctly regardless of which of the 6
      sources staged it.
- [ ] `query-rotation-history` returns correct JSON with no DB writes and no notification side effects.
- [ ] Full `pytest -q` suite passes with zero regressions in any existing Goat test file.
- [ ] `investments/TOOLS.md` and `scripts/deploy.ps1` reflect every new command/report/timer.

## COMPLETION CHECKLIST

- [ ] All 8 phases completed in order, each phase's own tests passing before the next starts.
- [ ] `ruff check` and the full test suite both pass.
- [ ] Every new config constant has a comment matching this file's documentation-density convention.
- [ ] Manual VPS validation (Level 3/4 above) run and spot-checked by Shaun before the new timers are
      enabled.
- [ ] `TOOLS.md` + `deploy.ps1` updated; VPS timer units hand-created (flagged to Shaun, not attempted
      autonomously over SSH).

---

## NOTES

- **1-month short window** was deliberately dropped from Part A's scope (Decision 8) to keep the new
  report section to one extra table. If the 1-week window proves too noisy in practice (Shaun's own
  worry in the original handoff — "if SMH drifts down to just +30%, will that represent a trend"),
  adding `return_pct_1m`/`rising_1m` is a small, mechanical fast-follow: one more column on
  `goat_rotation_snapshots`, one more `rank_*` field, one more `compute_flow`/`render_flow_section`
  call — no architecture change.
- **The on-demand chart itself (Artifact + `dataviz` skill) is explicitly NOT a task in this plan** —
  Decision 9/10 only commit to building `query-rotation-history` so the data is pullable; the chart
  gets built fresh, on request, in whatever Claude Code session Shaun asks for one in, once enough
  snapshot history exists to make it worth looking at.
- **`GOAT_ASX_INDUSTRY_CONSTITUENTS`'s initial coverage is a judgment call for whoever executes
  Phase 4** — prioritize breadth across likely-gated industries (large ASX sectors: Materials/Mining,
  Financials, Health Care, Energy) over exhaustive 200-ticker coverage on day one. This mirrors every
  other "ship a useful slice, extend later" precedent in this codebase (`GOAT_INDUSTRY_ETFS` itself
  is 39 of 143; `MOAT_TARGET_INDUSTRIES` is 11 hand-picked industries, not all 143).
- **Confidence score: 7/10** for one-pass success. The main risk is Phase 4's `GOAT_FINVIZ_INDUSTRY_SLUGS`
  (unverifiable without a live fetch at planning time — flagged as an explicit research task, not
  guessed inline) and the genuine research effort `GOAT_ASX_INDUSTRY_CONSTITUENTS` requires (not a
  mechanical code task). Every other phase has a near-exact existing-code template to copy
  structurally, which is why the rest of the plan should execute cleanly in one pass.
