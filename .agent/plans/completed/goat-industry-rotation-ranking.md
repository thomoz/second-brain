# Feature: Goat Industry Rotation Ranking

The following plan should be complete, but validate documentation and codebase patterns
and task sanity before implementing. Pay special attention to naming of existing utils,
types, and models — import from the right files.

## Feature Description

Extend Goat's existing sector-rotation ranking (`goat/sector_rotation.py`, the 11 SPDR
sector ETFs, `sector-ranking.md`) down to **industry** granularity — the ~130-150
finer-grained industry groups Finviz's screener uses (e.g. "Semiconductors" and
"Communication Equipment" as separate lines, rather than both folded into "Technology").
Same philosophy as existing Goat work: a finer-grained sibling to the sector scan, not a
new package.

Prompted by Shaun sharing Finviz-style "Money Flowing IN/OUT — Top 5 Industries"
screenshots and asking whether this repo can produce the same thing.

## User Story

As Shaun (advisor-mode Second Brain user)
I want to see which of Finviz's ~143 industry groups are showing the strongest/weakest
price momentum over a 6-month window
So that I can spot sector-rotation opportunities at finer granularity than the existing
11-sector ranking, without paying for a tool like TradeVision or Winston App.

## Problem Statement

Goat's Phase 2 sector rotation ranks only the 11 broad GICS sectors (via the SPDR Select
Sector ETFs). Shaun's own Finviz screenshots operate at a much finer industry level
(~130-150 groups) and he has no free, automated way to reproduce that view inside this
repo today.

## Solution Statement

Add a new `goat/industry_rotation.py` module, modeled directly on
`sector_rotation.py`'s `fetch_all_sector_closes()` + `rank_sectors()`, driven by a new
`GOAT_INDUSTRY_ETFS` ticker→label config dict covering every Finviz industry that has a
real, dedicated, currently-trading ETF (researched this session — see "Industry ETF
Universe" below). Industries with no dedicated ETF are left out and explicitly listed as
a coverage gap in the output report, never silently proxied by a looser substitute. No
new DB table, no candidate-staging, no WhatsApp notification — this is a pure
compute-and-render report, same shape as `sector-ranking.md` but with the full ranked
list (not just top/bottom 5) and a 6-month lookback window. The on-demand chart capability
from the original handoff stays purely conversational — no code, no CLI command; this
plan documents the recipe only.

## Feature Metadata

**Feature Type**: New Capability (sibling extension of an existing pattern)
**Estimated Complexity**: Low — mirrors an existing, working code path almost exactly;
no new DB schema, no new notification path, no new CLI-chart tooling.
**Primary Systems Affected**: `investments/goat/` only (`goat/config.py`, new
`goat/industry_rotation.py`, `goat/monitor.py`, `goat/main.py`, tests, `TOOLS.md`).
**Dependencies**: None new — reuses `yfinance` (already a goat dependency) via the
existing `goat/price_history.py`.

---

## Decisions Confirmed With Shaun (2026-08-23, this session)

1. **Ranking window: 6 months** (~126 trading days), matching the Finviz screenshots
   that prompted this feature — deliberately NOT reusing
   `GOAT_SECTOR_RANK_WINDOW_TRADING_DAYS` (63 days / 3 months), which stays as-is for the
   existing sector ranking. New, separate constant.
2. **Data storage: live re-fetch from yfinance at request time**, same as the sector
   ranking's `fetch_all_sector_closes()`. No new DB table, no daily-snapshot
   accumulation.
3. **Industry ETF universe: leave-out-with-gap-note.** An industry with no dedicated ETF
   is omitted from the ranking and named in a visible "not covered" list in the report —
   never silently substituted with a broader/looser proxy.
4. **Report shape: full ranked list of every covered industry**, with top 5 / bottom 5
   surfaced as the headline at the top (matches the Finviz screenshots' framing) followed
   by the complete table below.
5. **Chart trigger: purely conversational, no code.** No CLI subcommand, no new plotting
   dependency (nothing in this stack uses matplotlib or any charting library today —
   confirmed by search). Phase 3 of this plan is documentation of the recipe only, not an
   implementation task.

---

## Industry ETF Universe — Research Output (this session, 2026-08-23)

Sourced from Finviz's own industry taxonomy (`finviz.com/groups?g=industry`, 143
industries fetched this session — the canonical list to embed as `GOAT_FINVIZ_INDUSTRIES`,
see Task 1) cross-referenced against real, currently-trading, single-industry ETFs from
State Street/SPDR, iShares, VanEck, Invesco, Global X, First Trust, Pacer, and
AdvisorShares. Several (EATZ, BOAT, CRAK, CARZ, ESPO, XES, KBWB, PAVE) were explicitly
web-search-verified as still trading in August 2026 during this session; the rest are
long-established, large-AUM funds (GDX, SIL, XBI, IBB-class, SOXX/SMH-class, ITA, JETS,
XOP, ITB, XHB, KRE, TAN, BJK, IYZ, PHO, ICLN, WOOD, PICK, COPX, SLX, REM, FDN, IAI, KIE,
IHF, MOO, IHI) that did not need individual verification. Two initially-considered
tickers (HERO, AWAY) came back with no confirmable 2026 trading data during research and
were dropped rather than guessed — Electronic Gaming & Multimedia uses the verified ESPO
instead; Travel Services has no confident pick and is left as a gap.

**Gotcha — dict shape forces one ticker per industry, never one ticker for two
industries.** `GOAT_INDUSTRY_ETFS` must mirror `GOAT_SECTOR_ETFS`'s `dict[ticker,
label]` shape (ticker is the key). A ticker can only appear once, so where one ETF
plausibly fits two Finviz industries (e.g. IGV fits both "Software - Application" and
"Software - Infrastructure"; BJK fits both "Gambling" and "Resorts & Casinos"; IHI fits
both "Medical Devices" and "Medical Instruments & Supplies"), this plan picks exactly
one label per ticker and leaves the other as a gap — do NOT add the same ticker twice
under two dict entries; the second insert would silently overwrite the first with no
error. If a future session wants both industries "covered," that requires restructuring
to `dict[label, ticker]` instead (a larger, deliberate change, not an ad hoc tweak here).

**Coverage: 39 of 143 Finviz industries** get a dedicated-ETF mapping. The remaining 104
are gap-noted in the report, per Shaun's confirmed decision #3 above — this is expected,
not a shortfall to fix later (many of these industries, e.g. "Coking Coal", "Department
Stores", "Confectioners", genuinely have no dedicated US-listed ETF).

| Ticker | Finviz Industry Label |
|--------|------------------------|
| ITA | Aerospace & Defense |
| JETS | Airlines |
| CARZ | Auto Manufacturers |
| KBWB | Banks - Diversified |
| KRE | Banks - Regional |
| XBI | Biotechnology |
| XHB | Building Products & Equipment |
| IAI | Capital Markets |
| COPX | Copper |
| ESPO | Electronic Gaming & Multimedia |
| PAVE | Engineering & Construction |
| BJK | Gambling |
| GDX | Gold |
| IHF | Healthcare Plans |
| KIE | Insurance - Diversified |
| FDN | Internet Content & Information |
| IBUY | Internet Retail |
| WOOD | Lumber & Wood Production |
| BOAT | Marine Shipping |
| IHI | Medical Devices |
| XOP | Oil & Gas E&P |
| XES | Oil & Gas Equipment & Services |
| CRAK | Oil & Gas Refining & Marketing |
| PICK | Other Industrial Metals & Mining |
| INDS | REIT - Industrial |
| REM | REIT - Mortgage |
| ITB | Residential Construction |
| EATZ | Restaurants |
| SMH | Semiconductors |
| SIL | Silver |
| IGV | Software - Application |
| TAN | Solar |
| SLX | Steel |
| IYZ | Telecom Services |
| URA | Uranium |
| PHO | Utilities - Regulated Water |
| ICLN | Utilities - Renewable |
| MOO | Agricultural Inputs |
| EVX | Waste Management |

**Confidence note for the execution agent**: INDS (Pacer Industrial Real Estate ETF) and
EVX (VanEck Environmental Services ETF) are smaller/less liquid funds than the rest of
this list and were not individually web-verified this session (medium confidence, not
low). Task 6 below adds a one-time smoke test against real yfinance data specifically to
catch any of these 39 tickers that fail to resolve before this ships — treat a failure
there as "drop this one row to the gap list," not a blocker for the rest.

**Full 143-industry Finviz taxonomy** (source: `finviz.com/groups?g=industry`, fetched
2026-08-23) — embed verbatim as `GOAT_FINVIZ_INDUSTRIES` in Task 1:

```
Advertising Agencies, Aerospace & Defense, Agricultural Inputs, Airlines, Airports & Air
Services, Aluminum, Apparel Manufacturing, Apparel Retail, Asset Management, Auto & Truck
Dealerships, Auto Manufacturers, Auto Parts, Banks - Diversified, Banks - Regional,
Beverages - Brewers, Beverages - Non-Alcoholic, Beverages - Wineries & Distilleries,
Biotechnology, Broadcasting, Building Materials, Building Products & Equipment, Business
Equipment & Supplies, Capital Markets, Chemicals, Coking Coal, Communication Equipment,
Computer Hardware, Confectioners, Conglomerates, Consulting Services, Consumer
Electronics, Copper, Credit Services, Department Stores, Diagnostics & Research, Discount
Stores, Drug Manufacturers - General, Drug Manufacturers - Specialty & Generic, Education
& Training Services, Electrical Equipment & Parts, Electronic Components, Electronic
Gaming & Multimedia, Electronics & Computer Distribution, Engineering & Construction,
Entertainment, Farm & Heavy Construction Machinery, Farm Products, Financial
Conglomerates, Financial Data & Stock Exchanges, Food Distribution, Footwear &
Accessories, Furnishings, Fixtures & Appliances, Gambling, Gold, Grocery Stores, Health
Information Services, Healthcare Plans, Home Improvement Retail, Household & Personal
Products, Industrial Distribution, Information Technology Services, Insurance -
Diversified, Insurance - Life, Insurance - Property & Casualty, Insurance - Reinsurance,
Insurance - Specialty, Insurance Brokers, Integrated Freight & Logistics, Internet
Content & Information, Internet Retail, Leisure, Lodging, Lumber & Wood Production,
Luxury Goods, Marine Shipping, Medical Care Facilities, Medical Devices, Medical
Distribution, Medical Instruments & Supplies, Metal Fabrication, Mortgage Finance, Oil &
Gas Drilling, Oil & Gas E&P, Oil & Gas Equipment & Services, Oil & Gas Integrated, Oil &
Gas Midstream, Oil & Gas Refining & Marketing, Other Industrial Metals & Mining, Other
Precious Metals & Mining, Packaged Foods, Packaging & Containers, Paper & Paper Products,
Personal Services, Pharmaceutical Retailers, Pollution & Treatment Controls, Publishing,
Railroads, Real Estate - Development, Real Estate Services, Recreational Vehicles, REIT -
Diversified, REIT - Healthcare Facilities, REIT - Hotel & Motel, REIT - Industrial, REIT
- Mortgage, REIT - Office, REIT - Residential, REIT - Retail, REIT - Specialty, Rental &
Leasing Services, Residential Construction, Resorts & Casinos, Restaurants, Scientific &
Technical Instruments, Security & Protection Services, Semiconductor Equipment &
Materials, Semiconductors, Shell Companies, Silver, Software - Application, Software -
Infrastructure, Solar, Specialty Business Services, Specialty Chemicals, Specialty
Industrial Machinery, Specialty Retail, Staffing & Employment Services, Steel, Telecom
Services, Textile Manufacturing, Thermal Coal, Tobacco, Tools & Accessories, Travel
Services, Trucking, Uranium, Utilities - Diversified, Utilities - Independent Power
Producers, Utilities - Regulated Electric, Utilities - Regulated Gas, Utilities -
Regulated Water, Utilities - Renewable, Waste Management
```

Sources:
- [Finviz Group Screener](https://finviz.com/groups?g=industry&v=110&o=name)
- [State Street Sector and Industry ETFs](https://www.ssga.com/us/en/intermediary/capabilities/equities/sector-investing/sector-and-industry-etfs)
- Individual ticker verification via web search this session (EATZ, BOAT, CRAK, CARZ,
  ESPO, XES, KBWB, PAVE)

---

## CONTEXT REFERENCES

### Relevant Codebase Files — READ THESE BEFORE IMPLEMENTING

- `investments/goat/goat/sector_rotation.py` — the exact pattern to mirror.
  `fetch_all_sector_closes()` (lines 17-27) and `rank_sectors()` (lines 30-50) are the
  two functions to port to `industry_rotation.py`, swapping `GOAT_SECTOR_ETFS` for
  `GOAT_INDUSTRY_ETFS` and the window constant. **Do not port `check_sector_breakout()`**
  — no breakout/candidate signal is in scope for this feature (see "Explicitly Deferred"
  below).
- `investments/goat/goat/config.py` (lines 43-91) — `GOAT_SECTOR_ETFS` dict shape,
  `GOAT_SECTOR_HISTORY_LOOKBACK_DAYS`/`GOAT_SECTOR_RANK_WINDOW_TRADING_DAYS`/
  `GOAT_SECTOR_RANKING_MD_PATH` naming convention to mirror for the new
  `GOAT_INDUSTRY_*` constants. Note the comment style: every tunable constant gets an
  inline comment explaining its sourcing/reasoning — follow this exactly, it is a hard
  convention in this file.
- `investments/goat/goat/monitor.py` (lines 227-272) — `run_sector_scan()`,
  `render_sector_ranking_report()`, `write_sector_ranking_report()`. The industry
  equivalent's render/write functions belong in `monitor.py` too (not
  `industry_rotation.py`), matching where the sector ones live — `industry_rotation.py`
  itself should only hold the fetch/rank computation, same file-boundary as
  `sector_rotation.py`.
- `investments/goat/goat/main.py` (lines 62-80, 218-271) — `cmd_scan_sectors()` +
  its `subparsers.add_parser("scan-sectors", ...)` registration + `cmd_monitor()`'s call
  into `run_sector_scan()`/`write_sector_ranking_report()`. Mirror this shape for a new
  `scan-industries` subcommand and its `cmd_monitor()` integration.
- `investments/goat/goat-report.md` / `investments/goat/sector-ranking.md` — existing
  auto-generated report format/tone to match (the "Advisor notes only; no trade action is
  ever suggested here (see SOUL.md)" disclaimer line is required on every Goat report,
  do not drop it).
- `investments/goat/goat/tests/test_sector_rotation.py` — test pattern to mirror
  (`_flat_then_move`, `_dates` helpers; `test_rank_sectors_orders_by_window_return_missing_data_sorts_last`
  is the direct template for the industry-ranking equivalent test).
- `investments/goat/goat/tests/conftest.py` (lines 29-44) — `_isolate_goat_report_path`
  autouse fixture. **Must add** a `monkeypatch.setattr(goat_config,
  "GOAT_INDUSTRY_RANKING_MD_PATH", tmp_path / "industry-ranking.md")` line here, or any
  test exercising the new report-writer will write into the real repo path during test
  runs.
- `investments/goat/goat/price_history.py` — `fetch_close_history(ticker, lookback_days)`
  reused as-is, no changes needed. Already handles a bad/delisted ticker gracefully
  (returns `None`; `rank_sectors`-style code already sorts `None` rows last) — this is
  what makes the medium-confidence tickers (INDS, EVX) safe to ship even if one turns out
  to be wrong: it degrades to "no data" for that row, not a crash.
- `investments/TOOLS.md` (lines 39-70) — the "Manual / on-demand only" table. Add a new
  row for `scan-industries` here as part of this feature (documentation is part of the
  task, this file is explicitly maintained by hand per its own header).
- `investments/goat/HANDOFF.md` — update the top status line when this ships, same
  convention as every prior Goat phase (see how Phase 1/2/3/intraday entries are appended
  there).

### New Files to Create

- `investments/goat/goat/industry_rotation.py` — `fetch_all_industry_closes()` +
  `rank_industries()`, direct port of `sector_rotation.py`'s first two functions.
- `investments/goat/goat/tests/test_industry_rotation.py` — unit tests mirroring
  `test_sector_rotation.py`'s ranking tests (no breakout tests needed — there is no
  breakout check in scope).
- `investments/goat/goat/tests/test_monitor_industry_scan.py` (or add functions to the
  existing `test_monitor.py` — execution agent's call, whichever keeps `test_monitor.py`
  from growing unreasonably long is fine) — tests for `run_industry_scan()`,
  `render_industry_ranking_report()`, `write_industry_ranking_report()`.
- `investments/goat/industry-ranking.md` — the generated report itself (created by
  running the new command at least once during Level 4 validation; do not hand-author
  this file's content, it must come from a real run).

### Patterns to Follow

**Config comment convention** (from `config.py`): every tunable constant carries an
inline `#` comment stating *why* that number/value was chosen and citing the date/person
who confirmed it if applicable. Example to match:

```python
GOAT_INDUSTRY_RANK_WINDOW_TRADING_DAYS = 126  # ~6 calendar months of trading days --
                                                 # matches the Finviz screenshots that
                                                 # prompted this feature. Deliberately a
                                                 # SEPARATE constant from
                                                 # GOAT_SECTOR_RANK_WINDOW_TRADING_DAYS
                                                 # (63/3-month) -- Shaun confirmed
                                                 # 2026-08-23 these do not need to match.
```

**Error handling**: per-ticker `try/except` around each `fetch_close_history` call inside
the loop (see `fetch_all_sector_closes`), printing `[goat-industry-scan] error fetching
{ticker}: {e}` and storing `None` for that ticker rather than raising — one bad ticker
must never abort the whole scan.

**Report tone**: "Advisor notes only; no trade action is ever suggested here (see
SOUL.md)" disclaimer line, present on every existing Goat report — required here too.

**No candidate/alert/notification code** — this feature deliberately has none of that;
do not add `conn: sqlite3.Connection` parameters, DB writes, or `maybe_notify()` calls to
anything in this feature's scope. If a future session wants an industry-level breakout
signal, that is explicitly out of scope here (see "Explicitly Deferred").

---

## IMPLEMENTATION PLAN

### Phase 1: Config — Industry ETF Universe

**Tasks:**
- Add `GOAT_FINVIZ_INDUSTRIES: list[str]` (143 names, verbatim from the table above) to
  `goat/config.py`.
- Add `GOAT_INDUSTRY_ETFS: dict[str, str]` (39 ticker→label pairs from the table above).
- Add `GOAT_INDUSTRY_HISTORY_LOOKBACK_DAYS = 400` (reuse the same calendar-day margin as
  `GOAT_SECTOR_HISTORY_LOOKBACK_DAYS` — 400 calendar days ≈ 276 trading days,
  comfortably exceeds the 126-trading-day window below).
- Add `GOAT_INDUSTRY_RANK_WINDOW_TRADING_DAYS = 126`.
- Add `GOAT_INDUSTRY_RANKING_MD_PATH = GOAT_DIR / "industry-ranking.md"`.

### Phase 2: Core Implementation — Ranking

**Tasks:**
- `goat/industry_rotation.py`: `fetch_all_industry_closes()` (mirrors
  `fetch_all_sector_closes`, iterates `GOAT_INDUSTRY_ETFS`, uses
  `GOAT_INDUSTRY_HISTORY_LOOKBACK_DAYS`) and `rank_industries()` (mirrors `rank_sectors`,
  uses `GOAT_INDUSTRY_RANK_WINDOW_TRADING_DAYS`, same missing-data-sorts-last rule).
- `goat/monitor.py`: `run_industry_scan()` — no `conn` param needed (no DB access at
  all: no candidates, no alerts). Returns `{"ranking": [...], "not_covered": [...]}`
  where `not_covered = sorted(set(GOAT_FINVIZ_INDUSTRIES) - set(GOAT_INDUSTRY_ETFS.values()))`.
- `goat/monitor.py`: `render_industry_ranking_report(result)` — header/disclaimer lines
  matching `render_sector_ranking_report`'s tone; a "Top 5 Rising" and "Bottom 5 Falling"
  headline table (from the top/bottom of `result["ranking"]`), then a "Full Ranking"
  section with every covered industry, then a "Not Covered" section listing
  `result["not_covered"]` (count + full names, per Shaun's decision #3 — visible, not
  just a number).
- `goat/monitor.py`: `write_industry_ranking_report(result)` — writes to
  `config.GOAT_INDUSTRY_RANKING_MD_PATH`.

### Phase 3: On-Demand Chart (documentation only — no code)

Per Shaun's confirmed decision #5, this stays purely conversational. Document the recipe
here so a future session (or Shaun asking Claude Code directly) knows the shape without
re-deriving it:

1. Resolve the industry name to its ETF ticker via `GOAT_INDUSTRY_ETFS` (reverse lookup:
   label → ticker).
2. Fetch its history: `price_history.fetch_close_history(ticker, lookback_days)` for
   whatever window is being charted (does not have to match the 126-day ranking window —
   a chart request can ask for any length).
3. Rebase to 100 at the start of the window: `rebased = close / close.iloc[0] * 100`.
4. Render conversationally in the session (matplotlib or any ad hoc method available at
   the time) — same precedent as the one-off LULU chart referenced in
   `investments/goat/HANDOFF.md`. No new CLI command, no new file in this repo.

**No implementation tasks for this phase.**

### Phase 4: Integration — CLI + Monitor Cadence

**Tasks:**
- `goat/main.py`: add `cmd_scan_industries(args)` mirroring `cmd_scan_sectors` (imports
  `run_industry_scan`, `write_industry_ranking_report` from `.monitor`; note this command
  does NOT call `_open_conn()`/need a DB connection at all, unlike `cmd_scan_sectors`).
  Register `subparsers.add_parser("scan-industries", help="On-demand industry rotation
  ranking (also runs daily as part of monitor)")` and add to the `dispatch` dict.
- `goat/main.py`: `cmd_monitor()` — add the `run_industry_scan()` +
  `write_industry_ranking_report()` calls alongside the existing sector scan calls, so
  industry ranking refreshes daily on the same cadence as sector ranking (per the
  handoff's "Cadence: daily, same as Goat Monitor's existing sector scan" — this reuses
  the existing `second-brain-goat-monitor.timer`, no new systemd unit needed).
- `investments/TOOLS.md`: add a `scan-industries` row to the "Manual / on-demand only"
  table (mirror the `scan-sectors` row), and update the Goat Monitor row's "Output"
  column to mention `industry-ranking.md`.
- `investments/goat/HANDOFF.md`: append a status-line note when this ships, matching the
  existing convention for every prior Goat feature.

---

## STEP-BY-STEP TASKS

### CREATE `investments/goat/goat/industry_rotation.py`
- **IMPLEMENT**: `fetch_all_industry_closes() -> dict[str, pd.Series | None]` and
  `rank_industries(closes: dict) -> list[dict[str, Any]]`.
- **PATTERN**: `investments/goat/goat/sector_rotation.py:17-50` — port these two
  functions near-verbatim, swap `GOAT_SECTOR_ETFS`/`GOAT_SECTOR_HISTORY_LOOKBACK_DAYS`/
  `GOAT_SECTOR_RANK_WINDOW_TRADING_DAYS` for the `GOAT_INDUSTRY_*` equivalents, rename the
  `sector_label` key to `industry_label` throughout (row dicts, function params) for
  clarity in the new module — do not silently keep the old key name from a copy-paste.
- **IMPORTS**: `from . import config, price_history` (same as `sector_rotation.py`).
- **GOTCHA**: do not port `check_sector_breakout` — no breakout signal in this feature's
  scope.
- **VALIDATE**: `uv run --directory investments/goat python -m pytest goat/tests/test_industry_rotation.py -q`

### UPDATE `investments/goat/goat/config.py`
- **IMPLEMENT**: add `GOAT_FINVIZ_INDUSTRIES`, `GOAT_INDUSTRY_ETFS`,
  `GOAT_INDUSTRY_HISTORY_LOOKBACK_DAYS`, `GOAT_INDUSTRY_RANK_WINDOW_TRADING_DAYS`,
  `GOAT_INDUSTRY_RANKING_MD_PATH` per Phase 1 above and the sourced tables in this plan.
- **PATTERN**: `investments/goat/goat/config.py:43-91` (GOAT_SECTOR_* block) for naming,
  comment density, and placement (add the new block immediately after the sector block,
  keep the file's existing top-to-bottom chronological-by-feature ordering).
- **GOTCHA**: `GOAT_INDUSTRY_ETFS` is `dict[ticker, label]` — every key (ticker) must be
  unique. Do NOT add the same ticker under two different labels (see "Gotcha" note in the
  Industry ETF Universe section above); a duplicate key silently overwrites, no
  `KeyError`, no test failure unless a test specifically counts dict length.
- **VALIDATE**: `uv run --directory investments/goat python -c "from goat import config; assert len(config.GOAT_INDUSTRY_ETFS) == len(set(config.GOAT_INDUSTRY_ETFS.keys())); print(len(config.GOAT_INDUSTRY_ETFS), 'tickers,', len(config.GOAT_FINVIZ_INDUSTRIES), 'total industries')"`

### UPDATE `investments/goat/goat/monitor.py`
- **IMPLEMENT**: `run_industry_scan()`, `render_industry_ranking_report(result)`,
  `write_industry_ranking_report(result)` per Phase 2 above.
- **PATTERN**: `investments/goat/goat/monitor.py:227-272` (`run_sector_scan`,
  `render_sector_ranking_report`, `write_sector_ranking_report`) — mirror structure and
  the "Advisor notes only" disclaimer line. `run_industry_scan()` takes no `conn` arg
  (contrast with `run_sector_scan(conn)`) since there is no candidate staging.
- **IMPORTS**: `from . import industry_rotation` alongside the existing `sector_rotation`
  import at the top of `monitor.py`.
- **GOTCHA**: `render_industry_ranking_report` must render three sections in order — Top
  5 / Bottom 5 headline, full ranked table, "Not Covered" list — per Shaun's confirmed
  decision #4 (full list, not just top/bottom 5) and #3 (visible gap note, not silent).
- **VALIDATE**: `uv run --directory investments/goat python -m pytest goat/tests/test_monitor.py -q -k industry`

### UPDATE `investments/goat/goat/tests/conftest.py`
- **IMPLEMENT**: add `monkeypatch.setattr(goat_config, "GOAT_INDUSTRY_RANKING_MD_PATH", tmp_path / "industry-ranking.md")` inside `_isolate_goat_report_path`.
- **PATTERN**: `investments/goat/goat/tests/conftest.py:29-44` — same fixture, same
  pattern as the other 4 report-path monkeypatches already there.
- **GOTCHA**: skipping this means any test that calls `write_industry_ranking_report`
  writes into the real `investments/goat/industry-ranking.md` during `pytest`, polluting
  the working tree — this is exactly what the existing fixture exists to prevent for
  every other Goat report.
- **VALIDATE**: run the full goat test suite (Level 2 below) and confirm `git status`
  shows no unexpected modification to `investments/goat/industry-ranking.md` after the
  run.

### CREATE `investments/goat/goat/tests/test_industry_rotation.py`
- **IMPLEMENT**: port `test_sector_rotation.py`'s ranking tests (missing-data-sorts-last,
  ordering by window return) for `rank_industries`. No breakout tests (none exist for
  this feature).
- **PATTERN**: `investments/goat/goat/tests/test_sector_rotation.py:1-74` — reuse
  `_dates`/`_flat_then_move` helpers, adapt
  `test_rank_sectors_orders_by_window_return_missing_data_sorts_last` directly (swap in
  `GOAT_INDUSTRY_ETFS` monkeypatching instead of `GOAT_SECTOR_ETFS`).
- **VALIDATE**: `uv run --directory investments/goat python -m pytest goat/tests/test_industry_rotation.py -q`

### UPDATE `investments/goat/goat/tests/test_monitor.py`
- **IMPLEMENT**: tests for `run_industry_scan()` (stub `fetch_all_industry_closes` via
  monkeypatch, same style as `test_run_monitor_creates_new_alert_for_first_flag` stubs
  `fetch_close_history`), `render_industry_ranking_report()` (assert Top 5/Bottom
  5/full-list/not-covered sections all present), `write_industry_ranking_report()`
  (assert it writes to the monkeypatched `GOAT_INDUSTRY_RANKING_MD_PATH`, not the real
  file).
- **PATTERN**: `investments/goat/goat/tests/test_monitor.py:1-60` and the existing
  `test_run_sector_scan*`/`test_render_sector_ranking_report*`/
  `test_write_sector_ranking_report*` tests further down the same file (read the whole
  file, not just the excerpt above, before writing these).
- **VALIDATE**: `uv run --directory investments/goat python -m pytest goat/tests/test_monitor.py -q`

### UPDATE `investments/goat/goat/main.py`
- **IMPLEMENT**: `cmd_scan_industries(args)`, new `scan-industries` subparser entry, add
  to `dispatch` dict; update `cmd_monitor()` to also call `run_industry_scan()` +
  `write_industry_ranking_report()`.
- **PATTERN**: `investments/goat/goat/main.py:62-80` (`cmd_scan_sectors`) for the
  standalone command; `main.py:22-46` (`cmd_monitor`) for the integration point.
- **GOTCHA**: `cmd_scan_industries` does not call `_open_conn()` at all (no DB needed) —
  don't copy that line from `cmd_scan_sectors` reflexively.
- **VALIDATE**: `uv run --directory investments/goat python -m goat.main scan-industries --help`
  (argparse smoke test only — do NOT run this against the real DB locally, see Level 4).

### UPDATE `investments/TOOLS.md`
- **IMPLEMENT**: add a `scan-industries` row to the "Manual / on-demand only" table
  (mirror the existing `scan-sectors` row's format exactly); update the Goat Monitor row's
  Output column to also list `industry-ranking.md`.
- **PATTERN**: `investments/TOOLS.md:33` (Goat Monitor row) and `:55` (scan-sectors row).
- **VALIDATE**: manual read-through — no automated check for a docs file.

### UPDATE `investments/goat/HANDOFF.md`
- **IMPLEMENT**: append a status note to the top status line, same convention as every
  prior phase entry in that file (see line 3 for the existing chain of "Phase 1 complete
  ... Phase 2 complete ... Phase 3 complete ..." status entries).
- **PATTERN**: `investments/goat/HANDOFF.md:3`.
- **VALIDATE**: manual read-through.

---

## TESTING STRATEGY

### Unit Tests
`rank_industries` ordering (rising sorts first, missing data sorts last — same invariant
as `rank_sectors`), `run_industry_scan`'s `not_covered` computation (set difference is
correct, sorted, matches expected count), `render_industry_ranking_report`'s three
required sections all present with correct content.

### Integration Tests
`run_industry_scan()` → `render_industry_ranking_report()` → `write_industry_ranking_report()`
round-trip against the monkeypatched report path (mirrors the existing
`test_write_sector_ranking_report_writes_to_configured_path`-style test if one exists in
`test_monitor.py` — check before writing a new one).

### Edge Cases
- All 39 tickers return `None` (simulated yfinance outage) — report must still render
  with an all-empty ranking table and the same "Not Covered" list, not crash.
- `GOAT_INDUSTRY_ETFS` dict-key-uniqueness regression (the Phase-1 validate command above
  doubles as a permanent guard — consider adding it as an actual test, not just a
  one-time manual check, e.g. `test_config.py::test_goat_industry_etfs_keys_are_unique`
  — trivially true for a Python dict literal, but protects against a future edit
  reintroducing a duplicate key by copy-paste).

---

## VALIDATION COMMANDS

### Level 1: Syntax & Style
```powershell
uv run --directory investments/goat ruff check goat/
uv run --directory investments/goat mypy goat/
```

### Level 2: Unit Tests
```powershell
uv run --directory investments/goat python -m pytest -q
```

### Level 3: Integration Tests
Covered by Level 2 (this codebase does not separate unit/integration test files for
Goat — see `pyproject.toml`'s single `testpaths = ["goat/tests"]`).

### Level 4: Manual Validation (VPS only — per TOOLS.md, never run locally against the real DB)
```powershell
.\scripts\invoke_investments.ps1 -Package goat -Command "scan-industries"
```
Then read `investments/goat/industry-ranking.md` (pulled to this machine via the
existing vault-sync flow) and manually sanity-check:
- Top 5 / Bottom 5 headline matches the full table's first/last 5 rows.
- "Not Covered" section lists a plausible ~104 industries (no `GOAT_INDUSTRY_ETFS`-covered
  industry appears in it).
- No Python traceback in the VPS command output; any individual ticker fetch failures
  print as `[goat-industry-scan] error fetching {ticker}: {e}` and that industry's row
  shows `—`/`None`, not a crash.
- Run `.\scripts\invoke_investments.ps1 -Package goat -Command "monitor"` once afterward
  and confirm `industry-ranking.md` also refreshes as part of that (Phase 4's cadence
  integration).

### Level 5: Additional Validation
None required — no MCP servers or extra CLI tools apply to this feature.

---

## ACCEPTANCE CRITERIA

- [ ] `GOAT_INDUSTRY_ETFS` (39 tickers) and `GOAT_FINVIZ_INDUSTRIES` (143 names) added to
      `config.py`, matching the sourced tables in this plan exactly.
- [ ] `industry_rotation.py` ranks industries by 6-month (126-trading-day) price return,
      missing data sorts last — mirrors `sector_rotation.rank_sectors`'s tested behavior.
- [ ] `industry-ranking.md` shows Top 5 / Bottom 5 headline, full ranked list of all 39
      covered industries, and an explicit "Not Covered" list of the other ~104.
- [ ] No new DB table, no candidate staging, no WhatsApp notification added — confirmed
      by code review against "Explicitly Deferred" below.
- [ ] `scan-industries` CLI command works standalone; `monitor` also refreshes
      `industry-ranking.md` on its existing daily cadence (no new systemd timer).
- [ ] All validation commands (Levels 1-4) pass with zero errors.
- [ ] `investments/TOOLS.md` and `investments/goat/HANDOFF.md` updated.
- [ ] No trade-action language anywhere in the new report (SOUL.md compliance, same as
      every other Goat report).

## COMPLETION CHECKLIST

- [ ] All tasks completed in order
- [ ] Each task's validation command passed immediately after that task
- [ ] Full goat test suite passes (`uv run --directory investments/goat python -m pytest -q`)
- [ ] ruff + mypy clean
- [ ] Level 4 manual VPS validation run, `industry-ranking.md` inspected by eye
- [ ] Acceptance criteria all met
- [ ] `TOOLS.md` / `HANDOFF.md` updated

---

## Explicitly Deferred (do not build as part of this plan)

- Constituent-stock aggregation for full industry coverage (ETFs only, per Shaun's
  original 2026-08-23 scoping call in the handoff).
- Real $ fund-flow data — price performance stays the proxy, same as sector rotation.
- Any dashboard/interactive UI, or a CLI chart command — chart stays purely
  conversational (Phase 3 above is documentation only).
- Any buy/sell opportunity-style verdict, breakout check, candidate staging, or
  WhatsApp notification layered on top of the ranking — this plan is the ranking report
  only. Worth asking Shaun later whether an industry-level breakout signal (mirroring
  `check_sector_breakout`) is wanted too, but it is not scoped here.
- Own daily-snapshot DB table — live re-fetch only, per confirmed decision #2.

## NOTES

- The industry ETF universe (39/143 covered) is a real, sourced starting point, not a
  final list — Shaun may want to revisit coverage later (e.g. if a niche industry he
  cares about turns out to have an ETF this session's research missed). Adding one is a
  one-line `GOAT_INDUSTRY_ETFS` edit plus a `GOAT_FINVIZ_INDUSTRIES` cross-check, not a
  re-plan.
- `GOAT_BANNED_TICKERS` (currently just `XLI`, for RTX/defense exposure) is NOT applied
  to `GOAT_INDUSTRY_ETFS` — there is no candidate-staging/promotion path for this
  feature to gate, so the concept doesn't transfer. If a future breakout-signal follow-up
  is ever built on top of this ranking, revisit whether `ITA` (Aerospace & Defense) needs
  the same ban ITA's sector-level sibling XLI already has.

## Confidence Score

**8/10** for one-pass implementation success. The core ranking logic is a near-exact
mirror of already-shipped, already-tested code (`sector_rotation.py`), which is the main
source of confidence. Points held back for: (1) the 39-ticker ETF universe, while
genuinely researched this session, includes a few medium-confidence picks (INDS, EVX)
that could turn out to be wrong on live yfinance data — Task 6's edge-case test and Level
4's manual VPS run are the safety net, not a guarantee; (2) `render_industry_ranking_report`'s
three-section format has no existing template to copy verbatim (sector's report only has
one section), so the execution agent has some real design latitude there — reviewed
against the acceptance criteria before calling it done.
