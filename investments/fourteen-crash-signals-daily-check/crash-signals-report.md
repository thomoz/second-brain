# 14 Crash Signals — Daily Check

What this is: 14 historical market-crash warning markers, checked daily so an early warning doesn't slip by unnoticed.

Auto-generated daily -- overwritten every run. Advisor notes only; no trade action is ever suggested here (see SOUL.md). Per-marker source: investments/my-trader/14-signals-crash-warning-handoff.md.

## Run: 2026-10-31

## Hot Company Watchlist (shared input for markers 1-4, 8, 10-13)
Dynamically recomputed every run from currently-rising GICS sectors + S&P 500 mega-cap constituents -- never hardcoded to a fixed ticker list.

| Rank | Ticker | Sector | Market Cap |
|------|--------|--------|------------|
| 1 | AAPL | Technology | $5030B |
| 2 | NVDA | Technology | $4941B |
| 3 | MSFT | Technology | $3876B |
| 4 | AVGO | Technology | $1557B |
| 5 | LLY | Health Care | $1263B |
| 6 | MU | Technology | $1001B |
| 7 | WMT | Consumer Staples | $983B |
| 8 | AMD | Technology | $824B |
| 9 | XOM | Energy | $770B |
| 10 | JNJ | Health Care | $658B |

## Markers

| # | Marker | Status | Detail |
|---|--------|--------|--------|
| 1 | Record debt issuance, hot sector (AAPL) | ok | AAPL: 0 debt-prospectus filing(s) in the trailing 180d (own 730d average: 0.7/period) -- counts filing events, not dollar principal |
| 1 | Record debt issuance, hot sector (NVDA) | flag | NVDA: 3 debt-prospectus filing(s) in the trailing 180d (own 730d average: 0.7/period) -- counts filing events, not dollar principal |
| 1 | Record debt issuance, hot sector (MSFT) | flag | MSFT: 2 debt-prospectus filing(s) in the trailing 180d (own 730d average: 0.5/period) -- counts filing events, not dollar principal |
| 1 | Record debt issuance, hot sector (AVGO) | ok | AVGO: 0 debt-prospectus filing(s) in the trailing 180d (own 730d average: 3.0/period) -- counts filing events, not dollar principal |
| 1 | Record debt issuance, hot sector (LLY) | ok | LLY: 3 debt-prospectus filing(s) in the trailing 180d (own 730d average: 2.2/period) -- counts filing events, not dollar principal |
| 1 | Record debt issuance, hot sector (MU) | ok | MU: 0 debt-prospectus filing(s) in the trailing 180d (own 730d average: 1.5/period) -- counts filing events, not dollar principal |
| 1 | Record debt issuance, hot sector (WMT) | flag | WMT: 6 debt-prospectus filing(s) in the trailing 180d (own 730d average: 3.0/period) -- counts filing events, not dollar principal |
| 1 | Record debt issuance, hot sector (AMD) | flag | AMD: 3 debt-prospectus filing(s) in the trailing 180d (own 730d average: 1.5/period) -- counts filing events, not dollar principal |
| 1 | Record debt issuance, hot sector (XOM) | flag | XOM: 2 debt-prospectus filing(s) in the trailing 180d (own 730d average: 0.5/period) -- counts filing events, not dollar principal |
| 1 | Record debt issuance, hot sector (JNJ) | ok | JNJ: 0 debt-prospectus filing(s) in the trailing 180d (own 730d average: 1.5/period) -- counts filing events, not dollar principal |
| 2 | Debt moves off balance sheet (AMD) | ok | AMD: $4.5B uncommenced lease commitments (+0.0% since last filing, 10-Q filed 2026-08-05) |
| 3 | Seller finances buyer | unknown | No automatable source exists for vendor/circular-financing deals -- periodically news-scan the current hot watchlist yourself: AAPL, NVDA, MSFT, AVGO, LLY, MU, WMT, AMD, XOM, JNJ |
| 4 | Capex outruns cash flow (AAPL) | ok | AAPL: Free Cash Flow $+98.8B, Capital Expenditure $12.7B (period ending 2025-09-30) |
| 4 | Capex outruns cash flow (NVDA) | ok | NVDA: Free Cash Flow $+96.7B, Capital Expenditure $6.0B (period ending 2026-01-31) |
| 4 | Capex outruns cash flow (MSFT) | ok | MSFT: Free Cash Flow $+67.0B, Capital Expenditure $115.9B (period ending 2026-06-30) |
| 4 | Capex outruns cash flow (AVGO) | ok | AVGO: Free Cash Flow $+26.9B, Capital Expenditure $0.6B (period ending 2025-10-31) |
| 4 | Capex outruns cash flow (LLY) | ok | LLY: Free Cash Flow $+6.0B, Capital Expenditure $10.8B (period ending 2025-12-31) |
| 4 | Capex outruns cash flow (MU) | ok | MU: Free Cash Flow $+59.0B, Capital Expenditure $30.7B (period ending 2026-08-31) |
| 4 | Capex outruns cash flow (WMT) | ok | WMT: Free Cash Flow $+14.9B, Capital Expenditure $26.6B (period ending 2026-01-31) |
| 4 | Capex outruns cash flow (AMD) | ok | AMD: Free Cash Flow $+6.7B, Capital Expenditure $1.0B (period ending 2025-12-31) |
| 4 | Capex outruns cash flow (XOM) | ok | XOM: Free Cash Flow $+23.6B, Capital Expenditure $28.4B (period ending 2025-12-31) |
| 4 | Capex outruns cash flow (JNJ) | ok | JNJ: Free Cash Flow $+19.3B, Capital Expenditure $5.2B (period ending 2025-12-31) |
| 5 | Margin debt YoY growth | ok | Margin debt $1.48T as of 2026-09-01, +31.4% YoY vs 2025-09-01 |
| 6 | Record IPO/equity issuance | ok | S-1 (intent to register): 180 filing(s) in the trailing 30d vs 252 in the same window a year ago (0.71x); 424B4 (priced IPO): 25 filing(s) in the trailing 30d vs 49 in the same window a year ago (0.51x) |
| 7 | Retail piles into leverage | ok | Equity put/call ratio 0.58 (z=0.02 vs trailing 71d mean 0.58) -- options positioning proxy, not the video's ETF/fund-flow mechanism |
| 8 | Insider selling (AAPL) | flag | AAPL: $209,057,793 sold vs $0 bought, trailing 365 days |
| 8 | Insider selling (NVDA) | flag | NVDA: $1,883,073,827 sold vs $0 bought, trailing 365 days |
| 8 | Insider selling (MSFT) | flag | MSFT: $120,242,344 sold vs $3,436,971 bought, trailing 365 days |
| 8 | Insider selling (AVGO) | flag | AVGO: $1,153,379,764 sold vs $698,699 bought, trailing 365 days |
| 8 | Insider selling (LLY) | flag | LLY: $1,043,202,981 sold vs $0 bought, trailing 365 days |
| 8 | Insider selling (MU) | flag | MU: $283,018,302 sold vs $7,821,723 bought, trailing 365 days |
| 8 | Insider selling (WMT) | flag | WMT: $2,946,984,606 sold vs $0 bought, trailing 365 days |
| 8 | Insider selling (AMD) | flag | AMD: $378,082,091 sold vs $0 bought, trailing 365 days |
| 8 | Insider selling (XOM) | flag | XOM: $2,395,656 sold vs $0 bought, trailing 365 days |
| 8 | Insider selling (JNJ) | flag | JNJ: $150,667,262 sold vs $257,688 bought, trailing 365 days |
| 9 | The Super Bowl signal | unknown | Next Super Bowl is 2027-02-14 (107 day(s) away) -- ad-share content is not automatable, nothing to check yet |
| 10 | Most-valuable-company milestone | flag | AAPL is the largest company in the current hot-sector watchlist ($5.03T, most recently crossed the $5.0T rung) |
| 11 | Regulators sound the alarm | flag | SEC Issues Exemptive Relief from Treasury Clearing Requirements for Certain Inter-Affiliate and Non-U.S. Repo Transactions (https://www.sec.gov/newsroom/press-releases/2026-111-sec-issues-exemptive-relief-treasury-clearing-requirements-certain-inter-affiliate-non-us-repo) |
| 12 | Credit turns in the hot sector while broad market stays calm (AAPL) | unknown | AAPL: bond CUSIP 037833EY2 found, but no live or manually-entered yield reading available -- run `record-bond-yield AAPL <yield_pct>` |
| 12 | Credit turns in the hot sector while broad market stays calm (MU) | unknown | MU: bond CUSIP 595112CG6 found, but no live or manually-entered yield reading available -- run `record-bond-yield MU <yield_pct>` |
| 12 | Credit turns in the hot sector while broad market stays calm (JNJ) | unknown | JNJ: bond CUSIP 478160CY8 found, but no live or manually-entered yield reading available -- run `record-bond-yield JNJ <yield_pct>` |
| 13 | Funding markets start choking | ok | CP-Treasury spread (DCPN3M-DTB3) 0.00pp (z=-1.03 vs trailing 365d) |
| 14 | High-yield credit spread streak | ok | ICE BofA US HY OAS at 3.26pp (as of 2026-10-29); 0 consecutive day(s) at/above 3.5pp (needs 21 to flag) -- WATCH: within 0.3pp of the flag threshold (WATCH) |
