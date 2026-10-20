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
    assert config.GOAT_INDUSTRY_FULL_PRIMARY_WINDOW == "perf_week"
    rows = [
        _row("Low", perf_week=-5.0),
        _row("High", perf_week=10.0),
        _row("Mid", perf_week=2.0),
    ]
    ranked = industry_rotation_full.rank_all_industries(rows)
    assert [r["name"] for r in ranked] == ["High", "Mid", "Low"]


def test_rank_all_industries_assigns_rank_starting_at_one():
    rows = [_row("A", perf_week=1.0), _row("B", perf_week=2.0)]
    ranked = industry_rotation_full.rank_all_industries(rows)
    assert [r["rank"] for r in ranked] == [1, 2]
    assert ranked[0]["name"] == "B"


def test_rank_all_industries_missing_data_sorts_last():
    rows = [
        _row("Known", perf_week=1.0),
        _row("Unknown", perf_week=None),
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


def test_render_full_industry_ranking_report_top_bottom_10_rank_column_matches_display_order():
    # 15 rows, distinct perf_week values -- Shaun's bug report 2026-10-20: the
    # Rank column shown in Top/Bottom 10 must be the SAME field the rows are
    # ordered by (Perf Week), not some other window's overall position, so it
    # reads as a clean contiguous sequence rather than scattered numbers.
    rows = [_row(f"Industry{i}", perf_week=float(i)) for i in range(15)]
    ranking = industry_rotation_full.rank_all_industries(rows)
    report = industry_rotation_full.render_full_industry_ranking_report({"ranking": ranking})

    assert "Top 10 Rising (by Perf Week)" in report
    assert "Bottom 10 Falling (by Perf Week)" in report

    top10 = industry_rotation_full._sorted_by_primary_window(ranking, descending=True)[:10]
    assert [r["name"] for r in top10] == [f"Industry{i}" for i in range(14, 4, -1)]
    assert [r["rank"] for r in top10] == list(range(1, 11))  # contiguous, matches display order

    bottom10 = industry_rotation_full._sorted_by_primary_window(ranking, descending=False)[:10]
    assert [r["name"] for r in bottom10] == [f"Industry{i}" for i in range(0, 10)]
    assert [r["rank"] for r in bottom10] == list(range(15, 5, -1))  # contiguous, matches display order


def test_sorted_by_primary_window_missing_data_sorts_last_in_both_directions():
    rows = [
        _row("Known", perf_week=1.0),
        _row("Unknown", perf_week=None),
    ]
    descending = industry_rotation_full._sorted_by_primary_window(rows, descending=True)
    ascending = industry_rotation_full._sorted_by_primary_window(rows, descending=False)
    assert [r["name"] for r in descending] == ["Known", "Unknown"]
    assert [r["name"] for r in ascending] == ["Known", "Unknown"]


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
