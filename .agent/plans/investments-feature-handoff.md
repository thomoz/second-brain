# Investments Feature — Discussion Handoff

**Status:** Design discussion only — nothing built yet
**Created:** 2026-06-19
**Next step:** Wait for first Briefs Finance tip sheet before designing ingestion layer

---

## Context

Shaun has subscribed to **Briefs Finance**, a market tips service that will:
- Send a monthly tip sheet (format unknown — likely PDF)
- Provide 5 years of historical tip sheets on joining

The goal is to build an investments feature into the Second Brain that can process these tip sheets, build a historical record, and help evaluate whether future tips are worth acting on.

---

## Agreed Architecture

### Location
Everything self-contained in one skill directory:

```
.claude/skills/investments/
├── scripts/          # ingestion, analysis, DB queries
├── data/             # investments.db (SQLite)
├── principles/       # investor knowledge files (one per investor/framework)
├── tip-sheets/       # raw ingested source files
└── investments.md    # skill entry point
```

No dependency on the shared `wiki/` or `llm-wiki` skill — the investments skill handles its own principles lookup internally.

### Four Layers

1. **Ingestion** — parse tip sheets into structured records: company, ticker, buy thesis, target metrics, sell signals, date issued
2. **Database** — `investments.db` (SQLite, separate from memory search DB). Stores tip history, company records, outcomes.
3. **Analysis tools** — historical lookup per company, tip-vs-outcome comparison, pattern surfacing
4. **Investing principles knowledge** — structured markdown files in `principles/`, one per investor/framework. Used as an evaluation layer when assessing new tips.

---

## Investor Principles to Cover

- **Benjamin Graham** — margin of safety, intrinsic value, Mr. Market
- **Warren Buffett** — moat, long-term holding, quality businesses
- **Charlie Munger** — mental models, circle of competence, inversion
- **Peter Lynch** — invest in what you know, PEG ratio, ten-bagger mindset
- **Philip Fisher** — qualitative research (scuttlebutt), management quality
- **Howard Marks** — market cycles, risk-first thinking, second-level thinking
- **Ray Dalio** — all-weather portfolio, macro debt cycles
- **Terry Smith** — quality at a reasonable price (applicable to ASX)
- **Kerr Neilson** (Platinum AM) — Australian practitioner, long track record

---

## Price Data

`yfinance` (Yahoo Finance Python package) — free, no API key, gives historical OHLCV for ASX and US tickers. Required to evaluate whether past tips were actually good advice.

---

## The Evaluation Vision

When a new tip sheet arrives, the system should be able to:
1. Ingest the tip and store it in the DB
2. Look up whether this company has been tipped before and what happened
3. Cross-reference the thesis against investor principles (does it have a moat? does the macro support the sector?)
4. Surface a structured assessment for Shaun's review

The historical backtesting angle — "did the previous 5 years of tips actually outperform?" — is the most valuable long-term output.

---

## Key Open Questions (resolve when first tip sheet arrives)

- What format are the tip sheets? (PDF, HTML, email body?)
- How structured is the data? (tables vs narrative prose)
- What exactly constitutes a "sell signal" in their format?
- Are ASX tickers explicitly named or do we need to resolve company names to tickers?
- Do historical sheets follow the same format as current ones?

---

## What to Do in the Next Session

1. Load this handoff file for context
2. If a tip sheet has arrived — drop it in and design the ingestion schema around the actual format
3. If no tip sheet yet — can begin writing the `principles/` knowledge files (no format dependency)
4. Run `/core_piv_loop:plan-feature` before building anything
