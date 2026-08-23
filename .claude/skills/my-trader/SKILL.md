---
name: my-trader
description: >
  Personal investing Find tool — conversational ticker assessment against Shaun's own
  criteria (sustainable, competitive edge, pricing power) via 7 checks (dividend trend,
  valuation, balance sheet/leverage, FX exposure, portfolio concentration incl. Berkshire
  overlap, sector/geopolitical risk, ETF mechanics), plus Briefs Finance's likelihood
  score layered in as a secondary input. Distinct from the `investments` skill
  (briefs-finance) — Find uses briefs-finance's score as one input among several, it
  doesn't replace that skill. Also handles holdings updates (buy/sell) conversationally.
  Triggers on: "check TICKER", "what do you think of TICKER", "add TICKER to watchlist",
  "I bought/sold N shares of TICKER", "show my holdings", "my-trader".
---

# my-trader Skill

Personal investing Find tool. Shares a database with `briefs-finance` (the `investments`
skill) via a uv workspace. All output is for Shaun's review only — nothing acts
autonomously, and no specific trade action is ever suggested (advisor-note style, per
SOUL.md).

## Quick Reference

`investments.db` lives only on the VPS now (no more local copy — see "Where This Runs"
below). Every command runs via the SSH wrapper:

```powershell
# Ephemeral lookup — "what do you think of TICKER" (writes nothing)
.\scripts\invoke_investments.ps1 -Package my-trader -Command "find --ticker VRTX"

# Explicit "add to watchlist" — persists a DB row + regenerates snapshots
.\scripts\invoke_investments.ps1 -Package my-trader -Command 'watchlist-add --ticker VRTX --name "Vertex Pharmaceuticals" --asset-type stock --bucket 1 --notes "..."'

# Record a buy/sell against a holding
.\scripts\invoke_investments.ps1 -Package my-trader -Command "holding-buy --ticker V --bucket 1 --qty 0.1 --price 340"
.\scripts\invoke_investments.ps1 -Package my-trader -Command "holding-sell --ticker V --bucket 1 --qty 0.05 --price 350"

# Regenerate holdings.md / watchlist.md from the DB
.\scripts\invoke_investments.ps1 -Package my-trader -Command "snapshot"

# One-time migration of the already-confirmed rows (VRTX, PMGOLD core+tactical, BRK-B,
# HDV, SCHD, ASML, LLY, LYV, V) into the shared DB — idempotent, safe to re-run
.\scripts\invoke_investments.ps1 -Package my-trader -Command "seed"

# Scheduled re-check of all holdings + vetted watchlist (also runs automatically —
# see scripts/setup_scheduler_windows.ps1 / scripts/systemd/second-brain-mytrader-monitor.timer)
.\scripts\invoke_investments.ps1 -Package my-trader -Command "monitor"

# Pull new Briefs Finance recommendations into synced-candidates-pending-review.md
# right now (also runs automatically once a day as part of `monitor`)
.\scripts\invoke_investments.ps1 -Package my-trader -Command "sync-candidates"

# Force a fresh gold backtest right now (slow, on-demand — also refreshes
# automatically, roughly once a day, as part of `monitor` — see "Gold Outlook" below)
.\scripts\invoke_investments.ps1 -Package my-trader -Command "gold-backtest"

# Review synced-candidates-pending-review.md, then promote or dismiss each one
.\scripts\invoke_investments.ps1 -Package my-trader -Command "promote-candidate --ticker VRTX --bucket 1 --status raw"
.\scripts\invoke_investments.ps1 -Package my-trader -Command "dismiss-candidate --ticker XYZ"

# Remove a ticker from the watchlist, or move it to a different bucket
.\scripts\invoke_investments.ps1 -Package my-trader -Command "watchlist-remove --ticker XYZ"
.\scripts\invoke_investments.ps1 -Package my-trader -Command "watchlist-move-bucket --ticker XYZ --to-bucket 2"
```

Quoting note: `-Command`'s value is reconstructed and re-parsed by the remote bash, so
a literal `$` inside a double-quoted argument (e.g. `--notes "worth $340"`) gets bash-
expanded to empty rather than preserved literally — avoid `$`, backticks, and
backslashes inside quoted argument values. See `scripts/invoke_investments.ps1`'s
header comment for detail.

## Where This Runs

`investments.db` (`investments/briefs-finance/data/investments.db`) exists in exactly
one place: the VPS. It is gitignored and never opened by a process on Shaun's Windows
machine — two independently-writable local/VPS copies kept jamming git on unmergeable
binary diffs (recurring incident, fixed 2026-08-23, see
`.agent/plans/investments-db-ssh-single-source.md`). All commands above run *on* the
VPS via `scripts/invoke_investments.ps1`, which streams output back live and propagates
the remote exit code — the workflow is identical to running locally, just routed over
SSH. The one exception is IBKR holdings sync (see below) — it must run locally against
IB Gateway, but its DB write still lands only on the VPS.

## Key Paths

- Package: `investments/my-trader/mytrader/`
- Shared database: `investments/briefs-finance/data/investments.db` (`holdings`,
  `watchlist`, `alert_history` tables — owned by my-trader; `reports`,
  `recommendations`, `likelihood_scores` etc. — owned by briefs-finance)
- Snapshots: `investments/my-trader/holdings.md`, `investments/my-trader/watchlist.md`
  (auto-regenerated after every write — never hand-edit these once the tool is in use).
  `watchlist.md` renders three sections: "Watchlist" (everything else), "Bucket 4 —
  Crash Discount Buys" (watchlist rows with `bucket="4"` — great, durable companies
  Shaun wants to buy at a crash-driven discount rather than today's price; not timed
  around a specific bubble and not a sell-after-recovery trade; migrates to Bucket 1
  once actually bought; see `config.CRASH_DISCOUNT_BUCKET`), and "Post-Crash AI Watch"
  (watchlist rows with `bucket="ai_postcrash"` — major AI-boom names with real moats
  that Shaun has deliberately chosen not to buy at current AI-bubble valuations, kept
  for reconsideration if/when the sector corrects; see `config.AI_POSTCRASH_BUCKET`).
  Strategy bucket framework (1/2/3/4) is documented in `tool-preplan.md`.
- Pending synced candidates: `investments/my-trader/synced-candidates-pending-review.md`
  (auto-regenerated from the `pending_candidates` table — separate from the watchlist
  until explicitly promoted).
- Strategy/criteria reference: `investments/my-trader/investment-strategy.md`

## MLP Filter

`mlp_filter.py` — added 2026-08-12, Shaun: "if i put in a stock to deep dive and it
turns out to be an mlp, please flag it and don't do a deep dive - i don't want mlps"
(K-1 tax filing, UBTI complications in retirement accounts). Runs first in
`engine.run_assessment()`, right after the single `fetch_ticker_data` call needed to
see the entity's own name — if `yfinance`'s `longName`/`shortName` ends in an
`L.P.`/`LP`-style legal suffix (e.g. "Enterprise Products Partners L.P.", "Kimbell
Royalty Partners, LP"), the assessment stops there: no backtest refresh, no
briefs-finance score compute, no checks run at all, `find`/Monitor just report
`MLP — skipped: <name> is structured as a Master Limited Partnership.` Detected from
the data itself, not a hardcoded ticker list — unlike `scripts.ethical_filter`'s
defense-contractor list, MLP structure is a fact already present in the entity's own
name, not a curated judgment call.

**Not gated on `quoteType`** (changed 2026-08-14) — an earlier version blanket-exempted
`quoteType == "ETF"` on the theory that a fund holding MLPs (e.g. AMLP, "Alerian MLP
ETF") shouldn't itself be flagged. That was right for AMLP (a C-corp fund, hence a
normal 1099), but the blanket exemption was still a real gap: CPER ("United States
Copper Index Fund, LP") is labeled `quoteType == "ETF"` by yfinance but is itself
organized and taxed as a limited partnership — confirmed live 2026-08-14 via USCF's
own K-1 info page, it genuinely issues a Schedule K-1 (Form 1065) every year, same
pattern as the rest of USCF's "United States X Fund" commodity-pool family (USO, UNG,
etc.). The end-anchored suffix regex alone already gets AMLP right without a
`quoteType` carve-out — "Alerian MLP ETF" ends in "ETF", not "LP" ("MLP" only appears
as a substring in the middle) — so the guard was solving a problem the regex didn't
have, while creating a real one for commodity-pool funds. AMLP/MLPX still get a full
deep dive; CPER-style commodity-pool ETFs are now correctly skipped.

## Company Profile Check

`checks/company_profile.py` — added 2026-08-12, Shaun: "have the deep dive also give
a brief explanation as to what each company/stock/etf does or represents." Always the
first check shown, always `verdict="info"`. Pulled from yfinance's own
`longBusinessSummary` (present for both individual equities and funds), trimmed to
its first ~2 sentences rather than the full paragraph — a name ending in an
abbreviation like "L.P." can consume one of those two sentence slots without adding
content (naive `". "` split can't tell an abbreviation from a real sentence
boundary), a known, accepted gap rather than a bug, same tradeoff class as the SEC/ASX
filing-section heuristics below. Falls back to `sector`/`industry`/`category` when no
summary is available at all.

## The 12 Assessment Checks

Every `find` / `watchlist-add` runs all 12 (unless the MLP filter above short-circuits
first):

| Check | What it looks at |
|-------|-------------------|
| Company profile | Brief plain-English description of what the ticker does/represents, from yfinance's `longBusinessSummary`. Added 2026-08-12 (see "Company Profile Check" above) |
| Dividend trend | Trailing vs. prior 12-month dividend sum |
| Valuation | Trailing/forward PE vs. configured rich/cheap bands |
| Balance sheet | Debt/equity and current ratio; falls back to return on equity when both are unavailable (common for financials/banks) |
| FX exposure | Non-AUD currency + AUD move (informational only) |
| Concentration | Berkshire 13F overlap + candidate's sector vs. existing holdings |
| Sector/geopolitical risk | Sector/industry vs. known active flashpoints |
| ETF mechanics | Expense ratio baseline / drift (drift only detectable after a repeat check) |
| Opportunity | Grounded in real investor-principle criteria — `verdict="interesting"` when any fire, gated on no active flags elsewhere. Added 2026-07-19 (see "Opportunity Signal" below) |
| Price action | Plain 1-month + 3-month price return, `verdict` always `"info"` — never a signal, just the fact. Added 2026-07-19 (see below) |
| Crash resilience | Peak-to-trough drawdown in each of 4 fixed historical windows (2008 GFC, Dec 2018 correction, COVID 2020, 2022 bear market), `verdict` always `"info"`/`"unknown"` — retrospective context, not gated into opportunity's flag-suppression list. Added 2026-07-25 (see below) |
| Technical levels | Current price vs 50/150/200-day moving averages, `verdict` always `"info"` — a contested signal (bullish trend-following vs. Goat's own 150DMA exit rule), reported not judged. Added 2026-08-13, `checks/technical_levels.py` |

Also, on every `run_assessment()` call (Find or Monitor): a ticker-scoped
`scripts.backtest.run_backtest(ticker_filter=...)` refresh (cheap — yfinance price
lookups only, no LLM calls — runs every time, not cached, since outcome windows
genuinely elapse) and a compute-if-missing Briefs Finance likelihood score (~9 haiku
LLM calls, cached after the first time). Both added 2026-07-19, Shaun: "throw
everything you have at assessing it."

## Two Distinct Find Actions

- **Ephemeral lookup** ("what do you think of TICKER") — runs the 12 checks (or stops
  early with an MLP flag), reports back, persists nothing.
- **Explicit watchlist-add** ("add TICKER to the watchlist") — same checks, plus writes
  a `watchlist` row (`status="discussed"`) and regenerates the markdown snapshots.

## Price Action Check

`checks/price_action.py` — confirmed 2026-07-19, same day as the opportunity check
rebuild. Shaun caught a real gap: DG was up +11.4% over 1 month but only -0.1% over 3
months (the whole move happened recently, invisible in a single 3-month window) —
Find showed nothing about it at all, since the opportunity check's 3-month figure
never gets displayed unless it crosses a threshold. This check always shows both
`fetch_recent_return_pct(ticker, period="1mo")` and `period="3mo"` as plain fact —
`verdict` is always `"info"`, never `"flag"` or `"interesting"`. Deliberately not a
signal: Graham's own principle file states "price momentum does not [matter]" for
value signals, and that's still true here — this check reports, it doesn't judge.

## Opportunity Signal

`checks/opportunity.py`. Confirmed 2026-07-19 after Shaun pointed out Monitor only
ever told him what to avoid, never what to be interested in. First version used
invented thresholds (raw PE cutoff, "price up 10%") and Shaun called it out directly:
"research a bunch of tests and mental models that expert and successful traders use,
otherwise this whole tool is a waste of time." Rebuilt the same day from
`investments/briefs-finance/principles/*.md` (the 9 investor-principle files already
in this codebase) — every threshold below is that principle's own literal stated
criterion, not invented:

- **Graham** — PE × P/B < 22.5 (the actual Graham Number formula; falls back to plain
  PE ≤ `PE_CHEAP_THRESHOLD` if P/B is unavailable). Graham's own file explicitly
  states "price momentum does not [matter]" for value signals — direct confirmation
  the original momentum-only design was wrong in principle, not just in the ASML edge
  case.
- **Lynch** — PEG ≤ `OPPORTUNITY_PEG_MAX` (1.0), his literal "growth at a reasonable
  price" threshold.
- **Buffett/Smith** — ROE ≥ `OPPORTUNITY_ROE_MIN_PCT` (15%, both files independently
  state this exact number) AND not already valuation-rich — quality at a fair price,
  not quality at any price.
- **Marks/Neilson** — price down ≥ `OPPORTUNITY_DIP_FLAG_PCT` (10%) over 3 months,
  answering Shaun's own follow-up ("a stock can be an opportunity if its price is
  falling") — a decline is only a signal when nothing else is actively wrong, which
  the gate below enforces. Magnitude is still a best-guess starting point; direction
  and gating are the sourced part.
- **Briefs Finance score** ≥ `OPPORTUNITY_SCORE_FLAG` (70, unchanged).

**Gate (Marks' risk-first framing / Munger's inversion)**: ALL signals above are
suppressed if the ticker has any active `"flag"` verdict among the other 7 checks in
the same assessment (dividend cut, balance sheet stress, rich valuation) —
`concentration` is explicitly excluded from this gate, since Shaun already ruled
sector overlap out of scope here ("it doesn't matter if I have another holding in the
same sector... I can make the choice myself by asking you to deeply compare them").
This is what caught and fixed the ASML case (was flagged "interesting" purely on
momentum while its own valuation check was actively flagging it rich in the same
report) more robustly than the first patch — any active flag suppresses everything,
not just a PE-specific carve-out on the momentum leg.

Multiple signals firing together get a "(N independent signals)" note per Munger's
confluence framing. Rendered by Monitor as a live snapshot every run (not deduped
through `alert_history` like the risk checks — Shaun wants to see it every run while
it's true, not just once). Only applies to `status="discussed"` watchlist rows, never
holdings (extending to holdings was proposed but not yet confirmed by Shaun).

**Standing rule**: nothing in this tool ever auto-removes a watchlist/holdings row as
a side effect of an assessment — Shaun: "you shouldn't auto-delete things from the
watchlist after you give results - it's up to me to tell you to delete a stock."

## Crash Resilience Check

`crash_windows.py` + `checks/crash_resilience.py` — added 2026-07-25. Prompted by a
real gap found comparing dollar-store tickers: FIVE and OLLI both "look like"
defensive dollar stores by name but historically amplified market crashes ~2x (FIVE:
-59.1% in COVID vs. the S&P 500's -33.9%), while DG (genuine consumables/staples
business) barely dipped (-1.1%) — that distinction wasn't visible anywhere in the
assessment until Shaun asked for it directly ("checks how well a stock has performed
during the major crashes").

Reports peak-to-trough drawdown over 4 fixed, well-documented broad-market windows —
not company-specific dips, so the same windows apply to every ticker:
- 2008 financial crisis (2007-10-01 → 2009-03-09)
- Dec 2018 correction (2018-08-01 → 2018-12-31)
- COVID crash (2020-01-01 → 2020-04-15)
- 2022 bear market (2021-10-01 → 2022-12-31)

A ticker that didn't exist yet for a given window (e.g. FIVE, IPO'd 2012, has no 2008
data) is simply skipped for that window. `verdict` is always `"info"` (or `"unknown"`
with no data) — retrospective context, not a live health signal, so it's deliberately
NOT included in `opportunity.py`'s flag-suppression gate.

## Monitor

Runs daily on a schedule (no chat trigger needed — it's automated, see "Setup" for the
scheduler entries). Re-checks every `holdings` row and every `watchlist` row with
`status="discussed"` (never `status="raw"` — Monitor doesn't discover new candidates,
that stays a Find/conversation action). Reuses the same 10-check engine as Find.

High-bar alerting: a check's first `flag` verdict for a given ticker/check creates one
alert; repeated flags on later runs stay quiet (already open); a check clearing back to
non-flag auto-acknowledges its open alert, so a future re-flag raises a fresh one. The
`opportunity` check's `"interesting"` verdict is explicitly exempt from this dedup —
see "Opportunity Signal" above.

Output is a standalone file, `investments/my-trader/my-trader-report.md` (full overwrite
every run — upcoming economic releases + a full per-holding report + new alerts this
run + all currently-open alerts + watchlist opportunities this run, in that order). A
bare Windows toast notification fires only when there's at least one new alert (reuses
`.claude/scripts/notifications.py`, same as heartbeat) — opportunities don't trigger a
toast, only visible in the report. No Second Brain daily-log entry and no WhatsApp
push — Monitor is a quieter, separate channel by design. Like Find, Monitor never
suggests a specific trade action — advisor notes only.

**Holdings section** — added 2026-08-13, Shaun: "the monitor report doesn't list my
Holdings, or give a report for each holding." Rated the original report 35/100 for
"would this help a trader decide what action to take" and rebuilt against 8 concrete
gaps (all confirmed and closed the same session):

1. **Live price + P&L** — `qty @ avg $X | now $Y | P&L +/-$Z (+/-N%)` on every
   holding, via the new `market_data.fetch_current_price()` (moved out of
   `snapshot.py`'s private `_current_price()` so both callers share one
   implementation). Degrades to "current price unavailable" rather than guessing.
2. **Bottom-line synthesis** — `monitor._bottom_line()` counts flags vs. `interesting`
   verdicts across the holding's checks and renders one sentence ("N flag(s) active
   (names) — worth a look" / "N opportunity signal(s)..." / "Nothing notable this
   run"), so a trader doesn't have to mentally scan every check line on every holding.
3. **Open alerts shown inline** — each holding's own open `alert_history` rows (from
   `db.get_open_alerts`, matched by ticker+source_table) render directly under that
   ticker as `OPEN ALERT (check_name, since DATE): message`, instead of only living in
   the separate "All Open Alerts" section further down.
4. **Noise suppression** — `monitor._NOISE_CHECKS` hides exact-match structural
   boilerplate lines that never carry information (currently just `etf_mechanics:
   "Not an ETF"` for non-fund tickers). `concentration`'s "unknown" verdict stays
   visible even with no Berkshire data, since it still carries a real per-ticker
   sector %.
5. **Technical entry/exit context** — the new `technical_levels` check (see the 12
   Assessment Checks table above) shows current price vs 50/150/200DMA on every
   holding.
6. **Bucket translated to plain English** — `config.BUCKET_LABELS` maps each bucket
   code to a sentence ("Long-term hold — never timed, dips are expected...", "Crash-
   trade tactical — bought for a crash trade, sold after recovery", etc.) rendered in
   the holding's header instead of a bare code.
7. **% of tracked portfolio** — `qty * current_price` summed across all priced
   holdings (currency-naive, same known limitation as `checks/concentration.py`'s own
   market-value aggregation), each holding shown as a % of that total.
8. **Opportunity-signal clarification** — when a holding's `opportunity` check fires
   `"interesting"`, the rendered line gets "(you already hold this — reads as an
   add-to-position signal, not a new-buy signal)" appended, since the check's
   Graham/Lynch/Buffett-Smith/Marks-Neilson signals were designed for a new-buy
   decision, not sizing an existing position.

Every check still renders (minus the noise-suppressed ones and minus
`principles_fit`/`news_events`, which are opt-in and Find-only). An MLP holding (see
"MLP Filter" above) renders as a one-line skip note instead of a check list, same as
Find's own output.

**Upcoming Economic Releases section** — added 2026-08-13 at the very top of the
report, above Holdings, Shaun: "I also need alerts to any major releases that are due
within the next 48 hours eg cpi, ppi reports, job data. That way I can deep dive them
myself to see if i need to take action." `mytrader/econ_calendar.py` — sourced from
FRED's own `/fred/releases/dates` endpoint (same `FRED_API_KEY` used everywhere else
in this codebase), filtered client-side to three release-name keywords: "Consumer
Price Index" (CPI), "Producer Price Index" (PPI), "Employment Situation" (the monthly
jobs report — nonfarm payrolls + unemployment rate). Weekly jobless claims deliberately
excluded — it fires almost every week, which would spam this section on nearly every
run rather than flag something rare/notable. Rendered as a live snapshot every run (not
deduped through `alert_history`) — the same real release should keep showing up on
every run it falls within the 48-hour window, same reasoning as the Opportunity Signal.
Degrades to "No CPI/PPI/jobs releases scheduled in the next 48 hours" if `FRED_API_KEY`
is unset or the request fails.

## Macro Monitoring Indicators

Every `monitor` run also runs 14 portfolio-wide checks (not per-ticker), once per run:
MOVE index (bond-market stress), housing price-to-income ratio, University of
Michigan Consumer Sentiment Index, a recession-probability check whose detail text
also folds in the 10Y-3M curve (the Fed's own preferred inversion metric, flags on
its own if inverted) and classifies bull vs. bear yield-curve steepening (both
refinements folded into that one check, not separate checks), market-implied
inflation expectations (10Y breakeven + the Fed's own preferred 5Y5Y forward gauge,
added 2026-07-30 as a forward-looking complement to the backward/coincident
recession-probability check and survey-based consumer-sentiment check),
high-yield credit spreads (ICE BofA US HY OAS, added 2026-07-30 — the bond market's
own pricing of default risk, a counter-check against equity valuation gauges), and
Australia's own headline CPI (added 2026-07-30, `mytrader/abs_cpi.py` — read
directly from the ABS's own published spreadsheet rather than FRED, whose
AUSCPIALLQINMEI series turned out to be 18+ months stale; flags outside the RBA's
2-3% inflation target band). The ABS file's URL embeds the release month with no
permanent link, so `abs_cpi.py` tries the current month and steps backward up to 4
months until one resolves — self-healing against release-day timing without a
hardcoded release calendar. Also US headline CPI (added 2026-07-30 — the realized/
backward-looking counterpart to inflation_expectations' forward-looking breakeven
read, via FRED's own CPIAUCSL with a `units="pc1"` transform for a ready-made YoY %;
flags outside a +/-1pp tolerance band around the Fed's 2% target), and UK headline
CPI (added 2026-07-30, `mytrader/ons_cpi.py` — read directly from the ONS's stable
CSV endpoint, which unlike ABS's file never moves — no release-month rollback
logic needed; flags outside the same +/-1pp tolerance band around the BoE's 2%
target). Japan CPI deliberately parked — e-Stat's API requires its own free
registered `appId` (same pattern as FRED's key) that hasn't been obtained yet.
These reuse the same high-bar alert-dedup
mechanism as the per-ticker checks, via a `"MACRO"`/`"macro"` sentinel ticker/
source_table pair in `alert_history`. Shown in `my-trader-report.md`'s "Macro
Indicators" section every run regardless of flag status (unlike per-ticker checks,
which are only shown when flagged/open). FRED-backed checks (housing, sentiment,
recession, inflation expectations, credit spreads, US CPI) degrade to `"unknown"` if
`FRED_API_KEY` is unset, and australia_cpi degrades to `"unknown"` if the ABS fetch/
parse fails,
and each surfaces its FRED observation date in its detail text so a stale-but-real
reading (e.g. annual household-income data, ~19-month publication lag) is never
mistaken for a live number.

Five more checks (added 2026-08-07, Phase 1 of a gold-tracking feature — Shaun holds
gold via PMGOLD, ASX bucket 3a) cover the macro drivers that actually move gold:
real yields (FRED DFII10, the 10Y TIPS yield — the opportunity cost of holding
non-yielding gold and the single most important gold driver; a two-sided band flags
both negative real yields, a bullish catalyst, and elevated real yields above 2%,
which historically pressure gold hard), the US dollar index (FRED DTWEXBGS, the
broad trade-weighted series — chosen over yfinance's `DX-Y.NYB` to keep this
module's FRED-first pattern; flags on a >3% move over a 30-day lookback rather than
an absolute level, since DXY has no natural high/low the way a bounded ratio does),
gold trend (GC=F futures price vs its 50-day and 200-day moving averages, with
sign-flip cross detection reporting the most recent price/200DMA cross plus PMGOLD's
own AUD price and AUD/USD 3-month context — deliberately always an `"info"` verdict,
never a flag or opportunity signal, since a 200DMA cross is a contested signal for
gold specifically: standard trend-following treats a break below as bearish, but
gold has a documented small-sample history of behaving as a contrarian buy signal
instead, so this reports the fact neutrally rather than judging it, same philosophy
as the per-ticker `price_action` check), the gold/silver ratio (GC=F/SI=F, flagged
at the commonly-cited historical-extreme bands of 80 high / 50 low), and VIX
(equity-market volatility, complementing the existing MOVE bond-volatility check,
flagged above the widely-cited crisis-adjacent level of 30). All five thresholds are
best-guess defaults pending Shaun's sign-off against real `my-trader-report.md`
readings, not sourced from a stated criterion the way `OPPORTUNITY_*` thresholds
are. These 5 signals' historical track record, plus 6 live technical indicators, now
feed a daily backtest-grounded directional read — see "Gold Outlook" below.

## Gold Outlook

Added 2026-08-07, Phase 2 of the gold-tracking feature (Phase 1 was the 5 macro
checks above). `investments/my-trader/gold-outlook.md` — regenerated every `monitor`
run, immediately after the macro checks. Combines:

- **6 live technical indicators** on GC=F (`mytrader/gold_technicals.py`): trend
  (20/50/200-day moving averages), MACD, RSI, Stochastic, ATR, Bollinger Bands, key
  support/resistance levels, volume context, and this-month seasonality — every
  indicator built as a full-history `*_series()` function (also used by the
  backtest) with a thin `compute_*()` wrapper for today's value, so there is exactly
  one implementation per indicator, never two independently-drifting copies.
- **The 5 Phase 1 macro signals**, reused as-is (`macro_indicators.py`'s
  `check_real_yields`/`check_dollar_index`/`check_gold_trend`/
  `check_gold_silver_ratio`/`check_vix`), with one additive `"direction"` field.
- **Two historical backtests** (`mytrader/gold_backtest.py`), refreshed roughly once
  a day (`GOLD_BACKTEST_REFRESH_MAX_AGE_DAYS = 1` — each new trading day's price/FRED
  data is folded in before the next outlook is built, not left stale for a week):
  **episode-based** for the 5 macro signals (rare regime-shift events — every
  historical occurrence's forward return, at 1-day/5-day/1-3-6-12-24-month horizons)
  and **state-conditioned** for the 6 technical indicators (common daily readings —
  every trading day's forward return conditioned on that day's state, at
  1-day/5-day/1-month horizons only, since a 14-day RSI or 20-day moving average has
  nothing meaningful to say 12+ months out).

Three horizon sections — Today/Tomorrow, This Week, This Month — all built by the
same shared lookup (`gold_outlook._horizon_read()`), differing only in which
`(horizon_unit, horizon_value)` they query against the backtest results. Every
currently-active signal/indicator state is looked up against its own real historical
track record (N always shown) — Today/Tomorrow and This Week are genuinely
backtest-grounded, not resting on documented rationale the way an earlier draft of
this feature did. Confidence is labeled per horizon and scales with how much history
backs it — lowest for Today/Tomorrow (smallest samples, shortest horizon), highest
for This Month (largest samples, longest-validated horizon, plus a seasonality
component).

**Weighted synthesis** (changed 2026-08-07). Each component's vote toward the
Today/Tomorrow, This Week, and This Month leans is weighted by its own historical
win-rate's distance from 50% (`gold_outlook._weight()`) — a signal with a 63%
win-rate counts for more than one sitting at 51%, rather than every active signal
getting an equal flat vote. Direction itself (`gold_outlook._label()`) also switched
from "does this state's mean beat an unconditioned baseline" to "is this state's own
win-rate above 50%" — a more direct, internally-consistent read of "how often did
gold go up after this state." Both changes were driven by a real problem: an
unweighted headcount let 6 highly-correlated, near-zero-edge technical readings
outvote 1-2 genuinely stronger signals (e.g. the 200DMA cross) just by outnumbering
them.

**Validated by honest walk-forward backtesting, not by fitting to any specific
day.** Point-in-time reconstruction of the Today/Tomorrow read across a full year
(252 trading days, 36 rolling 7-day blocks, zero threshold changes between blocks)
showed the unweighted design landing at 48.8% (calls made) / 42.1% (counting "mixed"
no-calls as misses) — the weighted design above raised that to **56.3%**, with zero
no-call days (weighted totals essentially never tie exactly). 56.3% is the real,
honest number — a genuine ~6-point edge over a coin flip, not the artificially high
number a per-day-tuned system would show and then fail to reproduce on new data. No
model of this kind (public price/macro data only) should be expected to land
anywhere near 90%+ on daily direction — a claim that high is itself a signal
something's overfit or leaking future information, not a sign of a better model.

**MACD/RSI/Stochastic excluded from the vote, kept as context** (changed
2026-08-07, same session as the weighting change). A follow-up walk-forward test
showed the moving-average trend states alone matched the full weighted vote
exactly — MACD/RSI/Stochastic weren't adding measurable value to a next-day
direction call, consistent with what these tools are actually designed for
(RSI/Stochastic are overbought/oversold mean-reversion *timing* signals, MACD is
momentum *confirmation* — none are direction predictors on their own). They're
still computed and still shown in `gold-outlook.md`, labeled "context only, not
counted in the lean," rather than silently disappearing.

**COT (Commitments of Traders) positioning added** (`mytrader/gold_cot.py`,
2026-08-08) — the first signal in this feature built from what large speculators
are actually doing with capital, not from price or macro data. Reads the CFTC's
public Socrata API (free, no login, weekly, history to 1986) for COMEX gold
futures, computes Larry Williams' COT Index (a standard, widely-cited
methodology: current net non-commercial position's percentile rank within a
trailing `COT_LOOKBACK_WEEKS` (156, ~3 years) window), and classifies
`extreme_long`/`extreme_short` (index ≥90/≤10) vs `neutral`. Direction is derived
the same way as every other signal — empirically, from its own backtested
win-rate, not assumed textbook contrarian theory: confirmed live 2026-08-08 that
`extreme_long` has actually been trend-*confirming* for gold in the 2018+
validation window (56–71% win-rate for continued gains), not the classic
contrarian-reversal read. Votes directly (`DIRECTIONAL_VOTE_SIGNALS`), same
weight formula as everything else. Honest point-in-time walk-forward testing
(both the standard 1-year window and a separate 2-year window chosen specifically
to include COT's last active stretch, which ended 2025-02-10) found it never
single-handedly changed a Today/Tomorrow call in either window — not a flaw, just
an honest result: COT extremes persist for consecutive weeks and, empirically,
tend to already agree with whichever direction the trend signals (ma20/ma50) are
pointing when active, so it currently acts as confirmation rather than a
deciding vote. Real, tested, live-validated signal; simply hasn't been the
swing vote yet in the windows tested.

**Real worked example** (live run, 2026-08-08, post-reweighting):

```
### Today / Tomorrow -- bullish lean (4/4 signals, 100% of weighted edge) (confidence: low -- shortest horizon, smallest per-signal samples)
- ma20_trend (above): N=1225, mean 0.04% vs baseline 0.06%, win-rate 54.2%
- gold_trend (crossed_below): N=35, mean 0.14% vs baseline 0.06%, win-rate 62.9%
- Expected daily move (ATR-based): ~$83.13 (1.89%)
- Nearest resistance: $4432.3, nearest support: $3964.2
- macd_histogram (positive): N=1121, ... win-rate 54.4% (context only, not counted in the lean)

### This Month -- bullish lean (5/5 signals, 100% of weighted edge) (confidence: highest -- most historical data, longest-validated horizon)
- real_yields (elevated): N=12, mean 3.1% vs baseline 1.19%, win-rate 75.0%
- seasonality: this calendar month has historically averaged 2.27% (median 2.9%, win-rate 73.1%, N=26 years)
```

Monitor writes the full file every run; `my-trader-report.md` gets a one-line pointer
under "### Gold Outlook". `investments/my-trader/mytrader/main.py`'s `gold-backtest`
subcommand forces an immediate full recompute on demand (bypassing the ~1-day cache)
— useful right after changing a `GOLD_TA_*`/`GOLD_BACKTEST_*` threshold in
`config.py`.

**Non-goals**: no buy/sell directive anywhere, no autonomous trading action — every
horizon gets a real directional *guess* (Shaun: "This isn't you deciding what I
should do. This is you giving a guided guess"), always caveated with sample size and
never presented as proof. See `.agent/plans/gold-tracker-phase2-outlook.md` for the
full design rationale, including why the two backtest methodologies differ and why
the refresh cadence is daily rather than weekly.

## SEC Filing Reads (principles_fit)

Added 2026-08-03 (`mytrader/sec_filings.py`). `principles_fit` — the opt-in, Find-only
check that grades Find's own thesis against all 9 investor frameworks — now folds in
each US-listed ticker's latest 10-K, 10-Q, and DEF 14A (proxy statement) primary-source
disclosures, fetched directly from SEC EDGAR (free, no API key, just a descriptive
`User-Agent`). Business/Risk Factors/MD&A sections are pulled from 10-K/10-Q; executive
compensation and CD&A sections from DEF 14A. Each filing's relevant sections are
summarized via one `sdk_compat` LLM call (`config.SEC_FILING_SUMMARY_MODEL`, default
`"sonnet"` — a Claude-shaped tier alias that resolves through whatever backend is
active, e.g. `gpt-5.4` under the current Codex backend) and folded into the same thesis
text all 9 principle files grade — so the frameworks are informed by what the company
itself discloses, not just yfinance's derived ratios.

**Caching**: two independent caches, deliberately different from `principles_fit`'s own
"never cache the thesis" policy (the thesis itself is still rebuilt fresh every Find
call). `sec_cik_map` (ticker→CIK, bulk-refreshed every `SEC_CIK_MAP_REFRESH_DAYS`, 30)
and `sec_filing_cache` (per-ticker/filing_type summary, invalidated only when SEC
publishes a new accession number for that filing type — filing text is static between
filings, so re-summarizing on every Find call would be wasted LLM spend for no benefit).
A stale cached summary is still returned if a live re-fetch fails, rather than dropping
that filing type entirely.

**Degradation**: non-US tickers (SEC EDGAR has no ASX/LSE/etc coverage) fall through a
plain CIK-lookup miss straight back to today's stats-only `principles_fit` behavior — no
exception, no visible difference beyond the transparency note below.

`find`'s output shows `(includes SEC filing read: 10-K, 10-Q, ...)` under the Principles
fit section whenever real filing content informed the run.

**Known limitations**:
- **DEF 14A section-finding is a blunt heuristic** and the biggest technical-risk area —
  proxy statements use free-form section titles with no reliable Item-header convention
  (unlike 10-K/10-Q). Individual filers also don't always use the exact SEC-caption
  wording (confirmed against a real 2026 KO proxy: it never uses the literal phrase
  "security ownership of certain beneficial owners" anywhere, so that section is simply
  skipped for filers phrasing it differently — a known, accepted gap, not a bug).
- **CIK-map staleness**: a ticker that IPO'd in the last `SEC_CIK_MAP_REFRESH_DAYS` (30)
  days may not resolve to a CIK yet even though SEC has since added it.
- `_latest_filing_entry` only checks the submissions JSON's `"recent"` array (SEC's own
  docs describe it as covering roughly the last ~1000 filings / most recent few years),
  not the paginated `"files"` array used for very long filing histories — in practice
  "most recent 10-K/10-Q/DEF 14A" should always land in `"recent"`.

## ASX Announcement Reads (principles_fit)

Added 2026-08-03 (`mytrader/asx_announcements.py`), the ASX-listed sibling of the SEC
filing reads above. Each `.AX`-suffixed ticker's latest Annual Report and Half-Year
Report are fetched as PDFs from the ASX Market Announcements Platform (free, no login
— a two-hop scrape: list announcements for the ticker/year, follow each announcement's
legal click-through interstitial, extract the real PDF URL from a hidden form field).
PDF text is extracted via `briefs-finance`'s own `scripts.extract.extract_text`
(pdfplumber, falling back to PyMuPDF+pytesseract OCR for scanned PDFs), a heading-search
heuristic pulls the Operating and Financial Review / Review of Operations / Risk
Management / Directors' Report sections, and each report's relevant sections are
summarized via one `sdk_compat` LLM call (`config.ASX_ANNOUNCEMENT_SUMMARY_MODEL`,
default `"sonnet"`, reusing the SEC filing reads' already-locked-in tier) and folded
into the same thesis text all 9 principle files grade.

**Caching**: one cache table, `asx_announcement_cache`, same invalidation philosophy as
`sec_filing_cache` — invalidated only when a new ASX announcement id (`idsId`) appears
for that (ticker, announcement type), not time-based. A stale cached summary is still
returned if a live re-fetch fails, rather than dropping that announcement type entirely.
No CIK-equivalent bulk map/cache is needed — ASX's announcement-list endpoint takes the
bare ticker code directly (`.AX` suffix stripped), a genuine simplification vs the SEC
build, not a missing piece.

**Degradation**: non-ASX tickers (no `.AX` suffix) return immediately with zero network
calls, straight back to today's stats-only `principles_fit` behavior.

**Year fallback**: if the current calendar year's announcement list is missing a target
type (confirmed live 2026-08-03: neither BXB nor WES had lodged their FY2026 Annual
Report yet, since both have a 30 June fiscal year end and annual reports typically lodge
Aug–Oct), the previous year's list is checked as a fallback for that type.

`find`'s output shows `(includes ASX announcement read: Annual Report, ...)` under the
Principles fit section whenever real announcement content informed the run.

**Known limitations**:
- **Heading-search is a blunt heuristic, the biggest technical-risk area** — same class
  of problem as the SEC filing reads' DEF 14A heuristic, but with a different real
  failure mode: ASX report headings repeat as running per-page headers spanning many
  pages of one section (confirmed live: WES's real 2025 Annual Report repeats
  "operating and financial review" 29 times across a ~40-page chapter), so neither
  "first occurrence" nor "last occurrence" alone is reliable — the first occurrence is
  often an isolated table-of-contents line, and the last occurrence can land in an
  unrelated subsection near the chapter's end. The current heuristic treats a lone early
  occurrence far ahead of the next one as a TOC line and skips to the second; this is
  still best-effort, and the LLM summarization step is expected to filter remaining
  window noise, not this extraction step.
- **Apostrophe encoding**: real filer PDFs render the possessive apostrophe in headings
  like "Directors' Report" inconsistently after PDF extraction (confirmed: pdfplumber
  renders it as a mangled replacement character for at least one real filer) — heading
  candidates and extracted text are both normalized (apostrophe-bearing characters
  replaced with a space) before matching to work around this.
- **Announcement-type title matching** is validated against real BXB/WES titles only —
  a different filer's wording for "Annual Report" or "Half-Year Report" equivalents may
  not match `config.ASX_ANNOUNCEMENT_TYPES`' patterns and would silently skip that type.
- **Appendix 4E** (preliminary final report) is not a separately-tracked type in v1 —
  WES's real Annual Report title already includes "(including Appendix 4E)" so its
  content is captured incidentally, but it isn't a standalone signal.

## Briefs Finance Candidate Sync

**Runs automatically once a day as part of `monitor`** (re-enabled 2026-07-19, same
day it was first turned off — the original problem was the first backlog sync
flooding `watchlist.md` with 270 stale/AI-hype picks in one shot by writing
directly into the watchlist; once the target became the separate pending-review
staging area below, running it unattended stopped being a problem). Also runnable
on-demand via the `sync-candidates` CLI subcommand.

New, non-excluded `briefs-finance` `recommendations` rows land in a separate
`pending_candidates` table, rendered as `investments/my-trader/synced-candidates-pending-review.md`
— never written directly into the watchlist/`watchlist.md`, which stays
exactly what Shaun has explicitly curated. Watermarked (`sync_state` table) so re-runs
don't reprocess the same recommendations. `my-trader-report.md` shows a "New Candidates
Synced (Pending Review)" section every run.

Review the pending file and either:
- `promote-candidate --ticker X [--bucket unassigned] [--asset-type stock] [--status raw]`
  — moves it into the real watchlist
- `dismiss-candidate --ticker X` — discards it without adding to the watchlist

## Scale Hints on Raw Figures

`checks/scale.py`, added 2026-08-03 at Shaun's request ("so I know if the figure is
good or not — otherwise I'll have no idea or forget"). Appends a `N/10 — label` hint
next to raw figures in `valuation.py` (PE) and `balance_sheet.py` (debt/equity,
current ratio, ROE fallback) — the two checks that print numbers with no built-in
explanation of whether they're good. `opportunity.py` already states its threshold
comparisons in words (e.g. "ROE 30.6% at/above 15.0%") so a scale there would be
redundant, and was deliberately left unchanged.

Every anchor reuses a threshold that already exists in `config.py` (PE_CHEAP/RICH,
DEBT_TO_EQUITY_FLAG, CURRENT_RATIO_FLAG, ROE_FLAG_THRESHOLD_PCT,
OPPORTUNITY_ROE_MIN_PCT) — no new signal or verdict logic, just a display label. Two
new named constants were added purely as the "good" end of the display range:
`DEBT_TO_EQUITY_IDEAL` (0 — debt-free) and `CURRENT_RATIO_HEALTHY` (2.0 — the
conventional "2:1 is healthy" liquidity rule of thumb, same citation class as
`HOUSING_P2I_FLAG_RATIO`'s "~2.5-3x considered affordable by convention").

**Deliberately not scaled**: dividend trend (a %-change with no natural ceiling, not a
bounded level) and expense ratio (no existing sourced good/bad threshold in
`config.py` to anchor against) — a possible follow-up if Shaun wants it, not built
here to avoid inventing a threshold the way the original opportunity.py thresholds
were once called out for doing.

## Relationship to the `investments` Skill

`investments` (briefs-finance) does PDF ingestion, backtesting, and a 0-100% likelihood
score against 9 investor principles. `my-trader`'s Find layers that score in as one
additional input — Shaun's own criteria (sustainable, competitive edge, pricing power)
plus the 7 checks above are the primary basis.

**Compute-if-missing** (changed 2026-07-19, Shaun: "throw everything you have at
assessing it"): `engine.run_assessment()` — shared by both Find and Monitor — now
computes a fresh briefs-finance score on the spot (`scripts.score.compute_score`,
~9 haiku LLM calls, one per investor-principle file) whenever a ticker has a
non-excluded Briefs Finance recommendation but no score yet. The result is persisted
to `likelihood_scores`, so this only costs anything the *first* time a given ticker
is assessed — every call after that reads the cached row. Returns `None` only when
the ticker was never a Briefs Finance recommendation at all (no `buy_thesis` to score
against the 9 principles, nothing to compute regardless). Because Find and Monitor
share this function, Monitor's first run after a backlog of unscored
holdings/watchlist tickers builds up will take noticeably longer than usual (one
compute_score call per missing ticker) — steady-state runs are fast again once
everything currently tracked has a cached score.

**Backtest refresh on every call** (also 2026-07-19): unlike the score, a
ticker-scoped `scripts.backtest.run_backtest(ticker_filter=...)` call runs on *every*
`run_assessment()`, not cached once — 3m/6m/12m outcome windows genuinely elapse over
time, so there's real value in refreshing rather than caching. Cheap compared to
scoring (yfinance price lookups only, no LLM calls). No-op for tickers with no Briefs
Finance recommendation. Note: `ingest` never auto-runs `backtest` — they're separate
commands (confirmed 2026-07-19 after Shaun asked why a same-day-ingested pick showed
no score despite `backtest` having been run manually during ingestion — `backtest`
only populates `outcomes`, not `likelihood_scores`).

## Known Limitations

- `BERKSHIRE_HOLDINGS` starts empty in `mytrader/config.py` — no free API for 13F data;
  manually maintained, update periodically from Berkshire's 13F filings.
- Portfolio concentration aggregation is currency-naive (no FX normalization across
  USD/AUD holdings) — matches the previous hand-maintained holdings.md.
- ETF expense-ratio drift can only be detected once a ticker has been checked twice —
  Monitor's repeated daily runs are what make this detection real in practice.
- Monitor (Phase B) and macro indicators + candidate sync (Phase C) are now built.
- Phase C's 4 macro threshold constants (`MOVE_INDEX_FLAG_LEVEL`,
  `HOUSING_P2I_FLAG_RATIO`, `CONSUMER_SENTIMENT_FLAG_LEVEL`, `RECESSION_PROB_FLAG_PCT`)
  are best-guess defaults set without live data access — tune after real output is
  observed.
- `candidate_sync` hardcodes `asset_type="stock"` since briefs-finance's
  `recommendations` table has no asset-type column — a rare mislabeled ETF
  recommendation is a cosmetic snapshot-display issue only.
- The MOVE index may permanently read `"unknown"` if `^MOVE` doesn't resolve via
  yfinance — see `handoff.md` for what was observed in this environment.

## Setup (first time)

```powershell
uv sync --directory investments/my-trader --extra dev
```
