"""Deterministic, LLM-free rebuild of the Rotation Watch page from
rotation-history-export.json + rotation-watch-template.html. Added 2026-10-20
after Shaun declined an Anthropic-cloud-hosted refresh routine for privacy
reasons (see memory feedback_no_anthropic_cloud_routines) -- this replaces
that plan entirely: no Claude API call, no Artifact, no new trust boundary.
Output (rotation-watch.html) is a plain static file vault sync carries to
Shaun's laptop like every other goat report; he opens it locally in a
browser, no hosting involved. See memory project_rotation_watch_artifact.md
for the full history."""

from __future__ import annotations

import json
from typing import Any

from . import config

_SECTOR_BEGIN_ANCHOR = "// === SECTOR_DATA:BEGIN"
_SECTOR_END_ANCHOR = "// === SECTOR_DATA:END ==="
_INDUSTRY_BEGIN_ANCHOR = "// === INDUSTRY_FULL_DATA:BEGIN"
_INDUSTRY_END_ANCHOR = "// === INDUSTRY_FULL_DATA:END ==="

# Regenerated verbatim on every build -- the live template's own copy of these
# comment lines must match exactly, or _replace_span's anchor search breaks.
_SECTOR_COMMENT = (
    "  // === SECTOR_DATA:BEGIN (auto-regenerated from rotation-history-export.json by the\n"
    "  // Rotation Watch refresh routine -- do not hand-edit values here, edit the refresh\n"
    "  // logic instead; everything else in this file IS hand-edited/structural) ===\n"
)
_INDUSTRY_COMMENT = (
    "  // === INDUSTRY_FULL_DATA:BEGIN (auto-regenerated, see SECTOR_DATA:BEGIN comment above) ===\n"
)

_TOP_N = 10
_BOTTOM_N = 10


def _round_or_none(v: float | None) -> float | None:
    return None if v is None else round(v, 2)


def build_sector_data(rows: list[dict[str, Any]]) -> tuple[list[str], list[dict[str, Any]]]:
    """rows: every row from rotation-history-export.json's "sector" scope (all 11 SPDR
    ETFs, every snapshot date on record). Returns (DATES, SECTORS) ready to drop
    straight into the template's var declarations via json.dumps."""
    dates = sorted({r["snapshot_date"] for r in rows})
    by_ticker: dict[str, dict[str, dict[str, Any]]] = {}
    for r in rows:
        by_ticker.setdefault(r["ticker"], {})[r["snapshot_date"]] = r

    sectors = []
    for ticker, by_date in by_ticker.items():
        label = next(iter(by_date.values()))["label"]
        ret = [_round_or_none(by_date[d]["return_pct"]) if d in by_date else None for d in dates]
        w1 = [_round_or_none(by_date[d]["return_pct_1w"]) if d in by_date else None for d in dates]
        latest = by_date.get(dates[-1]) if dates else None
        rising = 1 if (latest is not None and (latest["return_pct"] or 0) > 0) else 0
        sectors.append({"t": ticker, "n": label, "ret": ret, "w1": w1, "rising": rising})
    return dates, sectors


def build_industry_full_data(
    rows: list[dict[str, Any]], *, top_n: int = _TOP_N, bottom_n: int = _BOTTOM_N,
) -> tuple[list[str], list[dict[str, Any]]]:
    """rows: every row from rotation-history-export.json's "industry_full" scope (up
    to 144 industries x however many snapshot dates exist). Membership (which up-to-20
    industries get included) is fixed by the LATEST snapshot date's return_pct_1w (Perf
    Week) -- matches industry_rotation_full.rank_all_industries' own primary-window
    choice (GOAT_INDUSTRY_FULL_PRIMARY_WINDOW), not the longer return_pct window. Top N
    kept descending (highest first); bottom N kept ascending (most negative first),
    drawn from whatever's left after top N so the two groups never overlap even when
    fewer than top_n+bottom_n industries exist that day. "ticker"/"label" in the source
    rows both hold the Finviz industry NAME -- there's no real ticker for an industry."""
    full_dates = sorted({r["snapshot_date"] for r in rows})
    if not full_dates:
        return [], []
    latest_date = full_dates[-1]
    latest_rows = [r for r in rows if r["snapshot_date"] == latest_date]
    latest_rows.sort(key=lambda r: (r["return_pct_1w"] is None, -(r["return_pct_1w"] or 0)))

    top = latest_rows[:top_n]
    remaining = latest_rows[len(top):]
    bottom = sorted(
        remaining, key=lambda r: (r["return_pct_1w"] is None, (r["return_pct_1w"] or 0))
    )[:bottom_n]
    selected = top + bottom

    by_label: dict[str, dict[str, dict[str, Any]]] = {}
    for r in rows:
        by_label.setdefault(r["label"], {})[r["snapshot_date"]] = r

    industries = []
    for sel in selected:
        by_date = by_label[sel["label"]]
        ret = [_round_or_none(by_date[d]["return_pct"]) if d in by_date else None for d in full_dates]
        w1 = [_round_or_none(by_date[d]["return_pct_1w"]) if d in by_date else None for d in full_dates]
        rising = 1 if (sel["return_pct_1w"] or 0) > 0 else 0
        industries.append({
            "t": sel["label"], "n": f"#{sel['rank']} of 144", "ret": ret, "w1": w1, "rising": rising,
        })
    return full_dates, industries


def _render_array_block(
    dates_name: str, dates: list[str], rows_name: str, rows: list[dict[str, Any]]
) -> str:
    rows_text = ",\n".join(f"    {json.dumps(r)}" for r in rows)
    return f"  var {dates_name} = {json.dumps(dates)};\n\n  var {rows_name} = [\n{rows_text}\n  ];"


def _replace_span(text: str, begin_anchor: str, end_anchor: str, new_block: str) -> str:
    """Replaces everything from the START OF THE LINE containing begin_anchor through
    the end of end_anchor (inclusive) with new_block. Raises ValueError (via str.index)
    if either anchor is missing -- a template that's drifted out of sync with these
    anchors should fail loudly, not silently write a broken page."""
    start = text.index(begin_anchor)
    line_start = text.rfind("\n", 0, start) + 1
    end = text.index(end_anchor, start) + len(end_anchor)
    return text[:line_start] + new_block + text[end:]


def build_rotation_watch_html(export_data: dict[str, Any], template_text: str) -> str:
    scopes = export_data.get("scopes", {})
    sector_dates, sectors = build_sector_data(scopes.get("sector", []))
    full_dates, industries = build_industry_full_data(scopes.get("industry_full", []))

    sector_block = (
        _SECTOR_COMMENT
        + _render_array_block("DATES", sector_dates, "SECTORS", sectors)
        + "\n  " + _SECTOR_END_ANCHOR
    )
    industry_block = (
        _INDUSTRY_COMMENT
        + _render_array_block("FULL_DATES", full_dates, "INDUSTRY_FULL", industries)
        + "\n  " + _INDUSTRY_END_ANCHOR
    )

    text = _replace_span(template_text, _SECTOR_BEGIN_ANCHOR, _SECTOR_END_ANCHOR, sector_block)
    text = _replace_span(text, _INDUSTRY_BEGIN_ANCHOR, _INDUSTRY_END_ANCHOR, industry_block)
    return text


def write_rotation_watch_html() -> dict[str, Any]:
    """CLI-facing entrypoint. Reads config.GOAT_ROTATION_EXPORT_JSON_PATH +
    config.GOAT_ROTATION_WATCH_TEMPLATE_PATH, writes
    config.GOAT_ROTATION_WATCH_OUTPUT_PATH. Returns a summary dict rather than raising
    on a missing/empty export -- same fail-safe-skip posture as every other goat scan
    command (a bad day's data means no update, not a crashed timer)."""
    if not config.GOAT_ROTATION_EXPORT_JSON_PATH.exists():
        return {"ok": False, "reason": "rotation-history-export.json not found"}
    export_data = json.loads(config.GOAT_ROTATION_EXPORT_JSON_PATH.read_text(encoding="utf-8"))
    scopes = export_data.get("scopes", {})
    sector_rows = scopes.get("sector", [])
    industry_rows = scopes.get("industry_full", [])
    if not sector_rows or not industry_rows:
        return {"ok": False, "reason": "export JSON has an empty scope"}

    template_text = config.GOAT_ROTATION_WATCH_TEMPLATE_PATH.read_text(encoding="utf-8")
    html = build_rotation_watch_html(export_data, template_text)
    config.GOAT_ROTATION_WATCH_OUTPUT_PATH.write_text(html, encoding="utf-8")
    return {
        "ok": True,
        "generated_at": export_data.get("generated_at"),
        "sector_rows": len(sector_rows),
        "industry_rows": len(industry_rows),
    }
