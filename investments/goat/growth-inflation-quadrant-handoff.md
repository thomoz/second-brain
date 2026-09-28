# Growth/Inflation Quadrant Sector Guide — Handoff

Tool name: working title **"Macro Quad Guide"** (rename during `/plan-feature` if a
better one surfaces). Proposed home: **`investments/goat`**, as a new module
alongside `sector_rotation.py` — same package that already ranks the 11 SPDR
Select Sector ETFs by price momentum, since this is a second, different lens on
the same underlying question ("what sectors should I be in right now").

## Status: NOT BUILT — drafted 2026-09-25 from Shaun's request (prompted by a
screenshot of a Growth/Inflation quadrant chart). Research-only pass so far —
awaiting Shaun's manual `/plan-feature` run against this doc before any code.

## What This Is

A 2x2 macro-regime framework: classify the economy by whether **growth** and
**inflation** are each *accelerating or decelerating* (rate of change, not
level), giving four "quads":

- **Quad 1** — growth up, inflation down → pro-growth positioning (tech,
  discretionary typically lead).
- **Quad 2** — growth up, inflation up → pro-growth + inflation hedges
  (energy, materials, industrials).
- **Quad 3** — growth down, inflation up → stagflation protection (staples,
  utilities, gold/commodities).
- **Quad 4** — growth down, inflation down → defensive + volatility assets
  (staples, utilities, long bonds, cash).

This exact framing (and the "Quad 1–4" labels) is Hedgeye Risk Management's
branded "GIP Model" (Growth, Inflation, Policy). It is not a Hedgeye invention
in substance, though — the same growth/inflation 2x2 is the academic/industry
root of Merrill Lynch's 2004 "Investment Clock" (business-cycle sector
rotation, still widely cited) and is philosophically the same axis Bridgewater's
"All Weather"/risk-parity approach is built around. Three different lineages,
same core idea: **macro regime determines which sectors/assets lead.**

## What Experts and the Academic Literature Actually Say

Researched live 2026-09-25 — this is not fringe, but it is not settled either.

**The core idea has real backing.** Business-cycle-to-sector rotation is a
long-studied, mainstream concept — Fidelity has run its own "Business Cycle
Approach to Equity Sector Investing" research for years, and multiple academic
papers (sector-return prediction via macro factors, business-cycle-phase
detection strategies) treat it as a legitimate research question, not a fringe
one.

**But the evidence for any specific quadrant model is mixed, not strong:**

- Academic backtests of the Merrill Lynch Investment Clock find it **explains
  some sectors much better than others** — Consumer Discretionary and Oil & Gas
  fit the model reasonably well; Telecoms, Utilities, and Basic Materials are
  poorly explained. A model that works for half your sectors and not the other
  half is a weak foundation for a rules-based allocator.
- The same literature criticizes the Investment Clock as **oversimplified** —
  it classifies regime using only the *level* of growth/inflation judgment
  calls, ignores policy/government-intervention effects, and its handling of
  term spread/risk premium rotation is described as "highly subjective" and
  lacking a "scientifically rigorous econometric model." A study applying it to
  China's market found investors could not extract additional returns from the
  original theory without modification for that market's structure — i.e., the
  sector mapping is regime- and market-specific, not universal.
- **Fidelity's own research (not a marketer's) is candid about limits**: "every
  business cycle is different," performance can "deviate significantly from
  historical averages" over horizons under 30 years, and — importantly — the
  **mid-cycle phase produces the smallest sector performance differentiation
  of any phase**, meaning the framework's signal is weakest exactly when an
  economy is gradually transitioning rather than in a sharp regime shift. Real
  economies spend a lot of time in ambiguous, in-between states.
- **Hedgeye specifically** (the branded version prompting this request) has a
  polarizing reputation. It claims 27+ years of backtesting and cites
  "directionally accurate" 2008 calls, but independent commentary is thin and
  mixed: some users report being unable to translate its calls into actual
  investment returns, some cite specific Hedgeye products underperforming by
  160–300bps, and a recurring complaint (including on Reddit) is that Hedgeye
  does not publish a transparent, audited track record of its quad calls
  despite the marketing confidence — you're asked to trust the framework's
  history, not shown it independently verified.

**My own read:** the underlying growth/inflation regime idea is real and worth
building on — it's the same axis serious allocators (Bridgewater) use, not
just a media-firm gimmick. But every credible independent source agrees on the
same two weak points: (1) **the specific sector-to-quadrant mapping is a
historical correlation that varies by sector and by era**, not a physical law —
half the sectors fit cleanly, half don't, and (2) **real-time classification is
the hard part**, not the quadrant logic itself. Official GDP is quarterly and
revised; CPI has a real reporting lag. By the time you're confident which quad
you're in from official data, the regime may already be turning. This is
exactly the same class of trap the Matt Damon Price/Volatility/Volume Check
just got caught in — a plausible, well-precedented framework that still needs
a real backtest against real sector-return data before being trusted, not
adopted on reputation or a nice-looking chart alone.

## A Practical Fix for the Real-Time-Lag Problem

One approach seen in independent (non-Hedgeye) writeups of this same
growth/inflation quadrant concept: **use market-based proxies instead of
lagging official statistics** — e.g., the S&P 500's own trend as a
forward-looking growth proxy (the market is forward-looking, so it front-runs
GDP prints), and something like TIPS breakevens, gold, or a commodity/bond
ratio as an inflation proxy — rather than waiting on quarterly GDP and monthly
CPI. This sidesteps the single most consistently-cited practical flaw (lag +
revision) at the cost of a proxy that isn't literally "growth" or "inflation."
Worth treating as a real design option during `/plan-feature`, not an
afterthought — it may be a better fit for this codebase's existing pattern
of live daily price-based checks (see `sector_rotation.py`, `heartbeat.py`)
than a FRED-based lagging-data classifier would be.

## Relationship to Goat's Existing Sector Rotation

`investments/goat/goat/sector_rotation.py` already ranks the 11 SPDR sector
ETFs by trailing price momentum (`rank_sectors`) and flags 50DMA breakout
crosses (`check_sector_breakout`) — a **pure price-momentum** signal, no macro
regime awareness at all. A quadrant classifier would be a genuinely different
kind of input (macro regime vs. price momentum), not a duplicate. Whether it
should be:

(a) a **separate report section** (macro regime context shown alongside the
existing momentum ranking, advisor-notes only, no interaction), or
(b) a **filter/overlay** on the existing ranking (e.g., only surface momentum
breakouts in sectors the current quad also favors), or
(c) fully independent and unrelated to `sector_rotation.py`

...is a real open design question, not a given. Given Fidelity's own finding
that sector rotation strategies are already noisy and business-cycle-dependent,
combining two imperfect signals (momentum + quad) could compound noise instead
of canceling it — this needs a real backtest comparison (does quad-filtered
momentum actually beat unfiltered momentum, on real historical sector returns),
not an assumption either way.

## Real Gotchas to Research During `/plan-feature`

1. **Data sourcing for growth/inflation** (if going the official-statistics
   route rather than the market-proxy route above): FRED already has a
   working integration in this codebase (`scripts.macro.fred_series_range`,
   used by `gold_backtest.py`/`macro_indicators.py`) — GDP, CPI, PCE are all
   available there. Reuse that pattern; don't build a new fetcher.
2. **"Accelerating/decelerating" is a second derivative** — rate of change of
   a rate of change. This is noisier than a first-derivative signal and prone
   to false regime flips on revision-driven wobbles in official data,
   especially for GDP (revised repeatedly after first release). Needs a
   deliberately-chosen smoothing/confirmation window, researched against real
   history, not assumed.
3. **Regime relationships are era-dependent.** Multiple sources flag that
   quantitative easing, zero/negative rates, and pandemic-era stimulus
   materially broke historical growth/inflation/sector relationships in ways
   pre-2008 backtests don't capture. A backtest window needs to explicitly
   include (not exclude) the post-2008 and post-2020 regime to be honest about
   whether the framework still holds up now, not just historically.
4. **Sector-to-quadrant mapping needs to be derived from real data for the
   actual instruments this codebase trades** (the 11 SPDR sector ETFs already
   in `config.GOAT_SECTOR_ETFS`), not copied from a textbook/Hedgeye chart —
   per the academic finding above that half the sectors don't fit cleanly, a
   generic mapping risks encoding someone else's (weak) fit as if it were this
   portfolio's own.

## Explicitly NOT Scoped Here

- No implementation — this is a research handoff only.
- No live gate/alert/allocation-suggestion until a real backtest (mirroring
  the discipline the Matt Damon check established, and the goat-heartbeat
  "quiet base" BBW failure before it) shows the classifier's quad calls
  actually preceded real sector outperformance in this codebase's own
  historical data — not just cite that the general concept has academic
  support.
- No Hedgeye subscription/data integration — everything above is either
  already-available FRED data or derivable from price history already fetched
  elsewhere in this codebase.

## Validation (once built)

Same discipline as `investments/roc-triple-signal-handoff.md`: build the
classifier, then a one-off backtest against real historical SPDR sector ETF
returns conditioned on the classified quad (reusing `gold_backtest.py`'s
generic state-conditioned forward-return machinery — see that module and
`mytrader/checks/matt_damon_price_volitility_volume_check_backtest.py`'s git
history for the reusable pattern, even though that specific check was later
removed). Compare quad-conditioned sector returns against (a) an unconditioned
baseline and (b) `sector_rotation.py`'s existing pure-momentum ranking, over
the same historical window, before any live use. Write the result into this
handoff either way — positive or negative — so the finding isn't lost.

## Sources Consulted (2026-09-25)

- [Keith McCullough on using growth and inflation, quads and debunking 'Old Wall' misinformation](https://www.cmcmarkets.com/en-gb/opto/keith-mccullough-on-using-growth-and-inflation-quads-and-debunking-old-wall-misinformation) — Hedgeye's own framing of the GIP model.
- [Hedgeye — CHART OF THE DAY: Our GIP Model [Growth + Inflation + Policy]](https://app.hedgeye.com/insights/101860-chart-of-the-day-our-gip-model-growth-inflation-policy?type=macro)
- [Merrill Lynch: The Investment Clock: Making Money from Macro (2004) — wonkmonk's notes](https://wonkmonksnotes.wordpress.com/2024/09/08/merrill-lynch-the-investment-clock-making-money-from-macro-2004/)
- [The Feasibility Study of Merrill Lynch Investment Clock Theory in China's Market](https://webofproceedings.org/proceedings_series/ESSP/ASSAH%202021/DAS25146.pdf) — academic critique, mixed sector-level fit.
- [Introduction and Applications of the Investment Clock Theory](https://drpress.org/ojs/index.php/HBEM/article/download/16157/15678/16638)
- [Fidelity — The Business Cycle Approach to Equity Sector Investing](https://www.fidelity.com/webcontent/ap101883-markets_sectors-content/21.01.0/business_cycle/Business_Cycle_Sector_Approach_2020.pdf) — the "mid-cycle produces smallest differentiation" and "every cycle is different" cautions.
- [Fidelity — The business cycle and its investing implications](https://www.fidelity.com/learning-center/trading-investing/markets-sectors/business-cycle-investing-implications)
- [Growth and Inflation Sector Timing — Jaewon Jung, 1nve.st](https://www.1nve.st/p/growth-and-inflation-sector-timing) — the market-proxy-instead-of-lagging-official-data approach (Varadi's strategy).
- [Hedgeye Review — Is it Safe and Legit? (Traders Union)](https://tradersunion.com/reviews/hedgeye-com/)
- [Hedgeye Reviews (Trustpilot)](https://www.trustpilot.com/review/hedgeye.com) — mixed independent user sentiment, transparency complaints.
- `investments/goat/goat/sector_rotation.py`, `config.py` (`GOAT_SECTOR_ETFS`) — existing momentum-based sector ranking this would sit alongside.
- `investments/my-trader/mytrader/gold_backtest.py` — reusable state-conditioned backtest machinery.
- `investments/roc-triple-signal-handoff.md`, `.agent/plans/completed/matt-damon-price-volitility-volume-check.md` — direct precedent for "backtest before trust" discipline on a plausible-sounding technical framework.
