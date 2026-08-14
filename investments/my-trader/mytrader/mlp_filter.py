"""MLP (Master Limited Partnership) detection -- Shaun's standing preference is to
skip any ticker structured as an MLP (K-1 tax filing, UBTI complications in
retirement accounts) rather than run a full assessment against it. Detected from
yfinance's own longName/shortName, not a hardcoded ticker list -- unlike
scripts.ethical_filter's defense-contractor list, MLP structure is a fact about the
entity's legal form that's already present in the data, not a curated judgment call.

Confirmed live 2026-08-12 against EPD ("Enterprise Products Partners L.P.") and KRP
("Kimbell Royalty Partners, LP") -- both end their legal name in an L.P./LP suffix.

An ETF that merely holds MLPs (e.g. AMLP, "Alerian MLP ETF") is deliberately NOT
flagged -- AMLP itself is a fund (quoteType == "ETF"), not a partnership; its own
C-corp fund structure is precisely what lets it issue a normal 1099 instead of
passing K-1s through, the opposite of the thing being screened for.
"""

from __future__ import annotations

import re
from typing import Any

# Matches a trailing "L.P.", "LP", "L. P." etc. legal suffix, preceded by a comma,
# period, or whitespace separator -- e.g. "Partners L.P.", "Partners, LP".
_MLP_SUFFIX_RE = re.compile(r"[,.\s]L\.?\s?P\.?\s*$", re.IGNORECASE)


def detect(info: dict[str, Any]) -> str | None:
    """Returns the matched legal entity name if this ticker looks like an MLP,
    else None. Funds (quoteType == "ETF") are never flagged, regardless of name."""
    if info.get("quoteType") == "ETF":
        return None
    name = info.get("longName") or info.get("shortName")
    if not name:
        return None
    if _MLP_SUFFIX_RE.search(name):
        return name
    return None
