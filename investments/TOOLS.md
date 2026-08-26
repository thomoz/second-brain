# Investments Tools — What Runs, When, Where It Writes, How to Run It Now

Four packages share `investments/briefs-finance/data/investments.db` (VPS-only since
2026-08-23 — see `.agent/plans/completed/investments-db-ssh-single-source.md`):
**my-trader**, **briefs-finance**, **goat**, **fourteen-crash-signals-daily-check**.

Last updated 2026-08-26 — update this file whenever a tool's schedule, command, or
output path changes; it isn't regenerated automatically.

## Daily Read

Freshest reports worth actually opening most days:

| File | From | |
|------|------|---|
| [investments/my-trader/my-trader-report.md](my-trader/my-trader-report.md) | my-trader Monitor (7:30am Sydney) | [→](#mytrader-monitor) |
| [investments/goat/goat-report.md](goat/goat-report.md) | Goat Monitor (~7:35am Sydney) | [→](#goat-monitor) |
| [investments/goat/industry-ranking.md](goat/industry-ranking.md) | Part of Goat Monitor, industry rotation section (~7:35am Sydney) | [→](#goat-monitor) |
| [investments/goat/insider-scan-report.md](goat/insider-scan-report.md) | Goat Insider Scan (~7:50am Sydney) | [→](#goat-insider-scan) |
| [investments/fourteen-crash-signals-daily-check/crash-signals-report.md](fourteen-crash-signals-daily-check/crash-signals-report.md) | Fourteen Crash Signals (daily) | [→](#fourteen-crash-signals) |
| [investments/my-trader/gold-outlook.md](my-trader/gold-outlook.md) | Part of my-trader Monitor, gold section | [→](#mytrader-monitor) |
| [investments/my-trader/cash-value-report.md](my-trader/cash-value-report.md) | Cash-Value Scan (daily, ~22:30 UTC) | [→](#cashvalue-scan) |

Staging files (only worth checking when you want to review pending candidates, not a
daily habit): `investments/my-trader/synced-candidates-pending-review.md`,
`investments/goat/sector-candidates-pending-review.md`,
`investments/goat/heartbeat-candidates-pending-review.md`. WhatsApp already pushes new
alerts/discoveries as they fire — these files are for batch review, not discovery.

## Automated (scheduled)

| Tool | What it does | Where it runs | Schedule | Output |
|------|--------------|----------------|----------|--------|
| <a id="mytrader-monitor"></a>[↑](#daily-read) **my-trader Monitor** | Re-checks all holdings + vetted watchlist rows | Windows Task Scheduler (`SecondBrain-MyTraderMonitor`), this dev machine | Daily, 7:30am Sydney local | `investments/my-trader/my-trader-report.md`, refreshes `gold-outlook.md` |
| <a id="cashvalue-scan"></a>[↑](#daily-read) **Cash-Value Scan** | Screens US (Finviz) + ASX 200 (Wikipedia) for net cash ≥ 50% of market cap + positive operating cash flow (threshold `CASH_VALUE_RATIO_THRESHOLD` in `mytrader/config.py`); ranked advisor-notes list, no staging/alerts | VPS systemd (`second-brain-mytrader-cashvalue-scan.timer`) | Daily, 22:30 UTC | `investments/my-trader/cash-value-report.md` |
| <a id="goat-monitor"></a>[↑](#daily-read) **Goat Monitor** (150DMA exit check + sector rotation scan) | Flags holdings AND every watchlist ticker closing below their 150-day MA; ranks the 11 SPDR sector ETFs and stages fresh breakout candidates; also refreshes the industry rotation ranking | VPS systemd (`second-brain-goat-monitor.timer`) | Daily, 21:35 UTC (07:35 AEST / 08:35 AEDT) | `investments/goat/goat-report.md`, `sector-ranking.md`, `sector-candidates-pending-review.md`, `industry-ranking.md` |
| **Goat Intraday Live-Check** | Live-price 150DMA check against currently-open-market holdings | VPS systemd (`second-brain-goat-live-check.timer`) | Every 10 min around the clock (no-ops outside ASX/US session hours) | WhatsApp alert only if breached — no standalone report file |
| **Goat Heartbeat Scan** (S&P 500) | Screens S&P 500 constituents in currently-rising sectors for a tight sideways base sitting at/above a flat-to-rising 150-day MA (price mostly below its 50-day MA through the base), then a fresh 50-day-MA breakout, with fundamentals survival context | VPS systemd (`second-brain-goat-heartbeat-scan.timer`) | Weekly, Saturday 8:00am Sydney local | `investments/goat/heartbeat-candidates-pending-review.md` |
| <a id="goat-insider-scan"></a>[↑](#daily-read) **Goat Insider Scan** (OpenInsider) | Checks Form 4 filings on holdings, stages market-wide $25k+ buys as candidates, tracks $100k+ sells; price-since-trade tracking; feeds pattern analysis | VPS systemd (`second-brain-goat-insider-scan.timer`) | Daily, 21:50 UTC (~15min after Goat Monitor) | `investments/goat/insider-scan-report.md`; nightly pattern slice in `insider-pattern-analysis.md` |
| <a id="fourteen-crash-signals"></a>[↑](#daily-read) **Fourteen Crash Signals Daily Check** | Tracks all 14 crash-warning markers against a dynamically-recomputed hot-company watchlist | VPS systemd (`second-brain-fourteen-signals.timer`) | Daily, 22:05 UTC | `investments/fourteen-crash-signals-daily-check/crash-signals-report.md` |

## Manual / on-demand only

Every command below runs on the VPS via `scripts/invoke_investments.ps1` — **never**
run a package locally with `uv run --directory investments/<pkg> ...`; that talks to a
local `investments.db` that no longer exists and would silently recreate an empty one,
undoing the 2026-08-23 fix.

| Tool | What it does | Command | Output |
|------|--------------|---------|--------|
| **my-trader Find** | Conversational ticker assessment (7 checks + Briefs Finance score) | `invoke_investments.ps1 -Package my-trader -Command "find --ticker TICKER"` | Terminal only (ephemeral) |
| **my-trader watchlist ops** | Add/remove/move a watchlist ticker | `-Package my-trader -Command "watchlist-add / watchlist-remove / watchlist-move-bucket ..."` | DB row + regenerates `holdings.md`/`watchlist.md` |
| **my-trader holding ops** | Record a buy/sell | `-Package my-trader -Command "holding-buy / holding-sell ..."` | DB row + regenerates `holdings.md`/`watchlist.md` |
| **my-trader snapshot** | Regenerate markdown from the DB | `-Package my-trader -Command "snapshot"` | `investments/my-trader/holdings.md`, `watchlist.md` |
| **my-trader sync-candidates** | Pull new Briefs Finance recs into staging | `-Package my-trader -Command "sync-candidates"` | `investments/my-trader/synced-candidates-pending-review.md` |
| **my-trader gold-backtest** | Force a fresh gold backtest | `-Package my-trader -Command "gold-backtest"` | `investments/my-trader/gold-outlook.md` |
| **Cash-Value Scan (on-demand)** | Same US + ASX net-cash screen (net cash ≥ 50% of market cap + positive operating cash flow), right now | `-Package my-trader -Command "cash-value-scan"` | `investments/my-trader/cash-value-report.md` |
| **my-trader IBKR sync** | Diff real IB Gateway positions against tracked holdings — fetch is local (IB Gateway only runs here), diff/write happens on the VPS | `uv run --directory investments/my-trader python -m mytrader.main sync-ibkr [--apply]` (this one stays local — see `ibkr-setup-guide.md`) | Terminal report; `--apply` writes DB corrections + stages new positions |
| **Goat sector scan (on-demand)** | Same sector-rotation ranking, without the 150DMA holdings check | `-Package goat -Command "scan-sectors"` | `investments/goat/sector-ranking.md`, `sector-candidates-pending-review.md` |
| **Goat industry scan (on-demand)** | Same industry-rotation ranking (39 of 143 Finviz industries with a dedicated ETF, 6-month window), right now | `-Package goat -Command "scan-industries"` | `investments/goat/industry-ranking.md` |
| **Goat live-check (on-demand)** | Same intraday 150DMA check, right now | `-Package goat -Command "check-live"` | WhatsApp alert only |
| **Goat heartbeat scan (on-demand)** | Same weekly S&P 500 scan, right now | `-Package goat -Command "scan-heartbeat"` | `investments/goat/heartbeat-candidates-pending-review.md` |
| **Goat insider scan (on-demand)** | Same OpenInsider scan, right now | `-Package goat -Command "scan-insiders"` | `investments/goat/insider-scan-report.md` |
| **Goat Hormuz risk scan (on-demand)** | Strait of Hormuz war-risk check — not on a timer, manual only | `-Package goat -Command "scan-hormuz"` | `investments/goat/hormuz-risk-report.md` |
| **Goat promote/dismiss candidate** | Move a staged Goat candidate into my-trader's real watchlist, or discard it | `-Package goat -Command "promote-candidate --ticker TICKER"` / `"dismiss-candidate --ticker TICKER"` | Watchlist DB row (promote only) |
| **Briefs Finance ingest** | Ingest a PDF report into the scoring pipeline | `-Package briefs-finance -Command "ingest ..."` (scp the PDF up first if it's local — see `.claude/skills/investments/SKILL.md`) | DB only |
| **Briefs Finance backtest** | Backtest historical recommendations | `-Package briefs-finance -Command "backtest"` | DB only |
| **Briefs Finance score** | Compute 0–100% likelihood scores | `-Package briefs-finance -Command "score"` | DB only |
| **Briefs Finance assess / context / stats / excluded** | Full assessment / sector+macro context / track record / exclusion list | `-Package briefs-finance -Command "assess --ticker TICKER [--output markdown]"` / `"context"` / `"stats"` / `"excluded"` | Terminal by default; `--output markdown` writes to `investments/briefs-finance/assessments/` |
| **Fourteen Crash Signals (on-demand)** | Same daily check, right now | `-Package fourteen-signals -Command "daily-check"` | `investments/fourteen-crash-signals-daily-check/crash-signals-report.md` |
| **Fourteen Crash Signals: record bond yield** | Manually record a bond yield for Marker #12 (no live source exists) | `-Package fourteen-signals -Command "record-bond-yield TICKER YIELD_PCT [--cusip CUSIP]"` | DB only |

Full invocation is `.\scripts\invoke_investments.ps1` from the repo root — table rows
above show only the `-Package`/`-Command` args for brevity.

## Notes on the schedule mismatch

my-trader's own Monitor timer exists on the VPS (`second-brain-mytrader-monitor.timer`)
but is deliberately left **disabled** there — my-trader Monitor still runs on this
Windows machine via Task Scheduler instead, to avoid double-running the same check
from two places. If my-trader Monitor is ever migrated to the VPS, disable
`SecondBrain-MyTraderMonitor` on Windows first, the same way Heartbeat/Reflection/
WhatsAppBot were disabled after the VPS went live (see root `CLAUDE.md`).
