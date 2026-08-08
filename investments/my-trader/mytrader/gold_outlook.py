"""Daily Gold Outlook -- synthesizes gold_technicals.py (live indicators),
macro_indicators.py's 5 gold-relevant checks (live, unmodified except for the
additive `direction` field), and gold_backtest.py (both backtest methodologies,
refreshed roughly daily) into 3 horizon sections. Every section uses the SAME
lookup method (_horizon_read) against real historical data -- today/tomorrow and
this week are not a documented-rationale substitute, they use the same
backtest-grounded approach as this month, just at shorter horizons. Advisor-note
only: no buy/sell directive anywhere here (SOUL.md).

Synthesis is weighted, not a flat headcount (changed 2026-08-07 after a full-year
honest walk-forward validation -- see conversation history in
.agent/plans/gold-tracker-phase2-outlook.md -- showed the original unweighted
majority vote landed at 48.8% on Today/Tomorrow, WORSE than several of its own
individual input signals' backtested win-rates, because 6 of the 8 components are
highly correlated near-zero-edge technical readings that could outvote the 1-2
genuinely stronger signals just by outnumbering them). Each component's vote is
now weighted by its own win-rate's distance from 50% (see _weight()) -- a
63%-win-rate signal counts for more than a 51%-win-rate one, regardless of how
many other signals disagree with it.

MACD/RSI/Stochastic excluded from the directional vote (changed 2026-08-07, same
session). A follow-up walk-forward test showed the moving-average trend states
(ma20_trend/ma50_trend) alone matched the full 8-signal weighted vote exactly
(56.3% both ways) -- MACD/RSI/Stochastic weren't adding measurable value to a
next-day direction call. That's consistent with what these tools are actually
designed for in real technical-analysis practice: RSI and Stochastic are
overbought/oversold *mean-reversion timing* signals, and MACD is a *momentum
confirmation/divergence* tool -- none of them are direction predictors on their
own, so reducing them to a flat bullish/bearish vote was asking them a question
they weren't built to answer, and the vote-dilution this caused was actively
hurting accuracy (see the weighted-synthesis note above). They're still computed
and still shown -- as informational context (see `context_notes` on each horizon
read) -- just no longer counted toward the lean. Moving averages stayed in the
vote because they function as trend filters (a genuinely directional read, not a
timing one), and the 5 macro signals stayed because they're regime/catalyst
signals (real yield levels, a rare 200DMA cross, safe-haven demand via VIX), a
different character from a lagging oscillator.
"""

from __future__ import annotations

from datetime import date

from . import config, gold_backtest, gold_technicals

GOLD_SIGNALS = (
    "real_yields", "dollar_index", "gold_trend", "gold_silver_ratio", "vix", "cot_positioning",
)  # cot_positioning added 2026-08-08 (gold_cot.py) -- large-speculator positioning,
   # merged into macro_checks by build_outlook() below before this dict is consulted.

DIRECTIONAL_VOTE_SIGNALS = frozenset({
    "ma20_trend", "ma50_trend",  # trend filters -- genuine directional persistence
    "real_yields", "dollar_index", "gold_trend", "gold_silver_ratio", "vix",  # macro regime/catalyst signals
    "cot_positioning",  # large-speculator positioning -- a distinct evidence source
                         # (what large speculators are actually doing with capital),
                         # not a price-derived oscillator, so it votes like the
                         # other regime/catalyst signals rather than sitting in
                         # context_notes with MACD/RSI/Stochastic.
})  # Deliberately excludes macd_histogram/macd_crossover/rsi_zone/stochastic_crossover
   # -- see module docstring. "seasonality" (month horizon only) is added directly
   # in build_month_read, not listed here, but participates in the vote the same way.


def _label(win_rate: float) -> str:
    return "bullish" if win_rate > 50.0 else "bearish"


def _weight(win_rate: float) -> float:
    """Edge over a coin flip, in percentage points -- how much this component's
    own historical track record counts toward the synthesized lean. A signal
    sitting exactly at 50% win-rate carries zero weight; a 63% win-rate signal
    counts roughly 6x as much as a 51% one. Deliberately NOT weighted by sample
    size (N): the 6 technical indicators have far larger N than the 5 macro
    signals simply because they're daily-persistent states, not because they
    carry more real edge -- weighting by N would let that larger sample size
    dominate the vote even when the edge itself is weaker, which a real
    walk-forward validation (see .agent/plans/gold-tracker-phase2-outlook.md
    conversation history) showed was actively hurting accuracy under the
    previous unweighted-headcount design."""
    return abs(win_rate - 50.0)


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


def _synthesize_label(components: dict[str, str], weights: dict[str, float]) -> str:
    bullish = [name for name, v in components.items() if v == "bullish"]
    bearish = [name for name, v in components.items() if v == "bearish"]
    total = len(components)
    if total == 0:
        return "insufficient historical data for today's active signals"
    bullish_weight = sum(weights[name] for name in bullish)
    bearish_weight = sum(weights[name] for name in bearish)
    total_weight = bullish_weight + bearish_weight
    if total_weight == 0:
        return f"mixed, no net edge ({len(bullish)} bullish / {len(bearish)} bearish, all near 50% win-rate)"
    if bullish_weight > bearish_weight:
        pct = bullish_weight / total_weight * 100
        return f"bullish lean ({len(bullish)}/{total} signals, {pct:.0f}% of weighted edge)"
    if bearish_weight > bullish_weight:
        pct = bearish_weight / total_weight * 100
        return f"bearish lean ({len(bearish)}/{total} signals, {pct:.0f}% of weighted edge)"
    return f"mixed ({len(bullish)} bullish / {len(bearish)} bearish, evenly weighted)"


def _horizon_read(states: dict[str, str], backtest_results: dict, horizon_unit: str, horizon_value: int) -> dict:
    """Shared by all three horizons. Looks up EVERY currently-active
    signal/state's real backtest stats at (horizon_unit, horizon_value), scores
    only entries with actual historical data (n > 0), and always carries N so a
    thin sample never masquerades as a strong one. Direction and weight both
    come from the state's own historical win-rate (not "does the mean beat an
    unconditioned baseline") -- win-rate directly answers "how often did gold
    go up after this state," which is the practical question each horizon is
    trying to answer, and keeps direction/weight internally consistent (one
    measure, not two that can disagree).

    Only DIRECTIONAL_VOTE_SIGNALS participate in the weighted lean -- everything
    else with real backtest data (currently: MACD/RSI/Stochastic) still gets its
    own note, in context_notes, clearly marked as not counted (see module
    docstring for why)."""
    components: dict[str, str] = {}
    weights: dict[str, float] = {}
    notes: list[str] = []
    context_notes: list[str] = []
    for name, state_value in states.items():
        if state_value in (None, "neutral", "equal", "flat"):
            continue
        stats = backtest_results.get((name, state_value, horizon_unit, horizon_value))
        if not stats or stats["n"] == 0 or stats.get("win_rate") is None:
            continue
        note = (
            f"{name} ({state_value}): N={stats['n']}, mean {stats['mean']}% vs "
            f"baseline {stats['baseline']['mean']}%, win-rate {stats['win_rate']}%"
        )
        if name in DIRECTIONAL_VOTE_SIGNALS:
            components[name] = _label(stats["win_rate"])
            weights[name] = _weight(stats["win_rate"])
            notes.append(note)
        else:
            context_notes.append(f"{note} (context only, not counted in the lean)")
    return {
        "label": _synthesize_label(components, weights),
        "components": components, "weights": weights,
        "notes": notes, "context_notes": context_notes,
    }


def build_today_read(technicals: dict, macro_checks: list, backtest_results: dict) -> dict:
    states = _live_signal_states(technicals, macro_checks)
    read = _horizon_read(states, backtest_results, "day", 1)
    atr = technicals["atr"]
    price = technicals["trend"]["price"]
    return {
        "direction_guess": read["label"],
        "confidence": "low -- shortest horizon, smallest per-signal samples" if read["components"] else "unavailable",
        "components": read["components"], "notes": read["notes"], "context_notes": read["context_notes"],
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
        "components": read["components"], "notes": read["notes"], "context_notes": read["context_notes"],
    }


def build_month_read(technicals: dict, macro_checks: list, backtest_results: dict) -> dict:
    states = _live_signal_states(technicals, macro_checks)
    read = _horizon_read(states, backtest_results, "month", 1)
    seasonality = technicals["seasonality"]
    components = dict(read["components"])
    weights = dict(read["weights"])
    notes = list(read["notes"])
    if seasonality["n"] > 0 and seasonality.get("win_rate") is not None:
        components["seasonality"] = _label(seasonality["win_rate"])
        weights["seasonality"] = _weight(seasonality["win_rate"])
        notes.append(f"seasonality: this calendar month has historically averaged "
                     f"{seasonality['mean']}% (median {seasonality['median']}%, "
                     f"win-rate {seasonality['win_rate']}%, N={seasonality['n']} years)")
    return {
        "direction_guess": _synthesize_label(components, weights),
        "confidence": "highest -- most historical data, longest-validated horizon" if components else "unavailable",
        "components": components, "notes": notes, "context_notes": read["context_notes"],
        "seasonality": seasonality,
    }


def build_outlook(conn, macro_checks: list) -> dict | None:
    technicals = gold_technicals.compute_today_technicals()
    if technicals is None:
        return None
    from . import gold_cot

    try:
        cot_check = gold_cot.check_cot_positioning()
    except Exception as e:
        print(f"[gold_outlook] COT check unavailable: {e}")
        cot_check = None
    all_checks = list(macro_checks) + ([cot_check] if cot_check is not None else [])
    try:
        backtest_results = gold_backtest.get_cached_or_refresh(conn)
    except Exception as e:
        print(f"[gold_outlook] backtest unavailable: {e}")
        backtest_results = {}
    return {
        "as_of": date.today().isoformat(),
        "today": build_today_read(technicals, all_checks, backtest_results),
        "week": build_week_read(technicals, all_checks, backtest_results),
        "month": build_month_read(technicals, all_checks, backtest_results),
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
        f"- Volume: {t['volume_note']}",
    ]
    for note in t["context_notes"]:
        lines.append(f"- {note}")
    lines += ["", f"### This Week -- {w['direction_guess']} (confidence: {w['confidence']})"]
    for note in w["notes"]:
        lines.append(f"- {note}")
    for note in w["context_notes"]:
        lines.append(f"- {note}")
    lines += ["", f"### This Month -- {m['direction_guess']} (confidence: {m['confidence']})"]
    for note in m["notes"]:
        lines.append(f"- {note}")
    for note in m["context_notes"]:
        lines.append(f"- {note}")
    lines += ["", "Small sample sizes throughout -- read directionally, not as proof. "
                   "Never a buy/sell recommendation."]
    return "\n".join(lines) + "\n"


def write_outlook(outlook: dict) -> None:
    config.MY_TRADER_DIR.joinpath("gold-outlook.md").write_text(
        render_outlook_markdown(outlook), encoding="utf-8"
    )
