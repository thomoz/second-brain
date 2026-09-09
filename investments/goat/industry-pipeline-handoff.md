# Industry-Granularity Pipeline + Rotation Trend Tracking — Combined Session Handoff

## Status: NOT STARTED — combined handoff drafted 2026-09-02. Awaiting `/plan-feature` (Shaun's call to invoke, not automatic).

Folds together two previously separate handoffs that touch the same files
(`run_industry_scan`, `monitor.py`'s industry render, `main.py::cmd_monitor`,
`industry-ranking.md`, `config.py`, `db.py`, industry tests):

- **Part A — Rotation Trend Tracking.** Was
  `investments/goat/rotation-trend-tracking-handoff.md` + a full plan at
  `.agent/plans/goat-rotation-trend-tracking.md` (that plan is a good Part-A
  reference; the combined `/plan-feature` run supersedes it).
- **Part B — Industry-Granularity Heartbeat Pipeline.** Was
  `investments/goat/industry-heartbeat-pipeline-handoff.md`.

Both originals now carry a "superseded by this file" note.

---

## The Goal In One Line

Make Goat's **industry** layer a first-class part of the pick pipeline (not just a
viewing report), and give both the sector and industry rotation rankings a memory
of which way trends are heading.

The workflow Shaun wants to run end to end:

1. Find which industries are doing well — `industry-ranking.md` (built)
2. See which way each is **heading** since the last run — **Part A**
3. Take about four of the strong ones
4. Check the industry **index** (ETF) itself for a heartbeat / fresh 50DMA breakout — **Part B**
5. Scan the **companies inside** those industry indexes for the same heartbeat — **Part B**
6. Check each survivor's business (free cash flow etc.) before it becomes a candidate — reuses existing `fundamentals_context`

Today steps 4–5 exist only at the **11 SPDR sector** level. The 2026-08-23 industry
work added **only step 1** (a 39-ETF ranking), by design
(`.agent/plans/completed/goat-industry-rotation-ranking.md`: "no breakout signal,
no DB table, no candidate staging, pure compute-and-render").

---

## Current State — what exists vs. what's missing

| Pipeline step | Sector level (built) | Industry level |
|---|---|---|
| Rotation ranking | `rank_sectors` (11 ETFs, 63-day window) → `sector-ranking.md` | `rank_industries` (39 ETFs, 126-day window) → `industry-ranking.md` ✓ |
| Trend memory (which way is it heading) | **MISSING** — pure overwrite every run | **MISSING** — pure overwrite every run |
| Index heartbeat/breakout check | `check_sector_breakout` on all 11 sector ETFs in `run_sector_scan` → `sector-candidates-pending-review.md` | **MISSING** — `run_industry_scan()` has no breakout leg |
| Constituent universe | `sp500_universe` — Wikipedia scrape, cached in `goat_sp500_constituents`, mapped by GICS sector | **MISSING** — no stock→industry map anywhere |
| Stock heartbeat scan within hot groups | `heartbeat_scan` — S&P 500 stocks filtered to **rising sectors** (return > 0), `check_heartbeat_breakout` per stock, `fundamentals_context` attached, staged in `goat_pending_candidates` | **MISSING** |
| Promote/dismiss | `cmd_promote_candidate` / `cmd_dismiss_candidate` (writes into my-trader watchlist, labeled Goat-approved) | reusable, minor label tweak needed |

Even the sector path gates the stock scan on the sector being *rising*, not on the
sector ETF being *in a heartbeat*. Shaun's chain wants the tighter gate
(index heartbeat → then its constituents).

---

## PART A — Rotation Trend Tracking

### What it adds

Both `sector-ranking.md` and `industry-ranking.md` are pure live-re-fetch snapshots:
every run recomputes each ticker's window return and **overwrites** the file, with no
memory of the prior run. There is no way to answer "how many days has this been
falling" or see a transition table without `git log -p` archaeology.

Add a daily snapshot table plus a "Rotation Flow" section on both files showing which
tickers flipped Rising/Falling since the last snapshot, and a rollup summary of the
transitions.

Prompted by Shaun asking after the industry ranking shipped: *"if SMH drifts down to
just +30%, will that represent a trend and will we see it?"* — today's answer is no.

### Decisions already confirmed with Shaun (2026-08-23)

1. **State model: 2-state Rising/Falling**, reusing the existing `rising: bool`
   (`return_pct > 0`) that `rank_sectors`/`rank_industries` already compute. The
   3-state DOWNHILL/BASE/CLIMBING model from Goat Academy's own tool is explicitly
   deferred — it needs a sourced classification threshold that doesn't exist in this
   repo. Do not build it here.
2. **Comparison granularity: day-over-day.** Both scans run daily via `monitor`.
3. **Schema: one shared snapshot table** (`scope`, `snapshot_date`, `ticker`,
   `label`, `return_pct`, `rank`, `rising`), not two scope-specific tables.
4. **Retention: cap at 90 days**, matching the two existing 90-day lookback
   precedents in `config.py`.
5. **Write cadence: only the once-daily `monitor` run writes a snapshot.** On-demand
   `scan-sectors` / `scan-industries` compute and render the ranking as before but
   do NOT insert a snapshot row or show a Rotation Flow section (avoids same-day
   double-counting).
6. **Report layout: additive.** Rotation Flow is a new section alongside the
   existing Top 5 / Bottom 5 / Full Ranking tables, not a replacement.
7. **Filter chips** (per-industry drill-down from the reference screenshot): out of
   scope.

### Part A shape

- New `goat_rotation_snapshots` table + CRUD in `db.py`
  (`insert_rotation_snapshots`, `get_rotation_snapshot`,
  `get_latest_snapshot_date_before`, `prune_rotation_snapshots`), keyed
  `UNIQUE(scope, snapshot_date, ticker)` with `INSERT OR IGNORE` so a same-day
  double-run of `monitor` is a safe no-op.
- New `GOAT_ROTATION_SNAPSHOT_RETENTION_DAYS = 90` in `config.py`.
- New pure-compute `goat/rotation_flow.py` — `compute_flow(previous_rows,
  current_ranking, *, label_key)` returns `{transitions, summary, no_prior_count}`;
  `render_flow_section(...)` returns a `list[str]` markdown fragment. Tickers with
  `rising is None` on either side are excluded (an unknown state can't transition).
- New `monitor.capture_rotation_snapshot(conn, *, scope, ranking, label_key)` —
  looks up the most recent prior snapshot, diffs, inserts today's, prunes past the
  retention window. Called only from `cmd_monitor`, once per scope.
- `cmd_monitor` connection lifecycle change: `conn.close()` currently fires right
  after `run_sector_scan`, before `run_industry_scan`. It must move to after both
  scans + both `capture_rotation_snapshot` calls.
- Both `render_sector_ranking_report` and `render_industry_ranking_report` splice in
  the Rotation Flow section when `result.get("rotation_flow")` is present (absent on
  the on-demand scan path — the regression guard that proves `scan-sectors` /
  `scan-industries` reports are unaffected).

### Part A open question — short-window flow (NEW, raised 2026-09-02)

The confirmed 2-state model diffs the flip of the **126-day (industry) / 63-day
(sector)** return sign. That is sluggish for "where did money go **this week**" —
which is how Felix actually reads the board. **Consider having `rotation_flow` also
diff a short-window return** (1-week and/or 1-month, computed from the same closes
already fetched — no new data, no new fetch). This makes "flowed in this week /
flowed out this week" a real signal rather than waiting weeks for the half-year
number to change sign. Resolve during `/plan-feature`: add the short window now, or
ship the sign-flip model first and add short-window as a fast follow.

---

## PART B — Industry-Granularity Heartbeat Pipeline

### Reusable infrastructure already in the workspace

- **`check_sector_breakout` / `check_heartbeat_breakout` are ticker-agnostic** —
  `(ticker, label, close_series)`. Can be pointed at the 39 industry ETFs with no
  change to internals. `heartbeat.py`'s docstring says the deliberate-duplication
  convention favours a thin `check_industry_breakout` wrapper (or a second copy)
  over refactoring a shared helper — confirm during planning.
- **`mytrader/finviz_screener.py`** — a working Finviz screener scraper (requests +
  BeautifulSoup, pagination, `FINVIZ_REQUEST_DELAY_SECONDS` courtesy delay, the
  ticker-watermark descramble quirk handled). Currently hardcoded to
  `FINVIZ_SCREENER_FILTERS = "fa_pc_u3,geo_usa,sh_avgvol_o100,sh_price_o1"`. Its
  `_EXPECTED_COLUMNS` **already extracts an `Industry` field.** Parameterising it by
  a Finviz industry filter (`f=ind_<slug>` + liquidity prefilter) is the natural
  constituent source.
- **`sp500_universe.py`** — the cache-in-DB-with-TTL pattern to mirror for a
  `goat_industry_constituents` table + `GOAT_INDUSTRY_CONSTITUENTS_CACHE_TTL_DAYS`.
- **`heartbeat_scan.py`** — orchestration + three-way dedup (holding / watchlist /
  already-pending) + report-render pattern to mirror.
- **`fundamentals_context.compute_survival_context`** — already covers step 6
  (debt → cash runway = `totalCash / abs(freeCashflow)` → margins → revenue growth
  → cash generation). Reuse unchanged; optionally surface FCF as its own column.
- **`GOAT_FINVIZ_INDUSTRIES`** (config.py) — the canonical 143-name taxonomy is
  already embedded and it *is* Finviz's taxonomy, so a Finviz source aligns 1:1.

### Part B shape

- `industry_rotation.py` gains `check_industry_breakout(ticker, label, close)`.
  `run_industry_scan()` gains a breakout leg over the 39 ETFs — output: the ranking
  (unchanged) plus a "gate list" of industries whose ETF is in a fresh rising
  breakout / heartbeat. (This also means `run_industry_scan` now needs a `conn` —
  today it takes none. Coordinate with Part A's `cmd_monitor` change.)
- New `industry_constituents.py` — Finviz-screener-backed, one screen per industry
  slug, cached in `goat_industry_constituents` (`ticker, industry_label,
  fetched_at`), TTL-refreshed. Coarse liquidity prefilter in the filter string.
- New `industry_heartbeat_scan.py` (or a `scope=` parameter on `heartbeat_scan.py`)
  — for each gated industry: load constituents, `check_heartbeat_breakout` per
  stock, attach `compute_survival_context`, apply insolvency-risk suppression +
  three-way dedup, stage into `goat_pending_candidates` with
  `source="goat_industry_heartbeat_scan"`.
- New CLI `scan-industry-heartbeat`, with optional
  `--industries "Semiconductors,Oil & Gas Equipment & Services"` override for the
  "just these four" case (defaults to the gate list).
- Reports: `industry-heartbeat-candidates-pending-review.md` (mirrors existing
  pending-review files); add a breakout/candidate column or section to
  `industry-ranking.md`.
- `cmd_promote_candidate` currently hardcodes "Goat-approved sector rotation
  candidate" + `source="goat_sector_rotation"`; must read the pending row's `source`
  and label accordingly. `GOAT_BANNED_TICKERS` enforcement stays.

### Part B open questions (resolve during `/plan-feature`)

1. **The gate — which industries get their constituents scanned.**
   - (a) Only industries whose **ETF itself** passed a fresh rising 50DMA breakout /
     heartbeat this run. Tightest, matches the stated chain, bounds fetch counts.
     **Recommended default.**
   - (b) Any **rising** industry (return > 0) — ~20 today, could mean 1000+
     constituent price fetches per run.
   - (c) Only industries Shaun names via `--industries`. **Recommended as a manual
     override on top of (a).**
   - (d) Top-N ranked regardless of breakout.
2. **Constituent data source.**
   - Finviz screener by industry (reuse `finviz_screener.py`) — same taxonomy as
     `GOAT_FINVIZ_INDUSTRIES`, infra exists, covers all 143 industries. **Recommended.**
   - ETF holdings scrape — only the 39 ETF industries, fragile, holdings drift.
   - yfinance per-ticker `.info["industry"]` — slow, names don't map 1:1 to Finviz.
3. **Universe breadth / liquidity floor** — min market cap, min price, min average
   dollar volume. Concrete defaults needed (start from `sh_avgvol_o100,sh_price_o1`?).
4. **The 104 industries with no ETF** — skip for v1 (can't heartbeat-check an index
   that doesn't exist), or build a synthetic equal-weight industry index from the
   Finviz constituent list and run the heartbeat on that? Synthetic unlocks all 143
   but is a real scope increase (weighting, survivorship, history depth).
   **Recommend skip for v1, flag as a follow-up.**
5. **Cadence & Finviz load** — one screen per gated industry per run + pagination.
   Gate (a) → ~0–8 screens/run. Confirm daily cadence + the existing courtesy delay
   is fine, and whether the constituent-cache TTL should be long (membership barely
   changes).
6. **Replace or supplement the sector `scan-heartbeat`?** Recommend supplement.
7. **History guard** — `check_heartbeat_breakout` needs ~243 trading days or returns
   `verdict="unknown"`. Many smaller constituents will be unknown. Acceptable (same
   as today's S&P scan) or surface a count?
8. **Notification** — WhatsApp ping on new industry-heartbeat candidates, same as
   the sector and insider scans? (Assume yes unless told otherwise.)

---

## Suggested phase order for the plan

1. **Part A** — rotation snapshots + Rotation Flow (+ decide short-window flow).
   Smallest, already has a reference plan.
2. **Part B-1** — `check_industry_breakout` + the breakout leg in `run_industry_scan`
   (industry ETF heartbeat check → gate list). Shares the `cmd_monitor` /
   `run_industry_scan` connection changes with Part A, hence the folding.
3. **Part B-2** — `industry_constituents.py` + `goat_industry_constituents` cache +
   Finviz-screener parameterisation.
4. **Part B-3** — `industry_heartbeat_scan.py` + staging + reports + CLI +
   `cmd_promote_candidate` label fix.
5. Tests, `TOOLS.md`, VPS validation for the whole set.

---

## Explicitly NOT scoped here

- No automatic buy/sell action — advisor-notes-only (SOUL.md).
- No 3-state DOWNHILL/BASE/CLIMBING model (Part A Decision 1).
- No synthetic index for the 104 non-ETF industries (Part B Open Question 4).
- No new alerting on trend *drift* (Part A is visibility, not automation).
- No change to `rank_sectors` / `rank_industries` ranking maths.
- No change to the sector-level pipeline's behaviour.

## Validation (once built)

```powershell
uv run --directory investments/goat python -m pytest -q

# On the VPS via invoke_investments.ps1 — never run locally against the real DB:
.\scripts\invoke_investments.ps1 -Package goat -Command "monitor"
.\scripts\invoke_investments.ps1 -Package goat -Command "scan-industries"
.\scripts\invoke_investments.ps1 -Package goat -Command "scan-industry-heartbeat"
.\scripts\invoke_investments.ps1 -Package goat -Command "scan-industry-heartbeat --industries ""Semiconductors,Oil & Gas Equipment & Services"""
```

First `monitor` run after deploy shows "No prior snapshot yet" for both scopes
(expected — no history before this ships).
