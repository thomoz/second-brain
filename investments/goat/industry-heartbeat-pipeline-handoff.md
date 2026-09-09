# Industry-Granularity Heartbeat Pipeline — Session Handoff

## Status: SUPERSEDED 2026-09-02 (same day) — folded into
`investments/goat/industry-pipeline-handoff.md` (Part B) so it can be planned
alongside rotation trend tracking, which touches the same files. Use the combined
handoff. Original status: NOT STARTED — handoff drafted 2026-09-02.

## What This Is

Extend Goat's full pick pipeline from **sector** granularity down to **industry**
granularity, so the workflow Shaun described can actually be run end to end:

1. Find which industries are doing well (`industry-ranking.md` — already built)
2. Take about four of them
3. Check the industry **index** (ETF) itself for a heartbeat / fresh 50DMA breakout
4. Scan the **companies inside** those industry indexes for the same heartbeat pattern
5. Check each survivor's business (free cash flow etc.) before it becomes a real candidate

Today, steps 3–4 only exist at the **11 SPDR sector** level. The 2026-08-23
industry work (`.agent/plans/completed/goat-industry-rotation-ranking.md`) added
**only step 1** — a 39-ETF ranking report — and deliberately stopped there
("no breakout signal, no DB table, no candidate staging, pure compute-and-render",
per that plan and `HANDOFF.md`). The industry layer is a viewing tool, not part of
the pick pipeline.

## Current State — what exists vs. what's missing

| Pipeline step | Sector level (built) | Industry level |
|---|---|---|
| Rotation ranking | `sector_rotation.rank_sectors` (11 ETFs, 63-day window) → `sector-ranking.md` | `industry_rotation.rank_industries` (39 ETFs, 126-day window) → `industry-ranking.md` ✓ |
| Index heartbeat/breakout check | `sector_rotation.check_sector_breakout` runs on all 11 sector ETFs in `run_sector_scan` → `sector-candidates-pending-review.md` | **MISSING** — `run_industry_scan()` has no breakout leg |
| Constituent universe | `sp500_universe.get_or_refresh_sp500_constituents` — Wikipedia scrape, cached in `goat_sp500_constituents`, mapped by GICS sector | **MISSING** — no stock→industry map anywhere |
| Stock heartbeat scan within hot groups | `heartbeat_scan.run_heartbeat_scan` — S&P 500 stocks filtered to **rising sectors** (return > 0), `check_heartbeat_breakout` per stock, `fundamentals_context` attached, staged in `goat_pending_candidates` | **MISSING** |
| Promote/dismiss | `cmd_promote_candidate` / `cmd_dismiss_candidate` (writes into my-trader watchlist, labeled Goat-approved) | reusable, minor label tweak needed |

Note also: even the sector path gates the stock scan on the sector being *rising*,
not on the sector ETF being *in a heartbeat*. Shaun's stated chain wants the
tighter gate (index heartbeat → then its constituents).

## Reusable infrastructure already in the workspace

- **`check_sector_breakout` / `check_heartbeat_breakout` are ticker-agnostic** —
  they take `(ticker, label, close_series)`. They can be pointed at the 39 industry
  ETFs with no change to their internals. (`heartbeat.py`'s module docstring says
  the deliberate-duplication convention means adding a thin `check_industry_breakout`
  wrapper rather than refactoring a shared helper — confirm during planning.)
- **`mytrader/finviz_screener.py`** — a working Finviz screener HTML scraper
  (requests + BeautifulSoup, pagination, courtesy delay, the ticker-watermark
  descramble quirk already handled). Currently hardcoded to
  `config.FINVIZ_SCREENER_FILTERS = "fa_pc_u3,geo_usa,sh_avgvol_o100,sh_price_o1"`
  for the cash-value scan. **Its `_EXPECTED_COLUMNS` already extracts an `Industry`
  field.** Parameterising it by a Finviz industry filter (`f=ind_<slug>`, plus a
  liquidity prefilter) is the natural constituent source.
- **`sp500_universe.py`** — the cache-in-DB-with-TTL pattern to mirror for an
  industry-constituents cache (`goat_industry_constituents` table + a
  `GOAT_INDUSTRY_CONSTITUENTS_CACHE_TTL_DAYS` constant).
- **`heartbeat_scan.py`** — the orchestration + three-way dedup (holding /
  watchlist / already-pending) + report-render pattern to mirror exactly.
- **`fundamentals_context.compute_survival_context`** — already covers step 5
  (debt → cash runway = `totalCash / abs(freeCashflow)` → margins → revenue growth
  → cash generation). Reuse unchanged; optionally surface FCF as its own column.
- **`GOAT_FINVIZ_INDUSTRIES`** (config.py) — the canonical 143-name industry
  taxonomy is already embedded, and it *is* Finviz's own taxonomy, so a Finviz
  screener source aligns 1:1 with it.

## Proposed shape (for `/plan-feature` to validate, not final)

- **`industry_rotation.py`** gains `check_industry_breakout(ticker, label, close)`
  (thin wrapper over the shared 50DMA-cross+slope idiom, or a direct second copy per
  the duplication convention). `run_industry_scan()` gains a breakout leg over the
  39 ETFs — output: the ranking (unchanged) plus a list of industries whose ETF is
  in a fresh rising breakout / heartbeat ("the gate list").
- **New `industry_constituents.py`** — Finviz-screener-backed, one screen per
  industry slug, cached in a new `goat_industry_constituents` table
  (`ticker, industry_label, fetched_at`), TTL-refreshed like the S&P 500 cache.
  A coarse liquidity prefilter in the Finviz filter string (min price, min avg
  volume, optional min market cap).
- **New `industry_heartbeat_scan.py`** (or a `scope=` parameter on the existing
  `heartbeat_scan.py`) — for each gated industry: load its constituents, run
  `check_heartbeat_breakout` per stock, attach `compute_survival_context`, apply the
  same insolvency-risk suppression + three-way dedup, stage into
  `goat_pending_candidates` with `source="goat_industry_heartbeat_scan"`.
- **New CLI subcommand** `scan-industry-heartbeat`, with an optional
  `--industries "Semiconductors,Oil & Gas Equipment & Services"` override for the
  "just these four" case (defaults to the gate list from the industry breakout leg).
- **Reports** — `industry-heartbeat-candidates-pending-review.md` (mirrors the
  existing pending-review files); add a breakout/candidate column or section to
  `industry-ranking.md`.
- **`cmd_promote_candidate`** — currently hardcodes the notes string
  "Goat-approved sector rotation candidate" and `source="goat_sector_rotation"`;
  needs to read the pending row's `source` and label accordingly. `GOAT_BANNED_TICKERS`
  enforcement stays.

## Open Questions for Shaun (resolve during `/plan-feature`)

1. **Which industries get their constituents scanned — the gate.**
   - (a) Only industries whose **ETF itself** passed a fresh rising 50DMA breakout /
     heartbeat this run. Tightest, matches the stated chain, keeps fetch counts
     bounded. **Recommended as the default.**
   - (b) Any **rising** industry (6-month return > 0) — looser, ~20 industries
     today, could mean 1000+ constituent price fetches per run.
   - (c) Only industries Shaun names via `--industries`. **Recommended as a manual
     override on top of (a).**
   - (d) Top-N ranked regardless of breakout.
2. **Constituent data source.**
   - Finviz screener by industry (reuse `finviz_screener.py`) — same taxonomy as
     `GOAT_FINVIZ_INDUSTRIES`, infra exists, covers all 143 industries not just the
     39 with ETFs. **Recommended.**
   - ETF holdings scrape (issuer sites / a holdings endpoint) — only the 39 ETF
     industries, more fragile (many issuers/formats), holdings drift.
   - yfinance per-ticker `.info["industry"]` over a base universe — slow, and Yahoo
     industry names don't map 1:1 to Finviz's 143.
3. **Universe breadth / liquidity floor** — min market cap, min share price, min
   average dollar volume for a constituent to be scannable. Need concrete defaults
   (start from `finviz_screener`'s existing `sh_avgvol_o100,sh_price_o1`?).
4. **The 104 industries with no ETF** — skip for v1 (only the 39 ETF-covered
   industries can have their index checked in step 3), or build a synthetic
   equal-weight industry index from the Finviz constituent list and run the
   heartbeat on that? The synthetic route unlocks all 143 but is a real scope
   increase (weighting scheme, survivorship, history depth). **Recommend skip for
   v1, flag as a follow-up handoff.**
5. **Cadence & Finviz load** — one Finviz screen per gated industry per run, plus
   pagination. With gate (a) that's ~0–8 screens/run. Confirm the existing
   `FINVIZ_REQUEST_DELAY_SECONDS` courtesy delay + a daily cadence is acceptable,
   and whether the constituent cache TTL should be longer (industry membership
   barely changes) than the price scan cadence.
6. **Replace or supplement the sector `scan-heartbeat`?** Recommend supplement —
   keep both, they answer different-resolution questions.
7. **History guard** — `check_heartbeat_breakout` needs ~243 trading days or returns
   `verdict="unknown"`. Many smaller industry constituents will come back unknown.
   Acceptable (same as today's S&P scan silently skips) or worth surfacing a count?
8. **Notification** — WhatsApp ping on new industry-heartbeat candidates, same as
   the sector and insider scans? (Assume yes unless told otherwise.)

## Sequencing note

`.agent/plans/goat-rotation-trend-tracking.md` (already drafted, not yet executed)
also modifies `run_industry_scan`, `monitor.py`'s industry render function, and
`main.py::cmd_monitor`'s connection lifecycle. Whichever ships second must rebase
onto the first. Recommend executing the smaller rotation-trend plan first, or
explicitly folding both into one plan during `/plan-feature`.

## Explicitly NOT scoped here

- No automatic buy/sell action — advisor-notes-only, same as everything else in
  `investments/` (SOUL.md).
- No synthetic index for the 104 non-ETF industries (see Open Question 4).
- No change to `rank_sectors` / `rank_industries` ranking maths.
- No change to the sector-level pipeline's behaviour.

## Validation (once built)

```powershell
uv run --directory investments/goat python -m pytest -q

# On the VPS via invoke_investments.ps1 — never run locally against the real DB:
.\scripts\invoke_investments.ps1 -Package goat -Command "scan-industries"
.\scripts\invoke_investments.ps1 -Package goat -Command "scan-industry-heartbeat"
.\scripts\invoke_investments.ps1 -Package goat -Command "scan-industry-heartbeat --industries ""Semiconductors,Oil & Gas Equipment & Services"""
```
