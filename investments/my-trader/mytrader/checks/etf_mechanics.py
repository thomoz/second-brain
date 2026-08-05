"""ETF mechanics check — expense ratio baseline capture / drift detection, plus
ETF-specific criteria (added 2026-08-04): expense ratio richness, AUM/closure-risk,
and holdings/sector context.

Phase A can only capture an expense-ratio baseline on first sight; true drift
detection activates once Monitor (Phase B) runs repeatedly and this is called again
with a populated existing_row.

The AUM/expense-ratio thresholds below are industry rules-of-thumb, not sourced from
investments/briefs-finance's principle files (those don't cover funds at all) — see
config.py's ETF_AUM_FLAG_USD/ETF_EXPENSE_RATIO_FLAG_PCT docstrings for the reasoning,
confirmed with Shaun 2026-08-04. Built after the XMET (Betashares Energy Transition
Metals ETF) bug showed principles_fit's 9 stock-picking frameworks (Buffett/Graham/
etc.) don't apply to a diversified fund — that check now skips ETFs entirely (see
checks/principles_fit.py), and this file is where fund-appropriate criteria live
instead.
"""

from __future__ import annotations

from .. import config
from . import CheckResult
from .scale import format_scale


def _fetch_funds_data(ticker: str):
    """Best-effort ETF holdings/sector fetch — a separate yfinance call from the info
    dict already on TickerData, since funds_data (top holdings, sector weightings) is
    ETF-only and would be wasted for every non-ETF ticker if fetched eagerly in
    market_data.py. Swallows exceptions (same pattern as crash_windows.py's own
    history fetch) — a holdings-context hiccup shouldn't break the rest of the check."""
    import yfinance as yf

    try:
        return yf.Ticker(ticker).funds_data
    except Exception:
        return None


def _holdings_context(ticker: str) -> str | None:
    """Always informational, never gated — a thematic/sector fund (e.g. GDX, XMET)
    being concentrated in one sector is by design, not a red flag the way sector
    concentration is for a single stock (see checks/concentration.py). Same
    never-pass/fail pattern as crash_resilience.py/price_action.py."""
    fd = _fetch_funds_data(ticker)
    if fd is None:
        return None

    parts = []
    try:
        top = fd.top_holdings
        if top is not None and len(top):
            names = ", ".join(
                f"{row['Name']} ({row['Holding Percent'] * 100:.1f}%)"
                for _, row in top.head(3).iterrows()
            )
            parts.append(f"top holdings: {names}")
    except Exception:
        pass

    try:
        weights = fd.sector_weightings or {}
        if weights:
            top_sector, top_weight = max(weights.items(), key=lambda kv: kv[1])
            if top_weight > 0:
                parts.append(f"dominant sector: {top_sector.replace('_', ' ').title()} ({top_weight * 100:.0f}%)")
    except Exception:
        pass

    return "; ".join(parts) if parts else None


def check(data, existing_row) -> CheckResult:
    if data is None:
        return CheckResult(name="etf_mechanics", verdict="unknown", detail="No market data available")

    if data.info.get("quoteType") != "ETF":
        return CheckResult(name="etf_mechanics", verdict="unknown", detail="Not an ETF")

    expense_ratio = data.info.get("netExpenseRatio")
    category = data.info.get("category")
    total_assets = data.info.get("totalAssets")
    prior_ratio = existing_row["last_expense_ratio"] if existing_row is not None else None

    flags = []
    if prior_ratio is not None and expense_ratio is not None and prior_ratio != expense_ratio:
        flags.append(f"Expense ratio changed from {prior_ratio:.4f} to {expense_ratio:.4f}")

    if expense_ratio is not None and expense_ratio >= config.ETF_EXPENSE_RATIO_FLAG_PCT:
        er_scale = format_scale(expense_ratio, config.ETF_EXPENSE_RATIO_CHEAP_PCT, config.ETF_EXPENSE_RATIO_FLAG_PCT)
        flags.append(
            f"Expense ratio {expense_ratio:.2f}% at/above {config.ETF_EXPENSE_RATIO_FLAG_PCT}% ({er_scale})"
        )

    if total_assets is not None and total_assets < config.ETF_AUM_FLAG_USD:
        aum_scale = format_scale(total_assets, config.ETF_AUM_HEALTHY_USD, config.ETF_AUM_FLAG_USD)
        flags.append(
            f"AUM ${total_assets:,.0f} below ${config.ETF_AUM_FLAG_USD:,.0f} closure-risk "
            f"threshold ({aum_scale})"
        )

    context = _holdings_context(data.ticker)
    data_out = {
        "expense_ratio": expense_ratio, "prior_expense_ratio": prior_ratio,
        "category": category, "total_assets": total_assets,
    }

    if flags:
        detail = "; ".join(flags)
        if context:
            detail += f" — {context}"
        return CheckResult(name="etf_mechanics", verdict="flag", detail=detail, data=data_out)

    parts = [f"Expense ratio {expense_ratio:.2f}%" if expense_ratio is not None else "Expense ratio unavailable"]
    parts.append(f"AUM ${total_assets:,.0f}" if total_assets is not None else "AUM unavailable")
    detail = ", ".join(parts)
    if context:
        detail += f" — {context}"
    return CheckResult(name="etf_mechanics", verdict="info", detail=detail, data=data_out)
