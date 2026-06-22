"""Walk-Forward Trading Strategy Backtester — Streamlit UI."""

from datetime import date

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf

from backtester import (
    FoldResult,
    compute_cagr,
    compute_max_drawdown,
    compute_sharpe,
    run_walk_forward,
)

st.set_page_config(layout="wide", page_title="Walk-Forward Backtester")


# ── Chart builders ──────────────────────────────────────────────────────────

def build_gantt(folds: list[FoldResult]) -> go.Figure:
    rows = []
    for f in folds:
        rows.append({"Window": f"Fold {f.fold_num:02d}", "Start": f.train_start, "Finish": f.train_end, "Type": "Training"})
        rows.append({"Window": f"Fold {f.fold_num:02d}", "Start": f.test_start, "Finish": f.test_end, "Type": "Testing"})

    df = pd.DataFrame(rows)
    fig = px.timeline(
        df,
        x_start="Start",
        x_end="Finish",
        y="Window",
        color="Type",
        color_discrete_map={"Training": "#4472C4", "Testing": "#ED7D31"},
        title="Walk-Forward Windows — Blue: Training  |  Orange: Blind Testing",
    )
    fig.update_layout(
        height=max(350, len(folds) * 22 + 100),
        yaxis_autorange="reversed",
        margin=dict(l=80, r=20, t=50, b=20),
    )
    return fig


def build_equity_chart(oos_returns: pd.Series, is_returns: pd.Series, prices: pd.Series) -> go.Figure:
    start = oos_returns.index[0]

    oos_equity = (1 + oos_returns).cumprod()
    is_equity = (1 + is_returns).cumprod()

    bnh = prices[prices.index >= start]
    bnh_equity = bnh / bnh.iloc[0]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=oos_equity.index, y=oos_equity.values,
        name="Walk-Forward OOS",
        line=dict(color="#ED7D31", width=2.5),
    ))
    fig.add_trace(go.Scatter(
        x=is_equity.index, y=is_equity.values,
        name="Retail In-Sample (RSI 14, OS 40 / OB 70)",
        line=dict(color="#4472C4", width=2, dash="dash"),
    ))
    fig.add_trace(go.Scatter(
        x=bnh_equity.index, y=bnh_equity.values,
        name="Buy & Hold",
        line=dict(color="#70AD47", width=1.5, dash="dot"),
    ))
    fig.update_layout(
        title="Equity Curves: Walk-Forward OOS vs Retail In-Sample vs Buy & Hold",
        xaxis_title="Date",
        yaxis_title="Growth of $1",
        height=520,
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        margin=dict(l=60, r=20, t=80, b=40),
    )
    return fig


# ── Metric helpers ───────────────────────────────────────────────────────────

def metrics(returns: pd.Series) -> dict:
    equity = (1 + returns).cumprod()
    return {
        "Total Return": f"{(equity.iloc[-1] - 1) * 100:.1f}%",
        "CAGR": f"{compute_cagr(equity) * 100:.1f}%",
        "Sharpe": f"{compute_sharpe(returns):.2f}",
        "Max DD": f"{compute_max_drawdown(equity) * 100:.1f}%",
    }


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    st.title("Walk-Forward Trading Strategy Backtester")
    st.caption("RSI Crossover + 20-SMA Trend Filter  |  Grid-search optimisation per fold  |  0.10% fee + 0.05% slippage")

    # Sidebar
    with st.sidebar:
        st.header("Configuration")
        ticker = st.text_input("Ticker", "SPY")
        start_date = st.date_input("Start Date", date(2018, 1, 1))
        end_date = st.date_input("End Date", date.today())
        st.divider()
        train_months = st.slider("Training window (months)", 6, 24, 12)
        test_months = st.slider("Testing window (months)", 1, 6, 3)
        st.divider()
        st.caption(
            "**Strategy:** Enter when RSI touched oversold within 15 days and is now recovering. "
            "Exit when RSI crosses above overbought. 20-SMA used as soft trend context.\n\n"
            "**Optimisation grid:** RSI period [7,10,14,21] × oversold [35,40,45,50] × overbought [55,60,65,70] "
            "— maximises in-sample Sharpe."
        )
        run_btn = st.button("Run Backtest", type="primary", use_container_width=True)

    if not run_btn:
        st.info("Configure settings in the sidebar and click **Run Backtest** to begin.")
        return

    # Download
    with st.spinner(f"Downloading {ticker}…"):
        raw = yf.download(ticker, start=start_date, end=end_date, progress=False, auto_adjust=True)

    if raw.empty:
        st.error(f"No data found for **{ticker}**. Check the ticker symbol.")
        return

    prices: pd.Series = raw["Close"].squeeze().dropna()
    if prices.index.tz is not None:
        prices = prices.tz_convert(None)
    prices.name = ticker

    st.success(
        f"Loaded **{len(prices):,}** trading days for **{ticker}** "
        f"({prices.index[0].date()} – {prices.index[-1].date()})"
    )

    # Walk-forward
    st.subheader("Running Walk-Forward Analysis…")
    progress_bar = st.progress(0.0)
    status_txt = st.empty()

    def on_progress(done: int, total: int, fold: FoldResult) -> None:
        progress_bar.progress(done / total)
        status_txt.text(
            f"Fold {done}/{total}  |  Best params: RSI {fold.best_rsi_period}, "
            f"OS {fold.best_oversold}, OB {fold.best_overbought}  |  "
            f"IS Sharpe {fold.is_sharpe:.2f}  →  OOS Sharpe {fold.oos_sharpe:.2f}"
        )

    results = run_walk_forward(prices, train_months, test_months, on_progress)
    progress_bar.progress(1.0)

    folds = results["folds"]
    if not folds:
        st.error("Not enough data to build any folds. Try a longer date range or smaller windows.")
        return

    status_txt.text(f"Complete — {len(folds)} folds processed.")

    oos_returns: pd.Series = results["oos_returns"]
    is_returns: pd.Series = results["is_returns"]

    # ── 1. Gantt chart ────────────────────────────────────────────────────────
    st.subheader("Training & Blind Testing Windows")
    st.plotly_chart(build_gantt(folds), use_container_width=True)

    # ── 2. Metric comparison ──────────────────────────────────────────────────
    st.subheader("Performance Comparison")
    oos_m = metrics(oos_returns)
    is_m = metrics(is_returns)

    c1, c2, c3, c4 = st.columns(4)
    for col, key in zip([c1, c2, c3, c4], ["Total Return", "CAGR", "Sharpe", "Max DD"]):
        col.metric(
            label=key,
            value=oos_m[key],
            delta=f"IS: {is_m[key]}",
            delta_color="off",
            help="OOS = Walk-Forward out-of-sample  |  IS = Retail in-sample (fixed params)",
        )

    df_table = pd.DataFrame(
        {"Walk-Forward OOS": oos_m, "Retail In-Sample": is_m}
    ).T
    st.dataframe(df_table, use_container_width=True)

    # ── 3. Equity curves ──────────────────────────────────────────────────────
    st.subheader("Equity Curves")
    st.plotly_chart(build_equity_chart(oos_returns, is_returns, prices), use_container_width=True)

    # ── 4. Fold detail table (collapsed) ──────────────────────────────────────
    with st.expander(f"Fold Details ({len(folds)} folds)"):
        fold_rows = [
            {
                "Fold": f.fold_num,
                "Train Start": f.train_start.date(),
                "Train End": f.train_end.date(),
                "Test Start": f.test_start.date(),
                "Test End": f.test_end.date(),
                "RSI Period": f.best_rsi_period,
                "Oversold": f.best_oversold,
                "Overbought": f.best_overbought,
                "IS Sharpe": round(f.is_sharpe, 2),
                "OOS Sharpe": round(f.oos_sharpe, 2),
                "Trades": f.num_trades,
            }
            for f in folds
        ]
        st.dataframe(pd.DataFrame(fold_rows), use_container_width=True, hide_index=True)


if __name__ == "__main__":
    main()
