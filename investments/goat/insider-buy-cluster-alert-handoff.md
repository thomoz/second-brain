# Handoff: Universal Insider-Buy Discovery + Live Cluster Alerting

## Status: NOT BUILT — plan only, discussed with Shaun 2026-11-08

## What This Is

Triggered by checking why a real insider-buy event (Upbound Group / UPBD, 6
distinct insiders buying Nov 2–3 2026, $50K–$400K each) never generated a
notification. Investigation found two separate bugs plus a design decision
Shaun now wants changed, and folds in a new live cluster-alert feature.

### Root cause 1 — watchlist/holdings exclusion in discovery

`run_discovery_scan` (`investments/goat/goat/insider_scan.py:204-207`) skips
any ticker already in `holdings.md` or `watchlist.md`:

```python
if mt_db.get_holding_row(conn, ticker) is not None:
    continue
if mt_db.get_watchlist_row(conn, ticker) is not None:
    continue
```

Verified with a real case: INTC sits on watchlist.md Bucket 4 — any insider
buy on it is silently dropped by discovery, and Holdings Watch doesn't cover
it either since it isn't held. Net effect: anything on the watchlist but not
yet held has **zero** insider-buy coverage today.

### Root cause 2 — discovery feed capacity / no pagination

`openinsider.fetch_discovery_purchases()` hits `/latest-insider-purchases-25k`
with no date or count params — a fixed, unpaginated "most recent N"
market-wide snapshot.

Confirmed on the VPS: queried `goat_insider_filings_seen` for UPBD — only 2
rows exist, ever (an Aug 21 sell, correctly silent as `discovery_sell`, and an
Oct 27 Brown Jeffrey J buy, correctly captured as `discovery`). None of the 6
Nov 2–3 buys are in the table at all. Checked
`second-brain-goat-insider-scan.service` journalctl logs Nov 1–7: ran clean
every day, no errors — not an outage. The feed itself just rolls smaller
trades off the page before any day's run reads it, with no backfill once
that happens.

### Design decision Shaun wants changed

Independent of the two bugs above, Shaun wants insider-buy coverage to not
depend on hold/watchlist status at all: *"I don't want it to matter if I hold
the stock or if it's on the watchlist for any insider buying scans."* The
purpose of these scans is to surface potential positive insider information
regardless of whether the ticker is already on his radar.

### Cluster alerting (new feature, folded into this plan)

`goat/insider_pattern_analysis.py::_compute_clusters()` already exists — it
flags a filing as clustered when ≥2 distinct insiders buy/sell the same
ticker within `GOAT_INSIDER_CLUSTER_WINDOW_DAYS` (7 days, `config.py:752`).
But:

- It only runs over whatever's already in `goat_insider_filings_seen` — so
  it inherits root cause 2's data loss.
- It only feeds the retrospective stats report (`insider-pattern-analysis.md`)
  — nothing today turns a freshly-detected cluster into a live alert.
- It doesn't separate buy-clusters from sell-clusters. The current "By
  Cluster" bucket (Clustered: 55% confirm direction, -0.9% avg excess return
  vs. Isolated: 59%, -0.1%) mixes both directions, and sells (n=20,220)
  vastly outnumber buys (n=2,827) in the dataset — so that headline number
  says almost nothing about buy-clusters specifically.

Shaun's reasoning: multiple insiders independently buying in a short window
has a higher probability of reflecting real (if unconfirmable) positive
information than an isolated buy. Agreed directionally — insiders sell for
many non-bearish reasons (taxes, diversification), they only buy because
they expect upside, so a buy is already higher-signal than a sell, and
independent convergence by multiple insiders is a reasonable amplifier on
top of that. But flagged that the dataset doesn't yet prove buy-clusters
outperform isolated buys, since the needed buy-only × cluster-only cross-tab
doesn't exist yet — adding it lets future threshold tuning be evidence-based
rather than assumed.

## Proposed Design

### 1. Make insider-buy discovery universal

- Remove the `get_holding_row`/`get_watchlist_row` exclusion checks from
  `run_discovery_scan` — buys notify regardless of hold/watch status.
- Switch `fetch_discovery_purchases()`'s data source from the fixed
  `/latest-insider-purchases-25k` page to the paginated `/screener` endpoint
  (already used by `fetch_screener_filings` — supports `cnt`/`page`/`fd`)
  with no ticker filter, looping pages for a full day's volume (`fd=1`), so
  volume-heavy days don't silently drop trades. **Needs a live check first**:
  confirm `/screener` actually returns market-wide results with an
  empty/omitted `s` (ticker) field — every confirmed-live usage today is
  ticker-scoped.
- Keep Holdings Watch as-is for sells on held tickers only (buys fold into
  the new universal scan; sell-on-held remains its own "should I worry"
  signal, unaffected by this change).

### 2. Live buy-cluster alerting

- Reuse `_compute_clusters`'s windowing logic (extract to a shared helper
  callable from both `insider_scan.py` and `insider_pattern_analysis.py`) —
  **buy-direction only**, not buy-or-sell.
- Fire a distinct "cluster forming" WhatsApp alert the moment a 2nd distinct
  insider buy lands on the same ticker within
  `GOAT_INSIDER_CLUSTER_WINDOW_DAYS` — in addition to the existing per-trade
  discovery alert, not a replacement or batched summary.
- Consider surfacing insider title (officer/director vs. 10% owner vs.
  other) in the cluster alert text — already captured per-filing, just not
  used for anything beyond the institutional-filer exclusion today.

### 3. Evidence-based tuning

- Add a buy-only × cluster-only cross-tab to `insider-pattern-analysis.md` /
  `insider_pattern_analysis.py` so cluster-alert thresholds (window days,
  minimum distinct insiders) can be validated against Shaun's own data once
  enough buy-cluster volume accumulates post-fix.

## Open Questions

1. Does OpenInsider's `/screener` endpoint actually support a market-wide
   (no-ticker) query, or does universal pagination need a different
   source/approach? Must verify live before implementation.
2. Minimum cluster size to alert on — 2 distinct insiders (matches
   `_compute_clusters`'s existing bar) or 3+ for a live interruption
   specifically (higher bar than a retrospective stats bucket)?
3. Should the live cluster alert require a minimum per-insider or combined
   dollar value, so e.g. two directors buying $5k each doesn't fire the same
   escalation as two buying $500k each?
4. Once the watchlist/holdings exclusion is removed from discovery, a ticker
   Shaun already holds could land in `goat_pending_candidates` as a "new
   candidate" — odd UX (prompting to "add" something he already owns).
   Proposed: still fire the discovery/cluster alert regardless of hold
   status, but skip inserting into `goat_pending_candidates` when the ticker
   is already held. Confirm with Shaun before building.

## Cost

No new costs. OpenInsider has no official API or paid tier — `/screener` is
the same free public scrape already used elsewhere in this codebase
(Holdings Watch, the Find insider-selling check). Pagination adds a few
extra seconds of VPS CPU per run, nothing financial.
