# 14 Crash Signals — Daily Check

What this is: 14 historical market-crash warning markers, checked daily so an early warning doesn't slip by unnoticed.

Auto-generated daily -- overwritten every run. Advisor notes only; no trade action is ever suggested here (see SOUL.md). Per-marker source: investments/my-trader/14-signals-crash-warning-handoff.md.

## Run: 2026-11-19

## Hot Company Watchlist (shared input for markers 1-4, 8, 10-13)
Dynamically recomputed every run from currently-rising GICS sectors + S&P 500 mega-cap constituents -- never hardcoded to a fixed ticker list.

| Rank | Ticker | Sector | Market Cap |
|------|--------|--------|------------|
| 1 | LLY | Health Care | $1232B |
| 2 | WMT | Consumer Staples | $1014B |
| 3 | JNJ | Health Care | $656B |
| 4 | XOM | Energy | $655B |
| 5 | ABBV | Health Care | $506B |
| 6 | COST | Consumer Staples | $486B |
| 7 | KO | Consumer Staples | $422B |
| 8 | CVX | Energy | $402B |
| 9 | PG | Consumer Staples | $395B |
| 10 | UNH | Health Care | $314B |

## Markers

| # | Marker | Status | Detail |
|---|--------|--------|--------|
| 1 | Record debt issuance, hot sector (LLY) | ok | LLY: 0 debt-prospectus filing(s) in the trailing 180d (own 730d average: 2.2/period) -- counts filing events, not dollar principal |
| 1 | Record debt issuance, hot sector (WMT) | flag | WMT: 6 debt-prospectus filing(s) in the trailing 180d (own 730d average: 3.0/period) -- counts filing events, not dollar principal |
| 1 | Record debt issuance, hot sector (JNJ) | ok | JNJ: 0 debt-prospectus filing(s) in the trailing 180d (own 730d average: 1.5/period) -- counts filing events, not dollar principal |
| 1 | Record debt issuance, hot sector (XOM) | flag | XOM: 2 debt-prospectus filing(s) in the trailing 180d (own 730d average: 0.5/period) -- counts filing events, not dollar principal |
| 1 | Record debt issuance, hot sector (ABBV) | ok | ABBV: 3 debt-prospectus filing(s) in the trailing 180d (own 730d average: 2.5/period) -- counts filing events, not dollar principal |
| 1 | Record debt issuance, hot sector (COST) | ok | COST: 0 debt-prospectus filing(s) in the trailing 180d (own 730d average: 0.0/period) -- counts filing events, not dollar principal |
| 1 | Record debt issuance, hot sector (KO) | ok | KO: 0 debt-prospectus filing(s) in the trailing 180d (own 730d average: 0.0/period) -- counts filing events, not dollar principal |
| 1 | Record debt issuance, hot sector (CVX) | ok | CVX: 0 debt-prospectus filing(s) in the trailing 180d (own 730d average: 2.2/period) -- counts filing events, not dollar principal |
| 1 | Record debt issuance, hot sector (PG) | ok | PG: 8 debt-prospectus filing(s) in the trailing 180d (own 730d average: 4.7/period) -- counts filing events, not dollar principal |
| 1 | Record debt issuance, hot sector (UNH) | ok | UNH: 0 debt-prospectus filing(s) in the trailing 180d (own 730d average: 0.7/period) -- counts filing events, not dollar principal |
| 2 | Debt moves off balance sheet | ok | No hot-watchlist tickers with a resolvable lease-commitment reading this run. |
| 3 | Seller finances buyer | unknown | No automatable source exists for vendor/circular-financing deals -- periodically news-scan the current hot watchlist yourself: LLY, WMT, JNJ, XOM, ABBV, COST, KO, CVX, PG, UNH |
| 4 | Capex outruns cash flow (LLY) | ok | LLY: Free Cash Flow $+6.0B, Capital Expenditure $10.8B (period ending 2025-12-31) |
| 4 | Capex outruns cash flow (WMT) | ok | WMT: Free Cash Flow $+14.9B, Capital Expenditure $26.6B (period ending 2026-01-31) |
| 4 | Capex outruns cash flow (JNJ) | ok | JNJ: Free Cash Flow $+19.3B, Capital Expenditure $5.2B (period ending 2025-12-31) |
| 4 | Capex outruns cash flow (XOM) | ok | XOM: Free Cash Flow $+23.6B, Capital Expenditure $28.4B (period ending 2025-12-31) |
| 4 | Capex outruns cash flow (ABBV) | ok | ABBV: Free Cash Flow $+17.8B, Capital Expenditure $1.2B (period ending 2025-12-31) |
| 4 | Capex outruns cash flow (COST) | ok | COST: Free Cash Flow $+9.4B, Capital Expenditure $6.4B (period ending 2026-08-31) |
| 4 | Capex outruns cash flow (KO) | ok | KO: Free Cash Flow $+5.3B, Capital Expenditure $2.1B (period ending 2025-12-31) |
| 5 | Margin debt YoY growth | ok | Margin debt $1.45T as of 2026-10-01, +22.4% YoY vs 2025-10-01 |
| 6 | Record IPO/equity issuance | ok | S-1 (intent to register): 145 filing(s) in the trailing 30d vs 198 in the same window a year ago (0.73x); 424B4 (priced IPO): 21 filing(s) in the trailing 30d vs 52 in the same window a year ago (0.40x) |
| 7 | Retail piles into leverage | ok | Equity put/call ratio 0.71 (z=1.47 vs trailing 89d mean 0.60) -- options positioning proxy, not the video's ETF/fund-flow mechanism |
| 8 | Insider selling (LLY) | flag | LLY: $15,881,525 sold vs $0 bought, trailing 365 days |
| 8 | Insider selling (WMT) | flag | WMT: $2,967,673,609 sold vs $0 bought, trailing 365 days |
| 8 | Insider selling (JNJ) | flag | JNJ: $154,384,808 sold vs $257,688 bought, trailing 365 days |
| 8 | Insider selling (XOM) | flag | XOM: $2,395,656 sold vs $0 bought, trailing 365 days |
| 8 | Insider selling (ABBV) | flag | ABBV: $30,847,936 sold vs $0 bought, trailing 365 days |
| 8 | Insider selling (COST) | flag | COST: $13,466,818 sold vs $0 bought, trailing 365 days |
| 8 | Insider selling (KO) | flag | KO: $258,526,362 sold vs $0 bought, trailing 365 days |
| 8 | Insider selling (CVX) | flag | CVX: $677,056,564 sold vs $0 bought, trailing 365 days |
| 8 | Insider selling (PG) | flag | PG: $93,911,490 sold vs $0 bought, trailing 365 days |
| 8 | Insider selling (UNH) | flag | UNH: $944,910 sold vs $0 bought, trailing 365 days |
| 9 | The Super Bowl signal | unknown | Next Super Bowl is 2027-02-14 (87 day(s) away) -- ad-share content is not automatable, nothing to check yet |
| 10 | Most-valuable-company milestone | flag | LLY is the largest company in the current hot-sector watchlist ($1.23T, most recently crossed the $1.0T rung) |
| 11 | Regulators sound the alarm | ok | No new matching regulator statements this run. |
| 12 | Credit turns in the hot sector while broad market stays calm (JNJ) | unknown | JNJ: bond CUSIP 478160CY8 found, but no live or manually-entered yield reading available -- run `record-bond-yield JNJ <yield_pct>` |
| 12 | Credit turns in the hot sector while broad market stays calm (ABBV) | unknown | ABBV: bond CUSIP 00287YDR7 found, but no live or manually-entered yield reading available -- run `record-bond-yield ABBV <yield_pct>` |
| 12 | Credit turns in the hot sector while broad market stays calm (CVX) | unknown | CVX: bond CUSIP 166756AZ9 found, but no live or manually-entered yield reading available -- run `record-bond-yield CVX <yield_pct>` |
| 13 | Funding markets start choking | ok | CP-Treasury spread (DCPN3M-DTB3) 0.11pp (z=1.06 vs trailing 365d) |
| 14 | High-yield credit spread streak | ok | ICE BofA US HY OAS at 3.43pp (as of 2026-11-17); 0 consecutive day(s) at/above 3.5pp (needs 21 to flag) -- WATCH: within 0.3pp of the flag threshold (WATCH) |
