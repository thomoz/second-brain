"""Composite 0-100% likelihood scoring for Briefs Finance recommendations."""

from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

from .config import MACRO_SCORE_DEFAULT, PRINCIPLES_DIR, SCORING_WEIGHTS
from .db import get_connection, init_db

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent.parent / ".claude" / "scripts"
sys.path.insert(0, str(_SCRIPTS_DIR))
from sdk_compat import ClaudeAgentOptions, run_text  # noqa: E402


PRINCIPLES_PROMPT = """\
Score this investment thesis against the {principle} investing framework (0-100).
0 = completely fails the criteria, 100 = ideal match.

Thesis: {buy_thesis}

Framework:
{file_content}

Return ONLY valid JSON (no markdown, no explanation):
{{"score": <integer 0-100>, "reasoning": "<one sentence>"}}
"""


def _parse_json(raw: str) -> dict:
    cleaned = raw.strip()
    for fence in ("```json", "```"):
        if cleaned.startswith(fence):
            cleaned = cleaned[len(fence):]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    return json.loads(cleaned.strip())


def score_thesis_against_principle(buy_thesis: str, principle_name: str, file_content: str) -> tuple[int, str]:
    """Call LLM to score thesis against one principle. Returns (score, reasoning)."""
    prompt = PRINCIPLES_PROMPT.format(
        principle=principle_name,
        buy_thesis=buy_thesis,
        file_content=file_content[:3000],
    )
    try:
        raw = asyncio.run(run_text(
            prompt=prompt,
            options=ClaudeAgentOptions(allowed_tools=[], model="haiku"),
        ))
        data = _parse_json(raw)
        score = max(0, min(100, int(data.get("score", 50))))
        reasoning = data.get("reasoning", "")
        return score, reasoning
    except Exception:
        return 50, "Could not score"


def get_principles_scores(buy_thesis: str) -> list[dict]:
    """Score thesis against all 9 principle files. Returns list of {principle, score, reasoning}."""
    if not PRINCIPLES_DIR.exists():
        return []
    results = []
    for md_file in sorted(PRINCIPLES_DIR.glob("*.md")):
        principle_name = md_file.stem
        file_content = md_file.read_text(encoding="utf-8")
        score, reasoning = score_thesis_against_principle(buy_thesis, principle_name, file_content)
        results.append({"principle": principle_name, "score": score, "reasoning": reasoning})
        time.sleep(0.3)
    return results


def compute_score(recommendation_id: int, conn) -> dict:
    """Compute composite likelihood score for a recommendation."""
    rec = conn.execute("""
        SELECT r.*, rep.inferred_sector, rep.report_date, rep.id AS report_id
        FROM recommendations r
        JOIN reports rep ON rep.id = r.report_id
        WHERE r.id = ?
    """, (recommendation_id,)).fetchone()

    if not rec:
        return {}

    ticker = rec["ticker"]
    inferred_sector = rec["inferred_sector"]
    buy_thesis = rec["buy_thesis"] or ""

    # --- Base rate: % all backtested picks beating S&P 500 at 6m ---
    all_6m = conn.execute("""
        SELECT vs_sp500_6m FROM outcomes o
        JOIN recommendations r ON r.id = o.recommendation_id
        WHERE r.excluded = 0 AND o.vs_sp500_6m IS NOT NULL
    """).fetchall()
    if all_6m:
        beat = sum(1 for row in all_6m if row["vs_sp500_6m"] > 0)
        base_rate_score = beat / len(all_6m) * 100
    else:
        base_rate_score = 50.0

    # --- Sector rate: % picks in this sector beating S&P 500 at 6m ---
    if inferred_sector:
        sector_6m = conn.execute("""
            SELECT o.vs_sp500_6m FROM outcomes o
            JOIN recommendations r ON r.id = o.recommendation_id
            JOIN reports rep ON rep.id = r.report_id
            WHERE r.excluded = 0 AND rep.inferred_sector = ? AND o.vs_sp500_6m IS NOT NULL
        """, (inferred_sector,)).fetchall()
        if sector_6m:
            beat_s = sum(1 for row in sector_6m if row["vs_sp500_6m"] > 0)
            sector_rate_score = beat_s / len(sector_6m) * 100
        else:
            sector_rate_score = base_rate_score
    else:
        sector_rate_score = base_rate_score

    # --- Ticker history: this ticker's own accuracy ---
    ticker_6m = conn.execute("""
        SELECT o.vs_sp500_6m FROM outcomes o
        JOIN recommendations r ON r.id = o.recommendation_id
        WHERE r.ticker = ? AND r.excluded = 0 AND o.vs_sp500_6m IS NOT NULL
    """, (ticker,)).fetchall()
    if ticker_6m:
        beat_t = sum(1 for row in ticker_6m if row["vs_sp500_6m"] > 0)
        ticker_history_score = beat_t / len(ticker_6m) * 100
    else:
        ticker_history_score = base_rate_score

    # --- Macro score ---
    macro_score = float(MACRO_SCORE_DEFAULT)

    # --- Sector context: % times sector ETF rose over 6m when Briefs picked this sector ---
    if inferred_sector:
        sc_rows = conn.execute("""
            SELECT sc.etf_return_6m FROM sector_context sc
            JOIN recommendations r ON r.id = sc.recommendation_id
            JOIN reports rep ON rep.id = r.report_id
            WHERE rep.inferred_sector = ? AND sc.etf_return_6m IS NOT NULL AND r.excluded = 0
        """, (inferred_sector,)).fetchall()
        if sc_rows:
            rose = sum(1 for row in sc_rows if row["etf_return_6m"] > 0)
            sector_context_score = rose / len(sc_rows) * 100
        else:
            sector_context_score = 50.0
    else:
        sector_context_score = 50.0

    # --- Principles scoring (LLM) ---
    existing_principles = conn.execute("""
        SELECT principle, score, reasoning FROM principles_evaluations
        WHERE recommendation_id = ?
    """, (recommendation_id,)).fetchall()

    if existing_principles:
        principles_results = [dict(row) for row in existing_principles]
    else:
        principles_results = get_principles_scores(buy_thesis)
        for p in principles_results:
            conn.execute("""
                INSERT INTO principles_evaluations (recommendation_id, principle, score, reasoning, scored_at)
                VALUES (?, ?, ?, ?, datetime('now'))
            """, (recommendation_id, p["principle"], p["score"], p["reasoning"]))
        conn.commit()

    principles_score = (
        sum(p["score"] for p in principles_results) / len(principles_results)
        if principles_results else 50.0
    )

    # --- Check provisional flag (<5 historical outcomes) ---
    n_outcomes = len(all_6m)
    provisional = n_outcomes < 5

    # Adjust weights if provisional
    weights = dict(SCORING_WEIGHTS)
    if provisional:
        deficit = weights["base_rate"] + weights["sector_rate"] + weights["ticker_history"]
        weights["base_rate"] = 0.05
        weights["sector_rate"] = 0.05
        weights["ticker_history"] = 0.05
        redistributed = deficit - 0.15
        weights["principles"] += redistributed * 0.5
        weights["macro"] += redistributed * 0.25
        weights["sector_context"] += redistributed * 0.25

    components = {
        "base_rate": base_rate_score,
        "sector_rate": sector_rate_score,
        "ticker_history": ticker_history_score,
        "principles": principles_score,
        "macro": macro_score,
        "sector_context": sector_context_score,
    }

    composite = sum(components[k] * weights[k] for k in components)
    final_score = max(0, min(100, round(composite)))

    breakdown = {k: round(components[k], 1) for k in components}

    result = {
        "recommendation_id": recommendation_id,
        "ticker": ticker,
        "score": final_score,
        "provisional": provisional,
        "components": components,
        "breakdown": breakdown,
        "weights_used": weights,
        "principles_results": principles_results,
        "n_historical_outcomes": n_outcomes,
    }

    # Upsert likelihood score
    conn.execute("""
        INSERT OR REPLACE INTO likelihood_scores
        (recommendation_id, score, base_rate, sector_rate, ticker_history, principles, macro,
         sector_context, breakdown_json, provisional, computed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
    """, (
        recommendation_id, final_score,
        components["base_rate"], components["sector_rate"], components["ticker_history"],
        components["principles"], components["macro"], components["sector_context"],
        json.dumps(breakdown), int(provisional),
    ))
    conn.commit()

    return result


def score_ticker(ticker: str) -> None:
    """Score all non-excluded recommendations for a ticker."""
    init_db()
    conn = get_connection()
    recs = conn.execute("""
        SELECT r.id FROM recommendations r WHERE r.ticker = ? AND r.excluded = 0
    """, (ticker.upper(),)).fetchall()
    if not recs:
        print(f"No recommendations found for {ticker}")
        conn.close()
        return
    for rec in recs:
        result = compute_score(rec["id"], conn)
        print(f"\n{ticker}: {result.get('score', '?')}/100 (provisional={result.get('provisional')})")
        for k, v in result.get("breakdown", {}).items():
            print(f"  {k:<20}: {v:.1f}")
        if result.get("principles_results"):
            print("  Principles:")
            for p in result["principles_results"]:
                print(f"    {p['principle']:<15}: {p['score']}/100 — {p.get('reasoning', '')[:80]}")
    conn.close()


def score_all() -> None:
    """Score every non-excluded recommendation that has an outcome."""
    init_db()
    conn = get_connection()
    recs = conn.execute("""
        SELECT DISTINCT r.id FROM recommendations r
        JOIN outcomes o ON o.recommendation_id = r.id
        WHERE r.excluded = 0
    """).fetchall()
    print(f"Scoring {len(recs)} recommendations...")
    for rec in recs:
        result = compute_score(rec["id"], conn)
        print(f"  {result.get('ticker', '?'):<8}: {result.get('score', '?')}/100")
    conn.close()


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Score Briefs Finance recommendations")
    parser.add_argument("--ticker", help="Score a specific ticker")
    parser.add_argument("--report-id", type=int, help="Score all recs in a report")
    parser.add_argument("--all", action="store_true", help="Score all recommendations with outcomes")
    args = parser.parse_args()

    if args.ticker:
        score_ticker(args.ticker)
    elif args.all:
        score_all()
    elif args.report_id:
        init_db()
        conn = get_connection()
        recs = conn.execute("""
            SELECT id FROM recommendations WHERE report_id = ? AND excluded = 0
        """, (args.report_id,)).fetchall()
        for rec in recs:
            result = compute_score(rec["id"], conn)
            print(f"{result.get('ticker')}: {result.get('score')}/100")
        conn.close()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
