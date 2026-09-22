"""Earnings Deterioration Watch -- daily advisor-notes check on Shaun's HOLDINGS ONLY
(never watchlist, Decision #2 in .agent/plans/earnings-deterioration-watch.md) for
early evidence of deteriorating earnings, before the next 10-Q/10-K confirms it.
Three signals, each surfaced separately so Shaun can see which one is actually
firing:

1. Analyst estimate-revision trend (fetch_estimate_snapshot/compute_estimate_trend)
   -- yfinance's eps_trend/earnings_estimate/revenue_estimate/eps_revisions, tracked
   daily into earnings_estimate_history. The only signal that genuinely "moves every
   day" -- no history exists on day one, so compute_estimate_trend degrades to
   "insufficient history" until EARNINGS_WATCH_TREND_MIN_DATAPOINTS snapshots have
   accumulated (expected, not a bug).
2. Earnings-relevant 8-K filings (fetch_new_earnings_8ks) -- reuses sec_filings.py's
   fetch/cache shape; SEC's submissions JSON already carries each 8-K's Item codes
   in the `recent` block (confirmed live 2026-09-17), so no filing-body parsing is
   needed to know whether a given 8-K is earnings-relevant before fetching its
   document. Dedup is a dedicated earnings_watch_8k_seen table (new accession =
   always a new alert), not alert_history's flag/ok/flag reconcile -- a filing is a
   discrete event, not a continuous state.
3. Guidance / management-commentary web search (news_search.get_earnings_guidance_
   for_ticker) -- same WebSearch+LLM+TTL-cache mechanism as news_search.py's own
   get_news_events_for_ticker, earnings-focused prompt.

Callable two ways, both funneled through THIS module's functions so Find
(checks/earnings_deterioration.py) and the standalone daily job
(run_earnings_watch/the `scan-earnings-watch` CLI command) never fork the logic into
two copies:

- Find: checks/earnings_deterioration.py wraps compute_estimate_trend/
  fetch_new_earnings_8ks/get_earnings_guidance_for_ticker into one CheckResult,
  itemized per signal (mirrors checks/opportunity.py's "(N independent signals)"
  shape) -- always-on via find.lookup_ticker.
- Scheduled: run_earnings_watch(conn) iterates db.get_all_holdings(conn) ONLY, is its
  own systemd timer (23:55 UTC), own report (earnings-watch-report.md), own
  WhatsApp+toast alerting -- never wired into monitor.py's own daily loop. Cost
  reasoning: this needs an LLM+WebSearch call per holding (same class as
  checks/news_events.py's own "why this is opt-in/its own job, not folded into
  Monitor's re-check of 50+ rows/day" docstring) -- kept a separate, cheaper-scoped
  job like Cash-Value Scan / Goat Insider Scan / AI-Resistant Moat Scan already are.

Industry-context signal (fetch_industry_context) is read-only/informational only --
never gates the aggregate verdict by itself (Decision #6). Reads GOAT_INDUSTRY_ETFS
from mytrader.config (moved there from goat/goat/config.py 2026-09 specifically to
let this module read it without a circular workspace dependency -- goat depends on
my-trader, not the reverse -- see config.py's own migration comment).

Graceful degradation everywhere, never raises: an ETF/commodity-trust holding
naturally degrades every signal to "unknown"/None (empty yfinance estimate frame, no
SEC CIK match, guidance search finds nothing material) -- no special-case ETF branch
anywhere in this module, same philosophy as valuation.py/dividend.py's own ETF
handling.
"""

from __future__ import annotations

import asyncio
import sqlite3
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from . import config, db, market_data, mlp_filter, monitor, news_search, sec_filings, tickers
from .checks import CheckResult

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent.parent / ".claude" / "scripts"
sys.path.insert(0, str(_SCRIPTS_DIR))
from sdk_compat import ClaudeAgentOptions, run_text  # noqa: E402

SYDNEY_TZ = ZoneInfo("Australia/Sydney")


def _today_sydney() -> str:
    return datetime.now(SYDNEY_TZ).date().isoformat()

# --- Signal 1: analyst estimate-revision trend --------------------------------


def fetch_estimate_snapshot(ticker: str) -> dict[str, float | int | None] | None:
    """yfinance's `.eps_trend`/`.earnings_estimate`/`.revenue_estimate`/
    `.eps_revisions`, all indexed by period ("0q", "+1q", "0y", "+1y"). Uses "0y"
    (current fiscal year) as the tracked period -- less noisy quarter-to-quarter
    than "0q"; see module NOTES in the plan for why "0q" tracking is a clean future
    extension, not built in v1. Returns None if `.eps_trend` is empty or lacks a
    "0y" row (mirrors market_data.py's own empty-DataFrame degradation)."""
    import yfinance as yf

    try:
        t = yf.Ticker(ticker)
        eps_trend = t.eps_trend
        if eps_trend is None or eps_trend.empty or "0y" not in eps_trend.index:
            return None

        eps_estimate_avg = None
        earnings_estimate = t.earnings_estimate
        if earnings_estimate is not None and not earnings_estimate.empty and "0y" in earnings_estimate.index:
            val = earnings_estimate.loc["0y"].get("avg")
            eps_estimate_avg = float(val) if val is not None else None

        revenue_estimate_avg = None
        revenue_estimate = t.revenue_estimate
        if revenue_estimate is not None and not revenue_estimate.empty and "0y" in revenue_estimate.index:
            val = revenue_estimate.loc["0y"].get("avg")
            revenue_estimate_avg = float(val) if val is not None else None

        revisions_up_30d = revisions_down_30d = None
        eps_revisions = t.eps_revisions
        if eps_revisions is not None and not eps_revisions.empty and "0y" in eps_revisions.index:
            row = eps_revisions.loc["0y"]
            # GOTCHA (real, confirmed live 2026-09-17): columns are
            # upLast7days/upLast30days/downLast30days/downLast7Days -- note the
            # inconsistent capital-D in downLast7Days vs lowercase everywhere
            # else. Hardcoded exact strings, not derived. The 30-day columns
            # used here are both lowercase.
            up = row.get("upLast30days")
            down = row.get("downLast30days")
            revisions_up_30d = int(up) if up is not None else None
            revisions_down_30d = int(down) if down is not None else None

        return {
            "eps_estimate_avg": eps_estimate_avg,
            "revenue_estimate_avg": revenue_estimate_avg,
            "revisions_up_30d": revisions_up_30d,
            "revisions_down_30d": revisions_down_30d,
        }
    except Exception:
        return None


def record_estimate_snapshot(
    conn: sqlite3.Connection, ticker: str, snapshot: dict[str, Any], date_str: str
) -> None:
    db.record_estimate_snapshot(
        conn, ticker=ticker, date=date_str,
        eps_estimate_avg=snapshot.get("eps_estimate_avg"),
        revenue_estimate_avg=snapshot.get("revenue_estimate_avg"),
        revisions_up_30d=snapshot.get("revisions_up_30d"),
        revisions_down_30d=snapshot.get("revisions_down_30d"),
    )


def compute_estimate_trend(conn: sqlite3.Connection, ticker: str) -> dict[str, str]:
    """Returns {"verdict": "unknown"|"flag"|"ok", "detail": str}. "unknown" when
    fewer than EARNINGS_WATCH_TREND_MIN_DATAPOINTS usable rows exist yet in the
    trailing EARNINGS_WATCH_TREND_WINDOW_DAYS -- expected for the first ~week after
    this ships (this tool is the first thing in the codebase to record this data),
    not a bug. Otherwise compares earliest-in-window vs. latest-in-window
    eps_estimate_avg; flags if the cumulative decline meets/exceeds
    EARNINGS_WATCH_TREND_FLAG_PCT. Notes revisions_down_30d > revisions_up_30d as
    corroborating context in the detail text, not a separate gate."""
    since = (date.today() - timedelta(days=config.EARNINGS_WATCH_TREND_WINDOW_DAYS)).isoformat()
    history = db.get_estimate_history(conn, ticker, since=since)
    usable = [h for h in history if h["eps_estimate_avg"] is not None]

    if len(usable) < config.EARNINGS_WATCH_TREND_MIN_DATAPOINTS:
        return {
            "verdict": "unknown",
            "detail": f"Insufficient history ({len(usable)}/{config.EARNINGS_WATCH_TREND_MIN_DATAPOINTS} "
                      f"daily estimate snapshots recorded) -- estimate-trend tracking needs a few more days",
        }

    earliest, latest = usable[0], usable[-1]
    earliest_avg, latest_avg = earliest["eps_estimate_avg"], latest["eps_estimate_avg"]
    if earliest_avg == 0:
        return {"verdict": "unknown", "detail": "Earliest EPS estimate in window is zero -- can't compute a % trend"}

    pct_change = (latest_avg - earliest_avg) / abs(earliest_avg) * 100
    down, up = latest["revisions_down_30d"], latest["revisions_up_30d"]
    revisions_note = (
        f"; corroborating: {down} analyst downward revisions vs {up} upward in the last 30 days"
        if down is not None and up is not None and down > up else ""
    )

    if pct_change <= -config.EARNINGS_WATCH_TREND_FLAG_PCT:
        return {
            "verdict": "flag",
            "detail": f"EPS estimate down {abs(pct_change):.1f}% over the trailing "
                      f"{config.EARNINGS_WATCH_TREND_WINDOW_DAYS} days ({earliest_avg:.2f} -> "
                      f"{latest_avg:.2f}){revisions_note}",
        }
    return {
        "verdict": "ok",
        "detail": f"EPS estimate {'up' if pct_change >= 0 else 'down'} {abs(pct_change):.1f}% over the "
                  f"trailing {config.EARNINGS_WATCH_TREND_WINDOW_DAYS} days -- below the "
                  f"{config.EARNINGS_WATCH_TREND_FLAG_PCT}% flag threshold{revisions_note}",
    }

# --- Signal 2: earnings-relevant 8-K filings -----------------------------------

_8K_SUMMARY_PROMPT = """\
You are summarizing part of {ticker}'s SEC 8-K filing (Item(s) {items}) for an \
investment analyst watching for early signs of earnings deterioration. Condense the \
following into a focused summary (100-200 words) -- keep anything relevant to \
results of operations, cost/restructuring actions, material agreement changes, or \
guidance-relevant disclosures; drop boilerplate legal language.

{text}

Return plain text only, no markdown headers.
"""


def _summarize_8k(ticker: str, items: str, text: str) -> str | None:
    truncated = text[:config.SEC_MAX_SECTION_CHARS]
    if not truncated.strip():
        return None
    prompt = _8K_SUMMARY_PROMPT.format(ticker=ticker, items=items, text=truncated)
    try:
        raw = asyncio.run(run_text(
            prompt=prompt,
            options=ClaudeAgentOptions(allowed_tools=[], model=config.EARNINGS_WATCH_SUMMARY_MODEL),
        ))
        return raw.strip() or None
    except Exception:
        return None


def fetch_new_earnings_8ks(
    ticker: str, conn: sqlite3.Connection, *, since: date
) -> list[dict[str, Any]] | None:
    """Every earnings-relevant 8-K (Item codes intersecting
    config.EARNINGS_WATCH_8K_ITEM_ALLOWLIST) filed since `since`, each tagged
    "new_this_run" (not already in earnings_watch_8k_seen before this call) for the
    daily job's alerting to key off. Returns None when there's no SEC CIK match at
    all (foreign private issuer, non-US ASX holding) -- distinct from an empty list
    (checked, found nothing), mirroring sec_filings.get_filing_summaries_for_ticker's
    own CIK-miss degradation. Routine 8-Ks (Item codes outside the allowlist) are
    filtered out BEFORE any document fetch -- only allowlisted filings ever reach
    fetch_filing_document/summarization."""
    cik = sec_filings.get_cik(conn, ticker.upper())
    if cik is None:
        return None
    index = sec_filings.fetch_filing_index(cik)
    if index is None:
        return None

    filings = sec_filings.recent_filings_of_types(index, {"8-K"}, since)
    out: list[dict[str, Any]] = []
    for f in filings:
        filing_items = {i.strip() for i in f["items"].split(",") if i.strip()}
        if not filing_items & config.EARNINGS_WATCH_8K_ITEM_ALLOWLIST:
            continue

        cached = db.get_cached_earnings_8k(conn, ticker, f["accession_number"])
        if cached is None:
            new_this_run = True
            html = sec_filings.fetch_filing_document(cik, f["accession_number"], f["primary_document"])
            summary = None
            if html is not None:
                text = sec_filings.strip_html(html)
                summary = _summarize_8k(ticker, f["items"], text)
            db.upsert_earnings_8k_seen(
                conn, ticker=ticker, accession_number=f["accession_number"],
                items=f["items"], filing_date=f["filing_date"], summary=summary,
            )
            time.sleep(config.SEC_REQUEST_DELAY_SECONDS)
        else:
            new_this_run = False
            summary = cached["summary"]

        out.append({
            "form": f["form"], "accession_number": f["accession_number"],
            "items": f["items"], "filing_date": f["filing_date"],
            "summary": summary, "new_this_run": new_this_run,
        })
    return out

# --- Signal 3 lives in news_search.get_earnings_guidance_for_ticker -----------
# --- Industry context (informational only, never gates alone) ------------------

_industry_etf_by_label: dict[str, str] | None = None


def _get_industry_etf_by_label() -> dict[str, str]:
    global _industry_etf_by_label
    if _industry_etf_by_label is None:
        _industry_etf_by_label = {label: etf for etf, label in config.GOAT_INDUSTRY_ETFS.items()}
    return _industry_etf_by_label


def _fetch_close_history(ticker: str, lookback_days: int):
    """Private copy of goat.price_history.fetch_close_history's tries-.AX-fallback
    shape (11 lines) -- a direct import from goat would create a circular workspace
    dependency (goat already depends on my-trader, not the reverse; see config.py's
    GOAT_INDUSTRY_ETFS migration comment, Phase 0 of the plan)."""
    import yfinance as yf

    start = (date.today() - timedelta(days=lookback_days)).isoformat()
    for candidate in (tickers.normalize(ticker), tickers.asx_variant(ticker)):
        try:
            hist = yf.Ticker(candidate).history(start=start, auto_adjust=True)
        except Exception:
            continue
        if hist.empty:
            continue
        close = hist["Close"].dropna()
        if close.empty:
            continue
        if getattr(close.index, "tz", None) is not None:
            close.index = close.index.tz_localize(None)
        return close
    return None


def fetch_industry_context(ticker: str, data: market_data.TickerData | None) -> dict[str, Any] | None:
    """Maps this holding's yfinance industry string against GOAT_INDUSTRY_ETFS
    (reverse lookup). Returns None if there's no data, no industry string, or no
    dedicated ETF for that industry (expected for most individual holdings -- only
    39 of 143 Finviz industries have one). Read-only/context only -- never gates
    the aggregate verdict by itself (Decision #6)."""
    if data is None:
        return None
    industry = data.info.get("industry")
    if not industry:
        return None
    etf = _get_industry_etf_by_label().get(industry)
    if etf is None:
        return None

    window = config.GOAT_INDUSTRY_RANK_WINDOW_TRADING_DAYS
    close = _fetch_close_history(etf, config.GOAT_INDUSTRY_HISTORY_LOOKBACK_DAYS)
    if close is None or len(close) < window + 1:
        return None
    return_pct = float((close.iloc[-1] / close.iloc[-(window + 1)] - 1) * 100)
    return {
        "industry_label": industry, "etf_ticker": etf,
        "return_pct": return_pct, "rising": return_pct > 0,
    }

# --- Orchestrator ----------------------------------------------------------------


def run_earnings_watch(conn: sqlite3.Connection) -> dict[str, Any]:
    """Holdings only (db.get_all_holdings), per Decision #2 -- never watchlist. MLPs
    are skipped entirely (mirrors engine.run_assessment's own MLP-skip shape).
    Estimate-trend and guidance signals go through monitor.reconcile_flag_alerts
    (flag->ok->flag dedup, source_table="holdings") -- these alerts also
    automatically show up in my-trader's own Monitor "Open Alerts" section since
    both write to the same alert_history table, an intentional bonus, not a bug.
    The 8-K signal alerts directly off each filing's own "new_this_run" flag, no
    alert_history involvement (a new accession is always a new alert -- Decision
    #4)."""
    holdings = db.get_all_holdings(conn)
    today = _today_sydney()
    since_8k = date.today() - timedelta(days=config.EARNINGS_WATCH_8K_LOOKBACK_DAYS)

    new_alerts: list[dict[str, Any]] = []
    holdings_results: list[dict[str, Any]] = []

    with market_data.cached_session():
        for row in holdings:
            ticker = row["ticker"]
            try:
                data = market_data.fetch_ticker_data(ticker)
                mlp_name = mlp_filter.detect(data.info) if data is not None else None
                if mlp_name is not None:
                    holdings_results.append({
                        "ticker": ticker, "name": row["name"], "bucket": row["bucket"],
                        "mlp": True, "mlp_name": mlp_name,
                    })
                    continue

                snapshot = fetch_estimate_snapshot(ticker)
                if snapshot is not None:
                    record_estimate_snapshot(conn, ticker, snapshot, today)
                trend = compute_estimate_trend(conn, ticker)

                eight_ks = fetch_new_earnings_8ks(ticker, conn, since=since_8k)
                guidance = news_search.get_earnings_guidance_for_ticker(ticker, conn)
                industry_ctx = fetch_industry_context(ticker, data)

                trend_check = CheckResult(
                    name="earnings_watch_trend", verdict=trend["verdict"], detail=trend["detail"],
                )
                guidance_check = CheckResult(
                    name="earnings_watch_guidance",
                    verdict=guidance["verdict"] if guidance is not None else "unknown",
                    detail=guidance["detail"] if guidance is not None else "Guidance search unavailable this run",
                )
                row_alerts = monitor.reconcile_flag_alerts(
                    ticker, "holdings", [trend_check, guidance_check], conn
                )
                for a in row_alerts:
                    a["company"] = row["name"]
                new_alerts.extend(row_alerts)

                for f in (eight_ks or []):
                    if f["new_this_run"]:
                        new_alerts.append({
                            "ticker": ticker, "source_table": "holdings",
                            "check_name": "earnings_watch_8k", "company": row["name"],
                            "message": f"New earnings-relevant 8-K (Item {f['items']}) filed "
                                       f"{f['filing_date']}: {f['summary'] or 'summary unavailable'}",
                        })

                holdings_results.append({
                    "ticker": ticker, "name": row["name"], "bucket": row["bucket"], "mlp": False,
                    "trend": trend, "eight_ks": eight_ks, "guidance": guidance,
                    "industry_context": industry_ctx,
                })
            except Exception as e:
                print(f"[earnings_watch] error checking holding {ticker}: {e}")

    return {
        "checked_holdings": len(holdings),
        "holdings_results": holdings_results,
        "new_alerts": new_alerts,
    }


def _holding_has_no_earnings_data(h: dict[str, Any]) -> bool:
    """True when nothing about this holding differentiated this run -- the natural
    ETF/commodity-trust degradation path (no estimate history, no SEC CIK match/no
    qualifying 8-K, guidance search found nothing material). Report collapses this
    to a single line rather than 3 verbose "unknown" blocks, mirroring monitor.py's
    own _NOISE_CHECKS/_is_noise_check boilerplate-suppression philosophy."""
    guidance = h.get("guidance")
    return (
        h["trend"]["verdict"] == "unknown"
        and not h.get("eight_ks")
        and (guidance is None or guidance["verdict"] != "flag")
    )


def render_earnings_watch_report(result: dict[str, Any]) -> str:
    lines = [
        "# Earnings Deterioration Watch",
        "",
        "What this is: a daily early-warning check on your holdings for signs "
        "earnings may be deteriorating BEFORE the next 10-Q/10-K confirms it -- "
        "analyst estimate-revision trend, earnings-relevant SEC 8-Ks, and "
        "guidance/management-commentary search.",
        "",
        "Auto-generated -- overwritten every run. Advisor notes only; no trade "
        "action is ever suggested here (see SOUL.md).",
        "",
        "Not covered: alternative data (app downloads, web traffic, credit-card "
        "spend) -- no free source in this toolset.",
        "",
        f"## Run: {_today_sydney()}",
        f"Checked {result['checked_holdings']} holding(s).",
        "",
        "### Holdings",
    ]

    holdings_results = result.get("holdings_results", [])
    if not holdings_results:
        lines.append("No holdings tracked.")

    for h in holdings_results:
        lines.append(f"\n**{h['ticker']}** ({h.get('name') or 'unnamed'}, bucket {h.get('bucket')})")
        if h.get("mlp"):
            lines.append(f"- MLP -- skipped: {h['mlp_name']} is structured as a Master Limited Partnership.")
            continue
        if _holding_has_no_earnings_data(h):
            lines.append("- No earnings data available (fund/commodity instrument).")
            continue

        trend = h["trend"]
        lines.append(f"- [{trend['verdict']}] Estimate trend: {trend['detail']}")

        guidance = h.get("guidance")
        if guidance is not None:
            lines.append(f"- [{guidance['verdict']}] Guidance/commentary: {guidance['detail']}")
        else:
            lines.append("- [unknown] Guidance/commentary: search unavailable this run")

        eight_ks = h.get("eight_ks")
        if eight_ks:
            for f in eight_ks:
                tag = "NEW" if f["new_this_run"] else "seen"
                lines.append(
                    f"- [{tag}] 8-K (Items {f['items']}) filed {f['filing_date']}: "
                    f"{f['summary'] or 'summary unavailable'}"
                )
        else:
            lines.append("- No earnings-relevant 8-Ks in the lookback window.")

        industry_ctx = h.get("industry_context")
        if industry_ctx is not None:
            direction = "rising" if industry_ctx["rising"] else "falling"
            lines.append(
                f"- Industry context ({industry_ctx['industry_label']}, {industry_ctx['etf_ticker']}): "
                f"{direction} {industry_ctx['return_pct']:+.1f}% over the trailing window "
                f"(informational only, not a gate)"
            )

    lines += ["", "### New Alerts This Run"]
    if result["new_alerts"]:
        for a in result["new_alerts"]:
            company = f" ({a['company']})" if a.get("company") else ""
            lines.append(f"- **{a['ticker']}**{company} ({a['source_table']}) -- {a['check_name']}: {a['message']}")
    else:
        lines.append("No new material changes.")

    lines += ["", f"Last auto-generated: {_today_sydney()}."]
    return "\n".join(lines) + "\n"


def write_report(result: dict[str, Any]) -> None:
    config.EARNINGS_WATCH_REPORT_PATH.write_text(render_earnings_watch_report(result), encoding="utf-8")


def maybe_notify(result: dict[str, Any]) -> None:
    if not result["new_alerts"]:
        return
    sys.path.insert(0, str(_SCRIPTS_DIR))
    from notifications import send_toast_notification, send_whatsapp_notification

    n = len(result["new_alerts"])
    summary = f"{n} item(s) flagged -- check investments/my-trader/earnings-watch-report.md"
    send_toast_notification("Earnings Deterioration Watch", summary)

    lines = [f"Earnings Deterioration Watch: {n} item(s) flagged."] + [
        f"- {a['ticker']}" + (f" ({a['company']})" if a.get("company") else "")
        + f": {a['check_name']} -- {a['message']}"
        for a in result["new_alerts"]
    ]
    send_whatsapp_notification("\n".join(lines))
