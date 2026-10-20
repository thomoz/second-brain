from __future__ import annotations

import json

from goat import config, rotation_watch_build as rwb


def _sector_row(ticker, date, return_pct, return_pct_1w, label="Technology"):
    return {
        "id": 1, "scope": "sector", "snapshot_date": date, "ticker": ticker, "label": label,
        "return_pct": return_pct, "return_pct_1w": return_pct_1w, "rank": 1, "rising": None,
    }


def _industry_row(name, date, return_pct, return_pct_1w, rank):
    return {
        "id": 1, "scope": "industry_full", "snapshot_date": date, "ticker": name, "label": name,
        "return_pct": return_pct, "return_pct_1w": return_pct_1w, "rank": rank, "rising": None,
    }


# --- build_sector_data ----------------------------------------------------------

def test_build_sector_data_builds_dates_and_per_ticker_series():
    rows = [
        _sector_row("XLK", "2026-10-18", 1.0, 2.0, label="Technology"),
        _sector_row("XLK", "2026-10-19", 1.5, 2.5, label="Technology"),
        _sector_row("XLE", "2026-10-18", -1.0, -2.0, label="Energy"),
        _sector_row("XLE", "2026-10-19", -1.5, -2.5, label="Energy"),
    ]
    dates, sectors = rwb.build_sector_data(rows)
    assert dates == ["2026-10-18", "2026-10-19"]
    by_ticker = {s["t"]: s for s in sectors}
    assert by_ticker["XLK"]["n"] == "Technology"
    assert by_ticker["XLK"]["ret"] == [1.0, 1.5]
    assert by_ticker["XLK"]["w1"] == [2.0, 2.5]
    assert by_ticker["XLK"]["rising"] == 1
    assert by_ticker["XLE"]["rising"] == 0


def test_build_sector_data_missing_date_for_a_ticker_is_null():
    rows = [
        _sector_row("XLK", "2026-10-18", 1.0, 2.0),
        _sector_row("XLK", "2026-10-19", 1.5, 2.5),
        _sector_row("XLE", "2026-10-18", -1.0, -2.0),
    ]
    dates, sectors = rwb.build_sector_data(rows)
    xle = next(s for s in sectors if s["t"] == "XLE")
    assert xle["ret"] == [-1.0, None]
    assert xle["w1"] == [-2.0, None]


def test_build_sector_data_rounds_to_two_decimals():
    rows = [_sector_row("XLK", "2026-10-18", 1.23456, 2.34567)]
    _dates, sectors = rwb.build_sector_data(rows)
    assert sectors[0]["ret"] == [1.23]
    assert sectors[0]["w1"] == [2.35]


# --- build_industry_full_data ----------------------------------------------------

def test_build_industry_full_data_membership_fixed_by_latest_perf_week():
    # 25 industries on the latest date, only the latest date's return_pct_1w decides
    # which 20 (top 10 + bottom 10) are selected.
    rows = []
    for i in range(25):
        rows.append(_industry_row(f"Industry{i}", "2026-10-20", float(i - 12), float(i - 12), rank=i + 1))
    full_dates, industries = rwb.build_industry_full_data(rows)
    assert full_dates == ["2026-10-20"]
    assert len(industries) == 20
    names = [row["t"] for row in industries]
    # top 10 highest w1 (i=24..15), bottom 10 lowest w1 (i=0..9), middle (i=10..14) excluded
    assert set(names) == {f"Industry{i}" for i in list(range(15, 25)) + list(range(0, 10))}


def test_build_industry_full_data_top_ordered_descending_bottom_ascending():
    rows = [_industry_row(f"Industry{i}", "2026-10-20", float(i), float(i), rank=i + 1) for i in range(15)]
    _full_dates, industries = rwb.build_industry_full_data(rows, top_n=3, bottom_n=3)
    names = [row["t"] for row in industries]
    # top 3 (highest w1 first): 14, 13, 12 -- bottom 3 (lowest w1 first): 0, 1, 2
    assert names == ["Industry14", "Industry13", "Industry12", "Industry0", "Industry1", "Industry2"]


def test_build_industry_full_data_no_overlap_when_fewer_than_top_plus_bottom():
    rows = [_industry_row(f"Industry{i}", "2026-10-20", float(i), float(i), rank=i + 1) for i in range(5)]
    _full_dates, industries = rwb.build_industry_full_data(rows, top_n=10, bottom_n=10)
    names = [row["t"] for row in industries]
    assert len(names) == len(set(names)) == 5


def test_build_industry_full_data_n_field_uses_latest_date_rank():
    rows = [
        _industry_row("Semiconductors", "2026-10-18", 1.0, 1.0, rank=99),
        _industry_row("Semiconductors", "2026-10-20", 4.0, 4.0, rank=7),
    ]
    _full_dates, industries = rwb.build_industry_full_data(rows)
    assert industries[0]["n"] == "#7 of 144"


def test_build_industry_full_data_series_follows_full_dates_with_nulls():
    rows = [
        _industry_row("Semiconductors", "2026-10-18", 1.0, 1.0, rank=1),
        _industry_row("Semiconductors", "2026-10-20", 4.0, 4.0, rank=1),
    ]
    full_dates, industries = rwb.build_industry_full_data(rows)
    assert full_dates == ["2026-10-18", "2026-10-20"]
    assert industries[0]["ret"] == [1.0, 4.0]


def test_build_industry_full_data_empty_rows_returns_empty():
    assert rwb.build_industry_full_data([]) == ([], [])


# --- build_rotation_watch_html / _replace_span -----------------------------------

_FAKE_TEMPLATE = """<div>unchanged header</div>
<script>
(function () {
  // === SECTOR_DATA:BEGIN (placeholder) ===
  var DATES = ["stale"];

  var SECTORS = [
    { t: "OLD", n: "Old", ret: [1], w1: [1], rising: 1 }
  ];
  // === SECTOR_DATA:END ===

  // explanatory comment that must survive untouched
  // === INDUSTRY_FULL_DATA:BEGIN (placeholder) ===
  var FULL_DATES = ["stale"];

  var INDUSTRY_FULL = [
    { t: "Old Industry", n: "#1 of 144", ret: [1], w1: [1], rising: 1 }
  ];
  // === INDUSTRY_FULL_DATA:END ===

  var CUSTOM_DATES = ["must-not-change"];
})();
</script>
<div>unchanged footer</div>
"""


def test_build_rotation_watch_html_replaces_only_the_two_marked_blocks():
    export_data = {
        "generated_at": "2026-10-20T09:00:00+00:00",
        "scopes": {
            "sector": [_sector_row("XLK", "2026-10-20", 5.0, 6.0, label="Technology")],
            "industry_full": [_industry_row("Semiconductors", "2026-10-20", 7.0, 8.0, rank=3)],
        },
    }
    out = rwb.build_rotation_watch_html(export_data, _FAKE_TEMPLATE)
    assert "unchanged header" in out
    assert "unchanged footer" in out
    assert 'var CUSTOM_DATES = ["must-not-change"];' in out
    assert "explanatory comment that must survive untouched" in out
    assert "OLD" not in out
    assert "Old Industry" not in out
    assert '"t": "XLK"' in out
    assert '"t": "Semiconductors"' in out
    assert '"n": "#3 of 144"' in out


def test_build_rotation_watch_html_output_has_valid_json_rows():
    export_data = {
        "generated_at": "2026-10-20T09:00:00+00:00",
        "scopes": {
            "sector": [_sector_row("XLK", "2026-10-20", 5.0, 6.0)],
            "industry_full": [_industry_row("Semiconductors", "2026-10-20", 7.0, 8.0, rank=3)],
        },
    }
    out = rwb.build_rotation_watch_html(export_data, _FAKE_TEMPLATE)
    row_line = next(line for line in out.splitlines() if '"t": "XLK"' in line)
    json.loads(row_line.strip().rstrip(","))  # must parse as valid JSON (== valid JS object literal)


# --- write_rotation_watch_html ---------------------------------------------------

def test_write_rotation_watch_html_skips_when_export_missing():
    result = rwb.write_rotation_watch_html()
    assert result == {"ok": False, "reason": "rotation-history-export.json not found"}


def test_write_rotation_watch_html_skips_when_scope_empty(tmp_path, monkeypatch):
    export_path = tmp_path / "export.json"
    export_path.write_text(json.dumps({"generated_at": "x", "scopes": {"sector": [], "industry_full": []}}))
    monkeypatch.setattr(config, "GOAT_ROTATION_EXPORT_JSON_PATH", export_path)
    result = rwb.write_rotation_watch_html()
    assert result == {"ok": False, "reason": "export JSON has an empty scope"}


# --- ETF reference parsing/embedding ----------------------------------------------

_FAKE_ETF_REFERENCE_MD = """# Industry -> ETF Quick Reference

Some prose that isn't a table row.

| Industry | Popular ETF(s) | Sector ETF |
|---|---|---|
| Advertising Agencies | — | [XLC](https://finance.yahoo.com/quote/XLC/holdings/) |
| Aerospace & Defense | **[ITA](https://finance.yahoo.com/quote/ITA/holdings/)** (dedicated) | [XLI](https://finance.yahoo.com/quote/XLI/holdings/) |
| Other Precious Metals & Mining | [SIL](https://finance.yahoo.com/quote/SIL/holdings/) / [GDX](https://finance.yahoo.com/quote/GDX/holdings/) (related — precious metals) | [XLB](https://finance.yahoo.com/quote/XLB/holdings/) |

Last built: 2026-10-20.
"""


def test_parse_etf_reference_dash_cell_has_no_popular_etfs():
    mapping = rwb.parse_etf_reference(_FAKE_ETF_REFERENCE_MD)
    assert mapping["Advertising Agencies"]["popular"] == []
    assert mapping["Advertising Agencies"]["sector_etf"] == "XLC"


def test_parse_etf_reference_dedicated_cell():
    mapping = rwb.parse_etf_reference(_FAKE_ETF_REFERENCE_MD)
    popular = mapping["Aerospace & Defense"]["popular"]
    assert popular == [{"ticker": "ITA", "tier": "dedicated", "note": "dedicated"}]
    assert mapping["Aerospace & Defense"]["sector_etf"] == "XLI"


def test_parse_etf_reference_two_related_tickers_share_note():
    mapping = rwb.parse_etf_reference(_FAKE_ETF_REFERENCE_MD)
    popular = mapping["Other Precious Metals & Mining"]["popular"]
    assert [p["ticker"] for p in popular] == ["SIL", "GDX"]
    assert all(p["tier"] == "related" for p in popular)
    assert all(p["note"] == "related — precious metals" for p in popular)


def test_parse_etf_reference_ignores_non_table_lines():
    mapping = rwb.parse_etf_reference(_FAKE_ETF_REFERENCE_MD)
    assert len(mapping) == 3  # not the prose line, not "Last built" line


def test_render_etf_reference_block_is_valid_json_payload():
    mapping = rwb.parse_etf_reference(_FAKE_ETF_REFERENCE_MD)
    block = rwb.render_etf_reference_block(mapping)
    assert "ETF_REFERENCE_DATA:BEGIN" in block
    assert "ETF_REFERENCE_DATA:END" in block
    payload = block.split("var ETF_REFERENCE = ", 1)[1].rsplit(";", 1)[0]
    parsed = json.loads(payload)
    assert parsed["Aerospace & Defense"]["sector_etf"] == "XLI"


def test_apply_etf_reference_block_inserts_before_custom_dates_on_first_run():
    out = rwb.apply_etf_reference_block(_FAKE_TEMPLATE, "  // marker\n  var ETF_REFERENCE = {};\n  // end")
    assert "ETF_REFERENCE" in out
    assert out.index("ETF_REFERENCE") < out.index("CUSTOM_DATES")


def test_apply_etf_reference_block_replaces_existing_block_on_rerun():
    first = rwb.apply_etf_reference_block(_FAKE_TEMPLATE, "  // === ETF_REFERENCE_DATA:BEGIN ===\n  var ETF_REFERENCE = {\"old\": 1};\n  // === ETF_REFERENCE_DATA:END ===")
    second = rwb.apply_etf_reference_block(first, "  // === ETF_REFERENCE_DATA:BEGIN ===\n  var ETF_REFERENCE = {\"new\": 2};\n  // === ETF_REFERENCE_DATA:END ===")
    assert '"old": 1' not in second
    assert '"new": 2' in second
    assert second.count("ETF_REFERENCE_DATA:BEGIN") == 1


def test_write_etf_reference_block_end_to_end(tmp_path, monkeypatch):
    ref_path = tmp_path / "industry-etf-reference.md"
    ref_path.write_text(_FAKE_ETF_REFERENCE_MD, encoding="utf-8")
    template_path = tmp_path / "template.html"
    template_path.write_text(_FAKE_TEMPLATE, encoding="utf-8")
    monkeypatch.setattr(config, "GOAT_INDUSTRY_ETF_REFERENCE_PATH", ref_path)
    monkeypatch.setattr(config, "GOAT_ROTATION_WATCH_TEMPLATE_PATH", template_path)

    result = rwb.write_etf_reference_block()

    assert result == {"ok": True, "industries_mapped": 3}
    updated = template_path.read_text()
    assert "ETF_REFERENCE_DATA:BEGIN" in updated
    assert '"Aerospace & Defense"' in updated


def test_write_rotation_watch_html_writes_output_file(tmp_path, monkeypatch):
    export_data = {
        "generated_at": "2026-10-20T09:00:00+00:00",
        "scopes": {
            "sector": [_sector_row("XLK", "2026-10-20", 5.0, 6.0)],
            "industry_full": [_industry_row("Semiconductors", "2026-10-20", 7.0, 8.0, rank=3)],
        },
    }
    export_path = tmp_path / "export.json"
    export_path.write_text(json.dumps(export_data))
    template_path = tmp_path / "template.html"
    template_path.write_text(_FAKE_TEMPLATE)
    output_path = tmp_path / "out.html"
    monkeypatch.setattr(config, "GOAT_ROTATION_EXPORT_JSON_PATH", export_path)
    monkeypatch.setattr(config, "GOAT_ROTATION_WATCH_TEMPLATE_PATH", template_path)
    monkeypatch.setattr(config, "GOAT_ROTATION_WATCH_OUTPUT_PATH", output_path)

    result = rwb.write_rotation_watch_html()

    assert result["ok"] is True
    assert result["sector_rows"] == 1
    assert result["industry_rows"] == 1
    assert output_path.exists()
    assert '"t": "XLK"' in output_path.read_text()
