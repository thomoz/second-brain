# 14 Crash Signals — Daily Check

What this is: 14 historical market-crash warning markers, checked daily so an early warning doesn't slip by unnoticed.

Auto-generated daily -- overwritten every run. Advisor notes only; no trade action is ever suggested here (see SOUL.md). Per-marker source: investments/my-trader/14-signals-crash-warning-handoff.md.

## Run: 2026-11-05

## Hot Company Watchlist (shared input for markers 1-4, 8, 10-13)
Dynamically recomputed every run from currently-rising GICS sectors + S&P 500 mega-cap constituents -- never hardcoded to a fixed ticker list.

| Rank | Ticker | Sector | Market Cap |
|------|--------|--------|------------|
| 1 | AMZN | Consumer Discretionary | $2877B |
| 2 | TSLA | Consumer Discretionary | $1523B |
| 3 | LLY | Health Care | $1263B |
| 4 | BRK-B | Financials | $1240B |
| 5 | WMT | Consumer Staples | $1028B |
| 6 | JPM | Financials | $935B |
| 7 | V | Financials | $816B |
| 8 | XOM | Energy | $690B |
| 9 | JNJ | Health Care | $665B |
| 10 | MA | Financials | $586B |

## Markers

| # | Marker | Status | Detail |
|---|--------|--------|--------|
| 1 | Record debt issuance, hot sector (AMZN) | flag | AMZN: 9 debt-prospectus filing(s) in the trailing 180d (own 730d average: 4.4/period) -- counts filing events, not dollar principal |
| 1 | Record debt issuance, hot sector (TSLA) | ok | TSLA: 0 debt-prospectus filing(s) in the trailing 180d (own 730d average: 0.0/period) -- counts filing events, not dollar principal |
| 1 | Record debt issuance, hot sector (LLY) | ok | LLY: 1 debt-prospectus filing(s) in the trailing 180d (own 730d average: 2.2/period) -- counts filing events, not dollar principal |
| 1 | Record debt issuance, hot sector (BRK-B) | ok | BRK-B: 0 debt-prospectus filing(s) in the trailing 180d (own 730d average: 2.2/period) -- counts filing events, not dollar principal |
| 1 | Record debt issuance, hot sector (WMT) | flag | WMT: 6 debt-prospectus filing(s) in the trailing 180d (own 730d average: 3.0/period) -- counts filing events, not dollar principal |
| 1 | Record debt issuance, hot sector (JPM) | flag | JPM: 10000 debt-prospectus filing(s) in the trailing 180d (own 730d average: 2465.8/period) -- counts filing events, not dollar principal |
| 1 | Record debt issuance, hot sector (V) | ok | V: 0 debt-prospectus filing(s) in the trailing 180d (own 730d average: 1.5/period) -- counts filing events, not dollar principal |
| 1 | Record debt issuance, hot sector (XOM) | flag | XOM: 2 debt-prospectus filing(s) in the trailing 180d (own 730d average: 0.5/period) -- counts filing events, not dollar principal |
| 1 | Record debt issuance, hot sector (JNJ) | ok | JNJ: 0 debt-prospectus filing(s) in the trailing 180d (own 730d average: 1.5/period) -- counts filing events, not dollar principal |
| 2 | Debt moves off balance sheet (AMZN) | ok | AMZN: $164.9B uncommenced lease commitments (+0.0% since last filing, 10-Q filed 2026-10-30) |
| 3 | Seller finances buyer | unknown | No automatable source exists for vendor/circular-financing deals -- periodically news-scan the current hot watchlist yourself: AMZN, TSLA, LLY, BRK-B, WMT, JPM, V, XOM, JNJ, MA |
| 4 | Capex outruns cash flow (AMZN) | ok | AMZN: Free Cash Flow $+7.7B, Capital Expenditure $131.8B (period ending 2025-12-31) |
| 4 | Capex outruns cash flow (TSLA) | ok | TSLA: Free Cash Flow $+6.2B, Capital Expenditure $8.5B (period ending 2025-12-31) |
| 4 | Capex outruns cash flow (LLY) | ok | LLY: Free Cash Flow $+6.0B, Capital Expenditure $10.8B (period ending 2025-12-31) |
| 4 | Capex outruns cash flow (BRK-B) | ok | BRK-B: Free Cash Flow $+25.0B, Capital Expenditure $20.9B (period ending 2025-12-31) |
| 4 | Capex outruns cash flow (WMT) | ok | WMT: Free Cash Flow $+14.9B, Capital Expenditure $26.6B (period ending 2026-01-31) |
| 4 | Capex outruns cash flow (JPM) | ok | JPM: Free Cash Flow $-147.8B, Capital Expenditure $0.0B (period ending 2025-12-31) |
| 4 | Capex outruns cash flow (V) | ok | V: Free Cash Flow $+21.6B, Capital Expenditure $1.5B (period ending 2025-09-30) |
| 4 | Capex outruns cash flow (XOM) | ok | XOM: Free Cash Flow $+23.6B, Capital Expenditure $28.4B (period ending 2025-12-31) |
| 4 | Capex outruns cash flow (JNJ) | ok | JNJ: Free Cash Flow $+19.3B, Capital Expenditure $5.2B (period ending 2025-12-31) |
| 4 | Capex outruns cash flow (MA) | ok | MA: Free Cash Flow $+16.4B, Capital Expenditure $1.2B (period ending 2025-12-31) |
| 5 | Margin debt YoY growth | ok | Margin debt $1.48T as of 2026-09-01, +31.4% YoY vs 2025-09-01 |
| 6 | Record IPO/equity issuance | ok | S-1 (intent to register): 162 filing(s) in the trailing 30d vs 220 in the same window a year ago (0.74x); 424B4 (priced IPO): 24 filing(s) in the trailing 30d vs 39 in the same window a year ago (0.62x) |
| 7 | Retail piles into leverage | ok | Equity put/call ratio 0.60 (z=0.25 vs trailing 76d mean 0.58) -- options positioning proxy, not the video's ETF/fund-flow mechanism |
| 8 | Insider selling (AMZN) | flag | AMZN: $448,478,458 sold vs $0 bought, trailing 365 days |
| 8 | Insider selling (TSLA) | flag | TSLA: $87,688,429 sold vs $0 bought, trailing 365 days |
| 8 | Insider selling (LLY) | flag | LLY: $516,390,432 sold vs $0 bought, trailing 365 days |
| 8 | Insider selling (BRK-B) | ok | BRK-B: $0 sold vs $500,617 bought, trailing 365 days |
| 8 | Insider selling (WMT) | flag | WMT: $2,967,673,609 sold vs $0 bought, trailing 365 days |
| 8 | Insider selling (JPM) | flag | JPM: $126,350,253 sold vs $0 bought, trailing 365 days |
| 8 | Insider selling (V) | flag | V: $100,042,704 sold vs $0 bought, trailing 365 days |
| 8 | Insider selling (XOM) | flag | XOM: $2,395,656 sold vs $0 bought, trailing 365 days |
| 8 | Insider selling (JNJ) | flag | JNJ: $150,667,262 sold vs $257,688 bought, trailing 365 days |
| 8 | Insider selling (MA) | flag | MA: $73,363,034 sold vs $0 bought, trailing 365 days |
| 8 | Insider selling (BRK-A) | flag | BRK-A: $19,972,776 sold vs $0 bought, trailing 365 days |
| 9 | The Super Bowl signal | unknown | Next Super Bowl is 2027-02-14 (102 day(s) away) -- ad-share content is not automatable, nothing to check yet |
| 10 | Most-valuable-company milestone | flag | AMZN is the largest company in the current hot-sector watchlist ($2.88T, most recently crossed the $2.5T rung) |
| 11 | Regulators sound the alarm | ok | No new matching regulator statements this run. |
| 12 | Credit turns in the hot sector while broad market stays calm (AMZN) | unknown | AMZN: bond CUSIP 023135EA0 found, but no live or manually-entered yield reading available -- run `record-bond-yield AMZN <yield_pct>` |
| 12 | Credit turns in the hot sector while broad market stays calm (BRK-B) | unknown | BRK-B: bond CUSIP 084670EB0 found, but no live or manually-entered yield reading available -- run `record-bond-yield BRK-B <yield_pct>` |
| 12 | Credit turns in the hot sector while broad market stays calm (JPM) | unknown | JPM: bond CUSIP 46661MCB8 found, but no live or manually-entered yield reading available -- run `record-bond-yield JPM <yield_pct>` |
| 12 | Credit turns in the hot sector while broad market stays calm (JNJ) | unknown | JNJ: bond CUSIP 478160CY8 found, but no live or manually-entered yield reading available -- run `record-bond-yield JNJ <yield_pct>` |
| 12 | Credit turns in the hot sector while broad market stays calm (MA) | unknown | MA: bond CUSIP 57636QBH6 found, but no live or manually-entered yield reading available -- run `record-bond-yield MA <yield_pct>` |
| 13 | Funding markets start choking | ok | CP-Treasury spread (DCPN3M-DTB3) 0.00pp (z=-1.01 vs trailing 365d) |
| 14 | High-yield credit spread streak | ok | ICE BofA US HY OAS at 3.40pp (as of 2026-11-03); 0 consecutive day(s) at/above 3.5pp (needs 21 to flag) -- WATCH: within 0.3pp of the flag threshold (WATCH) |
