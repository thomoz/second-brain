# Superinvestor Fast-Disclosure Filings Scanner — Session Handoff

## Status: BUILT (EDGAR leg) 2026-09-07 — Phase 5 India / SEBI SAST: NOT STARTED (spike pending Shaun's sign-off, see `investments/superinvestor-filings/INDIA-LEG-FINDINGS.md`).

Plan: `.agent/plans/superinvestor-filings-scanner.md`. Package:
`investments/superinvestor-filings/`. Phases 1-4 complete: EDGAR submissions poll +
Form 3/4/5 + Schedule 13D/G parsers + seen-log dedup + grouped WhatsApp digest +
markdown report + `resolve-ciks` discovery command + systemd timer
(`second-brain-superinvestor-edgar.timer`, 02:35 UTC) + `invoke_investments.ps1` /
`deploy.ps1` wiring. Deploy is a manual step — see
`investments/superinvestor-filings/DEPLOY.md`. 36 new package tests + 7 new
`mytrader.sec_filings` tests pass; full `investments/` suite green apart from 3
pre-existing `test_retail_leverage` failures unrelated to this work.

## What This Is

Shaun tracks a handful of concentrated value investors (Mohnish Pabrai / Dalal
Street first) and wants to know when they trade **without waiting up to ~135 days
for the next 13F** (quarterly, due 45 days after quarter-end, and only a
point-in-time snapshot).

Certain filings are legally required much faster than 13F. Build a daily scanner,
keyed on a **configurable list of tracked filers**, that catches those and fires a
WhatsApp alert the day the filing appears. Two data sources:

1. **US — SEC EDGAR** (`Schedule 13D`, `13D/A`, `13G`, `13G/A`, `Form 3`,
   `Form 4`, `Form 4/A`, `Form 5`).
2. **India — SEBI SAST Regulation 29** 5%/2% crossing disclosures, filed with
   BSE/NSE. Pabrai's largest single positions have historically been Indian
   (Rain Industries, Sunteck Realty, etc.) via the Foreign Portfolio Investor
   route — these never touch EDGAR, so an India leg is required, not optional.

Advisor-notes only. The scanner surfaces a filing; it never trades, never adds to
the watchlist automatically. Same posture as every other tool here (SOUL.md).

## Why each filing type beats 13F (get this right before building)

The SEC shortened most of these deadlines in the 2023 rule amendments (13D initial
compliance date 2024-02-05; accelerated 13G amendment schedule compliance date
2024-09-30) — any older reference will overstate the lags.

| Filing | Deadline | When it triggers | Notes for this tool |
|---|---|---|---|
| **13F** | 45 days after quarter-end | holdings ≥ $100M AUM | the slow baseline we're beating |
| **SC 13D** | 5 business days after crossing 5% | activist / "intent to influence" | Pabrai rarely files this — signals activism |
| **SC 13D/A** | 2 business days after a material change (rule of thumb ≈ 1% of the class) | any material change while on a 13D | fast and detailed, but only if a 13D exists |
| **SC 13G** (passive filer) | 5 business days after crossing 5% | passive intent, < 20% | **Pabrai's usual form.** Initial crossing is genuinely fast |
| **SC 13G/A** | 45 days after quarter-end for ordinary changes; **2–5 business days** if crossing 10%, or (passive) a 5%+/−2.5% swing | | so ongoing trims/adds are only marginally faster than 13F — the real signals are **5% cross, 10% cross, and dropping below 5% (full/near exit)** |
| **Form 3** | 10 calendar days after becoming a > 10% beneficial owner | Section 16 insider status | initial; tells you they've crossed 10% on that issuer |
| **Form 4** | 2 business days | **every** buy/sell once a > 10% owner (or officer/director) | fastest + most granular. Dalal Street has been a > 10% holder on coal names (Alpha Met, Warrior Met) — Form 4s do occur |
| **Form 5** | 45 days after issuer fiscal year-end | deferred / missed Section 16 items | low value, include for completeness |

Net: for a passive concentrated filer like Pabrai the high-value events are
**threshold crossings** (5%, 10%, exit) and **Form 4s on any name where they're
already > 10%**. Ordinary position sizing inside 5–10% mostly still waits for the
quarterly cycle — set expectations accordingly so the alert isn't oversold.

## India — SEBI SAST Regulation 29 (the second leg)

- **Reg 29(1)** — an acquirer whose aggregate holding **crosses 5%** of a listed
  company must disclose within **2 working days** of the acquisition.
- **Reg 29(2)** — once at/above 5%, **every change of ≥ 2%** of the company
  (increase *or* decrease) must be disclosed within **2 working days**. This is
  materially better granularity than the US 13G once past 5%.
- Disclosures are filed with **BSE and NSE** and the target company. BSE publishes
  them under "Corp Announcements / SAST" and NSE under "Corporate
  Filings → Insider Trading / SAST"; both have per-company announcement feeds and
  bulk daily lists.
- Secondary India source worth noting: exchange **bulk-deal** (> 0.5% of a
  company's shares in a day) and **block-deal** windows are published by BSE/NSE
  end-of-day and name the client — a same-day signal, though not filer-scoped the
  way SAST is.
- Filer-name matching on the Indian exchanges is messy: Pabrai files under fund
  entity names ("The Pabrai Investment Fund II, LP", "…Fund IV, LP", "Dalal Street
  LLC", "Dhandho …") and spellings vary. The India leg needs a **name-pattern
  match list**, not a single exact string, plus manual confirmation of the current
  entity names during planning.

## Tracked-filer identity — resolve ALL of these, don't assume one CIK

Check for filings under **both**:
- `Dalal Street, LLC` (the investment manager — files the 13F)
- `Pabrai, Mohnish` (individual — 13D/G groups and Section 16 forms are often
  filed in the individual's name, or jointly)

…and during planning also enumerate any **fund-entity CIKs** (Pabrai Investment
Fund II / III / IV, Dhandho entities) that show up on EDGAR full-text search for
"Pabrai" — group filings list every group member and any could be the named filer
on a given form. Store a list of CIKs per tracked investor, not a scalar.

The config shape should make adding a second investor later (Li Lu / Himalaya
Capital, Guy Spier / Aquamarine, David Abrams, Norbert Lou, etc.) a data edit, not
a code change.

## Current State — reusable infrastructure already in the workspace

Grounded in code, checked 2026-09-07.

- **`investments/my-trader/mytrader/sec_filings.py`** already has most of the
  EDGAR fetch layer:
  - `_HEADERS = {"User-Agent": config.SEC_USER_AGENT}` — compliant UA already set.
  - `_fetch_cik_map_bulk()` / `get_cik(conn, ticker)` — bulk `company_tickers.json`
    ticker→CIK map, DB-cached with a staleness refresh (`sec_cik_map` table,
    `SEC_CIK_MAP_REFRESH_DAYS`). Note: this maps **issuer** tickers, not filer
    names — a filer-name→CIK lookup is new (EDGAR `company_tickers.json` won't
    have investment managers; use the full-text search endpoint or the
    `cik-lookup-data.txt` name index).
  - `fetch_filing_index(cik)` — hits `data.sec.gov/submissions/CIK{cik:010d}.json`
    (`config.SEC_SUBMISSIONS_URL_TEMPLATE`). Returns the filer's recent-filings
    list with form types, accession numbers, and dates. **This is the core poll
    for a filer-keyed scanner** — point it at Dalal Street's / Pabrai's CIK
    instead of an issuer's.
  - `edgar_fulltext_search_count(forms, cik=, startdt=, enddt=)` — hits
    `efts.sec.gov/LATEST/search-index`. Currently returns only a count; the same
    endpoint returns hit details (accession, issuer, form, date) — extend or add
    a sibling that returns the rows. GOTCHA already documented in that file: the
    `ciks` param must be 10-digit zero-padded.
  - `fetch_filing_document(cik, accession, document)` — pulls a specific filing
    doc, with a `SEC_MAX_RAW_DOCUMENT_BYTES` guard.
  - Non-US tickers degrade gracefully (CIK miss → `None`) — the India leg lives
    entirely outside this module.
- **`investments/goat/goat/insider_scan.py` + `goat/db.py`** — the pattern to
  mirror for the scan orchestration:
  - `goat_insider_filings_seen` (`goat/db.py:42`) — permanent, append-only,
    deduped-by-key filing log, never deleted. A new
    `superinvestor_filings_seen` table should copy this shape (`dedup_key`,
    `filer`, `form_type`, `issuer`, `issuer_ticker`, `event_date`, `filed_date`,
    `shares`, `pct_owned`, `pct_owned_change`, `source` = `edgar` | `sast` |
    `bulk_deal`, `raw_url`, `first_seen_at`).
  - `openinsider.build_dedup_key(row)` — dedup-key construction pattern.
  - `insider_scan.py` three-way dedup (holding / watchlist / already-seen) and
    report-render structure.
- **Systemd + alert pattern** — `scripts/systemd/second-brain-goat-insider-scan.{service,timer}`
  is the exact template: a daily `OnCalendar` timer, `EnvironmentFile` for the
  `.env`, runs a `-m <package>.main <subcommand>`. WhatsApp alert path is the same
  `notifications.py` / heartbeat-alert pipeline the insider scan already uses.
- **`invoke_investments.ps1`** — the only sanctioned way to run this against the
  real (VPS-only) `investments.db` from a local session.

## Proposed Design

### Package placement (open question — see below)
Leaning toward a **new small package** `investments/superinvestor-filings/`
(sibling to `fourteen-crash-signals-daily-check/`) rather than folding into goat
(this isn't sector-rotation / momentum) or my-trader (not a per-ticker
assessment). It would import `mytrader.sec_filings` for the EDGAR helpers, the
same way goat imports `mytrader.openinsider`.

### US leg — `edgar_monitor.py`
1. For each tracked investor, for each of their CIKs: `fetch_filing_index(cik)`.
2. Filter to the fast-disclosure form set (table above).
3. For each filing not already in `superinvestor_filings_seen`: fetch the primary
   doc, parse issuer name + ticker (13D/G cover page and Form 3/4/5 have
   structured XML — Form 4 especially is clean XML), shares, % of class,
   transaction date, transaction code (P/S for Form 4).
4. Insert into the seen-log. Build an alert line.
5. WhatsApp alert grouped per run: "Pabrai / Dalal Street — new fast disclosure(s):
   SC 13G on RAIN (new 5.2% stake, event 2026-09-02, filed 2026-09-05)".

### India leg — `sast_monitor.py`
1. Poll the BSE and NSE SAST / insider-trading disclosure feeds (per-day bulk
   lists are simplest; per-company feeds need a target list we don't have).
2. Name-pattern match the acquirer field against the tracked-investor alias list.
3. Same insert-into-seen-log + alert path, `source = 'sast'`.
4. (Optional, phase 2) also ingest BSE/NSE bulk-deal EOD files and name-match the
   client field, `source = 'bulk_deal'`.

### Dedup / "new" detection
`dedup_key` = `(source, filer, form_type, issuer, accession_or_exchange_ref)`.
Append-only; a filing is "new" (→ alert) only on first insert. A same-day
double-run is a safe no-op (`INSERT OR IGNORE`), matching the goat precedent.

### Config (`config.py`)
```
SUPERINVESTOR_TRACKED = {
    "pabrai": {
        "display": "Mohnish Pabrai / Dalal Street",
        "edgar_ciks": ["<Dalal Street LLC CIK>", "<Pabrai Mohnish CIK>", ...],
        "india_aliases": ["pabrai investment fund", "dalal street", "dhandho", ...],
    },
    # add more investors here — data only, no code change
}
SUPERINVESTOR_EDGAR_FORMS = ["SC 13D", "SC 13D/A", "SC 13G", "SC 13G/A", "3", "4", "4/A", "5"]
SUPERINVESTOR_LOOKBACK_DAYS = 30   # how far back to consider a filing "recent" on first ever run
```

## Open Questions (resolve during `/plan-feature`)

1. **Package placement** — new `investments/superinvestor-filings/` package, vs. a
   goat subcommand, vs. a my-trader subcommand. Recommendation: new package.
2. **First-run behaviour** — on the very first run every historical 13D/G/Form 4
   is "new". Seed the seen-log silently from the last `SUPERINVESTOR_LOOKBACK_DAYS`
   (or from all-time) without alerting, then alert only on genuinely new filings
   after that. Confirm the lookback.
3. **Filer-name → CIK resolution** — `company_tickers.json` won't have investment
   managers. Use `efts.sec.gov` full-text search by entity name, or the EDGAR
   `cik-lookup-data.txt` name index? And cache the resolved CIK list per investor
   with what TTL (these barely change — long TTL, plus a manual re-resolve
   command).
4. **13G/A noise control** — most 13G/A are ordinary quarterly-ish updates.
   Alert on every 13G/A, or only when the parsed % ownership crosses 5% / 10% or
   drops below 5% (the events that are actually faster than 13F)? Recommendation:
   alert on all initially, add a "material crossing" tag, tighten later if noisy.
5. **Form 4 parsing depth** — full XML parse (transaction-by-transaction, code,
   price, post-transaction holding) vs. a lighter "a Form 4 appeared, here's the
   link" alert. Recommendation: full parse — the XML is clean and the detail is
   the point.
6. **India source mechanics** — do BSE and NSE expose a machine-readable daily
   SAST disclosure list (CSV/JSON/scrapeable table) without login, and at what
   URL? Live-check during planning. If only per-company feeds exist, the India
   leg needs a watched-Indian-issuer list (seedable from Pabrai's last known
   India holdings + any new SAST hit auto-adding the issuer).
7. **India entity aliases** — confirm the *current* legal entity names Pabrai's
   funds file under on BSE/NSE (they have changed over the years).
8. **Bulk/block deal leg** — in scope for v1 or deferred to a fast-follow? It's a
   different match (client name in an EOD trade file, not a threshold
   disclosure) and catches sub-5% activity the SAST feed misses.
9. **Alert cadence & grouping** — one WhatsApp message per run listing all new
   filings (like the heartbeat digest), vs. one per filing. Recommendation:
   grouped digest.
10. **Timer schedule** — EDGAR filings post through the US business day; SEC EDGAR
    accepts filings until 22:00 ET. A single daily run after ~22:30 ET (≈ 12:30
    AEST next day) catches a full US day. India disclosures post through the IST
    business day — a run after ~18:00 IST (≈ 22:30 AEST) catches those. Two
    timers, or one run timed to catch both with up to a day's latency on one
    side? Confirm acceptable latency.
11. **Backfill** — do we want a one-off historical import of Pabrai's past
    13D/G/Form 4/SAST filings into the seen-log for reference (no alerts), or
    start the log empty from go-live?
12. **`goat_insider_filings_seen` overlap** — if Dalal Street files a Form 4 on a
    US name, the goat insider scanner's discovery scan could *also* pick it up
    from OpenInsider. Different table, different purpose (goat = market-wide
    pattern data; this = one tracked filer) — keep separate, but note the
    possible double alert and decide whether to suppress one.

## Explicitly NOT Scoped

- Any automatic trade / watchlist action from a filing — advisor-notes only.
- 13F ingestion / parsing — that's the slow source this exists to supplement, and
  briefs-finance / other tooling already covers quarterly holdings elsewhere.
- Europe / other non-US, non-India jurisdictions (UK TR-1, etc.) — note as a
  future leg only if Pabrai or a future tracked investor actually files there.
- Copy-trading logic, position-size inference, or "should Shaun buy this too"
  scoring — a filing is something Shaun reads and judges.
- A dashboard/UI beyond the markdown report + WhatsApp alert.

## Validation (once built)

```powershell
uv run --directory investments/superinvestor-filings python -m pytest -q

# On the VPS via invoke_investments.ps1 — never run locally against the real DB.
# (add "superinvestor-filings" to the invoke_investments.ps1 $PACKAGES map)
.\scripts\invoke_investments.ps1 -Package superinvestor-filings -Command "scan"
.\scripts\invoke_investments.ps1 -Package superinvestor-filings -Command "scan --edgar-only"
.\scripts\invoke_investments.ps1 -Package superinvestor-filings -Command "scan --india-only"
.\scripts\invoke_investments.ps1 -Package superinvestor-filings -Command "resolve-ciks"
```

First `scan` after deploy seeds the seen-log and sends no alert (expected — no
"new since last run" on the first run).

## Sources Consulted (2026-09-07)

- `investments/my-trader/mytrader/sec_filings.py` — confirmed the EDGAR fetch
  layer: `_HEADERS`/`SEC_USER_AGENT`, `_fetch_cik_map_bulk`, `fetch_filing_index`
  (→ `data.sec.gov/submissions/CIK*.json`), `edgar_fulltext_search_count`
  (→ `efts.sec.gov/LATEST/search-index`, with the zero-pad gotcha noted),
  `fetch_filing_document`.
- `investments/goat/goat/insider_scan.py`, `goat/db.py` — `goat_insider_filings_seen`
  append-only deduped-log shape (`db.py:42`), dedup-key construction, scan
  orchestration + three-way dedup pattern.
- `scripts/systemd/second-brain-goat-insider-scan.{service,timer}` — the daily
  timer + `.env` EnvironmentFile + `python -m <pkg>.main <cmd>` template to
  mirror.
- `scripts/invoke_investments.ps1` — package map + VPS-only DB access pattern
  (would need a `superinvestor-filings` entry added).
- User-provided research (2026-09-07) on 13D/13G/Form 4 deadlines — corrected
  here against the 2023 SEC amendment schedule (13D → 5 business days; accelerated
  13G/A schedule) and annotated for which events actually beat 13F for a passive
  concentrated filer.
- SEBI SAST Regulations 2011, Reg 29(1)/(2) — 5% crossing and ≥ 2% change
  disclosures to BSE/NSE within 2 working days (exact feed URLs/format to be
  live-checked during `/plan-feature`, per Open Question 6).
```
