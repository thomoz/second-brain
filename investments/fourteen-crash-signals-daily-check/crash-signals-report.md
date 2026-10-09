# 14 Crash Signals — Daily Check

What this is: 14 historical market-crash warning markers, checked daily so an early warning doesn't slip by unnoticed.

Auto-generated daily -- overwritten every run. Advisor notes only; no trade action is ever suggested here (see SOUL.md). Per-marker source: investments/my-trader/14-signals-crash-warning-handoff.md.

## Run: 2026-10-10

## Hot Company Watchlist (shared input for markers 1-4, 8, 10-13)
Dynamically recomputed every run from currently-rising GICS sectors + S&P 500 mega-cap constituents -- never hardcoded to a fixed ticker list.

| Rank | Ticker | Sector | Market Cap |
|------|--------|--------|------------|
| 1 | NVDA | Technology | $5536B |
| 2 | AAPL | Technology | $4913B |
| 3 | MSFT | Technology | $3973B |
| 4 | AVGO | Technology | $1726B |
| 5 | MU | Technology | $1162B |
| 6 | LLY | Health Care | $1052B |
| 7 | AMD | Technology | $993B |
| 8 | XOM | Energy | $695B |
| 9 | JNJ | Health Care | $630B |
| 10 | INTC | Technology | $553B |

## Markers

| # | Marker | Status | Detail |
|---|--------|--------|--------|
| 1 | Record debt issuance, hot sector (NVDA) | flag | NVDA: 3 debt-prospectus filing(s) in the trailing 180d (own 730d average: 0.7/period) -- counts filing events, not dollar principal |
| 1 | Record debt issuance, hot sector (AAPL) | ok | AAPL: 0 debt-prospectus filing(s) in the trailing 180d (own 730d average: 0.7/period) -- counts filing events, not dollar principal |
| 1 | Record debt issuance, hot sector (MSFT) | ok | MSFT: 0 debt-prospectus filing(s) in the trailing 180d (own 730d average: 0.0/period) -- counts filing events, not dollar principal |
| 1 | Record debt issuance, hot sector (AVGO) | ok | AVGO: 0 debt-prospectus filing(s) in the trailing 180d (own 730d average: 3.0/period) -- counts filing events, not dollar principal |
| 1 | Record debt issuance, hot sector (MU) | ok | MU: 0 debt-prospectus filing(s) in the trailing 180d (own 730d average: 1.5/period) -- counts filing events, not dollar principal |
| 1 | Record debt issuance, hot sector (LLY) | ok | LLY: 3 debt-prospectus filing(s) in the trailing 180d (own 730d average: 2.2/period) -- counts filing events, not dollar principal |
| 1 | Record debt issuance, hot sector (AMD) | flag | AMD: 3 debt-prospectus filing(s) in the trailing 180d (own 730d average: 1.5/period) -- counts filing events, not dollar principal |
| 1 | Record debt issuance, hot sector (XOM) | flag | XOM: 2 debt-prospectus filing(s) in the trailing 180d (own 730d average: 0.5/period) -- counts filing events, not dollar principal |
| 1 | Record debt issuance, hot sector (JNJ) | ok | JNJ: 0 debt-prospectus filing(s) in the trailing 180d (own 730d average: 1.5/period) -- counts filing events, not dollar principal |
| 1 | Record debt issuance, hot sector (INTC) | flag | INTC: 7 debt-prospectus filing(s) in the trailing 180d (own 730d average: 1.7/period) -- counts filing events, not dollar principal |
| 2 | Debt moves off balance sheet (AMD) | ok | AMD: $4.5B uncommenced lease commitments (+0.0% since last filing, 10-Q filed 2026-08-05) |
| 3 | Seller finances buyer | unknown | No automatable source exists for vendor/circular-financing deals -- periodically news-scan the current hot watchlist yourself: NVDA, AAPL, MSFT, AVGO, MU, LLY, AMD, XOM, JNJ, INTC |
| 4 | Capex outruns cash flow (NVDA) | ok | NVDA: Free Cash Flow $+96.7B, Capital Expenditure $6.0B (period ending 2026-01-31) |
| 4 | Capex outruns cash flow (AAPL) | ok | AAPL: Free Cash Flow $+98.8B, Capital Expenditure $12.7B (period ending 2025-09-30) |
| 4 | Capex outruns cash flow (MSFT) | ok | MSFT: Free Cash Flow $+67.0B, Capital Expenditure $115.9B (period ending 2026-06-30) |
| 4 | Capex outruns cash flow (AVGO) | ok | AVGO: Free Cash Flow $+26.9B, Capital Expenditure $0.6B (period ending 2025-10-31) |
| 4 | Capex outruns cash flow (MU) | ok | MU: Free Cash Flow $+1.7B, Capital Expenditure $15.9B (period ending 2025-08-31) |
| 4 | Capex outruns cash flow (LLY) | ok | LLY: Free Cash Flow $+6.0B, Capital Expenditure $10.8B (period ending 2025-12-31) |
| 4 | Capex outruns cash flow (AMD) | ok | AMD: Free Cash Flow $+6.7B, Capital Expenditure $1.0B (period ending 2025-12-31) |
| 4 | Capex outruns cash flow (XOM) | ok | XOM: Free Cash Flow $+23.6B, Capital Expenditure $28.4B (period ending 2025-12-31) |
| 4 | Capex outruns cash flow (JNJ) | ok | JNJ: Free Cash Flow $+19.3B, Capital Expenditure $5.2B (period ending 2025-12-31) |
| 4 | Capex outruns cash flow (INTC) | flag | INTC: Free Cash Flow $-4.9B, Capital Expenditure $14.6B (period ending 2025-12-31) |
| 5 | Margin debt YoY growth | ok | Margin debt $1.45T as of 2026-08-01, +37.2% YoY vs 2025-08-01 |
| 6 | Record IPO/equity issuance | ok | S-1 (intent to register): 200 filing(s) in the trailing 30d vs 315 in the same window a year ago (0.63x); 424B4 (priced IPO): 25 filing(s) in the trailing 30d vs 64 in the same window a year ago (0.39x) |
| 7 | Retail piles into leverage | ok | Equity put/call ratio 0.62 (z=0.76 vs trailing 50d mean 0.57) -- options positioning proxy, not the video's ETF/fund-flow mechanism |
| 8 | Insider selling (NVDA) | flag | NVDA: $2,081,291,195 sold vs $0 bought, trailing 365 days |
| 8 | Insider selling (AAPL) | flag | AAPL: $206,708,033 sold vs $0 bought, trailing 365 days |
| 8 | Insider selling (MSFT) | flag | MSFT: $116,258,041 sold vs $3,436,971 bought, trailing 365 days |
| 8 | Insider selling (AVGO) | flag | AVGO: $1,153,659,884 sold vs $698,699 bought, trailing 365 days |
| 8 | Insider selling (MU) | flag | MU: $281,864,063 sold vs $7,821,723 bought, trailing 365 days |
| 8 | Insider selling (LLY) | flag | LLY: $1,055,398,758 sold vs $0 bought, trailing 365 days |
| 8 | Insider selling (AMD) | flag | AMD: $372,516,369 sold vs $0 bought, trailing 365 days |
| 8 | Insider selling (XOM) | flag | XOM: $2,395,656 sold vs $0 bought, trailing 365 days |
| 8 | Insider selling (JNJ) | flag | JNJ: $154,853,055 sold vs $257,688 bought, trailing 365 days |
| 8 | Insider selling (INTC) | ok | INTC: $7,474,217 sold vs $10,249,970 bought, trailing 365 days |
| 9 | The Super Bowl signal | unknown | Next Super Bowl is 2027-02-14 (128 day(s) away) -- ad-share content is not automatable, nothing to check yet |
| 10 | Most-valuable-company milestone | flag | NVDA is the largest company in the current hot-sector watchlist ($5.54T, most recently crossed the $5.5T rung) |
| 11 | Regulators sound the alarm | flag | SEC Proposes Expanding Securities Eligible for Cross Trading by Registered Funds (https://www.sec.gov/newsroom/press-releases/2026-104-sec-proposes-expanding-securities-eligible-cross-trading-registered-funds) |
| 11 | Regulators sound the alarm | flag | Federal Reserve Board releases results of the 2025 Survey of Consumer Finances, which provides the public and policymakers with detailed insights into the economic condition of American families (https://www.federalreserve.gov/newsevents/pressreleases/other20261009a.htm) |
| 12 | Credit turns in the hot sector while broad market stays calm (AAPL) | unknown | AAPL: bond CUSIP 037833EY2 found, but no live or manually-entered yield reading available -- run `record-bond-yield AAPL <yield_pct>` |
| 12 | Credit turns in the hot sector while broad market stays calm (MU) | unknown | MU: bond CUSIP 595112CG6 found, but no live or manually-entered yield reading available -- run `record-bond-yield MU <yield_pct>` |
| 12 | Credit turns in the hot sector while broad market stays calm (JNJ) | unknown | JNJ: bond CUSIP 478160CY8 found, but no live or manually-entered yield reading available -- run `record-bond-yield JNJ <yield_pct>` |
| 12 | Credit turns in the hot sector while broad market stays calm (INTC) | unknown | INTC: bond CUSIP 458140CQ1 found, but no live or manually-entered yield reading available -- run `record-bond-yield INTC <yield_pct>` |
| 13 | Funding markets start choking | ok | CP-Treasury spread (DCPN3M-DTB3) 0.04pp (z=-0.39 vs trailing 365d) |
| 14 | High-yield credit spread streak | ok | ICE BofA US HY OAS at 3.15pp (as of 2026-10-08); 0 consecutive day(s) at/above 3.5pp (needs 21 to flag) |
