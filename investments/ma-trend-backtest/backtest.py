"""Moving-average trend-following backtest: S&P 500, 1999-present.

Strategies tested (see METHODOLOGY in the generated report for full rules):
  A. Buy & Hold            - always long
  B. Long/Cash             - long above MA (rising), cash below MA (falling), hold on disagreement
  C. Long/Short            - long above MA (rising), short below MA (falling), hold on disagreement

Signals come from ^GSPC close vs its SMA; execution happens on SPY at the next
trading day's open (no look-ahead). Returns are built from raw SPY price changes
plus explicit dividends (never from the pre-adjusted "Adj Close" series) so that
dividends are counted exactly once and can be correctly flipped in sign for shorts.

Usage:
    python backtest.py            # fetch (or reuse cached) data, run everything, write results/results.json
    python backtest.py --refresh  # force re-download of price data
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, asdict
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

HERE = Path(__file__).parent
DATA_DIR = HERE / "data"
RESULTS_DIR = HERE / "results"

FETCH_START = "1996-06-01"   # buffer so 250DMA is valid well before the test window
TEST_START = pd.Timestamp("1999-01-01")

MA_LENGTHS = [100, 125, 150, 175, 200, 250]
HEADLINE_MA = 200

INITIAL_CAPITAL = 10_000.0
COMMISSION_PER_LEG = 3.0          # USD flat, matches IBKR-style ~$6 round trip on a long
SLIPPAGE_BPS = 2.0 / 10_000       # 2bps of notional per leg (SPY is extremely liquid)
SHORT_BORROW_ANNUAL = 0.0030      # 0.30%/yr stock-loan fee, SPY is easy-to-borrow
DAYS_PER_YEAR_FINANCING = 365.0   # borrow fee / cash interest accrue on calendar days
TRADING_DAYS_PER_YEAR = 252

BEAR_MARKETS = [
    {"name": "Dot-com crash", "start": "2000-03-24", "end": "2002-10-09"},
    {"name": "Global Financial Crisis", "start": "2007-10-09", "end": "2009-03-09"},
    {"name": "COVID crash", "start": "2020-02-19", "end": "2020-03-23"},
    {"name": "2022 bear market", "start": "2022-01-03", "end": "2022-10-12"},
]


# --------------------------------------------------------------------------- #
# Data loading
# --------------------------------------------------------------------------- #

def _flatten_index(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.index = pd.to_datetime(df.index.tz_localize(None).normalize())
    return df


def fetch_data(refresh: bool = False) -> dict[str, pd.DataFrame]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    out = {}
    specs = {
        "gspc": "^GSPC",
        "spy": "SPY",
        "irx": "^IRX",
    }
    for key, ticker in specs.items():
        cache_path = DATA_DIR / f"{key}.csv"
        if cache_path.exists() and not refresh:
            df = pd.read_csv(cache_path, index_col=0, parse_dates=True)
        else:
            df = yf.Ticker(ticker).history(start=FETCH_START, auto_adjust=False)
            df = _flatten_index(df)
            df.to_csv(cache_path)
        out[key] = df
    return out


def build_aligned_frame(raw: dict[str, pd.DataFrame]) -> pd.DataFrame:
    gspc = raw["gspc"][["Close"]].rename(columns={"Close": "gspc_close"})
    spy = raw["spy"][["Open", "Close", "Dividends"]].rename(
        columns={"Open": "spy_open", "Close": "spy_close", "Dividends": "spy_div"}
    )
    irx = raw["irx"][["Close"]].rename(columns={"Close": "irx_pct"})

    df = spy.join(gspc, how="inner").join(irx, how="left")
    df["irx_pct"] = df["irx_pct"].ffill().bfill()
    df = df.sort_index()
    return df


# --------------------------------------------------------------------------- #
# Signal + position construction
# --------------------------------------------------------------------------- #

def compute_ma_signals(gspc_close: pd.Series, ma_length: int) -> tuple[pd.Series, pd.Series, pd.Series]:
    ma = gspc_close.rolling(ma_length).mean()
    ma_prev = ma.shift(1)
    long_sig = (gspc_close > ma) & (ma > ma_prev)
    bear_sig = (gspc_close < ma) & (ma < ma_prev)
    return ma, long_sig, bear_sig


def build_position_series(
    gspc_close: pd.Series, ma: pd.Series, long_sig: pd.Series, bear_sig: pd.Series,
    allow_short: bool,
) -> tuple[pd.Series, str]:
    """Daily *intended* position, known as of that day's close. Held on disagreement."""
    idx = gspc_close.index
    test_idx = idx[idx >= TEST_START]
    start_i = idx.get_loc(test_idx[0])

    cash_or_short = -1 if allow_short else 0

    if bool(long_sig.iloc[start_i]):
        current = 1
        init_rule = "long_signal_satisfied"
    elif bool(bear_sig.iloc[start_i]):
        current = cash_or_short
        init_rule = "bearish_signal_satisfied"
    else:
        current = 1 if gspc_close.iloc[start_i] > ma.iloc[start_i] else cash_or_short
        init_rule = "tiebreak_price_vs_ma_no_slope_confirmation"

    pos = pd.Series(0.0, index=idx)
    pos.iloc[start_i] = current
    for i in range(start_i + 1, len(idx)):
        if bool(long_sig.iloc[i]):
            current = 1
        elif bool(bear_sig.iloc[i]):
            current = cash_or_short
        pos.iloc[i] = current
    return pos.loc[test_idx], init_rule


# --------------------------------------------------------------------------- #
# Simulation engine
# --------------------------------------------------------------------------- #

@dataclass
class Trade:
    side: int               # 1 = long, -1 = short, 0 = cash
    entry_date: str
    exit_date: str
    entry_price: float
    exit_price: float
    pnl_pct: float
    duration_days: int
    win: bool


def simulate(
    pos_intent: pd.Series,
    df: pd.DataFrame,
    apply_costs: bool,
    cash_earns_interest: bool,
) -> dict:
    """Walk the position-intent series day by day, compounding an equity curve.

    `pos_intent[i-1]` (known at close of day i-1) is executed at open of day i,
    so a transition day splits into a gap leg (old position, close[i-1]->open[i])
    and an intraday leg (new position, open[i]->close[i]). Non-transition days
    apply the held position to the full close-to-close total return (price move
    + that day's dividend, which is 0 on non-ex-div days).
    """
    idx = pos_intent.index
    spy_open = df.loc[idx, "spy_open"]
    spy_close = df.loc[idx, "spy_close"]
    spy_div = df.loc[idx, "spy_div"]
    irx_daily = (df.loc[idx, "irx_pct"] / 100.0) / DAYS_PER_YEAR_FINANCING

    equity = INITIAL_CAPITAL
    equity_curve = np.empty(len(idx))
    held = int(pos_intent.iloc[0])

    trades: list[Trade] = []
    entry_date = idx[0]
    entry_price = float(spy_open.iloc[0])
    entry_equity = equity

    days_long = days_short = days_cash = 0

    def bump_day_count(pos: int) -> None:
        nonlocal days_long, days_short, days_cash
        if pos == 1:
            days_long += 1
        elif pos == -1:
            days_short += 1
        else:
            days_cash += 1

    equity_curve[0] = equity
    bump_day_count(held)

    for i in range(1, len(idx)):
        date = idx[i]
        prev_close = float(spy_close.iloc[i - 1])
        close = float(spy_close.iloc[i])
        open_ = float(spy_open.iloc[i])
        div = float(spy_div.iloc[i])
        desired = int(pos_intent.iloc[i - 1])  # signal known at close(i-1) -> executes at open(i)

        close_cost = 0.0
        open_cost = 0.0

        if desired != held:
            if apply_costs:
                if held != 0:
                    close_cost = COMMISSION_PER_LEG + equity * SLIPPAGE_BPS
                if desired != 0:
                    open_cost = COMMISSION_PER_LEG + equity * SLIPPAGE_BPS

            gap_ret = open_ / prev_close - 1.0
            intraday_ret = (close - open_ + div) / open_
            day_ret = held * gap_ret + desired * intraday_ret

            # mark the exit value of the trade that just closed (gap leg only, net of its closing cost)
            exit_equity = equity * (1 + held * gap_ret) - close_cost
            if held != 0:
                pnl_pct = (exit_equity - entry_equity) / entry_equity * 100.0
                trades.append(Trade(
                    side=held,
                    entry_date=str(entry_date.date()),
                    exit_date=str(date.date()),
                    entry_price=round(entry_price, 2),
                    exit_price=round(open_, 2),
                    pnl_pct=round(pnl_pct, 3),
                    duration_days=(date - entry_date).days,
                    win=pnl_pct > 0,
                ))

            held = desired
            entry_date = date
            entry_price = open_
        else:
            day_ret = held * ((close - prev_close + div) / prev_close)

        if held == -1 and apply_costs:
            day_ret -= SHORT_BORROW_ANNUAL / DAYS_PER_YEAR_FINANCING
        if held == 0 and cash_earns_interest:
            day_ret += float(irx_daily.iloc[i])

        equity = equity * (1 + day_ret) - close_cost - open_cost
        equity_curve[i] = equity
        bump_day_count(held)

        if entry_date == date:
            entry_equity = equity  # baseline for the trade that just opened

    # close out whatever position was still running at the end of the backtest
    if held != 0:
        final_pnl = (equity - entry_equity) / entry_equity * 100.0
        trades.append(Trade(
            side=held,
            entry_date=str(entry_date.date()),
            exit_date=str(idx[-1].date()) + " (open)",
            entry_price=round(entry_price, 2),
            exit_price=round(float(spy_close.iloc[-1]), 2),
            pnl_pct=round(final_pnl, 3),
            duration_days=(idx[-1] - entry_date).days,
            win=final_pnl > 0,
        ))

    return {
        "equity_curve": equity_curve,
        "trades": trades,
        "days_long": days_long,
        "days_short": days_short,
        "days_cash": days_cash,
        "dates": [str(d.date()) for d in idx],
    }


# --------------------------------------------------------------------------- #
# Metrics
# --------------------------------------------------------------------------- #

def compute_metrics(sim: dict, irx_daily_full: pd.Series) -> dict:
    eq = pd.Series(sim["equity_curve"], index=pd.to_datetime(sim["dates"]))
    daily_ret = eq.pct_change().dropna()
    trades: list[Trade] = sim["trades"]

    years = (eq.index[-1] - eq.index[0]).days / 365.25
    cagr = (eq.iloc[-1] / eq.iloc[0]) ** (1 / years) - 1 if years > 0 else 0.0
    total_return = eq.iloc[-1] / eq.iloc[0] - 1

    roll_max = eq.cummax()
    dd = (eq - roll_max) / roll_max
    max_dd = float(dd.min())

    vol = float(daily_ret.std() * np.sqrt(TRADING_DAYS_PER_YEAR))

    rf_daily = irx_daily_full.reindex(daily_ret.index).ffill().bfill()
    excess = daily_ret - rf_daily
    sharpe = float(excess.mean() / excess.std() * np.sqrt(TRADING_DAYS_PER_YEAR)) if excess.std() > 0 else 0.0
    downside = excess[excess < 0]
    sortino = float(excess.mean() / downside.std() * np.sqrt(TRADING_DAYS_PER_YEAR)) if len(downside) > 1 and downside.std() > 0 else 0.0
    calmar = float(cagr / abs(max_dd)) if max_dd != 0 else 0.0

    win_trades = [t for t in trades if t.win]
    lose_trades = [t for t in trades if not t.win]

    streak = longest_streak = 0
    for t in trades:
        if not t.win:
            streak += 1
            longest_streak = max(longest_streak, streak)
        else:
            streak = 0

    total_days = len(sim["dates"])
    return {
        "cagr_pct": round(float(cagr) * 100, 3),
        "total_return_pct": round(float(total_return) * 100, 2),
        "final_value": round(float(eq.iloc[-1]), 2),
        "max_drawdown_pct": round(max_dd * 100, 2),
        "annualized_vol_pct": round(vol * 100, 2),
        "sharpe": round(sharpe, 3),
        "sortino": round(sortino, 3),
        "calmar": round(calmar, 3),
        "num_trades": len(trades),
        "num_winning_trades": len(win_trades),
        "num_losing_trades": len(lose_trades),
        "win_rate_pct": round(len(win_trades) / len(trades) * 100, 1) if trades else None,
        "avg_winning_trade_pct": round(float(np.mean([t.pnl_pct for t in win_trades])), 3) if win_trades else 0.0,
        "avg_losing_trade_pct": round(float(np.mean([t.pnl_pct for t in lose_trades])), 3) if lose_trades else 0.0,
        "largest_winning_trade_pct": round(max((t.pnl_pct for t in trades), default=0.0), 3),
        "largest_losing_trade_pct": round(min((t.pnl_pct for t in trades), default=0.0), 3),
        "longest_losing_streak": longest_streak,
        "avg_holding_days": round(float(np.mean([t.duration_days for t in trades])), 1) if trades else 0.0,
        "pct_days_long": round(sim["days_long"] / total_days * 100, 1),
        "pct_days_short": round(sim["days_short"] / total_days * 100, 1),
        "pct_days_cash": round(sim["days_cash"] / total_days * 100, 1),
    }


def year_by_year_returns(sim: dict) -> dict:
    eq = pd.Series(sim["equity_curve"], index=pd.to_datetime(sim["dates"]))
    year_end = eq.resample("YE").last()
    out = {}
    prev = float(eq.iloc[0])
    for ts, val in year_end.items():
        out[ts.year] = round((float(val) / prev - 1) * 100, 2)
        prev = float(val)
    return out


def sub_period_cagr(sim: dict, start: str, end: str) -> float | None:
    eq = pd.Series(sim["equity_curve"], index=pd.to_datetime(sim["dates"]))
    window = eq.loc[start:end]
    if len(window) < 2:
        return None
    years = (window.index[-1] - window.index[0]).days / 365.25
    if years <= 0:
        return None
    return round(((float(window.iloc[-1]) / float(window.iloc[0])) ** (1 / years) - 1) * 100, 2)


def window_return_and_dd(sim: dict, start: str, end: str) -> dict:
    eq = pd.Series(sim["equity_curve"], index=pd.to_datetime(sim["dates"]))
    window = eq.loc[start:end]
    if len(window) < 2:
        return {"return_pct": None, "max_drawdown_pct": None}
    ret = float(window.iloc[-1] / window.iloc[0] - 1) * 100
    roll_max = window.cummax()
    dd = float(((window - roll_max) / roll_max).min()) * 100
    return {"return_pct": round(ret, 2), "max_drawdown_pct": round(dd, 2)}


def window_daily_series(sim: dict, start: str, end: str, pad_days: int = 45) -> dict:
    eq = pd.Series(sim["equity_curve"], index=pd.to_datetime(sim["dates"]))
    s = pd.Timestamp(start) - pd.Timedelta(days=pad_days)
    e = pd.Timestamp(end) + pd.Timedelta(days=pad_days)
    window = eq.loc[s:e]
    return {"dates": [str(d.date()) for d in window.index], "equity": [round(float(v), 2) for v in window.values]}


def trades_in_window(trades: list[Trade], start: str, end: str, pad_days: int = 90) -> list[dict]:
    s = pd.Timestamp(start) - pd.Timedelta(days=pad_days)
    e = pd.Timestamp(end) + pd.Timedelta(days=pad_days)
    out = []
    for t in trades:
        ed = pd.Timestamp(t.entry_date)
        if s <= ed <= e:
            out.append(asdict(t))
    return out


def downsample(sim: dict, freq: str = "ME") -> dict:
    eq = pd.Series(sim["equity_curve"], index=pd.to_datetime(sim["dates"]))
    sampled = eq.resample(freq).last().dropna()
    return {
        "dates": [str(d.date()) for d in sampled.index],
        "equity": [round(float(v), 2) for v in sampled.values],
    }


# --------------------------------------------------------------------------- #
# Driver
# --------------------------------------------------------------------------- #

VARIANTS = [
    ("long_cash_0pct", False, False),
    ("long_cash_tbill", False, True),
    ("long_short", True, False),
]


def run_ma_length(df: pd.DataFrame, ma_length: int, irx_daily_full: pd.Series) -> dict:
    gspc_close = df["gspc_close"]
    ma, long_sig, bear_sig = compute_ma_signals(gspc_close, ma_length)

    result = {"ma_length": ma_length, "variants": {}}

    for name, allow_short, cash_interest in VARIANTS:
        pos_intent, init_rule = build_position_series(gspc_close, ma, long_sig, bear_sig, allow_short)
        variant = {"init_rule": init_rule, "costs": {}}
        for cost_label, apply_costs in (("before_costs", False), ("after_costs", True)):
            sim = simulate(pos_intent, df, apply_costs=apply_costs, cash_earns_interest=cash_interest)
            metrics = compute_metrics(sim, irx_daily_full)
            variant["costs"][cost_label] = {
                "metrics": metrics,
                "equity_curve_monthly": downsample(sim),
            }
            if cost_label == "after_costs":
                variant["year_by_year"] = year_by_year_returns(sim)
                variant["trades"] = [asdict(t) for t in sim["trades"]]
                variant["bear_markets"] = {
                    bm["name"]: {
                        **window_return_and_dd(sim, bm["start"], bm["end"]),
                        "trades_near_window": trades_in_window(sim["trades"], bm["start"], bm["end"]),
                        "daily_series": window_daily_series(sim, bm["start"], bm["end"]),
                    }
                    for bm in BEAR_MARKETS
                }
                variant["sub_period_cagr"] = {
                    "1999_2008": sub_period_cagr(sim, "1999-01-01", "2008-12-31"),
                    "2009_2018": sub_period_cagr(sim, "2009-01-01", "2018-12-31"),
                    "2019_present": sub_period_cagr(sim, "2019-01-01", "2099-01-01"),
                }
        result["variants"][name] = variant

    return result


def run_buy_and_hold(df: pd.DataFrame, irx_daily_full: pd.Series) -> dict:
    idx = df.index[df.index >= TEST_START]
    pos_intent = pd.Series(1.0, index=idx)
    out = {"costs": {}}
    for cost_label, apply_costs in (("before_costs", False), ("after_costs", True)):
        sim = simulate(pos_intent, df, apply_costs=apply_costs, cash_earns_interest=False)
        metrics = compute_metrics(sim, irx_daily_full)
        out["costs"][cost_label] = {
            "metrics": metrics,
            "equity_curve_monthly": downsample(sim),
        }
        if cost_label == "after_costs":
            out["year_by_year"] = year_by_year_returns(sim)
            out["bear_markets"] = {
                bm["name"]: {
                    **window_return_and_dd(sim, bm["start"], bm["end"]),
                    "daily_series": window_daily_series(sim, bm["start"], bm["end"]),
                }
                for bm in BEAR_MARKETS
            }
            out["sub_period_cagr"] = {
                "1999_2008": sub_period_cagr(sim, "1999-01-01", "2008-12-31"),
                "2009_2018": sub_period_cagr(sim, "2009-01-01", "2018-12-31"),
                "2019_present": sub_period_cagr(sim, "2019-01-01", "2099-01-01"),
            }
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh", action="store_true", help="force re-download of price data")
    args = parser.parse_args()

    raw = fetch_data(refresh=args.refresh)
    df = build_aligned_frame(raw)
    irx_daily_full = (df["irx_pct"] / 100.0) / DAYS_PER_YEAR_FINANCING

    print(f"Data range: {df.index[0].date()} -> {df.index[-1].date()} ({len(df)} trading days)")

    buy_hold = run_buy_and_hold(df, irx_daily_full)

    ma_results = {}
    for ma_length in MA_LENGTHS:
        print(f"Running MA length {ma_length}...")
        ma_results[ma_length] = run_ma_length(df, ma_length, irx_daily_full)

    output = {
        "generated_at": pd.Timestamp.now().isoformat(),
        "data_range": {"start": str(df.index[0].date()), "end": str(df.index[-1].date())},
        "assumptions": {
            "initial_capital": INITIAL_CAPITAL,
            "commission_per_leg_usd": COMMISSION_PER_LEG,
            "slippage_bps_per_leg": SLIPPAGE_BPS * 10_000,
            "short_borrow_annual_pct": SHORT_BORROW_ANNUAL * 100,
            "cash_rate_source": "^IRX (13-week T-bill discount yield), accrued daily, variant 2 of Long/Cash only",
            "signal_instrument": "^GSPC close vs SMA",
            "execution_instrument": "SPY (raw Open/Close + actual Dividends, never Adj Close)",
            "execution_timing": "signal known at close(t-1) executes at open(t); no look-ahead",
        },
        "ma_lengths_tested": MA_LENGTHS,
        "headline_ma": HEADLINE_MA,
        "bear_markets": BEAR_MARKETS,
        "buy_and_hold": buy_hold,
        "ma_results": ma_results,
    }

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(RESULTS_DIR / "results.json", "w") as f:
        json.dump(output, f, indent=2, default=str)
    print(f"Wrote {RESULTS_DIR / 'results.json'}")


if __name__ == "__main__":
    main()
