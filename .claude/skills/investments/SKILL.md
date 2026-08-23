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

`investments.db` lives only on the VPS now (no more local copy — see "Where This Runs"
below). Every command runs via the SSH wrapper:

```powershell
# Ingest PDFs already present on the VPS
.\scripts\invoke_investments.ps1 -Package briefs-finance -Command "ingest"                              # all PDFs
.\scripts\invoke_investments.ps1 -Package briefs-finance -Command "ingest --path reports/pro-2026/1781550652-Golds_Comeback_May_30.pdf"
.\scripts\invoke_investments.ps1 -Package briefs-finance -Command "ingest --folder pro-2025"           # specific subfolder
.\scripts\invoke_investments.ps1 -Package briefs-finance -Command "ingest --dry-run"                   # preview only

# Ingesting a PDF that only exists locally: scp it up first (see "Ingesting a New PDF" below),
# then run --path against the path it landed at on the VPS

# Backtest historical picks
.\scripts\invoke_investments.ps1 -Package briefs-finance -Command "backtest"                            # all missing outcomes
.\scripts\invoke_investments.ps1 -Package briefs-finance -Command "backtest --ticker KGC"              # single ticker
.\scripts\invoke_investments.ps1 -Package briefs-finance -Command "backtest --stats"                   # track record summary

# Score recommendations
.\scripts\invoke_investments.ps1 -Package briefs-finance -Command "score --ticker KGC"
.\scripts\invoke_investments.ps1 -Package briefs-finance -Command "score --all"

# Full assessment (primary command)
.\scripts\invoke_investments.ps1 -Package briefs-finance -Command "assess --ticker KGC"                # terminal (default)
.\scripts\invoke_investments.ps1 -Package briefs-finance -Command "assess --ticker KGC --output markdown"   # vault .md
.\scripts\invoke_investments.ps1 -Package briefs-finance -Command "assess --ticker KGC --output html"       # Chart.js HTML

# Other commands
.\scripts\invoke_investments.ps1 -Package briefs-finance -Command "context --ticker KGC"               # sector + macro context
.\scripts\invoke_investments.ps1 -Package briefs-finance -Command "stats"                              # full track record
.\scripts\invoke_investments.ps1 -Package briefs-finance -Command "excluded"                           # list defense-filtered stocks
```

## Ingesting a New PDF

The source PDF is the one input in this skill that starts out local. Copy it to the
VPS's matching subfolder first, then ingest it by its VPS-side path:

```powershell
scp "<local path to PDF>" secondbrain@137.184.102.104:/home/secondbrain/second-brain/investments/briefs-finance/reports/<subfolder>/
.\scripts\invoke_investments.ps1 -Package briefs-finance -Command "ingest --path reports/<subfolder>/<filename>.pdf"
```

`<subfolder>` (`pro-2025`, `pro-2026`, `holdings`, `plus`) is a conscious placement
choice, same as it always was — pick the same one you would have used locally.

## Where This Runs

`investments.db` (`investments/briefs-finance/data/investments.db`) exists in exactly
one place: the VPS. It is gitignored and never opened by a process on Shaun's Windows
machine — two independently-writable local/VPS copies kept jamming git on unmergeable
binary diffs (recurring incident, fixed 2026-08-23, see
`.agent/plans/investments-db-ssh-single-source.md`). All commands above run *on* the
VPS via `scripts/invoke_investments.ps1`, which streams output back live and propagates
the remote exit code.

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
