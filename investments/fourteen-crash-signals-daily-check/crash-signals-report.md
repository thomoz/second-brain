# 14 Crash Signals — Daily Check

What this is: 14 historical market-crash warning markers, checked daily so an early warning doesn't slip by unnoticed.

Auto-generated daily -- overwritten every run. Advisor notes only; no trade action is ever suggested here (see SOUL.md). Per-marker source: investments/my-trader/14-signals-crash-warning-handoff.md.

## Run: 2026-09-26

## Hot Company Watchlist (shared input for markers 1-4, 8, 10-13)
Dynamically recomputed every run from currently-rising GICS sectors + S&P 500 mega-cap constituents -- never hardcoded to a fixed ticker list.

| Rank | Ticker | Sector | Market Cap |
|------|--------|--------|------------|
| 1 | NVDA | Technology | $5435B |
| 2 | AAPL | Technology | $4978B |
| 3 | GOOGL | Communication Services | $4206B |
| 4 | GOOG | Communication Services | $4171B |
| 5 | MSFT | Technology | $3833B |
| 6 | META | Communication Services | $1915B |
| 7 | AVGO | Technology | $1684B |
| 8 | MU | Technology | $1222B |
| 9 | BRK-B | Financials | $1082B |
| 10 | LLY | Health Care | $1055B |

## Markers

| # | Marker | Status | Detail |
|---|--------|--------|--------|
| 1 | Record debt issuance, hot sector (NVDA) | flag | NVDA: 3 debt-prospectus filing(s) in the trailing 180d (own 730d average: 0.7/period) -- counts filing events, not dollar principal |
| 1 | Record debt issuance, hot sector (AAPL) | ok | AAPL: 0 debt-prospectus filing(s) in the trailing 180d (own 730d average: 0.7/period) -- counts filing events, not dollar principal |
| 1 | Record debt issuance, hot sector (GOOGL) | flag | GOOGL: 23 debt-prospectus filing(s) in the trailing 180d (own 730d average: 10.1/period) -- counts filing events, not dollar principal |
| 1 | Record debt issuance, hot sector (GOOG) | flag | GOOG: 23 debt-prospectus filing(s) in the trailing 180d (own 730d average: 10.1/period) -- counts filing events, not dollar principal |
| 1 | Record debt issuance, hot sector (MSFT) | ok | MSFT: 0 debt-prospectus filing(s) in the trailing 180d (own 730d average: 0.0/period) -- counts filing events, not dollar principal |
| 1 | Record debt issuance, hot sector (META) | flag | META: 3 debt-prospectus filing(s) in the trailing 180d (own 730d average: 1.5/period) -- counts filing events, not dollar principal |
| 1 | Record debt issuance, hot sector (AVGO) | ok | AVGO: 0 debt-prospectus filing(s) in the trailing 180d (own 730d average: 3.7/period) -- counts filing events, not dollar principal |
| 1 | Record debt issuance, hot sector (MU) | ok | MU: 0 debt-prospectus filing(s) in the trailing 180d (own 730d average: 1.5/period) -- counts filing events, not dollar principal |
| 1 | Record debt issuance, hot sector (BRK-B) | ok | BRK-B: 3 debt-prospectus filing(s) in the trailing 180d (own 730d average: 3.0/period) -- counts filing events, not dollar principal |
| 1 | Record debt issuance, hot sector (LLY) | ok | LLY: 3 debt-prospectus filing(s) in the trailing 180d (own 730d average: 2.2/period) -- counts filing events, not dollar principal |
| 2 | Debt moves off balance sheet (GOOGL) | ok | GOOGL: $91.0B uncommenced lease commitments (+0.0% since last filing, 10-Q filed 2026-07-23) |
| 2 | Debt moves off balance sheet (GOOG) | ok | GOOG: $91.0B uncommenced lease commitments (+0.0% since last filing, 10-Q filed 2026-07-23) |
| 2 | Debt moves off balance sheet (META) | ok | META: $279.0B uncommenced lease commitments (+0.0% since last filing, 10-Q filed 2026-07-30) |
| 3 | Seller finances buyer | unknown | No automatable source exists for vendor/circular-financing deals -- periodically news-scan the current hot watchlist yourself: NVDA, AAPL, GOOGL, GOOG, MSFT, META, AVGO, MU, BRK-B, LLY |
| 4 | Capex outruns cash flow | ok | No hot-watchlist tickers with a resolvable cash-flow statement this run. |
| 5 | Margin debt YoY growth | ok | Margin debt $1.45T as of 2026-08-01, +37.2% YoY vs 2025-08-01 |
| 6 | Record IPO/equity issuance | ok | S-1 (intent to register): 176 filing(s) in the trailing 30d vs 305 in the same window a year ago (0.58x); 424B4 (priced IPO): 25 filing(s) in the trailing 30d vs 52 in the same window a year ago (0.48x) |
| 7 | Retail piles into leverage | ok | Equity put/call ratio 0.52 (z=-0.78 vs trailing 38d mean 0.57) -- options positioning proxy, not the video's ETF/fund-flow mechanism |
| 8 | Insider selling (?) | unknown | OpenInsider fetch failed for both purchases and sales |
| 9 | The Super Bowl signal | unknown | Next Super Bowl is 2027-02-14 (141 day(s) away) -- ad-share content is not automatable, nothing to check yet |
| 10 | Most-valuable-company milestone | flag | NVDA is the largest company in the current hot-sector watchlist ($5.43T, most recently crossed the $5.0T rung) |
| 11 | Regulators sound the alarm | ok | No new matching regulator statements this run. |
| 12 | Credit turns in the hot sector while broad market stays calm (AAPL) | unknown | AAPL: bond CUSIP 037833EY2 found, but no live or manually-entered yield reading available -- run `record-bond-yield AAPL <yield_pct>` |
| 12 | Credit turns in the hot sector while broad market stays calm (MU) | unknown | MU: bond CUSIP 595112CG6 found, but no live or manually-entered yield reading available -- run `record-bond-yield MU <yield_pct>` |
| 12 | Credit turns in the hot sector while broad market stays calm (BRK-B) | unknown | BRK-B: bond CUSIP 084670EB0 found, but no live or manually-entered yield reading available -- run `record-bond-yield BRK-B <yield_pct>` |
| 13 | Funding markets start choking | ok | CP-Treasury spread (DCPN3M-DTB3) 0.06pp (z=-0.05 vs trailing 365d) |
| 14 | High-yield credit spread streak | ok | ICE BofA US HY OAS at 2.80pp (as of 2026-09-24); 0 consecutive day(s) at/above 3.5pp (needs 21 to flag) |
