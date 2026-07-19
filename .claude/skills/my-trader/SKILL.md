---
name: my-trader
description: >
  Personal investing Find tool — conversational ticker assessment against Shaun's own
  criteria (sustainable, competitive edge, pricing power) via 7 checks (dividend trend,
  valuation, balance sheet/leverage, FX exposure, portfolio concentration incl. Berkshire
  overlap, sector/geopolitical risk, ETF mechanics), plus Briefs Finance's likelihood
  score layered in as a secondary input. Distinct from the `investments` skill
  (briefs-finance) — Find uses briefs-finance's score as one input among several, it
  doesn't replace that skill. Also handles holdings updates (buy/sell) conversationally.
  Triggers on: "check TICKER", "what do you think of TICKER", "add TICKER to watchlist",
  "I bought/sold N shares of TICKER", "show my holdings", "my-trader".
---

# my-trader Skill

Personal investing Find tool. Shares a database with `briefs-finance` (the `investments`
skill) via a uv workspace. All output is for Shaun's review only — nothing acts
autonomously, and no specific trade action is ever suggested (advisor-note style, per
SOUL.md).

## Quick Reference

```powershell
# Ephemeral lookup — "what do you think of TICKER" (writes nothing)
uv run --directory investments/my-trader python -m mytrader.main find --ticker VRTX

# Explicit "add to watchlist" — persists a DB row + regenerates snapshots
uv run --directory investments/my-trader python -m mytrader.main watchlist-add --ticker VRTX --name "Vertex Pharmaceuticals" --asset-type stock --bucket 1 --notes "..."

# Record a buy/sell against a holding
uv run --directory investments/my-trader python -m mytrader.main holding-buy --ticker V --bucket 1 --qty 0.1 --price 340
uv run --directory investments/my-trader python -m mytrader.main holding-sell --ticker V --bucket 1 --qty 0.05 --price 350

# Regenerate holdings.md / potential-holdings.md from the DB
uv run --directory investments/my-trader python -m mytrader.main snapshot

# One-time migration of the already-confirmed rows (VRTX, PMGOLD core+tactical, BRK-B,
# HDV, SCHD, ASML, LLY, LYV, V) into the shared DB — idempotent, safe to re-run
uv run --directory investments/my-trader python -m mytrader.main seed

# Scheduled re-check of all holdings + vetted watchlist (also runs automatically —
# see scripts/setup_scheduler_windows.ps1 / scripts/systemd/second-brain-mytrader-monitor.timer)
uv run --directory investments/my-trader python -m mytrader.main monitor
```

Note: use `uv run --directory <path> ...` rather than `cd`-ing into the directory first —
`cd` in this repo's shell breaks the PreToolUse hooks (see project memory).

## Key Paths

- Package: `investments/my-trader/mytrader/`
- Shared database: `investments/briefs-finance/data/investments.db` (`holdings`,
  `watchlist`, `alert_history` tables — owned by my-trader; `reports`,
  `recommendations`, `likelihood_scores` etc. — owned by briefs-finance)
- Snapshots: `investments/my-trader/holdings.md`, `investments/my-trader/potential-holdings.md`
  (auto-regenerated after every write — never hand-edit these once the tool is in use)
- Strategy/criteria reference: `investments/my-trader/investment-strategy.md`

## The 7 Assessment Checks

Every `find` / `watchlist-add` runs all 7:

| Check | What it looks at |
|-------|-------------------|
| Dividend trend | Trailing vs. prior 12-month dividend sum |
| Valuation | Trailing/forward PE vs. configured rich/cheap bands |
| Balance sheet | Debt/equity and current ratio |
| FX exposure | Non-AUD currency + AUD move (informational only) |
| Concentration | Berkshire 13F overlap + candidate's sector vs. existing holdings |
| Sector/geopolitical risk | Sector/industry vs. known active flashpoints |
| ETF mechanics | Expense ratio baseline / drift (drift only detectable after a repeat check) |

## Two Distinct Find Actions

- **Ephemeral lookup** ("what do you think of TICKER") — runs the 7 checks, reports
  back, persists nothing.
- **Explicit watchlist-add** ("add TICKER to the watchlist") — same checks, plus writes
  a `watchlist` row (`status="discussed"`) and regenerates the markdown snapshots.

## Monitor

Runs daily on a schedule (no chat trigger needed — it's automated, see "Setup" for the
scheduler entries). Re-checks every `holdings` row and every `watchlist` row with
`status="discussed"` (never `status="raw"` — Monitor doesn't discover new candidates,
that stays a Find/conversation action). Reuses the same 7-check engine as Find.

High-bar alerting: a check's first `flag` verdict for a given ticker/check creates one
alert; repeated flags on later runs stay quiet (already open); a check clearing back to
non-flag auto-acknowledges its open alert, so a future re-flag raises a fresh one.

Output is a standalone file, `investments/my-trader/monitor-report.md` (full overwrite
every run — new alerts this run + all currently-open alerts). A bare Windows toast
notification fires only when there's at least one new alert (reuses
`.claude/scripts/notifications.py`, same as heartbeat). No Second Brain daily-log entry
and no WhatsApp push — Monitor is a quieter, separate channel by design. Like Find,
Monitor never suggests a specific trade action — advisor notes only.

## Relationship to the `investments` Skill

`investments` (briefs-finance) does PDF ingestion, backtesting, and a 0-100% likelihood
score against 9 investor principles. `my-trader`'s Find layers that score in as one
additional input — Shaun's own criteria (sustainable, competitive edge, pricing power)
plus the 7 checks above are the primary basis. Find never triggers a fresh briefs-finance
scoring run as a side effect — it only reads whatever score already exists for that ticker.

## Known Limitations (Phase A)

- `BERKSHIRE_HOLDINGS` starts empty in `mytrader/config.py` — no free API for 13F data;
  manually maintained, update periodically from Berkshire's 13F filings.
- Portfolio concentration aggregation is currency-naive (no FX normalization across
  USD/AUD holdings) — matches the previous hand-maintained holdings.md.
- ETF expense-ratio drift can only be detected once a ticker has been checked twice —
  Monitor's repeated daily runs are what make this detection real in practice.
- Monitor is now built (Phase B). Phase C (macro indicators, Briefs Finance
  ingest→candidate data-flow) is still pending, not yet planned.

## Setup (first time)

```powershell
uv sync --directory investments/my-trader --extra dev
```
