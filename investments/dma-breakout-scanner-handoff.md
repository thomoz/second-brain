# DMA Breakout Scanner (stocks just crossed above 150DMA/200DMA) — Session Handoff

Tool name: **DMA Breakout Scanner**. Proposed home: **inside the existing `goat` package**
as a new module `investments/goat/goat/dma_breakout_scan.py` + CLI command
`scan-dma-breakout` (not a new uv-workspace member — this reuses goat's universe,
price-history, staging-table, and alerting infra directly, same "extend the existing
package" precedent as Goat's own sector/industry/heartbeat/insider scans all living
together in one package).

## Status: NOT BUILT — drafted 2026-09-16 from Shaun's request ("do we have a tool that
looks for stocks that have just broken above the 150DMA or 200DMA?" — answer was no).
Awaiting Shaun's manual `/plan-feature` run against this doc before any implementation.

## What This Is

A daily scan across a broad stock universe (S&P 500 + ASX 200, same combined-universe
precedent as `mytrader/cash_value_scan.py`) that flags any ticker whose closing price
has **crossed above its 150-day or 200-day moving average within the last N trading
days** — a plain, direct breakout signal, reported per ticker per MA (a name can fire
on 150DMA only, 200DMA only, both, or neither).

**This is deliberately simpler and broader than what already exists.** Two related but
materially different checks are already live and this tool must not duplicate either:

- **Goat Heartbeat Scan** (`goat/heartbeat.py` + `heartbeat_scan.py`) — a *compound*
  pattern: a tight sideways base sitting at/above a flat-to-rising 150DMA, THEN a fresh
  50DMA cross-and-slope-up. Narrow, high-conviction, rare (built specifically to find
  webinar-style "Stage 2" entries). Scoped to S&P 500 constituents of *currently rising
  sectors* only.
- **Goat Monitor's `exit_check.py`** — flags **existing holdings/watchlist tickers**
  closing *below* their 150DMA (downside protection on positions Shaun already has/is
  tracking). Opposite direction, and scoped only to what's already tracked, not a
  discovery scan across the whole universe.

This tool is neither of those: no base-pattern requirement, no "rising sector" filter,
no compound AND-gate, and it's specifically a **discovery** scan across the *whole*
universe (not just holdings/watchlist), checking the **150DMA and 200DMA themselves**
(not the 50DMA), for the **upside** cross only (someone wants an "opportunity found"
list, not a risk alert — the downside case is already `exit_check.py`'s job).

## Reference code to reuse (read all of these during `/plan-feature`)

- **`goat/sector_rotation.py`'s `check_sector_breakout()`** — the sign-flip
  cross-detection idiom this whole feature is built from: `diff = close - ma`,
  `sign = diff.gt(0).astype(int) - diff.lt(0).astype(int)`, find the last sign change,
  measure `trading_days_since_cross`, compare against a recency window. This is the
  exact mechanic to reuse for 150DMA/200DMA, just with a different MA window and applied
  per-stock instead of per-sector-ETF.
- **`goat/heartbeat.py`'s own docstring** — read this before writing a line of code. It
  documents that this codebase has an **explicit, deliberate policy of NOT
  refactoring the cross-detection idiom into a shared helper** across existing modules
  (`macro_indicators.check_gold_trend()` and `sector_rotation.check_sector_breakout()`
  are independently-written duplicates on purpose — see that docstring's own citation).
  **Do not go retrofit `sector_rotation.py` or `heartbeat.py` to import from this new
  module, or vice versa.** Writing one clean, newly-parameterized function *within* the
  new `dma_breakout_scan.py` module itself (e.g. `check_ma_cross(ticker, label, close,
  ma_days, recency_days) -> CheckResult`, called once for 150 and once for 200) is fine
  and is the right internal shape for this tool — the "no shared helper" rule is about
  not touching the two *existing* independent copies, not a ban on writing new code
  cleanly.
- **`goat/heartbeat_scan.py`** — the orchestrator shape to copy almost exactly: fetch a
  universe, loop tickers, run the check, skip anything already held/watchlisted/staged
  (`mt_db.get_holding_row`, `mt_db.get_watchlist_row`,
  `db.get_goat_pending_candidate`), stage genuinely new hits into
  `goat_pending_candidates`, render a pending-review markdown table, return a result
  dict. Also copy its **fundamentals-survival-context gate**
  (`fundamentals_context.compute_survival_context`, suppress `insolvency_risk` hits) —
  a raw price cross with zero quality filter will surface real junk (a beaten-down
  micro-cap bouncing off a low base crosses its 150DMA just as "cleanly" as a genuine
  recovery), so this gate is not optional here the way it might be for a
  higher-conviction signal.
- **`mytrader/cash_value_scan.py`** — the combined **US + ASX 200 universe** pattern
  (`asx200_universe.fetch_asx200_constituents()` alongside a US source), its
  courtesy-delay + DEGRADED-banner-on-rate-limit handling, and its use of the shared
  ethical filter (`scripts.ethical_filter` — drop defense contractors, tag `BA`/`PLTR`
  `REVIEW:`). This tool should run the same ethical filter for consistency — nothing
  about a moving-average cross is defense-specific, but every other broad-universe scan
  in this codebase applies it and this one shouldn't be the exception.
- **`goat/sp500_universe.py`** — the cached S&P 500 constituent list (ticker + GICS
  sector), reused as-is for the US leg.
- **`mytrader/asx200_universe.py`** — the cached ASX 200 constituent list, reused as-is
  for the AU leg (same cross-package import direction already established: goat imports
  from `mytrader`, not the reverse — see `openinsider.py`'s move history for the
  precedent).
- **`goat/price_history.py`'s `fetch_close_history()`** — the close-only price fetch
  both `sector_rotation.py` and `heartbeat.py` already use.
- **`mytrader/config.py`'s `GOLD_MA_HISTORY_LOOKBACK_DAYS` (500 calendar days, sized for
  a 200-day MA + slope + recency margin)** — the precedent for how much history a
  200DMA check needs; `goat/config.py`'s `GOAT_HEARTBEAT_HISTORY_LOOKBACK_DAYS` (500)
  is the same number for the same reason. Reuse 500 here too rather than inventing a
  new constant value (a new named constant is still fine, just the same number).
- **`db.get_goat_pending_candidate` / `insert_goat_pending_candidate` /
  `get_all_goat_pending_candidates`** — the existing generic staging table. **Important
  constraint to design around:** `goat_pending_candidates.ticker` is `UNIQUE` with no
  `source` in the key — a ticker can only be staged once regardless of which scan found
  it first. `heartbeat_scan.py` already handles this by skipping a ticker that's already
  staged (`db.get_goat_pending_candidate(conn, ticker) is not None: continue`) — this
  tool must do the same, meaning a name already staged by Heartbeat Scan (or the
  existing sector scan) won't also get staged here even if it independently qualifies.
  Worth surfacing in the report text so a "0 new" day isn't mysterious when the DMA
  cross count was actually nonzero.
- **`goat/monitor.py`'s `maybe_notify` / WhatsApp+toast pattern** — reuse for "N new DMA
  breakout candidate(s) found" on a fresh-hit day, silent on zero (same convention as
  Heartbeat Scan and the AI-Resistant Moat Scan).

## Design decisions to nail down in `/plan-feature` (this doc's best-guess defaults)

1. **Recency window ("just" crossed).** `GOAT_SECTOR_CROSS_RECENCY_DAYS` (10 trading
   days) is the existing precedent for a 50DMA cross. A 150/200DMA is far slower-moving,
   so a cross is a rarer, more significant event — a wider window (e.g. still 10, or
   stretched to 15) may make more sense. Start with 10 for consistency with the rest of
   the codebase's cross-detection checks, tune after the first live run (same
   "start conservative, tune from real output" precedent as Cash-Value Scan's threshold
   and the Moat Scan's stage threshold).
2. **150DMA and 200DMA are two independent checks, not one gate.** Report both per
   ticker (a name can cross one, the other, both, or neither on a given run) rather than
   requiring both — the user's own request named both MAs as an "or".
2a. **MA slope: informational, not a gate.** Unlike Heartbeat Scan (which hard-requires
   the 150DMA to be flat-to-rising as part of its compound AND), this tool should surface
   the plain cross event and note the MA's current slope in the detail text as context,
   not filter on it — keeping this tool the simple, broad signal it was asked for rather
   than reinventing Heartbeat Scan's stricter pattern under a different name.
3. **Liquidity/quality floor.** A raw cross-detection scan over 700 names with zero
   filter will be noisy (illiquid micro-caps, one-off gap-driven crosses). Recommend a
   minimum average-volume and/or market-cap floor, mirroring Cash-Value Scan's
   `sh_avgvol_o100`-style guard — exact numbers TBD in `/plan-feature`, but don't ship
   with zero floor.
4. **`sector_label` schema mismatch for ASX names.** `goat_pending_candidates.sector_label`
   is `NOT NULL`, populated today via `GOAT_GICS_TO_ETF_SECTOR_LABEL` (US GICS → SPDR
   ETF label mapping) — that mapping has no entry for ASX-listed names. Decide: reuse
   the raw Yahoo/ASX sector string for AU tickers, hardcode a literal `"ASX"` placeholder,
   or extend the label mapping. Needs a real decision, not a silent `KeyError`/skip like
   `heartbeat_scan.py`'s current unmapped-GICS-sector handling (which just skips and
   logs — acceptable there since it only ever sees US GICS values; here it would silently
   drop every single ASX name, which is not acceptable given ASX is half the point).
5. **Ethical filter.** Apply it (see Cash-Value Scan precedent above) — no reason this
   scan should be the one broad-universe screen in the codebase that skips it.
6. **MLP filter?** Probably not needed — MLPs are rare inside the S&P 500 and ASX 200
   index constituent lists this scan draws from (unlike my-trader's Find, which takes
   an arbitrary user-typed ticker). Confirm during `/plan-feature` rather than assuming.
7. **Full universe daily, not a rotation slice.** Cash-Value Scan already proves ~700
   sequential yfinance lookups/day with a small per-call delay is workable (~2.5 min
   added run time). This check is pure price-history (no `.info`/fundamentals call per
   name except the survival-context gate on actual hits, which will be a small number),
   so it's lighter than Cash-Value Scan, not heavier — no need for the Moat Scanner's
   1/5-rotation-per-day compromise (that one exists because of an LLM call per name).
8. **Staging + alert pattern.** Follow Heartbeat Scan exactly: stage genuinely-new hits
   (not held/watchlisted/already-staged, survival-context-clean) into
   `goat_pending_candidates` with `source="goat_dma_breakout_scan"`, render
   `investments/goat/dma-breakout-candidates-pending-review.md`, one WhatsApp+toast on a
   fresh-hit day, silent on zero. Reviewed the same way as every other Goat staging file
   — `promote-candidate` / `dismiss-candidate`.
9. **Schedule.** VPS systemd timer, daily. Existing Goat/investments UTC slots today:
   21:35 (Goat Monitor), 21:50 (Goat Insider Scan), 22:05 (Fourteen Crash Signals),
   22:30 (Cash-Value Scan), 22:45 (Goat Heartbeat Scan), 23:30 (AI-Resistant Moat Scan).
   Suggest **22:55 UTC** — right after Heartbeat Scan (so a name already staged by
   Heartbeat that morning is correctly skipped here, not staged twice under a race),
   before the Moat Scan. Confirm no VPS resource contention at that slot during
   `/plan-feature`.

## Recommended shape

- New module `investments/goat/goat/dma_breakout_scan.py`:
  `fetch_universe_closes()` (S&P 500 + ASX 200 combined, ethical-filtered),
  `check_ma_cross(ticker, label, close, ma_days, recency_days) -> CheckResult` (called
  per ticker for 150 and 200), `run_dma_breakout_scan(conn) -> dict` (orchestrator,
  mirrors `run_heartbeat_scan`), `render_dma_breakout_candidates_report(result) -> str`,
  `write_dma_breakout_candidates_report(result) -> None`.
- New CLI subcommand `scan-dma-breakout` in `goat/main.py`, dispatch-wired the same way
  as `scan-heartbeat`/`scan-sectors`.
- New config constants in `goat/config.py`: `GOAT_DMA_BREAKOUT_MA_DAYS = (150, 200)`,
  `GOAT_DMA_BREAKOUT_CROSS_RECENCY_DAYS`, `GOAT_DMA_BREAKOUT_HISTORY_LOOKBACK_DAYS`,
  liquidity/market-cap floor constant(s), report path constant.
- Output: `investments/goat/dma-breakout-candidates-pending-review.md` (pending-review
  table: Ticker | Name/Sector | MA crossed (150/200/both) | Trading days since cross |
  % above MA now | MA slope | Flagged date), plus a `promote-candidate`/
  `dismiss-candidate` review flow already shared with every other Goat staging file.
- No new uv-workspace member, no new database, no new package — extends `goat` in
  place, reusing its existing `goat_pending_candidates` table, `mt_db` cross-import,
  and WhatsApp/toast plumbing.

## Deployment / integration notes

- Add the new timer: `second-brain-goat-dma-breakout-scan.timer` +
  `.service` in `scripts/systemd/`, copying `second-brain-goat-heartbeat-scan.{timer,service}`
  almost verbatim (`ExecStart=... python -m goat.main scan-dma-breakout`).
- Add a row to `investments/TOOLS.md`'s "Daily Read" table and "Automated (scheduled)"
  table (same shape as the Goat Heartbeat Scan row), plus a "Goat DMA breakout scan
  (on-demand)" row in "Manual / on-demand only" (`-Package goat -Command
  "scan-dma-breakout"`).
- No changes needed to `scripts/deploy.ps1`'s `$TIMERS` stop/start list beyond adding
  the new timer name (the list already includes every other Goat timer).

## Validation (once built)

```powershell
.\scripts\invoke_investments.ps1 -Package goat -Command "scan-dma-breakout"
```

Expected output: `investments/goat/dma-breakout-candidates-pending-review.md`, a
WhatsApp+toast alert only if at least one genuinely new candidate was staged.

Test with hand-built fixtures covering: a close series with a clean cross above the
150DMA N days ago (should fire); a cross above the 200DMA but not the 150DMA on the
same series (should fire the 200DMA check only); a ticker that crossed above 150DMA
too long ago to be "fresh" (should not fire); a ticker with insufficient history for a
200-day MA (should return `unknown`, not crash); a ticker already on the watchlist
(should be skipped from staging even though the check itself still fires); a ticker
already staged by Heartbeat Scan under a different source (should be skipped from
staging here too, per the `UNIQUE ticker` constraint) — assert the report text makes
this skip legible rather than looking like a silent miss.
