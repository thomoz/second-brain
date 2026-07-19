"""Price action — plain, always-shown recent price context.

Confirmed 2026-07-19, same day as the opportunity check rebuild: Shaun asked "why
didn't you tell me DG was up 11% in a month" — Find showed nothing because the
opportunity check only ever looks at a 3-month window, and DG's 3-month return was
flat (-0.1%) even though its 1-month return was +11.4% (the whole move happened
recently, inside the 3-month window, and then reversed or started from a dip).

Deliberately NOT a buy/sell signal — verdict is always "info", never "flag" or
"interesting". Graham's own principle file states "price momentum does not [matter]"
for value signals, and that's still true: this check doesn't judge whether a move is
good or bad, it just reports it, the same way the fx check reports AUD movement
without a verdict on whether it's good or bad.
"""

from __future__ import annotations

from . import CheckResult


def check(return_1mo: float | None, return_3mo: float | None) -> CheckResult:
    parts = []
    if return_1mo is not None:
        parts.append(f"1mo {return_1mo:+.1f}%")
    if return_3mo is not None:
        parts.append(f"3mo {return_3mo:+.1f}%")

    if not parts:
        return CheckResult(name="price_action", verdict="unknown", detail="No price history available")
    return CheckResult(name="price_action", verdict="info", detail=", ".join(parts))
