"""Signal 1: volume spike. Flags a ticker whose most recent session's volume is far
above its own recent trailing average -- a proxy for institutional money quietly
starting to flow into a name before the market broadly notices (the TradingView-style
per-ticker alert that inspired this tool).

GOTCHA: this is deliberately a DIFFERENT, SHORTER window than
goat.dma_breakout_scan.passes_liquidity_floor's `averageVolume` liquidity floor (a
~3-month rolling average yfinance's `.info` computes). That number is checked
separately, downstream in scan.py, as a liquidity/tradability floor. This signal's
own `config.VE_VOLUME_AVG_WINDOW_DAYS`-day trailing average is what "normal" means for
measuring TODAY's spike -- a 3-month baseline would already have been dragged upward
by a whole quarter of rising volume, hiding exactly the spike this is meant to catch.
Don't conflate the two numbers.
"""

from __future__ import annotations

import pandas as pd
from mytrader.checks import CheckResult

from . import config

_NAME = "volume_spike"


def check_volume_spike(ticker: str, close: pd.Series, volume: pd.Series) -> CheckResult:
    window = config.VE_VOLUME_AVG_WINDOW_DAYS
    if len(volume) < window + 1:
        return CheckResult(
            name=_NAME, verdict="unknown",
            detail=f"{ticker}: insufficient volume history for a {window}-day trailing average",
        )

    today_volume = float(volume.iloc[-1])
    trailing_avg = float(volume.iloc[-(window + 1):-1].mean())

    if not trailing_avg or pd.isna(trailing_avg):
        return CheckResult(
            name=_NAME, verdict="unknown",
            detail=f"{ticker}: trailing {window}-day average volume is zero/unavailable -- "
                   "too illiquid to measure a spike",
        )

    ratio = today_volume / trailing_avg
    data = {"today_volume": today_volume, "trailing_avg_volume": trailing_avg, "ratio": round(ratio, 2)}

    if ratio >= config.VE_VOLUME_SPIKE_RATIO_THRESHOLD:
        return CheckResult(
            name=_NAME, verdict="interesting",
            detail=f"{ticker}: today's volume ({today_volume:,.0f}) is {ratio:.1f}x its trailing "
                   f"{window}-day average ({trailing_avg:,.0f}) -- volume spike",
            data=data,
        )
    return CheckResult(
        name=_NAME, verdict="ok",
        detail=f"{ticker}: today's volume is {ratio:.1f}x its trailing {window}-day average "
               f"-- below the {config.VE_VOLUME_SPIKE_RATIO_THRESHOLD:.1f}x spike threshold",
        data=data,
    )
