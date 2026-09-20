# ASX Director/Insider Dealing Scanner — Session Handoff

## Status: NOT BUILT — drafted 2026-09-19 from Shaun's question ("any insider buying or
selling for xero recently?"). Answer at the time was: no data, and not a gap in the
number — the existing `insider_selling` check (`mytrader/checks/insider_selling.py`)
and Goat's Holdings Watch (`goat/insider_scan.py`) both query OpenInsider only, which
scrapes **US SEC Form 4 filings exclusively**. Neither has ever had any ASX coverage;
"no filings found" for an ASX ticker today means "this tool was never watching", not
"nothing happened". Awaiting Shaun's manual `/plan-feature` run against this doc before
any implementation.

## What This Is

Extends the existing insider-tracking machinery to Australian-listed stocks and ETFs,
using ASX's own director/CEO interest-notice disclosures (Corporations Act s205G, ASX
Listing Rule 3.19A) as the Australian equivalent of a US Form 4. Two integration
points, both already live and both currently ASX-blind:

1. **Goat Holdings Watch** (`goat/insider_scan.py::run_holdings_watch`) — tracks P/S
   filings on every ticker in `mt_db.get_all_holdings`. That table already contains
   `.AX` tickers (e.g. Shaun's PMGOLD.AX, ETPMAG.AX) alongside US ones — the function
   just silently gets zero ASX rows back today since `openinsider.fetch_screener_filings`
   only ever queries OpenInsider.
2. **my-trader's `insider_selling` check** (`mytrader/checks/insider_selling.py`) —
   Find-only "look before you buy" read, same OpenInsider-only gap, same silent
   false-negative on an `.AX` ticker (confirmed live 2026-09-19 against XRO.AX: the
   check returned "ok, no filings" when real, genuine director dealings existed the
   same month — see below).

## Confirmed live 2026-09-19: the data exists, is free, and is structurally parseable

Checked real ASX Market Announcements Platform data for XRO (Xero) before writing this,
reusing the exact scrape mechanism `mytrader/asx_announcements.py` already has in
production (same list endpoint, same click-through interstitial, same PDF fetch):

- **The per-ticker announcement list already contains director/CEO dealing notices** —
  confirmed real titles present in XRO's 2026 list: `Change of CEO's Interest Notice`
  (×2), `Final Directors Interest Notice Anjali Joshi`. This is the exact same
  `by=asxCode&asxCode={code}&timeframe=Y&year={year}` endpoint
  `asx_announcements.py::_fetch_announcements_list` already calls for Annual/Half-Year
  Reports — no new fetch mechanism needed, just new title patterns to match (the same
  `ASX_ANNOUNCEMENT_TYPES`-style dict-of-patterns approach, extended).
- **The underlying PDF form is far more structurally parseable than the Annual
  Report sections `asx_announcements.py` already handles.** Fetched and read two real
  filings end-to-end (list → interstitial → PDF → text):
  - `Final Directors Interest Notice Anjali Joshi` (Appendix 3Z) — a departing
    director's final holdings snapshot, no transaction (this one is a "closing
    balance" notice, not a buy/sell — relevant for completeness but not itself a
    trade signal).
  - `Change of CEO's Interest Notice` (Xero's CEO-specific equivalent of Appendix 3Y)
    — a real transaction, cleanly labeled fields: `Date of change: 7 July 2026`,
    `No. of securities held prior to change: 29,608 Ordinary Shares`,
    `Number acquired: -`, `Number disposed: 29,608 shares`,
    `Value/Consideration: Sale for managing personal tax obligations: $2,190,992
    (29,608 at $74.00 per share)`, `No. of securities held after change: [RSUs/
    options only]`, `Nature of change: Sale of 29,608 shares on-market.`
  Unlike the Annual Report's free-form prose sections (the "biggest technical-risk
  area" called out in `asx_announcements.py`'s own docstring), this is a standardized
  ASX pro-forma with the same field labels across filers — a **label-based field
  extraction is realistic here** (regex or a lightweight structured-extraction LLM
  call), not the same class of heuristic risk as the heading-search problem.
- **Buy/sell direction and position-size context map directly onto the existing P/S
  row shape** `openinsider.py`/`insider_scan.py` already use: `Number acquired` (buy)
  vs `Number disposed` (sell) is OpenInsider's `trade_type_code` P/S distinction;
  `prior`/`after` security counts let a `pct_owned_change` be computed the same way
  OpenInsider's own ΔOwn column works today (`(after - prior) / prior * 100`) — no
  new concept, same field semantics, different source.

## Recommended architecture — extend the existing row shape, not a parallel pipeline

Mirrors the DMA Breakout ETF Universe handoff's own stated principle (one more branch
in the existing pipeline, not a second pipeline) and the `mlp_filter`/`asx_announcements`
precedent of degrading gracefully by ticker suffix:

1. **New module**, `mytrader/asx_director_notices.py` (sibling to `openinsider.py`,
   reusing `asx_announcements.py`'s fetch/interstitial/PDF-extract primitives rather
   than duplicating them) — returns rows in the **same dict shape** OpenInsider rows
   already have: `ticker`, `company_name`, `insider_name`, `title` (role — director vs
   CEO), `trade_type_code` (`"P"`/`"S"`), `value`, `trade_date`, `filing_date`,
   `pct_owned_change`. Matching this shape exactly means `insider_scan.py`'s existing
   per-row logic (dedup, `$`-value threshold gating, sale-repeat detection, detail-string
   building) needs **zero changes** — it already only cares about the dict shape, not
   the source.
2. **`run_holdings_watch`**: split `held_tickers` by `.AX` suffix (reuse
   `asx_announcements._is_asx_ticker`), fetch the US subset via the existing
   `openinsider.fetch_screener_filings` call, fetch the ASX subset via the new module,
   concatenate both row lists before the existing per-row loop. One new `kind` value
   on `goat_insider_filings_seen` (e.g. `"holdings_watch_asx"` or just reuse
   `"holdings_watch"` — same table, same dedup-by-`dedup_key` mechanic) — open question
   below.
3. **WhatsApp plumbing — this is the part Shaun explicitly asked for and it's already
   built**: `monitor.maybe_notify` (the "trade just found" ping) and
   `insider_scan.maybe_notify_price_flags` (the "price move just confirmed the signal"
   ping) both already render `company_name` and, for the confirmation ping,
   days-since-trade (shipped 2026-09-19, same session as this handoff — see
   `insider_scan.py`'s `new_alerts`/`new_candidates` dicts and
   `compute_holdings_watch_price_performance`). As long as the new ASX rows carry
   `company_name` (confirmed available — every notice's PDF header states
   `Name of entity`) and a real `trade_date`, **no changes are needed to either
   notification function** — an ASX director sale will show up in the exact same
   `TICKER (Company Name): ... (traded Nd ago, YYYY-MM-DD)` WhatsApp line a US one does
   today. This is the payoff of matching OpenInsider's row shape exactly in step 1.
4. **`insider_selling` check** (Find-only, `mytrader/checks/insider_selling.py`):
   same `.AX`-suffix branch, same new module, folded into its existing `rows`/`flagged`
   logic — no signature changes needed by its caller (`engine.run_assessment`).

## Open Questions (resolve during `/plan-feature`)

1. **Discovery/market-wide mode — a real free aggregator exists, but it's gated by
   Cloudflare, not a plain scrape.** ASX's own per-ticker announcement list
   (`asxCode={code}`) has no market-wide equivalent — checked
   `asx.com.au/markets/trade-our-cash-market/todays-announcements` live 2026-09-19: it
   exists but renders client-side, no API endpoint found in the static HTML/JS. But a
   third-party aggregator, **Market Index** (`marketindex.com.au/director-transactions`),
   publishes director transactions across every ASX-listed company in one place — the
   real ASX-wide equivalent of OpenInsider's screener, confirmed to exist via live
   search 2026-09-19 (Shaun's own follow-up question). However, a plain `requests` GET
   against it (same browser-like User-Agent that already works for `asx.com.au` itself)
   returned a Cloudflare "Just a moment..." bot-challenge page (HTTP 403), confirmed
   live the same session — unlike ASX's own Incapsula/Imperva WAF, which the existing
   `ASX_USER_AGENT` header alone already gets past. Getting through Cloudflare's
   challenge reliably generally needs real browser automation (Playwright/Selenium) or
   a paid scraping-proxy service — a genuinely new class of dependency, not present
   anywhere else in this codebase today. Recommend: **v1 ships Holdings Watch + Find-
   check only** (tickers Shaun already holds/watchlists, via the ASX per-ticker
   announcement list, no Cloudflare involved), same scope boundary Goat's own US
   Holdings Watch already has relative to Discovery. Revisit market-wide ASX discovery
   as a follow-up decision — specifically whether taking on browser automation (or a
   paid feed) is worth it — once v1's Holdings Watch value is proven out, Shaun's call
   given it's a real new dependency class, not a config tweak.
2. **ETF coverage is a real, confirmed structural gap, not an oversight.** Appendix
   3Y/3Z-style director/CEO interest notices exist because of Corporations Act s205G,
   which applies to a listed **company's** directors — an ASX-listed ETF is a trust
   with a responsible entity, not a company with directors, so this disclosure regime
   doesn't apply to it the same way. Shaun's own ETF holdings (PMGOLD.AX, GXLD.AX,
   ETPMAG.AX, URNM.AX, OOO.AX) would get zero rows from this feature, correctly, not
   as a bug. The closest ASX-listed proxy for "someone informed is moving" on a fund
   is a substantial-holder notice (`Change in substantial holding` / `Becoming a
   substantial holder` — confirmed present in XRO's own announcement list too), but
   that's a 5%+-ownership-change signal from any holder, not an "insider" signal in
   the director/officer sense this feature is otherwise built around — a different
   feature, not a variant of this one. Recommend: scope this handoff's "ETFs" word to
   **not building a false sense of coverage** — either explicitly document the gap in
   the report/WhatsApp output ("no insider-dealing regime applies to ETFs") or treat
   substantial-holder notices as an explicit separate future feature, Shaun's call.
3. **Field-extraction approach: regex-on-labels vs. LLM structured extraction.** The
   form's labels are consistent across filers (confirmed for two real XRO filings,
   Director and CEO variants) but this is only 2 data points from 1 company — worth
   testing against 4-5 more real filings from different filers during `/plan-feature`
   before committing to pure regex (cheaper, deterministic) over an LLM call (more
   robust to layout drift, consistent with how `asx_announcements.py`'s own prose
   sections are already handled, but adds a per-filing LLM cost the Annual Report path
   already accepts). The `Value/Consideration` field in particular is free-text within
   a labeled cell (e.g. "Sale for managing personal tax obligations: $2,190,992
   (29,608 at $74.00 per share)") — `insider_scan.py`'s own `_TRADE_VALUE_RE` `$`-regex
   already handles pulling a dollar figure out of prose like this, so reusing it here
   rather than a full LLM parse may be sufficient for the one field regex can't get
   directly from a clean label (`Number acquired`/`Number disposed` are clean enough
   to regex directly).
4. **Apostrophe/title matching robustness.** `Change of Director's Interest Notice`
   and `Change of CEO's Interest Notice` both contain a possessive apostrophe in the
   announcement title itself, not just inside the PDF body — `asx_announcements.py`'s
   existing `_APOSTROPHE_RE` normalization was built for in-PDF heading text; the
   announcement-list title matching (`_select_target_announcements`) has never needed
   it before since "Annual Report"/"Half-Year Report" have no apostrophes. Needs the
   same normalization applied to title matching, or a pattern set generous enough to
   not depend on the apostrophe rendering consistently (confirmed titles above render
   correctly in the list HTML — the known encoding issue in `asx_announcements.py` is
   specifically a PDF-text-extraction artifact via pdfplumber, which may or may not
   also affect this new module's PDF text; worth re-confirming rather than assuming
   the same bug applies here).
5. **Which `goat_insider_filings_seen` `kind` value, and does `run_discovery_scan`
   (market-wide) need to stay ASX-blind explicitly, or just naturally stay so per
   Open Question #1?** Recommend: reuse the existing `kind="holdings_watch"` value
   rather than a new `"holdings_watch_asx"` (the dedup key is already
   ticker+filing-identity scoped, and `get_recent_insider_filings_seen(kind=
   "holdings_watch")` is what feeds `compute_holdings_watch_price_performance` — a
   split kind would need that caller updated too, for no clear benefit since nothing
   downstream currently needs to distinguish US vs ASX holdings-watch rows).

## Explicitly deferred (do not build as part of this handoff)

- **Market-wide ASX discovery scan** (new-candidate surfacing the way US
  `run_discovery_scan` does) — see Open Question #1. No confirmed free bulk feed.
- **ETF "insider" tracking via substantial-holder notices** — see Open Question #2.
  A different signal (5%+ holder changes, any holder type) from a different regime,
  not a gap-fill for director dealings on a fund that structurally has none.
- **Extending this to NZX or any other non-ASX exchange** — out of scope, Shaun's
  question and holdings are ASX-only right now.

## Reference code to reuse (read all of these during `/plan-feature`)

- **`mytrader/asx_announcements.py`** — the whole file. Its list-fetch
  (`_fetch_announcements_list`), interstitial-resolve (`_resolve_pdf_url`), and
  PDF-fetch (`_fetch_pdf_bytes`)/text-extract (`_extract_pdf_text`) primitives are
  directly reusable as-is; only the title-pattern matching and post-extraction field
  parsing need to be new for this feature (prose-section extraction vs. labeled-field
  extraction are different problems).
- **`mytrader/openinsider.py`** — `_EXPECTED_COLUMNS`/row shape (the target shape the
  new ASX rows must match) and `_parse_money`/`_parse_pct_owned_change`-style parsing
  philosophy (fail-open, never block an alert over an unparsable field).
- **`goat/insider_scan.py`** — `run_holdings_watch` (lines ~100-168, where the
  `.AX`-suffix branch and row-list concatenation goes), `maybe_notify_price_flags` and
  `compute_holdings_watch_price_performance` (already company-name- and
  days-since-aware as of 2026-09-19, needs zero changes if the new rows match shape),
  `_TRADE_VALUE_RE`/`_parse_trade_value` (reusable for the Value/Consideration field).
- **`mytrader/checks/insider_selling.py`** — the Find-only check needing the same
  `.AX`-suffix branch, small/self-contained.
- **`mytrader/config.py`**'s `ASX_*` block (lines ~249-288) — `ASX_USER_AGENT`,
  `ASX_ANNOUNCEMENTS_LIST_URL_TEMPLATE`, `ASX_ANNOUNCEMENT_INTERSTITIAL_URL_TEMPLATE`,
  `ASX_REQUEST_DELAY_SECONDS` (WAF-caution rate limit) — all directly reusable
  constants, no new ones needed for the fetch layer itself.
- **`goat/db.py`** — `insert_goat_insider_filing_seen`/`get_recent_insider_filings_seen`
  (already `company_name`-aware as of 2026-09-19) — the ASX rows write through the
  exact same functions, no schema changes needed.

## Validation (once built)

```powershell
.\scripts\invoke_investments.ps1 -Package goat -Command "scan-insiders"
.\scripts\invoke_investments.ps1 -Package my-trader -Command "find --ticker XRO.AX"
```

Expected: XRO.AX's `insider_selling` check (and, if XRO.AX or another `.AX` ticker is
ever added to holdings, Goat's Holdings Watch) surfaces the real `Change of CEO's
Interest Notice` sale confirmed live in this handoff (Sukhinder Singh Cassidy, 29,608
shares, $2,190,992, 7 July 2026) instead of a false "no filings" read. A WhatsApp alert
for a fresh ASX filing should render identically in style to a US one:
`- XRO.AX (Xero Limited): Sukhinder Singh Cassidy (CEO) sold $2,190,992 of XRO.AX on
2026-07-07`.

## Sources consulted (2026-09-19)

- `investments/my-trader/mytrader/asx_announcements.py`, `openinsider.py`, `config.py`
  (`ASX_*` block), `checks/insider_selling.py`
- `investments/goat/goat/insider_scan.py`, `db.py`
- Live ASX Market Announcements Platform data for XRO (`asx.com.au/asx/v2/statistics/
  announcements.do?by=asxCode&asxCode=XRO&timeframe=Y&year=2026`) — 39 real 2026
  announcements listed, including 2× `Change of CEO's Interest Notice` and 1×
  `Final Directors Interest Notice Anjali Joshi`
- Two real PDF filings fetched and read in full: XRO's `Final Directors Interest
  Notice Anjali Joshi` (Appendix 3Z) and `Change of CEO's Interest Notice`
  (7 July 2026 sale, $2,190,992)
- `asx.com.au/markets/trade-our-cash-market/todays-announcements` (checked for a
  market-wide feed — exists but appears client-side rendered, no API endpoint found
  in static HTML/JS)
- `marketindex.com.au/director-transactions` (a real, free, market-wide ASX director-
  transaction aggregator — confirmed to exist via web search 2026-09-19, but a direct
  fetch with the same browser-like User-Agent already used for `asx.com.au` returned a
  Cloudflare bot-challenge page, HTTP 403, not the real content)
- ASIC's own public-facing pages on insider trading/market misconduct (confirmed ASIC's
  role is enforcement/investigation, not a disclosure database — the actual disclosure
  mechanism is ASX Listing Rule lodgement, already covered above)
