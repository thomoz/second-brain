# Feature: DMA Breakout — Industry Rotation Filter

The following plan should be complete, but validate documentation and codebase patterns and task sanity before implementing. Pay special attention to naming of existing utils/types/models — import from the right files, mirror existing docstring/comment conventions (dated rationale notes, "v1/tunable" markers, fail-open vs fail-closed call-outs).

## Feature Description

`investments/goat/dma-breakout-candidates-pending-review.md` currently lists every S&P 500 + ASX 200 + curated-ETF name that crossed above its 150/200-day MA that day — often 100+ rows, too many to realistically review. This feature narrows the scan to only stage a candidate when its Finviz industry is also in the day's top 36 (of 144) industries ranked by Perf Week in `industry-ranking-full.md` — i.e. only surface breakouts in industries where money is actively rotating in right now.

## User Story

As Shaun (reviewing the daily DMA breakout candidates report)
I want to only see breakout candidates whose industry is currently rotating in (top 36/144 by Perf Week)
So that the pending-review list is small enough to actually act on instead of 100+ undifferentiated rows

## Problem Statement

`dma_breakout_scan.py` tags every candidate with a coarse GICS sector (11 buckets), not Finviz's 144-industry taxonomy that `industry-ranking-full.md` ranks. There is no ticker → Finviz-industry mapping broad enough to gate against the full 144-industry universe — the existing per-industry constituent lookup (`industry_constituents.py`) only resolves for the 39 industries that have a dedicated ETF (`GOAT_FINVIZ_INDUSTRY_SLUGS`). On a sampled real run (2026-10-20's `industry-ranking-full.md`), only **7 of the day's top-36** industries already resolve (Waste Management, Healthcare Plans, Oil & Gas E&P, Restaurants, Lumber & Wood Production, Insurance - Diversified, Telecom Services) — the other 29 return `None`/zero constituents today, and since the top-36 rotates daily, a one-off fill of "today's winners" would need redoing constantly.

## Solution Statement

1. Extend `industry_constituents.fetch_industry_constituents_us` to derive a Finviz screener slug by rule (lowercase, strip spaces/`&`/`-`/`,`/`.`, prefix `ind_` — already documented in `config.py` and verified against 5 real cases) for any industry label not already in `GOAT_FINVIZ_INDUSTRY_SLUGS`, keeping that dict as an override table rather than the sole source. This covers all 144 industries permanently, not just whichever happen to be in today's top 36.
2. Read the latest `industry_full` snapshot already persisted in `goat_rotation_snapshots` (written daily by `scan-industries-full`) to get the day's top-36 industry names, cheaply — no new Finviz Groups fetch.
3. Build a ticker allow-set from those 36 industries via the existing (cached) `get_or_refresh_industry_constituents`.
3. Gate `run_dma_breakout_scan` on allow-set membership for non-ETF rows only (ETF rows stay exempt — no natural industry membership).
4. Fail open (skip the filter entirely, matching today's unfiltered behavior) if no `industry_full` snapshot exists yet for any date — never silently stage zero.

**Decision confirmed with Shaun (2026-10-20): rule-derive the slug, not hand-type ~105 more literal dict entries.**

## Feature Metadata

**Feature Type**: Enhancement
**Estimated Complexity**: Medium
**Primary Systems Affected**: `investments/goat/goat/dma_breakout_scan.py`, `industry_constituents.py`, `config.py`, `db.py`; `scripts/systemd/second-brain-goat-dma-breakout-scan.service`
**Dependencies**: None new — reuses `mytrader.finviz_screener`, existing `goat_rotation_snapshots`/`goat_industry_constituents` tables

---

## CONTEXT REFERENCES

### Relevant Codebase Files — READ THESE BEFORE IMPLEMENTING

- `investments/goat/goat/dma_breakout_scan.py` (whole file, esp. `fetch_universe_constituents` lines 75-116, `run_dma_breakout_scan` lines 215-297, `render_dma_breakout_candidates_report` lines 315-358) — the scan being extended; note the module docstring's "do not refactor to share internals with sector_rotation.py/heartbeat.py" rule, and the existing `asx_unavailable` fail-open banner pattern at lines 333-334 to mirror for the new industry-filter banner.
- `investments/goat/goat/industry_constituents.py` (whole file, 74 lines) — `fetch_industry_constituents_us` (lines 17-32) is the function to extend with the slug-derivation fallback; `get_or_refresh_industry_constituents` (lines 49-73) is reused as-is, no change needed.
- `investments/goat/goat/industry_rotation_full.py` (whole file) — confirms `GOAT_INDUSTRY_FULL_PRIMARY_WINDOW` ("perf_week") drives ranking, and that `capture_full_industry_snapshot` (lines 67-87) already writes each day's ranking into `goat_rotation_snapshots` under `scope="industry_full"` with the industry name stored in the `ticker` column (repurposed) and the rank in the `rank` column — this is what the new allow-set builder reads, not a re-scrape.
- `investments/goat/goat/config.py` lines 199-244 (`GOAT_FINVIZ_INDUSTRY_SLUGS`, 39 entries, comment at ~186-198 documents the exact slug-derivation rule to mirror) and lines 775-818 (`GOAT_DMA_BREAKOUT_*` constants — add `GOAT_DMA_BREAKOUT_TOP_INDUSTRY_COUNT` here).
- `investments/goat/goat/db.py` lines 92-103 (`goat_rotation_snapshots` schema), lines 520-536 (`get_rotation_snapshots_for_date`, `get_latest_snapshot_date_before` — note the latter requires a `before_date`, there is no "latest, full stop" helper yet), lines 563-590 (`get_industry_constituents_fetched_at`/`replace_industry_constituents`/`get_industry_constituents` — unchanged, reused via `industry_constituents.py`).
- `investments/goat/goat/finviz_groups.py` — confirms the industry label strings Finviz Groups returns (`_norm`'d, e.g. `"Oil & Gas Equipment & Services"`) are the same strings used as `goat_rotation_snapshots.ticker` for scope `industry_full`, and as `GOAT_FINVIZ_INDUSTRY_SLUGS` keys.
- `mytrader/finviz_screener.py` lines 149-179 (`fetch_screener_universe`) — the actual Finviz-screener HTTP call reused for every slug, including newly-derived ones; confirms a wrong/stale slug yields an empty result (`None`/`[]`), never a crash.
- `investments/goat/goat/tests/test_dma_breakout_scan.py` (whole file) — `_patch_common` (lines 265-287) is the fixture helper to extend with an industry-allow-set monkeypatch; mirror its monkeypatch style (`monkeypatch.setattr("goat.dma_breakout_scan.<name>", ...)`).
- `investments/goat/goat/tests/test_industry_constituents.py` (whole file, 94 lines) — **`test_fetch_industry_constituents_us_returns_none_for_unmapped_slug` (lines 15-18) will break/go live-network once the derive-fallback ships** (see GOTCHA below) — must be rewritten, not just left.
- `investments/goat/goat/tests/conftest.py` — `db_conn`/`db_path` fixtures and the autouse `_isolate_goat_report_path`/`_no_real_price_history_fetch` fixtures; no changes needed here.
- `scripts/systemd/second-brain-goat-dma-breakout-scan.service` and `second-brain-goat-industry-full-scan.service`/`.timer` — add the `After=` ordering line; confirms current `OnCalendar` times (21:40 UTC industry-full, 22:55 UTC dma-breakout — 75 min gap already).

### New Files to Create

None — every change is an extension of an existing module. No new test files (extend the two existing test files above).

### Patterns to Follow

**Dated rationale comments**: every non-obvious constant/behavior change in this codebase carries a `# <date> -- <who/what prompted it>: <reasoning>` comment (see `GOAT_INDUSTRY_FULL_PRIMARY_WINDOW` in `config.py` line 256, or `GOAT_DMA_BREAKOUT_PENDING_MAX_AGE_DAYS` line 809). Follow this for the new `GOAT_DMA_BREAKOUT_TOP_INDUSTRY_COUNT` constant and the slug-derivation change.

**Fail-open, never silently stage zero**: `asx_unavailable` (dma_breakout_scan.py line 225, reported at line 333) is the exact precedent — a data-source outage degrades to "skip this gate" with a visible banner in the rendered report, not a crash or an empty result. The new industry-filter-unavailable case must follow the same shape.

**Fail-safe-empty per-lookup**: `get_asx_industry_constituents` / `fetch_industry_constituents_us` never raise on an unmapped/empty case — they return `[]`/`None`. The new `_derive_finviz_slug` fallback must preserve this: a wrong derived slug just yields an empty Finviz screen for that industry (logged, not fatal), per `fetch_screener_universe`'s own documented behavior.

**Module-scoped diagnostic prints**: `print(f"[goat-industry-constituents] ...")` / `print(f"[goat-dma-breakout-scan] ...")` prefix convention — keep for the new "using derived slug" log line.

**Test monkeypatch style**: patch the *importing* module's reference (`"goat.dma_breakout_scan.industry_constituents.get_or_refresh_industry_constituents"` or similar), not the defining module directly — see every existing `monkeypatch.setattr("goat.dma_breakout_scan....")` call in `test_dma_breakout_scan.py`.

---

## IMPLEMENTATION PLAN

### Phase 1: Slug Derivation (industry_constituents.py + config.py)

Add the rule-based slug fallback so `fetch_industry_constituents_us` can resolve any of the 144 industry labels, not just the 39 in `GOAT_FINVIZ_INDUSTRY_SLUGS`.

**Tasks:**
- Add `_derive_finviz_slug(industry_label: str) -> str` in `industry_constituents.py`.
- Update `fetch_industry_constituents_us` to try the explicit dict first, fall back to the derived slug, and log which path was used.
- Add `GOAT_DMA_BREAKOUT_TOP_INDUSTRY_COUNT = 36` to `config.py`.
- Update `GOAT_FINVIZ_INDUSTRY_SLUGS`'s module comment (config.py ~line 186) to note it is now an override table, not the sole source.

### Phase 2: Latest-Snapshot Lookup (db.py)

**Tasks:**
- Add `get_latest_rotation_snapshot_date(conn, scope) -> str | None` to `db.py`, mirroring `get_sp500_constituents_fetched_at`'s `MAX(...)` idiom, scoped by `scope`.

### Phase 3: Allow-Set + Scan Wiring (dma_breakout_scan.py)

**Tasks:**
- Add `fetch_top_industry_allow_set(conn) -> set[str] | None` to `dma_breakout_scan.py`: reads the latest `industry_full` snapshot, takes the top `GOAT_DMA_BREAKOUT_TOP_INDUSTRY_COUNT` rows by `rank`, unions each industry's constituents (via `industry_constituents.get_or_refresh_industry_constituents`) into one ticker set. Returns `None` if no snapshot exists for scope `industry_full` yet (fail-open signal).
- Wire it into `run_dma_breakout_scan`: compute the allow-set once per run; in the per-ticker loop, right after the `interesting` check (before the banned-ticker/holdings/watchlist DB lookups and the real-time `market_data.fetch_ticker_data` call — cheapest-check-first), skip non-ETF tickers whose `ticker` isn't in the allow-set. ETF rows (`market == "ETF"`) are always exempt.
- Add a `filtered_by_industry` counter (incremented when this new gate rejects a ticker) and an `industry_filter_applied` bool to the result dict (mirrors `already_staged_elsewhere`'s shape).
- Update `render_dma_breakout_candidates_report`: add a banner line when `industry_filter_applied` is `False` (mirrors the existing `asx_unavailable` banner), and surface the `filtered_by_industry` count alongside the existing `already_staged_elsewhere` line.

### Phase 4: Deployment Ordering

**Tasks:**
- Add `After=second-brain-goat-industry-full-scan.service` to `second-brain-goat-dma-breakout-scan.service`'s `[Unit]` section (keep the existing `After=network.target`).

### Phase 5: Testing

**Tasks:**
- `test_industry_constituents.py`: rewrite the now-incorrect "returns None for unmapped slug" test into one proving the derive-by-rule fallback (and that it still calls the real Finviz screener call, mocked); add a test proving an explicit `GOAT_FINVIZ_INDUSTRY_SLUGS` entry wins over the derived rule when both would apply.
- `test_dma_breakout_scan.py`: tests for `fetch_top_industry_allow_set` (no snapshot → `None`; snapshot present → correct top-36-by-rank union) and for `run_dma_breakout_scan`'s gating (industry in allow-set → staged; industry not in allow-set → filtered + counted; ETF ticker → always staged regardless of allow-set; no snapshot at all → unfiltered fail-open behavior + report banner).

---

## STEP-BY-STEP TASKS

Execute in order; each task is atomic and independently testable.

### 1. UPDATE `investments/goat/goat/config.py`

- **IMPLEMENT**: Add a dated comment above `GOAT_FINVIZ_INDUSTRY_SLUGS` (near line 186) noting it is now consulted first, with `industry_constituents._derive_finviz_slug` as the rule-based fallback for every other Finviz industry — added 2026-10-20 for the DMA-breakout industry filter, per Shaun's explicit call not to hand-type ~105 more literal entries.
- **IMPLEMENT**: Add `GOAT_DMA_BREAKOUT_TOP_INDUSTRY_COUNT = 36` in the existing `GOAT_DMA_BREAKOUT_*` block (near line 808, after `GOAT_DMA_BREAKOUT_CANDIDATES_MD_PATH`), with a dated comment referencing this plan and `industry-ranking-full.md`'s Perf-Week ranking as the source.
- **GOTCHA**: Do not remove or restructure the existing 39 entries — they stay as live-verified overrides, per the new comment.
- **VALIDATE**: `uv run --directory investments/goat python -c "from goat import config; print(config.GOAT_DMA_BREAKOUT_TOP_INDUSTRY_COUNT)"`

### 2. UPDATE `investments/goat/goat/industry_constituents.py`

- **IMPLEMENT**: Add module-level `_FINVIZ_SLUG_STRIP_CHARS = " &-,."` and `_derive_finviz_slug(industry_label: str) -> str` returning `f"ind_{''.join(ch for ch in industry_label if ch not in _FINVIZ_SLUG_STRIP_CHARS).lower()}"`.
- **IMPLEMENT**: Update `fetch_industry_constituents_us` — replace the `slug = config.GOAT_FINVIZ_INDUSTRY_SLUGS.get(industry_label)` / `if slug is None: return None` pair with: look up the explicit dict first; if absent, derive via `_derive_finviz_slug` and log a `[goat-industry-constituents] no explicit slug override for {industry_label!r} -- using derived slug {slug!r}` line (keep this at the existing print-diagnostic verbosity, not a crash/warning level change). The function's docstring sentence about returning `None` for an unmapped label is no longer accurate — rewrite it to describe the derive-fallback instead.
- **PATTERN**: `config.py` lines 186-198 for the exact derivation rule (already verified against 5 live cases: Semiconductors, Oil & Gas Equipment & Services, Banks - Diversified, REIT - Mortgage, Auto & Truck Dealerships).
- **GOTCHA**: `get_or_refresh_industry_constituents`'s existing "US fetch failed and no cache exists yet" fallback path (lines 62-69) still applies unchanged — a bad derived slug just yields an empty Finviz screen, which is `rows == []`, not `None`, so it still gets cached (an empty cache entry) rather than retried every call within the TTL. This is existing, intentional behavior — do not change it.
- **VALIDATE**: `uv run --directory investments/goat python -c "from goat.industry_constituents import _derive_finviz_slug; assert _derive_finviz_slug('Oil & Gas Equipment & Services') == 'ind_oilgasequipmentservices'; assert _derive_finviz_slug('Business Equipment & Supplies') == 'ind_businessequipmentsupplies'; print('ok')"`

### 3. UPDATE `investments/goat/goat/db.py`

- **IMPLEMENT**: Add `get_latest_rotation_snapshot_date(conn: sqlite3.Connection, scope: str) -> str | None` near `get_latest_snapshot_date_before` (~line 529): `SELECT MAX(snapshot_date) AS snapshot_date FROM goat_rotation_snapshots WHERE scope = ?`, same `row["snapshot_date"] if row is not None else None` idiom as `get_sp500_constituents_fetched_at` (line 287-292) — `MAX()` over zero matching rows still returns one row with a `NULL` value, not an empty result set, so the `row is not None` guard is almost always true; return the (possibly `None`) value either way.
- **PATTERN**: `get_sp500_constituents_fetched_at` (db.py lines 287-292) for the exact shape.
- **VALIDATE**: `uv run --directory investments/goat python -m pytest goat/tests/test_db.py -q` (if it exists; otherwise covered transitively by task 5's new tests)

### 4. UPDATE `investments/goat/goat/dma_breakout_scan.py`

- **IMPLEMENT**: Add `from . import industry_constituents` to the existing `from . import config, db, fundamentals_context, price_history, sp500_universe` import line (line 59).
- **IMPLEMENT**: Add `fetch_top_industry_allow_set(conn: sqlite3.Connection) -> set[str] | None`:
  ```python
  def fetch_top_industry_allow_set(conn: sqlite3.Connection) -> set[str] | None:
      """Top GOAT_DMA_BREAKOUT_TOP_INDUSTRY_COUNT industries by rank from the
      latest industry_full snapshot (written daily by scan-industries-full),
      expanded into a ticker allow-set via the existing (cached) per-industry
      constituent lookup. Returns None -- not an empty set -- when no
      industry_full snapshot exists for any date yet, so the caller can fail
      open (skip the gate) rather than stage zero candidates."""
      latest_date = db.get_latest_rotation_snapshot_date(conn, "industry_full")
      if latest_date is None:
          return None
      rows = db.get_rotation_snapshots_for_date(conn, "industry_full", latest_date)
      top_rows = sorted(rows, key=lambda r: r["rank"])[:config.GOAT_DMA_BREAKOUT_TOP_INDUSTRY_COUNT]
      allow_set: set[str] = set()
      for row in top_rows:
          industry_label = row["ticker"]  # repurposed column -- holds the industry name for this scope
          for c in industry_constituents.get_or_refresh_industry_constituents(conn, industry_label):
              allow_set.add(c["ticker"])
      return allow_set
  ```
- **IMPLEMENT**: In `run_dma_breakout_scan`, right after `constituents = fetch_universe_constituents(conn)` / `asx_unavailable = ...`, add `industry_allow_set = fetch_top_industry_allow_set(conn)` and `filtered_by_industry = 0` (alongside the existing `already_staged_elsewhere = 0`).
- **IMPLEMENT**: In the per-ticker loop, immediately after `if not interesting: continue` and before `if ticker in config.GOAT_BANNED_TICKERS:`, add:
  ```python
  if industry_allow_set is not None and market != "ETF" and ticker not in industry_allow_set:
      filtered_by_industry += 1
      continue
  ```
- **IMPLEMENT**: Add `"industry_filter_applied": industry_allow_set is not None` and `"filtered_by_industry": filtered_by_industry` to the dict returned by `run_dma_breakout_scan`.
- **IMPORTS**: `industry_constituents` (new, see above). No other new imports — `db.get_latest_rotation_snapshot_date`/`db.get_rotation_snapshots_for_date` already available via the existing `from . import ... db ...` import.
- **PATTERN**: the existing `asx_unavailable` fail-open flag (set once near the top of `run_dma_breakout_scan`, surfaced via the result dict and the report banner) for the exact shape to mirror.
- **GOTCHA**: Place the allow-set check before the banned-ticker/holdings/watchlist/pending-candidate DB lookups and before `market_data.fetch_ticker_data` — those are strictly more expensive (DB round-trips, a live yfinance call) than an in-memory `set` membership test, so ordering this check first avoids wasted work on tickers that will be filtered anyway.
- **GOTCHA**: `row["ticker"]` on a `goat_rotation_snapshots` row for scope `industry_full` holds the **industry name**, not a real ticker (see `industry_rotation_full.capture_full_industry_snapshot`'s own comment) — don't rename this locally in a way that implies it's a stock ticker.
- **VALIDATE**: `uv run --directory investments/goat python -m pytest goat/tests/test_dma_breakout_scan.py -q`

### 5. UPDATE `investments/goat/goat/dma_breakout_scan.py` (report render)

- **IMPLEMENT**: In `render_dma_breakout_candidates_report`, after the existing `if result["asx_unavailable"]:` banner block, add:
  ```python
  if not result["industry_filter_applied"]:
      lines.append(
          "> Industry-rotation filter unavailable this run (no industry_full "
          "snapshot yet) -- unfiltered scan, matching pre-filter behavior."
      )
  elif result["filtered_by_industry"]:
      lines.append(
          f"{result['filtered_by_industry']} ticker(s) crossed but were filtered out -- "
          f"industry not in today's top {config.GOAT_DMA_BREAKOUT_TOP_INDUSTRY_COUNT} by Perf Week."
      )
  ```
- **PATTERN**: the existing `if result["asx_unavailable"]:` / `if result["already_staged_elsewhere"]:` blocks (lines 333-340) for placement and tone.
- **VALIDATE**: covered by task 5's report-render tests below.

### 6. UPDATE `scripts/systemd/second-brain-goat-dma-breakout-scan.service`

- **IMPLEMENT**: Add `After=second-brain-goat-industry-full-scan.service` as a second line in `[Unit]`, below the existing `After=network.target`.
- **GOTCHA**: This does not by itself force run ordering across two independently-`OnCalendar`-scheduled oneshot services on different timers — it only matters if both happen to be triggered by the same activation event (e.g. a boot catch-up via `Persistent=true`). It's explicitly belt-and-suspenders per the handoff doc, not the primary ordering mechanism (the 75-minute clock gap + the code's own fail-open path are). Do not also change the `OnCalendar` time in the `.timer` file — out of scope.
- **VALIDATE**: manual read-through only; no automated test for a systemd unit file. Flag for Shaun to `sudo cp` to `/etc/systemd/system/` + `systemctl daemon-reload` on the VPS when deploying (per existing deploy convention — never do this yourself).

### 7. UPDATE `investments/goat/goat/tests/test_industry_constituents.py`

- **IMPLEMENT**: Replace `test_fetch_industry_constituents_us_returns_none_for_unmapped_slug` — it currently calls `fetch_industry_constituents_us("Not A Real Industry")` with `fetch_screener_universe` **not** monkeypatched, which will hit the real network once the derive-fallback ships. Rewrite as a test that *does* monkeypatch `fetch_screener_universe` and asserts the derived slug was used, e.g.:
  ```python
  def test_fetch_industry_constituents_us_derives_slug_for_unmapped_industry_label(monkeypatch):
      _patch_universe(monkeypatch)
      captured = {}

      def _fake_fetch_screener_universe(filters=None, sort="pricecash"):
          captured["filters"] = filters
          return []

      monkeypatch.setattr(
          "goat.industry_constituents.finviz_screener.fetch_screener_universe",
          _fake_fetch_screener_universe,
      )
      result = industry_constituents.fetch_industry_constituents_us("Business Equipment & Supplies")
      assert captured["filters"] == "ind_businessequipmentsupplies,sh_avgvol_o100,sh_price_o1"
      assert result == []
  ```
- **IMPLEMENT**: Add `test_fetch_industry_constituents_us_explicit_slug_overrides_derived_rule` proving a label present in `GOAT_FINVIZ_INDUSTRY_SLUGS` uses that slug verbatim even if the derived rule would produce something different (use a fake override entry with a deliberately "wrong" slug string to prove precedence, not coincidence).
- **GOTCHA**: `_patch_universe` already monkeypatches `GOAT_FINVIZ_INDUSTRY_SLUGS` to `_FAKE_SLUGS = {"Semiconductors": "ind_semiconductors"}` — any label other than `"Semiconductors"` is already "unmapped" under this fixture, so no fixture change is needed, only new/rewritten test bodies.
- **VALIDATE**: `uv run --directory investments/goat python -m pytest goat/tests/test_industry_constituents.py -q`

### 8. UPDATE `investments/goat/goat/tests/test_dma_breakout_scan.py`

- **IMPLEMENT**: Add a `# --- fetch_top_industry_allow_set ---` section with:
  - `test_fetch_top_industry_allow_set_returns_none_when_no_snapshot_exists(db_conn)` — empty DB, asserts `None`.
  - `test_fetch_top_industry_allow_set_unions_top_n_industries(db_conn, monkeypatch)` — insert a fake `industry_full` snapshot via `goat_db.insert_rotation_snapshots` (or call `industry_rotation_full.capture_full_industry_snapshot` directly with a small fake ranking of e.g. 3 industries + `GOAT_DMA_BREAKOUT_TOP_INDUSTRY_COUNT` monkeypatched down to 2), monkeypatch `industry_constituents.get_or_refresh_industry_constituents` to return deterministic tickers per label, assert the union excludes the 3rd/excluded industry's tickers.
- **IMPLEMENT**: Extend `_patch_common` with an `industry_allow_set=None` parameter (default meaning "no filter" — patch `fetch_top_industry_allow_set` to return `None` by default, same "opt into the ETF/industry bucket explicitly" pattern `etf_universe` already uses) so every pre-existing test in this file stays unaffected unless it explicitly opts into the allow-set.
- **IMPLEMENT**: Add tests under `# --- run_dma_breakout_scan industry filter ---`:
  - staged when ticker's industry is in the allow-set,
  - filtered + `filtered_by_industry == 1` + not staged when not in the allow-set,
  - ETF ticker always staged regardless of allow-set contents (exemption),
  - `industry_allow_set is None` (no snapshot) → unfiltered, `industry_filter_applied is False`.
- **PATTERN**: `_patch_common` (lines 265-287) and the existing `etf_universe`-style opt-in parameter for the shape to mirror.
- **VALIDATE**: `uv run --directory investments/goat python -m pytest goat/tests/test_dma_breakout_scan.py -q`

### 9. UPDATE `investments/goat/goat/tests/test_dma_breakout_scan.py` (report render)

- **IMPLEMENT**: Add `test_render_dma_breakout_candidates_report_shows_industry_filter_unavailable_banner` and `test_render_dma_breakout_candidates_report_shows_filtered_by_industry_count`, mirroring the existing `asx_unavailable`/`already_staged_elsewhere` render tests in this file (search for `render_dma_breakout_candidates_report` in the file for the existing pattern — read the section below line 438 before writing these).
- **VALIDATE**: same pytest command as task 8.

---

## TESTING STRATEGY

### Unit Tests
- `_derive_finviz_slug` — pure function, table-driven against the 5 already-live-verified cases plus 2-3 of today's actual top-36 misses (e.g. "Business Equipment & Supplies", "REIT - Hotel & Motel", "Beverages - Wineries & Distilleries").
- `fetch_industry_constituents_us` — explicit-slug precedence + derived-slug fallback (task 7).
- `get_latest_rotation_snapshot_date` — empty table → `None`; one scope populated, another scope queried → `None` (scope isolation); multiple dates for the same scope → the max one.
- `fetch_top_industry_allow_set` — no snapshot → `None`; top-N union correctness; excluded industries' tickers not included.
- `run_dma_breakout_scan` gating — covered in task 8 (allow/filter/ETF-exempt/fail-open).

### Integration Tests
None beyond the existing `db_conn`-backed tests in `test_dma_breakout_scan.py` — this feature has no new external integration surface (same Finviz screener call, same SQLite tables).

### Edge Cases
- No `industry_full` snapshot has ever been captured (fresh DB, or `scan-industries-full` has never successfully run) — must fail open, not raise, not stage zero.
- A derived slug resolves to an empty Finviz screen (wrong guess) — that industry simply contributes zero tickers to the allow-set; must not crash or retry excessively (existing cache-fallback behavior already covers this).
- An ETF candidate crosses its MA in a day where the industry_full snapshot exists and most industries are filtered — ETF must still be staged.
- Fewer than `GOAT_DMA_BREAKOUT_TOP_INDUSTRY_COUNT` rows exist in the latest snapshot (e.g. a partial Finviz Groups scrape) — `sorted(...)[:36]` on a shorter list must not raise, just use what's there.

---

## VALIDATION COMMANDS

### Level 1: Syntax & Style
```powershell
uv run --directory investments/goat ruff check goat/dma_breakout_scan.py goat/industry_constituents.py goat/db.py goat/config.py
```
(If `ruff` isn't configured for this package, skip — confirm via `investments/goat/pyproject.toml` before assuming.)

### Level 2: Unit Tests
```powershell
uv run --directory investments/goat python -m pytest goat/tests/test_dma_breakout_scan.py goat/tests/test_industry_constituents.py -q
```

### Level 3: Integration Tests
```powershell
uv run --directory investments/goat python -m pytest -q
```
Full suite — confirms no regression elsewhere (e.g. `test_industry_rotation_full.py`, `test_monitor.py` which also exercise `goat_rotation_snapshots`).

### Level 4: Manual Validation
Run `scan-industries-full` then `scan-dma-breakout` **via `scripts/invoke_investments.ps1` on the VPS, never locally against the real DB**:
```powershell
scripts/invoke_investments.ps1 -Package goat -Command "scan-industries-full" && scripts/invoke_investments.ps1 -Package goat -Command "scan-dma-breakout"
```
Confirm `dma-breakout-candidates-pending-review.md` only contains tickers whose industry appears in that same day's `industry-ranking-full.md` top 36 — spot-check 2-3 included and 2-3 excluded candidates by hand against both files. Check the dma-breakout run's log (`dma_breakout_scan_runs.log`) for any `[goat-industry-constituents] no explicit slug override for ...` lines and spot-verify 2-3 of those derived slugs directly against `finviz.com/screener.ashx?f=ind_<slug>` to confirm they return sane, on-theme results (same live-check posture as the original 5).

### Level 5: Additional Validation
None.

---

## ACCEPTANCE CRITERIA

- [ ] `fetch_industry_constituents_us` resolves a Finviz slug for any of the 144 industry labels (explicit override or derived rule), not just the original 39.
- [ ] `run_dma_breakout_scan` only stages non-ETF candidates whose industry is in the latest `industry_full` snapshot's top `GOAT_DMA_BREAKOUT_TOP_INDUSTRY_COUNT` (36) by rank.
- [ ] ETF candidates are staged regardless of industry-filter membership.
- [ ] No `industry_full` snapshot yet → scan runs unfiltered (today's behavior), report shows the unavailable-filter banner.
- [ ] `filtered_by_industry` count surfaces in the rendered report.
- [ ] All validation commands pass with zero errors; full `investments/goat` test suite passes (regression-free).
- [ ] `second-brain-goat-dma-breakout-scan.service` has the new `After=` ordering line.
- [ ] Code follows this codebase's dated-comment/fail-open/fail-safe-empty conventions.

---

## COMPLETION CHECKLIST

- [ ] All 9 tasks completed in order
- [ ] Each task's validation command passed immediately after that task
- [ ] Full `investments/goat` pytest suite passes
- [ ] No linting errors (if `ruff` applies to this package)
- [ ] Manual VPS validation run completed and spot-checked (Shaun, not the execution agent, runs this — never run `invoke_investments.ps1` against the real DB from a dev/implementation session)
- [ ] Acceptance criteria all met
- [ ] systemd `.service` file change ready for Shaun's manual `sudo cp` + `daemon-reload` on next deploy

---

## NOTES

- **ETF exemption** (handoff Open Question 2): decided — ETF rows stay always-eligible, never gated by the industry filter (no natural Finviz-industry membership for a fund ticker).
- **ASX coverage gap** (handoff Open Question 3): decided — accepted as-is. `GOAT_ASX_INDUSTRY_CONSTITUENTS` is hand-curated and covers only a slice of the 144 industries; an ASX ticker in an uncovered industry simply never appears as a constituent (existing "Not Covered" discipline), not something this feature expands.
- **Snapshot-read mechanism** (handoff Open Question 4): confirmed cheap and already resolved via `get_latest_rotation_snapshot_date` + `get_rotation_snapshots_for_date` — no new query infrastructure beyond one small helper.
- **First-run cost** (handoff Open Question 5): the first real run after deploy will cold-fetch all 36 industries' constituents (one Finviz screener call each, not cached yet); after that, the existing 7-day TTL (`GOAT_INDUSTRY_CONSTITUENTS_CACHE_TTL_DAYS`) means most days hit cache. Worth a glance at `dma_breakout_scan_runs.log` runtime on the first live run, but not a blocking concern.
- **Slug derivation vs. hand-typing** (the plan's one real architectural fork): Shaun confirmed rule-derive over hand-typing ~105 more dict entries (2026-10-20). The existing 39 explicit entries stay as a verified-override table for any case the mechanical rule gets wrong.
