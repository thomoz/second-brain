"""Blend the quant and qualitative halves into the 0-100 moat score, and assemble
the full row dict the report + staging table use.

A row with no qualitative half (no readable 10-K, or a failed rubric call) has
moat_score = None and stageable = False -- it is shown quant-only in the report but
never staged.
"""

from __future__ import annotations

import json
from typing import Any

from . import config

_RUBRIC_KEYS = (
    "system_of_record",
    "switching_costs",
    "ecosystem_lockin",
    "regulatory_entrenchment",
    "workflow_breadth",
    "mission_criticality",
)


def blend_score(quant_score: float, qualitative_score: float) -> float:
    w = config.MOAT_BLEND_QUANT_WEIGHT
    return round(w * quant_score + (1.0 - w) * qualitative_score, 1)


def assemble_row(
    ticker: str,
    industry: str,
    company: str,
    quant: dict[str, Any],
    qualitative: dict[str, Any] | None,
    tags: list[str],
) -> dict[str, Any]:
    quant_score = quant["quant_score"]
    if qualitative is None:
        moat_score: float | None = None
        qualitative_score: float | None = None
        rubric_sub_scores = {k: None for k in _RUBRIC_KEYS}
        anti_signals: list[str] = []
        thesis = "No 10-K available -- quant-only, not stageable."
        filing_date = None
    else:
        qualitative_score = qualitative["qualitative_score"]
        moat_score = blend_score(quant_score, qualitative_score)
        rubric_sub_scores = dict(qualitative["sub_scores"])
        anti_signals = list(qualitative["anti_signals"])
        thesis = qualitative["thesis"]
        filing_date = qualitative.get("filing_date")

    sub_scores_json = json.dumps({
        "quant": quant.get("sub_scores", {}),
        "qualitative": rubric_sub_scores,
        "anti_signals": anti_signals,
    })

    return {
        "ticker": ticker,
        "industry": industry,
        "company": company,
        "moat_score": moat_score,
        "quant_score": quant_score,
        "qualitative_score": qualitative_score,
        "stageable": moat_score is not None,
        "rubric_sub_scores": rubric_sub_scores,
        "anti_signals": anti_signals,
        "thesis": thesis,
        "tags": tags,
        "worst_revenue_yoy": quant.get("worst_revenue_yoy"),
        "gross_margin": quant.get("gross_margin"),
        "fcf_margin": quant.get("fcf_margin"),
        "market_cap": quant.get("market_cap"),
        "currency": quant.get("currency"),
        "filing_date": filing_date,
        "sub_scores_json": sub_scores_json,
    }
