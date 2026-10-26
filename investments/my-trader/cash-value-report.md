# Cash-Value Scan

**Last run: 2026-10-27** - scanned 0 US + 200 ASX names (135 returned balance-sheet data), 1 qualify at net cash >= 50% of market cap.

What this is: companies whose net cash (cash minus all debt) is at least 50% of their market cap AND that generate positive operating cash flow - the market is pricing the whole operating business at a steep discount and handing you the balance-sheet cash on top. Classic Graham / deep-value screen. Free cash flow is shown and tagged when negative, but is not a filter (positive OCF with negative FCF is usually growth capex, not burn).

The three net-cash columns carry a `(more/less = cheaper)` hint in the header. `Net cash / mcap` = net cash (cash + short-term investments minus all debt) as a % of the whole company's market value; higher means more of the share price is just the bank balance (sorted high-to-low). `Biz / mcap` = what's left after the cash, i.e. what you're paying for the operating business itself; lower is cheaper and negative means the price is below the cash pile. `Net cash` = the same figure in dollars. `FCF yld on biz` = free cash flow as a % of that business value. Note: a high `Net cash / mcap` reads as *cheap*, not automatically *good* - the market often prices a company below its cash because it expects that cash to be burned, trapped, or never paid out (see the Read column, then run `find` / `assess`).

Auto-generated daily - overwritten every run. Advisor notes only; no trade action is ever suggested here (see SOUL.md). Run your own `find` / `assess` on anything you like the look of.

| Ticker | Company | Mkt | Net cash / mcap (more = cheaper) | Biz / mcap (less = cheaper) | Market cap | OCF (TTM) | FCF | FCF yld on biz | Net cash (more = bigger cushion) | Rev growth YoY | Sector | Tags | Read |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| TUA | Tuas | ASX | 72% | 28% | 693.7M SGD | 91.3M SGD | 52.0M SGD | 26.6% | 498.3M SGD | +22% | Communication Services | - | 498.3M SGD net cash, 693.7M SGD mcap, 52.0M SGD FCF - paying ~195.4M SGD for the operating business. |

Tag key: `held` / `watchlist` = already tracked in my-trader; `micro` = market cap under US$50M / A$75M (thinner liquidity, higher risk); `shrinking revenue` = negative YoY revenue growth; `negative FCF` = free cash flow negative (heavy capex or cash burn - check which); `REVIEW:` = borderline ethical-filter flag.
