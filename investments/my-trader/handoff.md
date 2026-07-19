# Handoff: my-trader Portfolio Build-Out

## Status: Portfolio triage in progress; Phase A + B + C tool build COMPLETE (2026-07-19)

**2026-07-19, same day — price_action check (9th check), plain informational price
context**: Shaun asked about DG and noted "its gone up 11% in a month" — Find had
shown nothing about it. Root cause: DG was +11.4% over 1 month but only -0.1% over 3
months (the whole move happened recently, then partially reversed within the window)
— the opportunity check's 3-month figure never gets displayed unless it crosses a
threshold, so a real move was completely invisible. New `checks/price_action.py`:
always shows both 1mo and 3mo returns, `verdict` always `"info"` — never a buy/sell
signal (Graham's "price momentum does not matter" still holds; this just reports).
170 tests passing, ruff/mypy clean. Verified live on DG: "1mo +11.4%, 3mo -0.1%" now
shows correctly, opportunity correctly stays suppressed (balance sheet flag active).

**2026-07-19, same day — opportunity check rebuilt from real investing frameworks**:
Shaun called out the first version directly: "You need to research a bunch of tests
and mental models that expert and successful traders use, otherwise this whole tool
is a waste of time." Also flagged the design was philosophically backwards — "a stock
can be an opportunity if its price is falling" — the old design only ever rewarded
rising prices. Rebuilt `checks/opportunity.py` entirely from
`investments/briefs-finance/principles/*.md` (the 9 investor-principle files already
in this codebase, previously only used by briefs-finance's own LLM scoring) — every
threshold is that principle's own literal stated criterion:
- **Graham**: actual Graham Number, PE × P/B < 22.5 (his file also explicitly states
  "price momentum does not [matter]" — direct confirmation the old design was wrong
  in principle).
- **Lynch**: PEG ≤ 1.0.
- **Buffett/Smith**: ROE ≥ 15% (both files independently state this exact number)
  AND not already valuation-rich — quality at a fair price.
- **Marks/Neilson**: price down ≥10% over 3 months, gated on nothing else being
  wrong — directly answers Shaun's falling-price point.
- Briefs Finance score ≥ 70 (unchanged).
All legs now gated on "no active flag among the other 7 checks in the same
assessment" (`concentration` excluded — Shaun ruled sector overlap out of scope
earlier) — a more robust, principled version of the earlier ASML-only patch. 2+
signals firing together get a "(N independent signals)" note (Munger's confluence).

**Second real bug caught during verification**: BRK-B's yfinance `priceToBook` came
back as 0.00097 — Berkshire's dual share classes (BRK-A/BRK-B, ~1500:1 price ratio)
caused Yahoo to pair BRK-B's price with BRK-A's book value, producing a nonsense
near-zero P/B that would have made an already-not-cheap PE 14.6 stock fire the Graham
leg on garbage data. Added `OPPORTUNITY_MIN_PLAUSIBLE_PB = 0.1` floor. Verified live:
BRK-B correctly shows no signal now; NU (3 signals: PEG 0.80, ROE 30.1%, down -10%),
PMGOLD (down -14.6%, gold-price-driven), and VRTX (ROE 24.2%) all look sane.

Also confirmed (standing rule, saved to memory): my-trader must never auto-remove a
watchlist/holdings row as a side effect of any check or score — deletion is always an
explicit user action. Holdings extension of the opportunity signal was proposed but
not yet confirmed by Shaun. 165 tests passing, ruff/mypy clean.

**2026-07-19, same day — momentum gated on valuation (opportunity check bug)**: Shaun
caught it within minutes of the feature shipping — ASML was flagged "interesting"
purely on +18.6% 3-month momentum while carrying an *open valuation alert* (PE 60.2,
above `PE_RICH_THRESHOLD`) in the very same report. Self-contradictory: a price
run-up on an already-expensive stock is a caution signal, not an opportunity one — if
there was a cheap entry point it likely already passed. `checks/opportunity.py`'s
momentum leg now suppresses itself when the ticker's own PE is at/above
`PE_RICH_THRESHOLD`. 160 tests passing (3 new, covering the gate and its edge cases).

**2026-07-19, same day — Opportunity signal (8th check) + Watchlist Opportunities
report section**: Shaun pushed back hard on `monitor-report.md` only ever showing
risk warnings ("did you think monitor-report was just for warning me... I also want
to know if I should be interested in a holding on the watchlist"). Added
`checks/opportunity.py`: looks at the candidate alone (cheap PE, strong 3-month price
momentum via new `return_data.fetch_recent_return_pct`, high Briefs Finance score),
`verdict="interesting"` when any fire. Deliberately does NOT compare against existing
same-sector holdings — Shaun explicitly rejected that scope ("it doesn't matter if I
have another holding in the same sector... I can make the choice myself by asking you
to deeply compare them"), so `checks/concentration.py` was left untouched. Wired into
`engine.run_assessment()` as an 8th check; `monitor.py` renders it as a live
"Watchlist Opportunities" section every run — NOT deduped through `alert_history`
like the risk checks, since Shaun wants to see it every run while it's true, not just
once. Two new config thresholds (`OPPORTUNITY_MOMENTUM_FLAG_PCT=10.0`,
`OPPORTUNITY_SCORE_FLAG=70`), both best-guess defaults per this session's established
pattern. Verified live: ASML (+18.6%) and VRTX (+10.6%) both flagged for 3-month
momentum on a real Monitor run. Also promoted NU into the real watchlist
(`bucket=1`, `status="discussed"`) per Shaun's explicit request — first real Monitor
alert on it was the sector-concentration flag (Financial Services, via the Visa
holding), exactly the scenario that prompted the "it doesn't matter" pushback above.
157 tests passing, ruff/mypy clean; the new `fetch_recent_return_pct` network call
required its own global `conftest.py` stub (same leak-prevention pattern as backtest
refresh and score computation) to keep the test suite hermetic.

**2026-07-19, same day — ticker-scoped backtest refresh added to Find/Monitor, and a
real test-isolation bug fully root-caused**: Shaun asked whether backtest should
auto-run on Find too (it's cheap — yfinance price lookups only, no LLM calls, unlike
score computation) — added `engine._refresh_backtest_for_ticker()`, called on every
`run_assessment()` alongside the score lookup, refreshing (not caching) since 3m/6m/
12m windows genuinely elapse over time. This opens its own DB connection via
`scripts.backtest.run_backtest()` (not the caller's `conn`), so a global autouse
`conftest.py` fixture now stubs it for every test by default — the same class of
real-DB leak risk as the file-path issue below, caught before it could bite.

Separately: Shaun noticed `watchlist.md` was empty. First suspected the VaultSync
scheduled task; the `vault_sync_runs.log` **disproved** that (every cycle logged
"already up to date" for the entire window — it never touched anything). Root cause
was `test_monitor.py` never isolating `config.HOLDINGS_MD_PATH`/`WATCHLIST_MD_PATH`/
`PENDING_CANDIDATES_MD_PATH` to `tmp_path` the way `test_snapshot.py`'s own
`_patch_paths` does — every `pytest` run silently overwrote the real snapshot files
with near-empty test-fixture data, and a prior commit (`6fbb609`) had captured one of
those corrupted states because the files were staged without diffing first. Fixed
`test_monitor.py`, but a second mtime-based bisection across all 19 test files (each
run individually, checking file mtimes before/after) found the SAME gap independently
copy-pasted into three more files — `test_find.py`, `test_holdings_ops.py`,
`test_seed.py` — each with its own `_patch_snapshot` helper that predated
`PENDING_CANDIDATES_MD_PATH` and was never updated when that third path was added.
Fixed all three. Verified with precision: all three real files' mtimes are now
byte-identical before and after a full 143-test suite run — confirmed clean.
Restored all three files from the database (always the correct source of truth
throughout this whole incident — the DB itself never lost a row) and committed
immediately after diffing, not before.

**Lesson, not just a bug**: copy-pasted test-isolation helpers drift silently when
new state is added to the thing they isolate. There's no single shared fixture for
"don't touch the real snapshot files" — it's independently reimplemented per test
file. Worth consolidating into one shared conftest.py fixture so this class of bug
can't recur a fourth time.

**2026-07-19, same day — "throw everything you have at it": compute-if-missing
Briefs Finance score + balance sheet ROE fallback**: Shaun asked Find on NU why the
balance sheet check said "unknown" and why the Briefs Finance score said "no history"
despite having just run `backtest` during today's report ingest. Root-caused both:
(1) `debtToEquity`/`currentRatio` are genuinely absent from yfinance for financial-
sector tickers (verified against NU's raw info dict) — `checks/balance_sheet.py` now
falls back to `returnOnEquity` (new `config.ROE_FLAG_THRESHOLD_PCT = 5.0`) rather than
reporting unknown for an entire sector; (2) `backtest` and `score`/`assess` are
separate briefs-finance commands — backtest only populates historical-return
`outcomes`, the 0-100% score in `likelihood_scores` needs a separate `compute_score`
call that ingestion never ran. `engine.py`'s `_lookup_briefs_finance_score` (shared by
Find and Monitor) is now `_lookup_or_compute_briefs_finance_score` — computes a score
on the spot (~9 haiku LLM calls) when a ticker has a recommendation but no score yet,
persists it, returns `None` only when there's no recommendation at all to score.
Verified live on NU: balance_sheet went from `[unknown]` to `[ok]` (ROE 30.1%),
briefs_finance_score went from "no history" to 60/100. Checked the current backlog
impact: only 3 of Monitor's 9 tracked tickers are missing a score, so the next
Monitor run will be slightly slower (not another backlog flood like candidate_sync's
first run) but not by much. 141 tests passing, ruff/mypy clean.

**2026-07-19, same day — renamed potential-holdings.md to watchlist.md**: Shaun asked
for the file to be renamed. `config.WATCHLIST_MD_PATH` now points to `watchlist.md`;
updated all references across `mytrader/*.py`, `SKILL.md`, `instructions.md`,
`CLAUDE.md`, and test files (git-mv preserved history on the file itself). Historical
docs (`tool-preplan.md`'s dated entries, completed `.agent/plans/*.md` phase docs,
and this file's own older dated entries below) were left untouched — they're accurate
records of what the file was called at the time, not meant to be retroactively
"corrected." 136 tests passing, ruff/mypy clean.

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

**2026-07-19, same day — AI watchlist cleanup**: Shaun reviewed the 270 newly-synced
candidates and confirmed he doesn't want tech/AI-boom exposure at current valuations.
Curated the batch: stripped 44 rows entirely (smaller/speculative AI plays,
robotics/quantum ETFs, cybersecurity, and the AI-infrastructure-demand
utilities/REITs/industrials that only made the list via the AI/data-center wave — e.g.
NEE, CEG, EQIX, DLR, CRWD, BOTZ, PLTR; also dropped a duplicate GOOG row). Moved 12
major AI-boom names with genuine moats (chip/foundry monopoly, hyperscaler platform
dominance) into a new `bucket="ai_postcrash"` instead of deleting them — NVDA, AMZN,
ASML, SNDK, MSFT, GOOGL, AVGO, TSM, MU, IBM, BABA, ISRG — deliberately not being
bought at current AI-bubble valuations, kept for reconsideration if/when the sector
corrects. `snapshot.py`'s `regenerate_watchlist_md()` now renders `potential-holdings.md`
as two sections ("Watchlist" + "Post-Crash AI Watch") based on this bucket. Watchlist
went from 308 → 264 rows.

**2026-07-19, same day — candidate_sync architecture change**: Shaun flagged that
auto-syncing straight into `potential-holdings.md` wasn't smart — most of the 270
backlog picks were from old reports and no longer relevant as live recommendations
(several were literally Briefs Finance's own "bottom performer" tracking notes or
explicit sell/closed-position calls, not real theses). Decision: `candidate_sync`
still runs, but (1) it's manual/on-demand only now — the automatic call was removed
from `monitor.run_monitor()` entirely, so a new Briefs Finance report ingestion no
longer silently adds to the watchlist on the next scheduled Monitor run; (2) synced
candidates land in a new `pending_candidates` table / `synced-candidates-pending-review.md`
file, never directly in `watchlist`/`potential-holdings.md`. New `promote-candidate`
and `dismiss-candidate` CLI commands move a pending row into the real watchlist or
discard it. Also added `watchlist-remove` and `watchlist-move-bucket` (there was
previously no way to remove or re-bucket a watchlist row without a one-off script —
today's AI cleanup needed one; won't need to again). `potential-holdings.md` is now
guaranteed to only ever change via an explicit action (watchlist-add/-remove/-move,
holding buy/sell, or promote-candidate) — never a silent bulk sync. 126 tests passing,
ruff/mypy clean.

Not yet done: the deeper fix belongs one level up, in `briefs-finance`'s own
report-extraction step (`investments/briefs-finance/scripts/ingest.py`), which is
currently treating "bottom performer" tracking callouts as recommendations in the
first place — a separate subsystem, not touched today.

**2026-07-19, same day — Dividend/10Y Return columns wired up**: These were
placeholder columns since Phase A (hardcoded "—", per the file's own header note).
New `mytrader/return_data.py`: `fetch_dividend_yield_pct`/`fetch_ten_year_return_pct`
(yfinance, 10Y Return = adjusted-close cumulative return as a total-return
approximation), `refresh_watchlist_return_data(conn)` iterates every watchlist row.
New DB columns on `watchlist` (additive `ALTER TABLE` migration, safe on the existing
real data): `dividend_yield_pct`, `ten_year_return_pct`, `return_data_updated_at`.
New `refresh-watchlist-data` CLI command — on-demand only, not run automatically
(a 10Y history fetch per ticker is too expensive to redo on every snapshot regen).
Ran once against the real shared DB: 45/49 rows got at least one value.
**Data-quality issue hit, root-caused, and properly fixed**: yfinance's `dividendYield`
field returned clearly-wrong values for several tickers in the real run (GDX 84%,
GRID 75%, ASML 52%, BABA 91%, MSFT 92%, TSM 95%, NVDA 49%, GOOGL 25%). First pass
added a plausibility filter (`MAX_PLAUSIBLE_DIVIDEND_YIELD_PCT = 15.0`) that caught
the extreme cases but left MU's 6.00% (still wrong) undetected. Shaun pushed back
("are you sure you're targeting the correct data") — root-caused it properly by
reading yfinance's own source (`scrapers/quote.py`'s `_fetch_info` — confirmed
yfinance applies zero scaling itself, just passes through Yahoo's raw value) and
cross-checking real info dicts: `info["dividendYield"]` is already a direct percent
number (0.92 means 0.92%, verified against MSFT's dividendRate/price), while
`info["trailingAnnualDividendYield"]` is a genuine fraction needing `*100` and is far
more precise for individual stocks but comes back 0.0 for most ETFs. `return_data.py`
now prefers the trailing fraction when populated, falls back to the direct-percent
forward figure for ETFs. Re-ran the real refresh: NVDA corrected from a filtered "—"
to an accurate 0.02%, MU from a wrong-but-plausible 6.00% to an accurate 0.06%, and
GDX/GRID/GOOGL/ASML recovered from filtered "—" to real plausible values. Plausibility
filter kept as a safety net for any remaining bad data. 136 tests passing, ruff/mypy
clean.

**2026-07-19, same day — candidate_sync re-enabled automatically (safely this time)**:
Shaun asked for Briefs Finance picks to auto-land in `synced-candidates-pending-review.md`
again. Re-added `candidate_sync.sync_new_candidates(conn)` to `run_monitor()` (removed
earlier the same day) — safe now because the target is the pending-review staging
area, not the watchlist. `render_report()` gained a "New Candidates Synced (Pending
Review)" section. The original "turn off automatic sync" complaint was specifically
about it silently writing into `potential-holdings.md`; once that path was closed off,
running it unattended on Monitor's daily schedule stopped being a problem. 135 tests
passing, ruff/mypy clean.

**2026-07-19, same day — watchlist cull to tool-preplan.md's vetted set**: Shaun
decided the main Watchlist section should only contain tickers actually vetted/
discussed in `tool-preplan.md` (the "Confirmed So Far" table + Bucket 1/2 raw
candidate lists), not the leftover Briefs Finance backlog. Removed 215 rows, kept 37
(36 unique tickers — PMGOLD occupies two rows for its 3a/3b buckets): AEM, BRK-B, DG,
DLTR, DOLLARAMA, FIVE, FPI, GDX, GOLD, GRID, HDV, IXI.AX, JOBY, KO, LAND, MCD, MCHI,
NEM, OLLI, PALI, PMGOLD, SCHD, TLT, TSLA, UBER, VAS, VDC, VGS, VOO, VRTX, VT, VTI,
WFC, WM, XLP, XLU. Post-Crash AI Watch section left completely untouched (still 12
rows). Shaun also considered adding BYD, IVV, ARKG, ARKQ, CRISPR (CRSP), ARKVX but
decided against it — none were added; ARKVX specifically dropped as not a
confidently-identified ticker.

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
