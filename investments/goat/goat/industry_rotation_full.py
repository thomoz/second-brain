"""Full-coverage (144/144) industry ranking, built directly from
finviz_groups.fetch_industry_groups() -- no price-series fetch needed, Finviz
already computed the return percentages server-side. See
.agent/plans/goat-industry-ranking-full-coverage.md.

Deliberately separate from industry_rotation.py/monitor.render_industry_ranking_report
(Decision #2 of that plan) -- this data source has no daily price series, so it
cannot feed or replace the 39-industry ETF-backed breakout/candidate pipeline.

Day-over-day flow tracking (added after the original plan's Decision #5 flagged
it as a cheap v2): each scan-industries-full run saves today's Perf Half/Perf
Week numbers into goat_rotation_snapshots under scope="industry_full"
(capture_full_industry_snapshot) and diffs them against the prior run's
snapshot, same "Rotation Flow" mechanism industry_rotation.py/monitor.py already
use for the 39 ETF-backed industries. Finviz itself gives no history -- the
trail only exists from whenever we start saving it ourselves, so flow sections
read "No prior snapshot yet" until there are at least two days of real runs."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from . import config, rotation_flow

_SYDNEY_TZ = ZoneInfo("Australia/Sydney")

# Scope key for goat_rotation_snapshots -- a third scope alongside the existing
# "sector"/"industry", added per Decision #5 of
# .agent/plans/goat-industry-ranking-full-coverage.md. No schema change needed:
# the table's `ticker` column is repurposed to hold the industry NAME (there is
# no real ticker here), and `return_pct`/`return_pct_1w` hold Perf Half/Perf Week.
_SNAPSHOT_SCOPE = "industry_full"

_PERF_COLUMNS = [
    ("perf_week", "Perf Week"),
    ("perf_month", "Perf Month"),
    ("perf_quarter", "Perf Quarter"),
    ("perf_half", "Perf Half"),
    ("perf_year", "Perf Year"),
    ("perf_ytd", "Perf YTD"),
]


def _today_sydney() -> str:
    """Report date label -- always Sydney local, regardless of host clock/timezone
    (Goat runs on the VPS, whose system clock is UTC). Deliberate duplicate of
    monitor._today_sydney -- same posture as industry_rotation.check_industry_breakout's
    own duplication note."""
    return datetime.now(_SYDNEY_TZ).date().isoformat()


def rank_all_industries(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sort by config.GOAT_INDUSTRY_FULL_PRIMARY_WINDOW descending. Missing data
    sorts last, never first/interspersed (same idiom as rank_industries/
    rank_sectors)."""
    window = config.GOAT_INDUSTRY_FULL_PRIMARY_WINDOW
    ranked = sorted(rows, key=lambda r: (r[window] is None, -(r[window] or 0)))
    for i, row in enumerate(ranked, start=1):
        row["rank"] = i
    return ranked


def capture_full_industry_snapshot(conn: sqlite3.Connection, ranking: list[dict[str, Any]]) -> dict[str, Any]:
    """Adapts the full-coverage ranking (name/perf_half/perf_week/rank) into the
    scope-parameterized shape monitor.capture_rotation_snapshot/goat_rotation_snapshots
    already use for sector/industry (ticker/return_pct/return_pct_1w/rank/rising)
    -- reuses that function and table as-is rather than cloning a parallel one,
    per Decision #5. Returns {"rotation_flow": ..., "short_window_flow": ...},
    both None on the first-ever run for this scope (no prior snapshot yet)."""
    from .monitor import capture_rotation_snapshot

    snapshot_rows = [
        {
            "ticker": row["name"],
            "name": row["name"],
            "return_pct": row["perf_half"],
            "return_pct_1w": row["perf_week"],
            "rank": row["rank"],
            "rising": None if row["perf_half"] is None else row["perf_half"] > 0,
        }
        for row in ranking
    ]
    return capture_rotation_snapshot(conn, scope=_SNAPSHOT_SCOPE, ranking=snapshot_rows, label_key="name")


def _perf_table_header() -> list[str]:
    header_cells = " | ".join(label for _field, label in _PERF_COLUMNS)
    divider_cells = " | ".join("---" for _field, _label in _PERF_COLUMNS)
    return [f"| Rank | Industry | {header_cells} |", f"|------|----------|{divider_cells}|"]


def _perf_table_rows(rows: list[dict[str, Any]]) -> list[str]:
    lines = []
    for row in rows:
        cells = " | ".join(
            f"{row[field]:+.2f}%" if row[field] is not None else "—"
            for field, _label in _PERF_COLUMNS
        )
        lines.append(f"| {row['rank']} | {row['name']} | {cells} |")
    return lines


def render_full_industry_ranking_report(result: dict[str, Any]) -> str:
    ranking = result["ranking"]
    lines = [
        "# Goat Full-Coverage Industry Ranking",
        "",
        "Advisor notes only; no trade action is ever suggested here (see SOUL.md). "
        "Sourced from Finviz's own Groups performance view "
        "(finviz.com/groups.ashx?g=industry&v=140), covering all 144 Finviz "
        "industries -- not just the 39 with a dedicated, currently-trading ETF "
        "(see industry-ranking.md for that narrower, breakout-gated report). This "
        "is a pure informational ranking: no breakout signal, no candidate "
        "staging, no WhatsApp alert.",
        "",
        f"## Run: {_today_sydney()}",
        "",
        "## Top 10 Rising",
    ]
    lines += _perf_table_header()
    lines += _perf_table_rows(ranking[:10])

    lines += ["", "## Bottom 10 Falling"]
    lines += _perf_table_header()
    lines += _perf_table_rows(ranking[-10:])

    lines += [
        "",
        "## Full Ranking",
        f"All {len(ranking)}/144 industries.",
        "",
    ]
    lines += _perf_table_header()
    lines += _perf_table_rows(ranking)

    # Only present once a snapshot has actually been captured for this scope
    # (capture_full_industry_snapshot) -- absent entirely on a render called
    # directly with a bare {"ranking": ...} dict, same guard idiom as
    # render_industry_ranking_report's identical check.
    if "rotation_flow" in result:
        lines += rotation_flow.render_flow_section(result.get("rotation_flow"), title="Rotation Flow")
        lines += rotation_flow.render_flow_section(
            result.get("short_window_flow"), title="Short-Window Flow (1-Week)"
        )

    lines += ["", f"Last auto-generated: {_today_sydney()}."]
    return "\n".join(lines) + "\n"


def write_full_industry_ranking_report(result: dict[str, Any]) -> None:
    config.GOAT_INDUSTRY_FULL_RANKING_MD_PATH.write_text(
        render_full_industry_ranking_report(result), encoding="utf-8"
    )
