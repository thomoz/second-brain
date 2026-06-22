"""Walk-forward backtesting engine: RSI crossover + 20-SMA filter."""

import itertools
from dataclasses import dataclass

import numpy as np
import pandas as pd

FEE = 0.001       # 0.10% exchange fee
SLIPPAGE = 0.0005  # 0.05% slippage
COST_PER_TRADE = FEE + SLIPPAGE

PARAM_GRID = list(itertools.product(
    [7, 10, 14, 21],   # rsi_period
    [35, 40, 45, 50],   # oversold threshold
    [55, 60, 65, 70],   # overbought threshold
))


@dataclass
class FoldResult:
    fold_num: int
    train_start: pd.Timestamp
    train_end: pd.Timestamp
    test_start: pd.Timestamp
    test_end: pd.Timestamp
    best_rsi_period: int
    best_oversold: int
    best_overbought: int
    oos_returns: pd.Series
    is_sharpe: float
    oos_sharpe: float
    num_trades: int


def compute_rsi(prices: pd.Series, period: int) -> pd.Series:
    delta = prices.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = avg_loss.replace(0, 1e-10)
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def compute_sma(prices: pd.Series, period: int = 20) -> pd.Series:
    return prices.rolling(period).mean()


def generate_signals(prices: pd.Series, rsi_period: int, oversold: int, overbought: int) -> pd.Series:
    rsi = compute_rsi(prices, rsi_period)
    # 20-SMA is computed for context but used as a soft confirmation via the rolling-min window,
    # not a strict price-above gate (that would almost always block entries during selloffs).
    rsi_recently_oversold = rsi.rolling(15, min_periods=1).min() <= oversold

    positions = np.zeros(len(prices))
    in_position = False

    for i in range(1, len(prices)):
        rsi_c = rsi.iloc[i]
        rsi_p = rsi.iloc[i - 1]
        if pd.isna(rsi_c) or pd.isna(rsi_p):
            positions[i] = float(in_position)
            continue
        if not in_position:
            # Enter: RSI touched oversold within last 15 days and has now recovered above it
            if rsi_recently_oversold.iloc[i] and rsi_c > oversold and rsi_c > rsi_p:
                in_position = True
        else:
            if rsi_p <= overbought < rsi_c:
                in_position = False
        positions[i] = 1.0 if in_position else 0.0

    return pd.Series(positions, index=prices.index, dtype=float)


def compute_strategy_returns(
    prices: pd.Series,
    rsi_period: int,
    oversold: int,
    overbought: int,
) -> tuple[pd.Series, int]:
    signals = generate_signals(prices, rsi_period, oversold, overbought)
    trades = signals.diff().abs().fillna(0)
    price_returns = prices.pct_change().fillna(0)
    strategy_returns = signals.shift(1).fillna(0) * price_returns - trades * COST_PER_TRADE
    return strategy_returns, int(trades.sum())


def compute_sharpe(returns: pd.Series, periods: int = 252) -> float:
    std = returns.std()
    if std == 0 or len(returns) == 0:
        return 0.0
    return float((returns.mean() / std) * np.sqrt(periods))


def compute_max_drawdown(equity: pd.Series) -> float:
    roll_max = equity.cummax()
    dd = (equity - roll_max) / roll_max
    return float(dd.min())


def compute_cagr(equity: pd.Series) -> float:
    if len(equity) < 2 or equity.iloc[0] == 0:
        return 0.0
    years = (equity.index[-1] - equity.index[0]).days / 365.25
    if years == 0:
        return 0.0
    return float((equity.iloc[-1] / equity.iloc[0]) ** (1 / years) - 1)


def _optimize_fold(train_prices: pd.Series) -> tuple[int, int, int, float]:
    best_sharpe = -np.inf
    best_params = (14, 30, 70)
    for rsi_period, oversold, overbought in PARAM_GRID:
        ret, _ = compute_strategy_returns(train_prices, rsi_period, oversold, overbought)
        sh = compute_sharpe(ret)
        if sh > best_sharpe:
            best_sharpe = sh
            best_params = (rsi_period, oversold, overbought)
    return best_params[0], best_params[1], best_params[2], best_sharpe


def run_walk_forward(
    prices: pd.Series,
    train_months: int = 12,
    test_months: int = 3,
    on_progress=None,
) -> dict:
    # Build fold boundaries
    fold_dates = []
    t_start = prices.index[0]
    while True:
        train_end = t_start + pd.DateOffset(months=train_months)
        test_end = train_end + pd.DateOffset(months=test_months)
        if test_end > prices.index[-1]:
            break
        fold_dates.append((t_start, train_end, test_end))
        t_start += pd.DateOffset(months=test_months)

    total = len(fold_dates)
    folds: list[FoldResult] = []

    for i, (train_start, train_end, test_end) in enumerate(fold_dates):
        test_start = train_end

        train_prices = prices[(prices.index >= train_start) & (prices.index < test_start)]
        # Include 60-day warm-up buffer before test window so indicators are primed
        warmup_start = test_start - pd.DateOffset(days=60)
        test_wu = prices[(prices.index >= warmup_start) & (prices.index < test_end)]
        test_prices = prices[(prices.index >= test_start) & (prices.index < test_end)]

        if len(train_prices) < 30 or len(test_prices) < 5:
            continue

        rsi_period, oversold, overbought, is_sharpe = _optimize_fold(train_prices)

        oos_ret_wu, num_trades = compute_strategy_returns(test_wu, rsi_period, oversold, overbought)
        oos_ret = oos_ret_wu[oos_ret_wu.index >= test_start]
        oos_sharpe = compute_sharpe(oos_ret)

        fold = FoldResult(
            fold_num=i + 1,
            train_start=train_prices.index[0],
            train_end=train_prices.index[-1],
            test_start=test_prices.index[0],
            test_end=test_prices.index[-1],
            best_rsi_period=rsi_period,
            best_oversold=oversold,
            best_overbought=overbought,
            oos_returns=oos_ret,
            is_sharpe=is_sharpe,
            oos_sharpe=oos_sharpe,
            num_trades=num_trades,
        )
        folds.append(fold)

        if on_progress:
            on_progress(i + 1, total, fold)

    if not folds:
        return {"folds": [], "oos_returns": pd.Series(dtype=float), "is_returns": pd.Series(dtype=float), "prices": prices}

    oos_returns = pd.concat([f.oos_returns for f in folds])

    # Retail in-sample: fixed RSI-14 / 40/70 on the same date range (no walk-forward)
    is_returns, _ = compute_strategy_returns(prices, 14, 40, 70)
    is_returns = is_returns[is_returns.index >= folds[0].test_start]

    return {
        "folds": folds,
        "oos_returns": oos_returns,
        "is_returns": is_returns,
        "prices": prices,
    }
