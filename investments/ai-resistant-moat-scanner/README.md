# AI-Resistant Moat Scanner

Ranks US-listed public companies by how **AI-durable their embedded-software moat** is
— the Salesforce property: software so engrained in the customer's operations that the
ROI of building an AI replacement doesn't make sense.

The score is a blended 0–100 number: half quantitative (yfinance `.info` — gross /
FCF / operating margin, Rule of 40, revenue durability, disclosed recurring revenue),
half qualitative (an LLM grading a fixed 6-part rubric against the latest 10-K's
Business + Risk Factors sections). Blend is 50/50; `MOAT_STAGE_THRESHOLD` (80) is the
staging cutoff — tune it down after the first live run.

## Output

- `moat-scan-report.md` — full ranked table (moat / quant / qual, the six rubric
  sub-scores, anti-signals, thesis, tags).
- `moat-candidates-pending-review.md` — fresh names scoring ≥ 80 that aren't already
  held / watchlisted / staged. A fresh staged name fires one WhatsApp + toast titled
  **"AI-Resistant Moat Alert"**; zero-candidate days are silent.

## Running it

Daily on the VPS at **23:30 UTC** via `second-brain-ai-moat-scan.timer` (after the
22:45 Goat Heartbeat so they don't contend for yfinance). Each run scores 1/5 of the
screened universe (rotating by calendar date) plus every seed name plus every
currently-staged name; the expensive per-filing LLM work is cached per
`(ticker, accession_number, rubric_version)`.

All manual runs go through the SSH wrapper — never `uv run --directory` locally
(that creates an empty local `investments.db`):

```
scripts/invoke_investments.ps1 -Package ai-resistant-moat-scanner -Command "scan"
scripts/invoke_investments.ps1 -Package ai-resistant-moat-scanner -Command "promote-candidate --ticker TICKER"
scripts/invoke_investments.ps1 -Package ai-resistant-moat-scanner -Command "dismiss-candidate --ticker TICKER"
```

`promote-candidate` is the one deliberate cross-package write — it adds a row to
my-trader's watchlist (`source="ai_resistant_moat"`, thesis in the notes) and
regenerates `watchlist.md`, exactly as goat's promote does.

## Dated caveat

The AI-resistance rubric (`config.RUBRIC_VERSION`, currently `2026-09`) encodes a
2026 view of what AI can and cannot cheaply rebuild. Revisit it periodically; bump
`RUBRIC_VERSION` when the rubric text changes and every cached sub-score is
re-computed on the next run.
