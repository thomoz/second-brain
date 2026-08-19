# Handoff: 14-Signal Crash Warning Framework — Phase 3 (Markers #1, #3, #6, #7, #11, #13)

## Status: Draft for discussion (2026-08-18). Nothing added to `tool-preplan.md` or
`investment-strategy.md` yet, per `analyse-transcript.md` convention — standalone
working file until Shaun says what to keep.

**Scope**: the six markers Phase 1's own scoping deferred because none had a confirmed
free/structured data source: #1 (record debt issuance), #3 (seller finances buyer),
#6 (record IPO/equity issuance), #7 (retail piles into leverage), #11 (regulators sound
the alarm), #13 (funding markets start choking). Phase 1's own framing (`fourteen-crash-
signals-phase1-core-signals.md`, NOTES section) called this slice "genuinely needs
source-hunting during planning itself" — that's what this document is. Every candidate
source below was live-tested this session (real HTTP requests against real endpoints),
not taken on documentation's word.

**What Phase 1/2 already built, that this phase reads from**: same shared layers as
Phase 2 — `signals_hot_watchlist` (top-10 mega-cap names from currently-rising GICS
sectors, no TTL, recomputed every run) and `signals_alert_state` (transition-detection
upsert). Also directly relevant: `config.py` already declares
`SIGNALS_BOND_PROSPECTUS_FORM_TYPES = ("424B2", "424B5", "FWP")` for Marker #12's CUSIP
discovery — Marker #1 below reuses the exact same form-type tuple for a different
purpose, not a coincidence, the same filing types that disclose a CUSIP also *are* the
debt-issuance events Marker #1 wants to count.

---

## Marker #1 — Record debt issuance in the hot sector

**Solid source, confirmed live.** SEC EDGAR's full-text search API
(`efts.sec.gov/LATEST/search-index`) is real, free, and returns structured JSON — no
API key, just a compliant `User-Agent` header (`SEC_USER_AGENT` already exists in
`mytrader/config.py`, reused as-is). Live-tested this session:

- `forms=424B2,424B5,FWP&ciks=0001341439` (Oracle) → **32 hits since 2020**, including a
  real `424B5` filed 2026-06-23 — confirms per-issuer debt-prospectus filings are
  reliably countable by CIK and form type.
- This is the *same three form types* (`424B2`/`424B5`/`FWP`) already named in
  `config.SIGNALS_BOND_PROSPECTUS_FORM_TYPES` for Marker #12 — one shared constant,
  two consumers.

**Design**: per-issuer, reads the hot watchlist (like #2/#4/#12). For each hot-watchlist
ticker, resolve CIK (reuse `sec_filings.get_cik`, made public in Phase 2), count
424B2/424B5/FWP filings in a trailing window (propose 180 days), compare against that
same issuer's own trailing-2-year average filing rate. Flag when trailing-window count
exceeds a multiple of the historical rate (v1/tunable, propose 2x — mirrors the
divergence-ratio framing already used for Marker #12).

**Honest limitation**: EDGAR full-text search returns filing *counts*, not aggregate
dollar principal — it cannot reproduce the video's literal "$570B global AI-debt
issuance" figure. It answers "is this issuer suddenly filing debt prospectuses faster
than its own history," which is a real, directionally-correct proxy for "record debt
issuance," not an exact dollar match to the fact-check's numbers. State this plainly in
the report detail string (same honesty standard as Marker #12's bond-yield proxy).

**Checked and rejected as primary**: SIFMA's US corporate bond statistics page
(`sifma.org/resources/research/statistics/us-corporate-bonds-statistics`) does offer a
free downloadable Excel with issuance volume — but the download link routes through a
HubSpot form (`share.hsforms.com`), an email-gate rather than a direct file URL. Not a
drop-in `requests.get()` the way FRED/EDGAR are elsewhere in this codebase. Worth a
one-time manual download to seed a historical baseline if Shaun wants real dollar
figures eventually, but not the automated primary source.

---

## Marker #3 — Seller finances buyer (vendor/circular financing)

**No free structured source found — confirmed by live-testing, not just assumed.**
Tried EDGAR full-text search for vendor-financing-shaped phrases (`"capacity purchase
agreement"` in 8-Ks) — returned 7 hits, dominated by an unrelated Alaska Air Group
airline capacity agreement, not tech vendor-financing deals. Phrase search over EDGAR's
full-text index is too generic and noisy to isolate this specific deal structure; the
real examples in the original fact-check (Nvidia's $30B OpenAI stake, the Nvidia+
Microsoft+Anthropic deal, Coreweave's unsold-capacity commitment) were all identified
from trade-press coverage of specific named deals, not a queryable dataset or filing
category — there is no XBRL tag, form type, or SIC-scoped search that captures "Company
A invests in Company B who then buys Company A's product" as a discrete, structured
fact.

**Verdict: same shape as Marker #9's Super Bowl fallback — a maintained flag, not a
numeric check.** Propose `verdict="unknown"` by default, with the report detail listing
the hot-watchlist tickers Shaun should periodically news-scan himself (reusing the same
watchlist every other per-issuer marker already computes — no extra targeting work).
No polling cadence makes this into real automation; there is nothing to poll. This is
the one marker of the six where "no source exists" is the honest, final answer, not a
placeholder for more research.

---

## Marker #6 — Record IPO/equity issuance

**Solid source, confirmed live, with a real caveat.** Same EDGAR full-text search API,
market-wide rather than per-issuer (hot-watchlist mega-caps aren't IPO candidates).
Live-tested:

- `forms=S-1&startdt=2026-08-01&enddt=2026-08-18` → **85 hits**
- `forms=S-1&startdt=2025-08-01&enddt=2025-08-18` (same calendar window, one year
  earlier) → **145 hits**

This confirms the count is a real, moving signal (not a static/broken query) — and
notably the 2026 window is *lower* than 2025's, a useful reminder this metric doesn't
move monotonically upward and a naive "always flag" implementation would misfire.

**Design**: track a rolling filing-count baseline built from EDGAR's own history (no
external baseline source needed — the API can be queried for past months directly,
letting `/plan-feature`'s build seed a trailing-24-month baseline in one pass rather
than waiting to accumulate one over time). Flag when a trailing window's count
significantly exceeds the rolling baseline (v1/tunable ratio, propose 1.5x, distinct
from Marker #1's 2x since S-1 filing volume is naturally noisier / less issuer-specific).

**Honest limitation**: S-1 is used by a long tail of small-cap and shell-company
registrants, not just headline IPOs the video is describing (SpaceX-scale listings) —
raw filing count is a pace/activity proxy, not a dollar-proceeds or "big-name IPO" proxy.
Consider also counting `424B4` (IPO final prospectus, i.e. *actually priced*, a stronger
filter than S-1's "intent to register") as a second, cleaner sub-signal — not tested
this session, worth a quick live check during `/plan-feature`.

---

## Marker #7 — Retail piles into leverage

**Weakest of the six — a real but imperfect proxy, not a clean source.** The fact-check's
own framing (record ETF inflows, semiconductor/leveraged-fund flows) has no free
structured feed:

- **ICI** (`ici.org/research/stats`) — 403 Forbidden on a plain fetch; the page that
  historically hosted free weekly fund-flow data appears to have moved or gated access.
  Not usable as tested.
- **yfinance shares-outstanding history** (checked as a "are people creating new ETF
  shares" proxy, reusing this codebase's existing yfinance infrastructure) —
  `Ticker('SOXL').get_shares_full()` and `.info['sharesOutstanding']` both returned
  `None` live. Doesn't work for this specific leveraged product; not verified across
  other tickers, but not a reliable general mechanism as found.
- **CBOE daily options market statistics**
  (`cboe.com/us/options/market_statistics/daily/`) — **real, live data confirmed**
  (fetched a live total put/call ratio of 0.92 plus equity/index/ETP breakdowns), but
  **HTML-only, no CSV/API** (confirmed by grepping the page for download links — none
  found). Scrapeable in principle, same "read a public page, parse what's there" pattern
  as `sp500_universe.py`'s Wikipedia scrape, but fragile to page-structure changes and
  needs a live spike (fetch + parse the actual HTML table shape) before committing.

**Recommendation**: build against CBOE's put/call ratio as the proxy — flag when the
equity put/call ratio drops meaningfully below its own trailing average (low put/call =
more speculative call-buying, a reasonable retail-leverage proxy, conceptually related
though not identical to the fact-check's ETF-inflow framing). State plainly in the
report that this is a *different* mechanism than what the source video measured (options
positioning, not fund flows), same honesty standard as Marker #12's bond-yield-vs-CDS
distinction. Flag for Shaun's explicit sign-off before committing — this is the one
marker where the honest source is meaningfully different in kind from what the original
fact-check described, not just a data-access workaround.

---

## Marker #11 — Regulators sound the alarm

**Solid, multi-source, confirmed live.**

- **SEC press releases RSS** (`sec.gov/news/pressreleases.rss`) — confirmed valid,
  parseable, current (fetched real items dated Aug 10–14, 2026).
- **Federal Reserve press releases RSS** (`federalreserve.gov/feeds/press_all.xml`) —
  confirmed valid, current (items dated Aug 4–13, 2026).
- **Federal Reserve speeches RSS** (`federalreserve.gov/feeds/speeches.xml`) — confirmed
  valid, current, and directly relevant in content (a real August 2026 item titled
  "Navigating Economic Shocks: A Monetary Policymaker's Perspective" surfaced on the
  first fetch) — governors' speeches are plausibly a *better* source for this marker
  than press releases, which are dominated by routine bank-merger-approval notices.
- **BIS** — real, but not cleanly confirmed this session. `bis.org`'s press-release
  section required following two redirects (`/press/index.htm` →
  `/list/press_releases/index.htm` → `/press/pressrels.htm?r`) before landing on what
  looks like a navigation template, not an actual release listing — the page does
  reference an `/rss/index.htm` link, but that wasn't independently fetched and
  confirmed working. Treat BIS as a secondary/best-effort source needing a dedicated
  spike during `/plan-feature`, not the primary mechanism.

**Design**: daily poll of the SEC + Fed press-release + Fed speeches feeds, keyword-scan
titles/descriptions against a trigger-phrase list (propose: "systemic risk," "financial
stability," "leverage," "asset valuations," "bubble," "AI," "shadow bank," "private
credit" — tunable, v1). `verdict="flag"` on any new item matching, `detail` naming the
matched item and source. **Real limitation to flag for Shaun**: RSS titles/descriptions
are often generic (e.g. "Federal Reserve Board announces approval of the application by
[Bank]") — many of the substantive systemic-risk statements this marker actually wants
(BIS Quarterly Review commentary, Financial Stability Report language) live in the *body*
of a linked report, not the feed's own text, so a title/description keyword-scan will
under-fire relative to what a human reading the full documents would catch. Fetching and
scanning full linked-report text is possible but a meaningfully bigger scope item than
the other markers in this phase — recommend shipping the RSS-title-scan as v1 and
treating full-document scanning as an explicit future enhancement, not part of this
phase's baseline.

---

## Marker #13 — Funding markets start choking

**Solid, confirmed live, zero new fetch code needed.** All candidates are FRED series,
fetched through the exact `fred_series_range` function `credit_spread.py` (Phase 1)
already imports — live-tested this session with the real `FRED_API_KEY` already
configured in this workspace:

- **`STLFSI4`** (St. Louis Fed Financial Stress Index) — confirmed live, weekly,
  e.g. `2026-08-07: -0.7709`. A broad financial-stress gauge (includes funding-market
  sub-components among others).
- **`NFCI`** (Chicago Fed National Financial Conditions Index) — confirmed live,
  weekly, e.g. `2026-08-07: -0.549`. Similar broad-conditions gauge, independent
  methodology from STLFSI4.
- **`DCPN3M`** (3-Month AA Nonfinancial Commercial Paper Rate) — confirmed live, daily,
  e.g. `2026-08-13: 3.77`.
- **`DTB3`** (3-Month Treasury Bill rate) — confirmed live, daily, e.g.
  `2026-08-14: 3.71`.

**Design recommendation**: compute `DCPN3M - DTB3` (commercial-paper-over-Treasury
spread) as the primary check — this is a direct, textbook funding-market-stress
indicator (widens when short-term lenders demand more premium to fund non-bank
borrowers, exactly the "funding markets choking" mechanism the video describes, e.g. the
2007 Bear Stearns fund episode), daily-updating, and more targeted than the two broad
stress indices. Use `STLFSI4`/`NFCI` as a secondary cross-check (both already fetchable
with the same function, cheap to include) — flag when either broad index crosses into
its own historically elevated range, corroborating rather than replacing the CP-Treasury
spread signal. Threshold: v1/tunable, propose flagging the CP-Treasury spread on a
z-score-vs-its-own-trailing-year basis (mirrors the divergence-ratio framing used
elsewhere in this framework) rather than a fixed absolute level, since "normal" for this
spread shifts with the broader rate environment.

---

## Cross-cutting notes for whoever writes the Phase 3 plan

- **Three markers (#1, #6, #13) are clean, confirmed-live, no-new-dependency builds** —
  #1 and #6 both reuse the EDGAR full-text search API (already proven reachable with the
  existing `SEC_USER_AGENT` header), #13 reuses `fred_series_range` verbatim with zero
  new fetch code, just new series IDs and a subtraction.
- **One marker (#11) is solid but scoped down from what a human reading regulator
  reports would catch** — RSS title/description keyword-scanning, not full-document
  analysis. Real, useful, but flagged so Shaun doesn't expect it to catch everything a
  manual read of a BIS Quarterly Review would.
- **One marker (#7) is a genuine proxy substitution, not the same mechanism as the
  source material** — CBOE put/call ratio instead of ETF/fund-flow data, because no free
  fund-flow source was reachable this session. Needs Shaun's explicit sign-off on using
  a different-but-related signal, not just a threshold number.
- **One marker (#3) has no automatable source at all** — same "maintained flag,
  Shaun checks manually" shape as Marker #9, not a data problem to be solved later, an
  honest structural gap in what's publicly queryable.
- **New DB needs**: #1 needs a small per-ticker filing-count-history table (mirrors
  `signals_bond_cusip_cache`'s shape, but storing counts not CUSIPs) for its own-history
  baseline; #6 needs a market-wide filing-count-history table (one row per period, not
  per-ticker) for its rolling baseline; #13 needs a spread-history table (mirrors
  `signals_issuer_spread_history`, but for the CP-Treasury spread, market-wide not
  per-issuer). #11 needs a small "seen item GUIDs" table so the same RSS item isn't
  re-flagged every day it stays in the feed (mirrors `signals_bond_cusip_cache`'s
  dedup-by-key shape). #3 and #7 need no new tables — #3 has nothing to store, #7's
  put/call ratio is a simple point-in-time value like #13's spread.
- **Config constants to add** (mirroring the existing per-marker block style):
  `SIGNALS_DEBT_ISSUANCE_LOOKBACK_DAYS` (proposed 180), `SIGNALS_DEBT_ISSUANCE_FLAG_RATIO`
  (proposed 2.0), `SIGNALS_IPO_FILING_LOOKBACK_DAYS`, `SIGNALS_IPO_FILING_FLAG_RATIO`
  (proposed 1.5), `SIGNALS_PUTCALL_FLAG_THRESHOLD` (needs a live data spike to set
  sensibly — not proposed here without seeing real trailing CBOE data first),
  `SIGNALS_REGULATOR_TRIGGER_PHRASES` (list), `SIGNALS_FUNDING_SPREAD_SERIES` (`DCPN3M`,
  `DTB3`), `SIGNALS_FUNDING_SPREAD_FLAG_ZSCORE` (v1/tunable, propose 2.0).

## Status: ready for `/plan-feature`

All six markers have a documented verdict: three clean/confirmed sources (#1, #6, #13),
one solid-but-scoped-down source (#11), one proxy substitution needing Shaun's sign-off
(#7), and one honest no-source/manual-flag verdict (#3) — same standard Phase 2 held
Marker #12's bond-yield lookup to. Nothing has been built. Per this project's convention,
running `/plan-feature` against this file is Shaun's call, not run automatically here.
