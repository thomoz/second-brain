# 14 Crash Signals — Daily Check

What this is: 14 historical market-crash warning markers, checked daily so an early warning doesn't slip by unnoticed.

Auto-generated daily -- overwritten every run. Advisor notes only; no trade action is ever suggested here (see SOUL.md). Per-marker source: investments/my-trader/14-signals-crash-warning-handoff.md.

## Run: 2026-09-26

## Hot Company Watchlist (shared input for markers 1-4, 8, 10-13)
Dynamically recomputed every run from currently-rising GICS sectors + S&P 500 mega-cap constituents -- never hardcoded to a fixed ticker list.

| Rank | Ticker | Sector | Market Cap |
|------|--------|--------|------------|
| 1 | AAPL | Technology | $4978B |
| 2 | AVGO | Technology | $1684B |
| 3 | BRK-B | Financials | $1082B |
| 4 | AMD | Technology | $1029B |
| 5 | ABBV | Health Care | $467B |
| 6 | BAC | Financials | $396B |
| 7 | AMAT | Technology | $385B |
| 8 | ANET | Technology | $261B |
| 9 | C | Financials | $225B |
| 10 | AMGN | Health Care | $224B |

## Markers

| # | Marker | Status | Detail |
|---|--------|--------|--------|
| 1 | Record debt issuance, hot sector (AAPL) | ok | AAPL: 0 debt-prospectus filing(s) in the trailing 180d (own 730d average: 0.7/period) -- counts filing events, not dollar principal |
| 1 | Record debt issuance, hot sector (AVGO) | ok | AVGO: 0 debt-prospectus filing(s) in the trailing 180d (own 730d average: 3.7/period) -- counts filing events, not dollar principal |
| 1 | Record debt issuance, hot sector (BRK-B) | ok | BRK-B: 3 debt-prospectus filing(s) in the trailing 180d (own 730d average: 3.0/period) -- counts filing events, not dollar principal |
| 1 | Record debt issuance, hot sector (AMD) | flag | AMD: 3 debt-prospectus filing(s) in the trailing 180d (own 730d average: 1.5/period) -- counts filing events, not dollar principal |
| 1 | Record debt issuance, hot sector (ABBV) | ok | ABBV: 3 debt-prospectus filing(s) in the trailing 180d (own 730d average: 2.5/period) -- counts filing events, not dollar principal |
| 1 | Record debt issuance, hot sector (BAC) | flag | BAC: 5325 debt-prospectus filing(s) in the trailing 180d (own 730d average: 2465.8/period) -- counts filing events, not dollar principal |
| 1 | Record debt issuance, hot sector (AMAT) | ok | AMAT: 0 debt-prospectus filing(s) in the trailing 180d (own 730d average: 0.7/period) -- counts filing events, not dollar principal |
| 1 | Record debt issuance, hot sector (ANET) | ok | ANET: 0 debt-prospectus filing(s) in the trailing 180d (own 730d average: 0.0/period) -- counts filing events, not dollar principal |
| 1 | Record debt issuance, hot sector (C) | flag | C: 6920 debt-prospectus filing(s) in the trailing 180d (own 730d average: 2465.8/period) -- counts filing events, not dollar principal |
| 1 | Record debt issuance, hot sector (AMGN) | ok | AMGN: 0 debt-prospectus filing(s) in the trailing 180d (own 730d average: 0.5/period) -- counts filing events, not dollar principal |
| 2 | Debt moves off balance sheet (AMD) | ok | AMD: $4.5B uncommenced lease commitments (+0.0% since last filing, 10-Q filed 2026-08-05) |
| 3 | Seller finances buyer | unknown | No automatable source exists for vendor/circular-financing deals -- periodically news-scan the current hot watchlist yourself: AAPL, AVGO, BRK-B, AMD, ABBV, BAC, AMAT, ANET, C, AMGN |
| 4 | Capex outruns cash flow | ok | No hot-watchlist tickers with a resolvable cash-flow statement this run. |
| 5 | Margin debt YoY growth | ok | Margin debt $1.45T as of 2026-08-01, +37.2% YoY vs 2025-08-01 |
| 6 | Record IPO/equity issuance | ok | S-1 (intent to register): 176 filing(s) in the trailing 30d vs 305 in the same window a year ago (0.58x); 424B4 (priced IPO): 25 filing(s) in the trailing 30d vs 52 in the same window a year ago (0.48x) |
| 7 | Retail piles into leverage | ok | Equity put/call ratio 0.52 (z=-0.76 vs trailing 39d mean 0.57) -- options positioning proxy, not the video's ETF/fund-flow mechanism |
| 8 | Insider selling (AAPL) | flag | AAPL: $173,879,496 sold vs $0 bought, trailing 365 days |
| 8 | Insider selling (AVGO) | flag | AVGO: $1,278,280,106 sold vs $698,699 bought, trailing 365 days |
| 8 | Insider selling (BRK-B) | ok | BRK-B: $0 sold vs $500,617 bought, trailing 365 days |
| 8 | Insider selling (AMD) | flag | AMD: $373,535,839 sold vs $0 bought, trailing 365 days |
| 8 | Insider selling (ABBV) | flag | ABBV: $18,922,198 sold vs $0 bought, trailing 365 days |
| 8 | Insider selling (BAC) | flag | BAC: $31,081,032 sold vs $0 bought, trailing 365 days |
| 8 | Insider selling (AMAT) | flag | AMAT: $180,243,550 sold vs $0 bought, trailing 365 days |
| 8 | Insider selling (ANET) | flag | ANET: $1,344,474,638 sold vs $0 bought, trailing 365 days |
| 8 | Insider selling (C) | flag | C: $23,042,688 sold vs $0 bought, trailing 365 days |
| 8 | Insider selling (AMGN) | flag | AMGN: $29,330,642 sold vs $0 bought, trailing 365 days |
| 9 | The Super Bowl signal | unknown | Next Super Bowl is 2027-02-14 (141 day(s) away) -- ad-share content is not automatable, nothing to check yet |
| 10 | Most-valuable-company milestone | flag | AAPL is the largest company in the current hot-sector watchlist ($4.98T, most recently crossed the $4.5T rung) |
| 11 | Regulators sound the alarm | ok | No new matching regulator statements this run. |
| 12 | Credit turns in the hot sector while broad market stays calm (AAPL) | unknown | AAPL: bond CUSIP 037833EY2 found, but no live or manually-entered yield reading available -- run `record-bond-yield AAPL <yield_pct>` |
| 12 | Credit turns in the hot sector while broad market stays calm (BRK-B) | unknown | BRK-B: bond CUSIP 084670EB0 found, but no live or manually-entered yield reading available -- run `record-bond-yield BRK-B <yield_pct>` |
| 12 | Credit turns in the hot sector while broad market stays calm (ABBV) | unknown | ABBV: bond CUSIP 00287YDR7 found, but no live or manually-entered yield reading available -- run `record-bond-yield ABBV <yield_pct>` |
| 12 | Credit turns in the hot sector while broad market stays calm (BAC) | unknown | BAC: bond CUSIP 09712CWQ2 found, but no live or manually-entered yield reading available -- run `record-bond-yield BAC <yield_pct>` |
| 12 | Credit turns in the hot sector while broad market stays calm (AMAT) | unknown | AMAT: bond CUSIP 038222AH8 found, but no live or manually-entered yield reading available -- run `record-bond-yield AMAT <yield_pct>` |
| 12 | Credit turns in the hot sector while broad market stays calm (C) | unknown | C: bond CUSIP 17334DEC2 found, but no live or manually-entered yield reading available -- run `record-bond-yield C <yield_pct>` |
| 13 | Funding markets start choking | ok | CP-Treasury spread (DCPN3M-DTB3) 0.06pp (z=-0.05 vs trailing 365d) |
| 14 | High-yield credit spread streak | ok | ICE BofA US HY OAS at 2.80pp (as of 2026-09-24); 0 consecutive day(s) at/above 3.5pp (needs 21 to flag) |
