"""Tests for report.py — markdown/html file creation and terminal smoke test."""

from __future__ import annotations




SAMPLE_ASSESS_DATA = {
    "ticker": "KGC",
    "company_name": "Kinross Gold",
    "buy_thesis": "Gold miner with strong production growth and low AISC.",
    "exit_trigger": "Gold price below $1,800",
    "report_date": "2025-08-30",
    "report_title": "Gold's Comeback",
    "inferred_sector": "gold",
    "score_data": {
        "score": 72,
        "provisional": False,
        "breakdown": {
            "base_rate": 60.0,
            "sector_rate": 70.0,
            "ticker_history": 65.0,
            "principles": 75.0,
            "macro": 50.0,
            "sector_context": 80.0,
        },
    },
    "outcomes": [
        {
            "report_date": "2025-08-30",
            "price_at_rec": 8.50,
            "return_6m": 15.3,
            "vs_sp500_6m": 8.2,
        }
    ],
    "sector": {
        "sector_etf": "GDX",
        "etf_return_6m": 10.5,
        "stock_vs_sector_6m": 4.8,
    },
    "macro": {
        "treasury_10y": 4.25,
        "tbill_3m": 5.0,
        "vix": 18.5,
        "gold_price": 1920.0,
        "usd_strength": 28.5,
        "bonds_20y": None,
        "yield_curve": -0.4,
        "recession_prob": 12.0,
    },
    "principles": [
        {"principle": "graham", "score": 45, "reasoning": "Lacks margin of safety at current price."},
        {"principle": "dalio", "score": 80, "reasoning": "Strong macro tailwind from gold cycle."},
    ],
    "total_recs": 1,
}


def test_render_markdown_creates_file(tmp_path):
    """render_markdown writes a .md file with YAML frontmatter."""
    from scripts.report import render_markdown

    out_path = render_markdown(SAMPLE_ASSESS_DATA, output_dir=tmp_path)

    assert out_path.exists()
    assert out_path.suffix == ".md"
    content = out_path.read_text(encoding="utf-8")
    assert "---" in content
    assert "ticker: KGC" in content
    assert "score: 72" in content
    assert "Kinross Gold" in content


def test_render_markdown_contains_thesis(tmp_path):
    """Markdown output includes the buy thesis."""
    from scripts.report import render_markdown

    out_path = render_markdown(SAMPLE_ASSESS_DATA, output_dir=tmp_path)
    content = out_path.read_text(encoding="utf-8")
    assert "Gold miner" in content


def test_render_html_creates_file(tmp_path):
    """render_html writes a .html file containing the ticker."""
    from scripts.report import render_html
    from scripts.config import TEMPLATES_DIR

    template_path = TEMPLATES_DIR / "stats.html"
    out_path = render_html(SAMPLE_ASSESS_DATA, template_path=template_path, output_dir=tmp_path)

    assert out_path.exists()
    assert out_path.suffix == ".html"
    content = out_path.read_text(encoding="utf-8")
    assert "KGC" in content
    assert "72" in content  # score appears in output


def test_render_html_contains_chart_js(tmp_path):
    """HTML output includes Chart.js script tag."""
    from scripts.report import render_html
    from scripts.config import TEMPLATES_DIR

    template_path = TEMPLATES_DIR / "stats.html"
    out_path = render_html(SAMPLE_ASSESS_DATA, template_path=template_path, output_dir=tmp_path)
    content = out_path.read_text(encoding="utf-8")
    assert "chart.js" in content.lower()


def test_render_terminal_does_not_raise(capsys):
    """render_terminal should not raise for valid assess data."""
    from scripts.report import render_terminal

    render_terminal(SAMPLE_ASSESS_DATA)
    # No assertion on output — just verifying no exception thrown


def test_render_markdown_score_breakdown(tmp_path):
    """Score breakdown components appear in the markdown output."""
    from scripts.report import render_markdown

    out_path = render_markdown(SAMPLE_ASSESS_DATA, output_dir=tmp_path)
    content = out_path.read_text(encoding="utf-8")
    assert "Base Rate" in content or "base_rate" in content.lower()
    assert "Principles" in content or "principles" in content.lower()
