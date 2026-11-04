"""Price Check -- a hand-edited markdown list (price-check-list.md) of
ticker/target-price pairs, checked every 4 hours (second-brain-mytrader-
pricecheck.timer), pinging WhatsApp the moment a ticker's price crosses its
target in either direction. Shaun's own request 2026-11-04: "I just want to
have an md file that I have you add stocks to and prices over which if the
stock price crosses I get a whatsapp ping" -- a deliberate simplification of
this feature's first cut (CLI price-check-add/-remove commands driving a DB
list directly), same session.

price-check-list.md is the single source of truth (same pattern as
industry-etf-reference.md -> goat's ETF_REFERENCE) -- a plain table Shaun or
Claude edits directly, never auto-regenerated. The price_checks DB table is
purely derived sync state (each row's crossing-detection baseline); it is
never hand-edited and gets rewritten from the list on every run by
sync_price_checks_from_list, never read as its own source of truth.

Deliberately separate from watchlist/holdings -- this is a lightweight,
single-purpose list (ticker, target_price), not tied to bucket/status
semantics or the 13-check assessment engine. Direction-agnostic by design:
"crossed" means the price moved from one side of the target to the other
since the last check, regardless of whether that's up through a buy-target
or down through a stop level -- Shaun didn't specify a direction, and a
single ticker could reasonably be used either way.

Crossing detection (not alert_history's flag/ok/flag reconcile): each row
remembers which side of target_price the price was on at its last check
(price_checks.last_side). A crossing fires only when the side flips --
mirrors goat/sector_rotation.py's own sign-based MA-cross detection, the
established precedent in this codebase for "did a value cross a line"
rather than "is a value past a line" (which alert_history's flag/ok model is
built for). This also means a crossing fires again every time the price
re-crosses back and forth, which is the correct behavior for a watch level
Shaun is actively tracking -- not a one-time alert like a stale breakout
candidate.

The first check after a ticker is added to the list (or its target_price
changes) establishes the baseline side with no alert -- there's nothing to
have "crossed" yet, same reasoning as sector_rotation.check_sector_breakout
needing a prior MA value before a cross can be detected at all. A
name-only edit (target_price unchanged) does NOT reset the baseline.
"""

from __future__ import annotations

import re
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from . import config, db, market_data, tickers

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent.parent / ".claude" / "scripts"
SYDNEY_TZ = ZoneInfo("Australia/Sydney")

_ROW_RE = re.compile(r"^\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.*?)\s*\|\s*$")


def _today_sydney() -> str:
    """Own private copy, not a cross-import from monitor.py -- matches this
    codebase's established convention (see earnings_watch.py's identical copy)
    of each scheduled-job module owning its own date-label helper."""
    return datetime.now(SYDNEY_TZ).date().isoformat()


def _side(price: float, target: float) -> str:
    return "above" if price >= target else "below"


def parse_price_check_list(markdown_text: str) -> list[dict[str, Any]]:
    """Parses price-check-list.md's one table into
    [{"ticker", "target_price", "name"}, ...]. Skips the header row, the
    markdown separator row, and any non-table prose -- same parsing idiom as
    goat.rotation_watch_build.parse_etf_reference. A row whose price cell
    isn't a parseable number is skipped (not crashed on) -- a typo in one
    row shouldn't take the whole list down."""
    rows: list[dict[str, Any]] = []
    for line in markdown_text.splitlines():
        if not line.startswith("|"):
            continue
        stripped = line.replace("|", "").strip()
        if not stripped or set(stripped.replace(" ", "")) <= {"-"}:
            continue  # separator row
        if stripped.lower().startswith("ticker"):
            continue  # header row
        m = _ROW_RE.match(line)
        if not m:
            continue
        ticker_raw, price_raw, name_raw = m.groups()
        try:
            target_price = float(price_raw.replace(",", "").replace("$", ""))
        except ValueError:
            continue
        rows.append({
            "ticker": tickers.normalize(ticker_raw),
            "target_price": target_price,
            "name": name_raw or None,
        })
    return rows


def sync_price_checks_from_list(conn: sqlite3.Connection, parsed_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Makes the price_checks DB table match price-check-list.md exactly.
    New or target_price-changed rows upsert (re-baselining -- see
    db.upsert_price_check's docstring for why a target_price change must
    reset last_side); a name-only edit updates in place WITHOUT resetting the
    baseline (db.update_price_check_name); rows no longer in the list are
    deleted outright -- removing a line from the list is how Shaun stops
    tracking a ticker, there is no separate "remove" step."""
    wanted = {r["ticker"]: r for r in parsed_rows}
    existing = {r["ticker"]: r for r in db.get_all_price_checks(conn)}

    added, updated, removed = [], [], []
    for ticker, row in wanted.items():
        prior = existing.get(ticker)
        if prior is None:
            db.upsert_price_check(conn, ticker=ticker, name=row["name"], target_price=row["target_price"])
            added.append(ticker)
        elif prior["target_price"] != row["target_price"]:
            db.upsert_price_check(conn, ticker=ticker, name=row["name"], target_price=row["target_price"])
            updated.append(ticker)
        elif (prior["name"] or None) != row["name"]:
            db.update_price_check_name(conn, ticker, row["name"])

    for ticker in existing:
        if ticker not in wanted:
            db.delete_price_check(conn, ticker)
            removed.append(ticker)

    return {"added": added, "updated": updated, "removed": removed}


def run_price_check(conn: sqlite3.Connection) -> dict[str, Any]:
    list_text = (
        config.PRICE_CHECK_LIST_PATH.read_text(encoding="utf-8")
        if config.PRICE_CHECK_LIST_PATH.exists() else ""
    )
    parsed = parse_price_check_list(list_text)
    sync_price_checks_from_list(conn, parsed)

    rows = db.get_all_price_checks(conn)
    crossed: list[dict[str, Any]] = []
    checked: list[dict[str, Any]] = []

    with market_data.cached_session():
        for row in rows:
            ticker = row["ticker"]
            price = market_data.fetch_current_price(ticker)
            if price is None:
                checked.append({
                    "ticker": ticker, "name": row["name"], "target_price": row["target_price"],
                    "price": None, "side": row["last_side"], "crossed": False,
                })
                continue

            side = _side(price, row["target_price"])
            just_crossed = row["last_side"] is not None and side != row["last_side"]
            db.update_price_check_side(conn, ticker, side=side, price=price)

            entry = {
                "ticker": ticker, "name": row["name"], "target_price": row["target_price"],
                "price": price, "side": side, "crossed": just_crossed,
            }
            checked.append(entry)
            if just_crossed:
                crossed.append({**entry, "from_side": row["last_side"]})

    return {"checked": checked, "crossed": crossed}


def render_price_check_report(result: dict[str, Any]) -> str:
    lines = [
        "# Price Check",
        "",
        "What this is: tracks `price-check-list.md` (edit that file directly, or "
        "ask Shaun's Second Brain to add/remove a row) -- pings WhatsApp the "
        "moment a ticker's price crosses its target in either direction, every "
        "time it crosses. Advisor notes only; no trade action is ever suggested "
        "here (see SOUL.md).",
        "",
        f"## Run: {_today_sydney()}",
        "",
        "| Ticker | Name | Target | Current Price | Side |",
        "|--------|------|--------|----------------|------|",
    ]
    if not result["checked"]:
        lines.append("| — | price-check-list.md is empty — add a row to start tracking | — | — | — |")
    for c in result["checked"]:
        price_str = f"{c['price']:,.2f}" if c["price"] is not None else "unavailable"
        side_str = c["side"] or "—"
        name_str = c["name"] or ""
        lines.append(f"| {c['ticker']} | {name_str} | {c['target_price']:,.2f} | {price_str} | {side_str} |")

    lines += ["", "### Crossed This Run"]
    if result["crossed"]:
        for c in result["crossed"]:
            lines.append(
                f"- **{c['ticker']}**" + (f" ({c['name']})" if c.get("name") else "")
                + f" -- crossed {c['from_side']} -> {c['side']} its target of {c['target_price']:,.2f}, "
                  f"now {c['price']:,.2f}"
            )
    else:
        lines.append("No crossings this run.")

    lines += ["", f"Last auto-generated: {_today_sydney()}."]
    return "\n".join(lines) + "\n"


def write_report(result: dict[str, Any]) -> None:
    config.PRICE_CHECK_REPORT_PATH.write_text(render_price_check_report(result), encoding="utf-8")


def maybe_notify(result: dict[str, Any]) -> None:
    if not result["crossed"]:
        return
    sys.path.insert(0, str(_SCRIPTS_DIR))
    from notifications import send_toast_notification, send_whatsapp_notification

    n = len(result["crossed"])
    summary = f"{n} price check(s) crossed -- check investments/my-trader/price-check-report.md"
    send_toast_notification("Price Check", summary)

    lines = [f"Price Check: {n} crossed."] + [
        f"- {c['ticker']}" + (f" ({c['name']})" if c.get("name") else "")
        + f": crossed {c['from_side']} -> {c['side']} {c['target_price']:,.2f}, now {c['price']:,.2f}"
        for c in result["crossed"]
    ]
    send_whatsapp_notification("\n".join(lines))
