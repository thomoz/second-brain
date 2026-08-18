from __future__ import annotations

from goat import lma_jwc

_FAKE_PAGE = """
<html><body>
<nav>Home</nav>
<h2>Listed Areas</h2>
<p>In conjunction with independent security advisers, Herminius, the JWC publishes a list.</p>
<p>The committee last reviewed the areas in July 2026. See circular JWLA-034 for details.</p>
<h3>Venezuela</h3>
<p>Uncertain situation.</p>
<h2>Wordings</h2>
<p>The JWC helps to develop and issue wordings.</p>
</body></html>
"""


class _FakeResponse:
    def __init__(self, text: str, status_code: int = 200):
        self.text = text
        self.status_code = status_code


def test_fetch_listed_areas_snapshot_extracts_jwla_number_and_section(monkeypatch):
    monkeypatch.setattr("requests.get", lambda *a, **k: _FakeResponse(_FAKE_PAGE))
    snapshot = lma_jwc.fetch_listed_areas_snapshot()
    assert snapshot is not None
    assert snapshot["jwla_number"] == "034"
    assert "Venezuela" in snapshot["section_text"]
    assert "Wordings" not in snapshot["section_text"]


def test_fetch_listed_areas_snapshot_picks_highest_jwla_number(monkeypatch):
    page = _FAKE_PAGE.replace("JWLA-034", "JWLA-034, superseding JWLA-029")
    monkeypatch.setattr("requests.get", lambda *a, **k: _FakeResponse(page))
    snapshot = lma_jwc.fetch_listed_areas_snapshot()
    assert snapshot["jwla_number"] == "034"


def test_fetch_listed_areas_snapshot_returns_none_without_jwla_number(monkeypatch):
    page = _FAKE_PAGE.replace("See circular JWLA-034 for details.", "No circular referenced.")
    monkeypatch.setattr("requests.get", lambda *a, **k: _FakeResponse(page))
    snapshot = lma_jwc.fetch_listed_areas_snapshot()
    assert snapshot is not None
    assert snapshot["jwla_number"] is None


def test_fetch_listed_areas_snapshot_returns_none_on_non_200(monkeypatch):
    monkeypatch.setattr("requests.get", lambda *a, **k: _FakeResponse(_FAKE_PAGE, status_code=500))
    assert lma_jwc.fetch_listed_areas_snapshot() is None


def test_fetch_listed_areas_snapshot_returns_none_on_request_exception(monkeypatch):
    def _raise(*a, **k):
        raise ConnectionError("boom")
    monkeypatch.setattr("requests.get", _raise)
    assert lma_jwc.fetch_listed_areas_snapshot() is None


def test_fetch_listed_areas_snapshot_returns_none_when_section_headings_missing(monkeypatch):
    page = "<html><body><p>Page redesigned, no Listed Areas heading here.</p></body></html>"
    monkeypatch.setattr("requests.get", lambda *a, **k: _FakeResponse(page))
    assert lma_jwc.fetch_listed_areas_snapshot() is None
