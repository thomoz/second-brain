---
name: investments
description: >
  Briefs Finance investment research tool. Ingests PDF reports, backtests historical
  picks against real market data (yfinance), and produces 0-100% likelihood scores for
  new recommendations. Applies ethical filter (no defense/military stocks). Covers
  sector ETF thesis validation, macro snapshots, and 9 investor principles evaluations.
  Triggers on: "check investments", "score this stock", "ingest report", "Briefs Finance",
  "likelihood score", "backtest", "investment assessment", "should I invest in",
  "sector thesis", "macro context", "assess KGC", "track record".
---

# Investments Skill

Briefs Finance investment analysis tool. All output is for Shaun's review only — nothing acts autonomously.

## Quick Reference

```powershell
# Always run from the briefs-finance directory
cd investments/briefs-finance

# Ingest PDFs
uv run python -m scripts.main ingest                              # all PDFs
uv run python -m scripts.main ingest --path "reports/pro-2026/1781550652-Golds_Comeback_May_30.pdf"
uv run python -m scripts.main ingest --folder pro-2025           # specific subfolder
uv run python -m scripts.main ingest --dry-run                   # preview only

# Backtest historical picks
uv run python -m scripts.main backtest                            # all missing outcomes
uv run python -m scripts.main backtest --ticker KGC              # single ticker
uv run python -m scripts.main backtest --stats                   # track record summary

# Score recommendations
uv run python -m scripts.main score --ticker KGC
uv run python -m scripts.main score --all

# Full assessment (primary command)
uv run python -m scripts.main assess --ticker KGC                # terminal (default)
uv run python -m scripts.main assess --ticker KGC --output markdown   # vault .md
uv run python -m scripts.main assess --ticker KGC --output html       # Chart.js HTML

# Other commands
uv run python -m scripts.main context --ticker KGC               # sector + macro context
uv run python -m scripts.main stats                              # full track record
uv run python -m scripts.main excluded                           # list defense-filtered stocks
```

## Key Paths

- Scripts: `investments/briefs-finance/scripts/`
- Database: `investments/briefs-finance/data/investments.db`
- Reports (PDFs): `investments/briefs-finance/reports/` (pro-2025/, pro-2026/, holdings/, plus/)
- Principles: `investments/briefs-finance/principles/` (9 investor framework files)
- Assessments output: `investments/briefs-finance/assessments/`

## Ethical Filter

Defense/military primary contractors are **auto-excluded** at ingestion time:
LMT, RTX, NOC, GD, HII, LHX, LDOS, SAIC, CACI, KTOS, AVAV, BWXT, TXT, HEICO, TDG, CW, DRS

BA and PLTR are **flagged for review** but not excluded.

Excluded stocks are stored in the DB with `excluded=1` and never appear in scoring or assessments.

## Scoring Model (0-100%)

Six weighted components:
| Component | Weight | Source |
|-----------|--------|--------|
| base_rate | 20% | % all Briefs picks beating S&P at 6m |
| sector_rate | 15% | % picks in this sector beating S&P at 6m |
| ticker_history | 15% | This ticker's own accuracy |
| principles | 20% | LLM scores against 9 investor frameworks |
| macro | 15% | MACRO_SCORE from .env (manual editorial input) |
| sector_context | 15% | % times sector ETF rose when Briefs picked this sector |

Set `MACRO_SCORE` in `investments/briefs-finance/.env` to reflect current market conditions:
- 35 = high recession risk
- 50 = neutral (default)
- 70 = favourable conditions

## Setup (first time)

```powershell
cd investments/briefs-finance
uv sync
# Optional: add FRED_API_KEY to .env for yield curve + recession data
# Get free key at fred.stlouisfed.org
```
