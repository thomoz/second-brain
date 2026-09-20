# DMA Breakout Scan — Add an ETF Universe — Session Handoff

Tool: extends the existing **DMA Breakout Scanner**
(`investments/goat/goat/dma_breakout_scan.py`, built from
`investments/dma-breakout-scanner-handoff.md`). Proposed home: same module, same
package — no new file, no new uv-workspace member. This adds a third universe
(alongside the existing S&P 500 + ASX 200 stock universes) and a small number of
ETF-aware branches in the existing staging pipeline.

## Status: NOT BUILT — drafted 2026-09-17 from Shaun's question ("can we add ETFs to
the DMA breakout scan?" — answer was: currently no, it's stock-only by design, but the
underlying MA-cross logic is already ticker-agnostic). Awaiting Shaun's manual
`/plan-feature` run against this doc before any implementation.

## What This Is

Today, `dma_breakout_scan.py`'s discovery universe (`fetch_universe_constituents`) is
built entirely from two **stock**-index constituent lists — S&P 500 (Wikipedia,
`sp500_universe.py`) and ASX 200 (Wikipedia, `mytrader/asx200_universe.py`). Neither
list contains ETFs (they're both company/security index membership tables, not fund
lists), so a fresh 150DMA/200DMA breakout on an ETF is currently **invisible** to this
scanner — it would only ever get caught by `mytrader Monitor`'s exit check, and only
for the *downside* cross, and only if Shaun already holds/watchlists that specific ETF
(confirmed live 2026-09-17 against real `holdings.md`: Shaun already holds 6 ETFs/
commodity trusts — `ETPMAG.AX`, `GOLD.AX`, `GXLD.AX`, `PMGOLD.AX`, `URNM.AX`, `OOO.AX`
— none of which the DMA Breakout Scan's discovery step would ever have surfaced as new
finds in the first place).

The scan's actual signal logic (`check_ma_cross`) operates purely on a `pandas.Series`
of close prices — it has zero stock-specific assumptions and already works
identically for any ticker. **The gap is entirely in the universe source and two
downstream steps that assume an operating company, not the signal itself.**

## What already works for free, and what needs a real fix (confirmed live 2026-09-17)

Checked real `yfinance` `.info` for `SPY`, `GLD`, `ITA` (Aerospace & Defense industry
ETF), and `PMGOLD.AX` (Shaun's own ASX gold ETF holding) before writing this, rather
than guessing:

| Field | SPY | GLD | ITA | PMGOLD.AX |
|---|---|---|---|---|
| `quoteType` | ETF | ETF | ETF | ETF |
| `marketCap` | `None` | `None` | `None` | `None` |
| `averageVolume` | 46,009,008 | 9,110,950 | 675,148 | 227,591 |
| `totalAssets` | $811.9B | $152.9B | $13.6B | $2.2B |
| `debtToEquity` | `None` | `None` | `None` | `None` |
| `freeCashflow` | `None` | `None` | `None` | `None` |

**Already works, no change needed:**
- `check_ma_cross` — purely price-history-based, works identically for an ETF.
- `fundamentals_context.compute_survival_context` — already fully `None`-safe (its own
  module docstring: "a totally empty `.info` still returns a dict with
  `insolvency_risk=False`"). Confirmed live: an ETF's `debtToEquity`/`freeCashflow` are
  both `None`, so `insolvency_risk` correctly stays `False` and nothing crashes — it'll
  just render a slightly odd-looking "debt/equity unavailable, cash flow unavailable...
  not currently cash-generating" summary line for a fund, which is harmless but worth
  a cosmetic follow-up (see Open Questions).
- `scripts.ethical_filter.check_ticker` — a pure ticker-string lookup against
  `DEFENSE_TICKERS`/`DEFENSE_REVIEW_TICKERS` (individual company tickers like LMT/RTX),
  works fine unmodified on an ETF ticker string. **Real gap, not a crash risk**: a
  sector ETF whose whole *theme* is defense (e.g. `ITA`, already in
  `GOAT_INDUSTRY_ETFS` as "Aerospace & Defense") is not itself in `DEFENSE_TICKERS`, so
  it passes through as fully allowed even though it's effectively a defense-sector bet
  — see Open Questions.
- `data.info.get("fullExchangeName")`/`("exchange")` for the report's Exchange column
  — populates for ETFs the same as stocks, no change needed.

**Real, confirmed-live bug that must be fixed, not just "worth checking":**
`passes_liquidity_floor` (`dma_breakout_scan.py` lines 154-170) gates on
`info.get("marketCap")`, which is **`None` for every ETF tested above, unconditionally**
— `yfinance` reports fund size via `totalAssets` (AUM) instead, exactly the field
`etf_mechanics.py`'s own `ETF_AUM_FLAG_USD` check already uses for this. As written
today, adding an ETF universe would have every single ETF candidate silently die at
the liquidity-floor check regardless of how real its breakout is — this needs an
ETF-specific branch (`totalAssets` vs. an AUM floor) alongside the existing
market-cap branch, not a tweak to the existing thresholds.

## Universe source — no free "ETF index" table exists, use a curated list instead

Unlike S&P 500/ASX 200, there's no equivalent free, scrape-able "the ETF index"
Wikipedia table — ETFs aren't index constituents of anything analogous. Two curated
sources already exist **in this exact codebase** and cost zero new scraping:

1. **`GOAT_INDUSTRY_ETFS`** (`goat/config.py`, 39 tickers, e.g. `SMH`→Semiconductors,
   `GDX`→Gold, `XBI`→Biotechnology) — already lives inside the `goat` package itself
   (no cross-package import needed, unlike the Earnings Deterioration Watch plan's
   own use of this same dict, which *does* need a migration since it lives in
   `mytrader`, a different package — not a concern here since `dma_breakout_scan.py`
   already imports `from . import config` and can read `config.GOAT_INDUSTRY_ETFS`
   directly).
2. **A short new curated list**, mirroring the AI-Resistant Moat Scanner's
   `MOAT_SEED_TICKERS` precedent (a hand-picked anchor list, re-scored every run
   regardless of any broader screen) — for broad-market and commodity ETFs Shaun
   actually holds or would plausibly want a breakout alert on (`SPY`/`QQQ`/`IWM`-style
   broad market, `GLD`/`SLV`/`PMGOLD.AX`/`URNM.AX`-style commodities), since the
   39-name industry list is deliberately sector-narrow and doesn't cover these at all.

Recommend combining both into one new `GOAT_DMA_BREAKOUT_ETF_UNIVERSE` (or similar)
config list/dict, added as a third bucket in `fetch_universe_constituents` (alongside
the existing `"US"`/`"ASX"` `market` values — a new `"ETF"` market label), so the
existing dedup/liquidity/staging loop in `run_dma_breakout_scan` handles it via one
more branch, not a parallel pipeline.

## Open Questions (resolve during `/plan-feature`)

1. **ETF AUM floor value.** `etf_mechanics.py` already has `ETF_AUM_FLAG_USD` ($50M) —
   reuse that constant directly for the new liquidity-floor branch, or pick a
   DMA-Breakout-specific (likely higher) floor the way
   `GOAT_DMA_BREAKOUT_MIN_MARKET_CAP_USD` ($300M) is deliberately higher than a bare
   "not delisting-risk" bar? Recommend reusing `ETF_AUM_FLAG_USD` as the floor for
   consistency across the codebase's two ETF-quality gates, unless Shaun wants this
   scan pickier.
2. **Defense-sector ETF exposure.** Should an industry ETF whose `GOAT_INDUSTRY_ETFS`
   label is itself defense-adjacent (`ITA` = "Aerospace & Defense") get the same
   `REVIEW:`/exclude treatment as an individual defense contractor stock? The current
   ethical filter has no concept of a themed fund at all. Recommend: a small label-based
   check (`if label == "Aerospace & Defense": review_reason = "REVIEW: defense-themed ETF"`)
   rather than extending `ethical_filter.check_ticker` itself, which is stock-ticker-only
   by design and shared with every other tool in the workspace.
3. **Company-name column for a curated ETF, not scraped from Wikipedia.** The stock
   universes get `company`/`security` name from their Wikipedia scrape; the curated
   ETF list has no such source. Recommend sourcing it from `data.info.get("longName")`
   at staging time (already fetched via `market_data.fetch_ticker_data` for the
   liquidity check anyway — no new fetch needed) rather than hand-maintaining names in
   config alongside the ticker list.
4. **`fundamentals_context`'s cosmetic ETF wording.** Worth a one-line change
   ("not applicable — fund" instead of "debt/equity unavailable, cash flow
   unavailable... not currently cash-generating") when `data.info.get("quoteType") ==
   "ETF"`, or leave as-is since it's harmless and already correctly non-gating?
   Low-priority, cosmetic only.
5. **Should this also extend to Goat Heartbeat Scan?** Shaun's original question was
   specifically about DMA Breakout Scan. Heartbeat Scan's compound tight-base pattern
   is arguably less meaningful for a diversified fund than a plain MA cross is — explicitly
   out of scope for this handoff; revisit separately if wanted (see Explicitly Deferred).

## Explicitly deferred (do not build as part of this handoff)

- **Goat Heartbeat Scan ETF support** — a separate tool with a materially different
  (compound, pattern-based) signal; out of scope, see Open Question #5.
- **A broader/scraped ETF universe** (e.g. every US-listed ETF above some AUM floor,
  Finviz-style) — the curated-list approach above is deliberately smaller and
  zero-new-scraping; revisit only if the curated list proves too narrow in practice.
- **Extending `ethical_filter.check_ticker` itself** to understand themed funds — kept
  local to this scan (Open Question #2) since that function is shared workspace-wide
  and stock-ticker-only by design.

## Reference code to reuse (read all of these during `/plan-feature`)

- **`goat/dma_breakout_scan.py`** — the whole file. `fetch_universe_constituents`
  (lines 57-86) is where the new `"ETF"` market bucket gets added;
  `passes_liquidity_floor` (lines 154-170) is where the `totalAssets`-vs-AUM branch
  goes; `run_dma_breakout_scan` (lines 173-240) is the existing loop the new bucket
  slots into unmodified otherwise.
- **`goat/config.py`** — `GOAT_INDUSTRY_ETFS` (lines ~150-186, 39-name dict) and
  `GOAT_DMA_BREAKOUT_MIN_MARKET_CAP_USD`/`_AUD`/`MIN_AVG_VOLUME` (lines ~492-502, the
  existing stock liquidity floors to sit the new AUM floor alongside).
  `DEFENSE_TICKERS`/`DEFENSE_REVIEW_TICKERS` for Open Question #2.
- **`mytrader/config.py`**'s `ETF_AUM_FLAG_USD`/`ETF_AUM_HEALTHY_USD` — the existing
  AUM-floor precedent and its sourced reasoning (Open Question #1).
- **`mytrader/checks/etf_mechanics.py`** — the existing `quoteType == "ETF"` detection
  idiom (line 77) and its `totalAssets`-based AUM check (lines 95-100) — the exact
  pattern to mirror for `passes_liquidity_floor`'s new branch.
- **`goat/fundamentals_context.py`** — already-confirmed `None`-safe behavior for ETF
  `.info` (Open Question #4 is the only possible touch point here).
- **`ai_resistant_moat_scanner/config.py`**'s `MOAT_SEED_TICKERS` — the curated
  anchor-list precedent to mirror for the new broad-market/commodity ETF list.
- **`investments/dma-breakout-scanner-handoff.md`** — the original build handoff, for
  the tool's overall design intent and how it deliberately differs from Heartbeat
  Scan / Monitor's exit check (relevant to Open Question #5).

## Validation (once built)

```powershell
.\scripts\invoke_investments.ps1 -Package goat -Command "scan-dma-breakout"
```

Expected: `investments/goat/dma-breakout-candidates-pending-review.md` can now include
ETF rows (e.g. an industry ETF or a broad-market/commodity ETF that just crossed above
its 150/200DMA), each passing the new AUM-based liquidity floor instead of failing
silently on a missing `marketCap`. Test with real tickers confirmed live in this
handoff (`SPY`, `GLD`, `ITA`, `PMGOLD.AX`) plus a deliberately tiny/illiquid ETF to
confirm the AUM floor actually rejects it.

## Sources consulted (2026-09-17)

- `investments/goat/goat/dma_breakout_scan.py`, `fundamentals_context.py`, `config.py`
- `investments/briefs-finance/scripts/ethical_filter.py`
- `investments/my-trader/mytrader/checks/etf_mechanics.py`, `config.py`
  (`ETF_AUM_FLAG_USD`/`ETF_AUM_HEALTHY_USD`)
- Live `yfinance` (1.5.1) `.info` fetch against `SPY`/`GLD`/`ITA`/`PMGOLD.AX`
- `investments/my-trader/holdings.md` (real current ETF holdings)
- `investments/dma-breakout-scanner-handoff.md` (original tool handoff)
