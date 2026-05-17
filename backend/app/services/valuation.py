from __future__ import annotations

import statistics
from dataclasses import dataclass
from datetime import date, timedelta

from geoalchemy2 import Geography
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..logging_setup import get_logger
from ..models import Listing, Transaction

log = get_logger(__name__)

# (radius_m, min_count, confidence_label) — try in order.
RADIUS_STEPS: list[tuple[int, int, str]] = [
    (500, 10, "high"),
    (1000, 5, "medium"),
    (2000, 3, "low"),
]
LOOKBACK_DAYS = 18 * 30  # 18 months


@dataclass
class Valuation:
    estimated_value: int
    median_ppsqm: float
    comparable_count: int
    radius_m: int
    confidence: str
    discount_percent: float


def _trimmed_median(values: list[float], trim_frac: float = 0.05) -> float:
    """Median after trimming `trim_frac` from each end (when there's enough data)."""
    if not values:
        raise ValueError("empty values")
    values = sorted(values)
    trim = int(len(values) * trim_frac)
    if trim and len(values) > 2 * trim:
        values = values[trim:-trim]
    return float(statistics.median(values))


def value_listing(listing: Listing, db: Session, *, today: date | None = None) -> Valuation | None:
    """Return a deterministic valuation for a listing, or None if insufficient comparables."""
    if listing.sqm is None or listing.rooms is None or not listing.price:
        return None
    if listing.geom is None:
        return None

    sqm = float(listing.sqm)
    rooms = float(listing.rooms)
    asking = int(listing.price)
    today_d = today or date.today()
    cutoff = today_d - timedelta(days=LOOKBACK_DAYS)

    base_q = (
        select(
            Transaction.price,
            Transaction.sqm,
        )
        .where(
            Transaction.property_type == listing.property_type,
            Transaction.rooms.between(rooms - 1, rooms + 1),
            Transaction.sqm.between(sqm * 0.8, sqm * 1.2),
            Transaction.deal_date >= cutoff,
            Transaction.sqm > 0,
            Transaction.price > 0,
        )
    )

    for radius_m, min_count, conf in RADIUS_STEPS:
        q = base_q.where(
            func.ST_DWithin(
                func.cast(Transaction.geom, Geography),
                func.cast(listing.geom, Geography),
                radius_m,
            )
        )
        rows = db.execute(q).all()
        if len(rows) < min_count:
            continue
        ppsqms = [float(p) / float(s) for (p, s) in rows if s and float(s) > 0]
        if len(ppsqms) < min_count:
            continue
        median_ppsqm = _trimmed_median(ppsqms)
        estimated_value = median_ppsqm * sqm
        if estimated_value <= 0:
            return None
        discount = (estimated_value - asking) / estimated_value
        return Valuation(
            estimated_value=int(round(estimated_value)),
            median_ppsqm=round(median_ppsqm, 2),
            comparable_count=len(ppsqms),
            radius_m=radius_m,
            confidence=conf,
            discount_percent=round(discount, 4),
        )

    return None
