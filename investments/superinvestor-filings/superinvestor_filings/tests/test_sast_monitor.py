from __future__ import annotations

import json
import pathlib

import pytest
from mytrader.db import get_sync_watermark, set_sync_watermark

from superinvestor_filings import config, db, sast_monitor

FIXTURES = pathlib.Path(__file__).parent / "fixtures"
BSE_ROWS = json.loads((FIXTURES / "bse_sast_sample.json").read_text(encoding="utf-8"))["Table"]


@pytest.fixture(autouse=True)
def _no_real_bse(monkeypatch):
    monkeypatch.setattr(sast_monitor, "fetch_sast_disclosures", lambda prev, to: list(BSE_ROWS))


def _seed_done(conn):
    set_sync_watermark(conn, config.SUPERINVESTOR_SAST_FIRST_SEED_WATERMARK, "done")


def test_reg_label():
    assert sast_monitor._reg_label("Disclosures under Reg. 29(1) of SEBI (SAST) Regulations, 2011") == "SAST Reg 29(1)"
    assert sast_monitor._reg_label("Disclosures under Reg. 29(2) of SEBI (SAST) Regulations, 2011") == "SAST Reg 29(2)"
    assert sast_monitor._reg_label("Disclosures under Reg. 31(1) and 31(2) of SEBI (SAST) Regulations, 2011") is None
    assert sast_monitor._reg_label("Closure of Trading Window") is None


def test_acquirer_name_from_headline():
    h = ("The Exchange has received the disclosure under Regulation 29(2) of SEBI "
         "(Substantial Acquisition of Shares & Takeovers) Regulations, 2011 for Dalal Street LLC")
    assert sast_monitor._acquirer_name(h, "") == "Dalal Street LLC"


def test_acquirer_name_fallback_to_newssub_ignores_boilerplate_tail():
    # NEWSSUB whose tail is just the reg boilerplate -> no acquirer
    sub = "Rain Industries Ltd - 500111 - Disclosures under Reg. 29(2) of SEBI (SAST) Regulations, 2011"
    assert sast_monitor._acquirer_name("", sub) == ""


def test_match_tracked_filer():
    assert sast_monitor._match_tracked_filer("Dalal Street LLC") == ("pabrai", "Mohnish Pabrai / Dalal Street")
    assert sast_monitor._match_tracked_filer("MOHNISH PABRAI") == ("pabrai", "Mohnish Pabrai / Dalal Street")
    assert sast_monitor._match_tracked_filer("Bhavik N Mehta") is None
    assert sast_monitor._match_tracked_filer("") is None


def test_scan_india_alerts_on_matching_reg29_only(db_conn):
    _seed_done(db_conn)
    result = sast_monitor.scan_india(db_conn)
    # 2 rows match Pabrai AND are Reg 29 (the Reg 31 row for "Dalal Street LLC" is skipped)
    assert len(result["new_filings"]) == 2
    issuers = {a["issuer"] for a in result["new_filings"]}
    assert issuers == {"Rain Industries Placeholder Ltd", "Sunteck Placeholder Realty Ltd"}
    reg1 = next(a for a in result["new_filings"] if a["form_type"] == "SAST Reg 29(1)")
    assert reg1["material_crossing"] == "5% cross"
    assert "Mohnish Pabrai" in reg1["summary"]
    assert db.count_seen(db_conn) == 2


def test_scan_india_quiet_on_repeat_run(db_conn):
    _seed_done(db_conn)
    sast_monitor.scan_india(db_conn)
    result = sast_monitor.scan_india(db_conn)
    assert result["new_filings"] == []
    assert db.count_seen(db_conn) == 2


def test_scan_india_first_run_seeds_silently(db_conn):
    assert get_sync_watermark(db_conn, config.SUPERINVESTOR_SAST_FIRST_SEED_WATERMARK) is None
    result = sast_monitor.scan_india(db_conn)
    assert result["first_seed"] is True
    assert result["new_filings"] == []
    assert db.count_seen(db_conn) == 2  # seeded, not alerted
    assert get_sync_watermark(db_conn, config.SUPERINVESTOR_SAST_FIRST_SEED_WATERMARK) is not None


def test_scan_india_graceful_on_fetch_failure(db_conn, monkeypatch):
    _seed_done(db_conn)
    monkeypatch.setattr(sast_monitor, "fetch_sast_disclosures", lambda prev, to: None)
    result = sast_monitor.scan_india(db_conn)  # must not raise
    assert result["new_filings"] == []
    assert result["first_seed"] is False
    assert db.count_seen(db_conn) == 0
