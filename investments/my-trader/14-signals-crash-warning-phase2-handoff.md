# Handoff: 14-Signal Crash Warning Framework — Phase 2 (Markers #2, #4, #9, #12)

## Status: Draft for discussion (2026-08-18). Nothing added to `tool-preplan.md` or
`investment-strategy.md` yet, per `analyse-transcript.md` convention — standalone
working file until Shaun says what to keep.

**Scope**: the four markers the Phase 1 plan
(`.agent/plans/fourteen-crash-signals-phase1-core-signals.md`, "NOTES — How to create
Phase 2 / Phase 3") named as the next slice — the ones with an already-identified free
data source, needing codebase-pattern work rather than open-ended source-hunting:

| # | Marker | Phase 1 handoff's fact-check verdict (still current, not re-litigated here) |
|---|--------|-------------------------------------------------------------------------------|
| 2 | Debt moves off balance sheet | **Mostly confirmed** — Moody's $1.2T off-balance-sheet AI lease commitments (Jul 2026), Microsoft $329.1B uncommenced leases (Jun 30 2026) |
| 4 | Capex outruns cash flow | **Confirmed, cleanly** — Allianz Research ~46% AI capex/revenue growth gap; Oracle $55.7B FY26 capex vs. -$23.7B FCF |
| 9 | The Super Bowl signal | **Confirmed** — Feb 8 2026 Super Bowl: 15/66 ads (23%) AI-related |
| 12 | Credit turns in the hot sector while broad market stays calm | **Confirmed** — Oracle CDS 145→199-215bps, record high, above 2008 peak |

The historical/current-numbers fact-check for all four is done (see the table above and
`14-signals-crash-warning-handoff.md`'s full per-marker rows). **This document's job is
different**: it fact-checks *build feasibility* — is there a real, reachable, scriptable
data source for each, what's the access friction, and what codebase pattern reuses
cleanly — since that's what Phase 1's own scope decision deferred to this phase.

## What Phase 1 already built, that this phase reads from

Confirmed by reading the actual shipped code (not the plan doc's proposed code — Phase 1
made one on-the-fly change: `SIGNALS_HOT_WATCHLIST_TOP_N` is **10**, not 8, per Shaun's
correction during build: "top 10 most active players in the industry").

- `fourteen_crash_signals_daily_check/config.py` — thresholds live here, one block per
  marker with a "why this number" comment. Phase 2 adds its own blocks in the same style.
- `fourteen_crash_signals_daily_check/db.py` — `signals_hot_watchlist` (ticker, sector,
  market cap, rank, computed_at — delete-all-then-insert-all every run) and
  `signals_alert_state` (marker_key → is_firing, upsert-with-transition-detection via
  `upsert_signal_state`, returns `True` only on a False/absent → True flip). Phase 2's
  four markers plug straight into both — no new tables needed for the watchlist or
  alert-state layers.
- `fourteen_crash_signals_daily_check/watchlist.py` —
  `get_or_refresh_hot_watchlist(conn)` returns the current top-10 mega-cap names from
  currently-rising GICS sectors, recomputed fresh every run (no TTL, by design). This is
  the shared input markers #2, #4, #12 all read from (per-issuer checks); #9 doesn't need
  it (broad-market, not issuer-specific).
- `fourteen_crash_signals_daily_check/report.py` — markers #2, #4, #9, #12 currently
  render as `_NOT_YET_AUTOMATED` placeholder rows. This phase replaces those four rows
  with real `CheckResult`-shaped output, same as markers 5/8/10/14 already do.

---

## Marker #2 — Off-balance-sheet lease commitments

**Data source, confirmed live 2026-08-18**: this is a **narrative footnote disclosure**,
not a cleanly-tagged single XBRL field. Companies disclose "leases that have not yet
commenced" dollar figures in the Leases note of their 10-Q/10-K (ASC 842-20-50-3 requires
it when the uncommenced lease creates a significant right/obligation). There is an XBRL
element in the space (`UnrecordedUnconditionalPurchaseObligationBalanceSheetAmount`), but
it's for unconditional purchase obligations broadly, not a lease-specific tag applied
consistently across issuers — **not safe to treat as a universal structured pull**. The
figures the video/fact-check cite (Microsoft's $329.1B, Moody's $1.2T aggregate) come from
narrative MD&A/footnote text and third-party aggregation (Moody's own report), not a
single clean government API field.

**Reusable codebase pattern, already built**: `investments/my-trader/mytrader/
sec_filings.py` — `_get_cik` (ticker → CIK, cached, weekly-refresh watermark),
`_fetch_filing_index` + `_latest_filing_entry` (find the latest 10-Q/10-K), `_extract_
10q_sections`/`_extract_10k_sections` (HTML → per-Item text), and
`get_filing_summaries_for_ticker` (the whole pipeline, LLM-summarized via `sdk_compat`).
This already does everything except isolate the *Leases* note specifically and pull a
dollar figure out of it — `_split_by_item`/`_split_by_part` split by Item/Part headers,
not by footnote name, so a lease-note-specific split needs a new sub-extraction (regex on
"leases... not yet commenced" or similar, scoped to the Notes to Financial Statements
section) — a new function in this style, not a new fetch pipeline.

**Open build decision**: extract a dollar figure automatically (regex over the isolated
lease-note text, e.g. `\$[\d,.]+ (?:billion|million)` near "not yet commenced"), or reuse
`get_filing_summaries_for_ticker`'s existing LLM-summarization path and have the LLM
pull the number out in prose form (less brittle to phrasing variance across issuers, but
non-deterministic and costs an LLM call per hot-watchlist ticker per run). **Recommend
the LLM-summarization reuse** — it's already built, already async via `sdk_compat`
(model-agnostic per this project's architecture rule), and this marker only needs to run
against ~10 tickers, not hundreds. A regex approach would need per-issuer tuning as
phrasing varies ("have not yet commenced," "not yet commenced," "leases signed but not
yet begun") — fragile in exactly the way `sec_filings.py`'s own module docstring already
warns about for other sections.

**Firing condition, undecided**: the handoff never specified a numeric threshold for this
marker (unlike #5's YoY% or #14's streak-days) — it's presented as "this exists and is
growing fast," not "flag above X." Proposed for Shaun's sign-off: flag when a
hot-watchlist ticker's uncommenced-lease figure has grown ≥50% since the last filing seen
for that ticker (a *quarter-over-quarter growth* trigger, mirroring #5's YoY-growth
framing at the next filing frequency down) — requires storing the last-seen figure
per-ticker (a new small table, `signals_lease_commitment_history` or similar, following
`sec_filing_cache`'s own "invalidate on new accession_number" pattern already built in
`sec_filings.py`).

---

## Marker #4 — Capex outruns cash flow

**Data source, confirmed feasible**: yfinance's cash flow statement, via
`yf.Ticker(ticker).cashflow` (or `.cash_flow`) — **not currently wrapped anywhere in this
codebase**. `mytrader/market_data.py`'s `TickerData`/`fetch_ticker_data` only carries
`info`, `dividends`, `news`, `calendar` — no cash flow statement. This is a genuinely new
fetch, following `fetch_ticker_data`'s existing shape (try/except around the yfinance
call, `.AX` fallback, cache-aware if called inside `cached_session()`).

**GOTCHA, flagged for live verification during build**: yfinance's cash-flow field naming
has drifted across library versions — older code/docs reference `capitalExpenditures`
and `totalCashFromOperatingActivities` as `.info`-style dict keys; current yfinance
versions expose `.cashflow` as a `pandas.DataFrame` with row-index labels like `"Capital
Expenditure"` and `"Operating Cash Flow"` (title-case, space-separated) rather than
camelCase dict keys. **Confirm the exact installed yfinance version's actual row labels
live** (`python -c "import yfinance; print(yfinance.Ticker('ORCL').cashflow.index.tolist())"`)
before writing this fetch — do not trust either naming convention from web research
without checking the version actually pinned in this workspace's `uv.lock`.

**Formula, needs a decision**: the video/Allianz Research framing is a **capex growth
rate minus revenue growth rate gap** (~46pp), not a raw capex/revenue ratio — this needs
two data points per ticker per period (capex this year vs. last year, revenue this year
vs. last year), computed from the same cash-flow/income-statement pull. Proposed:
`CheckResult` per hot-watchlist ticker, flag when `capex_yoy_growth_pct -
revenue_yoy_growth_pct >= SIGNALS_CAPEX_CASHFLOW_GAP_FLAG_PCT` (v1/tunable, propose
32.0 — the video's own 2001-telecom baseline comparator, i.e. flag at least as extreme as
the historical dot-com-era divergence it's benchmarked against). Revenue growth needs the
income statement (`yf.Ticker(ticker).financials` or `.income_stmt`), a second new fetch
alongside the cash-flow one — same GOTCHA about confirming exact row labels live applies.

**Simpler fallback, worth considering**: Oracle's own figure in the fact-check ($55.7B
capex vs. -$23.7B free cash flow) is a **capex vs. FCF sign/magnitude check**, not a YoY
growth-gap — free cash flow itself (operating cash flow minus capex) going negative while
capex is large and rising is a much simpler, more robust single-period signal than a
two-period growth-gap calculation, and doesn't require the income-statement fetch at all.
**Recommend picking one of these two formulas explicitly before `/plan-feature`** — they
measure related but different things (a growth-gap flags *acceleration*, a negative-FCF
check flags *current unsustainability*), and the plan should implement one deliberately,
not both by default.

---

## Marker #9 — The Super Bowl signal

**Confirmed**: Super Bowl LXI is **February 14, 2027**, at SoFi Stadium (per NFL schedule
sources, confirmed 2026-08-18).

**Honest feasibility read, correcting the Phase 1 plan's optimism**: Phase 1's own
feasibility notes said this "costs nothing to daily-check for 'did a new one just air'" —
true for *the date*, but the marker's actual content (what % of Super Bowl ads were
AI-related) has **no structured free data source** to daily-poll. The 23% figure for the
2026 game came from post-game trade-press coverage (Adweek), not a queryable API or feed
— there's no dataset anywhere that publishes "ad category breakdown" on a schedule. A
scheduled Python script (this tool's systemd timer, not an interactive agent) has no web
search capability at runtime — it can't do what a research pass like this one just did.

**Realistic v1 scope for this marker**: not true automation of the *content* check —
propose a **date-proximity reminder check** instead: `verdict="unknown"` year-round with
`detail` counting down to the next Super Bowl date (a small hardcoded/updatable date
constant, `SIGNALS_NEXT_SUPER_BOWL_DATE`, manually bumped once a year — this is the one
marker in the whole 14 where a static, human-maintained constant is honestly the right
shape, not a workaround to fix later), then on/after that date, flip to a **standing
"check ad-share manually" flag** in the report (`verdict="flag"`, detail pointing Shaun to
check that year's post-game trade coverage himself) until Shaun manually records a value
and resets it. This keeps the marker honest in the report (never silently "ok" when
nothing was actually checked) rather than pretending an unbuilt content-classification
pipeline exists. Flag this explicitly for Shaun's sign-off — it's a real scope-down from
what Phase 1's own table implied.

---

## Marker #12 — Credit spread in the hot sector (bond-yield-vs-Treasury proxy)

**Phase 1's assumption re-checked, and it needs correction.** The Phase 1 handoff stated
"FINRA runs its own free TRACE API (developer.finra.org)... individual-CUSIP transaction
data" as a settled "concrete free source found." Live research this session found that's
**half right**:

- **Free access for personal, non-commercial use is real** — FINRA explicitly offers
  free real-time and delayed TRACE bond data to individuals, no fee, via a click-through
  Fixed Income User Agreement (not a paid tier).
- **But the *programmatic* `developer.finra.org` API** (the "Revised TRACE Corporate and
  Agencies API") is documented as requiring firms to hold a Vendor or FINRA Transparency
  Services Participation Agreement, **plus a CUSIP Daily License from S&P** to resolve
  CUSIP numbers through that specific API surface — that's institutional-access
  friction, not a drop-in `requests.get()` the way `abs_cpi.py`/FRED-via-`macro.py` are.
- **The actual free, no-agreement-beyond-clickthrough surface is the public lookup UI**
  — FINRA's Fixed Income Data Center (`finra.org/finra-data/fixed-income/bond`) and its
  Morningstar-hosted Bond Center (`finra-markets.morningstar.com/BondCenter`) — a bond
  lookup by CUSIP or issuer name/ticker returning price, yield, and trade history. This
  is scrapeable in principle (same "read a public page, parse what's there, degrade to
  `None` on failure" philosophy as every other scraper in this codebase — `sp500_
  universe.py` scrapes Wikipedia, `openinsider.py` scrapes OpenInsider), but **it was not
  live-tested this session** (no page fetch performed) — confirm during `/plan-feature`
  or Task-1 of the eventual plan whether it's a static-HTML table (parseable) or a
  JS-rendered widget (would need a headless browser, a meaningfully bigger dependency
  than anything else in this workspace) before committing to this as the fetch mechanism.

**Second open gap, more fundamental than the access-friction one**: **there is no
automated ticker → bond CUSIP mapping anywhere in this codebase or an identified free
source.** Oracle's specific bond used in the fact-check wasn't picked programmatically —
it was named in trade press. The Fixed Income Data Center's issuer-name search (if it
works as documented) might solve this by returning a list of an issuer's outstanding
CUSIPs to pick from (e.g. take the most-recently-traded or a fixed target-maturity bond),
but this needs to be verified live, not assumed. **If issuer-name search doesn't pan out,
propose a v1 fallback**: Shaun manually maintains a small `SIGNALS_CREDIT_SPREAD_ISSUER_
CUSIPS: dict[str, str]` mapping in `config.py` (ticker → one benchmark bond CUSIP),
refreshed by hand whenever the hot-watchlist's composition changes meaningfully — same
"static constant is honestly the right v1 shape" reasoning as marker #9's date constant,
not a workaround. Flag both options for Shaun's decision before `/plan-feature`.

**Formula, once a CUSIP and its yield are in hand**: bond yield minus a maturity-matched
Treasury constant-maturity yield (free, FRED `DGS10`/`DGS5`/etc. depending on the bond's
remaining maturity — already the exact `fred_series_range`/`fred_observation_on` helpers
`credit_spread.py` already imports from `briefs-finance/scripts/macro.py`, no new FRED
code needed for this half of the calculation). Threshold: **undecided** — the Phase 1
handoff's own text notes Oracle's real move was 145→199-215bps (+~54-70bps), described
across sources as "record, above 2008 peak" — propose flagging on a relative move
(current spread ≥1.3× the 90-day-prior reading for the same CUSIP, a *divergence* trigger
matching this marker's actual thesis) rather than an absolute bps threshold, since a
different bellwether issuer next cycle will have a different baseline spread level
entirely. v1/tunable, flag for Shaun's sign-off same as every other numeric threshold in
this framework.

---

## Cross-cutting notes for whoever writes the Phase 2 plan

- **All four markers are per-issuer or broad-market checks that read the existing
  `signals_hot_watchlist` table** (markers #2, #4, #12) or need no watchlist at all
  (#9) — none of them need a new detection layer, only new fetch/parse modules plus
  `report.py`/`main.py` wiring, following the exact shape markers 5/8/10/14 already
  establish (`CheckResult(verdict="ok"|"flag"|"unknown", detail=..., data={...})`, never
  raise, degrade to `"unknown"` on any fetch failure).
- **Two of the four (#9, #12) are honestly *not* fully automatable to the standard the
  other 10 markers hit** — #9 becomes a maintained-date reminder + manual-check flag,
  #12 has a real open question about CUSIP-mapping that may end in a manually-maintained
  config dict. This isn't a reason to drop them (the handoff's own "none of the 14 are
  written off as manual-only" principle still holds — a manual-assist flag beats no
  marker at all), but the eventual plan should not overstate them as clean automation the
  way markers 5/8/10/14 are.
- **#2 and #4 both need new financial-statement fetch code** that doesn't exist yet in
  `mytrader/market_data.py` — SEC EDGAR filing-note extraction (reusing `sec_filings.py`)
  for #2, yfinance cash-flow/income-statement DataFrames for #4. Both need a live
  version-check of the exact field/row names before writing extraction code — flagged
  explicitly in each section above, don't trust the web-research field names verbatim.
- **New DB needs**: #2 needs a small per-ticker "last-seen lease commitment figure" table
  (for its quarter-over-quarter growth trigger) if that firing condition is accepted;
  #12 needs a small per-CUSIP "last-seen spread" table for its divergence trigger. Both
  follow `signals_alert_state`'s existing upsert-with-transition-detection shape — no new
  pattern to invent, just two more tables in this package's `db.py`.
- **Config constants to add** (mirroring the existing per-marker block style in
  `config.py`): `SIGNALS_LEASE_COMMITMENT_GROWTH_FLAG_PCT` (proposed 50.0),
  `SIGNALS_CAPEX_CASHFLOW_GAP_FLAG_PCT` (proposed 32.0, *or* switch to a negative-FCF
  check instead — see Marker #4's open decision), `SIGNALS_NEXT_SUPER_BOWL_DATE`
  (`2027-02-14`, human-maintained), `SIGNALS_CREDIT_SPREAD_DIVERGENCE_FLAG_RATIO`
  (proposed 1.3) and either `SIGNALS_CREDIT_SPREAD_ISSUER_CUSIPS` (manual fallback dict)
  or a resolved issuer-search mechanism.

## ROUND 2 — Resolved decisions (2026-08-18, after live verification with Shaun)

All four open questions below are now resolved (Shaun's sign-off, several backed by
live checks run this session — real yfinance data pulled, real EDGAR/FINRA reachability
tested). One new scope item was added mid-discussion (Marker #14 enhancement). This
doc is now considered ready for `/plan-feature` — Shaun will run that himself in a new
session, per this project's "writing a handoff is fine to do proactively, invoking
`/plan-feature` itself is always Shaun's call" convention.

### Marker #2 — resolved

- **Extraction method**: reuse the existing LLM-summarization approach (Shaun confirmed) —
  not a regex extractor.
- **Firing threshold**: 50% QoQ growth, kept explicitly as v1/tunable. Flagged directly to
  Shaun and accepted: this is an unbacktestable number (no historical time series exists
  for "uncommenced lease commitments" disclosures the way FRED/FINRA series do for other
  markers), and the underlying dollar figures are naturally lumpy quarter to quarter (one
  new mega-data-center lease can single-handedly swing a quarter). The report must always
  show the raw dollar figure + % change in its detail string regardless of whether it
  fires, specifically so Shaun can eyeball real output over a few quarters and retune.
- **Build note (found this session, changes scope slightly)**: `get_filing_summaries_for_ticker`'s
  existing section extraction (`_extract_10k_sections`/`_extract_10q_sections` in
  `investments/my-trader/mytrader/sec_filings.py`) does **not** currently capture Item 8
  (10-K, "Financial Statements and Supplementary Data") or Part I Item 1 (10-Q, "Financial
  Statements") — it only keeps Business/Risk Factors/MD&A. The Leases footnote lives inside
  the financial-statements section, not MD&A, so both extractors need one new line each
  (`sections["financial_statements"] = items["8"]` / `part1_items["1"]`).
- **Also found**: `_get_cik`, `_fetch_filing_index`, `_fetch_filing_document`, `_strip_html`
  in `sec_filings.py` are currently private (leading underscore). Both this marker's new
  code AND Marker #12's new code below need to import and reuse them directly from outside
  `sec_filings.py` — the plan should rename them public (drop the underscore, update
  `sec_filings.py`'s own internal call sites to match) rather than reach into
  underscore-prefixed names across a package boundary.
- **New extraction step needed**: within the isolated Financial Statements text, find the
  Leases note specifically via a heading-substring search — mirror
  `_find_def14a_heading_index`'s "last ALL-CAPS occurrence, trailing ~8000-char window"
  heuristic (footnotes don't have Item-style headers the way `_split_by_item` relies on).
  Feed that window to a **new** summarization prompt, distinct from `_summarize_sections`'s
  free-prose one — this one needs a strictly parseable response: "Return ONLY a single
  number in USD (no symbols/commas) for the total dollar amount of leases that have not yet
  commenced. If not disclosed, return exactly NONE."
- **New DB table needed**: `signals_lease_commitment_history` (ticker, accession_number,
  figure, filing_date, checked_at) — invalidate-on-new-accession-number, same pattern as
  `sec_filing_cache`. First observation for a ticker stores a baseline only, never flags
  (nothing to compare growth against yet).
- Check must compare the latest of **either** 10-K or 10-Q (whichever posted most recently
  by filing date) — an annual 10-K can update this figure too, not just quarterlies.

### Marker #4 — resolved, verified live against real data

- **Design**: (b), the simpler negative free-cash-flow check.
- **Confirmed live** (2026-08-18, `uv run` against real yfinance data for ORCL):
  `yf.Ticker('ORCL').cashflow` already exposes a precomputed `"Free Cash Flow"` row
  (`-$23.686B`, matching the fact-check's `-$23.7B` almost exactly) alongside
  `"Capital Expenditure"` (`-$55.663B`, stored as a **negative** outflow, matching `$55.7B`
  in magnitude) and `"Operating Cash Flow"` (`$31.977B`) — confirms
  `Free Cash Flow = Operating Cash Flow + Capital Expenditure` (capex already negative, so
  this is addition not subtraction). **No separate income-statement fetch is needed at all**
  for this design — one fetch, already-computed FCF.
- Both `.cashflow` (annual, 5 periods) and `.quarterly_cashflow` (quarterly, 7 periods for
  ORCL) exist on the yfinance `Ticker` object.
- **Decision: use the latest ANNUAL period**, not quarterly/TTM — matches what the
  fact-check's own cited Oracle numbers actually are (FY26 annual), keeps the check a true
  single-period comparison as intended, avoids quarterly noise. A daily job just re-reads
  "no change" until a new annual 10-K posts a new figure — consistent with this whole
  framework's "daily job that mostly reports unchanged, catches a new filing whichever day
  it lands" philosophy.
- **Firing condition**: `verdict="flag"` when latest-annual Free Cash Flow < 0 AND
  latest-annual |Capital Expenditure| >= `SIGNALS_CAPEX_MIN_FLAG_ABS` (propose $10B — a
  cheap sanity floor; every hot-watchlist ticker is already mega-cap-filtered by
  `watchlist.py`, so this floor should never actually bind in practice, it's just insurance
  against a data glitch producing a spurious flag).
- **New fetch function needed** in `investments/my-trader/mytrader/market_data.py`:
  `fetch_cash_flow_statement(ticker) -> dict[str, float] | None` returning
  `{"free_cash_flow", "capital_expenditure", "operating_cash_flow", "period_end"}` from the
  latest annual column — mirror `fetch_balance_sheet_financials`'s exact
  try/except/return-None shape (same file).

### Marker #9 — resolved

- Confirmed: date-reminder + manual-check-flag shape, exactly as proposed.
- **No new DB table needed** — the config constant itself is the reset mechanism:
  `SIGNALS_NEXT_SUPER_BOWL_DATE = date(2027, 2, 14)`. While `today < that date`:
  `verdict="unknown"`, detail counts down. From that date onward: `verdict="flag"`, detail
  points Shaun to check that year's post-game trade coverage (Adweek etc.) and then manually
  bump `SIGNALS_NEXT_SUPER_BOWL_DATE` forward to next year's game once he's recorded a value
  — the flag clears itself the moment the constant is bumped forward, no separate
  acknowledgment table needed.

### Marker #12 — CUSIP discovery is now solved; the yield lookup itself is honestly not

Two separate sub-problems, resolved differently — this is the one marker where the answer
is genuinely mixed, not a clean yes/no:

1. **Ticker → bond CUSIP (discovery): now has a real automated path**, found and verified
   this session. Corporate bond prospectus filings (SEC form types `424B2`, `424B5`, `FWP`)
   state "CUSIP No. XXXXXXXXX" on the cover page as a matter of regulatory practice.
   `sec_filings.py`'s existing CIK-lookup + filing-index + document-fetch plumbing
   (`_get_cik`/`_fetch_filing_index`/`_fetch_filing_document`, already reachable with the
   required `SEC_USER_AGENT` header — confirmed this session that a plain WebFetch without
   that header gets 403'd by SEC, which is exactly why this codebase's own header-carrying
   `requests` calls are needed, not a sign EDGAR itself is unreachable) can be reused as-is
   (once made public per Marker #2's note above) — find the most recent filing of whichever
   of those 3 form types is present in the issuer's filing index, fetch it, regex the CUSIP
   off the cover-page text (`CUSIP\s*(?:No\.?|Number)?[:\s]*([A-Z0-9]{9})`, case-insensitive).
   New small cache table needed, `signals_bond_cusip_cache` (ticker, cusip, accession_number,
   resolved_at), mirroring `sec_cik_map`'s pattern.
   **Real caveat**: some issuers (especially newer/private-credit-heavy names like
   Coreweave) place bonds privately under Rule 144A rather than registering them publicly —
   those tickers will have no 424B/FWP filing on EDGAR at all, and this mechanism correctly
   degrades to "no public bond found" for them (an honest gap, not a bug). The manual
   `SIGNALS_CREDIT_SPREAD_ISSUER_CUSIPS_FALLBACK: dict[str, str]` dict is the fallback
   **only** for this case, not the primary mechanism anymore.
2. **CUSIP → current yield/price: still genuinely unresolved.** Live-checked this session:
   FINRA's own Fixed Income Security Lookup (`finra.org/finra-data/fixed-income/bond`)
   requires accepting a Fixed Income User Agreement before any search works, is
   JS-rendered (no data present in a plain fetch), and only accepts CUSIP/TRACE-symbol
   input — no issuer-name search, and not scrapeable via a plain `requests.get()` the way
   every other source in this codebase is. The Morningstar-hosted Bond Center mirror is
   similarly a JS shell with no static data. A round of web research into third-party free
   bond-data sites turned up candidates claiming free no-login bond lookup by CUSIP —
   Atlantis Data Solutions, Terrapin Finance, Empirasign, Cbonds — but **none were confirmed
   working this session** (Empirasign returned an outright 403 on a plain fetch, likely
   bot-protection rather than a hard dead end, but genuinely unverified either way).
   **Recommendation for `/plan-feature`**: make Task 1 of the `credit_spread_issuer.py`
   work a live verification spike — once the EDGAR CUSIP-discovery mechanism above is built
   and produces a real CUSIP to test with, try each of the 4 candidate sites against that
   real CUSIP (proper request headers, check for a JSON/AJAX endpoint behind the page, not
   just the top-level URL) before committing to one.
   **Realistic fallback if none pan out**: Shaun manually checks a yield reading
   periodically (e.g. via his own brokerage's bond lookup, which he may already have login
   access to) and enters it into a small state table — the tool still automates everything
   else around that one manually-entered number (CUSIP discovery, the Treasury-yield
   subtraction, the 90-day/1.3x divergence computation, the report/alert wiring). A
   semi-automated marker, not a failure — genuinely better than the fully-manual
   CUSIP-dict-only version originally proposed, even if the yield step itself resists
   scraping.
- **Divergence trigger confirmed**: flag when the current spread (bond yield minus a
  maturity-matched Treasury yield) is >=1.3x the reading from 90 days ago. Maturity-matched
  Treasury yield already has a home — `FRED_2Y_TREASURY_SERIES`/`FRED_10Y_TREASURY_SERIES`
  already exist in `investments/my-trader/mytrader/config.py` (no new FRED series needed).
  New small table needed for the "90 days ago" comparison point,
  `signals_issuer_spread_history` (ticker, spread_value, observed_at), mirroring
  `signals_alert_state`'s upsert shape.

### NEW scope item — Marker #14 enhancement (added 2026-08-18, not in the original Phase 2 scope)

Raised by Shaun mid-discussion while resolving Marker #12's threshold — a real, separate
piece of work against the **already-shipped** `credit_spread.py` (Phase 1), distinct from
markers #2/#4/#9/#12 above, but natural to ship in the same Phase 2 build since it touches
the same file:

- **"Watch" tier**: add a state for when the spread is within 0.3pp of the 3.5pp flag
  threshold (i.e. >=3.2%) but hasn't crossed it yet — today the check is strictly binary
  ok/flag. Needs a decision during `/plan-feature`: a literal third `CheckResult.verdict`
  value (e.g. `"watch"`, alongside the existing `"ok"|"flag"|"unknown"` contract documented
  in `mytrader/checks/__init__.py`), or keep `verdict="ok"` and add a `data={"watch": True}`
  flag instead. **Recommend the latter** — `verdict` staying within the existing 4-value
  contract avoids breaking any other consumer that might iterate/branch on verdict values —
  but flag this for explicit confirmation during planning, not a silent choice.
- **Daily alert while the streak continues**: today `alerts.py`'s `maybe_notify` is
  transition-only (fires once, only on a False→True flip via `db.upsert_signal_state`).
  Shaun wants different behavior for this one marker specifically: once `streak_days >= 1`
  at/above 3.5%, WhatsApp-ping **every single day** the streak continues (not just once),
  each message reading "day N and counting" — a deliberate, explicit exception to the rest
  of the framework's "alert only on new firings, never a daily dump" rule, scoped to this
  one marker only, on Shaun's own request ("to remind me and keep it on my mind"). Needs
  either a marker-specific override path inside `alerts.py`'s `maybe_notify`, or a separate
  small alert call from `main.py` just for this marker that bypasses the generic
  transition-only path the other markers use — decide the cleaner shape during
  `/plan-feature`.

## Status: ready for `/plan-feature`

All four original open questions (markers #2, #4, #9, #12) are resolved, plus one new scope
item (Marker #14's watch-tier + daily-streak-alert enhancement). Marker #12 carries one
real, still-open sub-problem (bond-yield lookup) that the plan should treat as a Task-1 live
verification spike with a documented manual-entry fallback, not a blocker to starting the
plan. Per this project's convention, running `/plan-feature` against this file is Shaun's
call — not run automatically here.
