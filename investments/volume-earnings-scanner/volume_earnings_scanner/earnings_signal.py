"""Signal 2: record earnings. The closest existing precedent for "pull something
earnings-shaped out of yfinance that's never been used in this codebase before" is
mytrader.earnings_watch.fetch_estimate_snapshot -- same yf_retry.call(lambda: ...)
+ empty/missing-index degradation shape is reused here.

LIVE-VERIFIED 2026-10-14 (Phase 0 of
.agent/plans/volume-spike-earnings-scanner.md), against yfinance 1.5.1:
  - `Ticker.quarterly_income_stmt` carries a "Diluted EPS" row (also "Basic EPS").
    Columns are pandas Timestamps, already ordered NEWEST-FIRST.
  - Mega-cap (NVDA) returned 5 quarterly columns; small/micro-caps tested (FUBO,
    GSAT, CLSK) returned 6 columns but with occasional NaN EPS cells for thinly
    -covered quarters -- NaN is handled as "no data for that quarter", not dropped
    positionally (dropping would break the 4-quarters-back == "a year ago"
    alignment YoY comparison depends on).
  - `Ticker.earnings_history` is cleaner (no row-label parsing) but only ever
    returned 4 quarters in this check -- one quarter short of
    VE_EARNINGS_MIN_QUARTERS_FOR_YOY_ACCEL (5), which would make the
    accelerating-YoY sub-check permanently "insufficient history". Chosen against:
    quarterly_income_stmt's extra quarter of depth matters more than the simpler
    parsing.
  - `Ticker.quarterly_earnings` is confirmed removed (returns None) on this
    yfinance version, as expected -- not used.

Free yfinance quarterly data realistically goes back ~5-6 quarters even for a
mega-cap, not further -- "record" below is honestly a record WITHIN THE AVAILABLE
FREE-DATA WINDOW, not a true all-time record. Documented in every detail string a
candidate's row surfaces, per Decision #3's honesty requirement.
"""

from __future__ import annotations

from typing import Any

from mytrader import yf_retry
from mytrader.checks import CheckResult

from . import config

_NAME = "record_earnings"


def fetch_quarterly_eps_history(ticker: str) -> list[float | None] | None:
    """Newest-first list of diluted EPS per fetched quarter, `None` for a quarter
    with no usable value (NaN/missing -- small/micro-caps with thin coverage are
    expected to have gaps, not crash). Returns None (not []) only when the ticker
    has no usable quarterly earnings data at all -- distinct from "fetched, but
    every quarter is a gap"."""
    import yfinance as yf

    try:
        t = yf.Ticker(ticker)
        q = yf_retry.call(lambda: t.quarterly_income_stmt)
    except Exception:
        return None

    if q is None or q.empty or "Diluted EPS" not in q.index:
        return None

    row = q.loc["Diluted EPS"]
    history = [None if (v is None or v != v) else float(v) for v in row.tolist()]  # v != v -> NaN
    if not any(v is not None for v in history):
        return None
    return history


def check_record_earnings(ticker: str, eps_history: list[float | None] | None) -> CheckResult:
    if not eps_history:
        return CheckResult(
            name=_NAME, verdict="unknown",
            detail=f"{ticker}: no quarterly EPS history available",
        )

    usable = [v for v in eps_history if v is not None]
    if len(usable) < config.VE_EARNINGS_MIN_QUARTERS_FOR_RECORD:
        return CheckResult(
            name=_NAME, verdict="unknown",
            detail=f"{ticker}: only {len(usable)} usable quarter(s) of EPS history "
                   f"(need {config.VE_EARNINGS_MIN_QUARTERS_FOR_RECORD}) -- insufficient history",
        )

    latest = eps_history[0]
    findings: list[str] = []
    data: dict[str, Any] = {"quarters_available": len(eps_history), "usable_quarters": len(usable)}

    record_eps = False
    if latest is not None:
        record_eps = latest >= max(usable)
        data["latest_eps"] = latest
        data["record_eps"] = record_eps
        if record_eps:
            findings.append(
                f"latest quarter's diluted EPS ({latest:.2f}) is the highest of the "
                f"{len(usable)} quarters available (record within available reporting history)"
            )

    accelerating_yoy = False
    if len(eps_history) >= config.VE_EARNINGS_MIN_QUARTERS_FOR_YOY_ACCEL:
        yoy_pairs: dict[int, float] = {}
        for k in range(0, len(eps_history) - 4):
            cur, prior = eps_history[k], eps_history[k + 4]
            if cur is None or prior is None or prior == 0:
                continue
            yoy_pairs[k] = (cur - prior) / abs(prior)

        if 0 in yoy_pairs:
            latest_yoy = yoy_pairs[0]
            accelerating_yoy = latest_yoy > 0 and latest_yoy >= max(yoy_pairs.values())
            data["latest_yoy_growth_pct"] = round(latest_yoy * 100, 1)
            data["accelerating_yoy"] = accelerating_yoy
            if accelerating_yoy:
                findings.append(
                    f"latest quarter's YoY EPS growth ({latest_yoy * 100:+.1f}%) is the fastest "
                    f"of every YoY-comparable quarter pair available (accelerating growth within "
                    f"available reporting history)"
                )

    if record_eps or accelerating_yoy:
        return CheckResult(
            name=_NAME, verdict="interesting",
            detail=f"{ticker}: " + "; ".join(findings),
            data=data,
        )
    return CheckResult(
        name=_NAME, verdict="ok",
        detail=f"{ticker}: no record EPS or accelerating YoY growth within the "
               f"{len(eps_history)} quarter(s) of available history",
        data=data,
    )
