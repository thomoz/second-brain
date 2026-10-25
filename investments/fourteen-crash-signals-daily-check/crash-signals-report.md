# 14 Crash Signals — Daily Check

What this is: 14 historical market-crash warning markers, checked daily so an early warning doesn't slip by unnoticed.

Auto-generated daily -- overwritten every run. Advisor notes only; no trade action is ever suggested here (see SOUL.md). Per-marker source: investments/my-trader/14-signals-crash-warning-handoff.md.

## Run: 2026-10-26

## Hot Company Watchlist (shared input for markers 1-4, 8, 10-13)
Dynamically recomputed every run from currently-rising GICS sectors + S&P 500 mega-cap constituents -- never hardcoded to a fixed ticker list.

| Rank | Ticker | Sector | Market Cap |
|------|--------|--------|------------|
| 1 | NVDA | Technology | $5094B |
| 2 | AAPL | Technology | $5075B |
| 3 | MSFT | Technology | $3895B |
| 4 | AMZN | Consumer Discretionary | $2675B |
| 5 | AVGO | Technology | $1536B |
| 6 | TSLA | Consumer Discretionary | $1471B |
| 7 | LLY | Health Care | $1136B |
| 8 | MU | Technology | $993B |
| 9 | WMT | Consumer Staples | $954B |
| 10 | AMD | Technology | $844B |

## Markers

| # | Marker | Status | Detail |
|---|--------|--------|--------|
| 1 | Record debt issuance, hot sector (NVDA) | flag | NVDA: 3 debt-prospectus filing(s) in the trailing 180d (own 730d average: 0.7/period) -- counts filing events, not dollar principal |
| 1 | Record debt issuance, hot sector (AAPL) | ok | AAPL: 0 debt-prospectus filing(s) in the trailing 180d (own 730d average: 0.7/period) -- counts filing events, not dollar principal |
| 1 | Record debt issuance, hot sector (MSFT) | ok | MSFT: 0 debt-prospectus filing(s) in the trailing 180d (own 730d average: 0.0/period) -- counts filing events, not dollar principal |
| 1 | Record debt issuance, hot sector (AMZN) | flag | AMZN: 9 debt-prospectus filing(s) in the trailing 180d (own 730d average: 4.4/period) -- counts filing events, not dollar principal |
| 1 | Record debt issuance, hot sector (AVGO) | ok | AVGO: 0 debt-prospectus filing(s) in the trailing 180d (own 730d average: 3.0/period) -- counts filing events, not dollar principal |
| 1 | Record debt issuance, hot sector (TSLA) | ok | TSLA: 0 debt-prospectus filing(s) in the trailing 180d (own 730d average: 0.0/period) -- counts filing events, not dollar principal |
| 1 | Record debt issuance, hot sector (LLY) | ok | LLY: 3 debt-prospectus filing(s) in the trailing 180d (own 730d average: 2.2/period) -- counts filing events, not dollar principal |
| 1 | Record debt issuance, hot sector (MU) | ok | MU: 0 debt-prospectus filing(s) in the trailing 180d (own 730d average: 1.5/period) -- counts filing events, not dollar principal |
| 1 | Record debt issuance, hot sector (WMT) | flag | WMT: 8 debt-prospectus filing(s) in the trailing 180d (own 730d average: 3.0/period) -- counts filing events, not dollar principal |
| 1 | Record debt issuance, hot sector (AMD) | flag | AMD: 3 debt-prospectus filing(s) in the trailing 180d (own 730d average: 1.5/period) -- counts filing events, not dollar principal |
| 2 | Debt moves off balance sheet (AMZN) | ok | AMZN: $0.0B uncommenced lease commitments (+0.0% since last filing, 10-Q filed 2026-07-31) |
| 2 | Debt moves off balance sheet (AMD) | ok | AMD: $4.5B uncommenced lease commitments (+0.0% since last filing, 10-Q filed 2026-08-05) |
| 3 | Seller finances buyer | unknown | No automatable source exists for vendor/circular-financing deals -- periodically news-scan the current hot watchlist yourself: NVDA, AAPL, MSFT, AMZN, AVGO, TSLA, LLY, MU, WMT, AMD |
| 4 | Capex outruns cash flow (NVDA) | ok | NVDA: Free Cash Flow $+96.7B, Capital Expenditure $6.0B (period ending 2026-01-31) |
| 4 | Capex outruns cash flow (AAPL) | ok | AAPL: Free Cash Flow $+98.8B, Capital Expenditure $12.7B (period ending 2025-09-30) |
| 4 | Capex outruns cash flow (MSFT) | ok | MSFT: Free Cash Flow $+67.0B, Capital Expenditure $115.9B (period ending 2026-06-30) |
| 4 | Capex outruns cash flow (AMZN) | ok | AMZN: Free Cash Flow $+7.7B, Capital Expenditure $131.8B (period ending 2025-12-31) |
| 4 | Capex outruns cash flow (AVGO) | ok | AVGO: Free Cash Flow $+26.9B, Capital Expenditure $0.6B (period ending 2025-10-31) |
| 4 | Capex outruns cash flow (TSLA) | ok | TSLA: Free Cash Flow $+6.2B, Capital Expenditure $8.5B (period ending 2025-12-31) |
| 4 | Capex outruns cash flow (LLY) | ok | LLY: Free Cash Flow $+6.0B, Capital Expenditure $10.8B (period ending 2025-12-31) |
| 4 | Capex outruns cash flow (MU) | ok | MU: Free Cash Flow $+59.0B, Capital Expenditure $30.7B (period ending 2026-08-31) |
| 4 | Capex outruns cash flow (WMT) | ok | WMT: Free Cash Flow $+14.9B, Capital Expenditure $26.6B (period ending 2026-01-31) |
| 4 | Capex outruns cash flow (AMD) | ok | AMD: Free Cash Flow $+6.7B, Capital Expenditure $1.0B (period ending 2025-12-31) |
| 5 | Margin debt YoY growth | ok | Margin debt $1.48T as of 2026-09-01, +31.4% YoY vs 2025-09-01 |
| 6 | Record IPO/equity issuance | ok | S-1 (intent to register): 152 filing(s) in the trailing 30d vs 283 in the same window a year ago (0.54x); 424B4 (priced IPO): 23 filing(s) in the trailing 30d vs 54 in the same window a year ago (0.43x) |
| 7 | Retail piles into leverage | ok | Equity put/call ratio 0.67 (z=1.41 vs trailing 65d mean 0.58) -- options positioning proxy, not the video's ETF/fund-flow mechanism |
| 8 | Insider selling (NVDA) | flag | NVDA: $1,867,951,168 sold vs $0 bought, trailing 365 days |
| 8 | Insider selling (AAPL) | flag | AAPL: $208,234,072 sold vs $0 bought, trailing 365 days |
| 8 | Insider selling (MSFT) | flag | MSFT: $100,274,637 sold vs $3,436,971 bought, trailing 365 days |
| 8 | Insider selling (AMZN) | flag | AMZN: $448,478,458 sold vs $0 bought, trailing 365 days |
| 8 | Insider selling (AVGO) | flag | AVGO: $1,153,379,764 sold vs $698,699 bought, trailing 365 days |
| 8 | Insider selling (TSLA) | flag | TSLA: $87,688,429 sold vs $0 bought, trailing 365 days |
| 8 | Insider selling (LLY) | flag | LLY: $293,939,049 sold vs $0 bought, trailing 365 days |
| 8 | Insider selling (MU) | flag | MU: $246,511,451 sold vs $7,821,723 bought, trailing 365 days |
| 8 | Insider selling (WMT) | flag | WMT: $2,946,762,004 sold vs $0 bought, trailing 365 days |
| 8 | Insider selling (AMD) | flag | AMD: $378,082,091 sold vs $0 bought, trailing 365 days |
| 9 | The Super Bowl signal | unknown | Next Super Bowl is 2027-02-14 (112 day(s) away) -- ad-share content is not automatable, nothing to check yet |
| 10 | Most-valuable-company milestone | flag | NVDA is the largest company in the current hot-sector watchlist ($5.09T, most recently crossed the $5.0T rung) |
| 11 | Regulators sound the alarm | ok | No new matching regulator statements this run. |
| 12 | Credit turns in the hot sector while broad market stays calm (AAPL) | unknown | AAPL: bond CUSIP 037833EY2 found, but no live or manually-entered yield reading available -- run `record-bond-yield AAPL <yield_pct>` |
| 12 | Credit turns in the hot sector while broad market stays calm (AMZN) | unknown | AMZN: bond CUSIP 023135EA0 found, but no live or manually-entered yield reading available -- run `record-bond-yield AMZN <yield_pct>` |
| 12 | Credit turns in the hot sector while broad market stays calm (MU) | unknown | MU: bond CUSIP 595112CG6 found, but no live or manually-entered yield reading available -- run `record-bond-yield MU <yield_pct>` |
| 13 | Funding markets start choking | ok | CP-Treasury spread (DCPN3M-DTB3) 0.00pp (z=-1.06 vs trailing 365d) |
| 14 | High-yield credit spread streak | ok | ICE BofA US HY OAS at 3.40pp (as of 2026-10-22); 0 consecutive day(s) at/above 3.5pp (needs 21 to flag) -- WATCH: within 0.3pp of the flag threshold (WATCH) |
