# Rate-of-Change Triple Signal (Price / Volatility / Volume) — Handoff

Tool name: **ROC Triple Signal** (working name — rename during `/plan-feature` if a
better one surfaces). Proposed home: **inside the existing `my-trader` package**, as
a new check module `investments/my-trader/mytrader/checks/roc_signal.py` wired into
`monitor.py`'s existing per-ticker check list, next to `price_action.py` and
`technical_levels.py`. Not a new uv-workspace member, not a new standalone scan with
its own timer — this is pure `yfinance` history math (no LLM/WebSearch calls), so it
is cheap enough to run inline inside Monitor's existing daily holdings+watchlist loop
rather than needing the separate-timer treatment Earnings Watch or Cash-Value Scan
needed (those were separate timers specifically because of LLM cost / market-wide
screen scope, neither of which applies here).

## Status: NOT BUILT — drafted 2026-09-25 from Shaun's request. Awaiting Shaun's
manual `/plan-feature` run against this doc before any implementation.

## What This Is

Shaun's ask, in his words: a daily check across his **watchlist and holdings** that
looks at the **rate of change of price** as it relates to the **rate of change of
volatility** and the **rate of change of volume** — to see whether that combination
is a better predictor of which direction a stock is about to head than looking at any
one of those three in isolation.

The underlying idea (standard technical-analysis territory, sometimes called
volatility-contraction/expansion or volume-confirmation analysis): price, volatility,
and volume each carry a different piece of the story —

- **Price ROC** — is the move itself accelerating or decelerating?
- **Volatility ROC** — is the stock's day-to-day dispersion widening (breakout/
  breakdown energy building) or narrowing (a quiet coil, or exhaustion)?
- **Volume ROC** — is participation confirming the price move (real conviction) or
  drying up (a move on thin volume, more likely to reverse)?

Reading the three together is the actual ask — e.g. price and volume both
accelerating in the same direction while volatility contracts into the move is a
classically bullish combination; price rising on falling volume with volatility also
falling is the kind of move that tends to fade. But "classically" is doing a lot of
work in that sentence — see "This is a research question, not a known-good recipe"
below.

## This is a research question, not a known-good recipe — build order matters

Every other technical check in this codebase that makes an implicit predictive claim
has stayed deliberately non-committal about it:

- `checks/price_action.py`'s own docstring: "Deliberately NOT a buy/sell signal...
  this check doesn't judge whether a move is good or bad, it just reports it."
- `checks/technical_levels.py`'s own docstring: "a moving-average cross is a widely
  contested, context-dependent signal... this check reports the fact... not a
  judgment on what it means."

And the one time this codebase tried to encode a specific quantitative pattern as a
predictive gate — Goat's heartbeat "quiet base" BBW-percentile leg
(`.agent/plans/completed/goat-heartbeat-quiet-redesign.md`) — it **shipped, ran for
10 days, and produced zero candidates against the entire S&P 500**, then had to be
diagnosed and rebuilt from scratch. The failure wasn't a bad idea, it was an
unvalidated implementation detail (a 252-trading-day rolling percentile window that
the fetched history couldn't actually fill) that nobody caught before it shipped
because it was never checked against real data first.

The direct lesson for this handoff: **do not ship this as a verdict-bearing
"interesting"/"flag" signal on day one.** Recommended build order:

1. **Build the three ROC series + fetch the data** (this handoff, section below).
2. **Backtest/validate first** — before wiring anything into Monitor's daily report,
   run the three ROC series against real historical data for a sample of tickers
   (start with Shaun's actual holdings + watchlist, ~1-3 years of history each) and
   check: does *this specific combination* actually correlate with subsequent N-day
   price direction any better than price ROC alone, or than chance? This is the same
   discipline the Hated Industries Scanner applied (backtested against a real SaaS
   drawdown episode before shipping) and that heartbeat's redesign *should* have
   applied before the BBW leg went live. `investments/backtest/` may already have
   reusable historical-data-pull scaffolding worth checking during `/plan-feature`.
3. **Only if the backtest shows a real edge**, decide on thresholds/verdict logic
   from that evidence, not from a plausible-sounding a-priori rule.
4. **If the backtest is inconclusive or negative**, this still shipped value: the
   check surfaces the three ROC readings as `verdict="info"` (like `price_action.py`)
   — useful context for Shaun to read himself even without an automated verdict — and
   the negative backtest result gets written up so nobody re-attempts the same
   unvalidated combination later.

This reframes Shaun's ask correctly: he asked whether this combination is a *better
predictor* — that is an empirical question this handoff should answer with real
numbers, not assume the answer to while building the plumbing.

## Real gotcha already found: Volume is not currently fetched anywhere

Checked live 2026-09-25 across every existing price-history fetcher in the codebase:

- `goat/price_history.py::fetch_close_history` — `yf.Ticker(...).history(...)`, then
  immediately does `hist["Close"].dropna()` and discards the rest of the frame.
- `mytrader/checks/technical_levels.py::_fetch_close_series` — same pattern, own
  private copy, same `hist["Close"]`-only extraction.
- `mytrader/crash_windows.py`, `mytrader/return_data.py` — same close-only shape
  (per `technical_levels.py`'s own docstring, which explicitly says it mirrors them).
- `mytrader/market_data.py::TickerData` — no history fetch at all, just `.info` (a
  single current snapshot — `averageVolume`/`regularMarketVolume` exist here but are
  **single point-in-time values, not a daily time series**, so they can't build a
  Volume ROC series on their own).

**None of these keep the `Volume` column.** yfinance's `.history()` call already
returns it in the same DataFrame every one of these functions calls — it is being
fetched and thrown away, not something that needs a new API surface. This is good
news (no new external dependency) but means the new fetcher genuinely needs to keep
`hist[["Close", "Volume"]]` (or the full OHLCV frame if a true-range volatility
measure is chosen — see next section) rather than reusing any existing close-only
function as-is.

## Volatility measure — pick deliberately, and watch the lookback-window trap

Three candidate volatility measures, in order of how much history each one burns
before producing a first valid reading (direct lesson from the BBW-percentile
failure — the trap was never the measure itself, it was a rolling-percentile window
that needed more clean history than was actually being fetched):

1. **Rolling std-dev of daily log/pct returns** (simplest, close-only, no High/Low
   needed) — e.g. a `N`-day rolling `.std()` of daily returns. Needs `N` returns
   (`N+1` closes) to produce a first reading — cheap, e.g. a 20-day window only
   costs 21 days of warm-up.
2. **ATR (Average True Range)**, normalized by price (`ATR / close`) — needs
   High/Low, not just Close, so it requires keeping the full OHLC frame (a further
   reason not to reuse any close-only fetcher unmodified). Same cheap warm-up cost
   as the std-dev approach for a similarly sized window.
3. **Bollinger Band Width** — **already tried and abandoned in this exact codebase**
   for the *rolling-percentile* variant specifically (see previous section). A raw,
   non-percentile BBW (`(upper - lower) / middle`) is cheap by itself (one 20-day
   MA + std), but if any percentile-vs-own-history normalization gets added later,
   deliberately re-derive the lookback math the way the heartbeat redesign plan did
   (line up trading-days-needed against `GOAT_HEARTBEAT_HISTORY_LOOKBACK_DAYS`'s
   actual yfinance-returned depth) rather than picking a round number like 252 and
   assuming the fetch window covers it.

**Recommendation: start with rolling std-dev of returns** — cheapest, close-only (no
new OHLC-frame requirement beyond adding Volume), and the ROC of a std-dev series is
a well-understood "is volatility expanding or contracting" read on its own, without
needing a percentile-vs-history normalization at all (sidesteps the BBW trap
entirely rather than re-solving it). Revisit ATR only if the backtest step shows the
close-only measure isn't discriminating well and Shaun wants to spend the extra
OHLC-frame cost.

## Rate of Change definition — needs an explicit window, and probably two

"Rate of change" needs a concrete window to mean anything computable. Standard ROC
indicator shape: `(value_today - value_N_days_ago) / value_N_days_ago * 100` — apply
identically to the price series, the volatility series, and the volume series (or a
volume moving average, to avoid single-day volume noise dominating — see below).

Open question (below) on exactly what `N` should be, but worth flagging directly:
this may want **two windows**, not one — a short one (e.g. 5-10 days, "is this
accelerating *right now*") and a longer one (e.g. 20-30 days, "is this move
established or brand new") — since a single window conflates "just started
accelerating" with "has been accelerating for a while," which are different
situations for predicting what happens next. Confirm during the backtest step
whether one window is discriminating enough or two genuinely add information.

**Volume ROC should probably be computed on a smoothed volume series** (e.g. a
5-day or 10-day rolling average of daily volume), not raw daily volume — a single
outlier-volume day (news event, index rebalance, options expiry) would otherwise
dominate the ROC reading the same way a single-day price spike would distort a naive
price ROC if it weren't reading off the actual close series. Confirm this choice
against real data during the backtest step rather than assuming it.

## Open Questions (resolve during `/plan-feature`)

1. **ROC window(s).** One window or two (short + long, per above)? What specific
   day counts? No default recommendation here — this is exactly the kind of
   parameter the backtest step (not intuition) should settle.
2. **Volatility measure.** Rolling std-dev of returns (recommended default above) vs
   ATR vs raw BBW — confirm during backtest whether the simplest option
   discriminates well enough before spending the extra OHLC-frame cost on ATR.
3. **How the three ROC readings combine into one thing Shaun reads.** Three separate
   numbers shown side by side (like `technical_levels.py`'s multi-line detail), a
   single composite/aligned-vs-diverging read (e.g. "price+volume rising together,
   volatility contracting — aligned bullish" vs "diverging — no read"), or both (raw
   numbers plus a plain-English alignment label)? Recommend showing both, same
   philosophy as `earnings-deterioration-watch-handoff.md`'s open question #3 (show
   each signal so Shaun can see which one is actually firing, don't collapse into an
   opaque score) — but the exact alignment-label logic should come out of whatever
   the backtest step finds actually correlates, not be designed in advance.
4. **Backtest scope and pass bar.** How many tickers, how much history, and what
   counts as "this is better than chance / better than price ROC alone" before this
   graduates from `verdict="info"` to something with a real gate? Needs a concrete
   answer during `/plan-feature`, not left implicit — the heartbeat BBW failure
   happened partly because "does this actually work" was never pinned down as a
   checkable question before build.
5. **Where the ROC history itself lives.** A rolling ROC needs the underlying value
   series recomputed each run (cheap, done live from a fresh `yf.Ticker(...).history()`
   pull every time, no persisted state — matches every other Monitor check's
   stateless-per-run shape) vs. persisting a daily snapshot table the way Earnings
   Watch's estimate-history table does (only useful if something later wants to look
   *back* at how the ROC reading itself has trended day-over-day, not just today's
   value). Recommend stateless/live-computed for v1, matching `technical_levels.py`
   and `price_action.py` — add persistence later only if a real need for
   day-over-day ROC-of-ROC tracking shows up.
6. **Watchlist scope.** Confirm this covers the same watchlist scope Monitor's own
   loop already re-checks daily (not just `status="held"` — Monitor's holdings+
   watchlist loop is the whole point of putting this here rather than in a
   holdings-only tool like Earnings Watch).
7. **ASX/non-US tickers.** Reuse the same bare-then-`.AX`-variant fallback pattern
   every other fetcher here uses (`technical_levels.py::_fetch_close_series`,
   `crash_windows.py`, `price_history.py`) — should be a direct copy, not a new
   design decision, just confirm during build.

## Reference code to reuse (read all of these during `/plan-feature`)

- **`mytrader/checks/technical_levels.py`** — closest direct precedent for this new
  check's shape: private `_fetch_*_series` helper split out for unit testing, `check()`
  function taking `data`, `verdict="info"`/`"unknown"` only (no `"flag"`/
  `"interesting"` — matches this handoff's "don't ship a verdict on day one"
  recommendation), `data={}` dict on the `CheckResult` for the raw numbers.
- **`mytrader/checks/price_action.py`** — the "report the fact, don't judge it"
  philosophy this new check should follow until/unless the backtest earns a verdict.
- **`goat/heartbeat.py`'s module docstring** and
  **`.agent/plans/completed/goat-heartbeat-quiet-redesign.md`** — read both in full;
  this is the direct cautionary precedent for "a plausible technical-pattern rule
  that failed against real history because of an unvalidated lookback-window
  assumption," and this handoff's whole "backtest before verdict" structure is built
  directly from that failure.
- **`mytrader/monitor.py`** — the per-ticker check-list wiring
  (`price_action.check(...)`, `technical_levels.check(data)` calls) to extend with
  this new check; also `cached_session()`, worth checking whether it needs extending
  to cache the new history+Volume fetch the same way it already avoids refetching
  `.info` per ticker.
- **`mytrader/engine.py`** (lines ~11-26 import block, ~164-174 check invocation) —
  where new checks get registered into Find's/Monitor's shared check list.
- **`goat/price_history.py`** — the fetch pattern to extend (or write a sibling
  function to, given the Volume-column gap above) rather than copy verbatim.
- **`investments/backtest/`** — check what's already there before building new
  historical-data-pull scaffolding for the validation step; may already have
  reusable pieces.
- **`investments/hated-industries-scanner-handoff.md`** (or its completed plan) —
  precedent for backtesting a new signal against a real historical episode before
  shipping it as a live gate; same discipline this handoff is asking for here.

## Explicitly deferred (do not build as part of this handoff)

- **Any buy/sell verdict.** Same SOUL.md discipline as every other `investments/`
  tool — advisor notes only, Shaun decides.
- **A live gate/alert/staging into a candidates table**, unless and until the
  backtest step shows real predictive value. Until then this is a report-only
  `verdict="info"` addition to Monitor's existing per-ticker output, no WhatsApp
  alert, no watchlist auto-add.
- **ATR/OHLC-based volatility**, unless the close-only std-dev measure proves
  insufficient during backtesting (see volatility-measure section above).
- **Percentile-vs-own-history volatility normalization** (the BBW-percentile shape
  that already failed once) — the ROC-of-volatility framing sidesteps needing this
  at all; don't reintroduce it without the same "equally real justification" bar the
  original Phase 3 heartbeat plan demanded and that its own redesign later met.

## Validation (once built)

```powershell
uv run --directory investments/my-trader python -m pytest -q
```

Backtest step (before wiring into Monitor): validate the three-ROC combination
against real historical data for holdings + watchlist tickers (1-3 years each) —
does it correlate with actual subsequent price direction any better than price ROC
alone? Write the result up (positive or negative) in this handoff or a follow-up
note either way, so the answer isn't lost the way the BBW leg's original research
justification nearly was.

Once wired into Monitor:

```powershell
.\scripts\invoke_investments.ps1 -Package my-trader -Command "find --ticker TICKER"
```

Expected: a new `roc_signal` line in the check output showing price/volatility/
volume ROC readings (whatever window(s) get chosen), `verdict="info"`, no alert.
Test with hand-built fixtures covering: a ticker with clearly accelerating price+
volume+contracting volatility (should compute cleanly, whatever the eventual
alignment label logic says); a ticker with insufficient history for the chosen ROC
window (`verdict="unknown"`, graceful); a ticker where volume data is missing/zero
(shouldn't crash the whole check); an ASX ticker routing through the `.AX` fallback.

## Sources consulted (2026-09-25)

- `investments/my-trader/mytrader/checks/price_action.py`, `technical_levels.py`
- `investments/my-trader/mytrader/market_data.py`, `monitor.py`, `engine.py`,
  `config.py`
- `investments/goat/goat/heartbeat.py`, `price_history.py`
- `.agent/plans/completed/goat-heartbeat-quiet-redesign.md`
- `investments/earnings-deterioration-watch-handoff.md`,
  `investments/goat/lse-heartbeat-universe-handoff.md` (handoff style precedent)
- `investments/TOOLS.md`
