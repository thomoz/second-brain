from __future__ import annotations

from goat import config, finviz_groups

_HEADER_ROW = (
    "<tr><th>No.</th><th>Name</th><th>Perf Week</th><th>Perf Month</th>"
    "<th>Perf Quart</th><th>Perf Half</th><th>Perf Year</th><th>Perf YTD</th>"
    "<th>Avg Volume</th><th>Rel Volume</th><th>Change %</th><th>Volume</th></tr>"
)

# Live-shaped fixture rows, 2026-10-18 verification sample (see
# .agent/plans/goat-industry-ranking-full-coverage.md Decision #1).
_LIVE_SAMPLE_ROWS = [
    ("1", "Advertising Agencies", "-1.24%", "-11.71%", "-27.69%", "-32.96%", "-47.16%", "-50.25%", "50.47M", "0.76", "-3.50%", "38.22M"),
    ("144", "Waste Management", "7.09%", "5.30%", "-0.42%", "4.43%", "2.99%", "3.19%", "24.01M", "1.24", "1.02%", "29.82M"),
]


def _row_html(fields: tuple[str, ...]) -> str:
    return "<tr>" + "".join(f"<td>{f}</td>" for f in fields) + "</tr>"


def _page_html(rows: list[tuple[str, ...]]) -> str:
    body = "".join(_row_html(r) for r in rows)
    return f"<table>{_HEADER_ROW}{body}</table>"


class _FakeResponse:
    def __init__(self, text: str, status_code: int = 200):
        self.text = text
        self.status_code = status_code


# --- _parse_pct ----------------------------------------------------------------

def test_parse_pct_handles_percent_strings_and_dash_placeholder():
    assert finviz_groups._parse_pct("-1.24%") == -1.24
    assert finviz_groups._parse_pct("7.09%") == 7.09
    assert finviz_groups._parse_pct("-") is None
    assert finviz_groups._parse_pct("") is None
    assert finviz_groups._parse_pct("not-a-number%") is None


# --- fetch_industry_groups -------------------------------------------------------

def test_fetch_industry_groups_parses_all_rows(monkeypatch):
    html = _page_html(_LIVE_SAMPLE_ROWS)
    monkeypatch.setattr("requests.get", lambda *a, **k: _FakeResponse(html))
    rows = finviz_groups.fetch_industry_groups()
    assert rows is not None
    assert len(rows) == 2
    by_name = {r["name"]: r for r in rows}
    ad = by_name["Advertising Agencies"]
    assert ad["perf_half"] == -32.96
    assert ad["change_pct"] == -3.50
    assert ad["rel_volume"] == 0.76
    assert ad["avg_volume"] == "50.47M"
    wm = by_name["Waste Management"]
    assert wm["perf_half"] == 4.43
    assert wm["perf_year"] == 2.99


def test_fetch_industry_groups_returns_none_on_bad_status(monkeypatch):
    monkeypatch.setattr("requests.get", lambda *a, **k: _FakeResponse("x", status_code=503))
    assert finviz_groups.fetch_industry_groups() is None


def test_fetch_industry_groups_returns_none_on_network_error(monkeypatch):
    def _raise(*a, **k):
        raise Exception("boom")

    monkeypatch.setattr("requests.get", _raise)
    assert finviz_groups.fetch_industry_groups() is None


def test_fetch_industry_groups_returns_none_when_table_not_found(monkeypatch):
    html = "<html><body><table><tr><th>Unrelated</th></tr></table></body></html>"
    monkeypatch.setattr("requests.get", lambda *a, **k: _FakeResponse(html))
    assert finviz_groups.fetch_industry_groups() is None


def test_canonical_industry_list_matches_scraped_names(monkeypatch):
    rows = [
        (str(i), name, "1.00%", "1.00%", "1.00%", "1.00%", "1.00%", "1.00%", "1.00M", "1.00", "1.00%", "1.00M")
        for i, name in enumerate(config.GOAT_FINVIZ_INDUSTRIES, start=1)
    ]
    html = _page_html(rows)
    monkeypatch.setattr("requests.get", lambda *a, **k: _FakeResponse(html))
    result = finviz_groups.fetch_industry_groups()
    assert result is not None
    assert {r["name"] for r in result} == set(config.GOAT_FINVIZ_INDUSTRIES)
