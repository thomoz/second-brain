# Briefs Finance — Session Handoff

## What This Is

A local investment research tool that ingests Briefs Finance PDF reports, extracts stock
recommendations with an LLM, backtests them against real yfinance price data, applies an
ethical filter (no defense/military stocks), and produces a 0–100 likelihood score per ticker.
Advisor mode only — no autonomous trading.

## Directory Layout

```
investments/briefs-finance/
├── scripts/              # All Python source (treated as a package)
│   ├── config.py         # ALL path constants + scoring weights + ETF map + filters
│   ├── db.py             # 7-table SQLite schema + upsert helpers
│   ├── extract.py        # PDF text extraction (pdfplumber) + SHA-256 hash
│   ├── llm_extract.py    # LLM call to parse tickers/thesis from raw text (3x retry)
│   ├── ethical_filter.py # Defense exclusion + review flagging
│   ├── ingest.py         # Orchestration: discover PDFs → hash dedup → extract → upsert
│   ├── prices.py         # yfinance wrappers: get_close_on_or_after, compute_return_pct
│   ├── sector_map.py     # resolve_sector_etf() → ETF ticker; fetch_sector_prices()
│   ├── macro.py          # fetch_macro_snapshot(): yfinance proxies + optional FRED
│   ├── backtest.py       # run_backtest(): outcomes + sector_context per rec; print_stats()
│   ├── score.py          # compute_score(): 6-component composite (see Scoring section)
│   ├── report.py         # assess_ticker(): terminal (Rich) / markdown / html (Chart.js)
│   ├── main.py           # argparse CLI — all commands live here
│   └── tests/            # 50 unit tests, all green
├── principles/           # 9 investor principle .md files (graham, buffett, munger, …)
├── reports/              # PDF reports — 84 files already present
│   ├── pro-2025/         # ~80 PDFs
│   └── pro-2026/
├── data/                 # SQLite DB lives here (gitignored)
│   └── investments.db    # Created on first init_db() call
├── assessments/          # Markdown/HTML output from `assess --output markdown/html`
├── scripts/templates/
│   └── stats.html        # Chart.js dark-theme bar chart template
├── pyproject.toml        # uv project; pytest pythonpath=["."]; ruff excludes legacy files
├── .env.example          # FRED_API_KEY (optional), MACRO_SCORE (default 50)
├── instructions.md       # User-facing workflow guide (4 scenarios)
└── HANDOFF.md            # This file
```

## Data Flow (end to end)

```
PDF reports/
    └─ ingest.py
         ├─ extract.py       → raw text + SHA-256 hash
         ├─ llm_extract.py   → [{ticker, company, buy_thesis, exit_trigger, sector}]
         ├─ ethical_filter.py → mark excluded / flag for review
         └─ db.py            → reports + recommendations tables

    └─ backtest.py
         ├─ prices.py        → stock price at rec date + 3m/6m/12m + S&P 500 benchmark
         ├─ sector_map.py    → sector ETF prices at same windows
         ├─ macro.py         → macro snapshot at report date
         └─ db.py            → outcomes + sector_context + macro_snapshot tables

    └─ score.py / assess ticker
         ├─ DB queries       → base_rate, sector_rate, ticker_history, sector_context
         ├─ LLM (haiku ×9)  → principles_evaluations table
         └─ db.py            → likelihood_scores table

    └─ report.py
         └─ terminal / markdown (assessments/*.md) / html (assessments/*.html)
```

## CLI Quick Reference

```powershell
# From: investments/briefs-finance/
# Or prefix with Push-Location + Pop-Location to avoid changing CWD

uv run python -m scripts.main ingest                         # all PDFs (hash-dedup)
uv run python -m scripts.main ingest --path reports/pro-2026/report.pdf
uv run python -m scripts.main ingest --dry-run               # preview only

uv run python -m scripts.main backtest                       # all recs
uv run python -m scripts.main backtest --ticker KGC          # one ticker
uv run python -m scripts.main backtest --stats               # track record table

uv run python -m scripts.main score --ticker KGC             # score + print breakdown
uv run python -m scripts.main score --all                    # score everything

uv run python -m scripts.main assess --ticker KGC            # terminal Rich output
uv run python -m scripts.main assess --ticker KGC --output markdown
uv run python -m scripts.main assess --ticker KGC --output html

uv run python -m scripts.main context --ticker KGC           # macro + sector at rec date
uv run python -m scripts.main stats                          # full track record
uv run python -m scripts.main excluded                       # defense-filtered list
```

## Scoring Model (6 components → 0-100)

| Component       | Weight | Source                                      |
|----------------|--------|---------------------------------------------|
| base_rate      | 20%    | % all Briefs picks beating S&P 500 at 6m   |
| sector_rate    | 15%    | % picks in this sector beating S&P 500 @6m |
| ticker_history | 15%    | % prior picks of this exact ticker @6m      |
| principles     | 20%    | Avg of 9 LLM principle scores (haiku)       |
| macro          | 15%    | `MACRO_SCORE` env var (default 50)          |
| sector_context | 15%    | % times sector ETF rose when sector tipped  |

**Provisional flag**: when <5 total historical outcomes exist, base_rate/sector_rate/ticker_history
weights each drop to 5%, and the freed weight redistributes to principles (50%) + macro (25%) +
sector_context (25%).

## Ethical Filter

- `DEFENSE_TICKERS` (17 auto-excluded): LMT, RTX, NOC, GD, HII, LHX, LDOS, SAIC, CACI, KTOS, AVAV, BWXT, TXT, HEICO, TDG, CW, DRS
- `DEFENSE_REVIEW_TICKERS` (flagged, not excluded): BA, PLTR
- `.AX` suffix is stripped before comparison; input is uppercased
- Exclusions happen at ingest time and are stored in `recommendations.excluded=1`

## Sector ETF Map (30 sectors)

Lives in `config.py:SECTOR_ETF_MAP`. Key mappings:
- gold → GDX/GLD, energy → XLE/XOP, uranium → URA, ai → XLK/BOTZ
- defence/defense → `None` (no ETF; sector_context_score defaults to 50)

## Key Paths in config.py

```python
_HERE = Path(__file__).resolve().parent          # scripts/
PROJECT_ROOT = _HERE.parent.parent.parent        # repo root (3 levels up)
INVESTMENTS_DIR = PROJECT_ROOT / "investments" / "briefs-finance"
DATA_DIR     = INVESTMENTS_DIR / "data"
DB_PATH      = DATA_DIR / "investments.db"
REPORTS_DIR  = INVESTMENTS_DIR / "reports"
PRINCIPLES_DIR = INVESTMENTS_DIR / "principles"
TEMPLATES_DIR  = _HERE / "templates"
```

**Critical**: `PROJECT_ROOT` is `_HERE.parent.parent.parent` (3 `.parent` from the `scripts/`
dir). `llm_extract.py` and `score.py` use `Path(__file__).resolve().parent.parent.parent.parent`
(4 `.parent` from the file itself — same depth, correct).

## LLM / sdk_compat Integration

```python
_SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent.parent / ".claude" / "scripts"
sys.path.insert(0, str(_SCRIPTS_DIR))
from sdk_compat import ClaudeAgentOptions, run_text  # noqa: E402
```

- `llm_extract.py`: calls LLM to extract recommendations from raw PDF text
- `score.py`: calls LLM with `model="haiku"` for each of the 9 principle files
- Backend is controlled by `SB_AGENT_BACKEND` env var (currently Codex)

## Macro Data Sources

```python
MACRO_YFINANCE = {
    "treasury_10y": "^TNX", "tbill_3m": "^IRX", "vix": "^VIX",
    "gold": "GLD", "usd": "UUP", "bonds_20y": "TLT",
}
```
- `fetch_macro_snapshot()` looks BACKWARD from the report date (uses `get_close_on_or_before`)
- Indices use `auto_adjust=False` — important for ^TNX/^IRX/^VIX
- FRED (yield curve, recession prob, CPI, fed funds) is optional; gracefully returns None if no key

## Tests

```powershell
Push-Location investments/briefs-finance
uv run pytest scripts/tests/ -v
Pop-Location
```

50 tests, all pass. In-memory SQLite (tmp_path), mocked yfinance, mocked LLM calls.
Patch target for macro tests: `scripts.macro.get_close_on_or_before` (not `scripts.prices.` —
macro.py has a bound import name).

## Known Gotchas

1. **PowerShell CWD**: Never `cd` or `Set-Location` to `investments/briefs-finance/` and leave it
   there. The `block-secrets.py` PreToolUse hook resolves `.claude/` relative to CWD — if CWD has
   no `.claude/`, every tool call will fail. Use `Push-Location`/`Pop-Location` in a single PS call,
   or pass `--path` with absolute paths. Always `Set-Location` back to repo root before Read/Edit.

2. **Ruff exclude**: `inspect_monthly.py` and `update_plan.py` are pre-existing scripts with their
   own import patterns that break ruff. They are in `[tool.ruff.lint.per-file-ignores]` + exclude.
   Don't touch them unless specifically asked.

3. **PDF FontBBox warnings**: `extract.py` suppresses pdfplumber's `FontBBox` warnings via
   `warnings.filterwarnings("ignore", message=".*FontBBox.*")` — this is intentional.

4. **`assess` calls `score` internally**: `report.py:assess_ticker()` calls `compute_score()` if no
   cached score exists. So `assess --ticker X` is safe to run even if `score` hasn't been run first.

## Current State (as of 2026-06-23)

- **Code**: complete — all 7 pipeline stages built and tested
- **Bulk ingest**: NOT YET RUN — 84 PDFs are present but the DB is empty
- **Backtest**: NOT YET RUN — depends on ingest completing first
- **Initial setup time**: ~45 min total (1s sleep between LLM calls × ~84 PDFs + yfinance calls)

To kick it off:
```powershell
Push-Location investments/briefs-finance
uv run python -m scripts.main ingest      # ~45 min
uv run python -m scripts.main backtest    # ~10-15 min
uv run python -m scripts.main stats
uv run python -m scripts.main assess --ticker KGC
Pop-Location
```

## Ideas / Possible Extensions

- Add a `watchlist` command that scores every ticker in a user-defined list and ranks by score
- Add `--since YYYY-MM-DD` filter to `ingest` to only process recent PDFs
- Persist `MACRO_SCORE` overrides in the DB per scoring run rather than env var only
- Add a `compare --tickers KGC,WPM,AGI` mode for side-by-side terminal output
- Sector performance heatmap HTML report across all sectors Briefs has covered
