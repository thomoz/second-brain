from __future__ import annotations

from superinvestor_filings import config


def test_tracked_shape_and_pabrai_ciks():
    assert "pabrai" in config.SUPERINVESTOR_TRACKED
    pabrai = config.SUPERINVESTOR_TRACKED["pabrai"]
    assert pabrai["display"]
    assert len(pabrai["edgar_ciks"]) == 6
    assert all(c.isdigit() for c in pabrai["edgar_ciks"])  # unpadded digit strings
    assert pabrai["india_aliases"]


def test_edgar_form_set_contents():
    assert config.SUPERINVESTOR_EDGAR_FORMS == {
        "SC 13D", "SC 13D/A", "SC 13G", "SC 13G/A", "3", "4", "4/A", "5",
    }


def test_lookback_and_watermark_key():
    assert config.SUPERINVESTOR_LOOKBACK_DAYS == 30
    assert isinstance(config.SUPERINVESTOR_FIRST_SEED_WATERMARK, str)


def test_pkg_dir_points_at_package_root():
    assert config.PKG_DIR.name == "superinvestor-filings"
    assert (config.PKG_DIR / "superinvestor_filings").is_dir()
