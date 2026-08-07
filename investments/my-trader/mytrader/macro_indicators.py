"""Macro monitoring indicators — portfolio-wide (not per-ticker) leading indicators
for Monitor. Distinct from checks/*.py's 7 per-ticker checks: these run once per
Monitor invocation, never from Find, and are reconciled against alert_history using
a "MACRO"/"macro" sentinel ticker/source_table (see monitor.py) rather than a real
ticker. Covers the 5 indicators confirmed in tool-preplan.md's "Monitoring Indicators"
section (2026-07-19): MOVE index, housing price-to-income ratio, University of
Michigan Consumer Sentiment Index, NY Fed recession-probability model, and the
bull/bear-steepener distinction — the last is folded into check_recession_signal()'s
detail text rather than being a 5th standalone check, per that section's own note
that it's "a refinement to fold into the existing bullet," not an independently
tested signal.

check_inflation_expectations(), check_credit_spreads(), check_australia_cpi(),
check_us_cpi(), and check_uk_cpi() (added 2026-07-30) are later additions beyond
tool-preplan.md's original 5-indicator list -- inflation_expectations is a
market-implied/forward-looking complement to recession_signal's backward-looking
yield-curve/recession-probability read and consumer_sentiment's survey-based read;
credit_spreads is investment-strategy.md's "credit stress" job, previously flagged
but never implemented; australia_cpi/uk_cpi read directly from the ABS/ONS
(mytrader/abs_cpi.py, mytrader/ons_cpi.py) since FRED's own AU CPI series turned
out to be 18+ months stale (UK was never tracked via FRED at all); us_cpi is the
realized/backward-looking counterpart to inflation_expectations' forward-looking
breakeven read, via FRED's own CPIAUCSL with a units="pc1" transform. Japan CPI
deliberately parked (2026-07-30) -- e-Stat requires its own registered appId,
same as FRED's key, not yet obtained. recession_signal also gained a folded-in
10Y-3M curve refinement (the Fed's own preferred inversion metric) at the same
time, same treatment as the existing bull/bear steepener refinement.

FRED_YIELD_CURVE_SERIES/FRED_RECESSION_PROB_SERIES in config.py intentionally
duplicate string values already present in briefs-finance's own
scripts/config.py:FRED_SERIES — that dict is shaped for fetch_fred_macro()'s bulk
multi-series report-ingestion-time snapshot, while this module needs individual
point-in-time reads at two different dates (today + a lookback date, for the
steepener comparison), a different access pattern. Duplicating two short strings was
judged simpler than reshaping shared code across two independently-versioned projects.

check_real_yields(), check_dollar_index(), check_gold_trend(), check_gold_silver_ratio(),
and check_vix() (added 2026-08-07, taking this module from 9 to 14 checks) are Phase 1
of the gold-tracking feature (see .agent/plans/gold-tracker-handoff.md) -- Shaun holds
gold via PMGOLD and wanted daily visibility into the macro drivers that actually move
it (real yields, USD strength) plus the gold price itself and a general risk-sentiment
gauge, none of which the existing 9 checks (portfolio-wide but gold-agnostic) surface.
check_gold_trend() is deliberately always "info", never "flag" -- a 200DMA cross is a
contested signal (gold specifically has a documented small-sample history of behaving
as a contrarian buy signal rather than the standard trend-following "bearish" read), so
it's reported as neutral fact, same philosophy as checks/price_action.py.
"""

from __future__ import annotations

from datetime import date, timedelta

from scripts.macro import fred_observation_on, fred_value_on

from . import abs_cpi, config, market_data, ons_cpi
from .checks import CheckResult


def _yfinance_latest_close(ticker: str) -> float | None:
    import yfinance as yf

    try:
        hist = yf.Ticker(ticker).history(period="5d")
        if hist.empty:
            return None
        return float(hist["Close"].iloc[-1])
    except Exception:
        return None


def check_move_index() -> CheckResult:
    value = _yfinance_latest_close(config.MOVE_INDEX_TICKER)
    if value is None:
        return CheckResult(
            name="move_index", verdict="unknown",
            detail=f"{config.MOVE_INDEX_TICKER} data unavailable via yfinance",
        )
    if value >= config.MOVE_INDEX_FLAG_LEVEL:
        return CheckResult(
            name="move_index", verdict="flag",
            detail=f"MOVE index at {value:.1f}, at/above the "
                   f"{config.MOVE_INDEX_FLAG_LEVEL:.0f} bond-market-stress threshold",
            data={"value": value},
        )
    return CheckResult(
        name="move_index", verdict="ok",
        detail=f"MOVE index at {value:.1f}, below the flag threshold",
        data={"value": value},
    )


def check_housing_affordability() -> CheckResult:
    today = date.today()
    price_obs = fred_observation_on(config.FRED_MEDIAN_HOME_PRICE_SERIES, today)
    income_obs = fred_observation_on(config.FRED_MEDIAN_HOUSEHOLD_INCOME_SERIES, today)
    if not price_obs or not income_obs:
        return CheckResult(
            name="housing_affordability", verdict="unknown",
            detail="FRED median home price / household income data unavailable "
                   "(FRED_API_KEY not set, or series unavailable)",
        )
    price, price_date = price_obs
    income, income_date = income_obs
    ratio = round(price / income, 2)
    # income (annual, ~19mo publication lag) is almost always the stale side --
    # surface both dates since they're rarely the same and the ratio is meaningless
    # without knowing how current each side actually is.
    as_of = f"price as of {price_date.isoformat()}, income as of {income_date.isoformat()}"
    data = {
        "ratio": ratio,
        "price_date": price_date.isoformat(),
        "income_date": income_date.isoformat(),
    }
    if ratio >= config.HOUSING_P2I_FLAG_RATIO:
        return CheckResult(
            name="housing_affordability", verdict="flag",
            detail=f"Housing price-to-income ratio at {ratio}x ({as_of}), at/above the "
                   f"{config.HOUSING_P2I_FLAG_RATIO}x stress threshold",
            data=data,
        )
    return CheckResult(
        name="housing_affordability", verdict="ok",
        detail=f"Housing price-to-income ratio at {ratio}x ({as_of})",
        data=data,
    )


def check_consumer_sentiment() -> CheckResult:
    obs = fred_observation_on(config.FRED_CONSUMER_SENTIMENT_SERIES, date.today())
    if obs is None:
        return CheckResult(
            name="consumer_sentiment", verdict="unknown",
            detail="FRED UMich consumer sentiment data unavailable "
                   "(FRED_API_KEY not set, or series unavailable)",
        )
    value, obs_date = obs
    as_of = f"as of {obs_date.isoformat()}"
    if value <= config.CONSUMER_SENTIMENT_FLAG_LEVEL:
        return CheckResult(
            name="consumer_sentiment", verdict="flag",
            detail=f"UMich consumer sentiment at {value:.1f} ({as_of}), at/below the "
                   f"{config.CONSUMER_SENTIMENT_FLAG_LEVEL:.0f} stress threshold",
            data={"value": value, "as_of": obs_date.isoformat()},
        )
    return CheckResult(
        name="consumer_sentiment", verdict="ok",
        detail=f"UMich consumer sentiment at {value:.1f} ({as_of})",
        data={"value": value, "as_of": obs_date.isoformat()},
    )


def check_recession_signal() -> CheckResult:
    today = date.today()
    prior = today - timedelta(days=config.STEEPENER_LOOKBACK_DAYS)

    curve_obs = fred_observation_on(config.FRED_YIELD_CURVE_SERIES, today)
    prob_obs = fred_observation_on(config.FRED_RECESSION_PROB_SERIES, today)
    if curve_obs is None or prob_obs is None:
        return CheckResult(
            name="recession_signal", verdict="unknown",
            detail="FRED yield-curve / recession-probability data unavailable "
                   "(FRED_API_KEY not set, or series unavailable)",
        )
    curve_now, curve_date = curve_obs
    recession_prob, prob_date = prob_obs

    short_now = fred_value_on(config.FRED_2Y_TREASURY_SERIES, today)
    short_prior = fred_value_on(config.FRED_2Y_TREASURY_SERIES, prior)
    long_now = fred_value_on(config.FRED_10Y_TREASURY_SERIES, today)
    long_prior = fred_value_on(config.FRED_10Y_TREASURY_SERIES, prior)

    steepener = None
    if None not in (short_now, short_prior, long_now, long_prior):
        short_falling = short_now < short_prior
        long_rising = long_now > long_prior
        if short_falling and not long_rising:
            steepener = "bull steepener (short rates falling — benign, Fed-cut-driven)"
        elif long_rising and not short_falling:
            steepener = ("bear steepener (long rates rising — inflation/debt-concern "
                          "driven, historically the more concerning pattern)")
        elif short_falling and long_rising:
            steepener = "mixed steepening (both ends moving)"

    # 3m10y (the Fed's own preferred inversion metric) is a refinement on top of the
    # 2s10s spread above, same treatment as the steepener classification -- optional,
    # degrades gracefully (curve_now/recession_prob remain the required inputs).
    curve_3m10y_obs = fred_observation_on(config.FRED_YIELD_CURVE_3M10Y_SERIES, today)

    detail = (
        f"10Y-2Y spread {curve_now:+.2f}pp (as of {curve_date.isoformat()}), "
        f"recession probability {recession_prob:.1f}% (as of {prob_date.isoformat()})"
    )
    if curve_3m10y_obs is not None:
        curve_3m10y, curve_3m10y_date = curve_3m10y_obs
        detail += f"; 10Y-3M spread {curve_3m10y:+.2f}pp (as of {curve_3m10y_date.isoformat()})"
        if curve_3m10y < 0:
            detail += " (inverted)"
    if steepener:
        detail += f"; {steepener}"

    verdict = "flag" if (
        recession_prob >= config.RECESSION_PROB_FLAG_PCT
        or (curve_3m10y_obs is not None and curve_3m10y_obs[0] < 0)
    ) else "ok"
    return CheckResult(
        name="recession_signal", verdict=verdict, detail=detail,
        data={
            "yield_curve": curve_now, "yield_curve_date": curve_date.isoformat(),
            "recession_prob": recession_prob, "recession_prob_date": prob_date.isoformat(),
            "yield_curve_3m10y": curve_3m10y_obs[0] if curve_3m10y_obs else None,
            "yield_curve_3m10y_date": curve_3m10y_obs[1].isoformat() if curve_3m10y_obs else None,
            "steepener": steepener,
        },
    )


def check_inflation_expectations() -> CheckResult:
    """Market-implied inflation expectations -- complements recession_signal's
    yield-curve/recession-probability read (backward/coincident) with a forward-looking
    signal: what the TIPS/breakeven market currently prices in for future inflation,
    as opposed to check_consumer_sentiment's survey-based read or realized CPI.
    """
    today = date.today()
    breakeven_obs = fred_observation_on(config.FRED_BREAKEVEN_10Y_SERIES, today)
    forward_obs = fred_observation_on(config.FRED_BREAKEVEN_5Y5Y_FORWARD_SERIES, today)
    if breakeven_obs is None or forward_obs is None:
        return CheckResult(
            name="inflation_expectations", verdict="unknown",
            detail="FRED breakeven inflation data unavailable "
                   "(FRED_API_KEY not set, or series unavailable)",
        )
    breakeven, breakeven_date = breakeven_obs
    forward, forward_date = forward_obs

    detail = (
        f"10Y breakeven {breakeven:.2f}% (as of {breakeven_date.isoformat()}), "
        f"5Y5Y forward {forward:.2f}% (as of {forward_date.isoformat()})"
    )
    verdict = "flag" if forward >= config.INFLATION_EXPECTATION_FLAG_PCT else "ok"
    return CheckResult(
        name="inflation_expectations", verdict=verdict, detail=detail,
        data={
            "breakeven_10y": breakeven, "breakeven_10y_date": breakeven_date.isoformat(),
            "forward_5y5y": forward, "forward_5y5y_date": forward_date.isoformat(),
        },
    )


def check_credit_spreads() -> CheckResult:
    """High-yield credit spread -- the bond market's own pricing of default risk,
    investment-strategy.md's "credit stress" job (alongside recession_signal's
    recession-onset job and the valuation checks in checks/valuation.py). Useful as a
    counter-check against equity valuation gauges: spreads can stay tight even when
    equity valuations look stretched, meaning credit markets aren't (yet) pricing in
    the same stress.
    """
    obs = fred_observation_on(config.FRED_HY_OAS_SERIES, date.today())
    if obs is None:
        return CheckResult(
            name="credit_spreads", verdict="unknown",
            detail="FRED high-yield credit spread data unavailable "
                   "(FRED_API_KEY not set, or series unavailable)",
        )
    value, obs_date = obs
    as_of = f"as of {obs_date.isoformat()}"
    if value >= config.CREDIT_SPREAD_FLAG_PCT:
        return CheckResult(
            name="credit_spreads", verdict="flag",
            detail=f"ICE BofA US HY OAS at {value:.2f}pp ({as_of}), at/above the "
                   f"{config.CREDIT_SPREAD_FLAG_PCT:.1f}pp stress threshold",
            data={"value": value, "as_of": obs_date.isoformat()},
        )
    return CheckResult(
        name="credit_spreads", verdict="ok",
        detail=f"ICE BofA US HY OAS at {value:.2f}pp ({as_of})",
        data={"value": value, "as_of": obs_date.isoformat()},
    )


def check_australia_cpi() -> CheckResult:
    """Australia's own headline CPI (YoY), read directly from the ABS (see
    mytrader/abs_cpi.py) rather than FRED's OECD-relay copy, which was found 18+
    months stale (verified 2026-07-30). Flags outside the RBA's official 2-3%
    inflation target band.
    """
    result = abs_cpi.fetch_australia_cpi_yoy()
    if result is None:
        return CheckResult(
            name="australia_cpi", verdict="unknown",
            detail="ABS CPI data unavailable (fetch/parse failed)",
        )
    value, ref_month = result
    as_of = f"reference month {ref_month.isoformat()}"
    data = {"value": value, "reference_month": ref_month.isoformat()}
    if value < config.RBA_TARGET_BAND_LOW_PCT or value > config.RBA_TARGET_BAND_HIGH_PCT:
        return CheckResult(
            name="australia_cpi", verdict="flag",
            detail=f"Australia headline CPI {value:.1f}% YoY ({as_of}), outside the "
                   f"RBA's {config.RBA_TARGET_BAND_LOW_PCT:.0f}-"
                   f"{config.RBA_TARGET_BAND_HIGH_PCT:.0f}% target band",
            data=data,
        )
    return CheckResult(
        name="australia_cpi", verdict="ok",
        detail=f"Australia headline CPI {value:.1f}% YoY ({as_of}), within RBA target band",
        data=data,
    )


def check_us_cpi() -> CheckResult:
    """US headline CPI (YoY), via FRED's own units="pc1" transform on CPIAUCSL --
    the realized/backward-looking counterpart to check_inflation_expectations'
    forward-looking breakeven read. Flags outside a +/-1pp band around the Fed's 2%
    target (the Fed itself targets a single point, not an official band like the
    RBA's, so this is a reasonable-tolerance approximation, not an official range).
    """
    obs = fred_observation_on(config.FRED_US_CPI_SERIES, date.today(), units="pc1")
    if obs is None:
        return CheckResult(
            name="us_cpi", verdict="unknown",
            detail="FRED US CPI data unavailable (FRED_API_KEY not set, or series unavailable)",
        )
    value, obs_date = obs
    as_of = f"as of {obs_date.isoformat()}"
    data = {"value": value, "as_of": obs_date.isoformat()}
    if value < config.US_CPI_TARGET_BAND_LOW_PCT or value > config.US_CPI_TARGET_BAND_HIGH_PCT:
        return CheckResult(
            name="us_cpi", verdict="flag",
            detail=f"US headline CPI {value:.2f}% YoY ({as_of}), outside the "
                   f"{config.US_CPI_TARGET_BAND_LOW_PCT:.0f}-"
                   f"{config.US_CPI_TARGET_BAND_HIGH_PCT:.0f}% tolerance band around "
                   f"the Fed's 2% target",
            data=data,
        )
    return CheckResult(
        name="us_cpi", verdict="ok",
        detail=f"US headline CPI {value:.2f}% YoY ({as_of})",
        data=data,
    )


def check_uk_cpi() -> CheckResult:
    """UK headline CPI (YoY), read directly from the ONS's stable CSV endpoint
    (mytrader/ons_cpi.py) -- same realized/backward-looking job as australia_cpi
    and us_cpi. Flags outside a +/-1pp tolerance band around the BoE's 2% target
    (a single point target, not an official band, same approximation as us_cpi).
    """
    result = ons_cpi.fetch_uk_cpi_yoy()
    if result is None:
        return CheckResult(
            name="uk_cpi", verdict="unknown",
            detail="ONS CPI data unavailable (fetch/parse failed)",
        )
    value, ref_month = result
    as_of = f"reference month {ref_month.isoformat()}"
    data = {"value": value, "reference_month": ref_month.isoformat()}
    if value < config.UK_CPI_TARGET_BAND_LOW_PCT or value > config.UK_CPI_TARGET_BAND_HIGH_PCT:
        return CheckResult(
            name="uk_cpi", verdict="flag",
            detail=f"UK headline CPI {value:.1f}% YoY ({as_of}), outside the "
                   f"{config.UK_CPI_TARGET_BAND_LOW_PCT:.0f}-"
                   f"{config.UK_CPI_TARGET_BAND_HIGH_PCT:.0f}% tolerance band around "
                   f"the BoE's 2% target",
            data=data,
        )
    return CheckResult(
        name="uk_cpi", verdict="ok",
        detail=f"UK headline CPI {value:.1f}% YoY ({as_of}), within tolerance band",
        data=data,
    )


def _yfinance_history_close(ticker: str, lookback_days: int):
    """Long-range close history for a single non-ASX (futures/index) ticker -- mirrors
    crash_windows._fetch_close_series, simplified since futures/index tickers never
    need the .AX equity fallback that function carries for ASX-listed stocks.
    """
    import yfinance as yf

    try:
        start = (date.today() - timedelta(days=lookback_days)).isoformat()
        hist = yf.Ticker(ticker).history(start=start, auto_adjust=True)
        if hist.empty:
            return None
        close = hist["Close"]
        if getattr(close.index, "tz", None) is not None:
            close.index = close.index.tz_localize(None)
        return close
    except Exception:
        return None


def check_real_yields() -> CheckResult:
    """10Y TIPS real yield (FRED DFII10) -- the opportunity cost of holding
    non-yielding gold, the single most important gold driver per the handoff
    research. Two-sided band: negative real yields are a bullish catalyst for gold,
    while elevated real yields historically pressure it hard -- opposite-direction
    signals, so the detail text always states which side triggered rather than a
    generic "outside band" message.
    """
    obs = fred_observation_on(config.FRED_REAL_YIELD_10Y_SERIES, date.today())
    if obs is None:
        return CheckResult(
            name="real_yields", verdict="unknown",
            detail="FRED 10Y TIPS real yield data unavailable "
                   "(FRED_API_KEY not set, or series unavailable)",
        )
    value, obs_date = obs
    as_of = f"as of {obs_date.isoformat()}"
    data = {"value": value, "as_of": obs_date.isoformat(), "direction": None}
    if value < config.REAL_YIELD_FLAG_NEGATIVE_PCT:
        data["direction"] = "negative"
        return CheckResult(
            name="real_yields", verdict="flag",
            detail=f"10Y real yield {value:+.2f}% ({as_of}), negative -- historically "
                   f"a bullish catalyst for gold",
            data=data,
        )
    if value > config.REAL_YIELD_FLAG_HIGH_PCT:
        data["direction"] = "elevated"
        return CheckResult(
            name="real_yields", verdict="flag",
            detail=f"10Y real yield {value:+.2f}% ({as_of}), above the "
                   f"{config.REAL_YIELD_FLAG_HIGH_PCT:.1f}% threshold -- elevated real "
                   f"yields historically pressure gold hard",
            data=data,
        )
    return CheckResult(
        name="real_yields", verdict="ok",
        detail=f"10Y real yield {value:+.2f}% ({as_of}), within neutral range",
        data=data,
    )


def check_dollar_index() -> CheckResult:
    """Broad trade-weighted USD index (FRED DTWEXBGS) -- gold is priced in USD and
    usually inverse-correlated with dollar strength. Flags on a large move over the
    lookback window rather than an absolute level, since DXY has no natural high/low
    the way a bounded ratio does -- same today/prior lookback shape as
    check_recession_signal()'s steepener comparison.
    """
    today = date.today()
    prior = today - timedelta(days=config.DXY_LOOKBACK_DAYS)
    now_value = fred_value_on(config.FRED_USD_INDEX_SERIES, today)
    prior_value = fred_value_on(config.FRED_USD_INDEX_SERIES, prior)
    if now_value is None or prior_value is None:
        return CheckResult(
            name="dollar_index", verdict="unknown",
            detail="FRED broad USD index data unavailable "
                   "(FRED_API_KEY not set, or series unavailable)",
        )
    pct_change = round((now_value - prior_value) / prior_value * 100, 2)
    data = {
        "value": now_value, "pct_change": pct_change,
        "lookback_days": config.DXY_LOOKBACK_DAYS, "direction": None,
    }
    if pct_change >= config.DXY_FLAG_MOVE_PCT:
        data["direction"] = "rising"
    elif pct_change <= -config.DXY_FLAG_MOVE_PCT:
        data["direction"] = "falling"
    detail = (
        f"Broad USD index {now_value:.1f}, {pct_change:+.1f}% over the past "
        f"{config.DXY_LOOKBACK_DAYS} days"
    )
    if abs(pct_change) >= config.DXY_FLAG_MOVE_PCT:
        return CheckResult(name="dollar_index", verdict="flag", detail=detail, data=data)
    return CheckResult(name="dollar_index", verdict="ok", detail=detail, data=data)


def check_gold_trend() -> CheckResult:
    """Gold futures price vs its 50/200-day moving averages, the most recent
    price/200DMA cross event, and PMGOLD/AUD context for Shaun's actual holding.
    Deliberately always "info" (or "unknown" on total fetch failure) -- see module
    docstring for why a 200DMA cross is reported as neutral fact rather than judged.
    PMGOLD price and AUD/USD context are enrichment only: the GC=F fetch is the
    required leg, and either enrichment fetch is allowed to independently fail
    without failing the whole check.
    """
    close = _yfinance_history_close(config.GOLD_FUTURES_TICKER, config.GOLD_MA_HISTORY_LOOKBACK_DAYS)
    if close is None or len(close) < config.GOLD_MA_LONG_DAYS:
        return CheckResult(
            name="gold_trend", verdict="unknown",
            detail=f"{config.GOLD_FUTURES_TICKER} price history unavailable via yfinance",
        )

    ma_short = close.rolling(config.GOLD_MA_SHORT_DAYS).mean()
    ma_long = close.rolling(config.GOLD_MA_LONG_DAYS).mean()

    price = float(close.iloc[-1])
    short_dma = float(ma_short.iloc[-1])
    long_dma = float(ma_long.iloc[-1])
    pct_from_long = round((price - long_dma) / long_dma * 100, 1)

    # Sign-flip cross detection: dropna() first so the leading NaN block (before
    # GOLD_MA_LONG_DAYS rows of history exist) doesn't corrupt the comparison.
    diff = (close - ma_long).dropna()
    sign = diff.gt(0).astype(int) - diff.lt(0).astype(int)
    sign_changed = sign.diff().fillna(0) != 0  # first row's diff() is NaN -> not a change
    sign_changes = sign[sign_changed]

    if sign_changes.empty:
        cross_note = f"no cross in the past {config.GOLD_MA_HISTORY_LOOKBACK_DAYS} days of history"
        cross_date_str = None
        cross_direction = None
    else:
        cross_date = sign_changes.index[-1]
        cross_direction = "crossed above" if sign_changes.iloc[-1] > 0 else "crossed below"
        cross_price = float(close.loc[cross_date])
        cross_date_str = cross_date.date().isoformat()
        cross_note = (
            f"{cross_direction} 200DMA on {cross_date_str} at ${cross_price:,.0f}, "
            f"no cross back since"
        )

    direction = None
    if cross_direction == "crossed above":
        direction = "crossed_above"
    elif cross_direction == "crossed below":
        direction = "crossed_below"

    pmgold_price = _yfinance_latest_close(config.PMGOLD_YFINANCE_TICKER)
    fx_change = market_data.fetch_fx_change_pct("USD")

    detail = (
        f"{config.GOLD_FUTURES_TICKER} ${price:,.0f} (50DMA ${short_dma:,.0f}, "
        f"200DMA ${long_dma:,.0f}, {pct_from_long:+.1f}% from 200DMA); {cross_note}; "
        f"PMGOLD {'$' + format(pmgold_price, ',.2f') + ' AUD' if pmgold_price is not None else 'price unavailable'}; "
        f"AUD/USD 3mo move {f'{fx_change:+.1f}%' if fx_change is not None else 'unavailable'}"
    )

    return CheckResult(
        name="gold_trend", verdict="info", detail=detail,
        data={
            "price": price, "ma_short": short_dma, "ma_long": long_dma,
            "pct_from_200dma": pct_from_long,
            "cross_date": cross_date_str, "cross_direction": cross_direction,
            "direction": direction,
            "pmgold_price": pmgold_price, "aud_usd_3mo_change_pct": fx_change,
        },
    )


def check_gold_silver_ratio() -> CheckResult:
    """Gold/silver price ratio (GC=F / SI=F) -- flagged at commonly-cited
    historical-extreme high/low bands.
    """
    gold = _yfinance_latest_close(config.GOLD_FUTURES_TICKER)
    silver = _yfinance_latest_close(config.SILVER_FUTURES_TICKER)
    if gold is None or silver is None or silver == 0:
        return CheckResult(
            name="gold_silver_ratio", verdict="unknown",
            detail=f"{config.GOLD_FUTURES_TICKER}/{config.SILVER_FUTURES_TICKER} "
                   f"price data unavailable via yfinance",
        )
    ratio = round(gold / silver, 1)
    data: dict[str, float | str | None] = {"gold": gold, "silver": silver, "ratio": ratio, "direction": None}
    if ratio >= config.GOLD_SILVER_RATIO_FLAG_HIGH:
        data["direction"] = "high"
        return CheckResult(
            name="gold_silver_ratio", verdict="flag",
            detail=f"Gold/silver ratio at {ratio}, at/above the "
                   f"{config.GOLD_SILVER_RATIO_FLAG_HIGH:.0f} historical-extreme-high level",
            data=data,
        )
    if ratio <= config.GOLD_SILVER_RATIO_FLAG_LOW:
        data["direction"] = "low"
        return CheckResult(
            name="gold_silver_ratio", verdict="flag",
            detail=f"Gold/silver ratio at {ratio}, at/below the "
                   f"{config.GOLD_SILVER_RATIO_FLAG_LOW:.0f} historical-extreme-low level",
            data=data,
        )
    return CheckResult(
        name="gold_silver_ratio", verdict="ok",
        detail=f"Gold/silver ratio at {ratio}",
        data=data,
    )


def check_vix() -> CheckResult:
    value = _yfinance_latest_close(config.VIX_TICKER)
    if value is None:
        return CheckResult(
            name="vix", verdict="unknown",
            detail=f"{config.VIX_TICKER} data unavailable via yfinance",
        )
    if value >= config.VIX_FLAG_LEVEL:
        return CheckResult(
            name="vix", verdict="flag",
            detail=f"VIX at {value:.1f}, at/above the "
                   f"{config.VIX_FLAG_LEVEL:.0f} crisis-adjacent threshold",
            data={"value": value, "direction": "elevated"},
        )
    return CheckResult(
        name="vix", verdict="ok",
        detail=f"VIX at {value:.1f}, below the flag threshold",
        data={"value": value, "direction": None},
    )


def run_all() -> list[CheckResult]:
    return [
        check_move_index(),
        check_housing_affordability(),
        check_consumer_sentiment(),
        check_recession_signal(),
        check_inflation_expectations(),
        check_credit_spreads(),
        check_australia_cpi(),
        check_us_cpi(),
        check_uk_cpi(),
        check_real_yields(),
        check_dollar_index(),
        check_gold_trend(),
        check_gold_silver_ratio(),
        check_vix(),
    ]
