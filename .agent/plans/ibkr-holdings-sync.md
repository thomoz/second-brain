# Feature: IBKR Holdings Sync

The following plan should be complete, but it's important that you validate documentation and codebase patterns and task sanity before you start implementing.

Pay special attention to naming of existing utils, types, and models. Import from the right files etc.

This plan covers **Phase 1 (connect + read) and Phase 2 (reconcile + bucket-assign)** of `investments/my-trader/ibkr-sync-handoff.md`'s scope. The handoff's own "Phase 3" (bucket assignment for new positions) is folded into Phase 2 below rather than kept as a separate phase — it turned out to be a small, natural extension of the reconcile flow (one new CLI command), not a distinct body of work.

## Feature Description

A read-only, on-demand sync that connects to Shaun's own IB Gateway (running locally on his machine, already logged into his live IBKR account) and pulls his real brokerage positions, then reconciles them against my-trader's `holdings` table in `investments/briefs-finance/data/investments.db`. It replaces the fully-manual "I bought/sold N shares of TICKER" conversational entry with a "does this match what IBKR actually shows me?" check Shaun can run whenever he wants. It never places trades, never runs automatically, and never touches the VPS.

## User Story

As Shaun, tracking his holdings manually via `holding-buy`/`holding-sell`
I want an on-demand check that connects to my real IBKR account and shows me any mismatch against my tracked holdings
So that I catch drift (missed a manual entry, fat-fingered a quantity, forgot a sell) without re-entering everything by hand or trusting my own bookkeeping blindly.

## Problem Statement

Today, `holdings` table rows only change when Shaun tells the assistant about a trade. There's no way to verify the tracked state actually matches reality, and no path to discover a position IBKR shows that was never entered at all.

## Solution Statement

Add a new `mytrader/ibkr_sync.py` module using `ib_async` (see Research below) to connect to a local IB Gateway instance and fetch `ib.positions()` + `ib.accountSummary()`. A new `sync-ibkr` CLI command prints a diff against `holdings` (matched-but-different, new-to-IBKR, tracked-but-missing-from-IBKR) with zero writes. A `sync-ibkr --apply` command commits qty/avg-price corrections for tickers that already exist in `holdings` (batch, all-or-nothing per Shaun's chosen review style) and stages brand-new IBKR positions in a new `ibkr_pending_positions` table — mirroring the existing `pending_candidates`/`promote-candidate` staging pattern exactly, since a new position has no bucket yet and bucket is Shaun's own strategic call, not something IBKR can supply. A new `ibkr-assign-bucket` command (mirrors `promote-candidate`) turns a staged position into a real holding once Shaun gives it a bucket. Positions tracked in `holdings` but no longer seen in IBKR are only ever reported, never auto-removed (same "never auto-delete" precedent as `[[feedback_no_auto_delete_watchlist]]`) — Shaun resolves those via the existing `holding-sell` command or by leaving them alone.

## Feature Metadata

**Feature Type**: New Capability
**Estimated Complexity**: Medium (new external dependency + new local-process integration pattern the codebase hasn't done before; the DB/CLI/staging shape itself is a close mirror of `candidate_sync.py`)
**Primary Systems Affected**: New `investments/my-trader/mytrader/ibkr_sync.py`; `investments/my-trader/mytrader/db.py` (new table); `investments/my-trader/mytrader/main.py` (3 new CLI subcommands); `investments/my-trader/pyproject.toml` (new dependency); `Memory/SOUL.md` (wording clarification)
**Dependencies**: `ib_async` (new), a locally running, logged-in IB Gateway process (Shaun's own machine, not part of this codebase)

---

## Decisions Already Made (with Shaun, this session — do not re-litigate)

1. **App**: IB Gateway, not full TWS. Shaun has never used either — Phase 0 below (Setup Guide) exists specifically to walk him through it from zero, so don't assume prior familiarity anywhere in the CLI's error messages or docs.
2. **Account**: Live account (matches his real `holdings.md`), not paper. IB Gateway live port is **4001** (paper would be 4002 — TWS's equivalent ports are 7496 live / 7497 paper, not used here but worth knowing if Shaun ever switches to TWS).
3. **Reconciliation review style**: whole-batch diff, review-then-apply-together — not line-by-line confirm. `sync-ibkr` (dry-run) prints the full diff; `sync-ibkr --apply` commits all matched-ticker corrections at once. (New-position staging and removed-position reporting still require their own separate explicit action per position — see Solution Statement — that's a "never auto-write/delete" rule, not a contradiction of "batch review.")
4. **Scope**: positions (`ib.positions()`) **and** account summary (`ib.accountSummary()`, NetLiquidation + TotalCashValue) — printed for context on every `sync-ibkr` run, not persisted anywhere (holdings.md has no column for it, and Shaun didn't ask for history here, just live context).
5. **SOUL.md**: `Memory/SOUL.md`'s "Never access financial systems or make purchases" rule is confirmed (2026-08-11, recorded in the handoff) to mean no autonomous trading/money movement — read-only account queries the user explicitly requests are in scope. This plan updates the wording (Task 0.2) so a future cold read doesn't re-block on the same question.

---

## CONTEXT REFERENCES

### Relevant Codebase Files — READ THESE BEFORE IMPLEMENTING

- `investments/my-trader/ibkr-sync-handoff.md` (full file) — source design doc; every "Decisions Already Made" item above traces back to this file plus this session's follow-up answers.
- `investments/my-trader/mytrader/candidate_sync.py` (full file, 64 lines) — **the pattern to mirror almost exactly** for the new-position staging flow: read external source → normalize ticker → skip if already in holdings/watchlist/pending → insert into a staging table → return what was added. `sync_new_candidates()`'s shape (lines 36-63) is the direct template for a new `stage_new_ibkr_positions()`-equivalent function.
- `investments/my-trader/mytrader/db.py` (full file, 541 lines) — schema/CRUD shape to mirror:
  - `init_mytrader_tables()` (lines 27-145) — one `executescript()` CREATE TABLE block; add the new `ibkr_pending_positions` table here, same shape as `pending_candidates` (lines 74-81).
  - `get_pending_candidate`/`get_all_pending_candidates`/`insert_pending_candidate`/`delete_pending_candidate` (lines 251-277) — copy this exact CRUD shape for `ibkr_pending_positions` (rename fields: `ticker`, `name`, `qty`, `avg_price`, `currency`, `asset_type`, `exchange_raw` — the last one worth keeping to help debug ticker-mapping issues, see Gotchas).
  - `get_all_holdings(conn)` (lines 168-169) — the read this feature reconciles against.
  - `upsert_holding(conn, *, ticker, name, asset_type, bucket, qty, avg_price, currency, last_expense_ratio)` (lines 176-207) — used by both the matched-ticker `--apply` correction path and `ibkr-assign-bucket`.
- `investments/my-trader/mytrader/main.py` (full file, 347 lines) — CLI dispatch shape: every command is a thin `cmd_*(args)` function opening its own connection via `_open_conn()` (lines 8-17), doing work, closing the connection, printing a one-line result. `cmd_sync_candidates`/`cmd_promote_candidate`/`cmd_dismiss_candidate` (lines 174-224) are the exact shape for the three new commands (`sync-ibkr`, `ibkr-assign-bucket`, `ibkr-dismiss-position` for a staged position Shaun decides not to track after all — mirrors `dismiss-candidate`).
- `investments/my-trader/mytrader/holdings_ops.py` (full file, 62 lines) — `add_or_update_holding()`'s buy/sell weighted-average logic. Not reused directly (this feature writes exact IBKR-reported qty/avg-cost, it doesn't compute a weighted average from a delta), but read it so the new correction-write path in `ibkr_sync.py` doesn't accidentally duplicate or conflict with this logic — it should call `db.upsert_holding()` directly with IBKR's own numbers, not go through `add_or_update_holding()`.
- `investments/my-trader/mytrader/tickers.py` (full file, 15 lines) — `normalize()` (BRK.B → BRK-B) and `asx_variant()` (append `.AX`). The IBKR→my-trader ticker mapping (Gotcha below) must produce values consistent with what these two functions already produce elsewhere, since `holdings` rows are keyed by ticker string built from these.
- `investments/my-trader/mytrader/snapshot.py` (full file, 175 lines) — `regenerate_all(conn)` must be called after any write that changes `holdings` (matched-ticker `--apply` corrections, `ibkr-assign-bucket`), same as every other write path in the codebase.
- `investments/my-trader/mytrader/tests/conftest.py` (full file, 142 lines) — **note the accumulated pattern of autouse fixtures that stub every real network call** (`_no_real_backtest_refresh`, `_no_real_recent_return_fetch`, `_no_real_crash_drawdown_fetch`, etc., lines 50-141). This feature needs the same treatment: add a new autouse fixture stubbing the real IB Gateway connection so no test in the suite ever attempts a real socket connection (there is no CI/local Gateway running during `pytest`, so an unstubbed real call would just hang or error — same class of bug the file's own docstring on `_isolate_snapshot_paths` (lines 29-47) warns happened before with unpatched paths).
- `investments/my-trader/mytrader/tests/test_gold_cot.py` (lines 1-60 read; full file for more) — the pattern for testing a module with one private fetch function: `gold_cot._fetch_cot_history()` is the sole real-I/O boundary, monkeypatched in tests (`test_compute_today_cot_returns_none_when_fetch_fails`, lines 54-56), with all the actual logic (parsing, classification) tested directly against plain data structures. `ibkr_sync.py` should have the same shape: one private `_connect_and_fetch()` (or similar) doing the real `ib_async` connect/positions/accountSummary/disconnect calls, and pure functions for diff computation / ticker mapping that take already-fetched data as plain arguments.
- `investments/my-trader/mytrader/tests/test_candidate_sync.py` (full file, 124 lines) — the test shapes to mirror for the new staging-table tests: insert-when-new, skip-when-already-in-holdings, skip-when-already-in-watchlist, skip-when-already-staged, don't-reprocess-on-second-run.
- `investments/my-trader/mytrader/monitor.py` and `investments/my-trader/mytrader/tests/test_monitor.py` (lines 35-38, 258-266) — **read this to understand why `sync-ibkr` must never be called from `run_monitor()`.** `candidate_sync.sync_new_candidates()` *is* called from `run_monitor()` (re-added 2026-07-19 — see the test's own docstring) because it only ever stages data, so it was judged safe to automate. IBKR sync is different: it requires a locally running, already-logged-in IB Gateway process, which will never be true on the VPS's scheduled run (`scripts/systemd/second-brain-mytrader-monitor.service` runs `python -m mytrader.main monitor` unattended) and isn't reliably true locally either at Monitor's cadence. Do not add `ibkr_sync` calls anywhere in `monitor.py`, and do not add a new systemd unit for it (`scripts/systemd/second-brain-goat-monitor.service` / `second-brain-mytrader-monitor.service` are the pattern to explicitly *not* follow here).
- `investments/my-trader/mytrader/config.py` (skim; it's 501 lines of accumulated constants) — add the new `IBKR_*` constants at the end, following the file's own convention of a dated comment block explaining sourcing/rationale for each new constant group (see e.g. lines 480-501's COT block for the most recent example of this style).
- `Memory/SOUL.md` (full file, 51 lines) — line 11, `"Never access financial systems or make purchases"`, is the line Task 0.2 updates.

### New Files to Create

- `investments/my-trader/mytrader/ibkr_sync.py` — connection, fetch, ticker-mapping, and diff-computation logic.
- `investments/my-trader/mytrader/tests/test_ibkr_sync.py` — unit tests (no real Gateway connection).
- `investments/my-trader/ibkr-setup-guide.md` — plain-language, first-time setup walkthrough for Shaun (he has never used IB Gateway). See Task 0.1.

### Relevant Documentation — READ BEFORE IMPLEMENTING

- [ib_async GitHub](https://github.com/ib-api-reloaded/ib_async) and [ib_async docs](https://ib-api-reloaded.github.io/ib_async/readme.html)
  - Why: `ib_insync` (the library the handoff originally named) lost its maintainer in early 2024 and is no longer actively maintained; `ib_async`, under the `ib-api-reloaded` GitHub org, is the actively maintained continuation with the same API surface. **Use `ib_async`, not `ib_insync`** — this resolves the handoff's own open question #4.
  - Connection: `ib.connect(host, port, clientId=N)` is synchronous and manages its own asyncio event loop internally — fine to call directly from a plain CLI script (no Jupyter/`util.startLoop()` concern here, since `main.py`'s dispatch never runs inside an existing event loop).
  - `ib.positions(account='')` returns `Position(account, contract, position, avgCost)` — `contract` is a `Contract` object with `.symbol`, `.exchange`, `.currency`, `.secType`, `.primaryExchange`.
  - `ib.accountSummary(account='')` returns `AccountValue(account, tag, value, currency, modelCode)` rows; request/filter for `tag in ('NetLiquidation', 'TotalCashValue')`.
- [TWS API: Initial Setup](https://interactivebrokers.github.io/tws-api/initial_setup.html) and [IBKR API Settings guide](https://www.interactivebrokers.com/campus/trading-lessons/installing-configuring-tws-for-the-api/)
  - Why: exact steps for Task 0.1's setup guide — enable "Enable ActiveX and Socket Clients", set the socket port, add `127.0.0.1` as a trusted IP (or restrict to localhost-only), and **leave "Read-Only API" checked** (it is checked/enabled by default and blocks all API order placement at the account-settings level — this is a real, IBKR-enforced backstop underneath this codebase's own read-only design, worth calling out explicitly to Shaun as defense-in-depth, not just "trust the code").
- [IBKR: Auto Restart Considerations](https://www.ibkrguides.com/traderworkstation/auto-restart-considerations.htm)
  - Why: IB Gateway requires periodic re-authentication (daily without auto-restart configured, weekly with it — the security token reset runs Sundays ~1am ET). Since this is on-demand/local-only (no scheduled sync), Shaun just needs to know: if `sync-ibkr` fails to connect, the most likely cause is IB Gateway isn't open or has logged itself out — reopen it and log back in (2FA happens in the Gateway app itself, this codebase never sees IBKR credentials). Document this as the primary troubleshooting step, not a bug.

### Patterns to Follow

**Staging-then-explicit-promote (the core pattern this feature reuses):**
```python
# candidate_sync.py:36-63 — mirror this shape for stage_new_ibkr_positions()
def sync_new_candidates(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    ...
    for row in rows:
        normalized = tickers.normalize(row["ticker"])
        if db.get_holding_row(conn, normalized) is not None:
            continue
        ...
        db.insert_pending_candidate(conn, ticker=normalized, ...)
        added.append({"ticker": normalized, ...})
    return added
```

**CLI command shape (main.py):**
```python
# main.py:189-210 — promote_candidate is the template for ibkr-assign-bucket
def cmd_promote_candidate(args) -> None:
    from .db import delete_pending_candidate, get_pending_candidate, upsert_watchlist_row
    from .snapshot import regenerate_all
    from .tickers import normalize

    conn = _open_conn()
    ticker = normalize(args.ticker)
    pending = get_pending_candidate(conn, ticker)
    if pending is None:
        conn.close()
        print(f"No pending candidate found for {ticker}.")
        return
    upsert_watchlist_row(conn, ...)
    delete_pending_candidate(conn, ticker)
    regenerate_all(conn)
    conn.close()
    print(f"Promoted {ticker} ...")
```

**Real-I/O isolated behind one private function (for testability):**
```python
# gold_cot.py's shape — mirror for ibkr_sync.py
def _fetch_cot_history() -> pd.DataFrame | None: ...  # real network call
def compute_today_cot() -> ... :
    history = _fetch_cot_history()
    if history is None:
        return None
    ...  # pure logic, tested directly with fixture DataFrames
```

**Config constants (config.py's own convention — dated comment block per addition):**
```python
# Added 2026-08-11 -- IBKR Holdings Sync (see investments/my-trader/ibkr-sync-handoff.md
# and .agent/plans/ibkr-holdings-sync.md). Local-only, read-only, on-demand -- never
# wired into monitor.py or any systemd unit. Live account confirmed with Shaun
# 2026-08-11; IB Gateway (not TWS) is the app he's running.
IBKR_HOST = "127.0.0.1"
IBKR_PORT = 4001  # IB Gateway, live account. Paper would be 4002; TWS equivalents are
                    # 7496 (live) / 7497 (paper), not used here.
IBKR_CLIENT_ID = 27  # arbitrary, must be unique per simultaneous API client connected
                       # to the same Gateway instance -- change if this ever collides.
```

---

## IMPLEMENTATION PLAN

### Phase 0: Setup (prerequisite — Shaun's own manual steps + SOUL.md wording)

Nothing here is code the execution agent can validate by running tests — it's a doc Shaun follows himself, and a wording fix.

**Tasks:**
- Write `investments/my-trader/ibkr-setup-guide.md`, a first-time walkthrough (Shaun has never used IB Gateway or TWS): download/install IB Gateway, log in (2FA happens in the app), open Global Configuration → API → Settings, check "Enable ActiveX and Socket Clients", confirm "Read-Only API" stays checked, set socket port to 4001 (live), add `127.0.0.1` to trusted IPs (or restrict to localhost). Include a troubleshooting note: if `sync-ibkr` can't connect, Gateway is probably closed or logged out (daily/weekly re-auth is normal, not a bug) — reopen and log back in, then retry.
- Update `Memory/SOUL.md` line 11 from `"Never access financial systems or make purchases"` to explicit wording distinguishing read-only queries from trading/money-movement (e.g. `"Never place trades, transfer funds, or otherwise modify financial account state — read-only account/portfolio queries the user explicitly requests (e.g. IBKR holdings sync) are in scope"`). Reference this plan/handoff inline so a future cold read has the paper trail. Note: `soul-protect.py`'s PreToolUse hook blocks automated-agent edits to `SOUL.md`, not user-directed edits in an interactive session — confirm this edit goes through cleanly; if the hook blocks it, that's expected for autonomous agents and Shaun needs to make this specific edit himself.

### Phase 1: Connect + Read (no DB writes)

**Tasks:**
- Add `ib_async` to `investments/my-trader/pyproject.toml`'s `dependencies` list; run `uv lock` at the workspace root.
- Add the `IBKR_HOST` / `IBKR_PORT` / `IBKR_CLIENT_ID` constants to `mytrader/config.py` (see Patterns above).
- Create `mytrader/ibkr_sync.py` with:
  - `_connect() -> IB` — `from ib_async import IB; ib = IB(); ib.connect(config.IBKR_HOST, config.IBKR_PORT, clientId=config.IBKR_CLIENT_ID); return ib`. Let connection failures raise (don't swallow) — `main.py`'s `cmd_sync_ibkr` catches and prints a friendly message pointing at the setup guide's troubleshooting section, not this module.
  - `map_ibkr_ticker(symbol: str, exchange: str, currency: str) -> str` — maps an IBKR `Contract`'s fields to the ticker string my-trader expects. Best-guess starting logic (confirm against Shaun's real account at Task 1's manual validation step, do not ship unverified): if `currency == "AUD"` (or `exchange == "ASX"`), return `tickers.asx_variant(symbol)`; otherwise return `tickers.normalize(symbol)`. **Gotcha**: dual-class tickers like BRK.B may come back from IBKR as `"BRK B"` (space) rather than `"BRK.B"` — `tickers.normalize()` doesn't currently handle a space variant. Confirm the real string IBKR returns for any dual-class holding Shaun actually has (currently none in `holdings.md`'s Bucket 1, per `seed.py`, so this may be untestable against real data yet — don't invent a mapping for a case that can't be verified, just note it as a known gap in the module docstring).
  - `fetch_positions() -> list[dict]` — connects, calls `ib.positions()`, maps each to `{"ticker": ..., "name": None, "qty": position.position, "avg_price": position.avgCost, "currency": contract.currency, "asset_type": "stock", "exchange_raw": contract.exchange}` (name is unavailable from `positions()` alone — leave `None`, same as `holdings_ops.add_or_update_holding` already tolerates), disconnects, returns the list. **Note**: IBKR's `avgCost` for stocks may already include per-share commission depending on account settings — flag this in a docstring; it's a known IBKR quirk, not a bug in this code, and not solvable without live-account confirmation.
  - `fetch_account_summary() -> dict[str, str] | None` — connects, calls `ib.accountSummary()`, filters for `NetLiquidation`/`TotalCashValue`, disconnects, returns `{"net_liquidation": ..., "total_cash": ..., "currency": ...}` or `None` on failure. Print-only consumer (main.py), never persisted.
  - Both fetch functions should share one internal `_with_connection(fn)` helper (connect → call `fn(ib)` → always disconnect in `finally`) rather than duplicating connect/disconnect boilerplate — but keep it simple; don't over-abstract for two call sites.
- Add `cmd_sync_ibkr(args)` to `main.py` and a `sync-ibkr` subparser (`--apply` flag, default `False` = dry run). Phase 1's version of this command only prints what `fetch_positions()`/`fetch_account_summary()` found — no `holdings` comparison yet (that's Phase 2). Catch connection errors and print a one-line message pointing at `ibkr-setup-guide.md`'s troubleshooting section instead of a raw traceback.
- **VALIDATE**: `uv run --directory investments/my-trader python -m mytrader.main sync-ibkr` — run this for real, with IB Gateway open and logged in on Shaun's machine, before writing a single line of Phase 2 code. This is the step that turns every "best-guess" ticker-mapping/field assumption above into a confirmed fact or a documented gap — do not proceed to Phase 2 on assumptions alone.

### Phase 2: Reconcile + Bucket-Assign

**Tasks:**
- Add the `ibkr_pending_positions` table to `db.init_mytrader_tables()`, mirroring `pending_candidates`'s shape: `id, ticker UNIQUE, name, asset_type, qty, avg_price, currency, exchange_raw, synced_at`.
- Add matching CRUD to `db.py`: `get_ibkr_pending_position`, `get_all_ibkr_pending_positions`, `insert_ibkr_pending_position` (INSERT OR REPLACE, not OR IGNORE — a re-run should refresh qty/avg_price if Shaun trades again before assigning a bucket), `delete_ibkr_pending_position`.
- Add `compute_diff(ibkr_positions: list[dict], holdings: list[sqlite3.Row]) -> dict` to `ibkr_sync.py` — pure function, no I/O, easy to unit test directly:
  - `matched_with_mismatch`: ticker exists in both, qty or avg_price differs beyond a small float-epsilon tolerance (reuse `holdings_ops._EPSILON`-style `1e-6`, or a slightly looser one appropriate for price comparison — document the choice).
  - `matched_no_change`: ticker exists in both, values agree.
  - `new_to_ibkr`: ticker in IBKR positions, not in `holdings` at all (any bucket).
  - `missing_from_ibkr`: ticker in `holdings`, not in IBKR positions.
- `cmd_sync_ibkr(args)` (extends Phase 1's version): always fetches + prints the full diff (all four buckets above) with the account summary. When `--apply` is passed: for every `matched_with_mismatch` ticker, call `db.upsert_holding()` with IBKR's qty/avg_price (preserve the existing bucket/name/asset_type/currency from the current `holdings` row — only qty/avg_price come from IBKR); for every `new_to_ibkr` ticker, call `db.insert_ibkr_pending_position()` (does not touch `holdings`); `missing_from_ibkr` tickers are printed only, every run, with a reminder to run `holding-sell` if the sale is confirmed. Call `snapshot.regenerate_all(conn)` after any `holdings` write. Print a summary line: corrections applied, positions staged, positions missing.
- Add `cmd_ibkr_assign_bucket(args)` to `main.py` (mirrors `cmd_promote_candidate`, main.py:189-210): reads the staged row via `get_ibkr_pending_position`, calls `db.upsert_holding()` with the staged qty/avg_price/currency/asset_type and the `--bucket` Shaun supplies, deletes the staged row, regenerates snapshot. Error message if no staged row matches the ticker.
- Add `cmd_ibkr_dismiss_position(args)` to `main.py` (mirrors `cmd_dismiss_candidate`, main.py:213-224): deletes a staged row without ever writing to `holdings` — for a real IBKR position Shaun deliberately doesn't want tracked in this tool (e.g. held for a business/entity account he doesn't track here).
- Add the three new subparsers (`sync-ibkr --apply`, `ibkr-assign-bucket --ticker --bucket [--asset-type]`, `ibkr-dismiss-position --ticker`) and dispatch entries, following the existing block structure in `main()` (main.py:252-343) exactly — same ordering convention (subparser definitions, then the `dispatch` dict).
- **Do not** modify `monitor.py` or add a systemd unit — see the Context Reference note on `monitor.py` above for why.

---

## STEP-BY-STEP TASKS

### Task 0.1: CREATE investments/my-trader/ibkr-setup-guide.md
- **IMPLEMENT**: Plain-language walkthrough for someone who has never used IB Gateway. Download/install, login/2FA, API settings (enable socket clients, port 4001, trusted IP, confirm Read-Only API stays checked), and a troubleshooting section for connection failures.
- **VALIDATE**: Manual read-through with Shaun; no automated check applies.

### Task 0.2: UPDATE Memory/SOUL.md
- **IMPLEMENT**: Reword line 11's financial-systems rule to explicitly carve out user-requested read-only queries; reference this plan.
- **GOTCHA**: `soul-protect.py` blocks *automated agent* writes to `SOUL.md` (see `command-guard.py`/`soul-protect.py` docs in root `CLAUDE.md`'s Security section) — this edit is user-directed in an interactive session, but if the hook still blocks it, surface that to Shaun rather than working around the hook.
- **VALIDATE**: `git diff Memory/SOUL.md` shows the reworded line.

### Task 1.1: UPDATE investments/my-trader/pyproject.toml
- **IMPLEMENT**: Add `"ib_async"` to `dependencies`.
- **VALIDATE**: `cd investments && uv lock && uv sync --directory my-trader`

### Task 1.2: UPDATE investments/my-trader/mytrader/config.py
- **IMPLEMENT**: Add `IBKR_HOST`, `IBKR_PORT` (4001), `IBKR_CLIENT_ID` constants with a dated comment block (see Patterns).
- **VALIDATE**: `python -c "from mytrader import config; print(config.IBKR_PORT)"` (run via `uv run --directory investments/my-trader python -c ...`)

### Task 1.3: CREATE investments/my-trader/mytrader/ibkr_sync.py
- **IMPLEMENT**: `_connect()`, `map_ibkr_ticker()`, `fetch_positions()`, `fetch_account_summary()` — see Phase 1 tasks above for exact shape.
- **PATTERN**: `mytrader/gold_cot.py`'s single-real-I/O-boundary shape.
- **IMPORTS**: `from ib_async import IB`; `from . import config, tickers`.
- **GOTCHA**: connection failures should raise, not return `None`/swallow — let `main.py` decide how to present the error to Shaun.
- **VALIDATE**: `uv run --directory investments/my-trader python -m pytest mytrader/tests/test_ibkr_sync.py -q` (once Task 1.5's tests exist)

### Task 1.4: UPDATE investments/my-trader/mytrader/main.py
- **IMPLEMENT**: `cmd_sync_ibkr(args)` (Phase 1 version: fetch + print only) and its subparser (`--apply` flag included now even though unused until Phase 2, so the CLI surface doesn't change shape later).
- **PATTERN**: `cmd_find`/`_print_assessment` (main.py:20-59) for print formatting style.
- **VALIDATE**: `uv run --directory investments/my-trader python -m mytrader.main sync-ibkr` — real connection test, IB Gateway must be open and logged in.

### Task 1.5: CREATE investments/my-trader/mytrader/tests/test_ibkr_sync.py
- **IMPLEMENT**: Unit tests for `map_ibkr_ticker()` (US ticker passthrough, ASX-currency mapping) using plain fixture inputs — no real `ib_async` connection.
- **PATTERN**: `tests/test_gold_cot.py`'s pure-function test style.
- **VALIDATE**: `uv run --directory investments/my-trader python -m pytest mytrader/tests/test_ibkr_sync.py -q`

### Task 1.6: UPDATE investments/my-trader/mytrader/tests/conftest.py
- **IMPLEMENT**: New autouse fixture stubbing `ibkr_sync._connect` (or whichever function is the real socket boundary) so no test in the suite attempts a real Gateway connection.
- **PATTERN**: `_no_real_cot_fetch` (conftest.py:131-141) — same shape, same rationale.
- **VALIDATE**: `uv run --directory investments/my-trader python -m pytest -q` (full suite; confirm no hang/network attempt from unrelated tests)

### Task 2.1: UPDATE investments/my-trader/mytrader/db.py
- **IMPLEMENT**: `ibkr_pending_positions` table in `init_mytrader_tables()`; `get_ibkr_pending_position`, `get_all_ibkr_pending_positions`, `insert_ibkr_pending_position` (INSERT OR REPLACE), `delete_ibkr_pending_position`.
- **PATTERN**: `pending_candidates` table (db.py:74-81) and its CRUD (db.py:251-277) — copy shape, rename fields.
- **VALIDATE**: `uv run --directory investments/my-trader python -m pytest mytrader/tests/test_db.py -q`

### Task 2.2: ADD compute_diff() to investments/my-trader/mytrader/ibkr_sync.py
- **IMPLEMENT**: Pure function, four-way classification (matched_with_mismatch / matched_no_change / new_to_ibkr / missing_from_ibkr) — see Phase 2 tasks for exact logic.
- **GOTCHA**: qty/avg_price float comparisons need an epsilon, not `==` — reuse `holdings_ops._EPSILON` (1e-6) for qty; consider a looser tolerance for avg_price (e.g. relative, since IBKR's commission-inclusive avgCost may legitimately differ slightly from a manually-tracked avg_price without it being a real "mismatch" worth flagging) — document whichever choice is made and why.
- **VALIDATE**: unit tests in Task 2.4.

### Task 2.3: UPDATE investments/my-trader/mytrader/main.py
- **IMPLEMENT**: Extend `cmd_sync_ibkr` to call `compute_diff()`, print all four buckets + account summary, and apply matched-mismatch corrections + stage new positions when `--apply` is passed. Add `cmd_ibkr_assign_bucket` and `cmd_ibkr_dismiss_position` + their subparsers + dispatch entries.
- **PATTERN**: `cmd_promote_candidate` / `cmd_dismiss_candidate` (main.py:189-224).
- **VALIDATE**: `uv run --directory investments/my-trader python -m mytrader.main sync-ibkr` (dry run against real account, confirm diff looks sane) then `... sync-ibkr --apply` (confirm corrections write, staging populates) then `... ibkr-assign-bucket --ticker <staged> --bucket <bucket>` (confirm it lands in `holdings.md`).

### Task 2.4: UPDATE investments/my-trader/mytrader/tests/test_ibkr_sync.py
- **IMPLEMENT**: Unit tests for `compute_diff()` covering all four classification buckets plus the epsilon-tolerance edge case.
- **VALIDATE**: `uv run --directory investments/my-trader python -m pytest mytrader/tests/test_ibkr_sync.py -q`

### Task 2.5: CREATE investments/my-trader/mytrader/tests/test_db.py additions (or verify existing file covers it)
- **IMPLEMENT**: CRUD tests for `ibkr_pending_positions`, mirroring `test_candidate_sync.py`'s insert/skip-duplicate/delete coverage for `pending_candidates`.
- **VALIDATE**: `uv run --directory investments/my-trader python -m pytest mytrader/tests/test_db.py -q`

---

## TESTING STRATEGY

### Unit Tests
- `map_ibkr_ticker()`: US-listed passthrough, AUD/ASX mapping to `.AX` suffix.
- `compute_diff()`: all four classification buckets, plus the float-epsilon edge (a tiny qty/avg_price difference should land in `matched_no_change`, not `matched_with_mismatch`).
- DB CRUD for `ibkr_pending_positions`: insert-new, INSERT-OR-REPLACE-on-restage, delete.
- `main.py` command functions: mock `ibkr_sync.fetch_positions`/`fetch_account_summary` (not `ib_async` itself) so these tests exercise the diff/apply/stage logic without touching the connection layer at all.

### Integration Tests
- None planned that require a real IB Gateway connection (not CI-safe, not reproducible) — Phase 1/2's "VALIDATE" manual steps against Shaun's real account are the closest thing to an integration test this feature gets, and they're one-time/on-demand by design, matching the feature's own on-demand nature.

### Edge Cases
- IB Gateway not running / not logged in → connection error, friendly message pointing at the setup guide, no traceback dump.
- A ticker IBKR reports that has no clean my-trader mapping yet (e.g. an options position, a currency/FX position, a mutual fund) — `fetch_positions()` should not crash on an unexpected `secType`; document as a known gap if it comes up during Phase 1's manual validation, don't try to handle every asset class blind.
- Re-running `sync-ibkr --apply` twice in a row with no real-world changes → second run should show all-`matched_no_change`, zero new writes (idempotent).
- A ticker in both `new_to_ibkr` staging and already dismissed once → re-staging on a fresh `--apply` run is expected (IBKR still reports the position); `ibkr-dismiss-position` isn't a permanent exclude-list, just "not now."

---

## VALIDATION COMMANDS

### Level 1: Syntax & Style
```powershell
uv run --directory investments/my-trader ruff check mytrader/ibkr_sync.py mytrader/main.py mytrader/db.py mytrader/config.py
```

### Level 2: Unit Tests
```powershell
uv run --directory investments/my-trader python -m pytest -q
```

### Level 3: Integration Tests
N/A — see Testing Strategy above.

### Level 4: Manual Validation (requires IB Gateway open + logged in on Shaun's machine)
```powershell
uv run --directory investments/my-trader python -m mytrader.main sync-ibkr
uv run --directory investments/my-trader python -m mytrader.main sync-ibkr --apply
uv run --directory investments/my-trader python -m mytrader.main ibkr-assign-bucket --ticker <TICKER> --bucket <bucket>
uv run --directory investments/my-trader python -m mytrader.main ibkr-dismiss-position --ticker <TICKER>
```
What each result means, plain-English:
- `sync-ibkr` (dry run) prints a diff with nothing written — if `holdings.md` changes after running this, something's wrong.
- `sync-ibkr --apply` corrects qty/avg-price on tickers already tracked and stages brand-new ones — new tickers should NOT appear in `holdings.md` yet, only after `ibkr-assign-bucket`.
- `ibkr-assign-bucket` is the only command that can add a brand-new ticker to `holdings.md`, and only for a ticker IBKR actually reported.

### Level 5: Additional Validation
- Confirm `scripts/systemd/second-brain-mytrader-monitor.service` is unchanged and `monitor.py` has no reference to `ibkr_sync` — `grep -r ibkr_sync investments/my-trader/mytrader/monitor.py` should return nothing.

---

## ACCEPTANCE CRITERIA

- [ ] `sync-ibkr` (dry run) connects to a real, locally running IB Gateway and prints positions + account summary + a four-way diff against `holdings`, with zero DB writes.
- [ ] `sync-ibkr --apply` corrects qty/avg-price only for tickers already in `holdings`; new IBKR positions are staged, never written directly; missing-from-IBKR tickers are only reported.
- [ ] `ibkr-assign-bucket` is the only path that adds a new ticker to `holdings`, requires an explicit `--bucket`, and calls `regenerate_all()`.
- [ ] `ibkr-dismiss-position` removes a staged row without ever touching `holdings`.
- [ ] `monitor.py` and every systemd unit are unmodified — this feature is never invoked automatically.
- [ ] `Memory/SOUL.md` wording updated with the read-only carve-out.
- [ ] `investments/my-trader/ibkr-setup-guide.md` exists and a first-time IB Gateway user (Shaun) can follow it unaided.
- [ ] Full test suite passes with zero real network/socket calls (verified by the new autouse fixture in `conftest.py`).
- [ ] No regressions: `uv run --directory investments/my-trader python -m pytest -q` still shows the pre-existing test count passing, plus the new `test_ibkr_sync.py` tests.

---

## COMPLETION CHECKLIST

- [ ] Phase 0 (setup guide + SOUL.md wording) done first — Shaun needs the guide before he can produce any real data for Phase 1's manual validation.
- [ ] Phase 1 fully validated against Shaun's real account before Phase 2 code is written (ticker-mapping assumptions must be confirmed, not guessed, before the diff logic depends on them).
- [ ] Phase 2 tasks completed in order.
- [ ] All validation commands executed successfully.
- [ ] Full test suite passes.
- [ ] No linting errors (`ruff check`).
- [ ] Manual CLI walkthrough (Level 4) confirms the dry-run/apply/assign/dismiss lifecycle end to end against real IBKR data.
- [ ] Acceptance criteria all met.

---

## NOTES

- **Why `ib_async` and not `ib_insync`**: the handoff named `ib_insync` as the primary option to check; live research (this plan) confirms `ib_insync`'s original maintainer passed away in early 2024 and the project is no longer actively maintained. `ib_async` (github.com/ib-api-reloaded/ib_async) is the community continuation with the same API. This is a plan-time resolution, not left as an open question.
- **Why account summary is print-only, not persisted**: Shaun's own answer was "extra context," and neither `holdings.md` nor the DB currently has anywhere meaningful to show cash/net-liq history. If this becomes something Shaun wants tracked over time later, that's a new, separate feature (possibly reusing `holdings_price_history`'s "one row per day" shape) — not scoped here.
- **Why bucket assignment isn't a separate "Phase 3"**: the handoff scoped it as its own phase, but once the staging-table design was chosen (reusing `candidate_sync.py`'s exact pattern), it turned out to be one small CLI command (`ibkr-assign-bucket`), not a body of work large enough to warrant its own phase — same discipline as not inventing complexity that isn't there.
- **What's still genuinely unverified until Phase 1's manual validation**: the exact `exchange`/`currency` values IBKR returns for Shaun's specific ASX-listed holdings (PMGOLD, IXI.AX, VAS if ever bought), whether `avgCost` includes commission in his account configuration, and whether any dual-class-share mapping gap (BRK.B-style) actually matters given he holds none today. Do not treat any of `map_ibkr_ticker()`'s logic as final until confirmed live.
