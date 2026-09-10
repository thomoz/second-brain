"""Quant half of the moat score -- a pure function over a market_data.TickerData
plus the LLM extraction dict plus annual revenue history. Deliberately
yfinance-`.info`-thin, mirroring cash_value_scan.compute_cash_value_metrics: returns
None when the key fields needed to assess a software moat are absent.

Six sub-metrics, each ramped 0-100 and weighted (config.MOAT_QUANT_WEIGHTS):
gross margin, FCF margin, operating margin, Rule of 40, revenue durability, and
disclosed recurring-revenue %. An unavailable-but-not-negative sub-metric scores the
neutral 50 rather than dragging the blend down.
"""

from __future__ import annotations

from typing import Any

from . import config


def _ramp(value: float | None, zero_at: float, hundred_at: float) -> float:
    """Linear map from [zero_at, hundred_at] onto [0, 100], clamped. Handles a
    descending ramp (hundred_at < zero_at). A None value scores the neutral 50."""
    if value is None:
        return config.MOAT_QUANT_NEUTRAL
    if hundred_at == zero_at:
        return 100.0 if value >= hundred_at else 0.0
    frac = (value - zero_at) / (hundred_at - zero_at)
    return max(0.0, min(100.0, frac * 100.0))


def _revenue_durability_subscore(revenue_history: list[float] | None) -> tuple[float | None, float]:
    """Returns (worst_yoy_pct_or_None, subscore). Needs >= 3 annual points, else the
    subscore degrades to neutral. worst >= 0 (revenue never declined YoY) -> 100;
    worst <= -10 -> 0; in between, _ramp(worst, -10, 0) * 0.7 (a -5% worst year ~= 35,
    a -0.1% worst year ~= 70)."""
    if revenue_history is None or len(revenue_history) < 3:
        return None, config.MOAT_QUANT_NEUTRAL
    changes: list[float] = []
    for prev, cur in zip(revenue_history, revenue_history[1:]):
        if prev == 0:
            continue
        changes.append((cur - prev) / prev * 100.0)
    if not changes:
        return None, config.MOAT_QUANT_NEUTRAL
    worst = min(changes)
    if worst >= 0:
        return worst, 100.0
    if worst <= config.MOAT_REVENUE_DURABILITY_RAMP[0]:
        return worst, 0.0
    return worst, _ramp(worst, *config.MOAT_REVENUE_DURABILITY_RAMP) * 0.7


def compute_quant_metrics(
    data, extraction: dict[str, Any], revenue_history: list[float] | None
) -> dict[str, Any] | None:
    """`data` is a market_data.TickerData. Returns None when marketCap is absent /
    below config.MOAT_MIN_MARKET_CAP_USD, or when grossMargins is absent (can't assess
    a software moat without a margin). yfinance margins/growth are FRACTIONS (0.78,
    not 78); freeCashflow/totalRevenue are absolute."""
    info = data.info
    market_cap = info.get("marketCap")
    if not market_cap or market_cap < config.MOAT_MIN_MARKET_CAP_USD:
        return None
    gross_margin = info.get("grossMargins")
    if gross_margin is None:
        return None

    operating_margin = info.get("operatingMargins")
    total_revenue = info.get("totalRevenue")
    free_cashflow = info.get("freeCashflow")
    fcf_margin = (
        free_cashflow / total_revenue
        if free_cashflow is not None and total_revenue
        else None
    )

    revenue_growth = info.get("revenueGrowth")
    rule_of_40: float | None
    if revenue_growth is None and fcf_margin is None:
        rule_of_40 = None
    else:
        rule_of_40 = (revenue_growth or 0.0) * 100.0 + (fcf_margin or 0.0) * 100.0

    worst_revenue_yoy, revenue_durability_sub = _revenue_durability_subscore(revenue_history)

    recurring_revenue_pct = extraction.get("recurring_revenue_pct")
    recurring_frac = recurring_revenue_pct / 100.0 if recurring_revenue_pct is not None else None

    sub_scores = {
        "gross_margin": _ramp(gross_margin, *config.MOAT_GROSS_MARGIN_RAMP),
        "fcf_margin": _ramp(fcf_margin, *config.MOAT_FCF_MARGIN_RAMP),
        "operating_margin": _ramp(operating_margin, *config.MOAT_OPERATING_MARGIN_RAMP),
        "rule_of_40": _ramp(rule_of_40, *config.MOAT_RULE_OF_40_RAMP),
        "revenue_durability": revenue_durability_sub,
        "recurring_revenue": _ramp(recurring_frac, *config.MOAT_RECURRING_REVENUE_RAMP),
    }

    quant_score = sum(
        sub_scores[k] * config.MOAT_QUANT_WEIGHTS[k] for k in config.MOAT_QUANT_WEIGHTS
    )

    # Disclosure bonus -- each disclosed positive worth 1/3 of the max; nulls not counted.
    nrr = extraction.get("nrr_pct")
    rpo_yoy = extraction.get("rpo_yoy_pct")
    logo_churn = extraction.get("logo_churn_pct")
    disclosed_positives = sum([
        nrr is not None and nrr >= 110,
        rpo_yoy is not None and rpo_yoy > 0,
        logo_churn is not None and logo_churn < 10,
    ])
    bonus = config.MOAT_DISCLOSURE_BONUS_MAX * (disclosed_positives / 3.0)
    quant_score = min(100.0, quant_score + bonus)

    return {
        "quant_score": round(quant_score, 1),
        "sub_scores": {k: round(v, 1) for k, v in sub_scores.items()},
        "gross_margin": gross_margin,
        "fcf_margin": fcf_margin,
        "operating_margin": operating_margin,
        "rule_of_40": rule_of_40,
        "worst_revenue_yoy": worst_revenue_yoy,
        "market_cap": market_cap,
        "currency": info.get("financialCurrency") or info.get("currency"),
        "sector": info.get("sector"),
        "disclosure_bonus": round(bonus, 1),
    }
