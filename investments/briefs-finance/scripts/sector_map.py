"""Maps report sector themes to ETFs and fetches ETF historical prices."""

from __future__ import annotations

from datetime import date

from .config import SECTOR_ETF_MAP
from .prices import get_close_on_or_after


def resolve_sector_etf(inferred_sector: str | None) -> str | None:
    """Return primary ETF ticker for sector keyword (first in list), or None."""
    if not inferred_sector:
        return None
    key = inferred_sector.lower().replace("_", " ").strip()
    etfs = SECTOR_ETF_MAP.get(key)
    if etfs is None:
        return None
    return etfs[0] if etfs else None


def fetch_sector_prices(etf: str, rec_date: date) -> dict[str, float | None]:
    """Return ETF prices at rec date, +3m, +6m, +12m."""
    from dateutil.relativedelta import relativedelta

    def _price(delta_months: int) -> float | None:
        target = rec_date + relativedelta(months=delta_months)
        return get_close_on_or_after(etf, target)

    return {
        "etf_price_at_rec": get_close_on_or_after(etf, rec_date),
        "etf_price_3m": _price(3),
        "etf_price_6m": _price(6),
        "etf_price_12m": _price(12),
    }
