# my-trader Tool — Usage Instructions

## In plain English

- **Find** — ask about any stock, get an instant opinion. Nothing saved unless you say "add it."
- **Holdings** — what you actually own. Update by saying "I bought/sold X."
- **Watchlist** (`watchlist.md`) — your personal "maybe" list. Only changes when you tell the second brain to explicitly add/remove something (can't be directly edited)  .
- **Post-Crash AI Watch** — a section inside the watchlist for good AI companies you like but won't buy at today's prices. Same rule as the rest of the watchlist: it's rendered from the database, so you can't hand-edit it in the file — ask Claude, or run `watchlist-add`/`watchlist-remove`/`watchlist-move-bucket --to-bucket ai_postcrash` yourself.
- **Monitor** — runs once a day by itself. Re-checks your holdings/watchlist for problems (dividend cuts, overvaluation, etc.) and 4 big-picture economic warning signs.
- **Briefs Finance sync** — a research feed that finds new stock ideas from reports. Runs automatically once a day (as part of Monitor), but never touches your real watchlist directly — new ideas always land in the pending-review pile first.
- **Pending review** — new ideas from that sync sit here waiting for your thumbs up (add to watchlist) or thumbs down (bin it).

### Who actually checks if a pick is good

Two separate evaluation systems, and Monitor only touches one of them by default:

- **Briefs Finance's own code does all the "is this pick good" scoring** — a 0-100%
  likelihood score from backtesting past recommendations, sector context, macro
  conditions, and 9 investor-principle evaluations (`scripts.main assess`/`backtest`).
  This is entirely self-contained in `briefs-finance`, independent of my-trader.
- **The sync pipeline does zero scoring.** `candidate_sync` just copies ticker+thesis
  into `pending_candidates` (ethical-filter exclusion only, no quality check).
  `promote-candidate` just moves it into the real watchlist — by default with
  `status="raw"`.
- **Monitor only checks `status="discussed"` watchlist rows** (plus your actual
  holdings). A ticker sitting in pending-review, or even one you've promoted to the
  watchlist as `"raw"`, is invisible to Monitor's 7-check assessment engine
  (dividend, valuation, balance sheet, FX, concentration, sector risk, ETF mechanics)
  until it's explicitly marked `"discussed"`.
- **Find is the actual bridge.** When you ask "what do you think of TICKER" or "add
  TICKER to watchlist," that's when my-trader's own 7 checks run and briefs-finance's
  likelihood score gets layered in as a secondary input — and `watchlist-add`/that
  conversational flow is what flips status to `"discussed"`, which is what makes
  Monitor start tracking it going forward.

So: a freshly-synced Briefs Finance pick gets zero automated quality evaluation from
either system until you (or I, on your ask) run Find on it — sync just surfaces it
for your attention, it doesn't vet it. (You can also promote with
`--status discussed` directly if you want to skip straight to Monitor tracking it,
but that bypasses ever actually running the checks on it once — probably not what
you'd want.)

One automatic daily check-up (Monitor), one on-demand research feed (sync), one list that's truly yours (watchlist).

## Most things are conversational — just ask Claude

- "what do you think of TICKER" / "check TICKER" — ephemeral lookup, saves nothing
- "add TICKER to watchlist" — persists it, regenerates the snapshot files
- "I bought/sold N shares of TICKER at $X" — records it against holdings
- "show my holdings" / "what's on my watchlist"
- "what's my-trader Monitor showing" — reads today's `monitor-report.md` back to you

## Manual CLI (if you want to run it yourself)

```powershell
cd investments/my-trader

# Ephemeral lookup — writes nothing
uv run python -m mytrader.main find --ticker VRTX

# Explicit "add to watchlist" — persists + regenerates snapshots
uv run python -m mytrader.main watchlist-add --ticker VRTX --name "Vertex Pharmaceuticals" --asset-type stock --bucket 1 --notes "..."

# Record a buy/sell against a holding
uv run python -m mytrader.main holding-buy --ticker V --bucket 1 --qty 0.1 --price 340
uv run python -m mytrader.main holding-sell --ticker V --bucket 1 --qty 0.05 --price 350

# Regenerate holdings.md / watchlist.md / synced-candidates-pending-review.md from the DB
uv run python -m mytrader.main snapshot

# Pull new Briefs Finance recommendations into synced-candidates-pending-review.md
# right now (also runs automatically once a day as part of monitor)
uv run python -m mytrader.main sync-candidates

# Review synced-candidates-pending-review.md, then promote or dismiss each one
uv run python -m mytrader.main promote-candidate --ticker VRTX --bucket 1 --status raw
uv run python -m mytrader.main dismiss-candidate --ticker XYZ

# Remove a ticker from the watchlist entirely, or move it to a different bucket
uv run python -m mytrader.main watchlist-remove --ticker XYZ
uv run python -m mytrader.main watchlist-move-bucket --ticker XYZ --to-bucket 2

# Fetch/refresh Dividend + 10Y Return columns for every watchlist row (yfinance,
# cached — doesn't run automatically, re-run this whenever you want fresher numbers)
uv run python -m mytrader.main refresh-watchlist-data

# Force a full Monitor run right now
# (also runs automatically once a day — see "Runs automatically" below)
uv run python -m mytrader.main monitor
```

## Runs automatically — no action needed

**Monitor** re-checks every holding and every "discussed" watchlist row once a day
(Windows Task Scheduler locally, systemd timer on the VPS). Each run also checks 4
portfolio-wide macro indicators (MOVE index, housing price-to-income, UMich consumer
sentiment, recession-probability + yield-curve steepener).

Output overwrites `monitor-report.md` every run, plus a toast notification fires
only if something new flags. Nothing is pushed to WhatsApp or the Second Brain daily
log — Monitor is a quiet, separate channel by design.

**Briefs Finance candidate sync runs automatically as part of Monitor's daily run**
(re-enabled 2026-07-19) — but only writes to `synced-candidates-pending-review.md`,
never to `watchlist.md`. That file only ever changes when you (or I)
explicitly add, remove, promote, or move something — automation can fill up the
pending-review pile on its own, but nothing crosses into your real watchlist without
an explicit action.

## Where to look

| File | What's in it |
|---|---|
| `holdings.md` | Current positions (auto-generated, never hand-edit) |
| `watchlist.md` | Your curated watchlist — vetted ("discussed") + raw candidates you've explicitly added, plus a separate "Post-Crash AI Watch" section for major AI-boom names you're deliberately not buying at current valuations. Never touched by automatic sync (auto-generated from the DB, never hand-edit) |
| `synced-candidates-pending-review.md` | New Briefs Finance picks waiting for you to review — `promote-candidate` or `dismiss-candidate` each one (auto-generated, never hand-edit) |
| `monitor-report.md` | Today's new/open alerts, macro indicators |
| `investment-strategy.md` | Your own criteria + vetted late-cycle/warning-signal lessons |
| `tool-preplan.md` | Full design scratchpad — checks, thresholds, open questions |
| `handoff.md` | Build history / current status narrative |

## Notes

- Nothing here ever suggests a specific trade — advisor notes only (see `SOUL.md`)
- FRED-backed macro checks (housing affordability, consumer sentiment, recession
  signal) need `FRED_API_KEY` set in `investments/briefs-finance/.env` — currently
  unset, so those 3 read `"unknown"` until you add a free key from
  fred.stlouisfed.org. The MOVE index check doesn't need a key and is live.
- Shares one SQLite database with `briefs-finance` via a uv workspace — see that
  tool's own `instructions.md` (one directory up) for report ingestion/backtesting.
- Dividend/10Y Return columns come from yfinance and are best-effort, not audited.
  Yahoo exposes two dividend-yield fields on different scales (a fraction and an
  already-percent number) and one of them is frequently blank for ETFs — my-trader
  prefers the more precise field and falls back to the other, plus a plausibility
  filter drops anything above 15% as certainly-wrong. Still worth a gut-check on
  anything that looks off. 10Y Return is an adjusted-close approximation of total
  return, not a precise dividend-reinvestment calculation.
