"""Lloyd's Market Association Joint War Committee page scraper -- no free API
exists for JWC's Listed Areas circulars (confirmed via research 2026-08-18;
the full circular archive lives behind lloydswordings.com's login), so this
scrapes the public committee page directly, mirroring openinsider.py's
direct-fetch style (requests + BeautifulSoup, headers dict, timeout,
try/except-returns-None-on-any-failure).

The page is narrative prose, not a structured feed -- confirmed live
2026-08-18 that the "Listed Areas" section runs from a "Listed Areas" heading
to a "Wordings" heading, referencing the current circular as a bare "JWLA-034"
string near the top of that section (not a stable per-region subheading --
region coverage under Listed Areas has changed shape before and will again).
Tracking the JWLA number is therefore the most robust signal available: it's
a discrete identifier that changes only when the JWC actually issues a new
Listed Areas circular, unlike the surrounding prose which could be edited at
any time for unrelated reasons (typos, formatting) without any real change in
risk assessment.
"""

from __future__ import annotations

import re

from . import config

_SECTION_START_HEADING = "Listed Areas"
_SECTION_END_HEADING = "Wordings"
_JWLA_PATTERN = re.compile(r"JWLA-(\d+)")


def fetch_listed_areas_snapshot() -> dict | None:
    """Returns {"jwla_number": "034", "section_text": <full Listed Areas
    section prose>} or None on any fetch/parse failure or if the page's
    structure no longer contains a recognizable Listed Areas section
    (heading text changed, page redesigned, etc.) -- callers must treat
    that as "unknown", not "no circular"."""
    import requests
    from bs4 import BeautifulSoup

    try:
        r = requests.get(
            config.GOAT_LMA_JWC_URL,
            headers={"User-Agent": config.GOAT_LMA_JWC_USER_AGENT},
            timeout=30,
        )
        if r.status_code != 200:
            return None
        soup = BeautifulSoup(r.text, "html.parser")
        lines = [line.strip() for line in soup.get_text("\n").split("\n") if line.strip()]
    except Exception:
        return None

    try:
        start = next(i for i, line in enumerate(lines) if line == _SECTION_START_HEADING)
        end = next(i for i, line in enumerate(lines[start + 1:], start + 1) if line == _SECTION_END_HEADING)
    except StopIteration:
        return None

    section_text = "\n".join(lines[start:end])
    numbers = [int(m) for m in _JWLA_PATTERN.findall(section_text)]
    jwla_number = f"{max(numbers):03d}" if numbers else None

    return {"jwla_number": jwla_number, "section_text": section_text}
