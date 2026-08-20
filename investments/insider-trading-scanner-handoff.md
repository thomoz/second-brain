# Insider Trading Scanner (OpenInsider) — Session Handoff

## Status: COMPLETE — built 2026-08-17/18 per `.agent/plans/insider-trading-scanner.md` (`investments/goat/goat/insider_scan.py`). Kept in place (not archived) as the source design doc — cited directly by `investments/goat/goat/config.py` and `investments/goat/insider-pattern-analysis-handoff.md`.

## What This Is

Two related scans against OpenInsider.com's aggregated SEC Form 4 data (insiders —
officers/directors/10%+ owners — buying or selling their own company's stock),
per Shaun's 2026-08-17 request:

1. **Holdings watch** — for every ticker Shaun currently holds, check for recent
   insider buys or sells. A sell might be a warning worth Shaun's attention; a
   buy might be a signal worth adding to the position. This is a check against
   an existing list (his holdings), same shape as Goat's 150DMA exit check.
2. **Discovery scan** — market-wide daily scan for considerable insider
   *purchases* only (not sales) as potential new buy candidates — Shaun did not
   ask for a market-wide sell scan, only a market-wide buy-discovery scan. This
   is new-candidate discovery, same shape as Goat's sector-rotation and
   heartbeat scans.

Both are advisor-notes-only — no auto-buy/sell, no auto-watchlist-add. Discovery
candidates land in a pending-review staging area for explicit
promote/dismiss, same precedent as every other Goat candidate source.

## Context — OpenInsider's actual structure (confirmed live 2026-08-17)

Fetched `http://openinsider.com/latest-insider-trading` directly and confirmed:

- **It's a plain server-rendered HTML table, no JavaScript rendering needed** —
  fits the same `requests` + `BeautifulSoup` direct-fetch style already used for
  `sp500_universe.py` (Wikipedia) and `asx_announcements.py`. No new dependency.
- **Pre-built, pre-thresholded pages already exist** — no need to invent a
  "considerable" dollar cutoff:
  - `/latest-insider-purchases-25k` — insider purchases $25k+
  - `/latest-officer-purchases-25k`, `/latest-ceo-cfo-purchases-25k` — narrower
  - `/top-insider-purchases-of-the-day` (also `-week`/`-month`)
  - `/latest-insider-sales-100k` — insider sales $100k+
  - `/top-insider-sales-of-the-day` (also `-week`/`-month`)
- **A GET-parameterized screener exists for arbitrary ticker lists**:
  `/screener?s=TICKER1,TICKER2,...` (`s` = comma-separated symbols/CIKs), plus
  `o` (insider name/CIK), `td`/`tdr` (trade date / trade date range), `fd`/`fdr`
  (filing date / range), `vl`/`vh` (min/max trade value). This is the endpoint
  the holdings-watch scan would use — feed it Shaun's current holdings tickers
  plus a recent trade-date range, no CIK lookup step needed (unlike
  `sec_filings.py`, which needs a bulk ticker→CIK map for SEC EDGAR directly —
  OpenInsider takes tickers as-is).
- **Table columns confirmed**: Filing Date, Trade Date, Ticker, Company Name,
  Insider Name, Title, Trade Type (`P - Purchase`, `S - Sale`, and others — see
  Open Questions), Price, Qty, Owned, ΔOwn (%), Value, plus 1d/1w/1m/6m
  post-trade price-change columns (not needed for v1).

## Open Questions (resolve during /plan-feature)

1. **Package placement** — extend Goat (its pending-candidate staging +
   advisor-notes infrastructure is an exact fit for the discovery scan, and it
   already has precedent for read-only cross-package access to my-trader's
   `holdings` table for the 150DMA exit check) vs. a new check module in
   my-trader (fits the "per-ticker signal" framing better for the holdings-watch
   half, but my-trader has no discovery-scan/staging precedent — that's
   entirely a Goat pattern). Recommendation: Goat, mirroring the heartbeat
   scanner's shape for the discovery half and the 150DMA exit check's shape for
   the holdings-watch half — but worth confirming, not assumed.
2. **Form 4 transaction-type filtering** — Form 4 codes cover more than open-
   market buys/sells: `A` (grant/award), `M` (option exercise), `G` (gift), `F`
   (tax-withholding sale), etc. These don't reflect the same "conviction" signal
   as a genuine open-market `P`/`S` trade (an exec's tax-withholding sale on
   vesting RSUs isn't a bearish signal the way an unprompted market sale is).
   Needs a decision on which Trade Type codes count, sourced from OpenInsider's
   own documentation of its codes, not guessed.
3. **Dollar thresholds** — are OpenInsider's own $25k (purchases) / $100k
   (sales) cutoffs the right "considerable" bar for Shaun, or does he want
   something higher/different per bucket (e.g., a $25k purchase in a mega-cap
   is noise; the same in a small-cap is a real signal)?
4. **Cadence** — "daily" per Shaun's request, but what time, and does it need
   to be timezone-aware (`Australia/Sydney`) like the heartbeat scan's Saturday
   run, given Form 4s must be filed within 2 US business days of the trade (so
   "today's filings" often reflects trades from a day or two prior, not
   same-day)?
5. **Sector filter or not** — should discovery-scan candidates be filtered to
   currently-rising sectors (matching the heartbeat scanner's philosophy,
   reusing `sector_rotation.rank_sectors`), or is insider buying meant to be an
   independent signal that ignores sector rotation entirely? Genuinely unclear
   from the conversation that prompted this — worth asking directly.
6. **Notification shape** — does a holdings-watch hit (sell or buy on something
   Shaun owns) fire a WhatsApp alert immediately, same as a 150DMA breach? Does
   a discovery-scan hit get folded into the existing `maybe_notify` ticker+
   detail format (per the 2026-08-17 fix), or does it need its own message
   shape given it's a different kind of signal (insider conviction, not a
   technical pattern)?
7. **Staging table** — reuse `goat_pending_candidates` with a new `source`
   value (e.g. `goat_insider_discovery`), or a dedicated new table? The existing
   table's schema (`ticker`, `sector_label`, `signal_detail`, `source`,
   `flagged_at`) is generic enough to reuse as-is (same reasoning the heartbeat
   scanner used), but `sector_label` would need a placeholder/derived value for
   a signal that isn't inherently sector-scoped.
8. **Scrape etiquette** — OpenInsider is a small, free, community-run site (not
   a government source like SEC EDGAR, which has documented rate-limit/User-
   Agent rules). Needs a real User-Agent string, conservative request cadence
   (a handful of page fetches per daily run, not per-ticker fetches for a large
   holdings list), and the same stale-cache-fallback-on-scrape-failure pattern
   `sp500_universe.py` already uses, since there's no SLA here either.

## Explicitly deferred (do not build as part of this handoff)

- Real-time/same-day Form 4 alerting — would require polling SEC EDGAR's own
  filing feed directly rather than OpenInsider's aggregation, which has its own
  lag on top of Form 4's 2-day filing window. Out of scope unless OpenInsider's
  daily cadence proves too slow in practice.
- Any kind of "insider conviction score" or ranking beyond a plain alert/stage
  — no scoring model, just surface the raw filing with context, same
  advisor-notes philosophy as everywhere else.
- A direct SEC EDGAR Form 4 XML fallback path if OpenInsider ever becomes
  unreliable — worth knowing it exists as an option, not worth building
  speculatively now.

## Validation (once built)

```powershell
uv run --directory investments/goat python -m pytest -q

# Exact CLI shape TBD during implementation
uv run --directory investments/goat python -m goat.main scan-insiders
```

## Sources consulted (2026-08-17)

- `http://openinsider.com/latest-insider-trading` — live fetch, confirmed table
  columns, nav links to pre-thresholded pages, and the `/screener` GET
  parameter names listed above.
