# 14 Crash Signals — Daily Check

Auto-generated daily -- overwritten every run. Advisor notes only; no trade action is ever suggested here (see SOUL.md). Per-marker source: investments/my-trader/14-signals-crash-warning-handoff.md.

## Hot Company Watchlist (shared input for markers 1-4, 8, 10-13)
Dynamically recomputed every run from currently-rising GICS sectors + S&P 500 mega-cap constituents -- never hardcoded to a fixed ticker list.

| Rank | Ticker | Sector | Market Cap |
|------|--------|--------|------------|
| 1 | NVDA | Technology | $5201B |
| 2 | AAPL | Technology | $4515B |
| 3 | MSFT | Technology | $3588B |
| 4 | AVGO | Technology | $1753B |
| 5 | LLY | Health Care | $1119B |
| 6 | BRK-B | Financials | $1061B |
| 7 | JPM | Financials | $935B |
| 8 | WMT | Consumer Staples | $825B |
| 9 | AMD | Technology | $773B |
| 10 | V | Financials | $693B |

## Markers

| # | Marker | Status | Detail |
|---|--------|--------|--------|
| 1 | Record debt issuance, hot sector (NVDA) | flag | NVDA: 3 debt-prospectus filing(s) in the trailing 180d (own 730d average: 0.7/period) -- counts filing events, not dollar principal |
| 1 | Record debt issuance, hot sector (AAPL) | ok | AAPL: 0 debt-prospectus filing(s) in the trailing 180d (own 730d average: 0.7/period) -- counts filing events, not dollar principal |
| 1 | Record debt issuance, hot sector (MSFT) | ok | MSFT: 0 debt-prospectus filing(s) in the trailing 180d (own 730d average: 0.0/period) -- counts filing events, not dollar principal |
| 1 | Record debt issuance, hot sector (AVGO) | ok | AVGO: 0 debt-prospectus filing(s) in the trailing 180d (own 730d average: 3.7/period) -- counts filing events, not dollar principal |
| 1 | Record debt issuance, hot sector (LLY) | ok | LLY: 3 debt-prospectus filing(s) in the trailing 180d (own 730d average: 2.2/period) -- counts filing events, not dollar principal |
| 1 | Record debt issuance, hot sector (BRK-B) | ok | BRK-B: 3 debt-prospectus filing(s) in the trailing 180d (own 730d average: 3.0/period) -- counts filing events, not dollar principal |
| 1 | Record debt issuance, hot sector (JPM) | flag | JPM: 10000 debt-prospectus filing(s) in the trailing 180d (own 730d average: 2465.8/period) -- counts filing events, not dollar principal |
| 1 | Record debt issuance, hot sector (WMT) | flag | WMT: 3 debt-prospectus filing(s) in the trailing 180d (own 730d average: 1.5/period) -- counts filing events, not dollar principal |
| 1 | Record debt issuance, hot sector (AMD) | flag | AMD: 3 debt-prospectus filing(s) in the trailing 180d (own 730d average: 1.5/period) -- counts filing events, not dollar principal |
| 1 | Record debt issuance, hot sector (V) | ok | V: 0 debt-prospectus filing(s) in the trailing 180d (own 730d average: 1.5/period) -- counts filing events, not dollar principal |
| 2 | Debt moves off balance sheet (AMD) | ok | AMD: $4.5B uncommenced lease commitments (+0.0% since last filing, 10-Q filed 2026-08-05) |
| 3 | Seller finances buyer | unknown | No automatable source exists for vendor/circular-financing deals -- periodically news-scan the current hot watchlist yourself: NVDA, AAPL, MSFT, AVGO, LLY, BRK-B, JPM, WMT, AMD, V |
| 4 | Capex outruns cash flow (NVDA) | ok | NVDA: Free Cash Flow $+96.7B, Capital Expenditure $6.0B (period ending 2026-01-31) |
| 4 | Capex outruns cash flow (AAPL) | ok | AAPL: Free Cash Flow $+98.8B, Capital Expenditure $12.7B (period ending 2025-09-30) |
| 4 | Capex outruns cash flow (MSFT) | ok | MSFT: Free Cash Flow $+67.0B, Capital Expenditure $115.9B (period ending 2026-06-30) |
| 4 | Capex outruns cash flow (AVGO) | ok | AVGO: Free Cash Flow $+26.9B, Capital Expenditure $0.6B (period ending 2025-10-31) |
| 4 | Capex outruns cash flow (LLY) | ok | LLY: Free Cash Flow $+6.0B, Capital Expenditure $10.8B (period ending 2025-12-31) |
| 4 | Capex outruns cash flow (BRK-B) | ok | BRK-B: Free Cash Flow $+25.0B, Capital Expenditure $20.9B (period ending 2025-12-31) |
| 4 | Capex outruns cash flow (JPM) | ok | JPM: Free Cash Flow $-147.8B, Capital Expenditure $0.0B (period ending 2025-12-31) |
| 4 | Capex outruns cash flow (WMT) | ok | WMT: Free Cash Flow $+14.9B, Capital Expenditure $26.6B (period ending 2026-01-31) |
| 4 | Capex outruns cash flow (AMD) | ok | AMD: Free Cash Flow $+6.7B, Capital Expenditure $1.0B (period ending 2025-12-31) |
| 4 | Capex outruns cash flow (V) | ok | V: Free Cash Flow $+21.6B, Capital Expenditure $1.5B (period ending 2025-09-30) |
| 5 | Margin debt YoY growth | ok | Margin debt $1.42T as of 2026-07-01, +38.6% YoY vs 2025-07-01 |
| 6 | Record IPO/equity issuance | ok | S-1 (intent to register): 186 filing(s) in the trailing 30d vs 282 in the same window a year ago (0.66x); 424B4 (priced IPO): 48 filing(s) in the trailing 30d vs 57 in the same window a year ago (0.84x) |
| 7 | Retail piles into leverage | unknown | Equity put/call ratio 0.51 -- accumulating baseline, day 5 of 30 (different mechanism than ETF/fund-flow data -- see module docstring) |
| 8 | Insider selling (NVDA) | flag | NVDA: $1,484,600,616 sold vs $0 bought, trailing 365 days |
| 8 | Insider selling (AAPL) | flag | AAPL: $171,229,068 sold vs $0 bought, trailing 365 days |
| 8 | Insider selling (MSFT) | flag | MSFT: $52,104,664 sold vs $3,436,971 bought, trailing 365 days |
| 8 | Insider selling (AVGO) | flag | AVGO: $1,078,713,342 sold vs $1,926,569 bought, trailing 365 days |
| 8 | Insider selling (LLY) | flag | LLY: $2,026,158,792 sold vs $0 bought, trailing 365 days |
| 8 | Insider selling (BRK-B) | ok | BRK-B: $0 sold vs $500,617 bought, trailing 365 days |
| 8 | Insider selling (JPM) | flag | JPM: $125,468,226 sold vs $0 bought, trailing 365 days |
| 8 | Insider selling (WMT) | flag | WMT: $3,192,013,233 sold vs $0 bought, trailing 365 days |
| 8 | Insider selling (AMD) | flag | AMD: $304,331,211 sold vs $0 bought, trailing 365 days |
| 8 | Insider selling (V) | flag | V: $75,256,498 sold vs $0 bought, trailing 365 days |
| 9 | The Super Bowl signal | unknown | Next Super Bowl is 2027-02-14 (176 day(s) away) -- ad-share content is not automatable, nothing to check yet |
| 10 | Most-valuable-company milestone | flag | NVDA is the largest company in the current hot-sector watchlist ($5.20T, most recently crossed the $5.0T rung) |
| 11 | Regulators sound the alarm | ok | No new matching regulator statements this run. |
| 12 | Credit turns in the hot sector while broad market stays calm (AAPL) | unknown | AAPL: bond CUSIP 037833EY2 found, but no live or manually-entered yield reading available -- run `record-bond-yield AAPL <yield_pct>` |
| 12 | Credit turns in the hot sector while broad market stays calm (BRK-B) | unknown | BRK-B: bond CUSIP 084670EB0 found, but no live or manually-entered yield reading available -- run `record-bond-yield BRK-B <yield_pct>` |
| 12 | Credit turns in the hot sector while broad market stays calm (JPM) | unknown | JPM: bond CUSIP 46661MCB8 found, but no live or manually-entered yield reading available -- run `record-bond-yield JPM <yield_pct>` |
| 13 | Funding markets start choking | ok | CP-Treasury spread (DCPN3M-DTB3) -0.03pp (z=-1.66 vs trailing 365d) |
| 14 | High-yield credit spread streak | ok | ICE BofA US HY OAS at 2.75pp (as of 2026-08-20); 0 consecutive day(s) at/above 3.5pp (needs 21 to flag) |

Last auto-generated: 2026-08-22.
