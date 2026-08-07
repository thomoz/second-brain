"""Technical-analysis indicators for GC=F -- trend, momentum, volatility, key
levels, volume, and seasonality, computed from real OHLCV data. Every indicator
is built as a *_series() function (the full historical Series, consumed by
gold_backtest.py's state-conditioned backtest) with a thin compute_*() wrapper
around it (today's value only, consumed by the live outlook) -- one formula, two
consumers, so there is never a second, independently-drifting implementation of
the same indicator. Does NOT modify macro_indicators.check_gold_trend(), which
stays exactly as Phase 1 shipped it -- some overlap (both independently touch
50/200DMA) is accepted, same cross-module-coupling tradeoff macro_indicators.py's
own docstring already makes for its duplicated FRED series-ID strings.
"""

from __future__ import annotations

from datetime import date

import pandas as pd

from . import config


def _fetch_ohlcv(ticker: str, start: date) -> pd.DataFrame | None:
    import yfinance as yf
    try:
        hist = yf.Ticker(ticker).history(start=start.isoformat(), auto_adjust=True)
        if hist.empty:
            return None
        if getattr(hist.index, "tz", None) is not None:
            hist.index = hist.index.tz_localize(None)
        return hist[["Open", "High", "Low", "Close", "Volume"]]
    except Exception:
        return None


def moving_average_series(close: pd.Series, days: int) -> pd.Series:
    return close.rolling(days).mean()


def rsi_series(close: pd.Series, period: int = config.GOLD_TA_RSI_PERIOD_DAYS) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    # Wilder's smoothing (textbook RSI), not a plain SMA.
    avg_gain = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def macd_series(close: pd.Series) -> dict[str, pd.Series]:
    ema_fast = close.ewm(span=config.GOLD_TA_MACD_FAST_DAYS, adjust=False).mean()
    ema_slow = close.ewm(span=config.GOLD_TA_MACD_SLOW_DAYS, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=config.GOLD_TA_MACD_SIGNAL_DAYS, adjust=False).mean()
    return {"macd": macd_line, "signal": signal_line, "histogram": macd_line - signal_line}


def stochastic_series(df: pd.DataFrame) -> dict[str, pd.Series]:
    period = config.GOLD_TA_STOCH_PERIOD_DAYS
    low_min = df["Low"].rolling(period).min()
    high_max = df["High"].rolling(period).max()
    k = (df["Close"] - low_min) / (high_max - low_min) * 100
    d = k.rolling(config.GOLD_TA_STOCH_SMOOTHING_DAYS).mean()
    return {"k": k, "d": d}


def atr_series(df: pd.DataFrame, period: int = config.GOLD_TA_ATR_PERIOD_DAYS) -> pd.Series:
    prev_close = df["Close"].shift(1)
    tr = pd.concat([
        df["High"] - df["Low"],
        (df["High"] - prev_close).abs(),
        (df["Low"] - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False).mean()


def compute_trend(df: pd.DataFrame) -> dict:
    close = df["Close"]
    ma20 = moving_average_series(close, config.GOLD_TA_MA_FAST_DAYS)
    ma50 = moving_average_series(close, config.GOLD_MA_SHORT_DAYS)
    ma200 = moving_average_series(close, config.GOLD_MA_LONG_DAYS)
    price = float(close.iloc[-1])
    return {
        "price": price,
        "prev_close": float(close.iloc[-2]),
        "ma20": float(ma20.iloc[-1]), "ma50": float(ma50.iloc[-1]), "ma200": float(ma200.iloc[-1]),
        "price_above_ma20": price > ma20.iloc[-1],
        "price_above_ma50": price > ma50.iloc[-1],
        "price_above_ma200": price > ma200.iloc[-1],
        "ma20_rising": ma20.iloc[-1] > ma20.iloc[-6],
        "ma50_rising": ma50.iloc[-1] > ma50.iloc[-6],
    }


def compute_macd(close: pd.Series) -> dict:
    s = macd_series(close)
    return {
        "macd": float(s["macd"].iloc[-1]), "signal": float(s["signal"].iloc[-1]),
        "histogram": float(s["histogram"].iloc[-1]),
        "histogram_rising": s["histogram"].iloc[-1] > s["histogram"].iloc[-2],
    }


def compute_rsi(close: pd.Series) -> float:
    return float(rsi_series(close).iloc[-1])


def compute_stochastic(df: pd.DataFrame) -> dict:
    s = stochastic_series(df)
    return {"k": float(s["k"].iloc[-1]), "d": float(s["d"].iloc[-1])}


def compute_atr(df: pd.DataFrame) -> float:
    return float(atr_series(df).iloc[-1])


def compute_bollinger(close: pd.Series) -> dict:
    period = config.GOLD_TA_BOLLINGER_PERIOD_DAYS
    mid = close.rolling(period).mean()
    std = close.rolling(period).std()
    upper = mid + config.GOLD_TA_BOLLINGER_STD_MULTIPLIER * std
    lower = mid - config.GOLD_TA_BOLLINGER_STD_MULTIPLIER * std
    width_pct = (upper.iloc[-1] - lower.iloc[-1]) / mid.iloc[-1] * 100
    return {"mid": float(mid.iloc[-1]), "upper": float(upper.iloc[-1]),
            "lower": float(lower.iloc[-1]), "width_pct": round(float(width_pct), 2)}


def compute_levels(df: pd.DataFrame) -> dict:
    window = df.tail(config.GOLD_TA_LEVEL_LOOKBACK_DAYS)
    return {"resistance": float(window["High"].max()), "support": float(window["Low"].min())}


def compute_volume_context(df: pd.DataFrame) -> dict:
    avg = df["Volume"].rolling(config.GOLD_TA_VOLUME_AVG_DAYS).mean()
    today = float(df["Volume"].iloc[-1])
    avg_today = float(avg.iloc[-1])
    return {"volume": today, "avg_volume": avg_today,
            "above_average": today > avg_today if avg_today else None}


def compute_seasonality(close: pd.Series, as_of: date) -> dict:
    """This calendar month's historical average/median return across every year
    of available history -- month-of-year only (week-of-year would have far
    fewer samples per bucket given ~25 years of data)."""
    monthly = close.resample("ME").last()
    monthly_returns = monthly.pct_change().dropna() * 100
    same_month = monthly_returns[monthly_returns.index.month == as_of.month]
    if same_month.empty:
        return {"n": 0, "mean": None, "median": None}
    return {
        "n": len(same_month),
        "mean": round(float(same_month.mean()), 2),
        "median": round(float(same_month.median()), 2),
    }


def compute_today_technicals() -> dict | None:
    df = _fetch_ohlcv(config.GOLD_FUTURES_TICKER, config.GOLD_BACKTEST_HISTORY_START)
    if df is None or len(df) < config.GOLD_MA_LONG_DAYS:
        return None
    close = df["Close"]
    return {
        "trend": compute_trend(df), "macd": compute_macd(close), "rsi": compute_rsi(close),
        "stochastic": compute_stochastic(df), "atr": compute_atr(df),
        "bollinger": compute_bollinger(close), "levels": compute_levels(df),
        "volume": compute_volume_context(df), "seasonality": compute_seasonality(close, date.today()),
    }
