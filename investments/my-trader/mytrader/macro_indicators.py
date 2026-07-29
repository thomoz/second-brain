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

FRED_YIELD_CURVE_SERIES/FRED_RECESSION_PROB_SERIES in config.py intentionally
duplicate string values already present in briefs-finance's own
scripts/config.py:FRED_SERIES — that dict is shaped for fetch_fred_macro()'s bulk
multi-series report-ingestion-time snapshot, while this module needs individual
point-in-time reads at two different dates (today + a lookback date, for the
steepener comparison), a different access pattern. Duplicating two short strings was
judged simpler than reshaping shared code across two independently-versioned projects.
"""

from __future__ import annotations

from datetime import date, timedelta

from scripts.macro import fred_observation_on, fred_value_on

from . import config
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

    detail = (
        f"10Y-2Y spread {curve_now:+.2f}pp (as of {curve_date.isoformat()}), "
        f"recession probability {recession_prob:.1f}% (as of {prob_date.isoformat()})"
    )
    if steepener:
        detail += f"; {steepener}"

    verdict = "flag" if recession_prob >= config.RECESSION_PROB_FLAG_PCT else "ok"
    return CheckResult(
        name="recession_signal", verdict=verdict, detail=detail,
        data={
            "yield_curve": curve_now, "yield_curve_date": curve_date.isoformat(),
            "recession_prob": recession_prob, "recession_prob_date": prob_date.isoformat(),
            "steepener": steepener,
        },
    )


def run_all() -> list[CheckResult]:
    return [
        check_move_index(),
        check_housing_affordability(),
        check_consumer_sentiment(),
        check_recession_signal(),
    ]
