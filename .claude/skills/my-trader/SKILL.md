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

```powershell
# Ephemeral lookup — "what do you think of TICKER" (writes nothing)
uv run --directory investments/my-trader python -m mytrader.main find --ticker VRTX

# Explicit "add to watchlist" — persists a DB row + regenerates snapshots
uv run --directory investments/my-trader python -m mytrader.main watchlist-add --ticker VRTX --name "Vertex Pharmaceuticals" --asset-type stock --bucket 1 --notes "..."

# Record a buy/sell against a holding
uv run --directory investments/my-trader python -m mytrader.main holding-buy --ticker V --bucket 1 --qty 0.1 --price 340
uv run --directory investments/my-trader python -m mytrader.main holding-sell --ticker V --bucket 1 --qty 0.05 --price 350

# Regenerate holdings.md / watchlist.md from the DB
uv run --directory investments/my-trader python -m mytrader.main snapshot

# One-time migration of the already-confirmed rows (VRTX, PMGOLD core+tactical, BRK-B,
# HDV, SCHD, ASML, LLY, LYV, V) into the shared DB — idempotent, safe to re-run
uv run --directory investments/my-trader python -m mytrader.main seed

# Scheduled re-check of all holdings + vetted watchlist (also runs automatically —
# see scripts/setup_scheduler_windows.ps1 / scripts/systemd/second-brain-mytrader-monitor.timer)
uv run --directory investments/my-trader python -m mytrader.main monitor

# Pull new Briefs Finance recommendations into synced-candidates-pending-review.md
# right now (also runs automatically once a day as part of `monitor`)
uv run --directory investments/my-trader python -m mytrader.main sync-candidates

# Review synced-candidates-pending-review.md, then promote or dismiss each one
uv run --directory investments/my-trader python -m mytrader.main promote-candidate --ticker VRTX --bucket 1 --status raw
uv run --directory investments/my-trader python -m mytrader.main dismiss-candidate --ticker XYZ

# Remove a ticker from the watchlist, or move it to a different bucket
uv run --directory investments/my-trader python -m mytrader.main watchlist-remove --ticker XYZ
uv run --directory investments/my-trader python -m mytrader.main watchlist-move-bucket --ticker XYZ --to-bucket 2
```

Note: use `uv run --directory <path> ...` rather than `cd`-ing into the directory first —
`cd` in this repo's shell breaks the PreToolUse hooks (see project memory).

## Key Paths

- Package: `investments/my-trader/mytrader/`
- Shared database: `investments/briefs-finance/data/investments.db` (`holdings`,
  `watchlist`, `alert_history` tables — owned by my-trader; `reports`,
  `recommendations`, `likelihood_scores` etc. — owned by briefs-finance)
- Snapshots: `investments/my-trader/holdings.md`, `investments/my-trader/watchlist.md`
  (auto-regenerated after every write — never hand-edit these once the tool is in use).
  `watchlist.md` renders two sections: "Watchlist" (everything else) and
  "Post-Crash AI Watch" (watchlist rows with `bucket="ai_postcrash"` — major AI-boom
  names with real moats that Shaun has deliberately chosen not to buy at current
  AI-bubble valuations, kept for reconsideration if/when the sector corrects; see
  `config.AI_POSTCRASH_BUCKET`).
- Pending synced candidates: `investments/my-trader/synced-candidates-pending-review.md`
  (auto-regenerated from the `pending_candidates` table — separate from the watchlist
  until explicitly promoted).
- Strategy/criteria reference: `investments/my-trader/investment-strategy.md`

## The 9 Assessment Checks

Every `find` / `watchlist-add` runs all 9:

| Check | What it looks at |
|-------|-------------------|
| Dividend trend | Trailing vs. prior 12-month dividend sum |
| Valuation | Trailing/forward PE vs. configured rich/cheap bands |
| Balance sheet | Debt/equity and current ratio; falls back to return on equity when both are unavailable (common for financials/banks) |
| FX exposure | Non-AUD currency + AUD move (informational only) |
| Concentration | Berkshire 13F overlap + candidate's sector vs. existing holdings |
| Sector/geopolitical risk | Sector/industry vs. known active flashpoints |
| ETF mechanics | Expense ratio baseline / drift (drift only detectable after a repeat check) |
| Opportunity | Grounded in real investor-principle criteria — `verdict="interesting"` when any fire, gated on no active flags elsewhere. Added 2026-07-19 (see "Opportunity Signal" below) |
| Price action | Plain 1-month + 3-month price return, `verdict` always `"info"` — never a signal, just the fact. Added 2026-07-19 (see below) |

Also, on every `run_assessment()` call (Find or Monitor): a ticker-scoped
`scripts.backtest.run_backtest(ticker_filter=...)` refresh (cheap — yfinance price
lookups only, no LLM calls — runs every time, not cached, since outcome windows
genuinely elapse) and a compute-if-missing Briefs Finance likelihood score (~9 haiku
LLM calls, cached after the first time). Both added 2026-07-19, Shaun: "throw
everything you have at assessing it."

## Two Distinct Find Actions

- **Ephemeral lookup** ("what do you think of TICKER") — runs the 9 checks, reports
  back, persists nothing.
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

## Monitor

Runs daily on a schedule (no chat trigger needed — it's automated, see "Setup" for the
scheduler entries). Re-checks every `holdings` row and every `watchlist` row with
`status="discussed"` (never `status="raw"` — Monitor doesn't discover new candidates,
that stays a Find/conversation action). Reuses the same 9-check engine as Find.

High-bar alerting: a check's first `flag` verdict for a given ticker/check creates one
alert; repeated flags on later runs stay quiet (already open); a check clearing back to
non-flag auto-acknowledges its open alert, so a future re-flag raises a fresh one. The
`opportunity` check's `"interesting"` verdict is explicitly exempt from this dedup —
see "Opportunity Signal" above.

Output is a standalone file, `investments/my-trader/monitor-report.md` (full overwrite
every run — new alerts this run + all currently-open alerts + watchlist opportunities
this run). A bare Windows toast notification fires only when there's at least one new
alert (reuses `.claude/scripts/notifications.py`, same as heartbeat) — opportunities
don't trigger a toast, only visible in the report. No Second Brain daily-log entry
and no WhatsApp push — Monitor is a quieter, separate channel by design. Like Find,
Monitor never suggests a specific trade action — advisor notes only.

## Macro Monitoring Indicators

Every `monitor` run also runs 4 portfolio-wide checks (not per-ticker), once per run:
MOVE index (bond-market stress), housing price-to-income ratio, University of
Michigan Consumer Sentiment Index, and a recession-probability check whose detail
text also classifies bull vs. bear yield-curve steepening (a refinement folded into
that check, not a separate 5th check). These reuse the same high-bar alert-dedup
mechanism as the per-ticker checks, via a `"MACRO"`/`"macro"` sentinel ticker/
source_table pair in `alert_history`. Shown in `monitor-report.md`'s "Macro
Indicators" section every run regardless of flag status (unlike per-ticker checks,
which are only shown when flagged/open). FRED-backed checks (housing, sentiment,
recession) degrade to `"unknown"` if `FRED_API_KEY` is unset.

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
don't reprocess the same recommendations. `monitor-report.md` shows a "New Candidates
Synced (Pending Review)" section every run.

Review the pending file and either:
- `promote-candidate --ticker X [--bucket unassigned] [--asset-type stock] [--status raw]`
  — moves it into the real watchlist
- `dismiss-candidate --ticker X` — discards it without adding to the watchlist

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
