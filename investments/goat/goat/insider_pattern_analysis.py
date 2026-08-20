"""Nightly pattern-analysis pass over the market-wide (non-held) insider trade
dataset -- slices goat_insider_price_outcomes by trade size, %-of-position,
cluster buying/selling, elapsed-time velocity, insider title, and buy-vs-sell,
gated on a minimum sample size per slice (Shaun 2026-08-20). Explicitly
correlational/exploratory, not a trading strategy -- see render_pattern_
analysis_report's disclaimer and SOUL.md's advisor-mode framing."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from . import config


def _classify_trade_size(value: float) -> str:
    if value < 50_000:
        return "<$50k"
    if value < 250_000:
        return "$50k-250k"
    if value < 1_000_000:
        return "$250k-1M"
    return "$1M+"


def _classify_pct_owned(pct: float | None) -> str:
    if pct is None:
        return "New"
    abs_pct = abs(pct)
    if abs_pct < 5:
        return "<5%"
    if abs_pct < 25:
        return "5-25%"
    return "25-100%"


_OFFICER_KEYWORDS = {"CEO", "CFO", "COO", "CTO", "Pres", "Chief", "COB"}


def _classify_title(title: str) -> str:
    """Ground truth for real OpenInsider title strings (spot-checked in
    insider-scan-report.md 2026-08-20): CFO, Dir, COO, Exec COB, Chief
    Strategy Officer, Pres, See Remarks -- abbreviated, not full words like
    "Chairman"."""
    if not title:
        return "Other"
    if "10%" in title:
        return "10% Owner"
    if any(kw in title for kw in _OFFICER_KEYWORDS):
        return "Officer/Chair"
    if "Dir" in title:
        return "Director"
    return "Other"


def _parse_trade_date(trade_date_str: str) -> object | None:
    try:
        return datetime.strptime(trade_date_str, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def _compute_clusters(filings: list[dict[str, Any]]) -> dict[str, bool]:
    """Maps dedup_key -> is-clustered. A filing is clustered if >=2 distinct
    insider_name values traded the same ticker/trade_type within
    GOAT_INSIDER_CLUSTER_WINDOW_DAYS of it (both directions). O(n^2) over the
    filing set is fine at current volume (~15-20/day), revisit only if it
    becomes a real perf problem."""
    window = timedelta(days=config.GOAT_INSIDER_CLUSTER_WINDOW_DAYS)
    parsed = [
        (f, _parse_trade_date(f["trade_date"])) for f in filings
    ]
    clustered: dict[str, bool] = {}
    for f, d in parsed:
        if d is None:
            clustered[f["dedup_key"]] = False
            continue
        distinct_insiders = {
            other["insider_name"]
            for other, od in parsed
            if od is not None
            and other["ticker"] == f["ticker"]
            and other["trade_type"] == f["trade_type"]
            and abs((od - d).days) <= window.days
        }
        clustered[f["dedup_key"]] = len(distinct_insiders) >= 2
    return clustered


def _slice_stats(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Every slice carries n and a plain-English confirm-rate at minimum --
    'confirmed' means excess_pct_change moved in the signal-confirming
    direction (buy -> positive excess, sale -> negative excess)."""
    n = len(rows)
    if n < config.GOAT_INSIDER_PATTERN_MIN_SAMPLE:
        return {"status": "insufficient_data", "n": n}
    confirmed = 0
    excess_values = []
    for r in rows:
        excess = r.get("excess_pct_change")
        if excess is None:
            continue
        excess_values.append(excess)
        if (r["trade_type"] == "P" and excess > 0) or (r["trade_type"] == "S" and excess < 0):
            confirmed += 1
    return {
        "status": "ok",
        "n": n,
        "pct_direction_confirmed": (confirmed / n * 100) if n else 0.0,
        "avg_excess_pct_change": (sum(excess_values) / len(excess_values)) if excess_values else None,
    }


def _bucket_by(rows: list[dict[str, Any]], key_fn) -> dict[str, dict[str, Any]]:
    buckets: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        buckets.setdefault(key_fn(r), []).append(r)
    return {label: _slice_stats(bucket_rows) for label, bucket_rows in buckets.items()}


def compute_pattern_analysis(conn) -> dict[str, Any]:
    from . import db

    rows = [dict(r) for r in db.get_price_outcomes_for_pattern_analysis(conn)]

    # Cluster detection needs the underlying filings (ticker/trade_type/trade_date/
    # insider_name), one entry per dedup_key, not one per (dedup_key, horizon) row.
    filings_by_key: dict[str, dict[str, Any]] = {}
    for r in rows:
        filings_by_key.setdefault(
            r["dedup_key"],
            {
                "dedup_key": r["dedup_key"], "ticker": r["ticker"], "trade_type": r["trade_type"],
                "trade_date": r["trade_date"], "insider_name": r["insider_name"],
            },
        )
    clustered = _compute_clusters(list(filings_by_key.values()))

    trade_size = _bucket_by(rows, lambda r: _classify_trade_size(r["value"]))
    pct_owned = _bucket_by(rows, lambda r: _classify_pct_owned(r["pct_owned_change"]))
    title_role = _bucket_by(rows, lambda r: _classify_title(r.get("title") or ""))
    buy_vs_sell = _bucket_by(rows, lambda r: "Buy" if r["trade_type"] == "P" else "Sell")
    cluster = _bucket_by(rows, lambda r: "Clustered" if clustered.get(r["dedup_key"]) else "Isolated")

    # Elapsed-time velocity: among filings whose 7d horizon already crossed the
    # tier threshold ("confirmed-early"), what fraction were also excess-positive
    # (buys) / excess-negative (sells) at 30d/90d -- does an early signal predict
    # a later one.
    by_key_horizon: dict[tuple[str, int], dict[str, Any]] = {
        (r["dedup_key"], r["horizon_days"]): r for r in rows
    }
    velocity_rows: list[dict[str, Any]] = []
    for key, filing in filings_by_key.items():
        early = by_key_horizon.get((key, 7))
        if early is None or early.get("excess_pct_change") is None:
            continue
        confirmed_early = (
            (filing["trade_type"] == "P" and early["excess_pct_change"] > 0)
            or (filing["trade_type"] == "S" and early["excess_pct_change"] < 0)
        )
        if not confirmed_early:
            continue
        for later_horizon in (30, 90):
            later = by_key_horizon.get((key, later_horizon))
            if later is None or later.get("excess_pct_change") is None:
                continue
            velocity_rows.append({
                "dedup_key": key, "trade_type": filing["trade_type"],
                "value": 0.0, "pct_owned_change": None, "title": "",
                "excess_pct_change": later["excess_pct_change"],
            })

    return {
        "trade_size": trade_size,
        "pct_owned": pct_owned,
        "title_role": title_role,
        "buy_vs_sell": buy_vs_sell,
        "cluster": cluster,
        "velocity_early_confirms_later": _slice_stats(velocity_rows),
        "total_outcome_rows": len(rows),
        "total_filings": len(filings_by_key),
    }


def _render_slice(title: str, description: str, slice_result: dict[str, Any]) -> list[str]:
    lines = [f"### {title}", description, ""]
    if not slice_result:
        lines.append("No data yet.")
        return lines
    for label, stats in sorted(slice_result.items()):
        if stats["status"] == "insufficient_data":
            lines.append(
                f"- **{label}**: not enough data yet (n={stats['n']}, "
                f"need {config.GOAT_INSIDER_PATTERN_MIN_SAMPLE})"
            )
        else:
            avg = stats["avg_excess_pct_change"]
            avg_text = f"{avg:+.1f}%" if avg is not None else "n/a"
            lines.append(
                f"- **{label}** (n={stats['n']}): {stats['pct_direction_confirmed']:.0f}% "
                f"confirmed direction vs. SPY, avg excess return {avg_text}"
            )
    return lines


def render_pattern_analysis_report(analysis: dict[str, Any]) -> str:
    lines = [
        "# Insider Trade Outcome Pattern Analysis",
        "",
        "Auto-generated by Goat's nightly insider scan -- overwritten every run. "
        "This report is correlational/exploratory on Shaun's own captured "
        "OpenInsider data, not a validated trading strategy -- no trade action "
        "is ever suggested here (see SOUL.md). Trade dates in the dataset only "
        "go back to 2026-08-12; most slices are expected to need real time "
        "before a pattern is statistically meaningful.",
        "",
        f"Market-wide (non-held) dataset: {analysis['total_filings']} filing(s) tracked, "
        f"{analysis['total_outcome_rows']} price-outcome snapshot(s) matured so far.",
        "",
    ]
    lines += _render_slice(
        "By Trade Size", "Dollar value of the insider's trade.", analysis["trade_size"]
    )
    lines += ["", *_render_slice(
        "By % of Insider's Own Position",
        "Size of the trade relative to the insider's own prior stake.",
        analysis["pct_owned"],
    )]
    lines += ["", *_render_slice(
        "By Cluster",
        "Isolated single-insider trades vs. multiple distinct insiders on the same "
        f"ticker/direction within {config.GOAT_INSIDER_CLUSTER_WINDOW_DAYS} days.",
        analysis["cluster"],
    )]
    lines += ["", *_render_slice(
        "By Insider Title/Role",
        "Officer/Chair vs. Director vs. 10% Owner vs. Other.",
        analysis["title_role"],
    )]
    lines += ["", *_render_slice(
        "Buy vs. Sell",
        "The core comparison -- does the signaled direction actually hold.",
        analysis["buy_vs_sell"],
    )]
    lines += ["", "### Elapsed-Time Velocity",
              "Among filings whose 7-day move already confirmed the signal, what fraction "
              "still confirmed direction at 30/90 days -- does an early signal predict a "
              "later one.", ""]
    velocity = analysis["velocity_early_confirms_later"]
    if velocity["status"] == "insufficient_data":
        lines.append(
            f"Not enough data yet (n={velocity['n']}, need {config.GOAT_INSIDER_PATTERN_MIN_SAMPLE})"
        )
    else:
        lines.append(
            f"n={velocity['n']}: {velocity['pct_direction_confirmed']:.0f}% still confirmed "
            f"direction at 30/90d, avg excess return "
            f"{velocity['avg_excess_pct_change']:+.1f}%"
            if velocity["avg_excess_pct_change"] is not None
            else f"n={velocity['n']}: {velocity['pct_direction_confirmed']:.0f}% still confirmed direction at 30/90d"
        )

    from datetime import date
    lines += ["", f"Last auto-generated: {date.today().isoformat()}."]
    return "\n".join(lines) + "\n"


def write_pattern_analysis_report(analysis: dict[str, Any]) -> None:
    config.GOAT_INSIDER_PATTERN_ANALYSIS_PATH.write_text(
        render_pattern_analysis_report(analysis), encoding="utf-8"
    )
