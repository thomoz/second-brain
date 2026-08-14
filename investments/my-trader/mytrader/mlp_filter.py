"""MLP (Master Limited Partnership) detection -- Shaun's standing preference is to
skip any ticker structured as an MLP (K-1 tax filing, UBTI complications in
retirement accounts) rather than run a full assessment against it. Detected from
yfinance's own longName/shortName, not a hardcoded ticker list -- unlike
scripts.ethical_filter's defense-contractor list, MLP structure is a fact about the
entity's legal form that's already present in the data, not a curated judgment call.

Confirmed live 2026-08-12 against EPD ("Enterprise Products Partners L.P.") and KRP
("Kimbell Royalty Partners, LP") -- both end their legal name in an L.P./LP suffix.

Deliberately does NOT exempt funds by quoteType=="ETF" -- an earlier version did, on
the theory that AMLP ("Alerian MLP ETF") shouldn't be flagged just for holding MLPs.
That theory was right for AMLP (it's a C-corp fund, which is why it issues a normal
1099), but the blanket ETF exemption was still wrong: CPER ("United States Copper
Index Fund, LP") is labeled quoteType=="ETF" by yfinance but is itself organized and
taxed as a limited partnership -- confirmed live 2026-08-14 via USCF's own K-1
information page, it genuinely issues a Schedule K-1 (Form 1065) to unitholders every
year, exactly the thing being screened for. Same pattern applies to the rest of the
USCF "United States X Fund" commodity-pool family (USO, UNG, etc.).

The end-anchored suffix regex already does the real work here without a quoteType
carve-out: AMLP's name ends in "ETF", not "LP" ("Alerian MLP ETF" only has "MLP" as a
substring in the middle), so it was never going to match regardless -- the ETF guard
was solving a problem the regex didn't actually have, while creating a real gap for
commodity-pool funds whose own legal name genuinely does end in ", LP".
"""

from __future__ import annotations

import re
from typing import Any

# Matches a trailing "L.P.", "LP", "L. P." etc. legal suffix, preceded by a comma,
# period, or whitespace separator -- e.g. "Partners L.P.", "Partners, LP".
_MLP_SUFFIX_RE = re.compile(r"[,.\s]L\.?\s?P\.?\s*$", re.IGNORECASE)


def detect(info: dict[str, Any]) -> str | None:
    """Returns the matched legal entity name if this ticker looks like an MLP,
    else None. Not gated on quoteType -- see module docstring for why a fund label
    alone (e.g. CPER) doesn't mean K-1-free."""
    name = info.get("longName") or info.get("shortName")
    if not name:
        return None
    if _MLP_SUFFIX_RE.search(name):
        return name
    return None
