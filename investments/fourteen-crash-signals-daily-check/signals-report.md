# 14 Crash Signals — Daily Check

Auto-generated daily -- overwritten every run. Advisor notes only; no trade action is ever suggested here (see SOUL.md). Per-marker source: investments/my-trader/14-signals-crash-warning-handoff.md.

## Hot Company Watchlist (shared input for markers 1-4, 8, 10-13)
Dynamically recomputed every run from currently-rising GICS sectors + S&P 500 mega-cap constituents -- never hardcoded to a fixed ticker list.

| Rank | Ticker | Sector | Market Cap |
|------|--------|--------|------------|
| 1 | NVDA | Technology | $5322B |
| 2 | AAPL | Technology | $4525B |
| 3 | MSFT | Technology | $3576B |
| 4 | AMZN | Consumer Discretionary | $2799B |
| 5 | AVGO | Technology | $1808B |
| 6 | TSLA | Consumer Discretionary | $1330B |
| 7 | LLY | Health Care | $1093B |
| 8 | BRK-B | Financials | $1077B |
| 9 | MU | Technology | $1062B |
| 10 | JPM | Financials | $966B |

## Markers

| # | Marker | Status | Detail |
|---|--------|--------|--------|
| 1 | Record debt issuance, hot sector (NVDA) | flag | NVDA: 3 debt-prospectus filing(s) in the trailing 180d (own 730d average: 0.7/period) -- counts filing events, not dollar principal |
| 1 | Record debt issuance, hot sector (AAPL) | ok | AAPL: 0 debt-prospectus filing(s) in the trailing 180d (own 730d average: 0.7/period) -- counts filing events, not dollar principal |
| 1 | Record debt issuance, hot sector (MSFT) | ok | MSFT: 0 debt-prospectus filing(s) in the trailing 180d (own 730d average: 0.0/period) -- counts filing events, not dollar principal |
| 1 | Record debt issuance, hot sector (AMZN) | flag | AMZN: 12 debt-prospectus filing(s) in the trailing 180d (own 730d average: 3.7/period) -- counts filing events, not dollar principal |
| 1 | Record debt issuance, hot sector (AVGO) | ok | AVGO: 0 debt-prospectus filing(s) in the trailing 180d (own 730d average: 3.7/period) -- counts filing events, not dollar principal |
| 1 | Record debt issuance, hot sector (TSLA) | ok | TSLA: 0 debt-prospectus filing(s) in the trailing 180d (own 730d average: 0.0/period) -- counts filing events, not dollar principal |
| 1 | Record debt issuance, hot sector (LLY) | ok | LLY: 3 debt-prospectus filing(s) in the trailing 180d (own 730d average: 2.2/period) -- counts filing events, not dollar principal |
| 1 | Record debt issuance, hot sector (BRK-B) | ok | BRK-B: 3 debt-prospectus filing(s) in the trailing 180d (own 730d average: 3.0/period) -- counts filing events, not dollar principal |
| 1 | Record debt issuance, hot sector (MU) | ok | MU: 0 debt-prospectus filing(s) in the trailing 180d (own 730d average: 1.5/period) -- counts filing events, not dollar principal |
| 1 | Record debt issuance, hot sector (JPM) | flag | JPM: 10000 debt-prospectus filing(s) in the trailing 180d (own 730d average: 2465.8/period) -- counts filing events, not dollar principal |
| 2 | Debt moves off balance sheet (AMZN) | ok | AMZN: $0.0B uncommenced lease commitments (baseline, 10-Q filed 2026-07-31) -- no prior reading to compare growth against yet |
| 3 | Seller finances buyer | unknown | No automatable source exists for vendor/circular-financing deals -- periodically news-scan the current hot watchlist yourself: NVDA, AAPL, MSFT, AMZN, AVGO, TSLA, LLY, BRK-B, MU, JPM |
| 4 | Capex outruns cash flow (NVDA) | ok | NVDA: Free Cash Flow $+96.7B, Capital Expenditure $6.0B (period ending 2026-01-31) |
| 4 | Capex outruns cash flow (AAPL) | ok | AAPL: Free Cash Flow $+98.8B, Capital Expenditure $12.7B (period ending 2025-09-30) |
| 4 | Capex outruns cash flow (MSFT) | ok | MSFT: Free Cash Flow $+67.0B, Capital Expenditure $115.9B (period ending 2026-06-30) |
| 4 | Capex outruns cash flow (AMZN) | ok | AMZN: Free Cash Flow $+7.7B, Capital Expenditure $131.8B (period ending 2025-12-31) |
| 4 | Capex outruns cash flow (AVGO) | ok | AVGO: Free Cash Flow $+26.9B, Capital Expenditure $0.6B (period ending 2025-10-31) |
| 4 | Capex outruns cash flow (TSLA) | ok | TSLA: Free Cash Flow $+6.2B, Capital Expenditure $8.5B (period ending 2025-12-31) |
| 4 | Capex outruns cash flow (LLY) | ok | LLY: Free Cash Flow $+6.0B, Capital Expenditure $10.8B (period ending 2025-12-31) |
| 4 | Capex outruns cash flow (BRK-B) | ok | BRK-B: Free Cash Flow $+25.0B, Capital Expenditure $20.9B (period ending 2025-12-31) |
| 4 | Capex outruns cash flow (MU) | ok | MU: Free Cash Flow $+1.7B, Capital Expenditure $15.9B (period ending 2025-08-31) |
| 4 | Capex outruns cash flow (JPM) | ok | JPM: Free Cash Flow $-147.8B, Capital Expenditure $0.0B (period ending 2025-12-31) |
| 5 | Margin debt YoY growth | ok | Margin debt $1.42T as of 2026-07-01, +38.6% YoY vs 2025-07-01 |
| 6 | Record IPO/equity issuance | ok | S-1 (intent to register): 187 filing(s) in the trailing 30d vs 262 in the same window a year ago (0.71x); 424B4 (priced IPO): 46 filing(s) in the trailing 30d vs 55 in the same window a year ago (0.84x) |
| 7 | Retail piles into leverage | unknown | Equity put/call ratio 0.65 -- accumulating baseline, day 1 of 30 (different mechanism than ETF/fund-flow data -- see module docstring) |
| 8 | Insider selling (NVDA) | flag | NVDA: $1,704,447,876 sold vs $0 bought, trailing 365 days |
| 8 | Insider selling (AAPL) | flag | AAPL: $191,672,890 sold vs $0 bought, trailing 365 days |
| 8 | Insider selling (MSFT) | flag | MSFT: $127,419,785 sold vs $3,436,971 bought, trailing 365 days |
| 8 | Insider selling (AMZN) | flag | AMZN: $459,836,737 sold vs $0 bought, trailing 365 days |
| 8 | Insider selling (AVGO) | flag | AVGO: $1,178,592,557 sold vs $1,926,569 bought, trailing 365 days |
| 8 | Insider selling (TSLA) | ok | TSLA: $162,338,367 sold vs $999,959,042 bought, trailing 365 days |
| 8 | Insider selling (LLY) | flag | LLY: $2,026,893,722 sold vs $0 bought, trailing 365 days |
| 8 | Insider selling (BRK-B) | ok | BRK-B: $0 sold vs $500,617 bought, trailing 365 days |
| 8 | Insider selling (MU) | flag | MU: $249,358,626 sold vs $7,821,723 bought, trailing 365 days |
| 8 | Insider selling (JPM) | flag | JPM: $128,298,698 sold vs $0 bought, trailing 365 days |
| 9 | The Super Bowl signal | unknown | Next Super Bowl is 2027-02-14 (179 day(s) away) -- ad-share content is not automatable, nothing to check yet |
| 10 | Most-valuable-company milestone | flag | NVDA is the largest company in the current hot-sector watchlist ($5.32T, most recently crossed the $5.0T rung) |
| 11 | Regulators sound the alarm | flag | SEC Proposes New Regulation Crypto Assets (https://www.sec.gov/newsroom/press-releases/2026-76-sec-proposes-new-regulation-crypto-assets) |
| 11 | Regulators sound the alarm | flag | SEC Charges Boiler Room Operator and Three Entities with Defrauding Retail Investors in $74 Million Pre-IPO Investment Scam (https://www.sec.gov/newsroom/press-releases/2026-75-sec-charges-boiler-room-operator-three-entities-defrauding-retail-investors-74-million-pre-ipo) |
| 11 | Regulators sound the alarm | flag | SEC Charges Toms River Trio in Connection with Alleged $47 Million Fraud Targeting Orthodox Jewish Communities (https://www.sec.gov/newsroom/press-releases/2026-74-sec-charges-toms-river-trio-connection-alleged-47-million-fraud-targeting-orthodox-jewish) |
| 11 | Regulators sound the alarm | flag | Small Business Forum’s Report to Congress Highlights Recommendations to Improve Capital-Raising Policy (https://www.sec.gov/newsroom/press-releases/2026-70-small-business-forums-report-congress-highlights-recommendations-improve-capital-raising-policy) |
| 11 | Regulators sound the alarm | flag | SEC Forms New Retail Fraud Working Group (https://www.sec.gov/newsroom/press-releases/2026-63-sec-forms-new-retail-fraud-working-group) |
| 11 | Regulators sound the alarm | flag | SEC Publishes Updated Market Statistics, Highlighting Increase in IPOs and Proceeds Raised (https://www.sec.gov/newsroom/press-releases/2026-61-sec-publishes-updated-market-statistics-highlighting-increase-ipos-proceeds-raised) |
| 11 | Regulators sound the alarm | flag | SEC Appoints Kathleen Hutchinson as Director of Office of International Affairs (https://www.sec.gov/newsroom/press-releases/2026-58-sec-appoints-kathleen-hutchinson-director-office-international-affairs) |
| 11 | Regulators sound the alarm | flag | SEC, CFTC Seek Public Comment to Further Clarify and Harmonize Derivatives Product Definitions (https://www.sec.gov/newsroom/press-releases/2026-57-sec-cftc-seek-public-comment-further-clarify-harmonize-derivatives-product-definitions) |
| 11 | Regulators sound the alarm | flag | SEC Appoints John Moses as Director of the Office of Investor Education and Assistance (https://www.sec.gov/newsroom/press-releases/2026-55-sec-appoints-john-moses-director-office-investor-education-assistance) |
| 11 | Regulators sound the alarm | flag | SEC Establishes Joint Data Standards as Required Under the Financial Data Transparency Act of 2022 (https://www.sec.gov/newsroom/press-releases/2026-53-sec-establishes-joint-data-standards-required-under-financial-data-transparency-act-2022) |
| 11 | Regulators sound the alarm | flag | Federal Reserve Board requests comment on a proposal to amend its requirements for banks to maintain anti-money laundering programs (https://www.federalreserve.gov/newsevents/pressreleases/bcreg20260707a.htm) |
| 11 | Regulators sound the alarm | flag | Barr, Will Artificial Intelligence Broadly Raise Living Standards or Drive Income and Wealth Inequality? (https://www.federalreserve.gov/newsevents/speech/barr20260714a.htm) |
| 11 | Regulators sound the alarm | flag | Bowman, Opening Remarks on Sound Practices for Artificial Intelligence (https://www.federalreserve.gov/newsevents/speech/bowman20260707a.htm) |
| 12 | Credit turns in the hot sector while broad market stays calm (AAPL) | unknown | AAPL: bond CUSIP 037833EY2 found, but no live or manually-entered yield reading available -- run `record-bond-yield AAPL <yield_pct>` |
| 12 | Credit turns in the hot sector while broad market stays calm (AMZN) | unknown | AMZN: bond CUSIP 023135EA0 found, but no live or manually-entered yield reading available -- run `record-bond-yield AMZN <yield_pct>` |
| 12 | Credit turns in the hot sector while broad market stays calm (BRK-B) | unknown | BRK-B: bond CUSIP 084670EB0 found, but no live or manually-entered yield reading available -- run `record-bond-yield BRK-B <yield_pct>` |
| 12 | Credit turns in the hot sector while broad market stays calm (MU) | unknown | MU: bond CUSIP 595112CG6 found, but no live or manually-entered yield reading available -- run `record-bond-yield MU <yield_pct>` |
| 12 | Credit turns in the hot sector while broad market stays calm (JPM) | unknown | JPM: bond CUSIP 46661MCB8 found, but no live or manually-entered yield reading available -- run `record-bond-yield JPM <yield_pct>` |
| 13 | Funding markets start choking | ok | CP-Treasury spread (DCPN3M-DTB3) 0.06pp (z=-0.16 vs trailing 365d) |
| 14 | High-yield credit spread streak | ok | ICE BofA US HY OAS at 2.70pp (as of 2026-08-17); 0 consecutive day(s) at/above 3.5pp (needs 21 to flag) |

Last auto-generated: 2026-08-19.
