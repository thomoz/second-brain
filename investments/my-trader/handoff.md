# Handoff: my-trader Portfolio Build-Out

## Status: Portfolio triage in progress; Phase A + B + C tool build COMPLETE (2026-07-19)

**Phase C (macro indicators + Briefs Finance ingest→candidate data-flow) is built** —
see `.agent/plans/my-trader-phase-c-macro-and-briefs-sync.md` for the full plan. New
`macro_indicators.py` (4 portfolio-wide checks: MOVE index, housing price-to-income,
UMich consumer sentiment, recession-probability + bull/bear steepener classification)
and `candidate_sync.py` (`sync_new_candidates()`, watermarked via new `sync_state`
table), both wired into `run_monitor()` — no new scheduled infrastructure, both ride
Monitor's existing daily schedule. New `sync-candidates` CLI subcommand for manual
triggering. 116 unit tests passing (87 Phase A+B + 29 Phase C), ruff/mypy clean.

Live validation against the real shared DB:
- `FRED_API_KEY` is **not set** (no `.env` in `investments/briefs-finance/`) — the 3
  FRED-backed checks (housing_affordability, consumer_sentiment, recession_signal) all
  read `"unknown"` in the real run. This is expected graceful degradation, not a bug.
  Set `FRED_API_KEY` in `investments/briefs-finance/.env` (see `.env.example`) to
  activate them.
- `^MOVE` **does resolve** via yfinance — confirmed live, read 70.9 in the real run
  (well below the 140.0 flag threshold), consistent with tool-preplan.md's "confirmed
  low as of early 2026" note. This indicator is live, not permanently `"unknown"`.
- `sync-candidates` run against the real shared DB synced **270 new candidates** in one
  shot — this is the expected one-time backlog catch-up: 83 already-ingested
  briefs-finance reports (predating this sync feature) held 283 distinct non-excluded
  tickers with no prior path into the watchlist. A second immediate run correctly
  synced 0 (watermark works). All 270 landed as `bucket="unassigned"`,
  `status="raw"`, visible in `potential-holdings.md`.
- Full `monitor` run afterward: 0 new alerts (7 still open, unchanged from Phase B's
  validation), macro section showed the 4 expected entries, candidate-sync section
  correctly showed "None this run" (backlog already consumed by the standalone
  `sync-candidates` run above).
- The 270 newly-synced `bucket="unassigned"` watchlist rows are **not yet
  triaged** — they sit as raw candidates until Shaun/Find reviews and either promotes
  (`watchlist-add`, flips to `"discussed"`) or ignores them. Not a Phase C gap; no
  "un-sync"/reject action exists by design (see plan's NOTES).

**Phase A (shared assessment engine + conversational Find) is built** — see
`.agent/plans/my-trader-phase-a-find-engine.md` for the full plan. Root-level uv
workspace joining `investments/briefs-finance` + `investments/my-trader`; `mytrader/`
package with the 7 assessment checks, `engine.run_assessment()`, conversational
`find.py` (ephemeral lookup vs. explicit watchlist-add), `holdings_ops.py` (buy/sell),
`snapshot.py` (auto-regenerates `holdings.md`/`potential-holdings.md` from the DB),
`seed.py` (idempotent migration of the Confirmed So Far table), and
`.claude/skills/my-trader/SKILL.md`. The one-time `seed` run against the real shared
`investments.db` has been run for real (3 holdings, 38 watchlist rows present).

**Phase B (scheduled Monitor) is built** — see
`.agent/plans/my-trader-phase-b-monitor.md` for the full plan. New `monitor.py`:
`run_monitor()` re-checks every holding + every `status="discussed"` watchlist row
using the same Phase A engine, reconciles `flag` verdicts against the `alert_history`
table (high-bar dedup — only a flag→ok→flag transition raises a fresh alert), writes
`investments/my-trader/monitor-report.md` (full overwrite), and fires a toast via
`.claude/scripts/notifications.py` only when there's a new alert. New `monitor` CLI
subcommand, `cached_session()` in `market_data.py` (avoids an O(n²) yfinance blowup
across Monitor's per-row loop), Windows Task Scheduler entry + systemd timer/service
(`second-brain-mytrader-monitor.timer`/`.service`) added but **not yet registered/enabled
for real** — pending Shaun's go-ahead (Level 4's final step). 87 unit tests passing
(67 Phase A + 20 Phase B), ruff/mypy clean. Live `monitor` run validated twice against
the real shared DB: first run produced 7 new alerts (LLY/LYV valuation, LYV balance
sheet, LYV/V/BRK-B sector concentration, ASML valuation); second run confirmed the
dedup logic — 0 new alerts, same 7 still open.

Phase C (macro indicators, Briefs Finance ingest→candidate data-flow) is now built —
see the Phase C summary above and `tool-preplan.md`'s "Phase A scope finalized" section.

The portfolio-triage narrative below (2026-07-11 and earlier) predates the tool build
and is kept as historical context — the working method described there (discuss one
ticker at a time by hand) is superseded by Find once `seed` has run for real.

## Context

Building toward a "find + monitor" investing tool (see `tool-preplan.md`), but before
designing the tool itself, Shaun is first working through candidate stocks/ETFs one at
a time to build an actual starting portfolio. Three buckets: long-term holds, crash-trade
assets (buy before a crash, sell after), and gold (market-dependent, hold or sell based
on conditions).

**Working method** (established 2026-07-11, don't drift from this without Shaun saying
so): discuss each ticker briefly — what it is, fit against Shaun's own criteria
("sustainable, competitive edge, can raise prices without losing customers"), watch-outs,
verdict. Keep it short — deep, tool-style analysis is explicitly meant for the tool
we build later, not for doing by hand in conversation.

## Where things stand — resume here

Full detail lives in `tool-preplan.md`. Quick snapshot as of 2026-07-11:

**Confirmed So Far table** (only things actually discussed, not just listed):
- PMGOLD — leaning yes, vehicle decided, hold/sell rule still open
- BRK.B — good candidate
- VRTX — good candidate, belongs in Bucket 1 (non-cyclical, not a crash-trade)
- V (Visa) — **parked**, Berkshire exited its Visa stake in Q1 2026, reason not yet
  investigated
- HDV — candidate, relabeled from "staples ETF" (it's a broader quality/high-dividend
  fund with real energy-sector weighting)

**Standing rules established, apply going forward:**
- Before confirming any individual stock beyond Berkshire, check whether Berkshire's
  own portfolio already holds it/something similar — avoid duplicate exposure
- Dividend column added to the table: None (0%) / Low (<1.5%) / Medium (1.5-3%) /
  High (>3%)
- Allocation % is a rough anchor only, not fitted to Shaun's real portfolio size yet
- **Shaun's own "sustainable, competitive edge, pricing power" criteria (in
  `investment-strategy.md`) is now confirmed as Buffett's actual inflation hedge**
  (2026-07-11, second transcript vetted) — use this to prioritize Bucket 1 candidates
  that clearly meet it, not just as a generic quality filter
- **New candidate surfaced, not yet triaged into a bucket**: real estate / REITs
  (general, not just farmland) — inflation-hedging mechanics are real (rents rise
  with inflation), but not yet vetted with the same rigor as farmland REITs. Raise
  this when picking the next ticker to discuss.
- **Third transcript vetted (2026-07-11)** — "banks are conspiring to crash the
  economy" framing rejected (checked out as normal late-cycle credit dynamics, not
  a plot), but extracted a real leading-indicator checklist (yield curve, SLOOS
  bank lending survey, consumer credit growth, credit card delinquency vs. income,
  home sales, retail sales vs. income) — see "Lessons: Reading Late-Cycle /
  Recession Warning Signals" in `investment-strategy.md`. This is a concrete answer
  to the open "what does Monitor actually check?" question in `tool-preplan.md`.

**Resolved 2026-07-11**: the second transcript's overarching thesis ("own assets
whose value rises when the dollar falls, or whose income grows with prices") was
deliberately left out of `investment-strategy.md` — Shaun's call, leave it implicit
in the four specific lessons (gold, real estate, pricing-power stocks,
geo-diversification) rather than adding a summary line. Don't re-raise this.

**Not yet touched:**
- Rest of Bucket 1 raw list — dollar-store names (DG, DLTR, FIVE, OLLI, Dollarama),
  MCD, KO, Uber, WFC, Joby Aviation, broad index fund choice (VOO/VTI vs VGS/VAS),
  ASML/LLY/TSLA/LYV (Shaun's current holdings, not yet run through the criteria filter)
- All of Bucket 2 (crash-trade assets) — GDX, gold miners, LAND/FPI, TLT — nothing
  discussed yet, still raw transcript material
- Hold/sell rules — deliberately deferred until the basic portfolio is settled (see
  "Deferred: Hold/Sell Rules" in `tool-preplan.md`)
- Tool design itself — nothing started, waiting on the portfolio first

## Next step when resuming

Pick up the next undiscussed ticker from Bucket 1 (or wherever Shaun wants to point),
same brief format as above. Add to the Confirmed So Far table only after real
discussion — don't backfill it from the raw list without going through each one.

## Related files
- `tool-preplan.md` — full working scratchpad, candidate universe, open questions.
  As of 2026-07-19 most of the tool's mechanics are now Confirmed (not just
  proposed): trigger model (heartbeat-driven Monitor, manual/conversational Find),
  output channel (standalone file, no Second Brain integration), scope of
  "adjustment" (advisor note only, never drafts trades), data sources (yfinance +
  free news feeds, explicitly including fundamentals/earnings), tool architecture
  (one tool/two modes), Find's scoring workflow (Shaun's own criteria as primary,
  briefs-finance's principle scoring layered on top), plus the Assessment Checks and
  Monitoring Indicators sections. Still open: alert thresholds, Merge-with-Briefs-
  Finance path, tech stack, directory location — see that file directly, not
  summarized here
- `investment-strategy.md` — vetted lessons (crash-asset research, purchasing-power/
  inflation research, late-cycle warning signals research), current actual holdings,
  criteria
- `transcripts/lesson-extraction/` — durable strategy transcripts. Four processed into
  vetted lessons in `investment-strategy.md` so far (crash-assets, purchasing-power/
  inflation, late-cycle warning signals, yield-curve/valuation signals added
  2026-07-18); check here first before assuming a new transcript needs analysis.
  Analysed via `analyse-transcript.md`.
- `transcripts/daily/` — same-day trading-analyst videos, a different genre from the
  above (tactical/ephemeral, not durable lessons). Analysed via
  `analyse-daily-transcript.md`, which logs one line per analysis to
  `transcripts/daily/daily-market-reads.md`. New as of 2026-07-19, no transcripts
  processed here yet.
- `analyse-transcript.md` — directive for lesson-extraction transcripts → surfaces
  candidates for `tool-preplan.md` in chat, never auto-writes
- `analyse-daily-transcript.md` — directive for daily transcripts → ties calls to
  actual holdings/candidates, advisor-mode only (never recommends a trade), logs to
  `transcripts/daily/daily-market-reads.md`
- `holdings.md` — glanceable current-positions snapshot (LLY, LYV, V as of
  2026-07-19). Manually maintained until the tool exists, then auto-regenerated from
  the shared DB every run — never edited by hand once that happens.
- `potential-holdings.md` — glanceable watchlist, split into Vetted Candidates
  (discussed, matches `tool-preplan.md`'s Confirmed So Far) and Raw/Not Yet Discussed
  (full Bucket 1/2 candidate lists). Same manual-until-tool-exists caveat as
  `holdings.md`.
