# Briefs Finance Tool — Usage Instructions

## Initial Setup (run once, ~45 min)

```powershell
cd investments/briefs-finance

# Step 1: Read all 84 PDFs, call LLM to extract tickers and theses (will take a while - only needs to be done once)
uv run python -m scripts.main ingest

# Step 2: Fetch historical prices for every extracted ticker from yfinance
uv run python -m scripts.main backtest
```

## Check any company

```powershell
uv run python -m scripts.main assess --ticker KGC
```

Add `--output markdown` to save to `assessments/` vault, or `--output html` for a Chart.js report.

## When a new Briefs Finance report arrives

Drop the PDF into the relevant subfolder (`reports/pro-2026/` etc.) then:

```powershell
uv run python -m scripts.main ingest --path "reports/pro-2026/new_report.pdf"
uv run python -m scripts.main backtest --ticker NEWT
uv run python -m scripts.main assess --ticker NEWT
```

## Once a month (optional)

```powershell
uv run python -m scripts.main backtest
```

Picks up 3m/6m/12m return windows as they become available for older recommendations.

## Other commands

```powershell
uv run python -m scripts.main stats        # Briefs Finance full track record
uv run python -m scripts.main excluded     # list defense-filtered stocks
uv run python -m scripts.main context --ticker KGC   # sector ETF + macro at time of tip
```

## Notes

- Scores show `provisional: True` until enough backtested outcomes accumulate
- Set `MACRO_SCORE` in `.env` to reflect current conditions (35 = recession risk, 50 = neutral, 70 = favourable)
- FRED yield curve + recession data requires a free key at fred.stlouisfed.org — add as `FRED_API_KEY` in `.env`
- Defense/military stocks (LMT, RTX, NOC etc.) are auto-excluded at ingestion; BA and PLTR are flagged for review
