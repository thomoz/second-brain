from __future__ import annotations

from datetime import date, timedelta

from goat import config as goat_config, db as goat_db
from goat import insider_pattern_analysis as ipa


def _seed_outcome(
    conn, *, dedup_key, ticker="ACME", trade_type="P", trade_date=None, value=50_000.0,
    pct_owned_change=None, title="", insider_name="Jane Doe", kind="discovery",
    horizon_days=7, excess_pct_change=5.0,
):
    trade_date = trade_date or date.today().isoformat()
    goat_db.insert_goat_insider_filing_seen(
        conn, dedup_key=dedup_key, ticker=ticker, filing_date=trade_date, trade_date=trade_date,
        insider_name=insider_name, trade_type=trade_type, value=value, kind=kind,
        pct_owned_change=pct_owned_change, title=title,
    )
    goat_db.insert_price_outcome(
        conn, dedup_key=dedup_key, ticker=ticker, trade_type=trade_type, horizon_days=horizon_days,
        pct_change=excess_pct_change, benchmark_pct_change=0.0, excess_pct_change=excess_pct_change,
        snapshot_date=date.today().isoformat(),
    )


def test_classify_trade_size_buckets():
    assert ipa._classify_trade_size(10_000) == "<$50k"
    assert ipa._classify_trade_size(50_000) == "$50k-250k"
    assert ipa._classify_trade_size(250_000) == "$250k-1M"
    assert ipa._classify_trade_size(1_000_000) == "$1M+"


def test_classify_pct_owned_buckets():
    assert ipa._classify_pct_owned(None) == "New"
    assert ipa._classify_pct_owned(3.0) == "<5%"
    assert ipa._classify_pct_owned(-10.0) == "5-25%"
    assert ipa._classify_pct_owned(50.0) == "25-100%"


def test_classify_title_buckets():
    assert ipa._classify_title("CFO") == "Officer/Chair"
    assert ipa._classify_title("Exec COB") == "Officer/Chair"
    assert ipa._classify_title("Chief Strategy Officer") == "Officer/Chair"
    assert ipa._classify_title("Pres") == "Officer/Chair"
    assert ipa._classify_title("Dir") == "Director"
    assert ipa._classify_title("10% Owner") == "10% Owner"
    assert ipa._classify_title("See Remarks") == "Other"
    assert ipa._classify_title("") == "Other"


def test_compute_pattern_analysis_gates_slices_below_min_sample(db_conn):
    for i in range(5):
        _seed_outcome(db_conn, dedup_key=f"k{i}", value=10_000.0)
    analysis = ipa.compute_pattern_analysis(db_conn)
    for label, stats in analysis["trade_size"].items():
        assert stats["status"] == "insufficient_data"


def test_compute_pattern_analysis_reports_stats_at_min_sample(db_conn, monkeypatch):
    monkeypatch.setattr(goat_config, "GOAT_INSIDER_PATTERN_MIN_SAMPLE", 3)
    for i in range(3):
        _seed_outcome(db_conn, dedup_key=f"k{i}", value=10_000.0, trade_type="P", excess_pct_change=5.0)
    analysis = ipa.compute_pattern_analysis(db_conn)
    stats = analysis["trade_size"]["<$50k"]
    assert stats["status"] == "ok"
    assert stats["n"] == 3
    assert stats["pct_direction_confirmed"] == 100.0


def test_compute_pattern_analysis_excludes_holdings_watch(db_conn, monkeypatch):
    monkeypatch.setattr(goat_config, "GOAT_INSIDER_PATTERN_MIN_SAMPLE", 1)
    _seed_outcome(db_conn, dedup_key="k1", kind="holdings_watch")
    analysis = ipa.compute_pattern_analysis(db_conn)
    assert analysis["total_filings"] == 0


def test_compute_pattern_analysis_pct_owned_none_buckets_as_new_not_dropped(db_conn, monkeypatch):
    monkeypatch.setattr(goat_config, "GOAT_INSIDER_PATTERN_MIN_SAMPLE", 1)
    _seed_outcome(db_conn, dedup_key="k1", pct_owned_change=None)
    analysis = ipa.compute_pattern_analysis(db_conn)
    assert analysis["pct_owned"]["New"]["n"] == 1


def test_compute_pattern_analysis_clusters_distinct_insiders_same_day(db_conn, monkeypatch):
    monkeypatch.setattr(goat_config, "GOAT_INSIDER_PATTERN_MIN_SAMPLE", 1)
    today = date.today().isoformat()
    _seed_outcome(db_conn, dedup_key="k1", ticker="ACME", trade_date=today, insider_name="Jane Doe")
    _seed_outcome(db_conn, dedup_key="k2", ticker="ACME", trade_date=today, insider_name="John Smith")
    analysis = ipa.compute_pattern_analysis(db_conn)
    assert analysis["cluster"]["Clustered"]["n"] == 2
    assert "Isolated" not in analysis["cluster"]


def test_compute_pattern_analysis_single_insider_is_isolated_not_clustered(db_conn, monkeypatch):
    monkeypatch.setattr(goat_config, "GOAT_INSIDER_PATTERN_MIN_SAMPLE", 1)
    _seed_outcome(db_conn, dedup_key="k1", ticker="ACME")
    analysis = ipa.compute_pattern_analysis(db_conn)
    assert analysis["cluster"]["Isolated"]["n"] == 1


def test_render_pattern_analysis_report_includes_disclaimer():
    analysis = {
        "trade_size": {}, "pct_owned": {}, "title_role": {}, "buy_vs_sell": {}, "cluster": {},
        "velocity_early_confirms_later": {"status": "insufficient_data", "n": 0},
        "total_outcome_rows": 0, "total_filings": 0,
    }
    report = ipa.render_pattern_analysis_report(analysis)
    assert "correlational" in report.lower()
    assert "not a validated trading strategy" in report


def test_render_pattern_analysis_report_shows_insufficient_data_fallback():
    analysis = {
        "trade_size": {"<$50k": {"status": "insufficient_data", "n": 5}},
        "pct_owned": {}, "title_role": {}, "buy_vs_sell": {}, "cluster": {},
        "velocity_early_confirms_later": {"status": "insufficient_data", "n": 0},
        "total_outcome_rows": 5, "total_filings": 5,
    }
    report = ipa.render_pattern_analysis_report(analysis)
    assert "not enough data yet (n=5" in report
