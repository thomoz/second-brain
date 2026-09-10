from __future__ import annotations

from ai_resistant_moat_scanner import config as c


def test_quant_weights_sum_to_one():
    assert abs(sum(c.MOAT_QUANT_WEIGHTS.values()) - 1.0) < 1e-9


def test_db_path_is_investments_db():
    assert c.DB_PATH.name == "investments.db"


def test_every_ramp_is_a_2_tuple():
    ramps = [
        c.MOAT_GROSS_MARGIN_RAMP, c.MOAT_FCF_MARGIN_RAMP, c.MOAT_OPERATING_MARGIN_RAMP,
        c.MOAT_RULE_OF_40_RAMP, c.MOAT_REVENUE_DURABILITY_RAMP, c.MOAT_RECURRING_REVENUE_RAMP,
    ]
    for r in ramps:
        assert isinstance(r, tuple) and len(r) == 2


def test_seed_list_has_no_dupes():
    assert len(c.MOAT_SEED_TICKERS) == len(set(c.MOAT_SEED_TICKERS))


def test_stage_threshold_starts_at_80():
    assert c.MOAT_STAGE_THRESHOLD == 80.0


def test_finviz_sector_screens_all_carry_a_sector_token():
    for screen in c.MOAT_FINVIZ_SECTOR_SCREENS:
        assert any(tok.startswith("sec_") for tok in screen.split(","))
