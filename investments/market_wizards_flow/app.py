import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go
from datetime import datetime


# =========================================================
# PAGE CONFIG
# =========================================================

st.set_page_config(
    page_title="Market Wizards Flow",
    page_icon="📈",
    layout="wide"
)


# =========================================================
# CONFIG
# =========================================================

BENCHMARK = "SPY"

SECTORS = {
    "Materials": "XLB",
    "Communication Services": "XLC",
    "Energy": "XLE",
    "Financials": "XLF",
    "Industrials": "XLI",
    "Information Technology": "XLK",
    "Consumer Staples": "XLP",
    "Real Estate": "XLRE",
    "Utilities": "XLU",
    "Health Care": "XLV",
    "Consumer Discretionary": "XLY",
}


INDUSTRY_ETFS = {

    "Materials": [
        "XLB",
        "XME",
        "GDX",
        "SIL",
    ],

    "Communication Services": [
        "XLC",
        "IYZ",
        "SOCL",
    ],

    "Energy": [
        "XLE",
        "XOP",
        "OIH",
        "IEO",
    ],

    "Financials": [
        "XLF",
        "KRE",
        "KBE",
        "IAI",
    ],

    "Industrials": [
        "XLI",
        "ITA",
        "XAR",
        "IYT",
        "PAVE",
    ],

    "Information Technology": [
        "XLK",
        "SMH",
        "SOXX",
        "IGV",
        "HACK",
    ],

    "Consumer Staples": [
        "XLP",
        "IYK",
        "PBJ",
    ],

    "Real Estate": [
        "XLRE",
        "VNQ",
        "IYR",
    ],

    "Utilities": [
        "XLU",
        "VPU",
        "FUTY",
    ],

    "Health Care": [
        "XLV",
        "IBB",
        "XBI",
        "IHI",
        "IHF",
    ],

    "Consumer Discretionary": [
        "XLY",
        "XRT",
        "PEJ",
        "ITB",
    ],
}


# =========================================================
# CUSTOM THEMATIC GROUPS
# =========================================================

THEME_GROUPS = {

    "☢️ Nuclear / Power Renaissance": [

        "NUKZ",
        "NLR",
        "URA",
        "URNM",
        "URNJ",
        "GRID",
    ],

    "🚛 Alternative Energy Transport": [

        "BATT",
        "DTG.DE",
        "HAIL",
        "KARS",
        "VOLV-B.ST",
    ],
}


# =========================================================
# DATA DOWNLOAD
# =========================================================

@st.cache_data(ttl=3600, show_spinner=False)
def download_prices(tickers, period="1y"):

    tickers = sorted(set(tickers))

    data = yf.download(

        tickers=tickers,

        period=period,

        interval="1d",

        auto_adjust=True,

        group_by="ticker",

        progress=False,

        threads=True,
    )

    closes = {}
    volumes = {}

    if isinstance(data.columns, pd.MultiIndex):

        level0 = data.columns.get_level_values(0)

        for ticker in tickers:

            if ticker in level0:

                frame = data[ticker]

                if "Close" in frame.columns:

                    closes[ticker] = frame["Close"]

                if "Volume" in frame.columns:

                    volumes[ticker] = frame["Volume"]

    else:

        ticker = tickers[0]

        if "Close" in data.columns:

            closes[ticker] = data["Close"]

        if "Volume" in data.columns:

            volumes[ticker] = data["Volume"]

    close_df = (
        pd.DataFrame(closes)
        .sort_index()
    )

    volume_df = (
        pd.DataFrame(volumes)
        .sort_index()
    )

    return close_df, volume_df


@st.cache_data(ttl=86400, show_spinner=False)
def get_sp500_constituents():

    url = (
        "https://en.wikipedia.org/wiki/"
        "List_of_S%26P_500_companies"
    )

    table = pd.read_html(url)[0]

    table["Symbol"] = (

        table["Symbol"]

        .astype(str)

        .str.replace(
            ".",
            "-",
            regex=False
        )
    )

    return table


# =========================================================
# UTILITY FUNCTIONS
# =========================================================

def safe_return(series, days):

    series = series.dropna()

    if len(series) <= days:

        return np.nan

    return (
        series.iloc[-1]
        / series.iloc[-days - 1]
    ) - 1


def percentile(series):

    return (
        series.rank(
            pct=True
        )
        * 100
    )


def normalized_score(series):

    result = percentile(series)

    if result.isna().all():

        return pd.Series(
            50,
            index=series.index
        )

    return result.fillna(
        result.median()
    )


# =========================================================
# ROTATION / FLOW ENGINE
# =========================================================

def calc_rotation_metrics(
    close_df,
    volume_df,
    tickers,
    benchmark=BENCHMARK
):

    rows = []

    if benchmark not in close_df.columns:

        return pd.DataFrame()

    bench = (
        close_df[benchmark]
        .dropna()
    )

    for ticker in tickers:

        if ticker not in close_df.columns:

            continue

        px = (
            close_df[ticker]
            .dropna()
        )

        if len(px) < 65:

            continue

        # -------------------------------------------------
        # ABSOLUTE RETURNS
        # -------------------------------------------------

        r5 = safe_return(
            px,
            5
        )

        r10 = safe_return(
            px,
            10
        )

        r20 = safe_return(
            px,
            20
        )

        r60 = safe_return(
            px,
            60
        )

        # -------------------------------------------------
        # BENCHMARK RETURNS
        # -------------------------------------------------

        b5 = safe_return(
            bench,
            5
        )

        b10 = safe_return(
            bench,
            10
        )

        b20 = safe_return(
            bench,
            20
        )

        b60 = safe_return(
            bench,
            60
        )

        # -------------------------------------------------
        # RELATIVE STRENGTH
        # -------------------------------------------------

        rs5 = r5 - b5
        rs10 = r10 - b10
        rs20 = r20 - b20
        rs60 = r60 - b60

        # -------------------------------------------------
        # ACCELERATION
        # -------------------------------------------------

        short_acceleration = (

            rs5 -

            (
                rs20 / 4.0
            )
        )

        medium_acceleration = (

            rs10 -

            (
                rs20 / 2.0
            )
        )

        # -------------------------------------------------
        # VOLATILITY
        # -------------------------------------------------

        daily_ret = (
            px.pct_change()
            .dropna()
        )

        vol20 = (

            daily_ret
            .tail(20)
            .std()

            * np.sqrt(252)

            if len(daily_ret) >= 20

            else np.nan
        )

        # -------------------------------------------------
        # DRAWDOWN
        # -------------------------------------------------

        high60 = (
            px.tail(60)
            .max()
        )

        drawdown60 = (

            (
                px.iloc[-1]
                / high60
            ) - 1

            if high60 > 0

            else np.nan
        )

        # -------------------------------------------------
        # MOVING AVERAGES
        # -------------------------------------------------

        ma10 = (
            px.tail(10)
            .mean()
        )

        ma20 = (
            px.tail(20)
            .mean()
        )

        ma50 = (
            px.tail(50)
            .mean()
        )

        current_price = (
            px.iloc[-1]
        )

        trend_quality = 0

        if current_price > ma10:
            trend_quality += 1

        if current_price > ma20:
            trend_quality += 1

        if current_price > ma50:
            trend_quality += 1

        if ma10 > ma20:
            trend_quality += 1

        if ma20 > ma50:
            trend_quality += 1

        # -------------------------------------------------
        # SHORT-TERM PRICE SLOPE
        # -------------------------------------------------

        last10 = (
            px.tail(10)
        )

        if len(last10) >= 10:

            x = np.arange(
                len(last10)
            )

            short_slope = (
                np.polyfit(
                    x,
                    last10.values,
                    1
                )[0]
            )

            short_slope_pct = (

                short_slope

                / last10.mean()
            )

        else:

            short_slope_pct = 0

        # -------------------------------------------------
        # VOLUME
        # -------------------------------------------------

        volume_ratio = 1.0
        short_volume_ratio = 1.0

        if ticker in volume_df.columns:

            v = (
                volume_df[ticker]
                .dropna()
            )

            if (

                len(v) >= 40

                and

                v.tail(40).mean() > 0
            ):

                volume_ratio = (

                    v.tail(10).mean()

                    /

                    v.tail(40).mean()
                )

            if (

                len(v) >= 20

                and

                v.tail(20).mean() > 0
            ):

                short_volume_ratio = (

                    v.tail(5).mean()

                    /

                    v.tail(20).mean()
                )

        # -------------------------------------------------
        # STORE RAW METRICS
        # -------------------------------------------------

        rows.append({

            "Ticker": ticker,

            "Return 1W": r5,
            "Return 2W": r10,
            "Return 4W": r20,
            "Return 12W": r60,

            "RS 1W": rs5,
            "RS 2W": rs10,
            "RS 4W": rs20,
            "RS 12W": rs60,

            "Short Acceleration":
                short_acceleration,

            "Medium Acceleration":
                medium_acceleration,

            "Volatility":
                vol20,

            "Drawdown":
                drawdown60,

            "Trend Quality":
                trend_quality,

            "Volume Ratio":
                volume_ratio,

            "Short Volume Ratio":
                short_volume_ratio,

            "Short Slope":
                short_slope_pct,
        })

    df = pd.DataFrame(
        rows
    )

    if df.empty:

        return df

    df = df.set_index(
        "Ticker"
    )

    # =====================================================
    # CROSS-SECTIONAL SCORES
    # =====================================================

    df["RS1 Score"] = normalized_score(
        df["RS 1W"]
    )

    df["RS2 Score"] = normalized_score(
        df["RS 2W"]
    )

    df["RS4 Score"] = normalized_score(
        df["RS 4W"]
    )

    df["RS12 Score"] = normalized_score(
        df["RS 12W"]
    )

    df["Short Acceleration Score"] = normalized_score(
        df["Short Acceleration"]
    )

    df["Medium Acceleration Score"] = normalized_score(
        df["Medium Acceleration"]
    )

    df["Volume Score"] = normalized_score(
        df["Volume Ratio"]
    )

    df["Short Volume Score"] = normalized_score(
        df["Short Volume Ratio"]
    )

    df["Trend Quality Score"] = normalized_score(
        df["Trend Quality"]
    )

    df["Slope Score"] = normalized_score(
        df["Short Slope"]
    )

    # =====================================================
    # RISK SCORE
    # =====================================================

    low_vol_score = (

        100

        - normalized_score(
            df["Volatility"]
        )
    )

    drawdown_score = normalized_score(
        df["Drawdown"]
    )

    df["Risk Score"] = (

        0.55
        * low_vol_score

        +

        0.45
        * drawdown_score
    )

    # =====================================================
    # TREND SCORE
    # =====================================================

    df["Trend Score"] = (

        0.30
        * df["RS4 Score"]

        +

        0.30
        * df["RS12 Score"]

        +

        0.20
        * df["Trend Quality Score"]

        +

        0.10
        * df["Volume Score"]

        +

        0.10
        * df["Risk Score"]
    )

    # =====================================================
    # TURNAROUND SCORE
    # =====================================================

    return1_score = normalized_score(
        df["Return 1W"]
    )

    df["Turnaround Score"] = (

        0.30
        * df["RS1 Score"]

        +

        0.25
        * df["Short Acceleration Score"]

        +

        0.20
        * return1_score

        +

        0.15
        * df["Slope Score"]

        +

        0.10
        * df["Short Volume Score"]
    )

    # =====================================================
    # FLOW SCORE
    # =====================================================

    df["Flow Score"] = (

        0.25
        * df["RS4 Score"]

        +

        0.20
        * df["Medium Acceleration Score"]

        +

        0.20
        * df["RS12 Score"]

        +

        0.15
        * df["Trend Quality Score"]

        +

        0.10
        * df["Volume Score"]

        +

        0.10
        * df["RS1 Score"]
    )

    # =====================================================
    # OPPORTUNITY SCORE
    # =====================================================

# =====================================================
# OPPORTUNITY SCORE
#
# Goal:
# Find sectors/instruments that have been weak
# but are beginning to turn upward.
#
# High turnaround + high short acceleration +
# weak prior 12-week relative performance
# gets rewarded.
# =====================================================

    df["Weakness Bonus"] = (
        100 - df["RS12 Score"]
    )

    df["Opportunity Score"] = (

        0.45
        * df["Turnaround Score"]

        +

        0.25
        * df["Short Acceleration Score"]

        +

        0.15
        * df["Weakness Bonus"]

        +

        0.10
        * df["RS1 Score"]

        +

        0.05
        * df["Risk Score"]
    )

    return df


# =========================================================
# REGIME CLASSIFICATION
# =========================================================

def regime(row):

    rs1 = row[
        "RS 1W"
    ]

    rs4 = row[
        "RS 4W"
    ]

    rs12 = row[
        "RS 12W"
    ]

    short_accel = row[
        "Short Acceleration Score"
    ]

    turnaround = row[
        "Turnaround Score"
    ]

    # -----------------------------------------------------
    # POSSIBLE TURNAROUND
    # -----------------------------------------------------

    if (
        rs12 < 0
        and rs4 <= 0
        and rs1 > 0
        and short_accel >= 60
        and turnaround >= 65
    ):

        return (
            "🟣 Possible Turnaround"
        )

    # -----------------------------------------------------
    # EARLY ACCUMULATION
    # -----------------------------------------------------

    if (
        rs4 > 0
        and rs12 <= 0
        and short_accel >= 55
    ):

        return (
            "🟢 Early Accumulation"
        )

    # -----------------------------------------------------
    # LEADING
    # -----------------------------------------------------

    if (
        rs4 > 0
        and rs12 > 0
        and short_accel >= 50
    ):

        return (
            "🔵 Leading"
        )

    # -----------------------------------------------------
    # MATURING
    # -----------------------------------------------------

    if (
        rs4 > 0
        and rs12 > 0
        and short_accel < 50
    ):

        return (
            "🟡 Maturing"
        )

    # -----------------------------------------------------
    # DISTRIBUTION
    # -----------------------------------------------------

    if (
        rs4 <= 0
        and rs12 > 0
    ):

        return (
            "🟠 Distribution"
        )

    return (
        "🔴 Lagging"
    )


# =========================================================
# DIRECTION ARROW
# =========================================================

def direction_arrow(series):

    s = (
        series
        .dropna()
    )

    if len(s) < 10:

        return "→"

    recent = (
        s.iloc[-1]
    )

    prior = (
        s.iloc[-6]
    )

    change = (
        recent
        - prior
    )

    if change > 2:
        return "↗↗"

    if change > 0:
        return "↗"

    if change < -2:
        return "↘↘"

    if change < 0:
        return "↘"

    return "→"


# =========================================================
# RELATIVE FLOW LINE
# =========================================================

def relative_line(
    close_df,
    ticker,
    benchmark=BENCHMARK,
    days=60
):

    if (

        ticker not in close_df.columns

        or

        benchmark not in close_df.columns
    ):

        return pd.Series(
            dtype=float
        )

    pair = (

        close_df[
            [
                ticker,
                benchmark
            ]
        ]

        .dropna()

        .tail(days)
    )

    if pair.empty:

        return pd.Series(
            dtype=float
        )

    relative = (

        pair[ticker]

        /

        pair[benchmark]
    )

    normalized = (

        relative

        /

        relative.iloc[0]

        - 1
    ) * 100

    return normalized


# =========================================================
# MINI CHART
# =========================================================

def mini_chart(
    series,
    title,
    regime_text
):

    fig = go.Figure()

    if "Turnaround" in regime_text:

        color = "#9b59b6"

    elif "Leading" in regime_text:

        color = "#3498db"

    elif "Accumulation" in regime_text:

        color = "#20c997"

    elif "Maturing" in regime_text:

        color = "#f1c40f"

    elif "Distribution" in regime_text:

        color = "#e67e22"

    else:

        color = "#ff6b6b"

    fig.add_trace(

        go.Scatter(

            x=series.index,

            y=series.values,

            mode="lines",

            line=dict(
                color=color,
                width=3
            ),

            hovertemplate=(
                "%{x|%d %b}<br>"
                "%{y:.2f}% relative to SPY"
                "<extra></extra>"
            ),
        )
    )

    fig.update_layout(

        title=dict(
            text=title,
            font=dict(
                size=14
            )
        ),

        height=190,

        margin=dict(
            l=5,
            r=5,
            t=30,
            b=5
        ),

        xaxis=dict(
            visible=False
        ),

        yaxis=dict(
            visible=False
        ),

        showlegend=False,

        paper_bgcolor=(
            "rgba(0,0,0,0)"
        ),

        plot_bgcolor=(
            "rgba(0,0,0,0)"
        ),
    )

    return fig


# =========================================================
# FULL PRICE CHART
# =========================================================

def full_price_chart(
    close_df,
    ticker,
    title=None,
    days=120
):

    if ticker not in close_df.columns:

        return None

    px = (

        close_df[ticker]

        .dropna()

        .tail(days)
    )

    if px.empty:

        return None

    fig = go.Figure()

    fig.add_trace(

        go.Scatter(

            x=px.index,

            y=px.values,

            mode="lines",

            line=dict(
                color="#4da3ff",
                width=2.5
            ),

            name=ticker
        )
    )

    fig.update_layout(

        title=(
            title
            if title
            else ticker
        ),

        height=360,

        margin=dict(
            l=10,
            r=10,
            t=40,
            b=10
        ),

        yaxis_title=(
            "Adjusted price"
        ),

        showlegend=False,

        paper_bgcolor=(
            "rgba(0,0,0,0)"
        ),

        plot_bgcolor=(
            "rgba(0,0,0,0)"
        ),
    )

    return fig


# =========================================================
# STOCK / ETF / THEME SCANNER
# =========================================================

def score_instruments(
    close_df,
    volume_df,
    tickers
):

    metrics = calc_rotation_metrics(

        close_df,

        volume_df,

        tickers=tickers,

        benchmark=BENCHMARK
    )

    if metrics.empty:

        return metrics

    extension_penalties = []

    for ticker in metrics.index:

        px = (

            close_df[ticker]

            .dropna()
        )

        if len(px) < 20:

            extension_penalties.append(
                0
            )

            continue

        ma20 = (

            px.tail(20)

            .mean()
        )

        extension = (

            (
                px.iloc[-1]
                / ma20
            )

            - 1

        ) * 100

        if extension > 12:

            penalty = 20

        elif extension > 8:

            penalty = 10

        else:

            penalty = 0

        extension_penalties.append(
            penalty
        )

    metrics[
        "Extension Penalty"
    ] = extension_penalties

    metrics[
        "Setup Score"
    ] = (

        0.60
        * metrics["Turnaround Score"]

        +

        0.25
        * metrics["Short Acceleration Score"]

        +

        0.15
        * metrics["Weakness Bonus"]

        -

        metrics["Extension Penalty"]

    ).clip(
        0,
        100
    )

    def setup_label(row):

        if row[
            "Extension Penalty"
        ] >= 20:

            return (
                "⚠️ Too Extended"
            )

        if (
            row["Setup Score"] >= 70
            and row["RS 4W"] > 0
            and row[
                "Short Acceleration Score"
            ] >= 55
        ):

            return (
                "🟢 Strong Setup"
            )

        if (
            row[
                "Turnaround Score"
            ] >= 70

            and

            row[
                "RS 12W"
            ] < 0

            and

            row[
                "RS 1W"
            ] > 0
        ):

            return (
                "🟣 Turnaround Watch"
            )

        if row[
            "Setup Score"
        ] >= 55:

            return (
                "👀 Watch"
            )

        return "—"

    metrics[
        "Status"
    ] = metrics.apply(
        setup_label,
        axis=1
    )

    metrics[
        "Regime"
    ] = metrics.apply(
        regime,
        axis=1
    )

    return (

        metrics

        .sort_values(
            "Setup Score",
            ascending=False
        )
    )


# =========================================================
# HEADER
# =========================================================

st.title(
    "Market Wizards — Sector Flow"
)

st.caption(
    "Trend + turnaround detection • "
    "Risk first • Asymmetric setups • "
    "Relative strength versus SPY"
)


# =========================================================
# SIDEBAR
# =========================================================

with st.sidebar:

    st.header(
        "Controls"
    )

    refresh = st.button(
        "🔄 Refresh market data"
    )

    if refresh:

        st.cache_data.clear()

        st.rerun()

    st.divider()

    st.caption(
        "Trend Score = how strong "
        "a sector or instrument "
        "already is."
    )

    st.caption(
        "Turnaround Score = how rapidly "
        "a weak sector or instrument "
        "is beginning to improve."
    )

    st.caption(
        "Flow is inferred from price, "
        "relative strength, acceleration, "
        "trend and volume. "
        "It is not literal fund-flow data."
    )

    max_candidates = st.slider(

        "Candidates to show",

        min_value=3,

        max_value=15,

        value=8
    )


# =========================================================
# DOWNLOAD SECTOR DATA
# =========================================================

all_sector_tickers = (
    list(
        SECTORS.values()
    )
)

all_base_tickers = (

    [BENCHMARK]

    +

    all_sector_tickers
)

with st.spinner(
    "Downloading market data..."
):

    closes, volumes = (
        download_prices(
            all_base_tickers,
            period="1y"
        )
    )


sector_metrics = (
    calc_rotation_metrics(
        closes,
        volumes,
        all_sector_tickers
    )
)


if sector_metrics.empty:

    st.error(
        "Market data could not be loaded."
    )

    st.stop()


ticker_to_sector = {

    ticker: name

    for name, ticker
    in SECTORS.items()
}


sector_metrics[
    "Sector"
] = [

    ticker_to_sector.get(
        t,
        t
    )

    for t in sector_metrics.index
]


sector_metrics[
    "Regime"
] = (

    sector_metrics.apply(
        regime,
        axis=1
    )
)


sector_metrics[
    "Rank"
] = (

    sector_metrics[
        "Turnaround Score"
    ]

    .rank(
        ascending=False,
        method="min"
    )

    .astype(int)
)


# =========================================================
# TABS
# =========================================================

tab1, tab2, tab3, tab4, tab5 = st.tabs(

    [
        "🌊 Sector Flow",
        "🔎 Stock Finder",
        "📦 Industry ETFs",
        "🌐 Theme Finder",
        "🛡️ Risk Calculator",
    ]
)


# =========================================================
# TAB 1 — SECTOR FLOW
# =========================================================

with tab1:

    st.subheader(
        "12-week sector rotation"
    )

    st.caption(
        "The line shows each sector ETF "
        "relative to SPY. Rising means "
        "outperformance; falling means "
        "underperformance."
    )

    ordered = (

        sector_metrics

        .sort_values(
            [
                "Turnaround Score",
                "Short Acceleration Score"
            ],
            ascending=[
                False,
                False
            ]
        )

        .index

        .tolist()
    )

    for start in range(
        0,
        len(ordered),
        3
    ):

        cols = st.columns(3)

        for col, ticker in zip(

            cols,

            ordered[
                start:start + 3
            ]
        ):

            with col:

                row = (
                    sector_metrics
                    .loc[ticker]
                )

                rel = relative_line(

                    closes,

                    ticker,

                    BENCHMARK,

                    days=60
                )

                arrow = (

                    direction_arrow(
                        rel
                    )

                    if not rel.empty

                    else "→"
                )

                sector_name = (
                    ticker_to_sector[
                        ticker
                    ]
                )

                st.markdown(
                    f"### {arrow} "
                    f"{sector_name}"
                )

                st.markdown(
                    f"**{ticker}**"
                )

                st.caption(
                    row[
                        "Regime"
                    ]
                )

                return1 = (
                    row[
                        "Return 1W"
                    ]
                    * 100
                )

                return12 = (
                    row[
                        "Return 12W"
                    ]
                    * 100
                )

                c1, c2 = (
                    st.columns(2)
                )

                with c1:

                    st.metric(
                        "1 week",
                        f"{return1:+.1f}%"
                    )

                with c2:

                    st.metric(
                        "12 weeks",
                        f"{return12:+.1f}%"
                    )

                c3, c4 = (
                    st.columns(2)
                )

                with c3:

                    st.metric(
                        "Trend",
                        (
                            f"{row['Trend Score']:.0f}"
                            "/100"
                        )
                    )

                with c4:

                    st.metric(
                        "Turnaround",
                        (
                            f"{row['Turnaround Score']:.0f}"
                            "/100"
                        )
                    )

                if not rel.empty:

                    st.plotly_chart(

                        mini_chart(
                            rel,
                            ticker,
                            row["Regime"]
                        ),

                        use_container_width=True,

                        config={
                            "displayModeBar": False
                        }
                    )

    st.divider()

    st.subheader(
        "Current sector ranking"
    )

    display = (
        sector_metrics
        .copy()
    )

    display["1W %"] = (

        display[
            "Return 1W"
        ]

        * 100

    ).round(1)

    display["12W %"] = (

        display[
            "Return 12W"
        ]

        * 100

    ).round(1)

    display["Trend"] = (

        display[
            "Trend Score"
        ]

        .round(0)
    )

    display["Turnaround"] = (

        display[
            "Turnaround Score"
        ]

        .round(0)
    )

    display["Flow"] = (

        display[
            "Flow Score"
        ]

        .round(0)
    )

    display["Risk"] = (

        display[
            "Risk Score"
        ]

        .round(0)
    )

    display["Opportunity"] = (

        display[
            "Opportunity Score"
        ]

        .round(0)
    )

    display = (

        display[

            [
                "Rank",
                "Sector",
                "Regime",
                "1W %",
                "12W %",
                "Trend",
                "Turnaround",
                "Flow",
                "Risk",
                "Opportunity",
            ]
        ]

        .sort_values(
            "Rank"
        )
    )

    st.dataframe(

        display,

        use_container_width=True,

        hide_index=True
    )


# =========================================================
# TAB 2 — STOCK FINDER
# =========================================================

with tab2:

    st.subheader(
        "Find stocks inside a sector"
    )

    selected_sector = (
        st.selectbox(

            "Sector",

            list(
                SECTORS.keys()
            ),

            index=4,

            key="stock_sector"
        )
    )

    try:

        sp500 = (
            get_sp500_constituents()
        )

        subset = sp500[

            sp500[
                "GICS Sector"
            ]

            == selected_sector

        ].copy()

        tickers = (

            subset[
                "Symbol"
            ]

            .tolist()
        )

        if not tickers:

            st.warning(
                "No constituents found "
                "for this sector."
            )

        else:

            st.caption(
                f"Scanning {len(tickers)} "
                f"current S&P 500 constituents "
                f"in {selected_sector}."
            )

            if st.button(

                f"Scan {selected_sector}",

                type="primary"
            ):

                with st.spinner(
                    "Scanning stocks..."
                ):

                    stock_closes, stock_volumes = (

                        download_prices(

                            [BENCHMARK]
                            + tickers,

                            period="1y"
                        )
                    )

                    valid_tickers = [

                        t

                        for t in tickers

                        if t
                        in stock_closes.columns
                    ]

                    scores = (

                        score_instruments(

                            stock_closes,

                            stock_volumes,

                            valid_tickers
                        )
                    )

                if scores.empty:

                    st.warning(
                        "No usable stock "
                        "data returned."
                    )

                else:

                    names = (

                        subset[

                            [
                                "Symbol",
                                "Security"
                            ]
                        ]

                        .set_index(
                            "Symbol"
                        )[
                            "Security"
                        ]

                        .to_dict()
                    )

                    scores[
                        "Company"
                    ] = [

                        names.get(
                            t,
                            ""
                        )

                        for t
                        in scores.index
                    ]

                    result = (

                        scores

                        .head(
                            max_candidates
                        )

                        .copy()
                    )

                    result[
                        "Ticker"
                    ] = result.index

                    result[
                        "Setup"
                    ] = (

                        result[
                            "Setup Score"
                        ]

                        .round(0)
                    )

                    result[
                        "Trend"
                    ] = (

                        result[
                            "Trend Score"
                        ]

                        .round(0)
                    )

                    result[
                        "Turnaround"
                    ] = (

                        result[
                            "Turnaround Score"
                        ]

                        .round(0)
                    )

                    result[
                        "1W %"
                    ] = (

                        result[
                            "Return 1W"
                        ]

                        * 100

                    ).round(1)

                    result[
                        "4W RS %"
                    ] = (

                        result[
                            "RS 4W"
                        ]

                        * 100

                    ).round(1)

                    st.dataframe(

                        result[

                            [
                                "Ticker",
                                "Company",
                                "Status",
                                "Regime",
                                "Setup",
                                "Trend",
                                "Turnaround",
                                "1W %",
                                "4W RS %",
                            ]
                        ],

                        use_container_width=True,

                        hide_index=True
                    )

                    top_ticker = (
                        result.index[0]
                    )

                    st.subheader(
                        f"Top candidate: "
                        f"{top_ticker}"
                    )

                    fig = (
                        full_price_chart(

                            stock_closes,

                            top_ticker,

                            title=top_ticker
                        )
                    )

                    if fig is not None:

                        st.plotly_chart(

                            fig,

                            use_container_width=True
                        )

    except Exception as exc:

        st.error(
            "Could not load the current "
            "S&P 500 constituent list. "
            f"Error: {exc}"
        )


# =========================================================
# TAB 3 — INDUSTRY ETF FINDER
# =========================================================

with tab3:

    st.subheader(
        "Industry ETF finder"
    )

    etf_sector = (
        st.selectbox(

            "Sector",

            list(
                SECTORS.keys()
            ),

            key="etf_sector"
        )
    )

    etfs = (
        INDUSTRY_ETFS[
            etf_sector
        ]
    )

    st.markdown(
        "**ETFs:** "
        + ", ".join(etfs)
    )

    with st.spinner(
        "Downloading ETF data..."
    ):

        etf_closes, etf_volumes = (

            download_prices(

                [BENCHMARK]
                + etfs,

                period="1y"
            )
        )

    valid_etfs = [

        ticker

        for ticker in etfs

        if ticker
        in etf_closes.columns
    ]

    missing_etfs = [

        ticker

        for ticker in etfs

        if ticker
        not in etf_closes.columns
    ]

    if missing_etfs:

        st.warning(
            "No data returned for: "
            + ", ".join(
                missing_etfs
            )
        )

    if valid_etfs:

        etf_scores = (

            score_instruments(

                etf_closes,

                etf_volumes,

                valid_etfs
            )
        )

        if not etf_scores.empty:

            etf_display = (
                etf_scores
                .copy()
            )

            etf_display[
                "Ticker"
            ] = etf_display.index

            etf_display[
                "Setup"
            ] = (

                etf_display[
                    "Setup Score"
                ]

                .round(0)
            )

            etf_display[
                "Trend"
            ] = (

                etf_display[
                    "Trend Score"
                ]

                .round(0)
            )

            etf_display[
                "Turnaround"
            ] = (

                etf_display[
                    "Turnaround Score"
                ]

                .round(0)
            )

            etf_display[
                "1W %"
            ] = (

                etf_display[
                    "Return 1W"
                ]

                * 100

            ).round(1)

            etf_display[
                "4W RS %"
            ] = (

                etf_display[
                    "RS 4W"
                ]

                * 100

            ).round(1)

            st.dataframe(

                etf_display[

                    [
                        "Ticker",
                        "Status",
                        "Regime",
                        "Setup",
                        "Trend",
                        "Turnaround",
                        "1W %",
                        "4W RS %",
                    ]
                ],

                use_container_width=True,

                hide_index=True
            )

            selected_etf = (
                st.selectbox(

                    "Chart",

                    etf_display.index.tolist(),

                    key="etf_chart_selector"
                )
            )

            fig = full_price_chart(

                etf_closes,

                selected_etf,

                title=selected_etf
            )

            if fig is not None:

                st.plotly_chart(

                    fig,

                    use_container_width=True
                )


# =========================================================
# TAB 4 — THEME FINDER
# =========================================================

with tab4:

    st.subheader(
        "Thematic opportunity finder"
    )

    st.caption(
        "Compare stocks and ETFs inside "
        "a specific investment theme."
    )

    selected_theme = st.radio(
        "Theme",
        [
            "☢️ Nuclear / Power Renaissance",
            "🚛 Alternative Energy Transport",
        ],
        horizontal=True,
        key="theme_selector_radio"
    )

    theme_tickers = (
        THEME_GROUPS[
            selected_theme
        ]
    )

    st.markdown(
        "**Securities:** "
        + ", ".join(
            theme_tickers
        )
    )

    with st.spinner(
        f"Scanning "
        f"{selected_theme}..."
    ):

        theme_closes, theme_volumes = (

            download_prices(

                [BENCHMARK]
                + theme_tickers,

                period="1y"
            )
        )

    valid_theme_tickers = [

        ticker

        for ticker
        in theme_tickers

        if ticker
        in theme_closes.columns
    ]

    missing_theme_tickers = [

        ticker

        for ticker
        in theme_tickers

        if ticker
        not in theme_closes.columns
    ]

    if missing_theme_tickers:

        st.warning(
            "No data returned for: "
            + ", ".join(
                missing_theme_tickers
            )
        )

    if not valid_theme_tickers:

        st.error(
            "No usable market data "
            "was returned for this theme."
        )

    else:

        theme_scores = (

            score_instruments(

                theme_closes,

                theme_volumes,

                valid_theme_tickers
            )
        )

        if theme_scores.empty:

            st.warning(
                "Not enough historical data "
                "to calculate theme scores."
            )

        else:

            theme_display = (
                theme_scores
                .copy()
            )

            theme_display[
                "Ticker"
            ] = (
                theme_display.index
            )

            theme_display[
                "Setup"
            ] = (

                theme_display[
                    "Setup Score"
                ]

                .round(0)
            )

            theme_display[
                "Trend"
            ] = (

                theme_display[
                    "Trend Score"
                ]

                .round(0)
            )

            theme_display[
                "Turnaround"
            ] = (

                theme_display[
                    "Turnaround Score"
                ]

                .round(0)
            )

            theme_display[
                "Flow"
            ] = (

                theme_display[
                    "Flow Score"
                ]

                .round(0)
            )

            theme_display[
                "Risk"
            ] = (

                theme_display[
                    "Risk Score"
                ]

                .round(0)
            )

            theme_display[
                "1W %"
            ] = (

                theme_display[
                    "Return 1W"
                ]

                * 100

            ).round(1)

            theme_display[
                "4W %"
            ] = (

                theme_display[
                    "Return 4W"
                ]

                * 100

            ).round(1)

            theme_display[
                "12W %"
            ] = (

                theme_display[
                    "Return 12W"
                ]

                * 100

            ).round(1)

            theme_display[
                "1W RS %"
            ] = (

                theme_display[
                    "RS 1W"
                ]

                * 100

            ).round(1)

            theme_display[
                "4W RS %"
            ] = (

                theme_display[
                    "RS 4W"
                ]

                * 100

            ).round(1)

            st.dataframe(

                theme_display[

                    [
                        "Ticker",
                        "Status",
                        "Regime",
                        "Setup",
                        "Trend",
                        "Turnaround",
                        "Flow",
                        "Risk",
                        "1W %",
                        "4W %",
                        "12W %",
                        "1W RS %",
                        "4W RS %",
                    ]
                ],

                use_container_width=True,

                hide_index=True
            )

            st.divider()

            st.subheader(
                "Theme charts"
            )

            ordered_theme = (

                theme_scores

                .sort_values(
                    [
                        "Turnaround Score",
                        "Short Acceleration Score"
                    ],
                    ascending=[
                        False,
                        False
                    ]
                )

                .index

                .tolist()
            )

            for start in range(
                0,
                len(ordered_theme),
                3
            ):

                cols = (
                    st.columns(3)
                )

                for col, ticker in zip(

                    cols,

                    ordered_theme[
                        start:start + 3
                    ]
                ):

                    with col:

                        row = (
                            theme_scores
                            .loc[ticker]
                        )

                        rel = relative_line(

                            theme_closes,

                            ticker,

                            BENCHMARK,

                            days=60
                        )

                        arrow = (

                            direction_arrow(
                                rel
                            )

                            if not rel.empty

                            else "→"
                        )

                        st.markdown(
                            f"### {arrow} {ticker}"
                        )

                        st.caption(
                            row["Regime"]
                        )

                        c1, c2 = (
                            st.columns(2)
                        )

                        with c1:

                            st.metric(
                                "1 week",
                                (
                                    f"{row['Return 1W'] * 100:+.1f}%"
                                )
                            )

                        with c2:

                            st.metric(
                                "12 weeks",
                                (
                                    f"{row['Return 12W'] * 100:+.1f}%"
                                )
                            )

                        c3, c4 = (
                            st.columns(2)
                        )

                        with c3:

                            st.metric(
                                "Trend",
                                (
                                    f"{row['Trend Score']:.0f}"
                                    "/100"
                                )
                            )

                        with c4:

                            st.metric(
                                "Turnaround",
                                (
                                    f"{row['Turnaround Score']:.0f}"
                                    "/100"
                                )
                            )

                        if not rel.empty:

                            st.plotly_chart(

                                mini_chart(
                                    rel,
                                    ticker,
                                    row["Regime"]
                                ),

                                use_container_width=True,

                                config={
                                    "displayModeBar": False
                                }
                            )

            st.divider()

            selected_theme_ticker = (
                st.selectbox(

                    "Detailed chart",

                    ordered_theme,

                    key="theme_chart_selector"
                )
            )

            fig = full_price_chart(

                theme_closes,

                selected_theme_ticker,

                title=(
                    f"{selected_theme_ticker} — "
                    f"{selected_theme}"
                )
            )

            if fig is not None:

                st.plotly_chart(

                    fig,

                    use_container_width=True
                )


# =========================================================
# TAB 5 — RISK CALCULATOR
# =========================================================

with tab5:

    st.subheader(
        "Position sizing"
    )

    st.caption(
        "Position size is determined "
        "from defined risk, not conviction."
    )

    col1, col2 = (
        st.columns(2)
    )

    with col1:

        portfolio = st.number_input(

            "Portfolio value",

            min_value=1000.0,

            value=100000.0,

            step=1000.0
        )

        risk_pct = st.number_input(

            "Maximum risk per trade (%)",

            min_value=0.1,

            max_value=5.0,

            value=0.75,

            step=0.05
        )

    with col2:

        entry = st.number_input(

            "Entry price",

            min_value=0.01,

            value=100.0,

            step=1.0
        )

        invalidation = st.number_input(

            "Invalidation / stop",

            min_value=0.01,

            value=96.0,

            step=1.0
        )

        target = st.number_input(

            "Initial target",

            min_value=0.01,

            value=115.0,

            step=1.0
        )

    risk_per_share = (
        entry
        - invalidation
    )

    reward_per_share = (
        target
        - entry
    )

    max_dollar_risk = (

        portfolio

        *

        (
            risk_pct
            / 100
        )
    )

    if risk_per_share > 0:

        shares = int(

            max_dollar_risk

            /

            risk_per_share
        )

        position_value = (

            shares

            *

            entry
        )

        rr = (

            reward_per_share

            /

            risk_per_share

            if reward_per_share > 0

            else 0
        )

        c1, c2, c3, c4 = (
            st.columns(4)
        )

        c1.metric(
            "Max $ risk",
            f"${max_dollar_risk:,.0f}"
        )

        c2.metric(
            "Shares",
            f"{shares:,}"
        )

        c3.metric(
            "Position value",
            f"${position_value:,.0f}"
        )

        c4.metric(
            "Reward : Risk",
            f"{rr:.1f} : 1"
        )

        if rr >= 3:

            st.success(
                "✓ Passes the initial "
                "3:1 asymmetry filter."
            )

        else:

            st.warning(
                "Reward/risk is below "
                "the initial 3:1 filter."
            )

    else:

        st.warning(
            "For a long trade, "
            "the invalidation level "
            "must be below the entry."
        )


# =========================================================
# FOOTER
# =========================================================

st.divider()

st.caption(

    f"Last calculation: "
    f"{datetime.now().strftime('%Y-%m-%d %H:%M')} local time. "

    "Turnaround signals identify changing behaviour, "
    "not confirmed trend reversals. "
    "Research tool only."
)