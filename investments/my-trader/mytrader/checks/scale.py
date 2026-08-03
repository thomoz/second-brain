"""0(poor)-10(excellent) scale-hint helper for raw figures shown in check details.

Added 2026-08-03 at Shaun's request: a bare number like "ROE 30.6%" or "PE 21.8" means
nothing without a reference point for whether it's good or bad. Every anchor passed
into `scale()` below reuses a threshold that already exists in config.py, each
individually sourced from a stated investor-principle criterion or a named accounting
convention (same standard already applied to valuation.py/balance_sheet.py/
opportunity.py) -- this module adds no new signal or verdict, only a display label on
numbers the tool already treats as directionally good/bad.

Deliberately NOT applied to dividend trend (a %-change with no natural upper bound, not
a bounded level like PE/ROE) or expense ratio (no existing sourced threshold in
config.py to anchor against yet) -- flagged as a possible follow-up, not built here.
"""

from __future__ import annotations

_LABELS: tuple[tuple[int, str], ...] = (
    (10, "excellent"), (8, "very good"), (6, "good"),
    (4, "fair"), (2, "below average"), (0, "poor"),
)


def label_for_score(score: int) -> str:
    for floor, label in _LABELS:
        if score >= floor:
            return label
    return "poor"


def scale(value: float, good: float, bad: float) -> tuple[int, str]:
    """Map `value` onto a 0(bad)-10(good) scale, linearly interpolated between the two
    given reference points and clamped at both ends. `good`/`bad` can be given in
    either order -- e.g. lower-is-better metrics like PE pass good < bad."""
    if good == bad:
        return 5, label_for_score(5)
    frac = (value - bad) / (good - bad)
    frac = max(0.0, min(1.0, frac))
    score = round(frac * 10)
    return score, label_for_score(score)


def format_scale(value: float, good: float, bad: float) -> str:
    score, label = scale(value, good, bad)
    return f"{score}/10 — {label}"
