"""Output rendering: Rich terminal, Markdown vault, HTML with Chart.js."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from .config import ASSESSMENTS_DIR, TEMPLATES_DIR
from .db import get_connection, init_db
from .score import compute_score


def _gather_assess_data(ticker: str) -> dict:
    """Collect all assessment data for a ticker from the DB."""
    init_db()
    conn = get_connection()

    recs = conn.execute("""
        SELECT r.id, r.ticker, r.company_name, r.buy_thesis, r.exit_trigger,
               rep.report_date, rep.title, rep.inferred_sector, rep.series
        FROM recommendations r
        JOIN reports rep ON rep.id = r.report_id
        WHERE r.ticker = ? AND r.excluded = 0
        ORDER BY rep.report_date DESC
    """, (ticker.upper(),)).fetchall()

    if not recs:
        conn.close()
        return {"ticker": ticker, "error": "No recommendations found"}

    rec = recs[0]
    rec_id = rec["id"]

    # Get or compute score
    existing_score = conn.execute(
        "SELECT * FROM likelihood_scores WHERE recommendation_id = ?", (rec_id,)
    ).fetchone()
    if existing_score:
        score_data = {
            "score": existing_score["score"],
            "provisional": bool(existing_score["provisional"]),
            "breakdown": {
                "base_rate": existing_score["base_rate"],
                "sector_rate": existing_score["sector_rate"],
                "ticker_history": existing_score["ticker_history"],
                "principles": existing_score["principles"],
                "macro": existing_score["macro"],
                "sector_context": existing_score["sector_context"],
            },
        }
    else:
        score_data = compute_score(rec_id, conn)

    # Outcome history
    outcomes = conn.execute("""
        SELECT o.*, rep.report_date
        FROM outcomes o
        JOIN recommendations r ON r.id = o.recommendation_id
        JOIN reports rep ON rep.id = r.report_id
        WHERE r.ticker = ? AND r.excluded = 0
        ORDER BY rep.report_date DESC
    """, (ticker.upper(),)).fetchall()

    # Sector context
    sector = conn.execute("""
        SELECT sc.* FROM sector_context sc
        WHERE sc.recommendation_id = ?
    """, (rec_id,)).fetchone()

    # Macro snapshot
    macro = conn.execute("""
        SELECT ms.* FROM macro_snapshot ms
        JOIN reports rep ON rep.id = ms.report_id
        JOIN recommendations r ON r.report_id = rep.id
        WHERE r.id = ?
    """, (rec_id,)).fetchone()

    # Principles
    principles = conn.execute("""
        SELECT principle, score, reasoning FROM principles_evaluations
        WHERE recommendation_id = ?
        ORDER BY principle
    """, (rec_id,)).fetchall()

    conn.close()

    return {
        "ticker": ticker.upper(),
        "company_name": rec["company_name"] or ticker,
        "buy_thesis": rec["buy_thesis"] or "N/A",
        "exit_trigger": rec["exit_trigger"],
        "report_date": rec["report_date"],
        "report_title": rec["title"],
        "inferred_sector": rec["inferred_sector"],
        "score_data": score_data,
        "outcomes": [dict(o) for o in outcomes],
        "sector": dict(sector) if sector else None,
        "macro": dict(macro) if macro else None,
        "principles": [dict(p) for p in principles],
        "total_recs": len(recs),
    }


def render_terminal(assess_data: dict) -> None:
    """Render assessment as Rich terminal output."""
    try:
        from rich.console import Console
        from rich.panel import Panel
        from rich.table import Table
    except ImportError:
        _render_plain(assess_data)
        return

    console = Console()

    if "error" in assess_data:
        console.print(f"[red]{assess_data['error']}[/red]")
        return

    ticker = assess_data["ticker"]
    company = assess_data["company_name"]
    score_data = assess_data.get("score_data", {})
    score = score_data.get("score", "N/A")
    provisional = score_data.get("provisional", False)

    # Header
    prov_note = " [yellow](provisional — <5 outcomes)[/yellow]" if provisional else ""
    console.print(Panel(
        f"[bold cyan]{ticker}[/bold cyan] — {company}\n"
        f"[dim]Report: {assess_data.get('report_date')} | Sector: {assess_data.get('inferred_sector')}[/dim]",
        title="Briefs Finance Assessment",
        border_style="cyan",
    ))

    # Score panel
    score_color = "green" if isinstance(score, int) and score >= 60 else ("yellow" if isinstance(score, int) and score >= 40 else "red")
    console.print(Panel(
        f"Likelihood Score: [{score_color}][bold]{score}/100[/bold][/{score_color}]{prov_note}\n"
        f"Thesis: {(assess_data.get('buy_thesis') or 'N/A')[:200]}",
        border_style=score_color,
    ))

    # Score breakdown
    breakdown = score_data.get("breakdown") or {}
    if breakdown:
        bt = Table(title="Score Breakdown", show_header=True)
        bt.add_column("Component", style="bold")
        bt.add_column("Score", justify="right")
        for k, v in breakdown.items():
            if v is not None:
                bt.add_row(k.replace("_", " ").title(), f"{v:.1f}")
        console.print(bt)

    # Track record
    outcomes = assess_data.get("outcomes") or []
    if outcomes:
        ot = Table(title=f"Track Record ({len(outcomes)} tips)", show_header=True)
        ot.add_column("Date")
        ot.add_column("Price@Rec", justify="right")
        ot.add_column("Ret 6m", justify="right")
        ot.add_column("vs S&P 6m", justify="right")
        for o in outcomes[:5]:
            vs = o.get("vs_sp500_6m")
            vs_str = f"{vs:+.1f}%" if vs is not None else "—"
            vs_color = "green" if vs and vs > 0 else ("red" if vs and vs < 0 else "")
            ret = o.get("return_6m")
            ret_str = f"{ret:+.1f}%" if ret is not None else "—"
            ot.add_row(
                o.get("report_date") or "—",
                f"${o.get('price_at_rec'):.2f}" if o.get("price_at_rec") else "—",
                ret_str,
                f"[{vs_color}]{vs_str}[/{vs_color}]" if vs_color else vs_str,
            )
        console.print(ot)

    # Sector context
    sector = assess_data.get("sector")
    if sector:
        etf = sector.get("sector_etf", "—")
        etf_ret = sector.get("etf_return_6m")
        svs = sector.get("stock_vs_sector_6m")
        console.print(Panel(
            f"Sector ETF: [bold]{etf}[/bold]  6m return: {etf_ret:+.1f}%  Stock vs Sector: {svs:+.1f}%"
            if etf_ret is not None and svs is not None
            else f"Sector ETF: {etf} — data pending",
            title="Sector Thesis Context",
            border_style="blue",
        ))

    # Macro snapshot
    macro = assess_data.get("macro")
    if macro:
        mt = Table(title="Macro at Recommendation Date", show_header=True)
        mt.add_column("Indicator")
        mt.add_column("Value", justify="right")
        for k, label in [
            ("treasury_10y", "10Y Treasury"), ("vix", "VIX"), ("gold_price", "Gold (GLD)"),
            ("usd_strength", "USD (UUP)"), ("yield_curve", "Yield Curve (T10Y2Y)"),
            ("recession_prob", "Recession Prob"),
        ]:
            v = macro.get(k)
            mt.add_row(label, f"{v:.2f}" if v is not None else "—")
        console.print(mt)

    # Principles
    principles = assess_data.get("principles") or []
    if principles:
        pt = Table(title="Principles Evaluation", show_header=True, expand=True)
        pt.add_column("Framework", style="bold", no_wrap=True)
        pt.add_column("Score", justify="right", no_wrap=True)
        pt.add_column("Reasoning", ratio=1)
        for p in principles:
            score_val = p.get("score", 0)
            color = "green" if score_val >= 60 else ("yellow" if score_val >= 40 else "red")
            pt.add_row(
                p["principle"].title(),
                f"[{color}]{score_val}[/{color}]",
                p.get("reasoning") or "",
            )
        console.print(pt)


def _render_plain(assess_data: dict) -> None:
    """Fallback plain-text render when Rich is unavailable."""
    print(f"\n=== {assess_data.get('ticker')} — {assess_data.get('company_name')} ===")
    score_data = assess_data.get("score_data", {})
    print(f"Score: {score_data.get('score', 'N/A')}/100 (provisional={score_data.get('provisional')})")
    print(f"Thesis: {assess_data.get('buy_thesis', 'N/A')[:200]}")
    for k, v in (score_data.get("breakdown") or {}).items():
        if v is not None:
            print(f"  {k}: {v:.1f}")


def render_markdown(assess_data: dict, output_dir: Path | None = None) -> Path:
    """Write Markdown assessment to vault assessments directory."""
    out_dir = output_dir or ASSESSMENTS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    ticker = assess_data.get("ticker", "UNKNOWN")
    today = date.today().isoformat()
    out_path = out_dir / f"{ticker}-{today}.md"

    score_data = assess_data.get("score_data", {})
    score = score_data.get("score", "N/A")
    breakdown = score_data.get("breakdown") or {}
    outcomes = assess_data.get("outcomes") or []
    macro = assess_data.get("macro") or {}
    sector = assess_data.get("sector") or {}
    principles = assess_data.get("principles") or []

    lines = [
        "---",
        f"ticker: {ticker}",
        f"company: {assess_data.get('company_name', '')}",
        f"score: {score}",
        f"provisional: {score_data.get('provisional', False)}",
        f"report_date: {assess_data.get('report_date', '')}",
        f"sector: {assess_data.get('inferred_sector', '')}",
        f"assessed: {today}",
        "type: investment-assessment",
        "---",
        "",
        f"# {ticker} — {assess_data.get('company_name', '')}",
        "",
        f"**Likelihood Score: {score}/100**{'  *(provisional)*' if score_data.get('provisional') else ''}",
        "",
        "## Thesis",
        assess_data.get("buy_thesis") or "N/A",
        "",
    ]

    if assess_data.get("exit_trigger"):
        lines += ["## Exit Trigger", assess_data["exit_trigger"], ""]

    if breakdown:
        lines += ["## Score Breakdown", "| Component | Score |", "|-----------|-------|"]
        for k, v in breakdown.items():
            if v is not None:
                lines.append(f"| {k.replace('_', ' ').title()} | {v:.1f} |")
        lines.append("")

    if outcomes:
        lines += ["## Track Record", "| Date | Price@Rec | Ret 6m | vs S&P |", "|------|-----------|--------|--------|"]
        for o in outcomes[:10]:
            ret = o.get("return_6m")
            vs = o.get("vs_sp500_6m")
            lines.append(
                f"| {o.get('report_date', '—')} "
                f"| {'${:.2f}'.format(o['price_at_rec']) if o.get('price_at_rec') else '—'} "
                f"| {'{:+.1f}%'.format(ret) if ret is not None else '—'} "
                f"| {'{:+.1f}%'.format(vs) if vs is not None else '—'} |"
            )
        lines.append("")

    if sector:
        etf = sector.get("sector_etf", "—")
        etf_ret = sector.get("etf_return_6m")
        svs = sector.get("stock_vs_sector_6m")
        lines += [
            "## Sector Context",
            f"**ETF:** {etf}",
            f"**ETF 6m return:** {'{:+.1f}%'.format(etf_ret) if etf_ret is not None else '—'}",
            f"**Stock vs sector alpha:** {'{:+.1f}%'.format(svs) if svs is not None else '—'}",
            "",
        ]

    if macro:
        lines += ["## Macro at Recommendation Date", "| Indicator | Value |", "|-----------|-------|"]
        for k, label in [
            ("treasury_10y", "10Y Treasury"), ("vix", "VIX"), ("gold_price", "Gold"),
            ("usd_strength", "USD"), ("yield_curve", "Yield Curve"), ("recession_prob", "Recession Prob"),
        ]:
            v = macro.get(k)
            lines.append(f"| {label} | {'{:.2f}'.format(v) if v is not None else '—'} |")
        lines.append("")

    if principles:
        lines += ["## Principles Evaluation", "| Framework | Score | Reasoning |", "|-----------|-------|-----------|"]
        for p in principles:
            lines.append(f"| {p['principle'].title()} | {p.get('score', '—')} | {(p.get('reasoning') or '')[:100]} |")
        lines.append("")

    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path


def render_html(assess_data: dict, template_path: Path | None = None, output_dir: Path | None = None) -> Path:
    """Write HTML assessment with Chart.js score breakdown."""
    template_path = template_path or TEMPLATES_DIR / "stats.html"
    out_dir = output_dir or ASSESSMENTS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    ticker = assess_data.get("ticker", "UNKNOWN")
    today = date.today().isoformat()
    out_path = out_dir / f"{ticker}-{today}.html"

    score_data = assess_data.get("score_data", {})
    score = score_data.get("score", 0)
    breakdown = score_data.get("breakdown") or {}

    chart_labels = json_safe(list(breakdown.keys()))
    chart_data = json_safe([v for v in breakdown.values() if v is not None])
    macro = assess_data.get("macro") or {}
    outcomes = assess_data.get("outcomes") or []
    sector = assess_data.get("sector") or {}

    outcome_rows = ""
    for o in outcomes[:10]:
        ret = o.get("return_6m")
        vs = o.get("vs_sp500_6m")
        outcome_rows += (
            f"<tr><td>{o.get('report_date','—')}</td>"
            f"<td>{'${:.2f}'.format(o['price_at_rec']) if o.get('price_at_rec') else '—'}</td>"
            f"<td>{'{:+.1f}%'.format(ret) if ret is not None else '—'}</td>"
            f"<td>{'{:+.1f}%'.format(vs) if vs is not None else '—'}</td></tr>"
        )

    macro_rows = ""
    for k, label in [
        ("treasury_10y", "10Y Treasury"), ("vix", "VIX"), ("gold_price", "Gold"),
        ("usd_strength", "USD"), ("yield_curve", "Yield Curve"), ("recession_prob", "Recession Prob"),
    ]:
        v = macro.get(k)
        macro_rows += f"<tr><td>{label}</td><td>{'{:.2f}'.format(v) if v is not None else '—'}</td></tr>"

    template = template_path.read_text(encoding="utf-8") if template_path.exists() else _default_html_template()

    html = (
        template
        .replace("{{TICKER}}", ticker)
        .replace("{{COMPANY}}", assess_data.get("company_name") or ticker)
        .replace("{{SCORE}}", str(score))
        .replace("{{PROVISIONAL}}", "Provisional" if score_data.get("provisional") else "")
        .replace("{{THESIS}}", (assess_data.get("buy_thesis") or "N/A")[:500])
        .replace("{{REPORT_DATE}}", assess_data.get("report_date") or "—")
        .replace("{{SECTOR}}", assess_data.get("inferred_sector") or "—")
        .replace("{{ASSESSED_DATE}}", today)
        .replace("{{CHART_LABELS}}", chart_labels)
        .replace("{{CHART_DATA}}", chart_data)
        .replace("{{OUTCOME_ROWS}}", outcome_rows)
        .replace("{{MACRO_ROWS}}", macro_rows)
        .replace("{{SECTOR_ETF}}", sector.get("sector_etf") or "—")
        .replace("{{SECTOR_RETURN_6M}}", f"{sector['etf_return_6m']:+.1f}%" if sector.get("etf_return_6m") is not None else "—")
        .replace("{{STOCK_VS_SECTOR}}", f"{sector['stock_vs_sector_6m']:+.1f}%" if sector.get("stock_vs_sector_6m") is not None else "—")
    )

    out_path.write_text(html, encoding="utf-8")
    return out_path


def json_safe(value) -> str:
    import json
    return json.dumps(value)


def _default_html_template() -> str:
    stats_path = TEMPLATES_DIR / "stats.html"
    return stats_path.read_text(encoding="utf-8") if stats_path.exists() else ""


def render_assess(assess_data: dict, mode: str = "terminal", output_dir: Path | None = None) -> None:
    if mode == "terminal":
        render_terminal(assess_data)
    elif mode == "markdown":
        path = render_markdown(assess_data, output_dir)
        print(f"Written: {path}")
    elif mode == "html":
        path = render_html(assess_data, output_dir=output_dir)
        print(f"Written: {path}")
    else:
        render_terminal(assess_data)


def assess_ticker(ticker: str, output_mode: str = "terminal", output_dir: Path | None = None) -> None:
    assess_data = _gather_assess_data(ticker)
    render_assess(assess_data, mode=output_mode, output_dir=output_dir)
