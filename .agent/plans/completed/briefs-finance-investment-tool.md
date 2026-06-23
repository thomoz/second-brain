# Feature: Briefs Finance Investment Tool

The following plan should be complete, but validate codebase patterns and task sanity before implementing.
Pay special attention to the sdk_compat import pattern and the sys.path manipulation needed for scripts outside .claude/scripts/.

## Feature Description

A standalone investment research tool that ingests Briefs Finance PDF reports, extracts structured stock recommendations via LLM, backtests historical picks against real market data, applies an ethical filter (no defense/military stocks), and produces a 0-100% likelihood score for new recommendations.

Real-world context layers:
- **Price backtesting**: stock return vs S&P 500 at 3/6/12 months after recommendation (yfinance)
- **Sector ETF tracking**: did the whole sector thesis play out? (yfinance sector ETFs)
- **Macro snapshot**: interest rates, yield curve, VIX, gold, USD at recommendation date (yfinance + optional FRED)
- **News context**: yfinance .news() headlines around recommendation date

All output is for Shaun's review. Nothing acts autonomously.

## User Story

As a retail investor
I want to load a Briefs Finance report and get a scored, historically-calibrated assessment with real-world context showing whether past theses actually played out
So that I can evaluate new recommendations knowing the track record and macro conditions behind them

## Problem Statement

Briefs Finance publishes 84+ research reports (2025-2026) with stock picks buried in prose. No easy way to know: (a) whether picks outperformed the market, (b) whether the macro thesis materialised, or (c) whether sector tailwinds explain the return (luck) vs stock-specific insight (skill).

## Solution Statement

Five real-world data layers wired into a single 0-100% likelihood score:
1. LLM extraction of tickers + theses from PDF prose (sdk_compat/Codex)
2. Price backtesting vs S&P 500 at 3/6/12 months (yfinance)
3. Sector ETF performance over same period — thesis validation (yfinance)
4. Macro snapshot at recommendation date — rates, VIX, gold, USD (yfinance + optional FRED API)
5. Principles alignment — LLM scores thesis against 9 investor frameworks

## Feature Metadata

**Feature Type**: New Capability
**Estimated Complexity**: High
**Primary Systems Affected**: investments/briefs-finance/ (new standalone tool)
**Dependencies**: pdfplumber, yfinance, requests, python-dotenv, python-dateutil, sdk_compat (via sys.path)

---

## CONTEXT REFERENCES

### Relevant Codebase Files - READ BEFORE IMPLEMENTING

- `.claude/scripts/sdk_compat.py` - LLM backend selector. Import `run_text` and `ClaudeAgentOptions`. NEVER import from claude_agent_sdk or codex_sdk_compat directly.
- `.claude/scripts/codex_sdk_compat.py` (lines 1-50) - `run_text()` with `allowed_tools=[]` is the correct pattern for pure reasoning/JSON extraction.
- `.claude/scripts/config.py` - Pattern for path constants + env var loading. Mirror this structure.
- `.claude/scripts/shared.py` (lines 47-75) - `atomic_write`, `with_retry` patterns to reuse.
- `.claude/scripts/memory_reflect.py` - Shows `run_text()` with a structured JSON prompt. Mirror this.
- `.claude/scripts/pyproject.toml` - Tooling conventions to mirror.
- `.agent/plans/investments-feature-handoff.md` - Full design context; read before starting.

### New Files to Create

```
investments/briefs-finance/
  pyproject.toml
  .env.example                      # FRED_API_KEY=optional, MACRO_SCORE=50
  scripts/
    config.py                       # paths, defense filter, sector ETF map, scoring weights
    db.py                           # SQLite schema + CRUD (7 tables)
    extract.py                      # pdfplumber text + hash
    llm_extract.py                  # LLM JSON extraction from raw PDF text
    ethical_filter.py               # defense/military ticker filter
    sector_map.py                   # maps report themes to sector ETFs; fetches ETF prices
    macro.py                        # macro snapshot: yfinance proxies + optional FRED
    ingest.py                       # orchestration: PDF -> extract -> filter -> DB
    prices.py                       # yfinance OHLCV wrapper
    backtest.py                     # outcomes + sector context + macro snapshot
    score.py                        # composite 0-100% likelihood scoring
    report.py                       # display layer: Rich terminal / Markdown vault / HTML
    main.py                         # unified CLI
    templates/
      stats.html                    # Chart.js stats dashboard template
    tests/
      __init__.py
      conftest.py
      test_extract.py
      test_ethical_filter.py
      test_sector_map.py
      test_macro.py
      test_db.py
      test_backtest.py
      test_score.py
      test_report.py
  principles/
    graham.md  buffett.md  munger.md  lynch.md  fisher.md
    marks.md   dalio.md    smith.md   neilson.md
.claude/skills/investments/
  SKILL.md
```

### Patterns to Follow

**sys.path for sdk_compat** (investments scripts live outside .claude/scripts/):
```python
import sys
from pathlib import Path
_SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent.parent / ".claude" / "scripts"
sys.path.insert(0, str(_SCRIPTS_DIR))
from sdk_compat import run_text, ClaudeAgentOptions
```

**LLM call pattern** (mirror memory_reflect.py):
```python
import asyncio, json
raw = asyncio.run(run_text(prompt=PROMPT.format(text=text), options=ClaudeAgentOptions(allowed_tools=[], model="sonnet")))
data = json.loads(raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip())
```

**yfinance fetch pattern**:
```python
def get_close_on_or_after(ticker: str, target: date, window: int = 7) -> float | None:
    from datetime import timedelta
    import yfinance as yf
    end = target + timedelta(days=window)
    hist = yf.Ticker(ticker).history(start=target.isoformat(), end=end.isoformat(), auto_adjust=True)
    return float(hist["Close"].iloc[0]) if not hist.empty else None
```

**FRED API pattern** (requests, free key from fred.stlouisfed.org):
```python
def fred_value_on(series_id: str, target: date) -> float | None:
    if not FRED_API_KEY:
        return None
    from datetime import timedelta
    r = requests.get("https://api.stlouisfed.org/fred/series/observations", params={
        "series_id": series_id, "observation_start": (target - timedelta(days=30)).isoformat(),
        "observation_end": target.isoformat(), "sort_order": "desc", "limit": 1,
        "api_key": FRED_API_KEY, "file_type": "json"}, timeout=10)
    obs = r.json().get("observations", [])
    val = obs[0]["value"] if obs else None
    return float(val) if val and val != "." else None
```

**Test structure**: pytest, in-memory SQLite (`:memory:`), mock yfinance + LLM, no real network in unit tests.

---

## SECTOR ETF MAP (in config.py)

```python
SECTOR_ETF_MAP: dict[str, list[str] | None] = {
    "gold":          ["GDX", "GLD"],    "energy":        ["XLE", "XOP"],
    "oil":           ["XLE", "USO"],    "uranium":       ["URA"],
    "rare earth":    ["REMX"],          "copper":        ["COPX"],
    "lithium":       ["LIT"],           "water":         ["PHO"],
    "ai":            ["XLK", "BOTZ"],   "tech":          ["XLK", "QQQ"],
    "robotics":      ["ROBO", "BOTZ"],  "cybersecurity": ["CIBR"],
    "space":         ["ARKX"],          "data center":   ["IGV"],
    "china":         ["KWEB", "FXI"],   "japan":         ["EWJ"],
    "europe":        ["VGK"],           "biotech":       ["XBI", "IBB"],
    "healthcare":    ["XLV"],           "income":        ["VYM", "SCHD"],
    "consumer":      ["XLP"],           "gaming":        ["ESPO"],
    "drone":         ["DRON"],          "africa":        ["AFK"],
    "cannabis":      ["MSOS"],          "stablecoin":    ["BITO"],
    "quantum":       ["QTUM"],          "defence":       None,
    "defense":       None,              "helium":        ["XLE"],
}
```

Primary ETF = first in list (most liquid). If no match: sector_context NULL.

## MACRO INDICATORS

### Via yfinance (always available, no key)
| Symbol | Measures |
|--------|----------|
| `^TNX` | 10-year Treasury yield |
| `^IRX` | 13-week T-bill (Fed funds proxy) |
| `^VIX` | CBOE Volatility Index |
| `GLD`  | Gold price |
| `UUP`  | US Dollar ETF |
| `TLT`  | 20yr Treasury bond (rate sensitivity) |

### Via FRED API (optional, free key — fred.stlouisfed.org)
| Series ID | Measures |
|-----------|----------|
| `T10Y2Y` | 10Y-2Y yield spread (negative = recession signal) |
| `RECPROUSM156N` | US recession probability |
| `CPIAUCSL` | CPI inflation |
| `FEDFUNDS` | Federal Funds Rate |

FRED_API_KEY not set = NULL for those columns. Not an error.

---

## IMPLEMENTATION PLAN

### Phase 1: Foundation — pyproject.toml, config.py, db.py
### Phase 2: PDF Extraction + LLM Structuring — extract.py, llm_extract.py
### Phase 3: Ethical Filter + Ingestion — ethical_filter.py, ingest.py
### Phase 4: Real-World Data — prices.py, sector_map.py, macro.py
### Phase 5: Backtesting — backtest.py (all three data layers)
### Phase 6: Principles Knowledge Files — 9 markdown files
### Phase 7: Likelihood Scoring — score.py
### Phase 8: CLI + Skill — main.py, SKILL.md
### Phase 9: Tests + Bulk Ingest

---

## STEP-BY-STEP TASKS

### Task 1: CREATE investments/briefs-finance/pyproject.toml

- **IMPLEMENT**:
  ```toml
  [project]
  name = "briefs-finance"
  version = "0.1.0"
  requires-python = ">=3.12"
  dependencies = [
      "pdfplumber>=0.11.0",
      "yfinance>=0.2.40",
      "requests>=2.31.0",
      "python-dotenv>=1.0.0",
      "python-dateutil>=2.9.0",
      "rich>=13.0.0",
  ]
  [project.optional-dependencies]
  dev = ["pytest>=8.0.0", "ruff>=0.2.0", "mypy>=1.8.0", "pytest-mock>=3.12.0"]
  [tool.pytest.ini_options]
  testpaths = ["scripts/tests"]
  [tool.ruff]
  target-version = "py312"
  line-length = 100
  [tool.mypy]
  python_version = "3.12"
  ignore_missing_imports = true
  ```
- **GOTCHA**: Do NOT include claude-code-sdk or second-brain deps.
- **VALIDATE**: `cd investments/briefs-finance && uv sync`

### Task 2: CREATE investments/briefs-finance/scripts/config.py

- **IMPLEMENT**: All path constants, sector ETF map, defense filter, scoring weights.
  ```python
  from pathlib import Path
  import os
  from dotenv import load_dotenv

  _HERE = Path(__file__).resolve().parent
  load_dotenv(_HERE.parent / ".env")

  PROJECT_ROOT  = _HERE.parent.parent.parent.parent  # 4 levels up to repo root
  INVESTMENTS_DIR = PROJECT_ROOT / "investments" / "briefs-finance"
  DATA_DIR      = INVESTMENTS_DIR / "data"
  DB_PATH       = DATA_DIR / "investments.db"
  REPORTS_DIR   = INVESTMENTS_DIR / "reports"
  PRINCIPLES_DIR = INVESTMENTS_DIR / "principles"

  DEFENSE_TICKERS = frozenset({"LMT","RTX","NOC","GD","HII","LHX","LDOS","SAIC","CACI","KTOS","AVAV","BWXT","TXT","HEICO","TDG","CW","DRS"})
  DEFENSE_REVIEW_TICKERS = frozenset({"BA", "PLTR"})

  SP500_TICKER = "^GSPC"
  PRICE_WINDOW_DAYS = 7

  MACRO_YFINANCE = {"treasury_10y":"^TNX","tbill_3m":"^IRX","vix":"^VIX","gold":"GLD","usd":"UUP","bonds_20y":"TLT"}
  FRED_API_KEY = os.getenv("FRED_API_KEY", "")
  FRED_SERIES  = {"yield_curve":"T10Y2Y","recession_prob":"RECPROUSM156N","cpi":"CPIAUCSL","fed_funds":"FEDFUNDS"}

  SECTOR_ETF_MAP = { ... }  # full map as shown above

  SCORING_WEIGHTS = {
      "base_rate":0.20, "sector_rate":0.15, "ticker_history":0.15,
      "principles":0.20, "macro":0.15, "sector_context":0.15,
  }
  MACRO_SCORE_DEFAULT = int(os.getenv("MACRO_SCORE", "50"))
  ```
- **VALIDATE**: `uv run python -c "from scripts.config import DB_PATH, SECTOR_ETF_MAP; print(DB_PATH)"`

### Task 3: CREATE investments/briefs-finance/scripts/db.py

- **IMPLEMENT**: Seven tables:
  ```
  reports            (id, file_path, content_hash UNIQUE, report_date, report_type, series,
                      title, inferred_sector, raw_text, ingested_at)
  recommendations    (id, report_id FK, ticker, company_name, buy_thesis, exit_trigger,
                      excluded, exclusion_reason, extracted_at)
  outcomes           (id, recommendation_id FK UNIQUE, price_at_rec/3m/6m/12m,
                      sp500_at_rec/3m/6m/12m, return_3m/6m/12m, vs_sp500_3m/6m/12m, fetched_at)
  sector_context     (id, recommendation_id FK UNIQUE, sector_etf,
                      etf_price_at_rec/3m/6m/12m, etf_return_3m/6m/12m,
                      stock_vs_sector_3m/6m/12m, fetched_at)
  macro_snapshot     (id, report_id FK UNIQUE, snapshot_date,
                      treasury_10y, tbill_3m, vix, gold_price, usd_strength,
                      yield_curve, recession_prob, cpi_yoy, fetched_at)
  principles_evaluations (id, recommendation_id FK, principle, score 0-100, reasoning, scored_at)
  likelihood_scores  (id, recommendation_id FK UNIQUE, score 0-100,
                      base_rate/sector_rate/ticker_history/principles/macro/sector_context components,
                      breakdown_json, provisional, computed_at)
  ```
  Functions: `get_connection()`, `init_db()`, `upsert_report()`, `upsert_recommendation()`,
  `upsert_outcome()`, `upsert_sector_context()`, `upsert_macro_snapshot()`,
  `get_all_outcomes()`, `get_ticker_outcomes(ticker)`, `get_sector_outcomes(etf)`.
- **GOTCHA**: Use `INSERT OR REPLACE` for all upserts.
- **GOTCHA**: Call `DATA_DIR.mkdir(parents=True, exist_ok=True)` in `init_db()` before creating DB.
- **VALIDATE**: `uv run python -c "from scripts.db import init_db; init_db(); print('OK')"`

### Task 4: CREATE investments/briefs-finance/scripts/extract.py

- **IMPLEMENT**:
  ```python
  import hashlib, warnings
  import pdfplumber
  from pathlib import Path

  def extract_text(pdf_path: Path) -> str:
      warnings.filterwarnings("ignore", message=".*FontBBox.*")
      try:
          with pdfplumber.open(pdf_path) as pdf:
              return "\n".join(p.extract_text() or "" for p in pdf.pages)
      except Exception:
          return ""

  def compute_hash(pdf_path: Path) -> str:
      return hashlib.sha256(pdf_path.read_bytes()).hexdigest()
  ```
- **VALIDATE**: `uv run python -c "from scripts.extract import extract_text; from pathlib import Path; print(extract_text(Path('reports/pro-2026/1781550652-Golds_Comeback_May_30.pdf'))[:200])"`

### Task 5: CREATE investments/briefs-finance/scripts/llm_extract.py

- **IMPLEMENT**: LLM JSON extraction with sys.path sdk_compat injection.
  Prompt returns: `report_date`, `title`, `report_type`, `series`, `inferred_sector`, `recommendations[]`.
  Retry 3x on JSON parse failure. Strip ```json fences before parsing.

  ```python
  EXTRACTION_PROMPT = """
  Extract ALL stock recommendations from this Briefs Finance report.
  Also identify the primary market sector/theme keyword.
  Return ONLY valid JSON (no markdown, no explanation):
  {{
    "report_date": "YYYY-MM-DD",
    "title": "exact report title",
    "report_type": "thematic|flagship|holdings|plus",
    "series": "growth|income|wealth_preservation|null",
    "inferred_sector": "one of: gold energy oil uranium rare_earth copper lithium water ai tech
                        robotics cybersecurity space data_center china japan europe biotech
                        healthcare income consumer gaming drone africa cannabis stablecoin
                        quantum defence — or null",
    "recommendations": [
      {{"ticker":"SYMBOL","company_name":"Full Name","buy_thesis":"why buy","exit_trigger":"or null"}}
    ]
  }}
  Report text:
  ---
  {text}
  ---
  """
  ```
- **GOTCHA**: Holdings reports — top/bottom performers (e.g. "USAR: +85.22%") are the text-visible
  recommendations. Extract them with buy_thesis = "Briefs Fund top performer [month]".
- **GOTCHA**: sys.path inject BEFORE importing sdk_compat.
- **VALIDATE**: Run against Gold's Comeback — confirm KGC + Barrick (B) extracted with theses.

### Task 6: CREATE investments/briefs-finance/scripts/ethical_filter.py

- **IMPLEMENT**: Two-level filter (auto-exclude vs review flag).
  LMT/RTX/NOC etc. → `(True, "Primary defense/military contractor")`.
  BA/PLTR → `(False, "REVIEW: borderline defense exposure")`.
  All others → `(False, None)`.
- **VALIDATE**: `uv run python -c "from scripts.ethical_filter import check_ticker; assert check_ticker('LMT')[0]; assert not check_ticker('AAPL')[0]; print('OK')"`

### Task 7: CREATE investments/briefs-finance/scripts/ingest.py

- **IMPLEMENT**: Orchestration: discover PDFs → hash dedup → extract text → LLM extract →
  ethical filter → upsert report + recommendations.
  CLI: `--path FILE`, `--dry-run`, `--folder SUBFOLDER`.
  Sleep 1s between LLM calls for bulk run.
- **GOTCHA**: Duplicate `1779254685-Profit_from_doge_policies_02_22_25.pdf` caught by content hash.
- **VALIDATE**: `uv run python -m scripts.ingest --dry-run`

### Task 8: CREATE investments/briefs-finance/scripts/prices.py

- **IMPLEMENT**: `get_close_on_or_after(ticker, date)`, `get_close_on_or_before(ticker, date)`,
  `get_sp500_on_or_after(date)`, `compute_return_pct(start, end)`.
  Use `auto_adjust=True`. Return None if `hist.empty`.
  Skip if target within 2 business days of today.
  ASX fallback: if None returned and company looks Australian, retry with "{ticker}.AX".
- **VALIDATE**: `uv run python -c "from scripts.prices import get_close_on_or_after; from datetime import date; print(get_close_on_or_after('KGC', date(2025, 8, 30)))"`

### Task 9: CREATE investments/briefs-finance/scripts/sector_map.py

- **IMPLEMENT**:
  ```python
  def resolve_sector_etf(inferred_sector: str | None) -> str | None:
      """Return primary ETF for sector keyword (first in list), or None."""

  def fetch_sector_prices(etf: str, rec_date: date) -> dict:
      """Returns etf_price_at_rec, etf_price_3m, etf_price_6m, etf_price_12m."""
  ```
  Uses `get_close_on_or_after` from prices.py with dateutil.relativedelta for +3m/+6m/+12m.
  `stock_vs_sector` alpha computed in backtest.py once stock return is also known.
- **GOTCHA**: Use `auto_adjust=False` for index ETFs? No — ETFs are fine with auto_adjust=True.
- **VALIDATE**: `uv run python -c "from scripts.sector_map import resolve_sector_etf; print(resolve_sector_etf('gold'))"`

### Task 10: CREATE investments/briefs-finance/scripts/macro.py

- **IMPLEMENT**: Two-source macro snapshot.

  **yfinance (always, no key)** — use `get_close_on_or_before()` (look BACK to get value AT that date):
  ```python
  def fetch_yfinance_macro(snapshot_date: date) -> dict:
      result = {}
      for key, symbol in MACRO_YFINANCE.items():
          result[key] = get_close_on_or_before(symbol, snapshot_date)
      return result
  ```

  **FRED (optional)** — graceful None if no key:
  ```python
  def fetch_fred_macro(snapshot_date: date) -> dict:
      if not FRED_API_KEY:
          return {k: None for k in FRED_SERIES}
      return {key: fred_value_on(series_id, snapshot_date) for key, series_id in FRED_SERIES.items()}
  ```

  Public function: `fetch_macro_snapshot(snapshot_date: date) -> dict` — merges both sources.

- **GOTCHA**: Macro indicators look BACKWARDS (we want rates ON the recommendation date,
  not after). Use `get_close_on_or_before()`, not `on_or_after()`.
- **GOTCHA**: ^VIX/^TNX/^IRX are indices — use `auto_adjust=False` for these (no corporate actions).
- **GOTCHA**: FRED RECPROUSM156N is monthly. The most recent available value before snapshot_date
  is correct — fred_value_on() with sort_order=desc handles this naturally.
- **VALIDATE**: `uv run python -c "from scripts.macro import fetch_macro_snapshot; from datetime import date; import json; print(json.dumps(fetch_macro_snapshot(date(2025, 8, 30)), indent=2))"`

### Task 11: CREATE investments/briefs-finance/scripts/backtest.py

- **IMPLEMENT**: For every recommendation without an outcome:
  1. Fetch stock prices → return_3m/6m/12m vs S&P 500 → upsert_outcome()
  2. Fetch sector ETF prices → etf_return + stock_vs_sector alpha → upsert_sector_context()
  3. Fetch macro snapshot per report (not per recommendation, skip if already fetched) → upsert_macro_snapshot()

  Sleep 0.5s between yfinance calls. Skip future dates (within 2 business days).

  CLI:
  ```
  uv run python -m scripts.backtest               # all missing
  uv run python -m scripts.backtest --ticker USAR
  uv run python -m scripts.backtest --stats
  ```

  Stats output:
  - Total recs / backtested / pending future dates
  - % beating S&P 500 at 3m / 6m / 12m
  - % where sector ETF rose (thesis validated)
  - % where stock beat its sector ETF (alpha)
  - Best / worst performers with dates and theses
  - Per-sector breakdown

- **GOTCHA**: Macro snapshot is per report. Before fetching, check if report already has one.
- **VALIDATE**: `uv run python -m scripts.backtest --ticker KGC && uv run python -m scripts.backtest --stats`

### Task 12: CREATE principles/ knowledge files (9 files)

- **IMPLEMENT**: One file per investor: `graham.md`, `buffett.md`, `munger.md`, `lynch.md`,
  `fisher.md`, `marks.md`, `dalio.md`, `smith.md`, `neilson.md`.

  Each covers: core philosophy (3-5 bullets), criteria for a GOOD investment, red flags,
  scoring guidance (how to score a one-paragraph buy thesis 0-100).

  Keep each under 400 lines. Criteria must be applicable to Briefs Finance's prose-style theses.
- **VALIDATE**: `(Get-ChildItem investments/briefs-finance/principles/*.md).Count -eq 9`

### Task 13: CREATE investments/briefs-finance/scripts/score.py

- **IMPLEMENT**: Composite 0-100% score — six components via SCORING_WEIGHTS:

  1. **base_rate** (20%): % all backtested picks beating S&P 500 at 6m
  2. **sector_rate** (15%): % picks in this sector beating S&P 500 at 6m
  3. **ticker_history** (15%): this ticker's own historical accuracy (fall back to base_rate if none)
  4. **principles** (20%): average LLM score across all 9 principle files
  5. **macro** (15%): MACRO_SCORE_DEFAULT or .env MACRO_SCORE
  6. **sector_context** (15%): % of times this sector ETF rose over 6m when Briefs recommended in it

  Principles scoring — one LLM call per principle file:
  ```
  Score this thesis against {principle} principles (0-100).
  Thesis: {buy_thesis}
  Framework: {file_content}
  Return ONLY JSON: {{"score": int, "reasoning": "one sentence"}}
  ```

  If fewer than 5 historical outcomes: `provisional=True`, redistribute weights
  (boost principles + macro, reduce base_rate/sector_rate/ticker_history).

  CLI: `--ticker T`, `--report-id N`, `--all`
- **GOTCHA**: LLM is called 9 times per recommendation for principles. Use `model="haiku"` for speed.
- **VALIDATE**: `uv run python -m scripts.score --ticker KGC`

### Task 14: CREATE investments/briefs-finance/scripts/main.py

- **IMPLEMENT**: Unified CLI with argparse subcommands:
  ```
  ingest   [--path F] [--dry-run] [--folder SUBFOLDER]
  backtest [--ticker T] [--stats]
  score    [--ticker T | --report-id N | --all]
  assess   --ticker T          # primary command: full output for new report evaluation
  context  --ticker T          # sector ETF + macro at time of recommendation(s)
  stats                        # Briefs Finance full track record summary
  excluded                     # list all defense-filtered stocks
  ```

  `assess` output delegates all rendering to `report.py`. The `--output` flag controls mode.
- **VALIDATE**: `uv run python -m scripts.main --help`

### Task 14a: CREATE investments/briefs-finance/scripts/report.py

- **IMPLEMENT**: Three output modes, selected via `--output terminal|markdown|html` (default: terminal).

  **Terminal mode** (Rich): coloured panels, tables, progress bars.
  ```python
  from rich.console import Console
  from rich.panel import Panel
  from rich.table import Table

  def render_terminal(assess_data: dict) -> None:
      console = Console()
      console.print(Panel(f"[bold]{assess_data['ticker']}[/bold] — {assess_data['company_name']}", ...))
      # score panel, track record table, sector thesis panel, macro table, principles table
  ```

  **Markdown mode**: writes `assessments/{ticker}-{date}.md` to vault.
  ```python
  def render_markdown(assess_data: dict, output_dir: Path) -> Path:
      # YAML frontmatter + structured markdown sections
      # Returns path written
  ```

  **HTML mode**: fills `templates/stats.html` with Chart.js bar chart (score breakdown),
  performance table, macro panel. Writes to `assessments/{ticker}-{date}.html`.
  ```python
  def render_html(assess_data: dict, template_path: Path, output_dir: Path) -> Path:
      # Simple string substitution into template (no Jinja2 dep)
  ```

  Public function used by main.py:
  ```python
  def render_assess(assess_data: dict, mode: str = "terminal", output_dir: Path | None = None) -> None:
      if mode == "terminal":   render_terminal(assess_data)
      elif mode == "markdown": render_markdown(assess_data, output_dir or ASSESSMENTS_DIR)
      elif mode == "html":     render_html(assess_data, TEMPLATE_PATH, output_dir or ASSESSMENTS_DIR)
  ```

- **GOTCHA**: `assessments/` dir must exist — create with `mkdir(parents=True, exist_ok=True)` on first write.
- **GOTCHA**: HTML template uses `{{PLACEHOLDER}}` tokens (double braces avoid Python format conflict).
- **VALIDATE**:
  ```powershell
  uv run python -m scripts.main assess --ticker KGC --output terminal
  uv run python -m scripts.main assess --ticker KGC --output markdown
  uv run python -m scripts.main assess --ticker KGC --output html
  ```

### Task 15: CREATE .claude/skills/investments/SKILL.md

- **IMPLEMENT**: Thin entry point. Frontmatter description triggers on:
  "check investments", "score this stock", "ingest report", "Briefs Finance", "likelihood score",
  "backtest", "investment assessment", "should I invest in", "sector thesis", "macro context".

  Body: CLI commands, where scripts live (`investments/briefs-finance/scripts/`),
  where DB is (`investments/briefs-finance/data/investments.db`), ethical filter rule.
- **VALIDATE**: File has valid YAML frontmatter with name + description.

### Task 16: CREATE tests

- **IMPLEMENT**:

  `conftest.py`: in-memory SQLite fixture, tmp_path PDF fixtures.

  `test_extract.py`: hash determinism, text returns str, missing file returns ''.

  `test_ethical_filter.py`: LMT excluded, AAPL allowed, BA flagged-not-excluded.

  `test_sector_map.py`:
    - `test_resolve_gold_returns_gdx()` -- "gold" -> "GDX"
    - `test_resolve_unknown_returns_none()` -- "plumbing" -> None
    - `test_resolve_defense_returns_none()` -- "defense" -> None

  `test_macro.py`:
    - `test_fetch_yfinance_macro_returns_dict_with_expected_keys()` -- mock yfinance
    - `test_fred_returns_all_none_without_key()` -- FRED_API_KEY="" -> all None

  `test_db.py`:
    - `test_upsert_report_deduplicates_on_hash()`
    - `test_upsert_sector_context_stores_etf()`
    - `test_upsert_macro_snapshot_stores_rates()`

  `test_backtest.py` (mock yfinance):
    - `test_compute_return_pct()` -- pure math, no network
    - `test_stock_vs_sector_alpha()` -- stock +10%, ETF +5% -> alpha +5%
    - `test_empty_yfinance_returns_none()`

  `test_score.py` (mock DB + LLM):
    - `test_score_in_range()` -- always 0-100
    - `test_provisional_flag_when_few_outcomes()` -- <5 outcomes -> provisional=True
    - `test_sector_context_component_included_in_breakdown()`

  `test_report.py`:
    - `test_render_markdown_creates_file(tmp_path)` -- verify .md written with frontmatter
    - `test_render_html_creates_file(tmp_path)` -- verify .html written with ticker in content
    - `test_render_terminal_does_not_raise()` -- smoke test Rich output with mock data

- **VALIDATE**: `uv run pytest scripts/tests/ -v`

### Task 17: BULK INGEST + BACKTEST

- **RUN IN ORDER**:
  ```powershell
  cd investments/briefs-finance
  uv run python -m scripts.main ingest       # ~5-10 min (84 LLM calls, 1s sleep each)
  uv run python -m scripts.main backtest     # ~20-30 min (3-4 yfinance calls per rec)
  uv run python -m scripts.main stats        # verify track record
  uv run python -m scripts.main assess --ticker KGC  # verify full output
  ```
- **VALIDATE**: stats shows non-zero counts, sector context and macro present in assess output.

---

## TESTING STRATEGY

### Unit Tests
In-memory SQLite, mocked yfinance + LLM, no real network.
Covers: extract, filter, sector map, macro (no-key path), DB upsert, return math, score.

### Integration Tests (manual)
Single PDF end-to-end with real yfinance: `ingest -> backtest -> assess` for KGC (Gold's Comeback Aug 2025).
Verify GDX sector context populated. Verify macro snapshot non-NULL. Verify 0-100 score produced.

### Edge Cases
- PDF no tickers -> empty recommendations, report stored
- Ticker not in yfinance -> NULL outcomes, score falls back to base_rate
- No sector match -> sector_context NULL, weight redistributed to macro
- FRED_API_KEY absent -> FRED columns NULL, no error raised
- Report date in future (within 2 days) -> outcome skipped
- Duplicate PDF -> hash match, silent skip
- Defense-only report -> all recs excluded=1, report stored

---

## VALIDATION COMMANDS

### Level 1: Syntax
```powershell
cd investments/briefs-finance
uv run ruff check scripts/
uv run mypy scripts/ --ignore-missing-imports
```

### Level 2: Unit Tests
```powershell
uv run pytest scripts/tests/ -v
```

### Level 3: Smoke Test (single PDF)
```powershell
uv run python -m scripts.main ingest --path "reports/pro-2026/1781550652-Golds_Comeback_May_30.pdf"
uv run python -m scripts.main backtest --ticker KGC
uv run python -m scripts.main assess --ticker KGC
```

### Level 4: Macro Verification
```powershell
uv run python -c "from scripts.macro import fetch_macro_snapshot; from datetime import date; import json; print(json.dumps(fetch_macro_snapshot(date(2025, 8, 30)), indent=2))"
```

### Level 5: Full Bulk Run
```powershell
uv run python -m scripts.main ingest
uv run python -m scripts.main backtest
uv run python -m scripts.main stats
```

---

## ACCEPTANCE CRITERIA

- [ ] `uv sync` completes cleanly
- [ ] `uv run pytest scripts/tests/ -v` all tests pass
- [ ] `uv run ruff check scripts/` zero errors
- [ ] Single PDF ingest extracts at least one ticker (KGC from Gold's Comeback)
- [ ] KGC outcome: price_at_rec, return_6m, vs_sp500_6m all non-NULL
- [ ] GDX sector context populated for KGC (gold sector ETF)
- [ ] Macro snapshot: treasury_10y, vix, gold non-NULL for Aug 2025 report
- [ ] LMT auto-excluded if it appears in a report
- [ ] `assess --ticker KGC --output terminal` renders Rich panels without error
- [ ] `assess --ticker KGC --output markdown` writes `assessments/KGC-*.md` with YAML frontmatter
- [ ] `assess --ticker KGC --output html` writes `assessments/KGC-*.html` with Chart.js score breakdown
- [ ] `assess --ticker KGC` (default) includes sector context and macro sections
- [ ] FRED columns NULL (not error) when FRED_API_KEY not set
- [ ] Duplicate PDF silently skipped on second ingest
- [ ] `stats` shows % beating S&P 500 AND % where sector thesis played out
- [ ] SKILL.md has valid YAML frontmatter with correct CLI command references

---

## NOTES

**FRED API key**: Free at fred.stlouisfed.org. Add as `FRED_API_KEY=your_key` in
`investments/briefs-finance/.env`. Tool works without it; yield curve + recession
probability columns will be NULL.

**Macro score (manual)**: `MACRO_SCORE=50` in .env is a neutral placeholder. Update based
on current cycle — e.g. `MACRO_SCORE=35` in high-recession-risk environment, `MACRO_SCORE=70`
when conditions are favourable. This is your editorial input to the scoring model.

**Sector context scoring**: `sector_context_component` asks "when Briefs has historically
recommended stocks in this sector, what % of the time did the sector ETF rise over 6 months?"
This validates whether Briefs picks sectors with sector-level tailwinds, separate from
whether the individual stock was good. Sector skill + stock skill together explain full alpha.

**Macro indicators use on_or_before**: Unlike price data (look forward to find next trading day),
macro snapshots look BACKWARD to find the most recent value AT or before the recommendation date.

**Running the tool**: Always `cd investments/briefs-finance` first. This tool has its own
uv environment, separate from `.claude/scripts/`.

**Display modes**: `--output terminal` (default) uses Rich for coloured panels and tables in the terminal. `--output markdown` saves a structured `.md` file to `assessments/` for vault storage. `--output html` generates a self-contained HTML report with Chart.js score breakdown chart — open in any browser. All three modes write the same data; only the presentation differs.

**OCR deferred**: Holdings full position table is an image. Current ingestion captures top/bottom
performers and analyst notes from text. OCR upgrade is a future iteration.

**Confidence Score**: 7/10. Risks: (a) LLM extraction quality on prose (mitigated by retry +
JSON validation); (b) some sector ETF mappings are proxies not perfect matches; (c) scoring
weights are provisional until 12+ months of backtested outcomes available for calibration.
