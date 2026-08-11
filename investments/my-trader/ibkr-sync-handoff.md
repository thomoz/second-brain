# IBKR Holdings Sync — Session Handoff

## Status: Not started — design discussed 2026-08-11, ready for /plan-feature (Shaun to run in a separate session)

## What This Is

Read-only sync of Shaun's actual Interactive Brokers (IBKR) account positions into
my-trader's `holdings` table, as an alternative/supplement to the current 100%
manual "I bought/sold N shares of TICKER" conversational flow (`holdings_ops.py`).
**Local only** — this will not run on the VPS or on any schedule; it's an on-demand
sync Shaun triggers when he wants his tracked holdings to match his real account.

## SOUL.md note (resolve/record before implementation)

`Memory/SOUL.md` has a hard behavioral rule: "Never access financial systems or
make purchases." Raised this directly with Shaun before scoping this feature.
**Shaun's answer (2026-08-11): read-only holdings sync is explicitly in-scope** —
the rule is intended to block autonomous trading/purchases, not read-only account
queries. Recorded here since it's a deviation from a literal reading of a written
rule; whoever implements this should either update SOUL.md's wording to be
unambiguous (e.g. "never place trades or move money; read-only account queries for
holdings sync are permitted") or at minimum reference this handoff from there so a
future session doesn't re-block on the same question.

## Context

- **Today's holdings entry**: fully manual. Shaun tells the assistant "I bought N
  shares of TICKER", `holdings_ops.add_or_update_holding()` recomputes the
  weighted-average price and writes to the shared `investments.db` `holdings`
  table (columns: ticker, name, asset_type, bucket, qty, avg_price, currency,
  last_expense_ratio). `snapshot.regenerate_all()` then rewrites `holdings.md`.
- Buckets (1/2/3a/3b/4/ai_postcrash) are Shaun's own strategic categorization —
  IBKR has no concept of this, see Open Questions below.
- Shaun asked whether the tools could connect to his IBKR account for "instant
  access to holdings data." Two integration paths were discussed live:
  1. **IBKR Flex Queries** — a scheduled report (positions) configured in IBKR's
     Account Management, pulled via a plain authenticated HTTP GET (token + query
     ID). No persistent app/process required. Not truly real-time — IBKR queues
     these, refresh lag can range from minutes to longer depending on how it's
     configured.
  2. **TWS API via `ib_insync`/`ib_async`** — a live socket connection
     (`localhost:7497` TWS paper / `7496` TWS live / `4002` IB Gateway paper /
     `4001` IB Gateway live) to a running TWS or IB Gateway instance, giving
     real-time position data. Requires that app to be running locally at sync
     time.
- **Decision: local-only removes the main downside of option 2** (no headless
  daily-reauth burden on a VPS — Shaun just launches IB Gateway on his own machine
  when he wants to sync). Recommendation made and accepted in conversation:
  **go with `ib_insync`/`ib_async` (TWS API)**, not Flex Queries — genuinely
  real-time, and no query-lag caveat to explain to Shaun every time he asks "is
  this current?"
- No new secret needs to live in the vault for this — `ib_insync` just needs a
  host/port/clientId to connect to an already-logged-in local TWS/Gateway session
  (2FA happens once, in the TWS/Gateway app itself, not through this tool).

## Remaining Steps

### Phase 1 — Connect + read positions (read-only, no DB writes yet)

- Add `ib_insync` (or its actively-maintained fork `ib_async` — check which is
  current/healthier at implementation time) as a dependency in
  `investments/my-trader/pyproject.toml`.
- New module, e.g. `mytrader/ibkr_sync.py`: connect to a local TWS/IB
  Gateway instance, call `ib.positions()` (or `ib.portfolio()` for P&L/market
  value context too), return a plain list of `(symbol, exchange, currency, qty,
  avg_cost)` — don't write to the DB in this phase, just prove the connection and
  data shape against Shaun's real (paper or live — confirm which, see Open
  Questions) account.
- New CLI subcommand for manual triggering, e.g. `uv run --directory
  investments/my-trader python -m mytrader.main sync-ibkr --dry-run` — prints
  what it found, no writes.

### Phase 2 — Reconcile against `holdings` table

- **Do not silently overwrite** — same precedent as
  [[feedback_no_auto_delete_watchlist]] (my-trader must never auto-remove a
  watchlist/holdings row as a side effect of a check) and `candidate_sync.py`'s
  pending-review staging pattern (never write straight into a live file/table
  without an explicit confirm step).
- Diff IBKR's real positions against the current `holdings` table by ticker:
  report new positions found in IBKR but not tracked, quantity/avg-price
  mismatches on positions that exist in both, and tracked positions no longer
  present in IBKR (fully sold, or sold outside this tool's knowledge).
- Present the diff for Shaun's explicit confirm before writing anything — either
  a full diff-then-confirm-each-line flow, or a "review and approve the whole
  batch" flow (worth asking Shaun which fits his usage pattern better once the
  diff shape is real).
- Ticker normalization: `tickers.normalize()` already exists (handles BRK.B →
  BRK-B); IBKR's own symbol/exchange fields will need mapping to whatever ticker
  string my-trader expects (e.g. ASX-listed positions — check what IBKR returns
  for `exchange` on those vs. the `.AX` suffix `tickers.asx_variant()` expects).

### Phase 3 — Bucket assignment for newly-discovered positions

- A position IBKR reports that isn't already in `holdings` has no bucket — bucket
  is Shaun's own strategic categorization (long-term hold / crash-trade / gold /
  AI post-crash-watch), not something IBKR can supply. Needs an explicit
  conversational assignment step per new ticker, not a default guess.

## Explicitly deferred (do not build as part of this handoff)

- Any live quote streaming / real-time price feed from IBKR (my-trader already
  uses yfinance for prices elsewhere — this feature is about *position* data,
  qty/avg-cost, not a second price source)
- Any order placement, trade execution, or account modification of any kind —
  hard SOUL.md boundary regardless of the read-only clarification above
- Scheduled/automatic sync (Monitor's daily cadence, a systemd timer, etc.) — this
  is on-demand only, since it depends on Shaun having TWS/IB Gateway running
  locally
- VPS deployment of any part of this — explicitly local-only per Shaun's
  instruction (2026-08-11)

## Validation (once built)

```powershell
# Add ib_insync/ib_async to investments/my-trader/pyproject.toml first

uv run --directory investments/my-trader python -m pytest -q

# Exact CLI shape TBD during implementation — Phase 1 example:
# (requires TWS or IB Gateway already running and logged in locally)
uv run --directory investments/my-trader python -m mytrader.main sync-ibkr --dry-run
```

## Open Questions for Shaun (resolve during /plan-feature)

1. **Paper or live IBKR account/port?** — TWS and IB Gateway each expose
   different default ports for paper vs. live (7497/7496 TWS, 4002/4001
   Gateway). Needs a config value, and confirmation of which app (TWS vs. the
   lighter IB Gateway) Shaun actually intends to run locally.
2. **Diff-and-confirm UX** — batch approve vs. line-by-line confirm for the
   reconciliation step (Phase 2).
3. **Bucket assignment flow** for newly-discovered positions (Phase 3) — how much
   should the assistant infer/suggest vs. always ask.
4. **`ib_insync` vs. `ib_async`** — `ib_insync`'s original maintainer archived it;
   `ib_async` is the community fork. Check which is the healthier dependency
   choice at implementation time, not now (ecosystem status can shift).
5. **Scope of what's pulled** — just tradeable positions (qty/avg cost), or also
   cash balance/total account value context? Affects whether `ib.positions()`
   alone is enough or `ib.accountSummary()` is also needed.
6. **SOUL.md wording** — should this handoff's clarification get folded back into
   `Memory/SOUL.md` itself as an explicit read-only carve-out, so a future session
   doesn't re-raise the same question from a cold read of the file?
