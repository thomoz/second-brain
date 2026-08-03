# Handoff: Read ASX Market Announcements Into Find's Principles-Fit Check

## Status: Discovery/research complete, no code written yet — ready for `/plan-feature`

Access mechanism, PDF library, and test tickers are now all confirmed live (see
"CONFIRMED" sections below). Run `/plan-feature` in a fresh session to turn this into
a detailed implementation plan.

## Context

`mytrader/sec_filings.py` (built + deployed 2026-08-03, see
`.agent/plans/completed/sec-filings-principles-fit.md`) reads each US-listed ticker's
latest 10-K/10-Q/DEF 14A directly from SEC EDGAR and folds a summary into
`principles_fit.py`'s thesis, so all 9 investor-framework grades are informed by
primary-source disclosures instead of just `yfinance`'s derived ratios. It's fully
live, tested (13 new tests, full suite 256 passing), and validated against a real
KO filing.

**The gap this handoff addresses**: SEC EDGAR is the U.S. SEC's own filing system —
ASX-listed tickers (BXB.AX, WES.AX, etc. — several already in the watchlist/holdings,
see `investments/my-trader/watchlist.md`/`holdings.md`) never resolve to a CIK, so
`sec_filings.py` returns `None` for them every time (confirmed live: `find --ticker
BXB.AX` produces `filing_types_used == []`, no exception, clean degradation to
stats-only). ASX tickers still get the full yfinance-derived check suite (PE,
debt/equity, dividend trend, etc. — `tickers.asx_variant()` appends `.AX` for the
yfinance lookup, see `market_data.py:71`) — only the primary-source filing layer is
missing for them.

Shaun's framing, same as the SEC filings work: **"a tool that approximates an expert
investor"** — for ASX names, that means reading the company's own ASX-lodged
announcements (annual/half-year reports, Appendix 4E, etc.), not just derived stats.

## Key difference from the SEC filings build — flag this early in `/plan-feature`

**ASX company reports are typically lodged as PDF documents, not HTML.** SEC EDGAR
filings are HTML (BeautifulSoup tag-stripping + Item-header text-matching worked
well there, once fixed to prefer the real body section over the TOC — see that
plan's "GOTCHA" notes). ASX's Market Announcements Platform (the ASX's own free,
public announcements feed — no login required, this is the closest ASX equivalent to
EDGAR) serves company disclosures as PDFs. This means:
- **CONFIRMED**: a PDF-text-extraction library is already in this exact uv workspace —
  `pdfplumber` and `pymupdf` are both dependencies of `investments/briefs-finance`
  (resolved in the shared `investments/uv.lock`), and `briefs-finance/scripts/extract.py`
  already has a working, proven pattern to mirror directly: `pdfplumber` for primary
  text extraction, falling back to PyMuPDF-render + `pytesseract` OCR for image-based/
  scanned PDFs (common for older ASX filings). No new library evaluation needed — just
  add `pdfplumber`/`pymupdf` to `my-trader`'s `pyproject.toml` (already lock-resolved,
  so no new resolution work) and reuse/mirror `extract_text()` from that file.
- Section-splitting heuristics will differ entirely from `_split_by_item`/
  `_split_by_part` — ASX annual/half-year reports don't use SEC's numbered
  "Item N." convention. Likely need heading-search similar to `sec_filings.py`'s
  DEF 14A approach (blunter, TOC-vs-body duplication risk likely applies here too —
  test against a real fetched PDF before trusting any heuristic, same lesson learned
  building `sec_filings.py`).

**CONFIRMED live 2026-08-03** (unlike when this handoff was first drafted — the access
mechanism below was traced end-to-end and a real PDF was downloaded to verify it):

The old free JSON API (`asx.com.au/asx/1/company/...`) is dead — confirmed 404 live,
consistent with third-party reports it was killed off around October 2024. Ignore any
reference implementation (e.g. the `pyasx` PyPI package) that targets it. The current
working, free, no-login path is a two-hop scrape:

1. **List announcements for a ticker/year** — this legacy-looking endpoint is still
   live and returns real server-rendered HTML (no JS rendering needed):
   ```
   https://www.asx.com.au/asx/v2/statistics/announcements.do?by=asxCode&asxCode={CODE}&timeframe=Y&year={YYYY}
   ```
   Verified against real `BXB` and `WES` 2026 data — correctly listed every
   announcement with date, title, page count, file size, and a
   `displayAnnouncement.do?display=pdf&idsId={id}` link per row. `{CODE}` is the bare
   ASX ticker without `.AX` suffix (e.g. `BXB`, not `BXB.AX`).

2. **Each `idsId` link is a legal click-through interstitial, not the PDF** — ASX's
   terms distinguish "private/personal investment use" (free, unrestricted) from
   "commercial" use (requires a paid ComNews license — this is the legal mechanism
   behind Shaun's "surely this has to be free" instinct: continuous disclosure rules
   force ASX to publish, but they gate the free tier behind a use-attestation aimed at
   commercial redistributors, not personal tools like this one).

3. **The interstitial's HTML already contains the real PDF URL in a hidden form
   field** — no need to actually POST/accept anything, just fetch the interstitial
   and regex/parse out the hidden input:
   ```html
   <form name="showAnnouncementPDFForm" method="post" action="/asx/v2/statistics/announcementTerms.do">
       <input name="pdfURL" value="https://announcements.asx.com.au/asxpdf/20260219/pdf/06wgrb9r2wzmbt.pdf" type="hidden">
   </form>
   ```

4. **That `pdfURL` is a direct, sessionless PDF fetch** — verified live: downloaded
   BXB's actual 2026 Half-Year Report this way (`HTTP 200`, `application/pdf`,
   5.36MB, real PDF bytes confirmed via `curl`). Works generically for any ASX
   ticker, not just BXB/WES — this is a genuine EDGAR-equivalent, better fit than
   scraping individual companies' own investor-relations sites (which was the
   fallback considered before this was traced through, and would require a manual
   per-company URL registry with no uniform structure — see chat history if that
   path is ever revisited).

**Caveat**: the interstitial page loads an Incapsula (Imperva) WAF script tag. It
didn't block a handful of manual test requests, but a scheduled/automated scraper
should use a normal browser `User-Agent`, keep request volume low, and build in
retry/backoff rather than assume this stays this permissive indefinitely — same
"don't hammer it" caution SEC's `User-Agent` requirement got in the sibling build.

## Scope (needs confirming with Shaun during `/plan-feature`, mirroring the SEC handoff's approach)

- **Documents**: most recent Annual Report and Half-Year Report (ASX's rough
  equivalent of 10-K/10-Q — but reporting is half-yearly, not quarterly, for ASX-listed
  companies, so there's no direct quarterly analogue to a 10-Q). Appendix 4E
  (preliminary final report) may be a useful additional signal — confirm with Shaun
  whether it's in scope for v1.
- **Universe**: ASX-listed tickers only (`.AX` suffix) — this is a second, separate
  data source alongside `sec_filings.py`, not a replacement. A ticker that's neither
  US-listed nor ASX-listed (LSE/other, e.g. VOLV-B.ST from the original SEC handoff)
  still degrades to stats-only, same pattern.
- **Sections extracted**: whatever the equivalent of Business/Risk Factors/MD&A is in
  an ASX annual report — likely "Operating and Financial Review" / "Principal Risks" /
  Directors' Report sections, but confirm actual real-world heading conventions
  against a live fetch (e.g. BXB, WES — already-tracked ASX tickers) before assuming
  naming.
- **Integration point**: same as SEC filings — augment `principles_fit._build_thesis()`
  with a second optional parameter (e.g. `asx_announcement_summaries`), following the
  exact pattern `filing_summaries` already established (added last, default `None`,
  conditionally appended). Do not duplicate `sec_filings.py`'s module — either extend
  it to handle both sources, or add a sibling module (e.g. `asx_announcements.py`)
  that mirrors its style (direct-fetch, `requests`, graceful `None` on failure, no
  third-party wrapper beyond the PDF library, own cache table following
  `sec_filing_cache`'s invalidate-on-new-filing pattern rather than
  `principles_fit`'s own no-cache policy).

## Reference: the exact code to mirror

- `investments/my-trader/mytrader/sec_filings.py` (full file, ~320 lines) — the
  direct style/pattern reference: CIK-equivalent resolution + cache, filing-index
  fetch, document fetch, section extraction, one `sdk_compat` LLM summarization call
  per document, cache-aware orchestrator returning `dict[str, str] | None`. An ASX
  equivalent should follow this exact shape with PDF extraction swapped in for
  BeautifulSoup HTML extraction.
- `investments/my-trader/mytrader/checks/principles_fit.py` — `_build_thesis()`
  (the `macro_rows`/`filing_summaries` parameter-addition pattern) and `check()`
  (the `conn is not None`-gated lookup call) are exactly what a new
  `asx_announcement_summaries` parameter should replicate.
- `investments/my-trader/mytrader/db.py` — `sec_cik_map`/`sec_filing_cache` table
  definitions and CRUD (`upsert_cik_map_bulk`, `get_cik_for_ticker`,
  `get_cached_filing_summary`, `upsert_filing_summary_cache`) are the direct pattern
  for whatever ASX-equivalent tables are needed.
- `investments/my-trader/mytrader/tests/test_sec_filings.py` — the exact test-shape
  to mirror (CIK-map-equivalent lookup miss, cache hit/miss/stale-fallback, section
  extraction against a real saved fixture, never a live network call in tests).
- `.claude/skills/my-trader/SKILL.md`'s "SEC Filing Reads (principles_fit)" section
  — the documentation shape/density to match for a new "ASX Announcements" section.

## Open Questions for Shaun (resolve before/during `/plan-feature`)

1. ~~Confirm the actual ASX Market Announcements Platform access mechanism~~ —
   **RESOLVED**, see confirmed mechanism above.
2. ~~Which PDF-parsing library to add~~ — **RESOLVED**, `pdfplumber`/`pymupdf`
   already in the workspace, mirror `briefs-finance/scripts/extract.py`.
3. Annual Report + Half-Year Report only, or also Appendix 4E / other regular
   disclosures? Still open — the `announcements.do` listing returns everything
   (dividends, buy-backs, director notices, etc.), so filtering logic needs a
   decision on which announcement titles/categories to select.
4. Summarization model tier — reuse the same `sonnet` default already locked in for
   SEC filings (`config.SEC_FILING_SUMMARY_MODEL`), or test independently since PDF
   text extraction may be noisier than SEC's cleaner HTML? Still open.
5. ~~Which ASX tickers to test extraction against during build~~ — **RESOLVED**:
   `BXB.AX` (Brambles) and `WES.AX` (Wesfarmers) are the only two ASX-listed *stocks*
   in `watchlist.md` (both Bucket 4, both already have rich thesis notes). `VAS`,
   `VGS`, `IXI.AX` are also ASX-domiciled but are ETFs — out of scope, same as US
   ETFs (`principles_fit` isn't meaningful for baskets, per existing IVV/SPY notes).
   No ASX stocks currently in `holdings.md`. Both `BXB` and `WES` were used to
   verify the access mechanism above and both returned real 2026 Half-Year Report
   entries, so extraction can be built/tested against real fetched PDFs immediately.
