"""Shared fixtures for Briefs Finance tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.db import init_db, get_connection


@pytest.fixture
def db_path(tmp_path) -> Path:
    """In-memory SQLite DB for testing."""
    return tmp_path / "test_investments.db"


@pytest.fixture
def db_conn(db_path):
    """Initialised test DB connection."""
    init_db(db_path)
    conn = get_connection(db_path)
    yield conn
    conn.close()


@pytest.fixture
def sample_report_id(db_conn):
    """Insert a sample report and return its id."""
    with db_conn:
        cur = db_conn.execute(
            """INSERT INTO reports
               (file_path, content_hash, report_date, report_type, title, inferred_sector, ingested_at)
               VALUES (?, ?, ?, ?, ?, ?, datetime('now'))""",
            ("reports/pro-2025/test.pdf", "abc123", "2025-08-30", "thematic", "Gold Test", "gold"),
        )
    return cur.lastrowid


@pytest.fixture
def sample_rec_id(db_conn, sample_report_id):
    """Insert a sample recommendation and return its id."""
    with db_conn:
        cur = db_conn.execute(
            """INSERT INTO recommendations
               (report_id, ticker, company_name, buy_thesis, excluded, extracted_at)
               VALUES (?, ?, ?, ?, 0, datetime('now'))""",
            (sample_report_id, "KGC", "Kinross Gold", "Gold mining thesis", ),
        )
    return cur.lastrowid


@pytest.fixture
def mock_pdf(tmp_path) -> Path:
    """Create a minimal fake PDF (just bytes, not a real PDF — for hash tests)."""
    p = tmp_path / "test_report.pdf"
    p.write_bytes(b"%PDF-1.4 fake content for testing")
    return p
