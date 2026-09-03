# Cash-Value Scan

**Last run: 2026-09-04** - scanned 514 US + 200 ASX names (584 returned balance-sheet data), 9 qualify at net cash >= 50% of market cap.

What this is: companies whose net cash (cash minus all debt) is at least 50% of their market cap AND that generate positive operating cash flow - the market is pricing the whole operating business at a steep discount and handing you the balance-sheet cash on top. Classic Graham / deep-value screen. Free cash flow is shown and tagged when negative, but is not a filter (positive OCF with negative FCF is usually growth capex, not burn).

The three net-cash columns carry a `(more/less = cheaper)` hint in the header. `Net cash / mcap` = net cash (cash + short-term investments minus all debt) as a % of the whole company's market value; higher means more of the share price is just the bank balance (sorted high-to-low). `Biz / mcap` = what's left after the cash, i.e. what you're paying for the operating business itself; lower is cheaper and negative means the price is below the cash pile. `Net cash` = the same figure in dollars. `FCF yld on biz` = free cash flow as a % of that business value. Note: a high `Net cash / mcap` reads as *cheap*, not automatically *good* - the market often prices a company below its cash because it expects that cash to be burned, trapped, or never paid out (see the Read column, then run `find` / `assess`).

Auto-generated daily - overwritten every run. Advisor notes only; no trade action is ever suggested here (see SOUL.md). Run your own `find` / `assess` on anything you like the look of.

| Ticker | Company | Mkt | Net cash / mcap (more = cheaper) | Biz / mcap (less = cheaper) | Market cap | OCF (TTM) | FCF | FCF yld on biz | Net cash (more = bigger cushion) | Rev growth YoY | Sector | Tags | Read |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| FBIO | Fortress Biotech Inc | US | 159% | -59% (below net cash) | 90.4M USD | 125.9M USD | -17.1M USD | n/a | 143.3M USD | +14% | Healthcare | negative FCF | 143.3M USD net cash, 90.4M USD mcap, -17.1M USD FCF - the market is paying less than the cash pile (-59% of mcap for the business). |
| MED | Medifast Inc | US | 101% | -1% (below net cash) | 140.2M USD | 8.8M USD | 11.4M USD | n/a | 142.2M USD | -28% | Consumer Cyclical | shrinking revenue | 142.2M USD net cash, 140.2M USD mcap, 11.4M USD FCF - the market is paying less than the cash pile (-1% of mcap for the business). |
| MTRX | Matrix Service Co | US | 72% | 28% | 296.8M USD | 56.4M USD | 99.4M USD | 120.5% | 214.3M USD | +3% | Industrials | - | 214.3M USD net cash, 296.8M USD mcap, 99.4M USD FCF - paying ~82.5M USD for the operating business. |
| SPRO | Spero Therapeutics Inc | US | 69% | 31% | 71.0M USD | 19.6M USD | 28.8M USD | 129.3% | 48.7M USD | n/a | Healthcare | - | 48.7M USD net cash, 71.0M USD mcap, 28.8M USD FCF - paying ~22.3M USD for the operating business. |
| USNA | Usana Health Sciences Inc | US | 63% | 37% | 266.6M USD | 27.7M USD | 49.1M USD | 50.1% | 168.6M USD | -5% | Consumer Defensive | shrinking revenue | 168.6M USD net cash, 266.6M USD mcap, 49.1M USD FCF - paying ~98.1M USD for the operating business. |
| TRS | Trimas Corp | US | 58% | 42% | 1.39B USD | 20.1M USD | 293.6M USD | 49.8% | 804.7M USD | +2% | Consumer Cyclical | - | 804.7M USD net cash, 1.39B USD mcap, 293.6M USD FCF - paying ~589.0M USD for the operating business. |
| COUR | Coursera Inc | US | 57% | 43% | 1.72B USD | 34.5M USD | 366.2M USD | 48.9% | 972.5M USD | +60% | Consumer Defensive | watchlist | 972.5M USD net cash, 1.72B USD mcap, 366.2M USD FCF - paying ~748.5M USD for the operating business. |
| ACTG | Acacia Research Corp | US | 52% | 48% | 440.1M USD | 30.0M USD | -16.4M USD | -7.8% | 230.5M USD | +124% | Industrials | negative FCF | 230.5M USD net cash, 440.1M USD mcap, -16.4M USD FCF - paying ~209.6M USD for the operating business. |
| CVV | CVD Equipment Corp | US | 52% | 48% | 45.0M USD | 477K USD | 4.0M USD | 18.6% | 23.5M USD | -43% | Industrials | micro, shrinking revenue | 23.5M USD net cash, 45.0M USD mcap, 4.0M USD FCF - paying ~21.5M USD for the operating business. |

Tag key: `held` / `watchlist` = already tracked in my-trader; `micro` = market cap under US$50M / A$75M (thinner liquidity, higher risk); `shrinking revenue` = negative YoY revenue growth; `negative FCF` = free cash flow negative (heavy capex or cash burn - check which); `REVIEW:` = borderline ethical-filter flag.
