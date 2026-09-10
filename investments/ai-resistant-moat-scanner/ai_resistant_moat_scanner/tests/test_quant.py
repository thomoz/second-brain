from __future__ import annotations

from mytrader.market_data import TickerData

from ai_resistant_moat_scanner import config
from ai_resistant_moat_scanner.quant import _ramp, compute_quant_metrics


def _data(**info):
    return TickerData(ticker=info.get("_ticker", "CRM"), info=info, dividends=None)


# --- _ramp -------------------------------------------------------------------

def test_ramp_boundaries_and_midpoint():
    assert _ramp(0.50, 0.50, 0.75) == 0.0
    assert _ramp(0.75, 0.50, 0.75) == 100.0
    assert _ramp(0.625, 0.50, 0.75) == 50.0
    assert _ramp(1.0, 0.50, 0.75) == 100.0  # clamped


def test_ramp_descending():
    assert _ramp(-10.0, -10.0, 0.0) == 0.0
    assert _ramp(0.0, -10.0, 0.0) == 100.0
    assert _ramp(-5.0, -10.0, 0.0) == 50.0


def test_ramp_none_is_neutral():
    assert _ramp(None, 0.0, 1.0) == config.MOAT_QUANT_NEUTRAL


# --- compute_quant_metrics -------------------------------------------------

def test_returns_none_below_market_cap_floor():
    assert compute_quant_metrics(_data(marketCap=1_000_000_000, grossMargins=0.8), {}, None) is None


def test_returns_none_without_gross_margin():
    assert compute_quant_metrics(_data(marketCap=5_000_000_000), {}, None) is None


def test_known_info_produces_hand_computed_quant_score():
    data = _data(
        marketCap=5_000_000_000,
        grossMargins=0.625,       # -> gross sub 50
        operatingMargins=0.125,   # -> op sub 50
        freeCashflow=10.0,
        totalRevenue=100.0,       # fcf_margin 0.1 -> fcf sub 50; rule40 = 0 + 10 -> sub 0
    )
    metrics = compute_quant_metrics(data, {}, None)  # no revenue history -> durability neutral 50
    # 50*.25 + 50*.20 + 50*.15 + 0*.15 + 50*.15 + 50*.10 = 42.5
    assert metrics["quant_score"] == 42.5
    assert metrics["disclosure_bonus"] == 0.0
    assert metrics["sub_scores"]["rule_of_40"] == 0.0


def test_gross_margin_is_a_fraction_not_a_percent():
    metrics = compute_quant_metrics(_data(marketCap=5e9, grossMargins=0.78), {}, None)
    assert metrics["sub_scores"]["gross_margin"] > 90  # 0.78 is high, not clamped to 0


def test_revenue_durability_neutral_when_history_too_short():
    metrics = compute_quant_metrics(_data(marketCap=5e9, grossMargins=0.7), {}, [100.0, 110.0])
    assert metrics["sub_scores"]["revenue_durability"] == config.MOAT_QUANT_NEUTRAL
    assert metrics["worst_revenue_yoy"] is None


def test_revenue_durability_100_when_never_declined():
    metrics = compute_quant_metrics(_data(marketCap=5e9, grossMargins=0.7), {}, [100.0, 110.0, 121.0])
    assert metrics["sub_scores"]["revenue_durability"] == 100.0
    assert metrics["worst_revenue_yoy"] == 10.0


def test_disclosure_bonus_scales_with_disclosed_positives():
    base = _data(marketCap=5e9, grossMargins=0.7)
    zero = compute_quant_metrics(base, {}, None)["disclosure_bonus"]
    two = compute_quant_metrics(base, {"nrr_pct": 115, "rpo_yoy_pct": 10}, None)["disclosure_bonus"]
    three = compute_quant_metrics(
        base, {"nrr_pct": 115, "rpo_yoy_pct": 10, "logo_churn_pct": 4}, None
    )["disclosure_bonus"]
    assert zero == 0.0
    assert two == round(config.MOAT_DISCLOSURE_BONUS_MAX * 2 / 3, 1)
    assert three == config.MOAT_DISCLOSURE_BONUS_MAX
