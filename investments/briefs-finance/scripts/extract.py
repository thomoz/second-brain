"""PDF text extraction and content hashing."""

from __future__ import annotations

import hashlib
import io
import warnings
from pathlib import Path


def _extract_text_pdfplumber(pdf_path: Path) -> str:
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


def _extract_text_ocr(pdf_path: Path) -> str:
    """OCR fallback for image-based PDFs using PyMuPDF + pytesseract."""
    try:
        import fitz  # pymupdf
        import pytesseract
        from PIL import Image
    except ImportError:
        return ""
    # Point pytesseract at the Windows install location if not on PATH
    tesseract_win = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")
    if tesseract_win.exists():
        pytesseract.pytesseract.tesseract_cmd = str(tesseract_win)
    try:
        doc = fitz.open(str(pdf_path))
        pages: list[str] = []
        for page in doc:
            mat = fitz.Matrix(300 / 72, 300 / 72)  # 300 DPI
            pix = page.get_pixmap(matrix=mat)
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            pages.append(pytesseract.image_to_string(img))
        doc.close()
        return "\n".join(pages)
    except Exception:
        return ""


def extract_text(pdf_path: Path) -> str:
    """Extract all text from a PDF. Falls back to OCR for image-based PDFs."""
    text = _extract_text_pdfplumber(pdf_path)
    if not text.strip():
        text = _extract_text_ocr(pdf_path)
    return text


def compute_hash(pdf_path: Path) -> str:
    """SHA-256 hash of PDF bytes for deduplication."""
    try:
        return hashlib.sha256(pdf_path.read_bytes()).hexdigest()
    except FileNotFoundError:
        return ""
