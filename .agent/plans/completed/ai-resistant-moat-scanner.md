# Feature: AI-Resistant Moat Scanner

The following plan should be complete, but it is important that you validate documentation and
codebase patterns and task sanity before you start implementing. Pay special attention to naming of
existing utils, types and models. Import from the right files.

Source handoff: `investments/ai-resistant-moat-scanner-handoff.md` (read it first — this plan
resolves its 10 open questions with Shaun's answers below).

## Feature Description

A new `investments/` workspace tool that ranks US-listed public companies by how **AI-durable their
embedded-software moat** is — the Salesforce property: "so engrained in the customer's business' DNA
that the ROI of building an AI replacement doesn't make sense." Daily VPS systemd scan, advisor-notes
only (no auto-buy, no auto-watchlist-add). Fresh high-scoring names are staged into a pending-review
file for explicit promote/dismiss, and a WhatsApp alert fires when a new one is staged.

The score is a blended 0–100 "embedded moat / AI-resistance" number, half quantitative
(yfinance + light SEC-filing extraction, no judgement) and half qualitative (an LLM scoring a fixed
6-part rubric against the latest 10-K's Business + Risk Factors sections).

## User Story

As Shaun (a concentrated-value investor building conviction one name at a time)
I want a daily-refreshed ranked list of public companies whose software is embedded deeply enough in
their customers' operations to survive the AI wave, plus a push alert when a strong new one appears
So that I can find durable-moat compounders to run through my-trader Find / briefs-finance for
valuation, instead of manually hunting for "the next Salesforce."

## Problem Statement

There is no tool in the repo that ranks companies by moat *durability against AI disruption*. my-trader
Find grades a single ticker on request against value criteria; briefs-finance scores Briefs-Finance
report picks; goat is momentum/rotation. None of them screen the whole market for the specific
switching-cost / system-of-record / ecosystem-lock-in pattern Shaun is after, and none of them read
what the company itself discloses about that lock-in.

## Solution Statement

A new uv-workspace member `ai-resistant-moat-scanner` (module `ai_resistant_moat_scanner`) that:

1. Builds a universe: a Finviz coarse screen across software / vertical-software sectors (client-side
   filtered to a target-industry allow-list) + a curated seed list of known embedded-moat names.
2. Each daily run scores **1/N of the universe (rotating by date) + all seed names + all
   currently-staged names** — caching the expensive per-filing LLM work per `accession_number` so
   most days re-read cache.
3. **Quant half** (`quant.py`): pure function over `market_data.TickerData` + disclosed extraction
   fields → 0–100.
4. **Qualitative half** (`qualitative.py`): fetch latest 10-K via `mytrader.sec_filings`, extract
   Item 1 / 1A / 7, one LLM extraction call (nullable structured JSON: NRR / RPO / recurring-rev /
   customer count / churn) + one LLM rubric call (6 sub-scores 0–10 + anti-signals + one-line
   thesis) → 0–100. Cached per `(ticker, accession_number)`.
5. **Blend** (`scoring.py`): `moat_score = 0.5*quant + 0.5*qualitative`.
6. Stage fresh names scoring `>= 80` into `moat_pending_candidates`, skipping held / watchlisted /
   already-staged tickers. Fire a WhatsApp + toast alert titled **"AI-Resistant Moat Alert"**.
7. Write two Markdown files: `moat-scan-report.md` (full ranked table) and
   `moat-candidates-pending-review.md` (fresh high-scorers, goat-heartbeat two-file pattern).
8. `promote-candidate` / `dismiss-candidate` CLI subcommands (promote writes into my-trader's
   watchlist — the one deliberate cross-package write, exactly as goat does it).

### Shaun's answers to the handoff's open questions (2026-09-09)

1. **Package placement** — new workspace member, its own `moat_pending_candidates` table + its own
   promote/dismiss. Confirmed.
2. **Universe** — US-listed only for v1 (the SEC 10-K read *is* the qualitative half; a quant-only
   non-US score is too weak to stage). Finviz sector screens + curated industry allow-list +
   curated seed list, `market cap ≥ $2B`, `gross margin ≥ 60%` coarse prefilter. ASX noted as a
   follow-up, not built. Confirmed.
3. **NRR / RPO / churn extraction** — yes, a targeted LLM extraction pass returning nullable JSON,
   "not disclosed → neutral, never guessed." Nothing for Shaun to do; it is automatic.
4. **Score blend + cutoff** — 50/50 quant vs qualitative; stage only `>= 80` to start, tune down
   after the first live run (same discipline as cash-value's 0.80 → 0.50). Both are `config.py`
   constants.
5. **Output shape** — two files (full report + staging file). Staging file goes in TOOLS.md
   "Daily Read"; the full report is in the Automated + Manual tables only. Confirmed.
6. **Cadence** — daily systemd timer at **23:30 UTC** (after the 22:45 Goat Heartbeat so they don't
   contend for yfinance). 1/5 of the universe per calendar day (rotating), plus seed + staged names
   every day. `Persistent=true`. Confirmed.
7. **Notification** — WhatsApp + toast on a fresh staged name, silent on zero-candidate days. Both
   channels titled **"AI-Resistant Moat Alert"** so Shaun knows which module sent it.
8. **Ethical filter** — run the shared `scripts.ethical_filter.check_ticker`: hard-drop
   `DEFENSE_TICKERS`, `REVIEW:`-tag `BA`/`PLTR` but keep them in the report. Same as cash-value.
   Confirmed.
9. (handoff #10) **"AI-resistant is a moving target"** — dated note in the module docstring +
   report header + TOOLS.md that the rubric encodes a 2026 view and should be revisited.
10. **No dedicated skill** for v1 — documented via `investments/TOOLS.md` and the existing
    `investments` skill, like cash-value and superinvestor-filings.

## Feature Metadata

**Feature Type**: New Capability
**Estimated Complexity**: High (large reuse surface, two LLM passes, new workspace member + systemd)
**Primary Systems Affected**: new package `investments/ai-resistant-moat-scanner/`; small
backward-compatible change to `investments/my-trader/mytrader/finviz_screener.py` (optional `filters`
param) and one new helper in `investments/my-trader/mytrader/market_data.py`; one public wrapper in
`investments/my-trader/mytrader/sec_filings.py`; `investments/pyproject.toml`; `scripts/systemd/`;
`scripts/invoke_investments.ps1`; `investments/TOOLS.md`; `.gitignore`.
**Dependencies**: `my-trader` (workspace), `yfinance`, `pandas`, `requests`, `beautifulsoup4`,
`sdk_compat` (via `.claude/scripts` sys.path insert, existing pattern).

---

## CONTEXT REFERENCES

### Relevant Codebase Files — YOU MUST READ THESE BEFORE IMPLEMENTING

**Closest structural template — copy this shape:**
- `investments/goat/goat/heartbeat_scan.py` (whole file) — the exact orchestrator shape:
  filter a universe → per-ticker check → attach context → stage fresh finds into a pending table
  with a `source` value → skip held / watchlisted / already-staged → render a full report + a
  pending-review staging file. `run_heartbeat_scan()` / `render_heartbeat_candidates_report()` /
  `write_heartbeat_candidates_report()`.
- `investments/goat/goat/main.py` (whole file) — CLI dispatch, `_open_conn()` (lines 8-20),
  `cmd_scan_heartbeat` (100-118), `cmd_promote_candidate` (190-223, incl. the "deliberate
  exception to never-write-my-trader's-tables" comment), `cmd_dismiss_candidate` (225-233),
  `main()` subparser wiring (235-296).
- `investments/goat/goat/db.py` (whole file) — `init_goat_tables` executescript + idempotent
  ALTER-TABLE migration hook (15-115); `goat_pending_candidates` schema (28-35);
  `get_goat_pending_candidate` / `get_all_goat_pending_candidates` /
  `insert_goat_pending_candidate` (INSERT OR IGNORE + `_now()`) / `delete_goat_pending_candidate`
  (157-195). Mirror this table + CRUD naming exactly for `moat_pending_candidates`.
- `investments/superinvestor-filings/superinvestor_filings/` — newest package, dir-name =
  module-name convention:
  - `config.py` — path constants re-exporting `DB_PATH` from `scripts.config` (line 9),
    `PKG_DIR` derivation (11), data-only tracked config, lookback + seed watermark constants.
  - `db.py` — `superinvestor_filings_seen` table + `init_*` + INSERT-OR-IGNORE `rowcount == 1`
    dedup idiom + empty `_MIGRATIONS` hook (the "keep the pattern ready" comment).
  - `main.py` — `_open_conn()` (21-33): `init_db(DB_PATH)` → `get_connection(DB_PATH)` →
    `init_mytrader_tables(conn)` → `init_<pkg>_tables(conn)`.
  - `notify.py` (whole file) — `send_digest()`: `sys.path` insert to `.claude/scripts`, import
    `send_toast_notification` / `send_whatsapp_notification`, group by key, no-op on empty list.
    **This is the notify.py to mirror.**
  - `report.py` (whole file) — `render_report()` / `write_report()` copy style: "What this is:"
    opener, "## Run: <date>" heading, `_now_sydney_str()` footer, table header/row helpers.
  - `edgar_monitor.py` — `scan_edgar()` (206-247): the `sec_filings.get_cik(conn, "AAPL")`
    CIK-map warm-up (209-212), `first_seed` watermark gate, per-CIK
    `fetch_filing_index` → `recent_filings_of_types` loop, `time.sleep(delay)` pacing.
  - `pyproject.toml` (whole file) — exact package pyproject to copy (add `yfinance` + `pandas`).
  - `tests/conftest.py` (whole file) — tmp_path DB, `_isolate_report_path` autouse,
    `_no_real_network` autouse stubbing every `mytrader.sec_filings.*` entrypoint.
  - `DEPLOY.md` (whole file) — the deploy-doc shape + the chained `ssh … && git pull && uv sync
    … && sudo cp … && systemctl` block (memory: chain blocked/sudo commands into one pasteable
    `&&` block for Shaun).

**Closest behavioural analogue — a daily VPS universe scan:**
- `investments/my-trader/mytrader/cash_value_scan.py` (whole file) — `compute_cash_value_metrics`
  (44-90, pure function returning `None` when key fields absent — mirror this for `quant.py`);
  `_passes` (93-99); `_enrich_universe` (147-212, per-ticker try/except so one bad ticker can't
  sink the run, `ethical_check` call at 168-170, `time.sleep(CASH_VALUE_FETCH_DELAY_SECONDS)` at
  173); `run_scan` (217-254, `cached_session()` context at 228, STALE / DEGRADED early returns);
  `render_report` (306-356); `_write_banner` (362-379, non-stacking banner) / `write_report`
  (382-392). The "Cash-Value Scan — how it works + tuning" section of `investments/TOOLS.md`
  (lines 82-146) is the model for the TOOLS.md section this feature must add.
- `investments/my-trader/mytrader/config.py` — the whole "Cash-Value Scanner" block (lines
  561-638): `CASH_VALUE_*` and `FINVIZ_*` constants, the `FINVIZ_SCREENER_FILTERS` string, the
  `ASX200_*` block. `SEC_*` block (207-247): `SEC_USER_AGENT` (do NOT change — legally required),
  `SEC_FILING_TYPES`, `SEC_REQUEST_DELAY_SECONDS`, `SEC_FILING_SUMMARY_MODEL = "sonnet"`,
  `SEC_MAX_SECTION_CHARS = 6000`, `SEC_MAX_RAW_DOCUMENT_BYTES`. `DEBT_TO_EQUITY_FLAG`,
  `OPPORTUNITY_SCORE_FLAG = 70`.

**SEC filing fetch + extraction (≈80% of the qualitative half already exists):**
- `investments/my-trader/mytrader/sec_filings.py` (whole file) — `get_cik` (76-79),
  `fetch_filing_index` (83-91), `latest_filing_entry(index, "10-K")` (94-106),
  `fetch_filing_document` (109-120), `strip_html` (294-298), `_split_by_item` (301-316 — the
  "keep LAST occurrence, not first" TOC-vs-body gotcha), `_extract_10k_sections` (334-345 —
  returns `{"business": Item 1, "risk_factors": Item 1A, "mda": Item 7, "financial_statements":
  Item 8}`), `_extract_sections(html, "10-K")` (411-419), `_summarize_sections` /
  `_SUMMARY_PROMPT` (423-450 — the `run_text` + `ClaudeAgentOptions(allowed_tools=[], model=…)`
  call pattern), `get_filing_summaries_for_ticker` orchestrator (455-491 — the
  cache-hit-on-accession-match pattern at 468-471).
- `investments/my-trader/mytrader/checks/principles_fit.py` (whole file) — the pattern for an LLM
  scoring a fixed rubric against filing text: `_build_thesis` (96-177), `check` (180-247 — the
  `sorted(PRINCIPLES_DIR.glob("*.md"))` loop calling `score_thesis_against_principle`, the
  `average >= config.OPPORTUNITY_SCORE_FLAG` verdict at 235). The module docstring documents the
  "never cache the live-stats thesis, DO cache the filing-derived sub-scores per accession"
  distinction — the moat scanner's caching follows the second half of that.
- `investments/briefs-finance/scripts/score.py` — `PRINCIPLES_PROMPT` (19-30),
  `_parse_json` (33-40 — strips ` ```json ` / ` ``` ` fences; copy this verbatim into a module
  helper), `score_thesis_against_principle` (43-60 — `asyncio.run(run_text(prompt=…,
  options=ClaudeAgentOptions(allowed_tools=[], model="haiku")))` → `_parse_json` →
  `max(0, min(100, int(...)))` clamp → `except Exception: return 50, "Could not score"`).

**Finviz screen + universe caching:**
- `investments/my-trader/mytrader/finviz_screener.py` (whole file) — `_fetch_page(row_offset)`
  (51-67, `params` dict with `v`/`f`/`o`/`r`), `_descramble_ticker` (73-78, first-char-doubled
  watermark), `_rows_from_table` (91-115 — extracts `ticker`/`company`/`sector`/`industry`/
  `country`/`market_cap_text`/`price_text` via `_EXPECTED_COLUMNS`), `_parse_page` (118-144 —
  `None` = not a real screener page, `[]` = valid page no rows), `fetch_screener_universe`
  (147-178 — paginate, first-page failure → `None`, later-page failure → return partial).
- `investments/goat/goat/sp500_universe.py` (whole file) — scrape → cache-in-DB →
  stale-fallback pattern: `get_or_refresh_sp500_constituents` (61-80). Use this shape if you cache
  the Finviz universe in-DB (recommended — see Task 6).
- `investments/goat/goat/config.py` — `GOAT_SP500_CACHE_TTL_DAYS = 7` (309-312), the
  `GOAT_FINVIZ_INDUSTRIES` verbatim taxonomy list (98-148) and `GOAT_INDUSTRY_ETFS` (150-180) —
  the canonical Finviz industry-label strings; use the exact spellings from this list for the
  target-industry allow-list.

**Ethical filter:**
- `investments/briefs-finance/scripts/ethical_filter.py` (whole file) — `check_ticker(ticker)
  -> (excluded: bool, reason: str | None)`. `.split(".")[0]` strips `.AX` etc.
- `investments/briefs-finance/scripts/config.py` — `DEFENSE_TICKERS` (22-25),
  `DEFENSE_REVIEW_TICKERS = {"BA", "PLTR"}` (26), `PRINCIPLES_DIR` (18).

**Notifications + DB + shared plumbing:**
- `.claude/scripts/notifications.py` (whole file) — `send_toast_notification(title, message)`,
  `send_whatsapp_notification(message, chat_id="")`. Both title-string + message-string.
- `investments/goat/goat/monitor.py` `maybe_notify` (lines 155-206) — the `new_candidates` list
  shape (`{"ticker", "sector_label", "detail"}`), `candidate_label` param, toast+WhatsApp both,
  silent when `not n_alerts and not candidates`.
- `investments/briefs-finance/scripts/db.py` — `get_connection(db_path=DB_PATH)` (13),
  `init_db(db_path=DB_PATH)` (21). Package name is `scripts` in the workspace.
- `investments/my-trader/mytrader/db.py` — `get_holding_row(conn, ticker, bucket=None)` (163),
  `get_watchlist_row(conn, ticker, bucket=None)` (173), `get_all_holdings(conn)` (183),
  `get_all_watchlist(conn)` (187), `get_sync_watermark` / `set_sync_watermark` (415-420),
  `upsert_watchlist_row(conn, *, ticker, name, asset_type, bucket, status="raw", notes=None,
  source="manual", …)` (232-243), `init_mytrader_tables`. `get_cik_for_ticker` (461),
  `upsert_cik_map_bulk` (450).
- `investments/my-trader/mytrader/snapshot.py` — `regenerate_all(conn)` (181-184) — call after
  a promote so `watchlist.md` reflects the new row (goat does this).
- `investments/my-trader/mytrader/market_data.py` (whole file) — `TickerData` dataclass (12-18),
  `fetch_ticker_data(ticker)` (71-83, `.AX` fallback), `cached_session()` contextmanager (24-37),
  `fetch_cash_flow_statement(ticker)` (160-192 — the exact try/except/return-None shape + `t.cashflow`
  usage to mirror for the new `fetch_income_statement_history` helper),
  `fetch_balance_sheet_financials` (114-157).
- `investments/my-trader/mytrader/checks/__init__.py` — `CheckResult` dataclass
  (`name` / `verdict` in {"ok","flag","info","unknown"} / `detail` / `data`). Reuse it for the
  qualitative check return, mirroring `goat/goat/heartbeat.py:38` `from mytrader.checks import
  CheckResult`.

**Test patterns:**
- `investments/goat/goat/tests/conftest.py` (whole file) — tmp_path DB + `_isolate_*_report_path`
  autouse monkeypatch + `_no_real_*_fetch` autouse network stub.
- `investments/my-trader/mytrader/tests/conftest.py` (whole file) — the definitive collection of
  autouse network/LLM stubs and *why each exists* (real-file-corruption incidents). Note
  `_no_real_finviz_fetch` (171-176) stubs `fetch_screener_universe` as `lambda: None` (no args) —
  keep the optional `filters` param defaulted so this stub still binds.
- `investments/my-trader/mytrader/tests/test_sec_filings.py` (lines 1-70) — fixture-file loading
  (`_FIXTURES = pathlib.Path(__file__).parent / "fixtures"`), `_split_by_item` / `_extract_sections`
  tests, restoring the real fn saved at import time.
- `investments/briefs-finance/scripts/tests/test_score.py` (whole file) — `patch("scripts.score.
  get_principles_scores", return_value=[…])` — patch the scoring fn, not the LLM, for orchestrator
  tests.
- `investments/my-trader/mytrader/tests/fixtures/sec_10k_sample.html` — copy this into the new
  package's fixtures as `sec_10k_moat_sample.html`.

**Deployment:**
- `scripts/systemd/second-brain-goat-heartbeat-scan.service` + `.timer` — exact unit-file
  templates. `.service`: `Type=oneshot`, `User=secondbrain`,
  `WorkingDirectory=/home/secondbrain/second-brain/investments/<pkg-dir>`,
  `ExecStart=/home/secondbrain/second-brain/investments/.venv/bin/python -m <module>.main scan`,
  `StandardOutput`/`StandardError=append:.../<pkg-dir>/<name>_runs.log`. `.timer`:
  `OnCalendar=*-*-* HH:MM:00 UTC`, `Persistent=true`, `[Install] WantedBy=timers.target`.
- `scripts/invoke_investments.ps1` — `[ValidateSet(...)]` (line 24) + `$PACKAGES` hashtable
  (34-40): add `"ai-resistant-moat-scanner" = @{ Dir = "ai-resistant-moat-scanner"; Module =
  "ai_resistant_moat_scanner.main" }`.
- `investments/pyproject.toml` — `[tool.uv.workspace] members` (line 2): append
  `"ai-resistant-moat-scanner"`.
- `.gitignore` — add `investments/ai-resistant-moat-scanner/moat_scan_runs.log` (mirrors
  `investments/my-trader/monitor_runs.log` at line 18). The two `.md` reports ARE committed
  (goat's are).

### New Files to Create

```
investments/ai-resistant-moat-scanner/
  pyproject.toml
  DEPLOY.md
  README.md                                      (short — what/when/where-it-writes)
  ai_resistant_moat_scanner/
    __init__.py
    config.py            paths, universe (sector screens + industry allow-list + seed list),
                         thresholds, quant weights, blend weight, cache/pacing knobs, RUBRIC_VERSION
    db.py                moat_pending_candidates + moat_qualitative_cache tables + CRUD
    universe.py          Finviz sector screens -> industry-filtered rows -> merge seed list ->
                         DB cache w/ stale fallback; date-rotating slice selection
    quant.py             compute_quant_metrics(data, extraction) -> dict | None; quant_score 0-100
    filings_extract.py   fetch latest 10-K, extract Item 1/1A/7, LLM structured extraction
                         (nullable JSON) -> dict
    qualitative.py       get_qualitative(conn, ticker) -> dict | None  (cache-aware: rubric LLM
                         call + extraction, keyed on accession_number)
    scoring.py           blend_score(quant_score, qualitative_score) -> float; row assembly
    scan.py              run_scan(conn) -> dict  (orchestrator)
    report.py            render_report / render_candidates_report / write_* + non-stacking banner
    notify.py            maybe_notify(new_candidates) -> None  ("AI-Resistant Moat Alert")
    main.py              CLI: scan / promote-candidate / dismiss-candidate
    tests/
      __init__.py
      conftest.py
      fixtures/
        finviz_moat_screener_page.html            (saved from one real live fetch during build)
        sec_10k_moat_sample.html                  (copy of mytrader's sec_10k_sample.html)
      test_config.py
      test_db.py
      test_universe.py
      test_quant.py
      test_filings_extract.py
      test_qualitative.py
      test_scoring.py
      test_scan.py
      test_report.py
      test_notify.py
scripts/systemd/second-brain-ai-moat-scan.service
scripts/systemd/second-brain-ai-moat-scan.timer
```

### Relevant Documentation

- SEC EDGAR fair-access policy — https://www.sec.gov/os/webmaster-faq#developers
  - Why: `SEC_USER_AGENT` must stay a descriptive contact string; stay under ~10 req/s. Already
    handled by reusing `mytrader.sec_filings` + `SEC_REQUEST_DELAY_SECONDS`. Do not add a bare UA.
- SEC `data.sec.gov/submissions/CIK{10-digit}.json` shape — used via
  `sec_filings.fetch_filing_index` / `recent_filings_of_types`; you do not call it directly.
- Finviz screener filter tokens — https://finviz.com/screener.ashx (inspect the `f=` param the
  site builds when you tick filters in a browser).
  - Why: the exact tokens for "market cap $2B+", "gross margin > 60%", and each target sector MUST
    be verified live during Task 6 (Finviz changes token names; `cash-value-scanner.md` hit this
    exact class of surprise — the ticker-watermark bug — mid-execution). Best guesses in Task 6.
- yfinance `Ticker.info` / `Ticker.income_stmt` / `Ticker.cashflow` — fields used:
  `grossMargins`, `operatingMargins`, `freeCashflow`, `totalRevenue`, `revenueGrowth`,
  `marketCap`, `sector`, `financialCurrency`. `income_stmt` "Total Revenue" row for the durability
  metric (annual, ~4 cols — this is the known depth limit; pre-2021 history is usually absent, so
  the durability sub-metric degrades to neutral when < 3 years are available).

### Patterns to Follow

**Naming:** module dir = importable module name (`ai-resistant-moat-scanner` /
`ai_resistant_moat_scanner`). Config constants `MOAT_*` (mirrors `GOAT_*` / `CASH_VALUE_*`).
Path constants end `_PATH` / `_MD_PATH`. DB fns `init_moat_tables`, `insert_moat_pending_candidate`,
`get_moat_pending_candidate`, `get_all_moat_pending_candidates`, `delete_moat_pending_candidate`,
`get_cached_qualitative`, `upsert_qualitative_cache`.

**Error handling:** every network/LLM boundary returns `None` on any failure, never raises (module
policy — see `sec_filings.py` docstring). Per-ticker work wrapped in `try/except Exception as e:
print(f"[ai-moat-scan] error on {ticker}: {e}")` and `continue` (mirror
`cash_value_scan._enrich_universe:210-211`). A broken LLM call → that half is `None`, the row is
quant-only and **not** stageable — never fabricate a 50 and stage a name on a failed call.

**LLM calls:** `import asyncio`; `sys.path.insert(0, str(_SCRIPTS_DIR))` where
`_SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent.parent / ".claude" / "scripts"`;
`from sdk_compat import ClaudeAgentOptions, run_text`. Call:
`asyncio.run(run_text(prompt=…, options=ClaudeAgentOptions(allowed_tools=[], model=MODEL)))`.
Parse JSON with the copied `_parse_json` (strip fences). Clamp ints to range. `except Exception`
→ return the "failed" sentinel (`None`, not a default score).

**Logging:** `print(f"[ai-moat-scan] …")` prefix (mirrors `[goat-heartbeat-scan]` /
`[cash-value-scan]`). No `logging` module anywhere in `investments/`.

**Report copy:** "What this is:" opener; "Auto-generated … overwritten every run. Advisor notes
only; no trade action is ever suggested here (see SOUL.md)." disclaimer; the dated
rubric-is-a-2026-snapshot caveat; Sydney-time "Last auto-generated:" footer.

**DB:** one shared `investments.db` (VPS-only). `_open_conn()` does `init_db(DB_PATH)` →
`get_connection(DB_PATH)` → `init_mytrader_tables(conn)` → `init_moat_tables(conn)`. INSERT OR
IGNORE + `cur.rowcount == 1` for dedup. Idempotent `try: ALTER TABLE … except
sqlite3.OperationalError: pass` migration hook (empty list, pattern ready).

**Timezone:** report date labels always `datetime.now(ZoneInfo("Australia/Sydney"))` regardless of
host clock (`cash_value_scan._today_sydney`).

**Never** run the package locally with `uv run --directory investments/ai-resistant-moat-scanner
python -m ai_resistant_moat_scanner.main scan` — that creates an empty local `investments.db`. All
real runs go through `scripts/invoke_investments.ps1`. Local `pytest` (tmp_path DB) is fine.

---

## IMPLEMENTATION PLAN

### Phase 1: Foundation — package skeleton, config, DB, my-trader helpers

Create the workspace member, its `config.py` (all knobs), `db.py` (both tables), and the three
small backward-compatible additions to `my-trader`.

### Phase 2: Core — universe, quant half, filings extraction, qualitative half, scoring

Build each scoring component as an independently testable unit with a pure core where possible.

### Phase 3: Integration — orchestrator, report, notify, CLI, promote/dismiss

Wire the components into `run_scan`, the two report files, the alert, and the CLI incl. the
cross-package watchlist write.

### Phase 4: Deployment + docs — systemd, invoke wrapper, pyproject workspace, gitignore, TOOLS.md,
DEPLOY.md, memory update.

---

## STEP-BY-STEP TASKS

Execute in order, top to bottom. Each task ends with a runnable validation command. Run
`uv sync` from `investments/` once after Task 1 so the new member resolves.

### Task 1 — CREATE `investments/ai-resistant-moat-scanner/pyproject.toml` + `__init__.py` + register workspace

- **IMPLEMENT**: Copy `investments/superinvestor-filings/pyproject.toml` verbatim, change
  `name = "ai-resistant-moat-scanner"`, add `"yfinance>=0.2.40"` and `"pandas>=2.0.0"` to
  `dependencies` (keeps `my-trader`, `requests`, `beautifulsoup4`). Set
  `testpaths = ["ai_resistant_moat_scanner/tests"]`, `packages = ["ai_resistant_moat_scanner"]`.
  Create empty `ai_resistant_moat_scanner/__init__.py` and
  `ai_resistant_moat_scanner/tests/__init__.py`.
- **UPDATE** `investments/pyproject.toml`: append `"ai-resistant-moat-scanner"` to
  `[tool.uv.workspace] members`.
- **PATTERN**: `investments/superinvestor-filings/pyproject.toml`; `investments/pyproject.toml:2`.
- **GOTCHA**: `my-trader = { workspace = true }` must stay under `[tool.uv.sources]`.
- **VALIDATE**: `uv sync --directory investments && uv run --directory investments/ai-resistant-moat-scanner python -c "import ai_resistant_moat_scanner; print('ok')"`

### Task 2 — CREATE `ai_resistant_moat_scanner/config.py`

- **IMPLEMENT**: Module docstring incl. a dated line: "The AI-resistance rubric encodes a 2026 view
  of what AI can and cannot cheaply rebuild — revisit it, do not treat it as permanent (same spirit
  as the check-interpretation convention)." Constants:
  - `from scripts.config import DB_PATH  # noqa: F401`
  - `PKG_DIR = Path(__file__).resolve().parent.parent`
  - `MOAT_SCAN_REPORT_PATH = PKG_DIR / "moat-scan-report.md"`
  - `MOAT_CANDIDATES_MD_PATH = PKG_DIR / "moat-candidates-pending-review.md"`
  - `RUBRIC_VERSION = "2026-09"` (surfaced in the report header + cache rows)
  - Universe:
    - `MOAT_FINVIZ_SECTOR_SCREENS: list[str]` — one coarse filter string per target sector, each
      `"cap_midover,fa_grossmargin_o60,geo_usa,sh_avgvol_o100,sec_<sector>"`. Sectors:
      `technology`, `healthcare`, `financial`, `communicationservices`, `industrials`.
      **Every token here is a best guess — Task 6 verifies them live.**
    - `MOAT_TARGET_INDUSTRIES: frozenset[str]` — exact Finviz industry labels (from
      `goat/config.py:GOAT_FINVIZ_INDUSTRIES`): `"Software - Application"`,
      `"Software - Infrastructure"`, `"Information Technology Services"`,
      `"Health Information Services"`, `"Healthcare Plans"`, `"Insurance Brokers"`,
      `"Financial Data & Stock Exchanges"`, `"Specialty Business Services"`,
      `"Consulting Services"`, `"Financial Conglomerates"`, `"Diagnostics & Research"`.
    - `MOAT_SEED_TICKERS: tuple[str, ...]` = `("CRM","NOW","INTU","ADP","PAYX","VEEV","TYL","ADSK",
      "ANSS","PTC","ORCL","WDAY","SPGI","FICO","VRSK","MSCI","FDS","SSNC","MANH","DSGX","PCTY",
      "PEGA","BSY","GWRE","CSGP","IT","BR","JKHY","FIS","FI")`. Comment: curated known-embedded-moat
      names so the scan is anchored even if the Finviz screen drifts.
    - `MOAT_UNIVERSE_CACHE_TTL_DAYS = 7` (Finviz screen re-run cadence; seed list is code).
    - `MOAT_UNIVERSE_SLICES = 5` (1/5 of the screened universe scored per calendar day).
  - Scoring:
    - `MOAT_STAGE_THRESHOLD = 80.0` — blended score at/above which a fresh name is staged.
      Comment: start conservative, tune down after first run (cash-value 0.80 → 0.50 precedent).
    - `MOAT_BLEND_QUANT_WEIGHT = 0.5` (qualitative weight = `1 - this`).
    - `MOAT_QUANT_WEIGHTS: dict[str, float]` — `{"gross_margin":0.25,"fcf_margin":0.20,
      "operating_margin":0.15,"rule_of_40":0.15,"revenue_durability":0.15,"recurring_revenue":0.10}`
      (sums to 1.0).
    - Quant ramp thresholds (each `(zero_at, hundred_at)`): `MOAT_GROSS_MARGIN_RAMP=(0.50,0.75)`,
      `MOAT_FCF_MARGIN_RAMP=(0.0,0.20)`, `MOAT_OPERATING_MARGIN_RAMP=(0.0,0.25)`,
      `MOAT_RULE_OF_40_RAMP=(20.0,40.0)`, `MOAT_REVENUE_DURABILITY_RAMP=(-10.0,0.0)` (worst annual
      YoY %; ≥0 → 100, ≤-10 → 0, and only reaches 70 at 0 then 100 for "never declined" — see
      Task 8), `MOAT_RECURRING_REVENUE_RAMP=(0.50,0.90)`.
    - `MOAT_DISCLOSURE_BONUS_MAX = 5.0` — max points added to `quant_score` for strong disclosed
      NRR (≥110%) + growing RPO + low logo churn (<10%); null fields contribute nothing.
    - `MOAT_ANTI_SIGNAL_PENALTY_EACH = 8.0`, `MOAT_ANTI_SIGNAL_PENALTY_CAP = 30.0`.
    - `MOAT_QUANT_NEUTRAL = 50.0` (score for an unavailable-but-not-negative sub-metric).
  - Universe / market-cap floor: `MOAT_MIN_MARKET_CAP_USD = 2_000_000_000.0` (re-checked precisely
    per ticker via yfinance in `quant.py`, not trusted from the coarse screen).
  - Models: `MOAT_RUBRIC_MODEL = "sonnet"`, `MOAT_EXTRACTION_MODEL = "haiku"` (mirrors
    `SEC_FILING_SUMMARY_MODEL` / `score.py`'s haiku).
  - Pacing: `MOAT_SEC_REQUEST_DELAY_SECONDS = 0.2`, `MOAT_FETCH_DELAY_SECONDS = 0.2`,
    `MOAT_FINVIZ_REQUEST_DELAY_SECONDS = 0.5`.
  - `MOAT_MAX_SECTION_CHARS = 6000` (per-section cap into the LLM prompt — mirrors
    `SEC_MAX_SECTION_CHARS`).
  - `MOAT_REPORT_MAX_ROWS = 120`.
- **PATTERN**: `investments/my-trader/mytrader/config.py:561-638`; `investments/goat/goat/config.py`.
- **GOTCHA**: `scripts.config` resolves to `investments/briefs-finance/scripts/config.py` in the
  workspace (that's the one with `DB_PATH = DATA_DIR / "investments.db"`), NOT
  `.claude/scripts/config.py`.
- **VALIDATE**: `uv run --directory investments/ai-resistant-moat-scanner python -c "from ai_resistant_moat_scanner import config as c; assert abs(sum(c.MOAT_QUANT_WEIGHTS.values())-1.0)<1e-9; assert c.DB_PATH.name=='investments.db'; print('ok')"`

### Task 3 — CREATE `ai_resistant_moat_scanner/db.py`

- **IMPLEMENT**: `_now()` (UTC isoformat). `init_moat_tables(conn)`:
  ```sql
  CREATE TABLE IF NOT EXISTS moat_pending_candidates (
      id                INTEGER PRIMARY KEY AUTOINCREMENT,
      ticker            TEXT NOT NULL UNIQUE,
      industry          TEXT NOT NULL,
      moat_score        REAL NOT NULL,
      quant_score       REAL NOT NULL,
      qualitative_score REAL NOT NULL,
      thesis            TEXT NOT NULL,
      sub_scores_json   TEXT NOT NULL,
      source            TEXT NOT NULL DEFAULT 'ai_resistant_moat_scan',
      flagged_at        TEXT NOT NULL
  );
  CREATE TABLE IF NOT EXISTS moat_qualitative_cache (
      ticker           TEXT NOT NULL,
      accession_number TEXT NOT NULL,
      rubric_version   TEXT NOT NULL,
      extraction_json  TEXT NOT NULL,
      rubric_json      TEXT NOT NULL,
      thesis           TEXT NOT NULL,
      computed_at      TEXT NOT NULL,
      PRIMARY KEY (ticker, accession_number, rubric_version)
  );
  ```
  Then the idempotent migration hook: `_MIGRATIONS: tuple[str, ...] = ()` +
  `for stmt in _MIGRATIONS: try: conn.execute(stmt) except sqlite3.OperationalError: pass`.
  CRUD: `insert_moat_pending_candidate(conn, *, ticker, industry, moat_score, quant_score,
  qualitative_score, thesis, sub_scores_json, source="ai_resistant_moat_scan")` (INSERT OR IGNORE,
  return `cur.rowcount == 1`); `get_moat_pending_candidate(conn, ticker)`;
  `get_all_moat_pending_candidates(conn)` (`ORDER BY moat_score DESC`);
  `delete_moat_pending_candidate(conn, ticker) -> int` (return `cur.rowcount`).
  `get_cached_qualitative(conn, ticker, accession_number, rubric_version) -> sqlite3.Row | None`;
  `upsert_qualitative_cache(conn, *, ticker, accession_number, rubric_version, extraction_json,
  rubric_json, thesis)` (`INSERT OR REPLACE`).
- **PATTERN**: `investments/goat/goat/db.py:15-195`;
  `investments/superinvestor-filings/superinvestor_filings/db.py`.
- **GOTCHA**: `rubric_version` in the cache PK means bumping `RUBRIC_VERSION` in `config.py`
  cleanly invalidates all cached sub-scores without a manual DB wipe.
- **VALIDATE**: covered by `test_db.py` in Task 16; quick check:
  `uv run --directory investments/ai-resistant-moat-scanner python -c "import sqlite3, tempfile, os; from ai_resistant_moat_scanner.db import init_moat_tables, insert_moat_pending_candidate, get_all_moat_pending_candidates; p=tempfile.mktemp(); c=sqlite3.connect(p); c.row_factory=sqlite3.Row; init_moat_tables(c); assert insert_moat_pending_candidate(c, ticker='CRM', industry='Software - Application', moat_score=88.0, quant_score=80.0, qualitative_score=96.0, thesis='t', sub_scores_json='{}'); assert not insert_moat_pending_candidate(c, ticker='CRM', industry='x', moat_score=1, quant_score=1, qualitative_score=1, thesis='t', sub_scores_json='{}'); print(len(get_all_moat_pending_candidates(c)))"`

### Task 4 — UPDATE `investments/my-trader/mytrader/finviz_screener.py` — optional `filters` param

- **IMPLEMENT**: Add `filters: str | None = None` to `_fetch_page` and `fetch_screener_universe`.
  In `_fetch_page`, `"f": filters or config.FINVIZ_SCREENER_FILTERS`. In `fetch_screener_universe`,
  pass `filters` through to `_fetch_page`. Also add optional `sort: str = "pricecash"` to
  `_fetch_page` (`"o": sort`) and thread it through — the moat screen doesn't need the price/cash
  sort. Default behaviour is byte-for-byte unchanged.
- **PATTERN**: existing signatures in the same file.
- **GOTCHA**: `mytrader/tests/conftest.py:171-176` stubs `fetch_screener_universe` with
  `lambda: None` — it's called with **no** positional args from `cash_value_scan`, so the new
  params MUST be keyword-optional with defaults. Do not make them positional-required.
- **VALIDATE**: `uv run --directory investments/my-trader python -m pytest -q mytrader/tests/test_finviz_screener.py`

### Task 5 — ADD `fetch_income_statement_history` to `investments/my-trader/mytrader/market_data.py` + public `extract_sections` to `sec_filings.py`

- **IMPLEMENT (market_data.py)**: `fetch_income_statement_history(ticker) -> list[float] | None` —
  `t = yf.Ticker(ticker); stmt = t.income_stmt` (annual); if `stmt is None or stmt.empty` or
  `"Total Revenue" not in stmt.index` → `None`; return the "Total Revenue" row values
  **oldest-first** as a `list[float]` (yfinance columns are newest-first — reverse them), dropping
  NaN. Mirror `fetch_cash_flow_statement`'s try/except/return-None shape exactly.
- **IMPLEMENT (sec_filings.py)**: add `def extract_sections(html: str, filing_type: str) ->
  dict[str, str]: return _extract_sections(html, filing_type)` — a public alias so the new package
  doesn't reach into a `_`-private function for the TOC-gotcha-aware section splitter.
- **PATTERN**: `market_data.fetch_cash_flow_statement:160-192`; `sec_filings._extract_sections:411`.
- **GOTCHA**: `income_stmt` typically returns only 4 annual periods — the durability metric must
  degrade to neutral when `< 3` values are available (documented in Task 8). Don't assume 2020 data.
- **VALIDATE**: `uv run --directory investments/my-trader python -m pytest -q mytrader/tests/test_market_data.py mytrader/tests/test_sec_filings.py`

### Task 6 — CREATE `ai_resistant_moat_scanner/universe.py`

- **IMPLEMENT**:
  - `fetch_screened_universe() -> list[dict] | None` — for each string in
    `config.MOAT_FINVIZ_SECTOR_SCREENS`, call
    `mytrader.finviz_screener.fetch_screener_universe(filters=screen, sort="marketcap")`
    (`time.sleep(MOAT_FINVIZ_REQUEST_DELAY_SECONDS)` between screens), concat, dedup by ticker,
    then keep only rows whose `row["industry"]` is in `config.MOAT_TARGET_INDUSTRIES`. Return
    `None` only if **every** screen returned `None` (total Finviz failure); a partial result is
    fine (precise re-test happens in `quant.py`).
  - DB cache: `moat_universe_cache` table (add to `db.py` in Task 3 — small oversight-proof: add
    it now to `db.py`) `(ticker PRIMARY KEY, company, industry, sector, fetched_at)`, refreshed
    when the newest `fetched_at` is `> MOAT_UNIVERSE_CACHE_TTL_DAYS` old or the table is empty,
    with `replace_*` (delete-all-then-insert) + stale-fallback — copy
    `goat/sp500_universe.get_or_refresh_sp500_constituents` + `goat/db.replace_sp500_constituents`
    line for line.
  - `get_scan_universe(conn) -> dict` returns `{"screened": [rows], "seed": [tickers],
    "slice_today": [tickers], "slice_index": int}`. `slice_index = date.today().toordinal() %
    config.MOAT_UNIVERSE_SLICES`. `slice_today` = the `slice_index`-th of the screened tickers
    sorted deterministically (`sorted(set(screened_tickers))[slice_index::MOAT_UNIVERSE_SLICES]`).
- **IMPORTANT — verify live before finishing this task** (do it once, from anywhere with network):
  ```
  python -c "import sys; sys.path.insert(0,'investments/my-trader'); from mytrader import finviz_screener as f; rows=f.fetch_screener_universe(filters='cap_midover,fa_grossmargin_o60,geo_usa,sh_avgvol_o100,sec_technology', sort='marketcap'); print(len(rows or [])); [print(r) for r in (rows or [])[:5]]"
  ```
  Confirm: (a) the filter string returns a non-empty list; (b) the `industry` values match the
  `MOAT_TARGET_INDUSTRIES` spellings; (c) `market_cap_text` values look like `"$Nb"`. If a token
  is wrong, open finviz.com/screener.ashx in a browser, tick the filters, read the real `f=`
  param, and correct `config.MOAT_FINVIZ_SECTOR_SCREENS`. Save one screen's raw HTML to
  `tests/fixtures/finviz_moat_screener_page.html`.
- **PATTERN**: `finviz_screener.fetch_screener_universe`; `goat/sp500_universe.py`;
  `goat/db.replace_sp500_constituents` / `get_sp500_constituents_fetched_at`.
- **GOTCHA**: Finviz industry single-select — you cannot OR industries in `f=`; that's why this
  screens by **sector** and filters to industries client-side using the parsed `industry` column.
- **VALIDATE**: `test_universe.py` (Task 16) using the saved fixture; plus
  `uv run --directory investments/ai-resistant-moat-scanner python -c "from ai_resistant_moat_scanner import universe; print('import ok')"`

### Task 7 — CREATE `ai_resistant_moat_scanner/filings_extract.py`

- **IMPLEMENT**:
  - `_SCRIPTS_DIR` + `sys.path.insert` + `from sdk_compat import ClaudeAgentOptions, run_text`.
  - Copy `_parse_json` from `scripts/score.py:33-40` verbatim.
  - `latest_10k(conn, ticker) -> dict | None` — `cik = sec_filings.get_cik(conn, ticker)`;
    `index = sec_filings.fetch_filing_index(cik)`; `sec_filings.latest_filing_entry(index, "10-K")`.
    Returns `{"cik", "accession_number", "primary_document", "filing_date"}` or `None`.
  - `fetch_10k_sections(entry) -> dict[str, str] | None` —
    `html = sec_filings.fetch_filing_document(entry["cik"], entry["accession_number"],
    entry["primary_document"])`; `sec_filings.extract_sections(html, "10-K")`; return the dict
    (keys `business` / `risk_factors` / `mda`) or `None` if empty.
  - `_EXTRACTION_PROMPT` — asks for ONLY valid JSON:
    `{"recurring_revenue_pct": <0-100|null>, "nrr_pct": <number|null>, "rpo_usd": <number|null>,
    "rpo_yoy_pct": <number|null>, "customer_count": <int|null>, "logo_churn_pct": <number|null>,
    "notes": "<=40 words on what the filing does/doesn't disclose about lock-in economics"}`.
    "Use null for anything the filing does not explicitly state. Do not estimate or infer a
    number." Feed `business` + `mda` sections, each truncated to `MOAT_MAX_SECTION_CHARS`.
  - `extract_disclosures(ticker, sections) -> dict` — `asyncio.run(run_text(prompt=…,
    options=ClaudeAgentOptions(allowed_tools=[], model=config.MOAT_EXTRACTION_MODEL)))` →
    `_parse_json` → coerce to the 7-key dict with `None` for missing/invalid → `except
    Exception: return {all-None dict}`.
- **PATTERN**: `sec_filings.get_filing_summaries_for_ticker` (fetch chain) +
  `sec_filings._summarize_sections` (prompt/`run_text` call) + `score._parse_json`.
- **GOTCHA**: `run_text` is async — must be `asyncio.run(...)`. Non-US / no-CIK ticker →
  `latest_10k` returns `None` → caller degrades to quant-only.
- **VALIDATE**: `test_filings_extract.py` (Task 16) with `run_text` stubbed to an async fake.

### Task 8 — CREATE `ai_resistant_moat_scanner/quant.py`

- **IMPLEMENT**:
  - `_ramp(value, zero_at, hundred_at) -> float` — linear clamp to `[0, 100]`, handles
    `hundred_at < zero_at` (descending ramps) too. `None` value → return `config.MOAT_QUANT_NEUTRAL`.
  - `compute_quant_metrics(data, extraction, revenue_history) -> dict | None` — `data` is a
    `market_data.TickerData`. Return `None` if `data.info` lacks `marketCap` **or**
    `marketCap < config.MOAT_MIN_MARKET_CAP_USD` **or** `grossMargins` absent (can't assess a
    software moat without margin). Compute:
    - `gross_margin = info["grossMargins"]`, `operating_margin = info.get("operatingMargins")`.
    - `fcf_margin = info["freeCashflow"] / info["totalRevenue"]` when both present, else `None`.
    - `rule_of_40 = (info.get("revenueGrowth") or 0)*100 + (fcf_margin or 0)*100` — `None` if
      `revenueGrowth` absent AND `fcf_margin` `None`.
    - `revenue_durability`: from `revenue_history` (oldest-first list). If `< 3` values → `None`.
      Else compute the sequence of YoY % changes; `worst = min(changes)`. Sub-score = `100.0` if
      `min(revenue_history) == revenue_history[-1]` never true... — concretely:
      `if worst >= 0: 100.0` (revenue never declined YoY); `elif worst <= -10: 0.0`;
      `else: _ramp(worst, -10.0, 0.0) * 0.7` (so a −5% worst year lands at 35, a −0.1% year near 70).
    - `recurring_revenue = extraction.get("recurring_revenue_pct")` (0-100 or `None`).
  - Sub-scores dict via `_ramp` + the ramps in config; `revenue_durability` and
    `recurring_revenue` use the special handling above / neutral-on-None.
  - `quant_score = sum(sub[k] * config.MOAT_QUANT_WEIGHTS[k] for k in weights)`.
  - Disclosure bonus: `+config.MOAT_DISCLOSURE_BONUS_MAX` scaled by how many of
    {`nrr_pct >= 110`, `rpo_yoy_pct is not None and rpo_yoy_pct > 0`, `logo_churn_pct is not None
    and logo_churn_pct < 10`} are true (each worth 1/3 of the max); null → not counted.
    `quant_score = min(100.0, quant_score + bonus)`.
  - Return `{"quant_score": round(quant_score,1), "sub_scores": {…}, "gross_margin": …,
    "fcf_margin": …, "operating_margin": …, "rule_of_40": …, "worst_revenue_yoy": worst_or_None,
    "market_cap": …, "currency": info.get("financialCurrency") or info.get("currency"),
    "sector": info.get("sector"), "disclosure_bonus": round(bonus,1)}`.
- **PATTERN**: `cash_value_scan.compute_cash_value_metrics:44-90` (pure, returns `None` on missing
  key fields).
- **GOTCHA**: `grossMargins` / `operatingMargins` / `revenueGrowth` are **fractions** in yfinance
  (0.78 not 78). `freeCashflow` / `totalRevenue` are absolute. Don't double-`*100`.
- **VALIDATE**: `test_quant.py` (Task 16) — pure function, no mocking needed beyond building an
  `info` dict.

### Task 9 — CREATE `ai_resistant_moat_scanner/qualitative.py`

- **IMPLEMENT**:
  - `_SCRIPTS_DIR` sys.path insert + `run_text` import + copied `_parse_json`.
  - `_RUBRIC_PROMPT` — the 6-part rubric from the handoff (System of record / Switching costs /
    Ecosystem lock-in / Regulatory-compliance entrenchment / Workflow breadth / Mission
    criticality), each 0-10, **must quote or paraphrase the filing language that justifies the
    score**. Also asks for `anti_signals` (list of short strings — point-solution, LLM-reproducible
    core value, low switching cost, moat-eroding management language) and `thesis` (<=25 words,
    one line, what makes this AI-durable or not). Return ONLY valid JSON:
    ```json
    {"system_of_record":0,"switching_costs":0,"ecosystem_lockin":0,
     "regulatory_entrenchment":0,"workflow_breadth":0,"mission_criticality":0,
     "citations":{"system_of_record":"...", ...},
     "anti_signals":["..."],"thesis":"..."}
    ```
    Feed `business` + `risk_factors` (each truncated to `MOAT_MAX_SECTION_CHARS`) + the extraction
    `notes` string.
  - `score_rubric(ticker, sections, extraction) -> dict | None` — `asyncio.run(run_text(...,
    model=config.MOAT_RUBRIC_MODEL))` → `_parse_json` → clamp each of the 6 to `[0,10]` ints →
    return `{"sub_scores": {6 keys}, "citations": {...}, "anti_signals": [...], "thesis": "..."}`.
    `except Exception` → `None` (a failed rubric call must not stage a name).
  - `compute_qualitative_score(rubric) -> float` — `raw = sum(6 sub)/60*100`;
    `penalty = min(len(anti_signals) * MOAT_ANTI_SIGNAL_PENALTY_EACH, MOAT_ANTI_SIGNAL_PENALTY_CAP)`;
    `return max(0.0, round(raw - penalty, 1))`.
  - `get_qualitative(conn, ticker) -> dict | None` — cache-aware orchestrator:
    1. `entry = filings_extract.latest_10k(conn, ticker)`; `None` → return `None` (no 10-K).
    2. `cached = db.get_cached_qualitative(conn, ticker, entry["accession_number"],
       config.RUBRIC_VERSION)`. If hit → build the result dict from `rubric_json` + `extraction_json`
       + `thesis` and return (no LLM, no fetch).
    3. `sections = filings_extract.fetch_10k_sections(entry)`; `None` → return `None`.
    4. `extraction = filings_extract.extract_disclosures(ticker, sections)`.
    5. `rubric = score_rubric(ticker, sections, extraction)`; `None` → return `None`.
    6. `qualitative_score = compute_qualitative_score(rubric)`.
    7. `db.upsert_qualitative_cache(conn, ticker=…, accession_number=entry["accession_number"],
       rubric_version=config.RUBRIC_VERSION, extraction_json=json.dumps(extraction),
       rubric_json=json.dumps(rubric), thesis=rubric["thesis"])`.
    8. `time.sleep(config.MOAT_SEC_REQUEST_DELAY_SECONDS)`.
    9. Return `{"qualitative_score": …, "sub_scores": rubric["sub_scores"],
       "anti_signals": rubric["anti_signals"], "thesis": rubric["thesis"],
       "extraction": extraction, "accession_number": entry["accession_number"],
       "filing_date": entry["filing_date"]}`.
- **PATTERN**: `principles_fit.check` (rubric-against-filing-text) + `sec_filings.
  get_filing_summaries_for_ticker:468-471` (cache-hit-on-accession) + `score.score_thesis_against_
  principle` (run_text + parse + clamp + except-return-sentinel).
- **GOTCHA**: cache key includes `rubric_version` — a `RUBRIC_VERSION` bump re-scores everything.
  The extraction JSON is cached alongside the rubric (same accession = same filing text), so a
  cache hit needs zero LLM calls.
- **VALIDATE**: `test_qualitative.py` (Task 16) — stub `filings_extract.latest_10k` /
  `fetch_10k_sections` / `extract_disclosures` and `score_rubric`'s `run_text`.

### Task 10 — CREATE `ai_resistant_moat_scanner/scoring.py`

- **IMPLEMENT**:
  - `blend_score(quant_score, qualitative_score) -> float` —
    `round(config.MOAT_BLEND_QUANT_WEIGHT * quant_score + (1 - config.MOAT_BLEND_QUANT_WEIGHT) *
    qualitative_score, 1)`.
  - `assemble_row(ticker, industry, company, quant, qualitative, tags) -> dict` — builds the full
    row dict the report + staging use: `moat_score` (via `blend_score`; if `qualitative is None`
    → `moat_score = None`, `stageable = False`), `quant_score`, `qualitative_score`,
    all 6 rubric sub-scores, `anti_signals`, `thesis`, `tags`, `worst_revenue_yoy`, `gross_margin`,
    `fcf_margin`, `market_cap`, `currency`, `filing_date`, `sub_scores_json` (json.dumps of a
    `{"quant": {...}, "qualitative": {...}, "anti_signals": [...]}` blob for the DB row).
- **PATTERN**: `principles_fit.check`'s result assembly (`data={...}`).
- **VALIDATE**: `test_scoring.py` (Task 16) — pure.

### Task 11 — CREATE `ai_resistant_moat_scanner/scan.py`

- **IMPLEMENT**: `run_scan(conn) -> dict`:
  1. `try: sec_filings.get_cik(conn, "AAPL") except Exception: pass` — warm the CIK map on a fresh
     DB (superinvestor `scan_edgar:209-212`).
  2. `universe_data = universe.get_scan_universe(conn)`. If `universe_data["screened"] == []` AND
     the Finviz fetch signalled total failure → set `finviz_failed = True` (report gets a STALE
     banner) but still proceed with seed + staged names.
  3. `staged = {r["ticker"] for r in db.get_all_moat_pending_candidates(conn)}`.
  4. `held = {r["ticker"] for r in mt_db.get_all_holdings(conn)}`;
     `watched = {r["ticker"] for r in mt_db.get_all_watchlist(conn)}`.
  5. `to_score = sorted(set(universe_data["slice_today"]) | set(config.MOAT_SEED_TICKERS) | staged)`.
  6. `industry_by_ticker` from `universe_data["screened"]` (fallback `"seed / not screened"` for
     seed-only names).
  7. `with market_data.cached_session():` loop `to_score`:
     - `excluded, review_reason = ethical_check(ticker)`; if `excluded` → `continue` (dropped, never
       shown — same as cash-value).
     - `data = market_data.fetch_ticker_data(ticker)`; `None` → `print(...)`, `continue`.
     - `revenue_history = market_data.fetch_income_statement_history(data.ticker)`.
     - `qualitative = qualitative.get_qualitative(conn, ticker)` (may be `None`).
     - `extraction = qualitative["extraction"] if qualitative else {}`.
     - `quant = quant.compute_quant_metrics(data, extraction, revenue_history)`; `None` →
       `print(...)`, `continue` (below market-cap floor, or no margin data).
     - `tags = []` + `held` / `watchlist` / `staged` / `review_reason` tagging (mirror
       `cash_value_scan._enrich_universe:183-197`).
     - `row = scoring.assemble_row(ticker, industry_by_ticker.get(ticker, "seed / not screened"),
       data.info.get("shortName") or "", quant, qualitative, tags)`.
     - Stage if `row["moat_score"] is not None and row["moat_score"] >= config.MOAT_STAGE_THRESHOLD
       and ticker not in held and ticker not in watched and ticker not in staged`:
       `db.insert_moat_pending_candidate(conn, ticker=…, industry=row["industry"],
       moat_score=row["moat_score"], quant_score=row["quant_score"],
       qualitative_score=row["qualitative_score"], thesis=row["thesis"],
       sub_scores_json=row["sub_scores_json"])`; append to `new_candidates` as
       `{"ticker", "industry", "moat_score", "thesis"}`; add ticker to `staged` (so it isn't
       double-processed).
     - `rows.append(row)`; `time.sleep(config.MOAT_FETCH_DELAY_SECONDS)`.
     - Wrap the per-ticker body in `try/except Exception as e: print(f"[ai-moat-scan] error on
       {ticker}: {e}")`.
  8. Return `{"scanned": len(rows), "slice_index": universe_data["slice_index"],
     "slices": config.MOAT_UNIVERSE_SLICES, "screened_total": len(universe_data["screened"]),
     "finviz_failed": finviz_failed, "rows": sorted([r for r in rows if r["moat_score"] is not
     None], key=lambda r: r["moat_score"], reverse=True) + [r for r in rows if r["moat_score"] is
     None], "new_candidates": new_candidates,
     "pending_candidates": [dict(r) for r in db.get_all_moat_pending_candidates(conn)]}`.
- **PATTERN**: `goat/heartbeat_scan.run_heartbeat_scan` + `cash_value_scan.run_scan` +
  `cash_value_scan._enrich_universe`.
- **GOTCHA**: `cached_session()` prevents an O(n) yfinance re-fetch storm. Held/watchlist names
  are scored + shown (tagged) but never staged — the report is meant to show your own holdings'
  moat scores too, unlike goat-heartbeat which skips them entirely.
- **VALIDATE**: `test_scan.py` (Task 16) — fully stubbed conn + universe + qualitative + quant.

### Task 12 — CREATE `ai_resistant_moat_scanner/report.py`

- **IMPLEMENT**:
  - `_today_sydney()` + `_now_sydney_str()` (copy from `cash_value_scan` / superinvestor `report`).
  - `render_report(result) -> str` — header:
    `# AI-Resistant Moat Scan`, "What this is:" para (embedded-software moat durability vs AI,
    blended 0-100, half hard financials half an LLM read of the latest 10-K), the SOUL.md
    advisor-notes disclaimer, and the dated caveat: `f"Rubric version {config.RUBRIC_VERSION} —
    encodes a 2026 view of what AI can cheaply rebuild; revisit periodically."`
    `**Last run: {_today_sydney()}**` line with `scanned N / screened M total / slice
    {i+1} of {slices}`. STALE banner (`> STALE — Finviz screen fetch failed …`) prepended via a
    non-stacking `_write_banner` helper copied from `cash_value_scan:362-379` when
    `result["finviz_failed"]`.
    Full ranked table: `| Ticker | Company | Industry | Moat | Quant | Qual | SoR | Switch | Ecosys
    | Regul | Breadth | Crit | Anti-signals | Worst rev YoY | Thesis | Tags |`. Rows with
    `moat_score is None` rendered last with `Moat` = `"n/a (no 10-K)"`. `_row_line` replaces `|`
    with `/` in free text (cash-value pattern).
    Tag key + `Last auto-generated:` Sydney footer.
  - `render_candidates_report(result) -> str` — mirror
    `goat/heartbeat_scan.render_heartbeat_candidates_report`: title
    `# AI-Resistant Moat Candidates — Pending Review`, the promote/dismiss instruction line
    (`promote-candidate` writes into my-trader's watchlist labeled AI-moat-approved;
    `dismiss-candidate` discards; edits here are overwritten next run), the
    `Scanned N ticker(s), slice {i+1}/{slices}` line, table
    `| Ticker | Industry | Moat | Quant | Qual | Thesis | Flagged |` from
    `result["pending_candidates"]`, `Last auto-generated:` footer.
  - `write_report(result)` / `write_candidates_report(result)` — write to
    `config.MOAT_SCAN_REPORT_PATH` / `config.MOAT_CANDIDATES_MD_PATH`. `write_report` routes to
    `_write_banner` when `result["finviz_failed"]` and there are no rows at all.
- **PATTERN**: `cash_value_scan.render_report` / `_write_banner`;
  `goat/heartbeat_scan.render_heartbeat_candidates_report`; `superinvestor .../report.py`.
- **VALIDATE**: `test_report.py` (Task 16).

### Task 13 — CREATE `ai_resistant_moat_scanner/notify.py`

- **IMPLEMENT**: `maybe_notify(new_candidates: list[dict]) -> None` — `if not new_candidates:
  return`. `sys.path` insert to `.claude/scripts`, `from notifications import
  send_toast_notification, send_whatsapp_notification`.
  `title = "AI-Resistant Moat Alert"`.
  Toast: `send_toast_notification(title, f"{len(new_candidates)} new embedded-moat candidate(s) —
  see investments/ai-resistant-moat-scanner/moat-candidates-pending-review.md")`.
  WhatsApp body:
  ```
  AI-Resistant Moat Alert: N new embedded-moat candidate(s).
  - TICKER (Industry) moat 88.4: <thesis>
  ...
  ```
  `send_whatsapp_notification("\n".join(lines))`.
- **PATTERN**: `superinvestor_filings/notify.py` (whole file); `goat/monitor.maybe_notify:176-206`.
- **GOTCHA**: the `.claude/scripts` path depth from
  `investments/ai-resistant-moat-scanner/ai_resistant_moat_scanner/notify.py` is
  `parent.parent.parent.parent / ".claude" / "scripts"` (same as `notify.py` in superinvestor).
- **VALIDATE**: `test_notify.py` (Task 16) — stub both `send_*` fns, assert titled call + no-op on
  `[]`.

### Task 14 — CREATE `ai_resistant_moat_scanner/main.py`

- **IMPLEMENT**: `_open_conn()` (copy superinvestor `main._open_conn`: `init_db(DB_PATH)` →
  `get_connection(DB_PATH)` → `init_mytrader_tables(conn)` → `init_moat_tables(conn)`).
  - `cmd_scan(args)`: `conn = _open_conn(); result = scan.run_scan(conn); conn.close();
    report.write_report(result); report.write_candidates_report(result);
    notify.maybe_notify(result["new_candidates"])`; print a one-line summary
    (`f"AI-Resistant Moat scan complete: scanned {result['scanned']}, "
    f"{len(result['new_candidates'])} new candidate(s), "
    f"{len(result['pending_candidates'])} pending. See "
    f"investments/ai-resistant-moat-scanner/moat-candidates-pending-review.md"`).
  - `cmd_promote_candidate(args)`: mirror `goat/main.cmd_promote_candidate:190-222` —
    `pending = db.get_moat_pending_candidate(conn, ticker)`; `None` → print + return;
    `mytrader.db.upsert_watchlist_row(conn, ticker=ticker, name=None, asset_type="stock",
    bucket="unassigned", status="raw", notes=f"AI-moat-approved — {pending['thesis']}",
    source="ai_resistant_moat")`; `db.delete_moat_pending_candidate(conn, ticker)`;
    `mytrader.snapshot.regenerate_all(conn)`; print confirmation.
  - `cmd_dismiss_candidate(args)`: `count = db.delete_moat_pending_candidate(conn, ticker)`; print.
  - `main()`: argparse subparsers `scan` (no args), `promote-candidate --ticker` (+ optional
    `--bucket` default `"unassigned"`, `--asset-type` default `"stock"`, `--status` default
    `"raw"`), `dismiss-candidate --ticker`. Dispatch dict, else `parser.print_help()`.
- **PATTERN**: `goat/main.py` (whole file); `superinvestor_filings/main.py:_open_conn`.
- **GOTCHA**: `upsert_watchlist_row` is keyword-only (`*`). The promote write is the ONLY place
  this package writes a my-trader table — add the same "deliberate exception" comment goat uses.
- **VALIDATE**: `uv run --directory investments/ai-resistant-moat-scanner python -m ai_resistant_moat_scanner.main --help` (prints subcommands, exits 0).

### Task 15 — CREATE systemd units + register in `invoke_investments.ps1` + `.gitignore`

- **IMPLEMENT**:
  - `scripts/systemd/second-brain-ai-moat-scan.service` — copy
    `second-brain-goat-heartbeat-scan.service`, change `Description=AI-Resistant Moat Scan`,
    `WorkingDirectory=/home/secondbrain/second-brain/investments/ai-resistant-moat-scanner`,
    `ExecStart=/home/secondbrain/second-brain/investments/.venv/bin/python -m
    ai_resistant_moat_scanner.main scan`,
    `StandardOutput`/`StandardError=append:/home/secondbrain/second-brain/investments/ai-resistant-moat-scanner/moat_scan_runs.log`.
  - `scripts/systemd/second-brain-ai-moat-scan.timer` — copy the goat-heartbeat timer, change
    `Description=AI-Resistant Moat Scan Timer`, `Requires=second-brain-ai-moat-scan.service`,
    `OnCalendar=*-*-* 23:30:00 UTC`, keep `Persistent=true` + `[Install] WantedBy=timers.target`.
  - `scripts/invoke_investments.ps1` — add `"ai-resistant-moat-scanner"` to the `[ValidateSet(...)]`
    on the `$Package` param AND
    `"ai-resistant-moat-scanner" = @{ Dir = "ai-resistant-moat-scanner"; Module =
    "ai_resistant_moat_scanner.main" }` to the `$PACKAGES` hashtable.
  - `.gitignore` — add line `investments/ai-resistant-moat-scanner/moat_scan_runs.log`.
- **PATTERN**: `scripts/systemd/second-brain-goat-heartbeat-scan.{service,timer}`;
  `scripts/invoke_investments.ps1:24,34-40`; `.gitignore:18`.
- **VALIDATE**: `powershell -NoProfile -Command "& { . ./scripts/invoke_investments.ps1 }" ` is not
  safe to dot-source (it has mandatory params) — instead
  `Select-String -Path scripts/invoke_investments.ps1 -Pattern 'ai-resistant-moat-scanner'`
  returns 2 matches; `test -f scripts/systemd/second-brain-ai-moat-scan.timer`.

### Task 16 — CREATE the test suite

- **IMPLEMENT** `tests/conftest.py` (copy superinvestor + goat conftest shape):
  - `db_path` (tmp_path), `db_conn` (`init_db` → `get_connection` → `init_mytrader_tables` →
    `init_moat_tables`).
  - autouse `_isolate_report_paths` — monkeypatch `config.MOAT_SCAN_REPORT_PATH` +
    `MOAT_CANDIDATES_MD_PATH` to `tmp_path`, and `MOAT_SEC_REQUEST_DELAY_SECONDS` /
    `MOAT_FETCH_DELAY_SECONDS` / `MOAT_FINVIZ_REQUEST_DELAY_SECONDS` to `0`.
  - autouse `_no_real_network` — stub `mytrader.sec_filings.get_cik` / `fetch_filing_index` /
    `fetch_filing_document` / `_fetch_cik_map_bulk`; `mytrader.finviz_screener.fetch_screener_universe`
    (`lambda **k: None`); `mytrader.market_data.fetch_ticker_data` /
    `fetch_income_statement_history` (`lambda *a, **k: None`);
    `ai_resistant_moat_scanner.filings_extract.run_text` and
    `ai_resistant_moat_scanner.qualitative.run_text` — replace with an async fn that raises (so any
    un-stubbed LLM path fails loudly in tests).
  - `FIXTURES = Path(__file__).parent / "fixtures"`.
- **IMPLEMENT** per-module tests (assertions, not just smoke):
  - `test_config.py` — weights sum to 1.0; `DB_PATH` is `investments.db`; every `MOAT_*_RAMP` is a
    2-tuple; seed list has no dupes; `MOAT_STAGE_THRESHOLD == 80.0`.
  - `test_db.py` — table creation idempotent (call `init_moat_tables` twice); insert dedup
    (`rowcount` semantics); `get_all_*` ordering by `moat_score DESC`; cache upsert/get roundtrip
    incl. `rubric_version` in the key; `delete_*` returns count.
  - `test_universe.py` — `fetch_screened_universe` parses `fixtures/finviz_moat_screener_page.html`
    (monkeypatch `finviz_screener._fetch_page` to return it) → rows filtered to
    `MOAT_TARGET_INDUSTRIES`; cache stale-fallback (pre-seed a stale row, stub fetch → `None`,
    assert stale rows still returned); `get_scan_universe` slice math (`toordinal % 5` partitioning
    is deterministic and covers the whole set over 5 consecutive ordinals).
  - `test_quant.py` — `_ramp` boundaries + descending ramp; `compute_quant_metrics` returns `None`
    below market-cap floor / with no `grossMargins`; a known `info` dict → expected `quant_score`
    (hand-compute one); revenue durability neutral when `< 3` history points; disclosure bonus
    scaling with 0 / 2 / 3 disclosed positives; fraction-vs-percent (0.78 gross margin → high, not
    capped-at-0).
  - `test_filings_extract.py` — `fetch_10k_sections` against `fixtures/sec_10k_moat_sample.html`
    (stub `sec_filings.fetch_filing_document` to return it) → `business` + `risk_factors` present;
    `extract_disclosures` with `run_text` stubbed to return fenced ` ```json {...} ``` ` → all 7
    keys coerced, `null`s stay `None`; `run_text` raising → all-None dict, no exception.
  - `test_qualitative.py` — cache hit path makes zero `run_text` / fetch calls (stub them to
    raise, pre-seed cache, assert result); `score_rubric` clamps out-of-range sub-scores;
    `compute_qualitative_score` penalty capping (4 anti-signals → −30 not −32);
    `get_qualitative` returns `None` when `latest_10k` is `None`.
  - `test_scoring.py` — `blend_score` 50/50; `assemble_row` with `qualitative=None` →
    `moat_score is None`, `stageable` false; `sub_scores_json` is valid JSON.
  - `test_scan.py` — fully stubbed: monkeypatch `universe.get_scan_universe` →
    `{"screened":[{"ticker":"CRM","company":"Salesforce","industry":"Software - Application",
    "sector":"Technology"}], "seed":["CRM"], "slice_today":["CRM"], "slice_index":0}`,
    `market_data.fetch_ticker_data` → a fake `TickerData`, `quant.compute_quant_metrics` → a dict
    with `quant_score=85`, `qualitative.get_qualitative` → a dict with `qualitative_score=95`,
    `thesis`, `sub_scores`, `extraction`. Assert: a candidate scoring ≥80 is inserted into
    `moat_pending_candidates` and appears in `result["new_candidates"]`; a held ticker (add to
    `holdings` via `mytrader.db`) is scored + in `rows` but NOT staged; ethical-excluded ticker
    (`"LMT"`) is skipped entirely; `qualitative=None` → row present, not staged; a second run does
    not double-insert the same pending row.
  - `test_report.py` — `render_report` contains the RUBRIC_VERSION caveat, the SOUL.md disclaimer,
    a table row per scored ticker, `n/a (no 10-K)` for `moat_score is None`; STALE banner present
    when `finviz_failed` and non-stacking on a re-render; `render_candidates_report` lists pending
    rows + promote/dismiss instructions.
  - `test_notify.py` — `maybe_notify([])` calls nothing; `maybe_notify([{...}])` calls
    `send_whatsapp_notification` once with a body starting `"AI-Resistant Moat Alert:"` and
    `send_toast_notification` with title `"AI-Resistant Moat Alert"`.
- **PATTERN**: `investments/goat/goat/tests/` + `investments/superinvestor-filings/superinvestor_filings/tests/`.
- **VALIDATE**: `uv run --directory investments/ai-resistant-moat-scanner python -m pytest -q`

### Task 17 — CREATE `README.md` + `DEPLOY.md` + UPDATE `investments/TOOLS.md`

- **IMPLEMENT (README.md)**: short — what it is, the two output files, "runs daily 23:30 UTC on the
  VPS", "all manual runs via `scripts/invoke_investments.ps1 -Package ai-resistant-moat-scanner
  -Command scan`", the RUBRIC_VERSION caveat.
- **IMPLEMENT (DEPLOY.md)**: copy `superinvestor-filings/DEPLOY.md` shape. The chained VPS block
  (one pasteable `&&` line — memory `feedback_manual_command_chaining`):
  ```
  ssh secondbrain@137.184.102.104
  cd /home/secondbrain/second-brain && git pull && \
    ~/.local/bin/uv sync --directory investments --all-packages && \
    sudo cp scripts/systemd/second-brain-ai-moat-scan.service scripts/systemd/second-brain-ai-moat-scan.timer /etc/systemd/system/ && \
    sudo systemctl daemon-reload && \
    sudo systemctl enable --now second-brain-ai-moat-scan.timer && \
    cd investments/ai-resistant-moat-scanner && \
    ../.venv/bin/python -m ai_resistant_moat_scanner.main scan
  ```
  Note the first run does a full slice + all seed names (no silent-seed concept here — there's no
  alert-suppression window; the first run WILL alert on any seed name scoring ≥80, which is fine
  and expected). Verify block: `systemctl list-timers 'second-brain-ai-moat-scan*'`,
  `sudo systemctl start second-brain-ai-moat-scan.service && tail -n 40 .../moat_scan_runs.log`,
  `cat .../moat-scan-report.md`.
- **IMPLEMENT (TOOLS.md)**:
  - "Daily Read" table: add a row for `moat-candidates-pending-review.md` (link + "AI-Resistant
    Moat Scan (daily, 23:30 UTC)").
  - "Automated (scheduled)" table: add an `<a id="ai-moat-scan"></a>` row — what it does (universe
    slice + seed + staged, blended quant/qualitative 0-100, stages ≥80, WhatsApp alert on fresh
    names, silent on zero), where it runs (`second-brain-ai-moat-scan.timer`), schedule
    (daily 23:30 UTC), output (`moat-scan-report.md` + `moat-candidates-pending-review.md`).
  - "Manual / on-demand only" table: rows for `scan`, `promote-candidate --ticker X`,
    `dismiss-candidate --ticker X`.
  - Add a "## <a id="ai-moat-scan"></a>AI-Resistant Moat Scan — how it works + tuning" section
    modelled on the Cash-Value section: the idea (Salesforce embedded-moat thesis), the two
    universes (Finviz sector screens → industry allow-list, + seed list), the blended score
    (50/50, the 6-part rubric, the quant sub-metrics), the ≥80 staging cutoff (tune down after
    first run), the daily 1/5 slice rotation + caching, the RUBRIC_VERSION snapshot caveat, and a
    tuning-knobs table (`MOAT_STAGE_THRESHOLD`, `MOAT_BLEND_QUANT_WEIGHT`, `MOAT_QUANT_WEIGHTS`,
    `MOAT_UNIVERSE_SLICES`, `MOAT_FINVIZ_SECTOR_SCREENS`, `MOAT_SEED_TICKERS`, `RUBRIC_VERSION`).
  - Bump the "Last updated" date at the top of TOOLS.md.
- **PATTERN**: `investments/TOOLS.md:11-146`; `superinvestor-filings/DEPLOY.md`.
- **VALIDATE**: `Select-String -Path investments/TOOLS.md -Pattern 'ai-moat-scan'` → ≥4 matches.

### Task 18 — UPDATE memory + run full validation

- **IMPLEMENT**: Update `C:\Users\User\.claude\projects\O--AI-Dynamous-Courses-second-brain-workshop\memory\project_ai_resistant_moat_scanner.md`
  from "planned / awaiting /plan-feature" to "BUILT <date>; NOT yet deployed — see
  `investments/ai-resistant-moat-scanner/DEPLOY.md`" (and note the first-run-alerts-on-seed-names
  behaviour + the ≥80 cutoff to tune). Leave the `MEMORY.md` one-line pointer, just refresh its hook.
- **VALIDATE**: run every command in "VALIDATION COMMANDS" below; all green.

---

## TESTING STRATEGY

### Unit tests
pytest, per-module, fixtures + assertions, following `investments/goat/goat/tests/` and
`investments/superinvestor-filings/superinvestor_filings/tests/`. Pure functions (`quant`,
`scoring`, `_ramp`, `compute_qualitative_score`, `blend_score`, report renderers) tested directly.
Network/LLM boundaries stubbed globally in `conftest.py` (autouse) — no test in the suite makes a
real SEC / Finviz / yfinance / LLM call. `run_text` is stubbed to an async fn that **raises**, so
any code path that forgets to stub its LLM call fails loudly rather than hanging.

### Integration tests
`test_scan.py` exercises the real `run_scan` orchestrator against a tmp_path DB with `universe` /
`market_data` / `quant` / `qualitative` all stubbed — verifies staging logic, held/watchlist
suppression, ethical-filter drop, `moat_score is None` handling, idempotent re-run.

### Edge cases (must have explicit tests)
- Ticker below `MOAT_MIN_MARKET_CAP_USD` → `compute_quant_metrics` returns `None` → not in report.
- Ticker with no yfinance data → skipped with a `[ai-moat-scan]` print, not in report.
- Non-US / no-CIK ticker → `get_qualitative` returns `None` → row is quant-only, `moat_score` `None`,
  never staged.
- LLM rubric call raises / returns unparseable JSON → `get_qualitative` returns `None` (no
  fabricated 50, no staging).
- New 10-K filed (accession changes) → cache miss → re-score; same accession → cache hit, zero LLM.
- `RUBRIC_VERSION` bump → every cache row misses → full re-score.
- Finviz total failure → STALE banner, seed + staged names still scored; banner non-stacking on
  consecutive failed runs.
- Held / watchlisted ticker scoring ≥80 → scored + shown + tagged, NOT staged.
- Same candidate on two consecutive runs → single pending row (INSERT OR IGNORE).
- Revenue history < 3 annual points → durability sub-metric = neutral 50.
- `anti_signals` length 5 → penalty capped at `MOAT_ANTI_SIGNAL_PENALTY_CAP` (30), not 40.

---

## VALIDATION COMMANDS

Run every command; expect zero errors / zero regressions.

### Level 1: Syntax & Style
```
uv run --directory investments/ai-resistant-moat-scanner python -m ruff check .
uv run --directory investments/ai-resistant-moat-scanner python -m mypy ai_resistant_moat_scanner
uv run --directory investments/my-trader python -m ruff check mytrader/finviz_screener.py mytrader/market_data.py mytrader/sec_filings.py
```

### Level 2: Unit Tests
```
uv run --directory investments/ai-resistant-moat-scanner python -m pytest -q
uv run --directory investments/my-trader python -m pytest -q mytrader/tests/test_finviz_screener.py mytrader/tests/test_market_data.py mytrader/tests/test_sec_filings.py
```

### Level 3: Full investments suite (no regressions in sibling packages)
```
uv run --directory investments/my-trader python -m pytest -q
uv run --directory investments/goat python -m pytest -q
uv run --directory investments/superinvestor-filings python -m pytest -q
```

### Level 4: Manual Validation (on the VPS, after deploy — see DEPLOY.md)
```
# one real run
.\scripts\invoke_investments.ps1 -Package ai-resistant-moat-scanner -Command "scan"
# inspect both outputs
#   investments/ai-resistant-moat-scanner/moat-scan-report.md         (full ranked table, sub-scores, theses)
#   investments/ai-resistant-moat-scanner/moat-candidates-pending-review.md  (fresh >=80 names)
# promote / dismiss round-trip on a real staged ticker
.\scripts\invoke_investments.ps1 -Package ai-resistant-moat-scanner -Command "promote-candidate --ticker <TICKER>"
.\scripts\invoke_investments.ps1 -Package ai-resistant-moat-scanner -Command "dismiss-candidate --ticker <TICKER>"
```
Sanity-check the first real run: seed names (CRM, NOW, INTU, VEEV, TYL…) should land high
(moat 75-95); a thin point-tool should land low; theses should quote real 10-K language; no
defense contractor (LDOS, CACI) appears; PLTR/BA appear only if screened, tagged `REVIEW:`.

### Level 5: systemd
```
# on the VPS
systemctl list-timers 'second-brain-ai-moat-scan*' --no-pager
sudo systemctl start second-brain-ai-moat-scan.service
tail -n 60 /home/secondbrain/second-brain/investments/ai-resistant-moat-scanner/moat_scan_runs.log
```

---

## ACCEPTANCE CRITERIA

- [ ] New workspace member `ai-resistant-moat-scanner` resolves via `uv sync` from `investments/`.
- [ ] `python -m ai_resistant_moat_scanner.main scan` produces both `.md` files and (only when a
      fresh name is staged) one WhatsApp + toast titled "AI-Resistant Moat Alert".
- [ ] Blended score = `0.5*quant + 0.5*qualitative`; names ≥ `MOAT_STAGE_THRESHOLD` (80) that are
      not held / watchlisted / already staged are inserted into `moat_pending_candidates`.
- [ ] Qualitative sub-scores are cached per `(ticker, accession_number, rubric_version)`; a
      same-day re-run makes zero LLM calls for unchanged filings.
- [ ] Ethical filter: `DEFENSE_TICKERS` dropped entirely; `BA`/`PLTR` shown with `REVIEW:` tag.
- [ ] Held / watchlisted tickers are scored and shown (tagged) but never staged.
- [ ] Non-US / no-10-K tickers degrade to quant-only, `moat_score` `n/a`, never staged.
- [ ] `promote-candidate` writes one my-trader watchlist row (`source="ai_resistant_moat"`,
      `notes` carries the thesis), regenerates `watchlist.md`, deletes the pending row.
- [ ] Daily systemd timer at 23:30 UTC, `Persistent=true`; `.service` writes `moat_scan_runs.log`.
- [ ] `scripts/invoke_investments.ps1` accepts `-Package ai-resistant-moat-scanner`.
- [ ] `mytrader/finviz_screener.py` change is backward compatible — full my-trader + goat +
      superinvestor test suites still pass.
- [ ] `investments/TOOLS.md` has the Daily Read + Automated + Manual rows and a "how it works +
      tuning" section; "Last updated" date bumped.
- [ ] Report header + module docstring + TOOLS.md carry the dated `RUBRIC_VERSION` snapshot caveat.
- [ ] All Level 1–3 validation commands pass with zero errors.
- [ ] `project_ai_resistant_moat_scanner.md` memory updated to "BUILT, not yet deployed".

---

## COMPLETION CHECKLIST

- [ ] All 18 tasks completed in order, each task's VALIDATE passed immediately.
- [ ] Level 1 (ruff + mypy) clean.
- [ ] Level 2 + Level 3 (new suite + all sibling suites) green.
- [ ] Finviz filter tokens verified live (Task 6) and a real screener page saved as a fixture.
- [ ] `DEPLOY.md` written with the one-line chained VPS block.
- [ ] Manual VPS run (Level 4) done, both `.md` outputs eyeballed for sanity, promote/dismiss
      round-trip works. (This step is Shaun's — hand him the chained deploy command.)
- [ ] Memory + MEMORY.md pointer refreshed.
- [ ] `/commit` (auto-pushes + deploys to VPS).

---

## NOTES

**Design decisions / trade-offs**

- *Own staging table, not goat's.* `moat_pending_candidates` mirrors `goat_pending_candidates`'s
  schema but stays separate — goat's promote writes "Goat-approved sector rotation" notes and
  couples two unrelated tools. Cross-package precedent (goat reads my-trader's tables read-only,
  writes the watchlist only on explicit promote) is preserved.

- *US-only v1.* The qualitative half is the whole point and it's SEC-10-K-shaped. `sec_filings.py`
  already degrades non-US tickers to `None`; an ASX leg (reusing `asx_announcements.py`) is a
  clean follow-up but explicitly out of scope here (handoff "Explicitly deferred").

- *1/5 universe slice per day.* SEC fair-access + yfinance rate limits both argue against
  hammering ~300 names nightly. Seed + staged names are re-scored every day (they're the ones
  Shaun cares about); the rest rotate. Caching means an unchanged-filing name in today's slice
  costs one yfinance `.info` + one `income_stmt` call and zero LLM calls.

- *A failed LLM call never stages a name.* Unlike `score.py` (which defaults to 50 on a parse
  failure because it's grading an already-surfaced Briefs pick), staging a name into Shaun's
  review queue on a broken rubric call would be noise. Broken call → `qualitative_score = None`
  → quant-only row → not stageable.

- *Quant half is deliberately yfinance-`.info`-thin.* Mirrors `cash_value_scan`. Recurring-revenue
  %, NRR, RPO, churn come from the LLM extraction pass (nullable, "not disclosed → neutral"), not
  yfinance. Revenue-durability uses `income_stmt` (≈4 annual periods — the 2020 shock is usually
  out of range; the metric degrades to neutral below 3 points rather than pretending).

**Known risks / where a second pass is likely**

1. **Finviz filter tokens** (Task 6) — `sec_<sector>` / `fa_grossmargin_o60` / `cap_midover` are
   best guesses; Finviz renames tokens. Task 6 mandates a live check before finishing. Low blast
   radius: a wrong token → smaller/empty screened universe, seed list still carries the scan.
2. **LLM rubric consistency** — the 6-part 0-10 rubric prompt will likely need 1-2 iterations
   after seeing real output on 10-15 names (are software 10-Ks giving it enough to cite? is the
   anti-signal detection firing sensibly?). Budget for a prompt-tuning pass post-first-run, same
   as every other LLM check in this repo (`SEC_FILING_SUMMARY_MODEL` was A/B'd on a real KO 10-K).
3. **10-K section extraction on software filers** — `sec_filings._extract_10k_sections` was
   validated against KO (consumer goods). Software filers (esp. ones that file a combined
   10-K wrapper or heavy exhibits) may split differently. `test_filings_extract.py` uses a real
   software 10-K fixture; the manual Level 4 run is where any real-filer surprise shows up.
4. **`moat_universe_cache` table** — added to `db.py` in Task 3 (mentioned in Task 6); don't
   forget it when writing `db.py`.

**Estimated confidence for one-pass implementation: 7/10.** The plumbing (workspace member,
DB tables, systemd, invoke wrapper, report/notify/CLI, ethical filter, SEC fetch) is
heavily precedented and low-risk. The two genuine unknowns — exact Finviz tokens and LLM rubric
output quality — are both flagged with explicit live-validation steps and are expected to need a
short tuning pass after the first real VPS run, exactly like the cash-value scanner's 0.80→0.50
loosening.
