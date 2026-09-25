# LSE Heartbeat Universe — Handoff

## Status: PLANNED 2026-09-21 — see `.agent/plans/lse-heartbeat-universe.md` for the full implementation plan. All open questions below resolved (Q2: option (a), ICB→SPDR mapping). Awaiting `/execute`.

## Trigger

Shaun spotted a genuine heartbeat pattern on **Braemar Plc (`BMS.L`, London Stock
Exchange)** on his own charting platform and asked why Goat's heartbeat scan never
found it. Confirmed live 2026-09-21: `check_heartbeat_breakout` fires `"interesting"`
on `BMS.L`'s real price history — 13.6% range, 100% smoothness, 27 confirmed swings,
no breakdown. The pattern-detection logic is not the problem. The heartbeat scan's
universe (`sp500_universe.py`) is S&P 500 constituents only, scraped from Wikipedia
— an LSE stock was never going to be in the ~213 tickers scanned regardless of how
good its chart looked.

This is a distinct gap from the ASX + ETF addendum already logged in
`investments/goat/industry-pipeline-handoff.md` (2026-09-20) — that one covers ASX
and curated ETFs; neither it nor anything else in this codebase touches the London
Stock Exchange.

## The Goal In One Line

Let a London Stock Exchange-listed stock actually be scanned (and, if it clears the
gates, staged as a candidate) by Goat's heartbeat scan — today it's entirely outside
the universe, unconditionally.

## Reusable Infrastructure Already In the Workspace

- **`mytrader/asx200_universe.py`** — the closest direct precedent, and the shape to
  mirror almost exactly. Wikipedia-scrapes a `class="wikitable"` constituent table
  (requests + BeautifulSoup, headers dict, timeout, try/except-returns-None-on-any-
  failure), returns `{"ticker", "company", "sector"}` rows, bare code (exchange suffix
  added by the caller). No DB cache — re-scrapes every run.
- **Wikipedia's FTSE 100 page has an equivalent table** — live-verified 2026-09-21:
  `en.wikipedia.org/wiki/FTSE_100_Index` has one `class="wikitable"` with columns
  **Company / Ticker / FTSE industry classification benchmark sector**, ~100 data
  rows. Same shape as the ASX 200 page (`Code / Company / Sector / ...`) `asx200_universe.py`
  already parses — same header-matching approach should work with a new set of
  `_CODE_HEADERS`/`_COMPANY_HEADERS`/`_SECTOR_HEADERS` candidates for "ticker" and
  "ftse industry classification benchmark sector" (needs live confirmation of the
  exact header text during build — Wikipedia table headers drift).
- **`mytrader/tickers.py`** — `normalize()` + `asx_variant()` is the pattern to extend:
  add `lse_variant(ticker) -> f"{normalize(ticker)}.L"` (yfinance's LSE suffix,
  confirmed live via `BMS.L`).
- **`goat/sp500_universe.py`** — the cache-in-DB-with-TTL pattern, if an FTSE cache
  table ends up worth it (see Open Question 5 below; `asx200_universe.py`
  deliberately skips caching, a real alternative to just copying).
- **`goat/heartbeat.py`'s `check_heartbeat_breakout`** — ticker-agnostic
  `(ticker, sector_label, close_series)`, confirmed working unmodified on `BMS.L`.
  No changes needed to the check itself.
- **`fundamentals_context.compute_survival_context`** — already currency-naive (reads
  ratios/percentages off `.info`, not absolute price levels), should work unmodified
  for a GBp-denominated ticker. Not separately confirmed live against `BMS.L` — worth
  a quick check during build.

## Real Gotchas Found During Investigation (2026-09-21)

1. **Currency: yfinance reports many LSE stocks in pence (`GBp`), not pounds (`GBP`)**
   — confirmed live: `BMS.L`'s `.info["currency"]` is `"GBp"`, and its close prices
   are literally in the 200s (pence), not the low single-digit pounds you'd read off
   a UK financial site quoting £2.30. This is a 100x unit trap for anything comparing
   against an absolute price/market-cap/AUM threshold (e.g. the DMA breakout scan's
   `GOAT_DMA_BREAKOUT_MIN_MARKET_CAP_AUD`-style floors, or `ETF_AUM_FLAG_USD`) — NOT
   a problem for `check_heartbeat_breakout` itself, since every one of its gates is a
   ratio/percentage of the base's own mean, immune to the unit the numbers happen to
   be in. Still needs an explicit note/guard wherever an absolute-value threshold
   might get compared against an LSE ticker later (liquidity floor, see Open Question
   4).
2. **Ethical filter (`scripts/ethical_filter.py`) is US-ticker-curated** —
   `DEFENSE_TICKERS`/`DEFENSE_REVIEW_TICKERS` are hand-maintained lists of US defense
   contractor tickers. It already strips an exchange suffix (`ticker.split(".")[0]`)
   before matching, but the lists themselves have no UK names in them — a genuine UK
   defense contractor (e.g. BAE Systems, `BA.L`) would silently pass through
   unflagged. Either accept that gap for v1 (flag it, don't block on it) or add a
   small curated UK defense-ticker list alongside the existing US one.
3. **Liquidity is thin by US/ASX standards** — `BMS.L` itself averages only ~37,000
   shares/day (mcap ~£73.6M). Whatever liquidity floor gets set (Open Question 4)
   needs to be calibrated for LSE norms, not reused verbatim from
   `GOAT_DMA_BREAKOUT_MIN_AVG_VOLUME`'s US-calibrated 100,000 shares/day.

## Open Questions (resolve during `/plan-feature`)

1. **Breadth — FTSE 100 or FTSE 350?** FTSE 100 (large-cap) is the direct ASX-200
   analog and has a confirmed-clean Wikipedia source. FTSE 350 (100 + FTSE 250
   mid-caps) roughly doubles/triples coverage but its own Wikipedia constituent-list
   page hasn't been checked yet — Braemar itself, at ~£73.6M market cap, is small
   enough it may not even be in the FTSE 350's lower band; worth checking whether it's
   FTSE SmallCap/AIM-listed instead, which would mean even FTSE 350 wouldn't have
   caught this specific example. **Recommend starting with FTSE 100 for v1** (smaller,
   more liquid, cleanest source) and treating "should Braemar-sized names actually be
   in scope" as a deliberate, separate breadth decision rather than a default.
2. **Sector-gating mismatch.** `heartbeat_scan.py` filters S&P 500 constituents down
   to those in a *currently rising* GICS-mapped SPDR sector before running the
   heartbeat check at all (`GOAT_GICS_TO_ETF_SECTOR_LABEL`). FTSE's own sector
   taxonomy (the "FTSE industry classification benchmark," aka ICB) doesn't map 1:1
   onto the US SPDR-sector labels this codebase already ranks. Options: (a) build an
   ICB→SPDR-label mapping (same class of imprecision this codebase already accepts
   for GICS→SPDR), (b) gate LSE stocks on a UK-specific sector rotation ranking
   instead (a new, separate build — no UK sector ETF ranking exists anywhere in this
   codebase today), or (c) skip the rising-sector gate entirely for the LSE leg and
   scan all FTSE constituents unconditionally (simplest, but loses the "only look
   inside sectors that are actually working" filter the US scan relies on to bound
   scan cost and noise). **No default recommendation — this is the crux design
   decision**, unlike the ASX addendum where GICS sector data was already sitting in
   `asx200_universe`'s own scrape.
3. **Constituent caching.** Mirror `asx200_universe.py`'s no-cache-just-rescrape
   approach (simplest, consistent with the newest precedent), or `sp500_universe.py`'s
   DB-cached-with-TTL approach (lower Wikipedia load, matches the scan this is
   actually extending)? Recommend matching `sp500_universe.py` since this feeds
   `heartbeat_scan.py` specifically, not a DB-write-free tool like `cash_value_scan.py`.
4. **Liquidity floor.** Needs an LSE-appropriate minimum average volume (and/or
   market cap) distinct from the US/ASX constants already in `config.py` — concrete
   number not yet chosen; start from Finviz/LSE-community norms rather than reusing
   `GOAT_DMA_BREAKOUT_MIN_AVG_VOLUME` (100,000) verbatim, which may be too strict for
   a genuinely thinner market or too loose given LSE's overall lower average volumes
   across the board. Needs real data during build, not a guess here.
5. **Currency guard.** Decide whether to store/display GBp prices as-is (with a
   currency label so no one misreads pence as pounds) or normalize to GBP (÷100) at
   ingestion. Recommend storing/reporting the currency explicitly (same posture as
   `market_data`/`fundamentals_context` already take toward non-USD tickers
   elsewhere) rather than a silent conversion that could itself introduce a bug.
6. **Notification/report integration.** Does an LSE hit land in the existing
   `heartbeat-candidates-pending-review.md` (one combined report, `market` or
   `exchange` column added the way `dma_breakout_scan.py` already tags `market="ASX"`
   rows), or a separate `lse-heartbeat-candidates-pending-review.md`? Recommend the
   combined-report approach `dma_breakout_scan.py` already established, for
   consistency.
7. **Promote-candidate / watchlist integration.** `watchlist-add` and friends are
   already currency/exchange-agnostic (a `.L` ticker is just another string) — confirm
   `my-trader`'s checks (valuation, dividend trend, etc.) don't assume USD/AUD
   anywhere before promoting a real LSE candidate into the watchlist for the first
   time.

## Suggested Shape (pending the open questions above)

- New `mytrader/tickers.py::lse_variant()` (or a `goat`-local equivalent if this stays
  scoped to the heartbeat scan only — confirm placement during planning, mirroring
  why `asx_variant` lives in `mytrader/tickers.py` even though ASX support started in
  `goat`).
- New `ftse100_universe.py` (location TBD per placement question above) mirroring
  `asx200_universe.py`'s scraper, targeting the FTSE 100 Wikipedia page's confirmed
  wikitable.
- `heartbeat_scan.py` (or a small LSE-specific orchestrator, matching this
  codebase's established preference for a second copy over a shared/parameterized
  function — see `heartbeat.py`'s own docstring on that convention) gains an LSE leg:
  fetch constituents, apply Open Question 2's sector-gating decision, apply the
  ethical filter (accepting Gotcha 2's known gap or closing it), apply the liquidity
  floor from Open Question 4, run `check_heartbeat_breakout` unmodified, attach
  `compute_survival_context`, three-way dedup, stage into `goat_pending_candidates`
  with a distinguishing `source` (e.g. `"goat_heartbeat_scan_lse"`) and a `market`
  tag on the row (mirroring `dma_breakout_scan.py`'s existing `market="ASX"` /
  `market="US"` convention).
- Report rendering: extend `render_heartbeat_candidates_report` with a market/exchange
  column per Open Question 6, or add a parallel render function if the report stays
  separate.

## Explicitly NOT Scoped Here

- No FTSE sector-rotation ranking build (Open Question 2's option (b), if chosen,
  would need its own separate handoff/plan — this document assumes (a) or (c) unless
  redirected).
- No currency conversion/normalization across the portfolio-wide checks in `my-trader`
  (concentration, market-value aggregation) — those are already documented as
  currency-naive for USD/AUD; adding GBp is the same class of known limitation, not a
  new one to solve here.
- No other non-US, non-ASX exchange (this is LSE-specific; a similar gap likely
  exists for any other market Shaun happens to chart on his own platform, but each
  would need its own Wikipedia-source verification and gotcha investigation the way
  this document did for LSE).

## Validation (once built)

```powershell
uv run --directory investments/goat python -m pytest -q

# On the VPS via invoke_investments.ps1 — never run locally against the real DB:
.\scripts\invoke_investments.ps1 -Package goat -Command "scan-heartbeat"

# Sanity-check the pattern still holds against a currently-known-good example:
# BMS.L should appear as a candidate (or be explained why not, e.g. liquidity floor)
```
