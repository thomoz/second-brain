# Pre-Plan: my-trader Find + Monitor Tool

## Purpose

We'll use this to eventually create a structured plan which Shaun will execute to
create a tool or tools for a) picking stocks, ETFs, or assets (e.g. gold or bonds) to
purchase, and b) performing a daily check on current stocks and assets I own to see if
more should be bought or if instead we should sell some or all of individual holdings.

## Status: Pre-planning — discuss across sessions, do not build yet

This is a working scratchpad, not a spec. Add to it, argue with it, cross things out
across as many sessions as it takes. Once Shaun is happy with the shape of it, load
this file and run `/plan-feature` to turn it into a structured, executable plan under
`.agent/plans/`. Nothing in here should be built directly from this doc.

## Confirmed So Far (at a glance)

Only items that have actually been discussed and reasoned through go in this table.
Everything else — no matter how long it's been sitting in the Candidate Universe
section below — is raw material, not a decision. One row per item, added only after
a real discussion, not just because it appeared in a transcript or old note.

| Ticker | Company/Fund Name | Type | Chart | Bucket | Allocation % | Dividend | 10Y Return | Status |
|--------|--------------------|------|-------|--------|--------------|----------|------------|--------|
| VRTX | Vertex Pharmaceuticals Inc | Stock (US, NASDAQ) | tradingview.com/symbols/NASDAQ-VRTX | 1 — Long-term hold | TBD | None (0% — reinvests in R&D) | +458% (price; no dividend, so = total return) | Good candidate — CF franchise moat/pricing power, non-cyclical; watch patent cliff timeline and drug-pricing policy risk |
| PMGOLD (core) | Perth Mint Gold Structured Product | ETF (ASX) | tradingview.com/symbols/ASX-PMGOLD | 3a — Gold, permanent core | ~5-10% (Dalio All Weather reference point, not yet fitted to Shaun's own portfolio size) | None (gold pays no yield) | +257% (price; $16.12 → $57.56, AUD gold price, no dividend) | **Confirmed 2026-07-19** — never-sell ballast, hold/sell rule = no formal rule (periodic check-in) |
| PMGOLD (tactical) | Perth Mint Gold Structured Product | ETF (ASX) | tradingview.com/symbols/ASX-PMGOLD | 3b — Gold, timed tactical | TBD, smaller than the core sleeve | None (gold pays no yield) | +257% (price; $16.12 → $57.56, AUD gold price, no dividend) | **Confirmed 2026-07-19** — same vehicle as the core sleeve, tracked as a separate position; conditions-dependent, hold/sell rule = no formal rule (periodic check-in) to start |
| BRK.B | Berkshire Hathaway Inc (Class B) | Stock (US, NYSE) | tradingview.com/symbols/NYSE-BRK.B | 1 — Long-term hold | TBD | None (0% — long-standing policy, reinvests/buys back instead) | +227% (price; no dividend, so = total return) | Good candidate — proven capital allocation, diversified moats; watch succession (Abel) and index-fund overlap |
| V | Visa Inc (Class A) | Stock (US, NYSE) — current holding, $35.89 mkt value | tradingview.com/symbols/NYSE-V | 1 — Long-term hold | TBD | Low (0.81%) | +340% (total return, dividends reinvested; sources range 325-400% depending on exact end date) | **Confirmed 2026-07-19** — Shaun's call: position is low-value enough not to warrant deep scrutiny, keep as Bucket 1. The Berkshire-exit question below remains an open research task, just no longer a blocker for this small a position |
| LLY | Eli Lilly & Co | Stock (US, NYSE) — current holding, residual $0.12 mkt value (0.0001 shares) | tradingview.com/symbols/NYSE-LLY | 1 — Long-term hold | TBD | TBD — not researched | TBD — not researched | **Confirmed 2026-07-19** — Shaun's call: position value is negligible, added to Bucket 1 without deep scrutiny. Pharma pricing-power fit was already flagged as plausible in the raw candidate list; not independently verified this session |
| LYV | Live Nation Entertainment Inc | Stock (US, NYSE) — current holding, $72.09 mkt value | tradingview.com/symbols/NYSE-LYV | 1 — Long-term hold | TBD | TBD — not researched | TBD — not researched | **Confirmed 2026-07-19** — Shaun's call: position is low-value enough not to warrant deep scrutiny, keep as Bucket 1 despite the real concerns raised in discussion (active DOJ antitrust suit targeting the Ticketmaster/Live Nation vertical integration, and correlation with Shaun's own live-events businesses) — those concerns are on record above, just not a blocker at this position size |
| HDV | iShares Core High Dividend ETF | ETF (US) | tradingview.com/symbols/AMEX-HDV | 1 — Long-term hold | TBD | Medium (2.85%, near the high end) | +136% (total return, dividends reinvested) | Candidate — quality/moat + high-dividend screen; relabeled from "staples ETF" (it's broader: 24% staples, 24% healthcare, 20% energy — the energy weighting brings real commodity cyclicality). Check top-10 holdings + Berkshire overlap before committing |
| SCHD | Schwab US Dividend Equity ETF | ETF (US) | tradingview.com/symbols/AMEX-SCHD | 1 — Long-term hold | TBD | High (~3.5-4%, dividend-growth screen) | +240% (total return, dividends reinvested) | Candidate — dividend aristocrats-style ETF, carried over from existing watchlist; not yet deeply discussed (no mechanics/overlap review done, unlike gold) |
| ASML | ASML Holding NV | Stock (Netherlands, NASDAQ) — **not currently held**; position was fully closed as of 2026-07-19 (see `investment-strategy.md`), discussed here purely as a re-entry candidate | tradingview.com/symbols/NASDAQ-ASML | 1 — Long-term hold | TBD | TBD — not yet researched this session | TBD — not yet researched this session | **Discussed 2026-07-19** — strong Bucket 1 fit: sole global EUV lithography supplier (genuine hardware monopoly, ~20 years/tens of billions to replicate), structural chip-demand tailwind, real pricing power (customers have no alternative supplier). Watch-outs are political/timing, not quality: export-control risk (blocked from selling most advanced tools to China), semiconductor capex cyclicality (lumpy near-term revenue despite intact long-term moat), customer concentration (TSMC/Samsung/Intel/SK Hynix). Note: not currently held — this verdict is about re-buying, not monitoring an existing position |

Allocation % is a starting anchor, not a commitment — expect it to move as buckets
fill out, position sizes get set against Shaun's actual portfolio total, and the
hold/sell rules get defined. Revisit every time a new row is confirmed.

10Y Return figures are cumulative (not annualized), pulled from third-party return
calculators/price data in mid-July 2026 — treat as an approximate snapshot, not a
precise or refreshed-daily number (exact figure shifts with the exact 10-year window
used). Where the holding pays no dividend, price return and total return are the same.
Refresh via the actual monitoring tool once built rather than trusting this table long-term.

Dividend bands used in this table: **None** (0%), **Low** (<1.5%), **Medium**
(1.5-3%), **High** (>3%) — rough guide, not precise, and yields move with price so
treat as a snapshot not a fixed fact.

## Parked Research Tasks

- **Why did Berkshire exit Visa (and Mastercard) in Q1 2026?** Sold alongside
  Amazon, UnitedHealth, and others under new CEO Greg Abel's first 13F. Was it
  valuation/profit-taking after ~15 years of huge gains, a broader strategic
  shift away from positions Todd Combs managed (he recently left Berkshire), or
  something moat-related? Resolve before finalizing V as a Bucket 1 holding.

**Rule added 2026-07-11**: before confirming any individual stock beyond Berkshire,
check whether Berkshire's own portfolio already holds it (or something that gives
similar exposure) — avoid unknowingly duplicating/concentrating on the same
underlying bet through two different tickers. Check via Berkshire's 13F filings —
e.g. cnbc.com/berkshire-hathaway-portfolio or quiverquant.com (Warren Buffett /
Berkshire Hathaway Inc holdings).

## What we know so far

- Confirmed 2026-07-11: this is a **separate new tool**, not an extension of
  `investments/briefs-finance/` — but may get combined with Briefs Finance later, so
  don't build anything that would make a future merge painful.
- See "## Purpose" above for the tool's purpose, in Shaun's own words (original
  phrasing 2026-07-11: "a tool that helps me find stocks and asset classes to invest
  in, then checks on them daily to see if anything needs to be adjusted"; expanded
  2026-07-19 into the a)/b) breakdown at the top of this file).
- Knowledge base: `investments/my-trader/investment-strategy.md` — vetted lessons,
  current holdings, watchlists. Written to be structured/parseable, not just a journal.
  Add new strategies/lessons there as we develop them; this pre-plan should reference
  it rather than duplicate it.
- **Confirmed 2026-07-11 — monitoring requirement**: the tool must check whether any
  held ETF (or fund-like holding, e.g. Berkshire) has released a new report —
  especially quarterly ones showing holding changes — so we can reassess a position
  when its underlying composition shifts, not just when its price moves. Ties into
  the Berkshire-overlap check above: reassessment isn't a one-time check at purchase,
  it needs to repeat whenever the underlying holdings change.
- **Added 2026-07-16 — individual-holding earnings reports**: the same monitoring job
  as above, but for individual stock holdings (VRTX, V, etc.) rather than funds — the
  tool should flag when a held company releases quarterly earnings so we can re-check
  the "sustainable / competitive edge / pricing power" criteria still holds. This is
  distinct from the macro leading-indicator checklist in `investment-strategy.md`
  (aggregate S&P earnings trend): a single company's report says nothing about a
  market-wide crash, it's a per-holding thesis check, not a timing signal.
- **Confirmed 2026-07-18 — inflation data requirement**: the tool must pull the latest
  US inflation data (CPI and core CPI) for **both** jobs, not just one:
  - **Per-holding**: when assessing any individual holding or candidate, check current
    inflation against that company's pricing-power thesis ("Companies must have the
    following" criteria) — a stock that clears the bar when inflation is low may not
    still be growing real income once inflation re-accelerates.
  - **Macro/timing**: feed into the leading-indicator checklist in
    `investment-strategy.md` alongside the Sahm Rule, Buffett Indicator, CAPE, etc. —
    inflation trend/direction is part of the timing picture, not just a per-holding
    check. Ties directly into the core-inflation staleness case caught in the
    2026-07-18 yield-curve transcript analysis (source claimed core inflation >3%;
    actual latest print was 2.6% and falling) — a concrete example of why this can't
    be a one-time lookup and needs to pull current data at assessment time.
- **Confirmed 2026-07-19 — trigger model**: Monitor runs scheduled/heartbeat-driven
  (like the existing `heartbeat.py`) so reassessment of current holdings happens
  automatically without Shaun needing to remember to check. Find can still be run
  manually on demand when screening a new candidate. This applies only to the main
  Find+Monitor tool — the transcript analysers (`analyse-transcript.md`,
  `analyse-daily-transcript.md`) stay chat-triggered regardless, since they require a
  transcript to be dropped in first.
- **Confirmed 2026-07-19 — output channel**: standalone file only, no Second Brain
  integration (not the daily log, not WhatsApp). Monitor's check runs automatically
  on schedule, but its output goes to its own file/log in `investments/my-trader/`
  that Shaun checks himself — nothing pushes into the daily-log or notification
  workflow.
- **Confirmed 2026-07-19 — scope of "adjustment"**: advisor note only, not drafted
  trade details. When Monitor flags a holding needing attention (thesis broken,
  dividend cut, valuation stretched), it states what changed and why it matters —
  Shaun decides what to do and executes it himself. No specific trade action gets
  suggested. Consistent with SOUL.md's advisor-mode default used elsewhere in the
  Second Brain.
- **Confirmed 2026-07-19 — data sources**: yfinance (prices/dividends, same as
  backtest/briefs-finance) **plus free news feeds**. Two things must be explicitly
  covered, not left implicit in "news feeds": (1) **fundamentals** — balance sheet /
  leverage data, feeding the Balance Sheet / Leverage Health check above — and
  (2) **latest earnings reports** per holding — feeding the individual-holding
  earnings-report monitoring requirement (2026-07-16, above) and the dividend-cut
  check. Confirm at build time whether yfinance's own fundamentals/earnings-calendar
  data is sufficient for these two, or whether a dedicated free source is needed —
  don't assume news-feed headlines alone satisfy either requirement.
- **Confirmed 2026-07-19 — tool architecture**: one tool, two modes sharing a single
  assessment engine (Find + Monitor), not two separate tools/codebases — the
  2026-07-18 proposal in this section's history is now signed off, no longer just
  proposed.
- **Confirmed 2026-07-19 — Find interaction model**: conversational only, no direct
  CLI. When Shaun wants to check a stock/ETF/asset he doesn't currently hold (e.g.
  "check TICKER" or "what do you think of this stock"), he asks in chat and Claude
  runs the tool behind the scenes and reports back — mirrors how the existing
  `investments` skill already wraps briefs-finance's `assess` command
  conversationally. No separate terminal step required.
- **Confirmed 2026-07-19 — alert philosophy**: high-bar, material-changes-only.
  Monitor surfaces genuinely thesis-relevant events (a dividend cut, an earnings miss
  against the pricing-power criteria, a macro indicator crossing a known trigger
  level — e.g. Sahm Rule firing, CAPE crossing 40) rather than reporting full state
  every run. Quiet runs stay quiet. Matches SOUL.md's brief/no-information-overload
  style. Exact numeric thresholds per check (what % dividend cut, which specific
  levels trigger each macro indicator) are implementation detail for the actual
  build, not decided here.
- **Confirmed 2026-07-19 — tech stack + directory location**: my-trader stays a
  **separate project** in `investments/my-trader/` — own `scripts/`, own
  `pyproject.toml`/`uv.lock` — rather than living inside `briefs-finance/scripts/`.
  Preserves the 2026-07-11 decision that this is "a separate new tool, not an
  extension of `investments/briefs-finance/`." It imports `config.py`/`db.py` (or
  reads briefs-finance's DB directly) across the folder boundary — via a uv workspace
  or editable path dependency, decided at build time — to satisfy the Briefs Finance
  report integration requirement below without merging the two codebases. Trade-off
  accepted knowingly: two `pyproject.toml`/lockfiles to maintain, in exchange for
  keeping the tools genuinely separable if one is ever split off or open-sourced
  independently later.
- **Confirmed 2026-07-19 — coupling mechanism (resolves "decided at build time"
  above)**: root-level **uv workspace**, my-trader imports briefs-finance's
  `db.py`/`config.py` directly as a path dependency — not subprocess/CLI calls into
  briefs-finance, not duplicating constants like `DEFENSE_TICKERS`. Cleanest reuse;
  accepted trade-off that the two projects' environments/schemas are now coupled.
- **Confirmed 2026-07-19 — Monitor alert signal**: alongside the standalone output
  file (no daily-log/WhatsApp push, per "output channel" above), Monitor reuses the
  existing `send_toast_notification` (`.claude/scripts/notifications.py`, already
  wired into `heartbeat.py`) for a bare "N items flagged, check my-trader" ping.
  Pure silent-file-only was considered and rejected — a high-bar "material changes
  only" alert nobody gets pinged about defeats the point of Monitor running
  unattended.
- **Confirmed 2026-07-19 — Briefs Finance report integration**: when a new Briefs
  Finance report is ingested (`investments/briefs-finance` `ingest` command),
  the tickers/theses it extracts should automatically flow into my-trader as new
  Find candidates — not sit passively in briefs-finance until Shaun happens to ask
  about that specific ticker. This is the concrete answer to the
  "Merge-with-Briefs-Finance path" question: not a full codebase merge, just this
  one data-flow connection (briefs-finance ingestion → my-trader candidate pool).
  Exact mechanism (shared DB read, a hook after ingest, a periodic diff) is
  implementation detail for the build.
- **Confirmed 2026-07-19 — Find/scoring workflow**: Shaun's own criteria are the
  primary/core scoring basis — the "Companies must have the following" bar in
  `investment-strategy.md`, plus everything confirmed in this file's Assessment
  Checks and Monitoring Indicators sections (inflation, Berkshire overlap,
  balance sheet/leverage, dividend growth, FX
  exposure, concentration, etc.). Briefs-finance's existing 0-100% likelihood score
  against 9 investor principles gets pulled in as an **additional input layered on
  top**, not a replacement for Shaun's own criteria — this is the core idea of the
  tool, not a secondary feature.
- **Confirmed 2026-07-19 — data source of truth**: the database (shared with
  briefs-finance per the tech-stack decision above) is the source of truth for
  current holdings and the watchlist/candidates, not a hand-edited markdown table —
  needed because Find writes new candidates in automatically (Briefs Finance
  integration above) and Monitor needs to iterate holdings programmatically. But the
  tool must **auto-regenerate a glanceable markdown snapshot** of current holdings
  and the watchlist every time it runs, so Shaun always has an up-to-date,
  human-readable file to open — he never looks at the database directly, and never
  hand-syncs it either. `investment-strategy.md`'s Current Holdings table and this
  file's Candidate Universe become historical/reference once the tool exists; the
  live version is the auto-generated snapshot. Interim manual versions of both exist
  now — `holdings.md` (current positions) and `potential-holdings.md` (watchlist, one
  flat table, Status column shows what's actually been discussed vs. raw) — as
  glanceable references ahead of the tool existing. Keep these in sync with the
  Confirmed So Far table and Candidate Universe below by hand until the tool takes
  over.
- **Confirmed 2026-07-19 — target allocation % deferred**: Allocation % (what
  fraction of the total portfolio a holding *should* eventually be, not what it
  currently is) is only populated for PMGOLD and TBD everywhere else. Bundled into
  the already-deferred hold/sell-rules discussion below rather than decided now —
  most of the roster needs to be settled before percentages across it mean much.
  Dropped the column from `potential-holdings.md` for now since an all-TBD column
  wasn't adding anything; still tracked in this file's Confirmed So Far table.
- **Confirmed 2026-07-19 — Monitor's scope, two jobs**:
  1. **Current holdings** — check every owned position (`holdings.md`) against all
     confirmed checks (Assessment Checks, Monitoring Indicators, criteria) and advise
     on any action to take (per the advisor-note-only scope confirmed above).
  2. **Potential holdings / watchlist** — check every vetted-but-unowned candidate
     (`potential-holdings.md`'s rows marked as actually discussed, not the raw ones)
     against all the same checks and advise whether entry looks like a good idea now.
     This is the concrete answer to the earlier open question about Bucket 2/3
     timing — Monitor doesn't just sit
     idle on unowned candidates waiting for Shaun to ask, it actively watches them.
  Both jobs follow the same alert philosophy (material changes/signals only, not
  full-state noise) and the same output (standalone file, no Second Brain push).
  **Explicitly out of scope**: proactive discovery of brand-new candidates beyond
  the existing watchlist (considered and rejected 2026-07-19) — Shaun does his own
  screening for what's worth looking at, and `analyse-daily-transcript.md` may
  surface new ones too. The tool investigates current and potential holdings; it
  doesn't go looking for new ones on its own.
- **Confirmed 2026-07-19 — ethical filter inherited**: my-trader applies the same
  ethical exclusion filter briefs-finance already uses (no defense/military stocks)
  across everything it checks — consistent with layering briefs-finance's scoring in
  as an input to Find (confirmed above).
- **Confirmed 2026-07-19 — adding/updating a holding**: conversational only, same
  pattern as Find. Shaun tells Claude in chat when he buys/sells/adjusts a position
  (e.g. "I bought 10 shares of VRTX at $452") and the tool updates the database and
  regenerates the snapshot — no separate form, CLI, or manual DB edit, and no bulk
  import mechanism.
- Related existing tools (context, not necessarily reused):
  - `investments/briefs-finance/` — PDF ingestion, 0-100% likelihood scoring against
    9 investor principles (Buffett, Dalio, etc.), ethical filter (no defense/military)
  - `investments/backtest/` — SPY walk-forward backtester, Streamlit UI

## Open questions to work through together

None currently — all of the tool-mechanics questions that lived here were resolved
2026-07-19 (see "What we know so far" above for trigger model, output channel, scope
of "adjustment," data sources, tool architecture, Find/scoring workflow, Briefs
Finance integration, tech stack, alert philosophy). Remaining work is populating the
actual portfolio (Candidate Universe below) and the hold/sell rules (Deferred
section below) — new open questions will likely surface as that continues; add them
back here when they do.

## Assessment Checks (Confirmed 2026-07-19)

What the tool checks per-holding/candidate, beyond the requirements already listed
above (Berkshire overlap, quarterly/earnings reports, inflation data). Surfaced
2026-07-18 from transcript analysis, confirmed 2026-07-19 — Monitor and Find must
both apply all of these, not just the items already in "What we know so far."

- **Dividend cut / growth-rate monitoring** — SCHD, HDV, and the dividend-aristocrats
  framing all lean on dividends *growing*, not just existing. Nothing currently flags
  an actual cut or a slowing growth rate specifically; the existing earnings-report
  check is too generic to catch this on its own.
- **Per-holding valuation check** — CAPE/Buffett Indicator (in `investment-strategy.md`)
  cover the *market*, but nothing checks whether an individual holding (VRTX, BRK.B,
  etc.) has gotten expensive relative to its own history or peers. Ties to the
  "Valuation check" hold/sell option already sitting unused in Deferred Hold/Sell Rules
  below.
- **Balance sheet / leverage health** — "sustainable" is one of Shaun's three criteria
  (see "Companies must have the following"), but nothing checks debt levels or
  credit-rating actions, which is usually where "sustainable" breaks first.
- **Currency/FX exposure (AUD investor, USD-heavy holdings)** — not covered anywhere
  outside the gold research (PMGOLD's "no FX/withholding friction as AU resident" note
  is gold-specific). AUD/USD movement changes real returns on the US stock holdings
  independent of the stock's own performance.
- **Portfolio-level concentration/correlation** — the Berkshire-overlap rule only
  checks new candidates against Berkshire. There's an ad hoc note that LYV overlaps
  with Shaun's own hosting-business risk, but no standing rule to check new candidates
  against the *whole* existing portfolio, or against Shaun's business income risk more
  generally, for concentration.
- **Sector/geopolitical exposure per-holding** — the Geopolitical Risk (GPR) Index and
  the Strait of Hormuz/energy-price-shock example (in `investment-strategy.md`) are
  currently framed as macro-only. HDV's ~20% energy weighting is flagged as a concern,
  but there's no standing rule to check any holding's sector concentration against
  active geopolitical flashpoints.
- **ETF mechanics drift** — the existing "new report" check (`What we know so far`)
  catches holdings-composition changes, but not expense-ratio changes or
  index-methodology changes, which also silently change what you own.

## Monitoring Indicators (Confirmed 2026-07-19)

Macro indicators the tool tracks as part of Monitor, feeding the leading-indicator
checklist in `investment-strategy.md` alongside the Sahm Rule, Buffett Indicator, CAPE,
etc. Surfaced via transcript analysis (`analyse-transcript.md`), confirmed 2026-07-19.

**Confirmed 2026-07-19 — surfaced 2026-07-18 from "The Yield Curve Just Did Something
Not Seen Since 1929" transcript analysis**

- **MOVE index** (ICE BofA MOVE — bond market's "VIX," Treasury option-implied
  volatility) — a complacency/fear gauge for the bond market, distinct from the
  existing high-yield credit-spread indicator in `investment-strategy.md` (spreads
  price default risk; MOVE prices rate volatility). Confirmed low as of early 2026
  (lowest since 2021) — candidate to watch alongside the existing checklist, not
  independently verified as a standalone predictor.
- **Housing price-to-income ratio** — national ratio ~5x median home price to median
  household income vs. ~2.5-3x considered "affordable" by convention (fact-checked,
  confirmed 2026-07-18). Distinct from the existing real estate/REITs inflation-hedge
  lesson — this is a standalone affordability/valuation stress indicator, not a hedge
  mechanic.
- **University of Michigan Consumer Sentiment Index** — direct consumer-sentiment
  survey, distinct from the existing "retail sales vs. income growth" indicator (a
  spending-behavior proxy). Hit a record low (44.8) in May 2026, partially recovered
  to 49.5 by June 2026 — note the rebound if this gets picked up, don't treat the May
  low as the current reading.
- **NY Fed recession-probability model** (3-month/10-year spread, Estrella-Mishkin
  probit model) — a more precise, quantifiable version of the generic "yield curve"
  indicator already on the leading-indicator checklist in `investment-strategy.md`
  (which references the 2yr/10yr spread). Published model, ~25-30% 12-month recession
  probability as of mid-2026 (fact-checked, confirmed 2026-07-18). Worth reconciling
  with the existing yield-curve bullet rather than treating as fully separate.
- **Bull-steepener vs. bear-steepener distinction** — refines (doesn't replace) the
  existing yield-curve bullet in `investment-strategy.md` ("watch for it rolling
  over/re-normalizing, not just the inversion itself") by naming the mechanism: a
  bull steepener (short rates falling on Fed cuts) is the benign resolution, a bear
  steepener (long rates rising on inflation/debt concern) is the historically
  concerning one. Not independently verified as its own tested signal — flagged as a
  refinement to fold into the existing bullet, not a new standalone indicator.

## Candidate Universe (draft — assess before finalizing anything)

Working list to run through the tool once it exists, split into three behavior
buckets per Shaun's framing (2026-07-11). Existing watchlist entries from
`investment-strategy.md` have been folded in below rather than duplicated across
two files.

**Important distinction (added 2026-07-11 after Shaun flagged it): almost nothing
below has actually been discussed.** Everything except gold is just carried over
from old watchlist notes or the YouTube transcript — raw material, not vetted.
Gold is the only entry so far that's been through real back-and-forth (mechanics,
cost comparison, physical vs. ETF, why people hold it, tied back to Shaun's own
"sometimes hold sometimes sell" framing). Don't treat an item's presence in a
bucket as a sign it's been through that same process — it hasn't, until marked
DISCUSSED below.

**Resolved 2026-07-19**: gold's bucket question (permanent ballast vs. actively
timed) — see Bucket 3 below for the answer (both, as two separately tracked
positions using the same PMGOLD vehicle).

### Bucket 1 — Long-Term Holds (never timed, accumulate + hold indefinitely)
**NOT DISCUSSED — raw list, carried over from old watchlist notes.**
Must meet Shaun's existing criteria: sustainable, competitive edge, pricing power.

- strong general performers: BRK.B (Berkshire Hathaway)
- to check if they perform well during crashes: VRTX Vertex Pharmaceuticals, VISA, HDV — iShares Core High Dividend ETF (NOT a staples ETF — quality/moat + high-dividend screen, ~24% staples/24% healthcare/20% energy, so it carries real commodity cyclicality despite the "defensive" framing), IXI.AX — iShares Global Consumer Staples ETF management fee 0.41%; VDC — Vanguard Consumer Staples ETF Fee shown as 0.09%; XLP — Consumer Staples Select Sector SPDR ETF Fee 0.08%
. Dollar shop style shops: DG — Dollar General; DLTR — Dollar Tree; FIVE — Five Below; OLLI — Ollie’s Bargain Outlet; Dollarama - taking over reject shop. WFC : Wells Fargo & Co
- likely growth stocks: Uber
- Joby Aviation (speculative)
- Safe stocks (are they?): MCD - McDonalds (defensive?), Coca-Cola Co (defensive?)

- Broad index exposure — candidates to pick between depending on broker/domicile:
  VOO/VTI (US total market) vs. VGS/VAS (ASX-listed, AU-domiciled) — worth resolving
  since Shaun already holds US-listed stocks directly (see below)
- **Resolved 2026-07-19** — all of Shaun's actual current holdings (LLY, LYV, V) are
  now in the Confirmed So Far table as Bucket 1 — see that table for status/notes.
  Position sizes are small enough that Shaun chose not to require deep scrutiny for
  LLY/LYV; V's Berkshire-exit research task and LYV's DOJ-antitrust/business-
  correlation concerns remain on record there, just not blockers at this size.
  ASML and TSLA positions were fully closed (see `investment-strategy.md`) — ASML
  was separately discussed 2026-07-19 as a re-entry candidate (also now in Confirmed
  So Far); TSLA remains a raw, undiscussed Bucket 1 candidate on its own merits if
  Shaun wants to revisit it later.
- From existing watchlist, reasonable long-hold candidates: SCHD (dividend
  aristocrats ETF)
- From existing watchlist, needs re-homing — doesn't fit "long-term hold" cleanly:
  MCHI (China market fund — thematic/geopolitical bet), GRID, XLU (sector/thematic
  ETFs — need a bucket decision), XLP, VT




### Bucket 2 — Crash-Trade Assets (buy when a crash looks likely, sell after recovery)
**NOT DISCUSSED — raw list, carried over from the YouTube transcript + old watchlist.**
High-volatility, tactical, position-sized small. Per vetted lessons.

- Gold miners: GDX (VanEck Gold Miners ETF); individual names from the transcript —
  Newmont (NEM), Barrick (GOLD), Agnico Eagle (AEM)
- **Moved back to raw 2026-07-19** — PALI (Palisades Goldcorp Ltd, Canada TSXV) was
  sitting in the Confirmed So Far table despite its own note saying "not yet
  discussed/vetted" — an inconsistency. Removed from Confirmed So Far; belongs here
  until it actually gets a real discussion. Resource investment company/merchant bank
  holding equity/warrant stakes in 100+ junior miners (gold, silver, copper, lithium,
  uranium) — diversified critical-metals exposure via a merchant-bank structure, not
  a pure gold play like PMGOLD or a single miner like the GDX names above. Should be
  sized very small given micro-cap/junior-resource risk if it's ever confirmed.
- Farmland REITs: LAND (Gladstone Land), FPI (Farmland Partners) — remember FPI's
  2018 governance flag from the vetted lessons
- Long Treasuries: TLT — situational, only helps in deflationary/rate-cutting
  crashes (not inflationary ones like 2022) — the tool will need to distinguish
  crash *type*, not just "a crash is happening"
- From existing watchlist, needs re-homing — VRTX and WM don't obviously fit a
  crash-trade profile (VRTX is biotech growth, WM is a defensive utility-like
  business) — discuss whether these belong in Bucket 1 instead

### Bucket 3 — Gold: Both a Permanent Core and a Timed Tactical Sleeve
**DISCUSSED 2026-07-11, resolved 2026-07-19.** Mechanics, cost, physical vs. ETF, and
rationale were talked through 2026-07-11; the "permanent ballast vs. actively timed"
open question is now resolved as **both, as two separate tracked positions**, not an
either/or:
- **3a — Permanent core**: never-sell ballast (Dalio All Weather reference, ~5-10%),
  matches the "buy gradually, hold permanently" framing already vetted in
  `investment-strategy.md`'s Lessons section.
- **3b — Tactical/timed**: smaller sleeve, actively bought/sold based on conditions
  (the hold/sell rule above — starting with "no formal rule, periodic check-in").
Both sleeves use **PMGOLD as the vehicle for both** — no need for a second ETF. The
cost/FX research below already makes PMGOLD the clear choice regardless of role; using
a different vehicle for the tactical sleeve (e.g. GLD) would just reintroduce the FX/
fee friction PMGOLD avoids, for no benefit. The two sleeves get tracked as **separate
positions in the database** (same ticker, different bucket tag/rule each) once the
tool exists — not one blended PMGOLD holding, since "should I sell some PMGOLD" has
no clear answer if half the position is never-sell and half is conditions-dependent.
- **Researched 2026-07-11** (see daily log / conversation for full detail):
  PMGOLD trades at spot with no dealer premium, 0.15% p.a. fee — cheaper than GLD
  (0.40%) and IAU (0.25%), no FX/withholding friction as an AU resident. Physical
  bars carry a real ~4-5%+ round-trip buy-sell spread (Perth Mint 1kg example:
  buys A$194,575 / sells back A$185,560) plus optional storage — better suited to
  the permanent-core sleeve than the tactical one.
- China/BRICS gold-backed-currency angle checked and mostly separated from hype:
  real central-bank gold accumulation trend (bullish for gold generally) but no
  imminent gold-backed yuan/BRICS currency — doesn't change the physical-vs-ETF
  call, just supports holding gold at all.
- Gold miners (GDX etc.) are a **separate product from gold itself** — they live in
  Bucket 2, not here — don't conflate when the tool encodes rules for each.

## Hold/Sell Rules

**Confirmed 2026-07-19 — starting rule: no formal rule.** Just a periodic check-in
surfaced to Shaun (via Monitor's advisor notes), his judgment call each time, no
automated trigger. This is a deliberate starting point, not a permanent one — the
other options below (price target, recovery signal, valuation check) stay on record
as things to graduate to later, per-investment, once there's real experience running
the simpler rule first. Applies uniformly across buckets for now, including both of
gold's sleeves (below) — no per-investment variation until there's a reason to add one.

Options considered but not started with:
- **Price target** — sell once up X% from cost basis, hold below that
- **Recovery signal** — sell once a crash/recession has clearly passed (e.g.
  unemployment peaks and turns down, yield curve normalizes), hold while still
  stressed
- **Valuation check** — sell if the asset looks expensive relative to a benchmark
  (e.g. gold vs. real interest rates), hold if still cheap/fair

## Next step

**Revised 2026-07-19**: manually triaging the rest of the raw Bucket 1/2 candidate
list (DG, WFC, Uber, MCD, KO, MCHI, GRID, XLU, VT, TSLA, gold miners, farmland REITs,
etc.) is no longer planned work — that's literally Find's job once the tool exists,
and it'll do it with data (balance sheet, dividend trend, FX, briefs-finance scoring)
this conversation can't fully replicate by hand. They stay in
`potential-holdings.md`'s Raw/Not Yet Discussed tier as-is, to be checked via Find
on demand once built, not vetted here first.

**Resolved 2026-07-19**: both remaining blockers are now settled — hold/sell rule
(no formal rule, periodic check-in, see "Hold/Sell Rules" above) and gold's bucket
question (both permanent core and timed tactical, two tracked positions, same
PMGOLD vehicle — see Bucket 3 above).

No blockers left. **Confirmed 2026-07-19 — plan scope: phased, not one comprehensive
plan.** Mirrors how the core Second Brain was built (Phases 1-9) — each phase gets its
own `/plan-feature` + `/execute` pass rather than one giant plan document.

**Phase A scope finalized 2026-07-19** (revised after spotting that Find and Monitor
share one assessment engine per the "tool architecture" decision above, so the
Assessment Checks can't cleanly split across phases the way scheduling/alerting can):
- **Phase A**:
  - uv workspace wiring (my-trader imports briefs-finance's `db.py`/`config.py`
    directly, per "coupling mechanism" above)
  - DB schema: holdings, watchlist/candidates, alert history
  - The **full shared assessment engine** — all 7 Assessment Checks (dividend-cut,
    per-holding valuation, balance sheet/leverage, FX exposure, portfolio
    concentration, sector/geopolitical exposure, ETF mechanics drift) — built
    completely now rather than split, since Find needs the same engine Monitor will
    call in Phase B
  - Conversational Find (Shaun's own criteria primary, briefs-finance's likelihood
    score layered on top per "Find/scoring workflow" above), with **two distinct
    actions**: an ephemeral "what do you think of TICKER" lookup that persists
    nothing, vs. an explicit "add TICKER to the watchlist" that writes a DB row —
    mirrors `potential-holdings.md`'s existing raw-vs-discussed distinction and keeps
    Monitor's later watchlist job (Phase B) scoped to things Shaun actually chose to
    track, not every idle check
  - One-time seed/migration loading the already-confirmed rows from this file's
    Confirmed So Far table (VRTX, PMGOLD core+tactical, BRK.B, HDV, SCHD, ASML as
    watchlist; LLY, LYV, V from `holdings.md` as holdings) into the new DB — that
    reasoning took multiple real sessions to produce, re-deriving it conversationally
    afterward would be pure busywork
  - `holdings.md`/`potential-holdings.md` auto-regeneration from the DB
- **Phase B** — Monitor as a scheduled job (heartbeat-style), calling the same
  assessment engine built in Phase A; alert thresholds; toast+file output (reuses
  `send_toast_notification` per "Monitor alert signal" above).
- **Phase C** — the 5 Monitoring Indicators (macro), Briefs Finance ingest→candidate
  data-flow integration.

Run `/plan-feature` with this file as input, scoped to Phase A as defined above, to
produce a real plan in `.agent/plans/`.
