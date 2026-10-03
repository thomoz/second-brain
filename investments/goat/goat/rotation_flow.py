"""Rotation Flow -- Part A of .agent/plans/goat-industry-pipeline.md. Diffs
today's sector/industry ranking against the most recent PRIOR snapshot of the
same scope to answer "which way is this heading", not just today's static
number. A ticker missing from the prior snapshot, or carrying a None return
value on either side (insufficient price history that day), is excluded from
the diff entirely -- an unknown state can never be said to have "transitioned".

`field` selects which window to diff ("rising" for the long window, "rising_1w"
for the 1-week short window) but is resolved to the underlying return_pct
column internally, not read as a stored boolean -- goat_rotation_snapshots
only stores return_pct/return_pct_1w (see db.insert_rotation_snapshots), not a
separate rising_1w column, so both the previous (a sqlite3.Row) and current
(a plain dict, from rank_sectors/rank_industries) side are diffed off the same
return-pct sign test either way."""

from __future__ import annotations

from typing import Any

_FIELD_TO_RETURN_COLUMN = {"rising": "return_pct", "rising_1w": "return_pct_1w"}


def compute_flow(
    previous_rows: list[Any], current_ranking: list[dict[str, Any]], *,
    label_key: str, field: str = "rising",
) -> dict[str, Any]:
    return_col = _FIELD_TO_RETURN_COLUMN.get(field, field)
    previous_by_ticker = {row["ticker"]: row for row in previous_rows}

    transitions: list[dict[str, Any]] = []
    summary = {
        "rising_to_falling": 0, "falling_to_rising": 0,
        "unchanged_rising": 0, "unchanged_falling": 0,
    }
    no_prior_count = 0

    for row in current_ranking:
        ticker = row["ticker"]
        prev = previous_by_ticker.get(ticker)
        if prev is None:
            no_prior_count += 1
            continue
        prev_return = prev[return_col]
        curr_return = row.get(return_col)
        if prev_return is None or curr_return is None:
            continue
        prev_rising = prev_return > 0
        curr_rising = curr_return > 0
        if prev_rising == curr_rising:
            summary["unchanged_rising" if curr_rising else "unchanged_falling"] += 1
            continue
        transitions.append({
            "ticker": ticker, "label": row[label_key], "from": prev_rising, "to": curr_rising,
        })
        summary["falling_to_rising" if curr_rising else "rising_to_falling"] += 1

    return {"transitions": transitions, "summary": summary, "no_prior_count": no_prior_count}


def render_flow_section(flow: dict[str, Any] | None, *, title: str) -> list[str]:
    if flow is None:
        return ["", f"### {title}", "No prior snapshot yet."]

    summary = flow["summary"]
    lines = [
        "",
        f"### {title}",
        f"{summary['falling_to_rising']} newly rising, {summary['rising_to_falling']} newly falling "
        f"since the prior snapshot ({summary['unchanged_rising']} still rising, "
        f"{summary['unchanged_falling']} still falling unchanged"
        + (f", {flow['no_prior_count']} with no prior snapshot" if flow["no_prior_count"] else "")
        + ").",
    ]
    if flow["transitions"]:
        lines += ["", "| Ticker | Label | From | To |", "|--------|-------|------|----|"]
        for t in flow["transitions"]:
            from_label = "Rising" if t["from"] else "Falling"
            to_label = "Rising" if t["to"] else "Falling"
            lines.append(f"| {t['ticker']} | {t['label']} | {from_label} | {to_label} |")
    else:
        lines += ["", "No transitions since the prior snapshot."]
    return lines
