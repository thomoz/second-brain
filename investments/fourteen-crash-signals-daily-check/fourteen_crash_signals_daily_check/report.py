"""Combined 14-row markdown report -- all 14 markers render real data (Marker 3 is a
permanent verdict="unknown" maintained flag by design, not a fetch failure -- see
seller_financing.py). Rows are sorted 1-14 by marker number for readability."""

from __future__ import annotations

from datetime import date
from typing import Any

from . import config


def render_signals_report(
    watchlist: list[dict[str, Any]],
    credit_spread_result: Any,
    margin_debt_result: Any,
    insider_trend_results: list[Any],
    market_cap_result: Any,
    lease_commitment_results: list[Any],
    capex_cashflow_results: list[Any],
    super_bowl_result: Any,
    credit_spread_issuer_results: list[Any],
    debt_issuance_results: list[Any],
    seller_financing_result: Any,
    ipo_issuance_result: Any,
    retail_leverage_result: Any,
    regulator_alarm_results: list[Any],
    funding_stress_result: Any,
) -> str:
    lines = [
        "# 14 Crash Signals — Daily Check",
        "",
        "What this is: 14 historical market-crash warning markers, checked daily "
        "so an early warning doesn't slip by unnoticed.",
        "",
        "Auto-generated daily -- overwritten every run. Advisor notes only; no trade "
        "action is ever suggested here (see SOUL.md). Per-marker source: "
        "investments/my-trader/14-signals-crash-warning-handoff.md.",
        "",
        "## Hot Company Watchlist (shared input for markers 1-4, 8, 10-13)",
        "Dynamically recomputed every run from currently-rising GICS sectors + S&P 500 "
        "mega-cap constituents -- never hardcoded to a fixed ticker list.",
        "",
    ]
    if watchlist:
        lines += ["| Rank | Ticker | Sector | Market Cap |", "|------|--------|--------|------------|"]
        for row in watchlist:
            lines.append(f"| {row['rank']} | {row['ticker']} | {row['sector_label']} | ${row['market_cap'] / 1e9:.0f}B |")
    else:
        lines.append("No hot-watchlist companies resolved this run (no rising sectors, or data unavailable).")

    credit_spread_detail = credit_spread_result.detail
    if credit_spread_result.verdict == "ok" and credit_spread_result.data.get("watch"):
        credit_spread_detail += " (WATCH)"

    marker_rows: list[tuple[int, str]] = [
        (5, f"| 5 | Margin debt YoY growth | {margin_debt_result.verdict} | {margin_debt_result.detail} |"),
        (9, f"| 9 | The Super Bowl signal | {super_bowl_result.verdict} | {super_bowl_result.detail} |"),
        (10, f"| 10 | Most-valuable-company milestone | {market_cap_result.verdict} | {market_cap_result.detail} |"),
        (14, f"| 14 | High-yield credit spread streak | {credit_spread_result.verdict} | {credit_spread_detail} |"),
    ]
    if insider_trend_results:
        for r in insider_trend_results:
            marker_rows.append((8, f"| 8 | Insider selling ({r.data.get('ticker', '?')}) | {r.verdict} | {r.detail} |"))
    else:
        marker_rows.append((8, "| 8 | Insider selling (aggregate trend) | ok | No hot-watchlist tickers with insider activity this run. |"))
    if lease_commitment_results:
        for r in lease_commitment_results:
            marker_rows.append((2, f"| 2 | Debt moves off balance sheet ({r.data.get('ticker', '?')}) | {r.verdict} | {r.detail} |"))
    else:
        marker_rows.append((2, "| 2 | Debt moves off balance sheet | ok | No hot-watchlist tickers with a resolvable lease-commitment reading this run. |"))
    if capex_cashflow_results:
        for r in capex_cashflow_results:
            marker_rows.append((4, f"| 4 | Capex outruns cash flow ({r.data.get('ticker', '?')}) | {r.verdict} | {r.detail} |"))
    else:
        marker_rows.append((4, "| 4 | Capex outruns cash flow | ok | No hot-watchlist tickers with a resolvable cash-flow statement this run. |"))
    if credit_spread_issuer_results:
        for r in credit_spread_issuer_results:
            marker_rows.append((12, f"| 12 | Credit turns in the hot sector while broad market stays calm ({r.data.get('ticker', '?')}) | {r.verdict} | {r.detail} |"))
    else:
        marker_rows.append((12, "| 12 | Credit turns in the hot sector while broad market stays calm | ok | No hot-watchlist tickers with a resolvable bond CUSIP this run. |"))
    if debt_issuance_results:
        for r in debt_issuance_results:
            marker_rows.append((1, f"| 1 | Record debt issuance, hot sector ({r.data.get('ticker', '?')}) | {r.verdict} | {r.detail} |"))
    else:
        marker_rows.append((1, "| 1 | Record debt issuance, hot sector | ok | No hot-watchlist tickers with a resolvable CIK/filing count this run. |"))
    marker_rows.append((3, f"| 3 | Seller finances buyer | {seller_financing_result.verdict} | {seller_financing_result.detail} |"))
    marker_rows.append((6, f"| 6 | Record IPO/equity issuance | {ipo_issuance_result.verdict} | {ipo_issuance_result.detail} |"))
    marker_rows.append((7, f"| 7 | Retail piles into leverage | {retail_leverage_result.verdict} | {retail_leverage_result.detail} |"))
    if regulator_alarm_results:
        for r in regulator_alarm_results:
            marker_rows.append((11, f"| 11 | Regulators sound the alarm | {r.verdict} | {r.detail} |"))
    else:
        marker_rows.append((11, "| 11 | Regulators sound the alarm | ok | No new matching regulator statements this run. |"))
    marker_rows.append((13, f"| 13 | Funding markets start choking | {funding_stress_result.verdict} | {funding_stress_result.detail} |"))
    marker_rows.sort(key=lambda r: r[0])

    lines += ["", "## Markers", "", "| # | Marker | Status | Detail |", "|---|--------|--------|--------|"]
    lines += [row for _, row in marker_rows]

    lines += ["", f"Last auto-generated: {date.today().isoformat()}."]
    return "\n".join(lines) + "\n"


def write_signals_report(*args, **kwargs) -> None:
    config.SIGNALS_REPORT_PATH.write_text(render_signals_report(*args, **kwargs), encoding="utf-8")
