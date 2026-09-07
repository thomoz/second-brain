# India / SEBI SAST Leg (Phase 5) — Findings Note

## Status: NOT BUILT — spike pending Shaun's sign-off

Phase 5 of `.agent/plans/superinvestor-filings-scanner.md` is gated behind Task 5.1,
a spike that must confirm a **no-login, machine-readable** SAST Regulation 29 daily
feed on NSE or BSE before any parser is written. That spike has **not** been run —
it needs live network verification against actively bot-hostile endpoints, and the
plan's STOP CONDITION says not to build a browser-session scraper without Shaun's
sign-off.

## Why the India leg matters

Pabrai's largest single positions have historically been Indian (Rain Industries,
Sunteck Realty, etc.) via the Foreign Portfolio Investor route. Those holdings
**never touch SEC EDGAR**, so the EDGAR-only v1 has a real blind spot for this exact
filer. SEBI SAST Reg 29 is also better granularity than the US 13G once past 5%:
Reg 29(1) = 5% crossing within 2 working days; Reg 29(2) = every ≥ 2% change (up or
down) past 5% within 2 working days.

## Candidate feeds to verify (starting points, not confirmed)

- **NSE** — `https://www.nseindia.com/companies-listing/corporate-filings-insider-trading`
  ("System Driven Disclosures (SAST)"). Has a CSV download in the browser. NSE blocks
  non-browser User-Agents and requires priming a `requests.Session` with a
  `GET https://www.nseindia.com` first to obtain cookies. Use a browser-like UA
  (`sast_monitor.SAST_USER_AGENT`), never `config.SEC_USER_AGENT`.
- **BSE** — `https://www.bseindia.com/corporates/Regulation_29.aspx` and
  `https://www.bseindia.com/corporates/Sast.html`. BSE has historically been more
  scraper-tolerant than NSE.
- **Secondary** — BSE/NSE bulk-deal (> 0.5% of a company's shares in a day) and
  block-deal EOD files name the client; a same-day signal but not filer-scoped the
  way SAST is. Deferred (plan NOTES #8).

## What "build it" looks like once a feed is confirmed

`sast_monitor.py` becomes structurally parallel to `edgar_monitor.py`:

1. `fetch_sast_disclosures(session_date) -> list[dict] | None` — fetch the daily list.
2. `scan_india(conn)` — for each row, case-insensitive substring match the acquirer
   name against each tracked investor's `config.SUPERINVESTOR_TRACKED[key]["india_aliases"]`
   (any match), `build_dedup_key("sast", filer_key, "SAST Reg 29(x)", issuer, exchange_ref)`,
   `db.insert_superinvestor_filing_seen(..., source="sast")`, build an alert dict.
   Reg 29(2) rows carry a `pct_change` — surface it.
3. Wire `main.cmd_scan`'s `run_india` default to `True` (currently `--india-only` opt-in).
4. Add `second-brain-superinvestor-sast.{service,timer}` at ~12:30 UTC (~22:30 AEST)
   and to `deploy.ps1 $TIMERS`.
5. Verify + update `india_aliases` with the fund entities' current BSE/NSE names.
6. Commit a saved fixture of a real feed response for `test_sast_monitor.py`.

## Also verify during the spike

The `india_aliases` seed (`"pabrai investment fund"`, `"dalal street"`, `"dhandho"`)
is a guess. Pabrai's fund entities have been renamed over the years — confirm the
current legal names they file under on BSE/NSE.
