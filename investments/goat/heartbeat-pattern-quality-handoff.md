# Heartbeat Pattern Quality — Handoff

Separate from `.agent/plans/lse-heartbeat-universe.md` (which only widens the
*universe* of tickers scanned) — this handoff is about improving the *quality*
of `goat/heartbeat.py`'s `check_heartbeat_breakout` itself, the thing that
actually decides whether a ticker's base looks like a genuine heartbeat.

## Status: NOT BUILT — drafted 2026-10-01 from Shaun's request. Prompted by
Shaun sharing a detailed institutional-style "Heartbeat scanner" prompt
(Felix Prehn-style support/resistance/compression framework, written for an
LLM reading charts interactively) and asking whether it could improve the
current automated scan. Research-only pass so far — awaiting Shaun's manual
`/plan-feature` run against this doc before any code.

## Why This Exists

Shaun's own assessment of the current heartbeat scan: "hit and miss, mostly
misses." The scan flags candidates that quantitatively look like a tight,
smooth, multi-swing base, but a lot of them don't actually follow through.

Shaun's prompt (full text pasted into conversation 2026-10-01, not reproduced
here — see chat history) is a 15-section institutional pattern-scanner
framework meant for an LLM to read charts narratively (volume judgment,
weekly timeframe, catalyst/event risk, relative strength vs sector/market,
multi-stage scoring 0-100, qualitative "does this look clean" judgment).
**It is not a drop-in replacement for the current check** — running it
verbatim per-ticker across the ~500+ name daily universe would mean an LLM
call per ticker per day, which conflicts directly with this scan's whole
design point (cheap, pure-math, no LLM, runs over the whole index daily).
That's a separate, bigger architectural discussion (an opt-in "Stage 2" LLM
deep-read on survivors only, mirroring `checks/principles_fit.py`'s existing
Find-only LLM-opt-in pattern) — **explicitly out of scope for this handoff**.

This handoff extracts only the ideas from that prompt that are (a) cheaply
computable from data already available, (b) don't require a new data source
(no earnings calendars, no news, no chart images), and (c) plausibly explain
real misses given a honest read of what the current check actually measures.

## What `check_heartbeat_breakout` Currently Does (read `goat/heartbeat.py` in full)

Purely close-price-based (no volume, no OHLC — `price_history.fetch_close_history`
is close-only). Four gates, all on the most recent `GOAT_HEARTBEAT_MIN_DURATION_DAYS`
closes:

1. Base range tight (high-low as % of mean) below `GOAT_HEARTBEAT_BASE_RANGE_MAX_PCT`.
2. Base smooth (% of days inside an inner band around the mean) above
   `GOAT_HEARTBEAT_BASE_SMOOTHNESS_MIN_FRACTION`.
3. Not broken down (recent days haven't dipped below the settled/older part of
   the base's own low).
4. Real rhythm — at least `GOAT_HEARTBEAT_MIN_SWINGS` ZigZag-style confirmed
   up-down swings of >= `GOAT_HEARTBEAT_SWING_MIN_REVERSAL_PCT` each.

Sector-level relative strength is already handled upstream — `heartbeat_scan.py`
only feeds tickers from currently-rising sectors into this check at all.

**Two explicit, deliberate, documented prior decisions already baked into this
check** (both from `heartbeat.py`'s own module docstring, redesigned
2026-09-20, three revisions same day):

- No moving-average-relative gate of any kind. All were stripped out after
  causing bad results.
- No requirement that price be near/above the top of its range, let alone
  already broken out. Shaun explicitly wants the earlier, quieter entry —
  "he does not require the stock to have already broken out of its base --
  in fact he'd rather see it before it has."

**Either of these could be revisited** given the "mostly misses" feedback —
see Open Questions below — but they should be a conscious decision this plan
documents, not something quietly reversed by adding Shaun's new prompt's
preferences wholesale.

## What The Prompt Actually Offers That's Worth Taking

### 1. Volume — the single most likely real gap

The current check discards Volume even though `price_history.fetch_close_history`
calls yfinance's `.history()`, which already returns it in the same response —
it's being fetched and thrown away (confirmed pattern elsewhere in this
codebase — `mytrader/chart_setup_score.py`'s own docstring makes the identical
observation about a different close-only fetcher). A tight range with
*declining* volume is a real compression/accumulation signal; a tight range
with flat or rising volume may just be an illiquid or ignored stock sitting
still. This maps to the prompt's Section 5 (Volume Characteristics) and
Section M (false-breakout risk: "volume is weak" is its first listed
red flag).

**Proposed addition**: alongside the existing range/smoothness/swing checks,
compute whether volume over the base window is trending down (e.g., comparing
the base window's second-half average volume against its first-half average,
or a simple linear-regression slope sign) and report it as a new data field +
detail-string clause. Open question: report-only (`data["volume_declining"]`,
shown in the detail text) vs. an actual gate that can downgrade/reject an
otherwise-qualifying base. Recommend **report-only for v1** — same "don't
invent a new predictive claim without validating it first" discipline this
codebase already applies elsewhere (see
`.agent/plans/completed/matt-damon-price-volitility-volume-check.md` — a
near-identical price/volatility/volume signal that got built, backtested, and
found too weak to gate on). If Shaun wants it as a real gate, that should
follow a backtest the same way, not ship directly as a filter.

### 2. Invalidation level + reward:risk — report it, don't gate on it yet

The check already computes `base_low_settled` (the breakdown floor used for
the broke-down gate) and `base_high` internally — these just never reach the
report. Shaun judges and acts manually off the report; giving him a concrete
"if it goes below X, the thesis is wrong" level and a rough
reward:risk number costs nothing extra to compute (pure arithmetic on values
already in scope) and lets him filter weak setups himself before promoting a
candidate, matching the "report the fact, don't judge it" philosophy every
other check in this codebase already follows (`price_action.py`,
`technical_levels.py`).

Proposed fields: `invalidation_price` (= `base_low_settled`),
`resistance_price` (= `base_high`), `risk_per_share` (= current close −
invalidation), `reward_to_resistance` (= resistance − current close),
`reward_to_risk_ratio` (= reward ÷ risk, when risk > 0). Surfaced in the
detail string the same way every other number already is.

### 3. Position within the base's own range — report it, do NOT gate on it

The prompt strongly prefers candidates in the upper 75-100% of their range
(near resistance). The check already computes `pct_below_base_high` for
internal use (deciding the "already at/above the top" vs "no breakout yet"
detail text) — just promote it to its own labeled data field so it's easy to
scan across candidates in the report, without changing the actual
interesting/ok verdict logic. **Do not use this to gate or filter** — that
would reverse Shaun's explicit "I want the earlier, quieter entry" decision.
This is purely making an already-computed number more visible.

### 4. Weekly-trend context — open question, not a default

The prompt wants weekly-timeframe confirmation (price above major weekly
support, weekly trend constructive). This is cheaply computable — resample
the existing daily close series to weekly closes
(`close.resample("W").last()`) with zero new network calls — but it is
functionally a moving-average-relative trend gate, the exact category of
check this module explicitly removed on 2026-09-20 after it caused bad
results. **Do not add this by default.** Flagged as Open Question 1 below —
only build it if Shaun explicitly wants to revisit that removal, and ideally
backed by a look at what specifically went wrong with the old MA gates before
reintroducing a similar one in a new shape.

## Explicitly NOT Taken From The Prompt (and why)

- **Catalyst/event risk** (earnings dates, FDA decisions, etc.) — needs a new
  data source this codebase doesn't have wired up for Goat's universe-wide
  scan; a Find-only, single-ticker addition at most, not a daily-scan one.
- **Relative strength vs sector/market as a new check** — already functionally
  covered; `heartbeat_scan.py` only ever feeds currently-rising-sector tickers
  into this check in the first place.
- **The full qualitative scoring rubric, 0-100 Stage 1/Stage 2, "institutional
  quality" narrative judgment** — this is what an LLM reading a chart would
  produce, not what a pure-math function over close/volume series can produce
  without inventing a lot of arbitrary weightings. If Shaun wants this
  specifically, it's the separate "opt-in LLM Stage 2 deep-read on survivors"
  architecture flagged in the chat discussion, not this handoff.
- **Liquidity/bid-ask/slippage filters** — Goat's heartbeat scan has no
  liquidity floor at all today (confirmed precedent: the LSE universe plan's
  own Decision 4 treats index membership itself as the liquidity proxy,
  deliberately not adding one). Out of scope for a quality-of-check handoff;
  would be its own decision if ever revisited.

## Open Questions (resolve during `/plan-feature`)

1. **Weekly-trend gate: revisit the 2026-09-20 MA-gate removal, or leave it
   alone?** No default recommendation — this is Shaun's call given it
   reverses a documented prior decision made specifically because the old
   gates caused bad results. If yes, needs its own investigation into why the
   old gates failed before building a new one in the same spirit.
2. **Volume-declining: report-only or an actual new gate?** Recommend
   report-only for v1, mirroring the Matt Damon check's "ship info, backtest
   before gating" precedent — see that plan's own cautionary note about the
   Goat heartbeat "quiet base" BBW-percentile leg, which shipped an
   unvalidated gate and had to be redesigned after producing bad results for
   10 days.
3. **Does adding these fields change `goat_pending_candidates` schema**, or
   do they live purely in `CheckResult.data`/the rendered detail string
   without a DB migration? Recommend the latter for v1 (no new DB columns) —
   confirm during `/plan-feature` by reading `db.py`'s
   `insert_goat_pending_candidate`/`goat_pending_candidates` schema.
4. **Backtest the volume-declining signal before trusting it even as
   report-only?** Arguably report-only fields don't need the same bar as a
   gate, but if Shaun wants to eventually use it as a gate, the backtest
   should happen before that promotion, not after — same discipline as the
   Matt Damon check.

## Relevant Codebase Files — READ THESE DURING `/plan-feature`

- `investments/goat/goat/heartbeat.py` (whole file) — the function being
  extended. Read the module docstring in full; it is the direct record of
  why the MA gates and breakout requirement were removed.
- `investments/goat/goat/heartbeat_scan.py` — the caller; confirms where
  `close` comes from (`price_history.fetch_close_history`, close-only) and
  that sector-level relative strength is already a pre-filter.
- `investments/goat/goat/price_history.py` — the close-only fetcher. Needs a
  sibling/extended version that also keeps Volume (same pattern as
  `mytrader/chart_setup_score.py`'s own docstring describes for a different
  close-only-vs-OHLCV gap already fixed once in this codebase).
- `.agent/plans/completed/goat-heartbeat-quiet-redesign.md` — read in full.
  The direct cautionary precedent for shipping an unvalidated technical gate
  (the BBW-percentile leg) — this handoff's "report-only until backtested"
  posture for the volume signal exists specifically to not repeat it.
- `.agent/plans/completed/matt-damon-price-volitility-volume-check.md` — a
  near-identical price/volatility/volume signal, built, backtested, and found
  too weak to gate on (mean edge ~0.3pp, bearish side had none at all) —
  direct precedent for how to treat a plausible-sounding volume signal
  honestly rather than assuming it works.
- `investments/goat/goat/config.py` — `GOAT_HEARTBEAT_*` constants section,
  where any new threshold constants would go.
- `investments/goat/goat/tests/test_heartbeat.py` (if it exists — confirm
  filename) — existing test shape to mirror for new assertions.

## Validation (once built)

```powershell
uv run --directory investments/goat python -m pytest -q
```

Manual: run `scan-heartbeat` (via `invoke_investments.ps1`, never locally
against the real DB) and confirm the new fields (invalidation, resistance,
reward:risk, volume-declining flag, position-in-range) render sensibly in
`heartbeat-candidates-pending-review.md` for a handful of real candidates —
sanity-check the numbers against the actual chart for at least 2-3 names
before trusting the output.
