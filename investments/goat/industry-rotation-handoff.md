# Industry Rotation Ranking — Session Handoff

## Status: NOT STARTED — handoff drafted 2026-08-23. Awaiting Shaun's answers in
Open Questions below, then `/plan-feature` (Shaun's call to invoke, not automatic).

## What This Is

Extension of Goat's existing Phase 2 sector rotation (the 11 SPDR sector ETFs,
`goat/sector_rotation.py`, `sector-ranking.md`) down to **industry** granularity —
the ~130-150 finer-grained industry groups Finviz's screener uses (e.g.
"Semiconductors" and "Communication Equipment" as separate lines, rather than both
folded into "Technology"). Same philosophy as existing Goat work — this is not a
new package, it's a finer-grained sibling to the sector scan.

Prompted by Shaun sharing Finviz-style "Money Flowing IN/OUT — Top 5 Industries"
screenshots and asking whether this repo can produce the same thing.

## Context (corrections made during scoping, captured here so a fresh session doesn't re-litigate them)

- **The screenshots are price performance, not real $ fund-flow data.** No data
  source in this stack (or realistically available for free) reports actual ETF
  creation/redemption dollars by industry. "Money flowing in/out" is Finviz's
  plain-English label for "price rose/fell over the period" — same proxy Goat's
  existing sector ranking already uses.
- **Volume is not the right metric for direction.** Shaun's original framing asked
  to rank by volume; corrected in conversation — trading volume measures activity,
  not direction (it rises on both rallies and crashes). Price % change over a
  lookback window is the correct metric, matching what the screenshots actually
  showed and what `sector_rotation.py::rank_sectors()` already does for sectors.
- **Confirmed decisions (2026-08-23):**
  1. On-demand chart command per industry (e.g. "show me Semiconductors chart"),
     not an interactive dashboard — Shaun's explicit call, can pivot to something
     more sophisticated later if this proves insufficient.
  2. "What each industry is valued at each day" = a normalized index level (rebased
     to 100 at the start of whatever window is charted) so a chart shows real
     trend, not just a single %-change number.
  3. **Industry ETFs only** — no individual-stock constituent aggregation. Shaun's
     explicit call; full industry coverage is a known tradeoff of this decision
     (see Phase 1 below).

## Design direction (recommended, not yet built)

- **Reuse, don't reinvent.** `sector_rotation.py`'s `fetch_all_sector_closes()` +
  `rank_sectors()` is exactly the model — same `price_history.fetch_close_history()`
  yfinance sourcing, same rank-by-%-return-over-a-window logic, same
  ticker→label config dict shape as `GOAT_SECTOR_ETFS`. The industry version is a
  wider ticker universe through the same pipeline, not new logic.
- **Likely no new DB table needed.** Unlike Goat's constituent-scan features (S&P
  500 heartbeat scanner, insider scan), which persist candidate rows because
  there's no other record of what they found, a pure ETF-based ranking + chart can
  probably just re-fetch yfinance's own historical daily close series on demand —
  it already serves arbitrary-length history for any ETF ticker, same as
  `fetch_close_history()` does today for the sector ranking window. "Tracking daily
  value" would then mean *re-deriving* the rebased index from that history at
  request time, not accumulating our own daily snapshot rows. Flagged as an open
  question below in case Shaun wants Goat to keep its own independent daily log
  instead (e.g. resilience against yfinance history-window limits or ETF ticker
  changes over time) — recommended default is live re-fetch, simpler and no new
  storage.

## Remaining Steps

### Phase 1 — Industry ETF universe (the real work — needs actual research, not a guessed list)

- Build `GOAT_INDUSTRY_ETFS: dict[str, str]` (ticker → industry label) in
  `goat/config.py`, same shape as the existing `GOAT_SECTOR_ETFS`.
- No single source maps 1:1 onto Finviz's ~130-150 industries. Industry-specific
  ETFs exist scattered across State Street SPDR, iShares, VanEck, Invesco, First
  Trust and others, but coverage is partial — plenty of narrow Finviz industries
  (e.g. "Coking Coal") have no dedicated ETF at all. This needs a real research
  pass to build a defensible starting list, same discipline the Goat "heartbeat"
  threshold work was held to — don't invent/guess a list and ship it.
- Decide up front: an industry with no ETF match gets **left out with a visible
  gap note** ("N industries not covered — no ETF available"), not silently
  substituted with a broader/looser proxy that would misrepresent what's actually
  being measured. This is the recommended default, not yet confirmed with Shaun.

### Phase 2 — Ranking report

- New `industry_rotation.py`, modeled directly on `sector_rotation.py`'s
  `fetch_all_sector_closes()` + `rank_sectors()`.
- Output: `investments/goat/industry-ranking.md` — top 5 gaining / worst 5 losing
  by price return over the lookback window, mirroring the screenshot layout and
  `sector-ranking.md`'s existing `Rank | Ticker | Industry | Return | Rising`
  columns. Consider including the full ranked list below the headline top/bottom 5
  (see Open Questions).
- Window length: the screenshots used 6 months; Goat's existing sector window is
  `GOAT_SECTOR_RANK_WINDOW_TRADING_DAYS` (~3 months). Not yet decided which (or
  both) applies here — see Open Questions.
- Cadence: daily, same as Goat Monitor's existing sector scan — cheap, bounded
  ticker universe (not a market-wide scan like the S&P 500 heartbeat scanner).

### Phase 3 — On-demand chart command

- New on-demand trigger, e.g. a CLI subcommand
  (`-Package goat -Command "chart-industry --industry Semiconductors"`) or purely
  conversational (same precedent as the ad hoc LULU 50/150-day-MA chart already
  produced once in conversation, referenced in `goat/HANDOFF.md`).
- Pulls the mapped ETF's historical daily close series via
  `price_history.fetch_close_history()`, rebases to 100 at the start of the
  requested window, renders a chart.
- Exact rendering mechanism (a generated file vs. fully ad hoc/conversational) is
  an implementation-time decision — no existing built-command precedent to match,
  only the one-off manual chart already done.

## Explicitly deferred (do not build as part of this handoff)

- Constituent-stock aggregation for full industry coverage — Shaun's explicit call
  (2026-08-23) was ETFs only; revisit only if ETF coverage proves too thin to be
  useful in practice.
- Real $ fund-flow data (ETF creation/redemption) — no source exists in this
  stack; price performance is the proxy, same as what the original screenshots
  almost certainly used.
- Any dashboard/interactive UI — on-demand chart command only, per Shaun's
  explicit "start simple, pivot later if insufficient" call.
- Any buy/sell opportunity-style verdict layered on top of the ranking — this
  handoff is the ranking + chart only, not a new Goat signal/candidate type
  (unlike Phase 2 sector rotation's breakout check, which does emit a candidate).
  Worth asking Shaun later whether an industry-level breakout signal is wanted
  too, but it is not scoped here.

## Validation (once built)

```powershell
uv run --directory investments/goat python -m pytest -q

# On the VPS via invoke_investments.ps1, per investments/TOOLS.md convention —
# never run a package locally against the real DB:
.\scripts\invoke_investments.ps1 -Package goat -Command "scan-industries"
.\scripts\invoke_investments.ps1 -Package goat -Command "chart-industry --industry Semiconductors"
```

## Open Questions for Shaun (resolve during `/plan-feature`)

1. **Ranking window length** — 6 months (matches the screenshots) vs. Goat's
   existing 3-month sector convention, or support both/make it configurable.
2. **Own daily-snapshot table vs. live re-fetch from yfinance at chart time** —
   recommended default is live re-fetch (simpler, no new DB table); confirm that's
   acceptable rather than assumed.
3. **Industry ETF universe curation** — needs a dedicated research pass; confirm
   the leave-out-with-gap-note approach for industries with no ETF match, rather
   than a looser substitute.
4. **Report shape** — top 5/bottom 5 only (matches the screenshots) vs. a full
   ranked list of every covered industry, with top/bottom 5 as just the headline.
5. **Chart trigger mechanism** — a real CLI subcommand vs. purely
   conversational/ad hoc, same as the one-off LULU chart already done.
