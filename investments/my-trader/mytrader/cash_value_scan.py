"""Cash-Value Scanner -- daily VPS-scheduled screener, per
.agent/plans/cash-value-scanner.md. Finds companies trading near cash value: net
cash (cash + short-term investments minus total debt) >= config.CASH_VALUE_RATIO_
THRESHOLD of market cap, AND positive trailing operating cash flow. Free cash flow
is computed and shown (and tagged when negative) but is NOT a hard gate -- loosened
from OCF+FCF by Shaun 2026-08-26: positive OCF with negative FCF usually means heavy
growth capex, not cash burn, and FCF is the sparsest yfinance field.

Advisor-notes report only -- no candidate staging, no auto-watchlist-add, no
WhatsApp alert. Shaun runs his own `find` / `assess` on anything he likes.

Two universes:
  - US:  Finviz screener (coarse Price/Cash prefilter) -> yfinance precise test.
  - ASX: S&P/ASX 200 Wikipedia constituents -> yfinance precise test (.AX).
The net-cash-to-market-cap RATIO is currency-consistent per company (both figures
from the same yfinance .info in the listing currency), so no FX handling is needed
for the ratio; absolute-dollar columns are labelled with each row's currency.

`conn` is used READ-ONLY here -- only to tag rows Shaun already holds / watchlists.
Nothing in this module writes to investments.db.
"""

from __future__ import annotations

import sqlite3
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from scripts.ethical_filter import check_ticker as ethical_check

from . import asx200_universe, config, db as mt_db, finviz_screener, market_data, tickers

SYDNEY_TZ = ZoneInfo("Australia/Sydney")


def _today_sydney() -> str:
    """Report date label -- always Sydney local, regardless of host clock/timezone."""
    return datetime.now(SYDNEY_TZ).date().isoformat()


# --- metric math (pure) ------------------------------------------------------

def compute_cash_value_metrics(data) -> dict | None:
    """`data` is a market_data.TickerData. Returns None when marketCap / totalCash /
    totalDebt are not all present (can't run the test). net_cash uses raw totalDebt
    -- yfinance bundles IFRS 16 capitalised leases into it, and that is the
    conservative, defensible number (see checks/balance_sheet.py). Higher cash_ratio
    = more of the share price is just the bank balance."""
    info = data.info
    total_cash = info.get("totalCash")
    total_debt = info.get("totalDebt")
    market_cap = info.get("marketCap")
    if total_cash is None or total_debt is None or not market_cap:  # 0 mcap = unusable
        return None

    net_cash = total_cash - total_debt
    cash_ratio = net_cash / market_cap
    ev = market_cap - net_cash  # enterprise-value proxy -- the "stub" you pay for

    ocf = info.get("operatingCashflow")
    fcf = info.get("freeCashflow")  # shown + tagged, not gated
    source = "info"
    if ocf is None or fcf is None:
        annual = market_data.fetch_cash_flow_statement(data.ticker)  # latest ANNUAL or None
        if annual is not None:
            if ocf is None:
                ocf = annual.get("operating_cash_flow")
            if fcf is None:
                fcf = annual.get("free_cash_flow")
            source = "annual" if (info.get("operatingCashflow") is None
                                  and info.get("freeCashflow") is None) else "partial-annual"

    cash_flow_ok = ocf is not None and ocf > 0  # OCF-only gate (see module docstring)

    return {
        "net_cash": net_cash,
        "cash_ratio": cash_ratio,
        "ev": ev,
        "ev_pct_of_mcap": ev / market_cap,  # = 1 - cash_ratio; negative if below net cash
        "market_cap": market_cap,
        "operating_cash_flow": ocf,
        "free_cash_flow": fcf,
        "fcf_yield_on_ev": (fcf / ev) if (fcf is not None and ev > 0) else None,
        "revenue_growth": info.get("revenueGrowth"),
        "sector": info.get("sector"),
        "currency": info.get("financialCurrency") or info.get("currency"),
        "cash_flow_ok": cash_flow_ok,
        "cash_flow_source": source,
    }


def _passes(metrics: dict | None) -> bool:
    return (
        metrics is not None
        and metrics["cash_ratio"] >= config.CASH_VALUE_RATIO_THRESHOLD
        and metrics["cash_flow_ok"]
        and metrics["sector"] not in config.CASH_VALUE_EXCLUDED_SECTORS
    )


# --- formatting -------------------------------------------------------------

def _human_money(value: float | None) -> str:
    if value is None:
        return "n/a"
    a = abs(value)
    sign = "-" if value < 0 else ""
    if a >= 1e9:
        return f"{sign}{a / 1e9:.2f}B"
    if a >= 1e6:
        return f"{sign}{a / 1e6:.1f}M"
    if a >= 1e3:
        return f"{sign}{a / 1e3:.0f}K"
    return f"{sign}{a:.0f}"


def _money(value: float | None, currency: str | None) -> str:
    if value is None:
        return "n/a"
    cur = f" {currency}" if currency else ""
    return f"{_human_money(value)}{cur}"


def _pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value * 100:.0f}%"


def _plain_english_read(row: dict) -> str:
    cur = row["currency"]
    cash = f"{_money(row['net_cash'], cur)} net cash"
    mcap = f"{_money(row['market_cap'], cur)} mcap"
    fcf = row["free_cash_flow"]
    if row["ev"] <= 0:
        stub = (
            f"the market is paying less than the cash pile "
            f"({_pct(row['ev_pct_of_mcap'])} of mcap for the business)"
        )
    else:
        stub = f"paying ~{_money(row['ev'], cur)} for the operating business"
    fcf_bit = f", {_money(fcf, cur)} FCF" if fcf is not None else ""
    return f"{cash}, {mcap}{fcf_bit} - {stub}."


# --- enrichment ------------------------------------------------------------

def _enrich_universe(
    coarse_rows: list[dict], *, market: str, held: set[str], watched: set[str]
) -> tuple[list[dict], int]:
    """Returns (qualifying rows, usable_count). usable_count = how many coarse names
    yfinance returned balance-sheet data for (marketCap + totalCash + totalDebt all
    present) -- run_scan uses the ASX slice of this as a rate-limit tripwire."""
    micro_floor = (
        config.CASH_VALUE_MICRO_CAP_TAG_USD if market == "US"
        else config.CASH_VALUE_MICRO_CAP_TAG_AUD
    )
    results: list[dict] = []
    usable = 0
    for row in coarse_rows:
        bare = row["ticker"]
        yf_ticker = bare if market == "US" else tickers.asx_variant(bare)
        try:
            # Cheap pre-skip on the coarse universe sector (Finviz/Wikipedia wording)
            # -- saves a yfinance call for banks/REITs.
            if (row.get("sector") or "") in config.CASH_VALUE_EXCLUDED_SECTORS:
                continue

            excluded, review_reason = ethical_check(bare)
            if excluded:
                continue  # defense contractor -- dropped entirely, never shown

            data = market_data.fetch_ticker_data(yf_ticker)
            time.sleep(config.CASH_VALUE_FETCH_DELAY_SECONDS)  # ease off Yahoo's rate limit
            if data is None:
                continue
            metrics = compute_cash_value_metrics(data)
            if metrics is not None:
                usable += 1
            if not _passes(metrics):
                continue

            assert metrics is not None  # _passes guarantees this
            tags: list[str] = []
            if bare in held or yf_ticker in held:
                tags.append("held")
            elif bare in watched or yf_ticker in watched:
                tags.append("watchlist")
            if metrics["market_cap"] < micro_floor:
                tags.append("micro")
            rg = metrics["revenue_growth"]
            if rg is not None and rg < 0:
                tags.append("shrinking revenue")
            fcf = metrics["free_cash_flow"]
            if fcf is not None and fcf < 0:
                tags.append("negative FCF")
            if review_reason:
                tags.append(review_reason)  # "REVIEW: borderline defense exposure (BA)"

            result = {
                "ticker": bare,
                "yf_ticker": yf_ticker,
                "company": row.get("company") or "",
                "market": market,
                "review_reason": review_reason,
                "tags": tags,
                **metrics,
            }
            result["read"] = _plain_english_read(result)
            results.append(result)
        except Exception as e:  # one bad ticker must not sink the run
            print(f"[cash-value-scan] error on {yf_ticker}: {e}")
    return results, usable


# --- orchestration -------------------------------------------------------

def run_scan(conn: sqlite3.Connection) -> dict:
    held = {r["ticker"] for r in mt_db.get_all_holdings(conn)}
    watched = {r["ticker"] for r in mt_db.get_all_watchlist(conn)}

    us_coarse = finviz_screener.fetch_screener_universe()
    if us_coarse is None:
        # Total US failure -- caller re-serves the previous report with a banner.
        return {"stale": True}

    asx_coarse = asx200_universe.fetch_asx200_constituents()

    with market_data.cached_session():
        us_rows, us_usable = _enrich_universe(us_coarse, market="US", held=held, watched=watched)
        asx_rows, asx_usable = (
            _enrich_universe(asx_coarse, market="ASX", held=held, watched=watched)
            if asx_coarse is not None else ([], 0)
        )

    # Rate-limit tripwire: the ASX 200 is large-caps with near-complete yfinance
    # coverage, so a collapse in its usable-data count means Yahoo is throttling this
    # whole run -- don't overwrite a good report with a throttled-empty one.
    if asx_coarse is not None and asx_usable < len(asx_coarse) * config.CASH_VALUE_DEGRADED_ASX_MIN_FRACTION:
        return {"degraded": True, "asx_usable": asx_usable, "asx_scanned": len(asx_coarse)}

    combined = sorted(us_rows + asx_rows, key=lambda r: r["cash_ratio"], reverse=True)
    max_rows = config.CASH_VALUE_REPORT_MAX_ROWS
    shown, overflow = combined[:max_rows], max(0, len(combined) - max_rows)

    return {
        "stale": False,
        "rows": shown,
        "overflow": overflow,
        "qualifying_count": len(combined),
        "usable_count": us_usable + asx_usable,
        "asx_unavailable": asx_coarse is None,
        "us_scanned": len(us_coarse),
        "asx_scanned": len(asx_coarse or []),
    }


# --- report -------------------------------------------------------------

_DISCLAIMER = (
    "Auto-generated daily - overwritten every run. Advisor notes only; no trade "
    "action is ever suggested here (see SOUL.md). Run your own `find` / `assess` "
    "on anything you like the look of."
)

_TABLE_HEADER = (
    "| Ticker | Company | Mkt | Net cash / mcap | Biz / mcap | Market cap | "
    "OCF (TTM) | FCF | FCF yld on biz | Net cash | Rev growth YoY | Sector | Tags | Read |"
)
_TABLE_RULE = "|" + "---|" * 14
_COLUMN_NOTE = (
    "`Net cash / mcap` = net cash as a % of the whole company's market value (the "
    "headline number, sorted high-to-low). `Biz / mcap` = what's left, i.e. what "
    "you're paying for the operating business itself; negative means the price is "
    "below the cash pile. `FCF yld on biz` = free cash flow as a % of that business "
    "value."
)


def _row_line(r: dict) -> str:
    cur = r["currency"]
    rg = r["revenue_growth"]
    return "| " + " | ".join([
        r["ticker"],
        (r["company"] or "").replace("|", "/"),
        r["market"],
        f"{r['cash_ratio'] * 100:.0f}%",
        _pct(r["ev_pct_of_mcap"]) + (" (below net cash)" if r["ev"] <= 0 else ""),
        _money(r["market_cap"], cur),
        _money(r["operating_cash_flow"], cur),
        _money(r["free_cash_flow"], cur),
        ("n/a" if r["fcf_yield_on_ev"] is None else f"{r['fcf_yield_on_ev'] * 100:.1f}%"),
        _money(r["net_cash"], cur),
        ("n/a" if rg is None else f"{rg * 100:+.0f}%"),
        r["sector"] or "n/a",
        ", ".join(r["tags"]) if r["tags"] else "-",
        r["read"].replace("|", "/"),
    ]) + " |"


def render_report(result: dict) -> str:
    pct = f"{config.CASH_VALUE_RATIO_THRESHOLD * 100:.0f}%"
    lines = [
        "# Cash-Value Scan",
        "",
        f"**Last run: {_today_sydney()}** - scanned {result['us_scanned']} US + "
        f"{result['asx_scanned']} ASX names ({result.get('usable_count', 0)} returned "
        f"balance-sheet data), {result['qualifying_count']} qualify at net cash "
        f">= {pct} of market cap.",
        "",
        f"What this is: companies whose net cash (cash minus all debt) is at least "
        f"{pct} of their market cap AND that generate positive operating cash flow - "
        f"the market is pricing the whole operating business at a steep discount and "
        f"handing you the balance-sheet cash on top. Classic Graham / deep-value "
        f"screen. Free cash flow is shown and tagged when negative, but is not a "
        f"filter (positive OCF with negative FCF is usually growth capex, not burn).",
        "",
        _COLUMN_NOTE,
        "",
        _DISCLAIMER,
        "",
    ]
    if result["asx_unavailable"]:
        lines += [
            "> ASX universe unavailable this run (Wikipedia scrape failed) - US results only.",
            "",
        ]

    rows = result["rows"]
    if rows:
        lines += [_TABLE_HEADER, _TABLE_RULE]
        lines += [_row_line(r) for r in rows]
    else:
        lines.append("No companies qualify this run.")

    if result["overflow"]:
        lines += [
            "",
            f"... and {result['overflow']} more below the top {config.CASH_VALUE_REPORT_MAX_ROWS} "
            f"(by net cash / mcap).",
        ]

    lines += [
        "",
        "Tag key: `held` / `watchlist` = already tracked in my-trader; "
        "`micro` = market cap under US$50M / A$75M (thinner liquidity, higher risk); "
        "`shrinking revenue` = negative YoY revenue growth; "
        "`negative FCF` = free cash flow negative (heavy capex or cash burn - check which); "
        "`REVIEW:` = borderline ethical-filter flag.",
    ]
    return "\n".join(lines) + "\n"


_BANNER_SUFFIX = "showing the last good run below."


def _write_banner(reason: str) -> None:
    """A run couldn't produce trustworthy output (Finviz scrape failed, or Yahoo
    rate-limited the fundamentals pass) -> keep the previous report and prepend a
    single banner. Banners must not stack across consecutive bad runs. If there is
    no prior report at all, write a minimal placeholder."""
    path = config.CASH_VALUE_REPORT_PATH
    banner = f"> {reason} ({_today_sydney()}) - {_BANNER_SUFFIX}\n\n"
    if path.exists():
        existing = path.read_text(encoding="utf-8")
        first_para, sep, rest = existing.partition("\n\n")
        if first_para.startswith("> ") and first_para.rstrip().endswith(_BANNER_SUFFIX):
            existing = rest if sep else ""
        path.write_text(banner + existing, encoding="utf-8")
    else:
        path.write_text(
            f"# Cash-Value Scan\n\n{banner}No prior report to show.\n",
            encoding="utf-8",
        )


def write_report(result: dict) -> None:
    if result.get("stale"):
        _write_banner("STALE - Finviz screener fetch failed")
        return
    if result.get("degraded"):
        _write_banner(
            f"DEGRADED - Yahoo Finance rate-limited the fundamentals pass "
            f"(only {result['asx_usable']}/{result['asx_scanned']} ASX names returned data)"
        )
        return
    config.CASH_VALUE_REPORT_PATH.write_text(render_report(result), encoding="utf-8")
