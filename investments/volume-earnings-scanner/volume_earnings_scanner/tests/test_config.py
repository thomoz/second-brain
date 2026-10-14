from __future__ import annotations

from volume_earnings_scanner import config


def test_path_constants_resolve():
    # VE_CANDIDATES_MD_PATH.parent is monkeypatched to tmp_path by the autouse
    # _isolate_report_paths fixture -- only the filename is stable to assert on here.
    assert config.PKG_DIR.name == "volume-earnings-scanner"
    assert config.VE_CANDIDATES_MD_PATH.name == "volume-earnings-candidates-pending-review.md"


def test_db_path_reexported():
    assert config.DB_PATH.name == "investments.db"


def test_finviz_screens_are_two_cap_buckets():
    assert len(config.VE_FINVIZ_SCREENS) == 2
    assert "cap_microunder" in config.VE_FINVIZ_SCREENS[0]
    assert "cap_small" in config.VE_FINVIZ_SCREENS[1]


def test_earnings_quarter_thresholds_ordered():
    assert config.VE_EARNINGS_MIN_QUARTERS_FOR_YOY_ACCEL > config.VE_EARNINGS_MIN_QUARTERS_FOR_RECORD
