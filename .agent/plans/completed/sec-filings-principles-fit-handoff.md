# Handoff: Read SEC Filings Into Find's Principles-Fit Check

## Status: Not started — scoping/discovery conversation only, no code written yet

## Context

`my-trader`'s Find tool (`investments/my-trader/mytrader/`) assesses a ticker via 10
checks driven entirely by `yfinance`'s pre-computed summary stats (PE, ROE,
debt/equity, dividend history, price history) — never the company's own primary-source
documents. A `principles_fit` check was added 2026-08-02 (same session as this
handoff) that grades a Find-generated summary against the 9 investor-framework files
in `investments/briefs-finance/principles/*.md` (Buffett, Graham, Lynch, Munger,
Dalio, Marks, Fisher, Smith, Neilson), reusing
`briefs-finance/scripts/score.py::score_thesis_against_principle()`. See
`investments/my-trader/mytrader/checks/principles_fit.py` for the current
implementation — it's fully live and tested (8 tests, full suite 219 passing).

Discussing that check led to: "what would an expert investor actually read before
investing in a company?" Answer, worked through with Shaun in conversation: for the
six bottom-up frameworks (Buffett/Graham/Lynch/Munger/Fisher/Smith), it's the primary
filing documents — 10-K (Business, Risk Factors, MD&A) and 10-Q — not Yahoo's derived
ratios. Dalio/Marks lean more macro/cycle (partially already covered by Monitor's
existing 9 macro indicators, not wired per-ticker). Shaun's framing for this build:
**"we want a tool that approximates an expert investor."**

Key facts established in conversation (don't re-litigate these):
- 10-K/10-Q are genuinely free, legally mandated, public documents via SEC EDGAR — no
  API key, just a descriptive `User-Agent` header per SEC's fair-access policy.
- Earnings call transcripts are explicitly OUT OF SCOPE for this build — the call
  itself is legally required to be public (Reg FD) but a written transcript is not;
  getting one free means audio transcription (real added engineering) or a paid
  third-party API (Seeking Alpha/AlphaSense-style). Shaun confirmed: "No need for
  audio — just want access to the documents."
- **SEC EDGAR User-Agent to use: `"Shaun Thomson thomoz@outlook.com"`** — confirmed by
  Shaun, goes in every request header per SEC's policy.

## Scope (agreed in conversation)

- **Documents**: 10-K and 10-Q, most recent filing of each. Not historical filings,
  not transcripts, not proxy statements (DEF 14A) — those were mentioned as part of a
  general "what would an expert read" answer but never explicitly brought into scope;
  worth asking Shaun whether proxy statements (exec comp/insider alignment — relevant
  to Buffett/Munger's incentive-alignment criteria) belong in v1 or a later pass.
- **Universe**: US-listed tickers only (SEC EDGAR doesn't cover ASX/LSE/etc — BXB.AX,
  WES.AX, VOLV-B.ST and similar non-US watchlist names would degrade gracefully to
  today's stats-only behavior, same pattern `concentration.py`/`etf_mechanics.py`
  already use for missing data).
- **Sections extracted**: Item 1 (Business), Item 1A (Risk Factors), Item 7 (MD&A) —
  the parts of a 10-K that actually inform a Buffett/Graham/Lynch-style read, not the
  full document (financial statement tables are already covered numerically by
  Find's existing yfinance-based checks).

## Remaining Steps (for /plan-feature to detail — this handoff is discovery, not a plan)

### 1. SEC EDGAR fetch pipeline — new module, likely `mytrader/sec_filings.py`
Model this on `mytrader/abs_cpi.py`'s style (direct-from-government-source fetch, no
third-party wrapper library, `requests` + explicit User-Agent, graceful `None` return
on any failure) rather than introducing a new dependency.

Endpoints (all free, no key, `User-Agent: "Shaun Thomson thomoz@outlook.com"` required
on every request):
- Ticker → CIK: `https://www.sec.gov/files/company_tickers.json` (one bulk file,
  covers every US-listed ticker — cache this mapping locally rather than
  re-downloading per lookup)
- Company's filing list: `https://data.sec.gov/submissions/CIK{10-digit zero-padded}.json`
  — has `filings.recent` arrays with form type, accession number, filing date, and
  primary document filename. Find the most recent entries where `form == "10-K"` /
  `"10-Q"`.
- Actual filing document:
  `https://www.sec.gov/Archives/edgar/data/{CIK no padding}/{accession no dashes}/{primary document filename}`
  — an HTML document, needs tag-stripping + Item-header section splitting.

**Real technical risk to flag for /plan-feature**: 10-K HTML formatting is not
strictly standardized across filers/years — Item-header text-matching (`"Item 1."`,
`"Item 1A."`, `"Item 7."`) is a heuristic, not a guarantee. Needs testing against a
handful of real filings (pick 3-4 tickers already in the watchlist, e.g. AMZN, KO,
UBER, CPRT) before trusting it broadly. Have a defined fallback (skip the section,
don't crash the whole check) when a section can't be located.

SEC's stated rate limit is ~10 requests/second — not a concern at Find's call
frequency (one ticker at a time, on-demand), but worth a small delay/backoff if this
ever gets called in a loop (e.g. if Monitor ever opts in later).

### 2. Summarization pass — new LLM call, model tier TBD
Item 1A (Risk Factors) and Item 7 (MD&A) can each run 10-20 pages raw — too long and
too noisy (boilerplate legal hedging) to feed directly into the 9 short principle-
grading calls. Needs one summarization call per filing that condenses
Business+Risk Factors+MD&A into a focused, investment-relevant summary (a few hundred
words) before anything else touches it.

**Open question for Shaun**: which model tier for this summarization call? The 9
principle-grading calls already confirmed fine on `"haiku"` (→ `gpt-5.4-mini` on this
repo's active Codex backend, see `.claude/scripts/codex_sdk_compat.py`) because
they're short, structured, single-file-vs-thesis comparisons. Faithfully compressing
a real 10-K's Risk Factors section without dropping the material caveats is a
different, harder task — worth deliberately testing `"sonnet"`/mid tier against
`"haiku"`/cheap tier on a real filing before defaulting to the cheap option just
because it's cheap. All LLM calls must go through `sdk_compat` per
`CLAUDE.md`'s model-agnostic architecture rule — do not import a backend SDK directly.

### 3. Caching — new DB table, NOT the same caching rule as `principles_fit`
`principles_fit` (built this session) deliberately recomputes fresh every Find call,
because its input (live stats) changes constantly — see that file's docstring.
**Filing text is the opposite**: a 10-K doesn't change until the next one is filed, so
re-fetching + re-summarizing a 20-page document on every Find call would be pure
waste. Add a real cache table via `mytrader/db.py`'s `init_mytrader_tables()` (follow
the existing `_ensure_watchlist_return_columns`-style additive-migration pattern),
keyed on `(ticker, filing_type, accession_number)`, storing the summary text and
fetch timestamp. Only re-fetch when the filing index shows a newer accession number
than what's cached.

### 4. Wire into `principles_fit.py`
**Open question for Shaun, not yet decided** — two options were on the table when
this handoff was written:
- **(a) Augment `_build_thesis()`** — fold the filing summary into the same thesis
  text that already carries live stats, so all 9 principle files get graded against
  one richer combined picture. This was the direction the conversation was heading
  (directly "closes the gap" discussed), but not explicitly re-confirmed after the
  SEC-legal-requirements tangent.
- **(b) New standalone check** — keep `principles_fit` exactly as-is (stats-only,
  fast, always available even for non-US tickers), add a separate check/section for
  the filing-grounded read. More total output, but keeps the two signals
  distinguishable (e.g. if the filing-based grade and the stats-based grade disagree,
  that disagreement itself might be informative).

Confirm with Shaun before implementing either way.

### 5. Tests
Follow the existing pattern (`tests/test_checks_principles_fit.py`,
`tests/test_checks_opportunity.py`) — mock the SEC HTTP calls and the summarization
LLM call via `monkeypatch`, same style as `test_engine.py` mocks
`scripts.score.compute_score` / `scripts.backtest.run_backtest`. Need at least: CIK
lookup miss (non-US ticker) degrades gracefully, section-extraction on a real sample
10-K fixture (saved HTML snippet, not a live fetch in tests), cache hit skips
re-fetch, cache miss on new accession number triggers re-fetch.

## Validation (once built)

```powershell
uv run --directory investments/my-trader python -m pytest mytrader/tests -q
uv run --directory investments/my-trader ruff check mytrader/
uv run --directory investments/my-trader mypy mytrader/sec_filings.py mytrader/checks/principles_fit.py

# Live smoke test against a real US ticker already in the watchlist
uv run --directory investments/my-trader python -m mytrader.main find --ticker KO
```

## Open Questions for Shaun (resolve before/during `/plan-feature`)

1. Proxy statements (DEF 14A — exec comp, insider ownership) in scope for v1, or
   10-K/10-Q only?
2. Summarization LLM tier — test `"sonnet"` vs `"haiku"` quality on a real filing
   before deciding, or default to cheap and revisit if it's visibly bad?
3. Integration model — augment `principles_fit`'s existing thesis (recommended in
   conversation) vs. a new standalone check?
4. Any other US tickers besides AMZN/KO/UBER/CPRT worth testing Item-header
   extraction against, to catch formatting edge cases early?
