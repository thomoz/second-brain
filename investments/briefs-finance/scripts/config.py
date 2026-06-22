"""Path constants, filters, sector ETF map, and scoring weights for Briefs Finance tool."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

_HERE = Path(__file__).resolve().parent
load_dotenv(_HERE.parent / ".env")

PROJECT_ROOT = _HERE.parent.parent.parent  # scripts -> briefs-finance -> investments -> repo root
INVESTMENTS_DIR = PROJECT_ROOT / "investments" / "briefs-finance"
DATA_DIR = INVESTMENTS_DIR / "data"
DB_PATH = DATA_DIR / "investments.db"
REPORTS_DIR = INVESTMENTS_DIR / "reports"
PRINCIPLES_DIR = INVESTMENTS_DIR / "principles"
ASSESSMENTS_DIR = INVESTMENTS_DIR / "assessments"
TEMPLATES_DIR = _HERE / "templates"

DEFENSE_TICKERS = frozenset({
    "LMT", "RTX", "NOC", "GD", "HII", "LHX", "LDOS", "SAIC",
    "CACI", "KTOS", "AVAV", "BWXT", "TXT", "HEICO", "TDG", "CW", "DRS",
})
DEFENSE_REVIEW_TICKERS = frozenset({"BA", "PLTR"})

SP500_TICKER = "^GSPC"
PRICE_WINDOW_DAYS = 7

MACRO_YFINANCE: dict[str, str] = {
    "treasury_10y": "^TNX",
    "tbill_3m": "^IRX",
    "vix": "^VIX",
    "gold": "GLD",
    "usd": "UUP",
    "bonds_20y": "TLT",
}
FRED_API_KEY: str = os.getenv("FRED_API_KEY", "")
FRED_SERIES: dict[str, str] = {
    "yield_curve": "T10Y2Y",
    "recession_prob": "RECPROUSM156N",
    "cpi": "CPIAUCSL",
    "fed_funds": "FEDFUNDS",
}

SECTOR_ETF_MAP: dict[str, list[str] | None] = {
    "gold":          ["GDX", "GLD"],
    "energy":        ["XLE", "XOP"],
    "oil":           ["XLE", "USO"],
    "uranium":       ["URA"],
    "rare earth":    ["REMX"],
    "copper":        ["COPX"],
    "lithium":       ["LIT"],
    "water":         ["PHO"],
    "ai":            ["XLK", "BOTZ"],
    "tech":          ["XLK", "QQQ"],
    "robotics":      ["ROBO", "BOTZ"],
    "cybersecurity": ["CIBR"],
    "space":         ["ARKX"],
    "data center":   ["IGV"],
    "china":         ["KWEB", "FXI"],
    "japan":         ["EWJ"],
    "europe":        ["VGK"],
    "biotech":       ["XBI", "IBB"],
    "healthcare":    ["XLV"],
    "income":        ["VYM", "SCHD"],
    "consumer":      ["XLP"],
    "gaming":        ["ESPO"],
    "drone":         ["DRON"],
    "africa":        ["AFK"],
    "cannabis":      ["MSOS"],
    "stablecoin":    ["BITO"],
    "quantum":       ["QTUM"],
    "defence":       None,
    "defense":       None,
    "helium":        ["XLE"],
}

SCORING_WEIGHTS: dict[str, float] = {
    "base_rate": 0.20,
    "sector_rate": 0.15,
    "ticker_history": 0.15,
    "principles": 0.20,
    "macro": 0.15,
    "sector_context": 0.15,
}
MACRO_SCORE_DEFAULT: int = int(os.getenv("MACRO_SCORE", "50"))
