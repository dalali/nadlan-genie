from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import distinct, select
from sqlalchemy.orm import Session

from ..deps import get_db
from ..geo import SUPPORTED_CITIES
from ..models import Transaction
from ..schemas import CitiesOut

router = APIRouter(tags=["cities"])


@router.get("/cities", response_model=CitiesOut)
def list_cities(db: Session = Depends(get_db)) -> CitiesOut:
    """Return cities with at least one transaction. Falls back to the supported list."""
    rows = db.execute(select(distinct(Transaction.city)).order_by(Transaction.city)).all()
    cities = [r[0] for r in rows if r[0]]
    if not cities:
        cities = SUPPORTED_CITIES
    return CitiesOut(cities=cities)
