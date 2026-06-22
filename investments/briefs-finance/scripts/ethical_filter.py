"""Ethical filter — excludes defense/military stocks from recommendations."""

from __future__ import annotations

from .config import DEFENSE_REVIEW_TICKERS, DEFENSE_TICKERS


def check_ticker(ticker: str) -> tuple[bool, str | None]:
    """
    Returns (excluded, reason).
    - True, reason  → auto-exclude (primary defense contractor)
    - False, reason → flag for review (borderline)
    - False, None   → allowed
    """
    t = ticker.upper().split(".")[0]  # strip .AX suffix etc.
    if t in DEFENSE_TICKERS:
        return True, "Primary defense/military contractor"
    if t in DEFENSE_REVIEW_TICKERS:
        return False, f"REVIEW: borderline defense exposure ({t})"
    return False, None
