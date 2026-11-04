"""Price Check -- an ad-hoc, user-maintained list of ticker/target-price pairs,
checked every 4 hours (second-brain-mytrader-pricecheck.timer), pinging WhatsApp
the moment a ticker's price crosses its target in either direction. Shaun's own
request 2026-11-04: "I'd like to be able to set up a list of stocks that it
checks in on every 4 hours, and pings me if the price I set gets crossed."

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

First check after price-check-add establishes the baseline side with no
alert (there's nothing to have "crossed" yet) -- same reasoning as
sector_rotation.check_sector_breakout needing a prior MA value before a
cross can be detected at all.
"""

from __future__ import annotations

import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from . import config, db, market_data

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent.parent / ".claude" / "scripts"
SYDNEY_TZ = ZoneInfo("Australia/Sydney")


def _today_sydney() -> str:
    """Own private copy, not a cross-import from monitor.py -- matches this
    codebase's established convention (see earnings_watch.py's identical copy)
    of each scheduled-job module owning its own date-label helper."""
    return datetime.now(SYDNEY_TZ).date().isoformat()


def _side(price: float, target: float) -> str:
    return "above" if price >= target else "below"


def add_price_check(ticker: str, target_price: float, name: str | None, conn: sqlite3.Connection) -> None:
    db.upsert_price_check(conn, ticker=ticker, name=name, target_price=target_price)


def remove_price_check(ticker: str, conn: sqlite3.Connection) -> int:
    return db.delete_price_check(conn, ticker)


def run_price_check(conn: sqlite3.Connection) -> dict[str, Any]:
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
        "What this is: an ad-hoc, user-maintained watch list of ticker/target-price "
        "pairs, checked every 4 hours -- pings WhatsApp the moment a price crosses "
        "its set target in either direction. Set with `price-check-add`, remove "
        "with `price-check-remove`. Advisor notes only; no trade action is ever "
        "suggested here (see SOUL.md).",
        "",
        f"## Run: {_today_sydney()}",
        "",
        "| Ticker | Name | Target | Current Price | Side |",
        "|--------|------|--------|----------------|------|",
    ]
    if not result["checked"]:
        lines.append("| — | No price checks set — add one with `price-check-add` | — | — | — |")
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
