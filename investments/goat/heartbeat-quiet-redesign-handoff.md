# Goat Heartbeat Scanner — "Quiet" Redesign — Session Handoff

## Status: IMPLEMENTED 2026-08-26 — see `.agent/plans/goat-heartbeat-quiet-redesign.md` (planned then executed same day; four open questions for Shaun resolved there). `heartbeat.py` rewritten (direct base-range % + inner-band smoothness + 50/150-day-MA position filter; `bollinger_width_series` / `_is_in_squeeze` and the four `GOAT_HEARTBEAT_BBW_*` constants removed). 208/208 goat tests pass. Remaining: a real `scan-heartbeat` run on the VPS (Level 4) before the weekly timer is trusted/enabled. The rest of this doc is the historical diagnosis record.

## One-line summary

The heartbeat scanner (`investments/goat/goat/heartbeat.py`) has flagged **zero
candidates on every run since it shipped 2026-08-17**. Diagnosis below shows this is
not a quiet market — the "has this stock been quiet?" leg is structurally unable to
pass, because it measures quietness in a history-hungry, indirect way and the tool
does not download enough history to feed it. Shaun's proposed fix: replace the
volatility-percentile method with a **direct recent-range measure plus a 50-day /
150-day moving-average position filter** — closer to how the pattern is read off a
chart by eye.

## The finding (diagnostic run 2026-08-26)

A read-only diagnostic (no DB) ran `check_heartbeat_breakout` over 42 large S&P names
spread across all 7 currently-rising sectors. Script is reproduced at the bottom of
this doc.

- **Every name got exactly 343 trading days** of history from yfinance for the
  configured 500-calendar-day fetch.
- **Only 73 of those 343 days carry a valid "quiet" reading.** The other 270 are
  force-stamped "not quiet" because the trailing-252-day percentile yardstick can't be
  computed yet (`_is_in_squeeze`'s `.fillna(False)`).
- The quiet leg needs **63 valid days in a row, all landing in the ~2 weeks before the
  breakout cross.** With only 73 valid days total, that window barely fits when the
  cross is at the very end of the series and falls partly into the force-stamped zone
  otherwise.
- The resulting quiet score (`squeeze_fraction`, needs ≥ **0.80**): **0.00 for 27 of
  42 names**, sample max **0.25** (AXP). The 3 names that passed both breakout legs
  (fresh 50DMA cross-up + rising 50DMA) — DE, EQIX, WELL — scored **0.00 / 0.22 /
  0.00**.
- **`interesting`: 0 of 42.** Consistent with the live scanner: empty table on every
  run 2026-08-17 → 2026-08-26.

### Why it happens (the design choice, in plain terms)

The scanner turns "quiet" into a number — how wide the price's recent up/down swing
range is — then defines quiet as *"today's swing range is in the calmest 10% of days
compared to this stock's own previous full year."* That "compared to its own previous
year" anchor is what forces the history requirement:

- 1 trading year (252d) to build the yardstick
- + ~3 months (63d) of quiet before the breakout
- + 20d Bollinger warm-up + up to 10d of cross-recency slack
- ≈ **345 trading days minimum just to compute**, before there's any usable margin.

500 calendar days = ~343 trading days. The Phase 3 plan's GOTCHA (line ~222) asserted
"500 calendar days is comfortable margin, don't shrink it" — **that estimate was
wrong.** It is ~2 days short in the best case and leaves only 73 usable days where the
63-day pre-cross window needs to land.

### This clears the Phase 3 plan's bar for revisiting the metric

`.agent/plans/completed/goat-phase3-heartbeat-scanner.md`'s "RESEARCH RESOLVED …
BINDING" section says BBW-percentile-vs-VCP should not be revisited *"without equally
real justification (e.g. a manual validation run showing BBW-squeeze is producing
obviously wrong candidates against real charts)."* A validation run showing **zero
candidates across the entire S&P 500 for 10 straight days, with the quiet score pinned
near 0.00 for 42 of 42 hand-picked names**, is that justification. The redesign below
is in scope.

## Proposed redesign (Shaun's direction — validate during `/plan-feature`, don't treat as decided)

Replace the percentile-anchored squeeze with a **direct, recent-window** definition of
the heartbeat base:

1. **Sideways / narrow range** — the price has stayed inside a tight band for the base
   window (~3 months min, per the webinar). Measured directly against the recent past,
   not a trailing year. Candidate measures to research/pick one: high-low range over
   the window as a % of price; price held within ±X% of its own moving average for
   most of the window; or BBW below a *fixed* threshold (not a self-percentile).
2. **Position of strength** — during the base, price is **near or above both the
   50-day and 150-day moving averages**, and those averages are **flat-to-rising, not
   falling.** The current heartbeat check looks at the 50-day line only and ignores
   the 150-day line entirely, even though the 150-day line is central to the rest of
   Goat (the Phase 1 exit alert). "Near or above" needs a tolerance — the webinar's
   own exit rule explicitly allows brief dips through the 150.
3. **Breakout** — keep the existing leg: a fresh cross up through the 50-day line with
   the 50-day line turning up. This part works; the diagnostic shows it passing
   normally (DE, EQIX, WELL all had it).

Net effect: needs roughly 150 + 63 + slope-lookback + margin ≈ **one calendar year of
history**, behaves more like reading the chart, and the "quiet" score stops collapsing
to zero.

## What stays / what changes

**Stays:** `heartbeat_scan.py` orchestration (rising-sector filter, fundamentals
survival context, insolvency suppression, `goat_pending_candidates` staging with
`source="goat_heartbeat_scan"`, the report renderer, the weekly Saturday timer). The
breakout leg. `GOAT_HEARTBEAT_MIN_DURATION_DAYS = 63`.

**Changes:** the quiet leg in `heartbeat.py` (`_is_in_squeeze` + the
`squeeze_fraction` gate). New 150-day-line position/slope check. The `min_len`
insufficient-history guard (currently `252 + 63`; must reflect the real new
requirement so thin-history names return `"unknown"` honestly instead of a rigged
fail). `test_heartbeat.py` cases.

**Config (rough, planner to finalise):**
- Likely retire: `GOAT_HEARTBEAT_BBW_PERCENTILE_LOOKBACK_DAYS`, `GOAT_HEARTBEAT_BBW_PERCENTILE`
- Likely keep, maybe repurpose: `GOAT_HEARTBEAT_BBW_PERIOD_DAYS`, `GOAT_HEARTBEAT_BBW_STD_MULTIPLIER` (if BBW stays as the range measure against a fixed cut), `GOAT_HEARTBEAT_MIN_DURATION_DAYS`, `GOAT_HEARTBEAT_SQUEEZE_MIN_FRACTION` (rename)
- Likely new: base-range ceiling; 150DMA proximity tolerance; 150DMA slope lookback (or reuse `GOAT_SECTOR_SLOPE_LOOKBACK_DAYS` over 150). Reuse `GOAT_MA_LONG_DAYS = 150`.
- `GOAT_HEARTBEAT_HISTORY_LOOKBACK_DAYS`: 500 is fine (even generous) once the 252-day percentile window is gone; do not shrink below ~1 full year + the base window + slope lookback + weekend/holiday margin.

## Open questions for Shaun / `/plan-feature`

1. **How to measure "narrow sideways range"** — direct high-low % band, price-within-band-of-MA, or fixed-threshold BBW? Light research pass, same discipline as the original BBW-vs-VCP call. Do not ship a guessed number.
2. **"Near or above" the 150-day line** — require price ≥ 150DMA, or allow price up to X% below it? What X? (The webinar exit rule's dip tolerance is the reference point.)
3. **50-day line during the base** — does the setup require price to have been *below* the 50 during the base (so the cross-up is a real reclaim), while *above/near* the 150? Making this explicit sharpens the pattern.
4. **150-day slope** — "not falling" (flat-to-rising) or strictly rising?
5. **Base "smoothness"** — the webinar says "smooth up-down-up-down", not a dead-flat line. Keep a tolerance like the current 0.80-of-days framing, or a different shape test?
6. **History fetch size** — confirm the new minimum and set the lookback with margin.
7. **Regression coverage** — keep `test_heartbeat.py`'s key case: a series where the breakout leg alone passes but the base is *not* quiet must still NOT flag `interesting` (proves the quiet leg is actually gating).

## Explicitly NOT in scope

- No change to Phase 1 / Phase 2 cadence or thresholds.
- No VCP pivot/swing-detection (still deferred, same as Phase 3).
- No change to the fundamentals survival context or insolvency suppression.
- No new alerting behaviour beyond what the weekly scan already does.
- No batched/parallel yfinance fetching.

## Validation (once built)

```powershell
uv run --directory investments/goat python -m pytest -q

# On the VPS via invoke_investments.ps1 — never run locally against the real DB:
.\scripts\invoke_investments.ps1 -Package goat -Command "scan-heartbeat"
```

Plus: re-run the diagnostic below and confirm the quiet score is no longer pinned near
zero across a hand-checked sample, and spot-check 3-5 flagged names against real charts
(50 + 150 MA plotted) before flipping any behaviour on.

## Reproduce the diagnostic

> Historical: this snippet imports `bollinger_width_series` /
> `GOAT_HEARTBEAT_BBW_PERCENTILE_LOOKBACK_DAYS`, both removed in the 2026-08-26
> rewrite, so it no longer runs as-is. The post-rewrite DB-free diagnostic is in
> `.agent/plans/goat-heartbeat-quiet-redesign.md` Task 6.

Read-only, no DB. Save to scratchpad and run:
`uv run --directory investments/goat python -c "import sys,runpy; sys.path.insert(0,'.'); runpy.run_path(r'<path>', run_name='__main__')"`

```python
import pandas as pd
from goat import config
from goat.heartbeat import bollinger_width_series, check_heartbeat_breakout
from goat.price_history import fetch_close_history

SAMPLE = ["KO","PG","WMT","COST","MDLZ","CL","XOM","CVX","COP","EOG","WMB","KMI",
          "JPM","BAC","GS","BLK","SCHW","AXP","JNJ","UNH","LLY","ABBV","MRK","ABT",
          "CAT","DE","HON","UNP","RTX","EMR","LIN","SHW","APD","FCX","NEM","NUE",
          "PLD","AMT","EQIX","WELL","O","VICI"]

for t in SAMPLE:
    close = fetch_close_history(t, config.GOAT_HEARTBEAT_HISTORY_LOOKBACK_DAYS)
    if close is None:
        print(f"{t}: no history"); continue
    bbw = bollinger_width_series(close)
    thr = bbw.rolling(config.GOAT_HEARTBEAT_BBW_PERCENTILE_LOOKBACK_DAYS).quantile(
        config.GOAT_HEARTBEAT_BBW_PERCENTILE / 100)
    res = check_heartbeat_breakout(t, "sample", close)
    d = res.data or {}
    print(f"{t:<6} days={len(close):>4} validQuiet={int(thr.notna().sum()):>4} "
          f"verdict={res.verdict:<12} quietScore={d.get('squeeze_fraction')} "
          f"crossUp={d.get('crossed_above')} slopeUp={d.get('slope_up')} "
          f"daysSinceCross={d.get('trading_days_since_cross')}")
```
