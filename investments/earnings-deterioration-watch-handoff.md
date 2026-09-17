# Earnings Deterioration Watch — Session Handoff

Tool name: **Earnings Deterioration Watch**. Proposed home: **inside the existing
`my-trader` package** as a new module `investments/my-trader/mytrader/earnings_watch.py`
+ a new `checks/earnings_deterioration.py` check, with its own dedicated daily VPS
timer (own report, own cadence) rather than folded into Monitor's core loop — see
"Why not just add this to Monitor" below. Not a new uv-workspace member: this tool
leans almost entirely on infrastructure `my-trader` already owns (`sec_filings.py`,
`asx_announcements.py`, `news_search.py`, the `holdings` table), same "extend the
existing package" precedent as the Hated Industries Scanner handoff and Goat's own
family of scans living together in one package.

## Status: NOT BUILT — drafted 2026-09-17 from Shaun's request. Awaiting Shaun's
manual `/plan-feature` run against this doc before any implementation.

## What This Is

Shaun's ask, in his words: a daily check on his **holdings** that looks for an
indication that **earnings are starting to go down** — early enough to be a reason
to consider selling, not just a confirmation after the fact. His explicit framing:
official reported earnings only arrive quarterly (10-Q/10-K), but **earnings
expectations move every day** — guidance updates, 8-Ks, operating KPIs, industry
data, alternative data, and analyst estimate revisions all shift between report
dates and can be read as leading indicators of a coming earnings miss or downgrade.

This is the mirror image of `checks/opportunity.py` — same spirit as every other
`investments/` tool: advisor notes only, no sell recommendation, no automatic
action (SOUL.md). It surfaces evidence for Shaun to weigh; it does not compute a
single "sell" verdict.

Scope: **holdings only**, not watchlist. Deliberately narrower than Monitor's
holdings+watchlist loop (see cost discussion below) — a ticker Shaun doesn't yet
own doesn't need an earnings-decline early warning; that's Find's job when he's
actually assessing it.

## Why not just add this to Monitor

`checks/news_events.py`'s own module docstring already ruled on this shape of
question: an LLM+WebSearch call per ticker is "too costly/slow for Monitor's daily
re-check of 50+ holdings/watchlist rows" — which is why `news_events` is Find-only,
opt-in, never run unattended. This new tool needs *multiple* such calls per ticker
(guidance search, 8-K summarization, industry context) run daily, unattended, so
folding it into Monitor's existing loop would compound exactly the cost problem
that decision already flagged.

The fix isn't to skip the daily cadence Shaun asked for — it's to scope this tool to
**holdings only** (materially fewer tickers than Monitor's holdings+watchlist
combined) and give it its **own timer**, matching the precedent already set by
**Goat Insider Scan**: a separate daily VPS job that also only checks holdings,
with its own report file and its own WhatsApp alert channel, run independently of
Monitor rather than folded into it.

## The signal set (mapped to what this codebase can and can't already do)

Shaun listed seven source categories. Grouping them by how cheaply/reliably they
can actually be built here, cheapest-and-most-reliable first:

### 1. Analyst estimate revisions — the closest thing to "moves every day," and free

yfinance already exposes forward-looking analyst data (`Ticker.eps_trend`,
`Ticker.earnings_estimate`, `Ticker.revenue_estimate`, `Ticker.analyst_price_targets`)
that this codebase does not currently use anywhere for holdings. Also worth noting:
`market_data.py`'s `TickerData` already fetches `t.calendar` (next earnings date +
current EPS/revenue estimate avg/low/high) into every `TickerData` object — and it
is **currently unused by any check**, exactly the same "already fetched, nobody
reads it yet" gap `checks/news_events.py`'s docstring found for `TickerData.news`
before that check was built.

Proposed mechanic: record each day's consensus EPS/revenue estimate (and, if
`eps_trend` is available, the revisions-up/revisions-down counts over the last
7/30/60/90 days) into a new small history table, and flag when the **trend** is
consistently downward over a rolling window — not a single day's noise, a genuine
multi-day drift. This is the one sub-signal that directly matches Shaun's closing
line ("official earnings are periodic; earnings expectations move every day") with
hard, free, structured data — should be the backbone of the tool, not an add-on.

### 2. Regulatory filings (8-Ks) — hard, filed, event-driven data

`sec_filings.py` today only fetches `SEC_FILING_TYPES = ("10-K", "10-Q", "DEF 14A")`
— **no 8-K support exists yet**. This is a real gap to close, not a tuning knob:
8-Ks are the SEC's event-driven disclosure form, and several of its Items are
directly earnings-relevant — Item 2.02 (Results of Operations, incl. pre-announced
results/guidance updates), Item 2.05/2.06 (restructuring/impairment charges),
Item 1.01/1.02 (material agreement entered/terminated — e.g. losing a major
customer contract), Item 7.01 (Reg FD disclosures, often investor-day materials).

Proposed mechanic: extend `sec_filings.py`'s per-ticker EDGAR index fetch to also
list 8-Ks, filter to the earnings-relevant Item codes above (ignore routine ones —
8-Ks fire for many housekeeping reasons that aren't earnings signals, e.g. Item 5.02
officer appointments unrelated to performance), and run the *existing*
`_summarize_sections`-style LLM summary over just the newly-filed ones since the
last run (same `sec_filing_cache`-style dedup-by-`accession_number` this module
already does for 10-Ks — a new 8-K is a new accession number, so the cache pattern
extends cleanly).

### 3. Industry data — already built elsewhere, reusable read-only

Goat's `industry_rotation.py` + `GOAT_INDUSTRY_ETFS` (39 industry-ETF universe,
already tracks price momentum by industry) is a ready-made proxy for "is the whole
industry rolling over," and the still-unbuilt Hated Industries Scanner (see its own
handoff) will add drawdown/underperformance-vs-SPY on top of that. Rather than
re-fetch commodity/freight/loan-growth/ad-spend data per sector from scratch,
reuse Goat's per-industry price context read-only for each holding's mapped
industry (same cross-package read precedent already established: Goat reads
my-trader's `holdings`/`watchlist` tables, the Moat Scanner reads Goat's
`sp500_universe`). This is context, not a standalone gate — "your holding's whole
industry ETF is also declining" corroborates a company-specific deterioration
signal but isn't one on its own (a rising tide can still sink one boat and vice
versa).

### 4. Guidance / management commentary / conference appearances

Reuse `news_search.py`'s exact mechanism (`sdk_compat.run_text` with
`allowed_tools=["WebSearch"]`, cached per subject with a time-based TTL, same as
`NEWS_EVENTS_CACHE_HOURS`) with a new earnings-focused prompt: "{ticker} lowers
guidance", "{ticker} cuts outlook", "{ticker} misses estimates", "{ticker} investor
day" / "{ticker} conference presentation" commentary specifically about
deteriorating demand, margin pressure, or slowing growth. Same discipline as
`_SEARCH_PROMPT`'s existing style — report only what's found with real evidence,
never speculate, ignore routine noise older than ~last quarter.

### 5. Monthly/weekly operating data (same-store sales, subscribers, GMV, traffic…)

No structured feed for this exists in the codebase and none is generic across
arbitrary tickers — fold this into signal #4's same WebSearch call rather than
building a fifth separate mechanism (a per-ticker "any published operating metrics
this month showing a slowdown?" question added to the same prompt) — keeps this
to one LLM/search call per holding per day instead of two.

### 6. Alternative data (app downloads, web traffic, credit-card spend, job postings)

**Explicitly deferred — no free source exists.** App download/web-traffic/
credit-card-spend panels (Sensor Tower, Similarweb, Facteus/Earnest, Thinknum,
etc.) are paid data providers this codebase has no subscription to and none of its
existing tools touch. Don't fake this with a WebSearch call dressed up as
alt-data — flag it explicitly in the report as "not covered" rather than silently
omitting it, so Shaun knows the gap exists rather than assuming it's covered.

## Open Questions (resolve during `/plan-feature`)

1. **Estimate-revision trend threshold.** How many consecutive days of downward
   consensus EPS/revenue drift (or how big a cumulative % cut) should flag, vs.
   normal day-to-day estimate noise? Start conservative, tune after the first
   week or two of real history accumulates in the new history table (there's no
   way to backtest this against fixtures the way Hated Industries backtested
   against the real SaaS episode — this one needs live data first).
2. **8-K Item-code allowlist.** Confirm the exact Item codes worth surfacing
   (2.02, 2.05, 2.06, 1.01, 1.02, 7.01 proposed above) vs. the ones to ignore
   (5.02 officer changes, 5.03 bylaw amendments, etc. — routine housekeeping that
   would just be noise on a daily holdings report).
3. **Per-signal verdict vs. one blended verdict.** Does each holding get one
   combined "early warning" verdict (analogous to `opportunity.py`'s single
   verdict), or does the report show each of the 5 active signals independently
   so Shaun can see *which* one is firing? Recommend the latter — Shaun's own
   framing treats these as different categories of evidence with different
   reliability (hard filed data vs. LLM-judged commentary), and collapsing them
   into one verdict would hide that distinction the way `news_events.py`'s
   docstring is careful never to do for its own LLM-judged calls.
4. **Alerting cadence.** New-8K-Item and new-guidance-cut events should alert
   once (dedup via a `first_seen`/`accession_number`-keyed table, same pattern as
   `sec_filing_cache` / Goat's various `_seen` tables) — but should the estimate-
   revision trend re-alert if it keeps worsening day over day, or only on first
   crossing the threshold? Recommend: fire once on first threshold-cross, then
   stay quiet unless the trend meaningfully worsens further by some second,
   larger threshold (avoids a daily repeat alert for an unchanged decline).
5. **Cadence/schedule.** Daily, VPS systemd timer. Existing UTC slots: 21:35
   (Goat Monitor), 21:50 (Goat Insider Scan), 22:05 (Fourteen Crash Signals),
   22:30 (Cash-Value Scan), 22:45 (Goat Heartbeat Scan), 23:30 (AI-Resistant Moat
   Scan), 23:50 (Hated Industries Scanner, unbuilt). Suggest a slot after my-trader
   Monitor's own 7:30am Sydney run (this tool wants that day's fresh holdings list
   and current prices, same as Monitor) — confirm exact UTC time during
   `/plan-feature` once the still-unbuilt tools above have claimed their slots.
6. **ASX holdings.** `asx_announcements.py` is the ASX-listed sibling of
   `sec_filings.py` (PDF announcements, not 8-Ks) — should ASX holdings get an
   equivalent "material announcement" check reusing that module, so this tool
   isn't US-only? Recommend yes, same non-US-degrades-gracefully pattern already
   established (`sec_filings.py` returns `None` for non-US tickers; ASX holdings
   would instead route through `asx_announcements.py`).
7. **Cost/call-volume check.** Confirm actual holdings count at build time and
   estimate total daily LLM/WebSearch calls (signal #4/#5 combined = 1 call per
   holding/day; 8-K summarization = 1 call per *newly filed* 8-K, which is
   intermittent, not daily-per-holding) — sanity-check against Monitor's own
   cost reasoning before committing to the daily-for-every-holding shape.

## Explicitly deferred (do not build as part of this handoff)

- **Any sell verdict or price target.** This tool surfaces evidence only — same
  SOUL.md discipline as every other `investments/` tool. The decision to sell
  stays entirely Shaun's.
- **Alternative data (app downloads, web traffic, credit-card spend, job
  postings).** No free source exists in this codebase's current toolset — see
  signal #6 above. Note as a future idea if Shaun later wants to pay for a data
  provider.
- **Watchlist coverage.** v1 is holdings-only, deliberately, for cost reasons —
  see "Why not just add this to Monitor" above. A future version could extend to
  `status="discussed"` watchlist rows the same way Monitor already scopes its own
  watchlist loop, if the cost math holds up after holdings-only is proven out.
- **Backtesting the estimate-revision threshold against history.** No historical
  estimate-revision data is stored anywhere yet (this tool would be the first
  thing to start capturing it) — nothing exists to backtest against on day one;
  tune forward from live data instead (see open question #1).

## Reference code to reuse (read all of these during `/plan-feature`)

- **`mytrader/sec_filings.py`** — SEC EDGAR fetch + CIK map + per-filing LLM
  summary cache keyed on `accession_number`. Needs extending: add `"8-K"` support
  (today's `SEC_FILING_TYPES = ("10-K", "10-Q", "DEF 14A")` has none), including
  Item-code parsing from the filing index (8-Ks disclose their triggering Item(s)
  in the EDGAR filing index metadata, not just the document body).
- **`mytrader/asx_announcements.py`** — the ASX-listed sibling, PDF-based, for
  open question #6.
- **`mytrader/news_search.py`** + **`checks/news_events.py`**'s module docstring —
  the exact WebSearch+LLM mechanism and cache-with-TTL shape for signals #4/#5,
  plus the cost-reasoning precedent this handoff's "Why not just add this to
  Monitor" section is built on.
- **`mytrader/market_data.py`**'s `TickerData.calendar` — already-fetched, currently
  unused yfinance `.calendar` data (next earnings date + estimate avg/low/high).
  Check live whether `yfinance`'s newer `Ticker.eps_trend` /
  `Ticker.earnings_estimate` / `Ticker.revenue_estimate` accessors are available in
  the pinned yfinance version — those weren't checked live for this handoff, only
  `.calendar` was confirmed in use elsewhere.
- **`goat/industry_rotation.py`** + **`goat/config.py`**'s `GOAT_INDUSTRY_ETFS` —
  read-only industry-context reuse for signal #3.
- **`mytrader/monitor.py`** — the orchestrator shape (per-holding loop, alert
  reconcile/dedup via `alert_history`, report render, toast-only notify pattern)
  to copy for this tool's own `run_earnings_watch()`, even though it runs as its
  own timer rather than inside Monitor itself.
- **`mytrader/db.py`**'s `holdings` table + `alert_history` — reuse the existing
  dedup-alert pattern (`get_open_alert`/`insert_alert`/`acknowledge_alert`) for the
  8-K/guidance signals; the estimate-revision trend needs a **new** history table
  (see open question #1) since nothing tracks day-over-day analyst estimates yet.
- **`goat/db.py`**'s various `_seen` tables (e.g. `goat_insider_filings_seen`) —
  precedent for a small dedup table keyed on filing accession number.

## Recommended shape

- New module `investments/my-trader/mytrader/earnings_watch.py`:
  `fetch_estimate_snapshot()` (yfinance estimate/eps_trend pull + write to new
  history table), `compute_estimate_trend()` (rolling-window drift check),
  `fetch_new_earnings_relevant_8ks()` (extends `sec_filings.py`), `search_guidance_and_kpis()`
  (reuses `news_search.py`'s mechanism, earnings-focused prompt), `fetch_industry_context()`
  (read-only Goat industry reuse), `run_earnings_watch(conn) -> dict` (orchestrator
  over holdings only), `render_earnings_watch_report(result) -> str`.
- New check `investments/my-trader/mytrader/checks/earnings_deterioration.py` if
  the signals should also surface inside Find/Monitor's per-ticker check list (TBD
  in open question #3 — may instead be report-only, not wired into `engine.py`'s
  check list at all, if it stays a standalone daily scan rather than an on-demand
  check).
- New config constants in `mytrader/config.py`: extend `SEC_FILING_TYPES` (or a
  parallel `EARNINGS_WATCH_8K_ITEM_CODES` allowlist), estimate-revision trend
  window/threshold constants, report path constant.
- New CLI subcommand (e.g. `scan-earnings-watch`) in `mytrader/main.py`.
- New table(s) in `mytrader/db.py`: an estimate-history table (ticker, date,
  eps_estimate, revenue_estimate, revisions_up, revisions_down) and a small
  8-K/guidance "seen" dedup table (ticker, accession_number or a hash of the
  guidance-search finding, first_seen_at).
- Output: `investments/my-trader/earnings-watch-report.md` — per holding with any
  active signal: which signal(s) fired, the underlying evidence (accession number
  + Item code for 8-Ks, the WebSearch finding text for guidance, the estimate
  trend numbers), and an explicit "not covered: alternative data" note per the
  deferred signal #6. One WhatsApp+toast alert per **newly** flagged signal per
  holding, silent on a day with nothing new (same dedup discipline as every other
  scanner in this codebase).

## Deployment / integration notes

- New timer: `second-brain-mytrader-earnings-watch.timer` + `.service` in
  `scripts/systemd/`, modeled on `second-brain-goat-insider-scan.{timer,service}`
  (`ExecStart=... python -m mytrader.main scan-earnings-watch`).
- Add rows to `investments/TOOLS.md`'s "Daily Read" table, "Automated (scheduled)"
  table, and a "my-trader earnings watch (on-demand)" row in "Manual / on-demand
  only" (`-Package my-trader -Command "scan-earnings-watch"`).
- Add the new timer name to `scripts/deploy.ps1`'s `$TIMERS` stop/start list.

## Validation (once built)

```powershell
.\scripts\invoke_investments.ps1 -Package my-trader -Command "scan-earnings-watch"
```

Expected output: `investments/my-trader/earnings-watch-report.md`, a WhatsApp+toast
alert only for holdings with a **newly** fired signal this run.

Test with hand-built fixtures covering: a holding with a clean downward
estimate-revision trend crossing threshold (should fire); a holding with normal
day-to-day estimate noise, no sustained trend (should not fire); a holding with a
new earnings-relevant 8-K (Item 2.02 guidance cut — should fire and be summarized)
vs. a routine 8-K (Item 5.02 officer change — should be ignored); a holding whose
signal fired yesterday and is still true today (should not re-alert, per the seen
table); a non-US (ASX) holding routing through `asx_announcements.py` instead of
`sec_filings.py`; a holding with zero data available anywhere (all signals
degrade gracefully, report says "no data" rather than erroring the whole run).

## Sources consulted (2026-09-17)

- `investments/my-trader/mytrader/sec_filings.py`, `asx_announcements.py`,
  `news_search.py`, `market_data.py`, `monitor.py`, `db.py`, `config.py`
- `investments/my-trader/mytrader/checks/news_events.py`,
  `checks/opportunity.py`
- `investments/goat/goat/config.py` (`GOAT_INDUSTRY_ETFS`)
- `investments/TOOLS.md`
- `investments/hated-industries-scanner-handoff.md`,
  `investments/ai-resistant-moat-scanner-handoff.md` (handoff + deployment style)
- `scripts/systemd/second-brain-goat-insider-scan.{service,timer}`
