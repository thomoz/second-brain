"""Daily Gold Outlook -- synthesizes gold_technicals.py (live indicators),
macro_indicators.py's 5 gold-relevant checks (live, unmodified except for the
additive `direction` field), and gold_backtest.py (both backtest methodologies,
refreshed roughly daily) into 3 horizon sections. Every section uses the SAME
lookup method (_horizon_read) against real historical data -- today/tomorrow and
this week are not a documented-rationale substitute, they use the same
backtest-grounded approach as this month, just at shorter horizons. Advisor-note
only: no buy/sell directive anywhere here (SOUL.md).
"""

from __future__ import annotations

from datetime import date

from . import config, gold_backtest, gold_technicals

GOLD_SIGNALS = ("real_yields", "dollar_index", "gold_trend", "gold_silver_ratio", "vix")


def _label(beat_baseline: bool) -> str:
    return "bullish" if beat_baseline else "bearish"


def _live_signal_states(technicals: dict, macro_checks: list) -> dict[str, str]:
    """Every currently-active signal/indicator this plan has a backtest for,
    by name -> today's state-value string. Values MUST match gold_backtest.py's
    state classifiers / episode directions character-for-character -- this
    dict is the live half of the join."""
    trend = technicals["trend"]
    macd = technicals["macd"]
    rsi = technicals["rsi"]
    stoch = technicals["stochastic"]
    states = {
        "ma20_trend": "above" if trend["price_above_ma20"] else "below",
        "ma50_trend": "above" if trend["price_above_ma50"] else "below",
        "macd_histogram": "positive" if macd["histogram"] > 0 else "negative",
        "macd_crossover": "above" if macd["macd"] > macd["signal"] else "below",
        "rsi_zone": ("elevated" if rsi > config.GOLD_TA_RSI_BULLISH_ABOVE
                     else "depressed" if rsi < config.GOLD_TA_RSI_BEARISH_BELOW else "neutral"),
        "stochastic_crossover": "above" if stoch["k"] > stoch["d"] else "below",
    }
    for check in macro_checks:
        if check.name in GOLD_SIGNALS and check.data and check.data.get("direction"):
            states[check.name] = check.data["direction"]
    return states


def _synthesize_label(components: dict[str, str]) -> str:
    bullish = sum(1 for v in components.values() if v == "bullish")
    bearish = sum(1 for v in components.values() if v == "bearish")
    total = len(components)
    if total == 0:
        return "insufficient historical data for today's active signals"
    if bullish > bearish and bullish >= total / 2:
        return f"bullish lean ({bullish}/{total})"
    if bearish > bullish and bearish >= total / 2:
        return f"bearish lean ({bearish}/{total})"
    return f"mixed ({bullish} bullish / {bearish} bearish / {total - bullish - bearish} neutral)"


def _horizon_read(states: dict[str, str], backtest_results: dict, horizon_unit: str, horizon_value: int) -> dict:
    """Shared by all three horizons. Looks up EVERY currently-active
    signal/state's real backtest stats at (horizon_unit, horizon_value), scores
    only entries with actual historical data (n > 0), and always carries N so a
    thin sample never masquerades as a strong one."""
    components: dict[str, str] = {}
    notes: list[str] = []
    for name, state_value in states.items():
        if state_value in (None, "neutral", "equal", "flat"):
            continue
        stats = backtest_results.get((name, state_value, horizon_unit, horizon_value))
        if not stats or stats["n"] == 0:
            continue
        beat_baseline = (stats["mean"] or 0) > (stats["baseline"]["mean"] or 0)
        components[name] = _label(beat_baseline)
        notes.append(
            f"{name} ({state_value}): N={stats['n']}, mean {stats['mean']}% vs "
            f"baseline {stats['baseline']['mean']}%, win-rate {stats['win_rate']}%"
        )
    return {"label": _synthesize_label(components), "components": components, "notes": notes}


def build_today_read(technicals: dict, macro_checks: list, backtest_results: dict) -> dict:
    states = _live_signal_states(technicals, macro_checks)
    read = _horizon_read(states, backtest_results, "day", 1)
    atr = technicals["atr"]
    price = technicals["trend"]["price"]
    return {
        "direction_guess": read["label"],
        "confidence": "low -- shortest horizon, smallest per-signal samples" if read["components"] else "unavailable",
        "components": read["components"], "notes": read["notes"],
        "expected_move_dollars": round(atr, 2),
        "expected_move_pct": round(atr / price * 100, 2),
        "resistance": technicals["levels"]["resistance"], "support": technicals["levels"]["support"],
        "volume_note": "above-average volume" if technicals["volume"]["above_average"] else "below-average volume",
    }


def build_week_read(technicals: dict, macro_checks: list, backtest_results: dict) -> dict:
    states = _live_signal_states(technicals, macro_checks)
    read = _horizon_read(states, backtest_results, "day", 5)
    return {
        "direction_guess": read["label"],
        "confidence": "medium -- more historical data than today/tomorrow, less than this month" if read["components"] else "unavailable",
        "components": read["components"], "notes": read["notes"],
    }


def build_month_read(technicals: dict, macro_checks: list, backtest_results: dict) -> dict:
    states = _live_signal_states(technicals, macro_checks)
    read = _horizon_read(states, backtest_results, "month", 1)
    seasonality = technicals["seasonality"]
    components = dict(read["components"])
    notes = list(read["notes"])
    if seasonality["n"] > 0 and seasonality["median"] is not None:
        components["seasonality"] = _label(seasonality["median"] > 0)
        notes.append(f"seasonality: this calendar month has historically averaged "
                     f"{seasonality['mean']}% (median {seasonality['median']}%, N={seasonality['n']} years)")
    return {
        "direction_guess": _synthesize_label(components),
        "confidence": "highest -- most historical data, longest-validated horizon" if components else "unavailable",
        "components": components, "notes": notes, "seasonality": seasonality,
    }


def build_outlook(conn, macro_checks: list) -> dict | None:
    technicals = gold_technicals.compute_today_technicals()
    if technicals is None:
        return None
    try:
        backtest_results = gold_backtest.get_cached_or_refresh(conn)
    except Exception as e:
        print(f"[gold_outlook] backtest unavailable: {e}")
        backtest_results = {}
    return {
        "as_of": date.today().isoformat(),
        "today": build_today_read(technicals, macro_checks, backtest_results),
        "week": build_week_read(technicals, macro_checks, backtest_results),
        "month": build_month_read(technicals, macro_checks, backtest_results),
    }


def render_outlook_markdown(outlook: dict) -> str:
    t, w, m = outlook["today"], outlook["week"], outlook["month"]
    lines = [
        "# Gold Outlook", "",
        "Auto-generated by Monitor -- overwritten every run. Advisor notes only -- "
        "guesses for your own review, never a trade directive (see SOUL.md). Every "
        "horizon's guess is grounded in real historical backtest data (N always "
        "shown), refreshed roughly daily so each new trading day's data is folded "
        "in; confidence is labeled per horizon and scales with how much history "
        "backs it -- lowest for Today/Tomorrow, highest for This Month.",
        "", f"## As of {outlook['as_of']}", "",
        f"### Today / Tomorrow -- {t['direction_guess']} (confidence: {t['confidence']})",
    ]
    for note in t["notes"]:
        lines.append(f"- {note}")
    lines += [
        f"- Expected daily move (ATR-based): ~${t['expected_move_dollars']} ({t['expected_move_pct']}%)",
        f"- Nearest resistance: ${t['resistance']}, nearest support: ${t['support']}",
        f"- Volume: {t['volume_note']}", "",
        f"### This Week -- {w['direction_guess']} (confidence: {w['confidence']})",
    ]
    for note in w["notes"]:
        lines.append(f"- {note}")
    lines += ["", f"### This Month -- {m['direction_guess']} (confidence: {m['confidence']})"]
    for note in m["notes"]:
        lines.append(f"- {note}")
    lines += ["", "Small sample sizes throughout -- read directionally, not as proof. "
                   "Never a buy/sell recommendation."]
    return "\n".join(lines) + "\n"


def write_outlook(outlook: dict) -> None:
    config.MY_TRADER_DIR.joinpath("gold-outlook.md").write_text(
        render_outlook_markdown(outlook), encoding="utf-8"
    )
