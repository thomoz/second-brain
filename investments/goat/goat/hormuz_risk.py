"""Strait of Hormuz war-risk tracking -- Shaun 2026-08-18 wanted a leading
indicator for escalation/de-escalation of the Gulf conflict, as neither
premium-percentage figures nor the Baltic Exchange's TD3C index are freely
available (confirmed via research), this uses two free proxies:

  - check_bwet_shipping_risk(): BWET (Breakwave Tanker Shipping ETF, 90%
    TD3C VLCC futures) price move over a lookback window, via yfinance.
  - check_jwc_listed_areas(): whether the LMA Joint War Committee's Listed
    Areas circular number (see lma_jwc.py) has changed since the last run.

Both deliberately report "info"/"changed" rather than an auto-classified
escalation-vs-de-escalation verdict -- reading direction requires judgment
(a JWLA number change could be an expansion OR a contraction of listed
areas; a BWET spike could reflect Hormuz risk OR unrelated tanker-cycle
supply/demand), so the report surfaces the raw excerpt/numbers for Shaun to
read himself. Same "info, not flag" philosophy as
mytrader/macro_indicators.py's check_gold_trend()."""

from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from typing import Any

from mytrader.checks import CheckResult

from . import config, db, lma_jwc

_MACRO_STATE_JWLA_KEY = "hormuz_jwla_number"
_SOURCE_TABLE = "hormuz_risk"
_PSEUDO_TICKER = "HORMUZ"  # no real ticker applies -- these are portfolio-wide
    # macro checks, not per-holding ones. Reuses monitor.reconcile_alerts'
    # goat_alert_history dedup/auto-acknowledge machinery rather than inventing
    # a second notify-once mechanism alongside the JWLA-number DB compare.


def _yfinance_history_close(ticker: str, lookback_days: int):
    """Mirrors price_history.fetch_close_history's shape but without the
    ASX .AX fallback (BWET is a US-listed ETF, never needs it). Drops NaN
    rows -- confirmed live 2026-08-18 that BWET (thinly traded) can return a
    trailing NaN row for a still-settling session, which would otherwise
    propagate through iloc[-1] as a silent NaN "latest price"."""
    import yfinance as yf

    try:
        start = (date.today() - timedelta(days=lookback_days)).isoformat()
        hist = yf.Ticker(ticker).history(start=start, auto_adjust=True)
        if hist.empty:
            return None
        close = hist["Close"].dropna()
        if close.empty:
            return None
        if getattr(close.index, "tz", None) is not None:
            close.index = close.index.tz_localize(None)
        return close
    except Exception:
        return None


def check_bwet_shipping_risk() -> CheckResult:
    close = _yfinance_history_close(config.GOAT_BWET_TICKER, config.GOAT_BWET_LOOKBACK_DAYS + 5)
    if close is None or close.empty:
        return CheckResult(
            name="bwet_shipping_risk", verdict="unknown",
            detail=f"{config.GOAT_BWET_TICKER} price history unavailable via yfinance",
        )
    latest_price = float(close.iloc[-1])
    window = close[close.index >= close.index[-1] - timedelta(days=config.GOAT_BWET_LOOKBACK_DAYS)]
    start_price = float(window.iloc[0])
    pct_change = round((latest_price - start_price) / start_price * 100, 1) if start_price else 0.0

    detail = (
        f"{config.GOAT_BWET_TICKER} (tanker freight ETF, 90% TD3C VLCC futures) "
        f"${latest_price:.2f}, {pct_change:+.1f}% over the past {config.GOAT_BWET_LOOKBACK_DAYS} days -- "
        f"a proxy for Gulf/Hormuz tanker war-risk cost, but also moves on ordinary tanker-cycle "
        f"supply/demand unrelated to Hormuz, so treat a move here as a prompt to check the news, "
        f"not a standalone signal"
    )
    verdict = "flag" if abs(pct_change) >= config.GOAT_BWET_FLAG_MOVE_PCT else "ok"
    return CheckResult(
        name="bwet_shipping_risk", verdict=verdict, detail=detail,
        data={"price": latest_price, "pct_change": pct_change, "lookback_days": config.GOAT_BWET_LOOKBACK_DAYS},
    )


def check_jwc_listed_areas(conn: sqlite3.Connection) -> CheckResult:
    snapshot = lma_jwc.fetch_listed_areas_snapshot()
    if snapshot is None:
        return CheckResult(
            name="jwc_listed_areas", verdict="unknown",
            detail="LMA Joint War Committee page unavailable or its Listed Areas "
                   "section could not be located (page may have changed structure)",
        )
    current = snapshot["jwla_number"]
    previous = db.get_macro_state(conn, _MACRO_STATE_JWLA_KEY)
    changed = current is not None and current != previous

    if current is None:
        detail = "LMA page fetched but no JWLA circular number found in the Listed Areas section"
        verdict = "unknown"
    elif previous is None:
        detail = f"Current JWC Listed Areas circular: JWLA-{current} (first check, no prior baseline)"
        verdict = "info"
    elif changed:
        detail = (
            f"JWC Listed Areas circular changed: JWLA-{previous} -> JWLA-{current} -- the JWC has "
            f"issued a new Listed Areas notice since the last check; read the excerpt below to see "
            f"whether coverage expanded (escalation) or contracted (de-escalation)"
        )
        verdict = "flag"
    else:
        detail = f"Current JWC Listed Areas circular: JWLA-{current} (unchanged since last check)"
        verdict = "ok"

    if current is not None and current != previous:
        db.set_macro_state(conn, _MACRO_STATE_JWLA_KEY, current)

    return CheckResult(
        name="jwc_listed_areas", verdict=verdict, detail=detail,
        data={
            "jwla_number": current, "previous_jwla_number": previous, "changed": changed,
            "section_excerpt": snapshot["section_text"][:1500],
        },
    )


def run_hormuz_scan(conn: sqlite3.Connection) -> dict[str, Any]:
    from .monitor import reconcile_alerts

    checks = [check_bwet_shipping_risk(), check_jwc_listed_areas(conn)]
    new_alerts = reconcile_alerts(_PSEUDO_TICKER, checks, conn)
    return {"checks": checks, "new_alerts": new_alerts}


def maybe_notify(new_alerts: list[dict[str, Any]]) -> None:
    """Bespoke rather than reusing monitor.maybe_notify -- that function's
    summary template is hardcoded as "{n} holding(s) {label}" (see its
    docstring re: the 2026-08-18 candidate_label fix for the same class of
    issue), which doesn't fit a portfolio-wide macro check with no real
    ticker/holding involved."""
    if not new_alerts:
        return
    import sys
    from pathlib import Path

    _scripts_dir = Path(__file__).resolve().parent.parent.parent.parent / ".claude" / "scripts"
    sys.path.insert(0, str(_scripts_dir))
    from notifications import send_toast_notification, send_whatsapp_notification

    summary = f"{len(new_alerts)} Strait of Hormuz war-risk check(s) flagged"
    send_toast_notification("Goat Hormuz Risk", summary + " -- check investments/goat/hormuz-risk-report.md")

    lines = [f"Goat Hormuz Risk: {summary}."] + [f"- {a['message']}" for a in new_alerts]
    send_whatsapp_notification("\n".join(lines))


def render_hormuz_report(result: dict[str, Any]) -> str:
    lines = [
        "# Strait of Hormuz War-Risk Tracker",
        "",
        "Auto-generated by Goat -- overwritten every run. Advisor notes only; no "
        "trade action is ever suggested here (see SOUL.md). Neither check below "
        "auto-classifies escalation vs de-escalation -- read the detail/excerpt "
        "yourself to judge direction.",
        "",
    ]
    for check in result["checks"]:
        marker = {"flag": "\U0001F6A9 FLAG", "ok": "OK", "info": "INFO", "unknown": "UNKNOWN"}.get(
            check.verdict, check.verdict.upper()
        )
        lines += [f"## {check.name} -- {marker}", check.detail, ""]
        excerpt = check.data.get("section_excerpt")
        if excerpt:
            lines += ["<details><summary>Listed Areas section excerpt</summary>", "", excerpt, "", "</details>", ""]
    lines.append(f"Last auto-generated: {date.today().isoformat()}.")
    return "\n".join(lines) + "\n"


def write_hormuz_report(result: dict[str, Any]) -> None:
    config.GOAT_HORMUZ_REPORT_PATH.write_text(render_hormuz_report(result), encoding="utf-8")
