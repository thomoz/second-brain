"""Goat Hated Industries Scanner -- contrarian counterpart to industry_rotation.py,
per investments/hated-industries-scanner-handoff.md and
.agent/plans/hated-industries-scanner.md.

Finds industries suffering severe, still-live price underperformance vs. SPY (both a
3-month and 6-month window), a meaningful drawdown from their 52-week high, and no
sign of an already-started recovery -- Shaun's own framing (2026-09-16) is to catch
live pessimism before the reversal, not after it. Reuses industry_rotation.py's
existing 39-industry-ETF universe and fetch as-is.

Two extra reads run only for industries that clear the severity gate (bounds the
LLM/search cost to a handful of names a day):

  - classify_industry_narrative() -- an sdk_compat.run_text + WebSearch call, same
    mechanism as mytrader/news_search.py, industry-scoped instead of ticker-scoped.
    Returns the dominant negative narrative, whether it reads as industry-wide or
    concentrated in one/two large constituents, and the ETF's top holdings (folded
    into this one call rather than a static seed table -- see the plan's NOTES for
    why).
  - check_fundamentals_divergence() -- pulls revenueGrowth/earningsGrowth for the
    narrative call's returned constituents to check whether the underlying
    businesses actually got worse, or just the price.

Purely advisory -- no verdict, no ticker staging into goat_pending_candidates
(confirmed with Shaun 2026-09-16). A goat_hated_industries_seen table dedups
WhatsApp/toast alerts to newly-flagged industries only.
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from mytrader import market_data, tickers
from scripts.ethical_filter import check_ticker as ethical_check

from . import config, db, industry_rotation, price_history

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent.parent / ".claude" / "scripts"
sys.path.insert(0, str(_SCRIPTS_DIR))
from sdk_compat import ClaudeAgentOptions, run_text  # noqa: E402


def fetch_spy_close() -> pd.Series | None:
    return price_history.fetch_close_history("SPY", config.GOAT_HATED_HISTORY_LOOKBACK_DAYS)


def _window_return_pct(close: pd.Series | None, window: int) -> float | None:
    if close is None or len(close) < window + 1:
        return None
    return float((close.iloc[-1] / close.iloc[-(window + 1)] - 1) * 100)


def _drawdown_from_high_pct(close: pd.Series | None) -> float | None:
    if close is None or close.empty:
        return None
    trailing = close.iloc[-min(252, len(close)):]
    high = float(trailing.max())
    if high == 0:
        return None
    return float((close.iloc[-1] / high - 1) * 100)


def compute_industry_severity(
    closes: dict[str, pd.Series | None], spy_close: pd.Series | None
) -> list[dict[str, Any]]:
    """Per config.GOAT_INDUSTRY_ETFS row: 3mo/6mo return, vs-SPY underperformance on
    both windows, drawdown-from-52wk-high, and a recent-N-day return (the "not
    already reversing" check). `qualifies` requires: bottom
    config.GOAT_HATED_BOTTOM_N of the 39 by 6mo return (among industries with 6mo
    data -- missing-data sorts last, mirrors industry_rotation.rank_industries), AND
    both underperformance margins clear their thresholds, AND the drawdown floor
    clears, AND the industry is not already showing a sharp recent recovery (a
    missing recent-return reading does NOT disqualify -- an insufficient-history gap
    must never silently suppress an otherwise-qualifying industry)."""
    short_window = config.GOAT_HATED_RANK_WINDOW_SHORT_TRADING_DAYS
    long_window = config.GOAT_INDUSTRY_RANK_WINDOW_TRADING_DAYS
    recency_window = config.GOAT_HATED_REVERSAL_LOOKBACK_DAYS

    spy_3mo = _window_return_pct(spy_close, short_window)
    spy_6mo = _window_return_pct(spy_close, long_window)

    rows: list[dict[str, Any]] = []
    for etf_ticker, industry_label in config.GOAT_INDUSTRY_ETFS.items():
        close = closes.get(etf_ticker)
        return_3mo = _window_return_pct(close, short_window)
        return_6mo = _window_return_pct(close, long_window)
        drawdown = _drawdown_from_high_pct(close)
        recent_return = _window_return_pct(close, recency_window)

        underperformance_3mo = (
            return_3mo - spy_3mo if return_3mo is not None and spy_3mo is not None else None
        )
        underperformance_6mo = (
            return_6mo - spy_6mo if return_6mo is not None and spy_6mo is not None else None
        )

        rows.append({
            "ticker": etf_ticker, "industry_label": industry_label,
            "return_pct_3mo": return_3mo, "return_pct_6mo": return_6mo,
            "underperformance_3mo": underperformance_3mo, "underperformance_6mo": underperformance_6mo,
            "drawdown_from_high_pct": drawdown, "recent_return_pct": recent_return,
            "qualifies": False,
        })

    ranked = sorted(
        (r for r in rows if r["return_pct_6mo"] is not None),
        key=lambda r: r["return_pct_6mo"],
    )
    bottom_n_tickers = {r["ticker"] for r in ranked[: config.GOAT_HATED_BOTTOM_N]}

    for r in rows:
        if r["ticker"] not in bottom_n_tickers:
            continue
        if r["underperformance_3mo"] is None or r["underperformance_6mo"] is None:
            continue
        if r["drawdown_from_high_pct"] is None:
            continue
        not_reversing = (
            r["recent_return_pct"] is None
            or r["recent_return_pct"] <= config.GOAT_HATED_REVERSAL_MAX_RECENT_RETURN_PCT
        )
        r["qualifies"] = (
            r["underperformance_3mo"] <= -config.GOAT_HATED_MIN_UNDERPERFORMANCE_VS_SPY_PCT_3MO
            and r["underperformance_6mo"] <= -config.GOAT_HATED_MIN_UNDERPERFORMANCE_VS_SPY_PCT_6MO
            and r["drawdown_from_high_pct"] <= -config.GOAT_HATED_MIN_DRAWDOWN_FROM_HIGH_PCT
            and not_reversing
        )

    return rows


_NARRATIVE_SEARCH_PROMPT = """\
You are researching why the "{industry_label}" industry (tracked via the {ticker} \
ETF) has been suffering severe, still-live price underperformance recently, on \
behalf of a contrarian value investor looking for a possible market overreaction. \
Use web search to determine:

1. The dominant negative narrative driving this industry's underperformance right \
now (e.g. "AI disruption fear", "rate-cycle cost-of-capital fear", "oversupply/ \
commodity glut", "regulatory crackdown", "one large constituent's company-specific \
scandal dragging the index").
2. Whether that narrative plausibly applies UNIFORMLY across the industry, or is \
actually concentrated in one or two large constituents' company-specific issues \
being generalized to the whole industry.
3. The {ticker} ETF's 3-5 largest constituent holdings by weight (ticker + company \
name) -- current, real data, not a guess from training knowledge.

Respond with ONLY a JSON object, no markdown fences, no other text:
{{"narrative_thesis": "one or two sentence summary of the dominant negative \
narrative", "systemic": true, false, or null (true = applies industry-wide, false = \
concentrated in one/two names, null = genuinely unclear from available evidence), \
"reasoning": "one or two sentences explaining the systemic/concentrated call", \
"top_holdings": [{{"ticker": "...", "name": "..."}}, ...]}}

Never guess "systemic" with a confident-sounding answer if the evidence is thin -- \
return null in that case. Never invent top_holdings tickers you did not find -- an \
empty list is better than a fabricated one.
"""


def _parse_json(raw: str) -> dict:
    cleaned = raw.strip()
    for fence in ("```json", "```"):
        if cleaned.startswith(fence):
            cleaned = cleaned[len(fence):]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    return json.loads(cleaned.strip())


def _search_industry_narrative(industry_label: str, ticker: str) -> dict | None:
    prompt = _NARRATIVE_SEARCH_PROMPT.format(industry_label=industry_label, ticker=ticker)
    try:
        raw = asyncio.run(run_text(
            prompt=prompt,
            options=ClaudeAgentOptions(
                allowed_tools=["WebSearch"], model=config.GOAT_HATED_NARRATIVE_SUMMARY_MODEL
            ),
        ))
        return _parse_json(raw)
    except Exception:
        return None


def _narrative_from_row(row: sqlite3.Row) -> dict[str, Any]:
    systemic = row["systemic"]
    return {
        "narrative_thesis": row["narrative_thesis"],
        "systemic": bool(systemic) if systemic is not None else None,
        "reasoning": row["reasoning"],
        "top_holdings": json.loads(row["top_holdings_json"]),
    }


def classify_industry_narrative(
    industry_label: str, ticker: str, conn: sqlite3.Connection
) -> dict[str, Any] | None:
    """Cache-check -> call on miss -> write-through -> stale-cache fallback on
    failure, identical three-branch flow to mytrader.news_search.get_news_events_for_ticker."""
    cached = db.get_cached_hated_narrative(conn, industry_label)
    if cached is not None:
        fetched_at = datetime.fromisoformat(cached["fetched_at"])
        age_hours = (datetime.now(timezone.utc) - fetched_at).total_seconds() / 3600
        if age_hours < config.GOAT_HATED_NARRATIVE_CACHE_HOURS:
            return _narrative_from_row(cached)

    result = _search_industry_narrative(industry_label, ticker)
    if result is None:
        if cached is not None:
            return _narrative_from_row(cached)  # stale-but-usable fallback
        return None

    narrative_thesis = str(result.get("narrative_thesis") or "").strip() or "No narrative thesis returned."
    systemic = result.get("systemic")
    if systemic is not None and not isinstance(systemic, bool):
        systemic = None  # never a hallucinated confident guess -- unclear stays null
    reasoning = str(result.get("reasoning") or "").strip() or "No reasoning returned."
    top_holdings = [
        {"ticker": str(h.get("ticker") or "").strip(), "name": str(h.get("name") or "").strip()}
        for h in (result.get("top_holdings") or [])
        if isinstance(h, dict) and str(h.get("ticker") or "").strip()
    ]

    db.upsert_hated_narrative_cache(
        conn, industry_label=industry_label, ticker=ticker,
        narrative_thesis=narrative_thesis, systemic=systemic, reasoning=reasoning,
        top_holdings=top_holdings,
    )
    return {
        "narrative_thesis": narrative_thesis, "systemic": systemic,
        "reasoning": reasoning, "top_holdings": top_holdings,
    }


def check_fundamentals_divergence(top_holdings: list[dict[str, str]]) -> dict[str, Any]:
    """Ethical-filters top_holdings, then pulls revenueGrowth/earningsGrowth per
    resolvable ticker via yfinance. A ticker "grows" if either metric is positive,
    "declines" if both are <= 0 with at least one present; unresolvable tickers
    (no data / lookup failure / delisted) are skipped, never crash the run. Verdict
    is "insufficient_data" below config.GOAT_HATED_MIN_CONSTITUENT_FUNDAMENTALS_SAMPLE
    resolved tickers -- never asserts a divergence read from too few data points."""
    per_ticker: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    growing = 0
    declining = 0

    for holding in top_holdings:
        raw_ticker = (holding.get("ticker") or "").strip()
        if not raw_ticker:
            continue
        normalized = tickers.normalize(raw_ticker)
        is_excluded, review_reason = ethical_check(normalized)
        if is_excluded:
            excluded.append({"ticker": normalized, "review_reason": review_reason})
            continue

        try:
            data = market_data.fetch_ticker_data(normalized)
        except Exception:
            data = None
        if data is None:
            continue

        revenue_growth = data.info.get("revenueGrowth")
        earnings_growth = data.info.get("earningsGrowth")
        if revenue_growth is None and earnings_growth is None:
            continue

        is_growing = (revenue_growth is not None and revenue_growth > 0) or (
            earnings_growth is not None and earnings_growth > 0
        )
        classification = "growing" if is_growing else "declining"
        if classification == "growing":
            growing += 1
        else:
            declining += 1
        per_ticker.append({
            "ticker": normalized, "name": holding.get("name") or "",
            "revenue_growth": revenue_growth, "earnings_growth": earnings_growth,
            "classification": classification,
        })

    resolved_count = len(per_ticker)
    if resolved_count < config.GOAT_HATED_MIN_CONSTITUENT_FUNDAMENTALS_SAMPLE:
        verdict = "insufficient_data"
    elif growing > declining:
        verdict = "fundamentals_still_growing"
    elif declining > growing:
        verdict = "fundamentals_also_declining"
    else:
        verdict = "mixed"

    return {"verdict": verdict, "per_ticker": per_ticker, "resolved_count": resolved_count, "excluded": excluded}


def run_hated_industries_scan(conn: sqlite3.Connection) -> dict[str, Any]:
    closes = industry_rotation.fetch_all_industry_closes()
    spy_close = fetch_spy_close()
    severity = compute_industry_severity(closes, spy_close)

    flagged: list[dict[str, Any]] = []
    new_candidates: list[dict[str, Any]] = []
    qualifying_labels: set[str] = set()

    for row in severity:
        if not row["qualifies"]:
            continue
        industry_label = row["industry_label"]
        etf_ticker = row["ticker"]
        qualifying_labels.add(industry_label)

        try:
            narrative = classify_industry_narrative(industry_label, etf_ticker, conn)
        except Exception as e:
            print(f"[goat-hated-industries-scan] narrative classification failed for {industry_label}: {e}")
            narrative = None

        top_holdings = (narrative or {}).get("top_holdings") or []
        try:
            fundamentals = check_fundamentals_divergence(top_holdings)
        except Exception as e:
            print(f"[goat-hated-industries-scan] fundamentals-divergence check failed for {industry_label}: {e}")
            fundamentals = {"verdict": "insufficient_data", "per_ticker": [], "resolved_count": 0, "excluded": []}

        is_new = db.upsert_hated_industry_seen(conn, industry_label=industry_label, ticker=etf_ticker)
        seen_row = db.get_hated_industry_seen(conn, industry_label)

        enriched = dict(row)
        enriched["narrative"] = narrative
        enriched["fundamentals"] = fundamentals
        enriched["first_flagged_at"] = seen_row["first_flagged_at"] if seen_row is not None else None
        flagged.append(enriched)

        if is_new:
            new_candidates.append({
                "ticker": etf_ticker, "sector_label": industry_label,
                "detail": (narrative or {}).get("narrative_thesis") or "Cleared the severity gate.",
            })

    # Drop-out cleanup: an industry previously seen but not qualifying this run is
    # removed, so a later re-qualification is treated as a fresh alert (Shaun's own
    # framing -- a second wave of the same story is worth knowing about again).
    for seen_row in db.get_all_hated_industries_seen(conn):
        if seen_row["industry_label"] not in qualifying_labels:
            db.delete_hated_industry_seen(conn, seen_row["industry_label"])

    return {"severity": severity, "flagged": flagged, "new_candidates": new_candidates}


_VERDICT_LABELS = {
    "fundamentals_still_growing": "fundamentals still growing despite the price decline",
    "fundamentals_also_declining": "fundamentals also declining alongside the price",
    "mixed": "mixed -- some constituents growing, some declining",
    "insufficient_data": "insufficient constituent data to read a divergence signal",
}


def render_hated_industries_report(result: dict[str, Any]) -> str:
    lines = [
        "# Hated Industries Scanner",
        "",
        "Auto-generated by Goat's daily hated-industries scan -- finds industries "
        "suffering severe, still-live price underperformance vs. SPY (both a "
        "3-month and 6-month window), a meaningful drawdown from their 52-week "
        "high, and no sign of an already-started recovery, then layers on an LLM "
        "web-search read of the dominant negative narrative (industry-wide or "
        "concentrated in one/two names?) and a fundamentals-divergence check "
        "against a few of the industry's largest constituents (did the "
        "businesses actually get worse, or just the price?). Purely advisory -- "
        "no verdict, no ticker staging (see hated-industries-scanner-handoff.md). "
        "Representative constituent tickers below are read-only pointers, not "
        "stageable candidates. Advisor notes only; no trade action is ever "
        "suggested here (see SOUL.md).",
        "",
        f"## Run: {date.today().isoformat()}",
        "",
    ]

    flagged = result["flagged"]
    if not flagged:
        lines.append("No industry cleared the severity gate today.")
    else:
        for row in flagged:
            first_flagged = row.get("first_flagged_at")
            lines += [
                f"## {row['industry_label']} ({row['ticker']})",
                "",
                f"Hated since: {first_flagged[:10] if first_flagged else 'n/a'}",
                "",
                "| 3mo return | 6mo return | vs SPY (3mo) | vs SPY (6mo) | Drawdown from high |",
                "|------------|------------|--------------|--------------|---------------------|",
            ]
            r3 = f"{row['return_pct_3mo']:+.1f}%" if row["return_pct_3mo"] is not None else "—"
            r6 = f"{row['return_pct_6mo']:+.1f}%" if row["return_pct_6mo"] is not None else "—"
            u3 = f"{row['underperformance_3mo']:+.1f}pp" if row["underperformance_3mo"] is not None else "—"
            u6 = f"{row['underperformance_6mo']:+.1f}pp" if row["underperformance_6mo"] is not None else "—"
            dd = f"{row['drawdown_from_high_pct']:+.1f}%" if row["drawdown_from_high_pct"] is not None else "—"
            lines.append(f"| {r3} | {r6} | {u3} | {u6} | {dd} |")
            lines.append("")

            narrative = row.get("narrative")
            if narrative is None:
                lines.append("**Narrative:** unavailable this run (search failed, no prior cache).")
            else:
                systemic = narrative["systemic"]
                systemic_label = (
                    "industry-wide" if systemic is True
                    else "concentrated in one/two names" if systemic is False
                    else "unclear whether industry-wide or concentrated"
                )
                lines += [
                    f"**Narrative:** {narrative['narrative_thesis']}",
                    f"**Systemic read:** {systemic_label} -- {narrative['reasoning']}",
                ]
            lines.append("")

            fundamentals = row.get("fundamentals") or {}
            verdict = fundamentals.get("verdict", "insufficient_data")
            lines.append(f"**Fundamentals-divergence read:** {_VERDICT_LABELS.get(verdict, verdict)}")

            per_ticker = fundamentals.get("per_ticker") or []
            if per_ticker:
                lines += [
                    "",
                    "Representative constituents (read-only — not staged as candidates):",
                    "",
                    "| Ticker | Name | Revenue growth | Earnings growth | Read |",
                    "|--------|------|-----------------|-------------------|------|",
                ]
                for h in per_ticker:
                    rg = f"{h['revenue_growth']:+.1%}" if h["revenue_growth"] is not None else "—"
                    eg = f"{h['earnings_growth']:+.1%}" if h["earnings_growth"] is not None else "—"
                    lines.append(f"| {h['ticker']} | {h['name']} | {rg} | {eg} | {h['classification']} |")
            lines.append("")

    lines += ["", f"Last auto-generated: {date.today().isoformat()}."]
    return "\n".join(lines) + "\n"


def write_hated_industries_report(result: dict[str, Any]) -> None:
    config.GOAT_HATED_REPORT_PATH.write_text(
        render_hated_industries_report(result), encoding="utf-8"
    )
