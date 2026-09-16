"""Goat DMA Breakout Scanner -- a broad daily discovery scan across the combined
S&P 500 + ASX 200 universe for stocks whose close just crossed ABOVE their
150-day or 200-day moving average, per .agent/plans/goat-dma-breakout-scanner.md
and investments/goat/dma-breakout-scanner-handoff.md.

This is deliberately the simplest of the three MA-cross tools in `goat`:

  - Heartbeat Scan (heartbeat.py / heartbeat_scan.py) requires a whole compound
    tight-base pattern within currently-rising sectors, then a 50DMA breakout.
  - Monitor's exit check (config.GOAT_MA_LONG_DAYS) only watches tickers Shaun
    already holds/watchlists, and only for the DOWNSIDE cross.
  - This tool: no base pattern, no sector filter, no holdings/watchlist
    restriction -- just "did this name in the whole index universe just cross
    above its 150 or 200-day MA". The 150 and 200-day checks are run and
    reported INDEPENDENTLY per ticker (a name can fire on one, the other, or
    both) -- they are not gated together. MA slope is computed and shown as
    informational context only; unlike check_sector_breakout/
    check_heartbeat_breakout, a fresh cross fires here regardless of slope.

Reuses the sign-flip cross-detection idiom from sector_rotation.check_sector_
breakout, generalized over ma_days/recency_days. Per heartbeat.py's module
docstring, this is a deliberate independent copy, not a shared helper -- do not
refactor this, sector_rotation.py, or heartbeat.py to import each other's
internals.

Ticker-qualification GOTCHA: my-trader's holdings/watchlist tables store ASX
tickers WITH the `.AX` suffix (e.g. "XRO.AX", "GOLD.AX" -- confirmed against
investments/my-trader/holdings.md and watchlist.md). This module qualifies
every ASX ticker (tickers.asx_variant) once, at universe-fetch time, and uses
that same qualified string consistently through price history, fundamentals,
dedup, and staging -- unlike mytrader.cash_value_scan, which deliberately keeps
a separate bare `ticker` (report display) vs `yf_ticker` (yfinance calls) split
for its own report-only, no-dedup purpose. Using the bare code here would make
an already-held/watchlisted ASX ticker dedup-match fail and re-stage it.
"""

from __future__ import annotations

import re
import sqlite3
from datetime import date
from typing import Any

import pandas as pd
from mytrader import asx200_universe, db as mt_db, market_data, tickers
from mytrader.checks import CheckResult
from scripts.ethical_filter import check_ticker as ethical_check

from . import config, db, fundamentals_context, price_history, sp500_universe


def fetch_universe_constituents(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Combined S&P 500 + ASX 200 universe, each row already ticker-qualified (see
    module GOTCHA) and ethical-filtered. US tickers come from the cached
    goat_sp500_constituents table; ASX tickers are re-scraped from Wikipedia every
    run (asx200_universe has no DB cache) and returned as [] (not None/crash) on a
    scrape failure -- see run_dma_breakout_scan's asx-unavailable handling."""
    rows: list[dict[str, Any]] = []

    for c in sp500_universe.get_or_refresh_sp500_constituents(conn):
        bare = c["ticker"]
        excluded, review_reason = ethical_check(bare)
        if excluded:
            continue
        rows.append({
            "ticker": tickers.normalize(bare), "label": c["gics_sector"],
            "market": "US", "review_reason": review_reason, "company": c["security"],
        })

    asx_constituents = asx200_universe.fetch_asx200_constituents()
    for c in (asx_constituents or []):
        bare = c["ticker"]
        excluded, review_reason = ethical_check(bare)
        if excluded:
            continue
        rows.append({
            "ticker": tickers.asx_variant(bare), "label": c["sector"] or "ASX (sector unavailable)",
            "market": "ASX", "review_reason": review_reason, "company": c["company"] or "",
        })

    return rows


def check_ma_cross(ticker: str, label: str, close: pd.Series, ma_days: int, recency_days: int) -> CheckResult:
    """Flags 'interesting' when `ticker` crossed ABOVE its `ma_days`-day MA within
    the last `recency_days` trading days -- a plain, direct upside cross with no
    slope/base-pattern gate (unlike sector_rotation.check_sector_breakout and
    heartbeat.check_heartbeat_breakout, which both require the MA to also be
    sloping up -- see module docstring's design-decision note). MA slope is still
    computed and included in `data`/`detail` as informational context only."""
    name = f"dma_{ma_days}_cross"
    min_len = ma_days + config.GOAT_SECTOR_SLOPE_LOOKBACK_DAYS
    if len(close) < min_len:
        return CheckResult(
            name=name, verdict="unknown",
            detail=f"{ticker} ({label}): insufficient price history for a "
                   f"{ma_days}-day MA",
        )

    ma = close.rolling(ma_days).mean()
    diff = (close - ma).dropna()
    sign = diff.gt(0).astype(int) - diff.lt(0).astype(int)
    sign_changed = sign.diff().fillna(0) != 0
    sign_changes = sign[sign_changed]

    slope_up = bool(ma.iloc[-1] > ma.iloc[-1 - config.GOAT_SECTOR_SLOPE_LOOKBACK_DAYS])

    if sign_changes.empty:
        return CheckResult(
            name=name, verdict="ok",
            detail=f"{ticker} ({label}): no {ma_days}-day MA cross in available "
                   f"history; MA currently {'rising' if slope_up else 'falling'}",
        )

    cross_date = sign_changes.index[-1]
    crossed_above = bool(sign_changes.iloc[-1] > 0)
    cross_pos = close.index.get_loc(cross_date)
    trading_days_since_cross = (len(close) - 1) - cross_pos
    fresh = trading_days_since_cross <= recency_days

    data = {
        "ma_days": ma_days, "cross_date": cross_date.date().isoformat(),
        "crossed_above": crossed_above,
        "trading_days_since_cross": trading_days_since_cross, "slope_up": slope_up,
        "pct_above_ma_now": round(float((close.iloc[-1] / ma.iloc[-1] - 1) * 100), 2),
    }

    if crossed_above and fresh:
        detail = (
            f"{ticker} ({label}): crossed above its {ma_days}-day MA "
            f"{trading_days_since_cross} trading day(s) ago, now "
            f"{data['pct_above_ma_now']:+.1f}% above it (MA currently "
            f"{'rising' if slope_up else 'falling'}) -- DMA breakout discovery signal"
        )
        return CheckResult(name=name, verdict="interesting", detail=detail, data=data)

    direction = "crossed above" if crossed_above else "crossed below"
    return CheckResult(
        name=name, verdict="ok",
        detail=f"{ticker} ({label}): {direction} its {ma_days}-day MA "
               f"{trading_days_since_cross} trading day(s) ago -- not (yet) a fresh "
               f"breakout",
        data=data,
    )


def passes_liquidity_floor(market: str, data) -> bool:
    """`data` is a mytrader.market_data.TickerData | None. Returns False (fails the
    floor) when data or the required .info fields are missing -- an unusable ticker
    is never staged, matching cash_value_scan.compute_cash_value_metrics's
    None-on-missing-data posture."""
    if data is None:
        return False
    info = data.info
    market_cap = info.get("marketCap")
    avg_volume = info.get("averageVolume")
    if market_cap is None or avg_volume is None:
        return False
    floor = (
        config.GOAT_DMA_BREAKOUT_MIN_MARKET_CAP_USD if market == "US"
        else config.GOAT_DMA_BREAKOUT_MIN_MARKET_CAP_AUD
    )
    return market_cap >= floor and avg_volume >= config.GOAT_DMA_BREAKOUT_MIN_AVG_VOLUME


def run_dma_breakout_scan(conn: sqlite3.Connection) -> dict[str, Any]:
    constituents = fetch_universe_constituents(conn)
    asx_unavailable = not any(c["market"] == "ASX" for c in constituents)

    scanned = 0
    already_staged_elsewhere = 0
    new_candidates: list[dict[str, Any]] = []

    with market_data.cached_session():
        for c in constituents:
            ticker, label, market = c["ticker"], c["label"], c["market"]
            try:
                close = price_history.fetch_close_history(
                    ticker, config.GOAT_DMA_BREAKOUT_HISTORY_LOOKBACK_DAYS
                )
                if close is None:
                    continue
                scanned += 1

                hits = [
                    check_ma_cross(ticker, label, close, ma_days, config.GOAT_DMA_BREAKOUT_CROSS_RECENCY_DAYS)
                    for ma_days in config.GOAT_DMA_BREAKOUT_MA_DAYS
                ]
                interesting = [h for h in hits if h.verdict == "interesting"]
                if not interesting:
                    continue

                if mt_db.get_holding_row(conn, ticker) is not None:
                    continue
                if mt_db.get_watchlist_row(conn, ticker) is not None:
                    continue
                if db.get_goat_pending_candidate(conn, ticker) is not None:
                    already_staged_elsewhere += 1
                    continue

                data = market_data.fetch_ticker_data(ticker)
                if not passes_liquidity_floor(market, data):
                    continue
                context = fundamentals_context.compute_survival_context(ticker, data)
                if context["insolvency_risk"]:
                    print(f"[goat-dma-breakout-scan] {ticker} suppressed -- near-term insolvency risk")
                    continue

                signal_detail = "; ".join(h.detail for h in interesting)
                if c["review_reason"]:
                    signal_detail += f"; {c['review_reason']}"
                signal_detail += f"; survival context: {context['summary']}"

                db.insert_goat_pending_candidate(
                    conn, ticker=ticker, sector_label=label,
                    signal_detail=signal_detail, source="goat_dma_breakout_scan",
                    company_name=c["company"],
                )
                new_candidates.append({"ticker": ticker, "sector_label": label, "detail": signal_detail})
            except Exception as e:
                print(f"[goat-dma-breakout-scan] error checking {ticker}: {e}")

    return {
        "scanned": scanned,
        "asx_unavailable": asx_unavailable,
        "already_staged_elsewhere": already_staged_elsewhere,
        "new_candidates": new_candidates,
        "pending_candidates": [
            dict(r) for r in db.get_all_goat_pending_candidates(conn)
            if r["source"] == "goat_dma_breakout_scan"
        ],
    }


_DAYS_SINCE_CROSS_RE = re.compile(r"(\d+) trading day\(s\) ago")


def _freshest_days_since_cross(signal_detail: str) -> int:
    """A row's signal_detail embeds one or two "N trading day(s) ago" phrases
    (150DMA and/or 200DMA -- see check_ma_cross's detail string). Sorting by
    text rather than a dedicated column keeps this local to the report render
    -- goat_pending_candidates is a shared table across every Goat scan, and
    the other sources (heartbeat, sector rotation, insiders) have no equivalent
    concept to store there. Rows somehow missing a match (shouldn't happen)
    sort last, not first, so a parsing surprise doesn't masquerade as "newest"."""
    matches = _DAYS_SINCE_CROSS_RE.findall(signal_detail)
    return min((int(m) for m in matches), default=10**9)


def render_dma_breakout_candidates_report(result: dict[str, Any]) -> str:
    lines = [
        "# DMA Breakout Candidates — Pending Review",
        "",
        "Auto-generated by Goat's daily DMA breakout scan -- a stock across the "
        "S&P 500 + ASX 200 universe whose close just crossed ABOVE its 150-day or "
        "200-day moving average (checked independently; a name can fire on one, "
        "the other, or both), with fundamentals survival context attached for you "
        "to judge yourself. Sorted newest first (freshest 150/200DMA cross at the "
        "top). Broader and simpler than heartbeat-candidates-pending-"
        "review.md -- no base pattern required, no rising-sector filter, whole "
        "universe not just holdings/watchlist. Review each one and either "
        "`promote-candidate` (writes it into my-trader's real watchlist, labeled "
        "Goat-approved) or `dismiss-candidate` (discards it). Edits here are "
        "overwritten on the next `scan-dma-breakout` run.",
        "",
        f"Scanned {result['scanned']} ticker(s) across the combined universe.",
    ]
    if result["asx_unavailable"]:
        lines.append("> ASX 200 universe unavailable this run (Wikipedia scrape failed) -- US-only scan.")
    if result["already_staged_elsewhere"]:
        lines.append(
            f"{result['already_staged_elsewhere']} ticker(s) crossed but were already "
            "staged by another Goat scan (a ticker can only be pending from one "
            "source at a time) -- not double-counted below."
        )
    lines += [
        "",
        "| Ticker | Company | Sector | Signal | Flagged |",
        "|--------|---------|--------|--------|---------|",
    ]
    sorted_candidates = sorted(
        result["pending_candidates"],
        key=lambda r: _freshest_days_since_cross(r["signal_detail"]),
    )
    for row in sorted_candidates:
        company = (row.get("company_name") or "n/a").replace("|", "/")
        lines.append(
            f"| {row['ticker']} | {company} | {row['sector_label']} | {row['signal_detail']} "
            f"| {row['flagged_at'][:10]} |"
        )
    lines += ["", f"Last auto-generated: {date.today().isoformat()}."]
    return "\n".join(lines) + "\n"


def write_dma_breakout_candidates_report(result: dict[str, Any]) -> None:
    config.GOAT_DMA_BREAKOUT_CANDIDATES_MD_PATH.write_text(
        render_dma_breakout_candidates_report(result), encoding="utf-8"
    )
