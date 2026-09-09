# AI-Resistant Moat Scanner — Session Handoff

Tool name: **AI-Resistant Moat Scanner**. Proposed package dir
`investments/ai-resistant-moat-scanner/`, Python module `ai_resistant_moat_scanner`
(following the `fourteen-crash-signals-daily-check` / `superinvestor-filings`
dir-name = module-name convention). CLI: `python -m ai_resistant_moat_scanner.main scan`.

## Status: NOT BUILT — drafted 2026-09-07 from Shaun's request, named 2026-09-09. Awaiting Shaun's manual `/plan-feature` run against this doc before any implementation.

## What This Is

Shaun's thesis, in his words: Salesforce is a software company with a moat strong
enough to survive AI, because it is "so engrained in the customer's business' DNA
that the ROI of building something with AI to replace it doesn't make sense." He
wants a tool that scours the market for other companies with that same property.

So: a daily VPS scan that ranks public companies by how **AI-durable their
embedded-software moat** is — how much a customer would have to rip out, migrate,
re-integrate, re-train and re-certify to replace them, versus how cheaply an
LLM-built alternative could do the job. Advisor-notes only, same as every other
`investments/` tool — no auto-buy, no auto-watchlist-add. Fresh high-scoring names
land in a pending-review staging area for explicit promote/dismiss.

Shaun's two decisions already made (2026-09-07):
1. **Scope:** not software-only. Include embedded vertical software — healthcare
   IT, financial / tax / accounting, legal, industrials/engineering software,
   payroll/HR, logistics. The Salesforce pattern (system of record + switching
   costs + ecosystem lock-in) exists across all of them.
2. **Cadence:** daily, on a VPS systemd timer, same shape as the Goat Heartbeat
   Scan.

## The moat rubric (what the score actually measures)

A blended 0–100 "embedded moat / AI-resistance" score. Two halves.

### Quantitative half (yfinance + SEC filings — no LLM)

Proxies for real switching costs and durable, entrenched revenue:

- **Gross margin ≥ ~75%** — true software economics; low margin means a
  services/hardware business AI competes with differently.
- **Recurring / subscription revenue as a share of total** — one-off or
  transactional revenue is not lock-in.
- **Net revenue retention (a.k.a. dollar-based net retention) ≥ ~110%** —
  the single best public number for "customers can't leave and keep spending
  more." Not in yfinance; must be pulled from the 10-K / 10-Q text.
- **Deferred revenue and remaining performance obligations (RPO) growing** —
  contracted, prepaid backlog = customers locked into multi-year terms.
- **Revenue durability through drawdowns** — did revenue hold up through the
  2020 and 2022 macro shocks? Low revenue coefficient-of-variation = mission
  critical, paid through downturns.
- **Free-cash-flow margin ≥ ~20%** — pricing power still intact; a moat under
  attack shows up as margin erosion first.
- **Large, growing customer base with low logo churn** — disclosed in some
  10-Ks, not all.
- **Rule-of-40-ish health** — not a moat signal itself, but a fast-decaying
  score is an anti-signal (moat already eroding).

Most of these are computable from `yfinance` `.info` / financial statements the
same way `mytrader/cash_value_scan.py` already does it. NRR, RPO, customer
counts and churn need text extraction from filings.

### Qualitative half (LLM on the 10-K "Business" + "Risk Factors" sections)

Reuse the exact pattern in `mytrader/sec_filings.py` +
`mytrader/checks/principles_fit.py`: fetch the latest 10-K via SEC EDGAR, extract
Item 1 (Business) and Item 1A (Risk Factors), have the LLM score a fixed rubric.
Proposed sub-scores (0–10 each, LLM must cite filing language):

1. **System of record** — does the customer's critical operational data live
   inside this product? (CRM records, patient records, general ledger, payroll,
   claims, case files.) Migrating it out is the expensive, risky part.
2. **Switching costs** — how much re-implementation, data migration, staff
   re-training, workflow re-tooling, and re-certification does leaving cost?
3. **Ecosystem lock-in** — third-party app marketplace, developer platform,
   certified-consultant / systems-integrator economy, partner channel. (This is
   the specific thing that makes Salesforce near-impossible to displace even
   though a CRM is conceptually simple.)
4. **Regulatory / compliance entrenchment** — is the software the certified,
   audited system for a regulated process (HIPAA, SOX, tax filing, clinical)?
5. **Workflow breadth** — a broad integrated suite is far harder for a single
   AI build to replace than a narrow point tool.
6. **Mission criticality** — if it goes down, does the customer's business stop?

### Anti-signals (penalise, don't just omit)

- Point solution with a thin, easily-rebuilt workflow.
- Core value is content or data an LLM reproduces cheaply (generic analytics,
  templated docs, dashboards over public data).
- Low switching cost / month-to-month / seat-based-and-easily-cancelled.
- Moat already eroding: falling NRR, rising churn, margin compression, management
  language about "competitive pricing pressure" or "AI-native entrants."

## Open Questions (resolve during `/plan-feature`)

1. **Package placement.** This crosses more package boundaries than any existing
   tool: it needs `mytrader/finviz_screener.py` (universe), `mytrader/sec_filings.py`
   (10-K fetch + section extraction), the `principles_fit`-style LLM scoring
   pattern, `briefs-finance`'s ethical filter, and optionally `goat`'s
   `sp500_universe`. Options: (a) new uv-workspace member
   `investments/ai-resistant-moat-scanner/` that imports from `mytrader` the way
   `goat` already does — keeps `goat` focused on momentum/rotation; (b) a new subcommand
   inside `goat` (reuses its `goat_pending_candidates` staging + WhatsApp
   discovery-notify plumbing directly). Recommendation: **(a) new package**, but
   reusing goat's staging table cross-package (goat already reads mytrader's
   `holdings`/`watchlist` tables read-only, so precedent exists). Confirm.
2. **Universe definition.** S&P 500 is too narrow given decision #1 (embedded
   vertical software). Options: a Finviz screen across Technology +
   Healthcare-Information-Services + relevant Industrials/Financial-software
   industries with `market cap ≥ $2B` and `gross margin ≥ 60%` coarse prefilter;
   plus a small curated seed list of known embedded-moat names
   (CRM, NOW, INTU, ADP, PAYX, VEEV, TYL, ADSK, ANSS, PTC, SAP, ORCL, WDAY,
   SPGI, FICO, VRSK, ROP-family, CSU.TO, EPAM-no, etc.) so the scan is anchored
   even if the screen misses one. Which industries exactly, what market-cap
   floor, US-only or include ASX/LSE/TSX (SEC filing extraction is US-only —
   non-US names would run quant-half only, like `sec_filings.py` already
   degrades)? Shaun's ASX exposure matters here.
3. **NRR / RPO / churn extraction.** These live in free-form MD&A and Business
   prose, not in a fixed Item. Is a targeted LLM extraction pass over the MD&A
   section (returning structured JSON: `nrr_pct`, `rpo_usd`, `rpo_yoy`,
   `customer_count`, `churn_pct`, each nullable) acceptable, accepting that some
   filers just don't disclose them (score that sub-metric as "not disclosed",
   don't guess)?
4. **Score blend + threshold.** Weighting between the quant and qualitative
   halves, and the staging cutoff (what score makes a name a "candidate" worth
   Shaun's review vs. just a row in the full ranked report). Start conservative
   (only stage 80+), tune after first run — same approach as the cash-value
   scan's 0.80→0.50 loosening.
5. **Output shape.** A full ranked Markdown table
   (`investments/ai-resistant-moat-scanner/moat-scan-report.md`, overwritten each
   run) with sub-scores + a one-line thesis per name, plus a separate
   `moat-candidates-pending-review.md` staging file for fresh high-scorers —
   mirroring Goat Heartbeat's two-file pattern. Confirm the report belongs in
   TOOLS.md's "Daily Read" list or only the staging file does.
6. **Cadence details.** "Daily" per Shaun — what UTC time? The scan is heavy
   (Finviz pagination + one SEC 10-K fetch + 1–2 LLM calls per name over a
   universe of maybe 150–400 tickers). Options: run the full universe weekly and
   only a re-score of already-staged + seed names daily; or spread the universe
   across the week (N-th of the universe per weekday). SEC EDGAR fair-access
   rules (documented User-Agent, ~10 req/s cap) and yfinance rate-limiting both
   argue against hammering the whole universe nightly. The cash-value scan hits
   ~700 yfinance lookups/night with a 0.2s delay (~2.5 min) as a reference point.
7. **Caching.** 10-K text is static between annual filings — cache the extracted
   sections and the LLM sub-scores per `accession_number`, exactly like
   `sec_filings.py`'s `sec_filing_cache` does, so a daily run mostly re-reads
   cache and only re-scores names with a new filing or changed quant inputs.
8. **Notification shape.** Does a fresh high-scoring candidate fire a WhatsApp
   alert as it's found (like Goat Heartbeat discoveries via `maybe_notify`
   ticker+detail format), or is this a batch-review-only tool (open the staging
   file when you feel like it) with no push? Shaun's call.
9. **Ethical filter.** Run the shared `briefs-finance` ethical filter (defense
   contractors dropped, `BA`/`PLTR` tagged `REVIEW:`) — some defense-software
   and government-systems names (Palantir, Leidos, CACI) score very high on
   embedded moat, so this matters here.
10. **"AI-resistant" is a moving target.** The qualitative rubric encodes a
    2026 view. Worth a short dated note in the eventual SKILL.md / module
    docstring that the rubric is a snapshot and should be revisited, not treated
    as permanent — same spirit as the check-interpretation convention.

## Explicitly deferred (do not build as part of this handoff)

- Any attempt to price the moat (DCF, "is it cheap") — this tool ranks moat
  durability only. Valuation is my-trader Find's / briefs-finance's job; a
  high-moat name can then be run through those separately.
- Scoring private companies or pre-IPO names — public filings only.
- A "how exposed is my existing portfolio to AI disruption" reverse view — that's
  a holdings-side check (my-trader), a different tool. Note it exists as a future
  idea.
- Real-time news / sentiment ("is an AI-native competitor being funded") — a
  possible later enrichment, not v1. v1 is filings + financials only.
- Non-SEC filing extraction (ASX/LSE annual reports) beyond the quant half —
  `sec_filings.py` already documents this graceful degradation; don't build
  bespoke non-US filing parsers speculatively.

## Reference code already in the repo (reuse, don't reinvent)

- `investments/my-trader/mytrader/sec_filings.py` — SEC EDGAR fetch, CIK bulk
  map with staleness refresh, 10-K Item 1 / 1A / 7 section extraction (with the
  documented "keep LAST occurrence, not first" TOC-vs-body gotcha), per-filing
  LLM summary cache keyed on `accession_number`. This is ~80% of the qualitative
  half already.
- `investments/my-trader/mytrader/checks/principles_fit.py` — the pattern for an
  LLM scoring a fixed rubric against filing text and returning structured output.
- `investments/my-trader/mytrader/finviz_screener.py` — direct-fetch Finviz
  screener scraper, paginated, with the first-character-doubled watermark
  descramble and stale-fallback contract. `config.FINVIZ_SCREENER_FILTERS` is
  the coarse-prefilter knob.
- `investments/goat/goat/sp500_universe.py` — Wikipedia constituent scrape +
  cache-with-stale-fallback pattern, if an index universe is wanted alongside
  the Finviz screen.
- `investments/goat/goat/heartbeat_scan.py` — the exact orchestrator shape to
  copy: filter a universe, run a per-ticker check, attach context, stage fresh
  finds into `goat_pending_candidates` with a new `source` value, skip anything
  already held / on watchlist / already staged, render a two-part report
  (full ranked table + pending-review staging file), push new ones to WhatsApp,
  stay silent on a zero-candidate day.
- `investments/my-trader/mytrader/cash_value_scan.py` + the "Cash-Value Scan —
  how it works + tuning" section of `investments/TOOLS.md` — the closest
  existing analogue: a daily VPS universe scan, yfinance-per-ticker, ethical
  filter, ranked advisor-notes Markdown table, DEGRADED/STALE banner on
  rate-limit or scrape failure, `config.py` tuning knobs, no `Persistent=` on a
  scan where a missed day doesn't matter (contrast: the Goat Heartbeat timer
  DOES set `Persistent=true`).
- `investments/briefs-finance/scripts/ethical_filter.py` — the shared
  defense/military exclusion + `REVIEW:` tagging.

## Deployment pattern (from the insider-scanner + cash-value precedents)

- New uv-workspace member: add to `investments/pyproject.toml`
  `[tool.uv.workspace] members`.
- systemd unit pair under `scripts/systemd/`:
  `second-brain-ai-moat-scan.service` (Type=oneshot,
  `WorkingDirectory=.../investments/ai-resistant-moat-scanner`,
  `ExecStart=.../investments/.venv/bin/python -m ai_resistant_moat_scanner.main scan`,
  stdout+stderr `append:.../investments/ai-resistant-moat-scanner/moat_scan_runs.log`)
  and `second-brain-ai-moat-scan.timer` (`OnCalendar` daily UTC — pick a slot
  after the 22:45 Goat Heartbeat run so they don't contend for yfinance).
- Shared `investments.db` is VPS-only. All manual runs go through
  `scripts/invoke_investments.ps1 -Package ai-resistant-moat-scanner -Command "scan"` —
  never `uv run --directory` locally (would recreate an empty local DB, undoing
  the 2026-08-23 single-source fix).
- After building: add rows to `investments/TOOLS.md` (Automated table + Manual
  table + Daily Read if the report earns it) — that file is hand-maintained.

## Validation (once built)

```powershell
# tests (run on the VPS via the wrapper, or locally against fixtures only)
uv run --directory investments/ai-resistant-moat-scanner python -m pytest -q

# on-demand full run
.\scripts\invoke_investments.ps1 -Package ai-resistant-moat-scanner -Command "scan"

# expected outputs
#   investments/ai-resistant-moat-scanner/moat-scan-report.md                  (full ranked table)
#   investments/ai-resistant-moat-scanner/moat-candidates-pending-review.md    (fresh high-scorers)
```

## Sources consulted (2026-09-07)

- `investments/my-trader/mytrader/sec_filings.py`, `finviz_screener.py`
- `investments/goat/goat/sp500_universe.py`, `heartbeat_scan.py`
- `investments/TOOLS.md`, `investments/pyproject.toml`
- `investments/insider-trading-scanner-handoff.md` (handoff + deployment style)
- `scripts/systemd/second-brain-goat-heartbeat-scan.{service,timer}`
