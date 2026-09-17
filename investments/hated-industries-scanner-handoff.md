# Hated Industries Scanner — Session Handoff

Tool name: **Hated Industries Scanner**. Proposed home: **inside the existing `goat`
package** as a new module `investments/goat/goat/hated_industries_scan.py` + CLI
command `scan-hated-industries` (not a new uv-workspace member — same "extend the
existing package" precedent as the DMA Breakout Scanner handoff and Goat's own
sector/industry/heartbeat/insider scans all living together in one package).

## Status: NOT BUILT — drafted 2026-09-16 from Shaun's request. Awaiting Shaun's
manual `/plan-feature` run against this doc before any implementation.

## What This Is

Shaun's thesis, in his words: a few months back the market broadly "hated on" SaaS
software out of fear that AI could quickly replace it — but the reasoning wasn't
sound across the whole industry, because some software systems are so deeply
integrated into a customer's business (system-of-record, switching costs, data risk
of ripping it out) that the ROI of an AI replacement doesn't make sense and the risk
of one is high. The hate on some of those companies has since **reversed massively**.

He wants a daily check that finds **industries currently being hated on by the
market** — sustained, severe price underperformance/drawdown at the industry level —
so he can catch the *next* SaaS-style overreaction while the pessimism is still live,
not after it has already round-tripped back up. This is the deliberate mirror image
of Goat's existing sector/industry rotation ranking, which hunts for **momentum
strength**; this tool hunts for **momentum weakness that may not be fundamentally
deserved**, at the same industry granularity.

This is explicitly a **discovery/advisory** tool, same spirit as every other
`investments/` scanner: no buy/sell verdict, no automatic watchlist add. It flags
*industries*, not tickers — the natural next step for a flagged industry is for
Shaun to run individual constituent names through **my-trader Find** or check
whether they already show up in the **AI-Resistant Moat Scanner**'s ranking (that
tool already scores individual companies for exactly the "too embedded for AI to
cheaply replace" property Shaun's SaaS thesis describes — this scanner is the
sector-level early-warning trigger that feeds candidates *into* that kind of
deeper look, not a replacement for it).

## The three-part signal (what actually gets checked)

Three genuinely different questions, all needed together — severity alone just
finds "what's down," which isn't the ask; the ask is "what's down for reasons that
may not hold up."

### 1. Quant severity gate — is this industry actually being hated on, not just lagging a bit

Reuse `goat/industry_rotation.py`'s existing 39-industry-ETF universe
(`GOAT_INDUSTRY_ETFS`) and `fetch_all_industry_closes()` almost as-is. Compute, per
covered industry:
- 3-month **and** 6-month price return (the existing `rank_industries()` only does
  6-month/126 trading days today — add a second, shorter window; a fear-driven
  selloff can be a 3-month event, not always a slow 6-month bleed).
- The same return for **SPY** over the identical windows, so severity is measured
  **relative to the broad market**, not just "bottom 5 of 39" (bottom 5 always
  exists even when nothing is genuinely hated — a rising-tide market still has a
  last-place industry that's merely lagging, not hated).
- **Drawdown from 52-week high** — a distinct dimension from window return; a slow
  6-month grind down and a sharp 6-week crash both matter, and drawdown-from-high
  catches the crash case that a windowed return can dilute.
- **Not already reversing** — last ~20 trading days should not already show a sharp
  recovery. The whole point is catching live pessimism, not congratulating a rally
  that already happened (Shaun's own framing: he wants this *before* the massive
  reversal, not as a retrospective).

An industry "qualifies" as hated when it clears all of: bottom-N of the 39 on the
6-month window, underperforms SPY by some minimum margin on both windows, and a
minimum drawdown-from-high — exact thresholds TBD in `/plan-feature`, tune after
first run (same "start conservative, loosen from real output" precedent as
Cash-Value Scan's 0.80→0.50 and the Moat Scanner's 80 stage threshold).

### 2. Narrative classification — what's the story, and is it industry-wide or one loud name

Reuse `mytrader/news_search.py`'s exact mechanism: `sdk_compat.run_text` with
`allowed_tools=["WebSearch"]` (Codex backend's flat-rate web search, cached per
subject with a time-based TTL — see that module's docstring). Same idea, new
industry-scoped prompt, run **only** for industries that already cleared gate #1
(bounds the LLM/search cost to a handful of names a day, not all 39).

Ask it to return structured JSON: a one-line dominant negative narrative (e.g. "AI
disruption fear", "rate-cycle cost-of-capital fear", "oversupply/commodity glut",
"regulatory crackdown", "one large constituent's company-specific scandal dragging
the index"), whether the pain reads as **industry-wide/systemic** vs concentrated in
one or two large constituents, and — the actual point of this whole tool — whether
the stated reasoning plausibly applies **uniformly** across the industry or looks
like an overgeneralization from a subset of names (mirrors Shaun's own SaaS
argument: "AI replaces software" was treated as a blanket industry risk when it
demonstrably didn't apply evenly).

### 3. Fundamentals-divergence check — did the business actually get worse, or just the price

The concrete test for "reasons weren't sound": pull a small handful of the ETF's
largest constituent holdings and check whether **trailing revenue/earnings growth
is still healthy** despite the price collapse. Price down hard + fundamentals still
growing/flat = divergence = the overreaction signature Shaun described. Price down
hard + fundamentals also rolling over = the hate may be earned; say so, don't hide
it.

**Open gap, flag for `/plan-feature`:** nothing in this codebase currently fetches
an ETF's top holdings. `mytrader/cash_value_scan.py`, `ai_resistant_moat_scanner`,
etc. all work from a *screened universe* of individual tickers, never "what's inside
this ETF." Two realistic options: (a) a small hardcoded
`GOAT_INDUSTRY_TOP_HOLDINGS: dict[str, list[str]]` seed table (3-5 known largest
constituents per one of the 39 covered ETFs — same spirit as the Moat Scanner's
curated `MOAT_SEED_TICKERS`, and avoids a live holdings-scrape dependency), refreshed
by hand occasionally; (b) scrape the ETF provider's public holdings page
(State Street/iShares/VanEck/Invesco depending on issuer — no consistent format
across all 39, meaningfully more scraper surface area than option (a)). Recommend
(a) for v1 — cheaper, and the DMA Breakout handoff already established this
codebase's comfort with "leave a documented gap rather than build a fragile
scraper" (see its `sector_label` ASX gap note).

## Reference code to reuse (read all of these during `/plan-feature`)

- **`goat/industry_rotation.py`** (`fetch_all_industry_closes()`, `rank_industries()`)
  and **`goat/config.py`**'s `GOAT_INDUSTRY_ETFS` / `GOAT_FINVIZ_INDUSTRIES` /
  `GOAT_INDUSTRY_HISTORY_LOOKBACK_DAYS` — the entire industry-universe/price-history
  foundation this tool sits on top of. Do not re-fetch or re-derive the 39-ticker
  universe; import and extend.
- **`goat/sector_rotation.py`'s `check_sector_breakout()`** — the sign-flip/
  cross-detection idiom, useful reference for the "not already reversing" recency
  check (inverse direction: has the industry crossed back *above* a short MA
  recently, which would mean the reversal has already started).
- **`mytrader/news_search.py`** in full, plus **`checks/news_events.py`**'s module
  docstring (explains *why* yfinance's own `.news` feed was rejected as a data
  source for this kind of check — the same reasoning applies here, don't reach for
  `Ticker(x).news` instead of the WebSearch pattern). Copy the `_SEARCH_PROMPT` /
  `_parse_json` / per-subject cache-with-TTL shape (`NEWS_EVENTS_CACHE_HOURS`
  precedent), rewritten for an industry subject instead of a ticker subject.
- **`ai_resistant_moat_scanner/qualitative.py`** — the closest existing example of
  an LLM call returning a structured rubric-style verdict (nullable fields, "not
  disclosed → null, never guessed" discipline) rather than a single score; the
  narrative-classification call in part 2 above should follow the same discipline
  (uncertain → say so, don't force a confident-sounding label).
- **`mytrader/cash_value_scan.py`** — per-ticker fundamentals fetch via yfinance
  `.info`/financial statements, its courtesy-delay pattern, and its
  DEGRADED/STALE-banner-on-failure handling — reuse for part 3's small
  per-constituent fundamentals pull.
- **`goat/heartbeat_scan.py`** — the orchestrator shape (gate → enrich → stage
  fresh → render → notify-on-fresh-only, silent on zero) to copy for this tool's
  `run_hated_industries_scan()`.
- **`goat/db.py`**'s `goat_insider_filings_seen` / `superinvestor_filings/db.py`'s
  `superinvestor_filings_seen` — the "seen" dedup-table pattern this tool needs
  (see below) so a WhatsApp alert fires only when an industry **newly** crosses
  into hated status, not every day it remains hated.
- **`briefs-finance`'s ethical filter** (`scripts/ethical_filter.py`) — apply it to
  part 3's constituent-holdings list, same as every other broad-universe scan in
  this codebase.

## Design decisions to nail down in `/plan-feature` (this doc's best-guess defaults)

1. **Severity thresholds** (gate #1) — exact bottom-N cutoff, minimum
   underperformance-vs-SPY margin (3mo and 6mo), minimum drawdown-from-52wk-high.
   Start conservative (fewer, higher-conviction flags), tune after first live run.
2. **"Not already reversing" window** — how many recent trading days of recovery
   disqualifies an industry as "still currently hated." Too short and a one-day
   bounce filters it out prematurely; too long and the tool becomes retrospective
   (catches the story after the reversal, which is exactly what Shaun does *not*
   want). Suggest ~10-15 trading days as a first guess, same order of magnitude as
   `GOAT_SECTOR_CROSS_RECENCY_DAYS` (10) elsewhere in this codebase.
3. **Top-holdings source** — pick option (a) or (b) from part 3 above (recommend
   (a), the hardcoded seed table).
4. **Seen/dedup table schema** — new small table, e.g.
   `goat_hated_industries_seen (industry_label TEXT PRIMARY KEY, first_flagged_at
   TEXT, last_flagged_at TEXT, status TEXT)`, so re-qualifying on day 2 doesn't
   re-fire a WhatsApp alert; only a fresh industry_label not currently in the table
   fires one. Decide whether a status transition (industry drops back out of the
   hated set, later re-qualifies) should be treated as "new" again — recommend yes
   (delete or status-flip the row on drop-out, so a genuine second wave re-alerts).
5. **No ticker-level candidate staging in v1.** This tool flags industries, not
   stocks — recommend it does **not** write into `goat_pending_candidates` (that
   table's `ticker UNIQUE` constraint doesn't fit an industry label anyway, and
   conflating this with a stock-pick pipeline blurs its job versus the Moat
   Scanner's). Confirm Shaun agrees the output is industry-level only for v1, with
   representative constituent tickers shown as read-only pointers, not stageable
   candidates.
6. **Backtest sanity check against the real SaaS episode.** Before shipping,
   manually run the severity gate's logic against Software - Application (`IGV`,
   already in `GOAT_INDUSTRY_ETFS`) over the actual 2026 AI-fear window Shaun is
   describing, using real historical yfinance data, to confirm the chosen
   thresholds would genuinely have flagged it (and roughly when, relative to when
   the reversal started) rather than missing it or firing too late. This is the
   single best validation this tool has, since it's calibrating against a real,
   named episode rather than a synthetic fixture.
7. **Cadence/schedule.** VPS systemd timer, daily. Existing UTC slots today: 21:35
   (Goat Monitor), 21:50 (Goat Insider Scan), 22:05 (Fourteen Crash Signals), 22:30
   (Cash-Value Scan), 22:45 (Goat Heartbeat Scan), 23:30 (AI-Resistant Moat Scan).
   The still-unbuilt DMA Breakout Scanner handoff suggested 22:55. Suggest **23:50
   UTC** for this one (after Moat Scan) to avoid contention — confirm no clash if
   DMA Breakout ships first during `/plan-feature`.
8. **LLM/search cost shape.** Part 2's WebSearch call only runs for industries that
   already cleared gate #1 (a handful of names a day at most, likely 0-8 out of
   39), same cost-bounding principle as the Moat Scanner's "only score fresh/seed/
   staged names" and `news_events.py`'s per-ticker cache — confirm this stays true
   after `/plan-feature` fleshes out the actual call graph.

## Explicitly deferred (do not build as part of this handoff)

- **Breadth-of-selloff analysis** (what fraction of an industry's constituents are
  individually down, vs one or two large names dragging the whole ETF) — a real
  improvement to the narrative-classification step's "industry-wide vs
  concentrated" call, but needs full constituent-level data this tool doesn't yet
  have a source for. Note as a v2 idea.
- **Any buy/verdict/score.** This tool surfaces evidence (severity + narrative +
  fundamentals divergence) for Shaun to judge — it does not compute a single
  "overreaction score" or say "buy this." Same SOUL.md "no trade action" discipline
  as every other Goat report.
- **Extending past the 39 ETF-covered industries** — same known 39/143 coverage gap
  `industry-ranking.md` already documents; not this tool's job to fix.
- **Staging individual constituent tickers as watchlist candidates** — that's the
  Moat Scanner's and my-trader Find's job; this tool's output should point at them,
  not duplicate them.

## Recommended shape

- New module `investments/goat/goat/hated_industries_scan.py`:
  `compute_industry_severity()` (extends `industry_rotation`'s closes with a 3-month
  window + SPY comparison + drawdown-from-high), `classify_industry_narrative()`
  (WebSearch call, industry-scoped, cached), `check_fundamentals_divergence()`
  (per-constituent yfinance pull against the seed holdings table),
  `run_hated_industries_scan(conn) -> dict` (orchestrator), `render_hated_industries_report(result) -> str`.
- New config constants in `goat/config.py`: `GOAT_HATED_MIN_UNDERPERFORMANCE_VS_SPY_3MO`,
  `_6MO`, `GOAT_HATED_MIN_DRAWDOWN_FROM_HIGH_PCT`, `GOAT_HATED_REVERSAL_LOOKBACK_DAYS`,
  `GOAT_INDUSTRY_TOP_HOLDINGS` (seed table), report path constant.
- New CLI subcommand `scan-hated-industries` in `goat/main.py`.
- New table `goat_hated_industries_seen` in `goat/db.py` (dedup/first-seen tracking
  only, no candidate staging — see decision #4/#5 above).
- Output: `investments/goat/hated-industries-report.md` — per qualifying industry:
  3mo/6mo return, vs-SPY delta, drawdown-from-high, narrative thesis + systemic-vs-
  concentrated call, fundamentals-divergence read, 3-5 representative constituent
  tickers (read-only, not stageable). One WhatsApp+toast alert per **newly**
  flagged industry, silent on a day with no new entries.

## Deployment / integration notes

- New timer: `second-brain-goat-hated-industries-scan.timer` +
  `.service` in `scripts/systemd/`, copying `second-brain-goat-heartbeat-scan.{timer,service}`
  (`ExecStart=... python -m goat.main scan-hated-industries`).
- Add rows to `investments/TOOLS.md`'s "Daily Read" table, "Automated (scheduled)"
  table, and a "Goat hated-industries scan (on-demand)" row in "Manual / on-demand
  only" (`-Package goat -Command "scan-hated-industries"`).
- Add the new timer name to `scripts/deploy.ps1`'s `$TIMERS` stop/start list.

## Validation (once built)

```powershell
.\scripts\invoke_investments.ps1 -Package goat -Command "scan-hated-industries"
```

Expected output: `investments/goat/hated-industries-report.md`, a WhatsApp+toast
alert only for industries newly entering the hated set this run.

Test with hand-built fixtures covering: an industry with a clean severity-gate
qualification (should fire and get enriched with narrative + fundamentals);
an industry merely lagging (below-median but not clearing the vs-SPY/drawdown
thresholds — should not fire); an industry that qualified yesterday and still
qualifies today (should not re-alert, per the seen table); an industry that
qualified, dropped out, then re-qualified later (should re-alert, per decision #4);
an industry already showing a sharp recent recovery inside the reversal-lookback
window (should not fire even if the 6-month window is still deeply negative). Plus
the real-data backtest against `IGV`/Software - Application from decision #6 above.
