from __future__ import annotations

from goat import config, db as goat_db, industry_rotation_full, monitor


def _row(name: str, **perf) -> dict:
    base = {
        "name": name, "perf_week": None, "perf_month": None, "perf_quarter": None,
        "perf_half": None, "perf_year": None, "perf_ytd": None,
        "avg_volume": "1.00M", "rel_volume": 1.0, "volume": "1.00M", "change_pct": None,
    }
    base.update(perf)
    return base


def test_rank_all_industries_orders_by_primary_window_descending():
    assert config.GOAT_INDUSTRY_FULL_PRIMARY_WINDOW == "perf_half"
    rows = [
        _row("Low", perf_half=-5.0),
        _row("High", perf_half=10.0),
        _row("Mid", perf_half=2.0),
    ]
    ranked = industry_rotation_full.rank_all_industries(rows)
    assert [r["name"] for r in ranked] == ["High", "Mid", "Low"]


def test_rank_all_industries_assigns_rank_starting_at_one():
    rows = [_row("A", perf_half=1.0), _row("B", perf_half=2.0)]
    ranked = industry_rotation_full.rank_all_industries(rows)
    assert [r["rank"] for r in ranked] == [1, 2]
    assert ranked[0]["name"] == "B"


def test_rank_all_industries_missing_data_sorts_last():
    rows = [
        _row("Known", perf_half=1.0),
        _row("Unknown", perf_half=None),
    ]
    ranked = industry_rotation_full.rank_all_industries(rows)
    assert [r["name"] for r in ranked] == ["Known", "Unknown"]
    assert ranked[-1]["rank"] == 2


def test_render_full_industry_ranking_report_shows_all_six_perf_columns_and_no_not_covered_section():
    rows = [
        _row(
            "Semiconductors", perf_week=1.0, perf_month=2.0, perf_quarter=3.0,
            perf_half=4.0, perf_year=5.0, perf_ytd=6.0,
        ),
    ]
    ranking = industry_rotation_full.rank_all_industries(rows)
    report = industry_rotation_full.render_full_industry_ranking_report({"ranking": ranking})
    assert "Not Covered" not in report
    for label in ["Perf Week", "Perf Month", "Perf Quarter", "Perf Half", "Perf Year", "Perf YTD"]:
        assert label in report
    assert "Semiconductors" in report
    assert "+4.00%" in report


def test_render_full_industry_ranking_report_top_bottom_10_ordered_by_perf_week():
    # Overall rank (Perf Half) deliberately scrambled relative to Perf Week, so
    # a passing test proves the sections re-sort by Perf Week rather than just
    # slicing the already-Perf-Half-ordered ranking.
    rows = [
        _row("HighHalfLowWeek", perf_half=50.0, perf_week=-9.0),
        _row("LowHalfHighWeek", perf_half=-50.0, perf_week=9.0),
        _row("Mid", perf_half=0.0, perf_week=0.0),
    ]
    ranking = industry_rotation_full.rank_all_industries(rows)
    report = industry_rotation_full.render_full_industry_ranking_report({"ranking": ranking})

    top_section = report.split("## Top 10 Rising")[1].split("## Bottom 10 Falling")[0]
    assert top_section.index("LowHalfHighWeek") < top_section.index("Mid")
    assert top_section.index("Mid") < top_section.index("HighHalfLowWeek")

    bottom_section = report.split("## Bottom 10 Falling")[1].split("## Full Ranking")[0]
    assert bottom_section.index("HighHalfLowWeek") < bottom_section.index("Mid")
    assert bottom_section.index("Mid") < bottom_section.index("LowHalfHighWeek")

    assert "Top 10 Rising (by Perf Week)" in report
    assert "Bottom 10 Falling (by Perf Week)" in report


def test_render_full_industry_ranking_report_shows_no_flow_section_when_absent():
    ranking = industry_rotation_full.rank_all_industries([_row("Semiconductors", perf_half=4.0)])
    report = industry_rotation_full.render_full_industry_ranking_report({"ranking": ranking})
    assert "Rotation Flow" not in report


# --- capture_full_industry_snapshot --------------------------------------------

def test_capture_full_industry_snapshot_first_run_has_no_prior_flow(db_conn):
    ranking = industry_rotation_full.rank_all_industries([
        _row("Semiconductors", perf_half=4.0, perf_week=1.0),
    ])
    result = industry_rotation_full.capture_full_industry_snapshot(db_conn, ranking)
    assert result["rotation_flow"] is None
    assert result["short_window_flow"] is None
    rows = goat_db.get_rotation_snapshots_for_date(db_conn, "industry_full", monitor._today_sydney())
    assert len(rows) == 1
    assert rows[0]["ticker"] == "Semiconductors"  # industry name repurposing the ticker column
    assert rows[0]["return_pct"] == 4.0


def test_capture_full_industry_snapshot_detects_transition_from_prior_day(db_conn):
    goat_db.insert_rotation_snapshots(
        db_conn, scope="industry_full", snapshot_date="2020-01-01",
        rows=[{"ticker": "Semiconductors", "name": "Semiconductors", "return_pct": -5.0,
               "return_pct_1w": -1.0, "rank": 10}],
        label_key="name",
    )
    ranking = industry_rotation_full.rank_all_industries([
        _row("Semiconductors", perf_half=4.0, perf_week=1.0),
    ])
    result = industry_rotation_full.capture_full_industry_snapshot(db_conn, ranking)
    assert result["rotation_flow"]["summary"]["falling_to_rising"] == 1
    assert result["short_window_flow"]["summary"]["falling_to_rising"] == 1


def test_render_full_industry_ranking_report_includes_flow_section_when_present(db_conn):
    ranking = industry_rotation_full.rank_all_industries([
        _row("Semiconductors", perf_half=4.0, perf_week=1.0),
    ])
    flow = industry_rotation_full.capture_full_industry_snapshot(db_conn, ranking)
    report = industry_rotation_full.render_full_industry_ranking_report({"ranking": ranking, **flow})
    assert "Rotation Flow" in report
    assert "No prior snapshot yet." in report
