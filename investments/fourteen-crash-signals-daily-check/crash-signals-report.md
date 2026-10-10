# 14 Crash Signals — Daily Check

What this is: 14 historical market-crash warning markers, checked daily so an early warning doesn't slip by unnoticed.

Auto-generated daily -- overwritten every run. Advisor notes only; no trade action is ever suggested here (see SOUL.md). Per-marker source: investments/my-trader/14-signals-crash-warning-handoff.md.

## Run: 2026-10-10

## Hot Company Watchlist (shared input for markers 1-4, 8, 10-13)
Dynamically recomputed every run from currently-rising GICS sectors + S&P 500 mega-cap constituents -- never hardcoded to a fixed ticker list.

| Rank | Ticker | Sector | Market Cap |
|------|--------|--------|------------|
| 1 | AAPL | Technology | $4913B |
| 2 | MSFT | Technology | $3973B |
| 3 | AVGO | Technology | $1726B |
| 4 | LLY | Health Care | $1052B |
| 5 | AMD | Technology | $993B |
| 6 | XOM | Energy | $695B |
| 7 | JNJ | Health Care | $630B |
| 8 | INTC | Technology | $553B |
| 9 | PLTR | Technology | $502B |
| 10 | ABBV | Health Care | $489B |

## Markers

| # | Marker | Status | Detail |
|---|--------|--------|--------|
| 1 | Record debt issuance, hot sector (AAPL) | ok | AAPL: 0 debt-prospectus filing(s) in the trailing 180d (own 730d average: 0.7/period) -- counts filing events, not dollar principal |
| 1 | Record debt issuance, hot sector (MSFT) | ok | MSFT: 0 debt-prospectus filing(s) in the trailing 180d (own 730d average: 0.0/period) -- counts filing events, not dollar principal |
| 1 | Record debt issuance, hot sector (AVGO) | ok | AVGO: 0 debt-prospectus filing(s) in the trailing 180d (own 730d average: 3.0/period) -- counts filing events, not dollar principal |
| 1 | Record debt issuance, hot sector (LLY) | ok | LLY: 3 debt-prospectus filing(s) in the trailing 180d (own 730d average: 2.2/period) -- counts filing events, not dollar principal |
| 1 | Record debt issuance, hot sector (AMD) | flag | AMD: 3 debt-prospectus filing(s) in the trailing 180d (own 730d average: 1.5/period) -- counts filing events, not dollar principal |
| 2 | Debt moves off balance sheet (AMD) | ok | AMD: $4.5B uncommenced lease commitments (+0.0% since last filing, 10-Q filed 2026-08-05) |
| 3 | Seller finances buyer | unknown | No automatable source exists for vendor/circular-financing deals -- periodically news-scan the current hot watchlist yourself: AAPL, MSFT, AVGO, LLY, AMD, XOM, JNJ, INTC, PLTR, ABBV |
| 4 | Capex outruns cash flow | ok | No hot-watchlist tickers with a resolvable cash-flow statement this run. |
| 5 | Margin debt YoY growth | ok | Margin debt $1.45T as of 2026-08-01, +37.2% YoY vs 2025-08-01 |
| 6 | Record IPO/equity issuance | ok | 424B4 (priced IPO): 25 filing(s) in the trailing 30d vs 63 in the same window a year ago (0.40x) |
| 7 | Retail piles into leverage | ok | Equity put/call ratio 0.62 (z=0.75 vs trailing 51d mean 0.57) -- options positioning proxy, not the video's ETF/fund-flow mechanism |
| 8 | Insider selling (AAPL) | flag | AAPL: $206,708,033 sold vs $0 bought, trailing 365 days |
| 8 | Insider selling (MSFT) | flag | MSFT: $116,258,041 sold vs $3,436,971 bought, trailing 365 days |
| 8 | Insider selling (AVGO) | flag | AVGO: $1,153,659,884 sold vs $698,699 bought, trailing 365 days |
| 8 | Insider selling (LLY) | flag | LLY: $1,055,398,758 sold vs $0 bought, trailing 365 days |
| 8 | Insider selling (AMD) | flag | AMD: $372,516,369 sold vs $0 bought, trailing 365 days |
| 8 | Insider selling (XOM) | flag | XOM: $2,395,656 sold vs $0 bought, trailing 365 days |
| 8 | Insider selling (JNJ) | flag | JNJ: $154,853,055 sold vs $257,688 bought, trailing 365 days |
| 8 | Insider selling (INTC) | ok | INTC: $7,474,217 sold vs $10,249,970 bought, trailing 365 days |
| 8 | Insider selling (PLTR) | flag | PLTR: $866,268,147 sold vs $0 bought, trailing 365 days |
| 8 | Insider selling (ABBV) | flag | ABBV: $18,922,198 sold vs $0 bought, trailing 365 days |
| 9 | The Super Bowl signal | unknown | Next Super Bowl is 2027-02-14 (127 day(s) away) -- ad-share content is not automatable, nothing to check yet |
| 10 | Most-valuable-company milestone | flag | AAPL is the largest company in the current hot-sector watchlist ($4.91T, most recently crossed the $4.5T rung) |
| 11 | Regulators sound the alarm | ok | No new matching regulator statements this run. |
| 12 | Credit turns in the hot sector while broad market stays calm (AAPL) | unknown | AAPL: bond CUSIP 037833EY2 found, but no live or manually-entered yield reading available -- run `record-bond-yield AAPL <yield_pct>` |
| 12 | Credit turns in the hot sector while broad market stays calm (JNJ) | unknown | JNJ: bond CUSIP 478160CY8 found, but no live or manually-entered yield reading available -- run `record-bond-yield JNJ <yield_pct>` |
| 12 | Credit turns in the hot sector while broad market stays calm (INTC) | unknown | INTC: bond CUSIP 458140CQ1 found, but no live or manually-entered yield reading available -- run `record-bond-yield INTC <yield_pct>` |
| 12 | Credit turns in the hot sector while broad market stays calm (ABBV) | unknown | ABBV: bond CUSIP 00287YDR7 found, but no live or manually-entered yield reading available -- run `record-bond-yield ABBV <yield_pct>` |
| 13 | Funding markets start choking | ok | CP-Treasury spread (DCPN3M-DTB3) 0.04pp (z=-0.39 vs trailing 365d) |
| 14 | High-yield credit spread streak | ok | ICE BofA US HY OAS at 3.15pp (as of 2026-10-08); 0 consecutive day(s) at/above 3.5pp (needs 21 to flag) |
