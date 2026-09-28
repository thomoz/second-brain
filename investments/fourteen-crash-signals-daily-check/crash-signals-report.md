# 14 Crash Signals — Daily Check

What this is: 14 historical market-crash warning markers, checked daily so an early warning doesn't slip by unnoticed.

Auto-generated daily -- overwritten every run. Advisor notes only; no trade action is ever suggested here (see SOUL.md). Per-marker source: investments/my-trader/14-signals-crash-warning-handoff.md.

## Run: 2026-09-28

## Hot Company Watchlist (shared input for markers 1-4, 8, 10-13)
Dynamically recomputed every run from currently-rising GICS sectors + S&P 500 mega-cap constituents -- never hardcoded to a fixed ticker list.

No hot-watchlist companies resolved this run (no rising sectors, or data unavailable).

## Markers

| # | Marker | Status | Detail |
|---|--------|--------|--------|
| 1 | Record debt issuance, hot sector | ok | No hot-watchlist tickers with a resolvable CIK/filing count this run. |
| 2 | Debt moves off balance sheet | ok | No hot-watchlist tickers with a resolvable lease-commitment reading this run. |
| 3 | Seller finances buyer | unknown | No automatable source exists for vendor/circular-financing deals, and no hot-watchlist companies are resolved this run to suggest news-scanning. |
| 4 | Capex outruns cash flow | ok | No hot-watchlist tickers with a resolvable cash-flow statement this run. |
| 5 | Margin debt YoY growth | ok | Margin debt $1.45T as of 2026-08-01, +37.2% YoY vs 2025-08-01 |
| 6 | Record IPO/equity issuance | ok | S-1 (intent to register): 158 filing(s) in the trailing 30d vs 291 in the same window a year ago (0.54x); 424B4 (priced IPO): 20 filing(s) in the trailing 30d vs 46 in the same window a year ago (0.43x) |
| 7 | Retail piles into leverage | ok | Equity put/call ratio 0.52 (z=-0.73 vs trailing 41d mean 0.57) -- options positioning proxy, not the video's ETF/fund-flow mechanism |
| 8 | Insider selling (aggregate trend) | ok | No hot-watchlist tickers with insider activity this run. |
| 9 | The Super Bowl signal | unknown | Next Super Bowl is 2027-02-14 (139 day(s) away) -- ad-share content is not automatable, nothing to check yet |
| 10 | Most-valuable-company milestone | unknown | hot-company watchlist is empty this run (no rising sectors, or data unavailable) |
| 11 | Regulators sound the alarm | ok | No new matching regulator statements this run. |
| 12 | Credit turns in the hot sector while broad market stays calm | ok | No hot-watchlist tickers with a resolvable bond CUSIP this run. |
| 13 | Funding markets start choking | ok | CP-Treasury spread (DCPN3M-DTB3) 0.06pp (z=-0.06 vs trailing 365d) |
| 14 | High-yield credit spread streak | ok | ICE BofA US HY OAS at 2.80pp (as of 2026-09-24); 0 consecutive day(s) at/above 3.5pp (needs 21 to flag) |
