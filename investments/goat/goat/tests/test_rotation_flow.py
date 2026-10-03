from __future__ import annotations

from goat import rotation_flow


def _prev_row(ticker, return_pct, return_pct_1w=None, label="Technology"):
    return {"ticker": ticker, "label": label, "return_pct": return_pct, "return_pct_1w": return_pct_1w}


def _curr_row(ticker, return_pct, rising=None, return_pct_1w=None, rising_1w=None, label="Technology"):
    return {
        "ticker": ticker, "sector_label": label, "return_pct": return_pct,
        "rising": rising if rising is not None else (return_pct is not None and return_pct > 0),
        "return_pct_1w": return_pct_1w, "rising_1w": rising_1w,
    }


def test_compute_flow_detects_rising_to_falling_transition():
    previous = [_prev_row("XLK", return_pct=5.0)]
    current = [_curr_row("XLK", return_pct=-3.0)]
    flow = rotation_flow.compute_flow(previous, current, label_key="sector_label")
    assert flow["summary"]["rising_to_falling"] == 1
    assert flow["transitions"][0] == {"ticker": "XLK", "label": "Technology", "from": True, "to": False}


def test_compute_flow_detects_falling_to_rising_transition():
    previous = [_prev_row("XLK", return_pct=-5.0)]
    current = [_curr_row("XLK", return_pct=3.0)]
    flow = rotation_flow.compute_flow(previous, current, label_key="sector_label")
    assert flow["summary"]["falling_to_rising"] == 1
    assert flow["transitions"][0]["from"] is False
    assert flow["transitions"][0]["to"] is True


def test_compute_flow_unchanged_rising_and_falling_counted_not_transitioned():
    previous = [_prev_row("XLK", return_pct=5.0), _prev_row("XLF", return_pct=-5.0)]
    current = [
        _curr_row("XLK", return_pct=8.0),
        _curr_row("XLF", return_pct=-8.0),
    ]
    flow = rotation_flow.compute_flow(previous, current, label_key="sector_label")
    assert flow["transitions"] == []
    assert flow["summary"]["unchanged_rising"] == 1
    assert flow["summary"]["unchanged_falling"] == 1


def test_compute_flow_ticker_missing_from_previous_counts_as_no_prior():
    previous = [_prev_row("XLK", return_pct=5.0)]
    current = [
        _curr_row("XLK", return_pct=8.0),
        _curr_row("XLC", return_pct=2.0),
    ]
    flow = rotation_flow.compute_flow(previous, current, label_key="sector_label")
    assert flow["no_prior_count"] == 1
    assert flow["transitions"] == []


def test_compute_flow_none_return_on_either_side_excluded_not_a_transition():
    previous = [_prev_row("XLK", return_pct=None), _prev_row("XLF", return_pct=5.0)]
    current = [
        _curr_row("XLK", return_pct=8.0),
        _curr_row("XLF", return_pct=None, rising=None),
    ]
    flow = rotation_flow.compute_flow(previous, current, label_key="sector_label")
    assert flow["transitions"] == []
    assert flow["summary"]["unchanged_rising"] == 0
    assert flow["summary"]["unchanged_falling"] == 0
    assert flow["no_prior_count"] == 0


def test_compute_flow_short_window_field_works_identically_to_long_window():
    previous = [_prev_row("XLK", return_pct=5.0, return_pct_1w=-2.0)]
    current = [_curr_row("XLK", return_pct=8.0, return_pct_1w=4.0)]
    flow = rotation_flow.compute_flow(previous, current, label_key="sector_label", field="rising_1w")
    assert flow["summary"]["falling_to_rising"] == 1
    assert flow["transitions"][0]["from"] is False
    assert flow["transitions"][0]["to"] is True


def test_render_flow_section_no_prior_snapshot():
    lines = rotation_flow.render_flow_section(None, title="Rotation Flow")
    report = "\n".join(lines)
    assert "No prior snapshot yet." in report


def test_render_flow_section_lists_transitions():
    flow = {
        "transitions": [{"ticker": "XLK", "label": "Technology", "from": True, "to": False}],
        "summary": {"rising_to_falling": 1, "falling_to_rising": 0, "unchanged_rising": 2, "unchanged_falling": 3},
        "no_prior_count": 0,
    }
    report = "\n".join(rotation_flow.render_flow_section(flow, title="Rotation Flow"))
    assert "### Rotation Flow" in report
    assert "XLK" in report
    assert "Rising" in report
    assert "Falling" in report


def test_render_flow_section_no_transitions_says_so():
    flow = {
        "transitions": [],
        "summary": {"rising_to_falling": 0, "falling_to_rising": 0, "unchanged_rising": 2, "unchanged_falling": 3},
        "no_prior_count": 0,
    }
    report = "\n".join(rotation_flow.render_flow_section(flow, title="Rotation Flow"))
    assert "No transitions since the prior snapshot." in report
