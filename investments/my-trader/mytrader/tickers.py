"""Ticker normalization for yfinance lookups."""

from __future__ import annotations

SHARE_CLASS_MAP = {"BRK.B": "BRK-B", "BRK.A": "BRK-A"}


def normalize(ticker: str) -> str:
    t = ticker.strip().upper()
    return SHARE_CLASS_MAP.get(t, t)


def asx_variant(ticker: str) -> str:
    return normalize(ticker) + ".AX"
