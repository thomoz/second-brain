# India / SEBI SAST Leg (Phase 5) — Spike Findings

## Status: FEED CONFIRMED on BSE — 2026-09-08. Ready to build, pending Shaun's go.

The Task 5.1 spike (live recon from the VPS) found a working, no-login,
machine-readable feed of SEBI SAST Regulation 29 disclosures on **BSE**. NSE is a
dead end from this VPS (see below).

## The working BSE endpoint

```
GET https://api.bseindia.com/BseIndiaAPI/api/AnnSubCategoryGetData/w
    ?pageno=1
    &strCat=Insider Trading / SAST      <- dedicated category (URL-encodes to "Insider+Trading+/+SAST")
    &strPrevDate=YYYYMMDD               <- range start; range must be <= 1 month
    &strToDate=YYYYMMDD                  <- range end
    &strScrip=
    &strSearch=P
    &strType=C
    &subcategory=-1
```

Required request setup (confirmed):
- Browser-like `User-Agent` (a plain/absent UA or `SEC_USER_AGENT` is not enough).
- `Referer: https://www.bseindia.com/corporates/ann.html`
- `Origin: https://www.bseindia.com`
- `Sec-Fetch-Site: same-site`, `Sec-Fetch-Mode: cors`
- Prime the session first with `GET https://www.bseindia.com/` (reuse the
  `requests.Session`). Cookies came back empty in testing but priming still helped;
  keep it.
- No login, no API key.

Response: JSON `{"Table": [ ...rows... ], "Table1": [{"ROWCNT": <total>}]}`.
50 rows/page, paginate with `pageno`. The `Insider Trading / SAST` category runs
~977 rows/month (~30/day) — a small daily scan.

## Row shape (fields we need)

```json
{
  "NEWSID": "b6fed1a2-...",
  "SCRIP_CD": 512441,
  "SLONGNAME": "Enbee Trade & Finance Ltd",
  "NEWSSUB": "Enbee Trade & Finance Ltd - 512441 - Disclosure In Terms Of Regulation 29(2) Of Securities And Exchange Board Of India (Substantial Acquisition Of Shares And Takeovers) Regulations, 2011- AMARR NARENDRA GALLA",
  "NEWS_DT": "2026-09-07T21:24:38.053",
  "ATTACHMENTNAME": "e7090794-....pdf",
  "NSURL": "https://www.bseindia.com/stock-share-price/enbee-trade--finance-ltd/enbetrd/512441/",
  "CATEGORYNAME": "Company Update",
  ...
}
```

- **Issuer**: `SLONGNAME` + `SCRIP_CD`.
- **Regulation**: parse `"Regulation 29(1)"` / `"Regulation 29(2)"` (also see 10(5)/10(6)
  exemption disclosures — filter those out or tag them separately) out of `NEWSSUB`.
- **Acquirer**: the trailing segment of `NEWSSUB` after the last `" - "` / `"- "`
  ("AMARR NARENDRA GALLA" above). This is the field to name-pattern-match against
  each tracked investor's `india_aliases` (case-insensitive substring, any match).
- **Date**: `NEWS_DT`.
- **Detail link**: `https://www.bseindia.com/xml-data/corpfiling/AttachLive/<ATTACHMENTNAME>`
  (PDF). The exact **% of class** and **share count** are only in this PDF, not the
  JSON — so a v1 alert carries "Reg 29(2) disclosure by <acquirer> on <issuer>,
  <date>, [PDF]" and PDF-parsing the % is a fast-follow, not a blocker.
- **Dedup ref**: `NEWSID` (stable GUID) → use as the `accession`-equivalent in
  `build_dedup_key("sast", filer_key, "SAST Reg 29(x)", issuer, NEWSID)`.

Real SAST rows seen in the last 24h during the spike: Enbee Trade & Finance /
"AMARR NARENDRA GALLA" (Reg 29(2)), Fabtech Cleanrooms (Reg 29(2)), Nirmitee
Robotics (Reg 10(6)).

## NSE — dead end from this VPS

`GET https://www.nseindia.com/` returns **403 Access Denied** at the Akamai edge
for the VPS IP — can't even prime cookies, so the documented
"GET nseindia.com first, reuse the Session" approach is unavailable. BSE market-data
APIs (quotes, gainers) *do* serve this IP fine, so it is an NSE-specific block, not
a general geo-block. BSE-only is an acceptable v1: SAST disclosures are filed with
both exchanges, so BSE catches them.

## Build plan (unchanged from the plan's Phase 5, now unblocked)

1. `sast_monitor.fetch_sast_disclosures(prev_date, to_date) -> list[dict] | None` —
   the paginated BSE call above, browser UA + priming (`SAST_USER_AGENT` already
   defined in `sast_monitor.py`).
2. `sast_monitor.scan_india(conn)` — structurally identical to `scan_edgar`: for each
   row, filter to Reg 29(1)/(2), extract acquirer, substring-match against every
   tracked investor's `india_aliases`, `build_dedup_key("sast", ...)`,
   `db.insert_superinvestor_filing_seen(..., source="sast")`, build an alert dict.
   First-run silent seed shares the existing watermark pattern (or a `sast`-specific
   one).
3. `main.cmd_scan`: flip `run_india` default to `True` so a bare `scan` runs both legs.
4. `second-brain-superinvestor-sast.{service,timer}` at ~12:30 UTC (~18:00 IST /
   ~22:30 AEST — after the BSE filing day) + add to `deploy.ps1 $TIMERS`.
5. Verify `india_aliases` — Pabrai files on BSE under fund-entity names; confirm the
   current legal names (e.g. is it "Pabrai Investment Fund II" / "Dhandho India Zero
   Fee Fund" / "The Pabrai Wagons Fund"?) before trusting the seed list.
6. `test_sast_monitor.py` with a saved fixture of a real BSE response (a few SAST
   rows including a non-matching one).

## Estimate

Medium — one `/execute`-sized chunk. The feed works, the pattern is a copy of
`edgar_monitor`, the only genuine unknown is the exact `india_aliases` strings
(step 5), which the build resolves by dumping a month of `Insider Trading / SAST`
acquirer names and eyeballing for Pabrai's entities.
