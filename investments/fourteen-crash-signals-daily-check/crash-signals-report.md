# 14 Crash Signals — Daily Check

What this is: 14 historical market-crash warning markers, checked daily so an early warning doesn't slip by unnoticed.

Auto-generated daily -- overwritten every run. Advisor notes only; no trade action is ever suggested here (see SOUL.md). Per-marker source: investments/my-trader/14-signals-crash-warning-handoff.md.

## Run: 2026-10-22

## Hot Company Watchlist (shared input for markers 1-4, 8, 10-13)
Dynamically recomputed every run from currently-rising GICS sectors + S&P 500 mega-cap constituents -- never hardcoded to a fixed ticker list.

| Rank | Ticker | Sector | Market Cap |
|------|--------|--------|------------|
| 1 | NVDA | Technology | $5360B |
| 2 | AAPL | Technology | $5020B |
| 3 | GOOGL | Communication Services | $4094B |
| 4 | GOOG | Communication Services | $4047B |
| 5 | MSFT | Technology | $3957B |
| 6 | AMZN | Consumer Discretionary | $2830B |
| 7 | META | Communication Services | $1777B |
| 8 | AVGO | Technology | $1613B |
| 9 | TSLA | Consumer Discretionary | $1526B |
| 10 | LLY | Health Care | $1133B |

## Markers

| # | Marker | Status | Detail |
|---|--------|--------|--------|
| 1 | Record debt issuance, hot sector (NVDA) | flag | NVDA: 3 debt-prospectus filing(s) in the trailing 180d (own 730d average: 0.7/period) -- counts filing events, not dollar principal |
| 1 | Record debt issuance, hot sector (GOOGL) | flag | GOOGL: 23 debt-prospectus filing(s) in the trailing 180d (own 730d average: 10.1/period) -- counts filing events, not dollar principal |
| 1 | Record debt issuance, hot sector (GOOG) | flag | GOOG: 23 debt-prospectus filing(s) in the trailing 180d (own 730d average: 10.1/period) -- counts filing events, not dollar principal |
| 1 | Record debt issuance, hot sector (MSFT) | ok | MSFT: 0 debt-prospectus filing(s) in the trailing 180d (own 730d average: 0.0/period) -- counts filing events, not dollar principal |
| 1 | Record debt issuance, hot sector (AMZN) | flag | AMZN: 9 debt-prospectus filing(s) in the trailing 180d (own 730d average: 4.4/period) -- counts filing events, not dollar principal |
| 1 | Record debt issuance, hot sector (META) | flag | META: 3 debt-prospectus filing(s) in the trailing 180d (own 730d average: 1.5/period) -- counts filing events, not dollar principal |
| 1 | Record debt issuance, hot sector (AVGO) | ok | AVGO: 0 debt-prospectus filing(s) in the trailing 180d (own 730d average: 3.0/period) -- counts filing events, not dollar principal |
| 1 | Record debt issuance, hot sector (TSLA) | ok | TSLA: 0 debt-prospectus filing(s) in the trailing 180d (own 730d average: 0.0/period) -- counts filing events, not dollar principal |
| 1 | Record debt issuance, hot sector (LLY) | ok | LLY: 3 debt-prospectus filing(s) in the trailing 180d (own 730d average: 2.2/period) -- counts filing events, not dollar principal |
| 2 | Debt moves off balance sheet (GOOGL) | ok | GOOGL: $91.0B uncommenced lease commitments (+0.0% since last filing, 10-Q filed 2026-07-23) |
| 2 | Debt moves off balance sheet (GOOG) | ok | GOOG: $91.0B uncommenced lease commitments (+0.0% since last filing, 10-Q filed 2026-07-23) |
| 2 | Debt moves off balance sheet (AMZN) | ok | AMZN: $0.0B uncommenced lease commitments (+0.0% since last filing, 10-Q filed 2026-07-31) |
| 2 | Debt moves off balance sheet (META) | ok | META: $279.0B uncommenced lease commitments (+0.0% since last filing, 10-Q filed 2026-07-30) |
| 3 | Seller finances buyer | unknown | No automatable source exists for vendor/circular-financing deals -- periodically news-scan the current hot watchlist yourself: NVDA, AAPL, GOOGL, GOOG, MSFT, AMZN, META, AVGO, TSLA, LLY |
| 4 | Capex outruns cash flow (NVDA) | ok | NVDA: Free Cash Flow $+96.7B, Capital Expenditure $6.0B (period ending 2026-01-31) |
| 4 | Capex outruns cash flow (AAPL) | ok | AAPL: Free Cash Flow $+98.8B, Capital Expenditure $12.7B (period ending 2025-09-30) |
| 4 | Capex outruns cash flow (GOOGL) | ok | GOOGL: Free Cash Flow $+73.3B, Capital Expenditure $91.4B (period ending 2025-12-31) |
| 4 | Capex outruns cash flow (GOOG) | ok | GOOG: Free Cash Flow $+73.3B, Capital Expenditure $91.4B (period ending 2025-12-31) |
| 4 | Capex outruns cash flow (MSFT) | ok | MSFT: Free Cash Flow $+67.0B, Capital Expenditure $115.9B (period ending 2026-06-30) |
| 4 | Capex outruns cash flow (AMZN) | ok | AMZN: Free Cash Flow $+7.7B, Capital Expenditure $131.8B (period ending 2025-12-31) |
| 4 | Capex outruns cash flow (META) | ok | META: Free Cash Flow $+46.1B, Capital Expenditure $69.7B (period ending 2025-12-31) |
| 4 | Capex outruns cash flow (AVGO) | ok | AVGO: Free Cash Flow $+26.9B, Capital Expenditure $0.6B (period ending 2025-10-31) |
| 4 | Capex outruns cash flow (TSLA) | ok | TSLA: Free Cash Flow $+6.2B, Capital Expenditure $8.5B (period ending 2025-12-31) |
| 4 | Capex outruns cash flow (LLY) | ok | LLY: Free Cash Flow $+6.0B, Capital Expenditure $10.8B (period ending 2025-12-31) |
| 5 | Margin debt YoY growth | ok | Margin debt $1.48T as of 2026-09-01, +31.4% YoY vs 2025-09-01 |
| 6 | Record IPO/equity issuance | ok | S-1 (intent to register): 156 filing(s) in the trailing 30d vs 292 in the same window a year ago (0.53x); 424B4 (priced IPO): 25 filing(s) in the trailing 30d vs 54 in the same window a year ago (0.46x) |
| 7 | Retail piles into leverage | ok | Equity put/call ratio 0.56 (z=-0.21 vs trailing 62d mean 0.57) -- options positioning proxy, not the video's ETF/fund-flow mechanism |
| 8 | Insider selling (NVDA) | flag | NVDA: $1,867,951,168 sold vs $0 bought, trailing 365 days |
| 8 | Insider selling (AAPL) | flag | AAPL: $207,419,324 sold vs $0 bought, trailing 365 days |
| 8 | Insider selling (GOOGL) | flag | GOOGL: $121,566,706 sold vs $0 bought, trailing 365 days |
| 8 | Insider selling (MSFT) | flag | MSFT: $100,274,637 sold vs $3,436,971 bought, trailing 365 days |
| 8 | Insider selling (AMZN) | flag | AMZN: $448,478,458 sold vs $0 bought, trailing 365 days |
| 8 | Insider selling (META) | flag | META: $259,220,154 sold vs $0 bought, trailing 365 days |
| 8 | Insider selling (AVGO) | flag | AVGO: $1,153,379,764 sold vs $698,699 bought, trailing 365 days |
| 8 | Insider selling (TSLA) | flag | TSLA: $87,688,429 sold vs $0 bought, trailing 365 days |
| 8 | Insider selling (LLY) | flag | LLY: $515,909,991 sold vs $0 bought, trailing 365 days |
| 9 | The Super Bowl signal | unknown | Next Super Bowl is 2027-02-14 (115 day(s) away) -- ad-share content is not automatable, nothing to check yet |
| 10 | Most-valuable-company milestone | flag | NVDA is the largest company in the current hot-sector watchlist ($5.36T, most recently crossed the $5.0T rung) |
| 11 | Regulators sound the alarm | ok | No new matching regulator statements this run. |
| 12 | Credit turns in the hot sector while broad market stays calm (AAPL) | unknown | AAPL: bond CUSIP 037833EY2 found, but no live or manually-entered yield reading available -- run `record-bond-yield AAPL <yield_pct>` |
| 12 | Credit turns in the hot sector while broad market stays calm (AMZN) | unknown | AMZN: bond CUSIP 023135EA0 found, but no live or manually-entered yield reading available -- run `record-bond-yield AMZN <yield_pct>` |
| 13 | Funding markets start choking | unknown | FRED commercial-paper/Treasury spread data unavailable (FRED_API_KEY not set, series unavailable, or insufficient history) |
| 14 | High-yield credit spread streak | unknown | FRED high-yield credit spread data unavailable (FRED_API_KEY not set, or series unavailable) |
