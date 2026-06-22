"""Tests for score.py — composite scoring logic (mocked DB + LLM)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch



def _make_mock_conn(outcomes=None, ticker_outcomes=None, sector_outcomes=None, sc_rows=None, principles=None):
    """Build a mock sqlite3 connection that returns preset query results."""
    conn = MagicMock()

    def mock_execute(sql, params=None):
        cursor = MagicMock()
        sql_stripped = sql.strip().lower()

        if "from outcomes o" in sql_stripped and "rep.inferred_sector" in sql_stripped and "ticker" not in sql_stripped:
            # all_6m query
            cursor.fetchall.return_value = outcomes or []
        elif "where r.ticker = ?" in sql_stripped and "vs_sp500_6m" in sql_stripped:
            cursor.fetchall.return_value = ticker_outcomes or []
        elif "rep.inferred_sector = ?" in sql_stripped and "vs_sp500_6m" in sql_stripped:
            cursor.fetchall.return_value = sector_outcomes or []
        elif "sector_context sc" in sql_stripped and "etf_return_6m" in sql_stripped:
            cursor.fetchall.return_value = sc_rows or []
        elif "principles_evaluations" in sql_stripped:
            cursor.fetchall.return_value = principles or []
        elif "likelihood_scores" in sql_stripped and "select" in sql_stripped:
            cursor.fetchone.return_value = None
        else:
            cursor.fetchone.return_value = None
            cursor.fetchall.return_value = []

        return cursor

    conn.execute.side_effect = mock_execute
    conn.commit.return_value = None
    return conn


def test_score_in_range():
    """Composite score is always between 0 and 100."""
    from scripts.score import compute_score

    mock_rec = MagicMock()
    mock_rec.__getitem__ = lambda self, key: {
        "id": 1, "ticker": "KGC", "buy_thesis": "Gold miner thesis",
        "inferred_sector": "gold", "report_date": "2025-08-30", "report_id": 1,
    }.get(key)

    conn = MagicMock()

    # Mock the main recommendation query
    conn.execute.return_value.fetchone.return_value = mock_rec

    # Patch all DB sub-queries to return empty
    all_outcomes_mock = MagicMock()
    all_outcomes_mock.fetchall.return_value = []

    with patch("scripts.score.get_principles_scores", return_value=[
        {"principle": "graham", "score": 60, "reasoning": "Decent value"},
    ]):
        with patch.object(conn, "execute") as mock_exec:
            mock_exec.return_value.fetchone.return_value = {
                "id": 1, "ticker": "KGC", "company_name": "Kinross Gold",
                "buy_thesis": "Gold miner thesis", "inferred_sector": "gold",
                "report_date": "2025-08-30", "report_id": 1,
            }
            mock_exec.return_value.fetchall.return_value = []
            result = compute_score(1, conn)

    # Even with empty data, score should be a valid integer in [0, 100]
    assert 0 <= result.get("score", 50) <= 100


def test_provisional_flag_when_few_outcomes():
    """Fewer than 5 historical outcomes → provisional=True."""
    from scripts.score import compute_score

    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = {
        "id": 1, "ticker": "RARE", "company_name": "Rare Co",
        "buy_thesis": "Rare earth play", "inferred_sector": "rare earth",
        "report_date": "2025-03-01", "report_id": 1,
    }
    conn.execute.return_value.fetchall.return_value = []  # 0 outcomes → provisional

    with patch("scripts.score.get_principles_scores", return_value=[]):
        result = compute_score(1, conn)

    assert result.get("provisional") is True


def test_sector_context_component_included_in_breakdown():
    """sector_context key must be present in score breakdown."""
    from scripts.score import compute_score

    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = {
        "id": 1, "ticker": "KGC", "company_name": "Kinross",
        "buy_thesis": "Gold miner", "inferred_sector": "gold",
        "report_date": "2025-08-30", "report_id": 1,
    }
    conn.execute.return_value.fetchall.return_value = []

    with patch("scripts.score.get_principles_scores", return_value=[]):
        result = compute_score(1, conn)

    assert "sector_context" in result.get("breakdown", {})
