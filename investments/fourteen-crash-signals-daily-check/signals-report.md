# 14 Crash Signals — Daily Check

Auto-generated daily -- overwritten every run. Advisor notes only; no trade action is ever suggested here (see SOUL.md). Per-marker source: investments/my-trader/14-signals-crash-warning-handoff.md.

## Hot Company Watchlist (shared input for markers 1-4, 8, 10-13)
Dynamically recomputed every run from currently-rising GICS sectors + S&P 500 mega-cap constituents -- never hardcoded to a fixed ticker list.

| Rank | Ticker | Sector | Market Cap |
|------|--------|--------|------------|
| 1 | NVDA | Technology | $5450B |
| 2 | AAPL | Technology | $4460B |
| 3 | MSFT | Technology | $3567B |
| 4 | AVGO | Technology | $1867B |
| 5 | MU | Technology | $1143B |
| 6 | BRK-B | Financials | $1067B |
| 7 | LLY | Health Care | $1055B |
| 8 | JPM | Financials | $959B |
| 9 | WMT | Consumer Staples | $910B |
| 10 | AMD | Technology | $826B |

## Markers

| # | Marker | Status | Detail |
|---|--------|--------|--------|
| 1 | Record debt issuance, hot sector | n/a | Not yet automated in this build -- see investments/my-trader/14-signals-crash-warning-handoff.md for the fact-check and feasibility notes. |
| 2 | Debt moves off balance sheet (AMD) | ok | AMD: $4.5B uncommenced lease commitments (baseline, 10-Q filed 2026-08-05) -- no prior reading to compare growth against yet |
| 3 | Seller finances buyer | n/a | Not yet automated in this build -- see investments/my-trader/14-signals-crash-warning-handoff.md for the fact-check and feasibility notes. |
| 4 | Capex outruns cash flow (NVDA) | ok | NVDA: Free Cash Flow $+96.7B, Capital Expenditure $6.0B (period ending 2026-01-31) |
| 4 | Capex outruns cash flow (AAPL) | ok | AAPL: Free Cash Flow $+98.8B, Capital Expenditure $12.7B (period ending 2025-09-30) |
| 4 | Capex outruns cash flow (MSFT) | ok | MSFT: Free Cash Flow $+67.0B, Capital Expenditure $115.9B (period ending 2026-06-30) |
| 4 | Capex outruns cash flow (AVGO) | ok | AVGO: Free Cash Flow $+26.9B, Capital Expenditure $0.6B (period ending 2025-10-31) |
| 4 | Capex outruns cash flow (MU) | ok | MU: Free Cash Flow $+1.7B, Capital Expenditure $15.9B (period ending 2025-08-31) |
| 4 | Capex outruns cash flow (BRK-B) | ok | BRK-B: Free Cash Flow $+25.0B, Capital Expenditure $20.9B (period ending 2025-12-31) |
| 4 | Capex outruns cash flow (LLY) | ok | LLY: Free Cash Flow $+6.0B, Capital Expenditure $10.8B (period ending 2025-12-31) |
| 4 | Capex outruns cash flow (JPM) | ok | JPM: Free Cash Flow $-147.8B, Capital Expenditure $0.0B (period ending 2025-12-31) |
| 4 | Capex outruns cash flow (WMT) | ok | WMT: Free Cash Flow $+14.9B, Capital Expenditure $26.6B (period ending 2026-01-31) |
| 4 | Capex outruns cash flow (AMD) | ok | AMD: Free Cash Flow $+6.7B, Capital Expenditure $1.0B (period ending 2025-12-31) |
| 5 | Margin debt YoY growth | ok | Margin debt $1.42T as of 2026-07-01, +38.6% YoY vs 2025-07-01 |
| 6 | Record IPO/equity issuance | n/a | Not yet automated in this build -- see investments/my-trader/14-signals-crash-warning-handoff.md for the fact-check and feasibility notes. |
| 7 | Retail piles into leverage | n/a | Not yet automated in this build -- see investments/my-trader/14-signals-crash-warning-handoff.md for the fact-check and feasibility notes. |
| 8 | Insider selling (NVDA) | flag | NVDA: $1,439,880,040 sold vs $0 bought, trailing 365 days |
| 8 | Insider selling (AAPL) | flag | AAPL: $170,786,590 sold vs $0 bought, trailing 365 days |
| 8 | Insider selling (MSFT) | flag | MSFT: $52,104,664 sold vs $3,436,971 bought, trailing 365 days |
| 8 | Insider selling (AVGO) | flag | AVGO: $1,062,232,315 sold vs $1,926,569 bought, trailing 365 days |
| 8 | Insider selling (MU) | flag | MU: $244,715,400 sold vs $7,821,723 bought, trailing 365 days |
| 8 | Insider selling (BRK-B) | ok | BRK-B: $0 sold vs $500,617 bought, trailing 365 days |
| 8 | Insider selling (LLY) | flag | LLY: $1,944,625,658 sold vs $0 bought, trailing 365 days |
| 8 | Insider selling (JPM) | flag | JPM: $125,468,226 sold vs $0 bought, trailing 365 days |
| 8 | Insider selling (WMT) | flag | WMT: $2,944,389,138 sold vs $0 bought, trailing 365 days |
| 8 | Insider selling (AMD) | flag | AMD: $268,070,057 sold vs $0 bought, trailing 365 days |
| 9 | The Super Bowl signal | unknown | Next Super Bowl is 2027-02-14 (180 day(s) away) -- ad-share content is not automatable, nothing to check yet |
| 10 | Most-valuable-company milestone | flag | NVDA is the largest company in the current hot-sector watchlist ($5.45T, most recently crossed the $5.0T rung) |
| 11 | Regulators sound the alarm | n/a | Not yet automated in this build -- see investments/my-trader/14-signals-crash-warning-handoff.md for the fact-check and feasibility notes. |
| 12 | Credit turns in the hot sector while broad market stays calm (AAPL) | unknown | AAPL: bond CUSIP 037833EY2 found, but no live or manually-entered yield reading available -- run `record-bond-yield AAPL <yield_pct>` |
| 12 | Credit turns in the hot sector while broad market stays calm (MU) | unknown | MU: bond CUSIP 595112CG6 found, but no live or manually-entered yield reading available -- run `record-bond-yield MU <yield_pct>` |
| 12 | Credit turns in the hot sector while broad market stays calm (BRK-B) | unknown | BRK-B: bond CUSIP 084670EB0 found, but no live or manually-entered yield reading available -- run `record-bond-yield BRK-B <yield_pct>` |
| 12 | Credit turns in the hot sector while broad market stays calm (JPM) | unknown | JPM: bond CUSIP 46661MCB8 found, but no live or manually-entered yield reading available -- run `record-bond-yield JPM <yield_pct>` |
| 13 | Funding markets start choking | n/a | Not yet automated in this build -- see investments/my-trader/14-signals-crash-warning-handoff.md for the fact-check and feasibility notes. |
| 14 | High-yield credit spread streak | ok | ICE BofA US HY OAS at 2.67pp (as of 2026-08-14); 0 consecutive day(s) at/above 3.5pp (needs 21 to flag) |

Last auto-generated: 2026-08-18.
