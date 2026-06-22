"""PDF text extraction and content hashing."""

from __future__ import annotations

import hashlib
import warnings
from pathlib import Path


def extract_text(pdf_path: Path) -> str:
    """Extract all text from a PDF. Returns empty string on failure."""
    try:
        import pdfplumber
    except ImportError:
        return ""
    warnings.filterwarnings("ignore", message=".*FontBBox.*")
    try:
        with pdfplumber.open(pdf_path) as pdf:
            return "\n".join(p.extract_text() or "" for p in pdf.pages)
    except Exception:
        return ""


def compute_hash(pdf_path: Path) -> str:
    """SHA-256 hash of PDF bytes for deduplication."""
    try:
        return hashlib.sha256(pdf_path.read_bytes()).hexdigest()
    except FileNotFoundError:
        return ""
