# Feature: Goat Heartbeat Pattern Quality — Report-Only Fields

The following plan should be complete, but it's important that you validate
documentation and codebase patterns and task sanity before you start implementing.

Pay special attention to naming of existing utils/types/models. Import from the
right files.

## Feature Description

Add three report-only data points to Goat's `check_heartbeat_breakout`
(`investments/goat/goat/heartbeat.py`) — the check that decides whether a
ticker's recent price action looks like a genuine "quiet base" worth watching.
Shaun's own read of the current scan: "hit and miss, mostly misses." This
plan extracts the parts of a detailed institutional pattern-scanner prompt
Shaun shared that are (a) cheaply computable from data already fetched, (b)
need no new data source, and (c) don't reverse either of two deliberate prior
decisions baked into this check (no moving-average-relative gate; no
breakout-required gate — see `heartbeat.py`'s own module docstring, redesigned
2026-09-20, three times same day).

**Decisions locked in with Shaun 2026-10-01/02** (do not re-litigate during
implementation):
1. Weekly-trend confirmation gate — **OUT**. Functionally a moving-average-
   relative gate in new clothes; the exact category removed 2026-09-20 after
   causing real bad results (BAC/CAH). Not built in this plan.
2. Volume-declining signal — **report-only data field for v1, not a gate**.
   No backtest required before shipping it as report-only (that bar only
   applies if/when it's ever promoted to an actual gate — a separate future
   decision, not part of this plan).
3. No `goat_pending_candidates` schema change — confirmed by reading `db.py`:
   `signal_detail` is a free-form `TEXT` column already; new fields live in
   `CheckResult.data` (for tests/internal use) and get appended into the
   existing `detail` f-string (so they actually reach
   `heartbeat-candidates-pending-review.md`, the file Shaun actually reads).
4. No backtest script in this plan — correctly out of scope per the locked
   report-only decision above.

## User Story

As Shaun, reviewing Goat's daily heartbeat candidates report
I want to see each candidate's invalidation level, resistance level,
reward:risk ratio, and whether volume over its base is declining
So that I can judge a candidate's quality myself before promoting it, without
the check silently rejecting candidates on an unvalidated new gate

## Problem Statement

`check_heartbeat_breakout` already internally computes `base_low_settled`
(the breakdown floor) and `base_high` but never surfaces them. It discards
Volume entirely even though the yfinance `.history()` call it's built on
top of already returns it — Close-only is a deliberate narrowing done
upstream in `price_history.fetch_close_history`, not a yfinance limitation.
A tight range with declining volume (compression/accumulation) reads very
differently from a tight range with flat/rising volume (an ignored,
illiquid stock sitting still) — Shaun currently has no way to tell the two
apart from the report alone.

## Solution Statement

1. Add a new sibling fetcher, `fetch_close_volume_history`, in
   `goat/price_history.py` that keeps Volume alongside Close (the existing
   `fetch_close_history` is shared by six other Goat modules with no need for
   Volume — do not touch it).
2. Extend `check_heartbeat_breakout`'s signature with an optional `volume`
   parameter, and add five new `data` fields: `invalidation_price`,
   `resistance_price`, `risk_per_share`, `reward_to_risk_ratio`, and
   `volume_declining` — all computed from values already in scope, all
   report-only (none of them change the existing `interesting`/`ok` verdict
   logic).
3. Wire `heartbeat_scan.py` to call the new fetcher and pass `volume` through.
4. Append the new fields into the existing `detail` f-string (the
   "interesting" branch only — that's the string that reaches the Markdown
   report), following this codebase's "full metric name + which direction is
   good" convention.
5. Document the two locked decisions (weekly-trend OUT, volume-declining
   report-only) directly in `heartbeat.py`'s module docstring, matching this
   module's own existing convention of recording *why* a design choice was
   made, not just what it does.

## Feature Metadata

**Feature Type**: Enhancement
**Estimated Complexity**: Low-Medium — no new modules, mechanical test updates
across two existing test files, strong direct precedent (Matt Damon
Price/Volatility/Volume Check's Close+Volume sibling-fetcher pattern)
**Primary Systems Affected**: `investments/goat/goat/heartbeat.py`,
`investments/goat/goat/heartbeat_scan.py`, `investments/goat/goat/price_history.py`,
`investments/goat/goat/config.py`
**Dependencies**: None new — `yfinance`, `pandas` already in use.

---

## CONTEXT REFERENCES

### Relevant Codebase Files — READ THESE BEFORE IMPLEMENTING

- `investments/goat/goat/heartbeat.py` (all 217 lines, already read in full
  this session) — module docstring (lines 1-62) is the direct record of why
  the MA gates and breakout requirement were removed; `check_heartbeat_breakout`
  (lines 110-216) is the function being extended. `data` dict currently built
  at lines 164-170; "interesting" detail string at lines 178-185; "ok" reasons
  list at lines 188-210. `base_low_settled` (line 155) and `base_high` (line
  143) are already computed locally — just never surfaced.
- `investments/goat/goat/heartbeat_scan.py` (all 174 lines, already read in
  full) — `run_heartbeat_scan` lines 37-135; the fetch+check call is lines
  73-80 (`close = price_history.fetch_close_history(...)` then
  `check = heartbeat.check_heartbeat_breakout(ticker, sector_label, close)`).
  This is the ONLY production call site of `check_heartbeat_breakout`
  (confirmed via grep — `dma_breakout_scan.py` line 123 only *mentions* it in
  a comment, never calls it).
- `investments/goat/goat/price_history.py` (all 35 lines, already read in
  full) — `fetch_close_history` (lines 11-34) is the pattern to mirror for the
  new sibling function: two-candidate lookup (`tickers.normalize`, then
  `tickers.asx_variant`), `yf_retry.call(...)`, tz-naive index normalization,
  trailing-NaN-close-row drop (the 2026-08-18 regression fix — see
  `test_price_history.py`'s own docstring). **Do not modify this function** —
  confirmed via grep it's also called from `dma_breakout_scan.py`,
  `hated_industries_scan.py`, `industry_rotation.py`, `insider_scan.py`,
  `live_monitor.py`, `monitor.py`, and `sector_rotation.py`. Any change here
  risks six unrelated modules.
- `investments/goat/goat/tests/test_heartbeat.py` (all 177 lines, already
  read in full) — exact test shape to mirror: `_series`/`_dates`/`_osc_base`
  helpers (lines 39-52), one dedicated test per gate. Existing tests call
  `check_heartbeat_breakout("AAPL", "Technology", close)` with 3 positional
  args and assert on specific `data[...]` keys (never exact dict equality) —
  confirmed these will NOT break when a `volume` param with a default is
  added and new `data` keys appear.
- `investments/goat/goat/tests/test_heartbeat_scan.py` (all 221 lines, already
  read in full) — `_patch_common` (lines 44-73) monkeypatches
  `"goat.heartbeat_scan.price_history.fetch_close_history"` (line 59) and
  `"goat.heartbeat_scan.heartbeat.check_heartbeat_breakout"` (line 63, default
  lambda takes `(ticker, sector_label, close)`, line 64-68) and `_fake_close()`
  (lines 22-23). ALL THREE need updating once `heartbeat_scan.py` switches to
  the new fetcher and starts passing `volume` through — see Task 6 below for
  the exact, minimal set of edits (most of the 12 test functions in this file
  don't need to change at all, since they only override `fetch_close=` or
  `ticker_data=`, not `breakout_check=`).
- `investments/goat/goat/tests/test_price_history.py` (all 59 lines, already
  read in full) — `_install_fake_yfinance` (lines 13-23) + the fake
  `yfinance.Ticker.history(start=None, auto_adjust=True)` shape to mirror
  for the new fetcher's tests.
- `investments/goat/goat/config.py` lines 220-277 (`GOAT_HEARTBEAT_*`
  consolidation-leg block, already read in full) — banner-comment + inline
  rationale-comment style to mirror exactly for the new constant(s). Insert
  after line 277 (end of `GOAT_HEARTBEAT_MIN_SWINGS`'s comment block), before
  the blank line and `# Fundamentals survival context` section at line 279.
- `investments/goat/goat/db.py` lines 29-36 (`goat_pending_candidates` schema)
  and lines 220-232 (`insert_goat_pending_candidate`) — confirms
  `signal_detail` is a plain `TEXT NOT NULL` column (free-form), and
  `heartbeat_scan.py` already builds it as
  `f"{check.detail}; survival context: {context['summary']}"` (its own line
  103) — i.e. whatever this plan adds to `check.detail` automatically reaches
  the stored/rendered candidate row with zero `db.py`/schema changes.
  Confirms Open Question 3's "no migration" recommendation directly.
- `investments/my-trader/mytrader/chart_setup_score.py` lines 40-60 (already
  read in full) — contrary to the source handoff's claim, this file's
  `fetch_close` is ALSO close-only (discards Volume) — there is no
  Volume-keeping docstring precedent here. The real precedent for a
  Close+Volume sibling fetcher is
  `.agent/plans/completed/matt-damon-price-volitility-volume-check.md`'s
  `_fetch_price_volume_history` (Task 2 of that plan) — cite that, not
  `chart_setup_score.py`, when writing this plan's own fetcher docstring.
  (Minor factual correction to the source handoff doc — doesn't change any
  implementation decision, just the precedent citation.)
- `.agent/plans/completed/matt-damon-price-volitility-volume-check.md` Task 2
  (already read in full) — direct precedent for a Close+Volume sibling
  fetcher living alongside a Close-only one without modifying the original.
- `.agent/plans/completed/goat-heartbeat-quiet-redesign.md` — the direct
  cautionary precedent for shipping an unvalidated technical gate (the old
  BBW-percentile leg). Not directly reused for code, but is the reason this
  plan ships volume-declining as report-only, not a gate.

### Files to Update

- `investments/goat/goat/price_history.py` — add `fetch_close_volume_history`.
- `investments/goat/goat/heartbeat.py` — module docstring addition; new
  `_volume_trend_declining` helper; `check_heartbeat_breakout` signature +
  `data` dict + "interesting" detail string.
- `investments/goat/goat/heartbeat_scan.py` — switch the fetch call, pass
  `volume` through.
- `investments/goat/goat/config.py` — new `GOAT_HEARTBEAT_VOLUME_*` constant(s).
- `investments/goat/goat/tests/test_price_history.py` — new tests for
  `fetch_close_volume_history`.
- `investments/goat/goat/tests/test_heartbeat.py` — new tests for the three
  new report-only fields.
- `investments/goat/goat/tests/test_heartbeat_scan.py` — update `_patch_common`
  monkeypatch targets + `_fake_close()` to match the new fetcher/signature.

### No New Files

Everything here is additive to existing modules — no new module files, no
backtest script (explicitly out of scope per the locked decisions above).

### Patterns to Follow

**Naming:** `GOAT_HEARTBEAT_*` prefix for new config constants, `SCREAMING_SNAKE_CASE`,
grouped under a dated banner comment (see `config.py` lines 220-229 style).
`_leading_underscore` for the new module-private volume-trend helper, matching
`_count_swings` right above it.

**Report-only convention:** `price_action.py` / `technical_levels.py`'s "report
the fact, don't judge it" — new fields must never participate in the
`if base_is_narrow and base_is_smooth and not broke_down and has_enough_swings:`
gate at `heartbeat.py` line 172. Do not add a fifth condition to that `if`.

**Detail-string convention:** per project feedback memory on check
interpretation — spell out full metric names (not abbreviations) and state
which direction is good, not just a bare number. E.g. "reward-to-risk ratio
(distance to resistance over distance to the invalidation floor — higher is
better)", not "R:R".

**None-handling convention:** every new field must degrade to `None` (not a
crash, not a fabricated number) when its inputs don't support a real answer —
e.g. `reward_to_risk_ratio` when `risk_per_share <= 0` (price already at/below
its own invalidation floor — division would be nonsensical), `volume_declining`
when volume data is missing/too sparse. Mirrors `_roc`'s `None`-on-insufficient-
data convention in `matt_damon_price_volitility_volume_check.py`.

---

## IMPLEMENTATION PLAN

### Phase 1: Config + Fetcher

Add the new constant(s) and the Close+Volume sibling fetcher.

### Phase 2: Core Computation

Add the volume-trend helper and the four price-derived fields
(`invalidation_price`, `resistance_price`, `risk_per_share`,
`reward_to_risk_ratio`) plus `volume_declining` to `check_heartbeat_breakout`,
and extend the detail string.

### Phase 3: Wiring

Update `heartbeat_scan.py` to fetch and pass Volume through.

### Phase 4: Testing & Validation

Update the two affected test files, add new tests, run the full suite,
manually sanity-check a real `scan-heartbeat` run.

---

## STEP-BY-STEP TASKS

### 1. UPDATE `investments/goat/goat/config.py`

- **IMPLEMENT**: Insert after line 277 (before the blank line preceding
  `# Fundamentals survival context` at line 279):
  ```python

  # Volume-declining report-only signal -- added 2026-10-02, see
  # .agent/plans/goat-heartbeat-pattern-quality.md and
  # investments/goat/heartbeat-pattern-quality-handoff.md. Report-only (shown
  # in the candidate report's detail text, via CheckResult.data) -- does NOT
  # gate the interesting/ok verdict. Promote to a real gate only after a
  # backtest, per this codebase's existing "ship info, validate before
  # gating" precedent (matt_damon_price_volitility_volume_check).
  GOAT_HEARTBEAT_VOLUME_MIN_VALID_DAYS = 63  # at least this many valid
      # (non-NaN, > 0) volume days within the base window are required before
      # a declining/not-declining read is reported at all -- half of
      # GOAT_HEARTBEAT_MIN_DURATION_DAYS (126), so both the first-half and
      # second-half volume averages being compared are each backed by a
      # meaningful sample even if some days are missing/zero (illiquid
      # names, some ETFs). Below this, volume_declining reports None rather
      # than guessing off a thin sample.
  ```
- **PATTERN**: `config.py` lines 220-277 (banner comment + constant + inline
  rationale comment style).
- **VALIDATE**:
  `uv run --directory investments/goat python -c "from goat import config; print(config.GOAT_HEARTBEAT_VOLUME_MIN_VALID_DAYS)"`

### 2. UPDATE `investments/goat/goat/price_history.py`

- **IMPLEMENT**: Add below `fetch_close_history` (after line 34):
  ```python
  def fetch_close_volume_history(ticker: str, lookback_days: int) -> pd.DataFrame | None:
      """Sibling of fetch_close_history that also keeps Volume -- added for the
      heartbeat pattern-quality handoff's volume-declining report-only signal
      (see .agent/plans/goat-heartbeat-pattern-quality.md). fetch_close_history
      itself is shared by six other Goat modules with no need for Volume
      (dma_breakout_scan, hated_industries_scan, industry_rotation,
      insider_scan, live_monitor, monitor, sector_rotation) -- a new sibling
      avoids touching any of their call sites, matching the precedent set by
      mytrader/checks/matt_damon_price_volitility_volume_check.py's own
      _fetch_price_volume_history (a sibling of mytrader's close-only
      fetchers, not a modification of them -- see
      .agent/plans/completed/matt-damon-price-volitility-volume-check.md
      Task 2)."""
      import yfinance as yf

      start = (date.today() - timedelta(days=lookback_days)).isoformat()
      for candidate in (tickers.normalize(ticker), tickers.asx_variant(ticker)):
          try:
              hist = yf_retry.call(lambda c=candidate: yf.Ticker(c).history(start=start, auto_adjust=True))
          except Exception:
              continue
          if hist.empty:
              continue
          frame = hist[["Close", "Volume"]].dropna(subset=["Close"])
          if frame.empty:
              continue
          if getattr(frame.index, "tz", None) is not None:
              frame.index = frame.index.tz_localize(None)
          return frame
      return None
  ```
- **PATTERN**: `fetch_close_history` lines 11-34 (same retry/candidate loop,
  same tz handling, same trailing-NaN-close-row drop via
  `dropna(subset=["Close"])` — Volume's own NaNs are deliberately left alone
  here; `_volume_trend_declining` (Task 4) handles those).
- **IMPORTS**: None new — `date`, `timedelta`, `pd`, `tickers`, `yf_retry`
  already imported at the top of this file.
- **GOTCHA**: Do not touch `fetch_close_history` itself. Six other modules
  depend on its exact current behavior.
- **VALIDATE**:
  `uv run --directory investments/goat python -m pytest goat/tests/test_price_history.py -v`
  (after Task 7 adds the new tests below)

### 3. UPDATE `investments/goat/goat/heartbeat.py` — module docstring

- **IMPLEMENT**: Append a new paragraph at the end of the existing module
  docstring (after the line ending "...every 'range' here is a
  close-to-close range." at line 62), before the closing `"""`:
  ```
  2026-10-02: added three report-only fields -- invalidation_price,
  resistance_price, risk_per_share, reward_to_risk_ratio (all derived from
  base_low_settled/base_high, already computed above), and volume_declining
  (first-half vs. second-half mean volume over the base window, via a new
  Close+Volume sibling fetcher in price_history.py) -- prompted by Shaun
  sharing an institutional pattern-scanner prompt and asking whether it could
  improve this check (see heartbeat-pattern-quality-handoff.md). None of these
  participate in the interesting/ok verdict decision -- gating on
  volume_declining would need a backtest first, per this codebase's existing
  "ship info, validate before gating" precedent, and a weekly-trend
  confirmation gate from that same prompt was explicitly NOT added at all --
  functionally a moving-average-relative gate in new clothes, the exact
  category removed above after causing real bad results. Both calls per
  Shaun, confirmed 2026-10-02.
  ```
- **VALIDATE**: `uv run --directory investments/goat python -c "from goat import heartbeat; print(heartbeat.__doc__[-400:])"`

### 4. UPDATE `investments/goat/goat/heartbeat.py` — volume-trend helper

- **IMPLEMENT**: Add directly above `check_heartbeat_breakout` (after
  `_count_swings`, i.e. after line 107):
  ```python
  def _volume_trend_declining(base_volume: pd.Series | None, min_valid_days: int) -> bool | None:
      """Report-only compression/accumulation read: True when the base
      window's second-half mean volume is below its first-half mean (a tight
      range with thinning volume), False when it isn't, None when there isn't
      enough usable volume data to say -- never guessed. 'Usable' excludes
      NaN and non-positive readings (illiquid names, some ETFs, data gaps)."""
      if base_volume is None:
          return None
      valid = base_volume.dropna()
      valid = valid[valid > 0]
      if len(valid) < min_valid_days:
          return None
      half = len(valid) // 2
      first_half_mean = float(valid.iloc[:half].mean())
      second_half_mean = float(valid.iloc[half:].mean())
      if first_half_mean <= 0:
          return None
      return second_half_mean < first_half_mean
  ```
- **PATTERN**: `_count_swings` (lines 72-107) — same module-private,
  pure-function, docstring-explains-why shape.
- **VALIDATE**: covered by Task 8's unit tests.

### 5. UPDATE `investments/goat/goat/heartbeat.py` — `check_heartbeat_breakout`

- **IMPLEMENT**: Change the signature (line 110) to:
  ```python
  def check_heartbeat_breakout(
      ticker: str, sector_label: str, close: pd.Series, volume: pd.Series | None = None,
  ) -> CheckResult:
  ```
  After the existing `broke_down`/`base_is_narrow`/`base_is_smooth`/
  `swing_count` block (i.e. right after line 162, before the `data = {...}`
  dict at line 164), add:
  ```python
  last_close_value = last_close
  invalidation_price = base_low_settled
  resistance_price = base_high
  risk_per_share = last_close_value - invalidation_price
  reward_to_risk_ratio = (
      (resistance_price - last_close_value) / risk_per_share if risk_per_share > 0 else None
  )

  base_volume = volume.tail(base_window) if volume is not None else None
  volume_declining = _volume_trend_declining(base_volume, config.GOAT_HEARTBEAT_VOLUME_MIN_VALID_DAYS)
  ```
  Extend the existing `data = {...}` dict (lines 164-170) with:
  ```python
      "invalidation_price": round(invalidation_price, 2),
      "resistance_price": round(resistance_price, 2),
      "risk_per_share": round(risk_per_share, 2),
      "reward_to_risk_ratio": round(reward_to_risk_ratio, 2) if reward_to_risk_ratio is not None else None,
      "volume_declining": volume_declining,
  ```
  Extend the "interesting" branch's `detail` string (lines 178-185) by adding
  a new clause before `"-- heartbeat entry signal"`:
  ```python
  def _fmt_rr(rr: float | None) -> str:
      return f"{rr:.2f}" if rr is not None else "n/a (price already at/below its own invalidation floor)"

  def _fmt_volume(declining: bool | None) -> str:
      if declining is None:
          return "not enough volume data to read"
      return "declining (a possible compression/accumulation signal)" if declining else "not declining"

  detail = (
      f"{ticker} ({sector_label}): {base_window} trading days of tight sideways "
      f"consolidation -- {base_range_pct:.1f}% high-low close range vs. the "
      f"{config.GOAT_HEARTBEAT_BASE_RANGE_MAX_PCT:.0f}% ceiling (tighter is better), "
      f"{smoothness_fraction * 100:.0f}% of days inside the smooth inner band, "
      f"{swing_count} confirmed up-down swings (a real rhythm, not a single move) -- {position} "
      f"-- invalidation (base floor) {invalidation_price:.2f} / resistance (base high) "
      f"{resistance_price:.2f}, reward-to-risk ratio (distance to resistance over distance to "
      f"the invalidation floor -- higher is better) {_fmt_rr(reward_to_risk_ratio)}, volume over "
      f"the base is {_fmt_volume(volume_declining)} "
      f"-- heartbeat entry signal"
  )
  ```
  Do NOT add anything to the "ok" (non-qualifying) branch's `reasons` list —
  that branch explains *why* the base failed to qualify; the new report-only
  fields are only meaningful once a base has already qualified and gets
  staged for Shaun's review.
- **PATTERN**: existing `data` dict (lines 164-170) and detail string
  (lines 178-185) exactly — same rounding convention (`round(x, 2)` for
  prices, matching `round(base_range_pct, 2)` etc.), same inline helper
  functions placed just above their use (matching `fmt` in
  `matt_damon_price_volitility_volume_check.py`'s `check()`).
- **GOTCHA**: `last_close` is already computed at line 144 — reuse it
  directly, don't refetch `close.iloc[-1]` again (the `last_close_value =
  last_close` line above is just for naming clarity in this snippet; in the
  real edit, just use `last_close` directly and skip the alias).
- **GOTCHA**: `reward_to_risk_ratio`'s numerator (`resistance_price -
  last_close`) is mathematically identical to the already-existing
  `pct_below_base_high` numerator (`base_high - last_close`) — don't
  recompute it differently or the two could silently drift if either formula
  is later tweaked. Fine to compute independently here since both are simple
  one-line arithmetic on the same two values, but keep the sign convention
  consistent (positive reward = resistance above current price).
- **VALIDATE**: covered by Task 8's unit tests.

### 6. UPDATE `investments/goat/goat/heartbeat_scan.py`

- **IMPLEMENT**: Replace line 74
  (`close = price_history.fetch_close_history(ticker, config.GOAT_HEARTBEAT_HISTORY_LOOKBACK_DAYS)`)
  and the `if close is None:` check (line 75) with:
  ```python
  frame = price_history.fetch_close_volume_history(ticker, config.GOAT_HEARTBEAT_HISTORY_LOOKBACK_DAYS)
  if frame is None:
      print(f"[goat-heartbeat-scan] no price history for {ticker}, skipping")
      continue
  scanned += 1
  close = frame["Close"]
  volume = frame["Volume"]
  ```
  (`scanned += 1` moves here unchanged in meaning — it was already
  immediately after the old `if close is None` check at line 78; keep it in
  the same relative position.)
  Update line 80
  (`check = heartbeat.check_heartbeat_breakout(ticker, sector_label, close)`)
  to:
  ```python
  check = heartbeat.check_heartbeat_breakout(ticker, sector_label, close, volume)
  ```
- **PATTERN**: the surrounding `try/except Exception` block (lines 73-126) —
  unchanged in structure, only the fetch call and one new line change.
- **GOTCHA**: `price_history` is already imported in this file's import block
  (line 21) — no new import needed, just a new attribute off the same module.
- **VALIDATE**:
  `uv run --directory investments/goat python -m pytest goat/tests/test_heartbeat_scan.py -v`
  (after Task 9 updates the test file's monkeypatches below — expect failures
  before that task, not after)

### 7. UPDATE `investments/goat/goat/tests/test_price_history.py`

- **IMPLEMENT**: Add (mirroring the existing three tests exactly, same
  `_install_fake_yfinance` helper, same fake-`yfinance` module-injection
  pattern):
  ```python
  _real_fetch_close_volume_history = price_history.fetch_close_volume_history


  def test_fetch_close_volume_history_drops_trailing_nan_close_row_keeps_volume(monkeypatch):
      idx = pd.date_range("2026-08-10", periods=6, freq="D")
      hist = pd.DataFrame(
          {"Close": [186.3, 186.1, 188.9, 190.8, 190.0, float("nan")],
           "Volume": [1000, 1100, 1200, 1300, 1400, 1500]},
          index=idx,
      )
      _install_fake_yfinance(monkeypatch, hist)
      monkeypatch.setattr(price_history, "fetch_close_volume_history", _real_fetch_close_volume_history)

      frame = price_history.fetch_close_volume_history("XLK", lookback_days=30)

      assert frame is not None
      assert not frame["Close"].isna().any()
      assert frame["Close"].iloc[-1] == 190.0
      assert list(frame["Volume"]) == [1000, 1100, 1200, 1300, 1400]


  def test_fetch_close_volume_history_returns_none_when_all_close_nan(monkeypatch):
      idx = pd.date_range("2026-08-10", periods=2, freq="D")
      hist = pd.DataFrame({"Close": [float("nan"), float("nan")], "Volume": [100, 200]}, index=idx)
      _install_fake_yfinance(monkeypatch, hist)
      monkeypatch.setattr(price_history, "fetch_close_volume_history", _real_fetch_close_volume_history)

      assert price_history.fetch_close_volume_history("XLK", lookback_days=30) is None


  def test_fetch_close_volume_history_returns_none_when_empty(monkeypatch):
      _install_fake_yfinance(monkeypatch, pd.DataFrame())
      monkeypatch.setattr(price_history, "fetch_close_volume_history", _real_fetch_close_volume_history)

      assert price_history.fetch_close_volume_history("XLK", lookback_days=30) is None
  ```
- **PATTERN**: lines 10, 26-58 of the existing file (already read in full).
- **VALIDATE**: `uv run --directory investments/goat python -m pytest goat/tests/test_price_history.py -v`

### 8. UPDATE `investments/goat/goat/tests/test_heartbeat.py`

- **IMPLEMENT**: Add new tests after the existing `test_count_swings_counts_genuine_reversals`
  (after line 177):
  ```python
  def _volume_series(n: int, values: list[float]) -> pd.Series:
      return pd.Series(values, index=_dates(n))


  def test_reports_invalidation_resistance_and_reward_to_risk_fields():
      close = _series(_osc_base(_BASE_WINDOW, 100.0, 3.0))
      result = heartbeat.check_heartbeat_breakout("AAPL", "Technology", close)
      base_close = close.tail(_BASE_WINDOW)
      recent_days = config.GOAT_HEARTBEAT_BREAKDOWN_RECENT_DAYS
      expected_invalidation = float(base_close.iloc[:-recent_days].min())
      expected_resistance = float(base_close.max())
      expected_risk = float(close.iloc[-1]) - expected_invalidation
      expected_reward = (expected_resistance - float(close.iloc[-1])) / expected_risk
      assert result.data["invalidation_price"] == round(expected_invalidation, 2)
      assert result.data["resistance_price"] == round(expected_resistance, 2)
      assert result.data["risk_per_share"] == round(expected_risk, 2)
      assert result.data["reward_to_risk_ratio"] == round(expected_reward, 2)
      assert "invalidation" in result.detail
      assert "resistance" in result.detail
      assert "reward-to-risk ratio" in result.detail


  def test_reward_to_risk_ratio_is_none_when_price_already_below_invalidation():
      """Mirrors test_recent_breakdown_below_settled_base_does_not_fire's fixture
      -- when the recent stretch has broken down below the settled floor,
      last_close can sit at/below invalidation_price, making risk_per_share
      non-positive. The ratio must report None, not a negative/nonsensical
      number or a ZeroDivisionError."""
      recent_days = config.GOAT_HEARTBEAT_BREAKDOWN_RECENT_DAYS
      settled = _osc_base(_BASE_WINDOW - recent_days, 100.0, 3.0)
      recent = [96.0] * recent_days
      close = _series(settled + recent)
      result = heartbeat.check_heartbeat_breakout("AAPL", "Technology", close)
      assert result.data["risk_per_share"] <= 0
      assert result.data["reward_to_risk_ratio"] is None
      assert "n/a" in result.detail


  def test_volume_declining_is_none_when_volume_not_provided():
      close = _series(_osc_base(_BASE_WINDOW, 100.0, 3.0))
      result = heartbeat.check_heartbeat_breakout("AAPL", "Technology", close)
      assert result.data["volume_declining"] is None
      assert "not enough volume data" in result.detail


  def test_volume_declining_true_when_second_half_volume_lower():
      close = _series(_osc_base(_BASE_WINDOW, 100.0, 3.0))
      volume = _volume_series(_BASE_WINDOW, [2000.0] * (_BASE_WINDOW // 2) + [1000.0] * (_BASE_WINDOW - _BASE_WINDOW // 2))
      result = heartbeat.check_heartbeat_breakout("AAPL", "Technology", close, volume)
      assert result.data["volume_declining"] is True
      assert "declining (a possible compression" in result.detail


  def test_volume_declining_false_when_second_half_volume_higher():
      close = _series(_osc_base(_BASE_WINDOW, 100.0, 3.0))
      volume = _volume_series(_BASE_WINDOW, [1000.0] * (_BASE_WINDOW // 2) + [2000.0] * (_BASE_WINDOW - _BASE_WINDOW // 2))
      result = heartbeat.check_heartbeat_breakout("AAPL", "Technology", close, volume)
      assert result.data["volume_declining"] is False


  def test_volume_declining_is_none_when_too_few_valid_volume_days():
      close = _series(_osc_base(_BASE_WINDOW, 100.0, 3.0))
      volume = _volume_series(_BASE_WINDOW, [float("nan")] * (_BASE_WINDOW - 10) + [1000.0] * 10)
      result = heartbeat.check_heartbeat_breakout("AAPL", "Technology", close, volume)
      assert result.data["volume_declining"] is None


  def test_count_volume_trend_declining_direct():
      declining = pd.Series([2000.0] * 40 + [1000.0] * 40)
      flat_or_rising = pd.Series([1000.0] * 40 + [2000.0] * 40)
      assert heartbeat._volume_trend_declining(declining, min_valid_days=10) is True
      assert heartbeat._volume_trend_declining(flat_or_rising, min_valid_days=10) is False
      assert heartbeat._volume_trend_declining(None, min_valid_days=10) is None
      assert heartbeat._volume_trend_declining(pd.Series([1000.0] * 5), min_valid_days=10) is None
  ```
- **PATTERN**: existing `_series`/`_dates`/`_osc_base` helpers (lines 39-52)
  and the existing breakdown fixture in
  `test_recent_breakdown_below_settled_base_does_not_fire` (lines 130-143).
- **GOTCHA**: `volume` passed to `check_heartbeat_breakout` must share the
  same length/index convention as `close` in these fixtures (`_BASE_WINDOW`
  rows) since `check_heartbeat_breakout` does `volume.tail(base_window)` —
  the helper `_volume_series(n, values)` above builds exactly that.
- **VALIDATE**: `uv run --directory investments/goat python -m pytest goat/tests/test_heartbeat.py -v`

### 9. UPDATE `investments/goat/goat/tests/test_heartbeat_scan.py`

- **IMPLEMENT**: Minimal, targeted edits — most of the 12 test functions need
  no change at all.
  1. Replace `_fake_close()` (lines 22-23) with:
     ```python
     def _fake_price_volume_frame() -> pd.DataFrame:
         return pd.DataFrame(
             {"Close": [100.0, 101.0], "Volume": [1000.0, 1100.0]},
             index=pd.date_range("2026-01-01", periods=2),
         )
     ```
  2. In `_patch_common` (lines 44-73):
     - Rename the `fetch_close` parameter's default and target: change line
       58-61 from
       ```python
       monkeypatch.setattr(
           "goat.heartbeat_scan.price_history.fetch_close_history",
           fetch_close if fetch_close is not None else (lambda ticker, lookback_days: _fake_close()),
       )
       ```
       to
       ```python
       monkeypatch.setattr(
           "goat.heartbeat_scan.price_history.fetch_close_volume_history",
           fetch_close if fetch_close is not None else (lambda ticker, lookback_days: _fake_price_volume_frame()),
       )
       ```
       (keep the parameter name `fetch_close` — every caller that overrides
       it via `_patch_common(monkeypatch, fetch_close=...)` stays unchanged.)
     - Change the default `breakout_check` lambda (lines 64-68) from
       `lambda ticker, sector_label, close: CheckResult(...)` to
       `lambda ticker, sector_label, close, volume: CheckResult(...)` (same
       body otherwise).
  3. `test_run_heartbeat_scan_filters_non_rising_sector_before_any_fetch`
     (lines 87-97): its local `_tracking_fetch(ticker, lookback_days)`
     currently returns `_fake_close()` — change the return to
     `_fake_price_volume_frame()`. Signature (`ticker, lookback_days`) is
     unchanged since `fetch_close_volume_history` takes the same two args.
  4. `test_run_heartbeat_scan_skips_ticker_with_no_price_history` (lines
     136-140): `fetch_close=lambda ticker, lookback_days: None` needs no
     change — `None` is still the correct "no history" sentinel for the new
     fetcher.
  5. All other test functions (stages-new-candidate, skips-holding,
     skips-watchlist, stays-quiet-on-repeat, suppresses-on-insolvency,
     skips-unmapped-gics/icb, stages-from-both-us-and-lse,
     qualifies-lse-ticker, populates-exchange, both render tests) call
     `_patch_common(monkeypatch, ...)` without overriding `fetch_close` or
     `breakout_check` — they pick up the new defaults automatically and need
     NO changes.
- **PATTERN**: the file's existing structure end to end — this is a
  find-and-replace-scoped edit, not a rewrite.
- **VALIDATE**: `uv run --directory investments/goat python -m pytest goat/tests/test_heartbeat_scan.py -v`

---

## TESTING STRATEGY

### Unit Tests

- `test_price_history.py`: new fetcher's trailing-NaN-close-drop (Volume
  untouched), all-NaN-close → None, empty → None.
- `test_heartbeat.py`: invalidation/resistance/risk/reward fields match
  hand-computed values off the same fixture; reward_to_risk_ratio is `None`
  when risk_per_share is non-positive (breakdown fixture); volume_declining
  is `None` with no volume passed, `True`/`False` with a clear
  declining/rising synthetic volume series, `None` when too few valid
  (non-NaN, >0) volume days exist; `_volume_trend_declining` tested directly
  for all four branches.
- `test_heartbeat_scan.py`: confirms the scan still stages candidates and
  still skips cleanly on no-history, now routed through the new fetcher.

### Integration Tests

Full `investments/goat` suite — confirms no other module's use of
`fetch_close_history`/`check_heartbeat_breakout` regressed (they shouldn't;
neither was modified in a breaking way).

### Edge Cases

- Ticker with no Volume data at all (`volume=None` passed, e.g. if ever
  called without the new fetcher) — `volume_declining` must be `None`, never
  a crash.
- Ticker with Volume present but mostly zero/NaN (illiquid names, some ETFs)
  — must not divide by zero or treat a thin sample as a real read; covered by
  `test_volume_declining_is_none_when_too_few_valid_volume_days`.
- A base that both qualifies as "interesting" AND has already broken down in
  price terms is impossible by construction (broke_down is one of the four
  gates) — but a qualifying base whose `last_close` sits exactly at
  `invalidation_price` (risk_per_share == 0) must also report `None` for the
  ratio, not a `ZeroDivisionError` — covered by the `risk_per_share > 0`
  (strictly greater than) guard, not `>= 0`.

---

## VALIDATION COMMANDS

### Level 1: Syntax & Style

No project-wide linter/formatter config found for `investments/goat` — match
the surrounding file's existing style (confirm no `[tool.ruff]`/`[tool.black]`
section exists in `investments/goat/pyproject.toml` before assuming).

### Level 2: Unit Tests

```powershell
uv run --directory investments/goat python -m pytest goat/tests/test_price_history.py goat/tests/test_heartbeat.py goat/tests/test_heartbeat_scan.py -v
```

### Level 3: Full Suite (zero regressions)

```powershell
uv run --directory investments/goat python -m pytest -q
```

### Level 4: Manual Validation

```powershell
scripts\invoke_investments.ps1 -Package goat -Command "scan-heartbeat"
```
(Never run `scan-heartbeat` directly against the local machine — `investments.db`
is VPS-only, per CLAUDE.md.) Read the regenerated
`heartbeat-candidates-pending-review.md` and confirm, for at least 2-3 real
candidates: invalidation/resistance/reward:risk numbers are present and look
sane against the candidate's actual recent price action, and the
volume-declining phrase reads sensibly (sanity-check against the real chart
for at least one name before trusting it, per the source handoff's own
Validation section).

### Level 5: Additional Validation (Optional)

None — no backtest in scope for this plan (locked decision: report-only
fields don't require one).

---

## ACCEPTANCE CRITERIA

- [ ] `check_heartbeat_breakout`'s `interesting`/`ok` verdict logic is
      byte-for-byte unchanged — no fifth condition added to the existing gate.
- [ ] `data` dict gains exactly five new keys: `invalidation_price`,
      `resistance_price`, `risk_per_share`, `reward_to_risk_ratio`,
      `volume_declining`.
- [ ] The "interesting" branch's `detail` string includes all five new
      values in human-readable form with direction-of-good stated for the
      ratio; the "ok" branch's `reasons` list is unchanged.
- [ ] `fetch_close_history` and its six other call sites are untouched.
- [ ] No weekly-trend / moving-average-relative gate is added anywhere.
- [ ] No `goat_pending_candidates` schema change; no `db.py` change.
- [ ] No backtest script added.
- [ ] All new/existing tests pass; full `investments/goat` suite has zero
      regressions.
- [ ] Manual `scan-heartbeat` run shows sane new fields for real candidates.

---

## COMPLETION CHECKLIST

- [ ] All 9 tasks completed in order.
- [ ] Each task's validation command passed immediately after that task.
- [ ] Full test suite passes.
- [ ] Manual `scan-heartbeat` check confirms the new fields render correctly
      in `heartbeat-candidates-pending-review.md`.
- [ ] Module docstring records both locked decisions (weekly-trend OUT,
      volume-declining report-only).
- [ ] Acceptance criteria all met.

---

## NOTES

- **Why no backtest script**: unlike the Matt Damon check (which needed to
  empirically earn its right to exist as even a reporting signal before
  Shaun would trust it), these fields are either pure arithmetic on numbers
  the check already computes (invalidation/resistance/reward:risk — not a
  "signal" at all, just exposing existing internal state) or an explicitly
  report-only descriptive label (volume_declining) that Shaun evaluates
  himself alongside the chart, per his own locked decision 2026-10-01/02.
  Backtesting only becomes a prerequisite if/when volume_declining is ever
  proposed as an actual gate — a separate future plan, not this one.
- **Source handoff's claim about `chart_setup_score.py`'s docstring** is not
  quite accurate (that file is also close-only, with no stated Volume-gap
  docstring) — corrected above under Context References. Doesn't change any
  implementation decision; the real sibling-fetcher precedent is the Matt
  Damon plan.
- **Open Question 3 confirmed resolved** by reading `db.py` directly:
  `signal_detail` is free-form `TEXT`, so appending to `detail` is sufficient
  — no schema/migration work anywhere in this plan.

## Confidence Score

**8/10** for one-pass implementation success. This is a well-precedented,
mechanical extension (new sibling fetcher mirrors an exact existing pattern
twice over; new report-only fields are simple arithmetic on values already
in scope). The one area needing real care rather than copy-paste is Task 9's
test-file edit — getting the monkeypatch target/signature changes exactly
right without breaking the ~9 untouched test functions in
`test_heartbeat_scan.py`.
