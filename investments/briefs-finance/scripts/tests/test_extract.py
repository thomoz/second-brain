"""Tests for extract.py — hash determinism and text extraction."""

from __future__ import annotations


from scripts.extract import compute_hash, extract_text


def test_hash_determinism(mock_pdf):
    """Same file hashes to same value every time."""
    h1 = compute_hash(mock_pdf)
    h2 = compute_hash(mock_pdf)
    assert h1 == h2
    assert len(h1) == 64  # SHA-256 hex


def test_hash_missing_file(tmp_path):
    """Missing file returns empty string."""
    result = compute_hash(tmp_path / "nonexistent.pdf")
    assert result == ""


def test_extract_text_returns_str(mock_pdf):
    """extract_text always returns a string (even for non-PDF bytes)."""
    result = extract_text(mock_pdf)
    assert isinstance(result, str)


def test_extract_text_missing_file(tmp_path):
    """Missing file returns empty string without raising."""
    result = extract_text(tmp_path / "nonexistent.pdf")
    assert result == ""


def test_hash_different_for_different_content(tmp_path):
    """Two files with different content have different hashes."""
    p1 = tmp_path / "a.pdf"
    p2 = tmp_path / "b.pdf"
    p1.write_bytes(b"content one")
    p2.write_bytes(b"content two")
    assert compute_hash(p1) != compute_hash(p2)
