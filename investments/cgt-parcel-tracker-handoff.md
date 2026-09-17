# CGT Parcel Tracker (IBKR → accountant CGT report) — Session Handoff

Tool name: **CGT Parcel Tracker**. Proposed package dir `investments/cgt-parcel-tracker/`,
Python module `cgt_parcel_tracker` (dir-name = module-name convention, matching
`fourteen-crash-signals-daily-check` / `superinvestor-filings` /
`ai-resistant-moat-scanner`). CLI: `python -m cgt_parcel_tracker.main report --flex <file> --fy 2025`.

## Status: NOT BUILT — drafted 2026-09-10 from Shaun's request + his accountant's reply. Awaiting Shaun's manual `/plan-feature` run against this doc before any implementation.

## What This Is

Shaun's accountant confirmed that when he sells part of a share holding he can elect
**FIFO / LIFO / weighted-average** for the cost base of the shares sold, and said:
*"It is important to document your election (and keep records of the cost base of the
remaining shares for future sale events)."*

Shaun has full trade history in Interactive Brokers but no system for tracking parcels
or cost base. This tool:

1. Reads Shaun's **IBKR trade history** (Flex Query export — see "Input" below; NOT the
   live IB Gateway socket that `mytrader/ibkr_sync.py` uses).
2. Runs a **CGT parcel-matching engine** over every buy/sell of every holding, in AUD,
   under all of FIFO, LIFO, weighted-average, **and per-disposal specific
   identification**.
3. Produces, per Australian financial year (1 Jul – 30 Jun):
   - a **CSV** of every CGT event (disposal) with matched parcels, cost base, proceeds,
     brokerage, gross gain/loss, 12-month-discount eligibility, and net gain/loss;
   - a **CSV** of the **remaining-parcels ledger** as at 30 June (exactly what the
     accountant asked to keep records of);
   - a **CSV** method-comparison summary (total net capital gain under each method);
   - a **PDF** pack for the accountant containing the same tables plus a one-page
     **election statement** for Shaun to sign and date (the "document your election"
     step).

Advisor-mode / records only. This is **not tax advice** — it computes under clearly
stated assumptions and the accountant validates. Every output carries that disclaimer.

## Is LIFO actually better? (Shaun asked — short answer: don't pre-commit to it)

**Not automatically, and possibly the opposite, in Australia.** The reasoning:

- **The 50% CGT discount dominates.** An individual gets a 50% discount on a capital
  gain from an asset held **more than 12 months**. LIFO sells the *newest* parcels
  first — the ones least likely to have passed 12 months — so LIFO tends to make the
  sold portion **fully taxable** while parking your oldest, discount-eligible parcels
  for later. FIFO does the reverse: it burns the discount-eligible parcels first but
  gets the discount on this year's gain. Which is better depends entirely on the price
  path and the holding dates, not on a general rule.
- **LIFO minimises the *gross* gain only in a rising market** (newest parcels have the
  highest cost). In a falling market LIFO *maximises* the loss you realise now, which
  may or may not be what you want.
- **You almost certainly have a better option than any of the three defaults.**
  The ATO's actual position (TD 33 / "Identifying when shares are acquired") is: if you
  **can identify** which specific shares you sold, you use *that* (specific
  identification); FIFO is the fallback for when you genuinely can't distinguish them;
  weighted-average is only accepted in limited circumstances. Because Shaun has
  complete IBKR records, he can **nominate the exact parcel each sale draws from, per
  sale** — choosing for each disposal whether to take the smallest gain, realise a
  loss to offset other gains, or reach for a >12-month parcel to get the discount.
  FIFO/LIFO/weighted-average are just what you fall back to if you don't nominate.
- **Consistency constraint:** once a holding has been reported on a given basis you're
  expected to stay consistent for that holding. So the *first* year's choice per
  holding matters, and the tool must persist it and carry the ledger forward.

**After 1 July 2027 the calculus shifts** (see next section): with the 50% discount
gone and replaced by cost-base indexation + a 30% minimum rate, holding period stops
mattering the way it does now, and the only remaining lever on a disposal is
minimising the (indexed) gross gain or realising a useful loss. In a rising market
that favours the highest-cost parcels — i.e. LIFO, or better, specific-ID picking the
highest-cost lots. So Shaun's LIFO instinct becomes *more* right for post-2027
disposals, but specific identification still dominates it (specific-ID can always
replicate the LIFO choice and also do better).

**Recommendation for the tool:** model all four approaches, show Shaun + the accountant
the side-by-side FY outcome, let them pick (specific-ID where it helps, otherwise a
consistent method per holding), record whatever is chosen, and carry the
remaining-parcels ledger forward so next year is consistent. Don't hard-code LIFO.
The method choice should be re-evaluated for FY2028+ once the discount is gone.

Flag this to Shaun in the eventual SKILL.md too — the "LIFO is better" instinct is a
US rule-of-thumb that doesn't survive contact with the AU 12-month discount (until
1 July 2027).

## CGT regime change — 1 July 2027 (the discount treatment MUST be date-parameterised)

Legislated 26 June 2026 (Treasury Laws Amendment (Tax Reform No. 1) Act 2026), effective
for **CGT events on or after 1 July 2027**:

- The general **50% CGT discount** for individuals / trusts / partnerships is
  **abolished**.
- Replaced by **CPI cost-base indexation** (real gain only is taxed) **plus a 30%
  minimum tax rate** on the net capital gain (a top-up applies if the taxpayer's
  marginal rate on the gain is below 30%).
- **Transitional apportionment for assets held on 1 July 2027 and sold later:** the
  gain is split into a pre-1 July 2027 slice (old rules — 50% discount if held >12
  months) and a post-1 July 2027 slice (indexation from 1 July 2027 + 30% floor). The
  split is done off the asset's **market value at 1 July 2027** (obtained by valuation
  or an ATO-approved apportionment method — sources differ on the exact default and
  **ATO guidance is still pending**).

Design implications:

1. The discount / indexation / min-rate treatment is a **function of the CGT event
   date**, driven by a small config table, not hard-coded. Whatever the final ATO
   apportionment rule turns out to be, it's a config/plug-in, not a rewrite.
2. **v1 scope should be FY2025 – FY2027** (pre-change; clean 50%-discount rules). The
   post-1 July 2027 bifurcated calculation is a **documented follow-up** once ATO
   guidance lands — see "Explicitly deferred".
3. **Record the market value of every open holding as at 1 July 2027** regardless —
   the tool should emit that snapshot as a dated CSV even in v1, because it's needed
   for every future disposal of a currently-held parcel and is far easier to capture
   now than reconstruct later.
4. **Planning angle worth surfacing to the accountant:** there may be a case to realise
   gains on long-held, low-cost parcels **before 30 June 2027** while the full 50%
   discount still applies. The tool's multi-year method-comparison output (run for
   FY2026 and FY2027) is exactly the artefact that conversation needs — call this out
   in the summary, don't make a recommendation.

## Input — IBKR data source

Use an **Activity Flex Query** (Account Management → Reports → Flex Queries), exported
as **XML** (preferred) or CSV, NOT the live `ib_async` socket. Reasons:

- CGT needs the **complete history** from the first-ever purchase of every holding that
  was still open at the start of the period or sold during it — the socket API only
  returns current positions and recent activity.
- Flex Queries are configurable to include exactly the sections needed and can span
  multiple years in one export.

Flex sections to request (confirm exact field names against a real export during
`/plan-feature` — IBKR's Flex schema is stable but verbose):

- **Trades** — `symbol`, `assetCategory` (filter to `STK`), `tradeDate` (this is the
  contract date = CGT event date, correct per s104-10), `buySell`, `quantity`,
  `tradePrice`, `ibCommission`, `currency`, `fxRateToBase` (present per-row **if IBKR
  base currency is set to AUD** — see FX below), `conid`.
- **Corporate Actions** — splits, consolidations, mergers, spin-offs, in-specie
  distributions. The engine **cannot** infer these from trades alone.
- **Cash Transactions / Transfers** — return-of-capital, DRP share issues, ACATS/
  account transfers in (parcels acquired elsewhere carry their original cost base and
  date).

If a section isn't in the export, the run must **stop with a clear message**, not
silently produce a wrong cost base.

## FX — the biggest complexity

Shaun's IBKR account is almost certainly USD-denominated. The ATO requires **each
element of the cost base and the capital proceeds translated to AUD**: cost base at the
rate on the **acquisition** date, proceeds at the rate on the **disposal** date (an
average rate is permitted in limited cases if used consistently — accountant's call).
A USD-flat trade can be an AUD gain or an AUD loss purely on currency movement, so this
is not optional.

Two paths, decide in `/plan-feature`:

1. **Let IBKR stamp the rates.** If Shaun sets his IBKR **base currency to AUD**, Flex
   trades carry `fxRateToBase` per row and IBKR reports AUD values directly. Simplest,
   but (a) changing base currency doesn't retro-stamp historical trades and (b) the
   accountant should confirm IBKR's rate source is acceptable to the ATO.
2. **Independent FX table (recommended default).** Pull **RBA daily AUD/USD** (and any
   other traded currency) from the RBA's historical exchange-rate CSVs (F11 series,
   free, no key, daily back to 1983). Cache locally. Use the prior business day's rate
   for weekends/holidays, and document that rule (mirrors the
   [[feedback_check_interpretation_convention]] "spell out the rule" standard). Also
   support the **ATO annual average rates** as an alternative mode.

## Cost base / proceeds rules the engine must get right (document each precisely)

- **Brokerage on buy** → added to the parcel's cost base (2nd element, s110-25).
  **Brokerage on sell** → reduces capital proceeds. IBKR reports `ibCommission`
  per trade (negative). Include GST-inclusive amounts as charged.
- **12-month discount day-count** — CGT event must occur **more than 12 months** after
  acquisition (exclude the acquisition day; dispose on or after acquisition-date + 366
  days is the safe reading). Pick one precise rule, document it, expose it as config.
  The discount **rate/regime is itself keyed on the CGT event date** (50% up to
  30 Jun 2027; indexation + 30% floor from 1 Jul 2027 — see the regime-change section).
- **Loss/gain netting order** — current-year capital losses and carried-forward losses
  offset the **gross** gain *before* the 50% discount is applied. The comparison
  summary must reflect real post-discount, post-loss outcomes, not raw gross gains.
- **CGT event date = trade/contract date**, not settlement date.
- **Same-day multiple fills** — IBKR often splits one order into many fills. Decide
  whether to aggregate same-day same-price(-ish) fills into one parcel (cleaner ledger)
  or keep every fill (exact). Probably aggregate, but keep the fill detail in an
  appendix CSV.
- **Wash sales** — if a loss-generating sale is followed by a re-purchase of the same
  holding within ~30 days, **flag it** (TA 2008/7 anti-avoidance). Never silently
  optimise a disposal into a wash-sale position.

## Out of scope for the engine / needs manual input (`adjustments` file)

Corporate actions and anything the trade feed can't express go in a committed,
human-readable `adjustments.yaml` (or `.md`) that the engine reads:

- Splits / consolidations (adjust qty + per-share cost base of affected parcels).
- Mergers / takeovers / scrip-for-scrip rollovers (s124-M) — cost base transfers,
  sometimes with rollover relief the taxpayer elects.
- Spin-offs / demergers — cost base apportionment between parent and spun entity.
- Return of capital — reduces cost base, or triggers a gain if it exceeds cost base.
- DRP — each reinvested dividend is a **new parcel** at the market price used, with its
  own acquisition date.
- Parcels transferred in from another broker — original cost base + original date.
- Specific-identification nominations, per disposal, when Shaun wants them.

The engine applies these deterministically from the file; it does **not** try to
auto-detect a merger from a ticker vanishing.

## Explicitly deferred (do not build as part of this handoff)

- **Dividends / franking credits** — that's income, not CGT; the accountant handles it
  from IBKR's dividend report. This tool is disposals + cost base only.
- **Non-individual entities** — the 50% discount is individuals/trusts; companies get
  no discount, SMSFs get 1/3. v1 assumes Shaun holds personally. Confirm (Open Q 1);
  if it's a company/trust/SMSF the discount rate is a config value, not a rewrite.
- **Post-1 July 2027 disposals of pre-1 July 2027 parcels** — the bifurcated
  pre/post-27 split (market-value snapshot + CPI indexation + 30% floor). Build this
  only once ATO guidance on the apportionment method is published; v1 stops at
  FY2027. The date-parameterised regime table is the seam it plugs into. v1 still
  emits the 1 July 2027 market-value snapshot CSV so the data exists when this is built.
- **Options, futures, CFDs, forex P&L** — `assetCategory != STK` is filtered out.
  IBKR forex conversions are not CGT events for a share investor in the ordinary case
  but note them; don't model them.
- **Anything that places trades or touches the shared `investments.db`.** This tool is
  self-contained and local (see below).
- **Auto-lodgement / pre-fill / myTax integration** — output is for the accountant, who
  lodges.
- **Real-time / scheduled runs, VPS, WhatsApp** — run a handful of times a year,
  on-demand, locally.

## Recommended shape (confirm in `/plan-feature`)

- **New uv-workspace member** `investments/cgt-parcel-tracker/`, added to
  `investments/pyproject.toml` `[tool.uv.workspace] members`. **No dependency on
  `my-trader`** (would drag in briefs-finance / ib_async / pdfplumber for almost no
  reuse) — if ticker normalisation is needed, copy the few lines or add a narrow dep.
- **Local only. Does NOT use `investments.db`.** Keeps its own local SQLite
  `cgt_parcels.db` (parcel ledger + recorded elections), **gitignored** — it holds
  Shaun's complete financial history. The manual `adjustments.yaml` / `elections.md`
  *is* committed (small, reviewable, no position sizes required if kept to ratios/dates).
  Alternative: fully stateless, recompute from the full Flex history every run + the
  committed adjustments file, no DB. Decide based on whether Shaun wants an
  incrementally-maintained ledger or a clean recompute each year.
- **No systemd unit, no Task Scheduler entry, no `maybe_notify`.** Nothing added to
  `monitor.py` or `scripts/systemd/`.
- **PDF generation**: no PDF library exists in the investments workspace today. v1 =
  CSV + a Markdown summary + an HTML election statement. v1.1 = add a light dep
  (`fpdf2` or `reportlab`; avoid `weasyprint` — heavy/fragile on Windows) to render the
  accountant PDF, or hand the HTML to the repo's existing `pdf` skill. Confirm the
  accountant even wants PDF or is fine with CSV + a signed election page.
- **Outputs** land in `investments/cgt-parcel-tracker/reports/FY<year>/` (gitignored):
  `cgt-events.csv`, `remaining-parcels.csv`, `method-comparison.csv`,
  `fill-detail.csv`, `cgt-summary.md`, `election-statement.html` (+ `.pdf` at v1.1),
  and a one-off `market-value-2027-07-01.csv` (open-holding valuations at the regime-
  change date — emit whenever the run covers a period that includes open parcels held
  across 1 July 2027).

## Open Questions for Shaun (resolve during /plan-feature)

1. **Which legal entity holds the IBKR account** — Shaun personally, a company, a
   trust, or an SMSF? Sets the discount rate (50% / 0 / 50% / 33.3%) and some rules.
2. **How many IBKR accounts / any joint accounts?** Joint holdings split the CGT event
   between owners by their interest share.
3. **How far back does the history need to go** — i.e. what's the earliest still-held or
   since-sold parcel? Determines the Flex Query date range (may need several exports
   stitched).
4. **First year to report** — just the most recent completed FY (2024–25), or a catch-up
   across several prior years at once?
5. **FX approach** — set IBKR base currency to AUD and trust its `fxRateToBase`, or
   independent RBA daily rates (recommended), or ATO annual average rates? Accountant
   should weigh in.
6. **Method policy** — does Shaun want the tool to *recommend* the lowest-tax outcome
   per FY, or just present the options neutrally and let the accountant choose? (Advisor
   mode leans neutral-present.)
6a. **Method scope (ask the accountant):** one documented method portfolio-wide, one
   method per holding, or specific identification per disposal where it helps? Tax law
   doesn't force a single portfolio-wide election for shares (ATO TD 33 is about
   identifying the specific shares sold), but the accountant may want one method for
   defensibility. Convention is consistency *within* a holding over time. This answer
   defines what "document your election" produces.
6b. **Pre-30-June-2027 gain realisation** — does Shaun want the FY2026/FY2027
   comparison output to explicitly model "what if I sold parcel X before the discount
   ends" scenarios, or just report actual trades?
7. **Any corporate actions in his holdings' history** — splits, takeovers, spin-offs,
   DRP, return of capital, broker transfers? Each needs an `adjustments.yaml` entry.
8. **PDF or not** — does the accountant want a formatted PDF pack, or are CSVs + a
   signed one-page election statement enough?
9. **Ledger vs. stateless** — maintain `cgt_parcels.db` incrementally year to year, or
   recompute from the full Flex export every run?
10. **Confirm with the accountant before build**: (a) that specific identification per
    disposal is acceptable to them given full IBKR records, and (b) their preferred FX
    rate source. These two answers change the engine's defaults.

## Reference code already in the repo (reuse the patterns, not necessarily the code)

- `investments/my-trader/mytrader/ibkr_sync.py` + `ibkr-sync-handoff.md` +
  `ibkr-setup-guide.md` — IBKR integration precedent and the SOUL.md read-only
  clarification (2026-08-11: read-only account access is in scope; this tool reads
  exported files, even further from the trading boundary). **Different input path** —
  that tool uses the live socket, this one parses Flex exports.
- `investments/my-trader/mytrader/checks/` + `snapshot.py` — the "pure function over
  plain data, real I/O isolated at one boundary" style to copy for the parcel engine
  (engine = pure; Flex parsing + FX fetch = the only I/O).
- `investments/my-trader/mytrader/abs_cpi.py` / `ons_cpi.py` — existing pattern for
  fetching + caching an external statistical series (here: RBA F11 FX CSVs).
- `investments/my-trader/mytrader/cash_value_scan.py` + the TOOLS.md "how it works +
  tuning" section — the ranked-CSV/Markdown advisor-output shape, config-knob table,
  and STALE/DEGRADED banner discipline.
- `.claude/skills/pdf/SKILL.md` — fallback path for HTML→PDF if a Python PDF dep is
  not added.
- `investments/briefs-finance/scripts/config.py` — env/config layout for a
  workspace member.

## Deployment / integration notes

- Add `cgt-parcel-tracker` to `investments/pyproject.toml` workspace members.
- Add `investments/cgt-parcel-tracker/reports/` and `**/cgt_parcels.db` to
  `.gitignore`.
- Do **not** add anything to `scripts/systemd/`, `scripts/setup_scheduler_windows.ps1`,
  `scripts/invoke_investments.ps1` (VPS-only wrapper — this tool is local and DB-free),
  or `monitor.py`.
- After building: add a **Manual / on-demand** row to `investments/TOOLS.md` only
  (not Automated, not Daily Read), and a short SKILL.md under
  `.claude/skills/cgt-parcel-tracker/` if Shaun wants a conversational trigger
  ("run my CGT report", "generate the share report for my accountant").
- New plan file will be `.agent/plans/cgt-parcel-tracker.md` (Shaun runs
  `/plan-feature`, per [[feedback_plan_feature_user_only]]).

## Validation (once built)

```powershell
uv run --directory investments/cgt-parcel-tracker python -m pytest -q

# on-demand run (exact flags TBD in /plan-feature)
uv run --directory investments/cgt-parcel-tracker python -m cgt_parcel_tracker.main `
    report --flex path\to\ibkr-flex.xml --fy 2025 --adjustments path\to\adjustments.yaml

# expected outputs under investments/cgt-parcel-tracker/reports/FY2025/
#   cgt-events.csv  remaining-parcels.csv  method-comparison.csv
#   fill-detail.csv  cgt-summary.md  election-statement.html
```

Test with hand-built fixtures covering: the accountant's own worked example (1000 @ $10,
1000 @ $13, sell 1700) under each method; a parcel straddling the 12-month boundary; a
USD trade where AUD FX flips the sign of the gain; brokerage on both legs; a carried-
forward capital loss; a same-day multi-fill order; a wash-sale re-purchase.

## Worked example (the accountant's own numbers — sanity check for the engine)

Buy 1000 @ $10 (parcel A), buy 1000 @ $13 (parcel B), later sell 1700. Ignoring
brokerage and FX, proceeds allocated pro-rata to matched parcels:

| Method | Parcels matched to the 1700 sold | Cost base of sold shares |
|---|---|---|
| FIFO | 1000 × A ($10) + 700 × B ($13) | $10,000 + $9,100 = **$19,100** |
| LIFO | 1000 × B ($13) + 700 × A ($10) | $13,000 + $7,000 = **$20,000** |
| Weighted avg | 1700 × $11.50 | **$19,550** |

Remaining 300 shares carried forward: FIFO → 300 × B @ $13 ($3,900); LIFO → 300 × A @
$10 ($3,000); weighted-avg → 300 × $11.50 ($3,450). The discount outcome then depends
on each matched parcel's acquisition date, which is the whole point of tracking parcels
rather than a running average.

## Disclaimer to embed in every output

> This report is a record-keeping aid generated from IBKR trade data under the cost-base
> method and assumptions stated in its header. It is not tax advice. Cost base, CGT
> discount eligibility, FX treatment, corporate-action adjustments and loss offsets must
> be reviewed and confirmed by a registered tax agent before lodgement.
