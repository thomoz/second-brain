"""Chart setup score -- a 0-100 read of how good a stock's chart looks right now
for an insider/investor-buy discovery, shared between goat.insider_scan (the
original consumer) and superinvestor_filings (added the same day). Lives here
rather than in goat because superinvestor_filings already depends on my-trader
but not on goat -- see config.py's "Chart Setup Score" block for the constants.

Origin (Shaun, 2026-09-26): walked through THM's real chart after missing the
trade, then asked "look at the rundown you would give and convert it to a
score." This explicitly overrides opportunity.py's "no invented thresholds"
precedent, at Shaun's own request, on condition every boundary is still
traceable and shown alongside the total -- not a black box. Every threshold
below is either an existing, already-cited constant elsewhere in this
codebase (GOLD_TA_RSI_*) or a plainly-stated, transparent split (the range-
position thirds, the extension tiers), never a fitted/backtested number the
way OPPORTUNITY_* was originally built and rejected for.

Four named components:
- Trend confirmation (0-40): is price above its own 150/200-day MAs with both
  sloping up (Weinstein Stage Analysis' Stage 2, already referenced elsewhere
  in this codebase's ETPMAG exit rule) -- the single biggest factor in the THM
  read (the CEO buy landing right as the reclaim happened).
- Entry quality (0-25): did the buyer buy into a pullback (bottom third of its
  own trailing 90-day range) or chase an already-extended high (top third) --
  the second-biggest factor (THM's CEO bought at a multi-week low, not a high).
- Momentum (0-20): RSI(14) right now, against config.GOLD_TA_RSI_*.
- Extension (0-15): how far price has already run above its nearest long-term
  MA -- the chase-risk / "have I already missed it" read.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

import pandas as pd

from . import config, gold_technicals, tickers


def fetch_close(ticker: str, lookback_days: int = config.CHART_SETUP_LOOKBACK_DAYS) -> pd.Series | None:
    """Long-range daily close history for a single ticker. Same two-candidate
    (bare, then ASX .AX variant) lookup pattern as crash_windows.py/
    technical_levels.py/goat.price_history -- kept as its own copy rather than
    imported from goat.price_history since mytrader must not depend on goat
    (the dependency runs the other way)."""
    import yfinance as yf

    start = (date.today() - timedelta(days=lookback_days)).isoformat()
    for candidate in (tickers.normalize(ticker), tickers.asx_variant(ticker)):
        try:
            hist = yf.Ticker(candidate).history(start=start, auto_adjust=True)
        except Exception:
            continue
        if hist.empty:
            continue
        close = hist["Close"].dropna()
        if close.empty:
            continue
        if getattr(close.index, "tz", None) is not None:
            close.index = close.index.tz_localize(None)
        return close
    return None


def trend_context(close: pd.Series | None) -> str:
    """Where price sits vs its 50/150/200-day MAs right now -- paired onto
    every price-since-trade note so a raw % move never has to be judged alone
    (Shaun 2026-09-26: read THM's insider buy as '+17% since trade' by itself
    and assumed he'd missed the move, when the chart showed price had only
    just reclaimed its 150/200-day MAs -- arguably the start of a confirmed
    move, not the end). Same wording as mytrader.checks.technical_levels for a
    consistent read across reports; not imported directly since that check
    takes a full engine `data` object callers here don't have. Returns "" on
    insufficient history -- callers must render that as "no context", not a
    flag."""
    if close is None or len(close) < min(config.CHART_SETUP_TREND_MA_WINDOWS):
        return ""
    current = float(close.iloc[-1])
    parts = []
    for window in config.CHART_SETUP_TREND_MA_WINDOWS:
        if len(close) < window:
            continue
        ma = float(close.tail(window).mean())
        position = "above" if current >= ma else "below"
        pct_from_ma = (current / ma - 1) * 100
        parts.append(f"{position} {window}DMA ({pct_from_ma:+.1f}%)")
    return "; ".join(parts)


def chart_setup_score(close: pd.Series | None, trade_date_str: str) -> dict[str, Any] | None:
    """See module docstring for the four components. Returns None (not a 0)
    when there isn't enough history to judge the trend or entry-quality legs,
    or RSI hasn't converged yet -- an unscored chart is a different fact than
    a bad one."""
    if close is None or len(close) < 200 + config.CHART_SETUP_SLOPE_LOOKBACK_DAYS:
        return None
    try:
        trade_date_obj = datetime.strptime(trade_date_str, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None

    current = float(close.iloc[-1])
    breakdown: list[str] = []
    total = 0

    # -- Trend confirmation (0-40) --
    ma150_series = close.rolling(150).mean()
    ma200_series = close.rolling(200).mean()
    ma150, ma200 = float(ma150_series.iloc[-1]), float(ma200_series.iloc[-1])
    above150, above200 = current >= ma150, current >= ma200
    slope_lag = config.CHART_SETUP_SLOPE_LOOKBACK_DAYS
    ma150_rising = ma150 > float(ma150_series.iloc[-1 - slope_lag])
    ma200_rising = ma200 > float(ma200_series.iloc[-1 - slope_lag])
    trend_max = config.CHART_SETUP_SCORE_TREND_MAX
    if above150 and above200 and ma150_rising and ma200_rising:
        trend_score, trend_label = trend_max, "confirmed Stage 2 (above + rising 150/200DMA)"
    elif above150 and above200:
        trend_score, trend_label = round(trend_max * 0.7), "fresh reclaim (above 150/200DMA, slope not yet confirmed)"
    elif above150 or above200:
        trend_score, trend_label = round(trend_max * 0.4), "mixed (above one long-term MA, below the other)"
    else:
        trend_score, trend_label = 0, "Stage 4 (below both 150/200DMA)"
    breakdown.append(f"trend {trend_score}/{trend_max} ({trend_label})")
    total += trend_score

    # -- Entry quality (0-25) -- where the trade-day close sat in its own
    # trailing range, bought weakness vs. chased strength.
    window = close[close.index <= pd.Timestamp(trade_date_obj)].tail(
        config.CHART_SETUP_RANGE_LOOKBACK_DAYS
    )
    if len(window) < 20:
        return None
    trade_price = float(window.iloc[-1])
    lo, hi = float(window.min()), float(window.max())
    range_pos = 0.5 if hi == lo else (trade_price - lo) / (hi - lo)
    entry_max = config.CHART_SETUP_SCORE_ENTRY_MAX
    if range_pos <= 1 / 3:
        entry_score, entry_label = entry_max, "bought into weakness (bottom third of its own range)"
    elif range_pos <= 2 / 3:
        entry_score, entry_label = round(entry_max * 0.5), "bought mid-range"
    else:
        entry_score, entry_label = 0, "chased strength (top third of its own range)"
    breakdown.append(f"entry {entry_score}/{entry_max} ({entry_label})")
    total += entry_score

    # -- Momentum (0-20) -- RSI(14) right now, against mytrader's own already-
    # cited RSI thresholds (not new ones invented for this score).
    rsi = float(gold_technicals.rsi_series(close).iloc[-1])
    if rsi != rsi:  # NaN -- Wilder's smoothing hasn't converged yet
        return None
    momentum_max = config.CHART_SETUP_SCORE_MOMENTUM_MAX
    if config.GOLD_TA_RSI_BULLISH_ABOVE <= rsi < config.GOLD_TA_RSI_OVERBOUGHT:
        rsi_score, rsi_label = momentum_max, f"RSI {rsi:.0f} -- healthy, confirming strength"
    elif rsi >= config.GOLD_TA_RSI_OVERBOUGHT:
        rsi_score, rsi_label = round(momentum_max * 0.25), f"RSI {rsi:.0f} -- overbought, chase risk"
    elif rsi <= config.GOLD_TA_RSI_OVERSOLD:
        rsi_score, rsi_label = round(momentum_max * 0.25), f"RSI {rsi:.0f} -- hasn't turned up yet"
    else:
        rsi_score, rsi_label = round(momentum_max * 0.6), f"RSI {rsi:.0f} -- turning, not yet confirmed"
    breakdown.append(f"momentum {rsi_score}/{momentum_max} ({rsi_label})")
    total += rsi_score

    # -- Extension (0-15) -- chase risk: how far above its own trend already.
    ext_max = config.CHART_SETUP_SCORE_EXTENSION_MAX
    nearer_ma = min(ma150, ma200) if (above150 or above200) else None
    if nearer_ma is not None:
        pct_above = (current / nearer_ma - 1) * 100
        ext_score = 0
        for max_pct, pts in config.CHART_SETUP_EXTENSION_TIERS:
            if pct_above <= max_pct:
                ext_score = pts
                break
        ext_label = f"{pct_above:+.1f}% above its nearest long-term MA"
    else:
        ext_score, ext_label = round(ext_max * 0.5), "hasn't broken above a long-term MA yet, n/a"
    breakdown.append(f"extension {ext_score}/{ext_max} ({ext_label})")
    total += ext_score

    return {"score": total, "breakdown": "; ".join(breakdown)}


def build_chart_note(ticker: str, trade_date_str: str) -> str:
    """The single bracketed note callers append to a price-since-trade line --
    combines the raw trend-vs-MA read with the 0-100 chart setup score off one
    shared close-history fetch. Returns "" when neither half has anything to
    say (no history, or an unparsable/missing trade date)."""
    close = fetch_close(ticker)
    parts = []
    trend = trend_context(close)
    if trend:
        parts.append(trend)
    setup = chart_setup_score(close, trade_date_str)
    if setup:
        parts.append(f"chart setup score {setup['score']}/100 ({setup['breakdown']})")
    return " | ".join(parts)
