# 14 Crash Signals — Daily Check

What this is: 14 historical market-crash warning markers, checked daily so an early warning doesn't slip by unnoticed.

Auto-generated daily -- overwritten every run. Advisor notes only; no trade action is ever suggested here (see SOUL.md). Per-marker source: investments/my-trader/14-signals-crash-warning-handoff.md.

## Run: 2026-11-25

## Hot Company Watchlist (shared input for markers 1-4, 8, 10-13)
Dynamically recomputed every run from currently-rising GICS sectors + S&P 500 mega-cap constituents -- never hardcoded to a fixed ticker list.

| Rank | Ticker | Sector | Market Cap |
|------|--------|--------|------------|
| 1 | AMZN | Consumer Discretionary | $2728B |
| 2 | LLY | Health Care | $1254B |
| 3 | WMT | Consumer Staples | $1053B |
| 4 | JNJ | Health Care | $666B |
| 5 | ABBV | Health Care | $531B |
| 6 | COST | Consumer Staples | $484B |
| 7 | KO | Consumer Staples | $420B |
| 8 | PG | Consumer Staples | $400B |
| 9 | HD | Consumer Discretionary | $353B |
| 10 | MRK | Health Care | $349B |

## Markers

| # | Marker | Status | Detail |
|---|--------|--------|--------|
| 1 | Record debt issuance, hot sector (AMZN) | flag | AMZN: 9 debt-prospectus filing(s) in the trailing 180d (own 730d average: 4.4/period) -- counts filing events, not dollar principal |
| 1 | Record debt issuance, hot sector (LLY) | ok | LLY: 0 debt-prospectus filing(s) in the trailing 180d (own 730d average: 2.2/period) -- counts filing events, not dollar principal |
| 1 | Record debt issuance, hot sector (WMT) | flag | WMT: 6 debt-prospectus filing(s) in the trailing 180d (own 730d average: 3.0/period) -- counts filing events, not dollar principal |
| 1 | Record debt issuance, hot sector (JNJ) | ok | JNJ: 0 debt-prospectus filing(s) in the trailing 180d (own 730d average: 1.5/period) -- counts filing events, not dollar principal |
| 1 | Record debt issuance, hot sector (ABBV) | ok | ABBV: 3 debt-prospectus filing(s) in the trailing 180d (own 730d average: 2.5/period) -- counts filing events, not dollar principal |
| 1 | Record debt issuance, hot sector (COST) | ok | COST: 0 debt-prospectus filing(s) in the trailing 180d (own 730d average: 0.0/period) -- counts filing events, not dollar principal |
| 1 | Record debt issuance, hot sector (KO) | ok | KO: 0 debt-prospectus filing(s) in the trailing 180d (own 730d average: 0.0/period) -- counts filing events, not dollar principal |
| 1 | Record debt issuance, hot sector (PG) | ok | PG: 8 debt-prospectus filing(s) in the trailing 180d (own 730d average: 4.7/period) -- counts filing events, not dollar principal |
| 1 | Record debt issuance, hot sector (HD) | ok | HD: 0 debt-prospectus filing(s) in the trailing 180d (own 730d average: 0.7/period) -- counts filing events, not dollar principal |
| 1 | Record debt issuance, hot sector (MRK) | ok | MRK: 0 debt-prospectus filing(s) in the trailing 180d (own 730d average: 2.2/period) -- counts filing events, not dollar principal |
| 2 | Debt moves off balance sheet (AMZN) | ok | AMZN: $164.9B uncommenced lease commitments (+0.0% since last filing, 10-Q filed 2026-10-30) |
| 3 | Seller finances buyer | unknown | No automatable source exists for vendor/circular-financing deals -- periodically news-scan the current hot watchlist yourself: AMZN, LLY, WMT, JNJ, ABBV, COST, KO, PG, HD, MRK |
| 4 | Capex outruns cash flow (AMZN) | ok | AMZN: Free Cash Flow $+7.7B, Capital Expenditure $131.8B (period ending 2025-12-31) |
| 4 | Capex outruns cash flow (LLY) | ok | LLY: Free Cash Flow $+6.0B, Capital Expenditure $10.8B (period ending 2025-12-31) |
| 4 | Capex outruns cash flow (WMT) | ok | WMT: Free Cash Flow $+14.9B, Capital Expenditure $26.6B (period ending 2026-01-31) |
| 4 | Capex outruns cash flow (JNJ) | ok | JNJ: Free Cash Flow $+19.3B, Capital Expenditure $5.2B (period ending 2025-12-31) |
| 4 | Capex outruns cash flow (ABBV) | ok | ABBV: Free Cash Flow $+17.8B, Capital Expenditure $1.2B (period ending 2025-12-31) |
| 4 | Capex outruns cash flow (COST) | ok | COST: Free Cash Flow $+9.4B, Capital Expenditure $6.4B (period ending 2026-08-31) |
| 4 | Capex outruns cash flow (KO) | ok | KO: Free Cash Flow $+5.3B, Capital Expenditure $2.1B (period ending 2025-12-31) |
| 4 | Capex outruns cash flow (PG) | ok | PG: Free Cash Flow $+15.1B, Capital Expenditure $4.4B (period ending 2026-06-30) |
| 4 | Capex outruns cash flow (HD) | ok | HD: Free Cash Flow $+12.6B, Capital Expenditure $3.7B (period ending 2026-01-31) |
| 4 | Capex outruns cash flow (MRK) | ok | MRK: Free Cash Flow $+12.4B, Capital Expenditure $4.1B (period ending 2025-12-31) |
| 5 | Margin debt YoY growth | ok | Margin debt $1.45T as of 2026-10-01, +22.4% YoY vs 2025-10-01 |
| 6 | Record IPO/equity issuance | ok | S-1 (intent to register): 147 filing(s) in the trailing 30d vs 159 in the same window a year ago (0.92x); 424B4 (priced IPO): 24 filing(s) in the trailing 30d vs 43 in the same window a year ago (0.56x) |
| 7 | Retail piles into leverage | ok | Equity put/call ratio 0.55 (z=-0.64 vs trailing 89d mean 0.60) -- options positioning proxy, not the video's ETF/fund-flow mechanism |
| 8 | Insider selling (AMZN) | flag | AMZN: $450,501,232 sold vs $0 bought, trailing 365 days |
| 8 | Insider selling (LLY) | flag | LLY: $15,840,546 sold vs $0 bought, trailing 365 days |
| 8 | Insider selling (WMT) | flag | WMT: $2,970,185,544 sold vs $0 bought, trailing 365 days |
| 8 | Insider selling (JNJ) | flag | JNJ: $154,384,808 sold vs $257,688 bought, trailing 365 days |
| 8 | Insider selling (ABBV) | flag | ABBV: $30,847,936 sold vs $0 bought, trailing 365 days |
| 8 | Insider selling (COST) | flag | COST: $13,466,818 sold vs $0 bought, trailing 365 days |
| 8 | Insider selling (KO) | flag | KO: $256,275,557 sold vs $0 bought, trailing 365 days |
| 8 | Insider selling (PG) | flag | PG: $93,911,490 sold vs $0 bought, trailing 365 days |
| 8 | Insider selling (HD) | flag | HD: $13,241,014 sold vs $0 bought, trailing 365 days |
| 8 | Insider selling (MRK) | flag | MRK: $79,289,252 sold vs $0 bought, trailing 365 days |
| 9 | The Super Bowl signal | unknown | Next Super Bowl is 2027-02-14 (82 day(s) away) -- ad-share content is not automatable, nothing to check yet |
| 10 | Most-valuable-company milestone | flag | AMZN is the largest company in the current hot-sector watchlist ($2.73T, most recently crossed the $2.5T rung) |
| 11 | Regulators sound the alarm | ok | No new matching regulator statements this run. |
| 12 | Credit turns in the hot sector while broad market stays calm (AMZN) | unknown | AMZN: bond CUSIP 023135EA0 found, but no live or manually-entered yield reading available -- run `record-bond-yield AMZN <yield_pct>` |
| 12 | Credit turns in the hot sector while broad market stays calm (JNJ) | unknown | JNJ: bond CUSIP 478160CY8 found, but no live or manually-entered yield reading available -- run `record-bond-yield JNJ <yield_pct>` |
| 12 | Credit turns in the hot sector while broad market stays calm (ABBV) | unknown | ABBV: bond CUSIP 00287YDR7 found, but no live or manually-entered yield reading available -- run `record-bond-yield ABBV <yield_pct>` |
| 12 | Credit turns in the hot sector while broad market stays calm (HD) | unknown | HD: bond CUSIP 437076CX8 found, but no live or manually-entered yield reading available -- run `record-bond-yield HD <yield_pct>` |
| 12 | Credit turns in the hot sector while broad market stays calm (MRK) | unknown | MRK: bond CUSIP 58933YCD5 found, but no live or manually-entered yield reading available -- run `record-bond-yield MRK <yield_pct>` |
| 13 | Funding markets start choking | ok | CP-Treasury spread (DCPN3M-DTB3) 0.11pp (z=1.06 vs trailing 365d) |
| 14 | High-yield credit spread streak | ok | ICE BofA US HY OAS at 3.63pp (as of 2026-11-23); 3 consecutive day(s) at/above 3.5pp (needs 21 to flag) -- WATCH: within 0.3pp of the flag threshold (WATCH) |
