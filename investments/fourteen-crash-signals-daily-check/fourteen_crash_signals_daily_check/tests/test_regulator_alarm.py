from __future__ import annotations

from fourteen_crash_signals_daily_check import config, db, regulator_alarm

_FIXTURE_RSS = """<?xml version="1.0"?><rss version="2.0"><channel>
<item><title>Fed Board issues statement</title><link>https://example.com/x</link>
<guid>https://example.com/x</guid><description>systemic risk language here</description>
</item></channel></rss>"""


def _fake_items_by_url(mapping: dict[str, list[dict[str, str]]]):
    def _fake(url):
        return mapping.get(url, [])

    return _fake


def test_new_matching_item_flags_and_marks_seen(db_conn, monkeypatch):
    url = config.SIGNALS_REGULATOR_FEED_URLS[0]
    item = {"guid": "g1", "title": "Systemic risk warning", "description": "leverage concerns", "link": "https://x", "source": url}
    monkeypatch.setattr(regulator_alarm, "_fetch_feed_items", _fake_items_by_url({url: [item]}))
    results = regulator_alarm.check_regulator_alarm(db_conn)
    assert len(results) == 1
    assert results[0].verdict == "flag"
    assert db.has_seen_regulator_alert(db_conn, "g1") is True


def test_non_matching_item_marked_seen_but_no_result_and_no_reprocessing(db_conn, monkeypatch):
    url = config.SIGNALS_REGULATOR_FEED_URLS[0]
    item = {"guid": "g2", "title": "Routine bank merger approval", "description": "nothing notable", "link": "https://x", "source": url}
    monkeypatch.setattr(regulator_alarm, "_fetch_feed_items", _fake_items_by_url({url: [item]}))
    results = regulator_alarm.check_regulator_alarm(db_conn)
    assert results == []
    assert db.has_seen_regulator_alert(db_conn, "g2") is True

    # calling again with the same item still returned by _fetch_feed_items -- no new/dup result
    results_again = regulator_alarm.check_regulator_alarm(db_conn)
    assert results_again == []


def test_already_seen_item_produces_no_result_even_if_matching(db_conn, monkeypatch):
    url = config.SIGNALS_REGULATOR_FEED_URLS[0]
    db.mark_regulator_alert_seen(db_conn, guid="g3", source=url, title="Systemic risk warning")
    item = {"guid": "g3", "title": "Systemic risk warning", "description": "leverage concerns", "link": "https://x", "source": url}
    monkeypatch.setattr(regulator_alarm, "_fetch_feed_items", _fake_items_by_url({url: [item]}))
    results = regulator_alarm.check_regulator_alarm(db_conn)
    assert results == []


def test_items_across_all_configured_feeds_are_processed(db_conn, monkeypatch):
    urls = config.SIGNALS_REGULATOR_FEED_URLS
    mapping = {
        urls[0]: [{"guid": "a1", "title": "systemic risk update", "description": "", "link": "https://x", "source": urls[0]}],
        urls[1]: [{"guid": "a2", "title": "leverage rising", "description": "", "link": "https://x", "source": urls[1]}],
        urls[2]: [{"guid": "a3", "title": "financial stability speech", "description": "", "link": "https://x", "source": urls[2]}],
    }
    monkeypatch.setattr(regulator_alarm, "_fetch_feed_items", _fake_items_by_url(mapping))
    results = regulator_alarm.check_regulator_alarm(db_conn)
    assert {r.data["guid"] for r in results} == {"a1", "a2", "a3"}


def test_all_feeds_returning_empty_list_returns_empty(db_conn, monkeypatch):
    monkeypatch.setattr(regulator_alarm, "_fetch_feed_items", lambda url: [])
    assert regulator_alarm.check_regulator_alarm(db_conn) == []


def test_fetch_feed_items_parses_real_rss_fixture(monkeypatch):
    class _FakeResponse:
        status_code = 200
        content = _FIXTURE_RSS.encode("utf-8")

    monkeypatch.setattr(regulator_alarm.requests, "get", lambda url, headers=None, timeout=None: _FakeResponse())
    items = regulator_alarm._fetch_feed_items("https://example.com/feed.rss")
    assert len(items) == 1
    assert items[0]["guid"] == "https://example.com/x"
    assert items[0]["title"] == "Fed Board issues statement"
    assert "systemic risk" in items[0]["description"]
