"""Marker 11 -- regulators sound the alarm. Daily poll of 3 RSS feeds (SEC press
releases, Fed press releases, Fed speeches), all confirmed live 2026-08-18: valid RSS
2.0, parseable with stdlib xml.etree.ElementTree (no new dependency), current items,
<guid> present and stable on every item across all 3 feeds -- used as the dedup key so
the same item isn't re-flagged every day it stays in the feed (mirrors
signals_bond_cusip_cache's own dedup-by-key shape from Marker #12).

v1 scope, an honest scope-down from what a human reading the full documents would
catch: this keyword-scans only the RSS item's title+description, not the linked full
document. RSS titles/descriptions are often generic ("Federal Reserve Board announces
approval of the application by [Bank]") -- many of the substantive systemic-risk
statements this marker actually wants (BIS-style commentary, Financial Stability Report
language) live in the body of a linked report, not the feed's own text. Fetching and
scanning full linked-report text is a real, meaningfully bigger scope item, deliberately
NOT part of this phase's baseline (see this plan's NOTES)."""

from __future__ import annotations

import sqlite3
import xml.etree.ElementTree as ET

import requests
from mytrader.checks import CheckResult

from . import config, db

_HEADERS = {"User-Agent": "Shaun Thomson thomoz@outlook.com"}


def _fetch_feed_items(url: str) -> list[dict[str, str]]:
    try:
        r = requests.get(url, headers=_HEADERS, timeout=20)
        if r.status_code != 200:
            return []
        root = ET.fromstring(r.content)
    except Exception:
        return []
    items = []
    for item in root.findall(".//item"):
        guid_el = item.find("guid")
        title_el = item.find("title")
        desc_el = item.find("description")
        link_el = item.find("link")
        guid = (guid_el.text or "").strip() if guid_el is not None else None
        if not guid:
            continue  # no stable dedup key -- skip rather than risk re-flagging forever
        items.append({
            "guid": guid,
            "title": (title_el.text or "").strip() if title_el is not None else "",
            "description": (desc_el.text or "").strip() if desc_el is not None else "",
            "link": (link_el.text or "").strip() if link_el is not None else "",
            "source": url,
        })
    return items


def _matches_trigger_phrase(item: dict[str, str]) -> bool:
    haystack = f"{item['title']} {item['description']}".lower()
    return any(phrase in haystack for phrase in config.SIGNALS_REGULATOR_TRIGGER_PHRASES)


def check_regulator_alarm(conn: sqlite3.Connection) -> list[CheckResult]:
    results = []
    for feed_url in config.SIGNALS_REGULATOR_FEED_URLS:
        for item in _fetch_feed_items(feed_url):
            if db.has_seen_regulator_alert(conn, item["guid"]):
                continue
            db.mark_regulator_alert_seen(
                conn, guid=item["guid"], source=feed_url, title=item["title"]
            )
            if not _matches_trigger_phrase(item):
                continue  # seen and recorded, but not a keyword match -- not a CheckResult
            results.append(CheckResult(
                name="regulator_alarm", verdict="flag",
                detail=f"{item['title']} ({item['link']})",
                data={"guid": item["guid"], "source": feed_url, "title": item["title"]},
            ))
    return results
