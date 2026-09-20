# Feature: DMA Breakout Scan — ETF Universe

The following plan should be complete, but it's important to validate documentation and
codebase patterns and task sanity before implementing. Pay special attention to naming of
existing utils/types/models — import from the right files, and note the currency/AUM
GOTCHA in Task 3 before touching `passes_liquidity_floor`.

## Feature Description

Extends the existing Goat DMA Breakout Scanner (`investments/goat/goat/dma_breakout_scan.py`)
with a third discovery universe — a curated set of ETFs — alongside its existing S&P 500 and
ASX 200 stock universes. Today the scan's `fetch_universe_constituents` only builds rows from
two stock-index constituent lists, so a fresh 150DMA/200DMA breakout on an ETF is invisible to
it. `check_ma_cross` (the actual signal logic) is already ticker-agnostic — the gap is
entirely in the universe source plus one downstream liquidity-gate assumption that doesn't
hold for a fund.

## User Story

As Shaun (advisor-mode Second Brain user)
I want the DMA Breakout Scan to also discover ETFs across a broad range of sectors and
industries, not just individual stocks
So that a fresh upside 150/200DMA cross on a sector, industry, broad-market, or commodity ETF
gets surfaced the same way a stock breakout already does

## Problem Statement

Confirmed live 2026-09-17 against real `holdings.md`: Shaun already holds 6 ETFs/commodity
trusts (`ETPMAG.AX`, `GOLD.AX`, `GXLD.AX`, `PMGOLD.AX`, `URNM.AX`, `OOO.AX`), none of which the
DMA Breakout Scan's discovery step could ever have surfaced as a new find — it would only ever
be caught by `mytrader Monitor`'s exit check, and only for the downside cross, and only for a
ticker already held/watchlisted. There is no discovery path for a fresh ETF breakout today.

## Solution Statement

Add a curated `GOAT_DMA_BREAKOUT_ETF_UNIVERSE` config dict — built by combining the two
curated ticker→label dicts already in this codebase (`GOAT_SECTOR_ETFS`, 11 SPDR sector ETFs,
and `GOAT_INDUSTRY_ETFS`, 39 Finviz-industry ETFs — together already spanning virtually every
GICS sector and 39 distinct industries with zero new research) with a small new curated
broad-market/commodity dict (`GOAT_DMA_BREAKOUT_BROAD_ETFS`) for funds that aren't
sector/industry-themed at all. Wire this as a third `"ETF"` market bucket into the existing
`fetch_universe_constituents` → `run_dma_breakout_scan` pipeline, unmodified otherwise. Add an
ETF-specific liquidity branch to `passes_liquidity_floor` (AUM via `totalAssets`, reusing
my-trader's existing `ETF_AUM_FLAG_USD` floor — `marketCap` is `None` for every ETF, so the
existing market-cap gate would otherwise silently kill every ETF candidate). Add a
label-based defense-themed-ETF review flag (`ITA` etc.), exclude `GOAT_BANNED_TICKERS`
members from the new ETF bucket (closes a real gap — `XLI`, banned everywhere else in `goat`,
would otherwise be staged as an ETF breakout candidate), source the company name from
`longName` at staging time when the curated dict has none, and give
`fundamentals_context.compute_survival_context` a cosmetic ETF-appropriate summary instead of
its stock-oriented "debt/equity unavailable, cash flow unavailable..." wording.

## Feature Metadata

**Feature Type**: Enhancement
**Estimated Complexity**: Low
**Primary Systems Affected**: `investments/goat` package (`config.py`,
`dma_breakout_scan.py`, `fundamentals_context.py`, tests) — no new files, no new package, no
new CLI command, no new systemd timer (the existing `scan-dma-breakout` command/timer already
covers this).
**Dependencies**: None new — reuses `mytrader.config.ETF_AUM_FLAG_USD`,
`mytrader.config.GOAT_SECTOR_ETFS`/`GOAT_INDUSTRY_ETFS` (already re-exported into
`goat.config`), and `yfinance`'s existing `totalAssets`/`longName`/`quoteType` `.info` fields
(no new yfinance calls — `data` is already fetched once per hit).

---

## Decisions confirmed with Shaun (2026-09-19)

1. **ETF liquidity floor**: reuse `mytrader.config.ETF_AUM_FLAG_USD` ($50M) — same floor
   my-trader's own `etf_mechanics.py` check already uses — for consistency across the
   workspace's two ETF-quality gates. Not a DMA-Breakout-specific number.
2. **Defense-themed ETF exposure**: add a label-based review flag (`ITA` = "Aerospace &
   Defense" → `"REVIEW: defense-themed ETF"`) rather than extending
   `ethical_filter.check_ticker` (that function is ticker-string-only and shared
   workspace-wide by design — kept local to this scan).
3. **ETF universe breadth**: Shaun wants "a very broad range of ETFs in a broad range of
   sectors and industries" — resolved by combining `GOAT_SECTOR_ETFS` (11) +
   `GOAT_INDUSTRY_ETFS` (39) + a new small `GOAT_DMA_BREAKOUT_BROAD_ETFS` curated list (7:
   broad-market + commodity funds not covered by either sector/industry dict) = 57 tickers
   total, zero overlaps, zero new scraping. This supersedes the original handoff doc's
   narrower "just SPY/QQQ/IWM/GLD/SLV" suggestion.
4. **`fundamentals_context` cosmetic wording**: include — replace the stock-oriented
   "debt/equity unavailable, cash flow unavailable... not currently cash-generating" string
   with "not applicable — fund" when `quoteType == "ETF"`.
5. **Company name for curated ETF rows**: source from `data.info.get("longName")` at staging
   time (already fetched via `market_data.fetch_ticker_data` for the liquidity check anyway —
   no new fetch) rather than hand-maintaining names in config.
6. **Scope**: DMA Breakout Scan only. Goat Heartbeat Scan ETF support is explicitly deferred
   (separate, materially different compound-pattern signal — revisit separately if wanted).
   Extending `ethical_filter.check_ticker` itself is explicitly out of scope (see #2).

---

## CONTEXT REFERENCES

### Relevant Codebase Files — READ THESE BEFORE IMPLEMENTING

- `investments/goat/goat/dma_breakout_scan.py` (whole file, 311 lines) — the module being
  extended. `fetch_universe_constituents` (lines 57-86) is where the new `"ETF"` bucket gets
  added; `passes_liquidity_floor` (lines 154-170) is where the `totalAssets`-vs-AUM branch
  goes; `run_dma_breakout_scan` (lines 173-243) is the existing loop the new bucket slots
  into — only two small changes needed inside it (Task 4), the rest is unmodified. Module
  docstring's "Ticker-qualification GOTCHA" paragraph needs a one-line addition noting ETF
  rows use already-fully-qualified literal keys, not `tickers.asx_variant`.
- `investments/goat/goat/config.py` — `GOAT_SECTOR_ETFS` (lines 48-55, 11 SPDR sector ETFs,
  `dict[str, str]`), `GOAT_BANNED_TICKERS` (lines 57-62, currently `{"XLI"}` — banned because
  RTX is a top-5 holding of that ETF, per Shaun 2026-08-17; **not currently checked anywhere
  in `dma_breakout_scan.py`** — this plan adds that check, see Task 4 GOTCHA), the
  `GOAT_INDUSTRY_ETFS` re-export (line 151, imported `from mytrader.config import
  (GOAT_INDUSTRY_ETFS, ...)`), and the existing DMA Breakout Scanner config section (lines
  436-469, `GOAT_DMA_BREAKOUT_MIN_MARKET_CAP_USD`/`_AUD`/`MIN_AVG_VOLUME` etc.) — the new
  constants from Task 1 are appended directly after this section.
- `investments/my-trader/mytrader/config.py` — `ETF_AUM_FLAG_USD` (line 312, $50M, "widely
  cited... funds below this level are economically marginal for the issuer to keep running")
  and `ETF_AUM_HEALTHY_USD` (line 319) — reuse `ETF_AUM_FLAG_USD` directly via import, do not
  redefine. `GOAT_INDUSTRY_ETFS` (line 651, the 39-ticker dict, already confirmed defense
  label `"ITA": "Aerospace & Defense"` at line 652).
- `investments/my-trader/mytrader/checks/etf_mechanics.py` (whole file, 120 lines) — the
  exact idiom to mirror: `data.info.get("quoteType") != "ETF"` detection (line 77),
  `data.info.get("totalAssets")` for AUM (line 82), comparison against
  `config.ETF_AUM_FLAG_USD` (line 95). This is a **my-trader** module reusing
  **my-trader's own** `config.ETF_AUM_FLAG_USD` directly (no cross-package import needed
  there); `dma_breakout_scan.py` lives in `goat` and needs an explicit
  `from mytrader import config as mytrader_config` import to reach the same constant — see
  `fundamentals_context.py` below for the exact precedent of that cross-package alias.
- `investments/goat/goat/fundamentals_context.py` (whole file, 101 lines) —
  `compute_survival_context(ticker, data) -> dict`. **Already imports
  `from mytrader import config as mytrader_config`** (line 12) — this is the precedent Task 3
  copies for `dma_breakout_scan.py`'s own new import. The function's `data is None` branch
  (lines 24-31) is the exact dict shape to copy for the new ETF short-circuit branch (Task 5)
  — same keys, all `None`/`False`, only `summary` differs.
- `investments/goat/goat/tests/test_dma_breakout_scan.py` (whole file, 390 lines) — every
  existing test in this file must keep passing unchanged; `_healthy_ticker_data`/
  `_insolvent_ticker_data` helpers (lines 45-65), `_patch_common` (lines 221-236),
  `TickerData` import (line 5) — reuse these exact helpers/patterns for the new tests (Task
  6). `test_passes_liquidity_floor_*` (lines 133-169) is the existing test block Task 6's new
  ETF-branch tests sit alongside.
- `investments/goat/goat/tests/test_fundamentals_context.py` — `_data(info)` helper (line 9,
  `TickerData(ticker="TEST", info=info, dividends=None)`) — reuse for the new ETF-branch test
  (Task 6).
- `investments/goat/goat/tests/conftest.py` — `db_conn` fixture, `_no_real_price_history_fetch`
  autouse fixture. `GOAT_DMA_BREAKOUT_CANDIDATES_MD_PATH` is already in the
  `_isolate_goat_report_path` fixture from the original DMA Breakout Scanner build — **no
  conftest change needed** (no new path constant is added by this plan).
- `investments/briefs-finance/scripts/ethical_filter.py` (whole file, 21 lines) —
  `check_ticker(ticker) -> tuple[bool, str | None]`, ticker-string-only, strips `.AX` suffix,
  checks against `DEFENSE_TICKERS`/`DEFENSE_REVIEW_TICKERS` (individual stock tickers like
  `LMT`/`RTX` — confirms Decision #2 above: an ETF ticker like `ITA` will never match this
  set, so a label-based check is the only way to flag a defense-themed fund). **Not called
  for the new ETF bucket** (Task 2) — deliberately, since every real call would return
  `(False, None)` for a fund ticker; the label check is the substitute, not an addition.
- `investments/dma-breakout-etf-universe-handoff.md` — the source handoff this plan
  implements; read in full for the original research (live `yfinance` `.info` field
  comparison across `SPY`/`GLD`/`ITA`/`PMGOLD.AX`, confirming `marketCap`/`debtToEquity`/
  `freeCashflow` are `None` for every ETF tested but `totalAssets`/`averageVolume` populate
  normally).
- `.agent/plans/goat-dma-breakout-scanner.md` — the original build plan for this same module;
  read for the established code style (module docstring depth, `[goat-dma-breakout-scan]`
  log prefix, `GOAT_DMA_BREAKOUT_*` config naming convention, `render_.../write_...`
  function-pair pattern) — this plan's tasks follow the same conventions throughout.

### New Files to Create

None — every change is inside existing files.

### Patterns to Follow

**Naming convention**: `GOAT_DMA_BREAKOUT_*` prefix for the two new config constants
(`GOAT_DMA_BREAKOUT_BROAD_ETFS`, `GOAT_DMA_BREAKOUT_ETF_UNIVERSE`), matching every other
constant in the existing DMA Breakout Scanner config section.

**Error handling**: unchanged — the existing per-ticker `try/except Exception as e: print(...)`
in `run_dma_breakout_scan`'s loop already wraps every constituent row regardless of market, no
new error handling needed for the ETF bucket specifically.

**Logging**: `[goat-dma-breakout-scan]` prefix, matching every existing print statement in this
module.

**Cross-package config reuse**: `from mytrader import config as mytrader_config`, then
`mytrader_config.ETF_AUM_FLAG_USD` — copy `fundamentals_context.py` line 12's exact import
style, do not redefine the constant inside `goat/config.py`.

**Other Relevant Patterns**:
- `GOAT_BANNED_TICKERS` exclusion is checked right before a candidate would be staged in every
  other Goat scan that touches it (`monitor.py` line 226, `insider_scan.py` line 184) — Task
  4 adds the same check at the equivalent point in `run_dma_breakout_scan`'s loop, not inside
  `fetch_universe_constituents` (keeping it next to the other staging-time gates, same as the
  precedent).
- Config dicts in this codebase are combined with `{**a, **b}` unpacking when one constant is
  built from others already defined earlier in the same module (no existing precedent for
  this exact pattern in `goat/config.py`, but it is the standard, most readable Python idiom
  and keeps `GOAT_DMA_BREAKOUT_ETF_UNIVERSE` a single flat `dict[str, str]` the rest of the
  pipeline can iterate generically, same shape as `GOAT_SECTOR_ETFS`/`GOAT_INDUSTRY_ETFS`).

---

## IMPLEMENTATION PLAN

### Phase 1: Foundation

Add the two new config constants to `goat/config.py`. No logic changes yet.

### Phase 2: Core Implementation

Extend `fetch_universe_constituents` with the ETF bucket (banned-ticker exclusion, defense
label review flag). Extend `passes_liquidity_floor` with the AUM-based ETF branch. Update
`run_dma_breakout_scan`'s company-name sourcing.

### Phase 3: Integration

Add the `fundamentals_context.py` cosmetic ETF branch. Update the report's intro paragraph to
mention the ETF universe.

### Phase 4: Testing & Validation

Unit-test every new branch (universe fetch, liquidity floor, fundamentals cosmetic wording,
orchestration); run the full existing `goat` suite to confirm zero regressions; validate live
on the VPS once deployed.

---

## STEP-BY-STEP TASKS

Execute in order. Each task is atomic and independently testable.

### Task 1: ADD config constants to `investments/goat/goat/config.py`

- **IMPLEMENT**: Append directly after the existing DMA Breakout Scanner section (after
  `GOAT_DMA_BREAKOUT_CANDIDATES_MD_PATH`, line 469):
  ```python
  # DMA Breakout Scanner -- ETF universe extension, per
  # investments/dma-breakout-etf-universe-handoff.md and Shaun's confirmation 2026-09-19
  # ("a very broad range of ETFs in a broad range of sectors and industries"). Breadth
  # comes from combining the two curated ticker->label dicts already in this codebase
  # (GOAT_SECTOR_ETFS, GOAT_INDUSTRY_ETFS -- together already span virtually every GICS
  # sector and 39 Finviz industries with zero new research) with a small new curated list
  # for broad-market/commodity funds neither of those covers.
  GOAT_DMA_BREAKOUT_BROAD_ETFS: dict[str, str] = {
      "SPY": "Broad Market", "QQQ": "Broad Market", "IWM": "Broad Market",
      "GLD": "Commodity - Gold", "SLV": "Commodity - Silver",
      "PMGOLD.AX": "Commodity - Gold", "URNM.AX": "Commodity - Uranium",
  }  # broad-market + commodity funds Shaun already holds (PMGOLD.AX, URNM.AX) or would
     # plausibly want a breakout alert on -- neither GOAT_SECTOR_ETFS nor
     # GOAT_INDUSTRY_ETFS is themed broadly/commodity enough to cover these.
     # PMGOLD.AX/URNM.AX are already .AX-suffixed literal keys (not bare codes needing
     # tickers.asx_variant) -- matches exactly how holdings.md stores them. v1/tunable --
     # add more broad-market/commodity names here directly if this list proves too narrow.

  GOAT_DMA_BREAKOUT_ETF_UNIVERSE: dict[str, str] = {
      **GOAT_SECTOR_ETFS, **GOAT_INDUSTRY_ETFS, **GOAT_DMA_BREAKOUT_BROAD_ETFS,
  }  # 57 tickers total (11 + 39 + 7), no overlaps -- the third fetch_universe_constituents
     # bucket (market="ETF"), see dma_breakout_scan.py.
  ```
- **PATTERN**: `goat/config.py` lines 436-469 (existing DMA Breakout Scanner section) for
  comment density/style.
- **GOTCHA**: `GOAT_SECTOR_ETFS` and `GOAT_INDUSTRY_ETFS` are both already bound names in this
  module by the time this section runs (`GOAT_SECTOR_ETFS` defined at line 48; `GOAT_INDUSTRY_ETFS`
  imported at line 151) — no import reordering needed since this section is appended after
  both.
- **VALIDATE**: `uv run --directory investments/goat python -c "from goat import config; print(len(config.GOAT_DMA_BREAKOUT_ETF_UNIVERSE))"`
  should print `57`.

### Task 2: UPDATE `fetch_universe_constituents` in `dma_breakout_scan.py` — add the ETF bucket

- **IMPLEMENT**: Append a third loop after the existing ASX loop (before `return rows`):
  ```python
      for ticker, label in config.GOAT_DMA_BREAKOUT_ETF_UNIVERSE.items():
          if ticker in config.GOAT_BANNED_TICKERS:
              continue
          review_reason = "REVIEW: defense-themed ETF" if label == "Aerospace & Defense" else None
          rows.append({
              "ticker": ticker, "label": label, "market": "ETF",
              "review_reason": review_reason, "company": "",
          })

      return rows
  ```
  Also update the function's docstring (currently "Combined S&P 500 + ASX 200 universe...")
  to say "Combined S&P 500 + ASX 200 + curated ETF universe..." and add one sentence noting
  ETF rows are not passed through `ethical_check` (ticker-string-only, doesn't apply
  meaningfully to a fund ticker — a label-based defense-theme check is the substitute).
- **PATTERN**: The existing US/ASX loops immediately above (lines 65-84) for the dict-append
  shape — this loop is simpler (no `ethical_check` call, no `tickers.normalize`/`asx_variant`
  call since `GOAT_DMA_BREAKOUT_ETF_UNIVERSE` keys are already the exact tickers to use).
- **GOTCHA**: `company` starts as `""` here (no Wikipedia-style source for a curated ETF list)
  — populated later at staging time from `data.info.get("longName")`, see Task 4. Do not try
  to hand-maintain company names in the config dict.
- **VALIDATE**: `uv run --directory investments/goat pytest goat/tests/test_dma_breakout_scan.py -k fetch_universe -v`
  (new tests written in Task 6).

### Task 3: UPDATE `passes_liquidity_floor` in `dma_breakout_scan.py` — add the ETF AUM branch

- **IMPLEMENT**: Add the import at the top of the file (in the existing
  `from mytrader import asx200_universe, db as mt_db, market_data, tickers` line):
  ```python
  from mytrader import asx200_universe, db as mt_db, market_data, tickers
  from mytrader import config as mytrader_config
  ```
  Rewrite the function:
  ```python
  def passes_liquidity_floor(market: str, data) -> bool:
      """`data` is a mytrader.market_data.TickerData | None. Returns False (fails the
      floor) when data or the required .info fields are missing -- an unusable ticker
      is never staged, matching cash_value_scan.compute_cash_value_metrics's
      None-on-missing-data posture. ETF rows (market="ETF") gate on AUM (totalAssets)
      instead of marketCap, which yfinance reports as None for every ETF -- confirmed
      live against SPY/GLD/ITA/PMGOLD.AX, see investments/dma-breakout-etf-universe-
      handoff.md. Reuses my-trader's own ETF_AUM_FLAG_USD ($50M closure-risk floor,
      same one etf_mechanics.py already gates on) rather than a new DMA-Breakout-
      specific number, confirmed with Shaun 2026-09-19 -- no currency conversion is
      applied (same simplification etf_mechanics.py already makes for AUD-denominated
      funds like PMGOLD.AX)."""
      if data is None:
          return False
      info = data.info
      avg_volume = info.get("averageVolume")
      if avg_volume is None or avg_volume < config.GOAT_DMA_BREAKOUT_MIN_AVG_VOLUME:
          return False
      if market == "ETF":
          total_assets = info.get("totalAssets")
          return total_assets is not None and total_assets >= mytrader_config.ETF_AUM_FLAG_USD
      market_cap = info.get("marketCap")
      if market_cap is None:
          return False
      floor = (
          config.GOAT_DMA_BREAKOUT_MIN_MARKET_CAP_USD if market == "US"
          else config.GOAT_DMA_BREAKOUT_MIN_MARKET_CAP_AUD
      )
      return market_cap >= floor
  ```
- **PATTERN**: `mytrader/checks/etf_mechanics.py` lines 77-100 (the `quoteType`/`totalAssets`
  idiom) for the ETF-branch logic; `fundamentals_context.py` line 12 for the
  `mytrader_config` import alias.
- **GOTCHA**: This rewrite **must not change behavior for `market == "US"`/`"ASX"`** — the
  existing tests (`test_passes_liquidity_floor_below_market_cap_fails`,
  `_below_avg_volume_fails`, `_missing_info_fields_fails`, `_passes_both`,
  `_uses_per_market_threshold`) must all keep passing unmodified. Trace through: missing
  `averageVolume` → `False` either way (same as before); missing `marketCap` on a
  non-ETF market → `False` (same as before, just checked after the volume check instead of
  in the same `or` expression — net behavior identical).
- **VALIDATE**: `uv run --directory investments/goat pytest goat/tests/test_dma_breakout_scan.py -k liquidity -v`

### Task 4: UPDATE `run_dma_breakout_scan` in `dma_breakout_scan.py` — banned-ticker exclusion + company-name fallback

- **IMPLEMENT**: Inside the loop, right after `interesting = [...]` / `if not interesting:
  continue` (before the holdings/watchlist dedup checks), add:
  ```python
                  if ticker in config.GOAT_BANNED_TICKERS:
                      continue
  ```
  Then change the staging call's `company_name` argument:
  ```python
                  company_name = c["company"] or data.info.get("longName") or ""
                  db.insert_goat_pending_candidate(
                      conn, ticker=ticker, sector_label=label,
                      signal_detail=signal_detail, source="goat_dma_breakout_scan",
                      company_name=company_name, exchange=exchange_name,
                  )
                  new_candidates.append({
                      "ticker": ticker, "sector_label": label, "detail": signal_detail,
                      "company": company_name,
                  })
  ```
  (`data` is already fetched a few lines above via `market_data.fetch_ticker_data(ticker)` for
  the liquidity check — no new fetch.)
- **PATTERN**: `monitor.py` line 226 / `insider_scan.py` line 184 (`if ticker in
  config.GOAT_BANNED_TICKERS: continue`) — same exclusion, same point in the flow (right
  before staging, after the signal itself is confirmed interesting).
- **GOTCHA**: This closes a real, previously-latent gap: `XLI` is in `GOAT_SECTOR_ETFS` (now
  part of `GOAT_DMA_BREAKOUT_ETF_UNIVERSE`) and is banned everywhere else in `goat`
  (`GOAT_BANNED_TICKERS`, because RTX — a defense contractor — is a top-5 holding). Without
  this check, `XLI` could be staged as an ETF breakout candidate despite being un-promotable
  and excluded from every other Goat scan. This check applies to every bucket (US/ASX/ETF)
  uniformly, matching the existing per-scan precedent, though only ETF tickers are in
  `GOAT_BANNED_TICKERS` today.
- **GOTCHA**: `c["company"]` is always truthy for US/ASX rows (populated from the Wikipedia
  scrape), so `company_name = c["company"] or ...` is a no-op behavior change for stocks —
  only ETF rows (where `c["company"] == ""`) actually fall through to `data.info.get("longName")`.
- **VALIDATE**: `uv run --directory investments/goat pytest goat/tests/test_dma_breakout_scan.py -k run_dma_breakout_scan -v`

### Task 5: UPDATE `compute_survival_context` in `fundamentals_context.py` — cosmetic ETF branch

- **IMPLEMENT**: Add a short-circuit branch right after the `if data is None:` block:
  ```python
      info = data.info

      if info.get("quoteType") == "ETF":
          return {
              "debt_to_equity": None, "cash_runway_years": None,
              "gross_margin": None, "operating_margin": None,
              "revenue_growth": None, "cash_generating": None,
              "insolvency_risk": False,
              "summary": "not applicable — fund",
          }

      debt_to_equity = info.get("debtToEquity")
      # ... rest of the function unchanged from here
  ```
  (Move the existing `info = data.info` line up if it isn't already the first statement after
  the `data is None` check — confirm against the current file before editing.)
- **PATTERN**: The `data is None` branch immediately above (lines 24-31) — identical dict
  shape, only `summary` text differs. This keeps every caller (`dma_breakout_scan.py`,
  `heartbeat_scan.py`, any other `compute_survival_context` caller) working unchanged, since
  `insolvency_risk` is still always `False` for a fund (same behavior as today, just with
  better wording and skipping the now-pointless debt/cash-flow computation).
- **GOTCHA**: This changes behavior for **every** caller of `compute_survival_context` on an
  ETF ticker, not just the DMA Breakout Scan — confirmed acceptable per handoff Open Question
  #4 and Decision #4 above (purely cosmetic, `insolvency_risk` stays `False` either way, no
  existing caller branches on the exact `summary` string).
- **VALIDATE**: `uv run --directory investments/goat pytest goat/tests/test_fundamentals_context.py -v`
  (new test added in Task 6).

### Task 6: ADD/UPDATE tests

- **IMPLEMENT** in `investments/goat/goat/tests/test_dma_breakout_scan.py`:
  - `fetch_universe_constituents` — monkeypatch
    `goat.config.GOAT_DMA_BREAKOUT_ETF_UNIVERSE` to a small fake dict (mirroring
    `test_sector_rotation.py`'s `GOAT_SECTOR_ETFS` monkeypatch pattern) containing at least
    one normal ETF, one `GOAT_BANNED_TICKERS` member, and one `"Aerospace & Defense"`-labeled
    ETF. Assert: the normal ETF row has `market="ETF"`, `company=""`, `review_reason=None`;
    the banned ticker is excluded entirely; the defense-labeled ETF has
    `review_reason == "REVIEW: defense-themed ETF"`.
  - `passes_liquidity_floor` — ETF branch: `TickerData(info={"totalAssets": 10_000_000.0,
    "averageVolume": 500_000})` with `market="ETF"` → `False` (below $50M floor);
    `{"totalAssets": 100_000_000.0, "averageVolume": 500_000}` with `market="ETF"` → `True`;
    missing `totalAssets` on `market="ETF"` → `False`; below-avg-volume still fails on
    `market="ETF"` too (reuses the shared volume check). Re-run the existing
    `test_passes_liquidity_floor_*` tests unmodified to confirm no US/ASX regression (Task 3's
    GOTCHA).
  - `run_dma_breakout_scan` — stage a new ETF candidate via `_patch_common` with a fake ETF
    constituent (monkeypatch `GOAT_DMA_BREAKOUT_ETF_UNIVERSE` the same way as above) and
    `ticker_data` returning `TickerData(info={..., "totalAssets": 100_000_000.0, "longName":
    "Test Fund"})`; assert the staged row's `company_name == "Test Fund"` (proves the
    `longName` fallback). Assert a `GOAT_BANNED_TICKERS` member never gets staged even when
    its `check_ma_cross` fires `"interesting"`.
- **IMPLEMENT** in `investments/goat/goat/tests/test_fundamentals_context.py`: one new test —
  `data.info = {"quoteType": "ETF"}` (via the file's existing `_data()` helper) →
  `result["summary"] == "not applicable — fund"` and `result["insolvency_risk"] is False`.
- **PATTERN**: `test_dma_breakout_scan.py`'s existing `_patch_common`/`_healthy_ticker_data`
  helpers (lines 45-65, 221-236); `test_sector_rotation.py`'s `GOAT_SECTOR_ETFS`
  monkeypatch-and-restore pattern (lines 61-67) for monkeypatching
  `GOAT_DMA_BREAKOUT_ETF_UNIVERSE`.
- **VALIDATE**: `uv run --directory investments/goat pytest goat/tests/test_dma_breakout_scan.py goat/tests/test_fundamentals_context.py -v`

### Task 7: UPDATE report intro paragraph (cosmetic)

- **IMPLEMENT**: In `render_dma_breakout_candidates_report`'s intro paragraph, change "a stock
  across the S&P 500 + ASX 200 universe" to "a stock or ETF across the S&P 500 + ASX 200 +
  curated ETF universe".
- **PATTERN**: `dma_breakout_scan.py`'s existing `render_dma_breakout_candidates_report`
  (current intro paragraph).
- **VALIDATE**: `uv run --directory investments/goat pytest goat/tests/test_dma_breakout_scan.py -k render -v`
  (existing tests only assert substring presence of specific tickers/counts, not the exact
  intro wording — should pass unmodified; visually confirm the new wording reads correctly).

---

## TESTING STRATEGY

### Unit Tests

`passes_liquidity_floor`'s ETF branch and `compute_survival_context`'s ETF branch are pure
functions — test with hand-built `TickerData`/dict fixtures, no mocking, following each file's
existing style exactly.

### Integration Tests

`run_dma_breakout_scan` and `fetch_universe_constituents` against the `db_conn` fixture with
`GOAT_DMA_BREAKOUT_ETF_UNIVERSE` monkeypatched to a small fake dict (never the real 57-ticker
list in tests — keeps tests fast and independent of future config edits) and every
network/DB-adjacent call mocked, following `test_heartbeat_scan.py`/`test_dma_breakout_scan.py`'s
existing `_patch_common` pattern.

### Edge Cases

- ETF ticker in `GOAT_DMA_BREAKOUT_ETF_UNIVERSE` that is also in `GOAT_BANNED_TICKERS` (`XLI`)
  — must never be staged even on a fresh cross.
- ETF with `label == "Aerospace & Defense"` (`ITA`) — must carry the
  `"REVIEW: defense-themed ETF"` reason into `signal_detail`, must NOT be excluded (only
  flagged, same as a borderline stock via `ethical_check`'s review path).
- ETF with missing `totalAssets` — must fail the liquidity floor, not crash or silently pass.
- ETF with `totalAssets` present but below `ETF_AUM_FLAG_USD` — must fail.
- ETF with a populated `longName` — staged `company_name` must come from it, not be blank.
- Existing US/ASX liquidity-floor tests — must all still pass unmodified (Task 3's core
  regression risk).

---

## VALIDATION COMMANDS

### Level 1: Syntax & Style

```
uv run --directory investments/goat ruff check goat/dma_breakout_scan.py goat/config.py goat/fundamentals_context.py
uv run --directory investments/goat mypy goat/dma_breakout_scan.py goat/fundamentals_context.py
```

### Level 2: Unit Tests

```
uv run --directory investments/goat pytest goat/tests/test_dma_breakout_scan.py goat/tests/test_fundamentals_context.py -v
```

### Level 3: Integration Tests

```
uv run --directory investments/goat pytest goat/tests -v
```
(full package suite — confirms nothing in the existing `goat`/`mytrader`-dependent suite
regressed.)

### Level 4: Manual Validation

**Do not run this locally against the real `investments.db`** — per `investments/TOOLS.md`
and `CLAUDE.md`, that DB is VPS-only. Once deployed:
```powershell
.\scripts\invoke_investments.ps1 -Package goat -Command "scan-dma-breakout"
```
Expected: `investments/goat/dma-breakout-candidates-pending-review.md` can now include ETF
rows (e.g. a sector/industry ETF or `PMGOLD.AX`/`URNM.AX`-style commodity ETF that just
crossed above its 150/200DMA), each passing the new AUM-based liquidity floor instead of
failing silently on a missing `marketCap`. Confirm `XLI` never appears as a staged candidate
even if it technically crosses. Confirm a defense-themed industry ETF like `ITA`, if staged,
carries the `REVIEW:` tag in its signal detail.

### Level 5: Additional Validation

Manually inspect the first live report for: a plausible company name on any staged ETF row
(proves the `longName` fallback works against real yfinance data), no duplicate rows vs.
`sector-candidates-pending-review.md`/`industry-ranking.md` (proves the `UNIQUE ticker` dedup
still holds across scans now that the same tickers exist in multiple Goat universes), and a
sane total scanned count increase of ~57 over the prior US+ASX-only baseline.

---

## ACCEPTANCE CRITERIA

- [ ] `GOAT_DMA_BREAKOUT_ETF_UNIVERSE` combines `GOAT_SECTOR_ETFS` + `GOAT_INDUSTRY_ETFS` +
      `GOAT_DMA_BREAKOUT_BROAD_ETFS` with no ticker overlaps, 57 tickers total.
- [ ] `fetch_universe_constituents` returns ETF rows with `market="ETF"`, excludes
      `GOAT_BANNED_TICKERS` members, and flags `"Aerospace & Defense"`-labeled ETFs with a
      `"REVIEW: defense-themed ETF"` reason.
- [ ] `passes_liquidity_floor` gates ETF rows on AUM (`totalAssets` vs. my-trader's
      `ETF_AUM_FLAG_USD`), not `marketCap` — and existing US/ASX behavior is unchanged.
- [ ] Staged ETF candidates get a real company name sourced from `longName` when the curated
      dict has none.
- [ ] `compute_survival_context` returns "not applicable — fund" (not the stock-oriented
      debt/cash-flow wording) for any `quoteType == "ETF"` ticker, `insolvency_risk` still
      always `False`.
- [ ] `XLI` is never staged as an ETF breakout candidate, matching its exclusion from every
      other Goat scan.
- [ ] All validation commands pass with zero errors.
- [ ] Full existing `goat` test suite passes with zero regressions.

## COMPLETION CHECKLIST

- [ ] All 7 tasks completed in order.
- [ ] Each task's validation command passed immediately after that task.
- [ ] Full `goat` test suite passes (no regressions).
- [ ] `ruff`/`mypy` clean on all touched files.
- [ ] Manual VPS run (`invoke_investments.ps1 -Package goat -Command "scan-dma-breakout"`)
      confirmed working, once deployed.
- [ ] Acceptance criteria all met.

---

## NOTES

- **No new CLI command, systemd timer, or `TOOLS.md` entry needed** — `scan-dma-breakout`
  already exists and runs daily; this plan only broadens what it scans.
- **Deployment is a separate, explicit follow-up step** — building this plan does not deploy
  anything. After implementation + tests pass, Shaun runs the normal commit/push/`deploy.ps1`
  flow; the existing VPS timer picks up the change automatically on its next scheduled run
  (no new `sudo systemctl enable` step required, unlike a brand-new timer).
- **The 57-ticker ETF universe is v1/tunable**, same "start reasonable, tune from real
  output" precedent as every other Goat scan's thresholds — if it proves too broad (noisy) or
  too narrow (missing something Shaun cares about), add/remove tickers directly in
  `GOAT_DMA_BREAKOUT_BROAD_ETFS` or `goat/config.py`'s existing `GOAT_SECTOR_ETFS`/
  `GOAT_INDUSTRY_ETFS` dicts — no code changes needed for a ticker-list edit.
- **No currency conversion** is applied for AUD-denominated ETFs (`PMGOLD.AX`, `URNM.AX`)
  against the USD-denominated `ETF_AUM_FLAG_USD` floor — this is an existing simplification
  already present in my-trader's own `etf_mechanics.py` check, not something newly introduced
  here; revisit only if it proves to matter in practice (both funds are well above $50M
  either currency, per the handoff's live-data research).
