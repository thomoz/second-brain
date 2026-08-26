# Cash-Value Scanner ("Cash 80% Trading Value") — Session Handoff

## Status: BUILT 2026-08-26 — see `.agent/plans/cash-value-scanner.md`. Code + tests landed; pending Level 4 VPS run + timer enable (see the plan's validation section). The rest of this file is kept as the historical background record.

## What This Is

Shaun's idea, 2026-08-26: a scheduled screener that finds companies **trading at
roughly cash value** — where net cash (cash minus debt) is at least **80% of the
company's market cap** — AND that generate good cash flow (not melting the cash
pile). Classic Graham / deep-value "you're buying the business for ~20c on the
dollar after backing out the bank balance" setup, with a going-concern quality gate
so the list isn't just dying companies burning down their reserves.

Advisor-notes only. Output is a report file, same shape as `goat-report.md` /
`my-trader-report.md` — **just a ranked list**, no candidate staging, no
auto-watchlist-add, no WhatsApp alert. Shaun runs his own deep dive (my-trader
`find`, briefs-finance `assess`) on anything on the list he likes the look of.

## Shaun's answers (captured 2026-08-26 — treat as decisions, not open questions)

1. **The metric** — "essentially trading at cash value. At least 80% of their
   company value is cash, and they have good cash flow." → net cash ≥ 80% of market
   cap, plus a positive-cash-flow gate. (Option (a) from the question round: net
   cash = cash + marketable securities − total debt.)
2. **Universe / data source** — OK to pull a Finviz or SEC bulk list to build the
   universe.
3. **Filters** — exclude defense/military (reuse the existing ethical filter).
   Nothing else mandatory: "I can run a deep dive on anything I like the look of
   that this tool shows." (So: keep quality/liquidity gates light — enough to keep
   the list actionable, not so tight it hides borderline names Shaun might still
   want to eyeball.)
4. **Output + cadence** — scheduled VPS daily timer, report written to a local
   `.md` file like the other tools.
5. **Packaging** — a subcommand on an existing tool if that makes sense.
6. **Feed-through** — just list them. No staging.
7. **Ranking** — "rank by whatever you think is most useful for a rookie to
   consider." (See "Ranking design" below — proposed, tune during planning.)
8. **Name** — Shaun's working name: **"Cash 80% Trading Value"**. (Suggest a CLI
   command like `cash-value-scan` and a report file `cash-value-report.md` —
   confirm during planning.)

## Context — the metric math

Per ticker, from `mytrader.market_data.fetch_ticker_data(t).info`:

- `net_cash = totalCash − totalDebt`
  (`totalCash` in yfinance bundles cash + equivalents + short-term investments;
  `totalDebt` bundles short + long-term debt, and — per the note in
  `mytrader/checks/balance_sheet.py` — capitalised leases under IFRS 16. That's the
  conservative, defensible number; don't try to strip leases out.)
- `cash_ratio = net_cash / marketCap` → **qualifies if ≥ 0.80**
- `ev_pct = marketCap − net_cash`, as a % of market cap (`= 1 − cash_ratio`) — "you
  are paying this fraction of the share price for everything the business does
  except its bank account." The rookie-friendly framing of the same fact.
- **Cash-flow gate** ("good cash flow"): positive trailing `operatingCashflow` AND
  positive `freeCashflow`. Fall back to `mytrader.market_data.fetch_cash_flow_statement(t)`
  (latest annual OCF / FCF) when the `.info` fields are missing. Exact definition
  (OCF-only vs OCF+FCF, TTM vs annual, any positive-margin floor) is a **tunable to
  confirm during planning** — spell it out in `config.py` with a "which direction
  is good" comment, per the repo's check-interpretation convention.

Longer-term marketable securities held outside `totalCash` (common for cash-rich
Japanese-style balance sheets) are **not** captured by this — note it as a known
understatement, don't try to solve it in v1.

## Context — data source (Finviz screener, live-checked 2026-08-26)

`https://finviz.com/screener.ashx` is publicly viewable, no login. A coarse
pre-filter query —
`v=111&f=fa_pc_u3,geo_usa,sh_avgvol_o100,sh_price_o1&o=pricecash` (Price/Cash under
3, US-listed, avg volume > 100K, price > $1) — returned **492 matches across 25
pages** today. Table columns: Ticker, Company, Sector, Industry, Country, Market
Cap, P/E, Price, Change, Volume. Free tier shows 20 rows/page, paginated via
`&r=1,21,41,…`; CSV export is Elite-only, so the plan is **scrape the HTML table**,
same `requests` + `BeautifulSoup` + headers + timeout + try/except-returns-None
style as `mytrader/openinsider.py` and `goat/sp500_universe.py`.

Why P/C < 3 as the coarse cut: Price/Cash uses **gross** cash, and net cash ≤ gross
cash, so any true positive (net cash ≥ 80% of mcap ⇒ gross cash ≥ 80% ⇒ P/C ≤ 1.25)
is safely inside a P/C < 3 net. The ~500 survivors then get the **precise** net-cash
+ cash-flow test in a yfinance enrichment pass (≈ the same per-ticker loop size as
Goat's S&P 500 heartbeat scan already runs daily). Financials/REITs get dropped in
enrichment (`sector in {"Financial Services", "Real Estate"}`) — net cash is
meaningless for a bank.

**Alternative / future upgrade — SEC XBRL `frames` API**
(`data.sec.gov/api/xbrl/frames/us-gaap/<concept>/USD/CY2025Q2I.json`): one call
returns every filer's value for a concept. More complete (catches small caps Finviz
paginates away) and no scrape fragility, but needs a declared User-Agent with
contact info (returned 403 without one today), concept-name reconciliation across
filers, and a CIK→ticker map. Heavier — document it as the v2 universe source, not
v1.

## Recommended design (confirm / adjust during `/plan-feature`)

- **Package**: `my-trader`. It already owns the screener-scrape pattern
  (`openinsider.py`), the yfinance fundamentals wrapper (`market_data.py` incl.
  `fetch_cash_flow_statement`), `tickers.normalize`, and it already imports the
  ethical filter (`from scripts.ethical_filter import check_ticker` in
  `engine.py`). This is a fundamentals/value screen — it belongs with
  my-trader/briefs-finance, **not** Goat (momentum/sector rotation — explicitly a
  different philosophy per `goat/HANDOFF.md`).
- **New modules**:
  - `mytrader/finviz_screener.py` — reusable Finviz screener-table scraper (sibling
    to `openinsider.py`; returns list of `{ticker, company, sector, industry,
    market_cap, price}` dicts, `None` on fetch failure, paginates internally).
  - `mytrader/cash_value_scan.py` — orchestration: coarse list → per-ticker
    enrichment → net-cash + cash-flow test → ethical filter → rank → render report.
- **CLI**: `python -m mytrader.main cash-value-scan` (new subparser + `cmd_` in
  `main.py`). Pure compute — **no DB reads or writes** (Shaun said "just list
  them"), so it does not need `_open_conn()`. Optional nicety: open a read-only
  conn just to tag rows Shaun already holds / watchlists — decide during planning.
- **Output**: `investments/my-trader/cash-value-report.md`. The VPS vault-sync
  script (`.claude/scripts/run_vault_sync.sh`) already commits
  `investments/my-trader/*.md`, so a VPS-written report reaches the local repo with
  no extra wiring.
- **Schedule**: new VPS systemd pair `second-brain-mytrader-cashvalue-scan.{service,timer}`,
  daily. Pick a UTC time that doesn't collide with the 21:35 / 21:50 / 22:05 Goat +
  crash-signal stack — e.g. 22:30 UTC. NOTE: my-trader's *Monitor* deliberately
  runs on Windows Task Scheduler, not the VPS, to avoid double-running — that
  carve-out does **not** apply here; a brand-new command with no Windows twin
  should run on the VPS like every other scheduled scan, alongside the shared DB.
- **Ethical filter**: `from scripts.ethical_filter import check_ticker` —
  auto-exclude `DEFENSE_TICKERS`, show `DEFENSE_REVIEW_TICKERS` with a REVIEW tag
  (same 3-way handling as `engine.py`).
- **Scrape etiquette**: real User-Agent, ~25 sequential page fetches per run (not
  concurrent), stale-cache-fallback on scrape failure (mirror
  `sp500_universe.get_or_refresh_*` — though with no DB, "cache" here may just mean
  "if the scrape fails, keep yesterday's report and note it's stale").

## Ranking design (proposed — Shaun delegated this, tune freely)

Primary sort: **`cash_ratio` descending** (most cash-like first). But the very top
of that list is where the going-concern disasters and untradeable micro-shells
live, so the report should *lead with the ratio but show enough context to judge*:

| Column | Why a rookie cares |
|---|---|
| Cash ratio (net cash ÷ mcap) | the headline — how much of the price is just cash |
| EV as % of mcap (`1 − ratio`) | "you're paying X% for the actual business" |
| Market cap | size = liquidity/safety proxy; tag `⚠ micro` under ~US$50M |
| Operating cash flow (TTM) | is the business actually generating cash |
| Free cash flow (TTM) + FCF yield on EV | cash return on the stub you're paying for |
| Net cash ($) | absolute cushion |
| Revenue growth (YoY) | is the business shrinking into its cash pile |
| Sector / Industry / Country | context; flags ADRs, cyclicals, etc. |
| Last-filing / data date | staleness |
| One-line plain-English read | e.g. "US$120M cash, US$140M mcap, US$30M FCF — paying ~US$20M for a cash-generative business" |

Do **not** silently drop micro-caps or borderline names — tag them (`⚠ micro`,
`⚠ negative revenue growth`, `REVIEW: defense`) and keep them in, per Shaun's "I
can run a deep dive on anything I like the look of."

## Open questions for `/plan-feature`

1. **"Good cash flow" — exact definition.** OCF-positive only, or OCF + FCF both
   positive? TTM (`.info`) or latest annual (`fetch_cash_flow_statement`)? Any
   minimum FCF margin / FCF yield floor, or just "> 0"? (Recommendation: OCF > 0
   AND FCF > 0, TTM with annual fallback, no margin floor in v1.)
2. **Liquidity / size floor.** Finviz coarse filter already imposes avg vol > 100K
   and price > $1. Add a hard market-cap floor (drop, not just tag) below some
   level, or tag-only? (Recommendation: tag-only, hard-drop under ~US$10M.)
3. **Exclude financials & REITs?** (Recommendation: yes, exclude — net cash is not
   a meaningful concept for them. Confirm.)
4. **Currency.** Finviz universe is US-listed; ADRs report market cap in USD via
   yfinance so the ratio is currency-consistent. OK to keep v1 US-only and defer
   ASX (which would need FX on every figure)?
5. **`cash_ratio` threshold — exactly 80%, or a band?** Show 70–80% as a "near
   miss" section, or hard cutoff at 80%? (Recommendation: hard 80% for the main
   list, optional "75–80% watch" section below it.)
6. **Report cap.** If 40+ names qualify, show all, or top N with a count? (Ratio
   sort + the quality gate should keep it well under 40 in practice.)
7. **Scrape-failure behaviour** with no DB — keep and re-serve yesterday's report
   with a "STALE — Finviz fetch failed" banner, or write an explicit
   "scan failed" report? 
8. **Exact CLI name + report filename** — `cash-value-scan` /
   `cash-value-report.md` proposed; Shaun's name is "Cash 80% Trading Value".

## Explicitly deferred (do not build in v1)

- Candidate staging / promote-dismiss / watchlist integration — Shaun said "just
  list them."
- WhatsApp alerts / "new since last run" diffing — would need a DB snapshot table;
  not asked for.
- SEC XBRL `frames` universe — documented above as the v2 data source; v1 is Finviz.
- ASX / non-US listings and any FX handling.
- Any composite "score" — this is a filter + sort, not a scoring model, same
  advisor-notes philosophy as the rest of `investments/`.
- Long-term-marketable-securities adjustment to net cash.

## Validation (once built)

```powershell
uv run --directory investments/my-trader python -m pytest -q

# On-demand run — always via the VPS wrapper, never local (investments.db is
# VPS-only; this command doesn't touch the DB but the workspace still resolves
# `scripts.*` / shared config through it)
.\scripts\invoke_investments.ps1 -Package my-trader -Command "cash-value-scan"
```

Then confirm `investments/my-trader/cash-value-report.md` appears with a ranked
table, and spot-check 2–3 names by hand (pull up the 10-Q balance sheet, verify
cash − debt ≈ 80%+ of market cap).

## Sources consulted (2026-08-26)

- `finviz.com/screener.ashx?v=111&f=fa_pc_u3,geo_usa,sh_avgvol_o100,sh_price_o1` —
  live fetch: 492 matches / 25 pages, public (no login), columns as listed above,
  CSV export is Elite-only.
- `data.sec.gov/api/xbrl/frames/...` — returned HTTP 403 without a declared
  User-Agent (SEC requires one with contact info); structure not inspected this
  session.
- `mytrader/openinsider.py`, `goat/sp500_universe.py` — the screener-scrape
  pattern to mirror.
- `mytrader/market_data.py` — `fetch_ticker_data`, `fetch_cash_flow_statement`,
  `fetch_balance_sheet_financials`.
- `mytrader/engine.py:8,137` — `from scripts.ethical_filter import check_ticker`.
- `.claude/scripts/run_vault_sync.sh:21` — `investments/my-trader/*.md` is synced.
