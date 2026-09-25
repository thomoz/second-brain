# 14 Crash Signals — Daily Check

What this is: 14 historical market-crash warning markers, checked daily so an early warning doesn't slip by unnoticed.

Auto-generated daily -- overwritten every run. Advisor notes only; no trade action is ever suggested here (see SOUL.md). Per-marker source: investments/my-trader/14-signals-crash-warning-handoff.md.

## Run: 2026-09-25

## Hot Company Watchlist (shared input for markers 1-4, 8, 10-13)
Dynamically recomputed every run from currently-rising GICS sectors + S&P 500 mega-cap constituents -- never hardcoded to a fixed ticker list.

| Rank | Ticker | Sector | Market Cap |
|------|--------|--------|------------|
| 1 | AAPL | Technology | $4902B |
| 2 | AVGO | Technology | $1672B |
| 3 | BRK-B | Financials | $1081B |
| 4 | AMD | Technology | $1027B |
| 5 | ABBV | Health Care | $468B |
| 6 | CSCO | Technology | $422B |
| 7 | CVX | Energy | $403B |
| 8 | BAC | Financials | $392B |
| 9 | AMAT | Technology | $376B |
| 10 | DELL | Technology | $341B |

## Markers

| # | Marker | Status | Detail |
|---|--------|--------|--------|
| 1 | Record debt issuance, hot sector (AAPL) | ok | AAPL: 0 debt-prospectus filing(s) in the trailing 180d (own 730d average: 0.7/period) -- counts filing events, not dollar principal |
| 1 | Record debt issuance, hot sector (AVGO) | ok | AVGO: 0 debt-prospectus filing(s) in the trailing 180d (own 730d average: 3.7/period) -- counts filing events, not dollar principal |
| 1 | Record debt issuance, hot sector (BRK-B) | ok | BRK-B: 3 debt-prospectus filing(s) in the trailing 180d (own 730d average: 3.0/period) -- counts filing events, not dollar principal |
| 1 | Record debt issuance, hot sector (AMD) | flag | AMD: 3 debt-prospectus filing(s) in the trailing 180d (own 730d average: 1.5/period) -- counts filing events, not dollar principal |
| 1 | Record debt issuance, hot sector (ABBV) | ok | ABBV: 3 debt-prospectus filing(s) in the trailing 180d (own 730d average: 2.5/period) -- counts filing events, not dollar principal |
| 1 | Record debt issuance, hot sector (CSCO) | ok | CSCO: 0 debt-prospectus filing(s) in the trailing 180d (own 730d average: 0.7/period) -- counts filing events, not dollar principal |
| 1 | Record debt issuance, hot sector (CVX) | ok | CVX: 0 debt-prospectus filing(s) in the trailing 180d (own 730d average: 2.2/period) -- counts filing events, not dollar principal |
| 1 | Record debt issuance, hot sector (BAC) | flag | BAC: 5271 debt-prospectus filing(s) in the trailing 180d (own 730d average: 2465.8/period) -- counts filing events, not dollar principal |
| 1 | Record debt issuance, hot sector (AMAT) | ok | AMAT: 0 debt-prospectus filing(s) in the trailing 180d (own 730d average: 0.7/period) -- counts filing events, not dollar principal |
| 1 | Record debt issuance, hot sector (DELL) | ok | DELL: 6 debt-prospectus filing(s) in the trailing 180d (own 730d average: 3.5/period) -- counts filing events, not dollar principal |
| 2 | Debt moves off balance sheet (AMD) | ok | AMD: $4.5B uncommenced lease commitments (+0.0% since last filing, 10-Q filed 2026-08-05) |
| 3 | Seller finances buyer | unknown | No automatable source exists for vendor/circular-financing deals -- periodically news-scan the current hot watchlist yourself: AAPL, AVGO, BRK-B, AMD, ABBV, CSCO, CVX, BAC, AMAT, DELL |
| 4 | Capex outruns cash flow | ok | No hot-watchlist tickers with a resolvable cash-flow statement this run. |
| 5 | Margin debt YoY growth | ok | Margin debt $1.45T as of 2026-08-01, +37.2% YoY vs 2025-08-01 |
| 6 | Record IPO/equity issuance | ok | S-1 (intent to register): 175 filing(s) in the trailing 30d vs 298 in the same window a year ago (0.59x); 424B4 (priced IPO): 25 filing(s) in the trailing 30d vs 51 in the same window a year ago (0.49x) |
| 7 | Retail piles into leverage | ok | Equity put/call ratio 0.55 (z=-0.35 vs trailing 38d mean 0.57) -- options positioning proxy, not the video's ETF/fund-flow mechanism |
| 8 | Insider selling (AAPL) | flag | AAPL: $115,275,099 sold vs $0 bought, trailing 365 days |
| 8 | Insider selling (AVGO) | flag | AVGO: $619,303,491 sold vs $698,699 bought, trailing 365 days |
| 8 | Insider selling (BRK-B) | ok | BRK-B: $0 sold vs $500,617 bought, trailing 365 days |
| 8 | Insider selling (AMD) | flag | AMD: $292,389,236 sold vs $0 bought, trailing 365 days |
| 8 | Insider selling (ABBV) | flag | ABBV: $18,922,198 sold vs $0 bought, trailing 365 days |
| 8 | Insider selling (CSCO) | flag | CSCO: $14,843,415 sold vs $0 bought, trailing 365 days |
| 8 | Insider selling (CVX) | flag | CVX: $463,111,426 sold vs $0 bought, trailing 365 days |
| 8 | Insider selling (BAC) | flag | BAC: $31,081,032 sold vs $0 bought, trailing 365 days |
| 8 | Insider selling (AMAT) | flag | AMAT: $176,392,605 sold vs $0 bought, trailing 365 days |
| 8 | Insider selling (DELL) | flag | DELL: $3,349,278,143 sold vs $0 bought, trailing 365 days |
| 9 | The Super Bowl signal | unknown | Next Super Bowl is 2027-02-14 (142 day(s) away) -- ad-share content is not automatable, nothing to check yet |
| 10 | Most-valuable-company milestone | flag | AAPL is the largest company in the current hot-sector watchlist ($4.90T, most recently crossed the $4.5T rung) |
| 11 | Regulators sound the alarm | ok | No new matching regulator statements this run. |
| 12 | Credit turns in the hot sector while broad market stays calm (AAPL) | unknown | AAPL: bond CUSIP 037833EY2 found, but no live or manually-entered yield reading available -- run `record-bond-yield AAPL <yield_pct>` |
| 12 | Credit turns in the hot sector while broad market stays calm (BRK-B) | unknown | BRK-B: bond CUSIP 084670EB0 found, but no live or manually-entered yield reading available -- run `record-bond-yield BRK-B <yield_pct>` |
| 12 | Credit turns in the hot sector while broad market stays calm (ABBV) | unknown | ABBV: bond CUSIP 00287YDR7 found, but no live or manually-entered yield reading available -- run `record-bond-yield ABBV <yield_pct>` |
| 12 | Credit turns in the hot sector while broad market stays calm (CVX) | unknown | CVX: bond CUSIP 166756AZ9 found, but no live or manually-entered yield reading available -- run `record-bond-yield CVX <yield_pct>` |
| 12 | Credit turns in the hot sector while broad market stays calm (BAC) | unknown | BAC: bond CUSIP 09712CWQ2 found, but no live or manually-entered yield reading available -- run `record-bond-yield BAC <yield_pct>` |
| 12 | Credit turns in the hot sector while broad market stays calm (AMAT) | unknown | AMAT: bond CUSIP 038222AH8 found, but no live or manually-entered yield reading available -- run `record-bond-yield AMAT <yield_pct>` |
| 12 | Credit turns in the hot sector while broad market stays calm (DELL) | unknown | DELL: bond CUSIP 24703DBY6 found, but no live or manually-entered yield reading available -- run `record-bond-yield DELL <yield_pct>` |
| 13 | Funding markets start choking | ok | CP-Treasury spread (DCPN3M-DTB3) 0.06pp (z=-0.05 vs trailing 365d) |
| 14 | High-yield credit spread streak | ok | ICE BofA US HY OAS at 2.73pp (as of 2026-09-23); 0 consecutive day(s) at/above 3.5pp (needs 21 to flag) |
