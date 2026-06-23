# Investments Feature - Discussion Handoff

**Status:** Design phase - PDFs downloaded, architecture being finalised
**Created:** 2026-06-19
**Updated:** 2026-06-22
**Next step:** Run `/core_piv_loop:plan-feature` to build the implementation plan

---

## Context

Shaun has subscribed to **Briefs Finance**. The service provides three distinct report types (all PDFs):

### Briefs Pro Reports (2025 + 2026)
Three series: **Growth**, **Income**, **Wealth Preservation**. Each series has:
- A monthly flagship report (e.g. "Pro Growth Report | June 2026")
- Individual thematic research reports (e.g. "Gold's Comeback", "Rare Metal Profits", "America's Naval Bet")

These are **thematic/sector research**, not explicit stock tip sheets. Tickers and company names are embedded in narrative prose. Ingestion needs LLM-assisted extraction rather than table parsing.

### Briefs Portfolio / Holdings Reports (Jan 2026 onwards)
Monthly reports showing the actual Briefs Fund holdings and YTD performance vs. S&P 500 (fund up ~4.62% YTD as of May 2026). The full position table is rendered as an image (not extractable without OCR). What IS extractable as text: top/bottom 3 performers with %, YTD vs S&P figure, analyst notes (which name buy/sell tickers with reasoning).

### Briefs Plus Reports
One report available (Jun 2026). Condensed version of all three Pro series - one pick per theme with explicit exit triggers stated.

---

## PDF Inventory (as of 2026-06-22)

- `pro-2025/`: 51 reports (Jan 11 - Dec 27 2025); one duplicate (02_22_25 - deduplicate on content hash)
- `pro-2026/`: 26 reports (Jan 2 - Jun 2026) including 3 flagship monthlies (Growth/Income/Wealth Pres)
- `holdings/`: 6 monthly fund reports (Jan-May 2026) + Q1 quarterly
- `plus/`: 1 report (Jun 2026)

**Total: 84 PDFs ready for ingestion**

---

## Agreed Architecture

### Location
Top-level `investments/` directory at the repo root (peer to `Memory/`, `wiki/`, `.claude/`).
Each tool lives as a subdirectory. A thin `.claude/skills/investments/` entry point provides
the slash-command UX without burying application code in `.claude/`.

```
investments/
+-- briefs-finance/       # Briefs Finance ingestion + analysis tool
|   +-- scripts/          # ingestion, analysis, DB queries
|   +-- data/             # investments.db (SQLite)
|   +-- reports/          # raw PDFs organised by type
|   |   +-- pro-2025/
|   |   +-- pro-2026/
|   |   +-- holdings/
|   |   +-- plus/
|   +-- principles/       # investor framework knowledge files
+-- backtest/             # backtesting tool (separate concern)
|   +-- scripts/
|   +-- data/
+-- shared/               # yfinance wrapper, DB schema, common utils
```

### Five Layers

1. **Ingestion** - LLM-assisted extraction from PDF prose: company name, ticker, buy thesis, exit trigger, report date, report type. Holdings reports: top/bottom performers + analyst notes via text extraction; full position table deferred to OCR phase.
2. **Database** - `investments.db` (SQLite). Tables: reports, recommendations, outcomes, principles_scores.
3. **Backtesting** - for each historical recommendation, fetch price at report date and at 3/6/12-month intervals via yfinance. Compare return vs S&P 500 benchmark. Store outcome in DB.
4. **Likelihood scoring** - 0-100% confidence score for new recommendations (see Scoring Model below).
5. **Investing principles knowledge** - markdown files in `principles/`, one per investor/framework. Used as evaluation layer in scoring.

### Ethical Filter

**No defense/military stocks.** Any ticker whose primary business is weapons, military hardware, or defense contracting is excluded from recommendations and flagged during ingestion. Known examples: LMT, RTX, NOC, GD, BA (defense segment), HII, LHX, LDOS. Filter applied at ingestion time - flagged records stored in DB but excluded from all scoring output and surfaced recommendations.

### Scoring Model (Likelihood Score 0-100%)

When a new report arrives, produce a score representing how likely the recommendation is to be a good bet, based on everything known historically.

**Component inputs (weighted composite):**

| Component | What it measures | Weight (indicative) |
|---|---|---|
| Briefs Finance base rate | Overall % of past picks that beat S&P 500 at 6 months | 25% |
| Sector base rate | Briefs Finance accuracy on this specific sector/theme | 20% |
| Ticker history | Has this exact stock been tipped before, and what happened? | 20% |
| Principles alignment | Does the thesis pass Graham/Buffett/Munger criteria? | 20% |
| Macro context | CAPE, recession model, cycle indicators | 15% |

**Output:** A single 0-100% score plus a breakdown showing which components pulled it up or down. For Shaun's review only - never acts autonomously.

**Calibration:** Once 12+ months of backtested outcomes are available, weights can be tuned against actual results.

---

## Investor Principles to Cover

- **Benjamin Graham** - margin of safety, intrinsic value, Mr. Market
- **Warren Buffett** - moat, long-term holding, quality businesses
- **Charlie Munger** - mental models, circle of competence, inversion
- **Peter Lynch** - invest in what you know, PEG ratio, ten-bagger mindset
- **Philip Fisher** - qualitative research (scuttlebutt), management quality
- **Howard Marks** - market cycles, risk-first thinking, second-level thinking
- **Ray Dalio** - all-weather portfolio, macro debt cycles
- **Terry Smith** - quality at a reasonable price (applicable to ASX)
- **Kerr Neilson** (Platinum AM) - Australian practitioner, long track record

---

## Price Data

`yfinance` (Yahoo Finance Python package) - free, no API key, gives historical OHLCV for ASX and US tickers. Required to evaluate whether past tips were actually good advice.

---

## Macro Metrics to Investigate

- CAPE ratio (Robert Shiller) - market valuation context
- Moody's Recession Model - recession probability input to scoring
- Four-year mid-term election cycle pullback pattern

## Sectors That Historically Hold Up in Downturns

- Consumer staples
- Healthcare
- Utilities

---

## Key Open Questions

**Resolved:**
- Holdings full position table: image - not extractable without OCR (deferred)
- Pro reports: tickers stated as "Company Name (TICKER)" in prose - extractable with LLM
- Holdings analyst notes do name sell decisions with reasoning (partial substitute for position table)
- Briefs Plus: condensed version of all three Pro series, one pick per theme

**Still open:**
- Do explicit sell call reports exist in Briefs Finance format, or only embedded in analyst notes?
- Do 2025 Pro reports follow the same structure as 2026? (confirm during ingestion)
- Does Briefs Finance ever cover ASX tickers, or US-only?
- Scoring model weights - provisional until enough backtested outcomes to calibrate

---

## What to Do in the Next Session

1. Load this handoff file for context
2. Run `/core_piv_loop:plan-feature` - provide this doc as input
3. Plan should cover: ingestion pipeline, DB schema, yfinance backtest layer, ethical filter, scoring model
4. Build from the plan - never from this doc directly
