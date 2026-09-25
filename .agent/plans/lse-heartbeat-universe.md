# Feature: LSE Heartbeat Universe

The following plan should be complete, but it's important to validate documentation and codebase patterns and task sanity before implementing. Pay special attention to naming of existing utils/types/models — import from the right files.

## Feature Description

Goat's heartbeat scan (`goat/heartbeat_scan.py`) currently only ever looks at S&P 500 constituents. Shaun spotted a genuine "heartbeat" consolidation pattern on **Braemar Plc (`BMS.L`, London Stock Exchange)** on his own charting platform and asked why the scan never surfaced it — confirmed live 2026-09-21 that `check_heartbeat_breakout` itself fires `"interesting"` on `BMS.L`'s real price history (13.6% range, 100% smoothness, 27 confirmed swings, no breakdown); the pattern-detection logic isn't the problem, the universe is. This feature adds a second, FTSE 100-sourced leg to the same scan so a London Stock Exchange-listed stock can actually be scanned (and staged as a candidate) alongside the existing S&P 500 leg.

Full background, live research, and gotchas: `investments/goat/lse-heartbeat-universe-handoff.md`.

## User Story

As Shaun (running Goat's daily/on-demand heartbeat scan)
I want the scan to also cover FTSE 100-listed stocks, not just the S&P 500
So that a genuine heartbeat pattern on a UK-listed stock (like the one that prompted this) gets surfaced the same way a US one already does

## Problem Statement

`heartbeat_scan.run_heartbeat_scan` sources its entire universe from `sp500_universe.get_or_refresh_sp500_constituents` — an LSE stock is structurally impossible to surface regardless of how good its chart looks, because it's never in the ~500 tickers being checked.

## Solution Statement

Add a `ftse100_universe.py` module (mirroring `sp500_universe.py`'s Wikipedia-scrape + DB-cache-with-TTL pattern exactly, including its own `goat_ftse100_constituents` cache table), a `tickers.lse_variant()` helper (mirroring `asx_variant()`), and a `GOAT_ICB_TO_ETF_SECTOR_LABEL` mapping (mirroring `GOAT_GICS_TO_ETF_SECTOR_LABEL`) so FTSE 100 constituents can be gated by the same "currently rising sector" filter the US leg already uses. `run_heartbeat_scan` is extended to build one combined constituent list (US + LSE, each row market-tagged) instead of only fetching the S&P 500 — the existing per-ticker loop, `check_heartbeat_breakout` call, fundamentals context, and dedup/staging logic are untouched, they simply run over a longer list. The report gains an Exchange column (reusing the existing `exchange` DB column already added for `dma_breakout_scan.py`, not a new column).

## Feature Metadata

**Feature Type**: Enhancement (extends an existing scan's universe)
**Estimated Complexity**: Medium
**Primary Systems Affected**: `investments/goat` (heartbeat scan, config, db), `investments/my-trader` (tickers.py)
**Dependencies**: `requests` + `beautifulsoup4` (already used by `sp500_universe.py`/`asx200_universe.py`), `yfinance` (already a dependency)

---

## Design Decisions Made During Planning (read before implementing)

These resolve every "Open Question" in the handoff. Do not re-litigate them without checking with Shaun first — they were each explicitly reasoned through against the live research already gathered.

1. **Breadth: FTSE 100, not FTSE 350.** Per the handoff's own recommendation — smaller, more liquid, cleanest confirmed Wikipedia source. **Important, tell Shaun explicitly when this ships**: Braemar Plc (`BMS.L`, the actual stock that prompted this whole feature) is ~£73.6M market cap and is almost certainly NOT in the FTSE 100 itself — this v1 build will very likely still not catch that specific example. That's an accepted, known limitation of the breadth decision, not a bug to chase down; widening to FTSE 350/SmallCap is a deliberate future breadth decision, not this build's job.
2. **Sector gating: build an ICB→SPDR-label mapping (Shaun's choice).** New `GOAT_ICB_TO_ETF_SECTOR_LABEL` dict in `goat/config.py`, same shape and same "unmapped → print + skip, never crash" behavior as the existing `GOAT_GICS_TO_ETF_SECTOR_LABEL`. See Task 3 for the actual mapping — it was built from a live fetch of the real FTSE 100 Wikipedia page's ICB column values (2026-09-21), not guessed.
3. **Constituent caching: DB-cached with TTL, mirroring `sp500_universe.py` exactly** (not `asx200_universe.py`'s no-cache approach) — this feeds `heartbeat_scan.py` specifically, same as the S&P 500 leg, not a DB-write-free tool.
4. **Liquidity floor: none needed for v1 — this resolves Open Question 4, it's not left open.** The heartbeat scan today has **no liquidity/market-cap floor on the US leg at all** (unlike `dma_breakout_scan.py`, which does) — S&P 500 index membership itself is treated as a sufficient large-cap/liquidity proxy. FTSE 100 is the UK's own large-cap index and plays the same structural role. `BMS.L`'s thin ~37k shares/day volume (the handoff's Gotcha 3) is real, but per Decision 1 above `BMS.L` isn't even in the FTSE 100 universe this build scans — so it isn't a live concern for what's actually in scope. Do not add a liquidity floor to this leg; if FTSE 350/SmallCap breadth is ever added later, that's when a real floor becomes necessary and it should be researched then, against real data for whatever tickers are actually newly in scope.
5. **Currency (GBp vs GBP): no special handling needed — this also resolves Open Question 5.** The trap is real (yfinance reports many LSE stocks in pence, a 100x unit surprise), but it only matters for code comparing against an absolute price/market-cap/AUM threshold. Per Decision 4, this build adds no such threshold, and `fundamentals_context.compute_survival_context` is already confirmed ratio/percentage-based (debt/equity, cash runway, margins, revenue growth — none are absolute price levels), so it needs no changes either. Leave a short code comment on `ftse100_universe.py`/`heartbeat_scan.py`'s LSE branch noting the trap exists, for whoever adds a price-level threshold later — don't build currency-conversion machinery that has nothing to guard yet.
6. **Ethical filter (UK defense gap): accept for v1, no code change.** `heartbeat_scan.py` doesn't call `scripts.ethical_filter.check_ticker` for the existing US leg either (confirmed — only `dma_breakout_scan.py` does), so adding it only for the new LSE leg would be a new, asymmetric behavior, not a gap being "fixed". Leave both legs as they are; this is a pre-existing, accepted limitation of the heartbeat scan generally, not something this build introduces or must solve.
7. **Report/notification integration: combined into the existing `heartbeat-candidates-pending-review.md`, add an Exchange column.** Reuse the `exchange` column already on `goat_pending_candidates` (added 2026-09-17 for `dma_breakout_scan.py` — see `goat/db.py:141-150`) — do **not** add a new `market` column. Populate it the same way `dma_breakout_scan.py` does: `data.info.get("fullExchangeName") or data.info.get("exchange")` from `market_data.fetch_ticker_data`, at staging time.
8. **`lse_variant()` placement: `mytrader/tickers.py`**, mirroring `asx_variant()` — same file, same reasoning (a ticker-qualification helper belongs with the other ones even though this specific exchange support starts in `goat`).
9. **`ftse100_universe.py` placement: `goat/goat/`, not `mytrader/mytrader/`.** This is a deliberate departure from copying `asx200_universe.py`'s location. `asx200_universe.py` lives in `mytrader/` because it's DB-write-free and used by two packages (`mytrader/cash_value_scan.py` and `goat/dma_breakout_scan.py`). Per Decision 3, the FTSE 100 universe is DB-cached (like `sp500_universe.py`) and — for this build — consumed only by `goat/heartbeat_scan.py`. `sp500_universe.py` is the closer precedent on both counts (DB-cached, goat-only), and it lives in `goat/goat/` — so `ftse100_universe.py` does too.

---

## CONTEXT REFERENCES

### Relevant Codebase Files — READ THESE BEFORE IMPLEMENTING

- `investments/goat/goat/sp500_universe.py` (whole file, 81 lines) — **the primary pattern to mirror.** Fetch function (Wikipedia scrape, `requests` + `BeautifulSoup`, try/except-returns-None), `get_or_refresh_*` cache-with-TTL wrapper. `ftse100_universe.py` should have the same two-function shape.
- `investments/goat/goat/db.py:37-42` (`goat_sp500_constituents` table DDL) and `:244-267` (`get_sp500_constituents_fetched_at`, `replace_sp500_constituents`, `get_sp500_constituents`) — mirror exactly for the new `goat_ftse100_constituents` table/functions. Note the migration idiom used throughout this file (`ALTER TABLE ... ADD COLUMN`, wrapped in `try/except sqlite3.OperationalError: pass`) if a new column is ever needed later — not needed for this build since we're adding a whole new table, not altering an existing one.
- `investments/goat/goat/heartbeat_scan.py` (whole file, 135 lines) — the orchestrator being extended. `run_heartbeat_scan` (lines 21-99) is where the combined-universe logic goes; `render_heartbeat_candidates_report` (lines 102-128) is where the Exchange column goes.
- `investments/goat/goat/config.py:298-314` (`GOAT_GICS_TO_ETF_SECTOR_LABEL`) — mirror exactly for `GOAT_ICB_TO_ETF_SECTOR_LABEL`, including the "written out explicitly so an unmapped label fails loudly via a skip+print, not silently" comment convention.
- `investments/goat/goat/config.py:291-296` (`GOAT_SP500_WIKI_URL`/`GOAT_SP500_CACHE_TTL_DAYS`/`GOAT_SP500_USER_AGENT`) — mirror for the FTSE 100 equivalents.
- `investments/goat/goat/dma_breakout_scan.py:61-102` (`fetch_universe_constituents`) — the closest existing precedent in this codebase for combining more than one market into a single scan universe with per-row market tags. `heartbeat_scan.py`'s new combined-fetch logic should follow this row shape (`{"ticker", "label"/sector, "market", "company"}`) even though it isn't reusing this function directly (heartbeat has its own sector-gating step this function doesn't).
- `investments/goat/goat/dma_breakout_scan.py:239-243` — exact idiom for fetching `exchange_name` from `market_data.fetch_ticker_data(ticker).info` at staging time; reuse verbatim in `heartbeat_scan.py`.
- `investments/goat/goat/dma_breakout_scan.py:293-336` (`render_dma_breakout_candidates_report`) — has the Exchange column already; mirror its column addition and its `(row.get("exchange") or "n/a").replace("|", "/")` null-safety idiom (existing heartbeat candidates predate the `exchange` column being populated for this source, so it will be null for old rows).
- `investments/my-trader/mytrader/tickers.py` (whole file, 15 lines) — add `lse_variant()` next to `asx_variant()`.
- `investments/my-trader/mytrader/config.py:646-647` (`ASX200_WIKI_URL`/`ASX200_USER_AGENT`) — naming convention reference only; the actual FTSE100 constants go in `goat/config.py` per Decision 9, not here.
- `investments/goat/goat/main.py:100-117` (`cmd_scan_heartbeat`) — the `candidate_label="new S&P 500 heartbeat candidate(s)"` string (line 110) needs updating since the scan is no longer US-only.
- `investments/goat/goat/tests/conftest.py` (whole file) — `db_conn` fixture wiring, `_isolate_goat_report_path` (add nothing here — `GOAT_HEARTBEAT_CANDIDATES_MD_PATH` is already isolated), `_no_real_price_history_fetch` autouse stub.
- `investments/goat/goat/tests/test_sp500_universe.py` (whole file) — mirror test shape exactly for `test_ftse100_universe.py` (fetch parsing, missing-table, bad-status, network-error, cache-fresh/stale/fallback).
- `investments/goat/goat/tests/test_heartbeat_scan.py` (whole file) — existing tests already monkeypatch `goat.heartbeat_scan.sp500_universe.get_or_refresh_sp500_constituents`; new tests need to also monkeypatch the new `ftse100_universe` call the same way. `_patch_common` (lines 40-62) needs a new parameter for FTSE constituents.
- `investments/my-trader/mytrader/tests/test_asx200_universe.py` (whole file) — reference for the `_restore_real_fetch` autouse-fixture-override idiom if `ftse100_universe.py` ends up needing an equivalent "don't hit the network by default" global stub in `goat/tests/conftest.py` (check whether one already implicitly exists via `_no_real_price_history_fetch` — it doesn't cover constituent-scrape functions, only price history, so `test_ftse100_universe.py`'s own tests must monkeypatch `requests.get` per-test like `test_sp500_universe.py` already does; no new global stub needed).
- `investments/goat/goat/heartbeat.py` (whole file, module docstring especially) — **do not touch.** `check_heartbeat_breakout` is confirmed ticker-agnostic and works unmodified on `BMS.L`'s real data; this build only changes what tickers get fed into it.
- `investments/goat/goat/fundamentals_context.py` (whole file) — **do not touch.** Already currency-naive per Decision 5.
- `investments/goat/pyproject.toml` — confirms `goat` depends on `my-trader` (`tickers.lse_variant` import is valid) via `[tool.uv.sources] my-trader = { workspace = true }`.

### New Files to Create

- `investments/goat/goat/ftse100_universe.py` — FTSE 100 constituent scraper + DB-cached refresh, mirroring `sp500_universe.py`.
- `investments/goat/goat/tests/test_ftse100_universe.py` — mirrors `test_sp500_universe.py`.

### Files to Edit

- `investments/my-trader/mytrader/tickers.py` — add `lse_variant()`.
- `investments/my-trader/mytrader/tests/test_tickers.py` — add test(s) for `lse_variant()` (check existing test file structure for `test_asx_variant`-equivalent to mirror).
- `investments/goat/goat/config.py` — add `GOAT_FTSE100_WIKI_URL`, `GOAT_FTSE100_CACHE_TTL_DAYS`, `GOAT_FTSE100_USER_AGENT`, `GOAT_ICB_TO_ETF_SECTOR_LABEL`.
- `investments/goat/goat/db.py` — add `goat_ftse100_constituents` table to `init_goat_tables`, plus `get_ftse100_constituents_fetched_at`, `replace_ftse100_constituents`, `get_ftse100_constituents` (mirror the three `*_sp500_*` functions exactly).
- `investments/goat/goat/tests/test_db.py` — add CRUD tests for the new table (check existing `test_db.py` for whether it already covers `goat_sp500_constituents`'s CRUD — if so mirror those tests; if that CRUD is only tested via `test_sp500_universe.py`, mirror there instead and skip `test_db.py`).
- `investments/goat/goat/heartbeat_scan.py` — extend `run_heartbeat_scan` to combine US + LSE constituents; extend `render_heartbeat_candidates_report` with an Exchange column.
- `investments/goat/goat/tests/test_heartbeat_scan.py` — extend `_patch_common` and add LSE-leg test cases.
- `investments/goat/goat/main.py` — update the `candidate_label` string in `cmd_scan_heartbeat`.

### Live Research Already Done (do not re-derive)

**FTSE 100 Wikipedia table** (`https://en.wikipedia.org/wiki/FTSE_100_Index`, live-verified 2026-09-21): one wikitable, columns exactly `Company` / `Ticker` / `FTSE industry classification benchmark sector`. Same `class="wikitable"` shape `asx200_universe.py` already parses.

**Full set of distinct ICB sector values actually present in that column** (41 values, live-fetched 2026-09-21 — this is real Wikipedia data-quality noise, not a scraping bug: several are case-variant or synonym duplicates of each other):

```
Financial services, Insurance, Telecommunications services, Investment Trusts, Mining,
Food & tobacco, Pharmaceuticals & biotechnology, Media, Life insurance,
Aerospace & defence, Banks, Household goods & home construction, Oil & gas producers,
Tobacco, Real estate, Support services, Beverages, Health care equipment & supplies,
Chemicals, Travel and Leisure, General retailers, Banking Services, Retailers,
Real estate investment trusts, Multiline utilities, Electronic equipment & parts,
Non-life Insurance, Homebuilding & construction supplies, Industrial engineering,
Mobile telecommunications, Food & drug retailing, General industrials,
Electrical utilities & independent power producers, Personal goods, Retail hospitality,
Software & Computer Services, Software & computer services, Travel & leisure,
Leisure Goods, Collective investments, Industrial goods and services
```

Note the exact-string duplicates that differ only by case/ampersand: `"Travel and Leisure"` vs `"Travel & leisure"`, `"Software & Computer Services"` vs `"Software & computer services"` — the mapping dict below has separate keys for each variant (same "written out explicitly, no cleverness" convention `GOAT_GICS_TO_ETF_SECTOR_LABEL` already uses). **Re-verify this list live during implementation** (Wikipedia table headers/values drift, per the handoff's own gotcha) — treat the mapping below as a strong starting draft, not gospel; if the live table has changed, update the dict to match what's actually there rather than forcing old values.

### Patterns to Follow

**Wikipedia scrape function shape** (from `sp500_universe.fetch_sp500_constituents`):
```python
def fetch_ftse100_constituents() -> list[dict[str, str]] | None:
    import requests
    from bs4 import BeautifulSoup
    try:
        r = requests.get(config.GOAT_FTSE100_WIKI_URL, headers=_HEADERS, timeout=30)
        if r.status_code != 200:
            return None
        soup = BeautifulSoup(r.text, "html.parser")
        table = soup.find("table", {"class": "wikitable"})
        if table is None:
            return None
        rows: list[dict[str, str]] = []
        for tr in table.find_all("tr")[1:]:
            cells = tr.find_all("td")
            if len(cells) < 3:
                continue
            company = cells[0].get_text(strip=True)
            ticker = cells[1].get_text(strip=True)
            icb_sector = cells[2].get_text(strip=True)
            if not company or not ticker or not icb_sector:
                continue
            rows.append({
                "ticker": tickers.normalize(ticker),  # bare code; .L added by caller
                "company": company,
                "icb_sector": icb_sector,
            })
        return rows or None
    except Exception:
        return None
```
Confirm the actual column order live during implementation (Company/Ticker/Sector, per the research above) rather than trusting this draft's cell indices blindly.

**`GOAT_ICB_TO_ETF_SECTOR_LABEL` draft** (add to `goat/config.py`, same section as `GOAT_GICS_TO_ETF_SECTOR_LABEL`; verify against the live table during build):
```python
GOAT_ICB_TO_ETF_SECTOR_LABEL: dict[str, str] = {
    "Financial services": "Financials",
    "Insurance": "Financials",
    "Life insurance": "Financials",
    "Banks": "Financials",
    "Banking Services": "Financials",
    "Non-life Insurance": "Financials",
    "Telecommunications services": "Communication Services",
    "Media": "Communication Services",
    "Mobile telecommunications": "Communication Services",
    "Mining": "Materials",
    "Chemicals": "Materials",
    "Food & tobacco": "Consumer Staples",
    "Tobacco": "Consumer Staples",
    "Beverages": "Consumer Staples",
    "Food & drug retailing": "Consumer Staples",
    "Pharmaceuticals & biotechnology": "Health Care",
    "Health care equipment & supplies": "Health Care",
    "Aerospace & defence": "Industrials",
    "Support services": "Industrials",
    "Industrial engineering": "Industrials",
    "General industrials": "Industrials",
    "Industrial goods and services": "Industrials",
    "Household goods & home construction": "Consumer Discretionary",
    "Homebuilding & construction supplies": "Consumer Discretionary",
    "Travel and Leisure": "Consumer Discretionary",
    "Travel & leisure": "Consumer Discretionary",
    "General retailers": "Consumer Discretionary",
    "Retailers": "Consumer Discretionary",
    "Personal goods": "Consumer Discretionary",
    "Retail hospitality": "Consumer Discretionary",
    "Leisure Goods": "Consumer Discretionary",
    "Oil & gas producers": "Energy",
    "Real estate": "Real Estate",
    "Real estate investment trusts": "Real Estate",
    "Multiline utilities": "Utilities",
    "Electrical utilities & independent power producers": "Utilities",
    "Electronic equipment & parts": "Technology",
    "Software & Computer Services": "Technology",
    "Software & computer services": "Technology",
    # Deliberately NOT mapped -- these are fund/trust vehicles, not operating
    # companies in a GICS-style sector. Falls through to the same "unmapped ->
    # print + skip" path an unrecognized GICS sector already takes in
    # run_heartbeat_scan, same as GOAT_GICS_TO_ETF_SECTOR_LABEL's own docstring
    # explains for a future label drift.
    # "Investment Trusts": intentionally omitted
    # "Collective investments": intentionally omitted
}
```

**Combined-universe fetch in `run_heartbeat_scan`** — replace the current single-source constituent loop with two tagged sources feeding the same `filtered` list:
```python
us_constituents = sp500_universe.get_or_refresh_sp500_constituents(conn)
lse_constituents = ftse100_universe.get_or_refresh_ftse100_constituents(conn)

filtered = []
for c in us_constituents:
    etf_label = config.GOAT_GICS_TO_ETF_SECTOR_LABEL.get(c["gics_sector"])
    if etf_label is None:
        print(f"[goat-heartbeat-scan] unmapped GICS sector {c['gics_sector']!r} for {c['ticker']}, skipping")
        continue
    if etf_label in rising_etf_labels:
        filtered.append({"ticker": c["ticker"], "company": c["security"], "sector_label": etf_label, "market": "US"})
for c in lse_constituents:
    etf_label = config.GOAT_ICB_TO_ETF_SECTOR_LABEL.get(c["icb_sector"])
    if etf_label is None:
        print(f"[goat-heartbeat-scan] unmapped ICB sector {c['icb_sector']!r} for {c['ticker']}, skipping")
        continue
    if etf_label in rising_etf_labels:
        filtered.append({"ticker": tickers.lse_variant(c["ticker"]), "company": c["company"], "sector_label": etf_label, "market": "LSE"})
```
Then the existing per-row loop body (lines 39-91 today) runs over `filtered` unchanged in spirit, except: (a) it now reads `row["ticker"]`/`row["company"]`/`row["sector_label"]` from this normalized dict shape instead of the raw S&P-500-only row shape, (b) at staging time it additionally fetches `exchange_name` from `market_data.fetch_ticker_data(ticker).info` (mirroring `dma_breakout_scan.py:239-243`) and passes `exchange=exchange_name` into `db.insert_goat_pending_candidate` (the `exchange` kwarg already exists on that function, see `db.py:214-226` — just unused by this caller today).

**Naming Conventions:** snake_case functions/variables, `GOAT_*` prefix for every new `goat/config.py` constant, `_HEADERS`/`_CODE_HEADERS`-style module-private constants for scraper internals (see `asx200_universe.py:24-28`).

**Error Handling:** every external fetch (`requests.get`, yfinance calls) wrapped in try/except returning `None` on any failure — never raises out of a `fetch_*`/`check_*` function. The per-ticker loop in `run_heartbeat_scan` already wraps each ticker's whole body in try/except printing and continuing — no change needed there.

**Logging Pattern:** `print(f"[goat-heartbeat-scan] ...")` prefixed messages for skip/error conditions — match this exact prefix for any new print statements added to `heartbeat_scan.py`.

---

## IMPLEMENTATION PLAN

### Phase 1: Foundation — ticker qualification + config

- `mytrader/tickers.py`: add `lse_variant()`.
- `goat/config.py`: add FTSE100 URL/cache/user-agent constants and `GOAT_ICB_TO_ETF_SECTOR_LABEL`.

### Phase 2: FTSE 100 universe module + cache table

- `goat/db.py`: add `goat_ftse100_constituents` table + CRUD, mirroring the sp500 ones exactly.
- `goat/ftse100_universe.py`: new file, `fetch_ftse100_constituents()` + `get_or_refresh_ftse100_constituents()`.

### Phase 3: Wire into the heartbeat scan

- `goat/heartbeat_scan.py`: combined-universe fetch (Phase 1+2's outputs), Exchange column on the report, `candidate_label` copy update in `main.py`.

### Phase 4: Testing & Validation

- Unit tests for every new/changed function, mirroring the existing suites' shape exactly (see Testing Strategy below).

---

## STEP-BY-STEP TASKS

Execute in order — each is atomic and independently testable.

### Task 1 — ADD `lse_variant` to `mytrader/tickers.py`

- **IMPLEMENT**: `def lse_variant(ticker: str) -> str: return normalize(ticker) + ".L"`, placed directly after `asx_variant`.
- **PATTERN**: `investments/my-trader/mytrader/tickers.py:13-14` (`asx_variant`) — identical shape, different suffix.
- **GOTCHA**: yfinance's LSE suffix is `.L` (confirmed live against `BMS.L` per the handoff) — not `.LON` or `.LSE`.
- **VALIDATE**: `uv run --directory investments/my-trader python -m pytest mytrader/tests/test_tickers.py -q`

### Task 2 — ADD test for `lse_variant`

- **IMPLEMENT**: In `investments/my-trader/mytrader/tests/test_tickers.py`, add a test mirroring whatever existing `test_asx_variant`-style test is there (e.g. `assert tickers.lse_variant("BMS") == "BMS.L"`, and a normalization case like `tickers.lse_variant("bms") == "BMS.L"`).
- **PATTERN**: Read the existing file first — mirror its exact structure for `asx_variant`'s test(s).
- **VALIDATE**: same command as Task 1.

### Task 3 — ADD FTSE 100 constants + ICB mapping to `goat/config.py`

- **IMPLEMENT**: Add near `GOAT_SP500_WIKI_URL`/`GOAT_SP500_CACHE_TTL_DAYS`/`GOAT_SP500_USER_AGENT` (`config.py:291-296`):
  ```python
  GOAT_FTSE100_WIKI_URL = "https://en.wikipedia.org/wiki/FTSE_100_Index"
  GOAT_FTSE100_CACHE_TTL_DAYS = 7  # same reasoning as GOAT_SP500_CACHE_TTL_DAYS --
                                      # FTSE 100 membership changes only a handful of
                                      # times a year.
  GOAT_FTSE100_USER_AGENT = "Mozilla/5.0 (compatible; SecondBrainGoat/1.0)"
  ```
  Then add `GOAT_ICB_TO_ETF_SECTOR_LABEL` near `GOAT_GICS_TO_ETF_SECTOR_LABEL` (`config.py:298-314`), using the draft mapping in the Patterns section above — **re-verify the live Wikipedia ICB values first** (see Task 4) and adjust the dict to match reality before finalizing this task.
- **PATTERN**: `investments/goat/goat/config.py:291-314`.
- **GOTCHA**: The ICB column has real case/synonym duplicates (`"Travel and Leisure"` vs `"Travel & leisure"`, etc — see Live Research section). Include every distinct string variant actually present as its own dict key; do not normalize/lowercase the scraped value to "simplify" this, since `GOAT_GICS_TO_ETF_SECTOR_LABEL` sets the precedent of exact-string, no-cleverness mapping and an unmapped variant already fails safe (skip + print), it doesn't crash.
- **VALIDATE**: `python -c "from goat import config; print(len(config.GOAT_ICB_TO_ETF_SECTOR_LABEL))"` (via `uv run --directory investments/goat python -c "..."`) — sanity-check the dict imports without error.

### Task 4 — ADD `goat_ftse100_constituents` table + CRUD to `goat/db.py`

- **IMPLEMENT**: Add table DDL inside `init_goat_tables`'s `executescript` call, directly after the `goat_sp500_constituents` table:
  ```sql
  CREATE TABLE IF NOT EXISTS goat_ftse100_constituents (
      ticker      TEXT PRIMARY KEY,
      company     TEXT NOT NULL,
      icb_sector  TEXT NOT NULL,
      fetched_at  TEXT NOT NULL
  );
  ```
  Then add three functions mirroring `get_sp500_constituents_fetched_at`/`replace_sp500_constituents`/`get_sp500_constituents` (`db.py:244-267`) exactly, renamed for FTSE100 and using the `company`/`icb_sector` column names above.
- **PATTERN**: `investments/goat/goat/db.py:37-42` (DDL) and `:244-267` (CRUD).
- **GOTCHA**: No migration block needed — this is a brand-new table (`CREATE TABLE IF NOT EXISTS` already handles both fresh and existing DBs), not a column added to an existing table. Don't add an `ALTER TABLE` migration block for this.
- **VALIDATE**: `uv run --directory investments/goat python -m pytest goat/tests/test_db.py -q` (add new CRUD tests here first if that file already covers the sp500 table's CRUD; otherwise this task's validation rides on Task 5's tests instead — check the file before deciding).

### Task 5 — CREATE `goat/ftse100_universe.py`

- **IMPLEMENT**: `fetch_ftse100_constituents()` (Wikipedia scrape, see Patterns section draft) + `get_or_refresh_ftse100_constituents(conn)` (TTL-cache wrapper, identical control flow to `sp500_universe.get_or_refresh_sp500_constituents`, swapping in the FTSE100 config constants and db functions from Task 4).
- **PATTERN**: `investments/goat/goat/sp500_universe.py` (whole file) — copy the two-function shape directly, this is the closest possible precedent.
- **IMPORTS**: `from mytrader import tickers` (for `tickers.normalize`), `from . import config, db`.
- **GOTCHA**: Confirm the live table's actual column order/header text against `https://en.wikipedia.org/wiki/FTSE_100_Index` before finalizing cell indices — the Live Research section above is a snapshot from 2026-09-21 and Wikipedia table structure can drift (same caveat `asx200_universe.py`'s own docstring raises about header text). If the column order differs from Company/Ticker/Sector, adjust the cell-index reads accordingly — don't force the draft blindly.
- **VALIDATE**: covered by Task 6's tests.

### Task 6 — CREATE `goat/tests/test_ftse100_universe.py`

- **IMPLEMENT**: Mirror `test_sp500_universe.py` exactly: fake-HTML fetch-and-parse test, missing-table/bad-status/network-error tests, cache-fresh/stale/fallback-on-scrape-failure tests. Use a `_FAKE_HTML` fixture built from the real live-verified column order confirmed in Task 5.
- **PATTERN**: `investments/goat/goat/tests/test_sp500_universe.py` (whole file, 110 lines) — near-verbatim structural mirror, renamed for FTSE100/ICB.
- **VALIDATE**: `uv run --directory investments/goat python -m pytest goat/tests/test_ftse100_universe.py -q`

### Task 7 — EXTEND `goat/heartbeat_scan.py`'s `run_heartbeat_scan`

- **IMPLEMENT**: Replace the single-source `constituents = sp500_universe.get_or_refresh_sp500_constituents(conn)` + its filter loop (`heartbeat_scan.py:26-35`) with the combined US+LSE fetch/filter shown in the Patterns section above, producing a `filtered` list of `{"ticker", "company", "sector_label", "market"}` dicts. Update the per-ticker loop body (`heartbeat_scan.py:39-91`) to read from this normalized shape instead of the raw S&P-500-only row shape (`row["ticker"]` was already used; `company_name = row["security"]` becomes `company_name = row["company"]`; `sector_label = config.GOAT_GICS_TO_ETF_SECTOR_LABEL[row["gics_sector"]]` becomes simply `sector_label = row["sector_label"]` since the mapping already happened during the fetch/filter step above). At staging time (where `db.insert_goat_pending_candidate` is currently called, `heartbeat_scan.py:68-71`), add an `exchange_name = data.info.get("fullExchangeName") or data.info.get("exchange")` line (reusing the already-fetched `data` from `market_data.fetch_ticker_data(ticker)` two lines above) and pass `exchange=exchange_name` into the call.
- **PATTERN**: `investments/goat/goat/dma_breakout_scan.py:239-243` for the exchange-name fetch idiom; `investments/goat/goat/dma_breakout_scan.py:61-102` for the general shape of a market-tagged combined-universe row.
- **IMPORTS**: add `from . import ftse100_universe` to the existing `from . import config, db, fundamentals_context, heartbeat, price_history, sector_rotation, sp500_universe` line.
- **GOTCHA**: `heartbeat.check_heartbeat_breakout(ticker, sector_label, close)` and `price_history.fetch_close_history(ticker, ...)` both already take a fully-qualified ticker string (`.L`-suffixed for LSE rows, produced by `tickers.lse_variant` during the fetch/filter step) — no changes needed inside the per-ticker loop's actual check-calling logic, only the row-shape reads described above.
- **VALIDATE**: covered by Task 8's tests; also run `uv run --directory investments/goat python -m pytest goat/tests/test_heartbeat_scan.py -q` after Task 8.

### Task 8 — EXTEND `goat/heartbeat_scan.py`'s `render_heartbeat_candidates_report`

- **IMPLEMENT**: Add an `Exchange` column to the markdown table (header row + per-row cell), mirroring `render_dma_breakout_candidates_report`'s exact null-safety idiom: `exchange = (row.get("exchange") or "n/a").replace("|", "/")`.
- **PATTERN**: `investments/goat/goat/dma_breakout_scan.py:293-336`, specifically the `| Ticker | Company | Exchange | Sector | Signal | Flagged |` header and the corresponding row-building line.
- **VALIDATE**: covered by the report-rendering tests in Task 9.

### Task 9 — EXTEND `goat/tests/test_heartbeat_scan.py`

- **IMPLEMENT**: 
  - Update `_patch_common` (lines 40-62) to also monkeypatch `goat.heartbeat_scan.ftse100_universe.get_or_refresh_ftse100_constituents` (default to an empty list, so every existing US-only test stays isolated from the new LSE leg — same isolation pattern `test_dma_breakout_scan.py`'s `_patch_common` already uses for its ETF universe param, see `test_dma_breakout_scan.py:265-279`).
  - Add new tests: a combined US+LSE run stages candidates from both sources; an LSE ticker gets `tickers.lse_variant`-qualified (`.L` suffix) before being checked/staged; an unmapped ICB sector is skipped (mirrors `test_run_heartbeat_scan_skips_unmapped_gics_sector`); the staged row's `exchange` column is populated from `market_data.fetch_ticker_data`.
  - Add a `render_heartbeat_candidates_report` test asserting the Exchange column appears and a missing-exchange row shows `n/a` (mirror `test_render_dma_breakout_candidates_report_missing_company_name_and_exchange_show_na`).
- **PATTERN**: `investments/goat/goat/tests/test_heartbeat_scan.py` (whole file) for the existing shape; `investments/goat/goat/tests/test_dma_breakout_scan.py` for the multi-market/ETF-bucket test patterns to adapt.
- **VALIDATE**: `uv run --directory investments/goat python -m pytest goat/tests/test_heartbeat_scan.py -q`

### Task 10 — UPDATE `goat/main.py`'s `cmd_scan_heartbeat` label

- **IMPLEMENT**: Change `candidate_label="new S&P 500 heartbeat candidate(s)"` (line 110) to `candidate_label="new heartbeat candidate(s)"` (drop the now-inaccurate "S&P 500" qualifier — the WhatsApp notification this drives should not claim US-only when the scan now covers LSE too).
- **PATTERN**: `investments/goat/goat/main.py:100-117`.
- **VALIDATE**: no dedicated test exists for this string today (confirm during implementation) — visual check is sufficient; covered incidentally if any existing test asserts on this literal string.

---

## TESTING STRATEGY

### Unit Tests

Every new function gets direct unit test coverage mirroring the equivalent existing function's test file 1:1 in structure (see each task's VALIDATE line). No new test infrastructure/fixtures needed — `goat/tests/conftest.py`'s `db_conn` fixture already initializes `goat_ftse100_constituents` via `init_goat_tables` once Task 4 lands.

### Integration Tests

`test_heartbeat_scan.py`'s extended `run_heartbeat_scan` tests (Task 9) are the integration-level coverage — they exercise the full combined-universe → sector-gate → check → stage pipeline through mocked constituent/price/fundamentals data, same depth as the existing S&P-500-only tests.

### Edge Cases

- FTSE100 scrape fails entirely (network error / table missing) → `get_or_refresh_ftse100_constituents` falls back to stale cache if one exists, or returns `[]` if not (mirrors `sp500_universe`'s contract exactly — the scan must degrade to US-only, never crash).
- An ICB sector value not in `GOAT_ICB_TO_ETF_SECTOR_LABEL` → skipped with a print, same as an unmapped GICS sector.
- A ticker already held/watchlisted/pending (from either the US or LSE leg) → skipped, same dedup logic as today, now exercised against `.L`-suffixed tickers too.
- Missing `exchange` on an older/mocked candidate row → report renders `n/a`, doesn't crash (mirrors the DMA breakout report's existing test).

---

## VALIDATION COMMANDS

### Level 1: Syntax & Style

```powershell
uv run --directory investments/goat ruff check goat/
uv run --directory investments/my-trader ruff check mytrader/
```

### Level 2: Unit Tests

```powershell
uv run --directory investments/my-trader python -m pytest mytrader/tests/test_tickers.py -q
uv run --directory investments/goat python -m pytest goat/tests/test_ftse100_universe.py goat/tests/test_db.py goat/tests/test_heartbeat_scan.py -q
```

### Level 3: Full Suite Regression

```powershell
uv run --directory investments/goat python -m pytest -q
uv run --directory investments/my-trader python -m pytest -q
```

### Level 4: Manual Validation (on the VPS via `invoke_investments.ps1` — never run `scan-heartbeat` locally against the real DB)

```powershell
.\scripts\invoke_investments.ps1 -Package goat -Command "scan-heartbeat"
```
Check `investments/goat/heartbeat-candidates-pending-review.md` for: (a) the new Exchange column present on every row, (b) at least a plausible number of LSE tickers scanned (sanity-check against FTSE 100's ~100 constituents, not zero), (c) no crash/traceback in the run output. Per Decision 1, do **not** expect `BMS.L` itself to appear — that's a known, accepted v1 limitation, not a bug.

Confirm `my-trader`'s `promote-candidate` path doesn't assume USD/AUD before a real LSE candidate is ever promoted into the watchlist for the first time (Open Question 7) — this is a read-through check of `holdings_ops.py`/the relevant `mytrader/checks/*` modules for any hardcoded currency symbol or unit assumption, not a code change; only fix it if something is actually found.

---

## ACCEPTANCE CRITERIA

- [ ] `lse_variant()` exists in `mytrader/tickers.py` and is tested
- [ ] `goat_ftse100_constituents` table exists, CRUD functions mirror the sp500 ones, tested
- [ ] `ftse100_universe.py` fetches + TTL-caches FTSE 100 constituents, degrades gracefully on scrape failure, tested
- [ ] `GOAT_ICB_TO_ETF_SECTOR_LABEL` exists, verified against the live Wikipedia table during implementation (not just the 2026-09-21 snapshot in this plan)
- [ ] `run_heartbeat_scan` scans both US and LSE constituents in currently-rising sectors, in one combined run
- [ ] A staged LSE candidate carries a `.L`-suffixed ticker and a populated `exchange` field
- [ ] `heartbeat-candidates-pending-review.md` shows an Exchange column for every row (existing + new)
- [ ] `candidate_label` in `cmd_scan_heartbeat` no longer claims "S&P 500" specifically
- [ ] All existing tests still pass unmodified in behavior (US-only path is a strict subset of the new combined path)
- [ ] All new tests pass
- [ ] No regressions in `dma_breakout_scan.py`, `sp500_universe.py`, or any other module this build reads but doesn't edit

## COMPLETION CHECKLIST

- [ ] All 10 tasks completed in order
- [ ] Each task's validation command passed immediately after that task
- [ ] Full test suite passes for both `goat` and `my-trader` packages
- [ ] `ruff check` clean on both changed packages
- [ ] Manual VPS validation run completed and report checked
- [ ] Acceptance criteria all met

---

## NOTES

- **Do not build** a UK sector-rotation ranking (Open Question 2's option (b) — explicitly not chosen; ICB→SPDR mapping was chosen instead).
- **Do not build** currency conversion/normalization anywhere (Decision 5 — nothing in this build needs it).
- **Do not build** a liquidity/market-cap floor for the LSE leg (Decision 4 — none exists for the US leg either, FTSE 100 membership is the proxy).
- **Do not add** UK names to `scripts/ethical_filter`'s `DEFENSE_TICKERS`/`DEFENSE_REVIEW_TICKERS` as part of this build (Decision 6 — accepted pre-existing gap, out of scope).
- **Do not** generalize this into a reusable "add any exchange" framework — this codebase's established convention (see `heartbeat.py`'s and `dma_breakout_scan.py`'s own module docstrings) is a deliberate second copy per market, not a shared abstraction. Any future non-LSE, non-ASX exchange gets its own handoff/plan, not a parameter added here.
- Tell Shaun explicitly, when this ships, that Braemar Plc itself almost certainly still won't appear (Decision 1) — this is expected, not a failure of the build.

**Confidence score: 8/10** for one-pass implementation success. The two residual risks are both explicitly flagged as build-time verification steps rather than blind spots: (1) the live FTSE 100 Wikipedia table's exact column order/ICB values may have drifted since the 2026-09-21 snapshot in this plan (Task 5's gotcha), and (2) the ICB→SPDR mapping is a reasonable v1 judgment call on ~39 category names, not a sourced ground truth — it may need a small correction pass after the first live run once Shaun can eyeball which sectors real FTSE 100 heartbeat candidates are landing in.
