# Goat — Session Handoff

## Status: Phase 1 complete 2026-08-11 — see `.agent/plans/goat-phase1-150dma-exit-check.md` (150DMA holdings exit check). `investments/goat/` is a working uv workspace member; `python -m goat.main monitor` runs against the real shared DB, checks all holdings, writes only to `goat_alert_history` and `investments/goat/monitor-report.md`. systemd units exist but are NOT enabled on the VPS — needs Shaun's explicit go-ahead. Phase 2 complete 2026-08-11 — see `.agent/plans/goat-phase2-sector-rotation-ranking.md` (11 SPDR sector ETF ranking + 50DMA cross/slope breakout signal; 39/39 tests passing; `scan-sectors`/`monitor` run live against the real shared DB — real breakouts fired on XLB/XLI/XLK during validation; `promote-candidate` confirmed writing correctly-labeled Goat-approved rows into my-trader's real `watchlist.md` (XLB and XLK promoted live), `dismiss-candidate` confirmed to leave `watchlist.md` untouched (XLI dismissed live) — this is real production watchlist state, not test fixtures, see NOTES below). Intraday 150DMA Alerting built 2026-08-16 — see that section below; systemd units exist but are NOT enabled on the VPS, needs Shaun's explicit go-ahead. Phase 3 complete 2026-08-17 — see `.agent/plans/goat-phase3-heartbeat-scanner.md` (S&P 500 heartbeat scanner: Wikipedia constituent scrape cached weekly in `goat_sp500_constituents`, BBW-percentile-squeeze + 50DMA-cross-and-slope combined signal in `heartbeat.py`, informational fundamentals survival context in `fundamentals_context.py` with insolvency-risk staging suppression, orchestrated by `heartbeat_scan.py::run_heartbeat_scan()`; new `scan-heartbeat` CLI subcommand; 91/91 tests passing, ruff + mypy clean; `goat_pending_candidates` reused as-is with `source="goat_heartbeat_scan"`). systemd units exist but are NOT enabled on the VPS — needs Shaun's explicit go-ahead, same as every prior Goat rollout, plus a real `scan-heartbeat` run against the live DB (Level 4) before flipping the weekly timer on. Heartbeat "quiet" leg redesigned 2026-08-26 — see `.agent/plans/goat-heartbeat-quiet-redesign.md`. The BBW-percentile squeeze (structurally unable to pass on real history — flagged zero candidates every run 2026-08-17 → 08-26, quiet score pinned near 0.00 for 42/42 hand-checked large caps) is replaced by a direct base-range % + inner-band smoothness test plus a 50/150-day-MA position-of-strength filter in `heartbeat.py` (`bollinger_width_series` / `_is_in_squeeze` and the four `GOAT_HEARTBEAT_BBW_*` config constants removed; `GOAT_HEARTBEAT_SQUEEZE_MIN_FRACTION` → `GOAT_HEARTBEAT_BASE_SMOOTHNESS_MIN_FRACTION`; six new `GOAT_HEARTBEAT_*` constants). New minimum-history guard is 243 trading days (150 + 63 + 20 + 10); below that returns `verdict="unknown"` honestly. `heartbeat_scan.py` orchestration and the `goat_pending_candidates` staging are unchanged. 208/208 goat tests passing, my changed files ruff + mypy clean; DB-free diagnostic over 42 large caps confirms `base_range_pct` is now a real distribution (10–25%) instead of a pinned-near-zero quiet score. Validated with a real `scan-heartbeat` VPS run 2026-08-26 (327 tickers / 7 rising sectors / 0 candidates — the near-misses EQIX + PLD chart-checked and correctly rejected, so the six v1/tunable constants were left as-is). Cadence moved **weekly → daily** 2026-08-26 (`second-brain-goat-heartbeat-scan.timer` now `OnCalendar=*-*-* 22:45:00 UTC`; report renderer + `GOAT_SP500_CACHE_TTL_DAYS` comment updated to match); the VPS timer needs `sudo cp` of the new unit file + `daemon-reload` to pick that up. Industry Rotation Ranking complete 2026-08-23 — see `.agent/plans/goat-industry-rotation-ranking.md` (extends sector rotation down to Finviz's ~143 industry groups; 39/143 mapped to a dedicated ETF via new `GOAT_INDUSTRY_ETFS`, the rest gap-noted in `industry-ranking.md`'s "Not Covered" section, never silently proxied; `industry_rotation.py` mirrors `sector_rotation.py`'s fetch/rank pair over a 6-month/126-trading-day window — deliberately separate from the sector ranking's 3-month window; no breakout signal, no DB table, no candidate staging, no WhatsApp notification, pure live-refetch compute-and-render; new `scan-industries` CLI subcommand, also runs as part of daily `monitor` on the existing timer). On-demand chart-by-industry stays purely conversational per Shaun's decision — recipe documented in the plan, no code. Insider discovery queue filter added 2026-08-29 — `run_discovery_scan` now drops institutional 10%-owner Form 4 filers (outside asset managers / funds / holding vehicles that file only because they crossed the 13(d) 10% threshold; prompted by "Metlife Investment Management, LLC" staging $22M+ Mandatory Redeemable Preferred Share buys across 4 Calamos CEFs CCD/CHI/CHW/CHY). A filer is institutional when its name matches a corporate-designator pattern AND its title is a bare "10%" with no officer/director role — individual 10% owners and entities holding a board seat are still kept. New config: `GOAT_INSIDER_DISCOVERY_EXCLUDE_INSTITUTIONAL_10PCT` (bool toggle) + `GOAT_INSIDER_INSTITUTIONAL_NAME_RE_PARTS`; helpers `_is_institutional_10pct_filer` / `_INSTITUTIONAL_NAME_RE` / `_OFFICER_DIRECTOR_TITLE_RE` in `insider_scan.py`. Filter is discovery-buys-only — filing dropped before any `goat_insider_filings_seen` row is written; `run_discovery_sell_tracking` and `run_holdings_watch` untouched. 213/213 goat tests passing (+5 new). Ticker assignment was never wrong (the name column is the Form 4 reporting person, not the issuer) — this is a signal-quality filter, not a bug fix. Existing institutional rows already staged in `goat_pending_candidates` are not auto-removed — `dismiss-candidate` them manually or leave them.

## What This Is

A sector-rotation + momentum tool, named after the Goat's Academy webinar it's based
on. Source notes: `investments/my-trader/transcripts/lesson-extraction/goat-academy-webinar-1.md`

Genuinely different from my-trader/briefs-finance's fundamentals-driven, single-stock
value investing — this is technical/momentum-driven and operates at the sector level
first, individual stock level second. Kept as its **own package** (`investments/goat/`,
sibling to `briefs-finance/` and `my-trader/`) rather than folded into either, precisely
because the philosophies are different enough that mixing them would blur design
decisions already made deliberately elsewhere (see below).

## Context

**my-trader today**: fundamentals/quality-driven, single-stock picks graded against
Shaun's own criteria plus 9 value-investor frameworks (Graham, Buffett, Lynch, etc.).
`checks/price_action.py` has an explicit, deliberate design decision that **price
momentum is not a signal** — `verdict` is always `"info"`, never `"flag"` or
`"interesting"`, directly citing Graham's own principle file ("price momentum does not
[matter]").

**Goat (from the notes)**: sector-rotation + momentum-breakout investing. Three steps:
1. **Read the scoreboard** — find rising industries/sectors (follow institutional
   money), buy an index fund of that sector rather than picking individual stocks.
   Within a chosen sector, the entry signal on an individual stock/index is a
   "heartbeat" pattern: a smooth, low-volatility sideways consolidation for a minimum
   of ~3 months (longer is better — cited examples had 2-4 years of consolidation
   before a 10x move), followed by a breakout above the 50-day moving average with the
   50DMA itself turning from sloping down to sloping up. Risk-management check on the
   underlying fundamentals, in priority order: debt (zero is best) → cash runway in
   years → margins → revenue growth → cash generation — essentially "how unlikely is
   bankruptcy," not a valuation judgment.
2. **You don't have to pick stocks** — industries/sectors move together; a falling
   stock usually means the whole sector is falling, so rotate to whichever sector is
   rising rather than trying to time an individual name.
3. **The exit matters most** — the #1 investor mistake is holding a winner until it
   becomes a loser. Exit rule: sell when price drops "reasonably below" the 150-day
   moving average (allow for the price to dip through it briefly and recover — this
   isn't a same-day trigger).

Paid apps Shaun's notes reference (context only, not being adopted): TradeVision
($24.99/mo, general market view) and Winston App ($57/mo, finds index funds by
sector). Everything below is scoped to be buildable for free with what's already
available (yfinance + FRED, no new paid dependency), same philosophy as
briefs-finance/my-trader.

**Real connection already observed live**: the LULU chart Shaun screenshotted earlier
in the same conversation that produced this handoff (50 SMA + 150 MA both plotted,
"just crossed over the 50 day moving average") is this exact framework already being
applied manually, before these notes were even shared. Good validation this is a real,
currently-manual workflow worth automating, not a hypothetical.

## Shaun's three direct questions (answered in conversation, captured here for the plan)

1. **"Is there a free way to see which sectors are rising/falling?"** — Yes. The 11
   SPDR Select Sector ETFs (XLK tech, XLF financials, XLE energy, XLV healthcare, XLY
   discretionary, XLP staples, XLI industrials, XLB materials, XLU utilities, XLRE
   real estate, XLC communication) are all free on yfinance. Comparing relative
   performance/relative strength across them over a rolling window (e.g. 3-month)
   answers "where is money rotating into" without any paid tool.
2. **"Can it scan for stocks with the heartbeat pattern that just crossed the 50DMA?"**
   — Yes, technically, but this is the harder half — see Phase 3 and the open question
   on candidate universe below. The moving-average/cross-detection logic already
   exists in my-trader (`gold_technicals.py` + `macro_indicators.py`'s
   `check_gold_trend()` sign-flip cross detection) and generalizes directly to any
   ticker's 50DMA — worth reusing/porting rather than reinventing (see "Reuse vs.
   standalone" below). The "heartbeat" (low-volatility consolidation for 1-3+ months)
   needs a new, concrete definition — see Phase 3.
3. **"Should it auto-run daily?"** — Recommended split cadence, not a single answer:
   the holdings 150DMA exit check (Phase 1) is cheap and should run daily, same
   cadence as my-trader's Monitor. The sector-rotation ranking (Phase 2) is also cheap
   (11 ETF price fetches) and can run daily. The stock/heartbeat scanner (Phase 3) is
   the expensive, unresolved piece — see Open Questions.

## Reuse vs. standalone — RESOLVED 2026-08-11

**Decision: (a) Goat depends on my-trader as a workspace package.** Add `"goat"` to
`investments/pyproject.toml`'s `[tool.uv.workspace] members`, have Goat import
`mytrader.market_data` / the moving-average logic directly. Simplest to build now;
accepted coupling to my-trader's internals as the tradeoff.

**Data storage — RESOLVED 2026-08-11: new tables inside the existing
`investments/briefs-finance/data/investments.db`**, not a separate DB file — chosen
specifically so sector/stock data can be combined/joined with my-trader's holdings
data later if useful. Goat still must NOT write into the existing `holdings`/`watchlist`
tables (those stay my-trader's) — this is new Goat-specific tables in the same file,
not new rows in existing tables. Phase 1's 150DMA check reads my-trader's holdings
for reference; Goat's own scan results/pending-candidates go in its own new tables.

## Remaining Steps

### Phase 1 — Holdings 150DMA exit check (build first — cheapest, highest value, matches "exit matters most")

- Reads my-trader's holdings (`db.get_all_holdings(conn)` — read-only cross-package
  access, resolved by whichever option above is chosen)
- For each holding: fetch price history, compute 150-day MA, determine if price is
  "reasonably below" it — needs a concrete threshold, not just "any dip below" (the
  notes explicitly warn price can dip through and recover). Candidate approaches to
  resolve during planning: a %-below threshold (e.g. >2-3% below), and/or a
  minimum-consecutive-days-below requirement, to avoid a single noisy day firing an
  alert that reverses tomorrow.
- This is a genuine "the exit rule fired" event, not neutral info, unlike
  `price_action.py`'s deliberate neutrality — this check exists specifically *because*
  Shaun wants this rule enforced, not just observed. Needs its own dedup mechanism
  (either reuse my-trader's `alert_history` pattern against a Goat-specific
  ticker/source_table, or a Goat-native equivalent, depending on the reuse decision
  above)
- Cadence: **daily** — cheap (one price history fetch per holding); my-trader's
  `snapshot.py` already fetches a live price for every holding daily for the P&L
  column and records it to `holdings_price_history` — worth checking whether that
  data can be read directly instead of a second fetch

### Phase 2 — Sector rotation ranking (build second — cheap, standalone)

- Fetch the 11 SPDR Select Sector ETFs via yfinance, rank by relative performance
  over a rolling window (window length TBD during planning — the notes' own
  "heartbeat" cited multi-month-to-multi-year timeframes, so a single 3-month window
  is a starting guess, not settled)
- Output: which sector(s) are "rising" vs "falling" — this becomes the candidate
  filter Phase 3 uses, rather than Phase 3 scanning the whole market blindly
- **RESOLVED 2026-08-11 — Phase 2 is also a standalone signal, not just a filter.**
  Shaun wants both: individual stocks found within hot sectors (Phase 3), AND the
  sector ETF itself surfaced as a real candidate when it's showing strength — an ETF
  looking good is itself a sign the sector is heating up. This means Phase 2 needs its
  own opportunity-style signal (not just a plain info report as originally scoped) —
  likely the same heartbeat/50DMA-cross detection logic from Phase 3, applied to the
  11 sector ETFs directly rather than only to individual stocks within them. Needs
  scoping during planning: does Phase 2 reuse Phase 3's pattern-detection code on ETFs,
  or run it in parallel on both?
- Cadence: daily is cheap (11 tickers), but the *signal* itself is inherently
  slow-moving (sector rotation happens over weeks/months) — daily computation is fine,
  but don't expect the ranking to change often, and don't alert on every tiny reorder

### Phase 3 — Stock/index "heartbeat" scanner within rising sectors (build last — hardest, most open questions)

**Reference chart**: `investments/goat/references/heartbeat-pattern-example-2026-08-16.png` — a
real chart Shaun annotated showing the pattern this phase needs to detect: a low-volatility
sideways consolidation (candles ranging within a flat channel) followed by a breakout above the
top of the range. Use as a visual sanity-check against whatever consolidation-flatness metric
gets chosen during planning (e.g. does the metric correctly flag this exact shape as a
qualifying heartbeat, and not flag ordinary chop that never breaks out).

- For each candidate ticker (see Open Questions on where this list comes from):
  fetch price history, detect:
  1. A "heartbeat" consolidation — low-volatility sideways range sustained for a
     minimum duration (notes say 1-3 months minimum, longer is better). Needs a
     concrete definition during planning — e.g. rolling price range as a % of mean
     staying under some threshold over a rolling window, or an ATR-based flatness
     measure. This is the single most underspecified part of the whole framework and
     needs real research/backtesting before picking a number, same discipline
     `opportunity.py`'s thresholds went through in my-trader (sourced from real
     principles/methodology, not invented) — don't just guess a number and ship it.
  2. Confirmation the 50DMA has turned from sloping down to sloping up (compare
     50DMA today vs. N days ago — same shape as my-trader's `check_recession_signal()`
     today/prior lookback comparison)
  3. Confirmation price has just crossed above the 50DMA (reuse the existing
     sign-flip cross-detection logic directly)
- Fundamentals risk filter, applied after the technical pattern fires (per the notes'
  own ordering — technical signal first, then a survival check, not the other way
  around): debt (low/zero preferred), cash runway, margins, revenue growth, cash
  generation. Several of these already exist as raw numbers in my-trader's
  `balance_sheet.py`/`valuation.py` and could be reused/ported; "cash runway in years"
  specifically does **not** exist anywhere in my-trader today and would be new
  (relevant mainly for cash-burning, not-yet-profitable companies — a different
  company profile than most of what my-trader's existing 9 value frameworks are built
  around)
- Output: **do not write into my-trader's `watchlist.md`/`holdings.md` directly** —
  same precedent as my-trader's own `candidate_sync.py`, land in Goat's own
  pending-review staging file/table, explicit promote/dismiss action required. If
  "promote" ever means "add to my-trader's watchlist," that's a cross-package write
  and needs its own explicit design, not an assumption.
- **Candidate universe — RESOLVED 2026-08-11: (c) scrape S&P 500 constituents**
  (e.g. Wikipedia's S&P 500 table) tagged by GICS sector, for real new-idea discovery
  rather than being limited to my-trader's existing watchlist/holdings.
- **Cadence — RESOLVED 2026-08-11: weekly scheduled scan, plus on-demand trigger.**
  Matches the existing Monitor (scheduled) / Find (on-demand) split already used by
  my-trader — e.g. "scan tech sector for heartbeat setups" callable anytime, such as
  when news moves a sector, in addition to the automatic weekly run.

### Intraday 150DMA Alerting — built 2026-08-16 (cross-cutting timing change to Phase 1, not its own numbered phase)

**Status: built, not yet enabled on the VPS.** See `.agent/plans/goat-intraday-150dma-alerting.md`. New `goat/market_hours.py` (zoneinfo-based ASX/US regular-session gating, no holiday calendar), `exit_check.check_150dma_exit_live()` (live price vs. a 150DMA computed only from completed daily closes — never live-updating), `goat/live_monitor.py::run_live_monitor()` (filters holdings to whichever market is currently open, fetches live quotes via `mytrader.market_data.fetch_current_price`, reconciles alerts through the same `goat.monitor.reconcile_alerts`/`goat_alert_history` dedup the daily check uses — the two checks share one dedup row per ticker+check_name so they can never double-alert), new `check-live` CLI subcommand, new `second-brain-goat-live-check.service`/`.timer` (`OnCalendar=*:0/10`, `GOAT_LIVE_POLL_INTERVAL_MINUTES=10` in config.py), `deploy.ps1`'s `$TIMERS` array updated. 61/61 tests passing (8 new market-hours tests, 8 new live-monitor tests, 5 new live-exit-check tests), ruff + mypy clean. Systemd units exist but are **NOT enabled on the VPS** — needs Shaun's explicit go-ahead, same as Phase 1's original rollout, plus a real open-market manual validation run per the plan's Level 4 before flipping it on.

**Problem**: Phase 1's exit check (`goat/exit_check.py` + `goat/monitor.py`) is fully built and
live (systemd timer, enabled + active on the VPS since 2026-08-16, WhatsApp alerts firing via
`send_whatsapp_notification`) — but it only runs **once daily**, at 21:35 UTC (07:35 AEST), after
markets have closed, checking that day's final close price. Shaun explicitly wants to be alerted
the moment a holding's price crosses below its 150DMA **while the market is still open**, not
found out about it at next morning's batch run ("I need to be alerted via whatsapp AS SOON AS IT
DROPS BELOW THE 150DMA"). As an interim step, `GOAT_150DMA_FLAG_PCT` was dropped to `0.0` and
`GOAT_150DMA_MIN_CONSECUTIVE_DAYS` to `1` (2026-08-16, see `goat/config.py` comments) — this
removes the *within-a-run* confirmation delay (whipsaw filter) but does **not** change the once-
daily cadence itself, so it does not satisfy this request on its own.

**What's actually needed**: a live/intraday variant of the same check, running repeatedly during
market hours instead of once after close.

**Open design questions — needs real research/decisions during `/plan-feature`, not assumptions:**

1. **Live price source.** `goat/price_history.py`'s `fetch_close_history()` uses
   `yf.Ticker(ticker).history(...)` for daily bars — need to confirm/research the right yfinance
   call for a current/live quote (e.g. `fast_info`, `.info`, or short-interval `history(period="1d",
   interval="1m")`) and how reliable/rate-limited it is under frequent polling.
2. **Polling cadence during market hours** — how often is "as soon as" (every 5 min? 15? 30?),
   trading off alert latency against yfinance rate-limit/reliability risk and VPS load.
3. **Two separate market-hours windows.** Holdings include both ASX-listed tickers (trade Sydney
   daytime, ~10am-4pm AEST) and US-listed tickers (trade Sydney overnight, ~11:30pm-6am AEST/
   12:30-7am AEDT) — a single daily-hours polling window doesn't cover both; scheduling needs to
   either run near-continuously or dispatch per-ticker based on its listed exchange.
4. **What "crosses" means against a live price.** The 150DMA itself is still computed from daily
   closes (recomputing it intraday from partial-day data doesn't make sense) — so this is "does
   the *current live price* sit below the *most recently completed* 150DMA," not a live-updating
   MA. Needs to reuse `exit_check.check_150dma_exit`'s MA computation but swap in a live price
   for the "close" input.
5. **Dedup/re-alert behavior at this cadence.** Existing `goat_alert_history` dedup (one open
   alert per ticker+check_name until acknowledged) should still prevent repeat pings for a
   standing breach — confirm this still holds when checks run every few minutes instead of once
   daily, rather than assuming.
6. **Cost/reliability**: yfinance is a scraping-based, free, unofficial API — confirm during
   planning whether frequent intraday polling risks getting rate-limited/blocked in a way the
   once-daily cadence doesn't, and whether a fallback/backoff is needed.

**Not scoped here**: any change to the sector-rotation (Phase 2) or heartbeat-scanner (Phase 3)
cadence — this is scoped only to the holdings 150DMA exit check.

## Explicitly deferred (do not build as part of this handoff)

- Any automatic buy/sell action of any kind — advisor-notes-only, same as
  my-trader/briefs-finance (SOUL.md), regardless of how mechanical the framework's own
  rules sound
- A true portfolio-of-sector-ETFs product (the notes describe *buying the sector
  index fund itself* as the actual investment vehicle, not just using sector rotation
  to pick individual stocks within it) — worth explicitly asking Shaun during planning
  whether Phase 2's output is meant to inform "buy XLK itself" as a real candidate
  action, or purely as a filter for Phase 3's stock scan. The conversation that
  produced this handoff leaned toward the latter but never explicitly confirmed it.

## Validation (once built)

```powershell
# Add goat to the workspace first
# investments/pyproject.toml: members = ["briefs-finance", "my-trader", "goat"]

uv sync --directory investments/goat --extra dev
uv run --directory investments/goat python -m pytest -q

# Exact CLI shape TBD during implementation
uv run --directory investments/goat python -m goat.main monitor
uv run --directory investments/goat python -m goat.main scan
```

## Open Questions for Shaun

**Resolved 2026-08-11** (answers captured inline above where relevant):

1. ~~Reuse strategy~~ → (a) workspace dependency on my-trader.
2. ~~Phase 3's candidate universe~~ → (c) scrape S&P 500 constituents (e.g. Wikipedia),
   tagged by GICS sector.
3. ~~Does Phase 2 ever become a standalone buy candidate?~~ → Yes, both: individual
   stocks (Phase 3) AND the sector ETF itself when it's showing strength (Phase 2
   needs its own opportunity-style signal, not just a filter).
4. ~~Cadence for Phase 3~~ → weekly scheduled scan + on-demand trigger (Monitor/Find
   split, same as my-trader).
5. ~~Where does Goat's data live?~~ → new tables inside the existing
   `investments/briefs-finance/data/investments.db` (not a separate DB file), chosen
   to keep the option of combining/joining with my-trader's data later.

**Still open — needs real research/backtesting during `/plan-feature`, not a snap
preference call:**

1. **"Heartbeat" consolidation threshold** — genuinely unresearched. Needs either
   real backtesting against historical 10x-mover examples (as the notes themselves
   cite, informally) or at minimum a documented, sourced definition before shipping a
   number, same discipline `opportunity.py`'s thresholds went through in my-trader
   after being called out for inventing numbers the first time.
2. **150DMA "reasonably below" threshold for the holdings exit check** — needs a
   specific % and/or consecutive-days rule, not left as "reasonably" in the shipped
   code.
3. **Sector-ranking window length** (Phase 2) — 3-month starting guess, not confirmed.
