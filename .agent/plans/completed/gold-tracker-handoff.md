# Handoff: Daily Gold Tracking Tool (Macro Factors + Backtested Signals)

## Status: Not started — design agreed 2026-08-07, open questions resolved 2026-08-07, ready for /plan-feature (Phase 1 only)

## Decisions (resolved 2026-08-07 — supersedes "Open Questions" below)

1. **Price series: both.** Track GC=F (USD futures) for the macro-driver analysis
   (real yields, DXY correlate with USD gold) AND PMGOLD's own AUD price for
   "what this means for the actual position." Bridge via the existing
   `fetch_fx_change_pct` AUD/USD in `market_data.py`.
2. **Cadence: Monitor automatic daily**, same as every other macro check (MOVE,
   CPI, credit spreads, etc.) — matches the original "daily tracking" ask.
3. **Plan scope: Phase 1 indicators only.** The backtest module is a separate
   follow-up plan, built after Phase 1 indicators are live and producing real
   data — per the handoff's own "build first / build second, after" sequencing.
   Do not scope the backtest module into the Phase 1 plan-feature pass.
4. **Alert thresholds + backtest validation-split date: ship with documented
   defaults, revisit after first live report.** Same discipline as
   `ETF_AUM_FLAG_USD` elsewhere in `config.py` — each constant gets a sourced
   comment, ships as a best guess, gets tuned against what the first few real
   `monitor-report.md` runs actually show. Do not block Phase 1 on nailing down
   exact numbers now. (The validation-split date specifically is moot for this
   pass since backtest is out of scope — resolve it when that follow-up plan is
   written.)
5. **USD Dollar Index source (resolved during scoping, not a user preference
   call): FRED `DTWEXBGS`**, not yfinance `DX-Y.NYB`. Keeps the FRED-first
   pattern every other macro check already uses (single API, graceful
   `"unknown"` degradation already wired) and is broad trade-weighted rather
   than a narrow single-contract futures index.

## Context

Shaun holds gold (PMGOLD — Perth Mint Gold Structured Product, ASX-listed, bucket 3a
in `investments/my-trader/holdings.md` — currently ~69 units, AUD-denominated) and
recently added to the position (mentioned "$4000 in gold"). He wants a daily tracking
tool for gold that goes beyond just price — factoring in the macro drivers that
actually move gold (real yields, USD strength, etc.) and eventually validated
technical signals (moving averages), reusing my-trader's existing Monitor
infrastructure rather than building a standalone tool.

**Because PMGOLD is the actual holding**: any gold price series used should be
considered alongside AUD/USD FX (already have `fetch_fx_change_pct` in
`market_data.py`) — a move in USD gold price doesn't map 1:1 onto Shaun's AUD-
denominated PMGOLD return. Worth deciding explicitly whether to track USD spot/futures
gold, PMGOLD's own AUD price, or both (see Open Questions).

### Design agreed in conversation — read before implementing

**Architecture**: extend `mytrader/macro_indicators.py`'s existing pattern (the
MOVE index / housing P2I / consumer sentiment / recession probability / inflation
expectations / credit spreads / US+UK+AU CPI checks already there) rather than a new
standalone module. Reuses:
- The FRED-key infra already wired up (`FRED_API_KEY`, graceful `"unknown"`
  degradation when unset — same pattern every existing macro check uses)
- The `macro_snapshot_cache` / `alert_history` MACRO-sentinel dedup mechanism
  (ticker/source_table = `"MACRO"`/`"macro"`) already used by every macro check
- `monitor-report.md`'s existing "Macro Indicators" section (shown every run
  regardless of flag status, per existing convention)

**Output**: both a daily report section (new rows in the existing "Macro Indicators"
table) AND alerts on material moves (reusing the existing dedup mechanism — first
flag creates an alert, repeats stay quiet, clearing auto-acknowledges).

**Critical design constraint on the moving-average / technical signal specifically**
(this came out of real discussion, don't skip it): a 200-day-MA cross is
**contested, not settled** — standard trend-following convention treats a break below
the 200DMA as bearish, while gold specifically has a documented (but small-sample)
history of behaving as a contrarian buy signal instead. **Do NOT hard-code
"price < 200DMA => buy" as a flag/opportunity signal.** Report the cross event as
neutral **info** (same "report, don't judge" philosophy as `price_action.py` /
`crash_resilience.py`), with historical base-rate context in the detail text from the
backtest module (see below). Any "this looks like an opportunity" framing should be
**gated** on the other Phase 1 macro checks (real yields, DXY) not showing
deterioration — same risk-first gating pattern `opportunity.py` already uses for the
Marks/Neilson dip signal ("a decline is only a signal when nothing else is actively
wrong").

Confirmed live 2026-08-07 (GC=F futures, via yfinance): gold crossed below its
200-day MA on 2026-06-05 at $4,337; currently (as of that date) $4,323 vs. a 200DMA
of $4,479 (-3.5%), no cross back since. The 200DMA itself is elevated from a prior
rally (crossed *above* the 200DMA 2025-05-22 at $3,292 — roughly +30% over the
trailing year), so this reads as a pullback within an uptrend rather than a broken
downtrend on the numbers available — but this observation itself needs the backtest
module to be validated, not taken as given.

## Remaining Steps

### 1. Phase 1 indicators (build first)

All daily-cadence, all reuse existing FRED/yfinance infra — no new external
dependency needed.

| Metric | Source | Notes |
|---|---|---|
| Real yields (10Y TIPS) | FRED `DFII10` | Single most important gold driver per conversation research — opportunity cost of holding non-yielding gold |
| US Dollar Index | FRED `DTWEXBGS` (broad trade-weighted) or yfinance `DX-Y.NYB` | Gold priced in USD; usually inverse-correlated |
| Gold price + 50d/200d MA + cross detection | yfinance (confirm instrument — see Open Questions) | Same rolling-average technique as needed for crash_windows.py-style history fetches |
| Gold-to-silver ratio | yfinance gold vs silver spot/futures | Simple division of two price feeds |
| VIX (equity vol, complements existing MOVE bond-vol check) | yfinance `^VIX` | Same shape as the existing MOVE check |

Proposed alert thresholds (**best-guess defaults, need Shaun's confirmation before
locking in** — same discipline as `ETF_AUM_FLAG_USD` etc. elsewhere in `config.py`,
not invented arbitrarily but not gospel either):
- Real yields: flag when negative (bullish catalyst) or above ~2% (historically
  pressures gold hard) — two-sided band
- DXY: flag on a large move (e.g. >3% in a month) rather than an absolute level
- Golden/death cross: flag exactly on the cross event itself (discrete, no
  threshold-tuning needed) — **info verdict, not flag/opportunity, per the
  constraint above**
- Gold/silver ratio: flag at historical extremes (commonly cited >80 high, <50 low)
- VIX: flag above ~30 (widely considered crisis-adjacent)

### 2. Backtest module (build second, after Phase 1 indicators exist)

Adapt the existing outcome-window methodology from
`investments/briefs-finance/scripts/backtest.py` (`backtest_recommendation` /
`run_backtest`) — that module computes forward returns at 3m/6m/12m from a
recommendation date and compares to an S&P 500 benchmark. Generalize the same shape
for gold **signal** dates instead of recommendation dates:

- Given a signal definition (e.g. "gold crosses below its 200DMA", "real yield goes
  negative", "gold/silver ratio > 80"), find every historical occurrence in the
  available price history.
- Compute forward gold returns at multiple horizons from each occurrence (probably
  longer than the stock-backtest's 3m/6m/12m given gold's cited multi-year cycles —
  consider adding 24m).
- **Compare against an unconditional baseline** — the average/median forward return
  of gold over any random period of the same length, not just after the signal.
  Without this comparison, "gold went up after the signal" doesn't tell you the
  signal added anything over just holding gold generally.
- Report a **distribution with sample size prominent**, not a single accuracy
  percentage: mean, median, win-rate (% positive), best/worst case, and the raw
  N — signal events like MA crosses are rare (a handful to a few dozen occurrences
  across available history), so sample size must be visible, not buried.

**Train/validation split — mandatory, not optional.** Agreed explicitly in
conversation to avoid curve-fitting (the risk: tuning thresholds against the same
data used to "validate" them produces a rule that looks great historically and fails
going forward). Implementation needs:
- A configurable split date (e.g. a `--validation-start` param or config constant).
- Any threshold tuning/adjustment happens only against data before the split.
- Reported "this signal works" conclusions come only from performance measured on
  the untouched validation window — never from the tuning window.
- See Open Questions for where to actually put the split date.

Frame all of this as **advisor-note historical context**, not a predictive
guarantee — consistent with my-trader's existing philosophy everywhere else (Find/
Monitor never suggest a specific trade action).

### 3. Explicitly deferred (Phase 2 — do not build as part of this handoff)

Discussed and intentionally scoped out for now — different cadence or no clean free
API, would need their own design pass:
- Central bank gold buying (World Gold Council — quarterly, PDF/report-based, closer
  to Briefs Finance's PDF-ingestion pattern than a daily check)
- COT futures positioning (CFTC — weekly, real free public API exists but needs a
  new direct-government-source integration, similar effort to `abs_cpi.py`/`ons_cpi.py`)
- ETF flows (GLD/IAU — needs shares-outstanding delta, not just AUM change, since AUM
  moves with price too; fiddlier than it first looks)
- Geopolitical Risk Index (Caldara-Iacoviello via the Fed — monthly, not a clean live API)

## Validation (once built)

```powershell
# Existing full suite must still pass
uv run --directory investments/my-trader python -m pytest mytrader/tests/ -q

# Manual check once wired into Monitor
uv run --directory investments/my-trader python -m mytrader.main monitor
# confirm new rows appear in investments/my-trader/monitor-report.md under Macro Indicators

# Backtest module, once built — exact CLI shape TBD during implementation
uv run --directory investments/my-trader python -m mytrader.scripts.gold_backtest --signal golden_cross_200dma --validation-start 2019-01-01
```

## Open Questions for Shaun (resolve before/while implementing)

1. **Which gold price series should be "the" tracked instrument** — USD gold
   futures/spot (GC=F, matches the exploratory numbers already pulled in
   conversation), or PMGOLD's own AUD price (matches what's actually held), or both
   (USD for the macro-driver analysis, PMGOLD/AUD for "what does this mean for my
   actual position")? Leaning toward both, given AUD/USD FX is itself one of the
   factors — but confirm before building.
2. **Where to put the train/validation split date** — conversation didn't land on a
   specific date. Needs enough history in the validation window to be meaningful
   (gold signal events are rare) while leaving enough in the tuning window to pick
   sensible thresholds at all.
3. **Confirm or adjust the Phase 1 best-guess alert thresholds** listed above (real
   yield band, DXY move size, gold/silver ratio extremes, VIX level) — flagged
   explicitly as guesses needing sign-off, not settled numbers.
4. **Cadence**: should this run automatically as part of Monitor's existing daily
   timer (like the other macro indicators), or be Find-only/on-demand like
   `principles_fit`/`news_events`? Given the original ask was specifically "daily
   tracking," Monitor's automatic cadence seems like the intended answer, but
   worth confirming explicitly since it's a different cadence decision than the two
   most recent features built (both of which were deliberately Find-only for cost
   reasons that don't really apply to a handful of free FRED/yfinance calls once a
   day).
